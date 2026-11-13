"""轻量 Excel 公式求值器（替代 formulas 库，用于 V2.0 排产结果的缺口列计算）。

背景：formulas 库 `.loads()` 解析 45KB 的 xlsx 就要 ~2.2s（纯 Python 逐字节解析 + AST 编译），
是 gap-stat 接口 2.9s 的绝对瓶颈。本模块用 zip 直读（复用 excel_reader）+ 自研递归下降
求值器，只支持本项目 V2.0 公式的有限子集，换取数量级的加速。

支持的公式子集（已对真实文件全量公式盘点确认）：
- 运算符：+ - * / ( )，以及一元 +/-（正确吸收脏公式里的 ++ / --）
- 单元格引用：A1（相对）、$A$1（绝对）、$A1 / A$1（混合）、Sheet!A1（跨表，中文 sheet 名）
- 无函数、无数组公式、无跨工作簿引用

用法：
    calc_sheet_formulas(path) -> {sheet: {(row, col): float}}   # row/col 均为 1 起

安全性：纯数值计算，除零返回 0，循环引用返回 0，不抛异常（与 Excel 打开容错行为对齐）。
"""

from __future__ import annotations

import re
import zipfile
from typing import Dict, Optional, Tuple

from app.data_model import excel_reader

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# 单元格引用（在公式文本里）：可选 sheet 前缀 + 列字母 + 行号（列/行可带 $ 绝对符）
_REF_RE = re.compile(r"^(?:(?P<sheet>[\w\u4e00-\u9fff]+)!)?(?P<col>\$?[A-Za-z]+)(?P<row>\$?\d+)$")


def _col_num(letters: str) -> int:
    """列字母 → 列号（A=1, J=10, K=11...）。"""
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def _parse_ref(ref: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """解析引用串，返回 (sheet 名或 None, 列号, 行号)；非法返回 (None, None, None)。"""
    m = _REF_RE.match(ref.strip())
    if not m:
        return None, None, None
    sheet = m.group("sheet")
    col = _col_num(m.group("col").lstrip("$"))
    row = int(m.group("row").lstrip("$"))
    return sheet, col, row


def _to_num(v) -> float:
    """值 → float；空/文本/非法返回 0（与 Excel 空单元格参与算术 = 0 对齐）。"""
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return 0.0


def _tokenize(expr: str) -> list:
    """公式字符串 → token 序列 [(类型, 值)]，类型 ∈ {op, num, ref}。"""
    tokens = []
    i = 0
    n = len(expr)
    while i < n:
        ch = expr[i]
        if ch in "+-*/()":
            tokens.append(("op", ch))
            i += 1
        elif ch.isdigit() or ch == ".":
            j = i
            while j < n and (expr[j].isdigit() or expr[j] == "."):
                j += 1
            tokens.append(("num", expr[i:j]))
            i = j
        elif ch == "$" or ch.isalpha() or "\u4e00" <= ch <= "\u9fff":
            j = i
            while j < n and (expr[j].isalnum() or expr[j] in "$!._" or "\u4e00" <= expr[j] <= "\u9fff"):
                j += 1
            tokens.append(("ref", expr[i:j]))
            i = j
        else:
            i += 1  # 跳过空格等
    return tokens


class _Parser:
    """递归下降表达式求值器（支持一元 +/-，从而正确吸收 ++ / -- 脏公式）。"""

    __slots__ = ("tokens", "pos", "resolver")

    def __init__(self, tokens, resolver):
        self.tokens = tokens
        self.pos = 0
        self.resolver = resolver

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def _next(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse(self) -> float:
        return self._expr()

    def _expr(self) -> float:
        v = self._term()
        while True:
            t, op = self._peek()
            if t == "op" and op in "+-":
                self._next()
                rhs = self._term()
                v = v + rhs if op == "+" else v - rhs
            else:
                return v

    def _term(self) -> float:
        v = self._factor()
        while True:
            t, op = self._peek()
            if t == "op" and op in "*/":
                self._next()
                rhs = self._factor()
                if op == "*":
                    v = v * rhs
                else:
                    v = v / rhs if rhs != 0 else 0.0
            else:
                return v

    def _factor(self) -> float:
        t, v = self._peek()
        if t == "op" and v == "-":
            self._next()
            return -self._factor()
        if t == "op" and v == "+":
            self._next()
            return self._factor()
        if t == "op" and v == "(":
            self._next()
            val = self._expr()
            self._next()  # 跳过 )
            return val
        if t == "num":
            self._next()
            return float(v)
        if t == "ref":
            self._next()
            return self.resolver(v)
        return 0.0


def _read_sheet_grid(zf: zipfile.ZipFile, spath: str, shared, date_xf):
    """读取一个 sheet 的 values {(row,col): 值} 与 formulas {(row,col): 公式文本}。"""
    root = excel_reader.ET.fromstring(zf.read(spath))
    values = {}
    formulas = {}
    for row in root.iter(f"{_NS}row"):
        rn = int(row.get("r", 0))
        for c in row.findall(f"{_NS}c"):
            ref = c.get("r")
            if not ref:
                continue
            _, col = excel_reader._parse_cell_ref(ref)
            if col is None:
                continue
            f = c.find(f"{_NS}f")
            if f is not None and f.text:
                formulas[(rn, col)] = f.text
            val = excel_reader._cell_value(c, shared, date_xf)
            if val is not None:
                values[(rn, col)] = val
    return values, formulas


def calc_sheet_formulas(path: str) -> Dict[str, Dict[Tuple[int, int], float]]:
    """计算 V2.0 文件所有公式单元格的值，返回 {sheet: {(row, col): float}}。

    row/col 均为 1 起。只对「有公式」的单元格产出结果，纯数值单元格不在结果里。
    """
    zf = zipfile.ZipFile(path)
    try:
        shared = excel_reader._load_shared_strings(zf)
        date_xf = excel_reader._load_date_xf_indexes(zf)
        sheets = {}
        for name, spath in excel_reader._list_sheets(zf):
            if not spath:
                continue
            values, formulas = _read_sheet_grid(zf, spath, shared, date_xf)
            sheets[name] = {"values": values, "formulas": formulas}
    finally:
        zf.close()

    memo: Dict[Tuple[str, int, int], float] = {}
    visiting: set = set()

    def _resolve_ref(ref: str, cur_sheet: str, resolve_fn) -> float:
        ref_sheet, col, row = _parse_ref(ref)
        if col is None:
            return 0.0
        return resolve_fn(ref_sheet or cur_sheet, col, row)

    def resolve(sheet: str, col: int, row: int) -> float:
        key = (sheet, col, row)
        if key in memo:
            return memo[key]
        if key in visiting:
            return 0.0  # 循环引用保护
        data = sheets.get(sheet)
        if data is None:
            return 0.0
        visiting.add(key)
        try:
            fx = data["formulas"].get((row, col))
            if fx is not None:
                parser = _Parser(_tokenize(fx), lambda ref: _resolve_ref(ref, sheet, resolve))
                val = parser.parse()
            else:
                val = _to_num(data["values"].get((row, col)))
        finally:
            visiting.discard(key)
        memo[key] = val
        return val

    result: Dict[str, Dict[Tuple[int, int], float]] = {}
    for name, data in sheets.items():
        out: Dict[Tuple[int, int], float] = {}
        for (row, col) in data["formulas"].keys():
            out[(row, col)] = resolve(name, col, row)
        result[name] = out
    return result
