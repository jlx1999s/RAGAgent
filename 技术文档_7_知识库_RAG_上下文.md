7. 知识库与RAG及上下文管理机制（后端技术设计）

目标：以知识库 + RAG + 多层上下文记忆实现高命中率、强上下文理解与个性化回答，适用于医疗/体检/慢病等复杂语义场景。仅涵盖后端实现与扩展规划，不涉及前端内容。

7.1 知识库分层结构设计
- 基础层（Static KB）：
  - 权威性事实来源：已解析的医疗指南（PDF→Markdown）、测试文档集与知识图谱。
  - 数据来源与路径：
    - 解析后的文档与索引由后端管理，详见 <mcfile name="enhanced_index_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/enhanced_index_service.py"></mcfile> 与 <mcfile name="pdf_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/pdf_service.py"></mcfile>
    - 知识图谱持久化：backend/data/medical_knowledge_graph.pkl，详见 <mcfile name="medical_knowledge_graph.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/medical_knowledge_graph.py"></mcfile>
    - 医疗术语词典：backend/data/medical_dict.txt（用于同义词/别名扩展）。
- 动态层（Dynamic KB）：
  - 个体数据与历史：会话历史与交互摘要由后端维护（内存态），用于短期上下文融合。
  - 现状：使用简单的会话内存结构，详见 <mcfile name="enhanced_rag_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/enhanced_rag_service.py"></mcfile> 的会话管理与检索融合。
- 融合层（Hybrid KB）：
  - 跨源知识融合：将知识图谱增强与医疗关联扩展加入检索阶段，形成多维检索增强与推荐。
  - 实现要点与元数据：通过医疗索引构建与查询接口传入类别元数据（科室、文档类型、疾病分类等），参见 <mcsymbol name="medical_index_build" filename="app.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/app.py" startline="408" type="function"></mcsymbol>、<mcsymbol name="medical_search" filename="app.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/app.py" startline="553" type="function"></mcsymbol>。

7.2 RAG 工作机制
- 检索层（Retriever）：
  - 使用增强医疗索引进行语义检索与命中文档片段，核心调用在医疗聊天入口中完成，参见 <mcsymbol name="medical_chat_stream" filename="app.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/app.py" startline="658" type="function"></mcsymbol>。
  - 结合知识图谱增强与医疗关联扩展：
    - KG增强：<mcsymbol name="enhance_query_with_kg" filename="medical_knowledge_graph.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/medical_knowledge_graph.py" startline="500" type="function"></mcsymbol>
    - 关联扩展：详见 <mcfile name="medical_association_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/medical_association_service.py"></mcfile>
  - 可选扩展（规划）：混合检索（BM25 + 向量检索）与 Reranker（cross-encoder）可在 <mcfile name="enhanced_index_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/enhanced_index_service.py"></mcfile> 增强后加入，以提升 Top-1 命中率。
- 融合层（Augmentation）：
  - 将命中的 citations 与上下文 text 聚合为受控长度的上下文块，并在检索阶段将 KG 增强与关联扩展术语拼接入查询，逻辑位于增强 RAG 服务中，参见 <mcfile name="enhanced_rag_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/enhanced_rag_service.py"></mcfile>。
  - 多源融合：通过医疗索引的元数据过滤（科室/文档类型/疾病分类）实现场景化召回，接口位于 <mcsymbol name="medical_search" filename="app.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/app.py" startline="553" type="function"></mcsymbol>。
- 生成层（Generation）：
  - 流式输出：SSE 事件包括 token/citation/done/error，详见通用与医疗 Chat 接口。
  - 医疗回答流：<mcsymbol name="medical_answer_stream" filename="enhanced_rag_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/enhanced_rag_service.py" startline="682" type="function"></mcsymbol>
  - 安全与意图：可选安全审查 <mcfile name="medical_safety_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/medical_safety_service.py"></mcfile> 与意图识别 <mcfile name="smart_intent_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/smart_intent_service.py"></mcfile> <mcfile name="qwen_intent_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/qwen_intent_service.py"></mcfile>。
- 高级扩展（Agent分层 RAG）：
  - 可按知识域划分多 Agent（如报告解读、风险评估），由中央调度统一协调检索与融合；该能力为架构规划，可在现有服务层之上演进实现。

7.3 上下文管理与记忆机制
- 短期记忆（Session Memory）：
  - 保存当前会话轮次的历史（内存结构），支持在生成阶段作为辅助上下文；接口引用：<mcsymbol name="get_medical_chat_history" filename="app.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/app.py" startline="847" type="function"></mcsymbol>、<mcsymbol name="medical_chat_clear" filename="app.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/app.py" startline="811" type="function"></mcsymbol>。
  - 现状：简单列表式历史；规划：按主题聚类与语义压缩形成滑动窗口记忆。
- 长期记忆（User Memory）：
  - 规划：以用户为中心维护体检记录、疾病风险轨迹、问答摘要等，采用向量化存储与相似度检索策略；可复用 <mcfile name="medical_vector_store.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/medical_vector_store.py"></mcfile> 能力并扩展用户维度的索引命名与检索策略。
- 主题与意图管理：
  - 通过意图识别模块识别话题与任务类型，作为检索过滤与回答风格的调控因子；参见 <mcfile name="medical_intent_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/medical_intent_service.py"></mcfile>、<mcfile name="smart_intent_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/smart_intent_service.py"></mcfile>、<mcfile name="qwen_intent_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/qwen_intent_service.py"></mcfile>。

7.4 知识库与记忆的联合推理（Hybrid Memory-RAG）
- 流程：
  1) 接收用户问题（医疗 Chat SSE 入口）→ 2) 同步调用 KG 增强 <mcsymbol name="enhance_query_with_kg" filename="medical_knowledge_graph.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/medical_knowledge_graph.py" startline="500" type="function"></mcsymbol> 与医疗关联扩展 → 3) 构造增强查询并进行医疗索引检索（按元数据过滤） → 4) 聚合 citations 与上下文 → 5) 结合 Session Memory（可选 User Memory）形成增强 Prompt → 6) 生成回答并进行安全审查与引用输出。
- 相关接口：
  - 医疗聊天：<mcsymbol name="medical_chat_stream" filename="app.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/app.py" startline="658" type="function"></mcsymbol>
  - 知识图谱统计/增强：<mcsymbol name="get_knowledge_graph_statistics" filename="app.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/app.py" startline="875" type="function"></mcsymbol>、<mcsymbol name="enhance_query_with_kg" filename="app.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/app.py" startline="893" type="function"></mcsymbol>
  - 医疗索引检索：<mcsymbol name="medical_search" filename="app.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/app.py" startline="553" type="function"></mcsymbol>

配置与参数（后端）
- RAG 检索参数：k（检索条数）、score_tau_top1/mean3（阈值）位于增强 RAG 服务配置中，参见 <mcfile name="enhanced_rag_service.py" path="/Users/jinlingxiao/Downloads/RAGAgent/backend/services/enhanced_rag_service.py"></mcfile>。
- 环境变量：HF_ENDPOINT/HUGGINGFACE_HUB_CACHE/TRANSFORMERS_CACHE/TIMM_CACHE_DIR（镜像与缓存）与 DASHSCOPE_API_KEY（模型与嵌入）。

实施建议
- 在医疗场景中持续丰富 static KB（指南、术语映射、KG 节点与关系），并以用户维度扩展 dynamic KB（画像与历史）；
- 引入混合检索与 Reranker，提升 Top-1 命中与稳定性；
- 在生成阶段强化来源引用与“不确定”响应策略，保障可信度与合规性。