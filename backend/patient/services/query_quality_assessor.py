"""
查询质量评估服务
用于评估医疗检索查询的质量和相关性
"""

from __future__ import annotations
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import math
from collections import Counter

class QueryQualityLevel(Enum):
    """查询质量等级"""
    EXCELLENT = "excellent"  # 优秀 (0.8-1.0)
    GOOD = "good"           # 良好 (0.6-0.8)
    FAIR = "fair"           # 一般 (0.4-0.6)
    POOR = "poor"           # 较差 (0.2-0.4)
    VERY_POOR = "very_poor" # 很差 (0.0-0.2)

@dataclass
class QueryQualityMetrics:
    """查询质量指标"""
    clarity_score: float        # 清晰度分数
    specificity_score: float    # 具体性分数
    medical_relevance: float    # 医疗相关性分数
    completeness_score: float   # 完整性分数
    complexity_score: float     # 复杂度分数
    overall_score: float        # 总体分数
    quality_level: QueryQualityLevel
    suggestions: List[str]      # 改进建议

@dataclass
class RetrievalQualityMetrics:
    """检索质量指标"""
    result_relevance: float     # 结果相关性
    result_diversity: float     # 结果多样性
    coverage_score: float       # 覆盖度分数
    confidence_score: float     # 置信度分数
    overall_score: float        # 总体分数
    quality_level: QueryQualityLevel

class QueryQualityAssessor:
    """查询质量评估器"""
    
    def __init__(self):
        self.logger = logging.getLogger("services.query_quality_assessor")
        
        # 医疗关键词词典
        self.medical_keywords = {
            'symptoms': ['症状', '疼痛', '发热', '咳嗽', '头痛', '恶心', '呕吐', '腹泻', '便秘', '失眠', '鼻塞', '流鼻涕', '喉咙痛'],
            'diseases': ['疾病', '病', '症', '炎', '癌', '瘤', '综合征', '感染', '过敏', '中毒', '感冒', '发烧', '肺炎', '胃炎', '肝炎'],
            'treatments': ['治疗', '手术', '药物', '康复', '护理', '预防', '诊断', '检查', '化疗', '放疗', '怎么办', '如何治疗'],
            'anatomy': ['心脏', '肺', '肝', '肾', '胃', '肠', '大脑', '血管', '骨骼', '肌肉'],
            'procedures': ['检查', '检验', '化验', '拍片', 'CT', 'MRI', 'B超', '内镜', '活检', '穿刺'],
            'demographics': ['小孩', '儿童', '孩子', '婴儿', '幼儿', '成人', '老人', '孕妇', '患者']
        }
        
        # 质量权重配置
        self.quality_weights = {
            'clarity': 0.25,        # 清晰度权重
            'specificity': 0.25,    # 具体性权重
            'medical_relevance': 0.3, # 医疗相关性权重
            'completeness': 0.15,   # 完整性权重
            'complexity': 0.05      # 复杂度权重
        }
    
    def assess_query_quality(self, query: str, context: Optional[Dict[str, Any]] = None) -> QueryQualityMetrics:
        """
        评估查询质量
        
        Args:
            query: 查询文本
            context: 上下文信息（意图识别结果等）
        
        Returns:
            查询质量指标
        """
        try:
            # 计算各项指标
            clarity_score = self._assess_clarity(query)
            specificity_score = self._assess_specificity(query, context)
            medical_relevance = self._assess_medical_relevance(query)
            completeness_score = self._assess_completeness(query, context)
            complexity_score = self._assess_complexity(query)
            
            # 计算总体分数
            overall_score = (
                clarity_score * self.quality_weights['clarity'] +
                specificity_score * self.quality_weights['specificity'] +
                medical_relevance * self.quality_weights['medical_relevance'] +
                completeness_score * self.quality_weights['completeness'] +
                complexity_score * self.quality_weights['complexity']
            )
            
            # 确定质量等级
            quality_level = self._determine_quality_level(overall_score)
            
            # 生成改进建议
            suggestions = self._generate_suggestions(
                query, clarity_score, specificity_score, 
                medical_relevance, completeness_score, complexity_score
            )
            
            self.logger.info(f"查询质量评估完成 - 总分: {overall_score:.3f}, 等级: {quality_level.value}")
            
            return QueryQualityMetrics(
                clarity_score=clarity_score,
                specificity_score=specificity_score,
                medical_relevance=medical_relevance,
                completeness_score=completeness_score,
                complexity_score=complexity_score,
                overall_score=overall_score,
                quality_level=quality_level,
                suggestions=suggestions
            )
            
        except Exception as e:
            self.logger.error(f"查询质量评估失败: {e}")
            return QueryQualityMetrics(
                clarity_score=0.0,
                specificity_score=0.0,
                medical_relevance=0.0,
                completeness_score=0.0,
                complexity_score=0.0,
                overall_score=0.0,
                quality_level=QueryQualityLevel.VERY_POOR,
                suggestions=["查询评估失败，请检查查询格式"]
            )
    
    def assess_retrieval_quality(
        self, 
        query: str, 
        results: List[Dict[str, Any]], 
        metadata: Dict[str, Any]
    ) -> RetrievalQualityMetrics:
        """
        评估检索结果质量
        
        Args:
            query: 原始查询
            results: 检索结果列表
            metadata: 检索元数据
        
        Returns:
            检索质量指标
        """
        try:
            # 计算结果相关性
            result_relevance = self._assess_result_relevance(query, results)
            
            # 计算结果多样性
            result_diversity = self._assess_result_diversity(results)
            
            # 计算覆盖度分数
            coverage_score = self._assess_coverage(query, results, metadata)
            
            # 计算置信度分数
            confidence_score = self._assess_confidence(results, metadata)
            
            # 计算总体分数
            overall_score = (
                result_relevance * 0.4 +
                result_diversity * 0.2 +
                coverage_score * 0.25 +
                confidence_score * 0.15
            )
            
            quality_level = self._determine_quality_level(overall_score)
            
            self.logger.info(f"检索质量评估完成 - 总分: {overall_score:.3f}, 等级: {quality_level.value}")
            
            return RetrievalQualityMetrics(
                result_relevance=result_relevance,
                result_diversity=result_diversity,
                coverage_score=coverage_score,
                confidence_score=confidence_score,
                overall_score=overall_score,
                quality_level=quality_level
            )
            
        except Exception as e:
            self.logger.error(f"检索质量评估失败: {e}")
            return RetrievalQualityMetrics(
                result_relevance=0.0,
                result_diversity=0.0,
                coverage_score=0.0,
                confidence_score=0.0,
                overall_score=0.0,
                quality_level=QueryQualityLevel.VERY_POOR
            )
    
    def _assess_clarity(self, query: str) -> float:
        """评估查询清晰度"""
        score = 0.5  # 基础分数
        
        # 长度适中性检查
        length = len(query.strip())
        if 5 <= length <= 100:
            score += 0.2
        elif length > 100:
            score -= 0.1
        
        # 语法完整性检查
        if self._has_complete_grammar(query):
            score += 0.2
        
        # 无歧义性检查
        if not self._has_ambiguity(query):
            score += 0.1
        
        return min(max(score, 0.0), 1.0)
    
    def _assess_specificity(self, query: str, context: Optional[Dict[str, Any]]) -> float:
        """评估查询具体性"""
        score = 0.3  # 基础分数
        
        # 具体医疗术语检查
        medical_terms = self._count_medical_terms(query)
        if medical_terms >= 2:
            score += 0.3
        elif medical_terms == 1:
            score += 0.2
        
        # 上下文信息加分
        if context:
            if context.get('department'):
                score += 0.15
            if context.get('document_type'):
                score += 0.1
            if context.get('disease_category'):
                score += 0.15
        
        # 数量词和修饰词检查
        if self._has_quantifiers(query):
            score += 0.1
        
        return min(max(score, 0.0), 1.0)
    
    def _assess_medical_relevance(self, query: str) -> float:
        """评估医疗相关性"""
        score = 0.0
        
        # 医疗关键词匹配
        for category, keywords in self.medical_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in query)
            if matches > 0:
                score += min(matches * 0.1, 0.3)
        
        # 医疗模式匹配
        medical_patterns = [
            r'什么是.*?病',
            r'如何治疗.*?',
            r'.*?的症状',
            r'.*?的原因',
            r'.*?的诊断',
            r'.*?药物.*?',
            r'.*?手术.*?'
        ]
        
        for pattern in medical_patterns:
            if re.search(pattern, query):
                score += 0.15
                break
        
        return min(max(score, 0.0), 1.0)
    
    def _assess_completeness(self, query: str, context: Optional[Dict[str, Any]]) -> float:
        """评估查询完整性"""
        score = 0.4  # 基础分数
        
        # 包含主要医疗要素
        elements = {
            'condition': any(word in query for word in ['病', '症', '疾病', '症状']),
            'action': any(word in query for word in ['治疗', '诊断', '检查', '预防']),
            'target': any(word in query for word in ['患者', '病人', '人群', '儿童', '成人'])
        }
        
        score += sum(0.15 for element in elements.values() if element)
        
        # 上下文完整性
        if context and context.get('confidence', 0) > 0.7:
            score += 0.15
        
        return min(max(score, 0.0), 1.0)
    
    def _assess_complexity(self, query: str) -> float:
        """评估查询复杂度（适中的复杂度得分更高）"""
        # 计算复杂度指标
        word_count = len(query.split())
        char_count = len(query)
        medical_terms = self._count_medical_terms(query)
        
        # 理想复杂度范围
        ideal_word_range = (3, 15)
        ideal_char_range = (10, 80)
        ideal_medical_terms = (1, 3)
        
        # 计算各项复杂度分数
        word_score = 1.0 if ideal_word_range[0] <= word_count <= ideal_word_range[1] else 0.5
        char_score = 1.0 if ideal_char_range[0] <= char_count <= ideal_char_range[1] else 0.5
        term_score = 1.0 if ideal_medical_terms[0] <= medical_terms <= ideal_medical_terms[1] else 0.5
        
        return (word_score + char_score + term_score) / 3
    
    def _assess_result_relevance(self, query: str, results: List[Dict[str, Any]]) -> float:
        """评估结果相关性"""
        if not results:
            return 0.0
        
        total_relevance = 0.0
        query_terms = set(query.lower().split())
        
        for result in results:
            text = result.get('text', '').lower()
            score = result.get('score', 0.0)
            
            # 基于检索分数
            relevance = min(score, 1.0) * 0.6
            
            # 基于词汇重叠
            text_terms = set(text.split())
            overlap = len(query_terms.intersection(text_terms)) / len(query_terms) if query_terms else 0
            relevance += overlap * 0.4
            
            total_relevance += relevance
        
        return total_relevance / len(results)
    
    def _assess_result_diversity(self, results: List[Dict[str, Any]]) -> float:
        """评估结果多样性"""
        if not results:
            return 0.0
        
        # 科室多样性
        departments = set()
        doc_types = set()
        
        for result in results:
            metadata = result.get('metadata', {})
            if metadata.get('department'):
                departments.add(metadata['department'])
            if metadata.get('document_type'):
                doc_types.add(metadata['document_type'])
        
        # 计算多样性分数
        dept_diversity = min(len(departments) / 5, 1.0)  # 最多5个科室
        type_diversity = min(len(doc_types) / 3, 1.0)    # 最多3种文档类型
        
        return (dept_diversity + type_diversity) / 2
    
    def _assess_coverage(self, query: str, results: List[Dict[str, Any]], metadata: Dict[str, Any]) -> float:
        """评估覆盖度"""
        if not results:
            return 0.0
        
        # 基于结果数量
        result_count_score = min(len(results) / 10, 1.0)  # 理想结果数为10
        
        # 基于KG增强覆盖度
        kg_enhancement = metadata.get('kg_enhancement', {})
        kg_score = 0.0
        if kg_enhancement.get('entities'):
            kg_score += 0.3
        if kg_enhancement.get('relations'):
            kg_score += 0.2
        if kg_enhancement.get('suggestions'):
            kg_score += 0.2
        
        # 基于医疗关联覆盖度
        associations = metadata.get('medical_associations', [])
        assoc_score = min(len(associations) / 5, 0.3)  # 最多5个关联
        
        return (result_count_score * 0.5 + kg_score + assoc_score)
    
    def _assess_confidence(self, results: List[Dict[str, Any]], metadata: Dict[str, Any]) -> float:
        """评估置信度"""
        if not results:
            return 0.0
        
        # 基于检索分数
        scores = [result.get('score', 0.0) for result in results]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # 基于意图识别置信度
        intent_confidence = metadata.get('intent_recognition', {}).get('confidence', 0.0)
        
        return (avg_score * 0.7 + intent_confidence * 0.3)
    
    def _determine_quality_level(self, score: float) -> QueryQualityLevel:
        """确定质量等级"""
        if score >= 0.8:
            return QueryQualityLevel.EXCELLENT
        elif score >= 0.6:
            return QueryQualityLevel.GOOD
        elif score >= 0.4:
            return QueryQualityLevel.FAIR
        elif score >= 0.2:
            return QueryQualityLevel.POOR
        else:
            return QueryQualityLevel.VERY_POOR
    
    def _generate_suggestions(
        self, 
        query: str, 
        clarity: float, 
        specificity: float, 
        medical_relevance: float, 
        completeness: float, 
        complexity: float
    ) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        if clarity < 0.6:
            suggestions.append("建议使用更清晰、简洁的表达方式")
        
        if specificity < 0.6:
            suggestions.append("建议添加更具体的医疗术语或症状描述")
        
        if medical_relevance < 0.5:
            suggestions.append("建议增加医疗相关的关键词")
        
        if completeness < 0.6:
            suggestions.append("建议补充完整的医疗问题描述")
        
        if complexity < 0.4:
            if len(query.split()) < 3:
                suggestions.append("查询过于简单，建议添加更多描述信息")
            else:
                suggestions.append("查询过于复杂，建议简化表达")
        
        return suggestions
    
    def _has_complete_grammar(self, query: str) -> bool:
        """检查语法完整性"""
        # 简化的语法检查
        return bool(re.search(r'[？?。！!]$', query.strip()) or 
                   any(word in query for word in ['什么', '如何', '怎么', '为什么', '哪些']))
    
    def _has_ambiguity(self, query: str) -> bool:
        """检查是否有歧义"""
        ambiguous_words = ['这个', '那个', '它', '他们', '什么东西']
        return any(word in query for word in ambiguous_words)
    
    def _count_medical_terms(self, query: str) -> int:
        """统计医疗术语数量"""
        count = 0
        for keywords in self.medical_keywords.values():
            count += sum(1 for keyword in keywords if keyword in query)
        return count
    
    def _has_quantifiers(self, query: str) -> bool:
        """检查是否包含数量词或修饰词"""
        quantifiers = ['多少', '几个', '多久', '什么时候', '哪里', '严重', '轻微', '急性', '慢性']
        return any(word in query for word in quantifiers)

# 全局实例
query_quality_assessor = QueryQualityAssessor()