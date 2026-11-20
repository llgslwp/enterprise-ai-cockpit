"""钻杆钳产能（可产数量）计算：两维口径。

业务口径（2026-11-20 文鹏口述锁定）：

生产链：配件 → 组装 → 组装简易钳体 → 热处理 → 装配（+活动齿块 +自由钳外管）→ 成品

第一维度（装配约束，直接可产）：
  1 把钻杆钳 = 1 组装简易钳体(装配I) + 1 活动齿块(半成品H) + 1 自由钳外管(半成品H)
  X = min(三者现有量)

第二维度（组装追加，触发 = 活动齿块 和 自由钳外管 都还有剩余）：
  1 组装简易钳体 = 2 固定钢板(毛坯C) + 1 活动钳体(H) + 1 夹紧头(H)
                 + 2 长销子(H) + 1 短销子(H) + 2 组装齿块+方块座(H)
  可新组 = floor( min(各配件现有量 ÷ 用量) )
  Y = min(可新组, 剩余活动齿块, 剩余自由钳外管)

总可产 = X + Y

特殊规则：
- 组装齿块+方块座 是必须的组合件（固定齿块+方块座组装而成），产能只看它自身数量，
  不单独看固定齿块、方块座够不够。
- 整除一律向下取整（不够 1 套不算）。
- 第二维度的配件在第一维度不消耗，用其完整现有量。

数据源 = V2.0 半成品计划表（gap_stat 读同一份）。
当前仅实现钻杆钳品类；其余品类待口径确认后照此模式推广。

分层：`_calc_capacity_core(rows)` 是纯计算逻辑（不碰文件、可单元测试）；
`calc_capacity` / `calc_capacity_all` 负责读文件 + 调纯函数。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import gap_stat

# 列 key（gap_stat 的 cells 用 str(列号) 作 key）
COL_C = str(gap_stat.COL_MAOPI)      # C 毛坯库
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

# 本模块支持产能计算的品类 → 阶段1 支持的独立规格白名单。
# 其余规格/品类待阶段2：借件规格需竞争分配、借用规格不排产、其他品类口径待对齐。
SUPPORTED_SPECS = {
    "钻杆钳": ("54-56", "71-75"),
}


def _cell(row: Optional[Dict[str, Any]], col_key: str) -> int:
    """取某配件的某列现有量，None/缺行 按 0 处理。"""
    if not row:
        return 0
    v = row.get("cells", {}).get(col_key)
    if v is None:
        return 0
    return int(float(v))


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


def calc_capacity(spec: str = "71-75", category: str = "钻杆钳") -> Dict[str, Any]:
    """计算某规格的现有资源可产数量（两维口径）。

    Args:
        spec: 规格块标签，如「71-75」「54-56」。
        category: 品类，默认「钻杆钳」（阶段1 仅钻杆钳 54-56/71-75 支持）。

    返回方向自明的结构：总可产把数 + 第一/第二维度 + 瓶颈件。
    """
    if category not in SUPPORTED_SPECS:
        supported = "、".join(f"{c}（{'/'.join(s)}）" for c, s in SUPPORTED_SPECS.items())
        return {
            "品类": category,
            "说明": f"当前产能口径仅支持 {supported}；「{category}」待阶段2 扩展",
        }

    data = gap_stat.extract_gap_stat(gap_stat.resolve_result_file())
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
    if category not in SUPPORTED_SPECS:
        return []
    data = gap_stat.extract_gap_stat(gap_stat.resolve_result_file())
    if category not in data["products"]:
        return []
    results = []
    for b in data["products"][category]["blocks"]:
        if b["block_label"] not in SUPPORTED_SPECS[category]:
            continue
        rows = {r["name"]: r for r in b["rows"]}
        result = _calc_capacity_core(rows)
        result["品类"] = category
        result["规格"] = b["block_label"]
        results.append(result)
    return results
