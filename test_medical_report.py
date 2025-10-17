#!/usr/bin/env python3
"""
测试体检报告功能的脚本
"""

import requests
import json
import sys

def test_medical_report_api():
    """测试体检报告API功能"""
    
    # API端点
    url = "http://localhost:8001/api/v1/medical/qa"
    
    # 测试用的体检报告数据
    test_cases = [
        {
            "name": "血常规异常测试",
            "data": {
                "message": "我的血常规报告有什么问题吗？需要注意什么？",
                "sessionId": "test-session-1",
                "medicalReport": """血常规检查报告：
白细胞计数：12.5 × 10^9/L (正常值：4.0-10.0)
红细胞计数：3.8 × 10^12/L (正常值：4.0-5.5)
血红蛋白：95 g/L (正常值：120-160)
血小板计数：180 × 10^9/L (正常值：100-300)
中性粒细胞百分比：78% (正常值：50-70%)""",
                "reportType": "血常规",
                "enableSafetyCheck": True,
                "intentRecognitionMethod": "qwen_llm"
            }
        },
        {
            "name": "肝功能异常测试",
            "data": {
                "message": "根据我的肝功能检查结果，我应该怎么办？",
                "sessionId": "test-session-2", 
                "medicalReport": """肝功能检查报告：
谷丙转氨酶(ALT)：85 U/L (正常值：5-40)
谷草转氨酶(AST)：92 U/L (正常值：8-40)
总胆红素：28 μmol/L (正常值：3.4-20.5)
直接胆红素：18 μmol/L (正常值：0-6.8)
白蛋白：35 g/L (正常值：35-55)""",
                "reportType": "肝功能",
                "enableSafetyCheck": True,
                "intentRecognitionMethod": "qwen_llm"
            }
        },
        {
            "name": "无体检报告对照测试",
            "data": {
                "message": "血常规异常应该注意什么？",
                "sessionId": "test-session-3",
                "enableSafetyCheck": True,
                "intentRecognitionMethod": "qwen_llm"
            }
        }
    ]
    
    print("开始测试体检报告功能...")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {test_case['name']}")
        print("-" * 40)
        
        try:
            # 发送请求
            response = requests.post(url, json=test_case['data'], timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                
                print(f"✅ 请求成功")
                print(f"问题: {test_case['data']['message']}")
                
                if 'medicalReport' in test_case['data']:
                    print(f"体检报告类型: {test_case['data']['reportType']}")
                    print(f"体检报告内容: {test_case['data']['medicalReport'][:100]}...")
                else:
                    print("无体检报告")
                
                print(f"\n回答: {result.get('answer', '无回答')[:200]}...")
                
                # 检查引用
                citations = result.get('citations', [])
                print(f"引用数量: {len(citations)}")
                
                # 检查质量评估
                quality = result.get('quality_assessment', {})
                print(f"质量评估: {quality.get('quality_level', 'unknown')}")
                
                # 检查安全性
                safety = result.get('safety_warning', {})
                print(f"安全等级: {safety.get('safety_level', 'unknown')}")
                
            else:
                print(f"❌ 请求失败: {response.status_code}")
                print(f"错误信息: {response.text}")
                
        except Exception as e:
            print(f"❌ 测试异常: {str(e)}")
        
        print("-" * 40)
    
    print("\n测试完成!")

if __name__ == "__main__":
    test_medical_report_api()