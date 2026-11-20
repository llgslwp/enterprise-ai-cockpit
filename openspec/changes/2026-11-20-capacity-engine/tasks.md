# Tasks

## 1. 实现（配置驱动改造 + 阶段1 范围限定）

- [x] 1.1 新建 `modules/production/capacity.py`：两维口径纯函数 `_calc_capacity_core` + `calc_capacity` / `calc_capacity_all`
- [x] 1.2 `modules/agent/tools.py` 新增 `query_capacity` tool（docstring 写「使用时机」+「可产≠缺口≠库存」区分），加入 `ALL_TOOLS`
- [x] 1.3 `modules/agent/agent.py` 提示词止血：可产数量用 `query_capacity`，严禁拿缺口减成品计划硬凑
- [x] 1.4 新增 `tests/test_capacity.py`：71-75=627 真值锚点 + 第二维度触发/不触发/整除取整/缺件归零
- [ ] 1.5 `capacity.py` 抽配置驱动骨架：`_DIM1`/`_DIM2` 明确为品类 BOM 配置；新增 `SUPPORTED_SPECS`（钻杆钳: 54-56, 71-75）
- [ ] 1.6 借件规格（89-95/114-117）与借用规格（成品计划=0）返回明确提示、不孤立算 0；`calc_capacity_all` 只算支持规格

## 2. 验证

- [ ] 2.1 真值锚点：54-56=210（瓶颈=组装简易钳体）、71-75=627（瓶颈=自由钳外管），与真实台账快照逐值一致
- [ ] 2.2 借件/借用规格排除：89-95/114-117 返回「借件规格」提示、139-146/86-91/58-62/108-110 返回「不单独排产」，无 0 值误导
- [ ] 2.3 全量 pytest 跑通（原 58 + 新增），无回归
- [ ] 2.4 性能回归：单规格 ≤200ms、`calc_capacity_all` 只读一次文件 ≤200ms
- [ ] 2.5 端到端复现：重问「最多能生产多少把 71-75」，模型调 `query_capacity` 答 627、瓶颈=自由钳外管，工具轨迹可追溯

## 3. 验收

- [ ] 3.1 业务方在「辅助决策」页实际提问确认（铁律第 7 条「完成 = 用户能用起来」）
- [ ] 3.2 业务方验收通过后 archive
