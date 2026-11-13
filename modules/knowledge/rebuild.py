"""知识库索引自动重建（供知识管理「上传后自动重建」调用）。

上传/新版本/回滚/启停等会改变「哪些文件、哪个版本进索引」的操作，落盘后触发
本模块的后台重建：加载文档 → 分块 → 构建双索引 → 重置问答单例，让新索引立即生效。

设计要点：
- 重建是耗时操作（GPU 向量化 20~30 秒），放后台线程执行，不阻塞上传请求。
- 用「节流合并」：短时间内多次上传只触发最后一次重建，避免重复跑。
- 重建期间前端可轮询 /rebuild-status 查看进度；完成后重置 _qa 单例。
"""

from __future__ import annotations

import threading

from .chunker import chunk_all
from .index import build_index
from .loaders import load_all

# 重建状态（供前端轮询）
_state_lock = threading.Lock()
_state = {"running": False, "pending": False, "last_result": None, "last_error": None}

# 触发节流：重建结束后若期间又有新请求，再跑一次（pending 标记）
_trigger_lock = threading.Lock()
_worker: threading.Thread | None = None


def _do_rebuild() -> None:
    """执行一次完整的索引重建（加载 → 分块 → 构建）。"""
    with _state_lock:
        _state["running"] = True
        _state["pending"] = False
        _state["last_error"] = None
    try:
        docs = load_all(verbose=False)
        chunks = chunk_all(docs)
        info = build_index(chunks, verbose=False)
        with _state_lock:
            _state["last_result"] = {
                "n_docs": len(docs),
                "n_chunks": info["n_chunks"],
                "dim": info["dim"],
            }
    except Exception as e:  # noqa: BLE001
        with _state_lock:
            _state["last_error"] = str(e)
    finally:
        with _state_lock:
            _state["running"] = False
        # 重建完成后重置问答单例，让下次问答加载新索引
        _invalidate_qa()
        # 若期间又有新变更，补跑一次
        with _state_lock:
            again = _state["pending"]
            _state["pending"] = False
        if again:
            _worker = threading.Thread(target=_do_rebuild, daemon=True)
            _worker.start()


def _invalidate_qa() -> None:
    """重置 api.py 的 _qa 单例，使下次问答重新 load_index() 加载新索引。"""
    try:
        from . import api
        api._qa = None
    except Exception:  # noqa: BLE001
        # 若 api 模块尚未初始化（如离线命令行重建），忽略
        pass


def trigger_rebuild() -> None:
    """请求重建索引（幂等，去抖合并）。"""
    global _worker
    with _state_lock:
        if _state["running"]:
            # 正在重建：标记 pending，结束后再跑
            _state["pending"] = True
            return
    _worker = threading.Thread(target=_do_rebuild, daemon=True)
    _worker.start()


def get_status() -> dict:
    """返回当前重建状态（供前端轮询）。"""
    with _state_lock:
        return dict(_state)
