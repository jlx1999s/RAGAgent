# services/enhanced_rag_service.py
from __future__ import annotations
import os, asyncio, textwrap, logging
from typing import List, Dict, Any, Tuple, AsyncGenerator, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
# 兼容导入 TypedDict（优先使用标准库typing，其次typing_extensions）
try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

from dotenv import load_dotenv
load_dotenv(override=True)

# 可选依赖：langchain_community 与 langchain_openai，不存在时提供占位
try:
    from langchain_community.chat_models import ChatTongyi
except Exception:
    ChatTongyi = None
try:
    from langchain_openai import OpenAIEmbeddings
except Exception:
    OpenAIEmbeddings = None
try:
    from langchain_community.vectorstores import FAISS
except Exception:
    FAISS = None
from collections import defaultdict
# Embeddings作为类型注解可选导入，缺失时提供最小占位类，避免运行时导入错误
try:
    from langchain.embeddings.base import Embeddings
except Exception:
    class Embeddings:
        pass
import dashscope
from http import HTTPStatus

# 导入医疗相关服务
from .medical_safety_service import MedicalReviewService, SafetyLevel, QualityLevel
from .enhanced_index_service import EnhancedMedicalIndexService
from .medical_knowledge_graph import MedicalKnowledgeGraphService, kg_service
from .medical_association_service import MedicalAssociationService, medical_association_service, AssociationType
from .query_quality_assessor import query_quality_assessor
from .medical_taxonomy import MedicalDepartment, DocumentType, DiseaseCategory
from .state_store import (
    get_session_history as _get_session_history,
    append_session_history as _append_session_history,
    clear_session_history as _clear_session_history,
)
from .cache_service import cache_service

# 会话历史改用 Redis/内存回退，通过 services.state_store 统一管理

class DashScopeEmbeddings(Embeddings):
    """自定义DashScope嵌入类，使用原生SDK"""
    
    def __init__(self, model: str = "text-embedding-v4"):
        self.model = model
        # 设置API密钥
        dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入文档列表，支持批处理以避免API限制"""
        try:
            all_embeddings = []
            batch_size = 10  # DashScope API限制
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                resp = dashscope.TextEmbedding.call(
                    model=self.model,
                    input=batch
                )
                
                if resp.status_code == HTTPStatus.OK:
                    batch_embeddings = [record['embedding'] for record in resp.output['embeddings']]
                    all_embeddings.extend(batch_embeddings)
                else:
                    raise Exception(f"DashScope API error: {resp}")
            
            return all_embeddings
        except Exception as e:
            print(f"Error in embed_documents: {e}")
            raise e
    
    def embed_query(self, text: str) -> List[float]:
        """嵌入单个查询"""
        try:
            resp = dashscope.TextEmbedding.call(
                model=self.model,
                input=text
            )
            
            if resp.status_code == HTTPStatus.OK:
                return resp.output['embeddings'][0]['embedding']
            else:
                raise Exception(f"DashScope API error: {resp}")
        except Exception as e:
            print(f"Error in embed_query: {e}")
            raise e

class EnhancedMedicalRAGService:
    """增强的医疗RAG服务，集成安全审核机制"""
    
    def __init__(self):
        self.review_service = MedicalReviewService()
        self.index_service = EnhancedMedicalIndexService()
        self.kg_service = kg_service
        self.association_service = medical_association_service
        
        # 配置参数
        self.model_name = "qwen-plus"
        self.temperature = 0
        self.k = 5  # 增加检索数量以提高医疗问答质量
        self.score_tau_top1 = 2.0  # 放宽阈值以提高召回率
        self.score_tau_mean3 = 2.5  # 放宽阈值以提高召回率
        
        # 医疗专用系统指令
        self.system_instruction = (
            "你是一个医疗问答助手，基于医疗文档提供简洁实用的健康建议。\n"
            "回答要求：\n"
            "1. 回答简洁明了，用通俗语言\n"
            "2. 重点突出关键建议\n"
            "3. 提醒严重情况需就医\n"
        )
        
        self.medical_answer_prompt = (
            "基于以下医疗文档回答用户问题：\n\n"
            "问题：{question}\n\n"
            "相关医疗文档：\n{context}\n\n"
            "回答要求：\n"
            "1. 回答要简洁明了，控制在200字以内\n"
            "2. 使用通俗易懂的语言，避免过多专业术语\n"
            "3. 重点突出最关键的建议\n"
            "4. 简单提醒咨询医生即可\n"
            "5. 不需要复杂的格式，直接回答\n"
        )
        
        self.no_context_prompt = (
            "抱歉，在当前的医疗知识库中未找到与您问题直接相关的权威文档。\n"
            "问题：{question}\n\n"
            "建议：\n"
            "1. 请咨询专业医生获取准确的医疗建议\n"
            "2. 可以尝试重新描述问题或使用更具体的医学术语\n"
            "3. 对于紧急情况，请立即就医\n"
        )

    async def get_history(self, session_id: str) -> list[dict]:
        """获取会话历史（Redis/内存回退）"""
        return await _get_session_history(session_id)

    async def append_history(self, session_id: str, role: str, content: str) -> None:
        """添加会话历史（Redis/内存回退）"""
        await _append_session_history(session_id, role, content)

    async def clear_history(self, session_id: str) -> None:
        """清除会话历史（Redis/内存回退）"""
        await _clear_session_history(session_id)

    def _get_llm(self):
        """获取语言模型"""
        return ChatTongyi(
            model=self.model_name,
            dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"),
            temperature=self.temperature,
        )

    def _get_grader(self):
        """获取评分模型"""
        return ChatTongyi(
            model=self.model_name,
            dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"),
            temperature=0,
        )

    def _score_ok(self, scores: List[float]) -> bool:
        """评估检索分数是否满足阈值"""
        if not scores:
            return False
        top1 = scores[0]
        mean3 = sum(scores[:3]) / min(3, len(scores))
        return (top1 <= self.score_tau_top1) or (mean3 <= self.score_tau_mean3)

    async def medical_retrieve(
        self, 
        question: str, 
        department: Optional[MedicalDepartment] = None,
        document_type: Optional[DocumentType] = None,
        disease_category: Optional[DiseaseCategory] = None,
        intent_method: str = "smart",
        session_id: Optional[str] = None
    ) -> tuple[list[dict], str, dict]:
        """
        优化的医疗知识检索流程：意图识别 → 上下文感知KG增强 → 检索
        """
        try:
            # 生成查询缓存键
            cache_key = {
                'question': question,
                'department': department.value if department else None,
                'document_type': document_type.value if document_type else None,
                'disease_category': disease_category.value if disease_category else None,
                'intent_method': intent_method,
                'k': self.k
            }
            
            # 检查缓存
            cached_result = cache_service.get('query_result', cache_key)
            if cached_result:
                logging.info("使用缓存的查询结果")
                return cached_result
            
            # 1. 智能意图识别（如果未提供department等参数）
            intent_result = None
            if not department and not document_type and not disease_category:
                from .smart_intent_service import recognize_smart_medical_intent
                from .qwen_intent_service import recognize_qwen_medical_intent
                from .medical_intent_service import recognize_medical_intent
                
                if intent_method == "smart":
                    intent = recognize_smart_medical_intent(question)
                    department_str = intent.get('department')
                    document_type_str = intent.get('document_type')
                    disease_category_str = intent.get('disease_category')
                    confidence = intent.get('confidence', 0.0)
                    reasoning = intent.get('reasoning', '')
                elif intent_method == "qwen":
                    intent = recognize_qwen_medical_intent(question)
                    department_str = intent.get('department')
                    document_type_str = intent.get('document_type')
                    disease_category_str = intent.get('disease_category')
                    confidence = intent.get('confidence', 0.0)
                    reasoning = intent.get('reasoning', '')
                else:
                    intent = recognize_medical_intent(question)
                    department_str = intent.department
                    document_type_str = intent.document_type
                    disease_category_str = intent.disease_category
                    confidence = getattr(intent, 'confidence', 0.0)
                    reasoning = intent.reasoning
                
                # 转换为枚举类型
                if department_str:
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
                        mapped_dept = department_mapping.get(department_str, department_str)
                        department = MedicalDepartment(mapped_dept)
                    except ValueError:
                        logging.warning(f"无效的科室参数: {department_str}")
                
                if document_type_str:
                    try:
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
                        mapped_doctype = doctype_mapping.get(document_type_str, document_type_str)
                        document_type = DocumentType(mapped_doctype)
                    except ValueError:
                        logging.warning(f"无效的文档类型参数: {document_type_str}")
                
                if disease_category_str:
                    try:
                        disease_category = DiseaseCategory(disease_category_str)
                    except ValueError:
                        logging.warning(f"无效的疾病分类参数: {disease_category_str}")
                
                intent_result = {
                    'department': department_str,
                    'document_type': document_type_str,
                    'disease_category': disease_category_str,
                    'confidence': confidence,
                    'reasoning': reasoning,
                    'method': intent_method
                }
                
                logging.info(f"意图识别完成 - 科室: {department_str}, 文档类型: {document_type_str}, 疾病分类: {disease_category_str}")
            
            # 1.5. 查询质量评估
            query_quality = query_quality_assessor.assess_query_quality(
                question, 
                context={
                    'department': department.value if department else None,
                    'document_type': document_type.value if document_type else None,
                    'disease_category': disease_category.value if disease_category else None,
                    'intent_confidence': intent_result.get('confidence', 0) if intent_result else 0,
                    'session_id': session_id
                }
            )
            
            logging.info(f"查询质量评估 - 总分: {query_quality.overall_score:.3f}, 等级: {query_quality.quality_level.value}")
            if query_quality.suggestions:
                logging.info(f"改进建议: {', '.join(query_quality.suggestions)}")
            
            # 根据查询质量调整后续处理策略
            quality_threshold = 0.6
            use_enhanced_kg = query_quality.overall_score >= quality_threshold
            
            # 2. 上下文感知的知识图谱增强（基于意图识别结果和查询质量）
            kg_enhanced_query = question
            kg_entities = []
            kg_relations = []
            kg_suggestions = []
            
            if use_enhanced_kg:  # 只有在查询质量足够高时才进行KG增强
                try:
                    # 并行执行实体提取和KG增强
                    async def run_kg_enhancement():
                        with ThreadPoolExecutor(max_workers=2) as executor:
                            # 检查实体提取缓存
                            entity_cache_key = {'text': question}
                            cached_entities = cache_service.get('entity_extraction', entity_cache_key)
                            
                            if cached_entities:
                                extracted_entities = cached_entities
                            else:
                                # 提取医疗实体
                                entities_future = executor.submit(
                                    kg_service.extract_entities_from_text, question
                                )
                                extracted_entities = entities_future.result()
                                # 缓存实体提取结果
                                cache_service.set('entity_extraction', entity_cache_key, extracted_entities, ttl=600)
                            
                            kg_entities = [entity[0] for entity in extracted_entities]
                            
                            if extracted_entities:
                                # 并行获取扩展建议和实体关系
                                suggestions_futures = []
                                relations_futures = []
                                
                                intent_confidence = intent_result.get('confidence', 0) if intent_result else 0
                                
                                # 为每个实体获取扩展建议
                                for entity_name in kg_entities[:3]:  # 限制处理的实体数量
                                    # 找到实体类型
                                    entity_type = None
                                    for ent_name, ent_type, _ in extracted_entities:
                                        if ent_name == entity_name:
                                            entity_type = ent_type
                                            break
                                    
                                    if entity_type:
                                        # 检查扩展建议缓存
                                        suggestion_cache_key = {
                                            'entity_name': entity_name,
                                            'entity_type': entity_type,
                                            'intent_confidence': intent_confidence
                                        }
                                        cached_suggestions = cache_service.get('kg_expansion', suggestion_cache_key)
                                        
                                        if cached_suggestions:
                                            kg_suggestions.extend(cached_suggestions[:2])
                                        else:
                                            context = {
                                                'intent': intent_result.intent if intent_result else None,
                                                'confidence': intent_confidence
                                            }
                                            suggestions_future = executor.submit(
                                                 kg_service.get_expansion_suggestions,
                                                 entity_name, entity_type, context
                                             )
                                            suggestions_futures.append((suggestions_future, suggestion_cache_key))
                                    
                                    # 获取实体关系
                                    relation_cache_key = {'entity_name': entity_name}
                                    cached_relations = cache_service.get('entity_relations', relation_cache_key)
                                    
                                    if cached_relations:
                                        kg_relations.extend(cached_relations[:2])
                                    else:
                                        entities_found = kg_service.find_entities_by_name(entity_name)
                                        if entities_found:
                                            entity_id = entities_found[0].id
                                            relations_future = executor.submit(
                                                 kg_service.get_related_entities,
                                                 entity_id, max_depth=1
                                             )
                                            relations_futures.append((relations_future, relation_cache_key))
                                
                                # 收集扩展建议结果
                                for future, cache_key in suggestions_futures:
                                    try:
                                        suggestions = future.result()
                                        if suggestions:
                                            kg_suggestions.extend(suggestions[:2])
                                            cache_service.set('kg_expansion', cache_key, suggestions, ttl=600)
                                    except Exception as e:
                                        logging.warning(f"获取KG扩展建议失败: {e}")
                                
                                # 收集实体关系结果
                                for future, cache_key in relations_futures:
                                    try:
                                        relations = future.result()
                                        if relations:
                                            for depth_key, relations_list in relations.items():
                                                relation_names = [rel[0].name for rel in relations_list[:2]]
                                                kg_relations.extend(relation_names)
                                                cache_service.set('entity_relations', cache_key, relation_names, ttl=600)
                                    except Exception as e:
                                        logging.warning(f"获取实体关系失败: {e}")
                            
                            return kg_entities, kg_relations, kg_suggestions
                    
                    # 执行KG增强
                    kg_entities, kg_relations, kg_suggestions = await run_kg_enhancement()
                    
                    # 构建上下文感知的增强查询
                    if kg_suggestions:
                        # 根据意图识别的置信度和查询质量调整扩展词数量
                        intent_confidence = intent_result.get('confidence', 0) if intent_result else 0
                        max_suggestions = 3 if (intent_confidence > 0.7 and query_quality.overall_score > 0.7) else 2
                        kg_enhanced_query = f"{question} {' '.join(kg_suggestions[:max_suggestions])}"
                    
                    logging.info(f"上下文感知KG增强 - 实体: {len(kg_entities)}, 相关实体: {len(kg_relations)}, 扩展建议: {len(kg_suggestions)}")
                    
                except Exception as kg_error:
                    logging.warning(f"KG增强失败: {kg_error}")
                    use_enhanced_kg = False
            else:
                logging.info("查询质量较低，跳过KG增强")
            
            # 3. 医疗关联增强（基于意图识别结果和查询质量优化）
            medical_associations = []
            
            if use_enhanced_kg:  # 只有在查询质量足够高时才进行医疗关联增强
                try:
                    # 检查医疗关联缓存
                    association_cache_key = {
                        'question': question,
                        'department': department.value if department else None,
                        'document_type': document_type.value if document_type else None,
                        'disease_category': disease_category.value if disease_category else None
                    }
                    
                    cached_associations = cache_service.get('medical_associations', association_cache_key)
                    if cached_associations:
                        medical_associations = cached_associations
                        logging.info(f"使用缓存的医疗关联: {len(medical_associations)}个")
                    else:
                        # 并行获取医疗关联
                        async def get_medical_associations():
                            with ThreadPoolExecutor(max_workers=1) as executor:
                                future = executor.submit(
                                     medical_association_service.find_associations,
                                     question,
                                     {
                                         'department': department.value if department else None,
                                         'document_type': document_type.value if document_type else None,
                                         'disease_category': disease_category.value if disease_category else None
                                     }
                                 )
                                associations = future.result()
                                return [
                                    {
                                        "source": assoc.source_entity,
                                        "target": assoc.target_entity,
                                        "type": assoc.association_type.value,
                                        "confidence": assoc.confidence,
                                        "description": assoc.description
                                    }
                                    for assoc in associations
                                ]
                        
                        medical_associations = await get_medical_associations()
                        
                        # 缓存医疗关联结果
                        cache_service.set('medical_associations', association_cache_key, medical_associations, ttl=600)
                        
                        logging.info(f"医疗关联增强完成 - 关联数: {len(medical_associations)}")
                    
                    # 将关联信息添加到查询中，根据意图识别置信度和查询质量调整数量
                    if medical_associations:
                        intent_confidence = intent_result.get('confidence', 0) if intent_result else 0
                        max_associations = 3 if (intent_confidence > 0.7 and query_quality.overall_score > 0.7) else 2
                        association_terms = [assoc["target"] for assoc in medical_associations[:max_associations]]
                        kg_enhanced_query = f"{kg_enhanced_query} {' '.join(association_terms)}"
                    
                    logging.info(f"上下文感知医疗关联增强 - 找到 {len(medical_associations)} 个关联")
                    
                except Exception as assoc_error:
                    logging.warning(f"医疗关联增强失败: {assoc_error}")
            else:
                logging.info("查询质量较低，跳过医疗关联增强")
            
            # 4. 执行增强的医疗搜索
            # 根据查询质量调整搜索参数
            search_k = self.k if query_quality.overall_score > 0.7 else max(3, self.k - 2)
            score_threshold = 0.3 if query_quality.overall_score > 0.7 else 0.5
            
            # 确保kg_enhanced_query已定义
            if 'kg_enhanced_query' not in locals():
                kg_enhanced_query = question
            
            # 转换意图识别结果为枚举类型
            dept_enum = None
            doc_type_enum = None
            disease_cat_enum = None
            
            if intent_result and intent_result.get('department'):
                try:
                    dept_enum = MedicalDepartment(intent_result['department'])
                except ValueError:
                    pass
            
            if intent_result and intent_result.get('document_type'):
                try:
                    doc_type_enum = DocumentType(intent_result['document_type'])
                except ValueError:
                    pass
            
            if intent_result and intent_result.get('disease_category'):
                try:
                    disease_cat_enum = DiseaseCategory(intent_result['disease_category'])
                except ValueError:
                    pass
            
            # 如果没有意图识别结果，使用传入的参数
            if not dept_enum:
                dept_enum = department
            if not doc_type_enum:
                doc_type_enum = document_type
            if not disease_cat_enum:
                disease_cat_enum = disease_category
            
            search_results = self.index_service.search_medical_documents(
                query=kg_enhanced_query,
                department=dept_enum,
                document_type=doc_type_enum,
                disease_category=disease_cat_enum,
                k=search_k,
                score_threshold=score_threshold
            )
            
            # 5. 动态权重调整和结果处理
            citations = []
            ctx_snippets = []
            scores = []
            
            # 检查search_results是否为None
            if search_results is None:
                return [], "", {
                    "error": "搜索服务返回空结果",
                    "intent_recognition": intent_result,
                    "query_quality": {
                        "overall_score": query_quality.overall_score,
                        "level": query_quality.quality_level.value,
                        "clarity_score": query_quality.clarity_score,
                        "specificity_score": query_quality.specificity_score,
                        "medical_relevance": query_quality.medical_relevance,
                        "completeness_score": query_quality.completeness_score,
                        "complexity_score": query_quality.complexity_score,
                        "suggestions": query_quality.suggestions
                    }
                }
            
            # 检查搜索结果
            if not search_results.get("ok", False):
                return [], "", {
                    "error": search_results.get("error", "搜索失败"),
                    "intent_recognition": intent_result,
                    "query_quality": {
                        "overall_score": query_quality.overall_score,
                        "level": query_quality.quality_level.value,
                        "clarity_score": query_quality.clarity_score,
                        "specificity_score": query_quality.specificity_score,
                        "medical_relevance": query_quality.medical_relevance,
                        "completeness_score": query_quality.completeness_score,
                        "complexity_score": query_quality.complexity_score,
                        "suggestions": query_quality.suggestions
                    },
                    "kg_enhancement": {
                        "enabled": use_enhanced_kg,
                        "entities": kg_entities if 'kg_entities' in locals() else [],
                        "relations": kg_relations if 'kg_relations' in locals() else [],
                        "suggestions": kg_suggestions if 'kg_suggestions' in locals() else []
                    },
                    "medical_associations": medical_associations
                }
            
            # 动态权重调整逻辑
            def calculate_dynamic_weights(query_quality, intent_result, kg_enhancement_used, medical_associations_count):
                """根据查询质量和增强效果动态调整权重"""
                base_weights = {
                    'semantic_similarity': 0.4,
                    'medical_relevance': 0.3,
                    'kg_enhancement': 0.2,
                    'medical_associations': 0.1
                }
                
                # 根据查询质量调整
                quality_factor = query_quality.overall_score
                if quality_factor > 0.8:
                    # 高质量查询，增加语义相似度权重
                    base_weights['semantic_similarity'] += 0.1
                    base_weights['medical_relevance'] -= 0.05
                    base_weights['kg_enhancement'] -= 0.05
                elif quality_factor < 0.5:
                    # 低质量查询，增加医疗相关性权重
                    base_weights['medical_relevance'] += 0.15
                    base_weights['semantic_similarity'] -= 0.1
                    base_weights['kg_enhancement'] -= 0.05
                
                # 根据意图识别置信度调整
                if intent_result and intent_result.get('confidence', 0) > 0.8:
                    base_weights['medical_relevance'] += 0.1
                    base_weights['semantic_similarity'] -= 0.1
                
                # 根据KG增强效果调整
                if kg_enhancement_used and len(kg_suggestions) > 0:
                    base_weights['kg_enhancement'] += 0.1
                    base_weights['semantic_similarity'] -= 0.05
                    base_weights['medical_relevance'] -= 0.05
                
                # 根据医疗关联数量调整
                if medical_associations_count > 3:
                    base_weights['medical_associations'] += 0.05
                    base_weights['semantic_similarity'] -= 0.05
                
                # 确保权重和为1
                total_weight = sum(base_weights.values())
                for key in base_weights:
                    base_weights[key] /= total_weight
                
                return base_weights
            
            # 计算动态权重
            dynamic_weights = calculate_dynamic_weights(
                query_quality, 
                intent_result, 
                use_enhanced_kg and len(kg_suggestions) > 0,
                len(medical_associations)
            )
            
            # 再次检查search_results是否为None（防御性编程）
            if search_results is None:
                return [], "", {
                    "error": "搜索结果为空",
                    "intent_recognition": intent_result,
                    "query_quality": {
                        "overall_score": query_quality.overall_score,
                        "level": query_quality.quality_level.value,
                        "clarity_score": query_quality.clarity_score,
                        "specificity_score": query_quality.specificity_score,
                        "medical_relevance": query_quality.medical_relevance,
                        "completeness_score": query_quality.completeness_score,
                        "complexity_score": query_quality.complexity_score,
                        "suggestions": query_quality.suggestions
                    }
                }
            
            results_list = search_results.get("results", [])
            
            # 应用动态权重调整结果排序
            def calculate_weighted_score(result, weights):
                """根据动态权重计算加权分数"""
                base_score = result.get("score", 0.0)
                
                # 语义相似度分数（基础分数）
                semantic_score = base_score * weights['semantic_similarity']
                
                # 医疗相关性分数（基于元数据）
                medical_score = 0.0
                metadata = result.get("metadata", {})
                if metadata.get("department"):
                    medical_score += 0.3
                if metadata.get("evidence_level") in ["A", "B"]:
                    medical_score += 0.4
                if metadata.get("document_type") in ["guideline", "protocol"]:
                    medical_score += 0.3
                medical_score *= weights['medical_relevance']
                
                # KG增强分数
                kg_score = 0.0
                if use_enhanced_kg and kg_suggestions:
                    text_lower = result.get("text", "").lower()
                    for suggestion in kg_suggestions:
                        if suggestion.lower() in text_lower:
                            kg_score += 0.2
                kg_score = min(kg_score, 1.0) * weights['kg_enhancement']
                
                # 医疗关联分数
                association_score = 0.0
                if medical_associations:
                    text_lower = result.get("text", "").lower()
                    for association in medical_associations:
                        # 处理字典格式的关联数据
                        if isinstance(association, dict):
                            target = association.get("target", "")
                            if target and target.lower() in text_lower:
                                association_score += 0.15
                        elif isinstance(association, str):
                            if association.lower() in text_lower:
                                association_score += 0.15
                association_score = min(association_score, 1.0) * weights['medical_associations']
                
                return semantic_score + medical_score + kg_score + association_score
            
            # 重新排序结果
            for result in results_list:
                result["weighted_score"] = calculate_weighted_score(result, dynamic_weights)
            
            # 按加权分数排序
            results_list.sort(key=lambda x: x["weighted_score"], reverse=True)
            
            metadata = {
                "total_results": len(results_list),
                "departments": set(),
                "document_types": set(),
                "evidence_levels": set(),
                "intent_recognition": intent_result,
                "query_quality": {
                    "overall_score": query_quality.overall_score,
                    "level": query_quality.quality_level.value,
                    "clarity_score": query_quality.clarity_score,
                    "specificity_score": query_quality.specificity_score,
                    "medical_relevance": query_quality.medical_relevance,
                    "completeness_score": query_quality.completeness_score,
                    "complexity_score": query_quality.complexity_score,
                    "suggestions": query_quality.suggestions
                },
                "kg_enhancement": {
                    "enabled": use_enhanced_kg,
                    "entities": kg_entities if 'kg_entities' in locals() else [],
                    "relations": kg_relations if 'kg_relations' in locals() else [],
                    "suggestions": kg_suggestions if 'kg_suggestions' in locals() else []
                },
                "medical_associations": medical_associations,
                "dynamic_weights": dynamic_weights
            }
            
            for i, result in enumerate(results_list, start=1):
                text = result["text"]
                score = result["score"]
                doc_metadata = result["metadata"]
                
                snippet_short = (text or "").strip()
                if len(snippet_short) > 500:
                    snippet_short = snippet_short[:500] + "..."
                
                # 收集元数据
                if doc_metadata.get("department"):
                    metadata["departments"].add(doc_metadata["department"])
                if doc_metadata.get("document_type"):
                    metadata["document_types"].add(doc_metadata["document_type"])
                if doc_metadata.get("evidence_level"):
                    metadata["evidence_levels"].add(doc_metadata["evidence_level"])
                
                citations.append({
                    "citation_id": f"med-c{i}",
                    "rank": i,
                    "snippet": (text or "")[:4000],
                    "score": float(score),
                    "department": doc_metadata.get("department"),
                    "document_type": doc_metadata.get("document_type"),
                    "evidence_level": doc_metadata.get("evidence_level"),
                    "source": doc_metadata.get("source", "Unknown"),
                    "title": doc_metadata.get("title", "Untitled")
                })
                
                # 构建上下文片段，包含来源信息
                source_info = f"[来源: {doc_metadata.get('title', 'Unknown')}"
                if doc_metadata.get("evidence_level"):
                    source_info += f", 证据等级: {doc_metadata.get('evidence_level')}"
                source_info += "]"
                
                ctx_snippets.append(f"[{i}] {source_info}\n{snippet_short}")
                scores.append(float(score))
            
            context_text = "\n\n".join(ctx_snippets) if ctx_snippets else "(no medical documents found)"
            
            # 转换set为list以便JSON序列化
            metadata["departments"] = list(metadata["departments"])
            metadata["document_types"] = list(metadata["document_types"])
            metadata["evidence_levels"] = list(metadata["evidence_levels"])
            
            # 确保kg_enhancement字段存在
            if "kg_enhancement" not in metadata:
                metadata["kg_enhancement"] = {
                    "enabled": False,
                    "entities": [],
                    "relations": [],
                    "suggestions": []
                }
            
            # 构建最终结果
            final_result = (citations, context_text, metadata)
            
            # 缓存结果
            cache_service.set('query_result', cache_key, final_result, ttl=300)  # 缓存5分钟
            
            return final_result
            
        except Exception as e:
            print(f"Error in medical_retrieve: {e}")
            return [], "", {"error": str(e)}

    async def medical_answer_stream(
        self,
        question: str,
        citations: list[dict],
        context_text: str,
        metadata: dict,
        session_id: str | None = None,
        enable_safety_check: bool = True
    ) -> AsyncGenerator[dict, None]:
        """
        医疗问答流式生成，集成安全审核
        """
        # 先进行安全检查
        if enable_safety_check:
            # 使用空回答进行初步安全检查
            safety_result = self.review_service.review_medical_qa(question, "")
            
            # 如果安全等级过低，拒绝回答
            if safety_result.safety.level in [SafetyLevel.DANGEROUS, SafetyLevel.BLOCKED]:
                yield {
                    "type": "safety_warning",
                    "data": {
                        "level": safety_result.safety.level.value,
                        "concerns": safety_result.safety.issues,
                        "recommendations": safety_result.safety.recommendations
                    }
                }
                
                warning_message = (
                    "⚠️ **安全提醒**\n\n"
                    "您的问题涉及高风险医疗内容，为了您的安全，建议：\n"
                    f"- {'; '.join(safety_result.safety.recommendations)}\n\n"
                    "请立即咨询专业医生或拨打急救电话。"
                )
                
                yield {"type": "token", "data": warning_message}
                yield {"type": "done", "data": {"used_retrieval": False, "safety_blocked": True}}
                return
        
        # 发送引用信息
        if citations:
            for c in citations:
                yield {"type": "citation", "data": c}
        
        # 发送检索元数据
        yield {"type": "metadata", "data": metadata}
        
        # 组装消息
        llm = self._get_llm()
        history_msgs = await self.get_history(session_id) if session_id else []
        
        if context_text and context_text != "(no medical documents found)":
            user_prompt = self.medical_answer_prompt.format(
                question=question, 
                context=context_text
            )
            has_context = True
        else:
            user_prompt = self.no_context_prompt.format(question=question)
            has_context = False
        
        # 构建完整消息序列
        msgs = [{"role": "system", "content": self.system_instruction}]
        msgs.extend(history_msgs)
        msgs.append({"role": "user", "content": user_prompt})
        
        # 生成回答
        final_text_parts: list[str] = []
        
        try:
            async for chunk in llm.astream(msgs):
                delta = getattr(chunk, "content", None)
                if delta:
                    final_text_parts.append(delta)
                    yield {"type": "token", "data": delta}
        except Exception:
            # 回退到非流式
            resp = await llm.ainvoke(msgs)
            text = resp.content or ""
            final_text_parts.append(text)
            for i in range(0, len(text), 20):
                yield {"type": "token", "data": text[i:i+20]}
                await asyncio.sleep(0.005)
        
        # 生成的完整回答
        full_answer = "".join(final_text_parts)
        
        # 对生成的回答进行质量和安全评估
        if enable_safety_check and full_answer:
            answer_review = self.review_service.review_medical_qa(question, full_answer, citations)
            
            # 发送质量评估信息
            yield {
                "type": "quality_assessment",
                "data": {
                    "quality_level": answer_review.quality.level.value,
                    "quality_score": answer_review.quality.score,
                    "quality_metrics": answer_review.quality.metrics,
                    "safety_level": answer_review.safety.level.value,
                    "safety_score": answer_review.safety.score
                }
            }
            

        
        # 保存会话历史
        if session_id:
            await self.append_history(session_id, "user", question)
            await self.append_history(session_id, "assistant", full_answer)
        
        yield {
            "type": "done", 
            "data": {
                "used_retrieval": has_context,
                "safety_checked": enable_safety_check,
                "citations_count": len(citations)
            }
        }

    async def symptom_based_search(self, symptoms: List[str]) -> dict:
        """基于症状的疾病搜索"""
        try:
            results = await self.index_service.search_by_symptoms(symptoms)
            return {
                "success": True,
                "results": results,
                "symptoms_analyzed": symptoms
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "symptoms_analyzed": symptoms
            }

    async def drug_interaction_search(self, drugs: List[str]) -> dict:
        """药物相互作用搜索"""
        try:
            # 查找药物相互作用
            interactions = await self.association_service.find_drug_interactions(drugs)
            
            # 构建药物相互作用查询
            drug_query = " ".join(drugs) + " 相互作用 副作用 禁忌"
            
            # 执行搜索
            citations, context_text, metadata = await self.medical_retrieve(drug_query)
            
            # 分析相互作用风险
            risk_level = "low"
            if interactions:
                max_confidence = max(interaction.confidence for interaction in interactions)
                if max_confidence > 0.8:
                    risk_level = "high"
                elif max_confidence > 0.6:
                    risk_level = "medium"
            
            # 添加药物相互作用特定信息
            drug_interaction_analysis = {
                'drugs': drugs,
                'interaction_risk': risk_level,
                'found_interactions': [
                    {
                        'drug1': interaction.source,
                        'drug2': interaction.target,
                        'confidence': interaction.confidence,
                        'evidence': interaction.evidence[:2] if interaction.evidence else []
                    }
                    for interaction in interactions
                ],
                'recommendations': self._generate_drug_recommendations(interactions, risk_level)
            }
            
            return {
                "success": True,
                "citations": citations,
                "context_text": context_text,
                "metadata": metadata,
                "drug_interaction_analysis": drug_interaction_analysis,
                "drugs_analyzed": drugs
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "drugs_analyzed": drugs
            }

    def _generate_drug_recommendations(self, interactions: List, risk_level: str) -> List[str]:
        """生成药物使用建议"""
        recommendations = []
        
        if risk_level == "high":
            recommendations.extend([
                "⚠️ 发现高风险药物相互作用，请立即咨询医生",
                "不建议同时使用这些药物",
                "如必须使用，需要医生严密监控"
            ])
        elif risk_level == "medium":
            recommendations.extend([
                "⚠️ 发现中等风险药物相互作用",
                "请咨询医生或药师调整用药方案",
                "注意观察不良反应症状"
            ])
        else:
            recommendations.extend([
                "未发现明显药物相互作用",
                "仍建议咨询医生确认用药安全性",
                "按医嘱正确服用药物"
            ])
        
        if interactions:
            recommendations.append(f"发现 {len(interactions)} 个潜在相互作用")
        
        return recommendations

    async def enhanced_symptom_analysis(self, symptoms: List[str]) -> dict:
        """增强症状分析"""
        try:
            # 查找症状-疾病关联
            symptom_associations = await self.association_service.find_symptom_disease_associations(symptoms)
            
            # 构建症状查询
            symptom_query = " ".join(symptoms) + " 症状 诊断 疾病 治疗"
            
            # 执行搜索
            citations, context_text, metadata = await self.medical_retrieve(symptom_query)
            
            # 分析可能的疾病
            possible_diseases = {}
            for assoc in symptom_associations:
                disease = assoc.target
                if disease not in possible_diseases:
                    possible_diseases[disease] = {
                        'confidence': 0,
                        'matching_symptoms': [],
                        'total_associations': 0
                    }
                
                possible_diseases[disease]['confidence'] = max(
                    possible_diseases[disease]['confidence'], 
                    assoc.confidence
                )
                possible_diseases[disease]['matching_symptoms'].append(assoc.source)
                possible_diseases[disease]['total_associations'] += 1
            
            # 按置信度排序
            sorted_diseases = sorted(
                possible_diseases.items(), 
                key=lambda x: (x[1]['confidence'], x[1]['total_associations']), 
                reverse=True
            )
            
            # 添加症状分析结果
            symptom_analysis = {
                'input_symptoms': symptoms,
                'possible_diseases': [
                    {
                        'disease': disease,
                        'confidence': data['confidence'],
                        'matching_symptoms': data['matching_symptoms'],
                        'symptom_count': len(data['matching_symptoms']),
                        'recommendation': self._generate_disease_recommendation(data['confidence'])
                    }
                    for disease, data in sorted_diseases[:10]
                ],
                'general_recommendations': [
                    "以上分析仅供参考，不能替代专业医疗诊断",
                    "如症状持续或加重，请及时就医",
                    "建议记录症状的详细情况和时间"
                ]
            }
            
            return {
                "success": True,
                "citations": citations,
                "context_text": context_text,
                "metadata": metadata,
                "symptom_analysis": symptom_analysis,
                "symptoms_analyzed": symptoms
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "symptoms_analyzed": symptoms
            }

    def _generate_disease_recommendation(self, confidence: float) -> str:
        """生成疾病建议"""
        if confidence > 0.8:
            return "高度相关，建议尽快就医确诊"
        elif confidence > 0.6:
            return "中度相关，建议咨询医生"
        else:
            return "低度相关，可继续观察"

# 全局实例
enhanced_rag_service = EnhancedMedicalRAGService()

# 兼容性函数
async def get_history(session_id: str) -> list[dict]:
    return await enhanced_rag_service.get_history(session_id)

async def append_history(session_id: str, role: str, content: str) -> None:
    await enhanced_rag_service.append_history(session_id, role, content)

async def clear_history(session_id: str) -> None:
    await enhanced_rag_service.clear_history(session_id)

async def medical_retrieve(
    question: str, 
    department: Optional[str] = None,
    document_type: Optional[str] = None,
    disease_category: Optional[str] = None
) -> tuple[list[dict], str, dict]:
    # 转换字符串参数为枚举
    dept_enum = None
    if department:
        try:
            dept_enum = MedicalDepartment(department)
        except ValueError:
            pass
    
    doc_type_enum = None
    if document_type:
        try:
            doc_type_enum = DocumentType(document_type)
        except ValueError:
            pass
    
    disease_cat_enum = None
    if disease_category:
        try:
            disease_cat_enum = DiseaseCategory(disease_category)
        except ValueError:
            pass
    
    return await enhanced_rag_service.medical_retrieve(
        question, dept_enum, doc_type_enum, disease_cat_enum
    )

async def medical_answer_stream(
    question: str,
    citations: list[dict],
    context_text: str,
    metadata: dict,
    session_id: str | None = None,
    enable_safety_check: bool = True
) -> AsyncGenerator[dict, None]:
    async for item in enhanced_rag_service.medical_answer_stream(
        question, citations, context_text, metadata, session_id, enable_safety_check
    ):
        yield item