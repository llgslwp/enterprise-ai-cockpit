---
name: openspec
description: 规范驱动开发（Spec-Driven Development）工作流。当用户要求创建变更提案（proposal）、按规范实施任务、归档变更、同步规范，或提到 OpenSpec / opsx / 规范驱动时使用。触发词：openspec 提案、变更提案、spec 提案、按规范实施、归档变更。
---

# OpenSpec 工作流（用户级路由 skill）

OpenSpec CLI 已全局安装（`openspec`）。本 skill 是**路由层**：OpenSpec 的工作流指令由项目内 `openspec init` 生成的文件提供，本 skill 负责定位并加载它们。不要凭记忆复述工作流细节——始终读取项目内最新指令，OpenSpec 升级后指令会更新而本 skill 无需改动。

## 第一步：定位项目根与指令文件

在当前项目目录依次检查：

1. 运行 `openspec list --json`（工作目录 = 项目根），读返回的 `root` 字段：
   - 有 `root` → 项目已初始化，记下 `root.path`。
   - `"root": null` 或命令报错 → 项目未初始化。若用户明确点名 OpenSpec/本 skill，询问是否执行 `openspec init . --tools agents --language zh`（**不要**未经确认自动 init）；若用户没点名 OpenSpec，直接按普通方式处理请求，不提 OpenSpec。
2. 已初始化的项目，读取 `.agents/skills/` 下的对应指令文件（每次都重读，不用缓存）：

| 用户意图                   | 读取的指令文件                                           |
| ---------------------- | ------------------------------------------------- |
| 想要新功能 / 提案 / "propose" | `.agents/skills/openspec-propose/SKILL.md`        |
| 按 tasks 实施             | `.agents/skills/openspec-apply-change/SKILL.md`   |
| 修改进行中的提案               | `.agents/skills/openspec-update-change/SKILL.md`  |
| 完成后归档                  | `.agents/skills/openspec-archive-change/SKILL.md` |
| 探索问题域 / 方案调研           | `.agents/skills/openspec-explore/SKILL.md`        |
| 把变更同步回主规范              | `.agents/skills/openspec-sync-specs/SKILL.md`     |

3. 若 `.agents/skills/` 不存在（如 init 时选了其他工具适配器），改用 CLI 获取指令：`openspec instructions propose`（或对应 artifact 名）。

## 第二步：按指令文件执行

严格遵循读到的指令文件，特别注意其中两条边界（来自 OpenSpec 官方工作流）：

- **规划边界**：propose 工作流只产出规划工件（proposal.md / specs/ / design.md / tasks.md），**不写项目代码**。工件完成后停下，等用户明确发起实施。
- **项目检查**：任何写操作（`openspec new change`、archive、sync）之前，先确认 root 存在；`"root": null` 时不得让命令隐式创建 openspec/ 目录。

## 常用命令速查

```bash
openspec list --json              # 列出进行中变更（含 root 检查）
openspec list --specs --json      # 列出主规范
openspec show <name> --json       # 查看变更/规范全文
openspec validate <name>          # 校验格式
openspec status --change <name>   # 工件完成度
openspec archive <name>           # 归档已完成变更
openspec context --json           # 输出当前规范上下文
```

## 约定

- 工件语言：跟随项目 init 时的 `--language` 设置（本机默认建议 zh）。
- 变更名用 kebab-case（如 `add-profile-filters`）。
- 用户偏好：提案先给结论和结构摘要供审阅，审阅通过再 apply——与 OpenSpec 的规划边界天然一致，不要跳过审阅直接实施。

## 开发协作铁律（每次按本 skill 实施前，先加载并遵守）

> 完整铁律见本套件的 `docs/开发协作铁律.md`。执行任何 propose / apply / 决策动作前，必须先读取该文件并遵守其全部条款；它与 OpenSpec 官方流程是「内容方法论 / 流程边界」的分层关系，二者叠加执行，不冲突。
