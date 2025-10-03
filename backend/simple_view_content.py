#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单查看数据库原始内容
"""

import json
import os
from pathlib import Path

def view_simple_content():
    """查看简单的数据库内容"""
    print("=== 医疗数据库内容查看 ===\n")
    
    # 查看data目录结构
    data_path = Path("data")
    if not data_path.exists():
        print("data目录不存在")
        return
    
    print(f"数据目录: {data_path.absolute()}\n")
    
    # 遍历所有子目录
    subdirs = [d for d in data_path.iterdir() if d.is_dir()]
    print(f"找到 {len(subdirs)} 个数据目录:\n")
    
    for i, subdir in enumerate(subdirs, 1):
        print(f"{'='*50}")
        print(f"目录 {i}: {subdir.name}")
        print(f"{'='*50}")
        
        # 列出目录中的所有文件
        files = list(subdir.iterdir())
        print(f"文件列表 ({len(files)} 个文件):")
        for file in files:
            size = file.stat().st_size if file.is_file() else "目录"
            print(f"  📄 {file.name} ({size} 字节)")
        
        # 查看processing_metadata.json
        metadata_file = subdir / "processing_metadata.json"
        if metadata_file.exists():
            print(f"\n📋 处理元数据:")
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                for key, value in metadata.items():
                    print(f"  {key}: {value}")
            except Exception as e:
                print(f"  ❌ 读取失败: {e}")
        
        # 查看原始markdown文件
        md_files = list(subdir.glob("*.md"))
        if md_files:
            print(f"\n📝 Markdown文件内容:")
            for md_file in md_files:
                print(f"\n  文件: {md_file.name}")
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    print(f"  大小: {len(content)} 字符")
                    # 显示前500字符
                    preview = content[:500] + "..." if len(content) > 500 else content
                    print(f"  内容预览:\n{preview}")
                except Exception as e:
                    print(f"  ❌ 读取失败: {e}")
        
        # 查看chunks.json文件
        chunks_file = subdir / "chunks.json"
        if chunks_file.exists():
            print(f"\n🧩 文档块信息:")
            try:
                with open(chunks_file, 'r', encoding='utf-8') as f:
                    chunks = json.load(f)
                print(f"  块数量: {len(chunks)}")
                
                # 显示前3个块的内容
                for j, chunk in enumerate(chunks[:3]):
                    print(f"\n  块 {j+1}:")
                    if isinstance(chunk, dict):
                        for key, value in chunk.items():
                            if key == 'content' and len(str(value)) > 200:
                                print(f"    {key}: {str(value)[:200]}...")
                            else:
                                print(f"    {key}: {value}")
                    else:
                        content = str(chunk)[:200] + "..." if len(str(chunk)) > 200 else str(chunk)
                        print(f"    内容: {content}")
                
                if len(chunks) > 3:
                    print(f"    ... 还有 {len(chunks) - 3} 个块")
                    
            except Exception as e:
                print(f"  ❌ 读取失败: {e}")
        
        print(f"\n")
    
    # 查看向量存储目录
    vector_store_path = data_path / "vector_stores"
    if vector_store_path.exists():
        print(f"{'='*50}")
        print("向量存储目录")
        print(f"{'='*50}")
        
        store_dirs = [d for d in vector_store_path.iterdir() if d.is_dir()]
        print(f"向量存储数量: {len(store_dirs)}")
        
        for store_dir in store_dirs:
            print(f"\n📦 {store_dir.name}:")
            files = list(store_dir.iterdir())
            for file in files:
                size = file.stat().st_size if file.is_file() else "目录"
                print(f"  {file.name} ({size} 字节)")

def main():
    view_simple_content()

if __name__ == "__main__":
    main()