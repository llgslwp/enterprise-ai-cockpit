# Design

## 技术选型（提审记录）

### Agent 运行时：LangChain 1.x `create_agent`

**决策**：agent 的「循环」层（模型选工具 → 执行 → 观察 → 再选）采用 LangChain 1.x 的 `create_agent`。

**已拍板**：本决策已通过 AskUserQuestion 单独提审，用户确认采用 `create_agent`（而非已废弃的 `AgentExecutor` / `initialize_agent`）。

**技术事实（已实机验证）**：
- 本地 langchain 版本 **1.4.8**（1.x），`langchain_openai`、`langchain_core` 齐备。
- `create_agent(model=..., tools=[...], system_prompt=...)` 返回 `CompiledStateGraph`（底层就是 LangGraph），`invoke({"messages":[...]})` 调用，内建「调工具直到满足停止条件」的循环——正是我们要的 Agent Loop，无需自写 while。
- `model` 直接传 `ChatOpenAI(model='deepseek-chat', api_key=..., base_url='https://api.deepseek.com')` 即通。
- `@tool` 装饰器：函数 docstring 自动转 tool description，参数注解自动转 JSON Schema，实机验证通过。

**为什么不用其它选项**：
- `AgentExecutor` / `initialize_agent`：langchain 1.x 已废弃，不用。
- 自写 while 循环：透明但重复造轮子，流式 / 护栏 / 多步都要手搓，MVP 阶段得不偿失。
- `LangGraph` 裸用：能力最强但样板多，MVP 阶段拖慢节奏。`create_agent` 本就是 LangChain 1.x 在 LangGraph 之上的高层封装，后续要复杂分支可平滑下沉到裸 LangGraph，不浪费。

### LLM：DeepSeek（延续既有选型）

沿用 `modules/knowledge/config.py` 的 `LLM_MODEL=deepseek-chat`、`LLM_BASE_URL=https://api.deepseek.com`、`LLM_API_KEY`（存 `.env`）。不本地部署模型。

## 工具封装标准（把现有业务函数收敛为 tool 的判据）

> 注：全项目业务函数的实际数量尚未盘点，本节四条是「收敛判据」（方法），不是对某个确定函数量的收敛。「50 个函数」只是前期交流中的概数，不作为标准数据。

一个 tool = 「模型可能需要临时决策调用」的、有明确输入输出的、可独立验证的一次业务动作。四条硬标准（全满足才封装）：

1. 模型要「动态决定」调不调（不是固定流程内必跑的那步）；
2. 有干净输入 → 输出，能写成 JSON Schema；
3. 结果可验证 / 可溯源（只读、返回数据，不是黑箱结论）；
4. 粒度 = 一次「业务动作」（用户能用一句话说清「帮我查 X」）。

**不封装**：固定流水线内部步骤（`run_pipeline` 内部先读后算）、内部实现细节（zip 直读、日期解码、`formula_eval`）、太碎的单元（读某 sheet 某单元格）、不可逆写操作。

**docstring 写「使用时机」而非「功能定义」**——这是模型选对工具的头号关键。当前 `query_stock` 的 docstring 已按此写「当用户问『库存还剩多少』『库里还有多少』时调用」。

## 可靠性设计（确定性包裹不确定性）

对应四道防线，本次落地其中三道：

| 层 | 保证什么 | 本次落地 |
|---|---|---|
| ① 数据层 | 不靠模型算数 | tool 只调 `flow_stats.build_flow_stats` 确定性实现，0 差异验证过 |
| ② 动作层 | 不靠模型守规矩 | 当前仅只读工具，无写操作；未来写操作走人工确认 |
| ③ 留痕层 | 不靠模型记忆 | `ask()` 返回 `tool_calls` 轨迹（name + content），可回放对账 |
| ④ 验收层 | 不靠模型自证 | golden set 评测集（后续变更）；当前用「工具返回 vs 确定性实现逐值 0 差异」回归 |

## 系统提示词（已实现）

`modules/agent/agent.py` 的 `_SYSTEM_PROMPT` 四规则：① 涉及具体数据必须先调工具、严禁编造；② 工具返回数字如实转述、不得改动夸大；③ 无工具可答则明说「我目前没有查询该数据的工具」；④ 简洁结构化中文回答。

## API 设计（MVP 同步接口）

- **路径**：`POST /api/agent/chat`（遵循 `api-contract` 的 `/api/` 前缀 + JSON 响应）。
- **请求**：`{"question": "..."}`。
- **响应**：`{"code": 0, "message": "ok", "data": {"answer": "...", "tool_calls": [{name, content}]}}`。
- **鉴权**：登录态保护（延续 `admin-auth`）。
- **性能**：同步返回，端到端数秒~十几秒（LLM 问答豁免 200ms）。前端发请求后立即进入 loading 态（「正在思考」），完成时渲染答案，满足「即时进度反馈 + 完成提示」。
- **后续**：流式（SSE）输出、多轮会话上下文，作为后续变更（对应 knowledge-base 已有的「分阶段进度反馈」经验）。

## 数据流

```
用户提问（自然语言）
  → POST /api/agent/chat
  → agent.build_agent() + invoke({"messages":[...]})
  → create_agent 循环：模型判断 → 调 query_stock(month) → 观察 JSON 结果 → 再判断 → 输出答案
  → 返回 {answer, tool_calls}
```

数据由 `flow_stats`（zip 直读）精确计算，模型只转述，逐值可对账。
