"""库存月度流水聚合（inventory 能力，支撑库存大屏三页）。

数据源：成品入出库台账（`data/raw/*成品入出库*.xlsx`）的「汇总看板」sheet。
该 sheet 结构（表头第 2 行）：
  C1=类别  C2=规格  C3=特征
  C4~C39 = 1~12 月 × 3 列（入库/出库/结存）
  C40=全年入库  C41=全年出库  C42=年末库存

本模块按「6 品类」与「两大系列」两套口径聚合各月的入库/出库/结存：
  6 品类：加力钳 / 美重 / 含钛 / 钻杆钳 / 套管钳 / 内管钳
  两大系列：管钳 = 加力 + 含钛 + 美重；自由钳 = 内管 + 钻杆 + 套管

关键：
- 台账走 zip 直读（read_excel_table），不解析样式、无 WPS 坏样式问题，读取仅 ~50ms。
- 类别分隔行（A 列以「▌」开头）不归集。
- 「特征」列不参与品类/系列聚合，但保留给明细页按规格展开时用。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

# 项目根（相对本文件定位）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(_PROJECT_ROOT, "data", "raw")

# 台账文件名关键字
LEDGER_KEYWORD = "成品入出库"

# 6 品类（展示顺序固定）
PRODUCT_CATEGORIES = ("加力钳", "美重", "含钛", "钻杆钳", "套管钳", "内管钳")

# 类别字段 -> 6 品类
_CAT_TO_PRODUCT = {
    "加力钳": "加力钳",
    "铸铁管钳": "美重",
    "含钛": "含钛",
    "钻杆钳": "钻杆钳",
    "套管钳": "套管钳",
    "内管钳": "内管钳",
}

# 两大系列划分
SERIES_MAP = {
    "加力钳": "管钳",
    "美重": "管钳",
    "含钛": "管钳",
    "内管钳": "自由钳",
    "钻杆钳": "自由钳",
    "套管钳": "自由钳",
}
SERIES_NAMES = ("管钳", "自由钳")

# 月份数（汇总看板固定 12 个月）
MONTHS = list(range(1, 13))


def resolve_ledger_file() -> str:
    """定位最新成品台账文件（排除 `_修复` 派生件，不修复）。

    台账改走 zip 直读（read_excel_table），不解析样式、无 WPS 坏样式问题，
    故无需 ensure_readable，直接返回 mtime 最新的原始件路径。
    """
    import glob
    pattern = os.path.join(DATA_DIR, f"*{LEDGER_KEYWORD}*.xlsx")
    candidates = [p for p in glob.glob(pattern)
                  if not os.path.basename(p).startswith("~$")
                  and "_修复" not in os.path.basename(p)]
    if not candidates:
        raise FileNotFoundError(f"未找到成品台账文件（data/raw/*{LEDGER_KEYWORD}*.xlsx）")

    # 取 mtime 最新的原始件（zip 直读，无需修复）
    return max(candidates, key=lambda p: os.path.getmtime(p))


def default_month() -> int:
    """默认目标月份：当前真实月份（如 11 月 → 11）。

    库存总览等页面「不传 month」时，动态显示当前月份的最新台账数据，
    不再写死某个月（历史版本曾写死 10 月，导致新月份数据不更新）。
    """
    return datetime.now().month


def _cat_to_product(cat: str) -> Optional[str]:
    """类别字段 -> 6 品类；无法归类返回 None。"""
    c = str(cat).strip()
    for key, product in _CAT_TO_PRODUCT.items():
        if key in c:
            return product
    return None


def _num(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return 0.0


def _read_ledger_monthly(path: str) -> List[Dict[str, Any]]:
    """读台账「汇总看板」，返回每行 {category, spec, feature, months:[{in,out,stock}x12], year_in, year_out, year_stock}。

    用 zip 直读（read_excel_table）替代 openpyxl：只解析「汇总看板」单 sheet、不碰样式，
    规避 177-sheet 全量加载与 WPS 坏样式，读取从 ~3s 降到 ~50ms。
    """
    from app.data_model.loader import load_product_ledger

    table = load_product_ledger(path, sheet_name="汇总看板")
    rows = []
    for r in table.rows:
        cat = r.get("类别")
        if cat is None:
            continue
        cat_s = str(cat).strip()
        if cat_s.startswith("▌") or cat_s == "":
            continue  # 类别分隔行 / 空行
        spec = r.get("规格")
        feat = r.get("特征")
        months = []
        for m in range(1, 13):
            months.append({
                "in": _num(r.get(f"{m}月入库")),
                "out": _num(r.get(f"{m}月出库")),
                "stock": _num(r.get(f"{m}月结存")),
            })
        rows.append({
            "category": cat_s,
            "spec": str(spec).strip() if spec is not None else "",
            "feature": str(feat).strip() if feat is not None else "",
            "months": months,
            "year_in": _num(r.get("全年入库")),
            "year_out": _num(r.get("全年出库")),
            "year_stock": _num(r.get("年末库存")),
        })
    return rows


def build_flow_stats(month: Optional[int] = None) -> Dict[str, Any]:
    """聚合库存月度流水，返回大屏三页所需数据。

    返回结构：
    {
      "file": 台账文件名,
      "month": 目标月份（默认当前真实月份）,
      "total": {"in":.., "out":.., "stock":..},                 # 单月合计
      "products": [{name, in, out, stock} x 6],                 # 6 品类单月
      "series":   [{name, in, out, stock} x 2],                 # 两大系列单月
      "monthly":  [{month, in, out, stock} x 12],               # 各月合计（总览趋势可选）
      "detail": {产品名: [{spec, feature, in, out, stock} ...]} # 分品类按规格明细
    }
    """
    path = resolve_ledger_file()
    rows = _read_ledger_monthly(path)

    m = month if month is not None else default_month()  # 默认当前真实月份（动态，不写死）
    idx = m - 1

    # 聚合
    prod = {p: {"in": 0.0, "out": 0.0, "stock": 0.0} for p in PRODUCT_CATEGORIES}
    series = {s: {"in": 0.0, "out": 0.0, "stock": 0.0} for s in SERIES_NAMES}
    detail: Dict[str, List[Dict[str, Any]]] = {p: [] for p in PRODUCT_CATEGORIES}
    monthly = [{"month": i + 1, "in": 0.0, "out": 0.0, "stock": 0.0} for i in range(12)]

    for row in rows:
        product = _cat_to_product(row["category"])
        if product is None:
            continue
        mo = row["months"][idx]
        prod[product]["in"] += mo["in"]
        prod[product]["out"] += mo["out"]
        prod[product]["stock"] += mo["stock"]

        s = SERIES_MAP[product]
        series[s]["in"] += mo["in"]
        series[s]["out"] += mo["out"]
        series[s]["stock"] += mo["stock"]

        detail[product].append({
            "spec": row["spec"],
            "feature": row["feature"],
            "in": mo["in"],
            "out": mo["out"],
            "stock": mo["stock"],
        })

        # 各月合计（用于总览趋势）
        for i in range(12):
            monthly[i]["in"] += row["months"][i]["in"]
            monthly[i]["out"] += row["months"][i]["out"]
            monthly[i]["stock"] += row["months"][i]["stock"]

    total = {"in": 0.0, "out": 0.0, "stock": 0.0}
    for p in PRODUCT_CATEGORIES:
        total["in"] += prod[p]["in"]
        total["out"] += prod[p]["out"]
        total["stock"] += prod[p]["stock"]

    return {
        "file": os.path.basename(path),
        "month": m,
        "total": total,
        "products": [{"name": p, **prod[p]} for p in PRODUCT_CATEGORIES],
        "series": [{"name": s, **series[s]} for s in SERIES_NAMES],
        "monthly": monthly,
        "detail": detail,
    }


def build_focus_stats(month: Optional[int] = None) -> Dict[str, Any]:
    """只返回「重点关注规格」的本月入库/出库/结存明细。

    数据源 = 台账汇总看板 + 重点关注规格清单（data/raw/重点关注规格.xlsx）。
    仅清单中「是否重点」勾选的规格才返回；未勾选/清单缺失 → 返回空明细。

    返回结构：
    {
      "file": 台账文件名,
      "month": 目标月份,
      "focus_file": 清单文件名（若存在）,
      "count": 重点规格数,
      "products": [{name, items:[{spec, feature, in, out, stock}]} x 品类],  # 仅含重点规格
      "flat": [{category, spec, feature, in, out, stock} ...],              # 平铺（供表格直显）
    }
    """
    from . import focus_specs
    from .focus_specs import load_focus_specs

    m = month if month is not None else default_month()
    focus_set = load_focus_specs()

    # 只读一次台账（不再重复调 build_flow_stats），遍历原始行（保留原始 category），
    # 用 (原始类别,规格,特征) 匹配重点清单。
    path = resolve_ledger_file()
    rows = _read_ledger_monthly(path)
    idx = m - 1

    flat: List[Dict[str, Any]] = []
    for row in rows:
        cat = row["category"]
        spec = row["spec"]
        feat = row["feature"]
        key = (cat.strip(), spec.strip(), feat.strip())
        if key not in focus_set:
            continue
        mo = row["months"][idx]
        flat.append({
            "category": cat,
            "spec": spec,
            "feature": feat,
            "in": mo["in"],
            "out": mo["out"],
            "stock": mo["stock"],
        })

    # 按 6 品类分组（保持展示顺序）
    products: List[Dict[str, Any]] = []
    for p in PRODUCT_CATEGORIES:
        items = [x for x in flat if _cat_to_product(x["category"]) == p]
        if items:
            products.append({"name": p, "items": items})

    focus_path = focus_specs._config_path()
    focus_file = os.path.basename(focus_path) if os.path.exists(focus_path) else None

    return {
        "file": os.path.basename(path),
        "month": m,
        "focus_file": focus_file,
        "count": len(flat),
        "products": products,
        "flat": flat,
    }


def _pct(v, total) -> float:
    return round(v / total * 100, 2) if total else 0.0


def build_share_stats(month: Optional[int] = None) -> Dict[str, Any]:
    """构建占比分析数据：入库/出库/结存 × 各品种/两大系列。

    返回：
    {
      "in":  {"products":[{name,value,pct}], "series":[{name,value,pct}]},
      "out": {...},
      "stock": {...}
    }
    """
    fs = build_flow_stats(month)

    def _group(items):
        total = sum(x["value"] for x in items)
        return [{"name": x["name"], "value": x["value"], "pct": _pct(x["value"], total)} for x in items]

    result = {}
    for key in ("in", "out", "stock"):
        prods = [{"name": p["name"], "value": p[key]} for p in fs["products"]]
        sers = [{"name": s["name"], "value": s[key]} for s in fs["series"]]
        result[key] = {
            "products": _group(prods),
            "series": _group(sers),
        }
    result["month"] = fs["month"]
    return result


def main(argv=None) -> int:
    import json
    stats = build_flow_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
