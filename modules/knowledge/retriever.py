"""混合检索：稠密向量 + BM25 双路召回，RRF 融合排序。"""

from __future__ import annotations

import numpy as np

from .config import TOP_K_RECALL
from .embedder import encode
from .index import BM25


def dense_search(query_vec: np.ndarray, dense: np.ndarray, top_k: int = TOP_K_RECALL) -> list[tuple[int, float]]:
    """稠密向量余弦相似度召回（向量已归一化，点积即余弦）。"""
    if dense.size == 0:
        return []
    sims = dense @ query_vec
    idx = np.argsort(-sims)[:top_k]
    return [(int(i), float(sims[i])) for i in idx]


def bm25_search(query: str, bm25: BM25, top_k: int = TOP_K_RECALL) -> list[tuple[int, float]]:
    """BM25 关键词召回（只返回命中分数 > 0 的）。"""
    scores = bm25.scores(query)
    order = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k]
    return [(i, scores[i]) for i in order if scores[i] > 0]


def rrf_fusion(*rankings: list[tuple[int, float]], k: int = 60) -> list[tuple[int, float]]:
    """RRF（Reciprocal Rank Fusion）融合多路排序，返回 (doc_id, 融合分) 降序。"""
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, (doc_id, _score) in enumerate(ranking):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(fused.items(), key=lambda x: -x[1])


def hybrid_search(query: str, dense: np.ndarray, bm25: BM25, top_k: int = TOP_K_RECALL) -> list[tuple[int, float]]:
    """混合检索：稠密 + BM25 双路召回，RRF 融合。"""
    q_vec = encode([query])[0]
    d_rank = dense_search(q_vec, dense, top_k)
    b_rank = bm25_search(query, bm25, top_k)
    return rrf_fusion(d_rank, b_rank)[:top_k]
