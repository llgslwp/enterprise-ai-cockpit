"""产能计算（capacity）单元测试。

真值锚点（钻杆钳阶段1 支持规格，2026-11-20 从 data/raw/半成品生产计划V2.0.xlsx 实读）：
- 71-75：组装简易钳体·装配=912，活动齿块·半成品=1404，自由钳外管·半成品=627 → 627 把，瓶颈=自由钳外管。
- 54-56：组装简易钳体·装配=210，活动齿块·半成品=1387，自由钳外管·半成品=2703 → 210 把，瓶颈=组装简易钳体。
- 口径（文鹏口述锁定）：两维 min，第二维度触发 = 齿块 和 外管 都还有剩余。

阶段1 范围：只算钻杆钳 54-56、71-75 独立规格；借件规格（89-95/114-117）、
借用规格（成品计划=0）返回说明、不孤立算 0。
"""

import pytest

from modules.production import gap_stat
from modules.production.capacity import (
    COL_C,
    COL_F,
    COL_H,
    COL_I,
    _calc_capacity_core,
    _calc_capacity_jiali_core,
    calc_capacity,
    calc_capacity_all,
)


def _make_rows(zhuangpei, chikuai, waiguan, gangban, huodong, jiajin, changxiao, duanxiao, zuhe):
    """构造 rows 结构 {配件名: {cells:{列号:值}}}，喂给纯计算函数。"""
    return {
        "组装简易钳体": {"cells": {COL_I: zhuangpei}},
        "活动齿块": {"cells": {COL_H: chikuai}},
        "自由钳外管": {"cells": {COL_H: waiguan}},
        "固定钢板": {"cells": {COL_C: gangban}},
        "活动钳体": {"cells": {COL_H: huodong}},
        "夹紧头": {"cells": {COL_H: jiajin}},
        "长销子": {"cells": {COL_H: changxiao}},
        "短销子": {"cells": {COL_H: duanxiao}},
        "组装齿块+方块座": {"cells": {COL_H: zuhe}},
    }


# ---------- 纯计算逻辑（不依赖真实文件，CI 可跑） ----------

def test_capacity_71_75_snapshot():
    """71-75 真实台账快照 → 627 把，瓶颈自由钳外管，第二维度不触发。"""
    rows = _make_rows(912, 1404, 627, 3, 3049, 1891, 11234, 2445, 2415)
    r = _calc_capacity_core(rows)
    assert r["总可产把数"] == 627
    assert r["第一维度可产"] == 627
    assert r["第二维度追加"] == 0
    assert r["瓶颈件"] == ["自由钳外管"]
    assert r["第二维度"]["触发"] is False
    # 第二维度即使不触发，也如实给出"可新组简易钳体"（固定钢板 3 // 2 = 1）
    assert r["第二维度"]["可新组简易钳体"] == 1


def test_capacity_54_56_snapshot():
    """54-56 真实台账快照 → 210 把，瓶颈组装简易钳体，第二维度触发但配件 0 无追加。"""
    rows = _make_rows(210, 1387, 2703, 2053, 2278, 0, 0, 0, 3610)
    r = _calc_capacity_core(rows)
    assert r["总可产把数"] == 210
    assert r["第一维度可产"] == 210
    assert r["第二维度追加"] == 0
    assert r["瓶颈件"] == ["组装简易钳体"]
    # 齿块(1177)/外管(2493)都有剩余 → 触发；但夹紧头/长销子/短销子=0 → 可新组=0
    assert r["第二维度"]["触发"] is True
    assert r["第二维度"]["可新组简易钳体"] == 0


def test_capacity_dim2_triggered():
    """组装简易钳体是瓶颈 → 第二维度触发并追加。"""
    rows = _make_rows(100, 1000, 1000, 1000, 1000, 1000, 2000, 1000, 2000)
    r = _calc_capacity_core(rows)
    # 第一维度 min(100,1000,1000)=100；剩余 齿块900 / 外管900
    # 可新组 = min(500,1000,1000,1000,1000,1000)=500；追加 = min(500,900,900)=500
    assert r["第一维度可产"] == 100
    assert r["第二维度追加"] == 500
    assert r["总可产把数"] == 600
    assert r["第二维度"]["触发"] is True
    assert "组装简易钳体" in r["瓶颈件"]
    assert "固定钢板" in r["瓶颈件"]


def test_capacity_dim2_not_triggered_when_waiguan_exhausted():
    """外管用尽（剩余 0）→ 第二维度不触发，即使配件够组。"""
    rows = _make_rows(1000, 1000, 100, 1000, 1000, 1000, 2000, 1000, 2000)
    r = _calc_capacity_core(rows)
    assert r["第一维度可产"] == 100  # min(1000,1000,100)
    assert r["第二维度"]["触发"] is False
    assert r["第二维度追加"] == 0
    assert r["总可产把数"] == 100
    assert r["瓶颈件"] == ["自由钳外管"]


def test_capacity_floor_division():
    """整除向下取整：固定钢板 3 件 → 可组 1 个（不够 2 件就不算 1 套）。"""
    rows = _make_rows(912, 1404, 627, 3, 3049, 1891, 11234, 2445, 2415)
    r = _calc_capacity_core(rows)
    assert r["第二维度"]["可新组简易钳体"] == 1


def test_capacity_missing_part_treated_as_zero():
    """缺配件（rows 里没有）按 0 处理，可产 = 0，不报错。"""
    rows = _make_rows(912, 1404, 627, 3, 3049, 1891, 11234, 2445, 2415)
    rows.pop("自由钳外管")
    r = _calc_capacity_core(rows)
    assert r["总可产把数"] == 0
    assert r["瓶颈件"] == ["自由钳外管"]


# ---------- 加力钳三维（纯计算，不依赖真实文件） ----------

def _jiali_95_rows():
    """加力 95 真实台账快照（2026-11-20 实读）：组合件 I 列 + 补件 H/F/I 列。

    真值锚点：三合一 I=945、二合一 I=1277、大钳口 H=1184、固定帽 H=2402、
    螺母 H=2841、把手 H=817+F=778、内管 H=1176、小钳口 H=1163+I=1277、钳体 H=0、外管 F=1204。
    """
    return {
        "加力钳体+外管+小钳口": {"cells": {COL_I: 945}},
        "加力钳体+外管": {"cells": {COL_I: 1277}},
        "加力大钳口": {"cells": {COL_H: 1184}},
        "固定帽": {"cells": {COL_H: 2402}},
        "加力螺母": {"cells": {COL_H: 2841}},
        "把手": {"cells": {COL_H: 817, COL_F: 778}},
        "加力内管（镀锌）": {"cells": {COL_H: 1176}},
        "加力小钳口": {"cells": {COL_H: 1163, COL_I: 1277}},
        "加力钳体": {"cells": {COL_H: 0}},
        "加力外管": {"cells": {COL_F: 1204, COL_H: 0}},
    }


def test_capacity_jiali_95_snapshot():
    """加力 95 真实台账快照 → 1176 把 = 945 + 231 + 0。"""
    r = _calc_capacity_jiali_core(_jiali_95_rows())
    assert r["总可产把数"] == 1176
    assert r["第一维度可产"] == 945
    assert r["第二维度可产"] == 231
    assert r["第三维度可产"] == 0
    assert "加力钳体+外管+小钳口" in r["瓶颈件"]
    assert "加力内管（镀锌）" in r["瓶颈件"]
    assert "加力钳体" in r["瓶颈件"]


def test_capacity_jiali_dim3_bare_assembly():
    """前两维组合件为 0，8 件裸件充足 → 第三维裸件凑装 = min(裸件)。"""
    rows = {
        "加力钳体+外管+小钳口": {"cells": {COL_I: 0}},
        "加力钳体+外管": {"cells": {COL_I: 0}},
        "加力大钳口": {"cells": {COL_H: 100}},
        "固定帽": {"cells": {COL_H: 100}},
        "加力螺母": {"cells": {COL_H: 100}},
        "把手": {"cells": {COL_H: 100, COL_F: 0}},
        "加力内管（镀锌）": {"cells": {COL_H: 100}},
        "加力小钳口": {"cells": {COL_H: 100}},
        "加力钳体": {"cells": {COL_H: 50}},
        "加力外管": {"cells": {COL_F: 100, COL_H: 0}},
    }
    r = _calc_capacity_jiali_core(rows)
    assert r["第一维度可产"] == 0
    assert r["第二维度可产"] == 0
    assert r["第三维度可产"] == 50  # 钳体 50 最少
    assert r["总可产把数"] == 50
    assert "加力钳体" in r["瓶颈件"]


def test_capacity_jiali_missing_combination():
    """缺组合件行 → 组合件按 0，该维度为 0。"""
    rows = _jiali_95_rows()
    rows.pop("加力钳体+外管+小钳口")
    r = _calc_capacity_jiali_core(rows)
    assert r["第一维度可产"] == 0
    assert "加力钳体+外管+小钳口" in r["瓶颈件"]


def _jiali_132_rows():
    """加力 132 真实台账快照（2026-11-20 实读）。

    真值锚点：三合一 I=2、二合一 I=500、大钳口 H=752、固定帽 H=2575、
    螺母 H=3299、把手 H=1501+F=3976、内管 H=1701、小钳口 H=308、钳体 H=2559、外管 F=1890。
    顺序消耗：第一维 2 + 第二维 308（小钳口 H=308 用光）+ 第三维 0 = 310。
    """
    return {
        "加力钳体+外管+小钳口": {"cells": {COL_I: 2}},
        "加力钳体+外管": {"cells": {COL_I: 500}},
        "加力大钳口": {"cells": {COL_H: 752}},
        "固定帽": {"cells": {COL_H: 2575}},
        "加力螺母": {"cells": {COL_H: 3299}},
        "把手": {"cells": {COL_H: 1501, COL_F: 3976}},
        "加力内管（镀锌）": {"cells": {COL_H: 1701}},
        "加力小钳口": {"cells": {COL_H: 308}},
        "加力钳体": {"cells": {COL_H: 2559}},
        "加力外管": {"cells": {COL_F: 1890, COL_H: 0}},
    }


def test_capacity_jiali_132_snapshot():
    """加力 132 真实台账快照 → 310 把 = 2 + 308 + 0，第三维因小钳口被第二维用光归零。"""
    r = _calc_capacity_jiali_core(_jiali_132_rows())
    assert r["总可产把数"] == 310
    assert r["第一维度可产"] == 2
    assert r["第二维度可产"] == 308
    assert r["第三维度可产"] == 0
    assert "加力钳体+外管+小钳口" in r["瓶颈件"]
    assert "加力小钳口" in r["瓶颈件"]


# ---------- 品类/规格路由（不依赖真实文件的部分） ----------

def test_capacity_unsupported_category():
    """非钻杆钳品类 → 返回「暂不支持」说明，不读文件。"""
    r = calc_capacity("71-75", category="美式")
    assert "说明" in r
    assert "钻杆钳" in r["说明"]


# ---------- 依赖真实文件的集成测试（CI 无数据文件时自动跳过） ----------

def _has_data() -> bool:
    try:
        gap_stat.resolve_result_file()
        return True
    except FileNotFoundError:
        return False


needs_data = pytest.mark.skipif(not _has_data(), reason="真实 V2.0 文件不存在（CI 环境）")


@needs_data
def test_capacity_real_file_71_75():
    """真实文件端到端：calc_capacity 读文件 → 627 把，瓶颈自由钳外管。"""
    r = calc_capacity("71-75")
    assert r["总可产把数"] == 627
    assert r["瓶颈件"] == ["自由钳外管"]
    assert r["品类"] == "钻杆钳"
    assert r["规格"] == "71-75"


@needs_data
def test_capacity_real_file_missing_spec():
    """真实文件下查不存在的规格 → 返回说明 + 可选规格。"""
    r = calc_capacity("不存在规格")
    assert "说明" in r
    assert "可选规格" in r


@needs_data
def test_capacity_real_file_borrow_item():
    """借件规格（89-95、114-117）→ 返回「借件」说明，不孤立算 0。"""
    for spec in ("89-95", "114-117"):
        r = calc_capacity(spec)
        assert "说明" in r
        assert "借用" in r["说明"]


@needs_data
def test_capacity_real_file_borrow_spec():
    """借用规格（成品计划=0）→ 返回「不单独排产」说明。"""
    for spec in ("139-146", "86-91", "58-62", "108-110"):
        r = calc_capacity(spec)
        assert "说明" in r
        assert "不单独排产" in r["说明"]


@needs_data
def test_capacity_real_file_all_whitelist():
    """calc_capacity_all 只返回白名单规格（54-56、71-75）。"""
    results = calc_capacity_all()
    specs = [x["规格"] for x in results]
    assert specs == ["54-56", "71-75"]


@needs_data
def test_capacity_real_file_jiali_95():
    """真实文件：加力 95 → 1176 把，瓶颈含三合一/内管/钳体。"""
    r = calc_capacity("95", category="加力")
    assert r["总可产把数"] == 1176
    assert r["品类"] == "加力"
    assert r["规格"] == "95D"
    assert "加力钳体+外管+小钳口" in r["瓶颈件"]


@needs_data
def test_capacity_real_file_jiali_alias():
    """「加力钳」别名归一化 → 加力。"""
    r = calc_capacity("95", category="加力钳")
    assert r["总可产把数"] == 1176
    assert r["品类"] == "加力"


@needs_data
def test_capacity_real_file_jiali_132():
    """真实文件：加力 132 → 310 把，瓶颈三合一/小钳口。"""
    r = calc_capacity("132", category="加力")
    assert r["总可产把数"] == 310
    assert r["品类"] == "加力"
    assert r["规格"] == "132D"
    assert "加力小钳口" in r["瓶颈件"]


@needs_data
def test_capacity_real_file_jiali_all():
    """calc_capacity_all('加力') 返回全部 10 规格（按 _JIALI_SPECS 顺序）。"""
    results = calc_capacity_all("加力")
    specs = [x["规格"] for x in results]
    assert specs == ["80D", '18"', "95D", '24"', "108D", "132D", '36"', "152D", "195D", '48"']
    by_spec = {x["规格"]: x["总可产把数"] for x in results}
    # 真值锚点：80=116(内管镀锌)、95=1176(三合一/内管)、132=310(三合一/小钳口)
    assert by_spec["80D"] == 116
    assert by_spec["95D"] == 1176
    assert by_spec["132D"] == 310
