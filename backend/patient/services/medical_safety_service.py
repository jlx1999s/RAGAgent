"""
医疗问答质量评估和安全审核机制
确保医疗AI系统的安全性、准确性和合规性
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class SafetyLevel(Enum):
    """安全等级"""
    SAFE = "safe"                    # 安全
    CAUTION = "caution"             # 需要谨慎
    WARNING = "warning"             # 警告
    DANGEROUS = "dangerous"         # 危险
    BLOCKED = "blocked"             # 阻止

class QualityLevel(Enum):
    """质量等级"""
    HIGH = "high"                   # 高质量
    MEDIUM = "medium"               # 中等质量
    LOW = "low"                     # 低质量
    UNRELIABLE = "unreliable"       # 不可靠

@dataclass
class SafetyAssessment:
    """安全评估结果"""
    level: SafetyLevel
    score: float  # 0-1之间，越高越安全
    issues: List[str]  # 发现的问题
    recommendations: List[str]  # 建议
    blocked_reasons: List[str]  # 阻止原因（如果被阻止）

@dataclass
class QualityAssessment:
    """质量评估结果"""
    level: QualityLevel
    score: float  # 0-1之间，越高质量越好
    metrics: Dict[str, float]  # 各项质量指标
    issues: List[str]  # 质量问题
    suggestions: List[str]  # 改进建议

@dataclass
class MedicalReviewResult:
    """医疗审核结果"""
    query: str
    response: str
    safety: SafetyAssessment
    quality: QualityAssessment
    overall_approved: bool
    review_timestamp: str
    reviewer_id: str = "system"

class MedicalSafetyChecker:
    """医疗安全检查器"""
    
    def __init__(self):
        # 危险关键词列表
        self.dangerous_keywords = [
            "自杀", "自残", "自我伤害", "结束生命",
            "毒药", "致命剂量", "过量服用",
            "非法药物", "毒品", "成瘾药物",
            "未经批准的治疗", "实验性药物",
            "替代医学", "偏方", "秘方"
        ]
        
        # 需要谨慎处理的关键词
        self.caution_keywords = [
            "手术", "开刀", "切除", "移植",
            "化疗", "放疗", "靶向治疗",
            "激素", "类固醇", "免疫抑制剂",
            "精神药物", "抗抑郁", "镇静剂",
            "怀孕", "妊娠", "哺乳期", "儿童用药"
        ]
        
        # 禁止的医疗建议模式
        self.forbidden_patterns = [
            r"建议您?立即?停止?服用",
            r"不要?去?医院",
            r"这个?药物?没有?副作用",
            r"可以?随意?增加?剂量",
            r"不需要?医生?处方",
            r"在家?自己?治疗?就行",
            r"这种?病?不用?治疗"
        ]
        
        # 必须包含的免责声明关键词
        self.required_disclaimers = [
            "建议咨询医生", "请就医", "医生指导", "专业医疗建议",
            "仅供参考", "不能替代", "医疗诊断"
        ]
    
    def assess_safety(self, query: str, response: str) -> SafetyAssessment:
        """评估医疗问答的安全性"""
        issues = []
        recommendations = []
        blocked_reasons = []
        score = 1.0
        
        # 检查危险关键词
        dangerous_found = []
        for keyword in self.dangerous_keywords:
            if keyword in query or keyword in response:
                dangerous_found.append(keyword)
        
        if dangerous_found:
            score -= 0.5
            issues.append(f"包含危险关键词: {', '.join(dangerous_found)}")
            blocked_reasons.append("涉及危险医疗内容")
        
        # 检查谨慎关键词
        caution_found = []
        for keyword in self.caution_keywords:
            if keyword in query or keyword in response:
                caution_found.append(keyword)
        
        if caution_found:
            score -= 0.2
            issues.append(f"包含需要谨慎处理的关键词: {', '.join(caution_found)}")
            recommendations.append("需要强调专业医疗指导的重要性")
        
        # 检查禁止的医疗建议模式
        forbidden_found = []
        for pattern in self.forbidden_patterns:
            if re.search(pattern, response):
                forbidden_found.append(pattern)
        
        if forbidden_found:
            score -= 0.6
            issues.append("包含禁止的医疗建议模式")
            blocked_reasons.append("提供了不当的医疗建议")
        
        # 检查是否包含必要的免责声明
        disclaimer_found = any(
            disclaimer in response for disclaimer in self.required_disclaimers
        )
        
        if not disclaimer_found and (caution_found or dangerous_found):
            score -= 0.3
            issues.append("缺少必要的免责声明")
            recommendations.append("应添加建议咨询专业医生的声明")
        
        # 检查是否提供具体药物剂量
        if re.search(r'\d+\s*(mg|ml|片|粒|毫升|毫克)', response):
            score -= 0.4
            issues.append("提供了具体的药物剂量信息")
            recommendations.append("不应提供具体剂量，应建议咨询医生")
        
        # 确定安全等级
        if blocked_reasons:
            level = SafetyLevel.BLOCKED
        elif score < 0.3:
            level = SafetyLevel.DANGEROUS
        elif score < 0.5:
            level = SafetyLevel.WARNING
        elif score < 0.7:
            level = SafetyLevel.CAUTION
        else:
            level = SafetyLevel.SAFE
        
        return SafetyAssessment(
            level=level,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations,
            blocked_reasons=blocked_reasons
        )

class MedicalQualityAssessor:
    """医疗质量评估器"""
    
    def __init__(self):
        # 质量指标权重
        self.quality_weights = {
            "accuracy": 0.3,      # 准确性
            "completeness": 0.2,  # 完整性
            "clarity": 0.2,       # 清晰度
            "relevance": 0.15,    # 相关性
            "evidence": 0.15      # 证据支持
        }
        
        # 医学术语词典（简化版）
        self.medical_terms = {
            "症状", "诊断", "治疗", "药物", "副作用", "禁忌症",
            "适应症", "病理", "生理", "解剖", "临床", "病史",
            "检查", "化验", "影像", "手术", "康复", "预防"
        }
    
    def assess_quality(self, query: str, response: str, 
                      retrieved_docs: Optional[List[Dict]] = None) -> QualityAssessment:
        """评估医疗问答的质量"""
        metrics = {}
        issues = []
        suggestions = []
        
        # 1. 准确性评估（基于医学术语使用）
        accuracy_score = self._assess_accuracy(response)
        metrics["accuracy"] = accuracy_score
        
        if accuracy_score < 0.6:
            issues.append("医学术语使用不够准确或专业")
            suggestions.append("增加更多专业医学术语的使用")
        
        # 2. 完整性评估
        completeness_score = self._assess_completeness(query, response)
        metrics["completeness"] = completeness_score
        
        if completeness_score < 0.6:
            issues.append("回答不够完整，可能遗漏重要信息")
            suggestions.append("提供更全面的信息覆盖")
        
        # 3. 清晰度评估
        clarity_score = self._assess_clarity(response)
        metrics["clarity"] = clarity_score
        
        if clarity_score < 0.6:
            issues.append("表达不够清晰，可能难以理解")
            suggestions.append("使用更简洁明了的表达方式")
        
        # 4. 相关性评估
        relevance_score = self._assess_relevance(query, response)
        metrics["relevance"] = relevance_score
        
        if relevance_score < 0.6:
            issues.append("回答与问题的相关性不够高")
            suggestions.append("更直接地回答用户的具体问题")
        
        # 5. 证据支持评估
        evidence_score = self._assess_evidence(response, retrieved_docs)
        metrics["evidence"] = evidence_score
        
        if evidence_score < 0.6:
            issues.append("缺乏足够的证据支持")
            suggestions.append("引用更多可靠的医学文献或指南")
        
        # 计算总体质量分数
        total_score = sum(
            metrics[metric] * self.quality_weights[metric]
            for metric in metrics
        )
        
        # 确定质量等级
        if total_score >= 0.8:
            level = QualityLevel.HIGH
        elif total_score >= 0.6:
            level = QualityLevel.MEDIUM
        elif total_score >= 0.4:
            level = QualityLevel.LOW
        else:
            level = QualityLevel.UNRELIABLE
        
        return QualityAssessment(
            level=level,
            score=total_score,
            metrics=metrics,
            issues=issues,
            suggestions=suggestions
        )
    
    def _assess_accuracy(self, response: str) -> float:
        """评估准确性"""
        # 检查医学术语的使用
        medical_term_count = sum(
            1 for term in self.medical_terms 
            if term in response
        )
        
        # 基于医学术语密度评估
        words = len(response.split())
        if words == 0:
            return 0.0
        
        term_density = medical_term_count / words
        accuracy_score = min(1.0, term_density * 10)  # 调整系数
        
        # 检查是否有明显错误的表述
        error_patterns = [
            r"100%\s*治愈", r"完全\s*没有\s*副作用", r"绝对\s*安全",
            r"立即\s*见效", r"永远\s*不会\s*复发"
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, response):
                accuracy_score -= 0.3
        
        return max(0.0, accuracy_score)
    
    def _assess_completeness(self, query: str, response: str) -> float:
        """评估完整性"""
        # 基于回答长度和问题复杂度
        query_words = len(query.split())
        response_words = len(response.split())
        
        if response_words == 0:
            return 0.0
        
        # 期望的回答长度比例
        expected_ratio = min(5.0, max(2.0, query_words * 0.5))
        actual_ratio = response_words / query_words
        
        completeness_score = min(1.0, actual_ratio / expected_ratio)
        
        # 检查是否涵盖了关键方面
        key_aspects = ["症状", "原因", "治疗", "预防", "注意事项"]
        covered_aspects = sum(1 for aspect in key_aspects if aspect in response)
        
        aspect_coverage = covered_aspects / len(key_aspects)
        
        return (completeness_score + aspect_coverage) / 2
    
    def _assess_clarity(self, response: str) -> float:
        """评估清晰度"""
        if not response:
            return 0.0
        
        # 检查句子长度分布
        sentences = re.split(r'[。！？]', response)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return 0.0
        
        avg_sentence_length = sum(len(s) for s in sentences) / len(sentences)
        
        # 理想句子长度为15-30字符
        if 15 <= avg_sentence_length <= 30:
            length_score = 1.0
        elif avg_sentence_length < 15:
            length_score = avg_sentence_length / 15
        else:
            length_score = max(0.3, 30 / avg_sentence_length)
        
        # 检查结构化程度
        structure_indicators = ["首先", "其次", "然后", "最后", "另外", "此外"]
        structure_score = min(1.0, sum(1 for indicator in structure_indicators if indicator in response) * 0.2)
        
        return (length_score + structure_score) / 2
    
    def _assess_relevance(self, query: str, response: str) -> float:
        """评估相关性"""
        if not query or not response:
            return 0.0
        
        # 提取查询中的关键词
        query_words = set(re.findall(r'\w+', query.lower()))
        response_words = set(re.findall(r'\w+', response.lower()))
        
        if not query_words:
            return 0.0
        
        # 计算词汇重叠度
        overlap = len(query_words & response_words)
        relevance_score = overlap / len(query_words)
        
        return min(1.0, relevance_score)
    
    def _assess_evidence(self, response: str, retrieved_docs: Optional[List[Dict]] = None) -> float:
        """评估证据支持"""
        evidence_score = 0.0
        
        # 检查是否引用了文献或指南
        citation_patterns = [
            r"根据.*指南", r"研究表明", r"临床试验", r"文献报告",
            r"专家建议", r"医学研究", r"循证医学"
        ]
        
        for pattern in citation_patterns:
            if re.search(pattern, response):
                evidence_score += 0.2
        
        # 如果有检索到的文档，检查引用情况
        if retrieved_docs:
            # 简单检查是否使用了检索到的信息
            evidence_score += 0.3
        
        # 检查是否有数据支持
        if re.search(r'\d+%|\d+/\d+|统计|数据', response):
            evidence_score += 0.2
        
        return min(1.0, evidence_score)

class MedicalReviewService:
    """医疗审核服务"""
    
    def __init__(self):
        self.safety_checker = MedicalSafetyChecker()
        self.quality_assessor = MedicalQualityAssessor()
        self.review_history = []
    
    def review_medical_qa(self, 
                         query: str, 
                         response: str,
                         retrieved_docs: Optional[List[Dict]] = None,
                         reviewer_id: str = "system") -> MedicalReviewResult:
        """全面审核医疗问答"""
        
        # 安全性评估
        safety_assessment = self.safety_checker.assess_safety(query, response)
        
        # 质量评估
        quality_assessment = self.quality_assessor.assess_quality(
            query, response, retrieved_docs
        )
        
        # 综合判断是否批准
        overall_approved = (
            safety_assessment.level != SafetyLevel.BLOCKED and
            safety_assessment.level != SafetyLevel.DANGEROUS and
            quality_assessment.level != QualityLevel.UNRELIABLE
        )
        
        # 创建审核结果
        review_result = MedicalReviewResult(
            query=query,
            response=response,
            safety=safety_assessment,
            quality=quality_assessment,
            overall_approved=overall_approved,
            review_timestamp=datetime.now().isoformat(),
            reviewer_id=reviewer_id
        )
        
        # 记录审核历史
        self.review_history.append(review_result)
        
        # 记录日志
        logger.info(f"医疗问答审核完成 - 安全等级: {safety_assessment.level.value}, "
                   f"质量等级: {quality_assessment.level.value}, "
                   f"是否批准: {overall_approved}")
        
        return review_result
    
    def get_review_statistics(self) -> Dict[str, Any]:
        """获取审核统计信息"""
        if not self.review_history:
            return {"total_reviews": 0}
        
        total_reviews = len(self.review_history)
        approved_count = sum(1 for review in self.review_history if review.overall_approved)
        
        safety_levels = {}
        quality_levels = {}
        
        for review in self.review_history:
            safety_level = review.safety.level.value
            quality_level = review.quality.level.value
            
            safety_levels[safety_level] = safety_levels.get(safety_level, 0) + 1
            quality_levels[quality_level] = quality_levels.get(quality_level, 0) + 1
        
        return {
            "total_reviews": total_reviews,
            "approved_count": approved_count,
            "approval_rate": approved_count / total_reviews,
            "safety_distribution": safety_levels,
            "quality_distribution": quality_levels,
            "avg_safety_score": sum(r.safety.score for r in self.review_history) / total_reviews,
            "avg_quality_score": sum(r.quality.score for r in self.review_history) / total_reviews
        }
    
    def export_review_report(self, file_path: str):
        """导出审核报告"""
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "statistics": self.get_review_statistics(),
            "reviews": [asdict(review) for review in self.review_history]
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"审核报告已导出到: {file_path}")

# 全局实例
medical_review_service = MedicalReviewService()

def review_medical_response(query: str, 
                          response: str, 
                          retrieved_docs: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """审核医疗回答的便捷函数"""
    review_result = medical_review_service.review_medical_qa(
        query=query,
        response=response,
        retrieved_docs=retrieved_docs
    )
    
    return {
        "approved": review_result.overall_approved,
        "safety_level": review_result.safety.level.value,
        "safety_score": review_result.safety.score,
        "quality_level": review_result.quality.level.value,
        "quality_score": review_result.quality.score,
        "issues": review_result.safety.issues + review_result.quality.issues,
        "recommendations": review_result.safety.recommendations + review_result.quality.suggestions,
        "blocked_reasons": review_result.safety.blocked_reasons
    }