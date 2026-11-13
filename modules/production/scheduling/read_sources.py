"""6 份源文件读取与归集（production-planning 能力，任务 3.1）。

读取 6 份源（毛坯库/车间在产品/半成品库/外协/在产品装配/成品计划），
按名称+规格归集到 V2.0 工序列（C 毛坯库 / D 机加工 / E 热处理 / F 待处理 /
G 外协 / H 半成品 / I 装配 / J 成品计划），产出归集映射。

本模块只负责「读取 + 归集」，不写文件、不算缺口（职责分离，便于 3.2/3.3 复用）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.data_model.excel_reader import read_excel_table
from . import maopi_match
from .plan_file_utils import (
    COLOR_SHEET_NAME,
    PRODUCT_SHEETS,
    find_qty_col,
    normalize_spec,
    resolve_source,
)

import openpyxl


# ---------------------------------------------------------------------------
# V2.0 结构解析
# ---------------------------------------------------------------------------

@dataclass
class PlanRow:
    """V2.0 产品表的一行（数据行或表头行或块头行）。"""
    row_idx: int          # Excel 实际行号（1 起）
    sheet: str            # 所属 sheet（加力/美式/内管钳/钻杆钳/套管钳）
    group_spec: str       # 所属规格块（如 '80D/18"'、'71-75'、'S61'），块头 C 列
    name: str             # 配件名称（A 列）
    spec: str             # 规格（B 列，原始文本）
    kind: str             # 'header' / 'data' / 'group_header' / 'number' / 'other'
    is_borrow: bool = False  # 借用行：L 列（装配缺口）写「见XX」文本，C~I 恒空不归集


@dataclass
class SheetLayout:
    """一个 V2.0 产品表的解析结果。"""
    sheet: str
    rows: List[PlanRow] = field(default_factory=list)
    # 列号定位（1-based）：数据列 C~I，公式/计划列 J~N（不同表末列不同）
    max_col: int = 0
    # 装配缺口列（借用行写「见XX」的列）
    gap_col: int = 0
    # 机加工生产计划列（末列）
    jix_col: int = 0


def _find_header_col(ws, keyword: str) -> int:
    """在表头行（1~3 行）找含 keyword 的列，返回 1-based 列号；找不到返回 -1。"""
    for r in range(1, 4):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(row=r, column=c).value
            if v is not None and keyword in str(v):
                return c
    return -1


def parse_v2_layout(ws, sheet: str) -> SheetLayout:
    """解析一个 V2.0 产品表，识别块头/表头/数据行及关键列号。"""
    layout = SheetLayout(sheet=sheet, max_col=ws.max_column)
    layout.gap_col = _find_header_col(ws, "装配缺口")
    layout.jix_col = _find_header_col(ws, "机加工生产计划")
    if layout.jix_col == -1:
        layout.jix_col = ws.max_column

    current_group = ""
    for r in range(1, ws.max_row + 1):
        a = ws.cell(row=r, column=1).value
        b = ws.cell(row=r, column=2).value
        c = ws.cell(row=r, column=3).value
        a_s = str(a).strip() if a is not None else ""
        b_s = str(b).strip() if b is not None else ""
        c_s = str(c).strip() if c is not None else ""

        # 块头行：A=产品名，C=规格块标签
        if a_s in maopi_match.PRODUCT_NAMES.values() and c_s and a_s != "配件名称":
            current_group = c_s
            layout.rows.append(PlanRow(
                row_idx=r, sheet=sheet, group_spec=c_s, name=a_s, spec="",
                kind="group_header",
            ))
            continue

        # 表头行：A=配件名称 B=规格
        if a_s == "配件名称" and b_s == "规格":
            layout.rows.append(PlanRow(
                row_idx=r, sheet=sheet, group_spec=current_group, name=a_s, spec=b_s,
                kind="header",
            ))
            continue

        # 数据行 / 组合件行 / 借用行：A 有配件名
        if a_s and a_s not in ("合计",):
            # 借用行判定：L 列（装配缺口列）为「见XX」文本
            is_borrow = False
            if layout.gap_col > 0:
                gap_v = ws.cell(row=r, column=layout.gap_col).value
                if gap_v is not None and isinstance(gap_v, str) and gap_v.startswith("见"):
                    is_borrow = True
            layout.rows.append(PlanRow(
                row_idx=r, sheet=sheet, group_spec=current_group, name=a_s, spec=b_s,
                kind="data", is_borrow=is_borrow,
            ))
            continue

    return layout


# ---------------------------------------------------------------------------
# 源文件读取
# ---------------------------------------------------------------------------

def read_source_rows(path: str, sheet_name: Optional[str] = None) -> Tuple[List[dict], List[str]]:
    """读取一个源文件（单 sheet）为行列表 + 列名列表。

    源文件表头在第 1 行，数据从第 2 行起。
    返回 (rows, columns)。
    """
    if sheet_name is None:
        # 取第一个 sheet 名
        import zipfile
        from xml.etree import ElementTree as ET
        NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        with zipfile.ZipFile(path) as zf:
            wb = ET.fromstring(zf.read("xl/workbook.xml"))
            sheet_name = next(
                s.get("name") for s in wb.iter(f"{{{NS}}}sheet")
            )
    t = read_excel_table(path, "源文件", sheet_name=sheet_name, header_row=1)
    return t.rows, t.columns


def aggregate_by_name_spec(rows: List[dict], name_col: str, spec_col: str,
                           qty_col: str) -> Dict[Tuple[str, str], float]:
    """按 (名称, 规格) 聚合数量，规格 rstrip(' |') 后归一。"""
    agg: Dict[Tuple[str, str], float] = {}
    for row in rows:
        name = row.get(name_col)
        spec = row.get(spec_col)
        qty = row.get(qty_col)
        if name is None or spec is None or qty is None:
            continue
        try:
            q = float(qty)
        except (TypeError, ValueError):
            continue
        n = str(name).strip()
        s = str(spec).rstrip(" |").strip()
        agg[(n, s)] = agg.get((n, s), 0.0) + q
    return agg


# ---------------------------------------------------------------------------
# 归集结果容器
# ---------------------------------------------------------------------------

@dataclass
class FillResult:
    """归集结果：{ (sheet, row_idx, column) -> 值 } 与统计/异常。"""
    # column 语义：3=C 毛坯库 4=D 机加工 5=E 热处理 6=F 待处理 7=G 外协 8=H 半成品 9=I 装配 10=J 成品计划
    fills: Dict[Tuple[str, int, int], float] = field(default_factory=dict)
    # 配件-颜色表归集：(名称, 规格, 颜色/特征) -> 数量
    color_fills: List[Tuple[str, str, str, float]] = field(default_factory=list)
    # 统计
    source_totals: Dict[str, float] = field(default_factory=dict)
    unmatched: List[str] = field(default_factory=list)   # 未匹配清单（源有、计划表无对应行）
    zero_fills: int = 0


def _find_target_row(layout: SheetLayout, part_name: str, plan_spec: str,
                     group_spec: str) -> Optional[PlanRow]:
    """在布局中找 (配件名称, 规格, 块规格) 匹配的数据行。"""
    norm_spec = normalize_spec(plan_spec)
    norm_group = normalize_spec(group_spec)
    for row in layout.rows:
        if row.kind != "data":
            continue
        if normalize_spec(row.group_spec) != norm_group:
            continue
        if normalize_spec(row.spec) != norm_spec:
            continue
        if row.name == part_name:
            return row
    # 名称不一致但规格一致（部分行名称可能有细微差异），做名称容错
    for row in layout.rows:
        if row.kind != "data":
            continue
        if normalize_spec(row.group_spec) != norm_group:
            continue
        if normalize_spec(row.spec) != norm_spec:
            continue
        return row
    return None
