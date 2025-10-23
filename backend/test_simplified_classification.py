#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试简化分类体系的效果
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from patient.services.smart_intent_service import SmartMedicalIntentRecognizer
from services.medical_taxonomy import (
    SimplifiedMedicalDepartment, SimplifiedDocumentType, SimplifiedDiseaseCategory
)
import json

def test_simplified_classification():
    """测试简化分类体系的效果"""
    print("=" * 60)
    print("测试简化分类体系效果")
    print("=" * 60)
    
    # 创建智能意图识别器，启用简化分类
    recognizer = SmartMedicalIntentRecognizer()
    recognizer.use_simplified_classification = True
    
    # 测试用例
    test_queries = [
        "感冒的症状有哪些？",
        "高血压的治疗方法有哪些？", 
        "骨折后应该如何处理？",
        "糖尿病患者的饮食注意事项",
        "心脏病的预防措施",
        "肺炎的诊断标准",
        "胃溃疡的治疗指南",
        "关节炎的康复训练",
        "抑郁症的心理治疗",
        "儿童发育迟缓的评估"
    ]
    
    print("\n1. 测试简化分类体系识别效果:")
    print("-" * 40)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n测试 {i}: {query}")
        try:
            result = recognizer.recognize_intent(query)
            
            print(f"  科室: {result.get('department', '未识别')}")
            print(f"  文档类型: {result.get('document_type', '未识别')}")
            print(f"  疾病分类: {result.get('disease_category', '未识别')}")
            print(f"  使用简化分类: {result.get('use_simplified_classification', False)}")
            
            if result.get('optimized'):
                print(f"  优化状态: 已优化")
                optimization_steps = result.get('optimization_steps', [])
                if optimization_steps:
                    print(f"  优化步骤: {len(optimization_steps)} 个")
                    for step in optimization_steps[:2]:  # 只显示前2个步骤
                        print(f"    - {step}")
            else:
                print(f"  优化状态: 未优化")
                
        except Exception as e:
            print(f"  错误: {str(e)}")
    
    print("\n\n2. 测试简化分类枚举:")
    print("-" * 40)
    
    print("简化科室分类:")
    for dept in SimplifiedMedicalDepartment:
        print(f"  - {dept.value}")
    
    print("\n简化文档类型:")
    for doc_type in SimplifiedDocumentType:
        print(f"  - {doc_type.value}")
    
    print("\n简化疾病分类:")
    for disease_cat in SimplifiedDiseaseCategory:
        print(f"  - {disease_cat.value}")
    
    print("\n\n3. 对比传统分类和简化分类:")
    print("-" * 40)
    
    # 测试同一个查询在两种模式下的结果
    test_query = "高血压的治疗方法有哪些？"
    
    # 传统分类
    recognizer.use_simplified_classification = False
    traditional_result = recognizer.recognize_intent(test_query)
    
    # 简化分类
    recognizer.use_simplified_classification = True
    simplified_result = recognizer.recognize_intent(test_query)
    
    print(f"测试查询: {test_query}")
    print("\n传统分类结果:")
    print(f"  科室: {traditional_result.get('department', '未识别')}")
    print(f"  文档类型: {traditional_result.get('document_type', '未识别')}")
    print(f"  疾病分类: {traditional_result.get('disease_category', '未识别')}")
    
    print("\n简化分类结果:")
    print(f"  科室: {simplified_result.get('department', '未识别')}")
    print(f"  文档类型: {simplified_result.get('document_type', '未识别')}")
    print(f"  疾病分类: {simplified_result.get('disease_category', '未识别')}")
    
    # 分析优化效果
    print("\n\n4. 优化效果分析:")
    print("-" * 40)
    
    traditional_optimized = traditional_result.get('optimized', False)
    simplified_optimized = simplified_result.get('optimized', False)
    
    print(f"传统分类优化状态: {'已优化' if traditional_optimized else '未优化'}")
    print(f"简化分类优化状态: {'已优化' if simplified_optimized else '未优化'}")
    
    if simplified_optimized:
        optimization_steps = simplified_result.get('optimization_steps', [])
        print(f"简化分类优化步骤数: {len(optimization_steps)}")
        for step in optimization_steps:
            print(f"  - {step}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_simplified_classification()