# Tasks

## 1. 离题拦截

- [x] 1.1 在 `modules/knowledge/router.py` 新增 `is_offtopic`，用 LLM 判断问题是否与知识库范围完全无关。验证：天气问题返回「离题」，工艺/制度问题返回「相关」。
- [x] 1.2 在 `chain.py` 的 answer/stream 中检索前插入离题拦截，命中即短路返回范围说明 + `offtopic: true`，不检索不引用。验证：curl 问天气，sources 为空、offtopic=true；问工艺，sources 正常 6 条。

## 2. 流式阶段事件

- [x] 2.1 在 `chain.py` stream 中，检索前 `yield phase=rewrite`、生成前 `yield phase=generate`。验证：curl 流式接口，事件顺序为 phase rewrite → phase generate → token...。
- [x] 2.2 前端 `api/index.js` 的 `knowledgeChatStream` 解析 phase 事件，新增 `onPhase` 回调。验证：编译产物含 onPhase 解析。

## 3. 前端体验

- [x] 3.1 `Knowledge.vue` assistant 消息加 `phase` 字段，`phaseText()` 按阶段显示「正在理解问题/正在生成回答」，去掉写死的「首次启动加载模型」文案。验证：编译产物三阶段文案齐全、旧文案消失。
- [x] 3.2 `Knowledge.vue` 引用来源改为折叠条，默认收起显示「▸ 引用来源 【1】【2】…」，点击展开。验证：编译产物含 src-toggle 组件。

## Workflow follow-up

- 归档本变更（openspec archive）。
- 业务方实际在知识库页提问，确认离题问题无引用、连续提问显示分阶段占位、引用可展开（铁律第 7 条）。
