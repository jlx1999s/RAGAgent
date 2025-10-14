#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精简版医疗流式问答测试脚本
"""

import json
import asyncio
import httpx

async def test_medical_chat(message: str, session_id: str = "test_user:thread_1"):
    """测试医疗聊天流式接口"""
    url = "http://localhost:8001/api/v1/medical/chat"
    payload = {
        "message": message,
        "sessionId": session_id,
        "enableSafetyCheck": True
    }
    
    print(f"问题: {message}")
    print("回答: ", end="", flush=True)
    
    full_answer = ""
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            if response.status_code != 200:
                print(f"错误: HTTP {response.status_code}")
                return
            
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                lines = buffer.split('\n')
                buffer = lines.pop() or ""
                
                for line in lines:
                    if line.startswith('data: '):
                        try:
                            event = json.loads(line[6:])
                            event_type = event.get('type')
                            data = event.get('data')
                            
                            if event_type == 'token':
                                print(data, end="", flush=True)
                                full_answer += data
                            elif event_type == 'done':
                                print(f"\n\n✅ 完成")
                                return full_answer
                            elif event_type == 'error':
                                print(f"\n❌ 错误: {data}")
                                return None
                        except json.JSONDecodeError:
                            continue
    
    return full_answer

async def main():
    """主函数"""
    question = "高血压怎么办"
    await test_medical_chat(question)

if __name__ == "__main__":
    asyncio.run(main())