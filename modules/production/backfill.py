"""入库填报（production-planning 能力）。

将成品入出库台账（176 个品类明细 sheet）中的「当月入库记录」，
按 批号 + 颜色 匹配到生产计划当月表的 F 列（{N}月份实际完成），
并覆盖最新生产计划文件。

核心规则（用户 2026-11-02 定稿，见 docs/入库填报-操作流程说明.md）：
- 入库 = 实际生产，不存在「当月实际完成」独立概念。
- 主匹配键：批号（台账「批号」列 -> 计划「生产批号」列）。
- 次匹配键：颜色（台账 sheet 名后缀解析 -> 计划「特殊要求」列）。
- 第三键：变体（加长/普通），仅候选行 > 1 时启用分流。
- 颜色筛选仅作用于「当月库存 / 当月订单」区段；「历史月份 / 世达订单」不筛。
- 多行分配：客户优先 + 行顺序；前 n-1 行填 min(剩余, 计划数)，末行兜底。
- 异常即暂停覆盖：只要存在异常（批号不在计划中 / 颜色不匹配 / 超计划数），
  就不覆盖原文件，只返回异常报告；异常清零后才一次性写入覆盖。
- 覆盖对象：只覆盖最新生产计划文件（resolve_plan_file 自动定位）。

生产计划实际列结构（openpyxl 1-based）：
    1 品名 / 2 规格 / 3 类别 / 4 客户名称/库存计划 / 5 未完成数量(计划数)
    6 {N}月份实际完成(动态) / 7 完成率% / 8 生产批号 / 9 特殊要求(颜色) / ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import openpyxl

from modules.production.mapping import (
    apply_great_wall_reverse,
    parse_color_from_sheet_name,
    parse_variant_from_sheet_name,
)

# 台账明细 sheet 的表头行（第 2 行是表头，第 3 行是期初库存，第 4 行起是明细）
LEDGER_HEADER_ROW = 2
LEDGER_MIN_ROW = 4

# 生产计划列号（openpyxl 1-based）
COL_NAME = 1          # 品名
COL_SPEC = 2          # 规格
COL_CATEGORY = 3      # 类别（区段）
COL_CUSTOMER = 4      # 客户名称/库存计划
COL_PLAN_QTY = 5      # 未完成数量（计划数）
COL_DONE = 6          # {N}月份实际完成（动态）
COL_BATCH = 9         # 生产批号（第8列为空占位，批号实际在第9列）
COL_COLOR = 10        # 特殊要求（颜色）

# Excel 日期序列号基准
_EXCEL_EPOCH = datetime(1899, 12, 30)


def excel_date_to_str(v) -> str:
    """日期值 -> 'YYYY-MM-DD'；文本日期原样返回；None/无法解析返回 ''。

    支持 datetime/date 对象（zip 直读会把 Excel 日期单元格解析成 datetime）、
    Excel 日期序列号（int/float）、纯文本日期字符串三种形态。
    """
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, (int, float)):
        try:
            d = _EXCEL_EPOCH + timedelta(days=int(v))
            return d.strftime("%Y-%m-%d")
        except (OverflowError, ValueError):
            return ""
    return str(v).strip()


def norm_month(v) -> str:
    """各种日期格式归一化为 'YYYY-MM'；无法解析返回 ''。

    支持 datetime/date 对象、Excel 序列号、'YYYY-MM-DD'、'YYYY-MM-DD HH:MM:SS'、
    'YYYY.MM.DD'、'YYYY/MM/DD'、'YYYY-MM' 等形态。
    """
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m")
    if isinstance(v, (int, float)):
        try:
            d = _EXCEL_EPOCH + timedelta(days=int(v))
            return d.strftime("%Y-%m")
        except (OverflowError, ValueError):
            return ""
    s = str(v).strip()
    # 去掉 'YYYY-MM-DD HH:MM:SS' 的时分秒部分
    if " " in s:
        s = s.split(" ")[0]
    for sep in ("-", ".", "/"):
        parts = s.split(sep)
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            y, m, _ = parts
            if len(y) == 4 and len(m) in (1, 2):
                return f"{y}-{int(m):02d}"
    parts = s.split("-")
    if len(parts) == 2 and all(p.isdigit() for p in parts) and len(parts[0]) == 4:
        return f"{parts[0]}-{int(parts[1]):02d}"
    return ""


@dataclass
class InboundRecord:
    """一条台账入库记录。"""
    sheet: str           # 来源 sheet 名（品类明细）
    date: str            # 'YYYY-MM-DD'
    batch: str           # 批号（非空）
    color: str           # 解析后的颜色
    color_explicit: bool # 颜色是否来自明确后缀
    variant: str         # "加长" 或 ""
    customer: Optional[str]  # 客户名称
    inbound: float       # 入库数量


@dataclass
class PlanRow:
    """生产计划的一行数据（用 openpyxl 定位，row_idx 为真实 Excel 行号）。"""
    row_idx: int         # Excel 实际行号（1 起，含表头）
    section: str         # 区段：历史月份 / 世达订单 / 当月库存 / 当月订单
    name: str            # 品名
    spec: str            # 规格
    customer: Optional[str]  # 客户名称/库存计划（D 列）
    plan_qty: Optional[float]  # 计划数（E 列，未完成数量）
    batch: Optional[str] # 生产批号（H 列）
    color: Optional[str] # 特殊要求（I 列，颜色）


@dataclass
class ExceptionItem:
    """一条未匹配异常。"""
    batch: str
    color: str
    inbound: float
    reason: str
    sheet: str
    date: str
    customer: Optional[str] = None


def list_ledger_sheets(ledger_path: str) -> List[str]:
    """读取台账所有 sheet 名。"""
    import zipfile
    from xml.etree import ElementTree as ET
    NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    with zipfile.ZipFile(ledger_path) as zf:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        return [s.get("name") for s in wb.iter(f"{{{NS}}}sheet")]


def read_inbound_records(ledger_path: str, target_month: str) -> List[InboundRecord]:
    """遍历台账所有品类明细 sheet，筛出当月（target_month）入库记录。

    筛选条件：批号非空 + 入库数量 > 0 + 日期归属 target_month。
    """
    from app.data_model.excel_reader import read_excel_table

    records: List[InboundRecord] = []
    for sheet_name in list_ledger_sheets(ledger_path):
        if sheet_name == "汇总看板":
            continue
        t = read_excel_table(
            ledger_path, "成品入出库台账", sheet_name=sheet_name, header_row=LEDGER_HEADER_ROW
        )
        color, explicit = parse_color_from_sheet_name(sheet_name)
        variant = parse_variant_from_sheet_name(sheet_name)
        for row in t.rows:
            batch = row.get("批号")
            if batch is None or str(batch).strip() == "":
                continue
            inbound = row.get("入库数量")
            if inbound is None:
                continue
            try:
                inbound_f = float(inbound)
            except (TypeError, ValueError):
                continue
            if inbound_f <= 0:
                continue
            date_str = excel_date_to_str(row.get("日期"))
            if norm_month(date_str) != target_month:
                continue
            customer = row.get("客户名称/库存计划")
            records.append(InboundRecord(
                sheet=sheet_name,
                date=date_str,
                batch=str(batch).strip(),
                color=color,
                color_explicit=explicit,
                variant=variant,
                customer=str(customer).strip() if customer is not None else None,
                inbound=inbound_f,
            ))
    return records


def read_production_plan(ws) -> List[PlanRow]:
    """读取生产计划当月表（openpyxl worksheet），识别区段/数据行，返回数据行。

    区段判定：类别列（C 列）的值即区段（历史月份/世达订单/当月库存/当月订单）。
    数据行要求：品名非空，且非「品名」表头、非「合计」行。
    """
    rows: List[PlanRow] = []
    current_section = ""
    for r in range(1, ws.max_row + 1):
        name = ws.cell(row=r, column=COL_NAME).value
        spec = ws.cell(row=r, column=COL_SPEC).value
        category = ws.cell(row=r, column=COL_CATEGORY).value
        batch = ws.cell(row=r, column=COL_BATCH).value

        # 表头行
        if name is not None and str(name).strip() == "品名":
            continue
        # 合计行
        if name is not None and str(name).strip() == "合计":
            continue
        # 空行（品名/规格/类别/批号全空）
        if not name and not spec and not category and not batch:
            continue

        # 区段推进：类别列有值则更新当前区段
        if category is not None and str(category).strip() not in ("", " "):
            current_section = str(category).strip()
        section = current_section

        plan_qty_raw = ws.cell(row=r, column=COL_PLAN_QTY).value
        try:
            plan_qty = float(plan_qty_raw) if plan_qty_raw is not None else None
        except (TypeError, ValueError):
            plan_qty = None

        rows.append(PlanRow(
            row_idx=r,
            section=section,
            name=str(name).strip() if name is not None else "",
            spec=str(spec).strip() if spec is not None else "",
            customer=ws.cell(row=r, column=COL_CUSTOMER).value,
            plan_qty=plan_qty,
            batch=str(batch).strip() if batch is not None else None,
            color=ws.cell(row=r, column=COL_COLOR).value,
        ))
    return rows


def _is_real_customer(v) -> bool:
    """判断计划 D 列值是否为真实客户名（非库存计划/安全库存等）。"""
    if v is None:
        return False
    s = str(v).strip()
    if s == "":
        return False
    if s in ("库存计划", "安全库存", "安全库存(月度目标)", "—", "-"):
        return False
    try:
        float(s)
        return False
    except (TypeError, ValueError):
        return True


def _customer_matches(inbound_customer: str, plan_customer: str) -> bool:
    """双向子串部分匹配。"""
    return inbound_customer in plan_customer or plan_customer in inbound_customer


def _color_filter_applies(section: str) -> bool:
    """颜色筛选仅作用于当月库存 / 当月订单区段。"""
    return section in ("当月库存", "当月订单")


def aggregate_inbound(records: List[InboundRecord]) -> Dict[Tuple[str, str, str], dict]:
    """按 (批号, 颜色, 变体) 聚合当月入库量。"""
    agg: Dict[Tuple[str, str, str], dict] = {}
    for r in records:
        color = apply_great_wall_reverse(r.color, r.color_explicit, r.customer)
        key = (r.batch, color, r.variant)
        if key not in agg:
            agg[key] = {"batch": r.batch, "color": color, "variant": r.variant,
                        "total": 0.0, "customers": set(), "records": []}
        agg[key]["total"] += r.inbound
        if r.customer:
            agg[key]["customers"].add(r.customer)
        agg[key]["records"].append(r)
    return agg


def match_and_distribute(
    aggregated: Dict[Tuple[str, str, str], dict],
    plan_rows: List[PlanRow],
) -> Tuple[Dict[int, float], List[ExceptionItem]]:
    """将聚合后的入库量分配到生产计划行，返回 (行号->F值, 异常清单)。

    注意：异常不丢弃「能填的」，能填的照常算出 fill_map；
    是否落盘由调用方根据「是否有异常」决定（异常即暂停覆盖）。
    """
    batch_index: Dict[str, List[PlanRow]] = {}
    for pr in plan_rows:
        if pr.batch:
            batch_index.setdefault(pr.batch, []).append(pr)

    fill_map: Dict[int, float] = {}
    exceptions: List[ExceptionItem] = []

    for key, item in aggregated.items():
        batch, color, variant = key
        total = item["total"]
        candidates = batch_index.get(batch, [])
        if not candidates:
            for rec in item["records"]:
                exceptions.append(ExceptionItem(
                    batch=batch, color=color, inbound=rec.inbound,
                    reason="批号不在生产计划中", sheet=rec.sheet,
                    date=rec.date, customer=rec.customer,
                ))
            continue

        # 颜色筛选（仅当月库存/当月订单区段）
        color_candidates = candidates
        if _color_filter_applies("当月库存") or _color_filter_applies("当月订单"):
            color_candidates = [
                c for c in candidates
                if not _color_filter_applies(c.section)
                or (c.color is not None and str(c.color).strip() == color)
            ]
            if not color_candidates:
                color_candidates = candidates

        if not color_candidates:
            for rec in item["records"]:
                exceptions.append(ExceptionItem(
                    batch=batch, color=color, inbound=rec.inbound,
                    reason=f"颜色不匹配（入库={color}，计划中无此颜色行）",
                    sheet=rec.sheet, date=rec.date, customer=rec.customer,
                ))
            continue

        _distribute_to_rows(
            batch=batch, color=color, variant=variant, total=total,
            candidates=color_candidates, item=item, fill_map=fill_map,
            exceptions=exceptions,
        )
    return fill_map, exceptions


def _distribute_to_rows(batch, color, variant, total, candidates, item, fill_map, exceptions):
    """把 total 分配到候选行列表。客户优先 + 行顺序，末行兜底。"""
    customers = item["customers"]

    def sort_key(pr: PlanRow):
        has_match = False
        if customers:
            for c in customers:
                if pr.customer and _is_real_customer(pr.customer) and _customer_matches(c, str(pr.customer)):
                    has_match = True
                    break
        return (0 if has_match else 1, pr.row_idx)

    sorted_candidates = sorted(candidates, key=sort_key)

    if len(sorted_candidates) > 1 and variant:
        def variant_key(pr: PlanRow):
            if variant == "加长":
                return (0 if pr.section == "当月订单" else 1, pr.row_idx)
            else:
                return (0 if pr.section == "当月库存" else 1, pr.row_idx)
        sorted_candidates = sorted(sorted_candidates, key=variant_key)

    remaining = total
    for i, pr in enumerate(sorted_candidates):
        if i == len(sorted_candidates) - 1:
            fill_map[pr.row_idx] = fill_map.get(pr.row_idx, 0.0) + remaining
            remaining = 0.0
        else:
            cap = pr.plan_qty if pr.plan_qty is not None else float("inf")
            alloc = min(remaining, cap)
            fill_map[pr.row_idx] = fill_map.get(pr.row_idx, 0.0) + alloc
            remaining -= alloc
            if remaining <= 0:
                break

    if remaining > 0:
        exceptions.append(ExceptionItem(
            batch=batch, color=color, inbound=remaining,
            reason=f"入库数超出计划总数（剩余{remaining}件无法分配）",
            sheet=item["records"][0].sheet, date=item["records"][0].date,
            customer=item["records"][0].customer,
        ))


def resolve_plan_file() -> str:
    """定位最新生产计划文件（复用 dashboard_calc 的逻辑）。"""
    from modules.production import dashboard_calc
    return dashboard_calc.resolve_plan_file()


def resolve_ledger_file() -> str:
    """定位最新成品入出库台账（按文件修改时间最新，排除 _修复 派生件）。"""
    import glob
    import os
    from modules.production.scheduling.plan_file_utils import DATA_DIR
    candidates = [p for p in glob.glob(os.path.join(DATA_DIR, "*台账*.xlsx"))
                  if not os.path.basename(p).startswith("~$")
                  and "_修复" not in os.path.basename(p)]
    if not candidates:
        raise FileNotFoundError("未找到成品入出库台账（data/raw/*台账*.xlsx）")
    return max(candidates, key=lambda p: os.path.getmtime(p))


def run_backfill(target_month: Optional[str] = None, commit: bool = True) -> Dict:
    """执行一次入库填报。

    target_month: 目标月份 'YYYY-MM'，默认取最新生产计划文件的当月 sheet。
    commit: 是否真正覆盖写入。调用方应只在异常=0 时传 commit=True。

    返回：
    {
        "plan_file": 生产计划文件,
        "ledger_file": 台账文件,
        "month": 月份数字,
        "sheet_name": 目标 sheet,
        "inbound_records": 入库记录数,
        "matched": 匹配到的行数,
        "fill_map": {行号: 值},
        "exceptions": [异常清单],
        "exception_count": 异常数,
        "committed": 是否已覆盖写入,
    }
    """
    plan_file = resolve_plan_file()
    ledger_file = resolve_ledger_file()

    # 先修复坏样式，拿到 openpyxl 可读文件（WPS 文件常见坏 Fill 样式）
    from modules.production.scheduling.plan_file_utils import ensure_readable
    readable = ensure_readable(plan_file, quiet=True)

    # 定位目标 sheet（最新月份的成品计划 sheet）
    import re
    from modules.production import dashboard_calc
    months = dashboard_calc.scan_months(readable)
    if not months:
        raise ValueError("生产计划文件中无「{N}月份成品计划」sheet")
    month = max(months)
    sheet_name = f"{month}月份成品计划"
    target = target_month or f"2026-{month:02d}"

    # 读台账入库记录
    ledger_path = ledger_file
    records = read_inbound_records(ledger_path, target)

    # 台账当月无入库记录 → 无可填报数据，直接返回（不写文件、不报成功）
    if not records:
        return {
            "plan_file": plan_file,
            "ledger_file": ledger_file,
            "month": month,
            "sheet_name": sheet_name,
            "inbound_records": 0,
            "matched": 0,
            "fill_map": {},
            "exceptions": [],
            "exception_count": 0,
            "committed": False,
            "no_inbound": True,
        }

    # 读生产计划
    wb = openpyxl.load_workbook(readable)
    ws = wb[sheet_name]
    plan_rows = read_production_plan(ws)

    # 匹配 + 分配
    aggregated = aggregate_inbound(records)
    fill_map, exceptions = match_and_distribute(aggregated, plan_rows)

    result = {
        "plan_file": plan_file,
        "ledger_file": ledger_file,
        "month": month,
        "sheet_name": sheet_name,
        "inbound_records": len(records),
        "matched": len(fill_map),
        "fill_map": fill_map,
        "exceptions": [
            {
                "batch": e.batch, "color": e.color, "inbound": e.inbound,
                "reason": e.reason, "sheet": e.sheet, "date": e.date,
                "customer": e.customer,
            }
            for e in exceptions
        ],
        "exception_count": len(exceptions),
        "committed": False,
    }

    # 异常即暂停覆盖
    if exceptions:
        wb.close()
        return result

    # 异常清零 → 写入覆盖
    if commit:
        for row_idx, value in fill_map.items():
            ws.cell(row=row_idx, column=COL_DONE, value=value)
        try:
            from modules.production.scheduling.plan_file_utils import ensure_writable
            ensure_writable(plan_file)
            wb.save(plan_file)
        except (PermissionError, OSError) as e:
            from modules.production.scheduling.plan_file_utils import friendly_file_error
            wb.close()
            raise RuntimeError(friendly_file_error(e, plan_file)) from e
        result["committed"] = True
    wb.close()
    return result
