# 多轮上下文能力 — 任务清单

## 1. 抽公共改写函数
- [x] 1.1 新建 `modules/common/query_rewrite.py`，迁移 `rewrite_query`（保留「无历史原样返回」门控 + 最近 6 条 + 失败回退）
- [x] 1.2 `modules/knowledge/router.py` 改为从公共模块导入并删除本地定义
- [x] 1.3 知识库问答冒烟：改写行为不变

## 2. 后端接线
- [x] 2.1 `router.py` `ChatRequest` 加 `history: list[dict] = []`
- [x] 2.2 `agent.ask(question, history=None)`：history 非空先 `rewrite_query`，返回值加 `rewritten_query`
- [x] 2.3 改写失败 / 为空回退原问题，不中断

## 3. 前端接线
- [x] 3.1 `api/index.js` `agentChat(question, history=[])`，body 加 history
- [x] 3.2 `AgentChat.vue` 发送时取最近 6 条（role/content，去空占位）传入
- [x] 3.3 响应 `rewritten_query` 非空时，答案上方展示「已理解：XXX」

## 4. 验收
- [x] 4.1 单测：门控（空 history 不改写）、有历史改写、失败回退、历史截断
- [x] 4.2 端到端：先问「加力95库存」→ 再问「它目前产能如何」，确认调用 `query_capacity(category='加力', spec='95')` 且回答正确
- [x] 4.3 回归：知识库改写行为不变；首轮提问不额外调用大模型
- [x] 4.4 重启后端 + 页面实测确认（业务方验收）
