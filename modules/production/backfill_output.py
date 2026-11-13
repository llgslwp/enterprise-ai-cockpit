"""回填结果本地产出（production-planning 能力，任务 2.2）。

将回填后的生产计划（F 列已填当月实际完成）写入 data/output/ 独立子目录，
生成一份新的 Excel 文件，保留原生产计划的全部内容，仅改动 F 列。

实现要点：
- 源文件存在 WPS 坏样式 bug（xl/styles.xml 的 <fill/> 空元素），
  需先正则修复 <fill/> -> <fill><patternFill/></fill> 再用 openpyxl 读写。
- 不覆盖源文件，产出到 data/output/ 独立子目录，保持可溯源。
"""

from __future__ import annotations

import os
import re
import zipfile
from datetime import datetime
from typing import Dict, Optional

import openpyxl

# 生产计划 F 列（当月实际完成）的列号（1-based）
F_COLUMN = 6

# 结果输出目录
OUTPUT_DIR = "data/output"


def _fix_wps_style(src_path: str, tmp_path: str):
    """修复 WPS 生成的 xlsx 坏样式（<fill/> 空元素），输出到 tmp_path。"""
    with zipfile.ZipFile(src_path) as zin:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                data = zin.read(item)
                if item == "xl/styles.xml":
                    txt = data.decode("utf-8")
                    txt = re.sub(r"<fill\s*/>", "<fill><patternFill/></fill>", txt)
                    data = txt.encode("utf-8")
                zout.writestr(item, data)


def write_backfill_result(
    plan_path: str,
    sheet_name: str,
    fill_map: Dict[int, float],
    output_name: Optional[str] = None,
) -> str:
    """将回填结果写入 data/output/ 下的新 Excel。

    plan_path:  源生产计划文件路径
    sheet_name: 目标工作表名（当月计划表）
    fill_map:   {Excel行号 -> F列值}
    output_name: 输出文件名（不含路径）；默认带时间戳

    返回输出文件路径。
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 修复样式到临时文件
    tmp_path = os.path.join(OUTPUT_DIR, "_tmp_fixed.xlsx")
    _fix_wps_style(plan_path, tmp_path)

    wb = openpyxl.load_workbook(tmp_path)
    if sheet_name not in wb.sheetnames:
        os.remove(tmp_path)
        raise ValueError(f"工作表不存在: {sheet_name}")

    ws = wb[sheet_name]
    for row_idx, value in fill_map.items():
        ws.cell(row=row_idx, column=F_COLUMN, value=value)

    if output_name is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"生产计划_回填结果_{ts}.xlsx"
    output_path = os.path.join(OUTPUT_DIR, output_name)
    wb.save(output_path)
    wb.close()
    os.remove(tmp_path)

    return output_path


def verify_backfill_result(
    output_path: str,
    sheet_name: str,
    fill_map: Dict[int, float],
    expected_total: Optional[float] = None,
) -> Dict[str, object]:
    """读回输出文件，核对 F 列与 fill_map 一致，返回核对结果。"""
    wb = openpyxl.load_workbook(output_path)
    ws = wb[sheet_name]
    errors = []
    total = 0.0
    for row_idx, expected in fill_map.items():
        actual = ws.cell(row=row_idx, column=F_COLUMN).value
        if actual is None:
            errors.append(f"行{row_idx}: 期望 {expected}，实际为空")
            continue
        try:
            actual_f = float(actual)
        except (TypeError, ValueError):
            errors.append(f"行{row_idx}: 期望 {expected}，实际非数值 {actual!r}")
            continue
        total += actual_f
        if abs(actual_f - expected) > 0.001:
            errors.append(f"行{row_idx}: 期望 {expected}，实际 {actual_f}")
    wb.close()

    result = {"total": total, "errors": errors, "pass": len(errors) == 0}
    if expected_total is not None:
        result["total_match"] = abs(total - expected_total) <= 0.001
        if not result["total_match"]:
            result["pass"] = False
            result["errors"].append(f"总量不符: 期望 {expected_total}，实际 {total}")
    return result
