# admin-auth Specification

## Purpose

定义单管理员账号登录能力，作为访问生产、库存、质量数据的统一前置入口，确保未登录用户无法进入业务页面。

## Requirements

### Requirement: 单管理员登录
系统 SHALL 提供单一管理员账号的登录能力，作为访问生产、库存、质量数据的统一前置入口。

#### Scenario: 未登录访问受限
- **WHEN** 用户未登录即访问生产、库存或质量相关页面
- **THEN** 系统 MUST 拒绝访问，并引导用户先登录

#### Scenario: 登录成功访问
- **WHEN** 用户以正确管理员账号密码登录
- **THEN** 系统 MUST 允许其访问生产、库存、质量相关页面

### Requirement: 登录凭证校验
系统 SHALL 对登录凭证进行校验，MUST 在凭证错误时拒绝登录并给出提示。

#### Scenario: 凭证错误
- **WHEN** 用户提交错误的账号或密码
- **THEN** 系统 MUST 拒绝登录并提示凭证错误

### Requirement: 单账号范围
系统本次 SHALL 仅支持单一管理员账号，MUST NOT 支持多用户或多角色。

#### Scenario: 无多用户能力
- **WHEN** 系统处理用户身份
- **THEN** 系统 MUST 仅识别一个管理员账号，不提供多用户或多角色管理能力

### Requirement: 登录会话稳定性
系统 SHALL 保证登录态在前端与后端之间可靠传递与保持：前端访问地址、后端会话 cookie 配置 MUST 统一使用 `127.0.0.1`（禁用 `localhost`），以避免 host-only cookie 因 host 不一致而无法写入。

#### Scenario: 域名一致才可登录
- **WHEN** 用户通过浏览器访问驾驶舱并登录
- **THEN** 系统 MUST 以 `127.0.0.1` 作为访问 host，后端 session cookie MUST 与前端 host 一致，登录成功后登录态可写入浏览器

#### Scenario: 使用 localhost 登录失败
- **WHEN** 用户以 `localhost` 访问驾驶舱
- **THEN** 系统 MUST 视为非法访问 host，登录态无法可靠写入（后端 session cookie 为 host-only，`localhost` 与 `127.0.0.1` 不互通）

### Requirement: 登录错误提示契约
系统 SHALL 对登录失败给出真实、可诊断的错误提示：前端 MUST 读取后端统一响应体 `{code,message,data}` 中的 `message` 字段作为错误文案，而非其他字段。

#### Scenario: 凭证错误提示真实原因
- **WHEN** 用户提交错误的账号或密码
- **THEN** 前端 MUST 展示后端 `message` 字段返回的具体错误，而非笼统的「登录失败」
