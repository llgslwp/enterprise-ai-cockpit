"""知识库问答 API（同步 + 流式 SSE）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.deps import require_login
from .chain import KnowledgeQA
from .index import index_exists
from .loaders import DOMAIN_NAMES

api_router = APIRouter()

_qa: KnowledgeQA | None = None
_warmup_started = False


def _get_qa() -> KnowledgeQA:
    global _qa
    if not index_exists():
        raise RuntimeError("知识库索引尚未构建，请先运行：python -m modules.knowledge.build")
    if _qa is None:
        _qa = KnowledgeQA()
    return _qa


def warmup() -> None:
    """后台预热：预加载 BGE-M3 + bge-reranker 模型，消除首次问答的冷启动静默期。

    模型是懒加载的（embedder/reranker 首次调用才加载），若不预热，用户第一次提问
    会在「吐第一个字之前」卡 10~20 秒加载模型，体验上像系统卡死。预热后首次问答
    只需跑正常的检索+rerank+生成，静默期大幅缩短。
    """
    global _warmup_started
    if _warmup_started:
        return
    _warmup_started = True

    def _do():
        try:
            # 预加载向量模型与 rerank 模型（触发下载/加载到内存与显存）
            from .embedder import get_embedder
            from .reranker import get_reranker
            get_embedder()
            get_reranker()
        except Exception:  # noqa: BLE001
            # 预热失败不阻塞服务：首次问答时仍会按懒加载路径重试
            _warmup_started = False

    import threading
    threading.Thread(target=_do, daemon=True).start()


class ChatBody(BaseModel):
    message: str
    history: list[dict] | None = None


@api_router.get("/domains")
def domains(_=Depends(require_login)):
    """返回当前知识库的全部知识域（用于前端展示）。"""
    return {"code": 0, "message": "ok", "data": {"domains": DOMAIN_NAMES}}


@api_router.post("/chat")
def chat(body: ChatBody, _=Depends(require_login)):
    """同步问答：返回回答 + 来源引用 + 改写 + 路由。"""
    try:
        qa = _get_qa()
        result = qa.answer(body.message, body.history or [])
        return {"code": 0, "message": "ok", "data": result}
    except Exception as e:  # noqa: BLE001
        return {"code": 1, "message": str(e), "data": None}


@api_router.post("/chat/stream")
def chat_stream(body: ChatBody, _=Depends(require_login)):
    """流式问答（SSE）：逐 token 推送，末尾推送 meta（含引用）。"""

    def gen():
        try:
            qa = _get_qa()
            for event in qa.stream(body.message, body.history or []):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
