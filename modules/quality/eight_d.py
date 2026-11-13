"""8D 问题解决闭环（工具③）：两个维度自动生成 8D 卡，D5–D8 可读写台账。

维度一（3.1 反复出现）：从 build_suggestions 里 source_alert == "3.1"（同一人 + 同一分类 ≥3 次）派生。
维度二（跨月锚点）：同一「工段 + 问题主题」跨 ≥2 个月反复出现（如热处理螺纹裂 8/9/10 月持续），
  体现「同一根因长期未根治」的痛点。

数据模型：
- 每张卡统一结构：id / type(repeat | cross_month) / problem / d1_team / d2_desc /
  d3_action / d4_rootcause / d5_correct / d6_verify / d7_prevent / d8_closed / status。
- D1–D4 从数据派生，D5–D8 可读写台账 data/8d_closure.json（独立于 data/raw，红线：绝不写回原始质检 Excel）。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from modules.quality import aggregate, reader

# 台账文件（项目根 data/ 下，与 data/raw 隔离）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLOSURE_FILE = os.path.join(_PROJECT_ROOT, "data", "8d_closure.json")

# 可写回字段白名单
_EDITABLE_FIELDS = ("d1_team", "d3_action", "d4_rootcause", "d5_correct",
                    "d6_verify", "d7_prevent", "d8_closed", "status")


def _load() -> Dict[str, Any]:
    """读取台账；不存在或损坏时返回空结构。"""
    if not os.path.exists(CLOSURE_FILE):
        return {"cards": {}}
    try:
        with open(CLOSURE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "cards" not in data:
            return {"cards": {}}
        return data
    except (json.JSONDecodeError, OSError):
        return {"cards": {}}


def _save(data: Dict[str, Any]) -> None:
    """写回台账（原子写：先写临时文件再替换）。"""
    os.makedirs(os.path.dirname(CLOSURE_FILE), exist_ok=True)
    tmp = CLOSURE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CLOSURE_FILE)


def _derive_repeat_cards(suggestions: List[dict], workshop_rows: List[dict]) -> List[dict]:
    """维度一：从 3.1 反复出现建议派生 8D 卡（人 + 分类）。"""
    cards = []
    for s in suggestions:
        if s.get("source_alert") != "3.1":
            continue
        name = s.get("name") or "未署名"
        cat = s.get("category") or "第六类"
        count = s.get("count", 0)

        # 最近一次处置方式（临时措施 D3）
        disp = ""
        for r in reversed(workshop_rows):
            rn = aggregate._canonical_name(r.get("name") or "")
            rc = aggregate.classify_problem(r.get("problem") or "")
            if rn == name and rc == cat and r.get("disp"):
                disp = r["disp"]
                break

        card_id = f"repeat_{name}_{cat}"
        cards.append({
            "id": card_id,
            "type": "repeat",
            "problem": s["problem"],
            "name": name,
            "category": cat,
            "count": count,
            "d1_team": s.get("dept", "对应工段主管 + 质检"),
            "d2_desc": s["problem"],
            "d3_action": disp or "待定（历史无明确处置记录）",
            "d4_rootcause": "",
            "d5_correct": "",
            "d6_verify": "",
            "d7_prevent": "",
            "d8_closed": False,
            "status": "待执行",
        })
    return cards


def _derive_cross_month_cards(all_months: Dict[str, Any]) -> List[dict]:
    """维度二：从跨月锚点派生 8D 卡（工段 + 问题主题）。"""
    anchors = aggregate.build_cross_month_anchors(all_months)
    cards = []
    for a in anchors:
        by_month_str = "；".join(f"{m.replace('月', '')}月{x}次" for m, x in a["by_month"].items())
        problem = f"{a['section']}·{a['theme']} 跨月反复 {a['total']} 次（{by_month_str}）"
        cards.append({
            "id": a["card_id"],
            "type": "cross_month",
            "problem": problem,
            "theme": a["theme"],
            "section": a["section"],
            "by_month": a["by_month"],
            "count": a["total"],
            "d1_team": f"{a['section']}工段主管 + 质检",
            "d2_desc": problem,
            "d3_action": "待定（历史无明确处置记录）",
            "d4_rootcause": "",
            "d5_correct": "",
            "d6_verify": "",
            "d7_prevent": "",
            "d8_closed": False,
            "status": "待执行",
        })
    return cards


def build_8d_cards(all_months: Dict[str, Any], workshop_rows: List[dict]) -> List[dict]:
    """生成 8D 卡列表（双维度，合并已写回的 D5–D8 状态）。"""
    material_rows = reader.read_material_records()
    suggestions = aggregate.build_suggestions(workshop_rows, material_rows)

    derived = _derive_repeat_cards(suggestions, workshop_rows) + _derive_cross_month_cards(all_months)

    saved = _load()
    saved_cards = saved.get("cards", {})
    for c in derived:
        key = c["id"]
        if key in saved_cards:
            sc = saved_cards[key]
            for field in _EDITABLE_FIELDS:
                if field in sc:
                    c[field] = sc[field]
    return derived


def get_8d_cards(month: Optional[int] = None) -> Dict[str, Any]:
    """返回某月 8D 卡列表（含 note）。跨月锚点基于全量月份数据计算，3.1 卡基于目标月。"""
    all_months = reader.load_all_months()
    available = sorted(all_months.keys(), key=lambda l: aggregate._parse_month_num(l) or 0)

    target = month if month is not None else aggregate._current_month_num()
    target_label = f"{target}月"

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

    if chosen is None:
        return {"month": target_label, "note": "暂无质量抽检数据", "cards": []}

    rows = all_months[chosen]["rows"]
    cards = build_8d_cards(all_months, rows)
    return {"month": chosen, "note": note, "cards": cards}


def update_8d_card(card_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """写回某张 8D 卡的 D5–D8 等字段。只允许更新白名单字段，防止污染其它字段。"""
    allowed = {"d4_rootcause", "d5_correct", "d6_verify", "d7_prevent", "d8_closed", "status"}
    data = _load()
    cards = data.setdefault("cards", {})
    card = cards.setdefault(card_id, {"id": card_id})
    for k, v in fields.items():
        if k in allowed:
            card[k] = v
    _save(data)
    return card


def reset_8d_card(card_id: str) -> None:
    """删除某张 8D 卡的写回状态（回到待执行）。"""
    data = _load()
    data.setdefault("cards", {}).pop(card_id, None)
    _save(data)
