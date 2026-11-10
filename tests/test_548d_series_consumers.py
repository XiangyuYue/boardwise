"""548D3B：标签感知的合法 lane / yield（placement 侧直接消费者）。

机制窄测，不依赖 MCU 夹具能否出候选。夹具是手写的最小臂：宿主 H → A1 → A2，
外加可让位件 X 与两枚标签走廊。四条读到的真实行为：

* 空走廊：座位、lane、预留、yield 与未声明走廊时逐值相同（零漂移）；
* 整臂 lane move 落到标签默认盒上时不被采用（非法 lane 不能被重新接受）；
* 普通件让位两个方向都试，取合法的那一个；
* 两个方向都不合法时具名拒绝，且 hard 留给定名者（不静默落座）。

「seed lane 压标签 → 自动改到合法 lane」在本夹具上**不成立**，原因写在
`evidence/548D/series-seat-plan/label-aware-implementation.md` §3：座位预留仍是
宿主脚到第一件的 AABB（主代理裁决保留），它必然含宿主脚那一行，所以任何与 lane 0
两端件 box 相交的标签，AABB 也相交——lane 无法把它让开。可让开的是「移动带上去」，
这正是第三、四条测的行为。
"""

from __future__ import annotations

from types import SimpleNamespace

from boardwise.core.symbolprofile import SymbolPin, SymbolPose, SymbolProfile
from boardwise.engines import placement

ZERO = SymbolPose(rotation=0)


def _pin(number: str, tip: tuple[float, float], direction: str) -> SymbolPin:
    return SymbolPin(number=number, name=number, tip=tip, direction=direction)


def _profile(ref: str, pins: list[SymbolPin]) -> SymbolProfile:
    return SymbolProfile(
        symbol_ref=ref, title=ref, body=(-5.0, -5.0, 5.0, 5.0), pins=pins,
    )


HOST = _profile("HOST", [_pin("1", (10.0, 0.0), "right")])
ARM = _profile("ARM", [_pin("1", (-10.0, 0.0), "left"), _pin("2", (10.0, 0.0), "right")])
SINK = _profile("SINK", [_pin("1", (0.0, -10.0), "down")])
RISE = _profile("RISE", [_pin("1", (0.0, 10.0), "up")])


def _template() -> placement.SeriesSeatTemplate:
    return placement.SeriesSeatTemplate(
        branch_id="arm", host_part="H", host_token="1",
        first=placement.SeriesSeatArmPart("A1", from_token="1", middle_token="2"),
        second=placement.SeriesSeatArmPart("A2", middle_token="1", to_token="2"),
        first_pose=ZERO, second_pose=ZERO,
        progress=(1.0, 0.0), lateral=(0.0, 1.0),
        grid=5.0, lattice=(0.0, 0.0), clearance=0.0,
        yield_parts=frozenset(("X",)),
    )


def _corridor(part: str, token: str, direction: str, *, reach: float, net: str):
    return placement.LabelCorridor(
        part_id=part, token=token, local_direction=direction,
        width=40.0, height=10.0, reach_x=reach, reach_y=reach, net_id=net,
    )


def _request(corridors=(), extra=()) -> placement.PlacementInput:
    rows = [("H", HOST), ("A1", ARM), ("A2", ARM), ("X", ARM)] + list(extra)
    parts = tuple(
        placement.PlacementPart(part_id=name, profile=profile, poses=(ZERO,))
        for name, profile in rows
    )
    nets = (
        placement.PlacementNet(net_id="S", members=(("H", "1"), ("A1", "1")), cls="signal"),
        placement.PlacementNet(net_id="M", members=(("A1", "2"), ("A2", "1")), cls="signal"),
        placement.PlacementNet(net_id="T", members=(("A2", "2"), ("X", "1")), cls="signal"),
    )
    return placement.PlacementInput(
        parts=parts, nets=nets, series_templates=(_template(),),
        label_corridors=tuple(corridors),
        progress=(1.0, 0.0), lateral=(0.0, 1.0),
    )


def _seed(state: dict | None = None) -> placement._State:
    origins = {"H": (0.0, 0.0), "A1": (100.0, 0.0), "A2": (190.0, 0.0), "X": (0.0, 60.0)}
    origins.update(state or {})
    return placement._State(origins, {part: ZERO for part in origins})


def _plan(request, seed=None) -> placement.BoundSeriesSeatPlan:
    plans = placement._bind_series_plans(request, seed or _seed())
    assert plans and plans[0].seated, (
        plans[0].refusal.render() if plans else "no plan"
    )
    return plans[0]


# ------------------------------------------------------------------ 空走廊


def test_no_corridor_keeps_the_seat_on_its_seed_lane():
    plan = _plan(_request())
    assert plan.lane == 0.0, f"an empty corridor list moved the seat to {plan.lane}"
    assert plan.first_origin == (65.0, 0.0), plan.first_origin
    assert plan.second_origin == (155.0, 0.0), plan.second_origin
    assert plan.reserved_boxes and plan.yields == ()


def test_an_empty_corridor_list_is_the_historical_request():
    plain = placement.PlacementInput(
        parts=_request().parts, nets=_request().nets,
        series_templates=(_template(),),
        progress=(1.0, 0.0), lateral=(0.0, 1.0),
    )
    assert plain.label_corridors == ()
    assert placement._bind_series_plans(plain, _seed()) == placement._bind_series_plans(
        _request(), _seed()
    )
    assert placement._foreign_labels(plain, _seed().origins, _seed().poses,
                                     frozenset()) == ()


# ------------------------------------------------- 非法 lane 不被重新接受


def _label_above_the_lane() -> placement.LabelCorridor:
    """A name whose default box sits one lane-step above the arm's row."""
    return _corridor("Y", "1", "down", reach=0.0, net="ABOVE")


def test_a_whole_arm_lane_move_onto_a_label_is_not_taken():
    request = _request((_label_above_the_lane(),), extra=(("Y", SINK),))
    seed = _seed({"Y": (65.0, 28.0)})
    plan = _plan(request, seed)
    assert plan.lane == 0.0, plan.lane
    # Y's default box is (45, 13, 85, 23): the arm's part boxes at lane +15 reach
    # (60, 10, 70, 20), which is inside it. That shift must be refused, and the
    # other side must still be allowed — the domain is not a blanket "no move".
    assert not placement._lane_shift_is_legal(request, plan, (0.0, 15.0), seed)
    assert placement._lane_shift_is_legal(request, plan, (0.0, -5.0), seed)


def test_a_lane_move_back_toward_an_earlier_label_is_refused_symmetrically():
    request = _request((_label_above_the_lane(),), extra=(("Y", SINK),))
    seed = _seed({"Y": (65.0, 28.0)})
    plan = _plan(request, seed)
    assert not placement._lane_shift_is_legal(request, plan, (0.0, 15.0), seed)
    # ... and the reflection of the same shift is legal, so the refusal is about
    # the label and not about the axis.
    assert placement._lane_shift_is_legal(request, plan, (0.0, -5.0), seed)


# -------------------------------------------------- 让位：两个方向都要试


def _yield_plan(corridors, extra, origins):
    request = _request(corridors, extra)
    seed = _seed(origins)
    plan = placement._bind_series_plans(request, seed)[0]
    assert plan.seated, plan.refusal.render() if plan.refusal else "unseated"
    return request, seed, plan


def test_the_legal_way_out_wins_when_the_natural_one_is_a_label():
    # X sits at (65, 8), so the nearer way out is upward — straight into Y's
    # default box. The downward seat is free and must be the one taken.
    up = _corridor("Y", "1", "down", reach=0.0, net="UP_BLOCK")
    request, seed, plan = _yield_plan(
        (up,), (("Y", SINK),), {"X": (65.0, 8.0), "Y": (65.0, 28.0)},
    )
    yields = [item for item in plan.yields if item.part_id == "X"]
    assert yields and not yields[0].refusal, yields
    assert yields[0].target[1] < 8.0, (
        f"the yield went up into the label: {yields[0].target}"
    )
    assert yields[0].direction == (0.0, -1.0), yields[0].direction


def test_neither_way_out_is_a_seat_and_the_refusal_names_it():
    up = _corridor("Y", "1", "down", reach=0.0, net="UP_BLOCK")
    down = _corridor("Z", "1", "up", reach=0.0, net="DOWN_BLOCK")
    request, seed, plan = _yield_plan(
        (up, down), (("Y", SINK), ("Z", RISE)),
        {"X": (65.0, 8.0), "Y": (65.0, 28.0), "Z": (65.0, -27.0)},
    )
    yields = [item for item in plan.yields if item.part_id == "X"]
    assert yields and yields[0].refusal, (
        f"a yield with no legal seat was still applied: {yields}"
    )
    assert yields[0].target is None
    # The refused yield leaves the hard where it was: the caller names it.
    boxes = placement._boxes_of(request, seed)
    assert any(
        placement._overlap_area(boxes["X"], box) > 0.0 for box in plan.reserved_boxes
    ), "the hard violation left with the refused yield"


# ------------------------------------------------ 双几何：reserved vs guard


def _two_row_seed() -> placement._State:
    return placement._State(
        {"H": (0.0, 0.0), "A1": (65.0, 30.0), "A2": (155.0, 30.0), "X": (0.0, 60.0)},
        {part: ZERO for part in ("H", "A1", "A2", "X")},
    )


def test_the_guard_keeps_the_corner_the_wire_never_crosses():
    """A seat whose feet are on different rows: the AABB corner is guard-only."""
    plan = placement._bind_series_plans(_request(), _two_row_seed())[0]
    reserved, guard = list(plan.reserved_boxes), list(plan.guard_boxes)
    assert plan.host_path == (
        (10.0, 0.0), (15.0, 0.0), (15.0, 30.0), (55.0, 30.0),
    ), plan.host_path
    assert len(reserved) == 6, reserved    # 2 parts + 3 legs + middle
    assert len(guard) == 4, guard          # 2 parts + AABB + middle
    inside = (30.0, 15.0)                  # between the legs, inside the AABB

    def _holds(boxes):
        return any(b[0] < inside[0] < b[2] and b[1] < inside[1] < b[3] for b in boxes)

    assert _holds(guard), guard
    assert not _holds(reserved), reserved


def test_an_ordinary_branch_in_the_air_is_not_yielded():
    """The same corner cell: a movable signal branch there keeps its seed seat."""
    seed = placement._State(
        {"H": (0.0, 0.0), "A1": (65.0, 30.0), "A2": (155.0, 30.0), "X": (30.0, 15.0)},
        {part: ZERO for part in ("H", "A1", "A2", "X")},
    )
    plan = placement._bind_series_plans(_request(), seed)[0]
    assert plan.yields == (), plan.yields


def test_an_unyieldable_part_in_the_same_air_still_holds_its_hard():
    """A part the seat may not move is judged on the conservative guard."""
    request = placement.PlacementInput(
        parts=_request().parts, nets=_request().nets,
        series_templates=(placement.SeriesSeatTemplate(
            branch_id="arm", host_part="H", host_token="1",
            first=placement.SeriesSeatArmPart("A1", from_token="1", middle_token="2"),
            second=placement.SeriesSeatArmPart("A2", middle_token="1", to_token="2"),
            first_pose=ZERO, second_pose=ZERO,
            progress=(1.0, 0.0), lateral=(0.0, 1.0),
            grid=5.0, lattice=(0.0, 0.0), clearance=0.0,
            yield_parts=frozenset(),
        ),),
        progress=(1.0, 0.0), lateral=(0.0, 1.0),
    )
    seed = placement._State(
        {"H": (0.0, 0.0), "A1": (65.0, 30.0), "A2": (155.0, 30.0), "X": (30.0, 15.0)},
        {part: ZERO for part in ("H", "A1", "A2", "X")},
    )
    plan = placement._bind_series_plans(request, seed)[0]
    yields = [item for item in plan.yields if item.part_id == "X"]
    assert yields and yields[0].refusal, (
        f"a decoupling/locked part in the guard air was not refused: {yields}"
    )
    boxes = placement._boxes_of(request, seed)
    assert any(
        placement._overlap_area(boxes["X"], box) > 0.0 for box in plan.guard_boxes
    )


def test_a_label_off_the_planned_legs_keeps_the_seed_lane():
    """A name above the lane corridor but off the legs does not move the seat."""
    above = placement.LabelCorridor(
        part_id="X", token="1", local_direction="right",
        width=40.0, height=10.0, reach_x=30.0, reach_y=30.0, net_id="ABOVE",
    )
    plan = placement._bind_series_plans(_request((above,)), _two_row_seed())[0]
    assert plan.seated, plan.refusal.render() if plan.refusal else ""
    assert plan.lane == 30.0, plan.lane          # the seed lane, not a detour


# ------------------------------------- 画出来的导线必须是计划的那条路（draw 侧）


def _ctx():
    return SimpleNamespace(circuit=object())


class _Placed:
    def __init__(self, plan):
        self.series_plans = (plan,)


def test_the_compiler_accepts_a_wire_that_runs_on_the_plan_path(monkeypatch):
    from boardwise.engines import drawcompiler as dc

    plan = placement._bind_series_plans(_request(), _two_row_seed())[0]
    monkeypatch.setattr(dc, "_part_nets", lambda circuit, part_id: {"1": "S"})
    segment = dc.LayoutSegment(net="S", points=list(plan.host_path))
    assert dc._series_path_mismatches(_ctx(), _Placed(plan), [segment]) == ()


def test_the_compiler_names_a_wire_that_takes_another_way(monkeypatch):
    from boardwise.engines import drawcompiler as dc

    plan = placement._bind_series_plans(_request(), _two_row_seed())[0]
    monkeypatch.setattr(dc, "_part_nets", lambda circuit, part_id: {"1": "S"})
    detour = dc.LayoutSegment(
        net="S", points=[(10.0, 0.0), (40.0, 0.0), (40.0, 50.0),
                        (55.0, 50.0), (55.0, 30.0)],
    )
    problems = dc._series_path_mismatches(_ctx(), _Placed(plan), [detour])
    assert problems, "a wire that leaves the plan's path was accepted"
    assert "host lead" in problems[0]


# ------------------------------------- topology 的**直接**消费者（placement.place）


def test_the_search_consumer_seats_the_arm_with_no_mismatch():
    """The topology round's own entry point, not a re-implementation of it."""
    from dataclasses import replace

    request = replace(_request(), iterations=60, restarts=1)
    result = placement.place(request)
    plan = result.series_plan("arm")
    assert plan is not None, "the search returned no plan for a declared arm"
    assert plan.seated, plan.refusal.render() if plan.refusal else "unseated"
    assert result.series_mismatches() == (), result.series_mismatches()
    assert not [
        term.name for term in result.hard if term.name.startswith("series-")
    ], [term.render() for term in result.hard]


# ------------------------- 通道与真实导线的连通性（draw 侧，逐段几何）


class _Circuit:
    pass


def test_same_net_runs_that_touch_are_one_connected_figure():
    from boardwise.engines import drawcompiler as dc

    one = dc.LayoutSegment(net="S", points=[(0.0, 0.0), (40.0, 0.0)])
    two = dc.LayoutSegment(net="S", points=[(40.0, 0.0), (40.0, 30.0)])
    pads = [(0.0, 0.0), (40.0, 30.0)]
    assert dc._runs_join([one, two], pads)
    assert dc._runs_join([one, two], pads + [(90.0, 90.0)]) is False


def test_same_net_runs_that_never_touch_are_not_a_connection():
    from boardwise.engines import drawcompiler as dc

    left = dc.LayoutSegment(net="S", points=[(0.0, 0.0), (40.0, 0.0)])
    right = dc.LayoutSegment(net="S", points=[(80.0, 0.0), (120.0, 0.0)])
    assert not dc._runs_join([left, right], [(0.0, 0.0), (120.0, 0.0)])


def test_the_arm_channel_is_the_from_net_and_the_middle_net(monkeypatch):
    from boardwise.engines import drawcompiler as dc

    plan = placement._bind_series_plans(_request(), _two_row_seed())[0]
    monkeypatch.setattr(
        dc, "_part_nets",
        lambda circuit, part_id: {"1": "S", "2": "M"} if part_id in ("H", "A1") else {},
    )
    monkeypatch.setattr(
        dc, "_pin_point",
        lambda ctx, part, token, poses, origins: {
            ("A1", "2"): (75.0, 30.0), ("A2", "1"): (145.0, 30.0),
        }.get((part, token)),
    )
    placed = _Placed(plan)
    placed.poses = {part: ZERO for part in ("H", "A1", "A2", "X")}
    placed.origins = {}
    channels = dc._series_channels(_ctx(), placed)
    assert set(channels) == {"S", "M"}, channels
    assert list(channels["S"][0].points) == list(plan.host_path)
    assert list(channels["M"][0].points) == [(75.0, 30.0), (145.0, 30.0)]
