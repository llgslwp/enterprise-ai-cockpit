"""成品计划 → V2.0 J/K 列归集（production-planning 能力，任务 3.3 的 J/K 列）。

成品计划文件（{Y}年{M}月份生产计划.xlsx，sheet {M}月份成品计划）包含多个区段：
- 历史月份（E 列=未完成数量，即历史计划；F 列=当月实际完成）
- 世达订单 / 当月库存 / 当月订单（E 列=计划数，F 列=当月实际完成）

关键语义（用户确认）：
    E 列「未完成数量」实际是「计划数」，F 列是「当月实际完成」。
    成品计划净未完成量 = ΣE（计划数） − ΣF（当月实际完成），横跨所有区段合并。

例：Z80S 历史月份 E=312/F=310，当月库存 E=500/F=150
    → J = (312+500) − (310+150) = 812 − 460 = 352。

品名 → (sheet, 列) 映射（match_product）：
- 伸缩型加力管子钳 → 加力（Z{spec}S → 公制 J；Z{spec}" → 英寸 K）
- 含钛重型管子钳 → 美式 K（含钛）
- 铸铁通用型管子钳 → 美式 J（老款）
- 金刚石内管钳 → 内管钳
- 钻杆自由钳 → 钻杆钳
- 套管自由钳 → 套管钳

V2.0 J 列（成品计划）是「蓝色单元格」数字行（块头+1 的表头行 J 列）。
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .plan_file_utils import ensure_readable, normalize_spec
from .read_sources import SheetLayout, read_source_rows


def read_chengpin(path: str, sheet_name: Optional[str] = None) -> List[dict]:
    """读成品计划，返回数据行（品名/规格/计划数/当月完成数）。

    E 列 = 计划数（历史月份区段的「未完成数量」即历史计划），
    F 列 = 当月实际完成（列名随月份变，如「10月份实际完成（动态）」/「11月份实际完成（动态）」，动态定位）。
    跳过 I 列批号含「发库存」的行（业务过滤：发库存无需再排产）。
    备注列仅作说明、不参与排产计算；内容仍保留在返回行里，供将来表述状态使用。
    """
    rows, cols = read_source_rows(path, sheet_name=sheet_name)
    # 动态定位「实际完成」列：列名随月份变（「N月份实际完成（动态）」），不能硬编码月份
    done_col = next((c for c in cols if "实际完成" in str(c)), None)
    out = []
    for row in rows:
        name = row.get("品名")
        spec = row.get("规格")
        if name is None or spec is None:
            continue
        # 跳过 I 列批号含"发库存"（业务过滤：发库存无需再排产）
        batch = row.get("生产批号")
        if batch and "发库存" in str(batch):
            continue
        # 备注仅作说明，不参与排产计算；但保留内容供将来表述状态（不完全忽略）
        remark = row.get("备注")
        plan = _num(row.get("未完成数量"))
        done = _num(row.get(done_col) if done_col else None)
        out.append({
            "name": str(name).strip(),
            "spec": str(spec).strip(),
            "plan": plan,   # E 列：计划数
            "done": done,   # F 列：当月实际完成
            "remark": str(remark).strip() if remark is not None else "",  # 仅说明，不参与计算
        })
    return out


def _num(v) -> float:
    """安全转 float，None/非数字 → 0.0。"""
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def match_product(name: str) -> Optional[str]:
    """品名 → V2.0 sheet 名。"""
    if "加力" in name and "管子钳" in name:
        return "加力"
    if "含钛" in name:
        return "美式"
    if "铸铁" in name and "通用" in name:
        return "美式"
    if "钻杆" in name and "自由钳" in name:
        return "钻杆钳"
    if "金刚石" in name and "内管" in name:
        return "内管钳"
    if "套管" in name and "自由钳" in name:
        return "套管钳"
    return None


def _spec_is_inch(spec: str) -> bool:
    """判断加力规格是英寸（Z18"）还是公制（Z80S）。"""
    return '"' in spec or "″" in spec


def aggregate_chengpin(rows: List[dict]) -> Dict[Tuple[str, str, str], float]:
    """按 (sheet, 列标记, 数字段) 汇总「净未完成量 = ΣE − ΣF」。

    列标记：'J' 或 'K'（加力 J=公制/K=英寸；美式 J=老款/K=含钛）。
    """
    agg: Dict[Tuple[str, str, str], float] = {}
    for row in rows:
        sheet = match_product(row["name"])
        if sheet is None:
            continue
        num = normalize_spec(row["spec"])
        if not num:
            continue
        net = row["plan"] - row["done"]
        if sheet == "加力":
            col = "K" if _spec_is_inch(row["spec"]) else "J"
        elif sheet == "美式":
            col = "K" if "含钛" in row["name"] else "J"
        else:
            col = "J"
        key = (sheet, col, num)
        agg[key] = agg.get(key, 0.0) + net

    # 净未完成量不为负：超额完成（ΣF > ΣE）时钳制为 0，表示无需再排产
    for k in agg:
        agg[k] = max(0.0, agg[k])
    return agg


def fill_chengpin_column(
    path: str,
    layouts: Dict[str, SheetLayout],
    sheet_name: Optional[str] = None,
) -> Dict[Tuple[str, int, int], float]:
    """成品计划 → J/K 列填值 {(sheet, 表头行号, 列号) -> 净未完成量}。

    - 加力：块含公制（J 列）与英寸（K 列）两个成品计划，
      group_spec 如 '80D/18"' → J=80D 公制值，K=18" 英寸值。
    - 美式：块含老款（J 列）与含钛（K 列）两个成品计划。
    - 内管/钻杆/套管：仅 J 列（列号 10）。
    """
    rows = read_chengpin(path, sheet_name=sheet_name)
    agg = aggregate_chengpin(rows)

    fills: Dict[Tuple[str, int, int], float] = {}
    for sheet, layout in layouts.items():
        for row in layout.rows:
            if row.kind != "header":
                continue
            parts = _split_group_parts(sheet, row.group_spec)
            for col, num in parts:
                col_mark = "J" if col == 10 else "K"
                qty = agg.get((sheet, col_mark, num), 0.0)
                fills[(sheet, row.row_idx, col)] = qty
    return fills


def _split_group_parts(sheet: str, group_spec: str) -> List[Tuple[int, str]]:
    """把块头标签拆成 [(列号, 数字段)]。

    - 加力：'80D/18"' → [(10, '80'), (11, '18')]（J=公制 D，K=英寸 "）
    - 美式：'18"' → [(10, '18'), (11, '18')]（J=老款，K=含钛，同一英寸规格）
    - 内管/钻杆/套管：'S61'/'71-75'/'73/89' → [(10, 数字段)]
    """
    if sheet == "加力":
        metric = re.findall(r"(\d+(?:-\d+)?)D", group_spec)
        inch = re.findall(r"(\d+(?:-\d+)?)[\"″]", group_spec)
        parts = []
        if metric:
            parts.append((10, metric[0]))  # J 列公制
        if inch:
            parts.append((11, inch[0]))    # K 列英寸
        if not parts:
            num = normalize_spec(group_spec)
            if num:
                parts.append((10, num))
        return parts

    if sheet == "美式":
        num = normalize_spec(group_spec)
        if num:
            # J=老款，K=含钛，同一英寸规格
            return [(10, num), (11, num)]
        return []

    # 内管/钻杆/套管：单个规格，归 J 列
    num = normalize_spec(group_spec)
    if num:
        return [(10, num)]
    return []
