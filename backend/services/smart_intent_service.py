"""
智能医疗意图识别服务
基于系统实际资源进行意图识别，避免过于严格的识别导致检索失败
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from .qwen_intent_service import QwenMedicalIntentRecognizer
from .medical_intent_service import MedicalIntentRecognizer
from .enhanced_index_service import enhanced_index_service

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
        
        # 科室映射规则
        self.department_mapping = {
            "呼吸科": ["内科"],  # 呼吸科相关问题映射到内科
            "消化科": ["内科"],  # 消化科相关问题映射到内科
            "内分泌科": ["内科"],  # 内分泌科相关问题映射到内科
            "肾内科": ["内科"],  # 肾内科相关问题映射到内科
            "血液科": ["内科"],  # 血液科相关问题映射到内科
            "神经科": ["内科"],  # 神经科相关问题映射到内科
            "风湿科": ["内科"],  # 风湿科相关问题映射到内科
        }
        
        # 文档类型映射规则
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
        
        # 疾病分类映射规则
        self.disease_category_mapping = {
            "呼吸系统疾病": ["感染性疾病", "循环系统疾病", "肌肉骨骼系统疾病"],  # 可能的映射目标
            "消化系统疾病": ["感染性疾病", "循环系统疾病", "肌肉骨骼系统疾病"],
            "内分泌系统疾病": ["循环系统疾病", "肌肉骨骼系统疾病", "感染性疾病"],
            "神经系统疾病": ["循环系统疾病", "肌肉骨骼系统疾病", "感染性疾病"],
            "泌尿系统疾病": ["感染性疾病", "循环系统疾病", "肌肉骨骼系统疾病"],
            "血液系统疾病": ["循环系统疾病", "肌肉骨骼系统疾病", "感染性疾病"],
            "免疫系统疾病": ["感染性疾病", "循环系统疾病", "肌肉骨骼系统疾病"],
            "感染性疾病": ["感染性疾病", "循环系统疾病", "肌肉骨骼系统疾病"]
        }
    
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
                available_categories.add(store_info["disease_category"])
        
        available_categories = list(available_categories)
        
        # 1. 直接匹配
        if target_category in available_categories:
            return target_category
        
        # 2. 映射匹配
        if target_category in self.disease_category_mapping:
            for mapped_category in self.disease_category_mapping[target_category]:
                if mapped_category in available_categories:
                    logger.info(f"疾病分类映射: {target_category} -> {mapped_category}")
                    return mapped_category
        
        # 3. 模糊匹配
        for category in available_categories:
            if target_category in category or category in target_category:
                logger.info(f"疾病分类模糊匹配: {target_category} -> {category}")
                return category
        
        # 4. 返回None，让系统自动选择
        return None
    
    def _get_disease_categories_for_department(self, department: str, store_details: Dict[str, Any]) -> List[str]:
        """获取指定科室下的所有疾病分类"""
        categories = []
        for store_name, store_info in store_details.items():
            if store_info.get("department") == department:
                disease_category = store_info.get("disease_category")
                if disease_category and disease_category not in categories:
                    categories.append(disease_category)
                elif disease_category is None:
                    # 对于没有疾病分类的科室（如内科），添加一个特殊标记
                    categories.append("通用")
        return categories
    
    def _find_best_disease_category_for_department(self, target_category: str, department: str, store_details: Dict[str, Any]) -> Optional[str]:
        """为指定科室寻找最佳疾病分类匹配"""
        available_categories = self._get_disease_categories_for_department(department, store_details)
        
        if not available_categories:
            return None
        
        # 1. 直接匹配
        if target_category in available_categories:
            return target_category
        
        # 2. 如果有"通用"分类（如内科），优先选择
        if "通用" in available_categories:
            logger.info(f"使用通用分类匹配科室 {department}")
            return None  # 返回None表示使用该科室的默认分类
        
        # 3. 基于疾病分类映射
        if target_category in self.disease_category_mapping:
            for mapped_category in self.disease_category_mapping[target_category]:
                if mapped_category in available_categories:
                    return mapped_category
        
        # 4. 模糊匹配
        for category in available_categories:
            if target_category in category or category in target_category:
                return category
        
        # 5. 返回该科室的第一个可用分类
        return available_categories[0] if available_categories else None
    
    def optimize_intent_result(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """优化意图识别结果，使其与系统资源匹配"""
        # 获取系统资源
        resources = self.get_system_resources()
        logger.info(f"获取到的系统资源: {resources}")
        
        if not resources or resources["total_stores"] == 0:
            logger.warning("系统中没有可用的向量库，返回原始结果")
            return intent_result
        
        # 优化后的结果
        optimized_result = intent_result.copy()
        logger.info(f"原始意图识别结果: {intent_result}")
        
        # 1. 科室优化 - 优先保持原科室，只在不存在时才映射
        original_department = intent_result.get("department")
        if original_department:
            if original_department in resources["departments"]:
                # 原科室存在，直接使用
                logger.info(f"科室直接匹配: {original_department}")
                optimized_result["department"] = original_department
            else:
                # 原科室不存在，寻找最佳匹配
                best_department = self.find_best_department_match(
                    original_department, 
                    resources["departments"]
                )
                logger.info(f"科室映射: {original_department} -> {best_department}")
                if best_department:
                    optimized_result["department"] = best_department
                    optimized_result["department_optimized"] = True
                    optimized_result["original_department"] = original_department
        
        # 2. 文档类型优化 - 同样优先保持原类型
        original_doc_type = intent_result.get("document_type")
        if original_doc_type:
            if original_doc_type in resources["document_types"]:
                logger.info(f"文档类型直接匹配: {original_doc_type}")
                optimized_result["document_type"] = original_doc_type
            else:
                best_doc_type = self.find_best_document_type_match(
                    original_doc_type, 
                    resources["document_types"]
                )
                logger.info(f"文档类型映射: {original_doc_type} -> {best_doc_type}")
                if best_doc_type:
                    optimized_result["document_type"] = best_doc_type
                    optimized_result["document_type_optimized"] = True
                    optimized_result["original_document_type"] = original_doc_type
        
        # 3. 疾病分类优化 - 基于最终确定的科室来匹配疾病分类
        final_department = optimized_result.get("department")
        original_disease_category = intent_result.get("disease_category")
        
        if original_disease_category and final_department:
            # 寻找该科室下的可用疾病分类
            available_categories = self._get_disease_categories_for_department(
                final_department, resources["store_details"]
            )
            
            if original_disease_category in available_categories:
                logger.info(f"疾病分类直接匹配: {original_disease_category}")
                optimized_result["disease_category"] = original_disease_category
            else:
                # 寻找最佳疾病分类匹配
                best_disease_category = self._find_best_disease_category_for_department(
                    original_disease_category, final_department, resources["store_details"]
                )
                logger.info(f"疾病分类映射: {original_disease_category} -> {best_disease_category}")
                if best_disease_category:
                    optimized_result["disease_category"] = best_disease_category
                    optimized_result["disease_category_optimized"] = True
                    optimized_result["original_disease_category"] = original_disease_category
        
        # 添加优化标记和系统资源信息
        optimized_result["optimized"] = True
        optimized_result["system_resources"] = {
            "departments": resources["departments"],
            "document_types": resources["document_types"],
            "total_stores": resources["total_stores"]
        }
        
        logger.info(f"意图识别结果优化完成: {optimized_result}")
        return optimized_result
    
    def recognize_intent(self, query: str) -> Dict[str, Any]:
        """智能意图识别"""
        try:
            # 1. 首先使用Qwen进行意图识别
            qwen_result = self.qwen_recognizer.recognize_intent(query)
            
            # 2. 优化识别结果，使其与系统资源匹配
            optimized_result = self.optimize_intent_result(qwen_result)
            
            # 3. 添加智能识别标记
            optimized_result["method"] = "smart_qwen"
            optimized_result["base_method"] = qwen_result.get("method", "qwen_llm")
            
            return optimized_result
            
        except Exception as e:
            logger.error(f"智能意图识别过程中发生错误: {str(e)}")
            
            # 使用降级方案
            try:
                fallback_result = self.fallback_recognizer.recognize_intent(query)
                fallback_result["method"] = "smart_fallback"
                fallback_result["error"] = str(e)
                return self.optimize_intent_result(fallback_result)
            except Exception as fallback_error:
                logger.error(f"降级方案也失败: {str(fallback_error)}")
                return {
                    "department": "内科",  # 默认科室
                    "document_type": "临床指南",  # 默认文档类型
                    "disease_category": None,
                    "confidence": 0.1,
                    "method": "smart_default",
                    "error": str(e),
                    "fallback_error": str(fallback_error)
                }


def recognize_smart_medical_intent(query: str) -> Dict[str, Any]:
    """
    使用智能意图识别的主函数
    
    Args:
        query: 用户的医疗咨询问题
        
    Returns:
        包含优化后识别结果的字典
    """
    recognizer = SmartMedicalIntentRecognizer()
    return recognizer.recognize_intent(query)


# 测试函数
if __name__ == "__main__":
    # 测试用例
    test_queries = [
        "感冒的症状有哪些？",  # 测试呼吸科->内科映射
        "高血压的治疗方法有哪些？",  # 测试心血管科
        "骨折后应该如何处理？",  # 测试骨科
        "糖尿病患者的饮食注意事项",  # 测试内分泌科->内科映射
    ]
    
    recognizer = SmartMedicalIntentRecognizer()
    
    for query in test_queries:
        print(f"\n问题: {query}")
        result = recognizer.recognize_intent(query)
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")