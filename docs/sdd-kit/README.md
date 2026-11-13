# SDD 开发套件 · 安装说明（README）

一套可移植的「规范驱动开发（Spec-Driven Development）」插件包。复制到任意一台装有 WorkBuddy 的电脑，按下面 4 步安装，即可获得完整的 SDD 开发流程。

## 套件目录结构

```
sdd-kit/
├── README.md                    ← 本文件（安装说明）
├── docs/
│   ├── 开发协作铁律.md          ← ① 内容方法论（自建，随包分发）
│   └── 四层关系说明.md          ← 四层关系图与职责说明
└── skills/
    └── openspec/
        └── SKILL.md             ← ② 路由 skill（自建，随包分发）
```

## 安装步骤（4 步）

### 第 1 步：安装 OpenSpec CLI（第④层 · 官方）

在目标电脑的终端执行：

```bash
npm install -g @openspec/cli
```

验证安装成功：

```bash
openspec --version
# 应输出类似 1.15.0
```

> 若目标电脑无 Node.js，需先安装 Node.js ≥ 18（CLI 依赖 Node 环境）。

### 第 2 步：安装路由 skill（第②层 · 自建）

把本套件的 `skills/openspec/` 目录**整个复制**到 WorkBuddy 的用户级技能目录：

- **Windows**：`C:\Users\<用户名>\.workbuddy\skills\openspec\`
- **macOS / Linux**：`~/.workbuddy/skills/openspec/`

复制后，目录下应有 `SKILL.md` 文件。

### 第 3 步：部署开发铁律（第①层 · 自建）

把本套件 `docs/开发协作铁律.md` 的内容，写入目标电脑的 WorkBuddy 全局记忆（跨项目生效）：

- **Windows**：`C:\Users\<用户名>\.workbuddy\user-<用户ID>-personal\SOUL.md`（追加到「长期偏好」区）
- 或按 WorkBuddy 的实际记忆文件位置，把铁律段落追加进去。

> 目的：让「开发铁律」在每次对话自动加载，而不只是躺在文档里没人读。

### 第 4 步：在目标项目初始化 OpenSpec（生成第③层 · 官方）

进入要开发的项目根目录，执行：

```bash
openspec init . --tools agents --language zh
```

这一步会在项目内自动生成 `.agents/skills/openspec-*.md`（第③层官方流程指令）和 `openspec/` 目录。

## 安装完成后的验证

在目标项目里，让 WorkBuddy 执行一次「创建变更提案」：

1. 说出你的需求（如「我想加一个报表功能」）。
2. 路由 skill（第②层）会定位到 `.agents/skills/openspec-propose/SKILL.md`（第③层），并自动加载开发铁律（第①层）。
3. WorkBuddy 会按「先澄清 material ambiguity → 生成 proposal/specs/design/tasks → 审阅 → 再 apply」的完整流程走。
4. 最终由 OpenSpec CLI（第④层）落盘、校验、归档。

四层全部跑通，即安装成功。

## 常见问题

- **Q：路由 skill 复制后不生效？** 确认 `SKILL.md` 的 YAML 头（`name`/`description`）完整，且目录名必须是 `openspec`。
- **Q：init 时报「openspec 未找到」？** 第 1 步的全局安装没成功，检查 `npm` 和 `openspec --version`。
- **Q：铁律没自动加载？** 确认第 3 步写入了正确的记忆文件（全局 SOUL.md 或等价位置）。

## 一句话

**这个套件 = 你的方法（①铁律 + ②路由）+ 官方工具（③流程 + ④CLI），复制后按 4 步装好，就能在任何电脑上复现同样的 SDD 开发流程。**
