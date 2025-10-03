#!/usr/bin/env python3
"""
测试 medical_retrieve 函数
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.enhanced_rag_service import enhanced_rag_service
from services.medical_taxonomy import MedicalDepartment, DocumentType, DiseaseCategory

async def test_medical_retrieve():
    """测试 medical_retrieve 函数"""
    
    print("=== 测试 medical_retrieve 函数 ===")
    
    # 测试参数
    question = "小孩子感冒怎么办"
    department = MedicalDepartment.PEDIATRICS  # 儿科
    document_type = DocumentType.CLINICAL_GUIDELINE  # 临床指南
    disease_category = DiseaseCategory.INFECTIOUS_DISEASES  # 感染性疾病
    
    print(f"查询: {question}")
    print(f"科室: {department.value}")
    print(f"文档类型: {document_type.value}")
    print(f"疾病分类: {disease_category.value}")
    print()
    
    try:
        # 调用 medical_retrieve 函数
        citations, context_text, metadata = await enhanced_rag_service.medical_retrieve(
            question=question,
            department=department,
            document_type=document_type,
            disease_category=disease_category
        )
        
        print("=== 检索结果 ===")
        print(f"引用数量: {len(citations)}")
        print(f"上下文长度: {len(context_text)}")
        print(f"元数据: {metadata}")
        print()
        
        if citations:
            print("=== 引用详情 ===")
            for i, citation in enumerate(citations, 1):
                print(f"引用 {i}:")
                print(f"  ID: {citation.get('citation_id')}")
                print(f"  分数: {citation.get('score')}")
                print(f"  科室: {citation.get('department')}")
                print(f"  文档类型: {citation.get('document_type')}")
                print(f"  疾病分类: {citation.get('disease_category', 'N/A')}")
                print(f"  来源: {citation.get('source')}")
                print(f"  片段: {citation.get('snippet', '')[:200]}...")
                print()
        else:
            print("❌ 没有找到相关文档")
            
        if context_text:
            print("=== 上下文文本 ===")
            print(context_text[:500] + "..." if len(context_text) > 500 else context_text)
        else:
            print("❌ 没有上下文文本")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_medical_retrieve())