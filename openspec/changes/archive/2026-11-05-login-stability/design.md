# Design

## Context

登录功能在 2026-11-04 至 11-05 反复报「登录失败」，经三层排查坐实三个独立根因，分别位于 cookie 域、后端进程形态、前端错误字段。此前修复已落地并验证（curl 实测 cookie 不互通、netstat 观察多进程抢端口、字段修正后真实报错可见），但未按 OpenSpec 立项归档。本次补档，把三项根因固化为规格约束。

## Goals / Non-Goals

**Goals:**
- 固化「全链路 127.0.0.1」访问契约，避免换电脑/换账号后重犯 localhost 坑。
- 固化「后端单进程」运行约束，消除 reload=True 双进程不稳定。
- 固化「前端读 message 字段」错误契约，保证登录失败提示真实可诊断。

**Non-Goals:**
- 不改变登录本身的账号校验逻辑（单管理员、凭证校验不变）。
- 不引入多用户/多角色能力。

## Decisions

- **cookie 域**：后端 session 为 host-only cookie（无 Domain），`localhost` 与 `127.0.0.1` 是两个 host、cookie 永不互通。统一全链路用 `127.0.0.1`：`start.ps1` 打开地址、`vite.config.js` 的 `changeOrigin:false`、`main.py` 的 `same_site="lax"` + `https_only=False`。备选「给 cookie 加 Domain=.localhost」不成立（无此域），弃用。
- **进程形态**：`main.py` 末尾 `uvicorn.run(..., reload=False)`，后端单进程。reload=True 会让每个后端变成主进程 + reloader 子进程，多套残留抢 8000 端口、会话清理时变孤儿、后端掉线。改代码后手动重启。
- **错误字段**：后端统一返回 `{code,message,data}`，前端 `Login.vue` 读 `e.response.data.message`（原误读 `detail`，把真实错误吞成笼统「登录失败」）。

## Risks / Trade-offs

- [reload=False 后无热重载] → 改后端代码需手动重启，属有意的取舍（稳定性优先于开发便利）；已在记忆与衔接说明中固化「改代码手动重启」。
- [cookie 约束依赖访问 host 统一] → 已在 `start.ps1` 全链路强制 127.0.0.1，并在衔接说明「已知坑」第一条固化。

## 验收基准（实跑结果）

- **cookie 域**：curl 实测 host-only cookie 不互通，统一 127.0.0.1 后登录态可写入。
- **进程形态**：改后仅 1 个 python 进程（无 reloader 子进程），健康检查 + 登录正常。
- **错误字段**：凭证错误时前端展示后端 `message` 具体原因，非笼统「登录失败」。
