"""质量管理模块（quality-dashboard 能力）。

面向高管的只读质量看板，展示「车间抽检」月度质量态势与「原料来料检验」情况。
数据实时读取 data/raw/ 本地 Excel，不缓存、不写回、不接腾讯文档。
另含「质量管理工具」三件套：控制图（p 图）、四预警建议动作、8D 闭环。

接口：
- GET  /api/quality?month=10           车间抽检质量看板（KPI/趋势/问题TOP/严重预警/建议动作）
- GET  /api/quality/material-inspection?month=7 原料来料检验看板
- GET  /api/quality/spc?month=10       控制图（p 图）
- GET  /api/quality/8d?month=10        8D 闭环卡片列表
- POST /api/quality/8d/update          写回 8D 卡 D5–D8 状态
- POST /api/quality/8d/reset           重置 8D 卡为待执行
"""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.deps import require_login
from modules.quality import aggregate, spc, eight_d

router = APIRouter()


class EightDUpdate(BaseModel):
    card_id: str
    fields: dict


class EightDReset(BaseModel):
    card_id: str


@router.get("")
def quality_home(request: Request, _=Depends(require_login)):
    return {"code": 0, "message": "ok", "data": {"module": "质量管理", "status": "已落地"}}


@router.get("/inspection")
def quality_view(
    request: Request,
    month: int = Query(None, description="目标月份（不传默认当前系统月）"),
    _=Depends(require_login),
):
    """车间抽检质量看板：KPI、月度趋势、问题 TOP、严重预警、缺月回退 note。"""
    try:
        data = aggregate.build_quality(month)
        return {"code": 0, "message": "ok", "data": data}
    except Exception as e:
        # 降级：不让整个服务 500
        return {
            "code": 0,
            "message": "ok",
            "data": {"month": f"{month}月" if month else "当月", "error": "quality_error", "detail": str(e)},
        }


@router.get("/material-inspection")
def material_inspection(
    request: Request,
    month: int = Query(None, description="目标月份（不传默认当前系统月）"),
    _=Depends(require_login),
):
    """原料来料检验看板：检验结果分布、供应商表现、物料/问题 TOP、退货+让步预警。"""
    try:
        data = aggregate.build_material_inspection(month)
        return {"code": 0, "message": "ok", "data": data}
    except Exception as e:
        return {
            "code": 0,
            "message": "ok",
            "data": {"month": f"{month}月" if month else "当月", "error": "material_error", "detail": str(e)},
        }


@router.get("/spc")
def quality_spc(
    request: Request,
    month: int = Query(None, description="目标月份（不传默认当前系统月）"),
    _=Depends(require_login),
):
    """控制图（p 图）：中心线 + 每日不合格率 + 破限点。"""
    try:
        data = spc.build_spc(month)
        return {"code": 0, "message": "ok", "data": data}
    except Exception as e:
        return {
            "code": 0,
            "message": "ok",
            "data": {"month": f"{month}月" if month else "当月", "error": "spc_error", "detail": str(e)},
        }


@router.get("/8d")
def quality_8d(
    request: Request,
    month: int = Query(None, description="目标月份（不传默认当前系统月）"),
    _=Depends(require_login),
):
    """8D 闭环卡片列表（从反复出现预警派生，含已写回的 D5–D8 状态）。"""
    try:
        data = eight_d.get_8d_cards(month)
        return {"code": 0, "message": "ok", "data": data}
    except Exception as e:
        return {
            "code": 0,
            "message": "ok",
            "data": {"month": f"{month}月" if month else "当月", "error": "8d_error", "detail": str(e)},
        }


@router.post("/8d/update")
def quality_8d_update(payload: EightDUpdate, request: Request, _=Depends(require_login)):
    """写回某张 8D 卡的 D5–D8 等字段。"""
    try:
        card = eight_d.update_8d_card(payload.card_id, payload.fields)
        return {"code": 0, "message": "ok", "data": card}
    except Exception as e:
        return {"code": 0, "message": "ok", "data": {"error": "8d_update_error", "detail": str(e)}}


@router.post("/8d/reset")
def quality_8d_reset(payload: EightDReset, request: Request, _=Depends(require_login)):
    """重置某张 8D 卡为待执行。"""
    try:
        eight_d.reset_8d_card(payload.card_id)
        return {"code": 0, "message": "ok", "data": {"card_id": payload.card_id}}
    except Exception as e:
        return {"code": 0, "message": "ok", "data": {"error": "8d_reset_error", "detail": str(e)}}
