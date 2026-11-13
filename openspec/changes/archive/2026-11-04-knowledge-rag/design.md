# Design

## Context

现有后端 FastAPI + 前端 Vue3，`modules/agent/` 是自研操作型编排引擎（意图识别 → 写回/排产），`modules/agent/llm.py` 是 OpenAI 兼容抽象层（默认 DeepSeek）。项目无数据库、纯文件。知识库素材在 `docs/产品工艺/`（文字版 5 MD + 1 docx；扫描版 3 PDF 留二期）。动机见 proposal.md - Why。

## Goals / Non-Goals

**Goals:**
- 用 LangChain 落地「人机对话 + 知识库 RAG」，覆盖完整技术链并做到可上 GitHub 的展示级。
- 知识库问答可独立运行、可评测，引用可溯源。
- 清除操作型助手，代码边界清晰（`modules/knowledge/` 独立成模块）。

**Non-Goals:**
- 一期不做扫描 PDF 的 OCR（83 页扫描件留二期）。
- 一期不做图片 / 视频 / 音频解析。
- 人机对话不触发任何生产管理写操作。

## Decisions

1. **框架选 LangChain**（langchain-core + langchain-openai + langchain-community）替代自研编排。理由：对齐「证明主流 Agent 技术栈」目标。备选：LangGraph（重状态图，一期链路是直线，用不上）、Dify（低代码，不展示代码能力）。
2. **Embedding = 本地 BGE-M3**：三合一模型，一次推理同时产出稠密 + 稀疏向量（稀疏即类 BM25），与「向量 + BM25 双索引」定位契合。备选：云 embedding（数据出域 + 按量计费）。代价：约 2GB 模型，需下载（用 hf-mirror 镜像）。
3. **向量存储 = numpy/JSON**：纯文件，符合无数据库架构，千行文档量级够用，代码透明利于展示。备选：Chroma（引入服务/依赖）、FAISS（C++ 依赖重）。
4. **Rerank = bge-reranker-v2-m3**：cross-encoder 精排，中文事实标准，补齐技术链（DeepSeek 无 rerank 接口）。备选：省略 rerank（少一环）。
5. **文档解析 = LangChain Loader 封装**：MD 用 TextLoader、PDF 用 PyPDF/fitz、Word 用 python-docx、Excel 用 openpyxl。
6. **语义分块**：MD/Word/PDF 按标题 / 段落边界切（RecursiveCharacterTextSplitter 调分隔符，保留语义完整）；Excel 按行 / 表切（不按段落）。
7. **语义路由 = LLM 分类**：把问题分到「生产工艺 / 作业指导书 / 行业标准」子库，先粗筛再全库兜底，误判时回落全库检索。
8. **Query 改写 = LLM 指代消解**：多轮对话把「它呢」改写为完整独立 query。
9. **模块结构**：`modules/knowledge/` 拆 `loaders / chunker / embedder / index / retriever / reranker / router / chain / eval`，职责单一、逐环节可验证。
10. **前端**：新增「知识库」页（对话流 + 引用溯源展示），替换原智能助手入口。

## Risks / Trade-offs

- [BGE-M3 下载慢 / 需镜像] → 用 hf-mirror.com 镜像，模型本地缓存。
- [本地模型加载耗时] → 懒加载 + 首次加载后常驻。
- [扫描 PDF 无文字层] → 一期只用文字版素材，扫描件明确标注二期 OCR。
- [DeepSeek 无 embedding / rerank] → 本地 BGE 补齐，已在决策 2/4 处理。
- [语义路由误判] → 允许 fallback 到全库检索，不因路由错误丢答案。

## Migration Plan

1. 清除 `modules/agent/` 操作型逻辑（engine.py 编排、router.py 操作入口），保留 llm.py 抽象层。
2. 新增 `modules/knowledge/` RAG 链路，按 spec 逐环实现并单测。
3. 前端「智能助手」入口改为「知识库」页。
4. 建 WorkBuddy skill 集群沉淀开发能力（详见 tasks）。
5. 回滚：操作型助手代码在 git 未提交前可撤销；本期尚未 git 化，保留改动前快照。
