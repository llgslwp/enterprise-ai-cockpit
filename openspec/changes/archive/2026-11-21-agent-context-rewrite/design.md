# Design

## 门控改写（性能核心）

改写不是每轮都做，而是「有历史才做」：

| 场景 | 行为 | 额外延迟 |
|---|---|---|
| history 为空（首轮 / 新话题） | 跳过改写，原样走 agent | 0 |
| history 非空（多轮追问） | 调 `rewrite_query` 改写 | 轻量调用，通常 <1s |

判定「是否依赖上文」≈「是否有历史」，比检测指代词更稳：不会漏掉「产能呢」这类省略主语的追问。

## 公共模块落点

`rewrite_query` 从 `modules/knowledge/router.py` 抽到 `modules/common/query_rewrite.py`。理由：agent 不应反向依赖 knowledge 模块，多轮改写是两模块共用的横切能力。

LLM 配置现状：`modules/knowledge/config.py` 已是事实上的全局 LLM 配置（`agent.py` 同样从中 import），公共模块沿用该 import；LLM 配置归属重构不在本次范围。

现有函数已含「无历史原样返回」门控 + 最近 6 条 + 失败回退，迁移仅改 import，行为不变。

## 改写透出（缓解延迟焦虑）

`ask()` 返回值新增 `rewritten_query` 字段：
- history 非空且改写成功 → 改写后的完整查询；
- history 为空 → 空串（前端不展示）。

前端在最终答案上方显示「已理解：XXX」，给用户「系统听懂了」的确定感，直接击穿「答非所问」的信任痛点。

## 契约变更（向后兼容）

`POST /api/agent/chat` 请求体：

```json
{
  "question": "它目前产能如何",
  "history": [
    {"role": "user", "content": "加力95库存多少"},
    {"role": "assistant", "content": "..."}
  ]
}
```

`history` 缺省为空列表，等同单轮，旧调用方不受影响。

## 延迟焦虑缓解（本次范围外）

SSE 流式输出 + 分阶段进度反馈属独立体验工程，本次不做，后续单独立项。本次以「门控改写（首轮零延迟）+ 改写透出（确定感）」覆盖焦虑主因。

## 性能约束

- 改写调用属 LLM 问答豁免类型（不套 200ms），前端已有 loading 态提供进度反馈；
- 首轮提问零额外延迟（门控跳过改写）；
- 改写输入历史截断（最近 6 条、单条限长），防 token 超限拖慢。
