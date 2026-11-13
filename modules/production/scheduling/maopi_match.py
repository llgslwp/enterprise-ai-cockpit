"""名称→源文件规格映射（production-planning 能力，任务 3.1）。

承载「V2.0 配件名称/规格 → 源文件(货品名称, 货品规格)」的映射规则。

核心规律（经真实数据验证）：
- 源文件货品名称 ≈ V2.0 配件名称（去掉括号后缀「（镀锌）/（老款）/（中性）/（世达）/（镀彩）」等）。
- 源规格 = 产品线前缀 + 数字段（重型{spec}D / 钻杆φ{spec} / 套管φ{spec} / 内管钳S{spec} / 加力重型{spec}″）。
- 规格归一后只剩数字段（normalize_spec 去 φ/″/"/D/S 前缀），故匹配关键是
  「名称映射」 + 「数字段相等」。

规则来源：example/03-全量重跑-开发说明文档.md §5.3 / §8（权威基准），
并经 data/raw 真实文件名称清单核对修正。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .plan_file_utils import normalize_spec

# 产品线名 → 计划表块头产品名
PRODUCT_NAMES = {
    "加力": "加力管钳",
    "美式": "美式重型/含钛",
    "内管钳": "内管钳",
    "钻杆钳": "钻杆钳",
    "套管钳": "套管钳",
}

# V2.0 配件名称 → 源文件货品名称（去掉括号后缀等变体）
# 仅列出与源名称不一致的项；一致的项走「名称直配」。
NAME_MAP: Dict[str, str] = {
    # 加力内管（镀锌）→ 加力内管
    "加力内管（镀锌）": "加力内管",
    # 加力钳体（英寸）→ 加力钳体（源名无「（英寸）」后缀）
    "加力钳体（英寸）": "加力钳体",
    # 美式钳把（老款）→ 美式钳把
    "美式钳把（老款）": "美式钳把",
    # 美式钳把覆膜砂（中性/世达）→ 美式钳把-覆膜砂（源名带连字符）
    "美式钳把覆膜砂（中性）": "美式钳把-覆膜砂",
    "美式钳把覆膜砂（世达）": "美式钳把-覆膜砂（世达）",
    # 组合件：小钳口+美式钳把（老款）→ 小钳口+美式钳把
    "小钳口+美式钳把（老款）": "小钳口+美式钳把",
    "小钳口+美式钳把-覆膜砂（中性）": "小钳口+美式钳把-覆膜砂",
    "小钳口+美式钳把-覆膜砂（世达）": "小钳口+美式钳把-覆膜砂（世达）",
}


def map_part_name(part_name: str) -> str:
    """V2.0 配件名称 → 源文件货品名称。"""
    if part_name in NAME_MAP:
        return NAME_MAP[part_name]
    return part_name


# 产品线 → 源规格前缀（数字段前的固定前缀）
SPEC_PREFIX: Dict[str, str] = {
    "加力": "重型",       # 重型{spec}D
    "美式": "重型",       # 重型{spec}"（引号变体在匹配时归一）
    "内管钳": "内管钳S",  # 内管钳S{spec}
    "钻杆钳": "钻杆φ",    # 钻杆φ{spec}
    "套管钳": "套管φ",    # 套管φ{spec}
}

# 加力「英寸」规格前缀（加力钳体（英寸）→ 加力重型{spec}″）
JIALI_INCH_PREFIX = "加力重型"

# 组合件行（名称含 +，C~H 恒空、仅 I 列有值）。
# 注意：'组装齿块+方块座' 虽含 +，但它是正常配件（C~H 有数据），
# 故组合件判定用「含 + 且不在正常配件白名单」。
NON_ASSEMBLY_PLUS = {"组装齿块+方块座"}


def is_assembly_row(part_name: str) -> bool:
    """判断是否组合件行（C~H 恒空、仅 I 列有值）。"""
    return "+" in part_name and part_name not in NON_ASSEMBLY_PLUS


def map_spec_prefix(sheet: str, part_name: str, spec: str) -> Optional[str]:
    """把 V2.0 的 (sheet, 配件名, 规格) 映射为源文件货品规格文本。

    返回源规格（如 '重型108D' / '钻杆φ54-56' / '内管钳S43' / '加力重型18″'）；
    无对应（应排除）返回 None。
    """
    num = normalize_spec(spec)
    if not num:
        return None

    # 内管钳 防护把手 → {spec}内管钳（源规格 56内管钳/73内管钳，非 内管钳S{spec}）
    if sheet == "内管钳" and "防护把手" in part_name:
        return f"{num}内管钳"

    # 内管钳 自由钳外管/简易外管/连接套 且规格 73/71-73 → 钻杆φ71-73（特殊规则）
    if sheet == "内管钳" and any(
        kw in part_name for kw in ("自由钳外管", "自由钳简易外管", "自由钳连接套")
    ):
        if num in ("73", "71-73"):
            return "钻杆φ71-73"
        return f"内管钳S{num}"

    # 加力「英寸」配件（加力钳体（英寸））→ 加力重型{spec}″
    if sheet == "加力" and "英寸" in part_name:
        return f"{JIALI_INCH_PREFIX}{num}″"

    prefix = SPEC_PREFIX.get(sheet)
    if prefix is None:
        return None

    # 加力 → 重型{spec}D；美式 → 重型{spec}"（引号）；内管/钻杆/套管 无后缀
    if sheet == "加力":
        return f"{prefix}{num}D"
    if sheet == "美式":
        return f'{prefix}{num}"'
    return f"{prefix}{num}"


def resolve_source_target(sheet: str, part_name: str, plan_spec: str) -> Optional[Tuple[str, str]]:
    """一站式映射：V2.0 行 → (源货品名称, 源货品规格)。

    返回 (src_name, src_spec) 或 None（应排除/无对应）。

    组合件行（名称含 +）：C~H 恒空，但 I 列（装配）有值——
    源装配库中组合件名称与 V2.0 一致（如「加力钳体+外管+小钳口」），
    故组合件行的 I 列映射也走同一逻辑（由调用方在装配填充时处理）。
    """
    src_name = map_part_name(part_name)
    src_spec = map_spec_prefix(sheet, part_name, plan_spec)
    if src_spec is None:
        return None
    return (src_name, src_spec)


# ---------------------------------------------------------------------------
# 匹配（三连容错）
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    """匹配归一：引号变体、去 φ、去空格、去括号内空白、去尾随管道符。"""
    return (str(s)
            .rstrip(" |")
            .strip()
            .replace("″", '"')
            .replace('"', "″")
            .replace("φ", "")
            .replace("Φ", "")
            .replace(" ", "")
            .strip())


# 源文件货品名称合并规则（权威文档 §8.3：长销子1/长销子2 → 长销子）
MERGE_NAMES: Dict[str, str] = {
    "长销子1": "长销子",
    "长销子2": "长销子",
}


def _merge_name(name: str) -> str:
    """源名称合并（长销子1/长销子2 → 长销子）。"""
    return MERGE_NAMES.get(name, name)


def build_source_dict(rows, name_col: str, spec_col: str, qty_col: str) -> Dict[Tuple[str, str], float]:
    """源文件行 → {(归一名称, 归一规格): 合计数量}。"""
    agg: Dict[Tuple[str, str], float] = {}
    for row in rows:
        name = row.get(name_col)
        spec = row.get(spec_col)
        qty = row.get(qty_col)
        if name is None or spec is None or qty is None:
            continue
        try:
            q = float(qty)
        except (TypeError, ValueError):
            continue
        key = (_norm(_merge_name(str(name))), _norm(str(spec)))
        agg[key] = agg.get(key, 0.0) + q
    return agg


def find_source_qty(
    source_dict: Dict[Tuple[str, str], float],
    src_name: Optional[str],
    src_spec: Optional[str],
) -> Optional[float]:
    """在聚合字典查 (源名称, 源规格) 数量；三连容错，查不到返回 None。

    容错：① 精确 ② 引号变体 ③ 缺 φ 前缀（钻杆φ71-75 vs 钻杆71-75）。
    """
    if src_name is None or src_spec is None:
        return None
    exact = (_norm(src_name), _norm(src_spec))
    if exact in source_dict:
        return source_dict[exact]

    # ② 引号变体
    alt_spec = str(src_spec).replace("″", '"').replace('"', "″")
    alt = (_norm(src_name), _norm(alt_spec))
    if alt in source_dict:
        return source_dict[alt]

    # ③ 缺 φ 前缀
    if "φ" in str(src_spec):
        no_phi = str(src_spec).replace("φ", "").replace("Φ", "")
        alt2 = (_norm(src_name), _norm(no_phi))
        if alt2 in source_dict:
            return source_dict[alt2]

    return None


def resolve_source_target(sheet: str, part_name: str, plan_spec: str) -> Optional[Tuple[str, str]]:
    """一站式映射：V2.0 行 → (源货品名称, 源货品规格)。

    返回 (src_name, src_spec) 或 None（应排除/无对应）。
    """
    if is_assembly_row(part_name):
        # 组合件行 C~H 恒空（仅 I 列装配有值，装配走独立映射）
        return None
    src_name = map_part_name(part_name)
    src_spec = map_spec_prefix(sheet, part_name, plan_spec)
    if src_spec is None:
        return None
    return (src_name, src_spec)
