"""
医疗意图识别服务
从用户问题中智能推断科室、文档类型、疾病类别等参数
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

@dataclass
class MedicalIntent:
    """医疗意图识别结果"""
    department: Optional[str] = None
    document_type: Optional[str] = None
    disease_category: Optional[str] = None
    confidence: float = 0.0
    keywords: List[str] = None
    reasoning: str = ""

class MedicalIntentRecognizer:
    """医疗意图识别器"""
    
    def __init__(self):
        # 科室关键词映射
        self.department_keywords = {
            "心血管科": [
                "高血压", "低血压", "心脏病", "冠心病", "心肌梗死", "心绞痛", "心律不齐", "心房颤动",
                "心衰", "心力衰竭", "动脉硬化", "血管", "心血管", "心脏", "胸痛", "心悸", "心慌",
                "血压", "心电图", "心脏彩超", "冠脉", "支架", "搭桥", "心导管", "心肌酶"
            ],
            "骨科": [
                "骨折", "骨裂", "脱臼", "关节", "韧带", "肌腱", "软骨", "椎间盘", "颈椎", "腰椎",
                "膝关节", "肩关节", "髋关节", "踝关节", "骨质疏松", "骨刺", "骨髓炎", "关节炎",
                "风湿", "类风湿", "痛风", "腰痛", "颈痛", "肩痛", "膝痛", "扭伤", "拉伤",
                "石膏", "固定", "牵引", "康复", "理疗", "X光", "CT", "MRI", "骨密度"
            ],
            "内科": [
                "糖尿病", "血糖", "胰岛素", "内分泌", "甲状腺", "甲亢", "甲减", "肝炎", "肝硬化",
                "肾炎", "肾病", "尿毒症", "透析", "胃炎", "胃溃疡", "肠炎", "腹泻", "便秘",
                "发热", "感冒", "咳嗽", "哮喘", "肺炎", "支气管炎", "贫血", "白血病", "淋巴瘤"
            ],
            "外科": [
                "手术", "开刀", "切除", "缝合", "伤口", "创伤", "外伤", "阑尾炎", "胆囊炎", "疝气",
                "肿瘤", "癌症", "良性", "恶性", "活检", "病理", "麻醉", "术前", "术后", "引流"
            ],
            "妇科": [
                "月经", "例假", "白带", "阴道", "子宫", "卵巢", "输卵管", "宫颈", "乳腺", "怀孕",
                "妊娠", "流产", "分娩", "产检", "避孕", "不孕", "妇科炎症", "盆腔炎", "附件炎"
            ],
            "儿科": [
                "小儿", "儿童", "婴儿", "新生儿", "幼儿", "发育", "生长", "疫苗", "预防接种",
                "小儿感冒", "小儿发热", "小儿腹泻", "小儿咳嗽", "儿童哮喘", "手足口病"
            ]
        }
        
        # 疾病类别关键词映射
        self.disease_category_keywords = {
            "循环系统疾病": [
                "高血压", "低血压", "心脏病", "冠心病", "心肌梗死", "心绞痛", "心律不齐",
                "心房颤动", "心衰", "心力衰竭", "动脉硬化", "血管疾病", "心血管病"
            ],
            "肌肉骨骼系统疾病": [
                "骨折", "骨裂", "脱臼", "关节炎", "骨质疏松", "颈椎病", "腰椎病",
                "关节疾病", "肌肉疾病", "韧带损伤", "软骨损伤", "骨科疾病"
            ],
            "内分泌系统疾病": [
                "糖尿病", "甲状腺疾病", "甲亢", "甲减", "内分泌失调", "激素异常",
                "胰岛素抵抗", "代谢综合征", "肥胖症"
            ],
            "消化系统疾病": [
                "胃炎", "胃溃疡", "肠炎", "腹泻", "便秘", "肝炎", "肝硬化", "胆囊炎",
                "阑尾炎", "消化不良", "胃肠疾病", "肝病", "胆道疾病"
            ],
            "呼吸系统疾病": [
                "感冒", "咳嗽", "哮喘", "肺炎", "支气管炎", "肺结核", "慢阻肺",
                "呼吸道感染", "肺部疾病", "气管疾病"
            ],
            "泌尿系统疾病": [
                "肾炎", "肾病", "尿毒症", "肾结石", "膀胱炎", "尿路感染",
                "前列腺疾病", "肾功能不全", "泌尿道疾病"
            ],
            "神经系统疾病": [
                "头痛", "偏头痛", "癫痫", "中风", "脑梗", "脑出血", "帕金森",
                "老年痴呆", "神经痛", "面瘫", "神经系统疾病"
            ]
        }
        
        # 文档类型关键词映射
        self.document_type_keywords = {
            "临床指南": [
                "指南", "诊疗指南", "治疗指南", "临床指南", "诊断标准", "治疗标准",
                "临床路径", "诊疗规范", "治疗方案", "诊断方法", "治疗方法"
            ],
            "药物说明": [
                "药物", "用药", "药品", "剂量", "副作用", "不良反应", "禁忌症",
                "适应症", "药理", "药代动力学", "药物相互作用"
            ],
            "检查报告": [
                "检查", "化验", "报告", "结果", "指标", "数值", "正常值", "异常",
                "血常规", "尿常规", "肝功能", "肾功能", "心电图", "B超", "CT", "MRI"
            ]
        }
        
        # 症状关键词
        self.symptom_keywords = [
            "疼痛", "痛", "胀", "闷", "痒", "麻", "酸", "胀", "困难", "不适", "异常", "障碍",
            "发热", "发烧", "咳嗽", "咳痰", "气短", "乏力", "头晕", "恶心", "呕吐", "腹泻"
        ]
        
        # 治疗关键词
        self.treatment_keywords = [
            "治疗", "疗法", "用药", "手术", "康复", "护理", "预防", "保健", "调理",
            "怎么治", "如何治", "治疗方法", "治疗方案", "用什么药", "吃什么药"
        ]
        
        # 诊断关键词
        self.diagnosis_keywords = [
            "诊断", "确诊", "检查", "化验", "是什么病", "什么疾病", "病因", "原因",
            "怎么回事", "为什么", "症状", "表现", "征象"
        ]

    def recognize_intent(self, query: str) -> MedicalIntent:
        """识别医疗意图"""
        query = query.strip().lower()
        
        # 提取关键词
        keywords = self._extract_keywords(query)
        
        # 识别科室
        department = self._recognize_department(query, keywords)
        
        # 识别疾病类别
        disease_category = self._recognize_disease_category(query, keywords)
        
        # 识别文档类型
        document_type = self._recognize_document_type(query, keywords)
        
        # 计算置信度
        confidence = self._calculate_confidence(query, department, disease_category, document_type)
        
        # 生成推理说明
        reasoning = self._generate_reasoning(query, keywords, department, disease_category, document_type)
        
        return MedicalIntent(
            department=department,
            document_type=document_type,
            disease_category=disease_category,
            confidence=confidence,
            keywords=keywords,
            reasoning=reasoning
        )
    
    def _extract_keywords(self, query: str) -> List[str]:
        """提取关键词"""
        keywords = []
        
        # 提取所有科室关键词
        for dept, dept_keywords in self.department_keywords.items():
            for keyword in dept_keywords:
                if keyword.lower() in query:
                    keywords.append(keyword)
        
        # 提取疾病类别关键词
        for category, cat_keywords in self.disease_category_keywords.items():
            for keyword in cat_keywords:
                if keyword.lower() in query:
                    keywords.append(keyword)
        
        # 提取症状关键词
        for keyword in self.symptom_keywords:
            if keyword.lower() in query:
                keywords.append(keyword)
        
        # 提取治疗关键词
        for keyword in self.treatment_keywords:
            if keyword.lower() in query:
                keywords.append(keyword)
        
        # 提取诊断关键词
        for keyword in self.diagnosis_keywords:
            if keyword.lower() in query:
                keywords.append(keyword)
        
        return list(set(keywords))  # 去重
    
    def _recognize_department(self, query: str, keywords: List[str]) -> Optional[str]:
        """识别科室"""
        department_scores = {}
        
        for dept, dept_keywords in self.department_keywords.items():
            score = 0
            for keyword in dept_keywords:
                if keyword.lower() in query:
                    # 根据关键词重要性给分
                    if keyword in ["高血压", "心脏病", "骨折", "糖尿病"]:
                        score += 3  # 高权重关键词
                    elif keyword in ["心血管", "骨科", "内科"]:
                        score += 2  # 中权重关键词
                    else:
                        score += 1  # 低权重关键词
            
            if score > 0:
                department_scores[dept] = score
        
        if department_scores:
            # 返回得分最高的科室
            return max(department_scores, key=department_scores.get)
        
        return None
    
    def _recognize_disease_category(self, query: str, keywords: List[str]) -> Optional[str]:
        """识别疾病类别"""
        category_scores = {}
        
        for category, cat_keywords in self.disease_category_keywords.items():
            score = 0
            for keyword in cat_keywords:
                if keyword.lower() in query:
                    score += 1
            
            if score > 0:
                category_scores[category] = score
        
        if category_scores:
            return max(category_scores, key=category_scores.get)
        
        return None
    
    def _recognize_document_type(self, query: str, keywords: List[str]) -> Optional[str]:
        """识别文档类型"""
        # 默认返回临床指南，因为这是我们主要的文档类型
        doc_type_scores = {}
        
        for doc_type, type_keywords in self.document_type_keywords.items():
            score = 0
            for keyword in type_keywords:
                if keyword.lower() in query:
                    score += 1
            
            if score > 0:
                doc_type_scores[doc_type] = score
        
        if doc_type_scores:
            return max(doc_type_scores, key=doc_type_scores.get)
        
        # 如果没有明确的文档类型指示，默认返回临床指南
        return "临床指南"
    
    def _calculate_confidence(self, query: str, department: Optional[str], 
                            disease_category: Optional[str], document_type: Optional[str]) -> float:
        """计算置信度"""
        confidence = 0.0
        
        # 基础置信度
        if department:
            confidence += 0.4
        if disease_category:
            confidence += 0.3
        if document_type:
            confidence += 0.2
        
        # 根据关键词匹配度调整
        keyword_count = len(self._extract_keywords(query))
        if keyword_count >= 3:
            confidence += 0.1
        elif keyword_count >= 2:
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def _generate_reasoning(self, query: str, keywords: List[str], 
                          department: Optional[str], disease_category: Optional[str], 
                          document_type: Optional[str]) -> str:
        """生成推理说明"""
        reasoning_parts = []
        
        if keywords:
            reasoning_parts.append(f"识别到关键词: {', '.join(keywords[:5])}")
        
        if department:
            reasoning_parts.append(f"推断科室: {department}")
        
        if disease_category:
            reasoning_parts.append(f"推断疾病类别: {disease_category}")
        
        if document_type:
            reasoning_parts.append(f"推断文档类型: {document_type}")
        
        if not reasoning_parts:
            reasoning_parts.append("未能识别出明确的医疗意图")
        
        return "; ".join(reasoning_parts)

# 全局服务实例
medical_intent_recognizer = MedicalIntentRecognizer()

def recognize_medical_intent(query: str) -> MedicalIntent:
    """识别医疗意图的便捷函数"""
    return medical_intent_recognizer.recognize_intent(query)