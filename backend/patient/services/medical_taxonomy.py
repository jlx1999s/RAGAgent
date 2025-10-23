# services/medical_taxonomy.py
"""
医疗文档分类和标签系统（简化版）
用于医疗知识库的文档分类、标签管理和元数据处理
采用简化的三级分类体系，提高匹配成功率和用户体验
"""

from enum import Enum
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime
import json
import re

# ============ 简化分类体系 ============

class MedicalDepartment(Enum):
    """简化医疗科室分类"""
    INTERNAL_MEDICINE = "内科系统"     # 合并心血管、呼吸、消化、内分泌、肾内科、血液科等
    SURGERY = "外科系统"              # 合并各类外科、骨科等
    SPECIALIZED = "专科系统"          # 合并眼科、耳鼻喉、皮肤科、泌尿科等
    PEDIATRICS = "儿科"               # 儿科
    OBSTETRICS_GYNECOLOGY = "妇产科"  # 妇产科
    EMERGENCY = "急诊科"              # 急诊相关

class DocumentType(Enum):
    """简化文档类型分类"""
    CLINICAL_GUIDELINE = "临床指南"    # 合并临床指南、诊断标准、感控指南
    TREATMENT_PROTOCOL = "治疗方案"    # 合并治疗方案、急救流程、质量标准
    DRUG_REFERENCE = "药物参考"        # 药物说明书、用药指南
    PROCEDURE_GUIDE = "操作指南"       # 手术操作、检验参考、影像图谱
    GENERAL_REFERENCE = "综合参考"     # 病例研究、研究论文、医学教材、护理手册、患者教育

class DiseaseCategory(Enum):
    """简化疾病分类"""
    CARDIOVASCULAR = "心血管疾病"      # 循环系统疾病
    RESPIRATORY = "呼吸系统疾病"       # 呼吸系统疾病
    DIGESTIVE = "消化系统疾病"         # 消化系统疾病
    NEUROLOGICAL = "神经系统疾病"      # 神经系统、视觉系统、耳部疾病
    MENTAL_DISORDERS = "精神心理疾病"  # 精神、行为和神经发育障碍
    INFECTIOUS = "感染性疾病"          # 感染性疾病
    CHRONIC_DISEASES = "慢性疾病"      # 肿瘤、内分泌、血液、免疫、肌肉骨骼疾病
    GENERAL_CONDITIONS = "常见病症"    # 皮肤疾病、泌尿生殖、妊娠相关、先天性疾病等

class EvidenceLevel(Enum):
    """证据等级"""
    LEVEL_1A = "1A级（系统评价/Meta分析）"
    LEVEL_1B = "1B级（至少一个RCT）"
    LEVEL_2A = "2A级（系统评价（队列研究））"
    LEVEL_2B = "2B级（单个队列研究）"
    LEVEL_3A = "3A级（系统评价（病例对照研究））"
    LEVEL_3B = "3B级（单个病例对照研究）"
    LEVEL_4 = "4级（病例系列）"
    LEVEL_5 = "5级（专家意见）"

@dataclass
class MedicalMetadata:
    """医疗文档元数据"""
    document_id: str
    title: str
    department: Optional[MedicalDepartment] = None
    document_type: Optional[DocumentType] = None
    disease_categories: List[DiseaseCategory] = None
    evidence_level: Optional[EvidenceLevel] = None
    keywords: List[str] = None
    medical_terms: List[str] = None
    icd_codes: List[str] = None
    drug_names: List[str] = None
    author: Optional[str] = None
    institution: Optional[str] = None
    publication_date: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    language: str = "zh-CN"
    confidence_score: float = 0.0
    
    def __post_init__(self):
        if self.disease_categories is None:
            self.disease_categories = []
        if self.keywords is None:
            self.keywords = []
        if self.medical_terms is None:
            self.medical_terms = []
        if self.icd_codes is None:
            self.icd_codes = []
        if self.drug_names is None:
            self.drug_names = []

class MedicalTermExtractor:
    """医疗术语提取器"""
    
    def __init__(self):
        # 常见医疗术语模式
        self.medical_patterns = {
            'symptoms': r'(症状|表现|临床表现|体征)',
            'diagnosis': r'(诊断|检查|检验|影像)',
            'treatment': r'(治疗|用药|手术|康复)',
            'disease': r'(疾病|病症|综合征|感染)',
            'anatomy': r'(心脏|肺部|肝脏|肾脏|大脑|血管)',
            'medication': r'(药物|药品|制剂|注射|口服)'
        }
    
    def extract_medical_terms(self, text: str) -> List[str]:
        """从文本中提取医疗术语"""
        terms = []
        for category, pattern in self.medical_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            terms.extend(matches)
        
        # 去重并返回
        return list(set(terms))
    
    def extract_icd_codes(self, text: str) -> List[str]:
        """提取ICD编码"""
        icd_pattern = r'[A-Z]\d{2}\.?\d*'
        return re.findall(icd_pattern, text)

class MedicalDocumentClassifier:
    """医疗文档分类器"""
    
    def __init__(self):
        self.term_extractor = MedicalTermExtractor()
        
        # 科室关键词映射
        self.department_keywords = {
            MedicalDepartment.INTERNAL_MEDICINE: ['内科', '心血管', '呼吸', '消化', '内分泌', '肾内', '血液', '风湿', '免疫'],
            MedicalDepartment.SURGERY: ['外科', '手术', '骨科', '胸外', '神外', '泌外', '整形', '烧伤'],
            MedicalDepartment.SPECIALIZED: ['眼科', '耳鼻喉', '皮肤', '泌尿', '口腔', '麻醉'],
            MedicalDepartment.PEDIATRICS: ['儿科', '小儿', '新生儿', '儿童'],
            MedicalDepartment.OBSTETRICS_GYNECOLOGY: ['妇产科', '妇科', '产科', '妊娠', '分娩'],
            MedicalDepartment.EMERGENCY: ['急诊', '急救', '抢救', '重症']
        }
        
        # 文档类型关键词映射
        self.document_type_keywords = {
            DocumentType.CLINICAL_GUIDELINE: ['指南', '共识', '标准', '规范', '诊断'],
            DocumentType.TREATMENT_PROTOCOL: ['治疗', '方案', '流程', '急救', '质量'],
            DocumentType.DRUG_REFERENCE: ['药物', '用药', '说明书', '处方'],
            DocumentType.PROCEDURE_GUIDE: ['操作', '手术', '检验', '影像', '技术'],
            DocumentType.GENERAL_REFERENCE: ['病例', '研究', '教材', '护理', '教育']
        }
        
        # 疾病分类关键词映射
        self.disease_keywords = {
            DiseaseCategory.CARDIOVASCULAR: ['心脏', '心血管', '高血压', '冠心病', '心律'],
            DiseaseCategory.RESPIRATORY: ['肺', '呼吸', '咳嗽', '哮喘', '肺炎'],
            DiseaseCategory.DIGESTIVE: ['胃', '肠', '肝', '消化', '腹痛'],
            DiseaseCategory.NEUROLOGICAL: ['神经', '大脑', '头痛', '癫痫', '中风'],
            DiseaseCategory.MENTAL_DISORDERS: ['精神', '抑郁', '焦虑', '心理'],
            DiseaseCategory.INFECTIOUS: ['感染', '病毒', '细菌', '发热'],
            DiseaseCategory.CHRONIC_DISEASES: ['肿瘤', '癌症', '糖尿病', '慢性'],
            DiseaseCategory.GENERAL_CONDITIONS: ['皮肤', '泌尿', '妊娠', '先天']
        }
    
    def classify_document(self, title: str, content: str) -> MedicalMetadata:
        """对医疗文档进行分类"""
        text = f"{title} {content}"
        
        # 分类
        department = self._classify_department(text)
        document_type = self._classify_document_type(text)
        disease_categories = self._classify_disease_categories(text)
        
        # 提取术语
        medical_terms = self.term_extractor.extract_medical_terms(text)
        icd_codes = self.term_extractor.extract_icd_codes(text)
        
        # 创建元数据
        metadata = MedicalMetadata(
            document_id="",
            title=title,
            department=department,
            document_type=document_type,
            disease_categories=disease_categories,
            medical_terms=medical_terms,
            icd_codes=icd_codes
        )
        
        # 计算置信度
        metadata.confidence_score = self._calculate_confidence(metadata, text)
        
        return metadata
    
    def _classify_department(self, text: str) -> Optional[MedicalDepartment]:
        """分类科室"""
        for dept, keywords in self.department_keywords.items():
            if any(keyword in text for keyword in keywords):
                return dept
        return None
    
    def _classify_document_type(self, text: str) -> Optional[DocumentType]:
        """分类文档类型"""
        for doc_type, keywords in self.document_type_keywords.items():
            if any(keyword in text for keyword in keywords):
                return doc_type
        return None
    
    def _classify_disease_categories(self, text: str) -> List[DiseaseCategory]:
        """分类疾病类别"""
        categories = []
        for category, keywords in self.disease_keywords.items():
            if any(keyword in text for keyword in keywords):
                categories.append(category)
        return categories
    
    def _calculate_confidence(self, metadata: MedicalMetadata, text: str) -> float:
        """计算分类置信度"""
        score = 0.0
        total_factors = 4
        
        # 科室匹配
        if metadata.department:
            score += 0.3
        
        # 文档类型匹配
        if metadata.document_type:
            score += 0.3
        
        # 疾病分类匹配
        if metadata.disease_categories:
            score += 0.2
        
        # 医疗术语匹配
        if metadata.medical_terms:
            score += 0.2
        
        return min(score, 1.0)

def get_all_departments() -> List[str]:
    """获取所有科室列表"""
    return [dept.value for dept in MedicalDepartment]

def get_all_document_types() -> List[str]:
    """获取所有文档类型列表"""
    return [doc_type.value for doc_type in DocumentType]

def get_all_disease_categories() -> List[str]:
    """获取所有疾病分类列表"""
    return [category.value for category in DiseaseCategory]

if __name__ == "__main__":
    classifier = MedicalDocumentClassifier()
    
    # 测试分类
    title = "冠心病诊疗指南"
    content = "冠心病是心血管系统常见疾病，主要表现为胸痛、心律不齐等症状。诊断需要心电图检查..."
    
    metadata = classifier.classify_document(title, content)
    print(f"科室: {metadata.department}")
    print(f"文档类型: {metadata.document_type}")
    print(f"疾病分类: {metadata.disease_categories}")
    print(f"医疗术语: {metadata.medical_terms}")
    print(f"置信度: {metadata.confidence_score}")