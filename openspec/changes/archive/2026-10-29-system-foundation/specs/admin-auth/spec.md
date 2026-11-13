# Spec Delta

## Purpose

定义单管理员账号登录能力，作为访问生产、库存、质量数据的统一前置入口。

## ADDED Requirements

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
