"""企业 AI 驾驶舱 —— Web 应用启动入口。

本文件是系统底座（system-foundation + tech-architecture）的运行入口。
架构：前后端分离。后端 FastAPI 提供 REST 接口（/api 前缀），前端为 Vue 3 + Vite SPA。
- 开发期：前端 Vite dev server（5173）通过代理访问后端（8000）。
- 生产期：前端构建产物由本后端静态托管。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import router as auth_router
from app.env import load_env

load_env()  # 尽早加载 .env（LLM_API_KEY 等敏感配置），供后续业务模块读取

from modules import production, inventory, quality
from modules.agent.router import router as agent_router
from modules.files import router as files_router
from modules.knowledge import api as knowledge_api
from modules.knowledge import manage_router as knowledge_manage_router

app = FastAPI(title="企业 AI 驾驶舱")

# 会话中间件（登录态）
# max_age=None：会话级 cookie，浏览器关闭即失效，每次打开都需重新登录
# same_site="lax"：同源请求携带 cookie（默认值，显式声明）
# https_only=False：本地开发走 HTTP，不强制 HTTPS
app.add_middleware(
    SessionMiddleware,
    secret_key="dev-secret-change-me",
    max_age=None,
    same_site="lax",
    https_only=False,
)

# CORS：允许前端开发端口 + 携带凭证（决策 3）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 鉴权接口（/api/auth/*）
app.include_router(auth_router, prefix="/api")

# 业务模块接口（/api/...）
app.include_router(production.router, prefix="/api/production", tags=["生产管理"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["库存管理"])
app.include_router(quality.router, prefix="/api/quality", tags=["质量管理"])
app.include_router(files_router, prefix="/api/files", tags=["文件上传"])
app.include_router(knowledge_api.api_router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(knowledge_manage_router.router, prefix="/api/knowledge/manage", tags=["知识管理"])
app.include_router(agent_router, prefix="/api/agent", tags=["智能辅助决策"])


@app.get("/api/health")
def health():
    return {"code": 0, "message": "ok", "data": {"status": "running"}}


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
