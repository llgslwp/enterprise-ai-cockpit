"""语义分块 + 切片语义标注（knowledge-base 能力之一）。

MD / Word 统一转成 markdown 结构后，用 MarkdownHeaderTextSplitter 按标题层级切分，
保证每个切片语义完整（不跨标题 / 段落硬切）；超长切片再用 RecursiveCharacterTextSplitter 兜底。

切片语义标注：以「标题路径」作为确定性的语义标签（如「产品工艺总汇 > 通用配件表」），
无额外 LLM 成本；可选 LLM 一句话摘要作为增强。
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

# 标题层级 -> 元数据字段名（MarkdownHeaderTextSplitter 约定）
_HEADERS = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]

_heading_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=_HEADERS, strip_headers=False)

_fallback_splitter = RecursiveCharacterTextSplitter(
    separators=["\n\n", "\n", "。", "；", "，", " ", ""],
    chunk_size=1200,
    chunk_overlap=120,
)


def _semantic_label(meta: dict) -> str:
    """由标题层级拼出语义标签（标题路径）。"""
    parts = [meta.get(k) for k in ("h1", "h2", "h3", "h4") if meta.get(k)]
    if parts:
        return " > ".join(parts)
    return meta.get("title", "未命名文档")


def chunk_document(doc: Document) -> list[Document]:
    """对单个文档做语义分块，返回切片列表（每个切片带 title_path 语义标签）。"""
    base = dict(doc.metadata)
    result: list[Document] = []

    # 一级：按标题层级切（语义边界）
    for part in _heading_splitter.split_text(doc.page_content):
        header_meta = {k: v for k, v in part.metadata.items() if k in ("h1", "h2", "h3", "h4")}
        # 二级：超长切片按段落兜底
        if len(part.page_content) > 1200:
            for sub in _fallback_splitter.split_text(part.page_content):
                result.append(_make_chunk(sub, base, header_meta))
        else:
            result.append(_make_chunk(part.page_content, base, header_meta))

    return result


def _make_chunk(text: str, base: dict, header_meta: dict) -> Document:
    meta = {**base, **header_meta}
    meta["title_path"] = _semantic_label(meta)
    return Document(page_content=text.strip(), metadata=meta)


def chunk_all(docs: list[Document]) -> list[Document]:
    """对全部文档做语义分块。"""
    chunks: list[Document] = []
    for doc in docs:
        chunks.extend(chunk_document(doc))
    return chunks


def annotate_chunks(chunks: list[Document], llm=None) -> list[Document]:
    """可选增强：用 LLM 为每个切片生成一句话摘要（写回 metadata["summary"]）。

    默认一期不调用（切片语义标注已由 title_path 标题路径承担）；
    llm 传入则逐切片生成摘要，用于评测或精检索时叠加语义维度。
    """
    if llm is None:
        return chunks
    for c in chunks:
        if c.metadata.get("summary"):
            continue
        try:
            prompt = (
                "用一句话概括下面这段工艺/作业文本的核心内容，不超过 30 字，只输出概括句：\n\n"
                f"{c.page_content[:500]}"
            )
            c.metadata["summary"] = llm.chat([{"role": "user", "content": prompt}])
        except Exception:  # noqa: BLE001
            c.metadata["summary"] = ""
    return chunks
