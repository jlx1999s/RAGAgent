#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的医疗文档切分演示
"""

import re
from typing import List, Dict

class SimpleMedicalTextSplitter:
    """简化的医疗文档分割器"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def split_medical_document(self, text: str) -> List[Dict]:
        """分割医疗文档，保持医疗概念的完整性"""
        # 识别文档结构
        structured_chunks = self._identify_document_structure(text)
        
        documents = []
        for chunk_info in structured_chunks:
            # 进一步分割过长的块
            if len(chunk_info['content']) > self.chunk_size:
                sub_chunks = self._split_long_text(chunk_info['content'])
                for i, sub_chunk in enumerate(sub_chunks):
                    documents.append({
                        'content': sub_chunk,
                        'chunk_type': chunk_info['type'],
                        'section_title': chunk_info.get('title', ''),
                        'sub_chunk_index': i
                    })
            else:
                documents.append({
                    'content': chunk_info['content'],
                    'chunk_type': chunk_info['type'],
                    'section_title': chunk_info.get('title', '')
                })
        
        return documents
    
    def _identify_document_structure(self, text: str) -> List[Dict]:
        """识别文档结构"""
        chunks = []
        lines = text.split('\n')
        current_chunk = {'content': '', 'type': 'paragraph', 'title': ''}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 识别标题
            if self._is_title(line):
                if current_chunk['content']:
                    chunks.append(current_chunk)
                current_chunk = {'content': line, 'type': 'title', 'title': line}
            
            # 识别列表
            elif self._is_list_item(line):
                if current_chunk['type'] != 'list':
                    if current_chunk['content']:
                        chunks.append(current_chunk)
                    current_chunk = {'content': line, 'type': 'list', 'title': ''}
                else:
                    current_chunk['content'] += '\n' + line
            
            # 识别表格
            elif self._is_table_row(line):
                if current_chunk['type'] != 'table':
                    if current_chunk['content']:
                        chunks.append(current_chunk)
                    current_chunk = {'content': line, 'type': 'table', 'title': ''}
                else:
                    current_chunk['content'] += '\n' + line
            
            # 普通段落
            else:
                if current_chunk['type'] not in ['paragraph', 'title']:
                    if current_chunk['content']:
                        chunks.append(current_chunk)
                    current_chunk = {'content': line, 'type': 'paragraph', 'title': ''}
                else:
                    if current_chunk['content']:
                        current_chunk['content'] += '\n' + line
                    else:
                        current_chunk['content'] = line
        
        if current_chunk['content']:
            chunks.append(current_chunk)
        
        return chunks
    
    def _is_title(self, line: str) -> bool:
        """判断是否为标题"""
        # Markdown标题
        if line.startswith('#'):
            return True
        
        # 标题模式：数字编号、短文本、特定关键词
        title_patterns = [
            r'^\d+[\.\、]\s*[\u4e00-\u9fff]+',  # 数字编号
            r'^[一二三四五六七八九十]+[\.\、]\s*[\u4e00-\u9fff]+',  # 中文数字编号
        ]
        
        # 短文本且包含医疗关键词
        if len(line) < 50 and any(keyword in line for keyword in ['诊断', '治疗', '症状', '病因', '预防', '检查', '用药']):
            return True
        
        return any(re.match(pattern, line) for pattern in title_patterns)
    
    def _is_list_item(self, line: str) -> bool:
        """判断是否为列表项"""
        list_patterns = [
            r'^[•·▪▫◦‣⁃-]\s+',  # 项目符号
            r'^\d+[\.\)]\s+',   # 数字列表
            r'^[a-zA-Z][\.\)]\s+',  # 字母列表
            r'^[\(（]\d+[\)）]\s+',  # 括号数字
            r'^\*\*.*\*\*：',  # Markdown粗体标记
        ]
        return any(re.match(pattern, line) for pattern in list_patterns)
    
    def _is_table_row(self, line: str) -> bool:
        """判断是否为表格行"""
        # 简单的表格识别：包含多个分隔符
        separators = ['|', '\t']
        return any(sep in line and line.count(sep) >= 2 for sep in separators)
    
    def _split_long_text(self, text: str) -> List[str]:
        """分割过长的文本"""
        # 简单的按句号分割
        sentences = text.split('。')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk + sentence + '。') <= self.chunk_size:
                current_chunk += sentence + '。'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + '。'
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text]

def main():
    # 读取感冒诊疗指南
    try:
        with open('../感冒诊疗指南.md', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("找不到感冒诊疗指南.md文件")
        return
    
    # 创建分割器
    splitter = SimpleMedicalTextSplitter(chunk_size=300, chunk_overlap=50)
    
    # 处理文档
    chunks = splitter.split_medical_document(content)
    
    print(f'文档被切分为 {len(chunks)} 个块:')
    print('=' * 60)
    
    for i, chunk in enumerate(chunks):
        print(f'块 {i+1}:')
        print(f'类型: {chunk["chunk_type"]}')
        print(f'内容长度: {len(chunk["content"])} 字符')
        if chunk.get('section_title'):
            print(f'章节标题: {chunk["section_title"]}')
        print(f'内容预览: {chunk["content"][:150]}...')
        print('-' * 40)

if __name__ == "__main__":
    main()