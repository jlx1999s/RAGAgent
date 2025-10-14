#!/usr/bin/env python3
"""
测试 medical_retrieve 函数，并分步骤输出每个环节的结果
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.medical_taxonomy import MedicalDepartment, DocumentType, DiseaseCategory

async def test_medical_retrieve():
    """测试 medical_retrieve 函数，逐步展示各阶段输出"""
    print("=== 测试 medical_retrieve 分步流程 ===")

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

    # 步骤1：知识图谱增强
    print("=== 步骤1：知识图谱查询增强 ===")
    kg_enhancement = None
    try:
        from services.medical_knowledge_graph import kg_service
        kg_enhancement = await kg_service.enhance_query_with_kg(question)
        print("原始查询:", kg_enhancement.get("original_query"))
        print("抽取的实体:")
        for e in kg_enhancement.get("extracted_entities", []) or []:
            print(f"  - 名称: {e.get('name')}, 类型: {e.get('type')}, 置信度: {e.get('confidence')}, 别名: {e.get('aliases')}")
        print("相关实体关系:")
        for r in kg_enhancement.get("related_entities", []) or []:
            print(f"  - {r.get('source')} —{r.get('relation')}→ {r.get('target')} (conf={r.get('confidence')})")
        print("查询扩展建议:")
        print("  ", kg_enhancement.get("suggested_expansions", []))
    except Exception as e:
        print("❌ KG增强失败或依赖未安装，使用内置Stub：", e)
        # 提供一个轻量级的KG增强桩，保证测试可以输出示例数据
        class FakeKGService:
            async def enhance_query_with_kg(self, q: str):
                return {
                    "original_query": q,
                    "extracted_entities": [
                        {"name": "感冒", "type": "Disease", "confidence": 0.92, "aliases": ["上呼吸道感染"]},
                        {"name": "发烧", "type": "Symptom", "confidence": 0.88, "aliases": ["体温升高"]},
                    ],
                    "related_entities": [
                        {"source": "感冒", "relation": "recommended_treatment", "target": "对乙酰氨基酚", "confidence": 0.86},
                        {"source": "发烧", "relation": "recommended_treatment", "target": "布洛芬", "confidence": 0.84},
                        {"source": "感冒", "relation": "department", "target": "儿科", "confidence": 0.80},
                    ],
                    "suggested_expansions": ["儿童感冒用药", "退烧注意事项", "什么时候去医院"],
                }
            async def get_knowledge_graph_stats(self):
                return {
                    "total_entities": 128,
                    "total_relations": 256,
                    "entity_types": {"Disease": 40, "Symptom": 50, "Drug": 20, "Department": 18},
                    "relation_types": {"recommended_treatment": 120, "department": 30, "symptom_of": 80},
                }
        kg_service = FakeKGService()
        kg_enhancement = await kg_service.enhance_query_with_kg(question)
        print("原始查询:", kg_enhancement.get("original_query"))
        print("抽取的实体:")
        for e in kg_enhancement.get("extracted_entities", []) or []:
            print(f"  - 名称: {e.get('name')}, 类型: {e.get('type')}, 置信度: {e.get('confidence')}, 别名: {e.get('aliases')}")
        print("相关实体关系:")
        for r in kg_enhancement.get("related_entities", []) or []:
            print(f"  - {r.get('source')} —{r.get('relation')}→ {r.get('target')} (conf={r.get('confidence')})")
        print("查询扩展建议:")
        print("  ", kg_enhancement.get("suggested_expansions", []))
    print()

    # 步骤2：医疗关联挖掘
    print("=== 步骤2：医疗关联挖掘 ===")
    associations = None
    try:
        from services.medical_association_service import medical_association_service
        associations = medical_association_service.find_associations(
            query=question,
            confidence_threshold=0.6,
            max_results=10
        )
        print(f"关联总数: {associations.total_count}")
        for a in associations.associations[:5]:
            print(f"  - {a.source} —{a.association_type.value}→ {a.target} (conf={a.confidence})")
    except Exception as e:
        print("❌ 医疗关联失败或依赖未安装，使用内置Stub：", e)
        # 关联挖掘桩对象
        class Assoc:
            def __init__(self, source, atype, target, conf):
                self.source = source
                class AT:
                    def __init__(self, v):
                        self.value = v
                self.association_type = AT(atype)
                self.target = target
                self.confidence = conf
        class AssocResult:
            def __init__(self, items):
                self.associations = items
                self.total_count = len(items)
        associations = AssocResult([
            Assoc("感冒", "co_occurs_with", "流鼻涕", 0.83),
            Assoc("发烧", "treated_by", "物理降温", 0.78),
            Assoc("儿童", "avoid", "阿司匹林", 0.90),
        ])
        print(f"关联总数: {associations.total_count}")
        for a in associations.associations[:5]:
            print(f"  - {a.source} —{a.association_type.value}→ {a.target} (conf={a.confidence})")
    print()

    # 步骤3：构建增强后的查询
    print("=== 步骤3：构建增强查询 ===")
    enhanced_query = question
    try:
        expansions = (kg_enhancement.get("suggested_expansions", []) if isinstance(kg_enhancement, dict) else [])
        if expansions:
            enhanced_query += " " + " ".join(expansions[:3])
        association_terms = []
        if associations and getattr(associations, 'associations', None):
            for assoc in associations.associations[:5]:
                association_terms.extend([assoc.source, assoc.target])
        if association_terms:
            enhanced_query = f"{enhanced_query} " + " ".join(sorted(set(association_terms)))
        print("增强后的查询:", enhanced_query)
    except Exception as e:
        print("❌ 构建增强查询失败:", e)
    print()

    # 步骤4：向量索引检索（增强索引服务）
    print("=== 步骤4：增强索引检索 ===")
    try:
        from services.enhanced_index_service import enhanced_index_service
        search_res = enhanced_index_service.search_medical_documents(
            query=enhanced_query,
            department=department.value,
            document_type=document_type.value,
            disease_category=disease_category.value,
            k=5
        )
        print("检索状态:", search_res.get("ok"))
        print("总命中:", search_res.get("total_found"))
        print("过滤条件:", search_res.get("filters"))
        results = search_res.get("results", [])
        print(f"结果数: {len(results)}")
        for i, item in enumerate(results[:3], 1):
            preview = (item.get("text") or "").strip()
            if len(preview) > 200:
                preview = preview[:200] + "..."
            print(f"  - Top{i} 分数: {item.get('score')} | 元数据: {item.get('metadata')}\n    片段: {preview}")
    except Exception as e:
        print("❌ 索引检索失败或依赖未安装，使用内置Stub：", e)
        search_res = {
            "ok": True,
            "total_found": 2,
            "filters": {
                "department": department.value,
                "document_type": document_type.value,
                "disease_category": disease_category.value,
            },
            "results": [
                {
                    "score": 0.12,
                    "metadata": {"source": "儿科健康手册", "department": department.value, "document_type": document_type.value},
                    "text": "儿童感冒多为病毒性，自限性疾病。补液、休息、监测体温，必要时使用退烧药如对乙酰氨基酚。避免使用阿司匹林。",
                },
                {
                    "score": 0.18,
                    "metadata": {"source": "国家临床指南-上呼吸道感染", "department": department.value, "document_type": document_type.value},
                    "text": "对症治疗为主：咳嗽、流涕可使用适龄剂量的止咳祛痰药物，注意药品标签。体温≥38.5℃可考虑退热，物理降温辅助。",
                },
            ],
        }
        print("检索状态:", search_res.get("ok"))
        print("总命中:", search_res.get("total_found"))
        print("过滤条件:", search_res.get("filters"))
        results = search_res.get("results", [])
        print(f"结果数: {len(results)}")
        for i, item in enumerate(results[:3], 1):
            preview = (item.get("text") or "").strip()
            if len(preview) > 200:
                preview = preview[:200] + "..."
            print(f"  - Top{i} 分数: {item.get('score')} | 元数据: {item.get('metadata')}\n    片段: {preview}")
    print()

    # 步骤5：完整RAG检索（含KG增强与关联融合）
    print("=== 步骤5：RAG检索整合输出 ===")
    try:
        from services.enhanced_rag_service import enhanced_rag_service
        citations, context_text, metadata = await enhanced_rag_service.medical_retrieve(
            question=question,
            department=department,
            document_type=document_type,
            disease_category=disease_category
        )
        print("引用数量:", len(citations))
        print("上下文长度:", len(context_text))
        print("KG增强信息:", (metadata or {}).get("kg_enhancement"))
        print("元数据摘要:", {k: metadata.get(k) for k in ["total_results", "departments", "document_types", "medical_associations"] if k in metadata})
        if citations:
            print("=== 引用详情（前3个） ===")
            for i, citation in enumerate(citations[:3], 1):
                snippet = (citation.get('snippet') or '').strip()
                if len(snippet) > 200:
                    snippet = snippet[:200] + '...'
                print(f"  - 引用{i}: 分数={citation.get('score')} 科室={citation.get('department')} 文档类型={citation.get('document_type')} 来源={citation.get('source')}\n    片段: {snippet}")
        else:
            print("❌ 没有找到相关文档")
        if context_text:
            ctx_preview = context_text.strip()
            if len(ctx_preview) > 500:
                ctx_preview = ctx_preview[:500] + "..."
            print("=== 上下文预览 ===")
            print(ctx_preview)
        else:
            print("❌ 没有上下文文本")
    except Exception as e:
        print("❌ RAG检索失败或依赖未安装，使用内置Stub：", e)
        # 使用前面步骤的结果构造一个可读的RAG输出
        citations = [
            {
                "score": 0.12,
                "department": department.value,
                "document_type": document_type.value,
                "source": "国家临床指南-上呼吸道感染",
                "snippet": "儿童感冒为自限性，以对症治疗为主；≥38.5℃可考虑退热，对乙酰氨基酚优先。",
            },
            {
                "score": 0.18,
                "department": department.value,
                "document_type": document_type.value,
                "source": "儿科健康手册",
                "snippet": "避免使用阿司匹林；充分补液与休息，监测体温与精神状态。",
            },
        ]
        context_text = (
            "基于知识图谱的扩展建议：" + ", ".join(kg_enhancement.get("suggested_expansions", [])) + "。\n" +
            "常见关联：" + ", ".join({f"{a.source}-{a.association_type.value}-{a.target}" for a in associations.associations}) + "。\n" +
            "检索预览：\n- " + "\n- ".join([r["text"] for r in search_res.get("results", [])])
        )
        metadata = {
            "total_results": len(search_res.get("results", [])),
            "departments": [department.value],
            "document_types": [document_type.value],
            "kg_enhancement": kg_enhancement,
            "medical_associations": [
                {"source": a.source, "type": a.association_type.value, "target": a.target, "confidence": a.confidence}
                for a in associations.associations
            ],
        }
        print("引用数量:", len(citations))
        print("上下文长度:", len(context_text))
        print("KG增强信息:", (metadata or {}).get("kg_enhancement"))
        print("元数据摘要:", {k: metadata.get(k) for k in ["total_results", "departments", "document_types", "medical_associations"] if k in metadata})
        if citations:
            print("=== 引用详情（前3个） ===")
            for i, citation in enumerate(citations[:3], 1):
                snippet = (citation.get('snippet') or '').strip()
                if len(snippet) > 200:
                    snippet = snippet[:200] + '...'
                print(f"  - 引用{i}: 分数={citation.get('score')} 科室={citation.get('department')} 文档类型={citation.get('document_type')} 来源={citation.get('source')}\n    片段: {snippet}")
        else:
            print("❌ 没有找到相关文档")
        if context_text:
            ctx_preview = context_text.strip()
            if len(ctx_preview) > 500:
                ctx_preview = ctx_preview[:500] + "..."
            print("=== 上下文预览 ===")
            print(ctx_preview)
        else:
            print("❌ 没有上下文文本")

    # 可选：知识图谱统计
    print()
    print("=== 步骤6：知识图谱统计 ===")
    try:
        from services.medical_knowledge_graph import kg_service
        stats = await kg_service.get_knowledge_graph_stats()
        print("实体总数:", stats.get("total_entities"))
        print("关系总数:", stats.get("total_relations"))
        print("类型分布:", stats.get("entity_types"))
        print("关系类型分布:", stats.get("relation_types"))
    except Exception as e:
        print("❌ 获取KG统计失败或依赖未安装，使用内置Stub：", e)
        # 使用步骤1里定义的 FakeKGService（如有）
        try:
            stats = await kg_service.get_knowledge_graph_stats()  # 如果 kg_service 是 FakeKGService，会成功
            print("实体总数:", stats.get("total_entities"))
            print("关系总数:", stats.get("total_relations"))
            print("类型分布:", stats.get("entity_types"))
            print("关系类型分布:", stats.get("relation_types"))
        except Exception:
            print("❌ 无法获取统计信息")

if __name__ == "__main__":
    asyncio.run(test_medical_retrieve())