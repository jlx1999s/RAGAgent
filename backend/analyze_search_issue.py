#!/usr/bin/env python3
"""
分析医疗搜索问题的脚本
测试为什么"糖尿病"查询返回阑尾炎结果
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.enhanced_index_service import EnhancedMedicalIndexService
from services.medical_vector_store import MedicalVectorStoreManager
from services.medical_taxonomy import MedicalDepartment, DocumentType, DiseaseCategory

def analyze_search_issue():
    """分析搜索问题"""
    
    print("=== 医疗搜索问题分析 ===\n")
    
    # 初始化服务
    service = EnhancedMedicalIndexService()
    
    # 1. 检查向量存储统计
    print("1. 向量存储统计信息:")
    stats = service.get_vector_store_statistics()
    if stats.get('ok'):
        stores = stats.get('stores', {})
        print(f"   总共有 {len(stores)} 个向量存储:")
        for store_key, store_info in stores.items():
            print(f"   - {store_key}: {store_info['document_count']} 个文档")
            print(f"     科室: {store_info['department']}")
            print(f"     文档类型: {store_info['document_type']}")
            print(f"     疾病分类: {store_info['disease_category']}")
    else:
        print(f"   获取统计信息失败: {stats.get('error')}")
    
    print("\n" + "="*50 + "\n")
    
    # 2. 测试糖尿病查询
    print("2. 测试糖尿病查询:")
    diabetes_queries = ["糖尿病", "什么是糖尿病", "糖尿病的症状", "diabetes"]
    
    for query in diabetes_queries:
        print(f"\n查询: '{query}'")
        result = service.search_medical_documents(query, k=5)
        
        if result.get('ok'):
            results = result.get('results', [])
            print(f"   找到 {len(results)} 个结果:")
            
            for i, res in enumerate(results[:3]):  # 只显示前3个
                print(f"   结果 {i+1}:")
                print(f"     分数: {res['score']:.4f}")
                print(f"     科室: {res['department']}")
                print(f"     文档类型: {res['document_type']}")
                print(f"     疾病分类: {res['disease_category']}")
                print(f"     内容预览: {res['text'][:100]}...")
                print()
        else:
            print(f"   搜索失败: {result.get('error')}")
    
    print("\n" + "="*50 + "\n")
    
    # 3. 测试指定科室搜索
    print("3. 测试指定内分泌科搜索:")
    result = service.search_medical_documents(
        "糖尿病", 
        k=5, 
        department="内科"
    )
    
    if result.get('ok'):
        results = result.get('results', [])
        print(f"   内科搜索找到 {len(results)} 个结果:")
        
        for i, res in enumerate(results):
            print(f"   结果 {i+1}:")
            print(f"     分数: {res['score']:.4f}")
            print(f"     科室: {res['department']}")
            print(f"     疾病分类: {res['disease_category']}")
            print(f"     内容预览: {res['text'][:100]}...")
            print()
    else:
        print(f"   内科搜索失败: {result.get('error')}")
    
    print("\n" + "="*50 + "\n")
    
    # 4. 测试阑尾炎查询
    print("4. 测试阑尾炎查询:")
    result = service.search_medical_documents("阑尾炎", k=3)
    
    if result.get('ok'):
        results = result.get('results', [])
        print(f"   阑尾炎搜索找到 {len(results)} 个结果:")
        
        for i, res in enumerate(results):
            print(f"   结果 {i+1}:")
            print(f"     分数: {res['score']:.4f}")
            print(f"     科室: {res['department']}")
            print(f"     疾病分类: {res['disease_category']}")
            print(f"     内容预览: {res['text'][:100]}...")
            print()
    else:
        print(f"   阑尾炎搜索失败: {result.get('error')}")
    
    print("\n" + "="*50 + "\n")
    
    # 5. 分析向量存储内容
    print("5. 分析各向量存储的内容:")
    
    # 直接访问向量存储管理器
    manager = service.vector_store_manager
    
    for store_key in manager.metadata_cache.keys():
        print(f"\n向量存储: {store_key}")
        
        # 尝试搜索糖尿病
        try:
            vector_store = manager._load_vector_store(store_key)
            if vector_store:
                store_results = vector_store.similarity_search_with_score("糖尿病", k=2)
                print(f"   糖尿病搜索结果数: {len(store_results)}")
                
                for doc, score in store_results:
                    print(f"     分数: {score:.4f}")
                    print(f"     内容: {doc.page_content[:80]}...")
                    
                # 尝试搜索阑尾炎
                store_results = vector_store.similarity_search_with_score("阑尾炎", k=2)
                print(f"   阑尾炎搜索结果数: {len(store_results)}")
                
                for doc, score in store_results:
                    print(f"     分数: {score:.4f}")
                    print(f"     内容: {doc.page_content[:80]}...")
            else:
                print("   无法加载向量存储")
        except Exception as e:
            print(f"   搜索出错: {e}")

if __name__ == "__main__":
    analyze_search_issue()