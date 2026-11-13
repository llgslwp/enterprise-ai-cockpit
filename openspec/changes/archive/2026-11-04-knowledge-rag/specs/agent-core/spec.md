# Spec Delta

## MODIFIED Requirements

### Requirement: 云端大模型接入
系统 SHALL 通过统一接入层调用云端大模型（国内厂商）实现自然语言问答与知识库生成能力，不本地部署大模型。

#### Scenario: 调用云端大模型
- **WHEN** 系统需要理解自然语言问题或生成回答
- **THEN** 系统 MUST 通过云端大模型 API 完成，而非本地部署模型

#### Scenario: 厂商可切换
- **WHEN** 需要更换云端大模型厂商
- **THEN** 系统 SHALL 通过抽象接入层隔离厂商差异，更换厂商不改动业务逻辑

### Requirement: 对话主交互形态
系统 SHALL 以「对话」作为知识库问答的主交互形态，用户以自然语言提问，系统返回基于知识库检索生成的回答。

#### Scenario: 核心操作经对话驱动
- **WHEN** 用户以自然语言向知识库提问
- **THEN** 系统 SHALL 通过对话返回基于知识库检索生成的回答

## REMOVED Requirements

### Requirement: 自研轻量编排引擎
**Reason**: 项目改用 LangChain 承载人机对话编排，自研编排引擎不再需要。
**Migration**: 人机对话编排改由 LangChain 实现，行为契约见 `knowledge-base` 规范。

### Requirement: 自然语言意图识别
**Reason**: 人机对话改为纯知识库问答，不再识别「写回/排产」等操作意图。
**Migration**: 问题的知识域识别由 `knowledge-base` 的「语义路由」能力承担。

### Requirement: 全局智能助手
**Reason**: 操作型智能助手（触发写回/排产）被清除，由知识库问答页取代。
**Migration**: 用户通过「知识库」页进行自然语言问答。

### Requirement: 副作用操作确认
**Reason**: 人机对话不再触发任何生产管理写操作，无副作用需要确认。
**Migration**: 无（写回/排产仍由生产管理页面按钮触发）。

### Requirement: 操作结果反馈
**Reason**: 人机对话不再执行写回/排产等操作，无操作结果需反馈。
**Migration**: 无。

### Requirement: 重点规格自然语言查询
**Reason**: 人机对话改为纯知识库问答，不再提供库存/台账等数据查询。
**Migration**: 重点规格数据仍可在库存管理页面查看。
