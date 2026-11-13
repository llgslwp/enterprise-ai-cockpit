# Tasks

## 1. 控制图能力

- [x] 1.1 新建 `modules/quality/spc.py`，复用 reader 按日聚合抽检/不合格，算 CL + 逐日 UCL/LCL，标记破限点与小样本（n<30），缺月回退 note。验证：跑 10 月数据，CL=0.95%，破限日 10/14/19/20/21/22/28，与规格基准一致。
- [x] 1.2 在 router.py 加 `/api/quality/spc` 接口，返回控制图聚合结果。验证：curl 登录后请求 `?month=10`，返回 code:0 且含 cl/points。

## 2. 四预警建议动作

- [x] 2.1 在 aggregate.py 追加六分类 `classify_problem` + 姓名异写归并 + `build_suggestions`（四预警→建议动作），`build_quality` 追加 `suggestions` 字段。验证：跑 10 月，3.1 反复出现「杨明光·材料缺陷 27 次」，3.3 让步 7 批，3.4 供应商日照垣豪3/龙口科艺隆2，均命中基准。

## 3. 8D 闭环

- [x] 3.1 新建 `modules/quality/eight_d.py`，从 3.1 派生人员反复卡（D1–D4 数据派生，D5–D8 可读写），台账存 `data/8d_closure.json`（原子写，独立于 data/raw）。验证：写回/合并读取/重置三个环节跑通。
- [x] 3.2 在 aggregate.py 追加 `build_cross_month_anchors`（工段+主题关键词归并），eight_d.py 改双维度（repeat/cross_month），前端 8D 卡加类型标签。验证：10 月生成 5 张卡（1 repeat + 4 cross_month），跨月锚点「热处理·螺纹裂·齿崩 98 次（8月35→9月36→10月27）」。
- [x] 3.3 在 router.py 加 `/api/quality/8d`、`/api/quality/8d/update`、`/api/quality/8d/reset`。验证：curl 写回与重置跨月卡，返回最新状态。

## 4. 前端页面

- [x] 4.1 新建 `web/src/views/QualityTools.vue`（一个页面三块：控制图 ECharts p 图 / 四预警建议表格 / 8D 闭环卡片，D4–D8 可编辑写回）。验证：Vite 编译产物正常，页面可访问 `/quality/tools`。
- [x] 4.2 api/index.js 加 4 个接口封装，router 注册 `/quality/tools`，Home.vue 导航「质量管理」下加「质量管理工具」。验证：刷新页面导航出现新菜单项。

## Workflow follow-up

- 归档本变更（openspec archive）。
- 业务方实际点开「质量管理工具」页确认可用（铁律第 7 条）。
