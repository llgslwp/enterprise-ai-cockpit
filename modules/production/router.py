"""生产管理模块（production-planning 能力）。

生产计划制定与过程管理。本模块提供：
- /dashboard  生产计划管理大屏数据（总体完成率 / 4区段 / 6品类，支持月份切换）
- /gap-stat   生产缺口统计（V2.0 排产结果网页直显，formulas 计算缺口）
- /backfill   入库填报（成品台账当月入库写回生产计划 F 列，异常即暂停覆盖）
"""

from fastapi import APIRouter, Depends, Query, Request

from app.deps import require_login
from modules.production import backfill, dashboard_calc, gap_stat
from modules.production.scheduling import run_pipeline

router = APIRouter()


@router.get("")
def production_home(request: Request, _=Depends(require_login)):
    return {"code": 0, "message": "ok", "data": {"module": "生产管理", "status": "已落地"}}


@router.get("/dashboard")
def production_dashboard(
    request: Request,
    month: int = Query(None, description="指定月份（不传返回全部月份+最新月）"),
    _=Depends(require_login),
):
    """生产计划管理大屏数据。

    - 不传 month：返回 {"latest": {...}, "months": {"8": {...}, "9": {...}, ...}}
    - 传 month：返回单月数据 {"month": N, "overall": {...}, "dimensions": [...], "products": [...]}
    """
    try:
        path = dashboard_calc.resolve_plan_file()
    except FileNotFoundError as e:
        return {"code": 1, "message": str(e), "data": None}

    if month is not None:
        data = dashboard_calc.calc_month(path, month)
    else:
        data = dashboard_calc.build_dashboard(path)
    return {"code": 0, "message": "ok", "data": data}


@router.get("/gap-stat")
def production_gap_stat(request: Request, _=Depends(require_login)):
    """生产缺口统计：V2.0 排产结果网页直显。

    返回 5 个品类（加力/美式/内管/钻杆/套管）的完整排产表格，
    含 C~I 库存量、成品计划、半成品需求/装配缺口/机加工（formulas 精确计算），
    以及单元格颜色信息（蓝底成品计划、黄/橙底配件、粉红底正缺口）。
    """
    try:
        path = gap_stat.resolve_result_file()
        data = gap_stat.extract_gap_stat(path)
    except FileNotFoundError as e:
        return {"code": 1, "message": str(e), "data": None}
    return {"code": 0, "message": "ok", "data": data}


@router.post("/backfill")
def production_backfill(request: Request, _=Depends(require_login)):
    """入库填报：把成品台账当月入库记录写回生产计划 F 列。

    规则（用户 2026-11-02 定稿）：
    - 无条件执行，不二次确认。
    - 先试算：有异常 → 只返回异常报告、不覆盖；异常清零 → 一次性覆盖最新生产计划文件。
    - 结果只在界面显示（成功/异常），无导出文件。

    返回：
    - code=0 成功（committed=true，覆盖完成）
    - code=0 但有异常（committed=false，返回异常报告，未覆盖）
    - code=1 系统错误
    """
    try:
        result = backfill.run_backfill(commit=True)
    except FileNotFoundError as e:
        return {"code": 1, "message": str(e), "data": None}
    except RuntimeError as e:
        # 文件被占用等，已翻译成通俗提示
        return {"code": 1, "message": str(e), "data": None}
    except (PermissionError, OSError) as e:
        from modules.production.scheduling.plan_file_utils import friendly_file_error
        return {"code": 1, "message": friendly_file_error(e), "data": None}
    except Exception as e:
        return {"code": 1, "message": f"入库填报执行失败：{e}", "data": None}

    # 台账当月无入库记录：无可填报数据（不写文件、不报成功）
    if result.get("no_inbound"):
        return {
            "code": 0,
            "message": f"台账 {result.get('month')} 月无入库记录，无可填报数据",
            "data": {
                "committed": False,
                "plan_file": result.get("plan_file"),
                "month": result.get("month"),
                "inbound_records": 0,
                "matched": 0,
                "exception_count": 0,
            },
        }

    # 有异常：未覆盖，返回异常报告
    if result.get("exception_count", 0) > 0:
        return {
            "code": 0,
            "message": "存在异常，已暂停覆盖",
            "data": {
                "committed": False,
                "plan_file": result.get("plan_file"),
                "month": result.get("month"),
                "inbound_records": result.get("inbound_records"),
                "matched": result.get("matched"),
                "exceptions": result.get("exceptions"),
                "exception_count": result.get("exception_count"),
            },
        }

    # 无异常：覆盖完成
    return {
        "code": 0,
        "message": "入库填报完成",
        "data": {
            "committed": result.get("committed"),
            "plan_file": result.get("plan_file"),
            "month": result.get("month"),
            "inbound_records": result.get("inbound_records"),
            "matched": result.get("matched"),
            "exception_count": 0,
        },
    }


@router.get("/source-files")
def production_source_files(request: Request, _=Depends(require_login)):
    """6 份源文件 + V2.0 基底的最后更新日期（供前端按钮旁常驻显示）。"""
    try:
        dates = run_pipeline.source_file_dates()
    except FileNotFoundError as e:
        return {"code": 1, "message": str(e), "data": None}
    return {"code": 0, "message": "ok", "data": dates}


@router.post("/schedule")
def production_schedule(request: Request, _=Depends(require_login)):
    """排产统计：跑完整排产链路，覆盖 V2.0 基底原文件。

    规则（用户 2026-11-02 定稿）：
    - 无条件执行，不二次确认。
    - 覆盖对象：最新月份的 V2.0 基底原文件本身（data/raw/半成品生产计划V2.0.xlsx）。
    - 执行后反馈：成功/失败在界面显示；排产完 gap-stat 读同一份文件，直接显示新结果。
    - 顺序：数据管理上先入库填报→再排产；实际不强制，靠源文件日期让副总自行判断。

    返回：
    - code=0 成功（含源文件定位、归集统计、覆盖的文件路径）
    - code=1 失败（缺源文件/异常）
    """
    try:
        base_path = run_pipeline.resolve_v2_base()
        summary = run_pipeline.run_pipeline(base_path, verify=False, overwrite_base=True)
    except FileNotFoundError as e:
        return {"code": 1, "message": str(e), "data": None}
    except RuntimeError as e:
        # 文件被占用等，已翻译成通俗提示
        return {"code": 1, "message": str(e), "data": None}
    except (PermissionError, OSError) as e:
        from modules.production.scheduling.plan_file_utils import friendly_file_error
        return {"code": 1, "message": friendly_file_error(e), "data": None}
    except Exception as e:
        return {"code": 1, "message": f"排产执行失败：{e}", "data": None}

    return {
        "code": 0,
        "message": "排产完成，已覆盖 V2.0",
        "data": {
            "base_path": base_path,
            "sources": summary.get("sources"),
            "source_totals": summary.get("source_totals"),
            "fill_count": summary.get("fill_count"),
            "color_fills": summary.get("color_fills"),
            "chengpin_fills": summary.get("chengpin_fills"),
            "output_path": summary.get("output_path"),
        },
    }
