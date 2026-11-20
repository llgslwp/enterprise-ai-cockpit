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
    COL_H,
    COL_I,
    _calc_capacity_core,
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
