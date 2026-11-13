# Tasks

## 1. 前端：月份切换按钮 + 历史趋势折线图

- [x] 1.1 `InventoryOverview.vue` 加 `current` / `monthOptions` 状态（最新 + 1~12 月）
- [x] 1.2 `load(month)` 改为接收可选月份参数，切换时重取 `inventoryFlowStats(month)` + `inventoryShareStats(month)`
- [x] 1.3 新增历史趋势折线图（12 个月 × 入库/出库/结存，配色绿/红/黄），数据取 `stats.monthly`
- [x] 1.4 顶部加月份切换按钮组（复用 Planning 的 `.mbtn` 样式），badge 随 `stats.month` 联动

## 2. 验证

- [x] 2.1 数据回归：切换各月份时，后端 `flow-stats?month=N` 的 total/products 随月正确变化（month=8 total.in=13989、month=11 total.in=4340），前端仅渲染后端返回、数据源一致
- [x] 2.2 趋势图数据：`monthly` 字段 = 台账「汇总看板」1~12 月列（12 个月全量），month 参数切换时 monthly 保持恒定（趋势图固定）
- [x] 2.3 性能回归：`build_flow_stats` 实测 66ms（≤200ms），month 参数切换无新增开销；`vite build` 编译通过（711 模块）
- [x] 2.4 业务方实际点开「成品总览」，确认历史趋势图 + 月份切换正常显示（铁律第 7 条「完成 = 用户能用起来」）

## 3. 归档

- [x] 3.1 业务方验收通过后 `openspec archive 2026-11-12-inventory-overview-history`
