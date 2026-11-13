"""企业知识库 RAG 模块（knowledge-base 能力）。

基于 LangChain 落地的检索增强问答链路：
解析 → 语义分块 → 向量化 → 双索引 → 混合检索 → Rerank → Query 改写 → 生成 + 引用溯源。

模块职责单一、逐环节可独立验证：
- loaders   文档解析（MD/Word 一期，PDF/Excel 预留接口）
- chunker   语义分块 + 切片语义标注
- embedder  BGE-M3 稠密向量
- index     numpy/JSON 双索引（稠密向量 + BM25 关键词）
- retriever 双路召回 + RRF 融合
- reranker  bge-reranker-v2-m3 精排
- router    知识域语义路由 + 多轮 Query 改写
- chain     LangChain 检索生成链（带来源引用）
- eval      检索 / 生成质量评测
"""
