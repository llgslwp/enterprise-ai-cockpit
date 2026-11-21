# 智能辅助决策「多轮上下文」能力补建

## Why

用户实测辅助决策模块存在上下文丢失：先问「加力95库存」得到正确回答，接着问「它目前产能如何」，系统无法理解「它」、答非所问。根因是 agent 模块为「无状态单轮问答」，模型每次只见孤零零一句追问：

1. 前端 `AgentChat.vue` 发送时只传当前一句，不传历史；
2. 后端 `ChatRequest` 仅有 `question` 字段，无 history 口子；
3. `agent.ask()` 每次 `agent.invoke({messages:[当前问题]})`，模型无上文可依。

同一项目知识库模块已实现多轮改写（`rewrite_query`），仅 agent 侧漏了这一步，两模块架构不一致。

## What Changes

1. **抽公共改写函数**：`rewrite_query` 从 `modules/knowledge/router.py` 抽到 `modules/common/query_rewrite.py`，agent 与知识库两模块共用（口径统一、可单测）。
2. **后端接口加历史**：`ChatRequest` 新增 `history: list[dict] = []`（缺省空列表，向后兼容）。
3. **门控改写**：`agent.ask(question, history)` 仅在 history 非空时改写，history 为空跳过（首轮零额外延迟）。
4. **改写结果透出**：`ask()` 返回值新增 `rewritten_query` 字段，前端展示「已理解：XXX」，消除「答非所问」的信任焦虑。
5. **前端传历史**：`agentChat(question, history)` 发送最近 6 条历史。

## Impact

- 能力：`agent-core`（ADDED「多轮上下文与指代消解改写」+ MODIFIED「对话主交互形态」）
- 接口契约：`POST /api/agent/chat` 请求体新增 `history` 字段，向后兼容
- 知识库模块：`rewrite_query` 位置迁移，行为不变（纯重构，不改知识库问答语义）
- 不改写操作边界、不回写数据源、不引入写工具
