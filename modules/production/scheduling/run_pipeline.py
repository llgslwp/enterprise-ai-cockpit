"""半成品排产链路主入口（production-planning 能力，任务 3）。

一键跑通：6 源读取 → 归集 C~I 列 → 成品计划 J 列 → 缺口方向验证 →
生成本地 V2.0 结果文件。

用法：
    python -m modules.production.scheduling.run_pipeline [--base <V2.0基底>] [--verify]

默认基底 = data/raw/2026年10月份半成品生产计划V2.0.xlsx
默认 6 源自动定位 data/raw/ 下最新文件。
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, Optional

from . import fill_columns as fc
from .gap_calc import compute_gap_check, summarize_gap_direction
from .output_v2 import write_v2_result
from .plan_file_utils import (
    DATA_DIR,
    PRODUCT_SHEETS,
    ensure_readable,
    resolve_source,
)
from .read_sources import FillResult, SheetLayout, parse_v2_layout

import openpyxl


def resolve_v2_base() -> str:
    """定位半成品生产计划 V2.0 基底文件（已去掉日期前缀，精确匹配）。"""
    import glob
    import os
    candidates = [p for p in glob.glob(os.path.join(DATA_DIR, "半成品生产计划*.xlsx"))
                  if not os.path.basename(p).startswith("~$")
                  and "_修复" not in os.path.basename(p)
                  and "_fix" not in os.path.basename(p)]
    if not candidates:
        raise FileNotFoundError("未找到半成品生产计划 V2.0 基底文件（data/raw/半成品生产计划*.xlsx）")
    exact = [p for p in candidates if os.path.basename(p) == "半成品生产计划V2.0.xlsx"]
    pool = exact or candidates
    return max(pool, key=lambda p: os.path.getmtime(p))


def resolve_chengpin_plan() -> Optional[str]:
    """定位成品生产计划文件（已去掉日期前缀，精确匹配「成品生产计划.xlsx」）。"""
    import glob
    import os
    candidates = [p for p in glob.glob(os.path.join(DATA_DIR, "*.xlsx"))
                  if os.path.basename(p) == "成品生产计划.xlsx"]
    return candidates[0] if candidates else None


def _resolve_sources() -> Dict[str, Optional[str]]:
    """定位 6 份源文件（data/raw 下最新）。"""
    return {
        "毛坯库": resolve_source("毛坯库"),
        "车间在产品": resolve_source("车间在产品"),
        "半成品库": resolve_source("半成品库", exclude=("颜色明细",)),
        "外协": resolve_source("外协", exclude=("在途", "填充", "中间")),
        "在产品装配": resolve_source("在产品装配"),
        "成品计划": resolve_chengpin_plan(),
    }


def source_file_dates() -> Dict[str, Dict[str, str]]:
    """返回 6 份源文件 + V2.0 基底各自的最后更新日期（供前端常驻显示）。

    返回 {中文名: {"path": 路径, "mtime": "YYYY-MM-DD HH:MM:SS"}}。
    """
    import os
    from datetime import datetime
    result = {}
    sources = _resolve_sources()
    sources["V2.0基底"] = resolve_v2_base()
    for name, path in sources.items():
        if not path or not os.path.exists(path):
            result[name] = {"path": path, "mtime": None}
            continue
        mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
        result[name] = {"path": path, "mtime": mtime}
    return result


def run_pipeline(base_path: str, verify: bool = False,
                 cp_sheet: Optional[str] = None,
                 overwrite_base: bool = True) -> Dict[str, object]:
    """执行完整排产链路，返回汇总结果。"""
    sources = _resolve_sources()

    # 源齐备自检（成品计划可选，其余 5 源必查）
    required = ["毛坯库", "车间在产品", "半成品库", "外协", "在产品装配"]
    missing = [k for k in required if sources.get(k) is None]
    if missing:
        raise FileNotFoundError(f"缺源文件: {missing}")

    # 读 V2.0 基底，解析布局
    base_readable = ensure_readable(base_path, quiet=True)
    wb = openpyxl.load_workbook(base_readable)
    layouts: Dict[str, SheetLayout] = {}
    for sn in PRODUCT_SHEETS:
        layouts[sn] = parse_v2_layout(wb[sn], sn)
    wb.close()

    # 归集 C~I 列
    result = FillResult()
    fc.fill_maopi(sources["毛坯库"], layouts, result)
    fc.fill_chejian(sources["车间在产品"], layouts, result)
    fc.fill_banchengpin(sources["半成品库"], layouts, result)
    fc.fill_waixie(sources["外协"], layouts, result)
    fc.fill_zaipeizhuangpei(sources["在产品装配"], layouts, result)

    # 成品计划 → J 列
    chengpin_fills: Dict = {}
    if sources.get("成品计划"):
        from .fill_chengpin import fill_chengpin_column
        chengpin_fills = fill_chengpin_column(
            sources["成品计划"], layouts, sheet_name=cp_sheet)

    # 缺口方向验证
    gap_summary = None
    if verify:
        checks = compute_gap_check(layouts, result, base_path)
        gap_summary = summarize_gap_direction(checks)

    # 生成本地结果文件（覆盖 V2.0 基底原文件本身）
    output_path = write_v2_result(base_path, result, chengpin_fills,
                                  overwrite_base=overwrite_base)

    return {
        "sources": sources,
        "source_totals": result.source_totals,
        "fill_count": len(result.fills),
        "color_fills": len(result.color_fills),
        "chengpin_fills": len(chengpin_fills),
        "gap_summary": gap_summary,
        "output_path": output_path,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="半成品排产链路（任务 3）")
    parser.add_argument("--base", default=None,
                        help="V2.0 基底文件路径（默认自动定位 data/raw/半成品生产计划V2.0.xlsx）")
    parser.add_argument("--verify", action="store_true", help="执行缺口方向验证")
    parser.add_argument("--cp-sheet", default=None, help="成品计划 sheet 名（默认自动）")
    args = parser.parse_args(argv)

    base_path = args.base or resolve_v2_base()
    try:
        summary = run_pipeline(base_path, verify=args.verify, cp_sheet=args.cp_sheet)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    print("=== 排产链路完成 ===")
    print(f"源文件定位:")
    for k, v in summary["sources"].items():
        print(f"  {k}: {v}")
    print(f"源文件总量:")
    for k, v in summary["source_totals"].items():
        print(f"  {k}: {v}")
    print(f"归集填充 {summary['fill_count']} 处，配件-颜色 {summary['color_fills']} 条，成品计划 {summary['chengpin_fills']} 处")
    if summary["gap_summary"]:
        gs = summary["gap_summary"]
        print(f"缺口方向验证: 数据行 {gs['total_data_rows']}，有需求 {gs['rows_with_demand']}，"
              f"缺口(正) {gs['gap_positive']}，富余(零/负) {gs['gap_zero_or_negative']}")
    print(f"结果文件: {summary['output_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
