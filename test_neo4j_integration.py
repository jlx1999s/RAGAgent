#!/usr/bin/env python3
"""
测试Neo4j集成的脚本
验证知识图谱是否能正确使用Neo4j或回退到NetworkX
"""

import os
import sys

# 添加backend目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.medical_knowledge_graph import MedicalKnowledgeGraph, MedicalEntity, EntityType

def test_neo4j_integration():
    """测试Neo4j集成"""
    print("🧪 测试Neo4j知识图谱集成")
    print("=" * 50)
    
    # 测试1: 不设置Neo4j环境变量（应该使用NetworkX）
    print("\n📋 测试1: 默认配置（NetworkX回退）")
    kg1 = MedicalKnowledgeGraph()
    stats1 = kg1.get_statistics()
    print(f"后端类型: {stats1.get('backend', 'unknown')}")
    print(f"实体数量: {stats1.get('total_entities', 0)}")
    print(f"关系数量: {stats1.get('total_relations', 0)}")
    
    # 测试2: 设置Neo4j环境变量（尝试使用Neo4j）
    print("\n📋 测试2: 设置Neo4j环境变量")
    os.environ["NEO4J_URI"] = "bolt://localhost:7687"
    os.environ["NEO4J_USERNAME"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "password"
    
    kg2 = MedicalKnowledgeGraph()
    stats2 = kg2.get_statistics()
    print(f"后端类型: {stats2.get('backend', 'unknown')}")
    print(f"实体数量: {stats2.get('total_entities', 0)}")
    print(f"关系数量: {stats2.get('total_relations', 0)}")
    
    # 测试3: 强制使用Neo4j
    print("\n📋 测试3: 强制使用Neo4j")
    try:
        kg3 = MedicalKnowledgeGraph(use_neo4j=True)
        stats3 = kg3.get_statistics()
        print(f"后端类型: {stats3.get('backend', 'unknown')}")
        print(f"Neo4j连接状态: {'成功' if kg3.use_neo4j else '失败，已回退到NetworkX'}")
    except Exception as e:
        print(f"Neo4j连接失败: {e}")
    
    # 测试4: 强制使用NetworkX
    print("\n📋 测试4: 强制使用NetworkX")
    kg4 = MedicalKnowledgeGraph(use_neo4j=False)
    stats4 = kg4.get_statistics()
    print(f"后端类型: {stats4.get('backend', 'unknown')}")
    print(f"实体数量: {stats4.get('total_entities', 0)}")
    
    # 测试5: 添加实体测试
    print("\n📋 测试5: 添加实体功能测试")
    test_entity = MedicalEntity(
        id="test_entity_001",
        name="测试疾病",
        entity_type=EntityType.DISEASE,
        description="这是一个测试疾病实体"
    )
    
    success = kg2.add_entity(test_entity)
    print(f"添加实体结果: {'成功' if success else '失败'}")
    
    # 查找刚添加的实体
    found_entities = kg2.find_entities_by_name("测试疾病")
    print(f"查找实体结果: 找到 {len(found_entities)} 个实体")
    
    # 测试6: 依赖检查
    print("\n📋 测试6: 依赖检查")
    try:
        import neo4j
        print("✅ Neo4j Python驱动已安装")
        print(f"Neo4j驱动版本: {neo4j.__version__}")
    except ImportError:
        print("❌ Neo4j Python驱动未安装")
    
    try:
        import networkx
        print("✅ NetworkX已安装")
        print(f"NetworkX版本: {networkx.__version__}")
    except ImportError:
        print("❌ NetworkX未安装")
    
    print("\n🎯 测试完成")
    print("=" * 50)
    
    # 清理环境变量
    if "NEO4J_URI" in os.environ:
        del os.environ["NEO4J_URI"]
    if "NEO4J_USERNAME" in os.environ:
        del os.environ["NEO4J_USERNAME"]
    if "NEO4J_PASSWORD" in os.environ:
        del os.environ["NEO4J_PASSWORD"]

if __name__ == "__main__":
    test_neo4j_integration()