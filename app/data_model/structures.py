"""库存数据结构约定（inventory-data-model 能力）。

定义六类库存数据的统一结构承载方式：
- 五类 ERP 导出库存：毛坯库、半成品库、外协、车间在产品、在产品装配
- 腾讯文档成品入出库新台账

设计原则（见 design.md）：
- 采用「统一结构」而非「强 Schema」：每类数据字段各不相同，
  以 (类别, 字段列表, 行数据) 的结构承载，字段按原始字段原样保留。
- 不做字段重命名、合并、归一化。
"""

from dataclasses import dataclass, field
from typing import List

# 六类数据的类别标识（与需求说明书中的五类库存 + 成品台账一致）
INVENTORY_CATEGORIES = [
    "毛坯库",
    "半成品库",
    "外协",
    "车间在产品",
    "在产品装配",
    "成品入出库台账",
]


@dataclass
class InventoryTable:
    """一类库存数据的统一结构。

    category: 类别（如「毛坯库」）
    columns:  字段列表，按 ERP 导出的原始字段原样保留
    rows:     行数据，每行是一个 dict（字段名 -> 原始值）
    source:   数据来源（文件名或来源标注）
    """

    category: str
    columns: List[str] = field(default_factory=list)
    rows: List[dict] = field(default_factory=list)
    source: str = ""
