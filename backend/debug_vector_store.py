#!/usr/bin/env python3
"""
调试向量存储问题的脚本
"""
import os
import sys
import json
from pathlib import Path

# 添加当前目录到Python路径
sys.path.append(str(Path(__file__).parent))

from services.medical_vector_store import MedicalVectorStoreManager
from services.medical_taxonomy import MedicalDepartment, DocumentType, DiseaseCategory
from services.index_service import load_embeddings

def debug_vector_store():
    print("=== 调试向量存储 ===")
    
    # 初始化嵌入模型
    embeddings = load_embeddings()
    
    # 初始化向量存储管理器
    base_path = "data/vector_stores"
    manager = MedicalVectorStoreManager(base_path=base_path, embeddings=embeddings)
    
    print(f"向量存储基础路径: {manager.base_path}")
    print(f"路径是否存在: {manager.base_path.exists()}")
    
    # 检查目录内容
    if manager.base_path.exists():
        print(f"\n实际目录内容:")
        items = list(manager.base_path.iterdir())
        print(f"总共找到 {len(items)} 个项目")
        
        for item in items:
            print(f"  项目: {item.name} (是目录: {item.is_dir()})")
            if item.is_dir():
                print(f"    目录: {item.name}")
                
                # 检查metadata.json
                metadata_file = item / "metadata.json"
                if metadata_file.exists():
                    print(f"      有metadata.json文件")
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                            print(f"      元数据内容: {metadata}")
                    except Exception as e:
                        print(f"      读取metadata.json失败: {e}")
                else:
                    print(f"      缺少metadata.json文件")
                
                # 检查向量存储文件
                faiss_file = item / "index.faiss"
                pkl_file = item / "index.pkl"
                print(f"      FAISS文件存在: {faiss_file.exists()}")
                print(f"      PKL文件存在: {pkl_file.exists()}")
    else:
        print(f"\n基础路径不存在: {manager.base_path}")
    
    # 检查元数据缓存
    print(f"\n元数据缓存: {manager.metadata_cache}")
    print(f"缓存中的键: {list(manager.metadata_cache.keys())}")
    
    # 检查可用的枚举值
    print(f"\n可用的医疗部门: {[dept.value for dept in MedicalDepartment]}")
    print(f"可用的文档类型: {[doc_type.value for doc_type in DocumentType]}")
    print(f"可用的疾病分类: {[cat.value for cat in DiseaseCategory]}")
    
    # 尝试手动加载一个向量存储
    print(f"\n=== 手动测试向量存储加载 ===")
    try:
        # 尝试加载外科向量存储
        store_key = "外科_临床指南_消化系统疾病"
        print(f"尝试加载向量存储: {store_key}")
        
        vector_store = manager._load_vector_store(store_key)
        if vector_store:
            print(f"成功加载向量存储")
            print(f"向量存储类型: {type(vector_store)}")
            
            # 尝试搜索
            print(f"尝试搜索...")
            results = vector_store.similarity_search("糖尿病", k=3)
            print(f"搜索结果数量: {len(results)}")
            for i, doc in enumerate(results):
                print(f"  结果 {i+1}: {doc.page_content[:100]}...")
        else:
            print(f"加载向量存储失败")
            
    except Exception as e:
        print(f"手动加载向量存储时出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_vector_store()