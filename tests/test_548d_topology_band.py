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
    circuit, presentation = fixture._documents()
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


def test_the_own_seat_fails_at_the_gnd_cluster_not_at_s3(monkeypatch):
    """548D3D-R 实测：S3 只是首个被构建座位的拒绝，binder 自己的座位死在别处。

    `_build_candidate` 先构建枚举出来的联合座位、最后构建 binder 自己的座位。
    被记进失败报告的是**第一个**座位的拒绝，所以报告里的 `S3` 不等于页面根因：
    binder 自己的座位没有 S3 冲突，它死在 `R1.2` 的 GND 簇 `4/5` 无旗位。
    """
    ctx, variant, result = _captured_topology(monkeypatch)
    assert not result.candidates
    placed, placement_failure = dc._place(ctx, variant)
    assert placement_failure is None and placed is not None
    built, refusal, _violations = dc._build_one_variant(
        ctx, variant, [], placement_override=placed,
    )
    assert built is None, "the binder's own seat built; this claim is stale"
    assert refusal.subject == "GND", refusal.detail
    assert "R1.2" in refusal.detail and "4/5" in refusal.detail, refusal.detail
    assert "S3" not in refusal.detail, (
        "the binder's own seat has no S3 conflict; if it does, the measured "
        "separation between the two refusals is gone"
    )


def test_the_build_spends_its_four_seats_on_joint_lanes(monkeypatch):
    """枚举出来的座位恰是这四个联合 lane，四个都卡在 `S3`（548D3D-R 实测）。"""
    ctx, _variant, _result = _captured_topology(monkeypatch)
    placed, placement_failure = dc._place(ctx, _variant)
    assert placement_failure is None and placed is not None
    attempts = dc._series_candidate_placements(ctx, placed)
    assert [label for label, _placement in attempts] == [
        "led1_series lane 0; led2_series lane -10",
        "led1_series lane 0; led2_series lane -5",
        "led1_series lane 5; led2_series lane 0",
        "led1_series lane -5; led2_series lane -10",
    ], [label for label, _placement in attempts]
    for _label, attempt in attempts:
        built, refusal, _violations = dc._build_one_variant(
            ctx, _variant, [], placement_override=attempt,
        )
        assert built is None
        assert refusal.category == dc.FAILURE_LAYOUT_UNSAT
        assert refusal.subject == "$.seriesBranches[0] (led1_series)"
        assert "S3" in refusal.detail


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


def test_forced_topology_still_refuses_at_the_s3_reserved_box():
    """实测首败：S3 让不出臂的保留走廊，5 个 lane 座位全拒。"""
    result = _forced_topology()
    assert not result.candidates, "forced topology produced a candidate"
    failure = result.failures[0]
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT
    assert failure.subject == "$.seriesBranches[0] (led1_series)"
    assert "S3" in failure.detail
    assert "reserved boxes still hold ordinary parts" in failure.detail
    assert "was refused (5)" in failure.detail
