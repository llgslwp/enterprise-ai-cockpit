# Design

## Context

知识库问答链路（`modules/knowledge/chain.py`）当前为「改写 → 路由 → 检索 → rerank → 生成」，流式接口只吐 `token` 与末尾 `meta` 两类事件。路由 `route_domain` 返回 None 时统一「回落全库检索」，未区分「跨域问题该检索」与「完全离题不该检索」。前端 `Knowledge.vue` 的加载占位是写死文案，引用来源直接铺开。

## Goals / Non-Goals

**Goals:**
- 离题问题短路，不浪费检索/rerank 开销，不展示无关引用。
- 前端按阶段反馈进度，引用来源默认收起。

**Non-Goals:**
- 不改变检索、rerank、生成的既有质量与排序逻辑。
- 不新增知识域或路由维度。

## Decisions

- **离题拦截位置**：在检索之前（`_prepare` 前）调用 `is_offtopic`，命中即短路。备选「检索后再过滤」无法省掉检索开销，弃用。
- **离题判定**：新增 `router.is_offtopic`，用 LLM 判断问题是否与本知识库两类内容（工艺/标准 + 公司制度）完全无关，输出「相关/离题」。与 `route_domain`（判知识域）职责分离，避免把「None=回落全库」与「离题=不检索」混为一谈。
- **阶段事件**：流式在检索前 `yield {"type":"phase","name":"rewrite"}`，生成前 `yield {"type":"phase","name":"generate"}`。前端 `onPhase` 回调据此切换占位文案，不新增接口。
- **引用折叠**：前端 `expandedSources` 响应式对象按消息索引控制展开/收起，默认收起显示「▸ 引用来源 【1】【2】…」。

## Risks / Trade-offs

- [离题判定依赖 LLM，可能把边缘问题误判为离题] → 判定提示词明确两类内容边界，且正常工艺/制度问题已实测不受影响。
- [阶段事件增加一次网络往返前的等待期，但 phase 事件本身开销可忽略] → 仅在生成前/检索前各一次，无实质延迟。
