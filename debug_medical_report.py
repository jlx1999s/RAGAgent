#!/usr/bin/env python3
"""
调试体检报告功能的脚本 - 查看完整API响应
"""

import requests
import json
import sys

def debug_medical_report_api():
    """调试体检报告API功能"""
    
    # API端点
    url = "http://localhost:8001/api/v1/medical/qa"
    
    # 测试数据 - 带体检报告
    test_data = {
        "message": "我的血常规报告有什么问题吗？需要注意什么？",
        "sessionId": "debug-session-1",
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
    
    print("调试体检报告功能...")
    print("=" * 60)
    print(f"请求URL: {url}")
    print(f"请求数据: {json.dumps(test_data, ensure_ascii=False, indent=2)}")
    print("=" * 60)
    
    try:
        # 发送请求
        response = requests.post(url, json=test_data, timeout=30)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        print("=" * 60)
        
        if response.status_code == 200:
            try:
                result = response.json()
                print("完整响应数据:")
                print(json.dumps(result, ensure_ascii=False, indent=2))
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {e}")
                print(f"原始响应内容: {response.text}")
        else:
            print(f"请求失败: {response.status_code}")
            print(f"错误内容: {response.text}")
            
    except Exception as e:
        print(f"请求异常: {str(e)}")
    
    print("\n" + "=" * 60)
    
    # 测试无体检报告的情况作为对比
    print("对比测试 - 无体检报告:")
    test_data_no_report = {
        "message": "血常规异常应该注意什么？",
        "sessionId": "debug-session-2",
        "enableSafetyCheck": True,
        "intentRecognitionMethod": "qwen_llm"
    }
    
    try:
        response2 = requests.post(url, json=test_data_no_report, timeout=30)
        print(f"响应状态码: {response2.status_code}")
        
        if response2.status_code == 200:
            try:
                result2 = response2.json()
                print("无体检报告的响应数据:")
                print(json.dumps(result2, ensure_ascii=False, indent=2))
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {e}")
                print(f"原始响应内容: {response2.text}")
        else:
            print(f"请求失败: {response2.status_code}")
            print(f"错误内容: {response2.text}")
            
    except Exception as e:
        print(f"请求异常: {str(e)}")

if __name__ == "__main__":
    debug_medical_report_api()