"""
增强的医疗索引服务
集成分层向量存储、医疗文档预处理和分类功能
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import os
import json
import logging
from datetime import datetime

from langchain.docstore.document import Document
from langchain.embeddings.base import Embeddings

from .index_service import DashScopeEmbeddings, load_embeddings, markdown_path, workdir
from .medical_vector_store import MedicalVectorStoreManager, MedicalSearchEngine
from .medical_taxonomy import MedicalDepartment, DocumentType, DiseaseCategory
from .medical_preprocessor import MedicalDocumentPreprocessor

logger = logging.getLogger(__name__)

class EnhancedMedicalIndexService:
    """增强的医疗索引服务"""
    
    def __init__(self, 
                 vector_store_base_path: Optional[str] = None,
                 embeddings: Optional[Embeddings] = None):
        
        # 初始化组件
        self.embeddings = embeddings or load_embeddings()
        # 统一指向后端共享目录 backend/data/vector_stores（若无法定位backend则回退到repo根目录的data/vector_stores）
        try:
            backend_root = next((p for p in Path(__file__).resolve().parents if p.name == "backend"), None)
            default_base = (backend_root / "data" / "vector_stores") if backend_root else Path("data/vector_stores").resolve()
        except Exception:
            default_base = Path("data/vector_stores").resolve()
        base_path = Path(vector_store_base_path).resolve() if vector_store_base_path else default_base
        
        self.vector_store_manager = MedicalVectorStoreManager(
            base_path=str(base_path),
            embeddings=self.embeddings
        )
        self.search_engine = MedicalSearchEngine(self.vector_store_manager)
        self.preprocessor = MedicalDocumentPreprocessor()
        
        # 创建数据目录（统一到 backend/data）
        try:
            backend_root = next((p for p in Path(__file__).resolve().parents if p.name == "backend"), None)
            self.data_root = (backend_root / "data") if backend_root else Path("data")
        except Exception:
            self.data_root = Path("data")
        self.data_root.mkdir(parents=True, exist_ok=True)
        
        logger.info("增强医疗索引服务初始化完成")
    
    def process_and_index_document(self,
                                 file_id: str,
                                 department: MedicalDepartment,
                                 document_type: DocumentType,
                                 disease_category: Optional[DiseaseCategory] = None,
                                 custom_metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """处理并索引医疗文档"""
        
        try:
            # 1. 读取markdown文件
            md_file = markdown_path(file_id)
            if not md_file.exists():
                return {"ok": False, "error": "MARKDOWN_NOT_FOUND"}
            
            md_text = md_file.read_text(encoding="utf-8")
            if not md_text.strip():
                return {"ok": False, "error": "EMPTY_DOCUMENT"}
            
            # 2. 医疗文档预处理
            logger.info(f"开始处理文档 {file_id}")
            processed_chunks = self.preprocessor.preprocess_document(
                text=md_text,
                metadata={
                    "file_id": file_id,
                    "department": department.value,
                    "document_type": document_type.value,
                    "disease_category": disease_category.value if disease_category else None,
                    "processed_at": datetime.now().isoformat(),
                    **(custom_metadata or {})
                }
            )
            
            # 转换为Document对象
            processed_docs = []
            for chunk in processed_chunks:
                doc = Document(
                    page_content=chunk.embedding_text,
                    metadata=chunk.metadata
                )
                processed_docs.append(doc)
            
            if not processed_docs:
                return {"ok": False, "error": "NO_VALID_CHUNKS"}
            
            # 3. 添加到分层向量存储
            success = self.vector_store_manager.add_documents(
                documents=processed_docs,
                department=department,
                document_type=document_type,
                disease_category=disease_category
            )
            
            if not success:
                return {"ok": False, "error": "VECTOR_STORE_ERROR"}
            
            # 4. 保存处理结果元数据
            self._save_processing_metadata(file_id, {
                "department": department.value,
                "document_type": document_type.value,
                "disease_category": disease_category.value if disease_category else None,
                "chunks_count": len(processed_docs),
                "processed_at": datetime.now().isoformat(),
                "custom_metadata": custom_metadata
            })
            
            logger.info(f"成功处理并索引文档 {file_id}，生成 {len(processed_docs)} 个文档块")
            
            return {
                "ok": True,
                "chunks": len(processed_docs),
                "department": department.value,
                "document_type": document_type.value,
                "disease_category": disease_category.value if disease_category else None
            }
            
        except Exception as e:
            logger.error(f"处理文档 {file_id} 时发生错误: {e}")
            import traceback
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
    
    def search_medical_documents(self,
                               query: str,
                               k: int = 10,
                               department: Optional[str] = None,
                               document_type: Optional[str] = None,
                               disease_category: Optional[str] = None,
                               score_threshold: float = 0.0) -> Dict[str, Any]:
        """搜索医疗文档"""
        
        try:
            # 构建过滤条件
            filters = {}
            if department:
                filters['department'] = department
            if document_type:
                filters['document_type'] = document_type
            if disease_category:
                filters['disease_category'] = disease_category
            
            # 执行搜索
            results = self.search_engine.search(
                query=query,
                k=k,
                filters=filters
            )
            
            # 过滤低分结果
            filtered_results = [
                (doc, score) for doc, score in results 
                if score >= score_threshold
            ]
            
            # 格式化结果
            formatted_results = []
            for doc, score in filtered_results:
                formatted_results.append({
                    "text": doc.page_content,
                    "score": float(score),
                    "metadata": doc.metadata,
                    "department": doc.metadata.get('department'),
                    "document_type": doc.metadata.get('document_type'),
                    "disease_category": doc.metadata.get('disease_category'),
                    "medical_entities": doc.metadata.get('medical_entities', []),
                    "enhanced_text": doc.metadata.get('enhanced_text', '')
                })
            
            return {
                "ok": True,
                "results": formatted_results,
                "total_found": len(filtered_results),
                "query": query,
                "filters": filters
            }
            
        except Exception as e:
            logger.error(f"搜索医疗文档时发生错误: {e}")
            return {"ok": False, "error": str(e)}
    
    def search_by_symptoms(self, symptoms: List[str], k: int = 10) -> Dict[str, Any]:
        """基于症状搜索相关疾病和治疗方案"""
        
        try:
            results = self.search_engine.search_by_symptoms(symptoms, k=k)
            
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "text": doc.page_content,
                    "score": float(score),
                    "metadata": doc.metadata,
                    "department": doc.metadata.get('department'),
                    "document_type": doc.metadata.get('document_type'),
                    "medical_entities": doc.metadata.get('medical_entities', [])
                })
            
            return {
                "ok": True,
                "results": formatted_results,
                "symptoms": symptoms,
                "total_found": len(formatted_results)
            }
            
        except Exception as e:
            logger.error(f"基于症状搜索时发生错误: {e}")
            return {"ok": False, "error": str(e)}
    
    def search_drug_interactions(self, drug_name: str, k: int = 10) -> Dict[str, Any]:
        """搜索药物相互作用和副作用信息"""
        
        try:
            results = self.search_engine.search_drug_interactions(drug_name, k=k)
            
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "text": doc.page_content,
                    "score": float(score),
                    "metadata": doc.metadata,
                    "medical_entities": doc.metadata.get('medical_entities', [])
                })
            
            return {
                "ok": True,
                "results": formatted_results,
                "drug_name": drug_name,
                "total_found": len(formatted_results)
            }
            
        except Exception as e:
            logger.error(f"搜索药物信息时发生错误: {e}")
            return {"ok": False, "error": str(e)}
    
    def get_vector_store_statistics(self) -> Dict[str, Any]:
        """获取向量存储统计信息"""
        try:
            stats = self.vector_store_manager.get_store_statistics()
            
            # 计算总体统计
            total_documents = sum(store['document_count'] for store in stats.values())
            departments = set(store['department'] for store in stats.values())
            document_types = set(store['document_type'] for store in stats.values())
            
            return {
                "ok": True,
                "total_stores": len(stats),
                "total_documents": total_documents,
                "departments": list(departments),
                "document_types": list(document_types),
                "store_details": stats
            }
            
        except Exception as e:
            logger.error(f"获取统计信息时发生错误: {e}")
            return {"ok": False, "error": str(e)}
    
    def delete_document_index(self,
                            department: str,
                            document_type: str,
                            disease_category: Optional[str] = None) -> Dict[str, Any]:
        """删除指定的文档索引"""
        
        try:
            # 参数验证
            dept = MedicalDepartment(department)
            doc_type = DocumentType(document_type)
            disease_cat = DiseaseCategory(disease_category) if disease_category else None
            
            logger.info(f"开始删除索引: department={department}, document_type={document_type}, disease_category={disease_category}")
            
            # 删除向量存储
            success = self.vector_store_manager.delete_store(
                department=dept,
                document_type=doc_type,
                disease_category=disease_cat
            )
            
            if success:
                # 清理相关缓存
                try:
                    from .cache_service import cache_service
                    
                    # 清理查询结果缓存
                    cache_service.invalidate('query_result')
                    cache_service.invalidate('medical_association')
                    cache_service.invalidate('kg_expansion')
                    
                    logger.info(f"已清理相关缓存: department={department}, document_type={document_type}")
                except Exception as cache_error:
                    logger.warning(f"清理缓存时出现警告: {cache_error}")
                
                logger.info(f"索引删除成功: department={department}, document_type={document_type}")
                return {
                    "ok": True, 
                    "message": "索引删除成功",
                    "details": {
                        "department": department,
                        "document_type": document_type,
                        "disease_category": disease_category,
                        "cache_cleared": True
                    }
                }
            else:
                logger.error(f"删除索引失败: department={department}, document_type={document_type}")
                return {"ok": False, "error": "删除索引失败"}
                
        except ValueError as e:
            logger.error(f"无效的参数: {e}")
            return {"ok": False, "error": f"无效的参数: {e}"}
        except Exception as e:
            logger.error(f"删除索引时发生错误: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}
    
    def optimize_vector_stores(self) -> Dict[str, Any]:
        """优化向量存储"""
        try:
            self.vector_store_manager.optimize_stores()
            return {"ok": True, "message": "向量存储优化完成"}
        except Exception as e:
            logger.error(f"优化向量存储时发生错误: {e}")
            return {"ok": False, "error": str(e)}
    
    def _save_processing_metadata(self, file_id: str, metadata: Dict):
        """保存文档处理元数据"""
        try:
            metadata_file = workdir(file_id) / "processing_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存处理元数据失败: {e}")
    
    def get_processing_metadata(self, file_id: str) -> Optional[Dict]:
        """获取文档处理元数据"""
        try:
            metadata_file = workdir(file_id) / "processing_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"读取处理元数据失败: {e}")
        return None

# 全局实例
enhanced_index_service = EnhancedMedicalIndexService()

# 兼容性函数，保持与现有API的兼容
def build_medical_index(file_id: str,
                       department: str,
                       document_type: str,
                       disease_category: Optional[str] = None,
                       custom_metadata: Optional[Dict] = None) -> Dict[str, Any]:
    """构建医疗文档索引（兼容性函数）"""
    try:
        dept = MedicalDepartment(department)
        doc_type = DocumentType(document_type)
        disease_cat = DiseaseCategory(disease_category) if disease_category else None
        
        return enhanced_index_service.process_and_index_document(
            file_id=file_id,
            department=dept,
            document_type=doc_type,
            disease_category=disease_cat,
            custom_metadata=custom_metadata
        )
    except ValueError as e:
        return {"ok": False, "error": f"无效的参数: {e}"}

def search_medical_knowledge(query: str,
                           k: int = 10,
                           **filters) -> Dict[str, Any]:
    """搜索医疗知识（兼容性函数）"""
    return enhanced_index_service.search_medical_documents(
        query=query,
        k=k,
        **filters
    )