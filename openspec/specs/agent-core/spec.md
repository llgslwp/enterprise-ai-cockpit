# agent-core Specification

## Purpose
定义 Agent 核心能力：云端大模型接入层与自然语言意图识别。这是本项目作为「制造业 × Agent」典型案例的核心展示点，自然语言操作通过调用国内云端大模型实现，不本地部署。

## Requirements

### Requirement: 云端大模型接入
系统 SHALL 通过统一接入层调用云端大模型（国内厂商）实现自然语言问答与知识库生成能力，不本地部署大模型。

#### Scenario: 调用云端大模型
- **WHEN** 系统需要理解自然语言问题或生成回答
- **THEN** 系统 MUST 通过云端大模型 API 完成，而非本地部署模型

#### Scenario: 厂商可切换
- **WHEN** 需要更换云端大模型厂商
- **THEN** 系统 SHALL 通过抽象接入层隔离厂商差异，更换厂商不改动业务逻辑

### Requirement: 对话主交互形态
系统 SHALL 以「对话」作为智能辅助决策的主交互形态，用户以自然语言提问，系统返回基于工具调用（含知识库检索）生成的回答。

#### Scenario: 核心操作经对话驱动
- **WHEN** 用户以自然语言提出业务数据或知识问题
- **THEN** 系统 SHALL 通过对话返回基于工具调用或知识库检索生成的回答

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

### Requirement: 多工具调用
系统 SHALL 支持 agent 通过工具调用循环回答业务数据问题：模型根据用户问题动态决定调用哪些只读工具，执行后观察结果，再决定下一步，直至给出答案。

#### Scenario: 模型选对工具
- **WHEN** 用户提出业务数据问题（如库存、缺口、合格率）
- **THEN** 模型 MUST 判断并调用对应的只读工具查询数据，而非凭记忆编造数字

#### Scenario: 多步编排
- **WHEN** 一个问题需要多个工具串联才能回答（如判断缺料需先查库存再查订单）
- **THEN** 模型 SHALL 根据前一步工具返回的结果，动态决定下一步调用哪个工具

### Requirement: 只读工具边界与写操作拦截
系统 SHALL 仅向 agent 暴露只读查询工具，不暴露任何写操作（写回、排产、回填）。未来若引入写操作工具，MUST 通过人工确认通道，不得由模型直接触发。

#### Scenario: 只读边界
- **WHEN** agent 需要查询业务数据
- **THEN** 它可调用的工具 MUST 仅为只读查询，无副作用、不改写任何数据

#### Scenario: 写操作拦截
- **WHEN** 未来引入写操作工具（如回填、排产）
- **THEN** 系统 MUST 要求人工确认后方可执行，模型不得直接触发

### Requirement: 数据真实性约束
agent 回答中涉及的具体业务数据（数字、数量、比率）MUST 来自工具返回值，模型 SHALL NOT 凭空编造或改动工具返回的数据。

#### Scenario: 数据可对账
- **WHEN** agent 回答包含具体业务数据
- **THEN** 该数据 MUST 与工具返回值逐值一致，可拿台账 / 缺口表对账

### Requirement: 工具调用轨迹可追溯
系统 SHALL 记录每次问答中模型调用的工具及其返回值，支持回放与对账。

#### Scenario: 轨迹记录
- **WHEN** agent 完成一次问答
- **THEN** 系统 SHALL 记录模型调用了哪些工具、各工具返回了什么，供回放对账

### Requirement: 性能约束符合全局 NFR
agent 问答属 LLM 问答豁免类型（不套 200ms 常规查询约束），但 MUST 提供即时进度反馈与完成提示。

#### Scenario: 进度反馈
- **WHEN** 用户发起一次问答
- **THEN** 系统 SHALL 立即返回可感知的进度反馈（如「正在思考」加载态），完成时给出完成提示，不得无反馈卡顿
