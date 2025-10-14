#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
支持并发的医疗流式问答测试脚本
"""

import json
import asyncio
import httpx
import time
from typing import List

async def test_medical_chat(message: str, session_id: str, task_id: int = 1):
    """测试医疗聊天流式接口"""
    url = "http://localhost:8001/api/v1/medical/chat"
    payload = {
        "message": message,
        "sessionId": session_id,
        "enableSafetyCheck": True
    }
    
    start_time = time.time()
    print(f"[任务{task_id}] 开始: {message[:30]}...")
    
    full_answer = ""
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    print(f"[任务{task_id}] 错误: HTTP {response.status_code}")
                    return None
                
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
                                    full_answer += data
                                elif event_type == 'done':
                                    duration = time.time() - start_time
                                    print(f"[任务{task_id}] ✅ 完成 ({duration:.2f}秒)")
                                    return full_answer
                                elif event_type == 'error':
                                    print(f"[任务{task_id}] ❌ 错误: {data}")
                                    return None
                            except json.JSONDecodeError:
                                continue
    except Exception as e:
        print(f"[任务{task_id}] 💥 异常: {e}")
        return None
    
    return full_answer

async def test_concurrent_requests():
    """测试并发请求"""
    questions = [
        "患者长期血压维持在140/90，如何管理与用药？",
        "糖尿病患者应该如何控制饮食？",
        "感冒发烧时应该注意什么？",
        "高血脂患者的运动建议是什么？",
        "失眠患者如何改善睡眠质量？"
    ]
    
    # 创建并发任务，每个任务使用不同的session_id
    tasks = []
    for i, question in enumerate(questions, 1):
        session_id = f"concurrent_user_{i}:thread_1"
        task = test_medical_chat(question, session_id, i)
        tasks.append(task)
    
    print(f"🚀 开始并发测试 - {len(tasks)}个任务")
    print("-" * 60)
    
    start_time = time.time()
    
    # 并发执行所有任务
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("📊 并发测试结果")
    print("=" * 60)
    
    success_count = 0
    for i, result in enumerate(results, 1):
        if isinstance(result, Exception):
            print(f"任务{i}: ❌ 异常 - {result}")
        elif result is None:
            print(f"任务{i}: ❌ 失败")
        else:
            print(f"任务{i}: ✅ 成功 - {len(result)}字符")
            success_count += 1
    
    print(f"\n📈 统计:")
    print(f"   总任务数: {len(tasks)}")
    print(f"   成功数: {success_count}")
    print(f"   失败数: {len(tasks) - success_count}")
    print(f"   总耗时: {total_time:.2f}秒")
    print(f"   平均耗时: {total_time/len(tasks):.2f}秒/任务")

async def test_same_session_concurrent():
    """测试相同session_id的并发请求（不推荐）"""
    questions = [
        "什么是高血压？",
        "高血压有什么症状？",
        "高血压如何治疗？"
    ]
    
    session_id = "same_session_test:thread_1"
    
    print("⚠️  测试相同session_id的并发请求（可能导致上下文混乱）")
    print("-" * 60)
    
    tasks = []
    for i, question in enumerate(questions, 1):
        task = test_medical_chat(question, session_id, i)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print("\n📝 注意: 相同session_id的并发请求可能导致聊天历史混乱")

async def main():
    """主函数"""
    print("🏥 并发医疗流式问答测试")
    print("=" * 60)
    
    # 测试1: 不同session_id的并发请求
    await test_concurrent_requests()
    
    print("\n" + "=" * 60)
    
    # 测试2: 相同session_id的并发请求
    await test_same_session_concurrent()

if __name__ == "__main__":
    asyncio.run(main())