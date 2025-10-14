#!/usr/bin/env python3
"""检查外科向量存储的内容"""

import sys
import os
from pathlib import Path
import pickle

# 添加backend目录到Python路径
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def check_surgery_vector_store():
    """检查外科向量存储的内容"""
    
    # 外科向量存储路径
    surgery_store_path = Path("/Users/jinlingxiao/Downloads/RAGAgent/backend/backend/data/medical_vector_stores/外科_临床指南_消化系统疾病")
    
    if not surgery_store_path.exists():
        print(f"❌ 外科向量存储不存在: {surgery_store_path}")
        return
    
    print(f"✅ 检查外科向量存储: {surgery_store_path}")
    
    # 检查文件
    files = list(surgery_store_path.glob("*"))
    print(f"📁 存储文件: {[f.name for f in files]}")
    
    # 加载并检查内容
    try:
        # 加载index.pkl
        index_file = surgery_store_path / "index.pkl"
        if index_file.exists():
            with open(index_file, 'rb') as f:
                data = pickle.load(f)
                print(f"📊 Index数据类型: {type(data)}")
                
                if isinstance(data, tuple) and len(data) >= 2:
                    docstore = data[0]  # InMemoryDocstore
                    index_to_docstore_id = data[1]  # dict
                    
                    print(f"📚 文档存储类型: {type(docstore)}")
                    print(f"🔗 索引映射类型: {type(index_to_docstore_id)}")
                    print(f"📄 文档数量: {len(index_to_docstore_id)}")
                    
                    # 检查前几个文档的内容
                    print("\n📖 文档内容预览:")
                    for i, (idx, doc_id) in enumerate(list(index_to_docstore_id.items())[:3]):
                        if hasattr(docstore, '_dict') and doc_id in docstore._dict:
                            doc = docstore._dict[doc_id]
                            content_preview = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                            print(f"\n文档 {i+1} (ID: {doc_id}):")
                            print(f"内容: {content_preview}")
                            print(f"元数据: {doc.metadata}")
                            
                            # 检查是否包含阑尾炎相关内容
                            if "阑尾炎" in doc.page_content:
                                print(f"🔍 发现阑尾炎相关内容!")
                        
    except Exception as e:
        print(f"❌ 加载向量存储失败: {e}")

if __name__ == "__main__":
    check_surgery_vector_store()