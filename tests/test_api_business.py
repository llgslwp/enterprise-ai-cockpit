"""L2 接口测试：业务模块契约（鉴权拦截 + 返回结构 + 优雅降级）。

覆盖 4 个轻依赖业务模块（production / inventory / quality / files）：
- 未登录一律 401（require_login 依赖在路由函数体之前拦截，不碰数据）。
- 登录后模块首页返回 200 + code=0 + data.status="已落地"。
- 读数据的路由：无论有无数据文件，都优雅返回 {code,message,data}（不 500 崩溃）。

注：本文件只测「确定的行为」。inventory/summary、quality/inspection 等路由
在无数据时是否优雅降级未逐一核实，故不写入降级断言（避免基于猜测写测试）。
"""

import pytest


# ===== 鉴权拦截：未登录访问业务路由一律 401 =====
@pytest.mark.parametrize("path", [
    "/api/production",
    "/api/production/dashboard",
    "/api/production/gap-stat",
    "/api/inventory",
    "/api/inventory/summary",
    "/api/quality",
    "/api/quality/inspection",
    "/api/files",
])
def test_require_login(client, path):
    """未登录访问受保护业务路由 → 401（require_login 依赖生效）。"""
    r = client.get(path)
    assert r.status_code == 401


# ===== 模块首页：登录后 200 + code=0 + status=已落地 =====
@pytest.mark.parametrize("path,module", [
    ("/api/production", "生产管理"),
    ("/api/inventory", "库存管理"),
    ("/api/quality", "质量管理"),
])
def test_module_home(auth_client, path, module):
    """模块首页不读数据，登录后应稳定返回 200 + code=0。"""
    r = auth_client.get(path)
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["module"] == module
    assert body["data"]["status"] == "已落地"


# ===== 读数据路由：优雅返回，不 500 崩溃 =====
@pytest.mark.parametrize("path", [
    "/api/production/dashboard",
    "/api/production/gap-stat",
])
def test_data_route_graceful(auth_client, path):
    """读数据的路由应优雅返回 {code,message,data} 而非 500。

    - 有数据文件：code=0（正常返回）
    - 无数据文件：FileNotFoundError 被路由捕获 → code=1（降级），HTTP 仍 200
    两种情况下都保证 HTTP 200 + 三元组结构，前端可据此区分「无数据」与「系统崩」。
    """
    r = auth_client.get(path)
    assert r.status_code == 200
    body = r.json()
    assert "code" in body and "message" in body and "data" in body
    assert body["code"] in (0, 1)


# ===== files 列表：登录后 code=0 + data 为列表 =====
def test_files_list(auth_client):
    """文件列表：登录后返回 code=0，data 为列表（无数据时为空列表）。"""
    r = auth_client.get("/api/files")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)
