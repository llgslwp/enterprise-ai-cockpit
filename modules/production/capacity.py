"""产能（可产数量）计算：多品类「组合件递减多维 min」口径。

统一口径（2026-11-20 文鹏口述锁定，取代此前错误的「顺序贪婪竞争」）：
装配是分步的——先把若干件预装成「组合件」，成品再补剩余件。产能按「组合件已装到哪一步」
分维度，组合件从最高级递减到「无（裸件凑装）」；每维可产 = min(组合件数量, 各补件可用量)，
补件在维度间顺序消耗。钻杆钳两维、加力钳三维是同一套逻辑，仅预装层级数不同。

【钻杆钳两维】
生产链：配件 → 组装 → 组装简易钳体 → 热处理 → 装配（+活动齿块 +自由钳外管）→ 成品
  第一维度（装配）：1 把 = 1 组装简易钳体(装配I) + 1 活动齿块(半成品H) + 1 自由钳外管(半成品H)
  第二维度（组装追加，触发 = 齿块和外管都有剩余）：
    1 简易钳体 = 2 固定钢板(毛坯C) + 1 活动钳体(H) + 1 夹紧头(H)
               + 2 长销子(H) + 1 短销子(H) + 2 组装齿块+方块座(H)

【加力钳三维】（1 把 = 8 件各 1：钳体/外管/小钳口/大钳口/固定帽/螺母/把手/内管镀锌）
  第一维：三合一组合件(钳体+外管+小钳口, 装配I) + 5 补件(大钳口/固定帽/螺母/把手/内管)
  第二维：二合一组合件(钳体+外管, 装配I) + 6 补件(小钳口/大钳口/固定帽/螺母/把手/内管)
  第三维：8 件半成品裸件凑装（外管取 待处理+半成品）；补件扣减前两维累计消耗

特殊规则：
- 钻杆钳「组装齿块+方块座」是组合件，产能只看它自身数量。
- 加力钳「把手」全维度额外计入待处理 F；「外管」第三维取 F+H。
- 补件在维度间顺序消耗：第三维补件现有量 = 本维取数列原始值 − 前两维累计消耗（钳体/外管是裸件、不被前两维消耗）。
- 整除一律向下取整（不够 1 套不算）。

数据源 = V2.0 半成品计划表（gap_stat 读同一份）。
分层：`_calc_capacity_core`（钻杆钳）/ `_calc_capacity_jiali_core`（加力钳）是纯计算逻辑；
`calc_capacity` / `calc_capacity_all` 负责读文件 + 调纯函数。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from . import gap_stat

# 列 key（gap_stat 的 cells 用 str(列号) 作 key）
COL_C = str(gap_stat.COL_MAOPI)      # C 毛坯库
COL_F = str(gap_stat.COL_DAICHULI)   # F 待处理
COL_H = str(gap_stat.COL_BANCHENG)   # H 半成品
COL_I = str(gap_stat.COL_ZHUANGPEI)  # I 装配

# 第一维度 BOM：配件名 -> (列 key, 位置说明)；每把用量均为 1
_DIM1 = [
    ("组装简易钳体", COL_I, "装配"),
    ("活动齿块", COL_H, "半成品"),
    ("自由钳外管", COL_H, "半成品"),
]

# 第二维度 BOM：配件名 -> (列 key, 每组装 1 个简易钳体的用量)
_DIM2 = [
    ("固定钢板", COL_C, 2),
    ("活动钳体", COL_H, 1),
    ("夹紧头", COL_H, 1),
    ("长销子", COL_H, 2),
    ("短销子", COL_H, 1),
    ("组装齿块+方块座", COL_H, 2),
]

# 第一维度三件名（用于判定借件规格：任一「见XX」即借件）
_DIM1_NAMES = [n for n, _, _ in _DIM1]

# 加力钳 10 规格取数配置（2026-11-20 文鹏口述锁定）。
# key = 规格数字（self，定位块内行）；share = 7 共享件默认取数数字（英制回退同块公制）；
# body = 钳体行名称（英制「加力钳体（英寸）」）；borrow = 借用件映射（配件名 -> 被借规格数字）；
# label = 展示用规格标签。
_JIALI_SPECS = {
    "80":  {"share": "80",  "body": "加力钳体",        "label": "80D"},
    "18":  {"share": "80",  "body": "加力钳体（英寸）", "label": '18"'},
    "95":  {"share": "95",  "body": "加力钳体",        "label": "95D"},
    "24":  {"share": "95",  "body": "加力钳体（英寸）", "label": '24"'},
    "108": {"share": "108", "body": "加力钳体",        "label": "108D", "borrow": {"加力小钳口": "95"}},
    "132": {"share": "132", "body": "加力钳体",        "label": "132D"},
    "36":  {"share": "132", "body": "加力钳体（英寸）", "label": '36"'},
    "152": {"share": "152", "body": "加力钳体",        "label": "152D", "borrow": {"加力小钳口": "132", "固定帽": "132", "把手": "132"}},
    "195": {"share": "195", "body": "加力钳体",        "label": "195D"},
    "48":  {"share": "195", "body": "加力钳体（英寸）", "label": '48"'},
}

# 7 共享件（英制回退公制行、借用规格被借件回退被借行的件）
_SHARED_PARTS = (
    "加力小钳口", "加力大钳口", "固定帽", "加力螺母", "把手", "加力内管（镀锌）", "加力外管",
)

# 本模块支持产能计算的品类 → 阶段1 支持的规格白名单。
# 加力钳 10 规格单规格孤立算（共享件回退映射，合问竞争属阶段2）；钻杆钳借件/借用规格待阶段2。
SUPPORTED_SPECS = {
    "钻杆钳": ("54-56", "71-75"),
    "加力": tuple(_JIALI_SPECS),
}

# 品类别名 → V2.0 sheet 名（agent 口语「加力钳」归一化到「加力」）
_CAT_ALIAS = {
    "加力钳": "加力", "加力": "加力",
    "钻杆钳": "钻杆钳",
    "美式": "美式", "美重": "美式", "含钛": "美式", "美式重型": "美式",
    "内管钳": "内管钳",
    "套管钳": "套管钳",
}

# 加力钳三维 BOM（公制规格通用，2026-11-20 文鹏口述锁定）。
# 每维 = 组合件(名称, 取数列, 位置说明) 或 None（裸件凑装）+ 补件列表[(名称, 取数列元组, 用量, 位置说明)]。
# 取数列：H=半成品、I=装配、F=待处理；元组 = 多列求和。
_JIALI_DIMS = [
    {
        "名称": "第一维度",
        "组合件": ("加力钳体+外管+小钳口", (COL_I,), "装配"),
        "补件": [
            ("加力大钳口", (COL_H, COL_I), 1, "半成品+装配"),
            ("固定帽", (COL_H, COL_I), 1, "半成品+装配"),
            ("加力螺母", (COL_H, COL_I), 1, "半成品+装配"),
            ("把手", (COL_H, COL_I, COL_F), 1, "半成品+装配+待处理"),
            ("加力内管（镀锌）", (COL_H, COL_I), 1, "半成品+装配"),
        ],
    },
    {
        "名称": "第二维度",
        "组合件": ("加力钳体+外管", (COL_I,), "装配"),
        "补件": [
            ("加力小钳口", (COL_H, COL_I), 1, "半成品+装配"),
            ("加力大钳口", (COL_H, COL_I), 1, "半成品+装配"),
            ("固定帽", (COL_H, COL_I), 1, "半成品+装配"),
            ("加力螺母", (COL_H, COL_I), 1, "半成品+装配"),
            ("把手", (COL_H, COL_I, COL_F), 1, "半成品+装配+待处理"),
            ("加力内管（镀锌）", (COL_H, COL_I), 1, "半成品+装配"),
        ],
    },
    {
        "名称": "第三维度",
        "组合件": None,
        "补件": [
            ("加力钳体", (COL_H,), 1, "半成品"),
            ("加力小钳口", (COL_H,), 1, "半成品"),
            ("加力大钳口", (COL_H,), 1, "半成品"),
            ("固定帽", (COL_H,), 1, "半成品"),
            ("加力螺母", (COL_H,), 1, "半成品"),
            ("把手", (COL_H, COL_F), 1, "半成品+待处理"),
            ("加力内管（镀锌）", (COL_H,), 1, "半成品"),
            ("加力外管", (COL_F, COL_H), 1, "待处理+半成品"),
        ],
    },
]


def _cell(row: Optional[Dict[str, Any]], col_key: str) -> int:
    """取某配件的某列现有量，None/缺行 按 0 处理。"""
    if not row:
        return 0
    v = row.get("cells", {}).get(col_key)
    if v is None:
        return 0
    return int(float(v))


def _sum_cells(row: Optional[Dict[str, Any]], col_keys) -> int:
    """取某配件在多列的现有量之和（如 半成品+装配 = H+I）。"""
    return sum(_cell(row, c) for c in col_keys)


def _find_block(data: Dict[str, Any], category: str, spec: str):
    """定位品类下的规格块，找不到返回 None。"""
    products = data["products"]
    if category not in products:
        return None
    for b in products[category]["blocks"]:
        if b["block_label"] == spec:
            return b
    return None


def _classify_block(block: Dict[str, Any]) -> str:
    """分类规格块，返回 'independent' / 'borrow-item' / 'borrow-spec'。

    - borrow-spec（借用规格）：成品计划 = 0，不单独排产，不计产能。
    - borrow-item（借件规格）：第一维度三件任一「见XX」借用，无独立库存，
      与基准规格共享库存，需阶段2 竞争分配。
    - independent（独立规格）：三件均自有库存，可两维计算。
    """
    plan = (block.get("headers") or {}).get("plan1") or {}
    plan_val = plan.get("value") if isinstance(plan, dict) else None
    if plan_val is None or (isinstance(plan_val, (int, float)) and float(plan_val) == 0):
        return "borrow-spec"
    rows = {r["name"]: r for r in block.get("rows", [])}
    for name in _DIM1_NAMES:
        r = rows.get(name)
        if r and r.get("is_borrow"):
            return "borrow-item"
    return "independent"


def _calc_dim1(rows: Dict[str, Any]) -> Dict[str, Any]:
    """第一维度：min(组装简易钳体·装配I, 活动齿块·半成品H, 自由钳外管·半成品H)。"""
    items = []
    qty = {}
    for name, col, pos in _DIM1:
        n = _cell(rows.get(name), col)
        qty[name] = n
        items.append({"配件": name, "位置": pos, "现有量": n})
    x = min(qty.values())
    bottleneck = [it["配件"] for it in items if it["现有量"] == x]
    for it in items:
        it["可产把数"] = it["现有量"]
        it["是否瓶颈"] = it["配件"] in bottleneck
    return {"可产": x, "明细": items, "瓶颈": bottleneck}


def _calc_dim2(rows: Dict[str, Any], remain_chikuai: int, remain_waiguan: int) -> Dict[str, Any]:
    """第二维度：配件组装追加。触发 = 活动齿块 和 自由钳外管 都还有剩余。"""
    caps = {}
    for name, col, per in _DIM2:
        caps[name] = _cell(rows.get(name), col) // per
    new_jianyi = min(caps.values())
    triggered = remain_chikuai > 0 and remain_waiguan > 0
    y = min(new_jianyi, remain_chikuai, remain_waiguan) if triggered else 0
    if triggered and y > 0:
        if y == new_jianyi:
            bottleneck = [n for n, v in caps.items() if v == new_jianyi]
        elif y == remain_chikuai:
            bottleneck = ["活动齿块"]
        else:
            bottleneck = ["自由钳外管"]
    else:
        bottleneck = []
    return {
        "触发": triggered,
        "可新组简易钳体": new_jianyi,
        "追加": y,
        "配件可组数": [
            {"配件": n, "现有量": _cell(rows.get(n), col), "用量": per, "可组": caps[n]}
            for n, col, per in _DIM2
        ],
        "瓶颈": bottleneck,
        "说明": ("" if triggered else
                 "活动齿块与自由钳外管未同时剩余，第二维度不触发"),
    }


def _calc_capacity_core(rows: Dict[str, Any]) -> Dict[str, Any]:
    """纯计算逻辑：输入 rows（配件名 -> {cells:{列号:值}}），输出两维产能结果。

    不读文件、不依赖 gap_stat，可单元测试。真值锚点测试直接喂真实台账快照值。
    """
    dim1 = _calc_dim1(rows)
    x = dim1["可产"]
    qty = {it["配件"]: it["现有量"] for it in dim1["明细"]}
    remain_chikuai = qty["活动齿块"] - x
    remain_waiguan = qty["自由钳外管"] - x

    dim2 = _calc_dim2(rows, remain_chikuai, remain_waiguan)
    y = dim2["追加"]

    bottleneck = list(dim1["瓶颈"])
    if y > 0 and dim2["瓶颈"]:
        for n in dim2["瓶颈"]:
            if n not in bottleneck:
                bottleneck.append(n)

    return {
        "总可产把数": x + y,
        "第一维度可产": x,
        "第二维度追加": y,
        "瓶颈件": bottleneck,
        "第一维度": dim1["明细"],
        "第二维度": dim2,
    }


def _calc_capacity_jiali_core(rows: Dict[str, Any]) -> Dict[str, Any]:
    """加力钳三维产能（纯计算）：组合件递减（三合一→二合一→裸件），补件顺序消耗。

    rows: 配件名 -> {cells:{列号:值}}（已按块内 B 列规格过滤，如 spec=95 的行）。
    真值锚点：95D = 945 + 231 + 0 = 1176（瓶颈=三合一/内管镀锌/钳体）。
    """
    total = 0
    bottleneck: List[str] = []
    dim_results: List[Dict[str, Any]] = []
    remaining: Dict[str, int] = {}  # 第一/二维补件顺序消耗池
    consumed: Dict[str, int] = {}   # 前两维对每个补件的累计消耗（第三维扣减用）
    for idx, dim in enumerate(_JIALI_DIMS):
        asm_name = None
        asm_qty = None
        if dim["组合件"]:
            asm_name = dim["组合件"][0]
            asm_qty = _sum_cells(rows.get(asm_name), dim["组合件"][1])
        parts = []
        for name, cols, per, pos in dim["补件"]:
            base = _sum_cells(rows.get(name), cols)
            if idx == 2:
                # 第三维「裸件凑装」：取本维列，并扣减前两维累计消耗（顺序消耗）
                avail = max(0, base - consumed.get(name, 0))
            else:
                if name not in remaining:
                    remaining[name] = base
                avail = remaining[name]
            parts.append({"配件": name, "取数": pos, "现有量": avail, "用量": per})
        vals = ([asm_qty] if asm_qty is not None else []) + [p["现有量"] for p in parts]
        x = min(vals)
        bn: List[str] = []
        if asm_name and asm_qty == x:
            bn.append(asm_name)
        bn += [p["配件"] for p in parts if p["现有量"] == x]
        # 消耗（仅第一/二维更新剩余池）
        if idx != 2:
            for name, cols, per, pos in dim["补件"]:
                remaining[name] -= x * per
                consumed[name] = consumed.get(name, 0) + x * per
        total += x
        for n in bn:
            if n not in bottleneck:
                bottleneck.append(n)
        dim_results.append({
            "维度": dim["名称"],
            "可产": x,
            "组合件": ({"名称": asm_name, "现有量": asm_qty} if asm_name else None),
            "补件": parts,
            "瓶颈": bn,
        })
    return {
        "总可产把数": total,
        "第一维度可产": dim_results[0]["可产"],
        "第二维度可产": dim_results[1]["可产"],
        "第三维度可产": dim_results[2]["可产"],
        "瓶颈件": bottleneck,
        "维度明细": dim_results,
    }


def _normalize_category(cat: str) -> str:
    """品类别名归一化（「加力钳」→「加力」）。"""
    c = str(cat).strip()
    return _CAT_ALIAS.get(c, c)


def _normalize_jiali_spec(spec_kw: str):
    """加力钳 spec 归一化：'95'/'95D'/'24'/'24"' → '95'/'24'（取第一个数字作规格标识）。"""
    nums = re.findall(r"\d+", str(spec_kw))
    if not nums:
        return None
    return nums[0]


def _find_jiali_block(data: Dict[str, Any], digits: str):
    """加力钳：找 block_label 里包含 digits 的块（'18'→'80D/18"'，'95'→'95D/24"'，'108'→'108D'）。"""
    for b in data["products"]["加力"]["blocks"]:
        label_nums = re.findall(r"\d+", str(b["block_label"]))
        if digits in label_nums:
            return b
    return None


def _build_jiali_rows(data: Dict[str, Any], digits: str) -> Optional[Dict[str, Any]]:
    """构造某加力规格的完整取数 rows（供 `_calc_capacity_jiali_core` 使用）。

    取数规则（2026-11-20 文鹏口述锁定）：
    - 钳体：取本规格行（英制名「加力钳体（英寸）」，统一映射到 key「加力钳体」）。
    - 组合件（二合一/三合一）：取本规格行。
    - 7 共享件：借用件跨块取被借规格所在块的真实行（borrow 映射）；其余同块回退 share 行
      （英制回退同块公制；借用规格的非借用件取本块行）。
    """
    cfg = _JIALI_SPECS[digits]
    block = _find_jiali_block(data, digits)
    if block is None:
        return None

    def _rows_of(block_obj: Dict[str, Any], spec_digits: str) -> Dict[str, Any]:
        return {r["name"]: r for r in block_obj["rows"] if str(r["spec"]).strip() == spec_digits}

    self_rows = _rows_of(block, digits)
    borrow = cfg.get("borrow", {})
    result: Dict[str, Any] = {}
    # 钳体（英制名映射回统一 key）
    body_name = cfg["body"]
    if body_name in self_rows:
        result["加力钳体"] = self_rows[body_name]
    # 组合件（各规格自有行）
    for asm in ("加力钳体+外管", "加力钳体+外管+小钳口"):
        if asm in self_rows:
            result[asm] = self_rows[asm]
    # 7 共享件：借用件跨块、其余同块回退 share
    for part in _SHARED_PARTS:
        if part in borrow:
            src_block = _find_jiali_block(data, borrow[part])
            if src_block is None:
                continue
            src_rows = _rows_of(src_block, borrow[part])
            if part in src_rows:
                result[part] = src_rows[part]
        else:
            share_rows = _rows_of(block, cfg["share"])
            if part in share_rows:
                result[part] = share_rows[part]
    return result


def calc_capacity(spec: str = "71-75", category: str = "钻杆钳") -> Dict[str, Any]:
    """计算某规格的现有资源可产数量（组合件递减多维 min 口径）。

    Args:
        spec: 规格标签。钻杆钳如「71-75」「54-56」；加力如「95」「95D」。
        category: 品类，默认「钻杆钳」（支持「加力钳」「加力」别名）。

    返回方向自明的结构：总可产把数 + 各维度 + 瓶颈件。
    """
    category = _normalize_category(category)
    if category not in SUPPORTED_SPECS:
        supported = "、".join(f"{c}（{'/'.join(s)}）" for c, s in SUPPORTED_SPECS.items())
        return {
            "品类": category,
            "说明": f"当前产能口径仅支持 {supported}；「{category}」待阶段2 扩展",
        }

    data = gap_stat.extract_gap_stat(gap_stat.resolve_result_file())

    # 加力钳：规格归一化 + 取数映射构造
    if category == "加力":
        digits = _normalize_jiali_spec(spec)
        if digits is None:
            return {"品类": "加力", "规格": spec, "说明": "未识别规格数字"}
        if digits not in _JIALI_SPECS:
            return {
                "品类": "加力", "规格": spec,
                "说明": f"未识别加力规格「{spec}」；可选规格数字：{'、'.join(_JIALI_SPECS)}",
            }
        rows = _build_jiali_rows(data, digits)
        if rows is None:
            return {
                "品类": "加力", "规格": spec,
                "说明": f"未找到规格「{spec}」",
                "可选规格": [b["block_label"] for b in data["products"]["加力"]["blocks"]],
            }
        result = _calc_capacity_jiali_core(rows)
        result["品类"] = "加力"
        result["规格"] = _JIALI_SPECS[digits]["label"]
        return result

    # 钻杆钳：块精确匹配
    block = _find_block(data, category, spec)
    if block is None:
        products = data["products"][category]["blocks"]
        return {
            "品类": category,
            "说明": f"未找到规格「{spec}」",
            "可选规格": [b["block_label"] for b in products],
        }

    if spec not in SUPPORTED_SPECS[category]:
        kind = _classify_block(block)
        if kind == "borrow-spec":
            return {
                "品类": category, "规格": spec,
                "说明": "该规格成品计划为 0（借用规格，不单独排产），不计产能",
            }
        if kind == "borrow-item":
            return {
                "品类": category, "规格": spec,
                "说明": "该规格存在借用配件（见XX），与基准规格共享库存，待阶段2 竞争口径支持",
            }
        return {
            "品类": category, "规格": spec,
            "说明": f"规格「{spec}」不在阶段1 支持范围，待阶段2 扩展",
        }

    rows = {r["name"]: r for r in block["rows"]}
    result = _calc_capacity_core(rows)
    result["品类"] = category
    result["规格"] = spec
    return result


def calc_capacity_all(category: str = "钻杆钳") -> List[Dict[str, Any]]:
    """计算某品类「阶段1 支持规格」的可产数量，返回列表。

    只读一次文件（gap_stat.extract_gap_stat 含 formula_eval，较慢），
    各规格循环纯计算，避免重复读文件导致耗时随规格数线性放大。
    只算 SUPPORTED_SPECS 白名单内的独立规格，借件/借用规格跳过。
    """
    category = _normalize_category(category)
    if category not in SUPPORTED_SPECS:
        return []
    data = gap_stat.extract_gap_stat(gap_stat.resolve_result_file())
    if category not in data["products"]:
        return []
    results = []
    if category == "加力":
        for digits in _JIALI_SPECS:
            rows = _build_jiali_rows(data, digits)
            if rows is None:
                continue
            result = _calc_capacity_jiali_core(rows)
            result["品类"] = category
            result["规格"] = _JIALI_SPECS[digits]["label"]
            results.append(result)
        return results
    for b in data["products"][category]["blocks"]:
        if b["block_label"] not in SUPPORTED_SPECS[category]:
            continue
        rows = {r["name"]: r for r in b["rows"]}
        result = _calc_capacity_core(rows)
        result["品类"] = category
        result["规格"] = b["block_label"]
        results.append(result)
    return results
