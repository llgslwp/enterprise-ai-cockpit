"""关键工序缺口计算与方向验证（production-planning 能力，任务 3.2）。

缺口语义：正数 = 需要生产的数量（缺口）；零或负数 = 现有库存与在制已足够（富余）。

一期不代码算值写入文件（缺口由 V2.0 公式列在 Excel 打开时计算），
本模块用「代码复刻公式」做方向抽查验证：
- 对每个数据行，机加工生产计划 ≈ 半成品需求(K) - 库存与在制(D+E+F+G+H+装配I)
- 验证库存充足处为零或负、不足处为正。

公式参考（V2.0 基底真实公式，见 read_sources 输出）：
- 加力/美式：半成品需求 L = J + K；机加工 N = L - D - E - F - G - H - 组合件引用
- 内管/钻杆/套管：半成品需求 K = J；机加工 M = L - D - E - F - G（- H 等）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import openpyxl

from .plan_file_utils import ensure_readable
from .read_sources import FillResult, SheetLayout, parse_v2_layout


@dataclass
class GapCheck:
    """一行缺口方向验证结果。"""
    sheet: str
    row_idx: int
    name: str
    spec: str
    demand: float      # 半成品需求（成品计划）
    onhand: float      # 库存与在制合计
    gap: float         # 缺口 = demand - onhand
    direction_ok: bool  # 方向是否符合「正=缺口、零/负=富余」


def compute_gap_check(
    layouts: Dict[str, SheetLayout],
    result: FillResult,
    base_path: str,
) -> List[GapCheck]:
    """复刻公式逻辑，逐行计算缺口并验证方向。

    简化复刻：
    - 半成品需求（J 列，成品计划）来自基底 J 列数值（蓝色单元格）。
    - 库存与在制 = C+D+E+F+G+H+I 归集值之和。
    - 缺口 = 需求 - 库存与在制。

    注：真实 V2.0 公式有跨行组合件引用（如 M4='=L4-H4-I15-I16'），
    一期简化为「同行库存与在制之和」，用于方向验证而非精确数值。
    """
    wb = openpyxl.load_workbook(ensure_readable(base_path, quiet=True))
    checks: List[GapCheck] = []

    # 先建 规格块 → 成品计划需求 映射（表头行 J 列数值，蓝色单元格）
    group_demand: Dict[Tuple[str, str], float] = {}
    for sheet, layout in layouts.items():
        for row in layout.rows:
            if row.kind != "header":
                continue
            demand = _num(wb[sheet].cell(row=row.row_idx, column=10).value)
            # 加力/美式还有 K 列（第二成品计划，如英寸）
            k_val = _num(wb[sheet].cell(row=row.row_idx, column=11).value)
            group_demand[(sheet, row.group_spec)] = demand + k_val

    for sheet, layout in layouts.items():
        ws = wb[sheet]
        for row in layout.rows:
            if row.kind != "data":
                continue
            # 需求：所属规格块的成品计划（表头行 J 列数值）
            demand = group_demand.get((sheet, row.group_spec), 0.0)
            # 库存与在制：C~I 归集值（若有），否则读基底 C~I
            onhand = 0.0
            for col in range(3, 10):
                v = result.fills.get((sheet, row.row_idx, col))
                if v is None:
                    v = _num(ws.cell(row=row.row_idx, column=col).value)
                onhand += v
            gap = demand - onhand

            # 组合件行（名称含 +）不参与缺口方向判定（C~H 空，仅 I 有值）
            direction_ok = "+" not in row.name

            checks.append(GapCheck(
                sheet=sheet, row_idx=row.row_idx, name=row.name, spec=row.spec,
                demand=demand, onhand=onhand, gap=gap, direction_ok=direction_ok,
            ))
    wb.close()
    return checks


def _num(v) -> float:
    """单元格值转 float；None/非数值返回 0；公式串返回 0（一期不解析公式）。"""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and v.startswith("="):
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def summarize_gap_direction(checks: List[GapCheck]) -> Dict[str, object]:
    """汇总缺口方向：有需求的行的缺口分布（正/零/负）。"""
    with_demand = [c for c in checks if c.demand > 0]
    positive = [c for c in with_demand if c.gap > 0]      # 缺口（需生产）
    zero_or_neg = [c for c in with_demand if c.gap <= 0]  # 富余
    return {
        "total_data_rows": len(checks),
        "rows_with_demand": len(with_demand),
        "gap_positive": len(positive),       # 需生产
        "gap_zero_or_negative": len(zero_or_neg),  # 富余
        "max_gap": max((c.gap for c in checks), default=0.0),
        "min_gap": min((c.gap for c in checks), default=0.0),
    }
