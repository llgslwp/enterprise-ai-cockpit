# Proposal

## Why

知识库人机对话存在两个体验问题：一是对完全离题的问题（如天气、股票）仍会执行检索并返回无关引用，浪费开销且误导用户；二是前端加载占位文案写死为「首次启动需加载本地模型约 30~40 秒」，每次提问（含连续提问）都显示且信息不实，引用来源也直接铺开在答案下、占用版面。本次优化拦截离题问题、改打字机式分阶段占位、引用来源默认收起。

## What Changes

- 新增 **离题拦截**：对与知识库范围完全无关的问题，不检索、不引用，直接返回范围说明，并打 `offtopic` 标记。
- 新增 **流式阶段事件**：后端流式接口在检索前、生成前分别下发 `phase` 事件，前端据此切换分阶段占位文案。
- 修改 **引用来源展示**：引用来源默认收起为「【1】【2】…」折叠条，点击展开详情。
- 前端加载占位文案从写死句改为按阶段动态显示（正在理解问题/正在生成回答）。

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `knowledge-base`: 新增「离题问题拦截」行为，并调整「生成与引用溯源」的展示与流式进度反馈。

## Impact

- **后端**：修改 `modules/knowledge/chain.py`（stream 增加 phase 事件，answer/stream 增加离题拦截）；`modules/knowledge/router.py`（新增 `is_offtopic` 判定）。
- **前端**：修改 `web/src/views/Knowledge.vue`（分阶段占位 + 引用折叠）；`web/src/api/index.js`（解析 phase 事件）。
- **依赖**：无新增第三方依赖。
