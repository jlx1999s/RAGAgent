"""
基于千问大语言模型的医疗意图识别服务
提供更智能、更准确的意图识别能力
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from dashscope import Generation
import dashscope
from .medical_taxonomy import get_all_departments, get_all_document_types, get_all_disease_categories

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QwenMedicalIntentRecognizer:
    """基于千问的医疗意图识别器"""
    
    def __init__(self):
        """初始化千问意图识别器"""
        # 从环境变量获取API密钥
        self.api_key = os.getenv('DASHSCOPE_API_KEY')
        if self.api_key:
            dashscope.api_key = self.api_key
        else:
            logger.warning("未找到DASHSCOPE_API_KEY环境变量，将使用降级方案")
        
        # 使用简化分类体系的枚举值作为候选集合，避免细颗粒度科室
        self.departments = get_all_departments()
        
        # 采用统一的疾病分类集合（简化枚举）
        self.disease_categories = get_all_disease_categories()
        
        # 采用统一的文档类型集合（简化枚举）
        self.document_types = get_all_document_types()
    
    def create_intent_prompt(self, query: str) -> str:
        """创建意图识别的提示词（含 is_medical 与候选项）"""
        prompt = f"""你是专业的医疗意图识别专家。请判断用户问题是否为医疗相关，并识别最相关的科室、疾病类别和文档类型，同时给出候选项。

用户问题：{query}

可选科室：{', '.join(self.departments)}
可选疾病类别：{', '.join(self.disease_categories)}
可选文档类型：{', '.join(self.document_types)}

请严格输出纯JSON，且仅包含如下字段（禁止额外文本）：
{{
  "is_medical": true,
  "department": "最相关的科室名称或null",
  "disease_category": "最相关的疾病类别或null",
  "document_type": "最相关的文档类型或null",
  "confidence": 0.95,
  "reasoning": "简明推理说明",
  "keywords": ["提取的关键医疗词汇"],
  "candidates": {{
    "departments": ["最多3个候选，来自可选科室"],
    "document_types": ["最多3个候选，来自可选文档类型"],
    "disease_categories": ["最多3个候选，来自可选疾病类别"]
  }}
}}

规则：
1. 若为非医疗（is_medical=false），将department、document_type、disease_category均设为null，但仍需给出confidence、reasoning和keywords。
2. confidence为0-1之间的小数。
3. candidates每个数组最多3项，必须从提供的可选集合中选择；若主预测值存在，应置于对应候选数组首位。
4. 严禁输出任何非JSON文本、注释或解释。
"""
        return prompt
    
    def call_qwen_api(self, prompt: str) -> Optional[str]:
        """调用千问API"""
        try:
            if not self.api_key:
                logger.warning("API密钥未配置，无法调用千问API")
                return None
                
            response = Generation.call(
                model='qwen-turbo',  # 使用qwen-turbo模型，速度快且效果好
                prompt=prompt,
                max_tokens=1000,
                temperature=0.1,  # 低温度确保输出稳定
                top_p=0.8,
                seed=42  # 固定种子确保结果可重现
            )
            
            if response.status_code == 200:
                return response.output.text.strip()
            else:
                logger.error(f"千问API调用失败: {response.status_code}, {response.message}")
                return None
                
        except Exception as e:
            logger.error(f"调用千问API时发生错误: {str(e)}")
            return None
    
    def parse_qwen_response(self, response_text: str) -> Dict[str, Any]:
        """解析千问的响应，补充 is_medical 与候选项，并进行基本校验"""
        try:
            # 提取JSON部分（容错）
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx == -1 or end_idx <= start_idx:
                raise ValueError("响应中未找到有效的JSON格式")

            json_str = response_text[start_idx:end_idx]
            result = json.loads(json_str)

            # 验证必要字段存在（允许为 None，但必须有键）
            required_fields = ['department', 'disease_category', 'document_type', 'confidence']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"缺少必要字段: {field}")

            # 置信度范围校验
            conf = result.get('confidence')
            if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
                result['confidence'] = 0.8

            # 标准化 is_medical
            is_med = result.get('is_medical')
            result['is_medical'] = bool(is_med) if isinstance(is_med, bool) else True

            # 字段归一化与合法性校验
            dept = result.get('department') or None
            doc_type = result.get('document_type') or None
            dis_cat = result.get('disease_category') or None

            # 去除首尾空格
            dept = dept.strip() if isinstance(dept, str) else None
            doc_type = doc_type.strip() if isinstance(doc_type, str) else None
            dis_cat = dis_cat.strip() if isinstance(dis_cat, str) else None

            # 跨字段纠错：将误放的值归位
            # 若 document_type 是科室（如“精神科”），而 department 为空或非法，则归到 department
            if doc_type and doc_type in self.departments and (not dept or dept not in self.departments):
                dept = doc_type
                doc_type = None
            # 若 department 是文档类型（如“临床指南”），而 document_type 为空或非法，则归到 document_type
            if dept and dept in self.document_types and (not doc_type or doc_type not in self.document_types):
                doc_type = dept
                dept = None
            # 若某字段值属于疾病类别但放错了位置，优先归到 disease_category
            if dept and dept in self.disease_categories and (not dis_cat or dis_cat not in self.disease_categories):
                dis_cat = dept
                dept = None
            if doc_type and doc_type in self.disease_categories and (not dis_cat or dis_cat not in self.disease_categories):
                dis_cat = doc_type
                doc_type = None

            # 仅保留合法分类值
            result['department'] = dept if dept in self.departments else None
            result['document_type'] = doc_type if doc_type in self.document_types else None
            result['disease_category'] = dis_cat if dis_cat in self.disease_categories else None

            # 归一化候选项结构并过滤到合法集合
            candidates = result.get('candidates') or {}
            cand_depts = candidates.get('departments') or []
            cand_docs = candidates.get('document_types') or []
            cand_cats = candidates.get('disease_categories') or []

            # 将主预测值放到候选首位并去重、限长
            if result['department']:
                cand_depts = [result['department']] + cand_depts
            cand_depts = [x for x in cand_depts if x in self.departments]
            cand_depts = list(dict.fromkeys(cand_depts))[:3]

            if result['document_type']:
                cand_docs = [result['document_type']] + cand_docs
            cand_docs = [x for x in cand_docs if x in self.document_types]
            cand_docs = list(dict.fromkeys(cand_docs))[:3]

            if result['disease_category']:
                cand_cats = [result['disease_category']] + cand_cats
            cand_cats = [x for x in cand_cats if x in self.disease_categories]
            cand_cats = list(dict.fromkeys(cand_cats))[:3]

            result['candidates'] = {
                'departments': cand_depts,
                'document_types': cand_docs,
                'disease_categories': cand_cats
            }

            # keywords 兜底
            if not isinstance(result.get('keywords'), list):
                result['keywords'] = []

            return result

        except Exception as e:
            logger.error(f"解析千问响应时发生错误: {str(e)}")
            # 返回默认结果（避免误判非医疗导致直接跳过检索）
            return {
                "is_medical": True,
                "department": None,
                "disease_category": None,
                "document_type": None,
                "candidates": {
                    "departments": [],
                    "document_types": [],
                    "disease_categories": []
                },
                "confidence": 0.0,
                "reasoning": f"解析失败: {str(e)}",
                "keywords": []
            }
    
    def fallback_recognition(self, query: str) -> Dict[str, Any]:
        """降级方案：基于关键词的简单识别"""
        from .medical_intent_service import MedicalIntentRecognizer
        
        logger.info("使用降级方案进行意图识别")
        fallback_recognizer = MedicalIntentRecognizer()
        mi = fallback_recognizer.recognize_intent(query)
        return {
            "is_medical": True,
            "department": getattr(mi, 'department', None),
            "document_type": getattr(mi, 'document_type', None),
            "disease_category": getattr(mi, 'disease_category', None),
            "confidence": getattr(mi, 'confidence', 0.0),
            "reasoning": getattr(mi, 'reasoning', ""),
            "keywords": getattr(mi, 'keywords', []) or [],
            "candidates": {
                "departments": [],
                "document_types": [],
                "disease_categories": []
            }
        }
    
    def recognize_intent(self, query: str) -> Dict[str, Any]:
        """识别医疗意图"""
        try:
            # 创建提示词
            prompt = self.create_intent_prompt(query)
            
            # 调用千问API
            response_text = self.call_qwen_api(prompt)
            
            if response_text:
                # 解析响应
                result = self.parse_qwen_response(response_text)
                result['method'] = 'qwen_llm'
                logger.info(f"千问意图识别成功: {result}")
                return result
            else:
                # 使用降级方案
                result = self.fallback_recognition(query)
                result['method'] = 'fallback'
                logger.info(f"使用降级方案识别意图: {result}")
                return result
                
        except Exception as e:
            logger.error(f"意图识别过程中发生错误: {str(e)}")
            # 使用降级方案
            result = self.fallback_recognition(query)
            result['method'] = 'fallback'
            result['error'] = str(e)
            return result


def recognize_qwen_medical_intent(query: str) -> Dict[str, Any]:
    """
    使用千问进行医疗意图识别的主函数
    
    Args:
        query: 用户的医疗咨询问题
        
    Returns:
        包含识别结果的字典
    """
    recognizer = QwenMedicalIntentRecognizer()
    return recognizer.recognize_intent(query)


# 测试函数
if __name__ == "__main__":
    # 测试用例
    test_queries = [
        "高血压的治疗方法有哪些？",
        "骨折后应该如何处理？",
        "糖尿病患者的饮食注意事项",
        "心律不齐的症状是什么？",
        "如何预防肺炎？"
    ]
    
    recognizer = QwenMedicalIntentRecognizer()
    
    for query in test_queries:
        print(f"\n问题: {query}")
        result = recognizer.recognize_intent(query)
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")