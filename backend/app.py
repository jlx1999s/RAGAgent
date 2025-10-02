from fastapi import FastAPI, UploadFile, File, Query, Body
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio, time, os, random, string, json
from typing import Optional, Dict, Any, List
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional

# 加载环境变量并配置Hugging Face镜像
from dotenv import load_dotenv
load_dotenv(override=True)

# 配置Hugging Face镜像
os.environ['HF_ENDPOINT'] = os.getenv('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ['HUGGINGFACE_HUB_CACHE'] = os.getenv('HUGGINGFACE_HUB_CACHE', '/tmp/huggingface_cache')
# 设置transformers和timm使用镜像
os.environ['TRANSFORMERS_CACHE'] = os.getenv('HUGGINGFACE_HUB_CACHE', '/tmp/huggingface_cache')
os.environ['TIMM_CACHE_DIR'] = os.getenv('HUGGINGFACE_HUB_CACHE', '/tmp/huggingface_cache')

from fastapi import BackgroundTasks
from services.pdf_service import (
    save_upload, run_full_parse_pipeline,
    original_pdf_path, dir_original_pages, dir_parsed_pages, markdown_output
)
from services.index_service import build_faiss_index, search_faiss
from fastapi.responses import StreamingResponse, JSONResponse
from services.rag_service import retrieve, answer_stream, clear_history

app = FastAPI(
    title="九天老师公开课：多模态RAG系统API",
    version="1.0.0",
    description="九天老师公开课《多模态RAG系统开发实战》后端API。"
)

# 允许前端本地联调
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 课堂演示方便，生产请收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

# ---------------- 内存态存储（教学Mock） ----------------
# 支持多个PDF文件的状态跟踪
pdf_files: Dict[str, Dict[str, Any]] = {}  # fileId -> {name, pages, status, progress}
citations: Dict[str, Dict[str, Any]] = {}   # citationId -> { fileId, page, snippet, bbox, previewUrl }

# ---------------- 工具函数 ----------------
def rid(prefix: str) -> str:
    return f"{prefix}_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

def now_ts() -> int:
    return int(time.time())

def err(code: str, message: str) -> Dict[str, Any]:
    return {"error": {"code": code, "message": message}, "requestId": rid("req"), "ts": now_ts()}

# ---------------- Pydantic 模型（契约） ----------------
class ChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None
    pdfFileId: Optional[str] = None

# ---------------- Health ----------------
@app.get(f"{API_PREFIX}/health", tags=["Health"])
async def health():
    return {"ok": True, "version": "1.0.0"}

# ---------------- Chat（SSE，POST 返回 event-stream） ----------------
class ChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None
    pdfFileId: Optional[str] = None

@app.post(f"{API_PREFIX}/chat", tags=["Chat"])
async def chat_stream(req: ChatRequest):
    """
    SSE 事件：token | citation | done | error
    """
    async def gen():
        try:
            question = (req.message or "").strip()
            session_id = (req.sessionId or "default").strip()  # 默认单会话
            file_id = (req.pdfFileId or "").strip()
            
            # 调试日志
            print(f"[DEBUG] 收到聊天请求:")
            print(f"  - message: {req.message}")
            print(f"  - sessionId: {session_id}")
            print(f"  - pdfFileId: {file_id}")
            print(f"  - 当前PDF文件状态: {list(pdf_files.keys())}")

            citations, context_text = [], ""
            branch = "no_context"
            if file_id:
                try:
                    citations, context_text = await retrieve(question, file_id)
                    branch = "with_context" if context_text else "no_context"
                except FileNotFoundError:
                    branch = "no_context"

            # 先推送引用（若有）
            if branch == "with_context" and citations:
                for c in citations:
                    # 将citation存储到全局字典中
                    citation_id = c.get("citation_id")
                    if citation_id:
                        globals()["citations"][citation_id] = c
                    yield "event: citation\n"
                    yield f"data: {json.dumps(c, ensure_ascii=False)}\n\n"

            # 再推送 token 流（内部会写入历史）
            async for evt in answer_stream(
                question=question,
                citations=citations,
                context_text=context_text,
                branch=branch,
                session_id=session_id
            ):
                if evt["type"] == "token":
                    yield "event: token\n"
                    # 注意：这里确保 data 是合法 JSON 字符串
                    text = evt["data"].replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
                    yield f'data: {{"text":"{text}"}}\n\n'
                elif evt["type"] == "citation":
                    yield "event: citation\n"
                    yield f"data: {json.dumps(evt['data'], ensure_ascii=False)}\n\n"
                elif evt["type"] == "done":
                    used = "true" if evt["data"].get("used_retrieval") else "false"
                    yield "event: done\n"
                    yield f"data: {{\"used_retrieval\": {used}}}\n\n"

        except Exception as e:
            yield "event: error\n"
            esc = str(e).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
            yield f'data: {{"message":"{esc}"}}\n\n'

    headers = {"Cache-Control": "no-cache, no-transform", "Connection": "keep-alive"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)

# ---------------- Chat: 清除对话 ----------------
class ClearChatRequest(BaseModel):
    sessionId: Optional[str] = None

@app.post(f"{API_PREFIX}/chat/clear", tags=["Chat"])
async def chat_clear(req: ClearChatRequest):
    sid = (req.sessionId or "default").strip()
    clear_history(sid)
    return {"ok": True, "sessionId": sid, "cleared": True}


# ---------------- PDF: 上传（仅单文件，直接替换） ----------------

@app.post(f"{API_PREFIX}/pdf/upload", tags=["PDF"])
async def pdf_upload(file: UploadFile = File(...), replace: Optional[bool] = True):
    if not file:
        return JSONResponse(err("NO_FILE", "缺少文件"), status_code=400)
    # 生成新的 fileId
    fid = rid("f")
    saved = save_upload(fid, await file.read(), file.filename)
    # 将文件信息存储到多文件字典中
    pdf_files[fid] = {
        "name": saved["name"],
        "pages": saved["pages"],
        "status": "idle",
        "progress": 0
    }
    return saved

# ---------------- PDF: 触发解析 ----------------
@app.post(f"{API_PREFIX}/pdf/parse", tags=["PDF"])
async def pdf_parse(payload: Dict[str, Any] = Body(...), bg: BackgroundTasks = None):
    file_id = payload.get("fileId")
    if file_id not in pdf_files:
        return JSONResponse(err("FILE_NOT_FOUND", "未找到该文件"), status_code=400)

    pdf_files[file_id]["status"] = "parsing"
    pdf_files[file_id]["progress"] = 5

    def _job():
        try:
            # 20 → 60 → 100 三阶段进度示意
            pdf_files[file_id]["progress"] = 20
            run_full_parse_pipeline(file_id)   # 真解析
            pdf_files[file_id]["progress"] = 100
            pdf_files[file_id]["status"] = "ready"
        except Exception as e:
            pdf_files[file_id]["status"] = "error"
            pdf_files[file_id]["progress"] = 0
            print("Parse error:", e)

    if bg is not None:
        bg.add_task(_job)
    else:
        _job()

    return {"jobId": rid("j")}

# ---------------- PDF: 状态 ----------------
@app.get(f"{API_PREFIX}/pdf/status", tags=["PDF"])
async def pdf_status(fileId: str = Query(...)):
    # 检查文件是否存在于内存状态中
    if fileId in pdf_files:
        resp = {"status": pdf_files[fileId]["status"], "progress": pdf_files[fileId]["progress"]}
        if pdf_files[fileId]["status"] == "error":
            resp["errorMsg"] = "解析失败"
        return resp
    
    # 如果内存中没有，检查文件系统中是否存在已解析的文件
    from services.pdf_service import original_pdf_path, markdown_output
    pdf_path = original_pdf_path(fileId)
    md_path = markdown_output(fileId)
    
    if pdf_path.exists():
        if md_path.exists():
            # 文件存在且已解析完成
            return {"status": "ready", "progress": 100}
        else:
            # 文件存在但未解析
            return {"status": "idle", "progress": 0}
    else:
        # 文件不存在
        return {"status": "idle", "progress": 0}

# ---------------- PDF: 页面图 ----------------
@app.get(f"{API_PREFIX}/pdf/page", tags=["PDF"])
async def pdf_page(
    fileId: str = Query(...),
    page: int = Query(..., ge=1),
    type: str = Query(..., regex="^(original|parsed)$")
):
    # 检查文件是否存在
    from services.pdf_service import original_pdf_path, markdown_output
    pdf_path = original_pdf_path(fileId)
    if not pdf_path.exists():
        return JSONResponse(status_code=404, content=None)

    # 对于parsed类型，检查是否已解析完成
    if type == "parsed":
        md_path = markdown_output(fileId)
        if not md_path.exists():
            # 未解析就请求 parsed 页，返回 204
            return JSONResponse(status_code=204, content=None)

    base = dir_original_pages(fileId) if type == "original" else dir_parsed_pages(fileId)
    img = base / f"page-{page:04d}.png"
    if not img.exists():
        return JSONResponse(err("PAGE_NOT_FOUND", "页面不存在或未渲染"), status_code=404)
    return FileResponse(str(img), media_type="image/png")

# ---------------- PDF: 图片文件 ----------------
@app.get(f"{API_PREFIX}/pdf/images", tags=["PDF"])
async def pdf_images(
    fileId: str = Query(...),
    imagePath: str = Query(...)
):
    """获取PDF解析后的图片文件"""
    # 检查文件是否存在
    from services.pdf_service import original_pdf_path, images_dir
    pdf_path = original_pdf_path(fileId)
    if not pdf_path.exists():
        return JSONResponse(status_code=404, content=None)

    # 构建图片文件的完整路径
    image_file = images_dir(fileId) / imagePath
    
    if not image_file.exists():
        return JSONResponse(err("IMAGE_NOT_FOUND", "图片文件不存在"), status_code=404)
    
    # 检查文件是否在images目录内（安全考虑）
    try:
        image_file.resolve().relative_to(images_dir(fileId).resolve())
    except ValueError:
        return JSONResponse(err("INVALID_PATH", "无效的图片路径"), status_code=400)
    
    return FileResponse(str(image_file), media_type="image/png")

# ---------------- PDF: 引用片段 ----------------
@app.get(f"{API_PREFIX}/pdf/chunk", tags=["PDF"])
async def pdf_chunk(citationId: str = Query(...)):
    ref = citations.get(citationId)
    if not ref:
        return JSONResponse(err("NOT_FOUND", "无该引用"), status_code=404)
    return ref

class BuildIndexRequest(BaseModel):
    fileId: str

class SearchRequest(BaseModel):
    fileId: str
    query: str
    k: Optional[int] = 5

@app.post(f"{API_PREFIX}/index/build", tags=["Index"])
async def index_build(req: BuildIndexRequest):
    # 检查文件是否存在
    if req.fileId not in pdf_files:
        # 如果内存中没有，检查文件系统中是否存在已解析的文件
        from services.pdf_service import original_pdf_path, markdown_output
        pdf_path = original_pdf_path(req.fileId)
        md_path = markdown_output(req.fileId)
        
        if not pdf_path.exists():
            raise HTTPException(status_code=400, detail="FILE_NOT_FOUND")
        if not md_path.exists():
            raise HTTPException(status_code=409, detail="NEED_PARSE_FIRST")
    else:
        # 检查文件状态
        if pdf_files[req.fileId]["status"] != "ready":
            raise HTTPException(status_code=409, detail="NEED_PARSE_FIRST")

    out = build_faiss_index(req.fileId)
    if not out.get("ok"):
        return JSONResponse(err(out.get("error", "INDEX_BUILD_ERROR"), "索引构建失败"), status_code=500)
    return {"ok": True, "chunks": out["chunks"]}

@app.post(f"{API_PREFIX}/index/search", tags=["Index"])
async def index_search(req: SearchRequest):
    out = search_faiss(req.fileId, req.query, req.k or 5)
    if not out.get("ok"):
        code = out.get("error", "INDEX_NOT_FOUND")
        return JSONResponse(err(code, "请先构建索引"), status_code=400)
    return out