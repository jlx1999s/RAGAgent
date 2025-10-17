"""
优化后检索流程的测试用例
测试意图识别前置、查询质量评估、上下文感知KG增强等功能
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from services.enhanced_rag_service import EnhancedMedicalRAGService
from services.query_quality_assessor import QueryQualityAssessor, QueryQualityLevel
from models.medical_models import Department, DocumentType, DiseaseCategory


class TestOptimizedRetrievalFlow:
    """测试优化后的检索流程"""
    
    @pytest.fixture
    def mock_services(self):
        """创建模拟服务"""
        return {
            'search_service': Mock(),
            'kg_service': Mock(),
            'association_service': Mock(),
            'intent_service': Mock(),
            'index_service': Mock()
        }
    
    @pytest.fixture
    def rag_service(self, mock_services):
        """创建RAG服务实例"""
        service = EnhancedMedicalRAGService(
            search_service=mock_services['search_service'],
            kg_service=mock_services['kg_service'],
            association_service=mock_services['association_service'],
            intent_service=mock_services['intent_service'],
            index_service=mock_services['index_service']
        )
        return service
    
    @pytest.mark.asyncio
    async def test_intent_recognition_first(self, rag_service, mock_services):
        """测试意图识别前置于KG增强"""
        # 模拟意图识别结果
        mock_services['intent_service'].smart_intent_recognition = AsyncMock(return_value={
            'department': Department.CARDIOLOGY,
            'document_type': DocumentType.GUIDELINE,
            'disease_category': DiseaseCategory.CARDIOVASCULAR,
            'confidence': 0.85,
            'method': 'smart'
        })
        
        # 模拟查询质量评估
        with patch.object(rag_service, 'quality_assessor') as mock_assessor:
            mock_quality = Mock()
            mock_quality.overall_score = 0.8
            mock_quality.level = QueryQualityLevel.HIGH
            mock_quality.clarity_score = 0.8
            mock_quality.specificity_score = 0.7
            mock_quality.medical_relevance_score = 0.9
            mock_quality.completeness_score = 0.8
            mock_quality.complexity_score = 0.6
            mock_quality.improvement_suggestions = []
            mock_assessor.assess_query_quality.return_value = mock_quality
            
            # 模拟KG服务
            mock_services['kg_service'].extract_entities_from_text.return_value = []
            mock_services['kg_service'].get_expansion_suggestions.return_value = ['心脏病', '心血管']
            
            # 模拟关联服务
            mock_services['association_service'].find_medical_associations = AsyncMock(return_value=[])
            
            # 模拟搜索结果
            mock_services['index_service'].enhanced_medical_search = AsyncMock(return_value=[
                {
                    'title': '心血管疾病诊疗指南',
                    'content': '心血管疾病的诊断和治疗...',
                    'score': 0.9,
                    'department': 'cardiology',
                    'document_type': 'guideline'
                }
            ])
            
            # 执行检索
            citations, context, metadata = await rag_service.medical_retrieve("心脏病的症状有哪些？")
            
            # 验证调用顺序：意图识别 -> 查询质量评估 -> KG增强 -> 搜索
            mock_services['intent_service'].smart_intent_recognition.assert_called_once()
            mock_assessor.assess_query_quality.assert_called_once()
            
            # 验证元数据包含所有组件的信息
            assert 'intent_recognition' in metadata
            assert 'query_quality' in metadata
            assert 'kg_enhancement' in metadata
            assert metadata['intent_recognition']['department'] == Department.CARDIOLOGY.value
            assert metadata['query_quality']['overall_score'] == 0.8
    
    @pytest.mark.asyncio
    async def test_query_quality_gating(self, rag_service, mock_services):
        """测试查询质量门控机制"""
        # 模拟低质量查询
        mock_services['intent_service'].smart_intent_recognition = AsyncMock(return_value={
            'department': None,
            'document_type': None,
            'disease_category': None,
            'confidence': 0.3,
            'method': 'smart'
        })
        
        with patch.object(rag_service, 'quality_assessor') as mock_assessor:
            # 低质量查询
            mock_quality = Mock()
            mock_quality.overall_score = 0.4  # 低于阈值
            mock_quality.level = QueryQualityLevel.LOW
            mock_quality.clarity_score = 0.3
            mock_quality.specificity_score = 0.4
            mock_quality.medical_relevance_score = 0.5
            mock_quality.completeness_score = 0.3
            mock_quality.complexity_score = 0.2
            mock_quality.improvement_suggestions = ['请提供更具体的症状描述']
            mock_assessor.assess_query_quality.return_value = mock_quality
            
            # 模拟基础搜索
            mock_services['index_service'].enhanced_medical_search = AsyncMock(return_value=[
                {
                    'title': '基础医疗信息',
                    'content': '一般医疗信息...',
                    'score': 0.6
                }
            ])
            
            # 执行检索
            citations, context, metadata = await rag_service.medical_retrieve("什么？")
            
            # 验证KG增强被跳过
            assert metadata['kg_enhancement']['enabled'] == False
            assert '查询质量较低，跳过KG增强' in str(mock_services)  # 检查日志
    
    @pytest.mark.asyncio
    async def test_context_aware_kg_enhancement(self, rag_service, mock_services):
        """测试上下文感知的KG增强"""
        # 模拟高质量查询和明确的意图识别
        mock_services['intent_service'].smart_intent_recognition = AsyncMock(return_value={
            'department': Department.CARDIOLOGY,
            'document_type': DocumentType.GUIDELINE,
            'disease_category': DiseaseCategory.CARDIOVASCULAR,
            'confidence': 0.9,
            'method': 'smart'
        })
        
        with patch.object(rag_service, 'quality_assessor') as mock_assessor:
            # 高质量查询
            mock_quality = Mock()
            mock_quality.overall_score = 0.85
            mock_quality.level = QueryQualityLevel.HIGH
            mock_quality.clarity_score = 0.9
            mock_quality.specificity_score = 0.8
            mock_quality.medical_relevance_score = 0.9
            mock_quality.completeness_score = 0.8
            mock_quality.complexity_score = 0.7
            mock_quality.improvement_suggestions = []
            mock_assessor.assess_query_quality.return_value = mock_quality
            
            # 模拟实体提取
            mock_entity = Mock()
            mock_entity.name = '心脏病'
            mock_entity.entity_type = Mock()
            mock_entity.entity_type.value = '疾病'
            mock_entity.confidence = 0.9
            mock_services['kg_service'].extract_entities_from_text.return_value = [mock_entity]
            
            # 模拟相关实体
            mock_related = Mock()
            mock_related.name = '心律不齐'
            mock_related.entity_type = Mock()
            mock_related.entity_type.value = '症状'
            mock_services['kg_service'].get_related_entities.return_value = [mock_related]
            
            # 模拟上下文感知的扩展建议
            mock_services['kg_service'].get_expansion_suggestions.return_value = [
                '心血管疾病', '心脏功能', '心电图'
            ]
            
            # 模拟关联服务
            mock_services['association_service'].find_medical_associations = AsyncMock(return_value=[])
            
            # 模拟搜索结果
            mock_services['index_service'].enhanced_medical_search = AsyncMock(return_value=[
                {
                    'title': '心血管疾病诊疗指南',
                    'content': '详细的心血管疾病信息...',
                    'score': 0.95,
                    'department': 'cardiology',
                    'document_type': 'guideline'
                }
            ])
            
            # 执行检索
            citations, context, metadata = await rag_service.medical_retrieve("心脏病的主要症状和治疗方法")
            
            # 验证KG增强被启用
            assert metadata['kg_enhancement']['enabled'] == True
            assert len(metadata['kg_enhancement']['entities']) > 0
            assert len(metadata['kg_enhancement']['suggestions']) > 0
            
            # 验证上下文感知的扩展建议被调用
            mock_services['kg_service'].get_expansion_suggestions.assert_called_with(
                '心脏病',
                mock_entity.entity_type,
                context={
                    'department': 'cardiology',
                    'document_type': 'guideline',
                    'disease_category': 'cardiovascular'
                }
            )
    
    @pytest.mark.asyncio
    async def test_retrieval_quality_assessment(self, rag_service, mock_services):
        """测试检索质量评估"""
        # 模拟服务调用
        mock_services['intent_service'].smart_intent_recognition = AsyncMock(return_value={
            'department': Department.INTERNAL_MEDICINE,
            'document_type': DocumentType.RESEARCH,
            'disease_category': DiseaseCategory.INFECTIOUS,
            'confidence': 0.8,
            'method': 'smart'
        })
        
        with patch.object(rag_service, 'quality_assessor') as mock_assessor:
            # 查询质量评估
            mock_query_quality = Mock()
            mock_query_quality.overall_score = 0.75
            mock_query_quality.level = QueryQualityLevel.MEDIUM
            mock_query_quality.clarity_score = 0.8
            mock_query_quality.specificity_score = 0.7
            mock_query_quality.medical_relevance_score = 0.8
            mock_query_quality.completeness_score = 0.7
            mock_query_quality.complexity_score = 0.6
            mock_query_quality.improvement_suggestions = []
            mock_assessor.assess_query_quality.return_value = mock_query_quality
            
            # 检索质量评估
            mock_retrieval_quality = Mock()
            mock_retrieval_quality.relevance_score = 0.85
            mock_retrieval_quality.diversity_score = 0.7
            mock_retrieval_quality.coverage_score = 0.8
            mock_retrieval_quality.confidence_score = 0.9
            mock_assessor.assess_retrieval_quality.return_value = mock_retrieval_quality
            
            # 模拟其他服务
            mock_services['kg_service'].extract_entities_from_text.return_value = []
            mock_services['association_service'].find_medical_associations = AsyncMock(return_value=[])
            
            # 模拟搜索结果
            search_results = [
                {
                    'title': '感染性疾病研究',
                    'content': '感染性疾病的最新研究进展...',
                    'score': 0.9,
                    'department': 'internal_medicine',
                    'document_type': 'research'
                },
                {
                    'title': '抗生素使用指南',
                    'content': '抗生素的合理使用...',
                    'score': 0.8,
                    'department': 'internal_medicine',
                    'document_type': 'guideline'
                }
            ]
            mock_services['index_service'].enhanced_medical_search = AsyncMock(return_value=search_results)
            
            # 执行检索
            citations, context, metadata = await rag_service.medical_retrieve("感染性疾病的治疗原则")
            
            # 验证检索质量评估被调用
            mock_assessor.assess_retrieval_quality.assert_called_once()
            
            # 验证元数据包含检索质量信息
            assert 'retrieval_quality' in metadata
            assert metadata['retrieval_quality']['relevance_score'] == 0.85
            assert metadata['retrieval_quality']['diversity_score'] == 0.7
    
    @pytest.mark.asyncio
    async def test_adaptive_search_parameters(self, rag_service, mock_services):
        """测试自适应搜索参数"""
        # 测试高质量查询的搜索参数
        mock_services['intent_service'].smart_intent_recognition = AsyncMock(return_value={
            'department': Department.SURGERY,
            'document_type': DocumentType.GUIDELINE,
            'disease_category': DiseaseCategory.SURGICAL,
            'confidence': 0.9,
            'method': 'smart'
        })
        
        with patch.object(rag_service, 'quality_assessor') as mock_assessor:
            # 高质量查询
            mock_quality = Mock()
            mock_quality.overall_score = 0.9
            mock_quality.level = QueryQualityLevel.HIGH
            mock_quality.clarity_score = 0.9
            mock_quality.specificity_score = 0.9
            mock_quality.medical_relevance_score = 0.9
            mock_quality.completeness_score = 0.9
            mock_quality.complexity_score = 0.8
            mock_quality.improvement_suggestions = []
            mock_assessor.assess_query_quality.return_value = mock_quality
            
            # 模拟其他服务
            mock_services['kg_service'].extract_entities_from_text.return_value = []
            mock_services['association_service'].find_medical_associations = AsyncMock(return_value=[])
            mock_services['index_service'].enhanced_medical_search = AsyncMock(return_value=[])
            
            # 执行检索
            await rag_service.medical_retrieve("外科手术的标准操作流程")
            
            # 验证搜索参数根据查询质量调整
            call_args = mock_services['index_service'].enhanced_medical_search.call_args
            assert call_args[1]['k'] >= 8  # 高质量查询使用更多结果
    
    def test_query_quality_assessor_integration(self):
        """测试查询质量评估器的集成"""
        assessor = QueryQualityAssessor()
        
        # 测试高质量查询
        high_quality_query = "请详细说明急性心肌梗死的诊断标准、治疗方案和预后评估"
        quality = assessor.assess_query_quality(high_quality_query)
        
        assert quality.overall_score > 0.7
        assert quality.level in [QueryQualityLevel.HIGH, QueryQualityLevel.MEDIUM]
        assert quality.medical_relevance_score > 0.8
        
        # 测试低质量查询
        low_quality_query = "什么？"
        quality = assessor.assess_query_quality(low_quality_query)
        
        assert quality.overall_score < 0.5
        assert quality.level == QueryQualityLevel.LOW
        assert len(quality.improvement_suggestions) > 0


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])