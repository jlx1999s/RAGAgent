# services/medical_preprocessor.py
"""
医疗文档预处理模块
支持医疗术语识别、标准化和文档结构化处理
"""

import re
import json
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
import jieba
import jieba.posseg as pseg

# 添加医疗词典到jieba
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
medical_dict_path = os.path.join(current_dir, '..', 'data', 'medical_dict.txt')
if os.path.exists(medical_dict_path):
    jieba.load_userdict(medical_dict_path)  # 加载医疗词典文件

@dataclass
class MedicalEntity:
    """医疗实体"""
    text: str
    entity_type: str  # 'disease', 'symptom', 'drug', 'examination', 'anatomy'
    standard_name: str  # 标准化名称
    confidence: float
    start_pos: int
    end_pos: int

@dataclass
class ProcessedChunk:
    """处理后的文档块"""
    content: str
    medical_entities: List[MedicalEntity]
    chunk_type: str  # 'title', 'paragraph', 'list', 'table'
    metadata: Dict
    embedding_text: str  # 用于向量化的文本

class MedicalTermNormalizer:
    """医疗术语标准化器"""
    
    def __init__(self):
        # 医疗术语同义词映射
        self.synonym_dict = {
            # 疾病同义词
            "高血压": ["高血压病", "原发性高血压", "继发性高血压"],
            "糖尿病": ["DM", "diabetes mellitus", "糖尿病"],
            "冠心病": ["冠状动脉粥样硬化性心脏病", "CHD", "冠状动脉疾病"],
            "心肌梗死": ["心梗", "MI", "急性心肌梗死", "STEMI", "NSTEMI"],
            
            # 症状同义词
            "胸痛": ["胸部疼痛", "胸闷", "心前区疼痛"],
            "呼吸困难": ["气短", "气促", "呼吸急促", "dyspnea"],
            "头痛": ["头疼", "cephalgia", "头部疼痛"],
            
            # 检查同义词
            "心电图": ["ECG", "EKG", "十二导联心电图"],
            "CT": ["计算机断层扫描", "computed tomography"],
            "MRI": ["磁共振成像", "核磁共振", "magnetic resonance imaging"],
            
            # 药物同义词
            "阿司匹林": ["aspirin", "乙酰水杨酸"],
            "硝酸甘油": ["nitroglycerin", "GTN"],
        }
        
        # 构建反向索引
        self.term_to_standard = {}
        for standard, synonyms in self.synonym_dict.items():
            self.term_to_standard[standard] = standard
            for synonym in synonyms:
                self.term_to_standard[synonym] = standard
    
    def normalize_term(self, term: str) -> str:
        """标准化医疗术语"""
        # 去除空格和标点
        cleaned_term = re.sub(r'[^\w\u4e00-\u9fff]', '', term)
        
        # 查找标准化名称
        return self.term_to_standard.get(cleaned_term, cleaned_term)
    
    def get_all_variants(self, standard_term: str) -> List[str]:
        """获取术语的所有变体"""
        if standard_term in self.synonym_dict:
            return [standard_term] + self.synonym_dict[standard_term]
        return [standard_term]

class MedicalEntityExtractor:
    """医疗实体提取器"""
    
    def __init__(self):
        self.normalizer = MedicalTermNormalizer()
        
        # 医疗实体识别模式
        self.entity_patterns = {
            'disease': [
                r'[\u4e00-\u9fff]+(?:病|症|炎|癌|瘤|综合征)',
                r'[\u4e00-\u9fff]+(?:性|型)[\u4e00-\u9fff]+(?:病|症)',
                r'(?:急性|慢性|原发性|继发性)[\u4e00-\u9fff]+',
            ],
            'symptom': [
                r'[\u4e00-\u9fff]*(?:痛|疼|胀|闷|痒|麻|酸|胀)',
                r'[\u4e00-\u9fff]*(?:困难|不适|异常|障碍)',
                r'(?:发热|发烧|咳嗽|咳痰|气短|乏力|头晕)',
            ],
            'drug': [
                r'[\u4e00-\u9fff]+(?:片|胶囊|注射液|颗粒|糖浆|软膏)',
                r'[\u4e00-\u9fff]+(?:滴眼液|喷雾剂|栓剂|贴剂)',
            ],
            'examination': [
                r'[\u4e00-\u9fff]*(?:检查|检验|测定|筛查|监测)',
                r'(?:CT|MRI|X线|B超|心电图|血常规|尿常规)',
                r'[\u4e00-\u9fff]+(?:造影|内镜|活检)',
            ],
            'anatomy': [
                r'[\u4e00-\u9fff]+(?:脏|腺|管|道|膜|肌|骨|关节)',
                r'(?:心脏|肝脏|肺部|肾脏|大脑|胃部|肠道)',
            ]
        }
    
    def extract_entities(self, text: str) -> List[MedicalEntity]:
        """提取医疗实体"""
        entities = []
        
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    entity_text = match.group()
                    standard_name = self.normalizer.normalize_term(entity_text)
                    
                    entity = MedicalEntity(
                        text=entity_text,
                        entity_type=entity_type,
                        standard_name=standard_name,
                        confidence=0.8,  # 基于规则的置信度
                        start_pos=match.start(),
                        end_pos=match.end()
                    )
                    entities.append(entity)
        
        # 去重和排序
        entities = self._deduplicate_entities(entities)
        return sorted(entities, key=lambda x: x.start_pos)
    
    def _deduplicate_entities(self, entities: List[MedicalEntity]) -> List[MedicalEntity]:
        """去重重叠的实体"""
        if not entities:
            return entities
        
        # 按位置排序
        entities.sort(key=lambda x: (x.start_pos, x.end_pos))
        
        deduplicated = [entities[0]]
        for entity in entities[1:]:
            last_entity = deduplicated[-1]
            
            # 检查是否重叠
            if entity.start_pos < last_entity.end_pos:
                # 保留置信度更高的实体
                if entity.confidence > last_entity.confidence:
                    deduplicated[-1] = entity
            else:
                deduplicated.append(entity)
        
        return deduplicated

class MedicalTextSplitter:
    """医疗文档分割器"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.base_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "；", "，", " ", ""]
        )
    
    def split_medical_document(self, text: str, metadata: Dict = None) -> List[Document]:
        """分割医疗文档，保持医疗概念的完整性"""
        if metadata is None:
            metadata = {}
        
        # 识别文档结构
        structured_chunks = self._identify_document_structure(text)
        
        documents = []
        for chunk_info in structured_chunks:
            # 进一步分割过长的块
            if len(chunk_info['content']) > self.chunk_size:
                sub_chunks = self.base_splitter.split_text(chunk_info['content'])
                for i, sub_chunk in enumerate(sub_chunks):
                    doc_metadata = {
                        **metadata,
                        'chunk_type': chunk_info['type'],
                        'section_title': chunk_info.get('title', ''),
                        'sub_chunk_index': i
                    }
                    documents.append(Document(page_content=sub_chunk, metadata=doc_metadata))
            else:
                doc_metadata = {
                    **metadata,
                    'chunk_type': chunk_info['type'],
                    'section_title': chunk_info.get('title', '')
                }
                documents.append(Document(page_content=chunk_info['content'], metadata=doc_metadata))
        
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
        # 标题模式：数字编号、短文本、特定关键词
        title_patterns = [
            r'^\d+[\.\、]\s*[\u4e00-\u9fff]+',  # 数字编号
            r'^[一二三四五六七八九十]+[\.\、]\s*[\u4e00-\u9fff]+',  # 中文数字编号
            r'^[\u4e00-\u9fff]{2,20}$',  # 短文本
        ]
        
        return any(re.match(pattern, line) for pattern in title_patterns) and len(line) < 50
    
    def _is_list_item(self, line: str) -> bool:
        """判断是否为列表项"""
        list_patterns = [
            r'^[•·▪▫◦‣⁃]\s+',  # 项目符号
            r'^\d+[\.\)]\s+',   # 数字列表
            r'^[a-zA-Z][\.\)]\s+',  # 字母列表
            r'^[\(（]\d+[\)）]\s+',  # 括号数字
        ]
        return any(re.match(pattern, line) for pattern in list_patterns)
    
    def _is_table_row(self, line: str) -> bool:
        """判断是否为表格行"""
        # 简单的表格识别：包含多个分隔符
        separators = ['|', '\t', '  ']
        return any(sep in line and line.count(sep) >= 2 for sep in separators)

class MedicalDocumentPreprocessor:
    """医疗文档预处理器主类"""
    
    def __init__(self):
        self.entity_extractor = MedicalEntityExtractor()
        self.text_splitter = MedicalTextSplitter()
        self.normalizer = MedicalTermNormalizer()
    
    def preprocess_document(self, text: str, metadata: Dict = None) -> List[ProcessedChunk]:
        """预处理医疗文档"""
        if metadata is None:
            metadata = {}
        
        # 文本清理
        cleaned_text = self._clean_text(text)
        
        # 分割文档
        documents = self.text_splitter.split_medical_document(cleaned_text, metadata)
        
        processed_chunks = []
        for doc in documents:
            # 提取医疗实体
            entities = self.entity_extractor.extract_entities(doc.page_content)
            
            # 生成用于向量化的增强文本
            embedding_text = self._generate_embedding_text(doc.page_content, entities)
            
            chunk = ProcessedChunk(
                content=doc.page_content,
                medical_entities=entities,
                chunk_type=doc.metadata.get('chunk_type', 'paragraph'),
                metadata=doc.metadata,
                embedding_text=embedding_text
            )
            processed_chunks.append(chunk)
        
        return processed_chunks
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符（保留中文、英文、数字、基本标点）
        text = re.sub(r'[^\w\u4e00-\u9fff\s\.\,\;\:\!\?\(\)\[\]\{\}\"\'\/\-\+\=\%\@\#\$\&\*]', '', text)
        
        # 标准化标点符号
        text = text.replace('，', ',').replace('。', '.').replace('；', ';')
        
        return text.strip()
    
    def _generate_embedding_text(self, content: str, entities: List[MedicalEntity]) -> str:
        """生成用于向量化的增强文本"""
        # 原始内容
        embedding_text = content
        
        # 添加标准化的医疗术语
        standard_terms = []
        for entity in entities:
            if entity.standard_name != entity.text:
                standard_terms.append(entity.standard_name)
            
            # 添加同义词
            variants = self.normalizer.get_all_variants(entity.standard_name)
            standard_terms.extend(variants)
        
        if standard_terms:
            # 去重并添加到文本末尾
            unique_terms = list(set(standard_terms))
            embedding_text += " [医疗术语: " + " ".join(unique_terms) + "]"
        
        return embedding_text

# 使用示例
if __name__ == "__main__":
    preprocessor = MedicalDocumentPreprocessor()
    
    # 示例医疗文档
    sample_text = """
    冠心病诊疗指南
    
    1. 概述
    冠状动脉粥样硬化性心脏病（冠心病）是由于冠状动脉粥样硬化使管腔狭窄或闭塞，
    导致心肌缺血缺氧而引起的心脏病。
    
    2. 临床表现
    • 典型胸痛：胸骨后或心前区疼痛
    • 呼吸困难
    • 心律不齐
    
    3. 诊断检查
    - 心电图检查
    - 冠状动脉造影
    - 心肌酶检测
    """
    
    chunks = preprocessor.preprocess_document(sample_text)
    
    for i, chunk in enumerate(chunks):
        print(f"块 {i+1}:")
        print(f"类型: {chunk.chunk_type}")
        print(f"内容: {chunk.content[:100]}...")
        print(f"实体: {[(e.text, e.entity_type) for e in chunk.medical_entities]}")
        print(f"向量化文本: {chunk.embedding_text[:150]}...")
        print("-" * 50)