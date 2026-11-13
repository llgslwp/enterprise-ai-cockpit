# Tasks

## 1. 技术选型确认

- [x] 1.1 拍板 agent 运行时选型（LangChain 1.x `create_agent`，AskUserQuestion 提审）
- [x] 1.2 实机验证 `create_agent` 可用、`@tool` 装饰器、`ChatOpenAI`(DeepSeek) 构造

## 2. 最小闭环（补档：已完成）

- [x] 2.1 封装第一个只读 tool：`query_stock`（读台账查库存，复用 `flow_stats.build_flow_stats`）
- [x] 2.2 用 `create_agent` 搭闭环：`build_agent()` + `ask()` 问答入口 + 系统提示词
- [x] 2.3 跑通最小闭环并验证：工具返回 vs 确定性实现 27/27 值 0 差异、模型正确选择 `query_stock(month=11)`、答案数字与工具返回逐字一致无编造

## 3. 对话入口

- [x] 3.1 后端对话 API：`POST /api/agent/chat`，遵循 `api-contract`（`/api/` 前缀 + JSON + 登录态）
- [x] 3.2 前端「智能辅助决策」页面：菜单 + 路由 + 对话 UI + 发送后立即 loading 进度反馈
- [x] 3.3 前端渲染：答案文本 + 工具调用轨迹（可展开对账）

## 4. 验收

- [x] 4.1 接口回归：对话 API 结构断言（code=0、answer 非空、tool_calls 类型正确）
- [x] 4.2 数据回归：`query_stock` 返回值 vs `flow_stats` 逐值 0 差异
- [x] 4.3 性能回归：记录端到端耗时基线，确认有即时进度反馈、无无反馈卡顿
- [x] 4.4 业务方点开「智能辅助决策」页面实际对话并确认（对齐铁律第 7 条）

## 后续变更（不在本次范围，另行 propose）

- 扩展到一批只读工具（缺口统计、质量合格率、排产计划、知识库检索等，具体数量待实际盘点确认）
- 多步复杂编排场景（「80D 会不会缺料」）
- golden set 评测集（漏调率、需人工纠正率）
- 流式（SSE）输出 + 多轮会话上下文
- 写操作工具 + 人工确认通道
