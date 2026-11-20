# Spec Delta

## ADDED Requirements

### Requirement: 产能查询工具
系统 SHALL 提供只读工具 `query_capacity`，用确定性代码计算「现有资源可产数量」，返回「可产把数 + 瓶颈件 + 两维明细」，供 agent 回答「最多能生产多少 / 可产 / 产能」类问题，替代模型自行硬凑。

#### Scenario: 按规格查可产数量
- **WHEN** 用户询问某规格的现有资源可产数量（如「以现有资源最多能生产多少把 71-75」）
- **THEN** 模型 MUST 调用 `query_capacity`，返回该规格的「总可产把数 + 瓶颈件 + 第一/第二维度逐配件明细」；可产把数 = 第一维度可产 + 第二维度追加；瓶颈件由工具返回、模型 MUST 照读，不得自行判断

#### Scenario: 两维口径
- **WHEN** `query_capacity` 计算某规格可产数量
- **THEN** 第一维度 MUST 取 min(组装简易钳体·装配I, 活动齿块·半成品H, 自由钳外管·半成品H)；第二维度 MUST 仅在活动齿块和自由钳外管都还有剩余时触发，追加 = min(floor(min(第二维度配件现有量÷用量)), 剩余齿块, 剩余外管)；整除一律向下取整

#### Scenario: 阶段 1 规格范围
- **WHEN** 用户询问借件规格（89-95、114-117，齿块/外管「见71-75」）、借用规格（成品计划=0）或其他品类的可产数量
- **THEN** 工具 MUST 返回明确提示（「借件规格，待阶段 2 支持」/「该规格不单独排产」/「当前产能口径仅支持钻杆钳 54-56、71-75」），MUST NOT 孤立算成 0 或给出误导数字

#### Scenario: 数据可对账
- **WHEN** `query_capacity` 返回可产数量
- **THEN** 该数据 MUST 与 `capacity._calc_capacity_core` 的确定性计算逐值一致，可拿 V2.0 半成品计划 C/H/I 列现有量对账（真值锚点：54-56=210、71-75=627）

#### Scenario: 只读无副作用
- **WHEN** agent 调用 `query_capacity`
- **THEN** 该工具 MUST 仅查询、不改写排产结果文件

#### Scenario: 性能约束
- **WHEN** agent 调用 `query_capacity`
- **THEN** 数据提取与计算耗时 MUST 符合全局 NFR（常规查询 ≤200ms）
