"""质量管理统计聚合（quality-dashboard 能力，任务 2）。

复用 modules.quality.reader 读取本地 Excel，输出看板所需聚合结构：
- 车间抽检：总体合格率、分工段、问题 TOP 四维、严重预警、月度趋势。
- 原料来料检验：检验结果分布、供应商表现、物料/问题 TOP、退货+让步预警。

口径（权威）：
- 总体合格率 = Σ合格数量 ÷ Σ抽检数量 × 100，保留 1 位小数（不是合格/工作量，也不是合格率列平均）。
- 问题 TOP：仅取「问题描述」非空行，按问题描述/配件/工段/姓名 四维统计条数，降序 Top 8。
- 严重预警：处置方式 ∈ {报废, 返工, 让步接收, 让步接受}。
- 缺月回退：month 缺省取当前系统月，无数据回退最近可用月 + note。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from modules.quality import reader

# 严重预警处置方式（两写法「让步接收/让步接受」都命中）
ALERT_DISPS = {"报废", "返工", "让步接收", "让步接受"}


def _parse_month_num(sheet_name: str) -> Optional[int]:
    """从月份 sheet 名提取起始月数字（`1-2月份` -> 1, `3月份` -> 3）。用于排序。"""
    m = re.search(r"(\d+)(?:-\d+)?月份?", sheet_name.strip())
    return int(m.group(1)) if m else None


def available_months() -> List[str]:
    """返回车间抽检表可用月份 sheet 名（按月份数字升序）。"""
    names = reader.month_sheet_names()
    names.sort(key=lambda s: _parse_month_num(s) or 0)
    return names


def _current_month_num() -> int:
    return datetime.now().month


def _month_has_data(rows: List[Dict[str, Any]]) -> bool:
    """某月是否「有数据」：存在日期非空的行。reader 已过滤空日期，这里 len>0 即视为有数据。"""
    return len(rows) > 0


def _top_counter(items: List[str], n: int = 8) -> List[Dict[str, Any]]:
    """对字符串列表计数，降序取 Top n。返回 [{name, count}]。"""
    from collections import Counter
    c = Counter(i for i in items if i)
    return [{"name": k, "count": v} for k, v in c.most_common(n)]


def build_quality(month: Optional[int] = None) -> Dict[str, Any]:
    """构建车间抽检质量看板数据。

    month: 目标月份数字（如 10）；None 时取当前系统月。无数据时回退最近可用月。

    返回：
    {
      "month": "10月",           # 实际展示月份标签
      "note": None,               # 回退说明（无回退时为 None）
      "trend": [{month, rate}...],# 各月整体合格率（升序）
      "overall": {checked, qualified, rate},
      "sections": [{name, checked, qualified, rate}...],
      "issue_top": {by_problem, by_part, by_section, by_name},
      "alerts": [{date, name, section, part, spec, problem, disp}...],
      "file": ..., "mtime": ...   # 数据来源标注
    }
    """
    # 一次性加载所有月份（避免逐 sheet 重复 IO）
    all_months = reader.load_all_months()  # {标签: {is_new, rows}}
    available_labels = sorted(all_months.keys(), key=lambda l: _parse_month_num(l) or 0)

    target = month if month is not None else _current_month_num()
    target_label = f"{target}月"

    note = None
    chosen_label = None
    # 优先目标月；无数据回退最近可用月
    if target_label in all_months and _month_has_data(all_months[target_label]["rows"]):
        chosen_label = target_label
    else:
        # 回退：从可用月里选数字 <= target 的最近一个；都没有则取最小可用月
        fallback = None
        for label in reversed(available_labels):
            num = _parse_month_num(label)
            if num is not None and num <= target:
                fallback = label
                break
        if fallback is None and available_labels:
            fallback = available_labels[0]
        if fallback is not None:
            chosen_label = fallback
            if fallback != target_label:
                note = f"本月({target_label})质量数据未就绪，回退显示最近可用月 {fallback}"

    if chosen_label is None:
        # 完全无数据
        info = reader.inspection_file_info()
        return {
            "month": target_label, "note": "暂无质量抽检数据",
            "trend": [], "overall": {"checked": 0, "qualified": 0, "rate": 0},
            "sections": [], "issue_top": {"by_problem": [], "by_part": [], "by_section": [], "by_name": []},
            "alerts": [],
            "file": info["file_name"], "mtime": info["mtime"],
        }

    # 月度趋势：对每个可用月算整体合格率
    # 新版（6月起）：Σ合格÷Σ抽检；旧版（1-5月）：合格率列加权（Σ rate×抽检 ÷ Σ抽检）
    trend = []
    for label in available_labels:
        entry = all_months[label]
        rows = entry["rows"]
        checked = sum(r["checked"] for r in rows)
        if entry["is_new"]:
            qualified = sum(r["qualified"] for r in rows)
            rate = round(qualified / checked * 100, 1) if checked else 0.0
        else:
            weighted = sum(r["rate"] * r["checked"] for r in rows)
            rate = round(weighted / checked * 100, 1) if checked else 0.0
        trend.append({"month": label, "rate": rate})

    # 目标月明细
    entry = all_months[chosen_label]
    rows = entry["rows"]
    chosen_is_new = entry["is_new"]

    checked = sum(r["checked"] for r in rows)
    if chosen_is_new:
        qualified = sum(r["qualified"] for r in rows)
        overall_rate = round(qualified / checked * 100, 1) if checked else 0.0
    else:
        # 旧版：合格率列加权（合格数量列语义不可靠）
        weighted = sum(r["rate"] * r["checked"] for r in rows)
        qualified = round(weighted, 1)
        overall_rate = round(weighted / checked * 100, 1) if checked else 0.0

    # 分工段聚合（机加工/热处理/装配，工段空标「未填」）
    section_map: Dict[str, Dict[str, float]] = {}
    for r in rows:
        sec = r["section"] if r["section"] else "未填"
        s = section_map.setdefault(sec, {"checked": 0.0, "qualified": 0.0})
        s["checked"] += r["checked"]
        s["qualified"] += r["qualified"]
    sections = []
    for name, s in section_map.items():
        rate = round(s["qualified"] / s["checked"] * 100, 1) if s["checked"] else 0.0
        sections.append({"name": name, "checked": s["checked"], "qualified": s["qualified"], "rate": rate})
    # 固定顺序：机加工/热处理/装配 在前，其余靠后
    order = {"机加工": 0, "热处理": 1, "装配": 2}
    sections.sort(key=lambda x: order.get(x["name"], 99))

    # 问题 TOP：仅问题描述非空的行
    problem_rows = [r for r in rows if r["problem"]]
    issue_top = {
        "by_problem": _top_counter([r["problem"] for r in problem_rows]),
        "by_part": _top_counter([r["part"] for r in problem_rows]),
        "by_section": _top_counter([(r["section"] or "未填") for r in problem_rows]),
        "by_name": _top_counter([r["name"] for r in problem_rows]),
    }

    # 严重预警
    alerts = [
        {
            "date": r["date"], "name": r["name"],
            "section": r["section"] or "未填", "part": r["part"], "spec": r["spec"],
            "problem": r["problem"], "disp": r["disp"],
        }
        for r in rows if r["disp"] in ALERT_DISPS
    ]

    info = reader.inspection_file_info()
    return {
        "month": chosen_label,
        "note": note,
        "trend": trend,
        "overall": {"checked": checked, "qualified": qualified, "rate": overall_rate},
        "sections": sections,
        "issue_top": issue_top,
        "alerts": alerts,
        "suggestions": build_suggestions(rows, reader.read_material_records()),
        "file": info["file_name"], "mtime": info["mtime"],
    }


def _date_to_month(date_str: str) -> Optional[int]:
    """从日期字符串提取月份。支持 `2026.7.3` / `2026.10.2` / `2026/7/3` 等。"""
    if not date_str:
        return None
    m = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", date_str.strip())
    if m:
        return int(m.group(2))
    return None


def build_material_inspection(month: Optional[int] = None) -> Dict[str, Any]:
    """构建原料来料检验看板数据。

    month: 目标月份数字；None 取当前系统月。按「检验日期」过滤到所选月。

    返回：
    {
      "month": "7月",
      "results": [{name, count}...],            # 检验结果分布（合格/不合格/让步接收）
      "suppliers": [{name, batches, qty, concession, reject}...],
      "materials_top": [{name, count}...],
      "issues_top": [{name, count}...],
      "alerts": [{date, supplier, material, spec, result, disp}...],  # 退货+让步
      "file": ..., "mtime": ...
    }
    """
    records = reader.read_material_records()
    target = month if month is not None else _current_month_num()

    # 全部记录涉及的月份（升序），供前端月份选择器使用
    all_month_nums = sorted({_date_to_month(r["date"]) for r in records if _date_to_month(r["date"])})
    months = [m for m in all_month_nums]

    # 按检验日期过滤到目标月
    rows = [r for r in records if _date_to_month(r["date"]) == target]

    # 结果分布
    from collections import Counter, defaultdict
    result_counter = Counter(r["result"] for r in rows if r["result"])
    results = [{"name": k, "count": v} for k, v in result_counter.most_common()]

    # 供应商表现
    supplier_map: Dict[str, Dict[str, float]] = defaultdict(lambda: {"batches": 0, "qty": 0.0, "concession": 0, "reject": 0})
    for r in rows:
        sup = r["supplier"] or "未填"
        s = supplier_map[sup]
        s["batches"] += 1
        s["qty"] += r["qty"]
        if r["disp"] in ("让步入库", "让步接收"):
            s["concession"] += 1
        if r["disp"] in ("退货", "不合格") or r["result"] == "不合格":
            s["reject"] += 1
    suppliers = [
        {"name": k, "batches": int(v["batches"]), "qty": v["qty"], "concession": v["concession"], "reject": v["reject"]}
        for k, v in supplier_map.items()
    ]
    # 按让步+退货 降序（问题多的靠前）
    suppliers.sort(key=lambda x: (x["concession"] + x["reject"], x["batches"]), reverse=True)

    # 物料/问题 TOP
    materials_top = _top_counter([r["material"] for r in rows])
    issues_top = _top_counter([r["problem"] for r in rows if r["problem"]])

    # 退货 + 让步接收预警明细
    alerts = [
        {
            "date": r["date"], "supplier": r["supplier"], "material": r["material"],
            "spec": r["spec"], "result": r["result"], "disp": r["disp"], "problem": r["problem"],
        }
        for r in rows if r["disp"] in ("退货", "让步入库", "让步接收") or r["result"] == "不合格"
    ]

    info = reader.material_file_info()
    return {
        "month": f"{target}月",
        "months": months,
        "results": results,
        "suppliers": suppliers,
        "materials_top": materials_top,
        "issues_top": issues_top,
        "alerts": alerts,
        "file": info["file_name"], "mtime": info["mtime"],
    }


# ======================================================================
# 四预警 → 建议动作（工具②）
# ======================================================================

from collections import Counter, defaultdict  # noqa: E402

# —— 六分类（问题类型，关键词匹配，按序命中，与《00-质量分析规则》六分类一致）——
# 注：第六类暂未定名，统一归「第六类」，今后依据实际数据重新定名。
_CLASSIFY_RULES = [
    ("材料缺陷", ["裂", "崩", "断裂", "裂纹", "断"]),
    ("表面质量", ["砂眼", "粗糙", "发蓝", "抛丸", "发黄", "氧化", "锈", "麻点", "毛刺"]),
    ("装配配合", ["装配", "配合", "间隙", "不流畅", "卡", "紧"]),
    ("尺寸精度", ["尺寸", "孔径", "超差", "偏", "高出", "不标准", "错位", "孔位"]),
    ("标识问题", ["标识", "字迹"]),
]

# —— 姓名异写归并（同名异写按第一个合并）——
# 规则：按「姓氏」归一 + 名字近似归并。左为 canonical（第一个出现的写法），右为异写集合。
_NAME_ALIASES = {
    "杨韶磊": {"杨邵磊"},
    "闫若琦": {"闫若奇"},
}


def _canonical_name(name: str) -> str:
    """把异写姓名归并到 canonical（第一个出现的写法）。"""
    if not name:
        return name
    for canon, aliases in _NAME_ALIASES.items():
        if name == canon or name in aliases:
            return canon
    return name


def classify_problem(text: str) -> str:
    """问题描述 → 六分类之一；空/无命中返回「第六类」。"""
    if not text:
        return ""
    for cat, kws in _CLASSIFY_RULES:
        if any(k in text for k in kws):
            return cat
    return "第六类"


# —— 建议动作映射表（规格 §10.2）——
_SUGGEST_TEMPLATE = {
    "3.1": {"dept": "对应工段主管 + 质检", "deadline": "7天", "level": "高",
            "action": "对该员工专项复盘；核对作业标准；针对性培训/纠偏"},
    "3.2": {"dept": "对应工段主管", "deadline": "3天", "level": "高",
            "action": "补齐当月抽检记录，核查是否漏检"},
    "3.3": {"dept": "采购 + 质检", "deadline": "15天", "level": "备注",
            "action": "跟踪厂家整改；让步件隔离标识；评估是否更换供应商"},
    "3.4": {"dept": "采购", "deadline": "15天", "level": "高",
            "action": "约谈供应商；加大来料抽检比例/频次"},
}


def build_suggestions(workshop_rows, material_rows) -> List[dict]:
    """四预警 → 建议动作清单（工具②核心）。按 高→中→备注 排序返回。

    workshop_rows: 某月车间抽检行（含 name/section/problem/disp）
    material_rows: 来料行（含 supplier/material/result/disp/problem）
    """
    suggestions: List[dict] = []

    # 3.1 反复出现：同一人 + 同一问题分类 >= 3 次（姓名异写先归并）
    combo: Dict[tuple, list] = defaultdict(list)
    for r in workshop_rows:
        if not r.get("problem"):
            continue
        cat = classify_problem(r["problem"])
        if not cat:
            continue
        name = _canonical_name(r.get("name") or "未署名")
        combo[(name, cat)].append(r)
    for (name, cat), rs in combo.items():
        if len(rs) >= 3:
            t = _SUGGEST_TEMPLATE["3.1"]
            suggestions.append({"problem": f"{name}·{cat} 反复出现 {len(rs)} 次",
                                "name": name, "category": cat, "count": len(rs),
                                "dept": t["dept"], "deadline": t["deadline"],
                                "level": t["level"], "action": t["action"], "source_alert": "3.1"})

    # 3.2 记录盲区：某工段当月记录 < 5 条
    sec_cnt = Counter((r.get("section") or "未填") for r in workshop_rows)
    for sec, c in sec_cnt.items():
        if c < 5:
            t = _SUGGEST_TEMPLATE["3.2"]
            suggestions.append({"problem": f"{sec} 工段当月记录仅 {c} 条（<5 盲区）",
                                "dept": t["dept"], "deadline": t["deadline"],
                                "level": t["level"], "action": t["action"], "source_alert": "3.2"})

    # 3.3 来料让步接收清单：处置含「让步」
    concession = [r for r in material_rows if "让步" in (r.get("disp") or "")]
    if concession:
        t = _SUGGEST_TEMPLATE["3.3"]
        summary = "；".join(f"{r.get('supplier') or '未填'}·{r.get('material') or ''} {r.get('spec') or ''}"
                            for r in concession[:5])
        more = f" 等 {len(concession)} 批" if len(concession) > 5 else ""
        suggestions.append({"problem": f"来料让步接收 {len(concession)} 批：{summary}{more}",
                            "dept": t["dept"], "deadline": t["deadline"],
                            "level": t["level"], "action": t["action"], "source_alert": "3.3"})

    # 3.4 供应商关注：同一供应商 >= 2 批让步
    sup_c = Counter((r.get("supplier") or "未填") for r in concession)
    for sup, c in sup_c.items():
        if c >= 2:
            t = _SUGGEST_TEMPLATE["3.4"]
            suggestions.append({"problem": f"供应商 {sup} 让步接收 {c} 批（≥2 关注）",
                                "dept": t["dept"], "deadline": t["deadline"],
                                "level": t["level"], "action": t["action"], "source_alert": "3.4"})

    # 按 高→备注 排序
    order = {"高": 0, "中": 1, "备注": 2}
    suggestions.sort(key=lambda s: order.get(s["level"], 9))
    return suggestions


# ======================================================================
# 跨月反复问题锚点（8D 闭环的第二维度：按「工段 + 问题主题」跨月聚合）
# ======================================================================

# 问题主题关键词组：把大量异写（试验/实验、螺纹裂/齿崩/齿推/勾头裂/崩皮 等）归并到同一根因主题。
# 按序命中，第一个命中的主题生效。key=主题名（不含工段，工段在锚点里单独记），value=触发关键词（任一命中即可）。
_PROBLEM_THEMES = [
    ("螺纹裂·齿崩", ["螺纹裂", "螺纹崩", "齿崩", "齿裂", "齿推", "勾头裂", "螺纹微裂", "螺纹有压裂纹", "崩皮"]),
    ("尺寸超差", ["尺寸超差", "尺寸偏差", "超差", "孔径"]),
    ("发蓝不均匀", ["发蓝"]),
    ("通规不过", ["通规"]),
]


def classify_theme(problem: str) -> str:
    """问题描述 → 跨月主题（按主题关键词归并）。空/无命中返回「其他」。"""
    if not problem:
        return ""
    for theme, kws in _PROBLEM_THEMES:
        if any(k in problem for k in kws):
            return theme
    return "其他"


def build_cross_month_anchors(all_months: Dict[str, Any]) -> List[dict]:
    """跨月反复问题锚点：同一「工段 + 问题主题」跨 ≥2 个月出现即触发。

    all_months: reader.load_all_months() 返回的 {月份标签: {is_new, rows}}。

    返回 [{theme, section, by_month:{月:次数}, total, card_id}...]，按 total 降序。
    """
    # 归并键：(工段, 主题) → {月份: 次数}
    combo: Dict[tuple, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for label, entry in all_months.items():
        for r in entry["rows"]:
            if not r.get("problem"):
                continue
            theme = classify_theme(r["problem"])
            if not theme or theme == "其他":
                continue
            sec = r.get("section") or "未填"
            combo[(sec, theme)][label] += 1

    anchors = []
    for (sec, theme), by_month in combo.items():
        # 触发条件：跨 ≥2 个月出现
        if len(by_month) < 2:
            continue
        total = sum(by_month.values())
        anchors.append({
            "theme": theme,
            "section": sec,
            "by_month": dict(sorted(by_month.items(), key=lambda kv: aggregate_month_num(kv[0]) or 0)),
            "total": total,
            "card_id": f"{sec}_{theme}",
        })
    anchors.sort(key=lambda a: -a["total"])
    return anchors


def aggregate_month_num(label: str) -> Optional[int]:
    """月份标签 → 数字（复用 _parse_month_num）。"""
    return _parse_month_num(label)
