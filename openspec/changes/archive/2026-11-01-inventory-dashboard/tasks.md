# Tasks

## 1. 数据聚合层

- [x] 1.1 新增 `modules/inventory/flow_stats.py` 的 build_flow_stats（6 品类 + 两大系列 + 分品类明细），验证：build_flow_stats() 返回 total/products/series/detail，10 月总入库 7256/出库 9878/结存 32040
- [x] 1.2 新增 build_share_stats（入库/出库/结存 × 各品种/两大系列占比），验证：返回 in/out/stock 三组各含 products/series 及 pct
- [x] 1.3 新增 `modules/inventory/focus_specs.py`（读重点规格清单为三元组集合），验证：load_focus_specs 正确识别「是/✓」并跳过空值与分隔行
- [x] 1.4 新增 build_focus_stats（过滤重点规格的本月入出库结存），验证：勾选 30 个规格后 count=30，按品类正确分组

## 2. 后端接口

- [x] 2.1 router.py 新增 /api/inventory/flow-stats、/share-stats、/focus-stats 三接口，验证：TestClient 登录后均返回 200 且数据结构正确
- [x] 2.2 重启后端服务使新路由生效，验证：curl /api/inventory/focus-stats 由 404 Not Found 变为 401 未登录（路由已加载）

## 3. 前端大屏四页

- [x] 3.1 新增 InventoryOverview.vue（3 KPI + 6 品类柱状图 + 占比环形图），验证：npm run build 无错，页面图表正常渲染
- [x] 3.2 新增 InventoryShare.vue（6 张占比环形图），验证：build 无错，两行三列渲染完整
- [x] 3.3 重写 InventoryDetail.vue（重点规格明细表 + 3 KPI），验证：只展示清单勾选规格，空状态有提示
- [x] 3.4 新增 InventoryGap.vue（缺口统计/预警明细），验证：复用 build_alerts，表格正常展示
- [x] 3.5 修复图表空白：统一改 watch + nextTick + requestAnimationFrame 渲染时机，验证：刷新后三页图表均非空白

## 4. 路由与导航

- [x] 4.1 router/index.js 注册 /inventory/overview、/share、/detail、/gap 四路由，验证：访问各路径均命中对应组件
- [x] 4.2 Home.vue 侧边栏「库存管理」改为可展开子菜单，验证：4 个子项可点击跳转

## 5. AI 助手查询

- [x] 5.1 agent engine.py 的 query 意图加「重点规格」关键词，验证：detect_intent("重点规格有哪些") 返回 query
- [x] 5.2 query 分支对重点规格查询返回真实数据摘要，验证：Orchestrator.handle 返回 30 个规格的逐条本月数据

## Workflow follow-up

- 归档本变更并将 inventory-dashboard 同步进主 specs。
