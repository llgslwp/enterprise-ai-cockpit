"""gap_stat 纯函数单元测试。

真值锚点：真实 V2.0 文件（data/raw/半成品生产计划V2.0.xlsx）的块头规格字符串。
- 加力 80D/18"（公制/英寸拆分，ASCII 引号 0x22）
- 加力 108D（仅公制，无英寸）
- 美式 18"（J 成品计划 + K 含钛）
- 内管钳 S43 / 钻杆钳 71-75（仅 J 一个成品计划）
- 套管钳 73/89（有斜杠但只有 13 列，绝不拆分——关键反例）
"""

from modules.production.gap_stat import _parse_group_spec, _col_letter, _num


# ---------- 块头规格解析 ----------

def test_parse_group_spec_jiali_split():
    assert _parse_group_spec("加力", '80D/18"') == {"J": '成品计划80D', "K": '成品计划18"'}
    assert _parse_group_spec("加力", '95D/24"') == {"J": '成品计划95D', "K": '成品计划24"'}


def test_parse_group_spec_jiali_metric_only():
    assert _parse_group_spec("加力", "108D") == {"J": "成品计划108D"}


def test_parse_group_spec_meishi():
    assert _parse_group_spec("美式", '18"') == {"J": "成品计划", "K": "成品计划（含钛）"}


def test_parse_group_spec_other_13col():
    assert _parse_group_spec("内管钳", "S43") == {"J": "成品计划"}
    assert _parse_group_spec("钻杆钳", "71-75") == {"J": "成品计划"}


def test_parse_group_spec_taoguan_no_split():
    # 关键反例：套管钳 73/89 有斜杠，但只有 13 列（仅 J），绝不拆分
    assert _parse_group_spec("套管钳", "73/89") == {"J": "成品计划"}


# ---------- 列号转字母 ----------

def test_col_letter():
    assert _col_letter(1) == "A"
    assert _col_letter(10) == "J"
    assert _col_letter(14) == "N"
    assert _col_letter(26) == "Z"
    assert _col_letter(27) == "AA"


# ---------- 数值转换 ----------

def test_num():
    assert _num(None) is None
    assert _num(5) == 5.0
    assert _num("5.5") == 5.5
    assert _num("=J5*$J$2") is None  # 公式串交给求值器，不在此转换
    assert _num("abc") is None
