"""公共 Query 改写 rewrite_query 的单元测试。

覆盖 spec「多轮上下文与指代消解改写」的核心场景：
门控（空 history 不改写、不调 LLM）、有历史改写、空结果回退、历史截断（6 条 + 单条 400 字）。
用 mock LLM，不真实调用云端大模型。
"""

import pytest

from modules.common.query_rewrite import rewrite_query


class _FakeLLM:
    """模拟 ChatOpenAI：记录 invoke 调用，返回可配置的 content。"""

    def __init__(self, reply: str = ""):
        self._reply = reply
        self.calls: list[str] = []

    def invoke(self, prompt: str):
        self.calls.append(prompt)

        class _Resp:
            content = self._reply

        return _Resp()


def test_no_history_returns_original_without_calling_llm():
    """门控：history 为空时原样返回，且不调用 LLM（首轮零额外延迟）。"""
    llm = _FakeLLM(reply="不该被调用")
    assert rewrite_query("加力95产能多少", [], llm) == "加力95产能多少"
    assert llm.calls == []


def test_no_history_none_also_skips():
    """门控：history 为 None 同样跳过改写。"""
    llm = _FakeLLM(reply="不该被调用")
    assert rewrite_query("加力95产能多少", None, llm) == "加力95产能多少"
    assert llm.calls == []


def test_with_history_rewrites_and_calls_llm():
    """有历史时调用 LLM 改写，返回改写结果。"""
    llm = _FakeLLM(reply="加力95目前能产多少把")
    out = rewrite_query("它产能如何", [{"role": "user", "content": "加力95库存多少"}], llm)
    assert out == "加力95目前能产多少把"
    assert len(llm.calls) == 1


def test_empty_result_falls_back_to_question():
    """改写返回空时回退原问题，不中断。"""
    llm = _FakeLLM(reply="")
    out = rewrite_query("它产能如何", [{"role": "user", "content": "加力95库存多少"}], llm)
    assert out == "它产能如何"


def test_whitespace_result_falls_back_to_question():
    """改写返回纯空白时回退原问题。"""
    llm = _FakeLLM(reply="   \n ")
    out = rewrite_query("它产能如何", [{"role": "user", "content": "加力95库存多少"}], llm)
    assert out == "它产能如何"


def test_history_truncated_to_last_6():
    """超过 6 条历史时只取最近 6 条进 prompt。"""
    llm = _FakeLLM(reply="改写")
    history = [{"role": "user", "content": f"问题{i}"} for i in range(10)]
    rewrite_query("它呢", history, llm)
    prompt = llm.calls[0]
    # 最近 6 条 = 问题4..问题9；更早的问题0..问题3 不应出现
    assert "问题0" not in prompt
    assert "问题3" not in prompt
    assert "问题4" in prompt
    assert "问题9" in prompt


def test_history_item_truncated_to_400_chars():
    """单条历史超 400 字时被截断，防止超长答案撑爆 prompt。"""
    llm = _FakeLLM(reply="改写")
    long_content = "长" * 500
    history = [{"role": "assistant", "content": long_content}]
    rewrite_query("它呢", history, llm)
    prompt = llm.calls[0]
    assert ("长" * 400) in prompt
    assert ("长" * 401) not in prompt
