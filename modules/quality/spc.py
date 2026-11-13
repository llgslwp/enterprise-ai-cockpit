"""控制图（p 图）能力：过程监控，把「月底统计」升级为「当天预警」。

复用 reader.load_all_months() 读取，不写回任何文件。仅新版（6月起）可算控制限，
旧版（1-5月）无工段/问题列，但抽检/合格列仍在，仍可画趋势（不合格率）但不产出预警建议。
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Optional

from modules.quality import reader, aggregate


def _day_of(date: str) -> str:
    """从日期串提取「日」（兼容 2026.10.5 / 2026/10/5 / 2026-10-05）。"""
    for sep in (".", "/", "-"):
        if sep in str(date):
            return str(date).split(sep)[-1]
    return ""


def build_spc(month: Optional[int] = None) -> Dict[str, Any]:
    """构建某月控制图数据。month=None 取当前系统月，缺月回退最近可用月（复用 aggregate 逻辑）。

    返回：
    {
      "month": "10月", "note": None, "cl": 0.95,
      "points": [{"day","checked","unqualified","rate","ucl","lcl","breach"}...],
      "file": ..., "mtime": ...
    }
    """
    all_months = reader.load_all_months()
    available = sorted(all_months.keys(), key=lambda l: aggregate._parse_month_num(l) or 0)

    target = month if month is not None else aggregate._current_month_num()
    target_label = f"{target}月"

    # —— 缺月回退（与 aggregate.build_quality 保持一致）——
    chosen, note = None, None
    if target_label in all_months and all_months[target_label]["rows"]:
        chosen = target_label
    else:
        for lb in reversed(available):
            if (aggregate._parse_month_num(lb) or 0) <= target:
                chosen = lb
                break
        if chosen is None and available:
            chosen = available[0]
        if chosen and chosen != target_label:
            note = f"本月({target_label})质量数据未就绪，回退显示最近可用月 {chosen}"

    info = reader.inspection_file_info()
    if chosen is None:
        return {"month": target_label, "note": "暂无质量抽检数据", "cl": 0.0,
                "points": [], "file": info["file_name"], "mtime": info["mtime"]}

    rows = all_months[chosen]["rows"]

    # —— 逐日聚合：抽检数 / 不合格数 ——
    daily: Dict[str, List[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        day = _day_of(r["date"])
        if not day.isdigit():
            continue
        daily[day][0] += r["checked"]
        daily[day][1] += max(0.0, r["checked"] - r["qualified"])

    total_c = sum(v[0] for v in daily.values())
    total_u = sum(v[1] for v in daily.values())
    pbar = total_u / total_c if total_c else 0.0

    points: List[Dict[str, Any]] = []
    for day in sorted(daily, key=int):
        n, u = daily[day]
        rate = u / n * 100 if n else 0.0
        sigma = math.sqrt(pbar * (1 - pbar) / n) if n else 0.0
        ucl = (pbar + 3 * sigma) * 100
        lcl = max(0.0, (pbar - 3 * sigma) * 100)
        points.append({
            "day": day,
            "checked": int(n),
            "unqualified": int(u),
            "rate": round(rate, 2),
            "ucl": round(ucl, 2),
            "lcl": round(lcl, 2),
            "breach": bool(u > 0 and rate > ucl),  # 破限：不合格率超上控制限
            "small_n": bool(n < 30),               # 小样本标记（前端提示统计意义弱）
        })

    return {"month": chosen, "note": note, "cl": round(pbar * 100, 2),
            "points": points, "file": info["file_name"], "mtime": info["mtime"]}
