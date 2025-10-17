#!/usr/bin/env python3
"""检查知识图谱内容的脚本"""

import pickle
import os
import sys

def check_kg_content():
    """检查知识图谱文件内容"""
    kg_path = "/Users/jinlingxiao/Downloads/RAGAgent/backend/data/medical_knowledge_graph.pkl"
    
    if not os.path.exists(kg_path):
        print(f"知识图谱文件不存在: {kg_path}")
        return
    
    try:
        with open(kg_path, 'rb') as f:
            kg_data = pickle.load(f)
        
        print(f"知识图谱文件大小: {os.path.getsize(kg_path)} bytes")
        print(f"知识图谱数据类型: {type(kg_data)}")
        
        if hasattr(kg_data, 'entities'):
            print(f"实体数量: {len(kg_data.entities)}")
            if kg_data.entities:
                print("前5个实体:")
                for i, (entity_id, entity) in enumerate(list(kg_data.entities.items())[:5]):
                    print(f"  {i+1}. ID: {entity_id}, 名称: {entity.name}, 类型: {entity.entity_type}")
            else:
                print("知识图谱中没有实体数据")
        
        if hasattr(kg_data, 'graph'):
            print(f"图节点数量: {kg_data.graph.number_of_nodes()}")
            print(f"图边数量: {kg_data.graph.number_of_edges()}")
        
        # 检查是否有统计信息方法
        if hasattr(kg_data, 'get_statistics'):
            stats = kg_data.get_statistics()
            print("知识图谱统计信息:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"读取知识图谱文件时出错: {e}")

if __name__ == "__main__":
    check_kg_content()