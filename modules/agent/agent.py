"""agent 编排：用 LangChain 1.x create_agent 搭最小闭环（agent-core 能力）。

create_agent 封装了「模型选工具 → 执行 → 观察 → 再选」的循环，底层是 LangGraph 的
CompiledStateGraph。这里提供两样东西：

1. build_agent()   —— 组装 agent（DeepSeek 模型 + 工具清单 + 系统提示词）
2. ask(question)   —— 同步问答入口：返回最终答案 + 工具调用轨迹（可追溯）

可靠性设计（对应「确定性包裹不确定性」四道防线）：
- 数据层：工具只调确定性实现，数字不靠模型生成；
- 动作层：当前仅只读工具，无写操作，模型天然无法越权；
- 留痕层：ask 返回 tool_calls 轨迹，便于回放与对账；
- 验收层：调用方可用 golden set 评测集 + 工具返回逐值对照做回归。
"""

from __future__ import annotations

import datetime as _dt

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from modules.knowledge.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from .tools import ALL_TOOLS

def _months_ago(n: int) -> int:
    """返回 n 个月前的月份（1-12，自动跨年）。如当前 11 月，n=1 → 10 月。"""
    return (_dt.datetime.now().month - 1 - n) % 12 + 1


def _build_system_prompt() -> str:
    """动态生成系统提示词，实时注入当前日期与相对月份映射。

    必须每次 ask() 实时生成（不能启动时固化），否则后端长跑几天后日期过期。
    相对月份（本月/上月/上上个月）由确定性代码算好明文列出，模型只照抄数字、不做日期算术，
    消除「模型算错日期偏移」的风险。
    """
    now = _dt.datetime.now()
    return (
        "你是「企业AI驾驶舱」的智能助手，面向企业管理者回答生产经营数据问题。\n"
        f"今天是 {now.year} 年 {now.month} 月 {now.day} 日。\n"
        f"本月 = {now.month} 月；上月 = {_months_ago(1)} 月；上上个月 = {_months_ago(2)} 月。\n"
        "用户说「本月/这个月/当月」时 month 传本月数字；说「上月/上个月」时传上月数字；说「上上个月」时传上上个月数字。\n"
        "规则：\n"
        "1. 凡涉及库存、数量、结存、出入库等数据的问题——包括查询、比较、排序、最多/最少、趋势、够不够——都必须先调用工具查询真实数据，严禁凭记忆猜测或编造数字，也严禁反问用户、让用户自己去查；\n"
        "2. 用户未指定月份时，默认查询当前月（即本月），不要反问「您要查哪个月」；\n"
        "3. 工具返回的数字要如实转述，不得改动、不得夸大、不得添加工具里没有的数据；\n"
        "4. 若没有能回答该问题的工具，明确说「我目前没有查询该数据的工具」，不要硬编；\n"
        "5. 用简洁、结构化的中文回答（可用 Markdown 表格）。"
    )


def build_agent():
    """组装 agent（每次调用新建，保证无状态、线程安全）。"""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=0.2,
    )
    return create_agent(
        model=llm,
        tools=ALL_TOOLS,
        system_prompt=_build_system_prompt(),
    )


def ask(question: str) -> dict:
    """同步问答入口。

    返回 {"answer": 最终答案文本, "tool_calls": [{name, content}...]}。
    tool_calls 为本次对话中模型实际调用的工具轨迹，供可追溯 / 对账。
    """
    agent = build_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    messages = result["messages"]

    # 最终答案 = 最后一条有实质内容的 AI 消息
    answer = ""
    for m in reversed(messages):
        if getattr(m, "type", None) == "ai":
            content = getattr(m, "content", "") or ""
            if content.strip():
                answer = content
                break

    # 工具调用轨迹（只读记录，供回放）：配对 AI 的 tool_calls（name+args）与 Tool 的返回（content）
    args_by_id = {}
    for m in messages:
        if getattr(m, "type", None) == "ai":
            for tc in (getattr(m, "tool_calls", None) or []):
                if isinstance(tc, dict):
                    args_by_id[tc.get("id", "")] = {
                        "name": tc.get("name", ""),
                        "args": tc.get("args", {}),
                    }
    tool_calls = []
    for m in messages:
        if getattr(m, "type", None) == "tool":
            tcid = getattr(m, "tool_call_id", "")
            info = args_by_id.get(tcid, {})
            tool_calls.append({
                "name": getattr(m, "name", "") or info.get("name", ""),
                "args": info.get("args", {}),
                "content": (getattr(m, "content", "") or "")[:800],
            })

    return {"answer": answer, "tool_calls": tool_calls}
