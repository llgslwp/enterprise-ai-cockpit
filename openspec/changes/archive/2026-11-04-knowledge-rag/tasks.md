# Tasks

## 1. 环境与模型准备

- [x] 1.1 安装 LangChain 及解析依赖（`langchain`、`langchain-openai`、`langchain-community`、`sentence-transformers`、`pypdf`、`python-docx`），并写回 `requirements.txt`
- [x] 1.2 下载本地模型 BGE-M3（Embedding）与 bge-reranker-v2-m3（Rerank），验证可本地加载推理

## 2. 清除操作型智能助手

- [x] 2.1 删除 `modules/agent/engine.py` 操作型编排逻辑（意图识别 / 副作用确认 / 写回 / 排产触发）
- [x] 2.2 调整 `modules/agent/router.py`，移除操作型 `/chat` 入口，保留 LLM 抽象层
- [x] 2.3 更新 `main.py` 路由注册，验证生产 / 库存 / 质量模块不受影响

## 3. 文档加载与语义分块

- [x] 3.1 实现 `modules/knowledge/loaders.py`：解析 MD 与 Word 文字版素材（PDF/Excel 解析器预留接口），产出统一文档对象
- [x] 3.2 实现 `modules/knowledge/chunker.py`：按标题 / 段落 / 表格边界语义分块，并生成切片语义标注

## 4. 向量化与索引

- [x] 4.1 实现 `modules/knowledge/embedder.py`：用 BGE-M3 产出稠密 + 稀疏向量
- [x] 4.2 实现 `modules/knowledge/index.py`：numpy/JSON 落地向量 + 关键词（BM25）双索引，支持增量更新

## 5. 检索与重排

- [x] 5.1 实现 `modules/knowledge/retriever.py`：向量 + 关键词双路召回，RRF 融合排序
- [x] 5.2 实现 `modules/knowledge/reranker.py`：用 bge-reranker-v2-m3 对召回结果精排

## 6. 语义路由与 Query 改写

- [x] 6.1 实现知识域语义路由（生产工艺 / 作业指导书 / 行业标准），误判回落全库检索
- [x] 6.2 实现多轮 Query 改写（指代消解，如「它呢」→ 完整查询）

## 7. 生成链路与问答接口

- [x] 7.1 实现 `modules/knowledge/chain.py`：LangChain 检索生成链，回答附带来源引用
- [x] 7.2 实现知识库问答 API（流式 SSE），并验证返回回答 + 引用

## 8. 前端知识库页

- [x] 8.1 新增「知识库」对话页（流式输出 + 引用溯源展示）
- [x] 8.2 侧边栏与路由：用知识库页替换原智能助手入口

## 9. 评测

- [x] 9.1 实现 `modules/knowledge/eval.py`：检索（召回 / 命中）与生成质量评测指标
- [x] 9.2 构建评测问题集并跑通，产出量化评测报告

## 10. skill 集群

- [x] 10.1 建立知识库开发相关 WorkBuddy skill 集群（SKILL.md + references，配合 Glob/Grep 检索）

## 11. 端到端验收

- [x] 11.1 业务方实际打开「知识库」页提问，确认回答与引用可用，且生产 / 库存 / 质量模块回归正常
