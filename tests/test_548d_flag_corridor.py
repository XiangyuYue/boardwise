"""548D3G 第一批：相邻旗脚的联合座位（placement 内部合同）。

WiFi `J2.3V3` 与 `J2.GND` 是同侧相邻脚，各自单独能坐、合起来没有合法候选：
两个旗盒、两段旗引线与去耦支路争用同一段出走空间。本批只做 draw 内部
`FlagCorridorTemplate` / `BoundFlagCorridorPlan` 与 binder，不接生产 compile
（`drawcompiler.py` 不动），也不宣称 WiFi 已通过。

合同来自 `evidence/548D/full-page/flag-corridor-design.md` 与
`tasks/548_drawing_capability_ladder.md` §22A，按主代理修订版而不是规划者初稿：

* 候选只有既有旗档/真实几何（`FlagCorridorCandidate` 的 `(anchor, rotation,
  lead, box)`，盒形状等同 `FlagReservation.box`），不新 reach、不加坐标；
* 普通支路**包括服务件**可以让位，让位距离由真实盒算出，没有 2 格上限；
* 锁 / 服务关系 / 无合法档一律具名拒绝，不静默退回逐脚搜索；
* 默认空 tuple 不绑定、不加成本、不改 seed/moves/输出；
* 旧 `FlagReservation` 与 series 合同原样保留。

夹具是内联的最小电路：连接器 `J2`（3V3/GND 同侧相邻脚）、一个去耦电容 `C1`
（服务支路）、一个电阻 `R1`。全部坐标由测试自己写，不读 evidence 文件。
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from boardwise.core.symbolprofile import SymbolPin, SymbolPose, SymbolProfile
from boardwise.engines import placement as pl
from boardwise.engines.placement import (
    BoundFlagCorridorPlan,
    FlagCorridorCandidate,
    FlagCorridorPin,
    FlagCorridorTemplate,
    FlagReservation,
    PlacementError,
    PlacementInput,
    PlacementNet,
    PlacementPart,
    PlacementResult,
    SeriesSeatYield,
    ServicePinGap,
    bind_flag_corridors,
    part_box,
    place,
    place_flag_corridors,
)

POSE = SymbolPose(rotation=0, mirror=False)


def _profile(ref: str, body: tuple[float, float, float, float], pins):
    return SymbolProfile(
        symbol_ref=ref, body=body,
        pins=[
            SymbolPin(number=number, tip=tip, name=name, direction=direction)
            for number, tip, name, direction in pins
        ],
        poses=[POSE],
    )


#: The connector: three same-side pins, `3V3` and `GND` adjacent — the WiFi shape.
J2 = _profile("CONN-3", (-40.0, -30.0, 40.0, 30.0), (
    ("1", (40.0, 10.0), "3V3", "right"),
    ("2", (40.0, 0.0), "GND", "right"),
    ("3", (40.0, -10.0), "SIG", "right"),
))
C1 = _profile("C0603", (-8.0, -4.0, 8.0, 4.0), (
    ("1", (0.0, 12.0), "A", "up"),
    ("2", (0.0, -12.0), "B", "down"),
))
R1 = _profile("R0603", (-6.0, -14.0, 6.0, 14.0), (
    ("1", (0.0, 20.0), "A", "up"),
    ("2", (0.0, -20.0), "B", "down"),
))

PARTS = (
    PlacementPart("J2", J2, (POSE,)),
    PlacementPart("C1", C1, (POSE,)),
    PlacementPart("R1", R1, (POSE,)),
)

NETS = (
    PlacementNet("3V3", (("J2", "1"), ("C1", "1"), ("R1", "1")), "power"),
    PlacementNet("GND", (("J2", "2"), ("C1", "2")), "gnd"),
    PlacementNet("SIG", (("J2", "3"), ("R1", "2")), "signal"),
)

POSES = {part.part_id: POSE for part in PARTS}

#: `C1` far away: the corridor can be seated without asking anyone to move.
FAR = {"J2": (0.0, 0.0), "C1": (0.0, 200.0), "R1": (0.0, 300.0)}
#: `C1` standing on the 3V3 flag's room: the yield case.
ON_FLAG = {"J2": (0.0, 0.0), "C1": (55.0, 2.0), "R1": (0.0, 300.0)}


def _seat_right(box, anchor=(30.0, 0.0), lead=((0.0, 0.0), (30.0, 0.0))):
    return FlagCorridorCandidate(
        anchor=anchor, rotation=0.0, lead=lead, box=box,
        source="flag-pin-right",
    )


#: A: the first real grade — the flag leaves along the pin's own direction.
CAND_A = _seat_right((0.0, -8.0, 60.0, 8.0))
#: B: the alternate grade one row down — same pin, real geometry, no new reach.
CAND_B = _seat_right(
    (0.0, -30.0, 60.0, -14.0),
    anchor=(30.0, -20.0),
    lead=((0.0, 0.0), (0.0, -20.0), (30.0, -20.0)),
)


def _corridor(pins=None, **kwargs):
    return FlagCorridorTemplate(
        group_id="j2_rail_gnd",
        host_part="J2",
        pins=pins or (
            FlagCorridorPin("J2", "1", "3V3", (CAND_A,)),
            FlagCorridorPin("J2", "2", "GND", (CAND_A, CAND_B)),
        ),
        **kwargs,
    )


def _request(corridors=(), **kwargs):
    return PlacementInput(
        parts=PARTS, nets=NETS, flag_corridors=corridors, **kwargs,
    )


# ------------------------------------------------------------- default empty


def test_default_empty_corridors_is_the_historical_request():
    """No corridor: no field, no plan, no cost, same seed and same answer."""
    request = _request()
    assert request.flag_corridors == ()
    explicit = _request(corridors=())
    small = dict(iterations=250, restarts=2)
    plain = place(replace(request, **small))
    again = place(replace(explicit, **small))
    assert plain.to_jsonable() == again.to_jsonable()
    assert "flagCorridors" not in plain.to_jsonable()
    assert plain.flag_corridors == ()
    assert plain.flag_corridor_mismatches() == ()
    assert (plain.iterations, plain.accepted, plain.seed) == (
        again.iterations, again.accepted, again.seed,
    )
    assert [item.to_jsonable() for item in plain.costs] == [
        item.to_jsonable() for item in again.costs
    ]


def test_old_constructors_keep_their_meaning():
    """The two contracts are appended last; every older call still reads."""
    request = PlacementInput(PARTS, NETS, ())
    assert request.flag_corridors == ()
    assert request.series_templates == ()
    assert request.label_corridors == ()
    result = PlacementResult(
        origins={"J2": (0.0, 0.0)}, poses={"J2": POSE},
    )
    assert result.flag_corridors == ()
    assert result.flag_corridor("j2_rail_gnd") is None
    assert result.flag_corridor_mismatches() == ()
    assert "flagCorridors" not in result.to_jsonable()


def test_empty_templates_bind_nothing():
    assert bind_flag_corridors(_request(), FAR, POSES) == ()
    plans, state = place_flag_corridors(_request(), (), FAR, POSES)
    assert plans == ()
    assert state.origins == FAR


# --------------------------------------------------------- joint seat choice


def test_adjacent_pins_take_a_joint_pair_without_overlap():
    plans = bind_flag_corridors(_request((_corridor(),)), FAR, POSES)
    assert len(plans) == 1
    plan = plans[0]
    assert plan.seated, plan.refusal.render() if plan.refusal else ""
    assert plan.group_id == "j2_rail_gnd"
    assert [seat.net_id for seat in plan.seats] == ["3V3", "GND"]
    first, second = plan.seats
    assert first.box == (40.0, 2.0, 100.0, 18.0)
    # The `GND` pin's first grade would sit straight on the `3V3` box; the joint
    # selection takes the alternate grade instead of seating one pin at a time.
    assert second.box == (40.0, -30.0, 100.0, -14.0)
    assert pl._overlap_area(first.box, second.box) == 0.0
    assert plan.mismatches(FAR, POSES) == ()
    assert plan.owned_parts() == frozenset({"J2"})
    assert plan.reserved_boxes[:2] == (first.box, second.box)
    assert plan.lead_paths == (first.lead, second.lead)


def test_same_net_flags_may_share_their_box():
    """The same-net exemption is real, and it is the only exemption."""
    shared = (
        FlagCorridorPin("J2", "1", "3V3", (CAND_A,)),
        FlagCorridorPin("J2", "2", "3V3", (CAND_A,)),
    )
    nets = (
        PlacementNet("3V3", (("J2", "1"), ("J2", "2"), ("R1", "1")), "power"),
        PlacementNet("SIG", (("J2", "3"), ("R1", "2")), "signal"),
    )
    request = PlacementInput(
        parts=PARTS, nets=nets,
        flag_corridors=(_corridor(pins=shared),),
    )
    plan = bind_flag_corridors(request, FAR, POSES)[0]
    assert plan.seated
    assert pl._overlap_area(plan.seats[0].box, plan.seats[1].box) > 0.0


# --------------------------------------------------------- box/lead exclusion


def test_a_lead_running_into_the_other_box_is_refused():
    a2 = _seat_right(
        (0.0, -8.0, 40.0, 8.0), anchor=(0.0, 1.0),
        lead=((0.0, 0.0), (0.0, 1.0)),
    )
    bad = _seat_right(
        (42.0, 0.0, 82.0, 16.0),
        anchor=(35.0, 5.0),
        lead=((0.0, 0.0), (35.0, 0.0), (35.0, 5.0)),
    )
    pins = (
        FlagCorridorPin("J2", "1", "3V3", (a2,)),
        FlagCorridorPin("J2", "2", "GND", (bad,)),
    )
    plan = bind_flag_corridors(_request((_corridor(pins=pins),)), FAR, POSES)[0]
    assert not plan.seated
    assert plan.refusal is not None
    assert plan.refusal.category == pl.FLAG_CORRIDOR_REFUSAL
    assert "runs into" in plan.refusal.detail
    assert plan.mismatches(FAR, POSES) != ()


def test_crossing_leads_are_refused():
    a2 = _seat_right(
        (0.0, -8.0, 40.0, 8.0), anchor=(60.0, 0.0),
        lead=((0.0, 0.0), (60.0, 0.0)),
    )
    crossing = _seat_right(
        (45.0, 20.0, 85.0, 36.0),
        anchor=(50.0, 20.0),
        lead=((0.0, 0.0), (50.0, 0.0), (50.0, 20.0)),
    )
    pins = (
        FlagCorridorPin("J2", "1", "3V3", (a2,)),
        FlagCorridorPin("J2", "2", "GND", (crossing,)),
    )
    plan = bind_flag_corridors(_request((_corridor(pins=pins),)), FAR, POSES)[0]
    assert not plan.seated
    assert "leads cross" in plan.refusal.detail


def test_an_alternate_grade_is_taken_when_the_first_one_collides():
    """The bad grade is legal on its own; the pair is what refuses it."""
    bad = _seat_right(
        (0.0, 20.0, 60.0, 36.0),
        anchor=(10.0, 20.0),
        lead=((0.0, 0.0), (10.0, 0.0), (10.0, 20.0)),
    )
    pins = (
        FlagCorridorPin("J2", "1", "3V3", (CAND_A,)),
        FlagCorridorPin("J2", "2", "GND", (bad, CAND_B)),
    )
    plan = bind_flag_corridors(_request((_corridor(pins=pins),)), FAR, POSES)[0]
    assert plan.seated
    assert plan.seats[1].box == (40.0, -30.0, 100.0, -14.0)
    assert plan.seats[1].source == "flag-pin-right"


# ------------------------------------------------------------- service yield


def test_service_branch_yields_the_measured_distance():
    plans = bind_flag_corridors(_request((_corridor(),)), ON_FLAG, POSES)
    plan = plans[0]
    assert plan.seated
    assert len(plan.yields) == 1
    yield_seat = plan.yields[0]
    assert isinstance(yield_seat, SeriesSeatYield)
    assert (yield_seat.part_id, yield_seat.branch_id) == ("C1", "j2_rail_gnd")
    assert yield_seat.refusal == ""
    assert yield_seat.direction == (0.0, 1.0)
    target = yield_seat.target
    assert target is not None
    assert target[0] == 55.0
    # The move is the real box's necessary distance, not a two-grid cap: `C1`'s
    # own pins reach from y = -10 to 14 and the 3V3 flag box ends at y = 18.
    assert abs(target[1] - 2.0) > 2 * _corridor().grid
    after = part_box(C1, POSE, target)
    assert all(pl._overlap_area(after, box) == 0.0 for box in plan.reserved_boxes)
    assert ON_FLAG["C1"] == (55.0, 2.0)  # binding never edits the caller's map
    moved_plans, state = place_flag_corridors(_request(), plans, ON_FLAG, POSES)
    assert state.origins["C1"] == target
    assert moved_plans == plans


def test_locked_part_refuses_by_name():
    locked = (
        PlacementPart("J2", J2, (POSE,)),
        PlacementPart("C1", C1, (POSE,), locked=POSE, locked_origin=(55.0, 2.0)),
        PlacementPart("R1", R1, (POSE,)),
    )
    request = PlacementInput(
        parts=locked, nets=NETS, flag_corridors=(_corridor(),),
    )
    plan = bind_flag_corridors(request, ON_FLAG, POSES)[0]
    assert not plan.seated
    assert plan.refusal is not None
    assert plan.refusal.category == pl.FLAG_CORRIDOR_REFUSAL
    assert "engineer lock" in plan.refusal.detail
    assert plan.seats == ()
    assert plan.mismatches(ON_FLAG, POSES) != ()


def test_yield_policy_can_refuse_the_service_part():
    plan = bind_flag_corridors(
        _request((_corridor(yield_parts=frozenset({"R1"})),)), ON_FLAG, POSES,
    )[0]
    assert not plan.seated
    assert "not an ordinary branch" in plan.refusal.detail


def test_no_real_grade_for_the_page_is_a_named_refusal():
    """A page box the flags cannot reach refuses; it does not seat over it."""
    plan = bind_flag_corridors(
        _request((_corridor(),), page_box=(-20.0, -20.0, 20.0, 20.0)),
        FAR, POSES,
    )[0]
    assert not plan.seated
    assert "leaves the page box" in plan.refusal.detail


def test_second_corridor_keeps_out_of_the_first_ones_flags():
    first = _corridor()
    second = FlagCorridorTemplate(
        group_id="j2_sig",
        host_part="J2",
        pins=(
            FlagCorridorPin("J2", "3", "SIG", (CAND_A,)),
            FlagCorridorPin("R1", "2", "SIG", (CAND_A,)),
        ),
    )
    request = _request((first, second))
    plans = bind_flag_corridors(request, FAR, POSES)
    assert len(plans) == 2
    assert plans[0].seated
    # The second group's `SIG` grade stands on the first group's boxes: refused
    # rather than drawn over them.
    assert not plans[1].seated
    assert "another corridor" in plans[1].refusal.detail


# --------------------------------------------------------- translation/drift


def test_translation_moves_every_point_and_keeps_the_shape():
    plan = bind_flag_corridors(_request((_corridor(),)), FAR, POSES)[0]
    delta = (100.0, -40.0)
    moved = plan.translated(delta)
    assert plan.seats[0].box == (40.0, 2.0, 100.0, 18.0)
    assert moved.seats[0].box == (
        140.0, -38.0, 200.0, -22.0,
    )
    assert moved.host_origin == (100.0, -40.0)
    assert moved.seats[0].rotation == plan.seats[0].rotation
    assert moved.seats[0].lead == tuple(
        (point[0] + delta[0], point[1] + delta[1])
        for point in plan.seats[0].lead
    )
    assert moved.reserved_boxes[0] == moved.seats[0].box
    moved_origins = {
        part_id: (point[0] + delta[0], point[1] + delta[1])
        for part_id, point in FAR.items()
    }
    assert moved.mismatches(moved_origins, POSES) == ()
    assert plan.mismatches(FAR, POSES) == ()


def test_mismatch_names_a_moved_host_and_a_changed_pose():
    plan = bind_flag_corridors(_request((_corridor(),)), FAR, POSES)[0]
    drifted = dict(FAR)
    drifted["J2"] = (10.0, 10.0)
    lines = plan.mismatches(drifted, POSES)
    assert any("host J2 sits at (10, 10)" in line for line in lines)
    turned = dict(POSES)
    turned["J2"] = SymbolPose(rotation=90, mirror=False)
    lines = plan.mismatches(FAR, turned)
    assert any("drawn in pose 90" in line for line in lines)


# ------------------------------------------------------- data checks / old contracts


def test_a_corridor_needs_two_pins_and_known_nets():
    with pytest.raises(PlacementError, match="at least two pins"):
        FlagCorridorTemplate(
            group_id="solo", host_part="J2",
            pins=(FlagCorridorPin("J2", "1", "3V3", (CAND_A,)),),
        )
    wrong_net = _corridor(pins=(
        FlagCorridorPin("J2", "1", "GND", (CAND_A,)),
        FlagCorridorPin("J2", "2", "GND", (CAND_A,)),
    ))
    with pytest.raises(PlacementError, match="the netlist says"):
        _request((wrong_net,))
    with pytest.raises(PlacementError, match="not a pin of that symbol"):
        _request((_corridor(pins=(
            FlagCorridorPin("J2", "9", "3V3", (CAND_A,)),
            FlagCorridorPin("J2", "2", "GND", (CAND_A,)),
        )),))


def test_a_candidate_must_be_real_relative_geometry():
    with pytest.raises(PlacementError, match="anchor"):
        FlagCorridorCandidate(
            anchor=(float("nan"), 0.0), rotation=0.0,
            lead=((0.0, 0.0), (30.0, 0.0)), box=(0.0, 0.0, 10.0, 10.0),
        )
    with pytest.raises(PlacementError, match="positive extent"):
        FlagCorridorCandidate(
            anchor=(30.0, 0.0), rotation=0.0,
            lead=((0.0, 0.0), (30.0, 0.0)), box=(0.0, 0.0, 0.0, 10.0),
        )
    with pytest.raises(PlacementError, match="first point"):
        FlagCorridorCandidate(
            anchor=(30.0, 0.0), rotation=0.0,
            lead=((5.0, 0.0), (30.0, 0.0)), box=(0.0, 0.0, 60.0, 10.0),
        )
    with pytest.raises(PlacementError, match="diagonal"):
        FlagCorridorCandidate(
            anchor=(30.0, 10.0), rotation=0.0,
            lead=((0.0, 0.0), (30.0, 10.0)), box=(0.0, 0.0, 60.0, 10.0),
        )
    with pytest.raises(PlacementError, match="not at its anchor"):
        FlagCorridorCandidate(
            anchor=(30.0, 0.0), rotation=0.0,
            lead=((0.0, 0.0), (20.0, 0.0)), box=(0.0, 0.0, 60.0, 10.0),
        )
    with pytest.raises(PlacementError, match="multiple of 90"):
        FlagCorridorCandidate(
            anchor=(30.0, 0.0), rotation=45.0,
            lead=((0.0, 0.0), (30.0, 0.0)), box=(0.0, 0.0, 60.0, 10.0),
        )


def test_old_flag_reservation_keeps_its_reading():
    """The soft seat price is untouched; a corridor does not read it or edit it."""
    reservation = FlagReservation(
        part_id="J2", token="1", net_id="3V3", box=(0.0, -8.0, 60.0, 8.0),
    )
    assert reservation.box_at((40.0, 10.0)) == (40.0, 2.0, 100.0, 18.0)
    request = PlacementInput(
        parts=PARTS, nets=NETS, flag_seats=(reservation,),
        iterations=250, restarts=2,
    )
    assert request.flag_seats == (reservation,)
    result = place(request)
    assert request.flag_seats == (reservation,)
    assert result.term("flag-room") is not None
    assert result.flag_corridors == ()


def test_place_reports_the_bound_corridor():
    request = PlacementInput(
        parts=PARTS, nets=NETS, flag_corridors=(_corridor(),),
        iterations=250, restarts=2,
    )
    result = place(request)
    assert len(result.flag_corridors) == 1
    plan = result.flag_corridor("j2_rail_gnd")
    assert plan is not None
    assert plan.seated, plan.refusal.render() if plan.refusal else ""
    assert result.flag_corridor_mismatches() == ()
    assert "flagCorridors" in result.to_jsonable()
    assert any("flag corridor" in note for note in result.notes)


def test_bound_plan_is_jsonable_and_printable():
    plan = bind_flag_corridors(_request((_corridor(),)), FAR, POSES)[0]
    body = plan.to_jsonable()
    assert body["groupId"] == "j2_rail_gnd"
    assert body["hostPart"] == "J2"
    assert len(body["seats"]) == 2
    assert body["refusal"] is None
    refused = bind_flag_corridors(
        _request((_corridor(),), page_box=(-20.0, -20.0, 20.0, 20.0)),
        FAR, POSES,
    )[0]
    assert refused.to_jsonable()["refusal"]["category"] == "layout-unsat"
    assert isinstance(refused, BoundFlagCorridorPlan)


# ------------------------------------------------------- service pin gap (22B)


def _gap_fixture(direction: str):
    """A host with two adjacent flagged pins and one uniquely served shunt."""
    host = _profile("CONN-2", (-20.0, -20.0, 20.0, 20.0), (
        ("1", (0.0, 0.0), "3V3", "right"),
        ("2", (0.0, 10.0), "GND", "right"),
    ))
    shunt = _profile("C0603-SERVED", (-10.0, -4.0, 10.0, 4.0), (
        ("1", (50.0, 0.0), "A", direction),
        ("2", (30.0, -12.0), "B", "down"),
    ))
    parts = (
        PlacementPart("J9", host, (POSE,)),
        PlacementPart("C9", shunt, (POSE,)),
    )
    nets = (
        PlacementNet("3V3", (("J9", "1"), ("C9", "1")), "power"),
        PlacementNet("GND", (("J9", "2"), ("C9", "2")), "gnd"),
    )
    rail = _seat_right((0.0, -8.0, 160.0, 8.0), anchor=(80.0, 0.0),
                       lead=((0.0, 0.0), (80.0, 0.0)))
    ground = _seat_right(
        (40.0, 20.0, 100.0, 36.0), anchor=(5.0, 20.0),
        lead=((0.0, 0.0), (5.0, 0.0), (5.0, 20.0)),
    )
    corridor = FlagCorridorTemplate(
        group_id="j9_rail_gnd", host_part="J9",
        pins=(
            FlagCorridorPin("J9", "1", "3V3", (rail,)),
            FlagCorridorPin("J9", "2", "GND", (ground,)),
        ),
        service_gaps=(ServicePinGap("C9", "1", "J9", "1", 150.0),),
    )
    request = PlacementInput(
        parts=parts, nets=nets, flag_corridors=(corridor,),
    )
    origins = {"J9": (0.0, 0.0), "C9": (100.0, 0.0)}
    poses = {"J9": POSE, "C9": POSE}
    return request, origins, poses


def test_a_service_yield_keeps_the_stated_pin_gap():
    """The shunt may move, but its service pin stays the stated gap from the host."""
    request, origins, poses = _gap_fixture("up")
    plan = bind_flag_corridors(request, origins, poses)[0]
    assert plan.seated, plan.refusal.render() if plan.refusal else ""
    yield_seat = plan.yields[0]
    assert yield_seat.part_id == "C9"
    assert yield_seat.direction == (0.0, -1.0)
    service = (150.0, yield_seat.target[1])
    gap = ((service[0] - 0.0) ** 2 + (service[1] - 0.0) ** 2) ** 0.5
    assert abs(gap - 150.0) <= request.grid / 2.0
    assert plan.to_jsonable()["serviceGaps"][0]["gap"] == 150.0


def test_a_yield_that_would_break_the_pin_gap_is_refused_by_name():
    """Along the service axis every exit changes the gap: refuse, do not move."""
    request, origins, poses = _gap_fixture("right")
    plan = bind_flag_corridors(request, origins, poses)[0]
    assert not plan.seated
    assert "service pin gap" in plan.refusal.detail
    assert plan.refusal.category == pl.FLAG_CORRIDOR_REFUSAL


def test_a_service_gap_must_name_real_pins():
    request, origins, poses = _gap_fixture("up")
    broken = replace(
        request.flag_corridors[0],
        service_gaps=(ServicePinGap("C9", "9", "J9", "1", 150.0),),
    )
    with pytest.raises(PlacementError, match="service gap service pin"):
        replace(request, flag_corridors=(broken,))
    with pytest.raises(PlacementError, match="positive length"):
        ServicePinGap("C9", "1", "J9", "1", 0.0)
