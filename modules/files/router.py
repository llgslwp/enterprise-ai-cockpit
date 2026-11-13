"""文件上传能力（决策 5）。

保管员端口上传 ERP 导出的库存文件（替代微信传文件），
文件落入 data/raw/，作为后续计算的输入源。

上传时间记录：data/upload_meta.json 持久化记录每个文件的上传时间戳。
列表接口按上传时间倒序返回，前端据此划分「最新上传（当天）/ 历史上传」。
"""

import json
import os
import shutil
import threading
from datetime import datetime

from fastapi import APIRouter, Depends, Request, UploadFile, File

from app.deps import require_login

router = APIRouter()

# 数据入口目录（与 data-access 约定一致）
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
META_PATH = os.path.join(DATA_DIR, "upload_meta.json")

_meta_lock = threading.Lock()


def _load_meta() -> dict:
    """读取上传时间记录 {文件名: 时间戳(float)}。"""
    if not os.path.isfile(META_PATH):
        return {}
    try:
        with open(META_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_meta(meta: dict) -> None:
    """写回上传时间记录。"""
    with _meta_lock:
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)


@router.post("/upload")
def upload(request: Request, file: UploadFile = File(...), _=Depends(require_login)):
    """上传库存 Excel 文件到 data/raw/，并记录上传时间。"""
    # 仅接受 Excel
    name = file.filename or ""
    if not name.lower().endswith((".xlsx", ".xls")):
        return {"code": 400, "message": "仅支持 .xlsx / .xls 文件", "data": None}

    os.makedirs(RAW_DIR, exist_ok=True)
    dest = os.path.join(RAW_DIR, os.path.basename(name))
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 记录上传时间
    basename = os.path.basename(name)
    meta = _load_meta()
    meta[basename] = datetime.now().timestamp()
    _save_meta(meta)

    return {"code": 0, "message": "ok", "data": {"filename": basename, "path": dest}}


@router.get("")
def list_files(request: Request, _=Depends(require_login)):
    """列出 data/raw/ 下已上传的文件，按上传时间倒序返回。

    返回 [{filename, upload_time}]，upload_time 为 'YYYY-MM-DD HH:MM' 字符串。
    无上传记录的旧文件用文件 mtime 兜底。
    """
    if not os.path.isdir(RAW_DIR):
        return {"code": 0, "message": "ok", "data": []}

    meta = _load_meta()
    items = []
    for f in os.listdir(RAW_DIR):
        if not f.lower().endswith((".xlsx", ".xls")):
            continue
        full = os.path.join(RAW_DIR, f)
        ts = meta.get(f) or os.path.getmtime(full)
        items.append({
            "filename": f,
            "upload_time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
            "ts": ts,
        })

    # 按上传时间倒序（最新在上）
    items.sort(key=lambda x: x["ts"], reverse=True)
    for it in items:
        it.pop("ts", None)
    return {"code": 0, "message": "ok", "data": items}
