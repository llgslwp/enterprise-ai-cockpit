"""构建知识库索引（离线入口）。

用法：python -m modules.knowledge.build
流程：加载文档 → 语义分块 → 构建双索引（稠密向量 + BM25）→ 落地 numpy/JSON。
"""

from __future__ import annotations

from .chunker import chunk_all
from .index import build_index, index_exists
from .loaders import load_all


def main() -> None:
    print("=== 1/3 加载文档 ===")
    docs = load_all(verbose=True)
    print(f"共加载 {len(docs)} 个文档")

    if not docs:
        print("无可用文档，请确认 docs/产品工艺/ 下有 MD/Word/Excel 或文字版 PDF。")
        return

    print("=== 2/3 语义分块 ===")
    chunks = chunk_all(docs)
    print(f"共分块 {len(chunks)} 个切片")

    print("=== 3/3 构建双索引 ===")
    info = build_index(chunks, verbose=True)
    print(f"索引完成：切片 {info['n_chunks']} 个，向量维度 {info['dim']}，目录 {info['index_dir']}")
    print(f"索引状态：{'已存在' if index_exists() else '缺失'}")


if __name__ == "__main__":
    main()
