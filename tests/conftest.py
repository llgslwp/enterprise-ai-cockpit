"""pytest 公共 fixture：组装轻量 app 供 L2 接口测试使用。

关键点：测试用 create_app(include_heavy=False)，只挂载轻依赖路由
（auth / production / inventory / quality / files），完全不 import
agent（langchain）/ knowledge（torch）的重依赖，因此 CI 免费 runner 也能跑。

「测试与生产同源」：create_app 与 main.py 共用同一套 prefix/中间件/挂载顺序，
不会因测试自建 app 而与生产行为脱节。
"""

import pytest
from fastapi.testclient import TestClient

from app.create_app import create_app


@pytest.fixture(scope="session")
def app():
    """轻量 FastAPI app（无 agent/knowledge 重依赖路由）。"""
    return create_app(include_heavy=False)


@pytest.fixture()
def client(app):
    """未登录的 TestClient。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_client(client):
    """已登录的 TestClient（默认管理员账号 admin / admin123）。"""
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, "fixture 登录失败，默认账号密码应可用"
    return client
