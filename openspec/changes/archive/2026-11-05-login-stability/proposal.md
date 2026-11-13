# Proposal

## Why

登录功能在 2026-11-04 至 11-05 期间反复出现「登录失败，请检查账号密码」，排查后确认是**三层根因叠加**，而非单一 bug：

1. **cookie 域不互通**：后端 session cookie 为 host-only（无 Domain），`localhost` 与 `127.0.0.1` 是两个不同 host，cookie 永不互通，用 localhost 打开会「登录成功但登录态写不进浏览器」。
2. **后端双进程抢端口掉线**：`main.py` 末尾 `uvicorn.run(..., reload=True)` 使每个后端成为「主进程 + reloader 子进程」双进程，多套残留抢 8000 端口、会话清理时变孤儿，后端悄悄掉线（表现为「登录失败但前端 5173 还在跑」）。
3. **前端错误字段吞掉真实报错**：`Login.vue` 误读 `e.response.data.detail`，后端统一返回 `{code,message,data}`，真实错误被吞成笼统「登录失败」。

这三处此前已实际修改并验证，但**未按 OpenSpec 规范立项与归档**，属遗漏。本次补档，把登录稳定性约束固化进规格，避免换电脑/换账号后重犯。

## What Changes

- **固化 cookie 域约束**：前端访问、后端 session 配置全链路统一使用 `127.0.0.1`，禁用 `localhost`。
- **固化后端单进程约束**：后端禁止 `reload=True`，改单进程运行，消除 reloader 子进程导致的端口争抢与掉线。
- **固化前端错误字段契约**：登录错误提示统一读取后端 `{code,message,data}` 的 `message` 字段。

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `admin-auth`: 新增「登录会话稳定性」与「登录错误提示契约」两条约束。
- `system-platform`: 新增「后端运行进程形态」约束（禁止 reload=True 多进程）。

## Impact

- **后端**：`main.py`（SessionMiddleware 加 `same_site="lax"`、`https_only=False`；`uvicorn.run(reload=False)`）。
- **前端**：`web/vite.config.js`（`changeOrigin:false`、`server.watch.usePolling:true` + `interval:300`）；`web/src/views/Login.vue`（错误字段 `detail`→`message`）。
- **启动脚本**：`start.ps1`（打开地址 `localhost`→`127.0.0.1`）。
- **依赖**：无新增第三方依赖。
