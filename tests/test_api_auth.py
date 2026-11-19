"""L2 接口测试：鉴权契约（health / 登录 / 登出 / me / 鉴权拦截）。

这些用例不依赖真实业务数据，本机与 CI 结果一致。
契约依据：app/auth.py（统一 {code,message,data}）+ app/deps.py（未登录 401）。
"""


def test_health(client):
    """健康检查：200 + code=0 + data.status=running。"""
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "running"


def test_login_success(client):
    """正确账号密码登录：200 + code=0 + 返回用户名与角色。"""
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["username"] == "admin"
    assert body["data"]["role"] == "admin"


def test_login_wrong_password(client):
    """错误密码：401 + code=401（不泄露是否命中账号）。"""
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong-pass"})
    assert r.status_code == 401
    assert r.json()["code"] == 401


def test_me_unauthenticated(client):
    """未登录访问 /me：401。"""
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_authenticated(auth_client):
    """登录后访问 /me：200 + code=0 + 返回当前用户。"""
    r = auth_client.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["username"] == "admin"
    assert body["data"]["role"] == "admin"


def test_logout_then_me_unauthorized(auth_client):
    """登出后 /me 回到 401（会话被清除）。"""
    r = auth_client.post("/api/auth/logout")
    assert r.status_code == 200
    assert r.json()["code"] == 0
    # 登出后再次访问 me 应为未登录
    assert auth_client.get("/api/auth/me").status_code == 401
