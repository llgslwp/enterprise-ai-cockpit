"""生产计划管理大屏数据计算（production-planning 能力，大屏指标）。

数据源：data/raw/成品生产计划.xlsx 的「{N}月份成品计划」sheet。
列语义（与排产链路 fill_chengpin.py 一致）：
    C1 品名 / C2 规格 / C3 类别（历史月份/当月订单/世达订单/当月库存）
    C5 未完成数量（=计划数）/ C6 {N}月份实际完成（动态）

产出口径（用户确认）：
    - 总体完成率 = 历史 + 当月库存 + 当月订单 + 世达 四区段之和
    - 4 区段：历史 / 当月库存 / 当月订单 / 世达
    - 6 品类：加力钳 / 美式 / 含钛 / 内管钳 / 钻杆钳 / 套管钳
    - 完成率 = 完成 / 计划 × 100%，超 100% 保持真实值

性能：用 zip 直读（复用 excel_reader），一次读取所有月份 sheet，替代 openpyxl
多次 load_workbook（原实现 scan_months 1 次 + calc_month N 次 = N+1 次全量加载，
100KB 文件也累计 ~900ms）。

用法：
    python -m modules.production.dashboard_calc [--month 10] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from .scheduling.plan_file_utils import DATA_DIR

# 月份 → sheet 名后缀（动态扫描成品计划文件的 "{N}月份成品计划" sheet）
MONTHS = [8, 9, 10]


def resolve_plan_file() -> str:
    """定位最新成品生产计划文件（按文件修改时间最新）。

    用户已把文件重命名为「成品生产计划.xlsx」（去掉日期前缀），故：
    - 精确优先匹配「成品生产计划.xlsx」；
    - 排除派生件：半成品、_修复 后缀（系统内部坏样式修复产物，非用户真实文件）。
    """
    import glob

    def _is_candidate(base: str) -> bool:
        if base.startswith("~$"):
            return False
        if "半成品" in base or "_修复" in base or "_fix" in base:
            return False
        return "生产计划" in base

    candidates = [p for p in glob.glob(os.path.join(DATA_DIR, "*.xlsx"))
                  if _is_candidate(os.path.basename(p))]
    if not candidates:
        raise FileNotFoundError("未找到成品生产计划文件（data/raw/成品生产计划.xlsx）")

    # 精确优先：文件名正好是「成品生产计划.xlsx」
    exact = [p for p in candidates if os.path.basename(p) == "成品生产计划.xlsx"]
    pool = exact or candidates
    # 按文件修改时间（mtime）最新
    return max(pool, key=lambda p: os.path.getmtime(p))


def _read_plan_sheets(path: str) -> Dict[int, list]:
    """zip 直读所有「{N}月份成品计划」sheet，返回 {month: [(name, c3, plan, done), ...]}。

    一次 zip 打开读全部月份，sharedStrings/styles 只解析一次，避免 openpyxl 逐月全量加载。
    """
    from app.data_model import excel_reader

    zf = zipfile.ZipFile(path)
    try:
        shared = excel_reader._load_shared_strings(zf)
        date_xf = excel_reader._load_date_xf_indexes(zf)
        result: Dict[int, list] = {}
        for sheet_name, sheet_path in excel_reader._list_sheets(zf):
            if not sheet_path:
                continue
            m = re.match(r"(\d+)月份成品计划", sheet_name)
            if not m:
                continue
            month = int(m.group(1))
            rows = []
            for _rn, row_data in excel_reader._iter_sheet_rows(zf, sheet_path, shared, date_xf):
                name = row_data.get(1)
                c3 = row_data.get(3)
                if name is None or str(name).strip() in ("", "品名"):
                    continue
                if str(c3 or "").strip() == "类别":
                    continue  # 表头行
                rows.append((name, c3, _num(row_data.get(5)), _num(row_data.get(6))))
            result[month] = rows
        return result
    finally:
        zf.close()


def scan_months(path: str) -> List[int]:
    """扫描文件中 "{N}月份成品计划" sheet，返回月份升序列表。"""
    return sorted(_read_plan_sheets(path).keys())


def _num(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _cat_of(c3: str) -> str:
    """C3 类别 → 4 区段 key。"""
    c3 = str(c3 or "").strip()
    if c3 == "历史月份":
        return "历史"
    if c3 == "世达订单":
        return "世达"
    if c3 == "当月订单":
        return "当月订单"
    if c3 == "当月库存":
        return "当月库存"
    return ""


def _prod_of(name: str) -> str:
    """品名 → 6 品类 key（与 fill_chengpin.match_product 同源，扩展含钛/美式区分）。"""
    name = str(name)
    if "加力" in name and "管子钳" in name:
        return "加力钳"
    if "含钛" in name:
        return "含钛"
    if "铸铁" in name and "通用" in name:
        return "美式"
    if "钻杆" in name and "自由钳" in name:
        return "钻杆钳"
    if "金刚石" in name and "内管" in name:
        return "内管钳"
    if "套管" in name and "自由钳" in name:
        return "套管钳"
    return ""


def _calc_from_rows(month: int, rows: list) -> Dict:
    """从已读的 [(name, c3, plan, done)] 计算某月成品计划全套指标。"""
    dim: Dict[str, List[float]] = defaultdict(lambda: [0.0, 0.0])
    prod: Dict[str, List[float]] = defaultdict(lambda: [0.0, 0.0])

    for name, c3, plan, done in rows:
        cat = _cat_of(str(c3))
        pr = _prod_of(str(name))
        if cat:
            dim[cat][0] += plan
            dim[cat][1] += done
        if pr:
            prod[pr][0] += plan
            prod[pr][1] += done

    def pct(p, d):
        return round(d / p * 100, 1) if p else 0.0

    # 四区段（固定顺序）
    dim_order = ["历史", "当月库存", "当月订单", "世达"]
    dimensions = []
    total_p = total_d = 0.0
    for k in dim_order:
        p, d = dim[k]
        total_p += p
        total_d += d
        dimensions.append({
            "key": k, "plan": round(p), "done": round(d), "rate": pct(p, d),
        })

    # 六品类（固定顺序）
    prod_order = ["加力钳", "美式", "含钛", "内管钳", "钻杆钳", "套管钳"]
    products = []
    for k in prod_order:
        p, d = prod[k]
        products.append({
            "key": k, "plan": round(p), "done": round(d), "rate": pct(p, d),
        })

    return {
        "month": month,
        "overall": {
            "plan": round(total_p), "done": round(total_d),
            "rate": pct(total_p, total_d),
        },
        "dimensions": dimensions,
        "products": products,
    }


def calc_month(path: str, month: int) -> Dict:
    """计算某月成品计划的全套指标。"""
    sheets = _read_plan_sheets(path)
    rows = sheets.get(month)
    if rows is None:
        return {}
    return _calc_from_rows(month, rows)


def build_dashboard(path: str) -> Dict:
    """汇总所有月份 + 最新月（一次 zip 直读全部月份）。"""
    sheets = _read_plan_sheets(path)
    months = {}
    latest = None
    for m in sorted(sheets.keys()):
        data = _calc_from_rows(m, sheets[m])
        if data:
            months[str(m)] = data
            latest = data  # 月份升序，最后即最新
    return {"latest": latest, "months": months}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生产计划管理大屏数据计算")
    parser.add_argument("--path", default=None, help="生产计划文件路径（默认自动定位最新）")
    parser.add_argument("--month", type=int, default=None, help="指定月份")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    path = args.path or resolve_plan_file()

    if args.month:
        data = calc_month(path, args.month)
    else:
        data = build_dashboard(path)

    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
