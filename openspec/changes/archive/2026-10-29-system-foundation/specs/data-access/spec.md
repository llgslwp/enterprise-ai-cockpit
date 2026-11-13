# Spec Delta

## Purpose

定义数据接入约定，固化「数据进入本项目前已经过处理、不做 ERP 对接、不做数据清洗」的边界契约。

## ADDED Requirements

### Requirement: 数据进入前已处理
系统 SHALL 假定进入本项目的数据已经过处理，MUST 不对输入数据执行 ERP 导出数据的清洗工作。

#### Scenario: 不做数据清洗
- **WHEN** 系统接收到外部传入的数据
- **THEN** 系统 MUST 直接使用该数据，不执行 ERP 导出数据的清洗处理

### Requirement: 不做 ERP 系统对接
系统 SHALL 不与 ERP 系统建立接口对接，MUST NOT 直接从 ERP 系统实时读取数据。

#### Scenario: 无 ERP 接口
- **WHEN** 系统需要业务数据
- **THEN** 系统 MUST 从已处理的数据来源获取，不通过 ERP 系统接口实时对接

### Requirement: 数据来源约定
系统 SHALL 明确数据以文件或已处理数据的形式进入，MUST 保证数据入口与清洗职责的边界清晰。

#### Scenario: 数据入口边界
- **WHEN** 需要确认数据进入本项目的入口与清洗职责
- **THEN** 清洗职责 MUST 归属数据进入前的上游环节，本项目仅负责消费已处理数据
