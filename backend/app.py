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

# 解决OpenMP冲突问题，防止FAISS加载时出现OMP错误
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

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
from services.state_store import (
    set_pdf_state, get_pdf_state, update_pdf_state,
    set_citation, get_citation,
    redis_health
)
from services.index_service import build_faiss_index, search_faiss
from services.enhanced_index_service import enhanced_index_service, build_medical_index, search_medical_knowledge
from services.enhanced_rag_service import (
    enhanced_rag_service, medical_retrieve, medical_answer_stream,
    get_history, append_history, clear_history
)
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROM_ENABLED = True
except Exception:
    PROM_ENABLED = False
    Counter = Histogram = Gauge = None  # type: ignore
    def generate_latest():  # type: ignore
        return b""
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"  # type: ignore
from fastapi.responses import Response
from services.medical_knowledge_graph import kg_service
from services.medical_association_service import medical_association_service
from services.medical_intent_service import recognize_medical_intent
from services.qwen_intent_service import recognize_qwen_medical_intent
from services.smart_intent_service import recognize_medical_intent as recognize_smart_medical_intent
from services.medical_taxonomy import MedicalDepartment, DocumentType, DiseaseCategory
from fastapi.responses import StreamingResponse, JSONResponse
# 原始RAG服务保留用于兼容性
# 已移除通用聊天依赖，保留医疗相关服务

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

# ---------------- 状态存储（Redis/内存回退） ----------------
# 统一通过 services.state_store 读写 pdf 状态与 citation 缓存

# ---------------- 指标定义与中间件 ----------------
if PROM_ENABLED:
    REQUEST_COUNT = Counter(
        "http_requests_total", "Total HTTP requests", ["method", "endpoint", "http_status"]
    )
    REQUEST_LATENCY = Histogram(
        "http_request_duration_seconds", "HTTP request latency", ["method", "endpoint"]
    )

    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        latency = time.perf_counter() - start
        endpoint = request.url.path
        REQUEST_COUNT.labels(request.method, endpoint, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(request.method, endpoint).observe(latency)
        return response

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
    """统一健康检查：包含基本版本与 Redis 健康"""
    r = await redis_health()
    return {"ok": True, "version": "1.0.0", "redis": r}

@app.get("/metrics")
async def metrics():
    """Prometheus 指标暴露端点"""
    if not PROM_ENABLED:
        return Response(status_code=204)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ---------------- 已移除通用聊天端点 ----------------
class ClearChatRequest(BaseModel):
    sessionId: Optional[str] = None


# ---------------- PDF: 上传（仅单文件，直接替换） ----------------

@app.post(f"{API_PREFIX}/pdf/upload", tags=["PDF"])
async def pdf_upload(file: UploadFile = File(...), replace: Optional[bool] = True):
    if not file:
        return JSONResponse(err("NO_FILE", "缺少文件"), status_code=400)
    # 生成新的 fileId
    fid = rid("f")
    saved = save_upload(fid, await file.read(), file.filename)
    # 写入状态存储
    await set_pdf_state(fid, {
        "name": saved["name"],
        "pages": saved["pages"],
        "status": "idle",
        "progress": 0
    })
    return saved

# ---------------- PDF: 触发解析 ----------------
@app.post(f"{API_PREFIX}/pdf/parse", tags=["PDF"])
async def pdf_parse(payload: Dict[str, Any] = Body(...), bg: BackgroundTasks = None):
    file_id = payload.get("fileId")
    state = await get_pdf_state(file_id)
    if not state:
        return JSONResponse(err("FILE_NOT_FOUND", "未找到该文件"), status_code=400)
    await update_pdf_state(file_id, {"status": "parsing", "progress": 5})

    async def _job():
        try:
            # 20 → 100 进度示意
            await update_pdf_state(file_id, {"progress": 20})
            # 运行解析管线（在线程池中避免阻塞事件循环）
            await asyncio.to_thread(run_full_parse_pipeline, file_id)
            await update_pdf_state(file_id, {"progress": 100, "status": "ready"})
        except Exception as e:
            await update_pdf_state(file_id, {"status": "error", "progress": 0})
            print("Parse error:", e)

    if bg is not None:
        bg.add_task(_job)
    else:
        await _job()

    return {"jobId": rid("j")}

# ---------------- PDF: 状态 ----------------
@app.get(f"{API_PREFIX}/pdf/status", tags=["PDF"])
async def pdf_status(fileId: str = Query(...)):
    # 优先从状态存储读取
    state = await get_pdf_state(fileId)
    if state:
        resp = {"status": state.get("status", "idle"), "progress": state.get("progress", 0)}
        if resp["status"] == "error":
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
    ref = await get_citation(citationId)
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
    state = await get_pdf_state(req.fileId)
    if not state:
        # 状态存储没有，再检查文件系统存在性
        from services.pdf_service import original_pdf_path, markdown_output
        pdf_path = original_pdf_path(req.fileId)
        md_path = markdown_output(req.fileId)
        if not pdf_path.exists():
            raise HTTPException(status_code=400, detail="FILE_NOT_FOUND")
        if not md_path.exists():
            raise HTTPException(status_code=409, detail="NEED_PARSE_FIRST")
    else:
        # 有状态，必须 ready 才能构建索引
        if state.get("status") != "ready":
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
    """获取医疗索引统计信息"""
    try:
        result = enhanced_index_service.get_vector_store_statistics()
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get(f"{API_PREFIX}/medical/knowledge-base/details", tags=["Medical Index"])
async def get_knowledge_base_details():
    """获取知识库详细信息"""
    try:
        result = enhanced_index_service.get_vector_store_statistics()
        if result.get("ok"):
            # 转换格式以匹配前端期望的数据结构
            stores = []
            store_details = result.get("store_details", {})
            for store_key, details in store_details.items():
                stores.append({
                    "id": store_key,
                    "department": details.get("department"),
                    "document_type": details.get("document_type"),
                    "disease_category": details.get("disease_category"),
                    "document_count": details.get("document_count", 0),
                    "created_at": details.get("created_at"),
                    "last_updated": details.get("last_updated"),
                    "is_loaded": details.get("is_loaded", False)
                })
            return {
                "ok": True,
                "stores": stores
            }
        else:
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

class RebuildIndexRequest(BaseModel):
    department: str
    documentType: str
    diseaseCategory: Optional[str] = None

@app.post(f"{API_PREFIX}/medical/index/delete", tags=["Medical Index"])
async def medical_index_delete(req: DeleteIndexRequest):
    """删除医疗索引"""
    try:
        result = enhanced_index_service.delete_document_index(
            department=req.department,
            document_type=req.documentType,
            disease_category=req.diseaseCategory
        )
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/medical/index/rebuild", tags=["Medical Index"])
async def medical_index_rebuild(req: RebuildIndexRequest):
    """重建医疗索引"""
    try:
        # 首先删除现有索引
        delete_result = enhanced_index_service.delete_document_index(
            department=req.department,
            document_type=req.documentType,
            disease_category=req.diseaseCategory
        )
        
        if not delete_result.get("ok", False):
            return {"ok": False, "error": f"删除现有索引失败: {delete_result.get('error', '未知错误')}"}
        
        # 查找对应的文件ID并重建索引
        # 这里需要根据部门、文档类型和疾病分类找到对应的文件
        from services.index_service import DATA_ROOT
        import os
        
        # 遍历数据目录寻找匹配的文件
        for item in os.listdir(DATA_ROOT):
            item_path = os.path.join(DATA_ROOT, item)
            if os.path.isdir(item_path):
                output_file = os.path.join(item_path, "output.md")
                if os.path.exists(output_file):
                    # 尝试重建这个文件的索引
                    try:
                        rebuild_result = build_medical_index(
                            file_id=item,
                            department=req.department,
                            document_type=req.documentType,
                            disease_category=req.diseaseCategory
                        )
                        if rebuild_result.get("ok"):
                            return {
                                "ok": True,
                                "chunks": rebuild_result.get("chunks", 0),
                                "message": "索引重建成功"
                            }
                    except Exception as rebuild_error:
                        continue
        
        return {"ok": False, "error": "未找到可重建的文档"}
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
    医疗问答聊天（暂时禁用SSE，改为JSON返回）
    集成安全审核和质量评估
    """
    # 为了便于生产系统（如慢病管理）对接，临时关闭SSE，直接复用非流式聚合实现
    # 行为与 /medical/qa 保持一致：一次性返回完整答案、引用、检索元数据、质量/安全评估
    return await medical_qa(req)

@app.post(f"{API_PREFIX}/medical/qa", tags=["Medical RAG"])
async def medical_qa(req: MedicalChatRequest):
    """
    医疗问答（非流式，JSON返回），用于生产前端“慢病管理系统”对接。
    - 入参与流式 MedicalChatRequest 相同（可自动意图识别）。
    - 返回完整答案、引用、检索元数据、质量/安全评估与使用检索标记。
    """
    try:
        question = (req.message or "").strip()
        session_id = (req.sessionId or "medical_default").strip()

        if not question:
            return {"ok": False, "error": "问题不能为空"}

        # 智能意图识别（当未显式指定department/documentType/diseaseCategory时）
        intent_result = None
        if not req.department and not req.documentType and not req.diseaseCategory:
            intent_method = req.intentRecognitionMethod or "smart"
            if intent_method == "smart":
                intent = recognize_smart_medical_intent(question)
                department = intent.get('department')
                document_type = intent.get('document_type')
                disease_category = intent.get('disease_category')
                confidence = intent.get('confidence', 0.0)
                reasoning = intent.get('reasoning', '')
                method = intent.get('method', intent_method)
            elif intent_method == "qwen":
                intent = recognize_qwen_medical_intent(question)
                department = intent.get('department')
                document_type = intent.get('document_type')
                disease_category = intent.get('disease_category')
                confidence = intent.get('confidence', 0.0)
                reasoning = intent.get('reasoning', '')
                method = intent.get('method', intent_method)
            else:
                intent = recognize_medical_intent(question)
                department = intent.department
                document_type = intent.document_type
                disease_category = intent.disease_category
                confidence = intent.confidence
                reasoning = intent.reasoning
                method = "keyword"
            intent_result = {
                'department': department,
                'document_type': document_type,
                'disease_category': disease_category,
                'confidence': confidence,
                'reasoning': reasoning,
                'method': method
            }
        else:
            department = req.department
            document_type = req.documentType
            disease_category = req.diseaseCategory

        # 字符串到枚举的映射与转换（与流式端点保持一致）
        department_enum = None
        document_type_enum = None
        disease_category_enum = None

        if department:
            try:
                department_mapping = {
                    "呼吸内科": "呼吸科",
                    "心内科": "心血管科",
                    "消化内科": "消化科",
                    "内分泌内科": "内分泌科",
                    "肾脏内科": "肾内科",
                    "预防科": "内科",
                    "保健科": "内科"
                }
                mapped_dept = department_mapping.get(department, department)
                department_enum = MedicalDepartment(mapped_dept)
            except ValueError:
                print(f"[WARNING] 无效的科室参数: {department}")
                department_enum = None

        if document_type:
            try:
                doctype_mapping = {
                    "预防指南": "临床指南",
                    "诊疗指南": "临床指南",
                    "治疗指南": "临床指南",
                    "治疗方案": "临床指南",
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

        if disease_category:
            try:
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

        # 聚合流式事件为非流式结果
        full_answer_parts: list[str] = []
        citations_list: list[dict] = []
        first_metadata: dict | None = None
        quality_info: dict | None = None
        safety_warning: dict | None = None
        used_retrieval: bool = False

        async for event in medical_answer_stream(
            question=question,
            citations=citations,
            context_text=context_text,
            metadata=metadata,
            session_id=session_id,
            enable_safety_check=req.enableSafetyCheck
        ):
            et, ed = event.get('type'), event.get('data')
            if et == 'token' and isinstance(ed, str):
                full_answer_parts.append(ed)
            elif et == 'citation' and isinstance(ed, dict):
                citations_list.append(ed)
                # 写入引用缓存，供 /pdf/chunk 按 citationId 查询
                try:
                    cid = ed.get('citation_id') or ed.get('id') or ed.get('citationId')
                    if cid:
                        await set_citation(cid, ed)
                except Exception as _cache_err:
                    print(f"[WARN] Failed to cache citation: {_cache_err}")
            elif et == 'metadata' and isinstance(ed, dict):
                first_metadata = ed
            elif et == 'quality_assessment' and isinstance(ed, dict):
                quality_info = ed
            elif et == 'safety_warning' and isinstance(ed, dict):
                safety_warning = ed
            elif et == 'done' and isinstance(ed, dict):
                used_retrieval = bool(ed.get('used_retrieval'))

        answer_text = "".join(full_answer_parts)

        return {
            "ok": True,
            "data": {
                "answer": answer_text,
                "citations": citations_list,
                "metadata": first_metadata or metadata,
                "quality_assessment": quality_info,
                "safety_warning": safety_warning,
                "used_retrieval": used_retrieval,
                "intent": intent_result or {
                    'department': department,
                    'document_type': document_type,
                    'disease_category': disease_category,
                    'method': req.intentRecognitionMethod or "smart"
                },
                "session_id": session_id
            }
        }
    except Exception as e:
        print(f"[ERROR] medical_qa: {e}")
        return {"ok": False, "error": str(e)}

@app.post(f"{API_PREFIX}/medical/chat/clear", tags=["Medical RAG"])
async def medical_chat_clear(req: ClearChatRequest):
    """清除医疗聊天历史"""
    try:
        session_id = (req.sessionId or "medical_default").strip()
        await clear_history(session_id)
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
        history = await get_history(sessionId)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)