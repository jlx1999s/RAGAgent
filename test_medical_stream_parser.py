#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医疗流式问答解析脚本
用于测试和解析 POST /api/v1/medical/chat 的流式返回数据
"""

import json
import asyncio
import httpx
from typing import Dict, List, Any, Optional
import time

class MedicalStreamParser:
    """医疗流式响应解析器"""
    
    def __init__(self, base_url: str = "http://localhost:8001/api/v1"):
        self.base_url = base_url
        self.session_id = f"test_session_{int(time.time())}"
        
    async def parse_medical_chat_stream(
        self, 
        message: str, 
        session_id: Optional[str] = None,
        enable_safety_check: bool = True
    ) -> Dict[str, Any]:
        """
        解析医疗聊天流式响应
        
        Args:
            message: 用户问题
            session_id: 会话ID，默认使用实例的session_id
            enable_safety_check: 是否启用安全检查
            
        Returns:
            解析结果字典，包含完整答案、引用、元数据等
        """
        if session_id is None:
            session_id = self.session_id
            
        url = f"{self.base_url}/medical/chat"
        payload = {
            "message": message,
            "sessionId": session_id,
            "enableSafetyCheck": enable_safety_check
        }
        
        # 解析结果存储
        result = {
            "question": message,
            "session_id": session_id,
            "full_answer": "",
            "citations": [],
            "metadata": {},
            "quality_assessment": {},
            "events": [],
            "status": "pending",
            "error": None,
            "start_time": time.time(),
            "end_time": None
        }
        
        try:
            print(f"🚀 开始请求: {message}")
            print(f"📡 URL: {url}")
            print(f"🔑 Session ID: {session_id}")
            print("-" * 60)
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
                    buffer = ""
                    token_count = 0
                    
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        lines = buffer.split('\n')
                        buffer = lines.pop() or ""
                        
                        for line in lines:
                            line = line.strip()
                            if line.startswith('data: '):
                                try:
                                    event_data = json.loads(line[6:])
                                    event_type = event_data.get('type')
                                    event_payload = event_data.get('data')
                                    
                                    # 记录所有事件
                                    result["events"].append({
                                        "type": event_type,
                                        "data": event_payload,
                                        "timestamp": time.time()
                                    })
                                    
                                    # 处理不同类型的事件
                                    if event_type == 'token':
                                        result["full_answer"] += event_payload
                                        token_count += 1
                                        print(f"📝 Token #{token_count}: {repr(event_payload)}")
                                        
                                    elif event_type == 'citation':
                                        result["citations"].append(event_payload)
                                        print(f"📚 Citation: {event_payload.get('title', 'N/A')}")
                                        
                                    elif event_type == 'metadata':
                                        result["metadata"] = event_payload
                                        print(f"🔍 Metadata: {json.dumps(event_payload, ensure_ascii=False, indent=2)}")
                                        
                                    elif event_type == 'quality_assessment':
                                        result["quality_assessment"] = event_payload
                                        print(f"⭐ Quality Assessment:")
                                        print(f"   质量等级: {event_payload.get('quality_level')}")
                                        print(f"   质量分数: {event_payload.get('quality_score')}")
                                        print(f"   安全等级: {event_payload.get('safety_level')}")
                                        print(f"   安全分数: {event_payload.get('safety_score')}")
                                        
                                    elif event_type == 'done':
                                        result["status"] = "completed"
                                        result["end_time"] = time.time()
                                        print(f"✅ 完成: {json.dumps(event_payload, ensure_ascii=False)}")
                                        return result
                                        
                                    elif event_type == 'error':
                                        result["status"] = "error"
                                        result["error"] = event_payload
                                        result["end_time"] = time.time()
                                        print(f"❌ 错误: {event_payload}")
                                        return result
                                        
                                except json.JSONDecodeError as e:
                                    print(f"⚠️  JSON解析错误: {e}, 原始行: {line}")
                                    continue
                    
                    # 如果循环结束但没有收到done事件
                    result["status"] = "incomplete"
                    result["end_time"] = time.time()
                    
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["end_time"] = time.time()
            print(f"💥 请求异常: {e}")
            
        return result
    
    def print_summary(self, result: Dict[str, Any]):
        """打印解析结果摘要"""
        print("\n" + "=" * 60)
        print("📊 解析结果摘要")
        print("=" * 60)
        
        print(f"❓ 问题: {result['question']}")
        print(f"🆔 会话ID: {result['session_id']}")
        print(f"📊 状态: {result['status']}")
        
        if result.get('error'):
            print(f"❌ 错误: {result['error']}")
        
        duration = (result.get('end_time', time.time()) - result['start_time'])
        print(f"⏱️  耗时: {duration:.2f}秒")
        
        print(f"📝 完整答案长度: {len(result['full_answer'])}字符")
        print(f"📚 引用数量: {len(result['citations'])}")
        print(f"🎯 事件总数: {len(result['events'])}")
        
        # 事件类型统计
        event_types = {}
        for event in result['events']:
            event_type = event['type']
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        print(f"📈 事件类型统计: {event_types}")
        
        if result['full_answer']:
            print(f"\n💬 完整答案:")
            print("-" * 40)
            print(result['full_answer'])
            print("-" * 40)
        
        if result['quality_assessment']:
            qa = result['quality_assessment']
            print(f"\n⭐ 质量评估:")
            print(f"   质量: {qa.get('quality_level')} (分数: {qa.get('quality_score')})")
            print(f"   安全: {qa.get('safety_level')} (分数: {qa.get('safety_score')})")

async def test_medical_questions():
    """测试多个医疗问题"""
    parser = MedicalStreamParser()
    
    test_questions = [
        "患者长期血压维持在140/90，如何管理与用药？",
        "糖尿病患者应该如何控制饮食？",
        "感冒发烧时应该注意什么？"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n🧪 测试 {i}/{len(test_questions)}")
        result = await parser.parse_medical_chat_stream(question)
        parser.print_summary(result)
        
        if i < len(test_questions):
            print("\n⏳ 等待3秒后继续下一个测试...")
            await asyncio.sleep(3)

async def main():
    """主函数"""
    print("🏥 医疗流式问答解析脚本")
    print("=" * 60)
    
    # 单个问题测试
    parser = MedicalStreamParser()
    question = "患者长期血压维持在140/90，如何管理与用药？"
    
    result = await parser.parse_medical_chat_stream(question)
    parser.print_summary(result)
    
    # 询问是否进行多问题测试
    print(f"\n🤔 是否要测试更多问题？(y/n): ", end="")
    try:
        choice = input().strip().lower()
        if choice in ['y', 'yes', '是', '好']:
            await test_medical_questions()
    except KeyboardInterrupt:
        print("\n👋 测试中断")

if __name__ == "__main__":
    asyncio.run(main())