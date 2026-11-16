"""formula_eval 纯函数单元测试。

真值锚点（独立于被测实现）：
- 列号转换：Excel 列字母数学语义（A=1, J=10, AA=27）
- 引用解析：Excel 单元格引用语法（$ 绝对符、跨表 Sheet! 前缀）
- 表达式求值：算术运算优先级 + 除零容错 + 一元符号吸收脏公式（++/--）

被测函数均为纯函数，不依赖真实文件、不依赖 GPU/模型。
"""

from modules.production.formula_eval import _col_num, _parse_ref, _to_num, _tokenize, _Parser


def _eval(expr: str, resolver=None) -> float:
    if resolver is None:
        resolver = lambda _ref: 0.0
    return _Parser(_tokenize(expr), resolver).parse()


# ---------- _col_num ----------

def test_col_num_basic():
    assert _col_num("A") == 1
    assert _col_num("J") == 10
    assert _col_num("N") == 14
    assert _col_num("Z") == 26


def test_col_num_two_letters():
    assert _col_num("AA") == 27
    assert _col_num("AB") == 28


# ---------- _parse_ref ----------

def test_parse_ref_relative():
    assert _parse_ref("A1") == (None, 1, 1)
    assert _parse_ref("J5") == (None, 10, 5)


def test_parse_ref_absolute():
    assert _parse_ref("$J$5") == (None, 10, 5)
    assert _parse_ref("$A1") == (None, 1, 1)
    assert _parse_ref("A$1") == (None, 1, 1)


def test_parse_ref_cross_sheet():
    assert _parse_ref("加力!C3") == ("加力", 3, 3)
    assert _parse_ref("Sheet1!$B$2") == ("Sheet1", 2, 2)


def test_parse_ref_invalid():
    assert _parse_ref("XYZ") == (None, None, None)
    assert _parse_ref("") == (None, None, None)


# ---------- _to_num ----------

def test_to_num_none_and_bool():
    assert _to_num(None) == 0.0
    assert _to_num(True) == 1.0
    assert _to_num(False) == 0.0


def test_to_num_number():
    assert _to_num(3) == 3.0
    assert _to_num("3.5") == 3.5


def test_to_num_non_numeric():
    assert _to_num("abc") == 0.0


# ---------- 表达式求值（算术优先级） ----------

def test_expr_precedence():
    assert _eval("1+2*3") == 7.0
    assert _eval("(1+2)*3") == 9.0
    assert _eval("10/2+1") == 6.0


def test_expr_div_zero_tolerant():
    assert _eval("10/0") == 0.0


def test_expr_unary_absorb_dirty():
    # 吸收脏公式里的 ++ / --（Excel 容错行为）
    assert _eval("--3") == 3.0
    assert _eval("1++2") == 3.0
    assert _eval("-1+2") == 1.0


def test_expr_ref_resolution():
    def resolver(ref):
        return {"A1": 10.0, "B1": 5.0}.get(ref, 0.0)
    assert _eval("A1+B1", resolver) == 15.0
    assert _eval("A1*2", resolver) == 20.0
