# services/enhanced_rag_service.py
from __future__ import annotations
import os, asyncio, textwrap
from typing import List, Dict, Any, Tuple, AsyncGenerator, Optional
from typing_extensions import TypedDict

from dotenv import load_dotenv
load_dotenv(override=True)

from langchain_community.chat_models import ChatTongyi
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from collections import defaultdict
from langchain.embeddings.base import Embeddings
import dashscope
from http import HTTPStatus

# 导入医疗相关服务
from .medical_safety_service import MedicalReviewService, SafetyLevel, QualityLevel
from .enhanced_index_service import EnhancedMedicalIndexService
from .medical_knowledge_graph import MedicalKnowledgeGraphService, kg_service
from .medical_association_service import MedicalAssociationService, medical_association_service, AssociationType
from .medical_taxonomy import MedicalDepartment, DocumentType, DiseaseCategory

# 存储结构：sessions[session_id] = [{"role":"user|assistant","content":"..."}...]
_sessions: dict[str, list[dict]] = defaultdict(list)

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
        self.score_tau_top1 = 1.5  # 更严格的阈值
        self.score_tau_mean3 = 2.0
        
        # 医疗专用系统指令
        self.system_instruction = (
            "你是一个专业的医疗问答助手，基于权威医疗文献和临床指南提供准确、安全的医疗信息。\n"
            "重要提醒：\n"
            "1. 你提供的信息仅供参考，不能替代专业医生的诊断和治疗建议\n"
            "2. 对于紧急医疗情况，请立即就医或拨打急救电话\n"
            "3. 任何药物使用都应在医生指导下进行\n"
            "4. 如果对医疗信息不确定，请明确说明并建议咨询专业医生\n"
            "请基于检索到的权威医疗文档回答问题，确保信息的准确性和安全性。"
        )
        
        self.medical_answer_prompt = (
            "基于以下医疗文档回答用户问题：\n\n"
            "问题：{question}\n\n"
            "相关医疗文档：\n{context}\n\n"
            "回答要求：\n"
            "1. 基于提供的权威医疗文档回答\n"
            "2. 使用专业但易懂的语言\n"
            "3. 明确标注信息来源和证据等级\n"
            "4. 如有不确定性，明确说明\n"
            "5. 提醒用户咨询专业医生\n"
            "6. 使用Markdown格式，结构清晰\n"
        )
        
        self.no_context_prompt = (
            "抱歉，在当前的医疗知识库中未找到与您问题直接相关的权威文档。\n"
            "问题：{question}\n\n"
            "建议：\n"
            "1. 请咨询专业医生获取准确的医疗建议\n"
            "2. 可以尝试重新描述问题或使用更具体的医学术语\n"
            "3. 对于紧急情况，请立即就医\n"
        )

    def get_history(self, session_id: str) -> list[dict]:
        """获取会话历史"""
        return _sessions.get(session_id, [])

    def append_history(self, session_id: str, role: str, content: str) -> None:
        """添加会话历史"""
        _sessions[session_id].append({"role": role, "content": content})

    def clear_history(self, session_id: str) -> None:
        """清除会话历史"""
        _sessions.pop(session_id, None)

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
        disease_category: Optional[DiseaseCategory] = None
    ) -> tuple[list[dict], str, dict]:
        """
        医疗检索功能
        返回 (citations, context_text, metadata)
        """
        try:
            # 使用知识图谱增强查询
            kg_enhancement = await self.kg_service.enhance_query_with_kg(question)
            
            # 查找相关医疗关联
            associations = self.association_service.find_associations(
                query=question,
                confidence_threshold=0.6,
                max_results=10
            )
            
            # 构建增强后的查询
            enhanced_query = question
            if kg_enhancement.get("suggested_expansions"):
                # 添加相关实体到查询中
                expansions = kg_enhancement["suggested_expansions"][:3]  # 限制扩展数量
                enhanced_query += " " + " ".join(expansions)
            
            # 基于关联扩展查询
            association_terms = []
            for assoc in associations.associations[:5]:  # 取前5个最相关的关联
                association_terms.extend([assoc.source, assoc.target])
            
            if association_terms:
                association_query = " ".join(set(association_terms))
                enhanced_query = f"{enhanced_query} {association_query}"
            
            # 使用增强的医疗搜索
            search_results = self.index_service.search_medical_documents(
                query=enhanced_query,
                department=department.value if department else None,
                document_type=document_type.value if document_type else None,
                disease_category=disease_category.value if disease_category else None,
                k=self.k
            )
            
            citations = []
            ctx_snippets = []
            scores = []
            
            # 检查搜索结果
            if not search_results.get("ok", False):
                return [], "", {"error": search_results.get("error", "搜索失败")}
            
            results_list = search_results.get("results", [])
            metadata = {
                "total_results": len(results_list),
                "departments": set(),
                "document_types": set(),
                "evidence_levels": set(),
                "kg_enhancement": kg_enhancement
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
            
            # 添加医疗关联信息到元数据
            metadata["medical_associations"] = {
                "total_found": associations.total_count,
                "associations": [
                    {
                        "source": assoc.source,
                        "target": assoc.target,
                        "type": assoc.association_type.value,
                        "confidence": assoc.confidence
                    }
                    for assoc in associations.associations[:5]
                ]
            }
            
            # 转换set为list以便JSON序列化
            metadata["departments"] = list(metadata["departments"])
            metadata["document_types"] = list(metadata["document_types"])
            metadata["evidence_levels"] = list(metadata["evidence_levels"])
            
            return citations, context_text, metadata
            
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
        history_msgs = self.get_history(session_id) if session_id else []
        
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
            
            # 如果质量或安全性不足，添加警告
            if (answer_review.quality.level == QualityLevel.LOW or 
                answer_review.safety.level in [SafetyLevel.WARNING, SafetyLevel.DANGEROUS]):
                
                warning = "\n\n⚠️ **重要提醒**: 此回答仅供参考，请务必咨询专业医生获取准确的医疗建议。"
                yield {"type": "token", "data": warning}
        
        # 添加医疗免责声明
        disclaimer = (
            "\n\n---\n"
            "**医疗免责声明**: 以上信息仅供教育和参考目的，不能替代专业医疗建议、诊断或治疗。"
            "如有健康问题，请咨询合格的医疗专业人员。"
        )
        yield {"type": "token", "data": disclaimer}
        
        # 保存会话历史
        if session_id:
            self.append_history(session_id, "user", question)
            self.append_history(session_id, "assistant", full_answer)
        
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
def get_history(session_id: str) -> list[dict]:
    return enhanced_rag_service.get_history(session_id)

def append_history(session_id: str, role: str, content: str) -> None:
    enhanced_rag_service.append_history(session_id, role, content)

def clear_history(session_id: str) -> None:
    enhanced_rag_service.clear_history(session_id)

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