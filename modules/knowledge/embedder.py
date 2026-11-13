"""BGE-M3 向量化（稠密向量）。

BGE-M3 是三合一模型（稠密 + 稀疏 + 多向量），此处用 sentence-transformers 加载取稠密向量；
稀疏/关键词召回由 index.py 的 BM25 关键词索引承担，共同构成「向量 + BM25 双索引」。
模型首次加载会自动从 HuggingFace 下载（国内走 hf-mirror 镜像），之后常驻内存。
"""

from __future__ import annotations

import numpy as np
import torch

# 必须先 import config（触发 HF_ENDPOINT 镜像设置），再 import sentence_transformers；
# 否则 huggingface_hub 在 import 时就把 ENDPOINT 固定为 huggingface.co，镜像失效。
from .config import EMBED_MODEL, MODEL_TORCH_DTYPE, EMBED_MAX_LENGTH, EMBED_BATCH_SIZE, no_proxy
from sentence_transformers import SentenceTransformer

_embedder: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    """惰性加载 BGE-M3（首次加载较慢，之后常驻）。下载时绕过环境代理直连。

    用半精度（fp16）加载 + 限制序列长度，内存从 ~2.27GB 降到 ~1.1GB，适配小内存机器。
    """
    global _embedder
    if _embedder is None:
        with no_proxy():
            _embedder = SentenceTransformer(
                EMBED_MODEL,
                model_kwargs={"torch_dtype": getattr(torch, MODEL_TORCH_DTYPE)},
            )
        _embedder.max_seq_length = EMBED_MAX_LENGTH
    return _embedder


def encode(texts: list[str], batch_size: int | None = None) -> np.ndarray:
    """把文本列表编码为归一化稠密向量矩阵 (n, dim)。"""
    if not texts:
        return np.empty((0, 0), dtype="float32")
    model = get_embedder()
    vecs = model.encode(
        texts,
        batch_size=batch_size or EMBED_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vecs, dtype="float32")
