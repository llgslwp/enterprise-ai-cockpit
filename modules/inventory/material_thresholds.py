"""原料库存底线配置表读取（inventory-status 能力，原料预警）。

读取独立的「原料库存底线配置表」Excel（data/raw/原料库存底线配置表.xlsx），
解析为「(货品名称, 货品规格) -> 原料底线值」映射。

开口式设计要点（复用 thresholds.py 同款模式）：
- 配置表是数据而非代码，用户随时增删底线行，本模块每次调用都重新读取。
- 缺表或表为空 → 返回空映射（不报错），预警结果自然为空。
- 仅「安全库存」列（兼容旧名「原料底线」）有数值的行才构成有效底线条目；空值行跳过。
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

from app.data_model.excel_reader import read_excel_table

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(_PROJECT_ROOT, "data", "raw")

# 配置表文件名（固定，不带日期——它是持续维护的基准配置）
CONFIG_FILENAME = "原料库存底线配置表.xlsx"
SHEET_NAME = "原料底线"

# 底线键：货品名称 + 货品规格 二元组
MaterialKey = Tuple[str, str]


def _numeric(v) -> Optional[float]:
    """把值安全转为数值；空/非数值返回 None（视为未定义底线）。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


def _config_path() -> str:
    return os.path.join(DATA_DIR, CONFIG_FILENAME)


def load_material_thresholds() -> Dict[MaterialKey, float]:
    """读取原料库存底线配置表，返回 {(货品名称,货品规格): 原料底线值}。

    缺表 / 表不存在 / 表为空 → 返回空 dict（不抛异常）。
    """
    path = _config_path()
    if not os.path.exists(path):
        return {}

    try:
        table = read_excel_table(path, "毛坯库", sheet_name=SHEET_NAME, header_row=1)
    except Exception:
        return {}

    result: Dict[MaterialKey, float] = {}
    for row in table.rows:
        name = row.get("货品名称")
        spec = row.get("货品规格")
        # 底线列名：用户实际填写的表头为「安全库存」，兼容早期空框架的「原料底线」旧名
        threshold = row.get("安全库存")
        if threshold is None:
            threshold = row.get("原料底线")

        # 规格为空的行是类别分隔行或说明行，跳过
        if spec is None:
            continue
        # 底线未填（None/空/非数值）→ 该行不参与预警，跳过
        value = _numeric(threshold)
        if value is None:
            continue

        key = (
            str(name).strip() if name is not None else "",
            str(spec).strip(),
        )
        result[key] = value

    return result
