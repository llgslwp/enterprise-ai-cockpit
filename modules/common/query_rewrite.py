"""公共 Query 改写：多轮对话指代消解（agent 与知识库两模块共用）。

把含指代（「它 / 这个 / 那个 / 其」等）或省略主语的追问，结合最近几轮历史改写成
完整独立查询，避免下游单轮模型「失忆」答非所问。无历史时原样返回（门控，零额外调用）。
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from modules.knowledge.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# 历史截断：最近 6 条（约 3 轮），单条限 400 字，防止超长答案（库存表格 / 产能明细）撑爆改写 prompt
_MAX_HIST_ITEMS = 6
_MAX_HIST_ITEM_LEN = 400


def _llm(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=temperature,
    )


def rewrite_query(question: str, history: list[dict] | None, llm: ChatOpenAI | None = None) -> str:
    """多轮 Query 改写：把含指代的追问改写为完整独立查询。无历史时原样返回（门控）。

    失败 / 返回空时回退原问题，保证不中断问答链路。
    """
    if not history:
        return question
    llm = llm or _llm()
    conv = "\n".join(
        f"{h.get('role', 'user')}: {str(h.get('content', '') or '')[: _MAX_HIST_ITEM_LEN]}"
        for h in history[-_MAX_HIST_ITEMS:]
    )
    prompt = (
        "你负责把用户的多轮对话追问改写成一句完整、独立、不含指代（如「它/这个/那个」）的查询。\n"
        "若当前问题本身已完整独立，原样返回。只输出改写后的查询，不要解释。\n\n"
        f"对话历史：\n{conv}\n\n当前追问：{question}"
    )
    resp = llm.invoke(prompt)
    return (resp.content or "").strip() or question
