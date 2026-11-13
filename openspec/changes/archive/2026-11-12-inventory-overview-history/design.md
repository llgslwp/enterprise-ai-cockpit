# Design

## 技术方案概述

纯前端改造，后端零改动。核心是利用后端早已就绪的两项能力：

1. **`flow-stats` 的 `monthly` 字段**：`build_flow_stats()` 返回 12 个月每月 `{month, in, out, stock}`，这是趋势折线图的数据源；
2. **`flow-stats` / `share-stats` 的 `month` 参数**：接口已支持 `?month=N`，这是月份切换的数据源。

## 数据流

```
首次加载：
  inventoryFlowStats()  →  stats { month, total, products, series, monthly }  →  趋势图取 monthly；KPI/柱状/环形取 total/products/series
  inventoryShareStats() →  share { in/out/stock }                              →  环形图取 share

切换月份（点击「N月」）：
  inventoryFlowStats(N)  →  stats { month=N, total, products, series, monthly }  →  KPI/柱状/环形刷新为 N 月；趋势图仍取 monthly（12 个月不变）
  inventoryShareStats(N) →  share { in/out/stock }                               →  环形图刷新为 N 月
```

要点：`monthly` 字段无论传不传 `month` 都返回完整 12 个月（`build_flow_stats` 中独立于月份索引累加），故趋势图数据源稳定、不受切换影响。

## 前端改动（`web/src/views/InventoryOverview.vue`）

1. **月份切换按钮**：复用 `Planning.vue` 的月份按钮模式（`.mbtn` 样式），顶部加「最新 + 1~12 月」按钮组。`current` 状态默认 `'latest'`（不传 month，展示当前真实月）。
2. **趋势折线图**：新增 ECharts line 图（`flow-bar` 之前/之后位置），三条线 = 入库（`#2ee6a8` 绿）/ 出库（`#ff5b7f` 红）/ 结存（`#ffd166` 黄），与既有柱状图配色一致；x 轴 = 1~12 月，数据取 `stats.monthly`。
3. **切换逻辑**：`load(month)` 接收可选月份参数，`switchMonth(key)` 更新 `current` 后重新调 `inventoryFlowStats(month)` + `inventoryShareStats(month)`；渲染逻辑复用既有 `watch` + `nextTick` 模式。
4. **badge 联动**：顶部「2026年{month}月」badge 随 `stats.month` 自动更新（`monthly` 里 month 值与返回的 `stats.month` 一致）。

## 关键实现细节

- **月份列表**：直接由 `1..12` 生成（台账「汇总看板」固定 12 个月列），不依赖后端额外返回。
- **趋势图固定**：月份切换只刷新 KPI/柱状/环形，趋势图实例不重建、数据不变（或保持 12 个月渲染），避免闪烁。
- **月份标签**：`最新` / `1月` / `2月` … `12月`（顶部 badge 已显示具体「2026年N月」，按钮不必重复年份）。

## 性能

- 月份切换 = 常规查询：zip 直读「汇总看板」单 sheet ~50ms，远低于 200ms 约束。
- 趋势图：12 点 × 3 线，ECharts 渲染 <10ms，无性能风险。
- 无新增后端开销、无新增数据文件读取。

## 风险与边界

- **仅改前端**，不触碰后端接口契约，故数据正确性风险极低（沿用已验证的 `flow_stats` 实现）。
- 趋势图与柱状图/环形图的月份联动，依赖 `stats.month` 正确回传——已有逻辑保证。
- 本期不做「趋势图高亮当前月」等交互增强，保持简单。
