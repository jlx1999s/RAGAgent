#!/usr/bin/env python3
"""
优化后检索流程的输入输出测试
测试缓存机制、并行处理和动态权重调整功能
"""

import asyncio
import time
import logging
from services.enhanced_rag_service import enhanced_rag_service
from services.cache_service import cache_service

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_optimized_retrieval():
    """测试优化后的检索流程"""
    print("=" * 80)
    print("优化后检索流程测试")
    print("=" * 80)
    
    # 测试查询
    test_queries = [
        "糖尿病的诊断标准是什么？",
        "高血压患者的用药指导",
        "心脏病的预防措施有哪些？"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n【测试 {i}】查询: {query}")
        print("-" * 60)
        
        # 第一次查询（无缓存）
        start_time = time.time()
        try:
            citations, context, metadata = await enhanced_rag_service.medical_retrieve(
                question=query,
                session_id=f"test_session_{i}"
            )
            first_query_time = time.time() - start_time
            
            print(f"✅ 第一次查询完成 - 耗时: {first_query_time:.2f}秒")
            print(f"📄 检索到文档数: {len(citations)}")
            print(f"🎯 意图识别: {metadata.get('intent_recognition', {}).get('department', '未识别')}")
            print(f"📊 查询质量: {metadata.get('query_quality', {}).get('overall_score', 0):.3f}")
            
            # KG增强信息
            kg_info = metadata.get('kg_enhancement', {})
            if kg_info.get('enabled'):
                print(f"🧠 KG增强: 实体{len(kg_info.get('entities', []))}个, 建议{len(kg_info.get('suggestions', []))}个")
            
            # 医疗关联信息
            medical_assoc = metadata.get('medical_associations', {})
            if medical_assoc.get('enabled'):
                print(f"🔗 医疗关联: {len(medical_assoc.get('associations', []))}个关联")
            
            # 动态权重信息
            dynamic_weights = metadata.get('dynamic_weights', {})
            if dynamic_weights:
                print(f"⚖️ 动态权重: 语义{dynamic_weights.get('semantic', 0):.2f}, "
                      f"医疗{dynamic_weights.get('medical', 0):.2f}, "
                      f"KG{dynamic_weights.get('kg', 0):.2f}")
            
        except Exception as e:
            print(f"❌ 第一次查询失败: {e}")
            continue
        
        # 第二次查询（测试缓存）
        print("\n🔄 测试缓存效果...")
        start_time = time.time()
        try:
            citations2, context2, metadata2 = await enhanced_rag_service.medical_retrieve(
                question=query,
                session_id=f"test_session_{i}"
            )
            second_query_time = time.time() - start_time
            
            print(f"✅ 第二次查询完成 - 耗时: {second_query_time:.2f}秒")
            print(f"⚡ 缓存加速: {((first_query_time - second_query_time) / first_query_time * 100):.1f}%")
            
            # 验证结果一致性
            if len(citations) == len(citations2):
                print("✅ 缓存结果一致性验证通过")
            else:
                print("⚠️ 缓存结果可能不一致")
                
        except Exception as e:
            print(f"❌ 第二次查询失败: {e}")
    
    # 缓存统计
    print("\n" + "=" * 60)
    print("缓存统计信息")
    print("=" * 60)
    
    try:
        cache_stats = cache_service.get_stats()
        print(f"📊 缓存统计:")
        print(f"   - 总条目: {cache_stats.get('total_entries', 0)}")
        print(f"   - 过期条目: {cache_stats.get('expired_count', 0)}")
        print(f"   - 最大容量: {cache_stats.get('max_size', 0)}")
        
        type_stats = cache_stats.get('type_stats', {})
        for cache_type, stats in type_stats.items():
            print(f"   - {cache_type}: {stats.get('count', 0)}条目, {stats.get('total_access', 0)}次访问")
    except Exception as e:
        print(f"❌ 获取缓存统计失败: {e}")

async def test_parallel_processing():
    """测试并行处理性能"""
    print("\n" + "=" * 80)
    print("并行处理性能测试")
    print("=" * 80)
    
    queries = [
        "糖尿病并发症有哪些？",
        "高血压的治疗方案",
        "心脏病的早期症状"
    ]
    
    # 串行处理测试
    print("🔄 串行处理测试...")
    start_time = time.time()
    serial_results = []
    
    for query in queries:
        try:
            result = await enhanced_rag_service.medical_retrieve(
                question=query,
                session_id="serial_test"
            )
            serial_results.append(result)
        except Exception as e:
            print(f"❌ 串行查询失败: {e}")
    
    serial_time = time.time() - start_time
    print(f"✅ 串行处理完成 - 总耗时: {serial_time:.2f}秒")
    
    # 并行处理测试
    print("\n⚡ 并行处理测试...")
    start_time = time.time()
    
    try:
        # 使用asyncio.gather进行并行处理
        parallel_results = await asyncio.gather(*[
            enhanced_rag_service.medical_retrieve(
                question=query,
                session_id=f"parallel_test_{i}"
            )
            for i, query in enumerate(queries)
        ])
        
        parallel_time = time.time() - start_time
        print(f"✅ 并行处理完成 - 总耗时: {parallel_time:.2f}秒")
        print(f"⚡ 性能提升: {((serial_time - parallel_time) / serial_time * 100):.1f}%")
        
    except Exception as e:
        print(f"❌ 并行处理失败: {e}")

async def main():
    """主测试函数"""
    print("🚀 开始优化后检索流程测试")
    
    # 清理缓存，确保测试环境干净
    cache_service.clear()
    
    try:
        # 测试优化后的检索流程
        await test_optimized_retrieval()
        
        # 测试并行处理性能
        await test_parallel_processing()
        
        print("\n" + "=" * 80)
        print("✅ 所有测试完成！")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())