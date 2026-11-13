"""知识管理——文件上传/管理 API（knowledge-management 能力）。

挂载前缀 /api/knowledge/manage（与知识库问答 /api/knowledge/chat 同域，不冲突）。

接口：
- POST /upload                上传新文件（multipart：file + type + visibility + remark）
- GET  /list                  文件列表
- POST /{id}/version          上传新版本
- GET  /{id}/versions         版本历史
- GET  /{id}/download         下载（?version=N 指定版本，缺省当前版）
- POST /{id}/rollback         回滚到指定版本
- POST /{id}/toggle           停用/启用
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.deps import require_login
from . import manage, rebuild

router = APIRouter()


@router.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    ftype: str = Form(..., alias="type"),
    visibility: str = Form(manage.DEFAULT_VISIBILITY),
    remark: str = Form(""),
    _=Depends(require_login),
):
    """上传新文件入库（v1），落盘后自动重建索引。"""
    name = file.filename or ""
    if not manage.validate_ext(name):
        return {"code": 400, "message": "仅支持 MD / TXT / docx / PDF 文件", "data": None}
    ftype_ok = manage.validate_type(ftype)
    if ftype_ok is None:
        return {"code": 400, "message": "入库类型必须是：工艺类 / 制度类 / 知识类", "data": None}
    content = await file.read()
    rec = manage.create_document(name, ftype_ok, visibility, content, remark)
    rebuild.trigger_rebuild()
    return {"code": 0, "message": "ok", "data": rec}


@router.get("/list")
def list_documents(request: Request, _=Depends(require_login)):
    """文件列表（按更新时间倒序）。"""
    items = manage.list_documents()
    return {"code": 0, "message": "ok", "data": {"items": items, "count": len(items)}}


@router.get("/{file_id}/versions")
def versions(file_id: str, request: Request, _=Depends(require_login)):
    """某文档的完整信息 + 版本历史。"""
    rec = manage.get_versions(file_id)
    if rec is None:
        return {"code": 404, "message": "文件不存在", "data": None}
    return {"code": 0, "message": "ok", "data": rec}


@router.get("/{file_id}/download")
def download(
    file_id: str,
    request: Request,
    version: int | None = None,
    _=Depends(require_login),
):
    """下载文件（缺省当前版本，可用 ?version=N 下载历史版本）。"""
    rec = manage.get_versions(file_id)
    if rec is None:
        return {"code": 404, "message": "文件不存在", "data": None}
    ver = version or rec["current_version"]
    path = manage.resolve_version_path(file_id, ver)
    if path is None or not os.path.isfile(path):
        return {"code": 404, "message": "版本不存在", "data": None}
    return FileResponse(path, filename=rec["name"])


@router.post("/{file_id}/version")
async def add_version(
    file_id: str,
    request: Request,
    file: UploadFile = File(...),
    remark: str = Form(""),
    _=Depends(require_login),
):
    """为已有文档上传新版本，落盘后自动重建索引。"""
    name = file.filename or ""
    if not manage.validate_ext(name):
        return {"code": 400, "message": "仅支持 MD / TXT / docx / PDF 文件", "data": None}
    content = await file.read()
    rec = manage.add_version(file_id, content, remark)
    if rec is None:
        return {"code": 404, "message": "文件不存在", "data": None}
    rebuild.trigger_rebuild()
    return {"code": 0, "message": "ok", "data": rec}


class RollbackBody(BaseModel):
    version: int


@router.post("/{file_id}/rollback")
def rollback(file_id: str, body: RollbackBody, request: Request, _=Depends(require_login)):
    """回滚到指定历史版本（复制为新当前版本），落盘后自动重建索引。"""
    rec = manage.rollback(file_id, body.version)
    if rec is None:
        return {"code": 404, "message": "文件或版本不存在", "data": None}
    rebuild.trigger_rebuild()
    return {"code": 0, "message": "ok", "data": rec}


@router.post("/{file_id}/toggle")
def toggle(file_id: str, request: Request, _=Depends(require_login)):
    """停用/启用翻转，翻转后自动重建索引（停用文件不进索引）。"""
    rec = manage.toggle(file_id)
    if rec is None:
        return {"code": 404, "message": "文件不存在", "data": None}
    rebuild.trigger_rebuild()
    return {"code": 0, "message": "ok", "data": rec}


@router.get("/rebuild-status")
def rebuild_status(request: Request, _=Depends(require_login)):
    """查询索引重建状态（供前端轮询提示「知识库索引更新中」）。"""
    return {"code": 0, "message": "ok", "data": rebuild.get_status()}
