"""
手动测试优化后的检索流程
通过输入输出验证意图识别前置、查询质量评估、上下文感知KG增强等功能
"""

import asyncio
import json
from services.enhanced_rag_service import EnhancedMedicalRAGService
from services.query_quality_assessor import QueryQualityAssessor


async def test_optimized_retrieval():
    """手动测试优化后的检索流程"""
    
    print("=" * 80)
    print("优化后检索流程测试")
    print("=" * 80)
    
    # 初始化服务
    try:
        rag_service = EnhancedMedicalRAGService()
        quality_assessor = QueryQualityAssessor()
        print("✅ 服务初始化成功")
    except Exception as e:
        print(f"❌ 服务初始化失败: {e}")
        return
    
    # 测试用例
    test_queries = [
        {
            "query": "心脏病的主要症状和治疗方法是什么？",
            "description": "高质量医疗查询 - 应该触发完整的增强流程"
        },
        {
            "query": "糖尿病",
            "description": "中等质量查询 - 缺乏具体性"
        },
        {
            "query": "什么？",
            "description": "低质量查询 - 应该跳过KG增强"
        },
        {
            "query": "急性心肌梗死的诊断标准、治疗方案和预后评估",
            "description": "高质量专业查询 - 应该获得最佳增强效果"
        }
    ]
    
    for i, test_case in enumerate(test_queries, 1):
        print(f"\n{'='*60}")
        print(f"测试用例 {i}: {test_case['description']}")
        print(f"查询: {test_case['query']}")
        print(f"{'='*60}")
        
        # 1. 测试查询质量评估
        print("\n1️⃣ 查询质量评估:")
        try:
            quality = quality_assessor.assess_query_quality(test_case['query'])
            print(f"   总体分数: {quality.overall_score:.3f}")
            print(f"   质量等级: {quality.quality_level.value}")
            print(f"   清晰度: {quality.clarity_score:.3f}")
            print(f"   具体性: {quality.specificity_score:.3f}")
            print(f"   医疗相关性: {quality.medical_relevance:.3f}")
            print(f"   完整性: {quality.completeness_score:.3f}")
            print(f"   复杂度: {quality.complexity_score:.3f}")
            
            if quality.suggestions:
                print(f"   改进建议: {', '.join(quality.suggestions)}")
            
        except Exception as e:
            print(f"   ❌ 查询质量评估失败: {e}")
        
        # 2. 测试完整的检索流程
        print("\n2️⃣ 完整检索流程:")
        try:
            citations, context, metadata = await rag_service.medical_retrieve(test_case['query'])
            
            print(f"   检索结果数量: {len(citations)}")
            print(f"   上下文长度: {len(context)} 字符")
            
            # 显示意图识别结果
            if 'intent_recognition' in metadata:
                intent = metadata['intent_recognition']
                print(f"   意图识别:")
                print(f"     科室: {intent.get('department', 'None')}")
                print(f"     文档类型: {intent.get('document_type', 'None')}")
                print(f"     疾病分类: {intent.get('disease_category', 'None')}")
                print(f"     置信度: {intent.get('confidence', 0):.3f}")
            
            # 显示查询质量信息
            if 'query_quality' in metadata:
                quality_info = metadata['query_quality']
                print(f"   查询质量: {quality_info.get('overall_score', 0):.3f} ({quality_info.get('level', 'Unknown')})")
            
            # 显示KG增强信息
            if 'kg_enhancement' in metadata:
                kg_info = metadata['kg_enhancement']
                print(f"   KG增强: {'启用' if kg_info.get('enabled', False) else '跳过'}")
                if kg_info.get('enabled', False):
                    print(f"     实体数量: {len(kg_info.get('entities', []))}")
                    print(f"     关系数量: {len(kg_info.get('relations', []))}")
                    print(f"     扩展建议: {len(kg_info.get('suggestions', []))}")
            
            # 显示检索质量
            if 'retrieval_quality' in metadata and metadata['retrieval_quality']:
                retrieval_info = metadata['retrieval_quality']
                print(f"   检索质量:")
                print(f"     相关性: {retrieval_info.get('relevance_score', 0):.3f}")
                print(f"     多样性: {retrieval_info.get('diversity_score', 0):.3f}")
                print(f"     覆盖度: {retrieval_info.get('coverage_score', 0):.3f}")
                print(f"     置信度: {retrieval_info.get('confidence_score', 0):.3f}")
            
            # 显示搜索元数据
            if 'search_metadata' in metadata:
                search_info = metadata['search_metadata']
                print(f"   搜索统计:")
                print(f"     平均分数: {search_info.get('avg_score', 0):.3f}")
                print(f"     最高分数: {search_info.get('max_score', 0):.3f}")
                print(f"     科室分布: {search_info.get('departments', [])}")
                print(f"     文档类型: {search_info.get('document_types', [])}")
            
            # 显示前3个引用
            if citations:
                print(f"   前3个引用:")
                for j, citation in enumerate(citations[:3], 1):
                    print(f"     {j}. {citation.get('title', 'Unknown')} (分数: {citation.get('score', 0):.3f})")
            
        except Exception as e:
            print(f"   ❌ 检索流程失败: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*80}")
    print("测试完成")
    print(f"{'='*80}")


def test_query_quality_only():
    """仅测试查询质量评估功能"""
    
    print("=" * 60)
    print("查询质量评估测试")
    print("=" * 60)
    
    assessor = QueryQualityAssessor()
    
    test_queries = [
        "心脏病的症状",
        "请详细说明急性心肌梗死的诊断标准、治疗方案和预后评估",
        "什么？",
        "糖尿病",
        "高血压患者应该注意什么饮食禁忌和生活方式调整？",
        "感冒",
        "儿童发热的处理原则和退热药物的使用方法"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. 查询: {query}")
        try:
            quality = assessor.assess_query_quality(query)
            print(f"   总体分数: {quality.overall_score:.3f} ({quality.quality_level.value})")
            print(f"   详细分数: 清晰度={quality.clarity_score:.2f}, "
                  f"具体性={quality.specificity_score:.2f}, "
                  f"医疗相关性={quality.medical_relevance:.2f}")
            
            if quality.suggestions:
                print(f"   建议: {', '.join(quality.suggestions[:2])}")
                
        except Exception as e:
            print(f"   ❌ 评估失败: {e}")


if __name__ == "__main__":
    print("选择测试模式:")
    print("1. 完整检索流程测试")
    print("2. 仅查询质量评估测试")
    
    choice = input("请输入选择 (1 或 2): ").strip()
    
    if choice == "1":
        asyncio.run(test_optimized_retrieval())
    elif choice == "2":
        test_query_quality_only()
    else:
        print("无效选择，运行查询质量评估测试...")
        test_query_quality_only()