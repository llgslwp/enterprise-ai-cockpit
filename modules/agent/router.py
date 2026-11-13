"""智能辅助决策路由（agent-core 多工具调用能力）。

POST /chat：接收自然语言问题，调用 modules.agent.agent.ask() 完成
「模型选工具 → 执行 → 观察 → 生成答案」的闭环，返回最终答案 + 工具调用轨迹。

设计要点（对应 spec 约束）：
- 只读工具边界：ask() 内部仅暴露只读 tool（query_stock），无写操作；
- 数据真实性：回答数字来自工具返回值，逐值可对账；
- 轨迹可追溯：返回 tool_calls 供回放；
- 性能：LLM 问答豁免 200ms（同步，端到端数秒~十几秒），前端负责 loading 进度反馈。
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.deps import require_login
from modules.agent.agent import ask

router = APIRouter()


class ChatRequest(BaseModel):
    question: str


@router.post("/chat")
def agent_chat(req: ChatRequest, request: Request, _=Depends(require_login)):
    """智能辅助决策对话入口。"""
    question = (req.question or "").strip()
    if not question:
        return {"code": 1, "message": "问题不能为空", "data": None}
    try:
        result = ask(question)
    except Exception as e:  # noqa: BLE001
        return {"code": 1, "message": f"智能助手调用失败：{e}", "data": None}
    return {"code": 0, "message": "ok", "data": result}
