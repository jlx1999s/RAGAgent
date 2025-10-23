"""
智能医疗意图识别服务
基于系统实际资源进行意图识别，避免过于严格的识别导致检索失败
支持简化分类体系，提高匹配成功率
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from .qwen_intent_service import QwenMedicalIntentRecognizer
from .medical_intent_service import MedicalIntentRecognizer
from .enhanced_index_service import enhanced_index_service

# 导入简化分类体系
from services.medical_taxonomy import MedicalDepartment, DocumentType, DiseaseCategory

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartMedicalIntentRecognizer:
    """智能医疗意图识别器"""
    
    def __init__(self):
        """初始化智能意图识别器"""
        self.qwen_recognizer = QwenMedicalIntentRecognizer()
        self.fallback_recognizer = MedicalIntentRecognizer()
        
        # 缓存系统资源信息
        self._system_resources = None
        self._last_resource_update = None
        
        # 启用简化分类体系
        self.use_simplified_classification = True
        
        # 简化科室映射规则（基于新的简化分类体系）
        self.simplified_department_mapping = {
            # 内科系统
            "心血管科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "呼吸科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "消化科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "内分泌科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "肾内科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "血液科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "肿瘤科": MedicalDepartment.INTERNAL_MEDICINE.value,
            "内科": MedicalDepartment.INTERNAL_MEDICINE.value,
            
            # 外科系统
            "外科": MedicalDepartment.SURGERY.value,
            "骨科": MedicalDepartment.SURGERY.value,
            "神经外科": MedicalDepartment.SURGERY.value,
            
            # 专科系统
            "眼科": MedicalDepartment.SPECIALIZED.value,
            "耳鼻喉科": MedicalDepartment.SPECIALIZED.value,
            "皮肤科": MedicalDepartment.SPECIALIZED.value,
            "泌尿科": MedicalDepartment.SPECIALIZED.value,
            "儿科": MedicalDepartment.PEDIATRICS.value,
            "妇产科": MedicalDepartment.OBSTETRICS_GYNECOLOGY.value,
            "放射科": MedicalDepartment.SPECIALIZED.value,
            "病理科": MedicalDepartment.SPECIALIZED.value,
            "检验科": MedicalDepartment.SPECIALIZED.value,
            "药剂科": MedicalDepartment.SPECIALIZED.value,
            "康复科": MedicalDepartment.SPECIALIZED.value,
            
            # 精神心理
            "精神科": MedicalDepartment.SPECIALIZED.value,
            "心理科": MedicalDepartment.SPECIALIZED.value,
            
            # 急诊科
            "急诊科": MedicalDepartment.EMERGENCY.value,
            "ICU": MedicalDepartment.EMERGENCY.value,
            
            # 全科医学
            "中医科": MedicalDepartment.SPECIALIZED.value,
            "全科": MedicalDepartment.SPECIALIZED.value,
        }
        
        # 简化文档类型映射规则
        self.simplified_document_type_mapping = {
            "临床指南": DocumentType.CLINICAL_GUIDELINE.value,
            "诊断标准": DocumentType.CLINICAL_GUIDELINE.value,
            "感控指南": DocumentType.CLINICAL_GUIDELINE.value,
            "预防指南": DocumentType.CLINICAL_GUIDELINE.value,
            "诊疗规范": DocumentType.CLINICAL_GUIDELINE.value,
            "专家共识": DocumentType.CLINICAL_GUIDELINE.value,
            
            "治疗方案": DocumentType.TREATMENT_PROTOCOL.value,
            "急救流程": DocumentType.TREATMENT_PROTOCOL.value,
            "质量标准": DocumentType.TREATMENT_PROTOCOL.value,
            "治疗指南": DocumentType.TREATMENT_PROTOCOL.value,
            "诊断指南": DocumentType.TREATMENT_PROTOCOL.value,
            
            "药物说明书": DocumentType.DRUG_REFERENCE.value,
            "用药指南": DocumentType.DRUG_REFERENCE.value,
            
            "手术操作": DocumentType.PROCEDURE_GUIDE.value,
            "检验参考": DocumentType.PROCEDURE_GUIDE.value,
            "影像图谱": DocumentType.PROCEDURE_GUIDE.value,
            "护理指南": DocumentType.PROCEDURE_GUIDE.value,
            "康复指导": DocumentType.PROCEDURE_GUIDE.value,
            "急救指南": DocumentType.PROCEDURE_GUIDE.value,
            
            "病例研究": DocumentType.GENERAL_REFERENCE.value,
            "研究论文": DocumentType.GENERAL_REFERENCE.value,
            "医学教材": DocumentType.GENERAL_REFERENCE.value,
            "护理手册": DocumentType.GENERAL_REFERENCE.value,
            "患者教育": DocumentType.GENERAL_REFERENCE.value,
        }
        
        # 简化疾病分类映射规则
        self.simplified_disease_category_mapping = {
            "循环系统疾病": DiseaseCategory.CARDIOVASCULAR.value,
            "心血管疾病": DiseaseCategory.CARDIOVASCULAR.value,
            
            "呼吸系统疾病": DiseaseCategory.RESPIRATORY.value,
            
            "消化系统疾病": DiseaseCategory.DIGESTIVE.value,
            
            "神经系统疾病": DiseaseCategory.NEUROLOGICAL.value,
            "视觉系统疾病": DiseaseCategory.NEUROLOGICAL.value,
            "耳部疾病": DiseaseCategory.NEUROLOGICAL.value,
            
            "精神、行为和神经发育障碍": DiseaseCategory.MENTAL_DISORDERS.value,
            "精神疾病": DiseaseCategory.MENTAL_DISORDERS.value,
            
            "感染性疾病": DiseaseCategory.INFECTIOUS.value,
            
            "肿瘤": DiseaseCategory.CHRONIC_DISEASES.value,
            "内分泌、营养和代谢疾病": DiseaseCategory.CHRONIC_DISEASES.value,
            "血液及造血器官疾病": DiseaseCategory.CHRONIC_DISEASES.value,
            "免疫机制疾病": DiseaseCategory.CHRONIC_DISEASES.value,
            "肌肉骨骼系统疾病": DiseaseCategory.CHRONIC_DISEASES.value,
            
            "皮肤疾病": DiseaseCategory.GENERAL_CONDITIONS.value,
            "泌尿生殖系统疾病": DiseaseCategory.GENERAL_CONDITIONS.value,
            "妊娠、分娩和产褥期": DiseaseCategory.GENERAL_CONDITIONS.value,
            "围产期疾病": DiseaseCategory.GENERAL_CONDITIONS.value,
            "先天性畸形": DiseaseCategory.GENERAL_CONDITIONS.value,
            "损伤、中毒和外因": DiseaseCategory.GENERAL_CONDITIONS.value,
        }
        
        # 保留原有映射规则作为备用
        self.department_mapping = {
            "呼吸科": ["内科"],
            "消化科": ["内科"],
            "内分泌科": ["内科"],
            "肾内科": ["内科"],
            "血液科": ["内科"],
            "神经科": ["内科"],
            "风湿科": ["内科"],
        }
        
        self.document_type_mapping = {
            "预防指南": "临床指南",
            "诊疗规范": "临床指南", 
            "专家共识": "临床指南",
            "治疗指南": "临床指南",
            "诊断指南": "临床指南",
            "护理指南": "临床指南",
            "康复指南": "临床指南",
            "急救指南": "临床指南",
        }
        
        self.disease_category_mapping = {
            "呼吸系统疾病": ["感染性疾病", "循环系统疾病", "肌肉骨骼系统疾病"],
            "消化系统疾病": ["感染性疾病", "循环系统疾病", "肌肉骨骼系统疾病"],
            "内分泌系统疾病": ["循环系统疾病", "肌肉骨骼系统疾病", "感染性疾病"],
            "神经系统疾病": ["循环系统疾病", "肌肉骨骼系统疾病", "感染性疾病"],
            "泌尿系统疾病": ["感染性疾病", "循环系统疾病", "肌肉骨骼系统疾病"],
            "血液系统疾病": ["循环系统疾病", "肌肉骨骼系统疾病", "感染性疾病"],
            "免疫系统疾病": ["感染性疾病", "循环系统疾病", "肌肉骨骼系统疾病"],
            "感染性疾病": ["感染性疾病", "循环系统疾病", "肌肉骨骼系统疾病"]
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
    
    def _generate_candidates(self, intent: Dict[str, Any], system_resources: Dict[str, Any]) -> Dict[str, List[str]]:
        """根据识别结果与系统资源生成候选项"""
        candidates = {
            "candidate_departments": [],
            "candidate_document_types": [],
            "candidate_disease_categories": []
        }
        # 科室候选：优先优化后的科室 + 同类简化映射项 + 系统中存在的备选
        dept = intent.get("department")
        if dept:
            candidates["candidate_departments"].append(dept)
        for k, v in self.simplified_department_mapping.items():
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
        for k, v in self.simplified_document_type_mapping.items():
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
        for k, v in self.simplified_disease_category_mapping.items():
            if v == dis and k not in candidates["candidate_disease_categories"]:
                candidates["candidate_disease_categories"].append(k)
        # 系统资源中如果有疾病分类信息
        for store in system_resources.get("store_details", {}).values():
            c = store.get("disease_category")
            if c and c not in candidates["candidate_disease_categories"]:
                candidates["candidate_disease_categories"].append(c)
        candidates["candidate_disease_categories"] = candidates["candidate_disease_categories"][:3]
        
        return candidates
    
    def get_system_resources(self) -> Dict[str, Any]:
        """获取系统实际资源信息"""
        try:
            # 直接调用底层服务获取实际资源，避免HTTP循环调用
            stats = enhanced_index_service.get_vector_store_statistics()
            
            if stats and stats.get("total_stores", 0) > 0:
                self._system_resources = {
                    "departments": stats.get("departments", []),
                    "document_types": stats.get("document_types", []),
                    "store_details": stats.get("store_details", {}),
                    "total_stores": stats.get("total_stores", 0)
                }
                logger.info(f"获取系统资源成功: {self._system_resources}")
                return self._system_resources
            else:
                logger.warning("系统中没有可用的向量库")
                return self._get_default_resources()
        except Exception as e:
            logger.error(f"获取系统资源时发生错误: {str(e)}")
            return self._get_default_resources()
    
    def _get_default_resources(self) -> Dict[str, Any]:
        """获取默认资源配置"""
        return {
            "departments": ["内科", "骨科", "心血管科"],
            "document_types": ["临床指南"],
            "store_details": {},
            "total_stores": 0
        }
    
    def find_best_department_match(self, target_department: str, available_departments: List[str]) -> Optional[str]:
        """寻找最佳科室匹配"""
        # 1. 直接匹配
        if target_department in available_departments:
            return target_department
        
        # 2. 映射匹配
        if target_department in self.department_mapping:
            for mapped_dept in self.department_mapping[target_department]:
                if mapped_dept in available_departments:
                    logger.info(f"科室映射: {target_department} -> {mapped_dept}")
                    return mapped_dept
        
        # 3. 模糊匹配（包含关系）
        for dept in available_departments:
            if target_department in dept or dept in target_department:
                logger.info(f"科室模糊匹配: {target_department} -> {dept}")
                return dept
        
        # 4. 默认选择第一个可用科室
        if available_departments:
            default_dept = available_departments[0]
            logger.info(f"科室默认匹配: {target_department} -> {default_dept}")
            return default_dept
        
        return None
    
    def find_best_document_type_match(self, target_type: str, available_types: List[str]) -> Optional[str]:
        """寻找最佳文档类型匹配"""
        # 1. 直接匹配
        if target_type in available_types:
            return target_type
        
        # 2. 映射匹配
        if target_type in self.document_type_mapping:
            mapped_type = self.document_type_mapping[target_type]
            if mapped_type in available_types:
                logger.info(f"文档类型映射: {target_type} -> {mapped_type}")
                return mapped_type
        
        # 3. 默认选择第一个可用类型
        if available_types:
            default_type = available_types[0]
            logger.info(f"文档类型默认匹配: {target_type} -> {default_type}")
            return default_type
        
        return None
    
    def find_best_disease_category_match(self, target_category: str, store_details: Dict[str, Any]) -> Optional[str]:
        """寻找最佳疾病分类匹配"""
        # 获取所有可用的疾病分类
        available_categories = set()
        for store_info in store_details.values():
            if store_info.get("disease_category"):
                available_categories.add(store_info.get("disease_category"))
        
        if target_category in available_categories:
            return target_category
        
        # 尝试使用简化映射
        mapped = self.simplified_disease_category_mapping.get(target_category)
        if mapped and mapped in available_categories:
            logger.info(f"疾病分类映射: {target_category} -> {mapped}")
            return mapped
        
        # 回退到默认：任意可用疾病分类
        if available_categories:
            return list(available_categories)[0]
        return None
    
    def _get_disease_categories_for_department(self, department: str, store_details: Dict[str, Any]) -> List[str]:
        """获取指定科室下的疾病分类集合"""
        categories = set()
        for key, info in store_details.items():
            if info.get("department") == department and info.get("disease_category"):
                categories.add(info["disease_category"])
        return list(categories)
    
    def _find_best_disease_category_for_department(self, target_category: str, department: str, store_details: Dict[str, Any]) -> Optional[str]:
        """在指定科室内寻找最佳疾病分类匹配"""
        dept_categories = self._get_disease_categories_for_department(department, store_details)
        if target_category in dept_categories:
            return target_category
        # 简化映射
        mapped = self.simplified_disease_category_mapping.get(target_category)
        if mapped in dept_categories:
            return mapped
        # 默认选择第一个
        if dept_categories:
            return dept_categories[0]
        return None
    
    def optimize_intent_result(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """优化意图识别结果，基于简化分类体系"""
        if not intent_result or not intent_result.get('success', False):
            return intent_result
        
        try:
            # 获取系统资源
            system_resources = self.get_system_resources()
            
            if not system_resources:
                logger.warning("系统中没有可用的向量库，返回原始结果")
                return intent_result
            
            # 优化科室
            original_department = intent_result.get('department')
            optimized_department = self.find_best_department_match(
                original_department, system_resources.get('departments', [])
            )
            
            # 优化文档类型
            original_doc_type = intent_result.get('document_type')
            optimized_doc_type = self.find_best_document_type_match(
                original_doc_type, system_resources.get('document_types', [])
            )
            
            # 优化疾病分类（优先同科室下的分类）
            original_disease = intent_result.get('disease_category')
            optimized_disease = self._find_best_disease_category_for_department(
                original_disease, optimized_department or original_department, system_resources.get('store_details', {})
            )
            if not optimized_disease:
                optimized_disease = self.find_best_disease_category_match(
                    original_disease, system_resources.get('store_details', {})
                )
            
            # 更新结果
            intent_result.update({
                'department': optimized_department,
                'document_type': optimized_doc_type,
                'disease_category': optimized_disease,
                'optimization_applied': True,
                'original_department': original_department,
                'original_document_type': original_doc_type,
                'original_disease_category': original_disease
            })
            
            # 生成候选项
            candidates = self._generate_candidates(intent_result, system_resources)
            intent_result.update(candidates)
            
            return intent_result
            
        except Exception as e:
            logger.error(f"优化意图结果时发生错误: {str(e)}")
            return intent_result
    
    def recognize_intent(self, query: str) -> Dict[str, Any]:
        """识别用户查询意图（统一输出结构）"""
        # 0. 先判断是否为医疗问题
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
            
            if qwen_result and qwen_result.get('success', True):
                # 标记为医疗问题
                qwen_result['is_medical'] = True
                # 优化识别结果并生成候选
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
            # 返回基础结果（仍标为医疗以进入医疗回答路径，但置信度低）
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


def recognize_smart_medical_intent(query: str) -> Dict[str, Any]:
    """统一入口：智能医疗意图识别"""
    recognizer = SmartMedicalIntentRecognizer()
    result = recognizer.recognize_intent(query)
    # 映射精神心理类到专科系统（确保一致）
    if result.get('disease_category') == DiseaseCategory.MENTAL_DISORDERS.value and not result.get('department'):
        result['department'] = MedicalDepartment.SPECIALIZED.value
    return result

# 保留原有测试入口
if __name__ == "__main__":
    test_queries = [
        "感冒的症状有哪些？",  # 测试呼吸科->内科映射
        "高血压的治疗方法有哪些？",  # 测试心血管科
        "骨折后应该如何处理？",  # 测试骨科
        "糖尿病患者的饮食注意事项",  # 测试内分泌科->内科映射
        "如何写简历？"  # 非医疗问题
    ]
    
    recognizer = SmartMedicalIntentRecognizer()
    for query in test_queries:
        print(f"\n问题: {query}")
        result = recognizer.recognize_intent(query)
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")