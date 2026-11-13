"""质量管理模块数据读取层（quality-dashboard 能力，任务 1）。

数据源：data/raw/ 下两份本地 Excel：
- 车间各工序质量抽检记录表.xlsx：WPS 坏样式文件；
  月份子表名含尾随空格（`3月份 ` 等），需 strip 归一；另有非月份 sheet `Sheet4`/`报废` 需排除。
  表头第 1 行、26 列：日期/姓名/工段（机加工/热处理/装配）/配件名称/规格/工作量/
  抽检数量/合格数量/合格率/问题描述/处置方式（返工/更换零件/让步接受/报废）。
- 毛坯来料检验记录v2.xlsx：sheet「来料检验记录」第 1 行空、第 2 行表头，10 列：
  检验日期/供货单位/物料名称/规格/来料数量/抽检数量/检验结果/问题描述/处置方式/硬度检测HRC。

设计原则：
- 读取层只负责「怎么读」，聚合层（aggregate）只负责「怎么算」。
- 只统计「日期/检验日期」非空的行，跳过表头与空行（历史脚本曾因未去空行导致记录虚高）。
- 采用 zip 直读（app.data_model.excel_reader.read_all_sheets），
  直接解析 xlsx 的 zip 结构，绕过 openpyxl 对 WPS 坏样式的兼容问题——
  不再现场修复临时文件，天然规避并发读写同一修复件的竞争（曾导致 Truncated file header）。
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from app.data_model.excel_reader import read_all_sheets, read_all_sheets_cached

# 项目根（相对本文件定位，保证任意 cwd 下可运行）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(_PROJECT_ROOT, "data", "raw")

# 文件名关键字
INSPECTION_KEYWORD = "车间各工序质量抽检记录表"
MATERIAL_KEYWORD = "毛坯来料检验记录v2"

# 非月份 sheet（需排除）
NON_MONTH_SHEETS = {"Sheet4", "报废"}


def _resolve_latest_file(keyword: str) -> Optional[str]:
    """定位 data/raw 下匹配 keyword 的最新文件（排除 ~$ 锁文件与 _修复 派生件）。"""
    import glob
    pattern = os.path.join(DATA_DIR, f"*{keyword}*.xlsx")
    candidates = [
        p for p in glob.glob(pattern)
        if not os.path.basename(p).startswith("~$") and "_修复" not in os.path.basename(p)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: os.path.getmtime(p))


def _resolve_inspection_file() -> Optional[str]:
    """定位车间抽检表最新文件（zip 直读，无需修复坏样式）。"""
    return _resolve_latest_file(INSPECTION_KEYWORD)


def _resolve_material_file() -> Optional[str]:
    """定位原料来料检验表最新文件。"""
    return _resolve_latest_file(MATERIAL_KEYWORD)


def _load_inspection_sheets() -> List[tuple]:
    """zip 直读车间抽检表所有 sheet，返回 [(原始sheet名, [(行号,{列号:值})...])...]。

    一次性解析、无写操作、无共享状态，可安全并发（多个接口同时调用不冲突）。
    """
    path = _resolve_inspection_file()
    if path is None:
        return []
    return read_all_sheets_cached(path)


def _num(v) -> float:
    """安全转数值；空/非数值返回 0。"""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return 0.0


def _cell_s(v) -> str:
    """安全转字符串（strip）。"""
    if v is None:
        return ""
    return str(v).strip()


def month_sheet_names() -> List[str]:
    """返回车间抽检表的月份 sheet 名列表（归一化后，如 `1-2月`、`3月`…`10月`），按出现顺序。"""
    sheets = _load_inspection_sheets()
    result = []
    for sn, _rows in sheets:
        name = sn.strip()
        if name in NON_MONTH_SHEETS:
            continue
        # 匹配「N月份」或「N月」或「N-N月份」
        if re.search(r"\d+(-\d+)?月份?$", name):
            result.append(name)
    return result


def month_label(sheet_name: str) -> str:
    """月份 sheet 名 -> 展示标签。`1-2月份` -> `1-2月`；`3月份` -> `3月`。"""
    name = sheet_name.strip()
    m = re.search(r"(\d+(?:-\d+)?)月份?$", name)
    if m:
        return f"{m.group(1)}月"
    return name


def is_new_version(sheet_name: str) -> bool:
    """判断某月份 sheet 是新版（6月起，含工段列）还是旧版（1-5月，无工段列）。

    依据第 1 行第 3 列表头：新版为「工段（…）」，旧版为「配件名称」。
    """
    sheets = _load_inspection_sheets()
    for sn, rows in sheets:
        if sn.strip() == sheet_name.strip():
            header3 = _grid_cell(rows, 1, 3)
            return "工段" in header3
    return False


def load_all_months() -> Dict[str, Dict[str, Any]]:
    """一次性加载车间抽检表所有月份数据（zip 直读，避免逐 sheet 重复解析的 IO 开销）。

    返回 {月份标签: {"is_new": bool, "rows": [行...]}}。
    """
    sheets = _load_inspection_sheets()
    result: Dict[str, Dict[str, Any]] = {}
    for sn, rows in sheets:
        name = sn.strip()
        if name in NON_MONTH_SHEETS:
            continue
        if not re.search(r"\d+(-\d+)?月份?$", name):
            continue
        is_new = "工段" in _grid_cell(rows, 1, 3)
        result[month_label(name)] = {"is_new": is_new, "rows": _read_rows_from_grid(rows, is_new)}
    return result


def _grid_cell(rows: List[tuple], row_num: int, col_num: int) -> str:
    """从 zip 直读的行网格里取指定单元格的字符串值（空/缺失返回空串）。"""
    for rn, row_data in rows:
        if rn == row_num:
            return _cell_s(row_data.get(col_num))
    return ""


def _read_rows_from_grid(rows_grid: List[tuple], is_new: bool) -> List[Dict[str, Any]]:
    """从 zip 直读的行网格提取数据行（第 2 行起，跳过日期空行）。"""
    rows = []
    for rn, row_data in rows_grid:
        if rn < 2:
            continue
        date = _cell_s(row_data.get(1))
        if not date:
            continue
        if is_new:
            rows.append({
                "date": date,
                "name": _cell_s(row_data.get(2)),
                "section": _cell_s(row_data.get(3)),
                "part": _cell_s(row_data.get(4)),
                "spec": _cell_s(row_data.get(5)),
                "workload": _num(row_data.get(6)),
                "checked": _num(row_data.get(7)),
                "qualified": _num(row_data.get(8)),
                "rate": _num(row_data.get(9)),
                "problem": _cell_s(row_data.get(10)),
                "disp": _cell_s(row_data.get(11)),
            })
        else:
            rows.append({
                "date": date,
                "name": _cell_s(row_data.get(2)),
                "section": "",
                "part": _cell_s(row_data.get(3)),
                "spec": _cell_s(row_data.get(4)),
                "workload": _num(row_data.get(5)),
                "checked": _num(row_data.get(6)),
                "qualified": _num(row_data.get(7)),
                "rate": _num(row_data.get(8)),
                "problem": "",
                "disp": "",
            })
    return rows


def read_inspection_sheet(sheet_name: str) -> List[Dict[str, Any]]:
    """读取车间抽检表某个月份 sheet，返回 [{date, name, section, part, spec, workload, checked, qualified, rate, problem, disp}]。

    只取「日期」非空的行；跳过表头行（第 1 行）。
    表头列顺序固定：1日期 2姓名 3工段 4配件名称 5规格 6工作量 7抽检数量 8合格数量 9合格率 10问题描述 11处置方式。
    """
    sheets = _load_inspection_sheets()
    for sn, rows in sheets:
        if sn.strip() == sheet_name.strip():
            is_new = "工段" in _grid_cell(rows, 1, 3)
            return _read_rows_from_grid(rows, is_new)
    return []


def read_material_records() -> List[Dict[str, Any]]:
    """读取原料来料检验表「来料检验记录」sheet，返回 [{date, supplier, material, spec, qty, checked, result, problem, disp, hardness}]。

    表头在第 2 行（第 1 行为空），数据从第 3 行起；只取「检验日期」非空的行。
    10 列：检验日期/供货单位/物料名称/规格/来料数量/抽检数量/检验结果/问题描述/处置方式/硬度检测HRC。
    """
    path = _resolve_material_file()
    if path is None:
        return []
    sheets = read_all_sheets_cached(path)
    target = None
    for sn, rows in sheets:
        if sn.strip() == "来料检验记录":
            target = rows
            break
    if target is None:
        return []
    result = []
    # 第 1 行空、第 2 行表头，数据从第 3 行起
    for rn, row in target:
        if rn < 3:
            continue
        date = _cell_s(row.get(1))
        if not date:
            continue
        result.append({
            "date": date,
            "supplier": _cell_s(row.get(2)),
            "material": _cell_s(row.get(3)),
            "spec": _cell_s(row.get(4)),
            "qty": _num(row.get(5)),
            "checked": _num(row.get(6)),
            "result": _cell_s(row.get(7)),
            "problem": _cell_s(row.get(8)),
            "disp": _cell_s(row.get(9)),
            "hardness": _cell_s(row.get(10)),
        })
    return result


def inspection_file_info() -> Dict[str, Any]:
    """返回车间抽检表文件信息 {file_name, mtime}（供数据来源标注）。"""
    path = _resolve_inspection_file()
    if path is None:
        return {"file_name": None, "mtime": None}
    from datetime import datetime
    return {
        "file_name": os.path.basename(path),
        "mtime": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M"),
    }


def material_file_info() -> Dict[str, Any]:
    """返回原料检验表文件信息 {file_name, mtime}。"""
    path = _resolve_material_file()
    if path is None:
        return {"file_name": None, "mtime": None}
    from datetime import datetime
    return {
        "file_name": os.path.basename(path),
        "mtime": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M"),
    }
