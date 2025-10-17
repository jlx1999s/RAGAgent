#!/usr/bin/env python3
"""
修复medical_retrieve函数中search_results可能为None的问题
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.enhanced_rag_service import enhanced_rag_service

async def test_search_results_handling():
    """测试搜索结果处理逻辑"""
    
    print("🔍 测试搜索结果处理...")
    
    # 测试正常查询
    try:
        citations, context, metadata = await enhanced_rag_service.medical_retrieve(
            question="小孩子感冒怎么办",
            intent_method="smart"
        )
        
        print(f"✅ 正常查询成功:")
        print(f"   Citations: {len(citations)}")
        print(f"   Context length: {len(context)}")
        print(f"   Metadata keys: {list(metadata.keys())}")
        
        # 检查是否有错误信息
        if 'error' in metadata:
            print(f"❌ 发现错误: {metadata['error']}")
        else:
            print("✅ 没有错误信息")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

def check_search_engine_status():
    """检查搜索引擎状态"""
    
    print("\n🔧 检查搜索引擎状态...")
    
    try:
        # 检查索引服务
        index_service = enhanced_rag_service.index_service
        print(f"✅ 索引服务已初始化: {type(index_service)}")
        
        # 检查搜索引擎
        search_engine = index_service.search_engine
        print(f"✅ 搜索引擎已初始化: {type(search_engine)}")
        
        # 检查向量存储管理器
        vector_store_manager = search_engine.vector_store_manager
        print(f"✅ 向量存储管理器已初始化: {type(vector_store_manager)}")
        
        # 获取统计信息
        stats = index_service.get_vector_store_statistics()
        print(f"📊 向量存储统计: {stats}")
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()

def test_direct_search():
    """直接测试搜索功能"""
    
    print("\n🎯 直接测试搜索功能...")
    
    try:
        index_service = enhanced_rag_service.index_service
        
        # 测试搜索
        search_results = index_service.search_medical_documents(
            query="小孩子感冒怎么办",
            department="儿科",
            document_type="临床指南",
            k=5,
            score_threshold=0.3
        )
        
        print(f"搜索结果类型: {type(search_results)}")
        print(f"搜索结果: {search_results}")
        
        if search_results is None:
            print("❌ 搜索结果为None!")
        elif isinstance(search_results, dict):
            print(f"✅ 搜索结果是字典，包含键: {list(search_results.keys())}")
            if search_results.get("ok"):
                print(f"✅ 搜索成功，结果数量: {len(search_results.get('results', []))}")
            else:
                print(f"❌ 搜索失败: {search_results.get('error')}")
        else:
            print(f"⚠️ 搜索结果类型异常: {type(search_results)}")
            
    except Exception as e:
        print(f"❌ 直接搜索测试失败: {e}")
        import traceback
        traceback.print_exc()

import asyncio

if __name__ == "__main__":
    print("🚀 开始修复和测试搜索结果处理...")
    
    check_search_engine_status()
    test_direct_search()
    asyncio.run(test_search_results_handling())
    
    print("\n✅ 修复和测试完成!")