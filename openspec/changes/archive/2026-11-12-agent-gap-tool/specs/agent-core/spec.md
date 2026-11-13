# Spec Delta

## ADDED Requirements

### Requirement: 缺口查询工具
系统 SHALL 提供只读工具 `query_gap`，查询最新排产结果的缺口数据（装配缺口、机加工缺口）与成品计划、半成品需求计划，供 agent 回答「还差多少」类排产决策问题。

#### Scenario: 按规格查缺口
- **WHEN** 用户询问某规格的缺口（如「71-75 还差多少」）
- **THEN** 模型 MUST 调用 `query_gap`，返回该规格的成品计划与各配件缺口；「装配缺口」「机加工缺口」两列以方向标注结构返回（`{"缺口": n, "富余": 0}` / `{"缺口": 0, "富余": n}`，null=无此工序），模型 MUST 照读方向、不得凭绝对值大小判方向；「半成品需求计划」返回裸数字（需求计划量，恒 ≥ 0），MUST NOT 当作缺口解读

#### Scenario: 数据可对账
- **WHEN** `query_gap` 返回缺口数据
- **THEN** 该数据 MUST 与 `gap_stat.extract_gap_stat` 逐值一致，可拿 V2.0 排产结果对账

#### Scenario: 只读无副作用
- **WHEN** agent 调用 `query_gap`
- **THEN** 该工具 MUST 仅查询、不改写排产结果文件

#### Scenario: 性能约束
- **WHEN** agent 调用 `query_gap`
- **THEN** 数据提取耗时 MUST 符合全局 NFR（常规查询 ≤200ms）
