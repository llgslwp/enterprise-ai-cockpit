"""numpy/JSON 双索引：稠密向量 + BM25 关键词索引。

纯文件落地（无数据库），文件布局（INDEX_DIR 下）：
- meta.json   切片元数据（page_content + metadata）
- dense.npy   稠密向量矩阵 (n, dim)
- bm25.json   BM25 索引（词表、倒排、文档长度）

支持增量更新（重建即全量覆盖，量级小、成本可控）。
"""

from __future__ import annotations

import json
import math
import os

import jieba
import numpy as np
from langchain_core.documents import Document

from .config import INDEX_DIR
from .embedder import encode

_STOP = set(" \t\n\r，。、；：！？（）【】《》“”‘’")


def _tokenize(text: str) -> list[str]:
    """jieba 中文分词，去掉停用符号与空白。"""
    return [t for t in jieba.lcut(text) if t.strip() and t not in _STOP]


class BM25:
    """轻量 Okapi BM25（jieba 分词 + 经典打分），用于关键词召回。"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: list[list[str]] = []  # 每个文档的分词结果
        self.doc_len: list[int] = []
        self.avg_len: float = 0.0
        self.df: dict[str, int] = {}    # 词 -> 文档频率
        self.total_docs = 0

    def add_document(self, text: str) -> None:
        tokens = _tokenize(text)
        self.docs.append(tokens)
        self.doc_len.append(len(tokens))
        self.total_docs += 1
        self.avg_len = sum(self.doc_len) / self.total_docs
        for tok in set(tokens):
            self.df[tok] = self.df.get(tok, 0) + 1

    def _idf(self, tok: str) -> float:
        n = self.df.get(tok, 0)
        return math.log((self.total_docs - n + 0.5) / (n + 0.5) + 1.0)

    def scores(self, query: str) -> list[float]:
        q_tokens = _tokenize(query)
        result: list[float] = []
        for i, tokens in enumerate(self.docs):
            if not tokens:
                result.append(0.0)
                continue
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            s = 0.0
            dl_norm = self.b * len(tokens) / self.avg_len
            for qt in q_tokens:
                if qt not in tf:
                    continue
                f = tf[qt]
                s += self._idf(qt) * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + dl_norm))
            result.append(s)
        return result


def build_index(chunks: list[Document], verbose: bool = True) -> dict:
    """构建双索引并落地到 INDEX_DIR。"""
    os.makedirs(INDEX_DIR, exist_ok=True)
    texts = [c.page_content for c in chunks]

    if verbose:
        print(f"向量化 {len(texts)} 个切片（BGE-M3）...")
    dense = encode(texts)

    bm25 = BM25()
    for t in texts:
        bm25.add_document(t)

    meta = [{"page_content": c.page_content, "metadata": c.metadata} for c in chunks]
    with open(os.path.join(INDEX_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    np.save(os.path.join(INDEX_DIR, "dense.npy"), dense)
    bm25_data = {
        "docs": bm25.docs,
        "doc_len": bm25.doc_len,
        "avg_len": bm25.avg_len,
        "df": bm25.df,
        "total_docs": bm25.total_docs,
    }
    with open(os.path.join(INDEX_DIR, "bm25.json"), "w", encoding="utf-8") as f:
        json.dump(bm25_data, f, ensure_ascii=False)

    return {"n_chunks": len(chunks), "dim": int(dense.shape[1]), "index_dir": INDEX_DIR}


def index_exists() -> bool:
    return all(
        os.path.exists(os.path.join(INDEX_DIR, f))
        for f in ("meta.json", "dense.npy", "bm25.json")
    )


def load_index() -> tuple[list[dict], np.ndarray, BM25]:
    """从磁盘加载双索引（meta / dense / bm25）。"""
    with open(os.path.join(INDEX_DIR, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    dense = np.load(os.path.join(INDEX_DIR, "dense.npy"))
    with open(os.path.join(INDEX_DIR, "bm25.json"), encoding="utf-8") as f:
        data = json.load(f)
    bm25 = BM25()
    bm25.docs = data["docs"]
    bm25.doc_len = data["doc_len"]
    bm25.avg_len = data["avg_len"]
    bm25.df = data["df"]
    bm25.total_docs = data["total_docs"]
    return meta, dense, bm25
