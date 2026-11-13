# Proposal

## Why

质量管理模块目前只有「看结果」的看板（生产巡检合格率、原料来料检验），缺少「用工具找问题、追根因、闭环整改」的能力。管理层能看见合格率低、问题多，但无法从数据中自动定位过程异常、反复出现的人/问题、以及需要 8D 闭环的质量事故。本次新增「质量管理工具」，把质量数据从「展示」升级为「可分析、可追踪、可闭环」。

## What Changes

- 新增「质量管理工具」子模块，挂在「质量管理」导航下，一个页面分三块。
- 新增 **控制图**（p 图）：逐日聚合抽检数/不合格数，计算中心线 CL 与随样本量变化的逐日 UCL/LCL，标记破限点与小样本（n<30）点。
- 新增 **四预警建议动作**：基于抽检数据自动生成四类预警（反复出现/记录盲区/让步清单/供应商关注）对应的建议动作，含问题六分类与姓名异写归并。
- 新增 **8D 闭环**：从「反复出现」与「问题描述跨月反复」两个维度自动派生 8D 卡（D1–D4 数据派生，D5–D8 可填写），写回独立台账文件。
- 新增接口 `/api/quality/spc`、`/api/quality/8d`、`/api/quality/8d/update`、`/api/quality/8d/reset`，并扩展 `/api/quality/inspection` 返回 `suggestions` 字段。

## Capabilities

### New Capabilities
- `quality-tools`: 质量分析与整改工具能力，覆盖控制图、四预警建议动作、8D 闭环三项，数据只读自本地抽检记录，8D 闭环状态写回独立台账。

### Modified Capabilities
（无）

## Impact

- **后端**：新增 `modules/quality/spc.py`、`modules/quality/eight_d.py`；修改 `modules/quality/aggregate.py`（追加六分类 + 建议动作 + 跨月锚点）、`modules/quality/router.py`（新增 4 个路由）。
- **前端**：新增 `web/src/views/QualityTools.vue`；修改 `web/src/api/index.js`、`web/src/router/index.js`、`web/src/views/Home.vue`。
- **数据**：新增写回台账 `data/8d_closure.json`（独立于 `data/raw`，绝不写回原始质检 Excel）。
- **依赖**：前端控制图复用 ECharts；无新增第三方依赖。
