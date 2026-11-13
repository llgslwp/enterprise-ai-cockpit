# Proposal

## Why

项目目标重新定位为「证明 Agent 应用开发能力」（可上 GitHub 的标杆案例）。现有人机对话是自研操作型智能助手（意图识别 → 触发写回/排产），不体现 LangChain 等主流 Agent 技术栈。本次用 LangChain 落地「人机对话 + 企业知识库（RAG + 语义理解）」，替换操作型助手，把项目核心展示点从「业务功能」转向「Agent 技术全面性」。

## What Changes

- **BREAKING**：清除现有操作型智能助手（`modules/agent/` 自研编排引擎的意图识别、副作用确认、写回/排产触发）。人机对话改为**纯知识库问答**，不再触发生产管理的任何操作。
- 新增 LangChain 知识库问答能力，覆盖完整 RAG 技术链：文档解析 → 清洗 → 语义分块 → Embedding → 向量 + BM25 双索引 → 混合检索 + RRF 融合 → Rerank → Query 改写 → 生成 + 引用溯源 → 评测。
- 知识范围：生产工艺 + 作业指导书 + 行业标准 + **公司制度**（人事行政类制度，迁移后新增）；文档格式：MD + PDF + Word + Excel（一期用文字版素材，扫描 PDF 的 OCR 留二期，Excel 仅留解析能力）。
- 语义理解四件套：语义分块、语义路由、Query 改写、切片语义标注。
- 技术选型（已单独提审确认）：Embedding = 本地 BGE-M3；向量存储 = 本地 numpy/JSON；Rerank = 本地 bge-reranker-v2-m3；LLM = DeepSeek（key 存 `.env`）。
- 用 WorkBuddy skill 集群组织开发能力（SKILL.md + references + Glob/Grep）。

## Capabilities

### New Capabilities
- `knowledge-base`: 企业知识库 RAG 问答能力——文档解析、语义分块、双索引混合检索、引用溯源生成。

### Modified Capabilities
- `agent-core`: 移除操作型意图识别与副作用执行，人机对话改为 LangChain 承载的纯知识库问答（云端大模型接入层保留）。

## Impact

- **删除代码**：`modules/agent/engine.py` 操作型编排逻辑（意图识别、副作用确认、写回/排产触发）；`modules/agent/router.py` 中操作型聊天入口。
- **新增代码**：`modules/knowledge/`（LangChain RAG 链路：加载 / 分块 / 索引 / 检索 / 生成）。
- **修改代码**：`main.py` 路由注册；前端「智能助手」入口改为「知识库」页。
- **新增依赖**：`langchain`、`langchain-openai`、`langchain-community`、`sentence-transformers`（BGE-M3 推理）、`pypdf`、`python-docx`、`openpyxl`（已有）。
- **数据**：`docs/产品工艺/` 文字版素材（5 MD + 1 docx）+ `docs/公司制度/`（4 个制度 docx，迁移后新增）；扫描 PDF（3 个，83 页）OCR 留二期；Excel 暂无素材、仅留能力。
- **配置**：`.env`（LLM_API_KEY 已配）、`.gitignore`（已建，排除密钥与缓存）。
