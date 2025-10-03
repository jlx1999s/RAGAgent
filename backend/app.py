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
from services.enhanced_index_service import enhanced_index_service, build_medical_index, search_medical_knowledge
from services.enhanced_rag_service import (
    enhanced_rag_service, medical_retrieve, medical_answer_stream,
    get_history, append_history, clear_history
)
from services.medical_knowledge_graph import kg_service
from services.medical_association_service import medical_association_service
from services.medical_intent_service import recognize_medical_intent
from services.qwen_intent_service import recognize_qwen_medical_intent
from services.smart_intent_service import recognize_smart_medical_intent
from services.medical_taxonomy import MedicalDepartment, DocumentType, DiseaseCategory
from fastapi.responses import StreamingResponse, JSONResponse
# 原始RAG服务保留用于兼容性
from services.rag_service import retrieve, answer_stream

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
    out = search_faiss(req.fileId, req.query, req.k)
    return out

# ============== 医疗索引相关API ==============

class MedicalIndexRequest(BaseModel):
    fileId: str
    department: str  # 医疗科室
    documentType: str  # 文档类型
    diseaseCategory: Optional[str] = None  # 疾病分类
    customMetadata: Optional[Dict[str, Any]] = None  # 自定义元数据
    markdownContent: Optional[str] = None  # 直接传递的markdown内容

class MedicalSearchRequest(BaseModel):
    query: str
    k: Optional[int] = 10
    department: Optional[str] = None
    documentType: Optional[str] = None
    diseaseCategory: Optional[str] = None
    scoreThreshold: Optional[float] = 0.0

class SymptomSearchRequest(BaseModel):
    symptoms: List[str]
    k: Optional[int] = 10

class DrugSearchRequest(BaseModel):
    drugName: str
    k: Optional[int] = 10

# 医疗RAG相关数据模型
class MedicalChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None
    department: Optional[str] = None
    documentType: Optional[str] = None
    diseaseCategory: Optional[str] = None
    enableSafetyCheck: Optional[bool] = True
    intentRecognitionMethod: Optional[str] = "smart"  # "smart", "qwen" 或 "keyword"

class SymptomAnalysisRequest(BaseModel):
    symptoms: List[str]
    sessionId: Optional[str] = None

class DrugInteractionRequest(BaseModel):
    drugs: List[str]
    sessionId: Optional[str] = None

# 知识图谱相关数据模型
class EntitySearchRequest(BaseModel):
    entityName: str

class KnowledgeGraphUpdateRequest(BaseModel):
    documents: List[str]

# 医疗关联查询相关模型
class AssociationSearchRequest(BaseModel):
    query: str
    associationTypes: Optional[List[str]] = None
    confidenceThreshold: Optional[float] = 0.5
    maxResults: Optional[int] = 20

class EnhancedSymptomAnalysisRequest(BaseModel):
    symptoms: List[str]
    sessionId: Optional[str] = None
    includeAssociations: Optional[bool] = True

class EnhancedDrugInteractionRequest(BaseModel):
    drugs: List[str]
    sessionId: Optional[str] = None
    includeAssociations: Optional[bool] = True

@app.post(f"{API_PREFIX}/medical/index/build", tags=["Medical Index"])
async def medical_index_build(req: MedicalIndexRequest):
    """构建医疗文档索引"""
    try:
        # 如果提供了markdown内容，先保存到文件
        if req.markdownContent:
            from services.index_service import DATA_ROOT
            import os
            
            # 创建文件目录
            file_dir = os.path.join(DATA_ROOT, req.fileId)
            os.makedirs(file_dir, exist_ok=True)
            
            # 保存markdown内容到output.md
            markdown_file = os.path.join(file_dir, "output.md")
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(req.markdownContent)
        
        result = build_medical_index(
            file_id=req.fileId,
            department=req.department,
            document_type=req.documentType,
            disease_category=req.diseaseCategory,
            custom_metadata=req.customMetadata
        )
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

# 医疗关联查询API端点
@app.post(f"{API_PREFIX}/medical/associations/search", tags=["Medical Associations"])
async def search_medical_associations(req: AssociationSearchRequest):
    """搜索医疗关联"""
    try:
        from services.medical_association_service import AssociationType
        
        # 转换关联类型
        association_types = None
        if req.associationTypes:
            association_types = []
            for type_str in req.associationTypes:
                try:
                    association_types.append(AssociationType(type_str))
                except ValueError:
                    continue
        
        result = medical_association_service.find_associations(
            query=req.query,
            association_types=association_types,
            confidence_threshold=req.confidenceThreshold,
            max_results=req.maxResults
        )
        
        return {
            "ok": True,
            "query": result.query,
            "total_count": result.total_count,
            "confidence_threshold": result.confidence_threshold,
            "associations": [
                {
                    "source": assoc.source,
                    "target": assoc.target,
                    "type": assoc.association_type.value,
                    "confidence": assoc.confidence,
                    "frequency": assoc.frequency,
                    "evidence": assoc.evidence[:2] if assoc.evidence else []
                }
                for assoc in result.associations
            ],
            "search_metadata": result.search_metadata
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/medical/analyze/symptoms-enhanced", tags=["Medical Associations"])
async def analyze_symptoms_enhanced(req: EnhancedSymptomAnalysisRequest):
    """增强症状分析（包含关联信息）"""
    try:
        result = await enhanced_rag_service.enhanced_symptom_analysis(req.symptoms)
        
        if result.get("success"):
            return {
                "ok": True,
                "symptoms": req.symptoms,
                "analysis": result.get("symptom_analysis", {}),
                "citations": result.get("citations", []),
                "context_text": result.get("context_text", ""),
                "metadata": result.get("metadata", {})
            }
        else:
            return {
                "ok": False,
                "error": result.get("error", "分析失败"),
                "symptoms": req.symptoms
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/medical/analyze/drug-interactions-enhanced", tags=["Medical Associations"])
async def analyze_drug_interactions_enhanced(req: EnhancedDrugInteractionRequest):
    """增强药物相互作用分析（包含关联信息）"""
    try:
        result = await enhanced_rag_service.drug_interaction_search(req.drugs)
        
        if result.get("success"):
            return {
                "ok": True,
                "drugs": req.drugs,
                "analysis": result.get("drug_interaction_analysis", {}),
                "citations": result.get("citations", []),
                "context_text": result.get("context_text", ""),
                "metadata": result.get("metadata", {})
            }
        else:
            return {
                "ok": False,
                "error": result.get("error", "分析失败"),
                "drugs": req.drugs
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get(f"{API_PREFIX}/medical/associations/statistics", tags=["Medical Associations"])
async def get_association_statistics():
    """获取医疗关联统计信息"""
    try:
        stats = await medical_association_service.get_association_statistics()
        return {
            "ok": True,
            "statistics": stats
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/medical/associations/update", tags=["Medical Associations"])
async def update_associations_from_documents(req: KnowledgeGraphUpdateRequest):
    """从文档更新医疗关联知识库"""
    try:
        result = await medical_association_service.update_associations_from_documents(req.documents)
        return {
            "ok": True,
            "update_result": result
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/medical/search", tags=["Medical Search"])
async def medical_search(req: MedicalSearchRequest):
    """搜索医疗文档"""
    try:
        result = enhanced_index_service.search_medical_documents(
            query=req.query,
            k=req.k,
            department=req.department,
            document_type=req.documentType,
            disease_category=req.diseaseCategory,
            score_threshold=req.scoreThreshold
        )
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/medical/search/symptoms", tags=["Medical Search"])
async def medical_search_by_symptoms(req: SymptomSearchRequest):
    """基于症状搜索相关疾病和治疗方案"""
    try:
        result = enhanced_index_service.search_by_symptoms(
            symptoms=req.symptoms,
            k=req.k
        )
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/medical/search/drug", tags=["Medical Search"])
async def medical_search_drug_interactions(req: DrugSearchRequest):
    """搜索药物相互作用和副作用信息"""
    try:
        result = enhanced_index_service.search_drug_interactions(
            drug_name=req.drugName,
            k=req.k
        )
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get(f"{API_PREFIX}/medical/statistics", tags=["Medical Index"])
async def medical_statistics():
    """获取医疗向量存储统计信息"""
    try:
        result = enhanced_index_service.get_vector_store_statistics()
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get(f"{API_PREFIX}/medical/departments", tags=["Medical Index"])
async def get_medical_departments():
    """获取支持的医疗科室列表"""
    from services.medical_taxonomy import MedicalDepartment
    return {
        "ok": True,
        "departments": [dept.value for dept in MedicalDepartment]
    }

@app.get(f"{API_PREFIX}/medical/document-types", tags=["Medical Index"])
async def get_document_types():
    """获取支持的文档类型列表"""
    from services.medical_taxonomy import DocumentType
    return {
        "ok": True,
        "document_types": [doc_type.value for doc_type in DocumentType]
    }

@app.get(f"{API_PREFIX}/medical/disease-categories", tags=["Medical Index"])
async def get_disease_categories():
    """获取支持的疾病分类列表"""
    from services.medical_taxonomy import DiseaseCategory
    return {
        "ok": True,
        "disease_categories": [category.value for category in DiseaseCategory]
    }

class DeleteIndexRequest(BaseModel):
    department: str
    documentType: str
    diseaseCategory: Optional[str] = None

@app.post(f"{API_PREFIX}/medical/index/delete", tags=["Medical Index"])
async def medical_index_delete(req: DeleteIndexRequest):
    """删除指定的医疗文档索引"""
    try:
        result = enhanced_index_service.delete_document_index(
            department=req.department,
            document_type=req.documentType,
            disease_category=req.diseaseCategory
        )
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/medical/index/optimize", tags=["Medical Index"])
async def medical_index_optimize():
    """优化医疗向量存储"""
    try:
        result = enhanced_index_service.optimize_vector_stores()
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ============== 医疗RAG端点 ==============

@app.post(f"{API_PREFIX}/medical/chat", tags=["Medical RAG"])
async def medical_chat_stream(req: MedicalChatRequest):
    """
    医疗问答聊天（SSE流式）
    集成安全审核和质量评估
    """
    async def gen():
        try:
            question = (req.message or "").strip()
            session_id = (req.sessionId or "medical_default").strip()
            
            if not question:
                yield f"data: {json.dumps({'type': 'error', 'data': {'message': '问题不能为空'}})}\n\n"
                return
            
            # 智能意图识别：如果用户没有指定参数，则自动推断
            if not req.department and not req.documentType and not req.diseaseCategory:
                # 根据用户选择的方法进行意图识别
                intent_method = req.intentRecognitionMethod or "smart"
                
                if intent_method == "smart":
                    # 使用智能意图识别（推荐）
                    intent = recognize_smart_medical_intent(question)
                    department = intent.get('department')
                    document_type = intent.get('document_type')
                    disease_category = intent.get('disease_category')
                    confidence = intent.get('confidence', 0.0)
                    reasoning = intent.get('reasoning', '')
                    method = intent.get('method', intent_method)
                elif intent_method == "qwen":
                    # 使用原始Qwen意图识别
                    intent = recognize_qwen_medical_intent(question)
                    department = intent.get('department')
                    document_type = intent.get('document_type')
                    disease_category = intent.get('disease_category')
                    confidence = intent.get('confidence', 0.0)
                    reasoning = intent.get('reasoning', '')
                    method = intent.get('method', intent_method)
                else:
                    # 使用关键词意图识别
                    intent = recognize_medical_intent(question)
                    department = intent.department
                    document_type = intent.document_type
                    disease_category = intent.disease_category
                    confidence = intent.confidence
                    reasoning = intent.reasoning
                    method = "keyword"
                
                # 发送意图识别结果
                intent_data = {
                    'department': department, 
                    'document_type': document_type, 
                    'disease_category': disease_category, 
                    'confidence': confidence, 
                    'reasoning': reasoning,
                    'method': method
                }
                yield f"data: {json.dumps({'type': 'intent_recognition', 'data': intent_data})}\n\n"
            else:
                # 使用用户指定的参数
                department = req.department
                document_type = req.documentType
                disease_category = req.diseaseCategory
            
            # 类型转换：将字符串转换为枚举类型
            department_enum = None
            document_type_enum = None
            disease_category_enum = None
            
            # 科室映射和转换
            if department:
                try:
                    # 科室映射 - 基于实际文档分布进行映射
                    department_mapping = {
                        "呼吸内科": "呼吸科",
                        "心内科": "心血管科",
                        "消化内科": "消化科",
                        "内分泌内科": "内分泌科",
                        "肾脏内科": "肾内科",
                        "预防科": "内科",
                        "保健科": "内科"
                    }
                    
                    # 使用智能意图识别的结果，不再进行硬编码映射
                    mapped_dept = department_mapping.get(department, department)
                    department_enum = MedicalDepartment(mapped_dept)
                except ValueError:
                    print(f"[WARNING] 无效的科室参数: {department}")
                    department_enum = None
            
            # 文档类型映射和转换
            if document_type:
                try:
                    # 文档类型映射
                    doctype_mapping = {
                        "预防指南": "临床指南",
                        "诊疗指南": "临床指南",
                        "治疗指南": "临床指南",
                        "护理规范": "护理手册",
                        "康复指导": "护理手册",
                        "急救指南": "急救流程",
                        "保健指南": "临床指南",
                        "健康指南": "临床指南"
                    }
                    mapped_doctype = doctype_mapping.get(document_type, document_type)
                    document_type_enum = DocumentType(mapped_doctype)
                except ValueError:
                    print(f"[WARNING] 无效的文档类型参数: {document_type}")
                    document_type_enum = None
            
            # 疾病分类映射和转换
            if disease_category:
                try:
                    # 疾病类别映射 - 修复错误的映射逻辑
                    # 注意：向量存储的实际结构是 呼吸科_临床指南_感染性疾病
                    # 所以不应该将"感染性疾病"映射为其他类别
                    disease_category_enum = DiseaseCategory(disease_category)
                except ValueError:
                    print(f"[WARNING] 无效的疾病分类参数: {disease_category}")
                    disease_category_enum = None
            
            # 医疗检索
            citations, context_text, metadata = await medical_retrieve(
                question=question,
                department=department_enum,
                document_type=document_type_enum,
                disease_category=disease_category_enum
            )
            
            # 将引用存储到全局字典中，以便 /pdf/chunk 端点可以访问
            if citations:
                for c in citations:
                    citation_id = c.get("citation_id")
                    if citation_id:
                        globals()["citations"][citation_id] = c
            
            # 流式生成回答
            async for event in medical_answer_stream(
                question=question,
                citations=citations,
                context_text=context_text,
                metadata=metadata,
                session_id=session_id,
                enable_safety_check=req.enableSafetyCheck
            ):
                yield f"data: {json.dumps(event)}\n\n"
                
        except Exception as e:
            print(f"[ERROR] medical_chat_stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"
    
    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")

@app.post(f"{API_PREFIX}/medical/chat/clear", tags=["Medical RAG"])
async def medical_chat_clear(req: ClearChatRequest):
    """清除医疗聊天历史"""
    try:
        session_id = (req.sessionId or "medical_default").strip()
        clear_history(session_id)
        return {"ok": True, "message": f"Medical chat history cleared for session: {session_id}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/medical/analyze/symptoms", tags=["Medical RAG"])
async def analyze_symptoms(req: SymptomAnalysisRequest):
    """症状分析和疾病推荐"""
    try:
        if not req.symptoms:
            return {"ok": False, "error": "症状列表不能为空"}
        
        result = await enhanced_rag_service.symptom_based_search(req.symptoms)
        return {"ok": True, "data": result}
        
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/medical/analyze/drug-interactions", tags=["Medical RAG"])
async def analyze_drug_interactions(req: DrugInteractionRequest):
    """药物相互作用分析"""
    try:
        if not req.drugs:
            return {"ok": False, "error": "药物列表不能为空"}
        
        result = await enhanced_rag_service.drug_interaction_search(req.drugs)
        return {"ok": True, "data": result}
        
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get(f"{API_PREFIX}/medical/chat/history", tags=["Medical RAG"])
async def get_medical_chat_history(sessionId: str = Query("medical_default")):
    """获取医疗聊天历史"""
    try:
        history = get_history(sessionId)
        return {"ok": True, "data": {"sessionId": sessionId, "history": history}}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get(f"{API_PREFIX}/medical/safety/review-stats", tags=["Medical RAG"])
async def get_safety_review_stats():
    """获取安全审核统计信息"""
    try:
        stats = await enhanced_rag_service.review_service.get_review_statistics()
        return {"ok": True, "data": stats}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# 知识图谱相关API端点
@app.post(f"{API_PREFIX}/knowledge-graph/entity/search", tags=["Knowledge Graph"])
async def search_entity_relationships(req: EntitySearchRequest):
    """查找实体关系"""
    try:
        relationships = await kg_service.find_entity_relationships(req.entityName)
        return {"ok": True, "data": relationships}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get(f"{API_PREFIX}/knowledge-graph/statistics", tags=["Knowledge Graph"])
async def get_knowledge_graph_statistics():
    """获取知识图谱统计信息"""
    try:
        stats = await kg_service.get_knowledge_graph_stats()
        return {"ok": True, "data": stats}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/knowledge-graph/update", tags=["Knowledge Graph"])
async def update_knowledge_graph(req: KnowledgeGraphUpdateRequest):
    """从文档更新知识图谱"""
    try:
        result = await kg_service.update_kg_from_documents(req.documents)
        return {"ok": True, "data": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/knowledge-graph/enhance-query", tags=["Knowledge Graph"])
async def enhance_query_with_kg(req: ChatRequest):
    """使用知识图谱增强查询"""
    try:
        enhancement = await kg_service.enhance_query_with_kg(req.message)
        return {"ok": True, "data": enhancement}
    except Exception as e:
        return {"ok": False, "error": str(e)}