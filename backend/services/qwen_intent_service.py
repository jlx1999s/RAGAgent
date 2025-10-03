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
        
        # 医疗科室映射
        self.departments = [
            "心血管科", "骨科", "内科", "外科", "神经科", 
            "呼吸科", "消化科", "内分泌科", "肾内科", "血液科",
            "肿瘤科", "皮肤科", "眼科", "耳鼻喉科", "口腔科",
            "妇产科", "儿科", "精神科", "康复科", "急诊科"
        ]
        
        # 疾病类别映射
        self.disease_categories = [
            "循环系统疾病", "肌肉骨骼系统疾病", "内分泌系统疾病",
            "呼吸系统疾病", "消化系统疾病", "神经系统疾病",
            "泌尿系统疾病", "血液系统疾病", "免疫系统疾病",
            "皮肤疾病", "感染性疾病", "肿瘤疾病", "精神疾病",
            "先天性疾病", "外伤疾病", "中毒疾病"
        ]
        
        # 文档类型映射
        self.document_types = [
            "临床指南", "诊疗规范", "专家共识", "病例报告",
            "研究论文", "药物说明", "检查标准", "手术指南",
            "护理规范", "康复指导", "预防指南", "急救指南"
        ]
    
    def create_intent_prompt(self, query: str) -> str:
        """创建意图识别的提示词"""
        prompt = f"""你是一个专业的医疗意图识别专家。请分析用户的医疗咨询问题，并识别出最相关的科室、疾病类别和文档类型。

用户问题：{query}

可选科室：{', '.join(self.departments)}
可选疾病类别：{', '.join(self.disease_categories)}
可选文档类型：{', '.join(self.document_types)}

请严格按照以下JSON格式输出结果，不要包含任何其他文字：

{{
    "department": "最相关的科室名称",
    "disease_category": "最相关的疾病类别",
    "document_type": "最相关的文档类型",
    "confidence": 0.95,
    "reasoning": "详细的推理过程，说明为什么选择这些分类",
    "keywords": ["从问题中提取的关键医疗词汇"]
}}

注意：
1. confidence应该是0-1之间的数值，表示识别的置信度
2. 如果无法确定某个分类，请选择最可能的选项
3. reasoning应该详细说明分析过程
4. keywords应该包含问题中的关键医疗术语
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
        """解析千问的响应"""
        try:
            # 尝试提取JSON部分
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                
                # 验证必要字段
                required_fields = ['department', 'disease_category', 'document_type', 'confidence']
                for field in required_fields:
                    if field not in result:
                        raise ValueError(f"缺少必要字段: {field}")
                
                # 确保置信度在合理范围内
                if not isinstance(result['confidence'], (int, float)) or not (0 <= result['confidence'] <= 1):
                    result['confidence'] = 0.8  # 默认置信度
                
                return result
            else:
                raise ValueError("响应中未找到有效的JSON格式")
                
        except Exception as e:
            logger.error(f"解析千问响应时发生错误: {str(e)}")
            # 返回默认结果
            return {
                "department": None,
                "disease_category": None,
                "document_type": "临床指南",
                "confidence": 0.0,
                "reasoning": f"解析失败: {str(e)}",
                "keywords": []
            }
    
    def fallback_recognition(self, query: str) -> Dict[str, Any]:
        """降级方案：基于关键词的简单识别"""
        from .medical_intent_service import MedicalIntentRecognizer
        
        logger.info("使用降级方案进行意图识别")
        fallback_recognizer = MedicalIntentRecognizer()
        return fallback_recognizer.recognize_intent(query)
    
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