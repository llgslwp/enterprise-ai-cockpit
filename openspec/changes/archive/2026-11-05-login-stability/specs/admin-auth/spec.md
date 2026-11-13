# Spec Delta

## MODIFIED Requirements

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
