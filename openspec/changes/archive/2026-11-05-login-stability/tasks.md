# Tasks

## 1. 全链路统一 127.0.0.1

- [x] 1.1 `start.ps1` 打开地址 `localhost`→`127.0.0.1`。验证：启动后浏览器地址为 127.0.0.1。
- [x] 1.2 `web/vite.config.js` 代理 `changeOrigin:false`（host 保持 127.0.0.1）。验证：前端请求后端 host 为 127.0.0.1。
- [x] 1.3 `main.py` SessionMiddleware 加 `same_site="lax"`、`https_only=False`。验证：登录成功后浏览器有 session cookie。

## 2. 后端改单进程

- [x] 2.1 `main.py` `uvicorn.run(reload=True)`→`reload=False`。验证：`netstat -ano | findstr :8000` 仅一个 python 进程监听，无 reloader 子进程。

## 3. 前端错误字段契约

- [x] 3.1 `web/src/views/Login.vue` 错误字段 `e.response.data.detail`→`.message`。验证：凭证错误时展示后端 `message` 真实原因。

## 4. Vite 文件监听改轮询（关联稳定性，11-04 一并修复）

- [x] 4.1 `web/vite.config.js` 加 `server.watch.usePolling:true` + `interval:300`。验证：`touch web/index.html` 后 Vite 日志立即输出 `page reload`。

## Workflow follow-up

- 归档本变更（openspec archive）。
- 同步主 specs：`openspec/specs/admin-auth/spec.md`、`openspec/specs/system-platform/spec.md`。
- 业务方实际双击 `start.ps1` 登录确认（铁律第 7 条：稳定常驻靠真实 cmd 环境，非工具启动）。
