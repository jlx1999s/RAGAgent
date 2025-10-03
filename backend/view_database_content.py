#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看向量数据库的具体内容
"""

import json
import pickle
import os
from pathlib import Path

def view_database_content():
    """查看数据库内容"""
    print("=== 医疗向量数据库内容查看 ===\n")
    
    # 向量存储路径
    vector_store_path = Path("data/vector_stores")
    
    if not vector_store_path.exists():
        print(f"向量存储目录不存在: {vector_store_path}")
        return
    
    print(f"向量存储基础路径: {vector_store_path.absolute()}")
    
    # 遍历所有向量存储目录
    store_dirs = [d for d in vector_store_path.iterdir() if d.is_dir()]
    print(f"找到 {len(store_dirs)} 个向量存储目录\n")
    
    for i, store_dir in enumerate(store_dirs, 1):
        print(f"{'='*60}")
        print(f"向量存储 {i}: {store_dir.name}")
        print(f"{'='*60}")
        
        # 读取元数据
        metadata_file = store_dir / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                print("📋 元数据信息:")
                print(f"  科室: {metadata.get('department', 'N/A')}")
                print(f"  文档类型: {metadata.get('document_type', 'N/A')}")
                print(f"  疾病分类: {metadata.get('disease_category', 'N/A')}")
                print(f"  文档数量: {metadata.get('document_count', 'N/A')}")
                print(f"  创建时间: {metadata.get('created_at', 'N/A')}")
                print(f"  最后更新: {metadata.get('last_updated', 'N/A')}")
            except Exception as e:
                print(f"❌ 读取元数据失败: {e}")
        else:
            print("❌ 缺少metadata.json文件")
        
        # 检查向量存储文件
        faiss_file = store_dir / "index.faiss"
        pkl_file = store_dir / "index.pkl"
        
        print(f"\n📁 文件状态:")
        print(f"  FAISS索引文件: {'✅ 存在' if faiss_file.exists() else '❌ 不存在'}")
        print(f"  PKL文档文件: {'✅ 存在' if pkl_file.exists() else '❌ 不存在'}")
        
        if faiss_file.exists():
            print(f"  FAISS文件大小: {faiss_file.stat().st_size} 字节")
        if pkl_file.exists():
            print(f"  PKL文件大小: {pkl_file.stat().st_size} 字节")
        
        # 尝试读取文档内容
        if pkl_file.exists():
            try:
                print(f"\n📄 文档内容预览:")
                with open(pkl_file, 'rb') as f:
                    data = pickle.load(f)
                
                print(f"  数据结构类型: {type(data)}")
                
                if isinstance(data, tuple) and len(data) >= 2:
                    docstore, index_to_docstore_id = data[0], data[1]
                    print(f"  文档存储类型: {type(docstore)}")
                    print(f"  索引映射数量: {len(index_to_docstore_id) if hasattr(index_to_docstore_id, '__len__') else 'N/A'}")
                    
                    # 尝试获取文档内容
                    if hasattr(docstore, '_dict') and docstore._dict:
                        docs = list(docstore._dict.values())
                        print(f"  实际文档数量: {len(docs)}")
                        
                        # 显示前几个文档的内容
                        for j, doc in enumerate(docs[:3]):
                            print(f"\n  📝 文档 {j+1}:")
                            if hasattr(doc, 'page_content'):
                                content = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                                print(f"    内容: {content}")
                            if hasattr(doc, 'metadata'):
                                print(f"    元数据: {doc.metadata}")
                        
                        if len(docs) > 3:
                            print(f"    ... 还有 {len(docs) - 3} 个文档")
                    
            except Exception as e:
                print(f"❌ 读取文档内容失败: {e}")
        
        print(f"\n")
    
    # 查看处理元数据
    print(f"{'='*60}")
    print("📊 处理元数据统计")
    print(f"{'='*60}")
    
    data_path = Path("data")
    if data_path.exists():
        processing_files = list(data_path.glob("*/processing_metadata.json"))
        print(f"找到 {len(processing_files)} 个处理元数据文件:")
        
        for proc_file in processing_files:
            try:
                with open(proc_file, 'r', encoding='utf-8') as f:
                    proc_data = json.load(f)
                print(f"\n📁 {proc_file.parent.name}:")
                print(f"  科室: {proc_data.get('department', 'N/A')}")
                print(f"  文档类型: {proc_data.get('document_type', 'N/A')}")
                print(f"  疾病分类: {proc_data.get('disease_category', 'N/A')}")
                print(f"  块数量: {proc_data.get('chunks_count', 'N/A')}")
                print(f"  处理时间: {proc_data.get('processed_at', 'N/A')}")
                if 'custom_metadata' in proc_data:
                    print(f"  自定义元数据: {proc_data['custom_metadata']}")
            except Exception as e:
                print(f"❌ 读取 {proc_file} 失败: {e}")

def main():
    view_database_content()

if __name__ == "__main__":
    main()