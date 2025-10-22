# services/neo4j_adapter.py
from __future__ import annotations
import os
import json
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import asdict
import asyncio
from collections import defaultdict

# 尝试导入Neo4j，如果失败则设置标志
try:
    from neo4j import GraphDatabase, Driver
    from neo4j.exceptions import ServiceUnavailable, AuthError
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    GraphDatabase = None
    Driver = None

from .medical_knowledge_graph import (
    MedicalEntity, MedicalRelation, EntityType, RelationType
)

class Neo4jAdapter:
    """Neo4j图数据库适配器，提供与NetworkX兼容的接口"""
    
    def __init__(self, uri: str = None, username: str = None, password: str = None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = username or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.driver: Optional[Driver] = None
        self.connected = False
        
        if NEO4J_AVAILABLE:
            self._connect()
    
    def _connect(self):
        """连接到Neo4j数据库"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password)
            )
            # 测试连接
            with self.driver.session() as session:
                session.run("RETURN 1")
            self.connected = True
            print(f"Successfully connected to Neo4j at {self.uri}")
        except (ServiceUnavailable, AuthError, Exception) as e:
            print(f"Failed to connect to Neo4j: {e}")
            self.connected = False
            if self.driver:
                self.driver.close()
                self.driver = None
    
    def is_available(self) -> bool:
        """检查Neo4j是否可用"""
        return NEO4J_AVAILABLE and self.connected and self.driver is not None
    
    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
            self.connected = False
    
    def add_entity(self, entity: MedicalEntity) -> bool:
        """添加实体到Neo4j"""
        if not self.is_available():
            return False
        
        try:
            with self.driver.session() as session:
                query = """
                MERGE (e:Entity {id: $id})
                SET e.name = $name,
                    e.entity_type = $entity_type,
                    e.aliases = $aliases,
                    e.description = $description,
                    e.confidence = $confidence,
                    e.attributes = $attributes
                """
                session.run(query, {
                    "id": entity.id,
                    "name": entity.name,
                    "entity_type": entity.entity_type.value,
                    "aliases": entity.aliases,
                    "description": entity.description,
                    "confidence": entity.confidence,
                    "attributes": json.dumps(entity.attributes)
                })
            return True
        except Exception as e:
            print(f"Error adding entity to Neo4j: {e}")
            return False
    
    def add_relation(self, relation: MedicalRelation) -> bool:
        """添加关系到Neo4j"""
        if not self.is_available():
            return False
        
        try:
            with self.driver.session() as session:
                query = """
                MATCH (source:Entity {id: $source_id})
                MATCH (target:Entity {id: $target_id})
                MERGE (source)-[r:RELATES {type: $relation_type}]->(target)
                SET r.confidence = $confidence,
                    r.evidence = $evidence,
                    r.attributes = $attributes
                """
                session.run(query, {
                    "source_id": relation.source_id,
                    "target_id": relation.target_id,
                    "relation_type": relation.relation_type.value,
                    "confidence": relation.confidence,
                    "evidence": relation.evidence,
                    "attributes": json.dumps(relation.attributes)
                })
            return True
        except Exception as e:
            print(f"Error adding relation to Neo4j: {e}")
            return False
    
    def find_entities_by_name(self, name: str, fuzzy: bool = True) -> List[MedicalEntity]:
        """根据名称查找实体"""
        if not self.is_available():
            return []
        
        try:
            with self.driver.session() as session:
                if fuzzy:
                    query = """
                    MATCH (e:Entity)
                    WHERE toLower(e.name) CONTAINS toLower($name)
                       OR any(alias IN e.aliases WHERE toLower(alias) CONTAINS toLower($name))
                    RETURN e
                    """
                else:
                    query = """
                    MATCH (e:Entity)
                    WHERE toLower(e.name) = toLower($name)
                       OR toLower($name) IN [alias IN e.aliases | toLower(alias)]
                    RETURN e
                    """
                
                result = session.run(query, {"name": name})
                entities = []
                
                for record in result:
                    node = record["e"]
                    entity = MedicalEntity(
                        id=node["id"],
                        name=node["name"],
                        entity_type=EntityType(node["entity_type"]),
                        aliases=node.get("aliases", []),
                        description=node.get("description", ""),
                        confidence=node.get("confidence", 1.0),
                        attributes=json.loads(node.get("attributes", "{}"))
                    )
                    entities.append(entity)
                
                return entities
        except Exception as e:
            print(f"Error finding entities by name: {e}")
            return []
    
    def find_entities_by_type(self, entity_type: EntityType) -> List[MedicalEntity]:
        """根据类型查找实体"""
        if not self.is_available():
            return []
        
        try:
            with self.driver.session() as session:
                query = """
                MATCH (e:Entity {entity_type: $entity_type})
                RETURN e
                """
                result = session.run(query, {"entity_type": entity_type.value})
                entities = []
                
                for record in result:
                    node = record["e"]
                    entity = MedicalEntity(
                        id=node["id"],
                        name=node["name"],
                        entity_type=EntityType(node["entity_type"]),
                        aliases=node.get("aliases", []),
                        description=node.get("description", ""),
                        confidence=node.get("confidence", 1.0),
                        attributes=json.loads(node.get("attributes", "{}"))
                    )
                    entities.append(entity)
                
                return entities
        except Exception as e:
            print(f"Error finding entities by type: {e}")
            return []
    
    def get_related_entities(
        self, 
        entity_id: str, 
        relation_types: Optional[List[RelationType]] = None,
        max_depth: int = 2
    ) -> Dict[str, List[Tuple[MedicalEntity, RelationType, float]]]:
        """获取相关实体"""
        if not self.is_available():
            return {}
        
        try:
            with self.driver.session() as session:
                # 构建关系类型过滤条件
                type_filter = ""
                if relation_types:
                    type_values = [rt.value for rt in relation_types]
                    type_filter = f"AND r.type IN {type_values}"
                
                query = f"""
                MATCH path = (start:Entity {{id: $entity_id}})-[r:RELATES*1..{max_depth}]-(related:Entity)
                WHERE true {type_filter}
                RETURN related, r, length(path) as depth
                """
                
                result = session.run(query, {"entity_id": entity_id})
                related = defaultdict(list)
                
                for record in result:
                    node = record["related"]
                    relations = record["r"]
                    depth = record["depth"]
                    
                    # 获取最后一个关系的信息
                    last_rel = relations[-1] if isinstance(relations, list) else relations
                    
                    entity = MedicalEntity(
                        id=node["id"],
                        name=node["name"],
                        entity_type=EntityType(node["entity_type"]),
                        aliases=node.get("aliases", []),
                        description=node.get("description", ""),
                        confidence=node.get("confidence", 1.0),
                        attributes=json.loads(node.get("attributes", "{}"))
                    )
                    
                    rel_type = RelationType(last_rel["type"])
                    confidence = last_rel.get("confidence", 0.0)
                    
                    related[f"depth_{depth}"].append((entity, rel_type, confidence))
                
                return dict(related)
        except Exception as e:
            print(f"Error getting related entities: {e}")
            return {}
    
    def find_shortest_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        """查找最短路径"""
        if not self.is_available():
            return None
        
        try:
            with self.driver.session() as session:
                query = """
                MATCH path = shortestPath((source:Entity {id: $source_id})-[*]-(target:Entity {id: $target_id}))
                RETURN [node IN nodes(path) | node.id] as path
                """
                result = session.run(query, {
                    "source_id": source_id,
                    "target_id": target_id
                })
                
                record = result.single()
                return record["path"] if record else None
        except Exception as e:
            print(f"Error finding shortest path: {e}")
            return None
    
    def get_entity_neighbors(self, entity_id: str, relation_type: Optional[RelationType] = None) -> List[MedicalEntity]:
        """获取实体的邻居"""
        if not self.is_available():
            return []
        
        try:
            with self.driver.session() as session:
                type_filter = ""
                if relation_type:
                    type_filter = f"AND r.type = '{relation_type.value}'"
                
                query = f"""
                MATCH (e:Entity {{id: $entity_id}})-[r:RELATES]-(neighbor:Entity)
                WHERE true {type_filter}
                RETURN DISTINCT neighbor
                """
                
                result = session.run(query, {"entity_id": entity_id})
                neighbors = []
                
                for record in result:
                    node = record["neighbor"]
                    entity = MedicalEntity(
                        id=node["id"],
                        name=node["name"],
                        entity_type=EntityType(node["entity_type"]),
                        aliases=node.get("aliases", []),
                        description=node.get("description", ""),
                        confidence=node.get("confidence", 1.0),
                        attributes=json.loads(node.get("attributes", "{}"))
                    )
                    neighbors.append(entity)
                
                return neighbors
        except Exception as e:
            print(f"Error getting entity neighbors: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取图统计信息"""
        if not self.is_available():
            return {}
        
        try:
            with self.driver.session() as session:
                # 获取实体数量
                entity_result = session.run("MATCH (e:Entity) RETURN count(e) as count")
                entity_count = entity_result.single()["count"]
                
                # 获取关系数量
                relation_result = session.run("MATCH ()-[r:RELATES]->() RETURN count(r) as count")
                relation_count = relation_result.single()["count"]
                
                # 获取实体类型分布
                type_result = session.run("""
                MATCH (e:Entity)
                RETURN e.entity_type as type, count(e) as count
                """)
                type_distribution = {record["type"]: record["count"] for record in type_result}
                
                return {
                    "total_entities": entity_count,
                    "total_relations": relation_count,
                    "entity_type_distribution": type_distribution,
                    "backend": "neo4j"
                }
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {}
    
    def clear_all(self):
        """清空所有数据"""
        if not self.is_available():
            return
        
        try:
            with self.driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
        except Exception as e:
            print(f"Error clearing Neo4j data: {e}")