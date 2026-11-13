"""LangChain 检索生成链 + 知识库问答服务（knowledge-base 能力）。

LangChain 实际使用点：
- ChatOpenAI：OpenAI 兼容客户端接 DeepSeek（langchain-openai）
- BaseRetriever：自定义检索器（混合检索 + Rerank），走 LangChain 标准 invoke 接口
- Document / ChatPromptTemplate：统一文档载体与提示词模板
- LCEL（| 管道）：声明式组装检索生成链（见 build_lcel_chain）
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_openai import ChatOpenAI
from pydantic import ConfigDict

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, TOP_K_RECALL, TOP_K_RERANK
from .index import load_index
from .reranker import rerank
from .retriever import hybrid_search
from .router import rewrite_query, route_domain, is_offtopic

# 检索兜底阈值：rerank 最高分低于此值，视为「知识库无相关内容」，才触发离题判定。
# cross-encoder 输出为 logit，正值=相关、负值=不相关，0 是自然分界。
# 取 -0.5 作保守下限，宁可放行不可误杀（离题判断本身已经很宽松）。
_RERANK_RELEVANCE_FLOOR = -0.5

_SYSTEM = (
    "你是「企业AI驾驶舱」的知识库助手，回答管钳生产工艺、作业指导书、行业标准相关问题。\n"
    "规则：\n"
    "1. 只依据【资料片段】回答，不得编造资料之外的内容；\n"
    "2. 资料不足以回答时，明确说「资料中未找到相关内容」，不要硬编；\n"
    "3. 回答引用资料时，用 [1][2] 等编号标注出处；\n"
    "4. 用简洁、结构化的中文回答。\n"
    "5. 输出格式：涉及多项对比、规格清单、工序步骤、配件明细等内容时，必须用 Markdown 表格呈现"
    "（竖线分隔的规范表格，含表头行和分隔行，例如 `| 规格 | 特点 |` 加 `|---|---|`），不要用空格对齐的伪表格或纯文本堆砌；"
    "其余说明性内容用简短段落或列表。"
)

# 元问题/寒暄关键词：命中则跳过检索，直接由 LLM 回答（避免无谓加载模型、检索）
_META_KEYWORDS = (
    "你是谁", "你叫什么", "你能做什么", "你会什么", "你会干嘛", "你能干嘛",
    "你有什么功能", "介绍一下你", "自我介绍", "你是什么", "你好", "在吗",
)

# 离题拒答文案（与 is_offtopic 的知识库范围描述保持一致，覆盖三类）
_OFFTOPIC_TEXT = (
    "这个问题超出了本知识库的范围。本知识库仅覆盖：\n"
    "1) 管钳/自由钳产品的生产工艺、作业指导书、行业标准；\n"
    "2) 宏润机具的公司制度（考勤/请假/报销/薪酬/考核/岗位职责/离职/人事行政）；\n"
    "3) 行业标准、术语原理、品牌建设、市场推广等通用知识。\n"
    "请在上述范围内提问。"
)


def _llm(temperature: float = 0.2) -> ChatOpenAI:
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=temperature,
    )


def _is_meta(question: str) -> bool:
    """判断是否为寒暄/身份/能力类元问题（无需检索知识库）。"""
    q = question.strip()
    if len(q) > 20:
        return False
    return any(k in q for k in _META_KEYWORDS)


class KnowledgeRetriever(BaseRetriever):
    """LangChain 自定义检索器：混合检索（稠密 + BM25 + RRF）→ Rerank，支持知识域过滤。"""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")
    domain_filter: str | None = None

    def __init__(self, meta, dense, bm25, domain_filter: str | None = None):
        super().__init__(domain_filter=domain_filter)
        # 非 pydantic 友好类型（list/dict、numpy 数组、BM25 实例）用 object.__setattr__ 绕过校验
        object.__setattr__(self, "_meta", meta)
        object.__setattr__(self, "_dense", dense)
        object.__setattr__(self, "_bm25", bm25)

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        fused = hybrid_search(query, self._dense, self._bm25, top_k=TOP_K_RECALL)
        cand_ids = [i for i, _ in fused]

        # 知识域过滤 + 兜底：该域结果不足 3 条时回落全库（避免路由误判丢答案）
        if self.domain_filter:
            domain_ids = [i for i in cand_ids if self._meta[i]["metadata"].get("domain") == self.domain_filter]
            if len(domain_ids) >= 3:
                cand_ids = domain_ids

        # Rerank 精排
        cand_texts = [self._meta[i]["page_content"] for i in cand_ids]
        ranked = rerank(query, cand_texts, top_k=TOP_K_RERANK)

        docs: list[Document] = []
        for local_i, score in ranked:
            global_i = cand_ids[local_i]
            m = self._meta[global_i]
            doc = Document(page_content=m["page_content"], metadata=dict(m["metadata"]))
            doc.metadata["rerank_score"] = round(score, 4)
            docs.append(doc)
        return docs


def _format_context(docs: list[Document]) -> str:
    parts = []
    for i, d in enumerate(docs, 1):
        title = d.metadata.get("title", "未知")
        domain = d.metadata.get("domain", "")
        path = d.metadata.get("title_path", "")
        parts.append(f"[{i}]（来源：{title}｜{domain}｜{path}）\n{d.page_content}")
    return "\n\n".join(parts)


def _build_messages(question: str, docs: list[Document]) -> list[dict]:
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"资料片段：\n{_format_context(docs)}\n\n用户问题：{question}"},
    ]


class KnowledgeQA:
    """知识库问答服务：Query 改写 → 语义路由 → 检索 → 生成（同步 + 流式）。"""

    def __init__(self):
        self._meta, self._dense, self._bm25 = load_index()
        self._llm = _llm()
        self.retriever = KnowledgeRetriever(self._meta, self._dense, self._bm25)

    def _prepare(self, question: str, history: list[dict] | None):
        history = history or []
        rewritten = rewrite_query(question, history, self._llm)
        domain = route_domain(rewritten, self._llm)
        self.retriever.domain_filter = domain
        docs = self.retriever.invoke(rewritten)
        return rewritten, domain, docs

    @staticmethod
    def _empty(docs: list[Document]) -> bool:
        """判断检索结果是否「无相关内容」（用于检索兜底）。

        返回 True 当：无任何切片，或 rerank 最高分低于兜底阈值（说明知识库确实
        没有与问题相关的内容）。有相关内容返回 False，直接放行生成。
        """
        if not docs:
            return True
        top = max((d.metadata.get("rerank_score", 0.0) or 0.0) for d in docs)
        return top < _RERANK_RELEVANCE_FLOOR

    def _sources(self, docs: list[Document]) -> list[dict]:
        return [
            {
                "index": i,
                "title": d.metadata.get("title", ""),
                "domain": d.metadata.get("domain", ""),
                "title_path": d.metadata.get("title_path", ""),
                "source": d.metadata.get("source", ""),
                "score": d.metadata.get("rerank_score"),
                "snippet": d.page_content[:200],
            }
            for i, d in enumerate(docs, 1)
        ]

    def answer(self, question: str, history: list[dict] | None = None) -> dict:
        # 元问题/寒暄：跳过检索，直接由 LLM 自我介绍
        if _is_meta(question):
            resp = self._llm.invoke(
                [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": question}]
            )
            return {
                "answer": resp.content,
                "sources": [],
                "rewritten": question,
                "domain": None,
                "meta": True,
            }
        # 检索兜底：先检索，用结果说话——有相关内容直接放行；仅当检索无相关内容时，
        # 才兜底走离题判定（此时知识库确实没有答案，判定是否该拒答）。
        rewritten, domain, docs = self._prepare(question, history)
        if self._empty(docs):
            if is_offtopic(question, self._llm):
                return {
                    "answer": _OFFTOPIC_TEXT,
                    "sources": [],
                    "rewritten": question,
                    "domain": None,
                    "offtopic": True,
                }
        resp = self._llm.invoke(_build_messages(rewritten, docs))
        return {
            "answer": resp.content,
            "sources": self._sources(docs),
            "rewritten": rewritten,
            "domain": domain,
        }

    def stream(self, question: str, history: list[dict] | None = None):
        """流式生成：先逐 token 产出，最后产出一条 meta（含改写 / 路由 / 引用）。

        阶段事件（type=phase，name 取值）按真实执行顺序推送，让前端实时展示进度：
        - rewrite   ：Query 改写中
        - retrieve  ：检索中（含首次加载向量模型）
        - rerank    ：精排中（含首次加载 rerank 模型）
        - generate  ：生成中（开始吐 token）
        """
        if _is_meta(question):
            messages = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": question}]
            for chunk in self._llm.stream(messages):
                if chunk.content:
                    yield {"type": "token", "text": chunk.content}
            yield {"type": "meta", "rewritten": question, "domain": None, "sources": []}
            return
        # 立即发出首个事件，让前端立刻有反馈（避免长静默）
        yield {"type": "phase", "name": "rewrite"}
        rewritten = rewrite_query(question, history, self._llm)

        yield {"type": "phase", "name": "retrieve"}
        domain = route_domain(rewritten, self._llm)
        self.retriever.domain_filter = domain

        # 检索内部会触发 embedding（可能首次加载 BGE-M3），单列一个阶段反馈
        docs = self.retriever.invoke(rewritten)

        # 检索兜底：仅当检索无相关内容时，才兜底走离题判定（此时知识库确实没有答案）。
        if self._empty(docs) and is_offtopic(question, self._llm):
            yield {"type": "token", "text": _OFFTOPIC_TEXT}
            yield {"type": "meta", "rewritten": question, "domain": None, "sources": [], "offtopic": True}
            return

        yield {"type": "phase", "name": "generate"}
        messages = _build_messages(rewritten, docs)
        for chunk in self._llm.stream(messages):
            if chunk.content:
                yield {"type": "token", "text": chunk.content}
        yield {
            "type": "meta",
            "rewritten": rewritten,
            "domain": domain,
            "sources": self._sources(docs),
        }


def build_lcel_chain():
    """LCEL 声明式检索生成链（展示 LangChain Expression Language 用法）。

    供评测 / 演示使用：RunnablePassthrough 组装 retriever → 格式化 → 提示词 → LLM。
    """
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnablePassthrough

    meta, dense, bm25 = load_index()
    retriever = KnowledgeRetriever(meta, dense, bm25)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _SYSTEM),
            ("human", "资料片段：\n{context}\n\n用户问题：{question}"),
        ]
    )
    chain = (
        {"context": retriever | _format_context, "question": RunnablePassthrough()}
        | prompt
        | _llm()
        | StrOutputParser()
    )
    return chain
