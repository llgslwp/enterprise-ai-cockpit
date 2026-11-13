# Spec Delta

## ADDED Requirements

### Requirement: 生产完成率查询工具
系统 SHALL 提供只读工具 `query_production`，查询成品生产计划的完成率数据（计划数、完成数、完成率），分 6 品类与 4 区段，供 agent 回答「完成得怎么样」「哪些品类拖后腿」类排产进度问题。

#### Scenario: 按月份查完成率
- **WHEN** 用户询问某月完成率（如「11月完成率多少」「本月完成得怎么样」）
- **THEN** 模型 MUST 调用 `query_production`，返回该月总体 + 6品类 + 4区段的计划数/完成数/完成率

#### Scenario: 按品类查逐月趋势
- **WHEN** 用户询问某品类逐月完成率（如「各月加力钳完成率趋势」）
- **THEN** 模型 MUST 调用 `query_production`（不传 month），从返回的「各月品类完成率」概览中读取该品类各月完成率，不得用「各月完成率」（总体）冒充品类数据

#### Scenario: 完成率语义
- **WHEN** `query_production` 返回完成率
- **THEN** 完成率 MUST 等于 完成数 ÷ 计划数 × 100%；完成率 MAY 超过 100%（表示超产，非错误）；完成率越低表示进度越慢（拖后腿），模型 MUST 照此解读、不得把超 100% 判为异常

#### Scenario: 数据可对账
- **WHEN** `query_production` 返回完成率数据
- **THEN** 该数据 MUST 与 `dashboard_calc` 的计算结果逐值一致，可拿生产计划大屏对账

#### Scenario: 只读无副作用
- **WHEN** agent 调用 `query_production`
- **THEN** 该工具 MUST 仅查询、不改写生产计划文件

#### Scenario: 性能约束
- **WHEN** agent 调用 `query_production`
- **THEN** 数据提取耗时 MUST 符合全局 NFR（常规查询 ≤200ms）
