# Spec Delta

## MODIFIED Requirements

### Requirement: 后端运行进程形态
系统 SHALL 以后端单进程形态运行，MUST NOT 启用 uvicorn 的 `reload=True` 热重载，以避免「主进程 + reloader 子进程」双进程结构导致的端口争抢、孤儿进程与后端掉线。

#### Scenario: 后端单进程常驻
- **WHEN** 系统启动后端服务
- **THEN** 后端 MUST 以单进程运行（仅一个 python 进程），MUST NOT 存在 reloader 子进程

#### Scenario: 代码变更后重启生效
- **WHEN** 后端代码发生变更
- **THEN** 系统 SHALL 通过手动重启后端加载新代码，而非依赖 reload 热重载
