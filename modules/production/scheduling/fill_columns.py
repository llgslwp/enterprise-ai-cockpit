"""6 源归集到 V2.0 各列（production-planning 能力，任务 3.1）。

把 6 份源文件按名称+规格映射，归集到 V2.0 的 C~J 列：

| 列 | 源 | 分流规则 |
| C | 毛坯库 | 全部汇总 |
| D | 车间在产品 | 状态=机加工 |
| E | 车间在产品 | 状态=热处理 |
| F | 半成品库 | 状态=待处理 |
| G | 外协 | 全部（状态全「外协」）|
| H | 半成品库 | 状态=半成品 |
| I | 在产品装配 | 全部汇总 |
| J | 成品计划 | 未完成量（蓝色单元格）|

规则来源：example/03-全量重跑-开发说明文档.md §8（权威基准）。
本模块只做归集计算（产出 FillResult），不写文件。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import openpyxl

from . import maopi_match
from .plan_file_utils import ensure_readable
from .read_sources import (
    FillResult,
    SheetLayout,
    read_source_rows,
)


# 列号常量（1-based，与 V2.0 结构一致）
COL_MAOPI = 3       # C 毛坯库
COL_JIJIA = 4       # D 机加工
COL_RECHULI = 5     # E 热处理
COL_DAICHULI = 6    # F 待处理
COL_WAIXIE = 7      # G 外协
COL_BANCHENGPIN = 8 # H 半成品
COL_ZHUANGPEI = 9   # I 装配
COL_CHENGPIN = 10   # J 成品计划


# ---------------------------------------------------------------------------
# 通用：读源 → 聚合 → 按名称规格匹配
# ---------------------------------------------------------------------------

def _read_source(path: str):
    """读源文件，返回 (rows, cols, qty_col_name)。"""
    rows, cols = read_source_rows(path)
    qty_col = None
    for c in cols:
        if c in ("现有存量", "数量"):
            qty_col = c
            break
    return rows, cols, qty_col


def _status_split(rows, status_col: str, qty_col: str, name_col: str, spec_col: str):
    """按状态列把源行拆成 {状态: {(归一名称, 归一规格): 数量}}。

    键与 maopi_match.build_source_dict 使用同一归一（_norm 去 φ/引号变体），
    保证 find_source_qty 能命中。
    """
    by_status: Dict[str, Dict[Tuple[str, str], float]] = {}
    for row in rows:
        status = str(row.get(status_col) or "").strip()
        name = row.get(name_col)
        spec = row.get(spec_col)
        qty = row.get(qty_col)
        if name is None or spec is None or qty is None:
            continue
        try:
            q = float(qty)
        except (TypeError, ValueError):
            continue
        key = (maopi_match._norm(maopi_match._merge_name(str(name))),
               maopi_match._norm(str(spec)))
        by_status.setdefault(status, {})
        by_status[status][key] = by_status[status].get(key, 0.0) + q
    return by_status


def is_borrow_row(row) -> bool:
    """判断是否为「借用行」。

    借用行特征：L 列（装配缺口）写「见XX」文本（如「见54-56」），
    表示其库存/计算直接引用被借用块，C~I 列恒空、不应归集。
    该判定在 parse_v2_layout 阶段完成，存入 PlanRow.is_borrow。
    """
    return getattr(row, "is_borrow", False)


def _apply_fill(result: FillResult, layouts: Dict[str, SheetLayout],
                agg: Dict[Tuple[str, str], float], column: int,
                include_assembly: bool = False) -> None:
    """把聚合字典按名称+规格匹配到 V2.0 数据行，填 column 列。

    include_assembly=False（默认）：跳过组合件行（名称含 +），
    因组合件行 C~H 恒空、仅 I 列（装配）有值。
    跳过「借用行」（B 列规格 ≠ 块规格）：其库存由被借用块承担，C~I 恒空。
    """
    for sheet, layout in layouts.items():
        for row in layout.rows:
            if row.kind != "data":
                continue
            if not include_assembly and maopi_match.is_assembly_row(row.name):
                continue
            if is_borrow_row(row):
                continue
            target = maopi_match.resolve_source_target(sheet, row.name, row.spec)
            if target is None:
                continue
            src_name, src_spec = target
            qty = maopi_match.find_source_qty(agg, src_name, src_spec)
            if qty is not None and qty > 0:
                result.fills[(sheet, row.row_idx, column)] = qty


# ---------------------------------------------------------------------------
# 各源填充
# ---------------------------------------------------------------------------

def fill_maopi(src_path: str, layouts: Dict[str, SheetLayout],
               result: FillResult) -> None:
    """毛坯库 → C 列。"""
    rows, cols, qty_col = _read_source(src_path)
    if qty_col is None:
        return
    agg = maopi_match.build_source_dict(rows, "货品名称", "货品规格", qty_col)
    result.source_totals["毛坯库"] = sum(agg.values())
    _apply_fill(result, layouts, agg, COL_MAOPI)


def fill_chejian(src_path: str, layouts: Dict[str, SheetLayout],
                 result: FillResult) -> None:
    """车间在产品 → D 列(机加工) / E 列(热处理)。"""
    rows, cols, qty_col = _read_source(src_path)
    if qty_col is None:
        return
    by_status = _status_split(rows, "库位名称", qty_col, "货品名称", "货品规格")
    result.source_totals["车间在产品"] = sum(
        sum(d.values()) for d in by_status.values())

    status_to_col = {"机加工": COL_JIJIA, "热处理": COL_RECHULI}
    for status, col in status_to_col.items():
        _apply_fill(result, layouts, by_status.get(status, {}), col)


def fill_banchengpin(src_path: str, layouts: Dict[str, SheetLayout],
                     result: FillResult) -> None:
    """半成品库 → F 列(待处理) / H 列(半成品)；把手/加力外管/自由钳外管颜色 → 配件-颜色。"""
    rows, cols, qty_col = _read_source(src_path)
    if qty_col is None:
        return
    by_status = _status_split(rows, "库位名称", qty_col, "货品名称", "货品规格")
    result.source_totals["半成品库"] = sum(
        sum(d.values()) for d in by_status.values())

    status_to_col = {"待处理": COL_DAICHULI, "半成品": COL_BANCHENGPIN}
    for status, col in status_to_col.items():
        _apply_fill(result, layouts, by_status.get(status, {}), col)

    # 颜色明细：半成品状态 + 有特征 + 名称属把手/加力外管/自由钳外管
    color_agg: Dict[Tuple[str, str, str], float] = {}
    for row in rows:
        status = str(row.get("库位名称") or "").strip()
        name = str(row.get("货品名称") or "").strip()
        spec = str(row.get("货品规格") or "").rstrip(" |").strip()
        feature = str(row.get("特征") or "").strip()
        qty = row.get(qty_col)
        if status != "半成品" or not feature or name not in ("把手", "加力外管", "自由钳外管"):
            continue
        if qty is None:
            continue
        try:
            q = float(qty)
        except (TypeError, ValueError):
            continue
        key = (name, spec, feature)
        color_agg[key] = color_agg.get(key, 0.0) + q
    for (name, spec, feature), q in color_agg.items():
        result.color_fills.append((name, spec, feature, q))


def fill_waixie(src_path: str, layouts: Dict[str, SheetLayout],
                result: FillResult) -> None:
    """外协 → G 列。"""
    rows, cols, qty_col = _read_source(src_path)
    if qty_col is None:
        return
    agg = maopi_match.build_source_dict(rows, "货品名称", "货品规格", qty_col)
    result.source_totals["外协"] = sum(agg.values())
    _apply_fill(result, layouts, agg, COL_WAIXIE)


def fill_zaipeizhuangpei(src_path: str, layouts: Dict[str, SheetLayout],
                         result: FillResult) -> None:
    """在产品装配 → I 列。

    特殊规则（权威文档 §8.7）：
    - 覆膜砂按批号拆：名称「美式钳把-覆膜砂」批号含「世达」→ 世达款，
      否则 → 中性款；名称自带「（世达）」后缀 → 世达款。
    """
    rows, cols, qty_col = _read_source(src_path)
    if qty_col is None:
        return
    agg = maopi_match.build_source_dict(rows, "货品名称", "货品规格", qty_col)
    result.source_totals["在产品装配"] = sum(agg.values())
    _apply_fill(result, layouts, agg, COL_ZHUANGPEI, include_assembly=True)

    # 覆膜砂按批号拆分（世达 / 中性）
    _apply_fumosha_fill(result, layouts, rows, qty_col)

    # 组合件行（名称含 +）的装配量：源名称带「（备钳）/（维度）」后缀的不计，
    # 仅匹配名称完全一致 + 规格数字段一致的条目（公制 D 与英寸 ″ 数字段区分）。
    _apply_assembly_fill(result, layouts, agg, COL_ZHUANGPEI)


def _apply_fumosha_fill(result: FillResult, layouts: Dict[str, SheetLayout],
                        rows: List[dict], qty_col: str) -> None:
    """覆膜砂装配量按批号拆成 中性 / 世达 两款。

    源「美式钳把-覆膜砂」批号含「世达」→ 世达，否则 → 中性；
    源「美式钳把-覆膜砂（世达）」→ 世达。
    """
    from .plan_file_utils import normalize_spec
    # 源侧聚合：{(源名称, 数字段): {中性: qty, 世达: qty}}
    fumosha: Dict[Tuple[str, str], Dict[str, float]] = {}
    for row in rows:
        name = str(row.get("货品名称") or "").strip()
        spec = str(row.get("货品规格") or "").strip()
        batch = str(row.get("批号") or "")
        qty = row.get(qty_col)
        if qty is None:
            continue
        try:
            q = float(qty)
        except (TypeError, ValueError):
            continue
        if "覆膜砂" not in name:
            continue
        kind = "世达" if ("世达" in name or "世达" in batch) else "中性"
        base_name = name.replace("（世达）", "")
        num = normalize_spec(spec)
        key = (base_name, num)
        fumosha.setdefault(key, {"中性": 0.0, "世达": 0.0})
        fumosha[key][kind] += q

    for sheet, layout in layouts.items():
        for row in layout.rows:
            if row.kind != "data":
                continue
            if "覆膜砂" not in row.name:
                continue
            kind = "世达" if "世达" in row.name else "中性"
            # 源名称：V2.0 名称经 map_part_name 归一
            src_name = maopi_match.map_part_name(row.name).replace("（世达）", "").replace("（中性）", "")
            num = normalize_spec(row.spec)
            d = fumosha.get((src_name, num))
            if d is None:
                continue
            q = d.get(kind, 0.0)
            if q > 0:
                result.fills[(sheet, row.row_idx, COL_ZHUANGPEI)] = q


def _apply_assembly_fill(result: FillResult, layouts: Dict[str, SheetLayout],
                         agg: Dict[Tuple[str, str], float], column: int) -> None:
    """组合件行装配量匹配（按名称精确 + 规格数字段相等）。"""
    # 建 {名称: [(数字段, 数量)]}，仅取无「（备钳）/（维度）」后缀的组合件名
    from .plan_file_utils import normalize_spec
    name_specs: Dict[str, Dict[str, float]] = {}
    for (name, spec), qty in agg.items():
        if "+" not in name:
            continue
        if "（" in name:  # （备钳）（维度）等不计
            continue
        num = normalize_spec(spec)
        if not num:
            continue
        name_specs.setdefault(name, {})
        name_specs[name][num] = name_specs[name].get(num, 0.0) + qty

    for sheet, layout in layouts.items():
        for row in layout.rows:
            if row.kind != "data":
                continue
            if not maopi_match.is_assembly_row(row.name):
                continue
            num = normalize_spec(row.spec)
            if not num:
                continue
            # 源名称经 map_part_name 归一（如 小钳口+美式钳把（老款）→ 小钳口+美式钳把）
            src_name = maopi_match.map_part_name(row.name)
            d = name_specs.get(src_name)
            if d is None:
                continue
            qty = d.get(num)
            if qty is not None and qty > 0:
                result.fills[(sheet, row.row_idx, column)] = qty
