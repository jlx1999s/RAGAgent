import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
import asyncio
from services.enhanced_rag_service import medical_retrieve, enhanced_rag_service

async def test_api_flow():
    try:
        # 1. 先调用检索
        print('=== 步骤1: 调用 medical_retrieve ===')
        citations, context_text, metadata = await medical_retrieve(
            question='小孩子感冒怎么办',
            department=None,
            document_type=None,
            disease_category=None
        )
        print(f'检索结果: citations={len(citations)}, context_length={len(context_text)}')
        print(f'Citations: {[c.get("citation_id") for c in citations]}')
        
        # 2. 然后调用流式处理
        print('\n=== 步骤2: 调用 medical_answer_stream ===')
        citations_list = []
        full_answer_parts = []
        first_metadata = None
        used_retrieval = False
        
        async for event in enhanced_rag_service.medical_answer_stream(
            question='小孩子感冒怎么办',
            citations=citations,
            context_text=context_text,
            metadata=metadata,
            session_id=None,
            enable_safety_check=True
        ):
            et, ed = event.get('type'), event.get('data')
            if et == 'token' and isinstance(ed, str):
                full_answer_parts.append(ed)
            elif et == 'citation' and isinstance(ed, dict):
                citations_list.append(ed)
                print(f'收到citation事件: {ed.get("citation_id")}')
            elif et == 'metadata' and isinstance(ed, dict):
                first_metadata = ed
            elif et == 'done' and isinstance(ed, dict):
                used_retrieval = bool(ed.get('used_retrieval'))
        
        print(f'\n=== 最终结果 ===')
        print(f'Citations收集到: {len(citations_list)}')
        print(f'Answer长度: {len("".join(full_answer_parts))}')
        print(f'Used retrieval: {used_retrieval}')
        
        return {
            'citations': citations_list,
            'answer': "".join(full_answer_parts),
            'metadata': first_metadata or metadata,
            'used_retrieval': used_retrieval
        }
        
    except Exception as e:
        print(f'测试过程中发生异常: {e}')
        import traceback
        traceback.print_exc()
        return {}

if __name__ == "__main__":
    result = asyncio.run(test_api_flow())