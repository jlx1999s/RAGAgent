#!/usr/bin/env python3
"""测试医疗搜索的实际行为"""

import sys
import os
from pathlib import Path

# 添加backend目录到Python路径
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from services.enhanced_index_service import enhanced_index_service

def test_medical_search():
    """测试医疗搜索"""
    
    print("🔍 测试医疗搜索功能")
    
    # 检查向量存储管理器的路径
    print(f"📁 向量存储基础路径: {enhanced_index_service.vector_store_manager.base_path}")
    
    # 检查元数据缓存
    print(f"📊 元数据缓存: {list(enhanced_index_service.vector_store_manager.metadata_cache.keys())}")
    
    # 测试搜索糖尿病
    print("\n🔍 搜索'糖尿病':")
    try:
        results = enhanced_index_service.search_medical_documents(
            query="糖尿病",
            k=5
        )
        
        print(f"✅ 搜索成功，找到 {len(results.get('documents', []))} 个结果")
        
        for i, doc in enumerate(results.get('documents', [])[:3]):
            print(f"\n文档 {i+1}:")
            print(f"内容: {doc.get('content', '')[:200]}...")
            print(f"元数据: {doc.get('metadata', {})}")
            
    except Exception as e:
        print(f"❌ 搜索失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_medical_search()