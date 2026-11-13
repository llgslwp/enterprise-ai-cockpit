"""库存数据聚合（inventory-status 能力，任务 1.1）。

复用 `app/data_model` 读取六类库存数据（五类 ERP 库存 + 成品台账汇总看板），
输出统一的聚合结构：类别 -> {物资数, 总存量, 明细}。

设计原则：
- 读取层（app/data_model）只负责「怎么读」，本模块只负责「怎么算」。
- 五类 ERP 库存以「现有存量」列求和，成品台账以「年末库存」列求和。
- 文件定位复用 production 的 plan_file_utils.resolve_latest（按日期取最新、排除 ~$ 锁文件）。
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from app.data_model.loader import load_category, load_product_ledger
from app.data_model.structures import InventoryTable

# 项目根（相对本文件定位，保证任意 cwd 下可运行）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(_PROJECT_ROOT, "data", "raw")

# 五类 ERP 库存：类别 -> 文件名关键字（用于 resolve_latest 定位最新文件）
ERP_CATEGORIES = {
    "毛坯库": "毛坯库",
    "半成品库": "半成品库",
    "外协": "外协",
    "车间在产品": "车间在产品",
    "在产品装配": "在产品装配",
}

# 成品台账文件名关键字
LEDGER_KEYWORD = "成品入出库"

# 五类 ERP 库存的「存量」字段
STOCK_FIELD = "现有存量"
# 成品台账汇总看板的「存量」字段
LEDGER_STOCK_FIELD = "年末库存"


def _resolve_latest(pattern: str) -> Optional[str]:
    """定位最新文件（原始件 + 派生件中取 mtime 最新，排除 ~$ 锁文件）。

    复用 production 的 resolve_latest 按文件名日期键排序；无日期时回落 mtime。
    同时排除 `_修复` 派生件——派生件是 WPS 坏样式的修复副本，若原始件更新了，
    派生件就是过期副本，继续用会读到旧数据。
    """
    import glob
    candidates = [
        p for p in glob.glob(pattern)
        if not os.path.basename(p).startswith("~$") and "_修复" not in os.path.basename(p)
    ]
    if not candidates:
        return None
    try:
        from modules.production.scheduling.plan_file_utils import resolve_latest
        return resolve_latest(pattern, exclude=("_修复",))
    except ImportError:
        return max(candidates, key=lambda p: os.path.getmtime(p))


def _resolve_erp_file(category: str) -> Optional[str]:
    """定位某类 ERP 库存的最新文件路径（排除 _修复 派生件）。"""
    keyword = ERP_CATEGORIES[category]
    return _resolve_latest(os.path.join(DATA_DIR, f"*{keyword}*.xlsx"))


def _resolve_ledger_file() -> Optional[str]:
    """定位成品台账最新文件路径（排除 _修复 派生件，不修复）。

    台账走 zip 直读（load_product_ledger → read_excel_table），不解析样式、
    无 WPS 坏样式问题，故无需 ensure_readable，直接返回 mtime 最新原始件。
    """
    import glob
    pattern = os.path.join(DATA_DIR, f"*{LEDGER_KEYWORD}*.xlsx")
    candidates = [p for p in glob.glob(pattern)
                  if not os.path.basename(p).startswith("~$")
                  and "_修复" not in os.path.basename(p)]
    if not candidates:
        return None
    return max(candidates, key=lambda p: os.path.getmtime(p))


def _numeric(v) -> float:
    """把值安全转为数值；空/非数值返回 0。"""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return 0.0


def _sum_stock(table: InventoryTable, field: str) -> float:
    """对 InventoryTable 的指定字段求和。"""
    total = 0.0
    for row in table.rows:
        total += _numeric(row.get(field))
    return total


def load_inventory_data() -> Dict[str, InventoryTable]:
    """读取六类库存数据，返回 {类别: InventoryTable}。

    缺文件或读取失败的类别标注为 None（不整体中断）。
    """
    result: Dict[str, InventoryTable] = {}

    # 五类 ERP 库存
    for category in ERP_CATEGORIES:
        path = _resolve_erp_file(category)
        if path is None:
            result[category] = None
            continue
        try:
            result[category] = load_category(category, path)
        except Exception:
            result[category] = None

    # 成品台账（汇总看板）
    ledger_path = _resolve_ledger_file()
    if ledger_path is None:
        result["成品入出库台账"] = None
    else:
        try:
            result["成品入出库台账"] = load_product_ledger(ledger_path, sheet_name="汇总看板")
        except Exception:
            result["成品入出库台账"] = None

    return result


def build_summary() -> List[dict]:
    """构建库存汇总看板：每类 -> 物资数 / 总存量 / 状态。

    返回列表，顺序：五类 ERP 库存 + 成品台账。
    """
    data = load_inventory_data()
    summary = []

    for category in list(ERP_CATEGORIES.keys()) + ["成品入出库台账"]:
        table = data.get(category)
        if table is None:
            summary.append({
                "category": category,
                "item_count": 0,
                "total_stock": 0.0,
                "status": "缺失",
            })
            continue

        if category == "成品入出库台账":
            stock_field = LEDGER_STOCK_FIELD
            # 台账汇总看板：物资数 = 有规格的行数（排除类别分隔行）
            item_count = sum(
                1 for r in table.rows if r.get("规格") is not None
            )
        else:
            stock_field = STOCK_FIELD
            item_count = len(table.rows)

        total_stock = _sum_stock(table, stock_field)
        summary.append({
            "category": category,
            "item_count": item_count,
            "total_stock": total_stock,
            "status": "正常",
        })

    return summary


def build_alerts() -> List[dict]:
    """构建库存预警列表：成品台账中「年末库存 < 库存底线」的规格。

    依赖 modules.inventory.thresholds 读取底线配置表（开口式，每次重新读）。
    返回 [{category, spec, feature, stock, threshold, gap}]，未定义底线的规格不出现。
    """
    from modules.inventory.thresholds import load_thresholds

    thresholds = load_thresholds()
    if not thresholds:
        return []

    data = load_inventory_data()
    ledger = data.get("成品入出库台账")
    if ledger is None:
        return []

    alerts = []
    for row in ledger.rows:
        cat = row.get("类别")
        spec = row.get("规格")
        feat = row.get("特征")
        if spec is None:
            continue

        key = (
            str(cat).strip() if cat is not None else "",
            str(spec).strip(),
            str(feat).strip() if feat is not None else "",
        )
        threshold = thresholds.get(key)
        if threshold is None:
            continue

        stock = _numeric(row.get(LEDGER_STOCK_FIELD))
        if stock < threshold:
            alerts.append({
                "category": cat,
                "spec": spec,
                "feature": feat,
                "stock": stock,
                "threshold": threshold,
                "gap": threshold - stock,
            })

    # 按缺口从大到小排序，最紧急的排前面
    alerts.sort(key=lambda x: x["gap"], reverse=True)
    return alerts


def build_material_alerts() -> List[dict]:
    """构建原料预警列表：毛坯库中「现有存量合计 < 原料底线」的货品。

    依赖 modules.inventory.material_thresholds 读取原料底线配置表（开口式，每次重新读）。
    安全库存底线是「名称+规格」粒度，故先将毛坯库按「货品名称+规格」汇总所有批号
    的现有存量求和，再与底线比对；逐批号比对会把同一规格拆散、产生误报。
    返回 [{name, spec, stock, threshold, gap}]，未定义底线的货品不出现。
    """
    from modules.inventory.material_thresholds import load_material_thresholds

    thresholds = load_material_thresholds()
    if not thresholds:
        return []

    data = load_inventory_data()
    maopi = data.get("毛坯库")
    if maopi is None:
        return []

    # 第一步：按「货品名称+规格」汇总所有批号的存量（求和）
    stock_sum: Dict[tuple, float] = {}
    for row in maopi.rows:
        name = row.get("货品名称")
        spec = row.get("货品规格")
        if spec is None:
            continue
        key = (
            str(name).strip() if name is not None else "",
            str(spec).strip(),
        )
        v = _numeric(row.get(STOCK_FIELD))
        if v is not None:
            stock_sum[key] = stock_sum.get(key, 0.0) + v

    # 第二步：汇总存量 vs 底线，逐规格生成预警
    alerts = []
    for key, stock in stock_sum.items():
        threshold = thresholds.get(key)
        if threshold is None:
            continue
        if stock < threshold:
            alerts.append({
                "name": key[0],
                "spec": key[1],
                "stock": stock,
                "threshold": threshold,
                "gap": threshold - stock,
            })

    # 按缺口从大到小排序，最紧急的排前面
    alerts.sort(key=lambda x: x["gap"], reverse=True)
    return alerts


def search_items(keyword: str) -> List[dict]:
    """按货品名称/规格检索某物资在各类库存中的明细。

    keyword 匹配「货品名称」「货品规格」（五类库存）或「类别」「规格」（成品台账）。
    返回 [{category, name, spec, stock, 其他原始字段}]。
    """
    if not keyword or not keyword.strip():
        return []
    kw = keyword.strip()

    data = load_inventory_data()
    results: List[dict] = []

    for category, table in data.items():
        if table is None:
            continue

        if category == "成品入出库台账":
            # 台账：按 类别/规格/特征 匹配
            for row in table.rows:
                spec = row.get("规格")
                if spec is None:
                    continue
                haystack = " ".join(
                    str(x) for x in [row.get("类别"), row.get("规格"), row.get("特征")]
                    if x is not None
                )
                if kw in haystack:
                    results.append({
                        "category": "成品入出库台账",
                        "name": row.get("类别"),
                        "spec": spec,
                        "feature": row.get("特征"),
                        "stock": _numeric(row.get(LEDGER_STOCK_FIELD)),
                    })
        else:
            # 五类 ERP：按 货品名称/货品规格 匹配
            for row in table.rows:
                name = row.get("货品名称")
                spec = row.get("货品规格")
                haystack = " ".join(
                    str(x) for x in [name, spec] if x is not None
                )
                if kw in haystack:
                    results.append({
                        "category": category,
                        "name": name,
                        "spec": spec,
                        "feature": row.get("特征"),
                        "stock": _numeric(row.get(STOCK_FIELD)),
                        "batch": row.get("批号"),
                        "location": row.get("库位名称") or row.get("状态"),
                    })

    return results
