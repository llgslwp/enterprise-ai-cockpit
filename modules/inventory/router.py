"""库存管理模块（inventory-status 能力）。

反映与产品直接相关的各项物资库存状态：
- 库存汇总看板（/summary）
- 逐物资明细查询（/search）
- 库存预警（/alerts，成品结存低于库存底线）

数据实时读取 data/raw/ 下最新文件，不缓存。
"""

from fastapi import APIRouter, Depends, Query, Request

from app.deps import require_login
from modules.inventory import aggregate
from modules.inventory import flow_stats

router = APIRouter()


@router.get("")
def inventory_home(request: Request, _=Depends(require_login)):
    return {"code": 0, "message": "ok", "data": {"module": "库存管理", "status": "已落地"}}


@router.get("/summary")
def inventory_summary(request: Request, _=Depends(require_login)):
    """库存汇总看板：各类别物资数与总存量。"""
    summary = aggregate.build_summary()
    return {"code": 0, "message": "ok", "data": {"summary": summary}}


@router.get("/ledger-meta")
def inventory_ledger_meta(request: Request, _=Depends(require_login)):
    """台账（成品入出库 v8.1）文件信息：文件名 + 最后更新日期。

    供库存管理四个子页面在月份下方常驻显示「数据更新日期」。
    """
    import os
    path = flow_stats.resolve_ledger_file()
    if not path:
        return {"code": 0, "message": "ok", "data": {"file_name": None, "mtime": None}}
    from datetime import datetime
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "file_name": os.path.basename(path),
            "mtime": mtime.strftime("%Y-%m-%d %H:%M"),
        },
    }


@router.get("/search")
def inventory_search(
    request: Request,
    keyword: str = Query(..., min_length=1, description="货品名称/规格关键词"),
    _=Depends(require_login),
):
    """逐物资明细查询：按名称/规格检索。"""
    results = aggregate.search_items(keyword)
    return {"code": 0, "message": "ok", "data": {"items": results, "count": len(results)}}


@router.get("/alerts")
def inventory_alerts(request: Request, _=Depends(require_login)):
    """库存预警（成品预警）：成品结存低于库存底线的规格。"""
    alerts = aggregate.build_alerts()
    return {"code": 0, "message": "ok", "data": {"alerts": alerts, "count": len(alerts)}}


@router.get("/material-gap")
def inventory_material_gap(request: Request, _=Depends(require_login)):
    """原料预警：毛坯库「现有存量」低于原料库存底线的货品。"""
    alerts = aggregate.build_material_alerts()
    return {"code": 0, "message": "ok", "data": {"alerts": alerts, "count": len(alerts)}}


@router.get("/flow-stats")
def inventory_flow_stats(
    request: Request,
    month: int = Query(None, description="目标月份（不传默认当前真实月份）"),
    _=Depends(require_login),
):
    """库存月度流水聚合：入库/出库/结存（6 品类 + 两大系列 + 分品类明细）。"""
    stats = flow_stats.build_flow_stats(month)
    return {"code": 0, "message": "ok", "data": stats}


@router.get("/share-stats")
def inventory_share_stats(
    request: Request,
    month: int = Query(None, description="目标月份（不传默认当前真实月份）"),
    _=Depends(require_login),
):
    """库存占比分析：入库/出库/结存 × 各品种/两大系列 的占比。"""
    stats = flow_stats.build_share_stats(month)
    return {"code": 0, "message": "ok", "data": stats}


@router.get("/focus-stats")
def inventory_focus_stats(
    request: Request,
    month: int = Query(None, description="目标月份（不传默认当前真实月份）"),
    _=Depends(require_login),
):
    """重点关注规格明细：仅清单勾选的规格，返回本月入库/出库/结存。"""
    stats = flow_stats.build_focus_stats(month)
    return {"code": 0, "message": "ok", "data": stats}
