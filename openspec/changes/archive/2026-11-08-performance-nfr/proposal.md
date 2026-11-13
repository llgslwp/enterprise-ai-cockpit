# Proposal

## Why

系统在开发过程中只考虑了功能实现，忽略了响应速度，导致供应链管理页面响应 15-20 秒、质量管理工具加载失败（并发写固定临时文件）。根因是：需求分析阶段从未把「性能/响应时间」作为非功能需求明确下来，`openspec/specs/` 里也没有任何性能约束的 requirement，导致 OpenSpec 的验收对照无性能可查。本次把性能分层约束补进行为契约，让性能约束今后被 OpenSpec 流程强制，而非靠 AI 自觉。

## What Changes

- 在 `system-platform` 能力中新增「响应时间性能约束」requirement：交互反馈 ≤200ms、常规查询/列表加载 ≤200ms（端到端）、批量计算/文件生成/知识库问答不套 200ms，改为「进度反馈 + 完成提示」。
- 同步在需求原文（`项目需求说明书.md`）与开发协作铁律（`docs/sdd-kit/docs/开发协作铁律.md`、`.workbuddy/memory/MEMORY.md`）中补「非功能需求（性能约束）」，明确交付前性能回归。

## Capabilities

### New Capabilities

<!-- 无新增能力 -->

### Modified Capabilities

- `system-platform`: 新增「响应时间性能约束」requirement（ADDED）。

## Impact

- **契约层**：`openspec/specs/system-platform/spec.md` 新增性能约束 requirement。
- **需求原文**：`项目需求说明书.md` 新增「非功能需求（性能约束）」章节（已写入）。
- **方法论层**：`docs/sdd-kit/docs/开发协作铁律.md` 与 `.workbuddy/memory/MEMORY.md` 新增「性能必问 + 交付前性能回归」铁律（已写入）。
- **现实差距**：生产管理页面当前约 2s，未达 200ms，需后续单独优化；本变更只立约束，不做该优化。
