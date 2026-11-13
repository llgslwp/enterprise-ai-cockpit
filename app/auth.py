"""登录与鉴权（admin-auth 能力）。

本期为单账号过渡，但数据模型为多角色预留扩展点（决策 4）。
管理员账号通过环境变量注入，默认值仅用于本地开发。
接口契约：REST JSON，供前端 SPA 调用。
"""

import os

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["鉴权"])

# 单账号（本期范围：仅一个账号，多角色后续逐个启用）
ADMIN_USERNAME = os.environ.get("COCKPIT_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("COCKPIT_ADMIN_PASS", "admin123")

# 会话中标记已登录的键
SESSION_KEY = "authenticated"
# 会话中记录当前用户（含角色，多角色扩展点）
SESSION_USER_KEY = "user"


class LoginBody(BaseModel):
    """登录请求体（JSON）。"""
    username: str
    password: str


class UserInfo(BaseModel):
    """当前用户信息。角色为多角色底座预留，本期固定 admin。"""
    username: str
    role: str


def is_authenticated(request: Request) -> bool:
    return request.session.get(SESSION_KEY, False) is True


def current_user(request: Request) -> UserInfo | None:
    """返回当前登录用户；未登录返回 None。"""
    if not is_authenticated(request):
        return None
    data = request.session.get(SESSION_USER_KEY, {})
    return UserInfo(
        username=data.get("username", ADMIN_USERNAME),
        role=data.get("role", "admin"),
    )


@router.post("/login")
def login(request: Request, body: LoginBody):
    """登录：校验账号密码，成功后写入会话。返回当前用户信息。"""
    if body.username == ADMIN_USERNAME and body.password == ADMIN_PASSWORD:
        request.session[SESSION_KEY] = True
        request.session[SESSION_USER_KEY] = {
            "username": body.username,
            "role": "admin",  # 多角色扩展点：本期固定 admin
        }
        return {"code": 0, "message": "ok", "data": {"username": body.username, "role": "admin"}}
    return _unauthorized("账号或密码错误")


@router.post("/logout")
def logout(request: Request):
    request.session.pop(SESSION_KEY, None)
    request.session.pop(SESSION_USER_KEY, None)
    return {"code": 0, "message": "ok", "data": None}


@router.get("/me")
def me(request: Request):
    """返回当前登录用户信息；未登录返回 401。"""
    user = current_user(request)
    if user is None:
        return _unauthorized("未登录")
    return {"code": 0, "message": "ok", "data": user.model_dump()}


def _unauthorized(detail: str):
    """统一未授权响应：401 + JSON 结构。"""
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=401, content={"code": 401, "message": detail, "data": None})
