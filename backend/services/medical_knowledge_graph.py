# services/medical_knowledge_graph.py
from __future__ import annotations
import json
import re
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import networkx as nx
from collections import defaultdict, Counter
import pickle
import os

class EntityType(Enum):
    """实体类型枚举"""
    DISEASE = "disease"
    SYMPTOM = "symptom"
    DRUG = "drug"
    TREATMENT = "treatment"
    ANATOMY = "anatomy"
    PROCEDURE = "procedure"
    GENE = "gene"
    PROTEIN = "protein"
    PATHOGEN = "pathogen"

class RelationType(Enum):
    """关系类型枚举"""
    CAUSES = "causes"  # 病因关系
    TREATS = "treats"  # 治疗关系
    SYMPTOM_OF = "symptom_of"  # 症状关系
    SIDE_EFFECT = "side_effect"  # 副作用关系
    INTERACTS_WITH = "interacts_with"  # 相互作用
    LOCATED_IN = "located_in"  # 位置关系
    PART_OF = "part_of"  # 部分关系
    ASSOCIATED_WITH = "associated_with"  # 关联关系
    CONTRAINDICATED = "contraindicated"  # 禁忌关系
    PREVENTS = "prevents"  # 预防关系

@dataclass
class MedicalEntity:
    """医疗实体"""
    id: str
    name: str
    entity_type: EntityType
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

@dataclass
class MedicalRelation:
    """医疗关系"""
    source_id: str
    target_id: str
    relation_type: RelationType
    confidence: float = 1.0
    evidence: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

class MedicalKnowledgeGraph:
    """医疗知识图谱"""
    
    def __init__(self, graph_path: Optional[str] = None):
        self.graph = nx.MultiDiGraph()
        self.entities: Dict[str, MedicalEntity] = {}
        self.entity_index: Dict[str, Set[str]] = defaultdict(set)  # name -> entity_ids
        self.type_index: Dict[EntityType, Set[str]] = defaultdict(set)  # type -> entity_ids
        self.graph_path = graph_path or "data/medical_knowledge_graph.pkl"
        
        # 预定义的医疗实体模式
        self.entity_patterns = {
            EntityType.DISEASE: [
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+disease|\s+syndrome|\s+disorder))\b',
                r'\b(癌症|肿瘤|炎症|感染|综合征|疾病)\b',
                r'\b([A-Z]{2,})\b'  # 缩写形式
            ],
            EntityType.SYMPTOM: [
                r'\b(疼痛|发热|咳嗽|头痛|恶心|呕吐|腹泻|便秘|失眠|疲劳)\b',
                r'\b(pain|fever|cough|headache|nausea|vomiting|diarrhea)\b'
            ],
            EntityType.DRUG: [
                r'\b([A-Z][a-z]+(?:cillin|mycin|prazole|statin|blocker))\b',
                r'\b(阿司匹林|青霉素|头孢|氨基糖苷|喹诺酮)\b'
            ],
            EntityType.ANATOMY: [
                r'\b(心脏|肝脏|肾脏|肺部|大脑|胃部|肠道)\b',
                r'\b(heart|liver|kidney|lung|brain|stomach|intestine)\b'
            ]
        }
        
        # 关系模式
        self.relation_patterns = {
            RelationType.CAUSES: [
                r'(\w+)\s+(?:causes?|leads?\s+to|results?\s+in)\s+(\w+)',
                r'(\w+)\s+(?:引起|导致|造成)\s+(\w+)'
            ],
            RelationType.TREATS: [
                r'(\w+)\s+(?:treats?|cures?|helps?\s+with)\s+(\w+)',
                r'(\w+)\s+(?:治疗|缓解|改善)\s+(\w+)'
            ],
            RelationType.SYMPTOM_OF: [
                r'(\w+)\s+(?:is\s+a\s+symptom\s+of|symptom\s+of)\s+(\w+)',
                r'(\w+)\s+(?:是|为)\s+(\w+)\s+(?:的症状|症状)'
            ]
        }
        
        self._load_graph()

    def _load_graph(self):
        """加载知识图谱"""
        if os.path.exists(self.graph_path):
            try:
                with open(self.graph_path, 'rb') as f:
                    data = pickle.load(f)
                    self.graph = data.get('graph', nx.MultiDiGraph())
                    self.entities = data.get('entities', {})
                    self._rebuild_indexes()
                print(f"Loaded medical knowledge graph with {len(self.entities)} entities")
            except Exception as e:
                print(f"Error loading knowledge graph: {e}")
                self._initialize_basic_graph()
        else:
            self._initialize_basic_graph()

    def _save_graph(self):
        """保存知识图谱"""
        try:
            os.makedirs(os.path.dirname(self.graph_path), exist_ok=True)
            data = {
                'graph': self.graph,
                'entities': self.entities
            }
            with open(self.graph_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            print(f"Error saving knowledge graph: {e}")

    def _rebuild_indexes(self):
        """重建索引"""
        self.entity_index.clear()
        self.type_index.clear()
        
        for entity_id, entity in self.entities.items():
            # 名称索引
            self.entity_index[entity.name.lower()].add(entity_id)
            for alias in entity.aliases:
                self.entity_index[alias.lower()].add(entity_id)
            
            # 类型索引
            self.type_index[entity.entity_type].add(entity_id)

    def _initialize_basic_graph(self):
        """初始化基础医疗知识图谱"""
        # 添加一些基础的医疗实体和关系
        basic_entities = [
            # 疾病
            MedicalEntity("disease_001", "高血压", EntityType.DISEASE, 
                         aliases=["hypertension", "高血压病"], 
                         description="血压持续升高的疾病"),
            MedicalEntity("disease_002", "糖尿病", EntityType.DISEASE, 
                         aliases=["diabetes", "糖尿病"], 
                         description="血糖代谢异常疾病"),
            MedicalEntity("disease_003", "冠心病", EntityType.DISEASE, 
                         aliases=["coronary heart disease", "CHD"], 
                         description="冠状动脉粥样硬化性心脏病"),
            
            # 症状
            MedicalEntity("symptom_001", "头痛", EntityType.SYMPTOM, 
                         aliases=["headache", "头疼"], 
                         description="头部疼痛症状"),
            MedicalEntity("symptom_002", "胸痛", EntityType.SYMPTOM, 
                         aliases=["chest pain", "胸部疼痛"], 
                         description="胸部疼痛症状"),
            MedicalEntity("symptom_003", "多饮", EntityType.SYMPTOM, 
                         aliases=["polydipsia", "口渴"], 
                         description="过度饮水症状"),
            
            # 药物
            MedicalEntity("drug_001", "阿司匹林", EntityType.DRUG, 
                         aliases=["aspirin", "ASA"], 
                         description="非甾体抗炎药"),
            MedicalEntity("drug_002", "二甲双胍", EntityType.DRUG, 
                         aliases=["metformin"], 
                         description="降糖药物"),
            MedicalEntity("drug_003", "硝酸甘油", EntityType.DRUG, 
                         aliases=["nitroglycerin"], 
                         description="血管扩张剂"),
        ]
        
        # 添加实体
        for entity in basic_entities:
            self.add_entity(entity)
        
        # 添加基础关系
        basic_relations = [
            # 症状关系
            MedicalRelation("symptom_001", "disease_001", RelationType.SYMPTOM_OF, 0.8),
            MedicalRelation("symptom_002", "disease_003", RelationType.SYMPTOM_OF, 0.9),
            MedicalRelation("symptom_003", "disease_002", RelationType.SYMPTOM_OF, 0.9),
            
            # 治疗关系
            MedicalRelation("drug_001", "disease_003", RelationType.TREATS, 0.8),
            MedicalRelation("drug_002", "disease_002", RelationType.TREATS, 0.9),
            MedicalRelation("drug_003", "disease_003", RelationType.TREATS, 0.8),
            
            # 关联关系
            MedicalRelation("disease_001", "disease_003", RelationType.ASSOCIATED_WITH, 0.7),
            MedicalRelation("disease_002", "disease_003", RelationType.ASSOCIATED_WITH, 0.6),
        ]
        
        for relation in basic_relations:
            self.add_relation(relation)
        
        self._save_graph()

    def add_entity(self, entity: MedicalEntity) -> bool:
        """添加实体"""
        try:
            self.entities[entity.id] = entity
            self.graph.add_node(entity.id, **entity.__dict__)
            
            # 更新索引
            self.entity_index[entity.name.lower()].add(entity.id)
            for alias in entity.aliases:
                self.entity_index[alias.lower()].add(entity.id)
            self.type_index[entity.entity_type].add(entity.id)
            
            return True
        except Exception as e:
            print(f"Error adding entity {entity.id}: {e}")
            return False

    def add_relation(self, relation: MedicalRelation) -> bool:
        """添加关系"""
        try:
            if relation.source_id not in self.entities or relation.target_id not in self.entities:
                return False
            
            self.graph.add_edge(
                relation.source_id, 
                relation.target_id,
                relation_type=relation.relation_type,
                confidence=relation.confidence,
                evidence=relation.evidence,
                **relation.attributes
            )
            return True
        except Exception as e:
            print(f"Error adding relation: {e}")
            return False

    def find_entities_by_name(self, name: str, fuzzy: bool = True) -> List[MedicalEntity]:
        """根据名称查找实体"""
        name_lower = name.lower()
        entity_ids = set()
        
        # 精确匹配
        if name_lower in self.entity_index:
            entity_ids.update(self.entity_index[name_lower])
        
        # 模糊匹配
        if fuzzy and not entity_ids:
            for indexed_name, ids in self.entity_index.items():
                if name_lower in indexed_name or indexed_name in name_lower:
                    entity_ids.update(ids)
        
        return [self.entities[entity_id] for entity_id in entity_ids if entity_id in self.entities]

    def find_entities_by_type(self, entity_type: EntityType) -> List[MedicalEntity]:
        """根据类型查找实体"""
        entity_ids = self.type_index.get(entity_type, set())
        return [self.entities[entity_id] for entity_id in entity_ids if entity_id in self.entities]

    def get_related_entities(
        self, 
        entity_id: str, 
        relation_types: Optional[List[RelationType]] = None,
        max_depth: int = 2
    ) -> Dict[str, List[Tuple[MedicalEntity, RelationType, float]]]:
        """获取相关实体"""
        if entity_id not in self.entities:
            return {}
        
        related = defaultdict(list)
        visited = set()
        
        def _traverse(current_id: str, depth: int):
            if depth > max_depth or current_id in visited:
                return
            
            visited.add(current_id)
            
            # 出边（当前实体指向其他实体）
            for target_id in self.graph.successors(current_id):
                if target_id in self.entities:
                    edges = self.graph[current_id][target_id]
                    for edge_data in edges.values():
                        rel_type = edge_data.get('relation_type')
                        confidence = edge_data.get('confidence', 0.0)
                        
                        if not relation_types or rel_type in relation_types:
                            related[f"depth_{depth}"].append((
                                self.entities[target_id], 
                                rel_type, 
                                confidence
                            ))
                            
                            if depth < max_depth:
                                _traverse(target_id, depth + 1)
            
            # 入边（其他实体指向当前实体）
            for source_id in self.graph.predecessors(current_id):
                if source_id in self.entities:
                    edges = self.graph[source_id][current_id]
                    for edge_data in edges.values():
                        rel_type = edge_data.get('relation_type')
                        confidence = edge_data.get('confidence', 0.0)
                        
                        if not relation_types or rel_type in relation_types:
                            related[f"depth_{depth}"].append((
                                self.entities[source_id], 
                                rel_type, 
                                confidence
                            ))
                            
                            if depth < max_depth:
                                _traverse(source_id, depth + 1)
        
        _traverse(entity_id, 1)
        return dict(related)

    def extract_entities_from_text(self, text: str) -> List[Tuple[str, EntityType, float]]:
        """从文本中提取医疗实体"""
        extracted = []
        text_lower = text.lower()
        
        # 基于已知实体的匹配
        for name, entity_ids in self.entity_index.items():
            if name in text_lower:
                for entity_id in entity_ids:
                    entity = self.entities[entity_id]
                    # 计算匹配置信度
                    confidence = len(name) / len(text_lower) * entity.confidence
                    extracted.append((entity.name, entity.entity_type, confidence))
        
        # 基于模式的提取
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    entity_name = match.group(1) if match.groups() else match.group(0)
                    confidence = 0.6  # 模式匹配的基础置信度
                    extracted.append((entity_name, entity_type, confidence))
        
        # 去重并排序
        unique_extracted = {}
        for name, entity_type, confidence in extracted:
            key = (name.lower(), entity_type)
            if key not in unique_extracted or unique_extracted[key][2] < confidence:
                unique_extracted[key] = (name, entity_type, confidence)
        
        return sorted(unique_extracted.values(), key=lambda x: x[2], reverse=True)

    def find_shortest_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        """查找两个实体间的最短路径"""
        try:
            if source_id not in self.graph or target_id not in self.graph:
                return None
            
            path = nx.shortest_path(self.graph, source_id, target_id)
            return path
        except nx.NetworkXNoPath:
            return None
        except Exception as e:
            print(f"Error finding path: {e}")
            return None

    def get_entity_neighbors(self, entity_id: str, relation_type: Optional[RelationType] = None) -> List[MedicalEntity]:
        """获取实体的邻居"""
        if entity_id not in self.graph:
            return []
        
        neighbors = []
        
        # 获取所有邻居节点
        neighbor_ids = set(self.graph.successors(entity_id)) | set(self.graph.predecessors(entity_id))
        
        for neighbor_id in neighbor_ids:
            if neighbor_id in self.entities:
                # 检查关系类型
                if relation_type:
                    # 检查出边
                    if neighbor_id in self.graph.successors(entity_id):
                        edges = self.graph[entity_id][neighbor_id]
                        if any(edge.get('relation_type') == relation_type for edge in edges.values()):
                            neighbors.append(self.entities[neighbor_id])
                    # 检查入边
                    elif neighbor_id in self.graph.predecessors(entity_id):
                        edges = self.graph[neighbor_id][entity_id]
                        if any(edge.get('relation_type') == relation_type for edge in edges.values()):
                            neighbors.append(self.entities[neighbor_id])
                else:
                    neighbors.append(self.entities[neighbor_id])
        
        return neighbors

    def get_statistics(self) -> Dict[str, Any]:
        """获取知识图谱统计信息"""
        stats = {
            "total_entities": len(self.entities),
            "total_relations": self.graph.number_of_edges(),
            "entity_types": {},
            "relation_types": {},
            "graph_density": nx.density(self.graph),
            "connected_components": nx.number_weakly_connected_components(self.graph)
        }
        
        # 实体类型统计
        for entity_type in EntityType:
            count = len(self.type_index.get(entity_type, set()))
            stats["entity_types"][entity_type.value] = count
        
        # 关系类型统计
        relation_counter = Counter()
        for _, _, edge_data in self.graph.edges(data=True):
            rel_type = edge_data.get('relation_type')
            if rel_type:
                relation_counter[rel_type.value] += 1
        
        stats["relation_types"] = dict(relation_counter)
        
        return stats

    def update_from_documents(self, documents: List[str]):
        """从文档中更新知识图谱"""
        new_entities = 0
        new_relations = 0
        
        for doc in documents:
            # 提取实体
            entities = self.extract_entities_from_text(doc)
            
            # 添加新实体
            for name, entity_type, confidence in entities:
                # 检查是否已存在
                existing = self.find_entities_by_name(name, fuzzy=False)
                if not existing:
                    entity_id = f"{entity_type.value}_{len(self.entities):06d}"
                    entity = MedicalEntity(
                        id=entity_id,
                        name=name,
                        entity_type=entity_type,
                        confidence=confidence
                    )
                    if self.add_entity(entity):
                        new_entities += 1
            
            # 提取关系（基于模式）
            for relation_type, patterns in self.relation_patterns.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, doc, re.IGNORECASE)
                    for match in matches:
                        if len(match.groups()) >= 2:
                            source_name = match.group(1)
                            target_name = match.group(2)
                            
                            source_entities = self.find_entities_by_name(source_name)
                            target_entities = self.find_entities_by_name(target_name)
                            
                            for source_entity in source_entities:
                                for target_entity in target_entities:
                                    relation = MedicalRelation(
                                        source_id=source_entity.id,
                                        target_id=target_entity.id,
                                        relation_type=relation_type,
                                        confidence=0.7,
                                        evidence=[doc[:200]]  # 保存证据片段
                                    )
                                    if self.add_relation(relation):
                                        new_relations += 1
        
        if new_entities > 0 or new_relations > 0:
            self._save_graph()
        
        return {
            "new_entities": new_entities,
            "new_relations": new_relations,
            "total_entities": len(self.entities),
            "total_relations": self.graph.number_of_edges()
        }

# 全局知识图谱实例
medical_kg = MedicalKnowledgeGraph()

class MedicalKnowledgeGraphService:
    """医疗知识图谱服务"""
    
    def __init__(self):
        self.kg = medical_kg
    
    async def enhance_query_with_kg(self, query: str) -> Dict[str, Any]:
        """使用知识图谱增强查询"""
        # 提取查询中的实体
        entities = self.kg.extract_entities_from_text(query)
        
        enhanced_info = {
            "original_query": query,
            "extracted_entities": [],
            "related_entities": [],
            "suggested_expansions": []
        }
        
        for name, entity_type, confidence in entities[:5]:  # 限制前5个实体
            # 查找匹配的实体
            matched_entities = self.kg.find_entities_by_name(name)
            
            for entity in matched_entities:
                entity_info = {
                    "name": entity.name,
                    "type": entity.entity_type.value,
                    "confidence": confidence,
                    "aliases": entity.aliases
                }
                enhanced_info["extracted_entities"].append(entity_info)
                
                # 获取相关实体
                related = self.kg.get_related_entities(entity.id, max_depth=1)
                for depth, relations in related.items():
                    for related_entity, rel_type, rel_confidence in relations[:3]:
                        enhanced_info["related_entities"].append({
                            "source": entity.name,
                            "target": related_entity.name,
                            "relation": rel_type.value,
                            "confidence": rel_confidence
                        })
                
                # 生成查询扩展建议
                neighbors = self.kg.get_entity_neighbors(entity.id)
                for neighbor in neighbors[:3]:
                    if neighbor.name.lower() not in query.lower():
                        enhanced_info["suggested_expansions"].append(neighbor.name)
        
        return enhanced_info
    
    async def find_entity_relationships(self, entity_name: str) -> Dict[str, Any]:
        """查找实体关系"""
        entities = self.kg.find_entities_by_name(entity_name)
        
        if not entities:
            return {"error": f"Entity '{entity_name}' not found"}
        
        entity = entities[0]  # 取第一个匹配的实体
        
        relationships = {
            "entity": {
                "name": entity.name,
                "type": entity.entity_type.value,
                "description": entity.description,
                "aliases": entity.aliases
            },
            "relationships": {}
        }
        
        # 获取各种类型的关系
        for rel_type in RelationType:
            related = self.kg.get_related_entities(entity.id, [rel_type], max_depth=1)
            if related:
                relationships["relationships"][rel_type.value] = []
                for depth, relations in related.items():
                    for related_entity, _, confidence in relations:
                        relationships["relationships"][rel_type.value].append({
                            "name": related_entity.name,
                            "type": related_entity.entity_type.value,
                            "confidence": confidence
                        })
        
        return relationships
    
    async def get_knowledge_graph_stats(self) -> Dict[str, Any]:
        """获取知识图谱统计信息"""
        return self.kg.get_statistics()
    
    async def update_kg_from_documents(self, documents: List[str]) -> Dict[str, Any]:
        """从文档更新知识图谱"""
        return self.kg.update_from_documents(documents)

# 全局服务实例
kg_service = MedicalKnowledgeGraphService()