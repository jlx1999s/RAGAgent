# services/medical_association_service.py
from __future__ import annotations
import re
import json
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from collections import defaultdict, Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class AssociationType(Enum):
    """关联类型枚举"""
    SYMPTOM_DISEASE = "symptom_disease"  # 症状-疾病关联
    DRUG_SIDE_EFFECT = "drug_side_effect"  # 药物-副作用关联
    DRUG_INTERACTION = "drug_interaction"  # 药物相互作用
    DISEASE_COMPLICATION = "disease_complication"  # 疾病-并发症关联
    TREATMENT_INDICATION = "treatment_indication"  # 治疗-适应症关联
    CONTRAINDICATION = "contraindication"  # 禁忌症关联
    RISK_FACTOR = "risk_factor"  # 风险因素关联

@dataclass
class MedicalAssociation:
    """医疗关联"""
    source: str  # 源实体
    target: str  # 目标实体
    association_type: AssociationType
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    frequency: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AssociationQueryResult:
    """关联查询结果"""
    query: str
    associations: List[MedicalAssociation]
    total_count: int
    confidence_threshold: float
    search_metadata: Dict[str, Any] = field(default_factory=dict)

class MedicalAssociationExtractor:
    """医疗关联提取器"""
    
    def __init__(self):
        # 症状-疾病关联模式
        self.symptom_disease_patterns = [
            r'(\w+(?:\s+\w+)*)\s*(?:是|为|属于)\s*(\w+(?:\s+\w+)*)\s*(?:的症状|症状)',
            r'(\w+(?:\s+\w+)*)\s*(?:可能|常常|经常|通常)\s*(?:出现|表现为|伴有)\s*(\w+(?:\s+\w+)*)',
            r'(\w+(?:\s+\w+)*)\s*(?:患者|病人)\s*(?:常见|多见|可见)\s*(\w+(?:\s+\w+)*)',
            r'(\w+(?:\s+\w+)*)\s*(?:引起|导致|造成)\s*(\w+(?:\s+\w+)*)',
            r'(\w+(?:\s+\w+)*)\s*(?:症状|表现)\s*(?:包括|有)\s*(\w+(?:\s+\w+)*)',
        ]
        
        # 药物-副作用关联模式
        self.drug_side_effect_patterns = [
            r'(\w+(?:\s+\w+)*)\s*(?:的副作用|副作用)\s*(?:包括|有|为)\s*(\w+(?:\s+\w+)*)',
            r'(\w+(?:\s+\w+)*)\s*(?:可能|会|能)\s*(?:引起|导致|造成)\s*(\w+(?:\s+\w+)*)',
            r'(?:服用|使用)\s*(\w+(?:\s+\w+)*)\s*(?:后|时)\s*(?:可能|会|能)\s*(?:出现|发生)\s*(\w+(?:\s+\w+)*)',
            r'(\w+(?:\s+\w+)*)\s*(?:的不良反应|不良反应)\s*(?:包括|有)\s*(\w+(?:\s+\w+)*)',
        ]
        
        # 药物相互作用模式
        self.drug_interaction_patterns = [
            r'(\w+(?:\s+\w+)*)\s*(?:与|和)\s*(\w+(?:\s+\w+)*)\s*(?:相互作用|相互影响|不能同用)',
            r'(\w+(?:\s+\w+)*)\s*(?:禁止|不宜|避免)\s*(?:与|和)\s*(\w+(?:\s+\w+)*)\s*(?:同时使用|联用)',
            r'(\w+(?:\s+\w+)*)\s*(?:会|能)\s*(?:增强|减弱|影响)\s*(\w+(?:\s+\w+)*)\s*(?:的效果|效应)',
        ]
        
        # 疾病-并发症模式
        self.disease_complication_patterns = [
            r'(\w+(?:\s+\w+)*)\s*(?:的并发症|并发症)\s*(?:包括|有)\s*(\w+(?:\s+\w+)*)',
            r'(\w+(?:\s+\w+)*)\s*(?:可能|会|能)\s*(?:并发|引起|导致)\s*(\w+(?:\s+\w+)*)',
            r'(\w+(?:\s+\w+)*)\s*(?:患者|病人)\s*(?:容易|易于)\s*(?:发生|出现)\s*(\w+(?:\s+\w+)*)',
        ]
        
        # 治疗-适应症模式
        self.treatment_indication_patterns = [
            r'(\w+(?:\s+\w+)*)\s*(?:用于|适用于|治疗)\s*(\w+(?:\s+\w+)*)',
            r'(\w+(?:\s+\w+)*)\s*(?:是|为)\s*(\w+(?:\s+\w+)*)\s*(?:的治疗|治疗方法)',
            r'(?:治疗|处理)\s*(\w+(?:\s+\w+)*)\s*(?:可以|能够|应该)\s*(?:使用|采用)\s*(\w+(?:\s+\w+)*)',
        ]
        
        # 禁忌症模式
        self.contraindication_patterns = [
            r'(\w+(?:\s+\w+)*)\s*(?:禁用于|禁止用于|不适用于)\s*(\w+(?:\s+\w+)*)',
            r'(\w+(?:\s+\w+)*)\s*(?:患者|病人)\s*(?:禁用|禁止使用|不能使用)\s*(\w+(?:\s+\w+)*)',
            r'(\w+(?:\s+\w+)*)\s*(?:是|为)\s*(\w+(?:\s+\w+)*)\s*(?:的禁忌症|禁忌)',
        ]
        
        # 风险因素模式
        self.risk_factor_patterns = [
            r'(\w+(?:\s+\w+)*)\s*(?:是|为)\s*(\w+(?:\s+\w+)*)\s*(?:的危险因素|危险因子|风险因素)',
            r'(\w+(?:\s+\w+)*)\s*(?:增加|提高)\s*(\w+(?:\s+\w+)*)\s*(?:的风险|风险)',
            r'(?:有|存在)\s*(\w+(?:\s+\w+)*)\s*(?:的人|患者)\s*(?:容易|易于)\s*(?:患|得)\s*(\w+(?:\s+\w+)*)',
        ]
        
        # 模式映射
        self.pattern_mapping = {
            AssociationType.SYMPTOM_DISEASE: self.symptom_disease_patterns,
            AssociationType.DRUG_SIDE_EFFECT: self.drug_side_effect_patterns,
            AssociationType.DRUG_INTERACTION: self.drug_interaction_patterns,
            AssociationType.DISEASE_COMPLICATION: self.disease_complication_patterns,
            AssociationType.TREATMENT_INDICATION: self.treatment_indication_patterns,
            AssociationType.CONTRAINDICATION: self.contraindication_patterns,
            AssociationType.RISK_FACTOR: self.risk_factor_patterns,
        }
        
        # 医疗实体词典
        self.medical_entities = {
            'symptoms': [
                '头痛', '发热', '咳嗽', '胸痛', '腹痛', '恶心', '呕吐', '腹泻', '便秘', '失眠',
                '疲劳', '心悸', '气短', '眩晕', '皮疹', '瘙痒', '水肿', '出血', '麻木', '疼痛'
            ],
            'diseases': [
                '高血压', '糖尿病', '冠心病', '心脏病', '肝炎', '肾炎', '肺炎', '胃炎', '肠炎', '关节炎',
                '癌症', '肿瘤', '感冒', '流感', '哮喘', '支气管炎', '肺结核', '肝硬化', '肾衰竭', '心衰'
            ],
            'drugs': [
                '阿司匹林', '青霉素', '头孢', '胰岛素', '降压药', '抗生素', '止痛药', '感冒药', '退烧药', '消炎药',
                '抗癌药', '免疫抑制剂', '激素', '维生素', '钙片', '铁剂', '叶酸', '胰岛素', '降糖药', '利尿剂'
            ],
            'treatments': [
                '手术', '化疗', '放疗', '免疫治疗', '中医治疗', '针灸', '按摩', '理疗', '康复训练', '心理治疗',
                '药物治疗', '物理治疗', '饮食治疗', '运动治疗', '休息', '观察', '监测', '护理', '支持治疗', '对症治疗'
            ]
        }

    def extract_associations_from_text(self, text: str) -> List[MedicalAssociation]:
        """从文本中提取医疗关联"""
        associations = []
        
        for association_type, patterns in self.pattern_mapping.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    if len(match.groups()) >= 2:
                        source = match.group(1).strip()
                        target = match.group(2).strip()
                        
                        # 验证是否为有效的医疗实体
                        if self._is_valid_medical_entity(source) and self._is_valid_medical_entity(target):
                            association = MedicalAssociation(
                                source=source,
                                target=target,
                                association_type=association_type,
                                confidence=0.7,  # 基础置信度
                                evidence=[text[:200]],  # 保存证据片段
                                frequency=1
                            )
                            associations.append(association)
        
        return associations

    def _is_valid_medical_entity(self, entity: str) -> bool:
        """验证是否为有效的医疗实体"""
        entity_lower = entity.lower()
        
        # 检查是否在预定义词典中
        for category, entities in self.medical_entities.items():
            if any(e.lower() in entity_lower or entity_lower in e.lower() for e in entities):
                return True
        
        # 基于长度和字符的简单验证
        if len(entity) < 2 or len(entity) > 50:
            return False
        
        # 检查是否包含医疗相关关键词
        medical_keywords = ['病', '症', '炎', '癌', '瘤', '药', '素', '酸', '胺', '醇', '酮']
        if any(keyword in entity for keyword in medical_keywords):
            return True
        
        return False

class MedicalAssociationService:
    """医疗关联服务"""
    
    def __init__(self):
        self.extractor = MedicalAssociationExtractor()
        self.associations_db: Dict[str, List[MedicalAssociation]] = defaultdict(list)
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.entity_vectors = {}
        
        # 预定义的医疗关联知识库
        self._initialize_knowledge_base()

    def _initialize_knowledge_base(self):
        """初始化医疗关联知识库"""
        # 症状-疾病关联
        symptom_disease_data = [
            ("头痛", "高血压", 0.8),
            ("头痛", "感冒", 0.9),
            ("胸痛", "冠心病", 0.9),
            ("胸痛", "心肌梗死", 0.95),
            ("咳嗽", "感冒", 0.8),
            ("咳嗽", "肺炎", 0.9),
            ("发热", "感冒", 0.8),
            ("发热", "肺炎", 0.9),
            ("腹痛", "胃炎", 0.8),
            ("腹痛", "阑尾炎", 0.9),
            ("多饮", "糖尿病", 0.9),
            ("多尿", "糖尿病", 0.9),
            ("心悸", "心律不齐", 0.8),
            ("气短", "心衰", 0.9),
        ]
        
        for symptom, disease, confidence in symptom_disease_data:
            association = MedicalAssociation(
                source=symptom,
                target=disease,
                association_type=AssociationType.SYMPTOM_DISEASE,
                confidence=confidence,
                frequency=10
            )
            self.associations_db[f"{symptom}_{disease}"].append(association)

        # 药物-副作用关联
        drug_side_effect_data = [
            ("阿司匹林", "胃出血", 0.7),
            ("阿司匹林", "胃痛", 0.6),
            ("青霉素", "过敏反应", 0.8),
            ("青霉素", "皮疹", 0.6),
            ("胰岛素", "低血糖", 0.9),
            ("降压药", "头晕", 0.7),
            ("降压药", "乏力", 0.6),
            ("抗生素", "腹泻", 0.6),
            ("抗生素", "菌群失调", 0.7),
            ("化疗药", "恶心", 0.8),
            ("化疗药", "脱发", 0.9),
            ("激素", "水肿", 0.7),
            ("激素", "血糖升高", 0.8),
        ]
        
        for drug, side_effect, confidence in drug_side_effect_data:
            association = MedicalAssociation(
                source=drug,
                target=side_effect,
                association_type=AssociationType.DRUG_SIDE_EFFECT,
                confidence=confidence,
                frequency=8
            )
            self.associations_db[f"{drug}_{side_effect}"].append(association)

        # 药物相互作用
        drug_interaction_data = [
            ("阿司匹林", "华法林", 0.9),
            ("阿司匹林", "降压药", 0.6),
            ("胰岛素", "降糖药", 0.8),
            ("抗生素", "避孕药", 0.7),
            ("抗癫痫药", "避孕药", 0.8),
            ("利尿剂", "降压药", 0.7),
        ]
        
        for drug1, drug2, confidence in drug_interaction_data:
            association = MedicalAssociation(
                source=drug1,
                target=drug2,
                association_type=AssociationType.DRUG_INTERACTION,
                confidence=confidence,
                frequency=5
            )
            self.associations_db[f"{drug1}_{drug2}"].append(association)

    def find_associations(
        self, 
        query: str, 
        association_types: Optional[List[AssociationType]] = None,
        confidence_threshold: float = 0.5,
        max_results: int = 20
    ) -> AssociationQueryResult:
        """查找医疗关联"""
        
        if association_types is None:
            association_types = list(AssociationType)
        
        # 从查询中提取实体
        query_entities = self._extract_entities_from_query(query)
        
        # 查找相关关联
        relevant_associations = []
        
        for key, associations in self.associations_db.items():
            for association in associations:
                if association.association_type not in association_types:
                    continue
                
                if association.confidence < confidence_threshold:
                    continue
                
                # 检查查询实体是否匹配
                if self._matches_query_entities(association, query_entities, query):
                    relevant_associations.append(association)
        
        # 按置信度排序
        relevant_associations.sort(key=lambda x: x.confidence, reverse=True)
        
        # 限制结果数量
        relevant_associations = relevant_associations[:max_results]
        
        return AssociationQueryResult(
            query=query,
            associations=relevant_associations,
            total_count=len(relevant_associations),
            confidence_threshold=confidence_threshold,
            search_metadata={
                "query_entities": query_entities,
                "association_types": [t.value for t in association_types]
            }
        )

    def _extract_entities_from_query(self, query: str) -> List[str]:
        """从查询中提取实体"""
        entities = []
        query_lower = query.lower()
        
        # 检查预定义实体
        for category, entity_list in self.extractor.medical_entities.items():
            for entity in entity_list:
                if entity.lower() in query_lower:
                    entities.append(entity)
        
        return entities

    def _matches_query_entities(self, association: MedicalAssociation, query_entities: List[str], query: str) -> bool:
        """检查关联是否匹配查询实体"""
        query_lower = query.lower()
        source_lower = association.source.lower()
        target_lower = association.target.lower()
        
        # 直接匹配
        if source_lower in query_lower or target_lower in query_lower:
            return True
        
        # 实体匹配
        for entity in query_entities:
            entity_lower = entity.lower()
            if (entity_lower in source_lower or source_lower in entity_lower or
                entity_lower in target_lower or target_lower in entity_lower):
                return True
        
        return False

    async def find_symptom_disease_associations(self, symptoms: List[str]) -> List[MedicalAssociation]:
        """查找症状-疾病关联"""
        associations = []
        
        for symptom in symptoms:
            result = self.find_associations(
                query=symptom,
                association_types=[AssociationType.SYMPTOM_DISEASE],
                confidence_threshold=0.6
            )
            associations.extend(result.associations)
        
        # 去重并按置信度排序
        unique_associations = {}
        for assoc in associations:
            key = f"{assoc.source}_{assoc.target}_{assoc.association_type.value}"
            if key not in unique_associations or unique_associations[key].confidence < assoc.confidence:
                unique_associations[key] = assoc
        
        return sorted(unique_associations.values(), key=lambda x: x.confidence, reverse=True)

    async def find_drug_side_effects(self, drug_name: str) -> List[MedicalAssociation]:
        """查找药物副作用"""
        result = self.find_associations(
            query=drug_name,
            association_types=[AssociationType.DRUG_SIDE_EFFECT],
            confidence_threshold=0.5
        )
        return result.associations

    async def find_drug_interactions(self, drugs: List[str]) -> List[MedicalAssociation]:
        """查找药物相互作用"""
        interactions = []
        
        for drug in drugs:
            result = self.find_associations(
                query=drug,
                association_types=[AssociationType.DRUG_INTERACTION],
                confidence_threshold=0.6
            )
            interactions.extend(result.associations)
        
        return interactions

    async def update_associations_from_documents(self, documents: List[str]) -> Dict[str, int]:
        """从文档更新关联知识库"""
        new_associations = 0
        updated_associations = 0
        
        for doc in documents:
            extracted = self.extractor.extract_associations_from_text(doc)
            
            for association in extracted:
                key = f"{association.source}_{association.target}_{association.association_type.value}"
                
                if key in self.associations_db:
                    # 更新现有关联
                    existing = self.associations_db[key][0]
                    existing.frequency += 1
                    existing.confidence = min(0.95, existing.confidence + 0.05)
                    if doc[:200] not in existing.evidence:
                        existing.evidence.append(doc[:200])
                    updated_associations += 1
                else:
                    # 添加新关联
                    self.associations_db[key].append(association)
                    new_associations += 1
        
        return {
            "new_associations": new_associations,
            "updated_associations": updated_associations,
            "total_associations": len(self.associations_db)
        }

    async def get_association_statistics(self) -> Dict[str, Any]:
        """获取关联统计信息"""
        stats = {
            "total_associations": len(self.associations_db),
            "by_type": {},
            "confidence_distribution": {
                "high": 0,  # > 0.8
                "medium": 0,  # 0.6 - 0.8
                "low": 0  # < 0.6
            },
            "top_entities": {
                "sources": Counter(),
                "targets": Counter()
            }
        }
        
        for associations in self.associations_db.values():
            for assoc in associations:
                # 按类型统计
                type_name = assoc.association_type.value
                if type_name not in stats["by_type"]:
                    stats["by_type"][type_name] = 0
                stats["by_type"][type_name] += 1
                
                # 置信度分布
                if assoc.confidence > 0.8:
                    stats["confidence_distribution"]["high"] += 1
                elif assoc.confidence > 0.6:
                    stats["confidence_distribution"]["medium"] += 1
                else:
                    stats["confidence_distribution"]["low"] += 1
                
                # 实体统计
                stats["top_entities"]["sources"][assoc.source] += 1
                stats["top_entities"]["targets"][assoc.target] += 1
        
        # 转换为列表格式
        stats["top_entities"]["sources"] = dict(stats["top_entities"]["sources"].most_common(10))
        stats["top_entities"]["targets"] = dict(stats["top_entities"]["targets"].most_common(10))
        
        return stats

# 全局服务实例
medical_association_service = MedicalAssociationService()