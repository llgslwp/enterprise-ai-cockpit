"""mapping 规则纯函数单元测试。

真值锚点：
- 颜色/变体：真实台账 sheet 名（data/raw/2026年成品入出库_新台账v8.1.xlsx，177 sheet）
- 借用规则：docs/产品工艺/产品工艺总汇_永久记忆.md 第九章「通用配件表」权威基准
- 长城反查：历史事故锚点（explicit=True 绝不允许被覆盖）
"""

from modules.production.mapping import (
    parse_color_from_sheet_name,
    parse_variant_from_sheet_name,
    apply_great_wall_reverse,
    borrow_rules_for,
    borrow_target,
)


# ---------- 颜色解析（真实 sheet 名） ----------

def test_color_real_sheets_explicit():
    assert parse_color_from_sheet_name("加力钳-Z108S-胜利红") == ("红色", True)
    assert parse_color_from_sheet_name("加力钳-Z108S-艺杰红") == ("红色", True)
    assert parse_color_from_sheet_name("加力钳-Z132S-吉林红") == ("红色", True)
    assert parse_color_from_sheet_name("加力钳-Z18-世达") == ("绿色", True)
    assert parse_color_from_sheet_name("加力钳-Z108S-绿") == ("绿色", True)
    assert parse_color_from_sheet_name("加力钳-Z195S-红") == ("红色", True)
    assert parse_color_from_sheet_name("内管钳-内管钳S43-黄护手") == ("黄色", True)
    assert parse_color_from_sheet_name("钻杆钳-φ114-117-加长黄") == ("黄色", True)


def test_color_default_no_suffix():
    assert parse_color_from_sheet_name("加力钳-Q95S-通用") == ("绿色", False)


# ---------- 变体判定（长后缀优先关键反例） ----------

def test_variant_long_suffix_priority():
    # -加长红 必须先于 -红 命中，否则「加长款」被误判为普通款
    assert parse_variant_from_sheet_name("钻杆钳-φ114-117-加长红") == "加长"
    assert parse_variant_from_sheet_name("钻杆钳-φ114-117-加长绿") == "加长"
    assert parse_variant_from_sheet_name("钻杆钳-φ71-75-加长黄") == "加长"


def test_variant_regular():
    assert parse_variant_from_sheet_name("加力钳-Z108S-胜利红") == ""
    assert parse_variant_from_sheet_name("加力钳-Z195S-红") == ""


# ---------- 长城反查（历史事故锚点） ----------

def test_great_wall_explicit_not_overridden():
    # explicit=True 绝不允许被长城反查覆盖（历史事故）
    assert apply_great_wall_reverse("红色", True, "长城") == "红色"
    assert apply_great_wall_reverse("绿色", True, "长城") == "绿色"


def test_great_wall_reverse_applies():
    assert apply_great_wall_reverse("绿色", False, "长城") == "蓝色"
    assert apply_great_wall_reverse("绿色", False, "长城客户A") == "蓝色"
    assert apply_great_wall_reverse("绿色", False, None) == "绿色"
    assert apply_great_wall_reverse("绿色", False, "其他客户") == "绿色"


# ---------- 借用规则（配件级优先 vs 整组） ----------

def test_borrow_target_part_level_priority():
    # 钻杆钳 56-58：配件级「固定齿块」→58-62；整组→54-56。配件级优先
    assert borrow_target("钻杆钳", "固定齿块", "56-58") == "58-62"
    assert borrow_target("钻杆钳", None, "56-58") == "54-56"


def test_borrow_target_real_rules():
    assert borrow_target("加力钳", "小钳口", "108") == "95"
    assert borrow_target("加力钳", "小钳口", "152") == "132"
    assert borrow_target("加力钳", "固定帽", "152") == "132"
    assert borrow_target("加力钳", "把手", "152") == "132"
    assert borrow_target("钻杆钳", "销子", "101-103") == "71-75"
    assert borrow_target("套管钳", None, "89/108") == "73/89"
    assert borrow_target("内管钳", None, "47") == "43"
    assert borrow_target("内管钳", None, "78") == "73"


def test_borrow_target_no_rule():
    assert borrow_target("加力钳", "小钳口", "999") is None


# ---------- 借用规则过滤 ----------

def test_borrow_rules_for_filter():
    assert len(borrow_rules_for("加力钳")) == 4
    assert len(borrow_rules_for("加力钳", part="小钳口")) == 2
    assert len(borrow_rules_for("钻杆钳", part="销子")) == 2
