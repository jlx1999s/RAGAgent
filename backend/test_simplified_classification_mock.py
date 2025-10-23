#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试简化分类体系的映射效果（模拟环境）
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.medical_taxonomy import (
    MedicalDepartment, DocumentType, DiseaseCategory,
    SimplifiedMedicalDepartment, SimplifiedDocumentType, SimplifiedDiseaseCategory,
    DEPARTMENT_MAPPING, DOCUMENT_TYPE_MAPPING, DISEASE_CATEGORY_MAPPING
)
import json

def test_classification_mapping():
    """测试分类映射效果"""
    print("=" * 60)
    print("测试简化分类体系映射效果")
    print("=" * 60)
    
    print("\n1. 科室映射测试:")
    print("-" * 40)
    
    # 测试科室映射
    original_departments = [dept.value for dept in MedicalDepartment]
    print(f"原始科室数量: {len(original_departments)}")
    
    simplified_departments = [dept.value for dept in SimplifiedMedicalDepartment]
    print(f"简化科室数量: {len(simplified_departments)}")
    
    print("\n科室映射关系:")
    mapped_count = 0
    for original_dept in original_departments:
        simplified_dept = DEPARTMENT_MAPPING.get(original_dept)
        if simplified_dept:
            print(f"  {original_dept} -> {simplified_dept}")
            mapped_count += 1
        else:
            print(f"  {original_dept} -> 未映射")
    
    print(f"\n映射覆盖率: {mapped_count}/{len(original_departments)} ({mapped_count/len(original_departments)*100:.1f}%)")
    
    print("\n\n2. 文档类型映射测试:")
    print("-" * 40)
    
    # 测试文档类型映射
    original_doc_types = [doc_type.value for doc_type in DocumentType]
    print(f"原始文档类型数量: {len(original_doc_types)}")
    
    simplified_doc_types = [doc_type.value for doc_type in SimplifiedDocumentType]
    print(f"简化文档类型数量: {len(simplified_doc_types)}")
    
    print("\n文档类型映射关系:")
    mapped_count = 0
    for original_type in original_doc_types:
        simplified_type = DOCUMENT_TYPE_MAPPING.get(original_type)
        if simplified_type:
            print(f"  {original_type} -> {simplified_type}")
            mapped_count += 1
        else:
            print(f"  {original_type} -> 未映射")
    
    print(f"\n映射覆盖率: {mapped_count}/{len(original_doc_types)} ({mapped_count/len(original_doc_types)*100:.1f}%)")
    
    print("\n\n3. 疾病分类映射测试:")
    print("-" * 40)
    
    # 测试疾病分类映射
    original_disease_categories = [disease_cat.value for disease_cat in DiseaseCategory]
    print(f"原始疾病分类数量: {len(original_disease_categories)}")
    
    simplified_disease_categories = [disease_cat.value for disease_cat in SimplifiedDiseaseCategory]
    print(f"简化疾病分类数量: {len(simplified_disease_categories)}")
    
    print("\n疾病分类映射关系:")
    mapped_count = 0
    for original_category in original_disease_categories:
        simplified_category = DISEASE_CATEGORY_MAPPING.get(original_category)
        if simplified_category:
            print(f"  {original_category} -> {simplified_category}")
            mapped_count += 1
        else:
            print(f"  {original_category} -> 未映射")
    
    print(f"\n映射覆盖率: {mapped_count}/{len(original_disease_categories)} ({mapped_count/len(original_disease_categories)*100:.1f}%)")

def test_smart_intent_with_mock_data():
    """使用模拟数据测试智能意图识别"""
    print("\n\n4. 模拟智能意图识别测试:")
    print("-" * 40)
    
    # 模拟系统资源
    mock_system_resources = {
        "departments": ["内科", "外科", "儿科", "妇产科", "急诊科"],
        "document_types": ["临床指南", "诊断标准", "治疗方案", "综合参考"],
        "store_details": {},
        "total_stores": 5
    }
    
    # 模拟意图识别结果
    test_cases = [
        {
            "query": "感冒的症状有哪些？",
            "original_result": {
                "department": "呼吸科",
                "document_type": "临床指南", 
                "disease_category": "呼吸系统疾病"
            }
        },
        {
            "query": "高血压的治疗方法",
            "original_result": {
                "department": "心血管科",
                "document_type": "治疗方案",
                "disease_category": "循环系统疾病"
            }
        },
        {
            "query": "骨折后的处理",
            "original_result": {
                "department": "骨科",
                "document_type": "诊疗规范",
                "disease_category": "肌肉骨骼系统疾病"
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试案例 {i}: {test_case['query']}")
        original = test_case['original_result']
        
        print(f"  原始识别结果:")
        print(f"    科室: {original['department']}")
        print(f"    文档类型: {original['document_type']}")
        print(f"    疾病分类: {original['disease_category']}")
        
        # 模拟简化分类映射
        simplified_dept = DEPARTMENT_MAPPING.get(original['department'], original['department'])
        simplified_doc_type = DOCUMENT_TYPE_MAPPING.get(original['document_type'], original['document_type'])
        simplified_disease_cat = DISEASE_CATEGORY_MAPPING.get(original['disease_category'], original['disease_category'])
        
        print(f"  简化分类映射:")
        print(f"    科室: {original['department']} -> {simplified_dept}")
        print(f"    文档类型: {original['document_type']} -> {simplified_doc_type}")
        print(f"    疾病分类: {original['disease_category']} -> {simplified_disease_cat}")
        
        # 检查是否在系统资源中
        dept_available = simplified_dept in mock_system_resources['departments']
        doc_type_available = simplified_doc_type in mock_system_resources['document_types']
        
        print(f"  资源匹配状态:")
        print(f"    科室可用: {'是' if dept_available else '否'}")
        print(f"    文档类型可用: {'是' if doc_type_available else '否'}")
        
        # 智能回退机制
        if not dept_available:
            fallback_dept = "内科"  # 通用科室
            print(f"    科室回退: {simplified_dept} -> {fallback_dept}")
        
        if not doc_type_available:
            fallback_doc_type = "综合参考"  # 通用文档类型
            print(f"    文档类型回退: {simplified_doc_type} -> {fallback_doc_type}")

def analyze_optimization_benefits():
    """分析优化效果"""
    print("\n\n5. 优化效果分析:")
    print("-" * 40)
    
    # 统计原始分类数量
    original_dept_count = len([dept.value for dept in MedicalDepartment])
    original_doc_type_count = len([doc_type.value for doc_type in DocumentType])
    original_disease_count = len([disease_cat.value for disease_cat in DiseaseCategory])
    
    # 统计简化分类数量
    simplified_dept_count = len([dept.value for dept in SimplifiedMedicalDepartment])
    simplified_doc_type_count = len([doc_type.value for doc_type in SimplifiedDocumentType])
    simplified_disease_count = len([disease_cat.value for disease_cat in SimplifiedDiseaseCategory])
    
    print("分类数量对比:")
    print(f"  科室: {original_dept_count} -> {simplified_dept_count} (减少 {original_dept_count - simplified_dept_count} 个)")
    print(f"  文档类型: {original_doc_type_count} -> {simplified_doc_type_count} (减少 {original_doc_type_count - simplified_doc_type_count} 个)")
    print(f"  疾病分类: {original_disease_count} -> {simplified_disease_count} (减少 {original_disease_count - simplified_disease_count} 个)")
    
    # 计算简化率
    dept_reduction = (original_dept_count - simplified_dept_count) / original_dept_count * 100
    doc_type_reduction = (original_doc_type_count - simplified_doc_type_count) / original_doc_type_count * 100
    disease_reduction = (original_disease_count - simplified_disease_count) / original_disease_count * 100
    
    print(f"\n简化率:")
    print(f"  科室简化率: {dept_reduction:.1f}%")
    print(f"  文档类型简化率: {doc_type_reduction:.1f}%")
    print(f"  疾病分类简化率: {disease_reduction:.1f}%")
    
    print(f"\n预期效果:")
    print(f"  - 减少分类过度细化问题")
    print(f"  - 提高匹配成功率")
    print(f"  - 降低系统复杂度")
    print(f"  - 改善用户体验")

if __name__ == "__main__":
    test_classification_mapping()
    test_smart_intent_with_mock_data()
    analyze_optimization_benefits()
    
    print("\n" + "=" * 60)
    print("简化分类体系测试完成")
    print("=" * 60)