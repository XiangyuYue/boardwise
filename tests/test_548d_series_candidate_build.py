"""548D3B：多臂候选级 SeriesSeatPlan 的构建合同。

三件事只在这里钉：

* 一个被**真实构建**拒绝的座位不会结束这个 variant —— 下一个合法座位接着建，
  交付的是第一个真正过完全部检查的图（`_Built.series_trials` 逐条记下被试座位和首败）；
* 全部座位都被拒时，拒绝语具名列出每一个被试座位（lane + 原因），不是“no legal layout”；
* 候选生成只碰自己的新 `_Placement`：绑定结果与 `ctx.topology` 不被改写；
  未声明/单臂页面一律不生成候选、构建次数不变。

页面沿用 `test_548d_series_reservation.py` 内联的 548D MCU 岛（14 件、31 网、两条
`seriesBranches`），不新增夹具、不写坐标、不碰 userLocks。
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, "tests")

import test_548d_series_reservation as base  # noqa: E402

from boardwise.engines import drawcompiler as dc  # noqa: E402
from boardwise.engines import placement  # noqa: E402


@pytest.fixture(autouse=True)
def _documents_cache_untouched():
    """每次编译都清一次缓存再重编；跑完把页面缓存还原，别毒到同会话的其它文件。"""
    saved = dict(base._CACHE)
    yield
    base._CACHE.clear()
    base._CACHE.update(saved)


def _compile_fresh(declared: bool = True):
    base._CACHE.pop(declared, None)
    return base._compiled(declared)


def test_a_refused_seat_is_rebuilt_on_the_next_one(monkeypatch):
    """第一个座位被真实构建拒绝时，下一个座位被真正建出来并交付。"""
    real_build = dc._build_one_variant
    real_candidates = dc._series_candidate_placements
    builds: list[str] = []
    purity: list[str] = []

    def spy_candidates(ctx, placed):
        before = tuple(
            (plan.branch_id, plan.lane, plan.first_origin, plan.second_origin)
            for plan in placed.series_plans
        )
        topology_before = ctx.topology
        answer = real_candidates(ctx, placed)
        after = tuple(
            (plan.branch_id, plan.lane, plan.first_origin, plan.second_origin)
            for plan in placed.series_plans
        )
        if before != after:
            purity.append("the base bound plans were rewritten")
        if ctx.topology is not topology_before:
            purity.append("ctx.topology was written by the candidate builder")
        for _label, placement in answer:
            if not placement.series_plans:
                purity.append("a candidate carries no bound plan")
        return answer

    refused_variants: set[str] = set()

    def spy_build(ctx, variant, fallbacks, **kwargs):
        if variant.label not in refused_variants:
            refused_variants.add(variant.label)
            builds.append("refused")
            return None, dc._series_seat_refusal(
                "$.seriesBranches",
                "the first bound seat is refused by the router's own test",
                "seat the arm again",
            ), []
        builds.append("built")
        return real_build(ctx, variant, fallbacks, **kwargs)

    monkeypatch.setattr(dc, "_series_candidate_placements", spy_candidates)
    monkeypatch.setattr(dc, "_build_one_variant", spy_build)
    _circuit, _presentation, result = _compile_fresh(True)

    assert not purity, "\n  ".join(purity)
    assert builds[0] == "refused" and len(builds) >= 2, builds
    assert result.ok and result.candidates, (
        "the page stopped drawing once its first seat was refused: "
        f"{[(item.category, item.subject) for item in result.failures]}"
    )
    assert "built" in builds, builds
    # 被试座位的具名记录由 `test_every_tried_seat_is_named_when_all_are_refused`
    # 与 548D 的真实拒绝档覆盖；这里钉的是“被拒之后还继续建”，不是哪一档获胜。


def test_every_tried_seat_is_named_when_all_are_refused(monkeypatch):
    """全败时拒绝语逐条列出被试座位（lane + 首败），不是一句 no legal layout。"""

    def always_refused(ctx, variant, fallbacks, **kwargs):
        return None, dc._series_seat_refusal(
            "$.seriesBranches", "measured refusal", "seat the arm again",
        ), []

    monkeypatch.setattr(dc, "_build_one_variant", always_refused)
    _circuit, _presentation, result = _compile_fresh(True)

    assert not result.candidates
    details = [item.detail for item in result.failures if "every bound seat" in item.detail]
    assert details, [(item.category, item.detail[:80]) for item in result.failures]
    detail = details[0]
    assert "led1_series lane" in detail, detail
    assert "led2_series lane" in detail, detail
    assert detail.count("refused — ") >= 2, detail
    assert "the binder's own seat" in detail, detail


def test_a_page_with_no_arm_or_one_arm_builds_as_before(monkeypatch):
    """未声明页面：不生成候选，拒绝形状不变；单臂：候选枚举直接返回空。"""
    builds: list[int] = []
    seen: list[object] = []
    real_build = dc._build_one_variant

    def counting(ctx, variant, fallbacks, **kwargs):
        builds.append(1)
        return real_build(ctx, variant, fallbacks, **kwargs)

    def spy_candidates(ctx, placed):
        seen.append(placed)
        return []

    monkeypatch.setattr(dc, "_build_one_variant", counting)
    monkeypatch.setattr(dc, "_series_candidate_placements", spy_candidates)
    _circuit, _presentation, result = _compile_fresh(False)

    assert not result.candidates
    assert result.failures and result.failures[0].subject == "GND"
    assert "seriesBranches" not in result.failures[0].detail
    assert not seen, "the undeclared page asked for series candidates"
    assert builds, "the undeclared page built nothing"

    single = SimpleNamespace(
        presentation=SimpleNamespace(series_branches=(SimpleNamespace(id="one"),)),
    )
    assert dc._series_candidate_placements(single, SimpleNamespace(series_plans=())) == []


# ---------------------------------------- 548D3B 交卷批：pair band / 联合组合 / host 验收


def test_two_arms_are_the_pair_band_opt_in_and_a_series_relation_is_not_a_sibling():
    """≥2 臂 = pair-band 显式 opt-in；臂自己的顺序关系不算“兄弟已排序”。"""
    from types import SimpleNamespace

    one = SimpleNamespace(id="one")
    two = SimpleNamespace(id="two")
    band = dc._pair_bands(SimpleNamespace(
        presentation=SimpleNamespace(series_branches=(one, two)),
    ))
    assert band is True
    untouched = dc._pair_bands(SimpleNamespace(
        presentation=SimpleNamespace(
            series_branches=(), text_placement="", service_layout=None,
        ),
    ))
    assert untouched is False

    branch = SimpleNamespace(kind="branch", owner="U1")
    series = SimpleNamespace(
        subject="D1", object="R2",
        reason=dc.SERIES_RELATION_REASON + "'led1_series' reads R2 -> LED1_A -> D1",
    )
    sibling = SimpleNamespace(
        subject="C1", object="C2", reason="098 sec.2: C1 and C2 are the same service",
    )
    ctx = SimpleNamespace(
        binding=SimpleNamespace(constraints=[series, sibling]),
        slots={"D1": branch, "R2": branch, "C1": branch, "C2": branch},
    )
    assert dc._declared_sibling_owners(ctx) == frozenset({"U1"}), (
        "the series relation was read as a sibling ordering"
    )
    ctx.binding.constraints = [series]
    assert dc._declared_sibling_owners(ctx) == frozenset(), (
        "a series relation still took its owner out of the band reading"
    )


def test_the_joint_combinations_mix_arms_and_order_by_total_travel():
    """联合组合：按总 |lane| 排序、声明顺序确定、含 led1=5/led2=0 这类混合档。"""
    combos = dc._joint_lane_combinations(
        [("led1_series", (0.0, -105.0, 5.0, -5.0)),
         ("led2_series", (-110.0, 0.0, -10.0))],
        7,
    )
    assert combos, "the joint product is empty"
    assert combos[0] == {"led1_series": 0.0, "led2_series": 0.0}
    earlier = [entry for entry in combos if entry["led1_series"] == 5.0
               and entry["led2_series"] == 0.0]
    assert earlier, f"the mixed combination is missing: {combos}"
    totals = [sum(abs(value) for value in entry.values()) for entry in combos]
    assert totals == sorted(totals), totals
    seeds = {"led1_series": -105.0, "led2_series": -110.0}
    assert seeds not in combos, (
        "the all-seed combination is a candidate; it is the caller's last attempt"
    )
    assert combos == dc._joint_lane_combinations(
        [("led1_series", (0.0, -105.0, 5.0, -5.0)),
         ("led2_series", (-110.0, 0.0, -10.0))],
        7,
    ), "the joint order is not deterministic"


def test_the_host_channel_accepts_an_equal_length_staircase(monkeypatch):
    """等长但更简单的直角弯可以过；长绕和出包络被拒。"""
    from types import SimpleNamespace

    import test_548d_series_consumers as consumers

    plan = placement._bind_series_plans(
        consumers._request(), consumers._two_row_seed(),
    )[0]
    assert plan.seated
    seed = consumers._two_row_seed()
    host = plan.host_path[0]
    foot = plan.host_path[-1]
    placed = SimpleNamespace(
        series_plans=(plan,), poses=seed.poses, origins=seed.origins,
    )
    ctx = SimpleNamespace(
        circuit=object(),
        profile=lambda part_id: consumers._request().part(part_id).profile,
    )
    net = "S"
    monkeypatch.setattr(dc, "_part_nets", lambda circuit, part_id: {"1": net})

    def segment(points):
        return dc.LayoutSegment(net=net, points=points)

    simpler = [
        (host[0], host[1]), (host[0], foot[1]), (foot[0], foot[1]),
    ]
    accepted = dc._series_host_channel_problems(ctx, placed, [segment(simpler)])
    assert accepted == (), accepted

    detour = [
        (host[0], host[1]), (host[0], host[1] - 120.0),
        (foot[0] + 200.0, host[1] - 120.0), (foot[0] + 200.0, foot[1]),
        (foot[0], foot[1]),
    ]
    refused = dc._series_host_channel_problems(ctx, placed, [segment(detour)])
    assert refused, "a lead that goes round the page was accepted"
    assert "travels" in refused[0] or "envelope" in refused[0], refused

    open_run = dc._series_host_channel_problems(
        ctx, placed, [segment([host, (host[0], host[1] + 30.0)])],
    )
    assert open_run and "does not reach" in open_run[0], open_run
