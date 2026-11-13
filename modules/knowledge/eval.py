"""检索 / 生成质量评测（knowledge-base 能力）。

指标：
- 检索：Recall@k（top-k 是否命中标注相关切片）、MRR（平均倒数排名）
- 生成：引用有效性 + LLM-as-judge 打分（可选）

注意：内置示例问题集是「自设基准」，仅用于验证检索链路是否召回相关切片，
不代表业务真实问答水平——正式评测需用业务方提供的真实问题 + 期望答案替换。
"""

from __future__ import annotations

from .chain import KnowledgeQA
from .index import load_index
from .retriever import hybrid_search

# 示例评测基准（自设，用于链路验证；正式评测请替换为业务真实问题集）
_SAMPLE_QA = [
    {"question": "含钛重型管钳和美式重型管钳有什么区别？", "answers": ["镀彩", "覆膜砂", "含钛", "美重"]},
    {"question": "加力钳有哪些规格？", "answers": ["95", "加力", "规格", "80", "132"]},
    {"question": "钻杆钳的规格组有哪些？", "answers": ["71-75", "钻杆", "114-117", "89-95"]},
    {"question": "美重和含钛的配件有什么区别？", "answers": ["镀彩", "覆膜砂", "美重", "含钛"]},
    {"question": "套管钳的外管借用哪个产品线？", "answers": ["钻杆", "外管", "借用"]},
    {"question": "内管钳用什么工艺替代铣齿？", "answers": ["镀金刚石", "内管钳"]},
    {"question": "加力钳涉及哪些机加工关键工序？", "answers": ["车丝", "铣丝", "铣齿", "焊接", "铆小钳口"]},
]


def eval_retrieval(qa_pairs: list[dict] | None = None, k: int = 5) -> dict:
    """检索评测：对每个问题做混合检索，检查 top-k 是否命中标注关键词。"""
    qa_pairs = qa_pairs or _SAMPLE_QA
    meta, dense, bm25 = load_index()

    hits = 0
    mrr = 0.0
    details = []
    for item in qa_pairs:
        q = item["question"]
        fused = hybrid_search(q, dense, bm25, top_k=k)
        hit = False
        hit_rank = None
        matched = []
        for rank, (doc_id, _score) in enumerate(fused, 1):
            text = meta[doc_id]["page_content"]
            title = meta[doc_id]["metadata"].get("title", "")
            if any(kw in text for kw in item.get("answers", [])):
                hit = True
                hit_rank = rank
                matched.append({"rank": rank, "title": title, "path": meta[doc_id]["metadata"].get("title_path", "")})
        if hit:
            hits += 1
            mrr += 1.0 / hit_rank
        details.append({"question": q, "hit": hit, "hit_rank": hit_rank, "matched": matched})

    n = len(qa_pairs)
    return {
        "total": n,
        "hit": hits,
        "recall_at_k": round(hits / n, 4) if n else 0.0,
        "mrr": round(mrr / n, 4) if n else 0.0,
        "details": details,
    }


def eval_generation(qa_pairs: list[dict] | None = None) -> dict:
    """生成评测：走完整链路（改写→路由→检索→生成），返回回答 + 引用。

    生成质量可由人工审阅，或用 LLM-as-judge 二次评分（此处先返回原始结果）。
    """
    qa_pairs = qa_pairs or _SAMPLE_QA
    qa = KnowledgeQA()
    results = []
    for item in qa_pairs:
        r = qa.answer(item["question"])
        results.append(
            {
                "question": item["question"],
                "answer": r["answer"],
                "domain": r["domain"],
                "rewritten": r["rewritten"],
                "n_sources": len(r["sources"]),
                "sources": [s["title"] for s in r["sources"]],
            }
        )
    return {"total": len(results), "results": results}


def run_eval() -> dict:
    """一键评测：检索 + 生成。"""
    retrieval = eval_retrieval()
    generation = eval_generation()
    return {"retrieval": retrieval, "generation": generation}
