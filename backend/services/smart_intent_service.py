"""
智能医疗意图识别服务（简化版）
基于简化分类体系进行意图识别，提高匹配成功率和用户体验
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from .qwen_intent_service import QwenMedicalIntentRecognizer
from .medical_intent_service import MedicalIntentRecognizer
from .enhanced_index_service import enhanced_index_service
from .medical_taxonomy import MedicalDepartment, DocumentType, DiseaseCategory

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartMedicalIntentRecognizer:
    """智能医疗意图识别器（简化版）"""
    
    def __init__(self):
        """初始化智能意图识别器"""
        self.qwen_recognizer = QwenMedicalIntentRecognizer()
        self.fallback_recognizer = MedicalIntentRecognizer()
        
        # 缓存系统资源信息
        self._system_resources = None
        self._last_resource_update = None
        
        # 科室映射规则（简化版）
        self.department_mapping = {
            # 内科系统映射
            "心血管科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "呼吸科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "消化科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "内分泌科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "肾内科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "血液科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "肿瘤科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "风湿科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "神经内科": MedicalDepartment.INTERNAL_MEDICINE.value,
            
            # 外科系统映射
            "普外科": MedicalDepartment.SURGERY.value,
            "骨科": MedicalDepartment.SURGERY.value,
            "神经外科": MedicalDepartment.SURGERY.value,
            "胸外科": MedicalDepartment.SURGERY.value,
            "泌尿外科": MedicalDepartment.SURGERY.value,
            "整形外科": MedicalDepartment.SURGERY.value,
            
            # 专科系统映射
            "眼科": MedicalDepartment.SPECIALIZED.value,
            "耳鼻喉科": MedicalDepartment.SPECIALIZED.value,
            "皮肤科": MedicalDepartment.SPECIALIZED.value,
            "口腔科": MedicalDepartment.SPECIALIZED.value,
            "康复科": MedicalDepartment.SPECIALIZED.value,
            "影像科": MedicalDepartment.SPECIALIZED.value,
            "检验科": MedicalDepartment.SPECIALIZED.value,
            "病理科": MedicalDepartment.SPECIALIZED.value,
            "药学科": MedicalDepartment.SPECIALIZED.value,
            
            # 儿科保持独立
            "儿科": MedicalDepartment.PEDIATRICS.value,
            "新生儿科": MedicalDepartment.PEDIATRICS.value,
            
            # 妇产科保持独立
            "妇科": MedicalDepartment.OBSTETRICS_GYNECOLOGY.value,
            "产科": MedicalDepartment.OBSTETRICS_GYNECOLOGY.value,
            "妇产科": MedicalDepartment.OBSTETRICS_GYNECOLOGY.value,
            
            # 急诊科保持独立
            "急诊科": MedicalDepartment.EMERGENCY.value,
            "重症医学科": MedicalDepartment.EMERGENCY.value,
            "ICU": MedicalDepartment.EMERGENCY.value,
        }
        
        # 文档类型映射规则（简化版）
        self.document_type_mapping = {
            # 临床指南类
            "临床指南": DocumentType.CLINICAL_GUIDELINE.value,
            "诊疗指南": DocumentType.CLINICAL_GUIDELINE.value,
            "诊断标准": DocumentType.CLINICAL_GUIDELINE.value,
            "专家共识": DocumentType.CLINICAL_GUIDELINE.value,
            "预防指南": DocumentType.CLINICAL_GUIDELINE.value,
            "感控指南": DocumentType.CLINICAL_GUIDELINE.value,
            "护理指南": DocumentType.CLINICAL_GUIDELINE.value,
            
            # 治疗方案类
            "治疗方案": DocumentType.TREATMENT_PROTOCOL.value,
            "治疗指南": DocumentType.TREATMENT_PROTOCOL.value,
            "急救流程": DocumentType.TREATMENT_PROTOCOL.value,
            "质量标准": DocumentType.TREATMENT_PROTOCOL.value,
            "诊疗规范": DocumentType.TREATMENT_PROTOCOL.value,
            "康复指南": DocumentType.TREATMENT_PROTOCOL.value,
            
            # 药物参考类
            "药物说明书": DocumentType.DRUG_REFERENCE.value,
            "用药指南": DocumentType.DRUG_REFERENCE.value,
            "药品手册": DocumentType.DRUG_REFERENCE.value,
            
            # 操作指南类
            "手术操作": DocumentType.PROCEDURE_GUIDE.value,
            "检验参考": DocumentType.PROCEDURE_GUIDE.value,
            "影像图谱": DocumentType.PROCEDURE_GUIDE.value,
            "操作规程": DocumentType.PROCEDURE_GUIDE.value,
            "技术规范": DocumentType.PROCEDURE_GUIDE.value,
            
            # 综合参考类
            "病例研究": DocumentType.GENERAL_REFERENCE.value,
            "研究论文": DocumentType.GENERAL_REFERENCE.value,
            "医学教材": DocumentType.GENERAL_REFERENCE.value,
            "护理手册": DocumentType.GENERAL_REFERENCE.value,
            "患者教育": DocumentType.GENERAL_REFERENCE.value,
        }
        
        # 疾病分类映射规则（简化版）
        self.disease_category_mapping = {
            # 心血管系统疾病
            "循环系统疾病": DiseaseCategory.CARDIOVASCULAR.value,
            "心血管疾病": DiseaseCategory.CARDIOVASCULAR.value,
            
            # 呼吸系统疾病
            "呼吸系统疾病": DiseaseCategory.RESPIRATORY.value,
            
            # 消化系统疾病
            "消化系统疾病": DiseaseCategory.DIGESTIVE.value,
            
            # 神经系统疾病
            "神经系统疾病": DiseaseCategory.NEUROLOGICAL.value,
            "视觉系统疾病": DiseaseCategory.NEUROLOGICAL.value,
            "耳部疾病": DiseaseCategory.NEUROLOGICAL.value,
            
            # 精神心理疾病
            "精神、行为和神经发育障碍": DiseaseCategory.MENTAL_DISORDERS.value,
            "抑郁症": DiseaseCategory.MENTAL_DISORDERS.value,
            "焦虑症": DiseaseCategory.MENTAL_DISORDERS.value,
            
            # 感染性疾病
            "感染性疾病": DiseaseCategory.INFECTIOUS.value,
            "病毒感染": DiseaseCategory.INFECTIOUS.value,
            "细菌感染": DiseaseCategory.INFECTIOUS.value,
            
            # 慢性疾病
            "肿瘤": DiseaseCategory.CHRONIC_DISEASES.value,
            "内分泌、营养和代谢疾病": DiseaseCategory.CHRONIC_DISEASES.value,
            "血液及造血器官疾病": DiseaseCategory.CHRONIC_DISEASES.value,
            "免疫系统疾病": DiseaseCategory.CHRONIC_DISEASES.value,
            "肌肉骨骼系统疾病": DiseaseCategory.CHRONIC_DISEASES.value,
            "糖尿病": DiseaseCategory.CHRONIC_DISEASES.value,
            
            # 常见病症
            "皮肤疾病": DiseaseCategory.GENERAL_CONDITIONS.value,
            "泌尿生殖系统疾病": DiseaseCategory.GENERAL_CONDITIONS.value,
            "妊娠、分娩和产褥期": DiseaseCategory.GENERAL_CONDITIONS.value,
            "围产期疾病": DiseaseCategory.GENERAL_CONDITIONS.value,
            "先天性畸形": DiseaseCategory.GENERAL_CONDITIONS.value,
            "损伤、中毒和外因": DiseaseCategory.GENERAL_CONDITIONS.value,
        }
    
    def _detect_is_medical(self, query: str) -> Tuple[bool, float, List[str]]:
        """判断是否为医疗问题，返回是否、置信度和命中词"""
        medical_signals = [
            "症状", "诊断", "治疗", "用药", "药物", "检查", "检验", "手术",
            "指南", "共识", "规范", "医生", "医院", "科", "病", "疾病",
            "患者", "康复", "急救", "临床", "处方", "剂量", "护理"
        ]
        matched = [w for w in medical_signals if w in query]
        score = min(1.0, 0.15 * len(matched))
        # 进一步加权：出现具体疾病词提高分数
        disease_hint_signals = ["抑郁", "焦虑", "高血压", "糖尿病", "肺炎", "胃炎", "骨折", "肿瘤"]
        if any(h in query for h in disease_hint_signals):
            score = min(1.0, score + 0.3)
        is_medical = score >= 0.3
        return is_medical, score, matched
    
    def _generate_candidates(self, intent: Dict[str, Any], system_resources: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
        """根据识别结果与系统资源生成候选项（医生端）"""
        candidates = {
            "candidate_departments": [],
            "candidate_document_types": [],
            "candidate_disease_categories": []
        }
        system_resources = system_resources or {"departments": [], "document_types": [], "disease_categories": []}
        
        # 科室候选
        dept = intent.get("department")
        if dept:
            candidates["candidate_departments"].append(dept)
        for k, v in self.department_mapping.items():
            if v == dept and k not in candidates["candidate_departments"]:
                candidates["candidate_departments"].append(k)
        for d in system_resources.get("departments", [])[:3]:
            if d not in candidates["candidate_departments"]:
                candidates["candidate_departments"].append(d)
        candidates["candidate_departments"] = candidates["candidate_departments"][:3]
        
        # 文档类型候选
        doc = intent.get("document_type")
        if doc:
            candidates["candidate_document_types"].append(doc)
        for k, v in self.document_type_mapping.items():
            if v == doc and k not in candidates["candidate_document_types"]:
                candidates["candidate_document_types"].append(k)
        for t in system_resources.get("document_types", [])[:3]:
            if t not in candidates["candidate_document_types"]:
                candidates["candidate_document_types"].append(t)
        candidates["candidate_document_types"] = candidates["candidate_document_types"][:3]
        
        # 疾病分类候选
        dis = intent.get("disease_category")
        if dis:
            candidates["candidate_disease_categories"].append(dis)
        for k, v in self.disease_category_mapping.items():
            if v == dis and k not in candidates["candidate_disease_categories"]:
                candidates["candidate_disease_categories"].append(k)
        for c in system_resources.get("disease_categories", [])[:3]:
            if c not in candidates["candidate_disease_categories"]:
                candidates["candidate_disease_categories"].append(c)
        candidates["candidate_disease_categories"] = candidates["candidate_disease_categories"][:3]
        
        return candidates
    
    def recognize_intent(self, query: str) -> Dict[str, Any]:
        """识别用户查询意图"""
        # 0. 医疗问题判定
        is_medical, medical_score, matched_terms = self._detect_is_medical(query)
        if not is_medical:
            return {
                'success': True,
                'query': query,
                'is_medical': False,
                'confidence': medical_score,
                'department': None,
                'document_type': None,
                'disease_category': None,
                'keywords': matched_terms,
                'reasoning': '非医疗问题或与医疗知识库无显著关联',
                'method': 'rule_detection'
            }
        
        try:
            # 首先使用千问模型进行意图识别
            qwen_result = self.qwen_recognizer.recognize_intent(query)
            
            if qwen_result and qwen_result.get('success', False):
                qwen_result['is_medical'] = True
                # 优化识别结果
                optimized_result = self.optimize_intent_result(qwen_result)
                optimized_result['method'] = qwen_result.get('method', 'qwen_llm')
                optimized_result['success'] = True
                return optimized_result
            else:
                # 千问识别失败，使用备用识别器
                logger.warning("千问意图识别失败，使用备用识别器")
                fallback_result = self.fallback_recognizer.recognize_intent(query)
                fallback_result['is_medical'] = True
                fallback_result['method'] = 'fallback_rules'
                fallback_result['success'] = True
                return self.optimize_intent_result(fallback_result)
                
        except Exception as e:
            logger.error(f"意图识别过程中发生错误: {str(e)}")
            # 返回基础结果
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'is_medical': True,
                'department': None,
                'document_type': None,
                'disease_category': None,
                'keywords': [],
                'confidence': 0.0,
                'method': 'error_fallback'
            }
    
    def optimize_intent_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """优化意图识别结果，基于简化分类体系"""
        if not result or not result.get('success', False):
            return result
        
        try:
            # 获取系统资源
            system_resources = self.get_system_resources()
            
            if not system_resources:
                logger.warning("系统中没有可用的向量库，返回原始结果")
                return result
            
            # 优化科室
            original_department = result.get('department')
            optimized_department = self.find_best_department_match(
                original_department, system_resources.get('departments', [])
            )
            
            # 优化文档类型
            original_doc_type = result.get('document_type')
            optimized_doc_type = self.find_best_document_type_match(
                original_doc_type, system_resources.get('document_types', [])
            )
            
            # 优化疾病分类
            original_disease = result.get('disease_category')
            optimized_disease = self.find_best_disease_category_match(
                original_disease, system_resources.get('disease_categories', [])
            )
            
            # 更新结果
            result.update({
                'department': optimized_department,
                'document_type': optimized_doc_type,
                'disease_category': optimized_disease,
                'optimization_applied': True,
                'original_department': original_department,
                'original_document_type': original_doc_type,
                'original_disease_category': original_disease
            })
            
            # 候选项
            candidates = self._generate_candidates(result, system_resources)
            result.update(candidates)
            
            return result
            
        except Exception as e:
            logger.error(f"优化意图结果时发生错误: {str(e)}")
            return result
    
    def find_best_department_match(self, target_department: str, available_departments: List[str]) -> Optional[str]:
        """寻找最佳科室匹配（简化版）"""
        if not target_department:
            return None
        
        # 1. 直接匹配
        if target_department in available_departments:
            return target_department
        
        # 2. 简化映射匹配
        mapped_department = self.department_mapping.get(target_department)
        if mapped_department and mapped_department in available_departments:
            return mapped_department
        
        # 3. 智能回退到通用分类
        for dept_enum in MedicalDepartment:
            if dept_enum.value in available_departments:
                # 根据原始科室特征选择最合适的简化分类
                if any(keyword in target_department for keyword in ['心血管', '呼吸', '消化', '内分泌', '肾内', '血液', '神经内']):
                    if MedicalDepartment.INTERNAL_MEDICINE.value in available_departments:
                        return MedicalDepartment.INTERNAL_MEDICINE.value
                elif any(keyword in target_department for keyword in ['外科', '骨科', '手术']):
                    if MedicalDepartment.SURGERY.value in available_departments:
                        return MedicalDepartment.SURGERY.value
                elif any(keyword in target_department for keyword in ['儿科', '小儿', '新生儿']):
                    if MedicalDepartment.PEDIATRICS.value in available_departments:
                        return MedicalDepartment.PEDIATRICS.value
                elif any(keyword in target_department for keyword in ['妇', '产科']):
                    if MedicalDepartment.OBSTETRICS_GYNECOLOGY.value in available_departments:
                        return MedicalDepartment.OBSTETRICS_GYNECOLOGY.value
                elif any(keyword in target_department for keyword in ['急诊', '重症', 'ICU']):
                    if MedicalDepartment.EMERGENCY.value in available_departments:
                        return MedicalDepartment.EMERGENCY.value
        
        # 4. 最后回退到内科系统（最通用）
        if MedicalDepartment.INTERNAL_MEDICINE.value in available_departments:
            return MedicalDepartment.INTERNAL_MEDICINE.value
        
        return None
    
    def find_best_document_type_match(self, target_doc_type: str, available_doc_types: List[str]) -> Optional[str]:
        """寻找最佳文档类型匹配（简化版）"""
        if not target_doc_type:
            return None
        
        # 1. 直接匹配
        if target_doc_type in available_doc_types:
            return target_doc_type
        
        # 2. 简化映射匹配
        mapped_doc_type = self.document_type_mapping.get(target_doc_type)
        if mapped_doc_type and mapped_doc_type in available_doc_types:
            return mapped_doc_type
        
        # 3. 智能回退到通用类型
        for doc_enum in DocumentType:
            if doc_enum.value in available_doc_types:
                if any(keyword in target_doc_type for keyword in ['指南', '标准', '共识', '规范']):
                    if DocumentType.CLINICAL_GUIDELINE.value in available_doc_types:
                        return DocumentType.CLINICAL_GUIDELINE.value
                elif any(keyword in target_doc_type for keyword in ['治疗', '急救', '质量']):
                    if DocumentType.TREATMENT_PROTOCOL.value in available_doc_types:
                        return DocumentType.TREATMENT_PROTOCOL.value
                elif any(keyword in target_doc_type for keyword in ['药', '用药', '说明书']):
                    if DocumentType.DRUG_REFERENCE.value in available_doc_types:
                        return DocumentType.DRUG_REFERENCE.value
                elif any(keyword in target_doc_type for keyword in ['操作', '手术', '检查', '技术']):
                    if DocumentType.PROCEDURE_GUIDE.value in available_doc_types:
                        return DocumentType.PROCEDURE_GUIDE.value
        
        # 4. 最后回退到综合参考（最通用）
        if DocumentType.GENERAL_REFERENCE.value in available_doc_types:
            return DocumentType.GENERAL_REFERENCE.value
        
        return None
    
    def find_best_disease_category_match(self, target_disease: str, available_diseases: List[str]) -> Optional[str]:
        """寻找最佳疾病分类匹配（简化版）"""
        if not target_disease:
            return None
        
        # 1. 直接匹配
        if target_disease in available_diseases:
            return target_disease
        
        # 2. 简化映射匹配
        mapped_disease = self.disease_category_mapping.get(target_disease)
        if mapped_disease and mapped_disease in available_diseases:
            return mapped_disease
        
        # 3. 智能回退到通用分类
        for disease_enum in DiseaseCategory:
            if disease_enum.value in available_diseases:
                # 根据原始疾病分类特征选择最合适的简化分类
                if any(keyword in target_disease for keyword in ['心脏', '心血管', '循环']):
                    if DiseaseCategory.CARDIOVASCULAR.value in available_diseases:
                        return DiseaseCategory.CARDIOVASCULAR.value
                elif any(keyword in target_disease for keyword in ['肺', '呼吸', '气管']):
                    if DiseaseCategory.RESPIRATORY.value in available_diseases:
                        return DiseaseCategory.RESPIRATORY.value
                elif any(keyword in target_disease for keyword in ['胃', '肠', '肝', '消化']):
                    if DiseaseCategory.DIGESTIVE.value in available_diseases:
                        return DiseaseCategory.DIGESTIVE.value
                elif any(keyword in target_disease for keyword in ['神经', '脑', '视觉', '耳']):
                    if DiseaseCategory.NEUROLOGICAL.value in available_diseases:
                        return DiseaseCategory.NEUROLOGICAL.value
                elif any(keyword in target_disease for keyword in ['精神', '心理', '行为']):
                    if DiseaseCategory.MENTAL_DISORDERS.value in available_diseases:
                        return DiseaseCategory.MENTAL_DISORDERS.value
                elif any(keyword in target_disease for keyword in ['感染', '病毒', '细菌']):
                    if DiseaseCategory.INFECTIOUS.value in available_diseases:
                        return DiseaseCategory.INFECTIOUS.value
                elif any(keyword in target_disease for keyword in ['肿瘤', '癌', '糖尿病', '慢性']):
                    if DiseaseCategory.CHRONIC_DISEASES.value in available_diseases:
                        return DiseaseCategory.CHRONIC_DISEASES.value
        
        # 4. 最后回退到常见病症（最通用）
        if DiseaseCategory.GENERAL_CONDITIONS.value in available_diseases:
            return DiseaseCategory.GENERAL_CONDITIONS.value
        
        return None
    
    def get_system_resources(self) -> Optional[Dict[str, List[str]]]:
        """获取系统可用资源"""
        try:
            # 从增强索引服务获取系统资源
            resources = enhanced_index_service.get_available_resources()
            
            if resources:
                self._system_resources = resources
                logger.info(f"获取到系统资源: {len(resources.get('departments', []))} 个科室, "
                          f"{len(resources.get('document_types', []))} 个文档类型, "
                          f"{len(resources.get('disease_categories', []))} 个疾病分类")
            
            return resources
            
        except Exception as e:
            logger.error(f"获取系统资源时发生错误: {str(e)}")
            return None

# 创建全局实例
smart_intent_recognizer = SmartMedicalIntentRecognizer()

def recognize_medical_intent(query: str) -> Dict[str, Any]:
    """识别医疗查询意图的便捷函数"""
    return smart_intent_recognizer.recognize_intent(query)

if __name__ == "__main__":
    # 测试示例
    recognizer = SmartMedicalIntentRecognizer()
    
    test_queries = [
        "高血压的治疗方法有哪些？",
        "儿童发热的处理流程",
        "糖尿病患者的用药指南",
        "骨折后的康复训练"
    ]
    
    for query in test_queries:
        print(f"\n查询: {query}")
        result = recognizer.recognize_intent(query)
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")