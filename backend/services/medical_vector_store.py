"""
医疗分层向量存储架构
支持按医疗领域、科室、文档类型等维度分类存储和检索
"""

import os
import json
import pickle
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import numpy as np
from dataclasses import dataclass, asdict
import logging

from langchain.vectorstores import FAISS
from langchain.embeddings.base import Embeddings
from langchain.schema import Document

from .medical_taxonomy import MedicalDepartment, DocumentType, DiseaseCategory, MedicalMetadata

logger = logging.getLogger(__name__)

@dataclass
class VectorStoreMetadata:
    """向量存储元数据"""
    department: MedicalDepartment
    document_type: DocumentType
    disease_category: Optional[DiseaseCategory] = None
    created_at: str = ""
    document_count: int = 0
    last_updated: str = ""
    
class MedicalVectorStoreManager:
    """医疗分层向量存储管理器"""
    
    def __init__(self, 
                 base_path: str = "data/vector_stores",
                 embeddings: Optional[Embeddings] = None):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.embeddings = embeddings
        self.vector_stores: Dict[str, FAISS] = {}
        self.metadata_cache: Dict[str, VectorStoreMetadata] = {}
        
        # 加载现有的向量存储
        self._load_existing_stores()
    
    def _get_store_key(self, 
                      department: MedicalDepartment, 
                      document_type: DocumentType,
                      disease_category: Optional[DiseaseCategory] = None) -> str:
        """生成向量存储的唯一键"""
        key_parts = [department.value, document_type.value]
        if disease_category:
            key_parts.append(disease_category.value)
        return "_".join(key_parts)
    
    def _get_store_path(self, store_key: str) -> Path:
        """获取向量存储的文件路径"""
        return self.base_path / store_key
    
    def _load_existing_stores(self):
        """加载现有的向量存储"""
        if not self.base_path.exists():
            return
            
        for store_dir in self.base_path.iterdir():
            if store_dir.is_dir():
                try:
                    # 加载元数据
                    metadata_file = store_dir / "metadata.json"
                    if metadata_file.exists():
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata_dict = json.load(f)
                            
                            # 转换字符串回枚举对象
                            if 'department' in metadata_dict and metadata_dict['department']:
                                metadata_dict['department'] = MedicalDepartment(metadata_dict['department'])
                            if 'document_type' in metadata_dict and metadata_dict['document_type']:
                                metadata_dict['document_type'] = DocumentType(metadata_dict['document_type'])
                            if 'disease_category' in metadata_dict and metadata_dict['disease_category']:
                                metadata_dict['disease_category'] = DiseaseCategory(metadata_dict['disease_category'])
                            
                            metadata = VectorStoreMetadata(**metadata_dict)
                            self.metadata_cache[store_dir.name] = metadata
                    
                    # 延迟加载向量存储（只在需要时加载）
                    logger.info(f"发现向量存储: {store_dir.name}")
                    
                except Exception as e:
                    logger.error(f"加载向量存储 {store_dir.name} 失败: {e}")
    
    def _load_vector_store(self, store_key: str) -> Optional[FAISS]:
        """延迟加载向量存储"""
        if store_key in self.vector_stores:
            return self.vector_stores[store_key]
        
        store_path = self._get_store_path(store_key)
        if not store_path.exists():
            return None
        
        try:
            if self.embeddings is None:
                logger.error("未提供embeddings，无法加载向量存储")
                return None
                
            vector_store = FAISS.load_local(
                str(store_path), 
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            self.vector_stores[store_key] = vector_store
            logger.info(f"成功加载向量存储: {store_key}")
            return vector_store
            
        except Exception as e:
            logger.error(f"加载向量存储 {store_key} 失败: {e}")
            return None
    
    def add_documents(self, 
                     documents: List[Document],
                     department: MedicalDepartment,
                     document_type: DocumentType,
                     disease_category: Optional[DiseaseCategory] = None) -> bool:
        """添加文档到指定的向量存储"""
        if not documents:
            return False
        
        if self.embeddings is None:
            logger.error("未提供embeddings，无法添加文档")
            return False
        
        store_key = self._get_store_key(department, document_type, disease_category)
        
        try:
            # 获取或创建向量存储
            vector_store = self._load_vector_store(store_key)
            
            if vector_store is None:
                # 创建新的向量存储
                vector_store = FAISS.from_documents(documents, self.embeddings)
                self.vector_stores[store_key] = vector_store
                logger.info(f"创建新的向量存储: {store_key}")
            else:
                # 添加到现有向量存储
                vector_store.add_documents(documents)
                logger.info(f"向现有向量存储添加 {len(documents)} 个文档: {store_key}")
            
            # 保存向量存储
            store_path = self._get_store_path(store_key)
            store_path.mkdir(parents=True, exist_ok=True)
            vector_store.save_local(str(store_path))
            
            # 更新元数据
            from datetime import datetime
            current_time = datetime.now().isoformat()
            
            if store_key in self.metadata_cache:
                metadata = self.metadata_cache[store_key]
                metadata.document_count += len(documents)
                metadata.last_updated = current_time
            else:
                metadata = VectorStoreMetadata(
                    department=department,
                    document_type=document_type,
                    disease_category=disease_category,
                    created_at=current_time,
                    document_count=len(documents),
                    last_updated=current_time
                )
                self.metadata_cache[store_key] = metadata
            
            # 保存元数据
            metadata_file = store_path / "metadata.json"
            # 转换枚举为字符串以便JSON序列化
            metadata_dict = asdict(metadata)
            metadata_dict['department'] = metadata.department.value if metadata.department else None
            metadata_dict['document_type'] = metadata.document_type.value if metadata.document_type else None
            metadata_dict['disease_category'] = metadata.disease_category.value if metadata.disease_category else None
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"删除向量存储 {store_key} 失败: {e}", exc_info=True)
            return False
    
    def search_documents(self,
                        query: str,
                        k: int = 5,
                        department: Optional[MedicalDepartment] = None,
                        document_type: Optional[DocumentType] = None,
                        disease_category: Optional[DiseaseCategory] = None,
                        score_threshold: float = 0.0) -> List[Tuple[Document, float]]:
        """在指定的向量存储中搜索文档"""
        results = []
        
        # 确定要搜索的向量存储
        target_stores: List[str] = []
        
        if department and document_type:
            # 精确匹配
            store_key = self._get_store_key(department, document_type, disease_category)
            if store_key in self.metadata_cache:
                target_stores.append(store_key)
            else:
                # 回退：聚合该科室+文档类型下的所有疾病类别存储
                fallback_candidates: List[str] = []
                for sk, metadata in self.metadata_cache.items():
                    meta_dept = metadata.department.value if hasattr(metadata.department, 'value') else str(metadata.department)
                    meta_dtype = metadata.document_type.value if hasattr(metadata.document_type, 'value') else str(metadata.document_type)
                    dept_val = department.value if hasattr(department, 'value') else str(department)
                    dtype_val = document_type.value if hasattr(document_type, 'value') else str(document_type)
                    if meta_dept == dept_val and meta_dtype == dtype_val:
                        # 若用户指定了疾病类别，则优先尝试仅匹配该类别
                        if disease_category is None:
                            fallback_candidates.append(sk)
                        else:
                            meta_dcat = metadata.disease_category.value if (metadata.disease_category and hasattr(metadata.disease_category, 'value')) else (str(metadata.disease_category) if metadata.disease_category else None)
                            dcat_val = disease_category.value if hasattr(disease_category, 'value') else str(disease_category)
                            if meta_dcat == dcat_val:
                                fallback_candidates.append(sk)
                            fallback_candidates.append(sk)

                # 如果按指定疾病类别仍无候选，则进一步忽略疾病类别进行聚合
                if not fallback_candidates and disease_category is not None:
                    for sk, metadata in self.metadata_cache.items():
                        meta_dept = metadata.department.value if hasattr(metadata.department, 'value') else str(metadata.department)
                        meta_dtype = metadata.document_type.value if hasattr(metadata.document_type, 'value') else str(metadata.document_type)
                        dept_val = department.value if hasattr(department, 'value') else str(department)
                        dtype_val = document_type.value if hasattr(document_type, 'value') else str(document_type)
                        if meta_dept == dept_val and meta_dtype == dtype_val:
                            fallback_candidates.append(sk)

                if fallback_candidates:
                    target_stores.extend(fallback_candidates)
                    try:
                        dept_val = department.value if hasattr(department, 'value') else str(department)
                        dtype_val = document_type.value if hasattr(document_type, 'value') else str(document_type)
                        dcat_val = disease_category.value if (disease_category and hasattr(disease_category, 'value')) else (str(disease_category) if disease_category else None)
                        logger.info(
                            f"未找到精确存储键 {store_key}，触发回退：聚合 '{dept_val}_{dtype_val}_*' 共 {len(fallback_candidates)} 个存储"
                            + (f"（原疾病类别: {dcat_val}）" if dcat_val else "")
                        )
                    except Exception:
                        # 记录日志失败不影响检索
                        pass
        else:
            # 模糊匹配
            for store_key, metadata in self.metadata_cache.items():
                meta_dept = metadata.department.value if hasattr(metadata.department, 'value') else str(metadata.department)
                meta_dtype = metadata.document_type.value if hasattr(metadata.document_type, 'value') else str(metadata.document_type)
                meta_dcat = metadata.disease_category.value if (metadata.disease_category and hasattr(metadata.disease_category, 'value')) else (str(metadata.disease_category) if metadata.disease_category else None)
                dept_val = department.value if (department and hasattr(department, 'value')) else (str(department) if department else None)
                dtype_val = document_type.value if (document_type and hasattr(document_type, 'value')) else (str(document_type) if document_type else None)
                dcat_val = disease_category.value if (disease_category and hasattr(disease_category, 'value')) else (str(disease_category) if disease_category else None)
                if dept_val and meta_dept != dept_val:
                    continue
                if dtype_val and meta_dtype != dtype_val:
                    continue
                if dcat_val and meta_dcat != dcat_val:
                    continue
                target_stores.append(store_key)
        
        # 在每个目标存储中搜索
        for store_key in target_stores:
            vector_store = self._load_vector_store(store_key)
            if vector_store is None:
                continue
            
            try:
                # 执行相似性搜索
                store_results = vector_store.similarity_search_with_score(query, k=k)
                
                # 过滤低分结果
                filtered_results = [
                    (doc, score) for doc, score in store_results 
                    if score >= score_threshold
                ]
                
                # 添加存储信息到文档元数据
                for doc, score in filtered_results:
                    if 'store_key' not in doc.metadata:
                        doc.metadata['store_key'] = store_key
                        doc.metadata['department'] = self.metadata_cache[store_key].department.value
                        doc.metadata['document_type'] = self.metadata_cache[store_key].document_type.value
                
                results.extend(filtered_results)
                
            except Exception as e:
                logger.error(f"在向量存储 {store_key} 中搜索失败: {e}")
        
        # 按分数排序并返回前k个结果
        # FAISS返回的是距离分数，距离越小表示越相似，所以使用升序排序
        results.sort(key=lambda x: x[1], reverse=False)
        return results[:k]
    
    def get_store_statistics(self) -> Dict[str, Dict]:
        """获取所有向量存储的统计信息"""
        stats = {}
        
        for store_key, metadata in self.metadata_cache.items():
            # 安全地获取枚举值
            department_value = metadata.department.value if hasattr(metadata.department, 'value') else str(metadata.department)
            document_type_value = metadata.document_type.value if hasattr(metadata.document_type, 'value') else str(metadata.document_type)
            disease_category_value = None
            if metadata.disease_category:
                disease_category_value = metadata.disease_category.value if hasattr(metadata.disease_category, 'value') else str(metadata.disease_category)
            
            stats[store_key] = {
                'department': department_value,
                'document_type': document_type_value,
                'disease_category': disease_category_value,
                'document_count': metadata.document_count,
                'created_at': metadata.created_at,
                'last_updated': metadata.last_updated,
                'is_loaded': store_key in self.vector_stores
            }
        
        return stats
    
    def delete_store(self, 
                    department: MedicalDepartment,
                    document_type: DocumentType,
                    disease_category: Optional[DiseaseCategory] = None) -> bool:
        """删除指定的向量存储"""
        store_key = self._get_store_key(department, document_type, disease_category)
        
        try:
            logger.info(f"开始删除向量存储: {store_key}")
            
            # 从内存中移除
            if store_key in self.vector_stores:
                del self.vector_stores[store_key]
                logger.info(f"从内存中移除向量存储: {store_key}")
            
            if store_key in self.metadata_cache:
                del self.metadata_cache[store_key]
                logger.info(f"从元数据缓存中移除: {store_key}")
            
            # 删除文件
            store_path = self._get_store_path(store_key)
            if store_path.exists():
                import shutil
                shutil.rmtree(store_path)
                logger.info(f"删除存储文件: {store_path}")
            else:
                logger.warning(f"存储文件不存在: {store_path}")
            
            logger.info(f"成功删除向量存储: {store_key}")
            return True
            
        except Exception as e:
            logger.error(f"删除向量存储 {store_key} 失败: {e}", exc_info=True)
            return False
    
    def optimize_stores(self):
        """优化向量存储（合并小存储、重建索引等）"""
        logger.info("开始优化向量存储...")
        
        # 统计每个科室的文档数量
        department_stats = {}
        for store_key, metadata in self.metadata_cache.items():
            dept = metadata.department.value
            if dept not in department_stats:
                department_stats[dept] = []
            department_stats[dept].append((store_key, metadata.document_count))
        
        # 合并小的向量存储
        for dept, stores in department_stats.items():
            small_stores = [(key, count) for key, count in stores if count < 100]
            if len(small_stores) > 1:
                logger.info(f"发现 {dept} 科室有 {len(small_stores)} 个小向量存储，考虑合并")
                # 这里可以实现合并逻辑
        
        logger.info("向量存储优化完成")

class MedicalSearchEngine:
    """医疗搜索引擎，整合分层向量存储"""
    
    def __init__(self, vector_store_manager: MedicalVectorStoreManager):
        self.vector_store_manager = vector_store_manager
    
    def search(self,
              query: str,
              k: int = 10,
              filters: Optional[Dict] = None) -> List[Tuple[Document, float]]:
        """智能搜索，支持多种过滤条件"""
        
        # 解析过滤条件
        department = None
        document_type = None
        disease_category = None
        
        # 疾病类别别名映射（临时纠偏，与现有向量存储保持一致）
        alias_map: Dict[str, DiseaseCategory] = {
            # 常见中文别名
            "精神障碍": DiseaseCategory.MENTAL_DISORDERS,
            "心理障碍": DiseaseCategory.MENTAL_DISORDERS,
            "精神疾病": DiseaseCategory.NERVOUS_SYSTEM,  # 现有库归到神经系统疾病
            "神经系统疾病": DiseaseCategory.NERVOUS_SYSTEM,
            "精神、行为和神经发育障碍": DiseaseCategory.MENTAL_DISORDERS,
            # 英文/拼写变体（如出现）
            "mental disorders": DiseaseCategory.MENTAL_DISORDERS,
            "nervous system": DiseaseCategory.NERVOUS_SYSTEM,
        }
        
        if filters:
            if 'department' in filters:
                try:
                    department = MedicalDepartment(filters['department'])
                except ValueError:
                    pass
            
            if 'document_type' in filters:
                try:
                    document_type = DocumentType(filters['document_type'])
                except ValueError:
                    pass
            
            if 'disease_category' in filters:
                try:
                    disease_category = DiseaseCategory(filters['disease_category'])
                except ValueError:
                    # 别名解析
                    raw = str(filters['disease_category']).strip()
                    if raw in alias_map:
                        disease_category = alias_map[raw]
                        try:
                            logger.debug(f"疾病类别别名映射: '{raw}' -> '{disease_category.value}'")
                        except Exception:
                            pass
                    else:
                        # 无法解析则保持 None，由回退逻辑处理
                        disease_category = None
        
        # 执行搜索
        results = self.vector_store_manager.search_documents(
            query=query,
            k=k,
            department=department,
            document_type=document_type,
            disease_category=disease_category
        )
        
        return results
    
    def search_by_symptoms(self, symptoms: List[str], k: int = 10) -> List[Tuple[Document, float]]:
        """基于症状搜索相关疾病和治疗方案"""
        query = " ".join(symptoms)
        
        # 优先搜索诊断指南和临床路径
        results = []
        
        # 搜索诊断指南
        diagnosis_results = self.vector_store_manager.search_documents(
            query=query,
            k=k//2,
            document_type=DocumentType.CLINICAL_GUIDELINE
        )
        results.extend(diagnosis_results)
        
        # 搜索治疗方案
        pathway_results = self.vector_store_manager.search_documents(
            query=query,
            k=k//2,
            document_type=DocumentType.TREATMENT_PROTOCOL
        )
        results.extend(pathway_results)
        
        # 按分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]
    
    def search_drug_interactions(self, drug_name: str, k: int = 10) -> List[Tuple[Document, float]]:
        """搜索药物相互作用和副作用信息"""
        query = f"{drug_name} 相互作用 副作用 禁忌"
        
        results = self.vector_store_manager.search_documents(
            query=query,
            k=k,
            document_type=DocumentType.DRUG_MANUAL
        )
        
        return results