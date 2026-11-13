"""业务函数 → LangChain tool 封装（agent-core 工具层）。

把已验证的确定性业务函数封装成模型可调用的 tool，是「确定性包裹不确定性」四道防线里的第②层：
模型只负责「选工具 + 转述」，数据仍由确定性代码精确计算，逐值可验证。

铁律：
- tool 只复用已 0 差异验证的确定性实现（如 flow_stats.build_flow_stats），绝不重写计算逻辑；
- 每个 tool 的 docstring 必须写「使用时机」（用户会怎么问、什么时候该调它），这是模型选对工具的头号关键；
- 只暴露「只读」动作；写操作（跑排产 / 回填）一律不进 tool，走人工确认通道。
"""

from __future__ import annotations

import json
import re

from langchain.tools import tool

from modules.inventory import flow_stats
from modules.production import dashboard_calc
from modules.production import gap_stat

from . import spec_aliases


def _fmt_num(v) -> int | float:
    """数字格式化：整数去小数点（500.0→500），小数保留合理精度，便于模型与人类阅读。"""
    f = float(v)
    if f == int(f):
        return int(f)
    return round(f, 4)


def _fmt_gap(v):
    """缺口值 → 方向标注结构，把「看负号判方向」这个模型最易错的活儿提前由确定性代码做掉。

    - v > 0  → {"缺口": n, "富余": 0}（正数 = 缺口，需补/生产）
    - v < 0  → {"缺口": 0, "富余": n}（负数 = 富余，够用，n = 绝对值）
    - v == 0 → {"缺口": 0, "富余": 0}
    - v None → None（该配件无此工序）

    返回「缺口/富余」显式字段，模型只需照读方向、无需再判符号，杜绝「绝对值大的负数被误读成缺口大」。
    """
    if v is None:
        return None
    if v > 0:
        return {"缺口": _fmt_num(v), "富余": 0}
    if v < 0:
        return {"缺口": 0, "富余": _fmt_num(abs(v))}
    return {"缺口": 0, "富余": 0}


def _fmt_req(v):
    """半成品需求计划：需求量（要生产多少半成品），恒 ≥ 0，不是缺口，不做方向标注。

    - v > 0 → 需求量（裸数字）
    - v == 0 → 0
    - v None → None（该配件无此工序/无需求）
    """
    return _fmt_num(v) if v is not None else None


def _nums(s) -> list:
    """提取字符串里的数字序列，如 '71-75'→['71','75']、'S73'→['73']。"""
    return re.findall(r"\d+", str(s))


def _match_label(kw: str, label: str) -> bool:
    """缺口块规格（block_label）匹配：字母对齐 + 数字指纹精确等值/前缀。

    - 关键词带字母（如 S73、80D）：该字母 MUST 在 label 里一致出现——S73 只匹配内管钳 S73，
      不误伤纯数字的套管钳 73/89；80D 只匹配加力 80D/18"。
    - 关键词纯数字（如 73、71-75、80）：数字指纹精确等值或前缀——73→S73 与 73/89 都返回
      （纯数字天然歧义，合理）；80→80D/18"（前缀）；71-75→71-75（精确等值）。
    """
    kw_alpha = re.findall(r"[A-Za-z]+", kw)
    label_alpha = re.findall(r"[A-Za-z]+", label)
    if kw_alpha:
        if not label_alpha:
            return False
        if kw_alpha != label_alpha:
            return False
    kw_nums = _nums(kw)
    label_nums = _nums(label)
    if not kw_nums or not label_nums:
        return kw.lower() in label.lower() or label.lower() in kw.lower()
    if kw_nums == label_nums:
        return True
    if kw_nums == label_nums[: len(kw_nums)]:
        return True
    return False


# 缺口表品类别名（V2.0 sheet 名 = 加力/美式/内管钳/钻杆钳/套管钳）
_CAT_ALIAS = {
    "加力钳": "加力",
    "加力": "加力",
    "美重": "美式",
    "美式": "美式",
    "美式重型": "美式",
    "含钛": "美式",
    "内管钳": "内管钳",
    "钻杆钳": "钻杆钳",
    "套管钳": "套管钳",
}


def _resolve_cat(kw: str) -> str | None:
    """品类关键词 → V2.0 sheet 名（先别名精确，再模糊包含）。"""
    kw = kw.strip()
    if kw in _CAT_ALIAS:
        return _CAT_ALIAS[kw]
    for s in gap_stat.PRODUCT_SHEETS:
        if kw in s or s in kw:
            return s
    return None


_CATEGORIES = flow_stats.PRODUCT_CATEGORIES


def _spec_examples(stats, scope):
    """未匹配到规格时，给模型每个品类的规格示例，便于纠正关键词。"""
    examples = {}
    for name in scope:
        items = stats["detail"].get(name, [])
        specs = list(dict.fromkeys(it["spec"] for it in items))[:5]
        examples[name] = specs
    return examples


@tool
def query_stock(month: int = 0, category: str = "", spec: str = "") -> str:
    """查成品入出库台账某月的库存：入库 / 出库 / 结存。可查整体、指定品类、指定规格三个粒度。

    只要用户的问题涉及库存、数量、结存、出入库，就调用本工具获取真实数据，不要反问、不要猜测，包括但不限于：
    - 「库存还剩多少」「XX月入库/出库/结存」「库存够不够」→ 不传 category/spec；
    - 「哪个品类最多/最少」「各品类比较/排名」→ 不传 category/spec，从返回的 6品类 里自行比较；
    - 「加力钳入库多少」→ category 传「加力钳」；
    - 「加力钳 95 入库多少」「108 出库多少」「绿色的结存」→ 拆出 spec 传规格/特征关键词（95、108、绿 等）。
    6 品类 = 加力钳 / 美重 / 含钛 / 钻杆钳 / 套管钳 / 内管钳；两大系列 = 管钳 / 自由钳。
    规格以台账为准，用户口语简称按数字精确匹配（非子串）：加力95→Z95S、加力195→Z195S、美重24→Z24"、71-75→φ71-75、73/89→φ73/89、内管钳56→内管钳S56。
    停产件不返回：Q 前缀（轻型，如 Q95S、Q24"）与 Z小95S 均已停产。
    美重新款/老款区分：默认老款（无 -01）；用户明确说「新款」时，spec 传「新款24」或 category 传「美重新款」→ 匹配带 -01 的新款编码。

    Args:
        month: 目标月份，1-12 的整数。用户未指定月份时传 0 或不传，默认当前月。
        category: 品类名（可选）。用户问到具体品类时传，如「加力钳」「美重」，支持模糊（「加力」也匹配「加力钳」）。美重新款时传「美重新款」。
        spec: 规格或特征关键词（可选）。问规格传数字（如「95」「108」「71-75」），问颜色/品牌传文字（如「绿」「吉林」）。数字按规格精确匹配，文字按特征匹配。美重新款时传「新款24」。
    """
    stats = flow_stats.build_flow_stats(month if month > 0 else None)
    month_val = stats["month"]

    def _p(x):
        return {"入库": _fmt_num(x["in"]), "出库": _fmt_num(x["out"]), "结存": _fmt_num(x["stock"])}

    # 0. 新款检测（美重新款/老款区分；「新款」可能出现在 category 或 spec）
    is_new = "新款" in category

    # 1. 品类匹配（category 可选）
    cat_names = []
    if category.strip():
        kw = category.replace("新款", "").strip()
        cat_names = [p for p in _CATEGORIES if kw in p or p in kw]
        if not cat_names:
            return json.dumps({
                "月份": month_val,
                "说明": f"未找到品类「{kw}」，可选品类：{'/'.join(_CATEGORIES)}",
            }, ensure_ascii=False)

    # 2. 规格/特征匹配（spec 可选，优先级最高）
    if spec.strip():
        kw = spec.strip()
        scope = cat_names if cat_names else list(_CATEGORIES)
        matches = []
        has_digit = any(ch.isdigit() for ch in kw)
        this_is_new = is_new or "新款" in kw
        for name in scope:
            items = stats["detail"].get(name, [])
            if has_digit:
                # 数字关键词 → 规格数字指纹精确匹配（「95」→Z95S，不误伤 Z195S/Q95S）
                for it in spec_aliases.match_specs(name, kw, items, is_new=this_is_new):
                    matches.append({
                        "品类": name,
                        "规格": it["spec"],
                        "特征": it["feature"],
                        **_p(it),
                    })
            else:
                # 非数字关键词（颜色/品牌）→ 特征子串匹配
                for it in items:
                    if kw in str(it["feature"]) or kw in str(it["spec"]):
                        matches.append({
                            "品类": name,
                            "规格": it["spec"],
                            "特征": it["feature"],
                            **_p(it),
                        })
        if matches:
            return json.dumps({
                "月份": month_val,
                "匹配数": len(matches),
                "匹配规格": matches,
            }, ensure_ascii=False)
        return json.dumps({
            "月份": month_val,
            "说明": f"未找到规格「{kw}」",
            "可选规格示例": _spec_examples(stats, scope),
        }, ensure_ascii=False)

    # 3. 指定品类（无规格）→ 返回该品类汇总 + 规格明细
    if cat_names:
        result = {"月份": month_val, "品类": {}}
        for name in cat_names:
            p = next(x for x in stats["products"] if x["name"] == name)
            items = stats["detail"].get(name, [])
            result["品类"][name] = {
                "汇总": _p(p),
                "规格明细": [{"规格": it["spec"], "特征": it["feature"], **_p(it)} for it in items],
            }
        return json.dumps(result, ensure_ascii=False)

    # 4. 默认：合计 + 6品类 + 两大系列
    result = {
        "月份": month_val,
        "合计": _p(stats["total"]),
        "6品类": {p["name"]: _p(p) for p in stats["products"]},
        "两大系列": {s["name"]: _p(s) for s in stats["series"]},
    }
    return json.dumps(result, ensure_ascii=False)


@tool
def query_gap(category: str = "", spec: str = "") -> str:
    """查生产缺口：最新排产结果里，各规格/配件的缺口（装配缺口、机加工缺口）与成品计划、半成品需求计划。

    只要用户的问题涉及「缺口、还差多少、要排产多少、缺料、差多少」就调用本工具，不要反问、不要猜测，包括：
    - 「71-75 还差多少」「哪些规格有缺口」→ spec 传「71-75」或不传；
    - 「钻杆钳的缺口」→ category 传「钻杆钳」；
    - 「S73 差多少」「加力 80 的缺口」→ spec 传「S73」「80」。
    5 品类（缺口表）= 加力钳、美式（含美重+含钛）、内管钳、钻杆钳、套管钳。
    字段语义（模型照读即可、勿再自行判方向）：
    - 缺口仅含「装配缺口」「机加工缺口」两列，返回 {"缺口": n, "富余": 0} 或 {"缺口": 0, "富余": n}，null=无此工序；正=缺口（需补/生产），负=富余（够用）。「富余」绝对值大 = 富余多、够用，不是缺口大。
    - 「半成品需求计划」= 要生产多少半成品的需求量（恒 ≥ 0），是需求计划、不是缺口，返回裸数字，别把它当缺口解读。
    数据来源：最新一次排产结果（半成品生产计划V2.0），非实时台账；若刚更新成品计划，需先在「生产缺口统计」页点「排产统计」。
    规格按数字精确匹配（非子串）：71-75→钻杆钳、73/89→套管钳、S73→内管钳、80→加力80D、54→钻杆钳54-56。

    Args:
        category: 品类名（可选）。问具体品类时传，如「钻杆钳」「加力钳」「美重」。
        spec: 规格关键词（可选）。问规格传数字或编号，如「71-75」「S73」「80」「54」。
    """
    data = gap_stat.extract_gap_stat(gap_stat.resolve_result_file())

    # 1. 品类匹配（先别名精确，再模糊；scope = 目标 sheet 列表）
    scope = list(gap_stat.PRODUCT_SHEETS)
    if category.strip():
        target = _resolve_cat(category)
        if target is None:
            return json.dumps({
                "说明": f"未找到品类「{category.strip()}」，可选：{'/'.join(gap_stat.PRODUCT_SHEETS)}",
            }, ensure_ascii=False)
        scope = [target]

    # 2. 规格匹配（收集命中的 (品类, 块)）
    hits = []
    if spec.strip():
        kw = spec.strip()
        for sheet in scope:
            for b in data["products"][sheet]["blocks"]:
                if _match_label(kw, b["block_label"]):
                    hits.append((sheet, b))
        if not hits:
            examples = {s: [b["block_label"] for b in data["products"][s]["blocks"]] for s in scope}
            return json.dumps({
                "说明": f"未找到规格「{kw}」",
                "可选规格": examples,
            }, ensure_ascii=False)
    else:
        for sheet in scope:
            for b in data["products"][sheet]["blocks"]:
                hits.append((sheet, b))

    # 3. 组装返回：带 spec 返回完整配件（含负缺口）；不带 spec 只列有正缺口的配件
    is_full = bool(spec.strip())
    blocks_out = []
    for sheet, b in hits:
        # 成品计划（块头 headers，加力/美式有 J/K 两列，用 col_titles 中文标题作 key）
        plan = {}
        hdr = b["headers"]
        titles = b["col_titles"]
        if "plan1" in hdr and hdr["plan1"].get("value") is not None:
            plan[titles.get("J", "成品计划")] = _fmt_num(hdr["plan1"]["value"])
        if "plan2" in hdr and hdr["plan2"].get("value") is not None:
            plan[titles.get("K", "成品计划")] = _fmt_num(hdr["plan2"]["value"])
        # 配件缺口（正数=缺口，负数=富余，null=无此工序）
        rows_out = []
        for row in b["rows"]:
            g = row["gap"]
            need, gp, machine = g.get("need"), g.get("gap"), g.get("machine")
            if not is_full:
                # 缺口仅含「装配缺口」「机加工缺口」两列；「半成品需求计划」是需求量、非缺口，不计入
                has_pos = (
                    (gp is not None and gp > 0)
                    or (machine is not None and machine > 0)
                )
                if not has_pos:
                    continue
            rows_out.append({
                "配件": row["name"],
                "半成品需求计划": _fmt_req(need),
                "装配缺口": _fmt_gap(gp),
                "机加工缺口": _fmt_gap(machine),
            })
        blocks_out.append({
            "品类": sheet,
            "规格": b["block_label"],
            "成品计划": plan,
            "配件": rows_out,
        })

    return json.dumps({
        "说明": "基于最新排产结果；缺口仅含「装配缺口」「机加工缺口」两列（正=缺口需补/生产，负=富余够用，null=无此工序）；「半成品需求计划」=需求计划量（要生产多少，非缺口）",
        "规格块": blocks_out,
    }, ensure_ascii=False)


def _fmt_prod_month(data) -> dict:
    """dashboard_calc 单月数据 → 中文语义结构（计划数/完成数/完成率）。"""
    ov = data["overall"]
    return {
        "月份": data["month"],
        "总体": {
            "计划数": _fmt_num(ov["plan"]),
            "完成数": _fmt_num(ov["done"]),
            "完成率": _fmt_num(ov["rate"]),
        },
        "6品类": [
            {
                "品类": p["key"],
                "计划数": _fmt_num(p["plan"]),
                "完成数": _fmt_num(p["done"]),
                "完成率": _fmt_num(p["rate"]),
            }
            for p in data["products"]
        ],
        "4区段": [
            {
                "区段": d["key"],
                "计划数": _fmt_num(d["plan"]),
                "完成数": _fmt_num(d["done"]),
                "完成率": _fmt_num(d["rate"]),
            }
            for d in data["dimensions"]
        ],
    }


@tool
def query_production(month: int = 0) -> str:
    """查成品生产计划的完成率/进度：计划数、完成数、完成率，分 6 品类与 4 区段。

    只要用户的问题涉及「完成率、进度、完成得怎么样、哪些品类拖后腿、超产、欠产」就调用本工具，不要反问、不要猜测，包括：
    - 「本月/11月完成率多少」「完成得怎么样」→ month 传 11（或 0 默认最新月）；
    - 「哪些品类拖后腿」「哪个品类完成率最低/最高」→ 不传或传目标月，从返回的「6品类」里比较完成率；
    - 「10月完成率」「上个月进度」→ month 传 10；
    - 「各月完成率趋势」→ 不传 month，从「各月完成率」（总体）概览里读；
    - 「各月某品类完成率趋势」（如「各月加力钳完成率」「美式逐月趋势」）→ 不传 month，从「各月品类完成率」概览里读。

    语义（模型照读即可、勿自行判断方向）：
    - 完成率 = 完成数 ÷ 计划数 × 100%；完成率 MAY 超过 100%（表示超产、超额完成，是正常的，不是错误）；完成率越低 = 进度越慢/拖后腿。
    - 「计划数」= 要生产的量（未完成数量），「完成数」= 当月实际完成量。
    - 4 区段 = 计划的来源分类（历史 / 当月库存 / 当月订单 / 世达），不是产能。
    - 6 品类 = 加力钳 / 美式 / 含钛 / 内管钳 / 钻杆钳 / 套管钳。

    注意区分：问「进度/完成率/完成得怎么样」用本工具；问「还差多少/缺口/缺料」用 query_gap。

    Args:
        month: 目标月份，1-12 的整数。用户未指定月份时传 0 或不传，返回最新月详情 + 各月完成率概览。
    """
    path = dashboard_calc.resolve_plan_file()

    # 指定单月
    if month > 0:
        data = dashboard_calc.calc_month(path, month)
        if not data:
            avail = dashboard_calc.scan_months(path)
            return json.dumps({
                "说明": f"未找到 {month} 月的成品计划数据",
                "可用月份": avail,
            }, ensure_ascii=False)
        return json.dumps(_fmt_prod_month(data), ensure_ascii=False)

    # 默认：最新月详情 + 各月完成率概览（趋势）
    d = dashboard_calc.build_dashboard(path)
    latest = d["latest"]
    overview = {
        str(m): {
            "计划数": _fmt_num(v["overall"]["plan"]),
            "完成数": _fmt_num(v["overall"]["done"]),
            "完成率": _fmt_num(v["overall"]["rate"]),
        }
        for m, v in d["months"].items()
    }
    # 各月各品类完成率（月份 × 品类 → 完成率），支持「某品类逐月完成率趋势」
    by_category = {
        str(m): {p["key"]: _fmt_num(p["rate"]) for p in v["products"]}
        for m, v in d["months"].items()
    }
    result = _fmt_prod_month(latest)
    result["各月完成率"] = overview
    result["各月品类完成率"] = by_category
    return json.dumps(result, ensure_ascii=False)


# 工具清单：模型可调用的全部只读工具（后续按能力域逐步扩充）
ALL_TOOLS = [query_stock, query_gap, query_production]
