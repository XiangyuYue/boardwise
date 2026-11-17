"""548D3D：强制 topology 轮的普通支路分排接入（真实读数，不粉饰）。

`_topology_placement` 在 page anchor 之后、series plan 翻译与关系闸之前，用
**同一个** `_spread_band_collisions` 分排普通同类支路，`exclude` 恰为所有
`seriesBranches` 臂内件（臂的 origin/pose 不得漂移）。

本文件把 topology 轮逼成唯一一轮（`_variants`/`_widened_variants` 都清空），
记录这一刻的真实答案：搜索自己已经保证普通件互不重叠，所以同一分排函数
**零移动**（它的契约就是“不重叠的组一个字节都不动”）；本轮仍然没有候选，
首败是 `S3` 站在臂的保留走廊里、绑定器每个 lane 的让位都无座。这一条是
**现状**的实测，不是通过声明；通过与否由首败的类别/对象/名字判定。
"""

from __future__ import annotations

from boardwise.engines import drawcompiler as dc

import test_548d_series_reservation as fixture


def _forced_topology():
    circuit, presentation = fixture._documents(c1_flag_room=True)
    ground = frozenset(
        dc._ground_domain(net.id) for net in circuit.nets if net.cls == "gnd"
    )
    real_variants, real_widened = dc._variants, dc._widened_variants
    dc._variants = lambda *_args: []
    dc._widened_variants = lambda *_args: []
    try:
        result = dc.compile(
            circuit, presentation, fixture._book(), fixture._budget(),
            page_ground_domains=ground,
        )
    finally:
        dc._variants, dc._widened_variants = real_variants, real_widened
    return result


def _captured_topology(monkeypatch):
    """强迫 topology 轮，并把这一轮的 `(ctx, variant)` 也带回来（548D3D-R）。"""
    captured: dict[str, object] = {}
    real_build = dc._build_candidate

    def record(ctx, variant, label_fallbacks=None):
        captured["ctx"], captured["variant"] = ctx, variant
        return real_build(ctx, variant, label_fallbacks)

    monkeypatch.setattr(dc, "_build_candidate", record)
    result = _forced_topology()
    return captured["ctx"], captured["variant"], result


def test_the_own_seat_fails_outside_s3_at_the_label_conductor(monkeypatch):
    """548D3D-R 实测：binder 自己的座位**不是**死在 S3，而是死在标签盒压在导体上。

    `_build_candidate` 先构建枚举出来的联合座位、最后构建 binder 自己的座位，
    被记进失败报告的是**第一个**座位的拒绝，所以报告里的 `S3`/`led1_series`
    不等于页面根因。新夹具（`c1_flag_room=True`，C1 让出旗位）上，binder 自己的
    座位已经过得了 069 旗闸，它的真实拒绝是 `labels[3]`：`KEY1` 的盒被一条 3V3
    导体穿过，且本地标签通道跑完后仍无空位。旧断言要求 `GND` + `R1.2 4/5`
    （旧布局死结的读数），已不适用；保留的机制是「own seat 与 S3 无关」。
    """
    ctx, variant, result = _captured_topology(monkeypatch)
    assert not result.candidates
    placed, placement_failure = dc._place(ctx, variant)
    assert placement_failure is None and placed is not None
    built, refusal, _violations = dc._build_one_variant(
        ctx, variant, [], placement_override=placed,
    )
    assert built is None, "the binder's own seat built; this claim is stale"
    assert refusal.category == dc.FAILURE_LAYOUT_UNSAT, refusal.category
    assert refusal.subject == "labels[3]", refusal.subject
    assert "conductor through its box" in refusal.detail
    assert "KEY1" in refusal.detail and "[194.5, 19, 225.5, 28]" in refusal.detail
    assert "refused rather than delivered" in refusal.detail
    assert "S3" not in refusal.detail, (
        "the binder's own seat has no S3 conflict; if it does, the measured "
        "separation between the two refusals is gone"
    )


def test_the_build_spends_its_four_seats_on_joint_lanes(monkeypatch):
    """枚举出来的座位恰是这四个联合 lane，四个**全部被拒**（读数：两类拒因各二）。

    旧活塞时四个 lane 都卡在 `S3` 保留盒；新夹具（`c1_flag_room=True`）上实测
    分裂成两类，机制不变——**四个联合 lane 没有一个能建出来**：
    * lane `-5;10` 与 `-10;10`：`$.seriesBranches[0] (led1_series)` +
      「reserved boxes still hold ordinary parts after the binder's yields」，
      且点名的是 `S2` / `S1` 让不出保留盒（这正是 S3 那一族闸）；
    * lane `0;15` 与 `0;20`：`$.seriesBranches` +
      「the drawn host lead is not the arm's channel … LED1_K is not drawn at all」，
      并核对臂的引线不存在（`so the arm's lead does not exist`）。
    """
    ctx, _variant, _result = _captured_topology(monkeypatch)
    placed, placement_failure = dc._place(ctx, _variant)
    assert placement_failure is None and placed is not None
    attempts = dc._series_candidate_placements(ctx, placed)
    assert [label for label, _placement in attempts] == [
        "led1_series lane 0; led2_series lane 15",
        "led1_series lane -5; led2_series lane 10",
        "led1_series lane 0; led2_series lane 20",
        "led1_series lane -10; led2_series lane 10",
    ], [label for label, _placement in attempts]
    reserved_box, host_lead = [], []
    for label, attempt in attempts:
        built, refusal, _violations = dc._build_one_variant(
            ctx, _variant, [], placement_override=attempt,
        )
        assert built is None, label
        assert refusal.category == dc.FAILURE_LAYOUT_UNSAT, (label, refusal.category)
        if "reserved boxes still hold ordinary parts" in refusal.detail:
            assert refusal.subject == "$.seriesBranches[0] (led1_series)", refusal.subject
            assert "neither way out of the reserved box is a seat" in refusal.detail
            reserved_box.append(label)
        else:
            assert refusal.subject == "$.seriesBranches", refusal.subject
            assert "the drawn host lead is not the arm's channel" in refusal.detail
            assert "LED1_K is not drawn at all" in refusal.detail
            assert "so the arm's lead does not exist" in refusal.detail
            host_lead.append(label)
    assert len(reserved_box) == 2 and len(host_lead) == 2, (reserved_box, host_lead)
    assert reserved_box == [
        "led1_series lane -5; led2_series lane 10",
        "led1_series lane -10; led2_series lane 10",
    ], reserved_box


def test_the_topology_round_spreads_ordinary_branches_with_the_shared_pass(
    monkeypatch,
):
    """分排调用点真的在 topology 轮里，且臂内件全部在 exclude 里。"""
    calls: list[frozenset[str]] = []
    real_spread = dc._spread_band_collisions

    def record(ctx, origins, poses, exclude, reserved=()):
        calls.append(frozenset(exclude))
        return real_spread(ctx, origins, poses, exclude, reserved=reserved)

    monkeypatch.setattr(dc, "_spread_band_collisions", record)
    result = _forced_topology()
    assert calls == [frozenset({"R2", "D1", "R3", "D2"})], (
        "the topology round did not ask the shared spread for exactly the arm "
        f"parts as exclude: {calls}"
    )
    assert not result.candidates, (
        "the fixture gained a topology candidate; update this test's measured "
        "claim instead of leaving a stale refusal here"
    )


def test_forced_topology_still_refuses_with_the_s3_reserved_boxes():
    """实测首败（新夹具）：host lead 没画出来，尾句点名「refused (5)」的座位。

    旧读数首败是 `$.seriesBranches[0] (led1_series)` + `S3`；`c1_flag_room=True` 之后
    GND 旗闸不再抢戏，首败上移成 `$.seriesBranches`（两条臂的 host lead 都没画出来），
    尾句仍是“每个绑定座位都被拒 (5)”，而**座位级**的拒因里有两条正是 S3 那一族
    （`reserved boxes still hold ordinary parts`）。机制不变：forced topology 仍零候选、
    仍拒在“臂的保留走廊 + host lead”这一层。
    """
    result = _forced_topology()
    assert not result.candidates, "forced topology produced a candidate"
    failure = result.failures[0]
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT
    assert failure.subject == "$.seriesBranches"
    assert "the drawn host lead is not the arm's channel" in failure.detail
    assert "LED1_K is not drawn at all" in failure.detail
    assert "was refused (5)" in failure.detail
