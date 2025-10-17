#!/usr/bin/env python3
"""
最终集成测试 - 验证所有优化功能
包括缓存机制、并行处理、动态权重调整、KG增强和医疗关联增强
"""

import asyncio
import time
import logging
from services.enhanced_rag_service import enhanced_rag_service
from services.cache_service import cache_service

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_comprehensive_functionality():
    """全面功能测试"""
    print("=" * 80)
    print("🔬 最终集成测试 - 全面功能验证")
    print("=" * 80)
    
    # 清空缓存，确保测试的准确性
    cache_service.clear()
    print("🧹 缓存已清空")
    
    # 测试用例 - 涵盖不同类型的医疗查询
    test_cases = [
        {
            "query": "糖尿病的诊断标准和治疗方案",
            "expected_department": "内科",
            "description": "内分泌疾病查询"
        },
        {
            "query": "高血压患者的用药指导和注意事项",
            "expected_department": "心血管科",
            "description": "心血管疾病查询"
        },
        {
            "query": "儿童发热的处理原则",
            "expected_department": "儿科", 
            "description": "儿科疾病查询"
        },
        {
            "query": "骨折后的康复训练方法",
            "expected_department": "骨科",
            "description": "骨科疾病查询"
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n【测试 {i}】{test_case['description']}")
        print(f"查询: {test_case['query']}")
        print("-" * 60)
        
        start_time = time.time()
        
        try:
            # 执行检索
            citations, context, metadata = await enhanced_rag_service.medical_retrieve(
                question=test_case['query'],
                session_id=f"integration_test_{i}"
            )
            
            execution_time = time.time() - start_time
            
            # 验证结果
            intent_info = metadata.get('intent_recognition', {})
            query_quality = metadata.get('query_quality', {})
            kg_enhancement = metadata.get('kg_enhancement', {})
            
            result = {
                "test_case": i,
                "query": test_case['query'],
                "execution_time": execution_time,
                "citations_count": len(citations),
                "detected_department": intent_info.get('department'),
                "expected_department": test_case['expected_department'],
                "query_quality_score": query_quality.get('overall_score', 0),
                "query_quality_level": query_quality.get('level'),
                "kg_enabled": kg_enhancement.get('enabled', False),
                "kg_entities_count": len(kg_enhancement.get('entities', [])),
                "kg_suggestions_count": len(kg_enhancement.get('suggestions', [])),
                "medical_associations_count": len(metadata.get('medical_associations', [])),
                "dynamic_weights": metadata.get('dynamic_weights', {}),
                "success": True
            }
            
            results.append(result)
            
            # 打印结果
            print(f"✅ 执行成功 - 耗时: {execution_time:.2f}秒")
            print(f"📄 检索文档数: {len(citations)}")
            print(f"🎯 意图识别: {intent_info.get('department', '未识别')} (期望: {test_case['expected_department']})")
            print(f"📊 查询质量: {query_quality.get('overall_score', 0):.3f} ({query_quality.get('level', '未知')})")
            print(f"🧠 KG增强: {'启用' if kg_enhancement.get('enabled') else '未启用'}")
            if kg_enhancement.get('enabled'):
                print(f"   - 实体: {len(kg_enhancement.get('entities', []))}个")
                print(f"   - 建议: {len(kg_enhancement.get('suggestions', []))}个")
            print(f"🔗 医疗关联: {len(metadata.get('medical_associations', []))}个")
            
            # 显示动态权重
            weights = metadata.get('dynamic_weights', {})
            if weights:
                print("⚖️ 动态权重:")
                for key, value in weights.items():
                    print(f"   - {key}: {value:.3f}")
            
        except Exception as e:
            print(f"❌ 执行失败: {str(e)}")
            results.append({
                "test_case": i,
                "query": test_case['query'],
                "error": str(e),
                "success": False
            })
    
    return results

async def test_caching_performance():
    """缓存性能测试"""
    print(f"\n{'='*80}")
    print("🚀 缓存性能测试")
    print("=" * 80)
    
    test_query = "高血压的诊断标准"
    
    # 第一次查询（无缓存）
    print("\n🔍 第一次查询（无缓存）...")
    start_time = time.time()
    citations1, context1, metadata1 = await enhanced_rag_service.medical_retrieve(
        question=test_query,
        session_id="cache_test_1"
    )
    first_query_time = time.time() - start_time
    
    # 第二次查询（有缓存）
    print("🔍 第二次查询（有缓存）...")
    start_time = time.time()
    citations2, context2, metadata2 = await enhanced_rag_service.medical_retrieve(
        question=test_query,
        session_id="cache_test_2"
    )
    second_query_time = time.time() - start_time
    
    # 计算性能提升
    if first_query_time > 0:
        performance_improvement = ((first_query_time - second_query_time) / first_query_time) * 100
    else:
        performance_improvement = 0
    
    print(f"\n📊 缓存性能结果:")
    print(f"   - 第一次查询: {first_query_time:.2f}秒")
    print(f"   - 第二次查询: {second_query_time:.2f}秒")
    print(f"   - 性能提升: {performance_improvement:.1f}%")
    
    return {
        "first_query_time": first_query_time,
        "second_query_time": second_query_time,
        "performance_improvement": performance_improvement
    }

async def test_parallel_processing():
    """并行处理测试"""
    print(f"\n{'='*80}")
    print("⚡ 并行处理测试")
    print("=" * 80)
    
    queries = [
        "糖尿病并发症预防",
        "心脏病早期症状",
        "儿童疫苗接种时间表"
    ]
    
    # 串行处理
    print("\n🔄 串行处理测试...")
    start_time = time.time()
    serial_results = []
    for i, query in enumerate(queries):
        result = await enhanced_rag_service.medical_retrieve(
            question=query,
            session_id=f"serial_test_{i}"
        )
        serial_results.append(result)
    serial_time = time.time() - start_time
    
    # 清空缓存
    cache_service.clear()
    
    # 并行处理
    print("⚡ 并行处理测试...")
    start_time = time.time()
    
    async def process_query(query, session_id):
        return await enhanced_rag_service.medical_retrieve(
            question=query,
            session_id=session_id
        )
    
    tasks = [
        process_query(query, f"parallel_test_{i}")
        for i, query in enumerate(queries)
    ]
    
    parallel_results = await asyncio.gather(*tasks)
    parallel_time = time.time() - start_time
    
    # 计算性能提升
    if serial_time > 0:
        performance_improvement = ((serial_time - parallel_time) / serial_time) * 100
    else:
        performance_improvement = 0
    
    print(f"\n📊 并行处理结果:")
    print(f"   - 串行处理: {serial_time:.2f}秒")
    print(f"   - 并行处理: {parallel_time:.2f}秒")
    print(f"   - 性能提升: {performance_improvement:.1f}%")
    
    return {
        "serial_time": serial_time,
        "parallel_time": parallel_time,
        "performance_improvement": performance_improvement
    }

def print_cache_statistics():
    """打印缓存统计信息"""
    print(f"\n{'='*80}")
    print("📈 缓存统计信息")
    print("=" * 80)
    
    stats = cache_service.get_stats()
    print(f"总缓存条目: {stats['total_entries']}")
    print(f"过期条目: {stats['expired_count']}")
    print(f"最大容量: {stats['max_size']}")
    
    if stats['type_stats']:
        print("\n按类型分类:")
        for cache_type, type_info in stats['type_stats'].items():
            print(f"   - {cache_type}: {type_info['count']}个条目, {type_info['total_access']}次访问")

async def main():
    """主测试函数"""
    print("🚀 开始最终集成测试...")
    
    # 1. 全面功能测试
    functionality_results = await test_comprehensive_functionality()
    
    # 2. 缓存性能测试
    cache_results = await test_caching_performance()
    
    # 3. 并行处理测试
    parallel_results = await test_parallel_processing()
    
    # 4. 打印缓存统计
    print_cache_statistics()
    
    # 5. 生成测试报告
    print(f"\n{'='*80}")
    print("📋 测试报告总结")
    print("=" * 80)
    
    # 功能测试总结
    successful_tests = sum(1 for result in functionality_results if result.get('success', False))
    total_tests = len(functionality_results)
    
    print(f"\n✅ 功能测试: {successful_tests}/{total_tests} 通过")
    
    if successful_tests > 0:
        avg_execution_time = sum(
            result.get('execution_time', 0) 
            for result in functionality_results 
            if result.get('success', False)
        ) / successful_tests
        
        avg_quality_score = sum(
            result.get('query_quality_score', 0)
            for result in functionality_results
            if result.get('success', False)
        ) / successful_tests
        
        print(f"📊 平均执行时间: {avg_execution_time:.2f}秒")
        print(f"📈 平均查询质量: {avg_quality_score:.3f}")
    
    # 性能测试总结
    print(f"\n🚀 性能优化效果:")
    print(f"   - 缓存性能提升: {cache_results['performance_improvement']:.1f}%")
    print(f"   - 并行处理提升: {parallel_results['performance_improvement']:.1f}%")
    
    # 详细结果
    print(f"\n📝 详细测试结果:")
    for result in functionality_results:
        if result.get('success'):
            status = "✅"
            dept_match = "✅" if result['detected_department'] == result['expected_department'] else "⚠️"
        else:
            status = "❌"
            dept_match = "❌"
        
        print(f"   {status} 测试{result['test_case']}: {dept_match} 科室识别, "
              f"质量{result.get('query_quality_score', 0):.2f}, "
              f"耗时{result.get('execution_time', 0):.2f}s")
    
    print(f"\n🎉 集成测试完成！")

if __name__ == "__main__":
    asyncio.run(main())