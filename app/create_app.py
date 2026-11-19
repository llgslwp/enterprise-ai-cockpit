"""FastAPI 应用工厂。

把 app 的组装逻辑从 main.py 抽离，供两处复用：
- main.py：生产启动，`create_app(include_heavy=True)` 挂载全部路由（含 agent/knowledge 重依赖）。
- tests/：L2 接口测试，`create_app(include_heavy=False)` 只挂载轻依赖路由。

为什么要抽离（2026-11-19 决策）：
main.py 顶层 `from modules.agent.router import ...` / `from modules.knowledge import api` 会连带
import langchain / torch / sentence-transformers 等重依赖。GitHub Actions 免费 runner 装不动这些，
导致「测试想用 TestClient 就得 import main，而 import main 又崩在重依赖」——L2 接口测试无法上 CI。

拆法：
- 轻依赖路由（auth / production / inventory / quality / files）只在模块顶层 import，
  它们的依赖链已核实为「标准库 + fastapi + openpyxl + numpy」，CI 可装。
- 重依赖路由（agent / knowledge）延迟到 `create_app()` 函数体内、`include_heavy=True` 分支才 import，
  这样 `create_app(include_heavy=False)` 时完全不触碰 torch/langchain。

「测试与生产同源」：测试用同一个 create_app，prefix / 中间件 / 挂载顺序与生产完全一致，
不会因「测试自建一个手写 app」而漏测或不同步。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.auth import router as auth_router
from modules import production, inventory, quality
from modules.files import router as files_router


def create_app(include_heavy: bool = True) -> FastAPI:
    """构建 FastAPI 应用。

    Args:
        include_heavy: True 挂载全部路由（含 agent/knowledge 重依赖），生产启动用；
                       False 只挂载轻依赖路由，接口测试（CI）用。
    """
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

    # 轻依赖业务模块接口（标准库 + openpyxl，CI 可跑）
    app.include_router(production.router, prefix="/api/production", tags=["生产管理"])
    app.include_router(inventory.router, prefix="/api/inventory", tags=["库存管理"])
    app.include_router(quality.router, prefix="/api/quality", tags=["质量管理"])
    app.include_router(files_router, prefix="/api/files", tags=["文件上传"])

    @app.get("/api/health")
    def health():
        return {"code": 0, "message": "ok", "data": {"status": "running"}}

    # 重依赖模块接口（agent 用 langchain，knowledge 用 torch/sentence-transformers）。
    # 延迟到函数体内 import，避免 create_app(include_heavy=False) 连带加载重依赖。
    if include_heavy:
        from modules.agent.router import router as agent_router
        from modules.knowledge import api as knowledge_api
        from modules.knowledge import manage_router as knowledge_manage_router

        app.include_router(knowledge_api.api_router, prefix="/api/knowledge", tags=["知识库"])
        app.include_router(knowledge_manage_router.router, prefix="/api/knowledge/manage", tags=["知识管理"])
        app.include_router(agent_router, prefix="/api/agent", tags=["智能辅助决策"])

    return app
