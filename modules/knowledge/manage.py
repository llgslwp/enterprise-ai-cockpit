"""知识管理——文件存储与版本管理（knowledge-management 能力）。

本地存储 data/knowledge/（按入库类型分文件夹）：
  data/knowledge/
  ├── meta.json            # 元数据索引（所有文件的当前状态）
  ├── 工艺类/<file_id>/    # 每个文档一个目录，按入库类型归类
  │   ├── v1_<原文件名>
  │   └── v2_<原文件名>
  ├── 制度类/<file_id>/...
  └── 知识类/<file_id>/...

设计要点：
- 元数据是数据而非代码，每次调用重新读取 meta.json（开口式）。
- 版本链单调递增：上传新版本或回滚都产生新版本号，不重写历史。
- 停用 = status 翻转，文件实体保留，不做物理删除。
- 单进程后端（reload=False），元数据读写加锁即可，无并发竞争。
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from datetime import datetime
from typing import Dict, List, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(_PROJECT_ROOT, "data", "knowledge")
META_PATH = os.path.join(DATA_DIR, "meta.json")

# 允许的文件扩展名（小写）
ALLOWED_EXTS = (".md", ".txt", ".docx", ".pdf")

# 入库类型（三选一）
TYPES = ("工艺类", "制度类", "知识类")

# 可见范围标签（本阶段仅作元数据，不拦截）
VISIBILITIES = ("全员", "生产", "质量", "管理")
DEFAULT_VISIBILITY = "全员"

_meta_lock = threading.Lock()


def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_meta() -> Dict[str, dict]:
    if not os.path.isfile(META_PATH):
        return {}
    try:
        with open(META_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_meta(meta: Dict[str, dict]) -> None:
    _ensure_dirs()
    with _meta_lock:
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _new_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:6]


def _safe_name(name: str) -> str:
    return os.path.basename(name or "").strip() or "未命名"


def _doc_dir(ftype: str, file_id: str) -> str:
    """返回某文档的磁盘目录：按入库类型分文件夹。"""
    return os.path.join(DATA_DIR, ftype, file_id)


def validate_ext(name: str) -> bool:
    """校验文件名是否属于允许的四类扩展名。"""
    return name.lower().endswith(ALLOWED_EXTS)


def validate_type(ftype: str) -> Optional[str]:
    """校验入库类型，合法返回原值，否则 None。"""
    if ftype in TYPES:
        return ftype
    return None


def normalize_visibility(visibility: Optional[str]) -> str:
    if visibility in VISIBILITIES:
        return visibility
    return DEFAULT_VISIBILITY


def create_document(name: str, ftype: str, visibility: Optional[str], content: bytes, remark: str = "") -> dict:
    """新建文档（v1）。content 为文件字节。"""
    _ensure_dirs()
    fname = _safe_name(name)
    file_id = _new_id()
    doc_dir = _doc_dir(ftype, file_id)
    os.makedirs(doc_dir, exist_ok=True)
    ver_file = f"v1_{fname}"
    dest = os.path.join(doc_dir, ver_file)
    with open(dest, "wb") as f:
        f.write(content)
    size = os.path.getsize(dest)
    now = _now()
    record = {
        "id": file_id,
        "name": fname,
        "type": ftype,
        "visibility": normalize_visibility(visibility),
        "status": "enabled",
        "current_version": 1,
        "created_at": now,
        "updated_at": now,
        "versions": [
            {"version": 1, "file_path": ver_file, "size": size, "uploaded_at": now, "remark": remark}
        ],
    }
    meta = _load_meta()
    meta[file_id] = record
    _save_meta(meta)
    return record


def add_version(file_id: str, content: bytes, remark: str = "") -> Optional[dict]:
    """为已有文档追加新版本（版本号递增，旧版本保留）。"""
    meta = _load_meta()
    rec = meta.get(file_id)
    if rec is None:
        return None
    doc_dir = _doc_dir(rec["type"], file_id)
    new_ver = int(rec["current_version"]) + 1
    ver_file = f"v{new_ver}_{rec['name']}"
    dest = os.path.join(doc_dir, ver_file)
    with open(dest, "wb") as f:
        f.write(content)
    size = os.path.getsize(dest)
    now = _now()
    rec["versions"].append({
        "version": new_ver, "file_path": ver_file, "size": size, "uploaded_at": now, "remark": remark,
    })
    rec["current_version"] = new_ver
    rec["updated_at"] = now
    meta[file_id] = rec
    _save_meta(meta)
    return rec


def list_documents() -> List[dict]:
    """列出所有文档的摘要（不含版本明细），按更新时间倒序。"""
    meta = _load_meta()
    items = []
    for rec in meta.values():
        items.append({
            "id": rec["id"],
            "name": rec["name"],
            "type": rec["type"],
            "visibility": rec["visibility"],
            "status": rec["status"],
            "current_version": rec["current_version"],
            "created_at": rec["created_at"],
            "updated_at": rec["updated_at"],
        })
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return items


def get_versions(file_id: str) -> Optional[dict]:
    """返回某文档的完整信息（含版本历史）。"""
    meta = _load_meta()
    rec = meta.get(file_id)
    if rec is None:
        return None
    return {
        "id": rec["id"],
        "name": rec["name"],
        "type": rec["type"],
        "visibility": rec["visibility"],
        "status": rec["status"],
        "current_version": rec["current_version"],
        "versions": rec["versions"],
    }


def resolve_version_path(file_id: str, version: int) -> Optional[str]:
    """返回某文档指定版本的磁盘绝对路径。"""
    meta = _load_meta()
    rec = meta.get(file_id)
    if rec is None:
        return None
    for v in rec["versions"]:
        if v["version"] == version:
            return os.path.join(_doc_dir(rec["type"], file_id), v["file_path"])
    return None


def rollback(file_id: str, version: int) -> Optional[dict]:
    """回滚：复制指定历史版本为新的当前版本（版本链单调递增，不重写历史）。"""
    meta = _load_meta()
    rec = meta.get(file_id)
    if rec is None:
        return None
    src_path = None
    for v in rec["versions"]:
        if v["version"] == version:
            src_path = os.path.join(_doc_dir(rec["type"], file_id), v["file_path"])
            break
    if src_path is None or not os.path.isfile(src_path):
        return None
    new_ver = int(rec["current_version"]) + 1
    ver_file = f"v{new_ver}_{rec['name']}"
    dest = os.path.join(_doc_dir(rec["type"], file_id), ver_file)
    shutil.copyfile(src_path, dest)
    size = os.path.getsize(dest)
    now = _now()
    rec["versions"].append({
        "version": new_ver, "file_path": ver_file, "size": size, "uploaded_at": now, "remark": f"回滚自 v{version}",
    })
    rec["current_version"] = new_ver
    rec["updated_at"] = now
    meta[file_id] = rec
    _save_meta(meta)
    return rec


def toggle(file_id: str) -> Optional[dict]:
    """停用/启用翻转，文件实体保留。"""
    meta = _load_meta()
    rec = meta.get(file_id)
    if rec is None:
        return None
    rec["status"] = "disabled" if rec.get("status") == "enabled" else "enabled"
    rec["updated_at"] = _now()
    meta[file_id] = rec
    _save_meta(meta)
    return rec
