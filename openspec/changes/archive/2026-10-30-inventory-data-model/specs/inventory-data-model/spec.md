# Spec Delta

## Purpose

定义库存数据建模能力，将 ERP 导出的五类库存数据与腾讯文档成品入出库台账按原始字段原样读入并建立统一数据结构，作为生产管理与库存管理模块的数据地基。

## ADDED Requirements

### Requirement: 五类库存数据建模
系统 SHALL 支持对五类 ERP 导出库存数据进行建模：毛坯库、半成品库、外协、车间在产品、在产品装配。

#### Scenario: 五类数据识别
- **WHEN** 系统读取库存数据文件
- **THEN** 系统 MUST 能识别毛坯库、半成品库、外协、车间在产品、在产品装配五类数据

### Requirement: 成品入出库台账建模
系统 SHALL 支持对腾讯文档成品入出库新台账进行建模。

#### Scenario: 成品台账识别
- **WHEN** 系统读取成品入出库新台账文件
- **THEN** 系统 MUST 能识别该台账数据

### Requirement: 原始字段原样承接
系统 SHALL 按 ERP 导出的原始字段原样承接数据，MUST NOT 重命名、合并字段，MUST NOT 对字段做归一化改造。

#### Scenario: 字段原样保留
- **WHEN** 系统将库存数据读入统一结构
- **THEN** 字段名与含义 MUST 与 ERP 导出的原始字段一致，不做重命名或合并

### Requirement: Excel 读取层
系统 SHALL 提供 Excel 文件的读取层，将各类库存文件读入为统一数据结构。

#### Scenario: 读取为统一结构
- **WHEN** 系统读取任一库存 Excel 文件
- **THEN** 系统 MUST 将其读入为统一的数据结构

### Requirement: 字段字典
系统 SHALL 建立字段字典，记录各类库存数据的字段定义与来源。

#### Scenario: 字段可溯源
- **WHEN** 需要查询某类库存数据的字段含义或来源
- **THEN** 系统 MUST 能从字段字典中获取字段定义与来源信息

### Requirement: 不含计算与报表
系统在数据建模层 SHALL 不实现任何计算或报表展示逻辑，MUST 仅负责数据读取与结构化。

#### Scenario: 无计算逻辑
- **WHEN** 系统处于数据建模层
- **THEN** 系统 MUST 只执行数据读取与结构化，不执行生产计划计算或库存状态展示等业务逻辑
