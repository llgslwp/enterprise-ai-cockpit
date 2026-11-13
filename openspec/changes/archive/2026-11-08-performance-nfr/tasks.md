# Tasks

## 1. 行为契约补性能约束

- [x] 1.1 在 `system-platform` 新增「响应时间性能约束」requirement（分层：交互反馈≤200ms、常规查询≤200ms、批量计算/文件生成/LLM 问答豁免+进度反馈），验证：spec delta 含该 requirement 及 scenario
- [x] 1.2 写 proposal / design / tasks，验证：结构完整、spec delta 与 openspec 规范一致

## 2. 需求原文与方法论同步

- [x] 2.1 `项目需求说明书.md` 新增「非功能需求（性能约束）」章节，验证：需求原文含性能分层约束
- [x] 2.2 `docs/sdd-kit/docs/开发协作铁律.md` 新增「性能必问 + 交付前性能回归」铁律，验证：铁律清单含第 7 条
- [x] 2.3 `.workbuddy/memory/MEMORY.md` 开发协作铁律新增第 10 条 + OpenSpec 触发规则补「今后 propose 新能力必须声明性能约束符合情况」，验证：记忆文件含对应条目

## Workflow follow-up

- 本变更只立性能约束，不优化任何模块（生产管理约 2s 未达标为已知差距）。
- 归档前须业务方确认接受该性能约束（对齐「归档前业务方验收」铁律第 9 条）。
