"""bge-reranker-v2-m3 精排（cross-encoder）。

对混合检索召回的候选切片做 cross-encoder 精排，取 top-k 送入生成，
补齐「Rerank 重排」这一环技术链（DeepSeek 无 rerank 接口，用本地模型补齐）。
"""

from __future__ import annotations

import torch

# 必须先 import config（触发 HF_ENDPOINT 镜像设置），再 import sentence_transformers
from .config import RERANK_MODEL, MODEL_TORCH_DTYPE, RERANK_MAX_LENGTH, RERANK_BATCH_SIZE, no_proxy
from sentence_transformers import CrossEncoder

_reranker: CrossEncoder | None = None


def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        with no_proxy():
            _reranker = CrossEncoder(
                RERANK_MODEL,
                model_kwargs={"torch_dtype": getattr(torch, MODEL_TORCH_DTYPE)},
                max_length=RERANK_MAX_LENGTH,
            )
    return _reranker


def rerank(query: str, docs: list[str], top_k: int | None = None) -> list[tuple[int, float]]:
    """对候选文本精排，返回 (原始下标, 分数) 按分数降序。

    分批预测：一次性打包过多候选对会让 cross-encoder 的 attention 矩阵
    （batch × seq × seq）内存爆炸，分批可把峰值压到可控范围。
    """
    if not docs:
        return []
    model = get_reranker()
    pairs = [[query, d] for d in docs]
    scores = model.predict(
        pairs,
        batch_size=RERANK_BATCH_SIZE,
        show_progress_bar=False,
    )
    order = sorted(range(len(scores)), key=lambda i: -float(scores[i]))
    if top_k:
        order = order[:top_k]
    return [(i, float(scores[i])) for i in order]
