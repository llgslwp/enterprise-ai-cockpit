"""名称/规格映射规则模块。

承载生产管理两条链路（回填、排产）共用的规则：
- 颜色解析（成品台账 sheet 名后缀 → 颜色）
- 变体判定（加长款 / 普通款）
- 规格借用规则（三元映射：产品线 × 配件 × 基准规格 → 通配规格）
- 排除件清单

规则来源：
- 颜色/变体：example/ 目录既有开发文档（高可信参考）+ data/raw/ 真实文件验证。
- 规格借用：docs/产品工艺/产品工艺总汇_永久记忆.md 第九章「通用配件表」为权威基准。

所有规则在落地前须经真实数据验证性抽查；未能印证的规则单独标记待确认。
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List, NamedTuple, Optional, Tuple

# ---------------------------------------------------------------------------
# 颜色解析规则：成品台账的「颜色」编码在明细 Sheet 名称的后缀中（台账 C 列颜色
# 目前基本为空）。后缀匹配必须从末尾、按「长后缀优先」顺序逐条 endswith 判定。
# ---------------------------------------------------------------------------

# 顺序敏感：长后缀在前，避免「-加长绿」被「-绿」误吞。
COLOR_SUFFIX_RULES: list[Tuple[str, str]] = [
    ("-世达", "绿色"),
    ("-吉林红", "红色"),
    ("-胜利红", "红色"),
    ("-艺杰红", "红色"),
    ("-加长红", "红色"),
    ("-加长黄", "黄色"),
    ("-加长绿", "绿色"),
    ("-黄护手", "黄色"),
    ("-黄", "黄色"),
    ("-绿", "绿色"),
    ("-红", "红色"),
    ("-蓝", "蓝色"),
]

# 默认颜色：无明确颜色后缀时默认绿色（explicit=False）
DEFAULT_COLOR = "绿色"

# 长城客户名 → 蓝色（仅当 explicit=False 且客户字段为空时反查生效）
GREAT_WALL_KEYWORD = "长城"
GREAT_WALL_COLOR = "蓝色"


def parse_color_from_sheet_name(sheet_name: str) -> Tuple[str, bool]:
    """从 sheet 名后缀解析颜色。

    返回 (颜色, explicit)。explicit=True 表示颜色来自明确后缀，
    不允许被「长城反查」覆盖。
    """
    for suffix, color in COLOR_SUFFIX_RULES:
        if sheet_name.endswith(suffix):
            return color, True
    return DEFAULT_COLOR, False


def parse_variant_from_sheet_name(sheet_name: str) -> str:
    """判定加长款 / 普通款。

    仅当命中的颜色后缀本身以「加长」开头时才算加长款。
    返回 "加长" 或 ""。
    """
    for suffix, _ in COLOR_SUFFIX_RULES:
        if sheet_name.endswith(suffix):
            return "加长" if suffix.startswith("-加长") else ""
    return ""


def apply_great_wall_reverse(
    color: str, explicit: bool, customer: Optional[str]
) -> str:
    """长城反查：explicit=False 且客户字段为空时，若客户名子串含「长城」则改判蓝色。

    explicit=True 的颜色绝不允许被反查覆盖（历史事故）。
    """
    if explicit:
        return color
    if customer and GREAT_WALL_KEYWORD in customer:
        return GREAT_WALL_COLOR
    return color


# ---------------------------------------------------------------------------
# 规格借用规则（权威基准）
#
# 来源：docs/产品工艺/产品工艺总汇_永久记忆.md 第九章「通用配件表」。
# 借用是三元关系（产品线 × 配件 × 基准规格 → 通配规格），不是纯数字双向/单向对。
#
# 语义：「借用」某规格的某配件时，该配件的需求并入「基准规格」，
# 本规格不单独排产（对应 V2.0 的「见XX」标注）。
# 即：通配规格不排产，需求累加到基准规格。
#
# 每条记录：
#   line    产品线（加力钳 / 钻杆钳 / 内管钳 / 套管钳）
#   part    配件名（None 表示该行未细分配件、作用于整组）
#   base    基准规格（需求并入这里）
#   generic 通配规格（本规格不单独排产，改用 base）
# ---------------------------------------------------------------------------

class BorrowRule(NamedTuple):
    line: str
    part: Optional[str]   # None = 整组通配，不区分配件
    base: str             # 基准规格
    generic: str          # 通配规格（不单独排产）

    @property
    def key(self) -> Tuple[str, str, str]:
        return (self.line, self.part or "", self.generic)


# 权威表逐条录入（顺序与源文件第九章一致，便于溯源比对）。
# 注：同一条「基准规格→多个通配规格」拆成多条；整组通配 part=None。
BORROW_RULES: List[BorrowRule] = [
    # 9.1 加力钳
    BorrowRule("加力钳", "固定帽", "132", "152"),
    BorrowRule("加力钳", "小钳口", "95", "108"),
    BorrowRule("加力钳", "小钳口", "132", "152"),
    BorrowRule("加力钳", "把手", "132", "152"),

    # 9.2 钻杆钳（同一规格组内多配件同时借用）
    BorrowRule("钻杆钳", None, "54-56", "56-58"),
    BorrowRule("钻杆钳", None, "54-56", "58-62"),
    BorrowRule("钻杆钳", "固定齿块", "58-62", "56-58"),
    BorrowRule("钻杆钳", None, "71-75", "70-73"),
    BorrowRule("钻杆钳", None, "71-75", "76-79"),
    BorrowRule("钻杆钳", None, "71-75", "79-83"),
    BorrowRule("钻杆钳", None, "71-75", "86-91"),
    BorrowRule("钻杆钳", None, "71-75", "88-93"),
    BorrowRule("钻杆钳", None, "71-75", "89-95"),
    BorrowRule("钻杆钳", "销子", "71-75", "101-103"),
    BorrowRule("钻杆钳", "销子", "71-75", "114-117"),
    BorrowRule("钻杆钳", "活动齿块", "71-75", "101-103"),
    BorrowRule("钻杆钳", "活动齿块", "71-75", "114-117"),
    BorrowRule("钻杆钳", "方块座", "71-75", "127-132"),
    BorrowRule("钻杆钳", "方块座", "71-75", "139-146"),
    BorrowRule("钻杆钳", "活动钳体", "89-95", "86-91"),
    BorrowRule("钻杆钳", "活动钳体", "89-95", "88-93"),
    BorrowRule("钻杆钳", None, "114-117", "101-103"),
    BorrowRule("钻杆钳", None, "127-132", "139-146"),

    # 9.3 套管钳（外管跨产品线借用钻杆钳）
    BorrowRule("套管钳", None, "73/89", "89/108"),
    BorrowRule("套管钳", None, "108/127", "127/146"),
    BorrowRule("套管钳", None, "146/168", "168/183"),

    # 9.4 内管钳（外管跨产品线借用钻杆钳）
    BorrowRule("内管钳", None, "43", "47"),
    BorrowRule("内管钳", None, "56", "51"),
    BorrowRule("内管钳", None, "56", "61"),
    BorrowRule("内管钳", None, "73", "78"),
    BorrowRule("内管钳", None, "73", "95"),
    BorrowRule("内管钳", None, "73", "110"),
]


def borrow_rules_for(line: str, part: Optional[str] = None,
                     spec: Optional[str] = None) -> List[BorrowRule]:
    """按产品线 / 配件 / 规格（通用三者）过滤借用规则，均可不传。

    part 语义：None 表示「不过滤配件」（返回整组 + 配件级全部），
    传入具体配件名表示「只取该配件的规则」。
    """
    out: List[BorrowRule] = []
    for r in BORROW_RULES:
        if line and r.line != line:
            continue
        if part is not None and r.part != part:
            continue
        if spec is not None and r.generic != spec:
            continue
        out.append(r)
    return out


def borrow_target(line: str, part: Optional[str], spec: str) -> Optional[str]:
    """返回某产品线某配件某通配规格对应的基准规格；无规则返回 None。

    匹配优先级：配件级规则 > 整组规则（part=None 且 r.part is None）。
    - 传了 part：先查 (line, part, spec) 精确命中；无命中再查整组规则
      (line, r.part is None, spec) 兜底。
    - part=None（调用方不区分配件）：只查整组规则 (r.part is None)，
      不把配件级规则混入，避免不同基准冲突。
    - 同一维度命中多条不同 base 视为数据异常，返回 None 由调用方记录。
    """
    def _base_of(rules: List[BorrowRule]) -> Optional[str]:
        bases = {r.base for r in rules}
        return bases.pop() if len(bases) == 1 else None

    # 整组规则：r.part 必须为 None
    group = [r for r in BORROW_RULES
             if r.line == line and r.part is None and r.generic == spec]

    if part is not None:
        exact = borrow_rules_for(line=line, part=part, spec=spec)
        if exact:
            return _base_of(exact)
        return _base_of(group)
    return _base_of(group)


# ---------------------------------------------------------------------------
# 排除件清单：不应进入排产/回填计算的特殊件。
# 待真实数据验证后补充。
# ---------------------------------------------------------------------------

EXCLUDED_ITEMS: list[str] = []
