# Spec Delta

## MODIFIED Requirements

### Requirement: 多格式文档解析
系统 SHALL 支持解析 MD、PDF、Word、Excel 四类文档，提取可检索的文本内容；文档来源 SHALL 为知识管理文件库（`data/knowledge/`），不再从 `docs/` 目录加载。

#### Scenario: 解析文字版文档
- **WHEN** 知识库从知识管理加载 MD、Word 或含文字层的 PDF 文档
- **THEN** 系统 MUST 提取其文本内容，供后续分块与索引使用

#### Scenario: 解析 Excel 表格
- **WHEN** 知识库从知识管理加载 Excel 文档
- **THEN** 系统 MUST 按表格结构提取内容，保留行列语义

### Requirement: 语义路由
系统 SHALL 判断用户问题所属的知识域（工艺类 / 制度类 / 知识类，与知识管理「入库类型」一致），并分流到对应子知识库检索。

#### Scenario: 识别知识域
- **WHEN** 用户提问
- **THEN** 系统 MUST 判断问题属于哪一类知识域（工艺类 / 制度类 / 知识类）

#### Scenario: 公司制度域
- **WHEN** 用户提出考勤、请假、报销、薪酬、考核、岗位职责、离职交接等人事行政类问题
- **THEN** 系统 MUST 将其路由到「制度类」域，并检索知识管理「制度类」文件

## ADDED Requirements

### Requirement: 启用状态过滤
系统 SHALL 仅索引「启用」状态的文件；停用（disabled）文件 SHALL 不进索引、不被检索。

#### Scenario: 停用文件不进索引
- **WHEN** 某文件被停用
- **THEN** 系统 MUST 在构建索引时跳过该文件，问答检索时无法命中该文件

### Requirement: 当前版本索引
系统 SHALL 仅索引文件的「当前版本」；历史版本 SHALL 不进索引，仅保留用于查看 / 下载 / 回滚。

#### Scenario: 只取当前版本
- **WHEN** 某文件存在多个版本（v1 / v2 / …）
- **THEN** 系统 MUST 仅将其当前版本内容纳入索引，历史版本不参与检索
