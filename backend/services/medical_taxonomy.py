# services/medical_taxonomy.py
"""
医疗文档分类和标签系统
用于医疗知识库的文档分类、标签管理和元数据处理
"""

from enum import Enum
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime
import json
import re

class MedicalDepartment(Enum):
    """医疗科室分类"""
    INTERNAL_MEDICINE = "内科"
    SURGERY = "外科"
    PEDIATRICS = "儿科"
    OBSTETRICS_GYNECOLOGY = "妇产科"
    NEUROLOGY = "神经科"
    PSYCHIATRY = "精神科"
    DERMATOLOGY = "皮肤科"
    OPHTHALMOLOGY = "眼科"
    ENT = "耳鼻喉科"
    ORTHOPEDICS = "骨科"
    UROLOGY = "泌尿科"
    CARDIOLOGY = "心血管科"
    RESPIRATORY = "呼吸科"
    GASTROENTEROLOGY = "消化科"
    ENDOCRINOLOGY = "内分泌科"
    NEPHROLOGY = "肾内科"
    HEMATOLOGY = "血液科"
    ONCOLOGY = "肿瘤科"
    EMERGENCY = "急诊科"
    ICU = "重症医学科"
    RADIOLOGY = "影像科"
    PATHOLOGY = "病理科"
    LABORATORY = "检验科"
    PHARMACY = "药学科"
    REHABILITATION = "康复科"
    TRADITIONAL_CHINESE_MEDICINE = "中医科"

class DocumentType(Enum):
    """文档类型分类"""
    CLINICAL_GUIDELINE = "临床指南"
    DIAGNOSIS_CRITERIA = "诊断标准"
    TREATMENT_PROTOCOL = "治疗方案"
    DRUG_MANUAL = "药物说明书"
    CASE_STUDY = "病例研究"
    RESEARCH_PAPER = "研究论文"
    MEDICAL_TEXTBOOK = "医学教材"
    NURSING_MANUAL = "护理手册"
    SURGICAL_PROCEDURE = "手术操作"
    LABORATORY_REFERENCE = "检验参考"
    IMAGING_ATLAS = "影像图谱"
    EMERGENCY_PROTOCOL = "急救流程"
    INFECTION_CONTROL = "感控指南"
    QUALITY_STANDARD = "质量标准"
    PATIENT_EDUCATION = "患者教育"

class DiseaseCategory(Enum):
    """疾病分类（基于ICD-11）"""
    INFECTIOUS_DISEASES = "感染性疾病"
    NEOPLASMS = "肿瘤"
    BLOOD_DISORDERS = "血液及造血器官疾病"
    IMMUNE_DISORDERS = "免疫系统疾病"
    ENDOCRINE_DISORDERS = "内分泌、营养和代谢疾病"
    MENTAL_DISORDERS = "精神、行为和神经发育障碍"
    NERVOUS_SYSTEM = "神经系统疾病"
    VISUAL_SYSTEM = "视觉系统疾病"
    EAR_DISORDERS = "耳和乳突疾病"
    CIRCULATORY_SYSTEM = "循环系统疾病"
    RESPIRATORY_SYSTEM = "呼吸系统疾病"
    DIGESTIVE_SYSTEM = "消化系统疾病"
    SKIN_DISORDERS = "皮肤疾病"
    MUSCULOSKELETAL = "肌肉骨骼系统疾病"
    GENITOURINARY = "泌尿生殖系统疾病"
    PREGNANCY_RELATED = "妊娠、分娩和产褥期"
    PERINATAL_CONDITIONS = "围产期疾病"
    CONGENITAL_ANOMALIES = "先天性畸形"
    INJURY_POISONING = "损伤、中毒和外因"

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
            'symptoms': r'(症状|表现|体征|主诉)',
            'diagnosis': r'(诊断|确诊|疑诊|鉴别诊断)',
            'treatment': r'(治疗|疗法|用药|手术|康复)',
            'examination': r'(检查|检验|影像|B超|CT|MRI|X线)',
            'medication': r'(药物|药品|用药|剂量|给药)',
            'anatomy': r'(器官|组织|系统|部位)',
        }
        
        # 常见药物后缀
        self.drug_suffixes = [
            '片', '胶囊', '注射液', '颗粒', '糖浆', '软膏', '滴眼液',
            '喷雾剂', '栓剂', '贴剂', '口服液', '冲剂'
        ]
    
    def extract_medical_terms(self, text: str) -> List[str]:
        """提取医疗术语"""
        terms = []
        
        # 提取药物名称
        drug_pattern = r'[\u4e00-\u9fff]+(?:' + '|'.join(self.drug_suffixes) + ')'
        drugs = re.findall(drug_pattern, text)
        terms.extend(drugs)
        
        # 提取疾病名称（通常以"病"、"症"、"炎"等结尾）
        disease_pattern = r'[\u4e00-\u9fff]+(?:病|症|炎|癌|瘤|综合征)'
        diseases = re.findall(disease_pattern, text)
        terms.extend(diseases)
        
        # 提取检查项目
        exam_pattern = r'[\u4e00-\u9fff]*(?:检查|检验|测定|筛查|监测)'
        exams = re.findall(exam_pattern, text)
        terms.extend(exams)
        
        return list(set(terms))  # 去重
    
    def extract_icd_codes(self, text: str) -> List[str]:
        """提取ICD编码"""
        # ICD-10编码模式：字母+数字
        icd_pattern = r'[A-Z]\d{2}(?:\.\d{1,2})?'
        return re.findall(icd_pattern, text)

class MedicalDocumentClassifier:
    """医疗文档分类器"""
    
    def __init__(self):
        self.term_extractor = MedicalTermExtractor()
        
        # 科室关键词映射
        self.department_keywords = {
            MedicalDepartment.CARDIOLOGY: ['心脏', '心血管', '冠心病', '心律', '心肌', '心电图'],
            MedicalDepartment.RESPIRATORY: ['肺', '呼吸', '气管', '支气管', '肺炎', '哮喘'],
            MedicalDepartment.GASTROENTEROLOGY: ['胃', '肠', '消化', '肝', '胆', '胰腺'],
            MedicalDepartment.NEUROLOGY: ['神经', '脑', '头痛', '癫痫', '中风', '帕金森'],
            MedicalDepartment.ONCOLOGY: ['肿瘤', '癌', '化疗', '放疗', '恶性', '良性'],
            MedicalDepartment.ENDOCRINOLOGY: ['糖尿病', '甲状腺', '内分泌', '激素', '代谢'],
            # 可以继续添加更多科室的关键词
        }
        
        # 文档类型关键词映射
        self.doctype_keywords = {
            DocumentType.CLINICAL_GUIDELINE: ['指南', '规范', '标准', '共识'],
            DocumentType.DIAGNOSIS_CRITERIA: ['诊断', '标准', 'criteria'],
            DocumentType.TREATMENT_PROTOCOL: ['治疗', '方案', 'protocol'],
            DocumentType.DRUG_MANUAL: ['说明书', '用法', '用量', '副作用'],
            DocumentType.CASE_STUDY: ['病例', '案例', 'case'],
        }
    
    def classify_document(self, title: str, content: str) -> MedicalMetadata:
        """分类医疗文档"""
        text = f"{title} {content}"
        
        # 创建基础元数据
        metadata = MedicalMetadata(
            document_id="",  # 需要外部设置
            title=title,
            last_updated=datetime.now()
        )
        
        # 提取医疗术语
        metadata.medical_terms = self.term_extractor.extract_medical_terms(text)
        metadata.icd_codes = self.term_extractor.extract_icd_codes(text)
        
        # 分类科室
        metadata.department = self._classify_department(text)
        
        # 分类文档类型
        metadata.document_type = self._classify_document_type(text)
        
        # 分类疾病类别
        metadata.disease_categories = self._classify_disease_categories(text)
        
        # 计算置信度
        metadata.confidence_score = self._calculate_confidence(metadata, text)
        
        return metadata
    
    def _classify_department(self, text: str) -> Optional[MedicalDepartment]:
        """分类科室"""
        scores = {}
        for dept, keywords in self.department_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                scores[dept] = score
        
        if scores:
            return max(scores, key=scores.get)
        return None
    
    def _classify_document_type(self, text: str) -> Optional[DocumentType]:
        """分类文档类型"""
        scores = {}
        for doctype, keywords in self.doctype_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                scores[doctype] = score
        
        if scores:
            return max(scores, key=scores.get)
        return None
    
    def _classify_disease_categories(self, text: str) -> List[DiseaseCategory]:
        """分类疾病类别"""
        categories = []
        
        # 基于关键词的简单分类
        category_keywords = {
            DiseaseCategory.CIRCULATORY_SYSTEM: ['心脏', '血管', '高血压', '冠心病'],
            DiseaseCategory.RESPIRATORY_SYSTEM: ['肺', '呼吸', '哮喘', '肺炎'],
            DiseaseCategory.DIGESTIVE_SYSTEM: ['胃', '肠', '肝', '消化'],
            DiseaseCategory.NERVOUS_SYSTEM: ['神经', '脑', '中风', '癫痫'],
            DiseaseCategory.NEOPLASMS: ['肿瘤', '癌', '恶性', '良性'],
            # 可以继续添加更多分类
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in text for keyword in keywords):
                categories.append(category)
        
        return categories
    
    def _calculate_confidence(self, metadata: MedicalMetadata, text: str) -> float:
        """计算分类置信度"""
        score = 0.0
        
        # 基于提取的术语数量
        if metadata.medical_terms:
            score += min(len(metadata.medical_terms) * 0.1, 0.3)
        
        # 基于ICD编码
        if metadata.icd_codes:
            score += 0.2
        
        # 基于科室分类
        if metadata.department:
            score += 0.2
        
        # 基于文档类型
        if metadata.document_type:
            score += 0.2
        
        # 基于疾病分类
        if metadata.disease_categories:
            score += 0.1
        
        return min(score, 1.0)

# 使用示例
if __name__ == "__main__":
    classifier = MedicalDocumentClassifier()
    
    # 示例文档
    title = "冠心病诊疗指南"
    content = "冠心病是心血管系统常见疾病，主要表现为胸痛、心律不齐等症状。诊断需要心电图检查..."
    
    metadata = classifier.classify_document(title, content)
    print(f"科室: {metadata.department}")
    print(f"文档类型: {metadata.document_type}")
    print(f"医疗术语: {metadata.medical_terms}")
    print(f"置信度: {metadata.confidence_score}")