"""文档文本清洗（knowledge-base 能力之一）。

在「解析 → 分块」之间对文本做通用清洗，去掉会影响分块 / 索引质量的脏内容：
- 不可见 / 控制字符、乱码残留（OCR 重灾）
- 换行符统一、全 / 半角空格与制表符统一、连续空行折叠
- 重复段落去重（内容指纹）

清洗为纯内存变换：不回写 `data/knowledge/` 下任何原始文件，不碰数据源三铁律
（只读当前版本 / 跳过停用 / 排除 index/）。

一期只落「通用清洗 + 分块后过滤去重」；PDF 断行合并 / Word 表格结构化等专项
待对应素材真入库再补（`clean_text` 的 `doc_type` 参数已预留分派位）。
"""

from __future__ import annotations

import re

from langchain_core.documents import Document

# 不可见 / 控制字符：C0 控制区（排除 \n \t，且 \r\x0c 已前置处理）、DEL、C1 控制区、替换符 U+FFFD
_CONTROL_RE = re.compile("[\x00-\x08\x0b\x0e-\x1f\x7f\u0080-\u009f\ufffd]")

# 全角空格 → 半角空格
_FULLWIDTH_SPACE = "\u3000"


def _normalize_blank(text: str) -> str:
    """全角空格 → 半角，制表符 → 空格，行内连续空格折叠为 1 个。"""
    text = text.replace(_FULLWIDTH_SPACE, " ")
    text = text.replace("\t", " ")
    return re.sub(r" {2,}", " ", text)


def _fold_blank_lines(text: str) -> str:
    """连续空行折叠为单个空行（保留段落边界）。"""
    return re.sub(r"\n{3,}", "\n\n", text)


def _dedup_paragraphs(text: str) -> str:
    """按「规范化内容指纹」去重段落，保留首次出现的段落。"""
    paras = text.split("\n\n")
    seen: set[str] = set()
    out: list[str] = []
    for p in paras:
        fp = re.sub(r"\s+", "", p)  # 指纹 = 去空白后的内容
        if not fp:
            continue
        if fp in seen:
            continue
        seen.add(fp)
        out.append(p)
    return "\n\n".join(out)


def clean_text(text: str, doc_type: str = "md") -> str:
    """分块前通用清洗（一期全类型共用；`doc_type` 预留二期 PDF/Word 专项分派）。"""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # 1. 换行符统一
    text = text.replace("\x0c", "\n")                        # 2. 换页符 → 换行（防删除后粘连）
    text = _CONTROL_RE.sub("", text)                        # 3. 控制字符 / 乱码清理
    text = _normalize_blank(text)                           # 4. 空格 / 制表符统一
    text = _fold_blank_lines(text)                          # 5. 空行折叠
    text = _dedup_paragraphs(text)                          # 6. 重复段落去重
    return text.strip()                                     # 7. 首尾空白


def clean_documents(docs: list[Document]) -> list[Document]:
    """对解析产出的文档做分块前清洗，返回新 Document 列表（不改原对象）。"""
    cleaned: list[Document] = []
    for doc in docs:
        dtype = doc.metadata.get("doc_type", "md")
        new_text = clean_text(doc.page_content, dtype)
        if not new_text:
            continue  # 清洗后为空的文档丢弃
        cleaned.append(Document(page_content=new_text, metadata=dict(doc.metadata)))
    return cleaned


def _chunk_fingerprint(chunk: Document) -> str:
    """切片指纹 = title_path + 规范化内容，用于去重。"""
    tp = chunk.metadata.get("title_path", "")
    content = re.sub(r"\s+", "", chunk.page_content)
    return f"{tp}|{content}"


def filter_chunks(chunks: list[Document], min_len: int = 30) -> list[Document]:
    """分块后过滤：过短切片（<min_len 字，纯标题孤立切片）+ 内容指纹去重。"""
    result: list[Document] = []
    seen: set[str] = set()
    for c in chunks:
        if len(c.page_content.strip()) < min_len:
            continue
        fp = _chunk_fingerprint(c)
        if fp in seen:
            continue
        seen.add(fp)
        result.append(c)
    return result
