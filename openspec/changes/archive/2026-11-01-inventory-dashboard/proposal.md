# Proposal

## Why

库存管理已有数据能力（`inventory-status` 提供汇总看板、明细查询、预警），但前端仍是一张浅色后台页，未匹配用户对「深色科技风大屏」的既定视觉规范，也缺少「只盯重点规格」的聚焦视图。需要把库存管理改造为一套 4 页深色大屏，并引入可维护的「重点关注规格」机制，让管理者一眼看清库存全貌与关键规格动向。

## What Changes

- 将原浅色 `Inventory.vue` 替换为深色科技风大屏，侧边栏「库存管理」展开为 4 个子菜单：库存总览、库存占比、库存明细、缺口统计。
- **库存总览**：3 个 KPI（本月入库/出库/结存）+ 6 品类入库/出库/结存柱状图 + 占比环形图。
- **库存占比**：入库/出库/结存 × 各品种（6 品类）/两大系列（管钳/自由钳）共 6 张环形图。
- **库存明细**：由「全量 6 品类规格」改为「重点关注规格」——仅展示清单中勾选的规格，展示本月入库/出库/结存。
- **缺口统计**：复用库存预警（低于安全库存），单独成页。
- 新增「重点关注规格」开口式清单机制：独立 Excel 清单表（`data/raw/重点关注规格.xlsx`，全量规格 + 「是否重点」勾选列），用户增删勾选即时生效。
- 新增后端接口 `/api/inventory/focus-stats`（重点规格本月入出库结存）与 `/api/inventory/flow-stats`、`/api/inventory/share-stats`（总览/占比数据）。
- AI 助手（`agent-core`）的 query 意图新增「重点规格」查询，返回重点规格本月数据摘要。

## Capabilities

### New Capabilities

- `inventory-dashboard`: 库存管理大屏——4 页深色可视化 + 重点关注规格清单机制 + 配套数据接口。

### Modified Capabilities

- `agent-core`: query 意图扩展「重点规格」关键词，并返回重点规格真实数据摘要（原为占位回复）。

## Impact

- 后端：`modules/inventory/flow_stats.py`（新增 build_flow_stats / build_share_stats / build_focus_stats）、`modules/inventory/focus_specs.py`（新增，读重点规格清单）、`modules/inventory/router.py`（新增 3 个接口）。
- 前端：`web/src/views/` 新增/重写 InventoryOverview.vue / InventoryShare.vue / InventoryDetail.vue / InventoryGap.vue；`web/src/router/index.js`、`web/src/api/index.js`、`web/src/views/Home.vue`（侧边栏子菜单）。
- 数据：新增 `data/raw/重点关注规格.xlsx`（开口式清单，用户维护）。
- 依赖：ECharts 6.1.0（前端图表）。
