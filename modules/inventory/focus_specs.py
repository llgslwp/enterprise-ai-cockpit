"""重点关注规格清单读取（inventory-status 能力）。

读取独立的「重点关注规格」Excel（data/raw/重点关注规格.xlsx），
解析为「(类别, 规格, 特征) -> 是否重点」集合。

开口式设计要点（与库存底线表一致）：
- 清单是数据而非代码，用户随时勾选/增删，本模块每次调用都重新读取。
- 缺表或表为空 → 返回空集合（不报错），明细页自然回退为无重点规格。
- 仅「是否重点」列填了 是/✓/√/1/true 的行才视为重点关注规格；空值跳过。
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Set, Tuple

from app.data_model.excel_reader import read_excel_table

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(_PROJECT_ROOT, "data", "raw")

CONFIG_FILENAME = "重点关注规格.xlsx"
SHEET_NAME = "重点关注规格"

# 规格键：类别 + 规格 + 特征 三元组
SpecKey = Tuple[str, str, str]

# 「是否重点」列判为 True 的值（兼容多种写法）
_TRUE_VALUES = {"是", "y", "yes", "true", "1", "✓", "√", "✔", "重点", "关注", "x", "*"}


def _config_path() -> str:
    return os.path.join(DATA_DIR, CONFIG_FILENAME)


def _is_true(v) -> bool:
    """判断「是否重点」列的值是否为真。"""
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    s = str(v).strip().lower()
    return s in _TRUE_VALUES


def load_focus_specs() -> Set[SpecKey]:
    """读取重点关注规格清单，返回 {(类别,规格,特征)} 集合。

    缺表 / 表不存在 / 表为空 → 返回空 set（不抛异常）。
    """
    path = _config_path()
    if not os.path.exists(path):
        return set()

    try:
        table = read_excel_table(path, SHEET_NAME, sheet_name=SHEET_NAME, header_row=1)
    except Exception:
        return set()

    result: Set[SpecKey] = set()
    for row in table.rows:
        cat = row.get("类别")
        spec = row.get("规格")
        feat = row.get("特征")
        flag = row.get("是否重点")

        # 规格为空的行是类别分隔行（▌ 开头）或说明行，跳过
        if spec is None or str(spec).strip() == "":
            continue
        # 「是否重点」未勾选 → 跳过
        if not _is_true(flag):
            continue

        key = (str(cat).strip() if cat is not None else "",
               str(spec).strip(),
               str(feat).strip() if feat is not None else "")
        result.add(key)

    return result


def is_focus(cat: str, spec: str, feat: str) -> bool:
    """查询某「类别+规格+特征」是否为重点关注规格。"""
    key = (cat.strip(), spec.strip(), (feat or "").strip())
    return key in load_focus_specs()
