#!/usr/bin/env python3
"""
检查医疗向量存储中的文档内容，找出测试PDF
"""

import pickle
import json
from pathlib import Path

def check_vector_store(store_path):
    """检查指定向量存储中的文档"""
    print(f"\n=== 检查向量存储: {store_path.name} ===")
    
    # 读取元数据
    metadata_file = store_path / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        print(f"部门: {metadata['department']}")
        print(f"文档类型: {metadata['document_type']}")
        print(f"疾病分类: {metadata['disease_category']}")
        print(f"文档数量: {metadata['document_count']}")
    
    # 读取向量存储的pickle文件
    pkl_file = store_path / "index.pkl"
    if pkl_file.exists():
        try:
            with open(pkl_file, 'rb') as f:
                data = pickle.load(f)
            
            print(f"数据类型: {type(data)}")
            
            # 如果是tuple，尝试解析
            if isinstance(data, tuple):
                print(f"Tuple长度: {len(data)}")
                for i, item in enumerate(data):
                    print(f"  项目 {i}: {type(item)}")
                    
                # 根据输出，格式是 (InMemoryDocstore, dict)
                if len(data) >= 2:
                    docstore, index_to_docstore_id = data[0], data[1]
                    print(f"文档存储类型: {type(docstore)}")
                    print(f"索引映射类型: {type(index_to_docstore_id)}")
                    
                    # InMemoryDocstore的文档存储在_dict中
                    if hasattr(docstore, '_dict'):
                        docs = docstore._dict
                        print(f"实际文档数量: {len(docs)}")
                        
                        # 检查每个文档
                        for i, (doc_id, doc) in enumerate(docs.items()):
                            print(f"\n文档 {i+1} (ID: {doc_id}):")
                            content_preview = doc.page_content[:200] if len(doc.page_content) > 200 else doc.page_content
                            print(f"  内容预览: {content_preview}")
                            print(f"  元数据: {doc.metadata}")
                            
                            # 检查是否是测试PDF
                            if ("test PDF" in doc.page_content.lower() or 
                                "upload testing" in doc.page_content.lower() or
                                "sample text" in doc.page_content.lower()):
                                print(f"  ⚠️  发现测试PDF!")
                                return True
                    else:
                        print("  文档存储没有_dict属性")
            
            # 如果是FAISS对象
            elif hasattr(data, 'docstore'):
                docstore = data.docstore
                print(f"文档存储类型: {type(docstore)}")
                
                if hasattr(docstore, '_dict'):
                    docs = docstore._dict
                    print(f"实际文档数量: {len(docs)}")
                    
                    # 检查每个文档
                    for i, (doc_id, doc) in enumerate(docs.items()):
                        print(f"\n文档 {i+1} (ID: {doc_id}):")
                        content_preview = doc.page_content[:200] if len(doc.page_content) > 200 else doc.page_content
                        print(f"  内容预览: {content_preview}")
                        print(f"  元数据: {doc.metadata}")
                        
                        # 检查是否是测试PDF
                        if ("test PDF" in doc.page_content.lower() or 
                            "upload testing" in doc.page_content.lower() or
                            "sample text" in doc.page_content.lower()):
                            print(f"  ⚠️  发现测试PDF!")
                            return True
                else:
                    print("  文档存储没有_dict属性")
            else:
                print("  未知的数据格式")
                
        except Exception as e:
            print(f"  读取向量存储失败: {e}")
    else:
        print("  index.pkl文件不存在")
    
    return False

def main():
    """主函数"""
    base_path = Path("/Users/jinlingxiao/Downloads/RAGAgent/backend/data/vector_stores")
    
    if not base_path.exists():
        print(f"向量存储目录不存在: {base_path}")
        return
    
    found_test_pdf = False
    
    # 检查所有向量存储
    for store_dir in base_path.iterdir():
        if store_dir.is_dir() and "心血管科" in store_dir.name:
            if check_vector_store(store_dir):
                found_test_pdf = True
    
    if found_test_pdf:
        print("\n🚨 发现测试PDF被错误索引到医疗知识库中!")
    else:
        print("\n✅ 未发现测试PDF")

if __name__ == "__main__":
    main()