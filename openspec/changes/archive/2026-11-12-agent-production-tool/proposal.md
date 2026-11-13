# Proposal: 新增生产完成率查询工具 query_production

## 动机

agent 已封装 `query_stock`（库存「有多少」）与 `query_gap`（缺口「还差多少」），构成排产决策的「现状 + 缺口」两环。但还缺「**产得怎么样**」这一环——排产复盘时最常问的是「这个月完成率多少、哪些品类拖后腿」。

数据层 `dashboard_calc.py` 是已通过 0 差异验证的确定性实现（zip 直读、完成率口径业务方已确认），只需薄薄一层 `@tool` 封装即可复用，风险最低、复用价值最高。

## 变更内容

新增只读工具 `query_production`，封装 `dashboard_calc`，查询成品生产计划的完成率数据（计划数 / 完成数 / 完成率），分 6 品类与 4 区段，供 agent 回答「完成得怎么样」「哪些品类拖后腿」类排产进度问题。

## 影响范围

- 仅 `modules/agent/tools.py` 新增一个 tool 并加入 `ALL_TOOLS`；
- 复用 `dashboard_calc.resolve_plan_file` / `calc_month` / `build_dashboard`，不改数据层；
- 只读、无副作用、不改写任何文件。

## 非目标（明确不做）

- 不改 `dashboard_calc` 的计算逻辑与口径；
- 不做产能（UPH/标准工时/设备产能）——那是另一条未建的数据层，另行提案。
