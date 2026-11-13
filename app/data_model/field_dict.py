"""字段字典（inventory-data-model 能力）。

以声明式方式记录各类库存数据的字段定义与来源，保证字段可溯源。
字段名均与 ERP 导出 / 腾讯文档导出的原始字段一致，原样承接，不做重命名。

字段条目结构：
    field:  字段名（与源文件表头一致）
    desc:   字段含义说明
    source: 来源文件 / 来源系统

设计原则：字段来源与含义可溯源、可维护，不散落在代码常量里。
"""

# 字段字典：类别 -> 字段定义列表
# 基于 2026-10 真实数据文件探查结果录入。
FIELD_DICTIONARY = {
    # 毛坯库：ERP 导出，Sheet1，第一行即表头
    "毛坯库": [
        {"field": "货品名称", "desc": "毛坯货品名称", "source": "ERP 导出（261026毛坯库.xlsx）"},
        {"field": "货品规格", "desc": "毛坯规格型号", "source": "ERP 导出（261026毛坯库.xlsx）"},
        {"field": "现有存量", "desc": "当前库存数量", "source": "ERP 导出（261026毛坯库.xlsx）"},
        {"field": "批号", "desc": "生产批号", "source": "ERP 导出（261026毛坯库.xlsx）"},
    ],
    # 半成品库：ERP 导出，含库位与特征列
    "半成品库": [
        {"field": "货品名称", "desc": "半成品货品名称", "source": "ERP 导出（261027半成品库.xlsx）"},
        {"field": "货品规格", "desc": "半成品规格型号", "source": "ERP 导出（261027半成品库.xlsx）"},
        {"field": "库位名称", "desc": "库位（如「半成品」）", "source": "ERP 导出（261027半成品库.xlsx）"},
        {"field": "现有存量", "desc": "当前库存数量", "source": "ERP 导出（261027半成品库.xlsx）"},
        {"field": "特征", "desc": "颜色/表面处理等特征", "source": "ERP 导出（261027半成品库.xlsx）"},
        {"field": "批号", "desc": "生产批号", "source": "ERP 导出（261027半成品库.xlsx）"},
    ],
    # 外协：ERP 导出，用「状态」列标识外协
    "外协": [
        {"field": "货品名称", "desc": "外协货品名称", "source": "ERP 导出（261027外协.xlsx）"},
        {"field": "货品规格", "desc": "外协货品规格", "source": "ERP 导出（261027外协.xlsx）"},
        {"field": "状态", "desc": "状态（如「外协」）", "source": "ERP 导出（261027外协.xlsx）"},
        {"field": "现有存量", "desc": "当前库存数量", "source": "ERP 导出（261027外协.xlsx）"},
        {"field": "特征", "desc": "颜色/表面处理等特征", "source": "ERP 导出（261027外协.xlsx）"},
        {"field": "批号", "desc": "生产批号", "source": "ERP 导出（261027外协.xlsx）"},
    ],
    # 车间在产品：ERP 导出
    "车间在产品": [
        {"field": "货品名称", "desc": "车间在产品名称", "source": "ERP 导出（261027车间在产品.xlsx）"},
        {"field": "货品规格", "desc": "车间在产品规格", "source": "ERP 导出（261027车间在产品.xlsx）"},
        {"field": "库位名称", "desc": "库位（如「机加工」）", "source": "ERP 导出（261027车间在产品.xlsx）"},
        {"field": "现有存量", "desc": "当前库存数量", "source": "ERP 导出（261027车间在产品.xlsx）"},
        {"field": "特征", "desc": "颜色/表面处理等特征", "source": "ERP 导出（261027车间在产品.xlsx）"},
        {"field": "批号", "desc": "生产批号", "source": "ERP 导出（261027车间在产品.xlsx）"},
    ],
    # 在产品装配：ERP 导出
    "在产品装配": [
        {"field": "货品名称", "desc": "在产品装配名称", "source": "ERP 导出（261027在产品装配.xlsx）"},
        {"field": "货品规格", "desc": "在产品装配规格", "source": "ERP 导出（261027在产品装配.xlsx）"},
        {"field": "库位名称", "desc": "库位（如「装配库」）", "source": "ERP 导出（261027在产品装配.xlsx）"},
        {"field": "现有存量", "desc": "当前库存数量", "source": "ERP 导出（261027在产品装配.xlsx）"},
        {"field": "特征", "desc": "颜色/表面处理等特征", "source": "ERP 导出（261027在产品装配.xlsx）"},
        {"field": "批号", "desc": "生产批号", "source": "ERP 导出（261027在产品装配.xlsx）"},
    ],
    # 成品入出库台账：腾讯文档导出，177 个 sheet（1 汇总看板 + 176 品类明细）
    "成品入出库台账": [
        {
            "field": "汇总看板",
            "desc": "汇总看板 sheet：类别/规格/特征 + 1~12月各「入库/出库/结存」+ 全年汇总，供前端图表",
            "source": "腾讯文档导出（2026年成品入出库_新台账v8.1.xlsx）",
        },
        {
            "field": "品类明细",
            "desc": "176 个品类明细 sheet：日期/批号/颜色/客户名称·库存计划/入库数量/出库数量/结存数量/备注，供生产计算",
            "source": "腾讯文档导出（2026年成品入出库_新台账v8.1.xlsx）",
        },
    ],
}


def get_field_dict(category: str) -> list:
    """返回指定类别库存数据的字段字典条目列表。"""
    return FIELD_DICTIONARY.get(category, [])


def lookup_field(category: str, field_name: str):
    """按类别 + 字段名查询字段定义，返回字段条目或 None。"""
    for entry in get_field_dict(category):
        if entry.get("field") == field_name:
            return entry
    return None
