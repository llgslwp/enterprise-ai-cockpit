"""登录依赖：拦截未登录访问受保护接口。

本模块是 admin-auth 能力的一部分，供业务模块路由复用。
对 API 请求（SPA 调用），未登录抛出 401 HTTPException。
"""

from fastapi import HTTPException, Request

from app.auth import SESSION_KEY


def require_login(request: Request):
    """未登录时抛出 401 未授权异常。

    前端 SPA 依赖 401 状态码判断登录态并跳转登录页。
    """
    if request.session.get(SESSION_KEY, False) is not True:
        raise HTTPException(
            status_code=401,
            detail={"code": 401, "message": "未登录", "data": None},
        )


class RedirectException(Exception):
    """表示需要重定向到登录页的未登录访问（保留给页面路由使用）。"""
