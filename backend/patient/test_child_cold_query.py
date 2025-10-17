#!/usr/bin/env python3
"""
测试"小孩子感冒怎么办"查询的检索流程
分析为什么没有返回相关知识库内容
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.enhanced_rag_service import EnhancedMedicalRAGService
from services.enhanced_index_service import EnhancedMedicalIndexService
from services.medical_intent_service import MedicalIntentRecognizer
from services.query_quality_assessor import QueryQualityAssessor
from services.medical_knowledge_graph import MedicalKnowledgeGraphService
from services.medical_association_service import MedicalAssociationService
from services.cache_service import CacheService
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_child_cold_query():
    """测试儿童感冒查询的完整流程"""
    
    print("🔍 测试查询: '小孩子感冒怎么办'")
    print("=" * 80)
    
    # 初始化服务
    cache_service = CacheService()
    index_service = EnhancedMedicalIndexService()
    intent_service = MedicalIntentRecognizer()
    quality_assessor = QueryQualityAssessor()
    kg_service = MedicalKnowledgeGraphService()
    association_service = MedicalAssociationService()
    
    # 初始化RAG服务（无需传入参数）
    rag_service = EnhancedMedicalRAGService()
    
    query = "小孩子感冒怎么办"
    
    try:
        print("📋 步骤1: 意图识别")
        print("-" * 40)
        intent_result = intent_service.recognize_intent(query)
        print(f"科室: {intent_result.department}")
        print(f"文档类型: {intent_result.document_type}")
        print(f"疾病类别: {intent_result.disease_category}")
        print(f"置信度: {intent_result.confidence:.3f}")
        print(f"关键词: {intent_result.keywords}")
        print(f"推理过程: {intent_result.reasoning}")
        print()
        
        print("📊 步骤2: 查询质量评估")
        print("-" * 40)
        quality_result = quality_assessor.assess_query_quality(query)
        print(f"总体质量分数: {quality_result.overall_score:.3f}")
        print(f"质量等级: {quality_result.quality_level.value}")
        print(f"清晰度: {quality_result.clarity_score:.3f}")
        print(f"具体性: {quality_result.specificity_score:.3f}")
        print(f"医疗相关性: {quality_result.medical_relevance:.3f}")
        print(f"完整性: {quality_result.completeness_score:.3f}")
        print(f"复杂性: {quality_result.complexity_score:.3f}")
        print(f"改进建议: {', '.join(quality_result.suggestions)}")
        print()
        
        print("🔍 步骤3: 向量搜索")
        print("-" * 40)
        search_results = index_service.search_medical_documents(
            query=query,
            department=intent_result.department,
            document_type=intent_result.document_type,
            disease_category=intent_result.disease_category,
            k=5
        )
        if search_results.get('ok') and search_results.get('results'):
            results_list = search_results['results']
            print(f"检索到 {len(results_list)} 个文档片段")
            for i, result in enumerate(results_list[:3]):  # 显示前3个结果
                print(f"\n📄 结果 {i+1}:")
                print(f"相关度分数: {result['score']:.3f}")
                print(f"科室: {result.get('department', 'N/A')}")
                print(f"文档类型: {result.get('document_type', 'N/A')}")
                print(f"疾病类别: {result.get('disease_category', 'N/A')}")
                print(f"内容预览: {result['text'][:200]}...")
                if result.get('medical_entities'):
                    print(f"医疗实体: {result['medical_entities'][:5]}")  # 显示前5个实体
        else:
            print("❌ 向量搜索失败或无结果")
            print(f"搜索结果: {search_results}")
        print()
        
        print("🧠 步骤4: 完整RAG检索")
        print("-" * 40)
        citations, context_text, metadata = await rag_service.medical_retrieve(query)
        
        print(f"引用数量: {len(citations)}")
        print(f"上下文长度: {len(context_text)} 字符")
        
        if citations:
            print("\n📚 引用详情:")
            for citation in citations:
                print(f"  引用ID: {citation.get('citation_id')}")
                print(f"  排名: {citation.get('rank')}")
                print(f"  分数: {citation.get('score', 0):.4f}")
                print(f"  科室: {citation.get('department', '未知')}")
                print(f"  文档类型: {citation.get('document_type', '未知')}")
                print(f"  内容: {citation.get('snippet', '')[:150]}...")
                print()
        else:
            print("❌ 没有生成引用")
            
        print(f"\n📈 元数据信息:")
        print(f"  总结果数: {metadata.get('total_results', 0)}")
        print(f"  科室列表: {metadata.get('departments', [])}")
        print(f"  文档类型: {metadata.get('document_types', [])}")
        print(f"  证据等级: {metadata.get('evidence_levels', [])}")
        
        # 检查KG增强和医疗关联
        kg_info = metadata.get('kg_enhancement', {})
        print(f"  KG增强启用: {kg_info.get('enabled', False)}")
        print(f"  KG实体: {len(kg_info.get('entities', []))}")
        print(f"  KG关系: {len(kg_info.get('relations', []))}")
        
        assoc_info = metadata.get('medical_associations', [])
        print(f"  医疗关联数: {len(assoc_info)}")
        
        return {
            'intent_result': intent_result,
            'quality_result': quality_result,
            'search_results': search_results,
            'citations': citations,
            'context_text': context_text,
            'metadata': metadata
        }
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """主函数"""
    print("🏥 儿童感冒查询诊断测试")
    print("=" * 80)
    
    result = await test_child_cold_query()
    
    if result:
        print("\n" + "=" * 80)
        print("📋 诊断总结")
        print("=" * 80)
        
        # 分析问题
        issues = []
        
        # 检查意图识别
        intent = result['intent_result']
        if not intent.department or intent.department == '未识别':
            issues.append("❌ 意图识别未能正确识别科室")
        else:
            print(f"✅ 意图识别成功: {intent.department}")
            
        # 检查查询质量
        quality = result['quality_result']
        if quality.overall_score < 0.5:
            issues.append(f"⚠️ 查询质量较低: {quality.overall_score:.3f}")
        else:
            print(f"✅ 查询质量良好: {quality.overall_score:.3f}")
            
        # 检查搜索结果
        search = result['search_results']
        if not search.get('ok') or not search.get('results'):
            issues.append("❌ 向量搜索未返回结果")
        else:
            print(f"✅ 向量搜索成功: {len(search.get('results', []))} 个结果")
            
        # 检查最终结果
        if not result['citations']:
            issues.append("❌ 最终未生成引用和上下文")
        else:
            print(f"✅ 成功生成 {len(result['citations'])} 个引用")
            
        if issues:
            print("\n🔧 发现的问题:")
            for issue in issues:
                print(f"  {issue}")
                
            print("\n💡 可能的解决方案:")
            print("  1. 检查知识库中是否有儿科感冒相关文档")
            print("  2. 优化意图识别的儿科关键词匹配")
            print("  3. 调整向量搜索的相似度阈值")
            print("  4. 增加儿科感冒相关的同义词和关键词")
            print("  5. 检查文档预处理和向量化是否正确")
        else:
            print("\n🎉 所有检查通过！")

if __name__ == "__main__":
    asyncio.run(main())