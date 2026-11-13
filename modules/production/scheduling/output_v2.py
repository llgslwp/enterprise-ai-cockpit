"""V2.0 结果文件生成（production-planning 能力，任务 3.3）。

把归集结果（C~I 列）+ J 列成品计划数值写入 V2.0 基底副本，
K/L/M/N 列保留原有 Excel 公式，产出到 data/output/。

关键：
- 以当月 V2.0 作基底（A/B 列、块结构、公式列原样保留）。
- 只改 C~I 数据列 + J 列成品计划（蓝色单元格），公式列 K~N 不动。
- 缺口由公式在 Excel 打开时计算，本模块不代码算值。
- WPS 坏样式需先修复（复用 plan_file_utils.ensure_readable）。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Optional, Tuple

import openpyxl

from .plan_file_utils import OUTPUT_DIR, ensure_readable
from .read_sources import FillResult

# 列号常量
COL_MAOPI = 3
COL_ZHUANGPEI = 9
COL_CHENGPIN = 10  # J 列成品计划


def write_v2_result(
    base_path: str,
    result: FillResult,
    chengpin_fills: Optional[Dict[Tuple[str, int, int], float]] = None,
    output_name: Optional[str] = None,
    overwrite_base: bool = True,
) -> str:
    """生成 V2.0 结果文件。

    base_path:      V2.0 基底（当月半成品生产计划V2.0.xlsx）
    result:         归集结果（fills: {(sheet, row, col) -> 值}）
    chengpin_fills: 成品计划填值 {(sheet, row_idx, col) -> 值}；None 则不动
    output_name:    输出文件名；默认带时间戳（仅 overwrite_base=False 时生效）
    overwrite_base: True=覆盖基底原文件本身（方案A）；False=另存结果文件到 data/output/

    返回输出文件路径。
    """
    # 修复样式到临时可读文件
    readable = ensure_readable(base_path, quiet=True)
    wb = openpyxl.load_workbook(readable)

    # 写 C~I 数据列（3~9）
    for (sheet, row_idx, col), value in result.fills.items():
        if col < 3 or col > 9:
            continue
        ws = wb[sheet]
        ws.cell(row=row_idx, column=col, value=value)

    # 写 J/K 列成品计划
    if chengpin_fills:
        for (sheet, row_idx, col), value in chengpin_fills.items():
            wb[sheet].cell(row=row_idx, column=col, value=value)

    # 写配件-颜色表
    _write_color_sheet(wb, result)

    if overwrite_base:
        # 方案A：直接覆盖基底原文件本身（gap-stat 读同一份）
        output_path = base_path
    else:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        if output_name is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"半成品生产计划V2.0_结果_{ts}.xlsx"
        output_path = os.path.join(OUTPUT_DIR, output_name)

    try:
        from .plan_file_utils import ensure_writable
        ensure_writable(output_path)
        wb.save(output_path)
    except (PermissionError, OSError) as e:
        from .plan_file_utils import friendly_file_error
        wb.close()
        raise RuntimeError(friendly_file_error(e, output_path)) from e
    wb.close()

    # 若 readable 是修复副本（与 base_path 不同），清理
    if os.path.abspath(readable) != os.path.abspath(base_path) and "_修复" in readable:
        try:
            os.remove(readable)
        except OSError:
            pass

    return output_path

def _write_color_sheet(wb, result: FillResult) -> None:
    """写配件-颜色表（A=配件名称 B=规格 C=颜色/特征 D=数量）。"""
    from .plan_file_utils import COLOR_SHEET_NAME
    if COLOR_SHEET_NAME not in wb.sheetnames:
        return
    ws = wb[COLOR_SHEET_NAME]
    # 清空第 2 行起
    for r in range(2, ws.max_row + 1):
        for c in range(1, 5):
            ws.cell(row=r, column=c, value=None)
    # 写表头
    ws.cell(row=1, column=1, value="配件名称")
    ws.cell(row=1, column=2, value="规格")
    ws.cell(row=1, column=3, value="颜色/特征")
    ws.cell(row=1, column=4, value="数量")
    # 写数据
    for i, (name, spec, feature, qty) in enumerate(result.color_fills, start=2):
        ws.cell(row=i, column=1, value=name)
        ws.cell(row=i, column=2, value=spec)
        ws.cell(row=i, column=3, value=feature)
        ws.cell(row=i, column=4, value=qty)
