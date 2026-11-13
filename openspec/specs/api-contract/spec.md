# api-contract Specification

## Purpose
定义后端 REST API 的统一契约：路径风格、请求 / 响应结构、错误码、鉴权与文件下载方式，作为前端与后端之间的唯一接口约定，以 FastAPI OpenAPI（Swagger UI）为唯一契约载体。

## Requirements

### Requirement: REST API 与 JSON 响应
后端 SHALL 通过 REST 接口向前端提供数据，业务接口的响应体 MUST 为 JSON。

#### Scenario: 业务数据接口
- **WHEN** 前端请求任一业务数据（如库存、回填、排产结果）
- **THEN** 后端 MUST 返回 JSON 响应，而非 HTML 页面或服务端渲染内容

### Requirement: 接口路径前缀
所有后端接口 SHALL 统一挂载在 `/api/` 前缀下，避免与前端静态资源路径冲突。

#### Scenario: 接口访问
- **WHEN** 前端调用后端接口
- **THEN** 接口路径 MUST 以 `/api/` 开头

### Requirement: OpenAPI 作为唯一契约载体
后端接口 SHALL 以 FastAPI 自动生成的 OpenAPI 文档（Swagger UI）作为接口契约的唯一载体，不另设独立的接口文档。

#### Scenario: 契约查阅
- **WHEN** 开发方或前端需要查阅接口契约
- **THEN** 接口的路径、参数、请求 / 响应结构 MUST 可从 OpenAPI 文档中获得，无需依赖额外手写接口文档

### Requirement: 鉴权与 CORS 凭证
受保护的接口 SHALL 要求登录态，前端跨域访问 MUST 携带凭证，后端 MUST 配置 CORS 允许凭证。

#### Scenario: 未登录访问受保护接口
- **WHEN** 未登录的请求访问受保护接口
- **THEN** 后端 MUST 拒绝访问并返回未授权状态（如 401 / 403），而非返回业务数据

#### Scenario: 跨域携带登录态
- **WHEN** 前端在开发期从不同端口跨域访问后端
- **THEN** 后端 MUST 允许携带凭证的跨域请求（CORS allow-credentials），前端 MUST 以携带凭证的方式发起请求

### Requirement: 文件下载契约
生成 Excel 等结果文件时，后端 SHALL 通过明确的下载接口返回文件流，前端据此触发下载。

#### Scenario: 下载结果文件
- **WHEN** 用户请求下载计算结果文件（如回填结果、V2.0 排产结果）
- **THEN** 后端 MUST 通过下载接口返回文件流，响应头 MUST 明确文件类型与下载文件名
