"""各类库存数据映射入口（inventory-data-model 能力）。

将各类库存 Excel 文件映射到对应的统一数据结构（InventoryTable）。

映射关系：
  五类 ERP 库存文件 -> 直接读取（第一行即表头）
  成品入出库台账   -> 177 个 sheet，区分「汇总看板」与「品类明细」
"""

from typing import Optional

from app.data_model.excel_reader import read_excel_table
from app.data_model.structures import INVENTORY_CATEGORIES, InventoryTable


def load_category(category: str, file_path: str, sheet_name=None) -> InventoryTable:
    """读取指定类别的库存文件为 InventoryTable。

    category:   六类之一（见 INVENTORY_CATEGORIES）
    file_path:  Excel 文件路径
    sheet_name: 可选工作表名；五类库存默认读第一个 sheet
    """
    if category not in INVENTORY_CATEGORIES:
        raise ValueError(f"未知库存类别: {category}")
    return read_excel_table(file_path, category, sheet_name=sheet_name)


def load_product_ledger(
    file_path: str,
    sheet_name: Optional[str] = None,
) -> InventoryTable:
    """读取成品入出库台账（腾讯文档导出，177 个 sheet）。

    sheet_name 为 None 时读「汇总看板」；
    指定品类名（如「加力钳-Q95S-通用」）时读对应品类明细 sheet。

    两类 sheet 表头都在第 2 行（第 1 行为标题行），故 header_row=2。
    """
    if sheet_name is None:
        sheet_name = "汇总看板"
    return read_excel_table(
        file_path,
        "成品入出库台账",
        sheet_name=sheet_name,
        header_row=2,
    )


def load_all(mapping: dict) -> dict:
    """按映射批量读取多类库存数据。

    mapping: {类别: 文件路径} 或 {类别: (文件路径, 工作表名)}
    返回 {类别: InventoryTable}
    """
    result = {}
    for category, spec in mapping.items():
        if isinstance(spec, tuple):
            file_path, sheet_name = spec
        else:
            file_path, sheet_name = spec, None
        result[category] = load_category(category, file_path, sheet_name)
    return result
