# Proposal

## Why

本项目目标已明确定位为「证明 Agent 应用开发能力」的可上 GitHub 标杆案例。但当前系统的 agent 能力只完成了一半：

- **已完成**：数据底座（zip 直读、formula_eval、0 差异逐值验收）、云端大模型接入、知识库 RAG 单步问答（`knowledge-base` 能力）。
- **缺失**：agent 的**本体**——「多工具调用」。现有 `agent-core` 能力在 `knowledge-rag` 变更后只剩「云端大模型接入 + 知识库问答」，模型只能做「检索一次 → 生成」的单步动作，无法「动态决定调用哪些业务工具、观察结果、再决定下一步」。

这就是前面反复确认过的判断：**数据底座只是地基，agent 的本体是「模型在循环里决策 + 调工具」**。本次新增「智能辅助决策」模块，把 `agent-core` 从「单步 RAG」升级为「多工具编排」，完成从「BI 系统」到「真正意义的 agent」的关键一跃。

## What Changes

- **ADDED `agent-core` 多工具调用能力**：模型根据用户问题动态决定调用哪些只读工具查询业务数据，观察结果后决定下一步，直至给出答案（Agent Loop）。
- **ADDED `agent-core` 只读工具边界与写操作拦截**：只暴露只读查询工具，不暴露任何写操作；未来引入写操作必须走人工确认通道。
- **ADDED `agent-core` 数据真实性约束**：回答中的具体数据必须来自工具返回值，模型不得凭空编造。
- **ADDED `agent-core` 工具调用轨迹可追溯**：每次问答记录调用了哪些工具、返回了什么，可回放对账。
- **ADDED `agent-core` 性能约束符合全局 NFR**：agent 问答属 LLM 问答豁免类型（不套 200ms），但必须即时进度反馈 + 完成提示。
- **MODIFIED `agent-core` 对话主交互形态**：从「知识库问答」扩展为「智能辅助决策」（知识库问答 + 业务数据查询）。
- **新增「智能辅助决策」对话入口**：后端对话 API + 前端对话页面，让业务方实际能用起来（对齐铁律第 7 条「完成 = 用户能用起来」）。

## 技术选型（需单独提审，见 design.md）

Agent 运行时（模型选工具 → 执行 → 观察 → 再选的循环）采用 **LangChain 1.x `create_agent`**（底层为 LangGraph `CompiledStateGraph`）。详见 design.md，此处只声明：这是架构基石级决策，单列提审，不混入功能实现。

## 本次范围边界

- **本次做**：最小闭环（1 个只读 tool `query_stock`）+ 对话入口（API + 前端页）+ 护栏 + 轨迹，让业务方实际点开对话。
- **本次不做（后续变更）**：扩展到一批只读工具（缺口统计、质量合格率、排产计划、知识库检索等，具体数量待实际盘点确认）、多步复杂编排（如「80D 会不会缺料」）、golden set 评测集、流式（SSE）输出。这些能力域已明确，但作为独立后续变更，避免一次 propose 过大无法验收。

## Capabilities

### New Capabilities

<!-- 无新增能力：本次是 `agent-core` 既有能力的扩展 -->

### Modified Capabilities

- `agent-core`: 新增「多工具调用」「只读工具边界与写操作拦截」「数据真实性约束」「工具调用轨迹可追溯」「性能约束符合全局 NFR」五个 requirement（ADDED）；「对话主交互形态」requirement 由「知识库问答」扩展为「智能辅助决策」（MODIFIED）。

## Impact

- **已交付代码**：`modules/agent/tools.py`（`query_stock` 只读 tool，复用 `flow_stats.build_flow_stats` 确定性实现）、`modules/agent/agent.py`（`create_agent` 闭环 + `ask()` 入口）。已跑通最小闭环：数据 0 差异 + 模型选对工具。
- **待交付代码**：后端对话 API（遵循 `api-contract`，挂 `/api/` 前缀）、前端「智能辅助决策」页面（菜单 + 路由 + 对话 UI + loading 进度反馈）。
- **依赖既有能力**：`inventory-status`（`flow_stats` zip 直读，已 0 差异验证）、`knowledge-base`（后续「知识库问答」tool 的依赖，本次不接）。
- **技术依赖**：`langchain` 1.x、`langchain-openai`（已在 requirements.txt）。
- **不引入**：本地模型部署（延续云端 DeepSeek）、数据库（延续纯文件）。
- **性能**：agent 问答为 LLM 问答豁免类型，端到端数秒~十几秒，需即时进度反馈（前端 loading + 「正在思考」提示），完成上限后续按功能约定。
