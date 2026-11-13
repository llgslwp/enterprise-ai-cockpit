"""生产缺口统计（production-planning 能力，网页直显 V2.0 排产结果）。

数据源：data/output/ 下最新的「半成品生产计划V2.0_结果_*.xlsx」。
该结果文件由排产链路生成：
- C~I 列（毛坯库/机加工/热处理/待处理/外协/半成品/装配）为已填数值
- J/K 列（成品计划）为已填数值（蓝色单元格）
- L/M/N 列（半成品需求/装配缺口/机加工）为 Excel 公式，无缓存值

本模块用 formulas 库解析并计算 L/M/N 公式，得到与 Excel 打开时完全一致的缺口数值，
再与 openpyxl 读到的 C~I、J/K 数值、块结构、单元格颜色组装成结构化数据，供前端直显。

关键：
- formulas 库的 key 格式为 '["文件名"]sheet名'!单元格（文件名不含路径）。
- 列号差异：加力/美式 14 列（J/K 两个成品计划），内管/钻杆/套管 13 列（仅 J）。
- 借用行（L 列写「见XX」文本）无缺口公式，前端显示「见XX」文本。
"""

from __future__ import annotations

import glob
import os
from typing import Any, Dict, List, Optional

import openpyxl

# 项目根（相对本文件定位，保证任意 cwd 下可运行，换电脑/换启动目录不失效）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 颜色常量（与 Excel 填充色一致）
FILL_BLUE = "FF00B0F0"     # 成品计划数值（蓝底白字）
FILL_GREEN = "FF92D050"    # 绿底（加力特殊行）
FILL_YELLOW = "FFFFFF00"   # 黄底（借用/特殊配件名）
FILL_ORANGE = "FFFFC000"   # 橙底（借用/特殊配件名）
FILL_RED = "FFFF0000"      # 红底（钻杆钳特殊行）
FILL_WHITE = "FFFFFFFF"    # 白底

# 品类 sheet 顺序
PRODUCT_SHEETS = ("加力", "美式", "内管钳", "钻杆钳", "套管钳")

# 块头行的产品名（A 列取值，用于区分「块头行」与「数据行」）
PRODUCT_NAMES = {
    "加力": "加力管钳",
    "美式": "美式重型/含钛",
    "内管钳": "内管钳",
    "钻杆钳": "钻杆钳",
    "套管钳": "套管钳",
}

# 列号常量（1-based，基础列；成品计划/缺口列由 _find_cols 动态定位）
COL_NAME = 1      # A 配件名称
COL_SPEC = 2      # B 规格
COL_MAOPI = 3     # C 毛坯库
COL_JIJIA = 4     # D 机加工
COL_RECHULI = 5   # E 热处理
COL_DAICHULI = 6  # F 待处理
COL_WAIXIE = 7    # G 外协
COL_BANCHENG = 8  # H 半成品
COL_ZHUANGPEI = 9 # I 装配


def _find_cols(row2_cells) -> Dict[str, int]:
    """动态定位关键列号（按块头行 R2 的标题关键词）。

    返回 {'name':1, 'spec':2, 'maopi':3, ..., 'plan1':J列, 'plan2':K列(可选),
          'need':半成品需求列, 'gap':装配缺口列, 'machine':机加工列}
    不同品类列数不同：加力/美式 14 列（J/K 两个成品计划），内管/钻杆/套管 13 列。
    """
    cols = {
        "name": COL_NAME, "spec": COL_SPEC,
        "maopi": COL_MAOPI, "jijia": COL_JIJIA, "rechuli": COL_RECHULI,
        "daichuli": COL_DAICHULI, "waixie": COL_WAIXIE, "bancheng": COL_BANCHENG,
        "zhuangpei": COL_ZHUANGPEI,
    }
    # 在 R2（块头行）扫描标题列
    for idx, cell in enumerate(row2_cells, start=1):
        v = cell.value
        if v is None:
            continue
        s = str(v).strip()
        if s.startswith("成品计划") and "plan1" not in cols:
            cols["plan1"] = idx
        elif s.startswith("成品计划") and "plan1" in cols and "plan2" not in cols:
            cols["plan2"] = idx
        elif s == "半成品需求计划":
            cols["need"] = idx
        elif s == "装配缺口":
            cols["gap"] = idx
        elif s == "机加工生产计划":
            cols["machine"] = idx
    return cols


def resolve_result_file() -> str:
    """定位排产结果文件 = V2.0 基底原文件（方案A：排产覆盖基底，gap-stat 读同一份）。

    精确定位 data/raw/半成品生产计划V2.0.xlsx（用户已去掉日期前缀）。
    """
    import glob
    candidates = [p for p in glob.glob(os.path.join(_PROJECT_ROOT, "data", "raw", "半成品生产计划*.xlsx"))
                  if not os.path.basename(p).startswith("~$")
                  and "_修复" not in os.path.basename(p)]
    if not candidates:
        raise FileNotFoundError("未找到排产结果文件（data/raw/半成品生产计划V2.0.xlsx）")
    exact = [p for p in candidates if os.path.basename(p) == "半成品生产计划V2.0.xlsx"]
    pool = exact or candidates
    return max(pool, key=os.path.getmtime)


def _num(v) -> Optional[float]:
    """单元格值转 float；None/公式串返回 None（调用方决定默认）。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        if v.startswith("="):
            return None  # 公式串，交给 formulas 计算
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    return None


def _fill_rgb(cell) -> str:
    """取单元格填充色（solid 填充的 fgColor rgb），无则空串。"""
    try:
        fill = cell.fill
        if fill and fill.fill_type == "solid":
            rgb = fill.fgColor.rgb
            if rgb:
                return str(rgb)
    except Exception:
        pass
    return ""


def _font_color(cell) -> str:
    """取单元格字体色，无则空串。"""
    try:
        font = cell.font
        if font and font.color:
            rgb = font.color.rgb
            if rgb:
                return str(rgb)
    except Exception:
        pass
    return ""


def _col_letter(n: int) -> str:
    """列号转字母（1->A, 10->J, 14->N）。"""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _parse_group_spec(sheet: str, group_spec: str) -> Dict[str, str]:
    """解析块头标签，返回各成品计划列的标题映射。

    加力 '80D/18"' → {J: '成品计划80D', K: '成品计划18"'}
    加力 '108D'    → {J: '成品计划108D'}（仅公制，无英寸）
    美式 '18"'     → {J: '成品计划', K: '成品计划（含钛）'}
    其他 'S73'     → {J: '成品计划'}
    """
    result = {"J": "成品计划"}
    if sheet == "加力":
        # 块头形如 80D/18"（公制/英寸）或 108D（仅公制）；按 / 拆分动态取名，杜绝硬编码 80D/18"
        gs = str(group_spec).strip()
        if "/" in gs:
            metric, inch = gs.split("/", 1)
            result["J"] = f"成品计划{metric.strip()}"
            result["K"] = f"成品计划{inch.strip()}"
        else:
            result["J"] = f"成品计划{gs}"
    elif sheet == "美式":
        result["K"] = "成品计划（含钛）"
    return result


def extract_gap_stat(path: str) -> Dict[str, Any]:
    """提取全部品类的缺口统计表格数据。

    返回 {"file": 文件名, "products": {品类: {sheets: [...]}}}
    每个 sheet 块包含：block_label、headers、rows。
    """
    fname = os.path.basename(path)

    # 1. 用自研轻量求值器计算公式（L/M/N 缺口值），替代 formulas 库（loads 要 ~2.2s）
    from .formula_eval import calc_sheet_formulas
    formula_results = calc_sheet_formulas(path)

    def calc_val(sheet: str, row: int, col: int) -> Optional[float]:
        """从自研求值结果里取某单元格计算值。"""
        v = formula_results.get(sheet, {}).get((row, col))
        return float(v) if v is not None else None

    # 2. 用 openpyxl read_only 流式读结构 + C~I + 成品计划值 + 颜色（read_only 27ms vs data_only 130ms）
    wb = openpyxl.load_workbook(path, read_only=True, data_only=False)
    products: Dict[str, Any] = {}

    for sn in PRODUCT_SHEETS:
        ws = wb[sn]
        grid = list(ws.iter_rows(values_only=False))  # grid[r-1] = 第 r 行的 cell tuple
        if len(grid) < 2:
            products[sn] = {"blocks": []}
            continue
        cols = _find_cols(grid[1])  # R2（索引 1）
        has_plan2 = "plan2" in cols
        blocks: List[Dict[str, Any]] = []
        current_block = None

        for r, row_cells in enumerate(grid, start=1):
            a = row_cells[cols["name"] - 1].value
            b = row_cells[cols["spec"] - 1].value
            c = row_cells[cols["maopi"] - 1].value
            a_s = str(a).strip() if a is not None else ""
            b_s = str(b).strip() if b is not None else ""
            c_s = str(c).strip() if c is not None else ""

            # 标题行 R1（跳过）
            if r == 1:
                continue

            # 块头行：A 列=产品名（加力管钳/美式重型/内管钳/钻杆钳/套管钳）
            if a_s == PRODUCT_NAMES.get(sn, ""):
                group_spec = c_s
                # 解析本块的成品计划列标题
                col_titles = _parse_group_spec(sn, group_spec)
                current_block = {
                    "block_label": group_spec,   # 如 '80D/18"'、'S73'
                    "col_titles": col_titles,     # {J:'成品计划80D', K:'成品计划18"'}
                    "headers": [],                # 表头行（成品计划值）
                    "rows": [],                   # 数据行
                }
                blocks.append(current_block)
                continue

            # 表头行：A=配件名称 B=规格
            if a_s == "配件名称" and b_s == "规格":
                if current_block is None:
                    continue
                j_val = _num(row_cells[cols["plan1"] - 1].value)
                j_fill = _fill_rgb(row_cells[cols["plan1"] - 1])
                hdr = {"plan1": {"value": j_val, "fill": j_fill}}
                if has_plan2:
                    k_val = _num(row_cells[cols["plan2"] - 1].value)
                    k_fill = _fill_rgb(row_cells[cols["plan2"] - 1])
                    hdr["plan2"] = {"value": k_val, "fill": k_fill}
                current_block["headers"] = hdr
                continue

            # 数据行 / 组合件行：A 有配件名
            if a_s and a_s not in ("合计",):
                if current_block is None:
                    continue
                row_data = {
                    "row_idx": r,
                    "name": a_s,
                    "spec": b_s,
                    "name_fill": _fill_rgb(row_cells[cols["name"] - 1]),
                    "spec_fill": _fill_rgb(row_cells[cols["spec"] - 1]),
                    "is_assembly": "+" in a_s,   # 组合件行
                    "is_borrow": False,
                    "cells": {},                 # C~I 列
                    "plan": {},                  # 成品计划
                    "gap": {},                   # 缺口（自研求值器计算值）
                    "gap_text": {},              # 借用行文本（如「见S73」）
                }

                # C~I 列（毛坯库 3 ~ 装配 9）
                for col in range(cols["maopi"], cols["zhuangpei"] + 1):
                    v = _num(row_cells[col - 1].value)
                    row_data["cells"][str(col)] = v

                # 成品计划（可能是公式 =N*$J$x，用自研求值器计算值；表头行已是数值）
                p1 = calc_val(sn, r, cols["plan1"])
                if p1 is None:
                    p1 = _num(row_cells[cols["plan1"] - 1].value)
                row_data["plan"]["plan1"] = p1
                if has_plan2:
                    p2 = calc_val(sn, r, cols["plan2"])
                    if p2 is None:
                        p2 = _num(row_cells[cols["plan2"] - 1].value)
                    row_data["plan"]["plan2"] = p2

                # 缺口列：半成品需求 / 装配缺口 / 机加工
                for col, key in ((cols.get("need"), "need"),
                                 (cols.get("gap"), "gap"),
                                 (cols.get("machine"), "machine")):
                    if col is None:
                        continue
                    raw = row_cells[col - 1].value
                    if raw is not None and isinstance(raw, str) and not raw.startswith("="):
                        # 借用行文本
                        row_data["gap_text"][key] = raw
                        if raw.startswith("见"):
                            row_data["is_borrow"] = True
                    else:
                        v = calc_val(sn, r, col)
                        row_data["gap"][key] = v

                current_block["rows"].append(row_data)
                continue

        products[sn] = {"blocks": blocks}

    wb.close()

    return {
        "file": fname,
        "product_sheets": list(PRODUCT_SHEETS),
        "products": products,
    }


def main(argv=None) -> int:
    import json
    path = resolve_result_file()
    data = extract_gap_stat(path)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
