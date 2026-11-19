"""企业 AI 驾驶舱 —— Web 应用启动入口。

本文件是系统底座（system-foundation + tech-architecture）的运行入口。
架构：前后端分离。后端 FastAPI 提供 REST 接口（/api 前缀），前端为 Vue 3 + Vite SPA。
- 开发期：前端 Vite dev server（5173）通过代理访问后端（8000）。
- 生产期：前端构建产物由本后端静态托管。
"""

from app.env import load_env

load_env()  # 尽早加载 .env（LLM_API_KEY 等敏感配置），供后续业务模块读取

from app.create_app import create_app

app = create_app(include_heavy=True)


# 知识库问答预热：后台线程预加载 BGE-M3 + reranker 模型。
# 消除首次问答「点发送后静默 10~20 秒才出第一个字」的冷启动体验问题（spec 要求即时进度反馈）。
# 用 on_event("startup") 触发，不阻塞服务启动；预热失败静默降级（首次问答仍走懒加载）。
from modules.knowledge import api as _knowledge_api


@app.on_event("startup")
def _warmup_knowledge():
    try:
        _knowledge_api.warmup()
    except Exception:  # noqa: BLE001
        pass


# 前端静态资源（生产期托管构建产物；若未构建则回退到健康提示）
import os
from fastapi.staticfiles import StaticFiles

_dist = os.path.join(os.path.dirname(__file__), "web", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    # 注意：reload=False（不用热重载）。reload 模式会 fork 出 reloader 子进程，
    # 在 Windows 双击 .bat 启动时进程树不稳定、易被误杀，导致「后端动不动就掉」。
    # 开发期改后端代码后，手动重启后端即可（双击 start.ps1 会重新拉起）。
    #
    # 2026-11-13 改为直接传 app 对象（而非 "main:app" 字符串）：
    # 字符串形式会让 uvicorn 用 importlib 二次 import 整个 main 模块，
    # 而 main 的 import 链极重（langchain + torch + sentence_transformers），
    # 二次 import 耗时约 60s、且产生额外子进程，双击启动时进程树不稳、易掉。
    # 直接传 app 对象可消除二次 import，启动更快、进程更稳。
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
