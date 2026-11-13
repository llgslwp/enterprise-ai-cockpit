"""规格语义归一化：用户口语规格简称 → 台账标准编码（数字指纹精确匹配）。

用户权威规则（2026-11-10 文鹏口述）：
- 加力钳：加力95 / 95加力 → Z95S；加力195 / 195加力 → Z195S；以此类推（数字 → Z{数字}S 或 Z{数字}"）
- 美重（铸铁管钳）：美重24 → Z24"-（600mm)；以此类推
- 含钛：含钛24 → Z24"-（600mm)；以此类推
- 钻杆钳：71-75 → φ71-75；只报数字范围
- 套管钳：73/89 → φ73/89；只报数字范围
- 内管钳：内管钳56 → 内管钳S56；以此类推

停产/新款规则（2026-11-10 文鹏补充）：
- Q 前缀 = 轻型，已停产，忽略（加力钳 Q95S、美重 Q08"~Q48"）
- Z小95S 已停产，忽略（加力钳）
- 美重 -01 后缀 = 新款：美重24 → 老款 Z24"-（600mm)（无 -01）；美重新款24 → 新款 Z24"-（600mm)-01

核心：数字指纹精确匹配（非子串），彻底解决「95 误伤 195」。
例：用户「95」→ 匹配 Z95S（数字 95），不匹配 Z195S（数字 195）、Q95S（Q 前缀已停产）。
"""

import re


def _nums(s):
    """提取字符串里按顺序出现的数字序列（"加力95"→[95]，"φ71-75"→[71,75]，"Z24"-（600mm)"→[24,600]）。"""
    return [int(x) for x in re.findall(r"\d+", str(s))]


def _prefix_ok(category, code):
    """按品类过滤前缀：加力/美重/含钛只认 Z 开头；内管钳认「内管钳」开头。"""
    if category == "内管钳":
        return code.startswith("内管钳")
    return code.startswith("Z")


def _is_active(code):
    """排除已停产编码：Q 前缀（轻型已停产）、含「小」（Z小95S 已停产）。"""
    if code.startswith("Q"):
        return False
    if "小" in code:
        return False
    return True


def _is_new(code):
    """美重新款判定：编码以 -01 结尾。"""
    return code.endswith("-01")


def match_specs(category, keyword, detail_items, is_new=False):
    """按品类规则，用数字指纹精确匹配规格明细。

    category: 6 品类名之一（加力钳/美重/含钛/钻杆钳/套管钳/内管钳）
    keyword: 用户口语规格关键词（如「95」「71-75」「73/89」「新款24」）
    detail_items: [{spec, feature, in, out, stock}...]
    is_new: 是否指定「新款」（仅美重有效）。False=老款（无 -01），True=新款（-01）。
    返回匹配的 items 列表（已剔除停产编码）。
    """
    # 关键词里也可能带「新款」（如「新款24」），双保险
    if "新款" in keyword:
        is_new = True
    kw = keyword.replace("新款", "").strip()
    kw_nums = _nums(kw)
    if not kw_nums:
        return []

    # 关键词类型：范围型（多数字，如「71-75」「73/89」）vs 单数字型（如「95」「24」「56」）。
    # 范围型关键词只能匹配范围型品类的完整数字序列，绝不能降级成「取首数字」去撞单数字编码
    # （否则「71-75」会误伤「内管钳S71」——两者数字序列 [71,75] ≠ [71]）。
    is_range_kw = len(kw_nums) > 1

    result = []
    for it in detail_items:
        code = str(it["spec"])
        if not _is_active(code):
            continue
        code_nums = _nums(code)
        if not code_nums:
            continue

        # 美重新款/老款过滤（默认老款）
        if category == "美重" and _is_new(code) != is_new:
            continue

        if category in ("钻杆钳", "套管钳"):
            # 范围型品类：完整数字序列精确等值（φ71-75 ↔ [71,75]），仅当关键词也是范围型
            if is_range_kw and code_nums == kw_nums:
                result.append(it)
        else:
            # 单数字型品类：主数字（第一个）精确匹配 + 前缀过滤，仅当关键词也是单数字
            if not is_range_kw and code_nums[0] == kw_nums[0] and _prefix_ok(category, code):
                result.append(it)
    return result
