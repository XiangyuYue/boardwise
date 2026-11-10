"""548D3I：placement 内部的可选串联座位合同（第一阶段窄测试）。

本文件只钉 `engines/placement.py` 的 draw 内部 API，不碰 drawcompiler、548D 的七项
xfail、CLI/DSH/connector。判据来自 `evidence/548D/series-seat-plan.md` 与
`series-seat-plan-criteria.md` 的第 3–5 节：

* 缺省/空 `series_templates` 是**历史请求**：不建计划、不加 cost term、不改种子/
  移动随机轨迹或旧输出。
* 模板引用与冲突在几何之前具名拒绝（缺件、缺脚、非法 pose、重复 branch、一件两臂、
  engineer lock、宿主兼臂件、非正交链轴）。
* pitch 从普通 seed 的两件中心距量一次，冻结于所有 restart；单臂保留 seed lateral，
  两臂在绑定点联合分 lane，整臂移动。
* 宿主平移/转姿时整臂随动；臂内两件不可独立转姿、交换、repair，lane 只可联合调整。
* 外国件侵入 reserved boxes 是具名 hard（`series-reservation:<branch>`）；普通件有
  确定性 yield，锁死件则留下具名 hard，由调用方拒绝，不静默返回合规。
* 结果携带最终 bound plans，`series_mismatches()` 能逐脚核对 origin/pose。

合成符号只做本合同的窄几何（两端针尖 ±20 的两脚件），不冒充 548D 的 MCU 七项验收。
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from boardwise.core.symbolprofile import SymbolPin, SymbolPose, SymbolProfile
from boardwise.engines import placement as pl

POSE = SymbolPose(rotation=0, mirror=False)
POSE_Q = SymbolPose(rotation=90, mirror=False)


def _two_pin(symbol_ref: str = "R") -> SymbolProfile:
    """横放两脚件：pin1 在局部 (-20, 0)，pin2 在 (20, 0)。"""
    return SymbolProfile(
        symbol_ref=symbol_ref, body=(-10.5, -4.5, 10.5, 4.5),
        pins=[
            SymbolPin(number="1", tip=(-20.0, 0.0), name="1"),
            SymbolPin(number="2", tip=(20.0, 0.0), name="2"),
        ],
    )


def _asymmetric(symbol_ref: str = "ASYM") -> SymbolProfile:
    """非对称 body/pin：pin1 (-30, 10)，pin2 (25, -5)，body 不居中。"""
    return SymbolProfile(
        symbol_ref=symbol_ref, body=(-5.0, -8.0, 15.0, 6.0),
        pins=[
            SymbolPin(number="1", tip=(-30.0, 10.0), name="1"),
            SymbolPin(number="2", tip=(25.0, -5.0), name="2"),
        ],
    )


def _part(part_id: str, poses: tuple[SymbolPose, ...] = (POSE,)) -> pl.PlacementPart:
    return pl.PlacementPart(part_id, _two_pin(part_id), poses)


def _parts(*part_ids: str) -> tuple[pl.PlacementPart, ...]:
    return tuple(_part(part_id) for part_id in part_ids)


def _nets(*part_ids: str) -> tuple[pl.PlacementNet, ...]:
    members = tuple((part_id, pin) for part_id in part_ids for pin in ("1", "2"))
    return (pl.PlacementNet("NET", members),)


def _template(
    branch_id: str = "B",
    *,
    host_part: str = "A0",
    host_token: str = "2",
    first: str = "B1",
    second: str = "B2",
    first_pose: SymbolPose = POSE,
    second_pose: SymbolPose = POSE,
    clearance: float = 0.0,
    lattice: tuple[float, float] = (0.0, 0.0),
    grid: float = pl.DEFAULT_GRID,
    progress: tuple[float, float] = (1.0, 0.0),
    lateral: tuple[float, float] = (0.0, 1.0),
) -> pl.SeriesSeatTemplate:
    return pl.SeriesSeatTemplate(
        branch_id=branch_id, host_part=host_part, host_token=host_token,
        first=pl.SeriesSeatArmPart(first, from_token="1", middle_token="2"),
        second=pl.SeriesSeatArmPart(second, middle_token="1", to_token="2"),
        first_pose=first_pose, second_pose=second_pose,
        clearance=clearance, lattice=lattice, grid=grid,
        progress=progress, lateral=lateral,
    )


def _request(
    parts: tuple[pl.PlacementPart, ...],
    templates: tuple[pl.SeriesSeatTemplate, ...] = (),
    *,
    iterations: int = 0,
    restarts: int = 1,
) -> pl.PlacementInput:
    return pl.PlacementInput(
        parts=parts, nets=_nets(*(part.part_id for part in parts)),
        series_templates=templates, iterations=iterations, restarts=restarts,
    )


def _seed(request: pl.PlacementInput) -> pl._State:
    return pl._seed(request, pl._ranks(request.relations, request.part_ids()))


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return ((second[0] - first[0]) ** 2 + (second[1] - first[1]) ** 2) ** 0.5


def _unit(vector: tuple[float, float]) -> tuple[float, float]:
    length = (vector[0] ** 2 + vector[1] ** 2) ** 0.5
    return (vector[0] / length, vector[1] / length)


def _dot(first: tuple[float, float], second: tuple[float, float]) -> float:
    return first[0] * second[0] + first[1] * second[1]


def _snap(value: float, grid: float, offset: float) -> float:
    return round((value - offset) / grid) * grid + offset


def _expected_seat(
    request: pl.PlacementInput,
    state: pl._State,
    template: pl.SeriesSeatTemplate,
) -> tuple[float, float, tuple[float, float], tuple[float, float]]:
    """The compiler's seat equation, computed here without the binder.

    pitch = ordinary-seed first/second **origin** distance;
    lead = the first part's posed from-pin local tip;
    first = snap(host_tip + progress*pitch/2 - lead + lateral*lane);
    second = snap(first + progress*pitch).
    The returned lane is read back from the **snapped** first origin against the
    no-lane seat, which is what the plan stores after quantization.
    """
    host_pin = request.part(template.host_part).profile.pin(template.host_token)
    first_pin = request.part(template.first.part_id).profile.pin(
        template.first.from_token
    )
    assert host_pin is not None and first_pin is not None
    host_tip = pl.posed_tip(
        host_pin.tip, state.poses[template.host_part], state.origins[template.host_part]
    )
    lead = pl.posed_tip(first_pin.tip, template.first_pose, (0.0, 0.0))
    pitch = _distance(
        state.origins[template.first.part_id], state.origins[template.second.part_id]
    )
    progress = _unit(template.progress)
    lateral = _unit(template.lateral)
    no_lane = (
        host_tip[0] + progress[0] * pitch / 2.0 - lead[0],
        host_tip[1] + progress[1] * pitch / 2.0 - lead[1],
    )
    lane = _dot(
        (state.origins[template.first.part_id][0] - no_lane[0],
         state.origins[template.first.part_id][1] - no_lane[1]),
        lateral,
    )
    first = (
        _snap(no_lane[0] + lateral[0] * lane, template.grid, template.lattice[0]),
        _snap(no_lane[1] + lateral[1] * lane, template.grid, template.lattice[1]),
    )
    second = (
        _snap(first[0] + progress[0] * pitch, template.grid, template.lattice[0]),
        _snap(first[1] + progress[1] * pitch, template.grid, template.lattice[1]),
    )
    readback = _dot((first[0] - no_lane[0], first[1] - no_lane[1]), lateral)
    return pitch, readback, first, second


# ------------------------------------------------- 1. 缺省 / 空输入逐字等价


def test_an_undeclared_request_is_the_historical_request():
    """空模板不建计划、不加 term，成本序列与移动结果逐字不变。"""
    request = _request(_parts("A0", "B1", "B2"), iterations=400)
    first = pl.place(request)
    second = pl.place(request)

    assert first.series_plans == ()
    assert first.series_mismatches() == ()
    assert [item.name for item in first.costs] == [
        "wire-length", "pin-facing", "flow-side", "spread", "clearance",
        "flag-room", "page", "keepout", "overlap",
    ]
    assert not any(item.name.startswith("series") for item in first.costs)
    assert "seriesPlans" not in first.to_jsonable()
    assert first.placement() == second.placement()
    assert [
        (item.name, item.value, item.hard) for item in first.costs
    ] == [
        (item.name, item.value, item.hard) for item in second.costs
    ]


def test_an_undeclared_request_and_an_explicit_empty_tuple_are_the_same():
    parts = _parts("A0", "B1", "B2")
    implicit = pl.place(_request(parts, iterations=100))
    explicit = pl.place(pl.PlacementInput(
        parts=parts, nets=_nets("A0", "B1", "B2"), series_templates=(),
        iterations=100, restarts=1,
    ))
    assert implicit.placement() == explicit.placement()
    assert [
        (item.name, item.value) for item in implicit.costs
    ] == [
        (item.name, item.value) for item in explicit.costs
    ]


# --------------------------------------------- 2. pitch 来自普通 seed 且冻结


def test_pitch_is_the_ordinary_seed_pair_distance_and_stays_frozen():
    template = _template()
    request = _request(
        _parts("A0", "B1", "B2"), (template,), iterations=0, restarts=3,
    )
    seed = _seed(request)
    pitch, lane, first, second = _expected_seat(request, seed, template)
    assert pitch == pytest.approx(80.0)

    result = pl.place(request)
    plan = result.series_plan("B")
    assert plan is not None and plan.seated
    assert plan.pitch == pytest.approx(pitch)
    assert plan.pitch_source == "ordinary-seed"
    assert plan.lane == pytest.approx(lane)
    assert plan.first_origin == pytest.approx(first)
    assert plan.second_origin == pytest.approx(second)
    assert result.series_mismatches() == ()
    assert plan.origin_pitch(result.origins) == pytest.approx(pitch)


def test_a_single_arm_keeps_the_ordinary_seed_lateral():
    parts = tuple(
        replace(part, locked_origin=(20.0, 40.0)) if part.part_id == "A0" else part
        for part in _parts("A0", "B1", "B2")
    )
    template = _template()
    request = pl.PlacementInput(
        parts=parts, nets=_nets("A0", "B1", "B2"),
        series_templates=(template,), iterations=0, restarts=1,
    )
    seed = _seed(request)
    assert seed.origins["A0"] == pytest.approx((20.0, 40.0))
    pitch, lane, first, second = _expected_seat(request, seed, template)

    result = pl.place(request)
    plan = result.series_plan("B")
    assert plan is not None and plan.seated
    # The seed's first origin sits 40 units below the no-lane seat; that is the
    # lane the plan keeps, instead of forcing the arm onto the host's row.
    assert lane == pytest.approx(-40.0)
    assert plan.lane == pytest.approx(lane)
    assert plan.first_origin == pytest.approx(first)
    assert plan.second_origin == pytest.approx(second)


# ---------------------------------------------------- 3. 模板引用与冲突


def _valid_request(templates: tuple[pl.SeriesSeatTemplate, ...]) -> pl.PlacementInput:
    return _request(_parts("A0", "B1", "B2", "D1", "D2"), templates)


def test_missing_host_part_is_refused_before_geometry():
    template = _template(host_part="ZZ")
    with pytest.raises(pl.PlacementError, match="host part"):
        _valid_request((template,))


def test_missing_host_pin_is_refused_before_geometry():
    template = _template(host_token="9")
    with pytest.raises(pl.PlacementError, match="host pin"):
        _valid_request((template,))


def test_missing_arm_part_is_refused_before_geometry():
    template = _template(first="ZZ")
    with pytest.raises(pl.PlacementError, match="first part"):
        _valid_request((template,))


def test_missing_arm_pin_is_refused_before_geometry():
    template = replace(
        _template(),
        first=pl.SeriesSeatArmPart("B1", from_token="9", middle_token="2"),
    )
    with pytest.raises(pl.PlacementError, match="is not a pin"):
        _valid_request((template,))


def test_an_illegal_pose_is_refused_before_geometry():
    template = _template(first_pose=POSE_Q)
    with pytest.raises(pl.PlacementError, match="not legal in pose"):
        _valid_request((template,))


def test_the_same_part_in_both_seats_is_refused():
    with pytest.raises(pl.PlacementError, match="both seats name the same part"):
        _template(first="B1", second="B1")


def test_two_templates_may_not_share_a_branch_id():
    with pytest.raises(pl.PlacementError, match="share one branch id"):
        _valid_request((_template("B"), _template("B", first="D1", second="D2")))


def test_one_part_may_not_belong_to_two_arms():
    other = _template("D", first="B1", second="D2")
    with pytest.raises(pl.PlacementError, match="already in series branch"):
        _valid_request((_template("B"), other))


def test_an_arm_part_with_an_engineer_origin_lock_is_refused():
    parts = tuple(
        replace(part, locked_origin=(0.0, 0.0)) if part.part_id == "B1" else part
        for part in _parts("A0", "B1", "B2")
    )
    with pytest.raises(pl.PlacementError, match="engineer origin lock"):
        _request(parts, (_template(),))


def test_a_host_may_not_be_the_part_of_another_arm():
    other = _template("D", host_part="B1", first="D1", second="D2")
    with pytest.raises(pl.PlacementError, match="also a host"):
        _valid_request((_template("B"), other))


def test_a_non_perpendicular_chain_axis_is_refused():
    template = _template(progress=(1.0, 0.0), lateral=(1.0, 1.0))
    with pytest.raises(pl.PlacementError, match="not perpendicular"):
        _valid_request((template,))


# --------------------------------------- 4. 宿主移动 / 转姿整臂随动，lane 联合


def _bound(request: pl.PlacementInput) -> tuple[pl._State, tuple[pl.BoundSeriesSeatPlan, ...]]:
    seed = _seed(request)
    plans = pl._bind_series_plans(request, seed)
    pl._seat_series_arms(plans, seed)
    return seed, plans


def test_a_host_translation_carries_both_arm_parts():
    request = _request(_parts("A0", "B1", "B2"), (_template(),))
    seed, plans = _bound(request)
    before = seed.origins
    candidate = pl._State(dict(seed.origins), dict(seed.poses))
    candidate.origins["A0"] = (20.0, -25.0)

    projected = pl._project_series(request, plans, seed, candidate)
    delta = (0.0, -25.0)
    assert projected.origins["B1"] == pytest.approx(
        (before["B1"][0] + delta[0], before["B1"][1] + delta[1])
    )
    assert projected.origins["B2"] == pytest.approx(
        (before["B2"][0] + delta[0], before["B2"][1] + delta[1])
    )


def test_a_host_turn_carries_the_arm_by_the_pin_delta():
    # The projection is the seam under test, so the hypothetical turn is fed
    # directly: the seed keeps a legal pose, the candidate asks "what if the host
    # were turned". The expected delta is measured with the public geometry
    # transform, not with the series code.
    request = _request((_part("A0"), _part("B1"), _part("B2")), (_template(),))
    seed, plans = _bound(request)
    before = seed.origins
    candidate = pl._State(dict(seed.origins), dict(seed.poses))
    candidate.poses["A0"] = POSE_Q

    host_pin = request.part("A0").profile.pin("2")
    assert host_pin is not None
    old_tip = pl.posed_tip(host_pin.tip, POSE, seed.origins["A0"])
    new_tip = pl.posed_tip(host_pin.tip, POSE_Q, seed.origins["A0"])
    delta = (new_tip[0] - old_tip[0], new_tip[1] - old_tip[1])
    assert delta == pytest.approx((-20.0, 20.0))

    projected = pl._project_series(request, plans, seed, candidate)
    assert projected.origins["B1"] == pytest.approx(
        (before["B1"][0] + delta[0], before["B1"][1] + delta[1])
    )
    assert projected.origins["B2"] == pytest.approx(
        (before["B2"][0] + delta[0], before["B2"][1] + delta[1])
    )


def test_an_arm_move_is_joint_and_only_across_the_lane():
    request = _request(_parts("A0", "B1", "B2"), (_template(),))
    seed, plans = _bound(request)
    before = seed.origins
    candidate = pl._State(dict(seed.origins), dict(seed.poses))
    candidate.origins["B1"] = (before["B1"][0] + 30.0, before["B1"][1] - 10.0)

    projected = pl._project_series(request, plans, seed, candidate)
    # progress component (+30) is dropped, lateral (-10) applies to both parts.
    assert projected.origins["B1"] == pytest.approx((before["B1"][0], before["B1"][1] - 10.0))
    assert projected.origins["B2"] == pytest.approx((before["B2"][0], before["B2"][1] - 10.0))


# ------------------------------------------------------- 5. 两臂不互压


def test_two_arms_sharing_a_host_are_allocated_separate_lanes():
    request = _request(
        _parts("A0", "B1", "B2", "D1", "D2"),
        (_template("B"), _template("D", first="D1", second="D2")),
        iterations=0, restarts=1,
    )
    result = pl.place(request)
    first = result.series_plan("B")
    second = result.series_plan("D")
    assert first is not None and first.seated
    assert second is not None and second.seated
    assert result.series_mismatches() == ()
    assert result.hard == []

    assert first.lane != second.lane
    assert second.lane > first.lane
    for left in first.reserved_boxes[:2]:
        for right in second.reserved_boxes[:2]:
            assert pl._overlap_area(left, right) == 0.0


# --------------------------------------- 6. 普通件 yield / 不可让留具名 hard


def _yield_request(locked: bool = False) -> pl.PlacementInput:
    parts = list(_parts("A0", "B1", "B2", "C1"))
    if locked:
        parts[3] = replace(parts[3], locked_origin=(260.0, 0.0))
    return pl.PlacementInput(
        parts=tuple(parts), nets=_nets("A0", "B1", "B2", "C1"),
        series_templates=(_template(clearance=70.0),), iterations=0, restarts=1,
    )


def test_an_ordinary_part_yields_and_the_reservation_hard_returns_to_zero():
    request = _yield_request()
    seed = _seed(request)
    bound = pl._bind_series_plans(request, seed)
    yields = [item for item in bound[0].yields if item.part_id == "C1"]
    assert len(yields) == 1
    moved = yields[0]
    assert moved.refusal == ""
    assert moved.direction is not None and moved.target is not None
    assert moved.target != seed.origins["C1"]

    result = pl.place(request)
    plan = result.series_plan("B")
    assert plan is not None and plan.seated
    assert result.origins["C1"] == pytest.approx(moved.target)
    # The final report describes the final state: C1 has already yielded, so it
    # is no longer listed as an intrusion. The binding-time mapping above is the
    # record of the move itself.
    assert plan.yields == ()

    term = result.term("series-reservation:B")
    assert term is not None and term.hard
    assert term.value == pytest.approx(0.0)
    assert result.hard == []
    reserved = plan.reserved_boxes
    foreign_box = pl.part_box(
        request.part("C1").profile, result.poses["C1"], result.origins["C1"]
    )
    assert all(pl._overlap_area(foreign_box, box) == 0.0 for box in reserved)


def test_an_unyieldable_intrusion_stays_a_named_hard_violation():
    request = _yield_request(locked=True)
    result = pl.place(request)
    plan = result.series_plan("B")
    assert plan is not None and plan.seated
    yields = [item for item in plan.yields if item.part_id == "C1"]
    assert len(yields) == 1
    assert yields[0].direction is None
    assert "engineer lock" in yields[0].refusal

    term = result.term("series-reservation:B")
    assert term is not None and term.hard and term.violated
    assert "C1" in term.detail
    assert term in result.hard
    assert result.series_mismatches() == ()


def test_a_seat_on_another_parts_box_is_refused_and_a_clear_seat_is_allowed():
    """`_yield_target_is_legal` 对外国件只看别的件：自己那一格不算遮挡。"""
    request = _yield_request()
    seed = _seed(request)
    part_id, foreign_id = "C1", "B1"
    pose = seed.poses[part_id]
    profile = request.part(part_id).profile
    foreign = pl.part_box(
        request.part(foreign_id).profile, seed.poses[foreign_id],
        seed.origins[foreign_id],
    )
    own = pl.part_box(profile, pose, seed.origins[part_id])
    others = {foreign_id: foreign, part_id: own}

    occupied = seed.origins[foreign_id]
    assert pl._overlap_area(
        pl.part_box(profile, pose, occupied), foreign
    ) > 0.0
    assert pl._yield_target_is_legal(
        request, part_id, pose, seed.origins[part_id], occupied, others, (), ()
    ) is False

    clear = (seed.origins[part_id][0] + 80.0, seed.origins[part_id][1])
    clear_box = pl.part_box(profile, pose, clear)
    assert pl._overlap_area(clear_box, foreign) == 0.0
    assert pl._overlap_area(clear_box, own) == 0.0
    assert pl._yield_target_is_legal(
        request, part_id, pose, seed.origins[part_id], clear, others, (), ()
    ) is True


# --------------------------------------------- 7. 结果能核对最终 origin/pose


def test_the_result_can_name_a_part_that_left_its_bound_seat():
    request = _request(_parts("A0", "B1", "B2"), (_template(),))
    result = pl.place(request)
    plan = result.series_plan("B")
    assert plan is not None and plan.first_origin is not None

    moved = replace(
        plan,
        first_origin=(plan.first_origin[0] + 5.0, plan.first_origin[1]),
    )
    assert pl.PlacementResult(
        origins=result.origins, poses=result.poses,
        series_plans=(moved,),
    ).series_mismatches()

    turned = replace(plan, first_pose=SymbolPose(rotation=90, mirror=False))
    assert pl.PlacementResult(
        origins=result.origins, poses=result.poses,
        series_plans=(turned,),
    ).series_mismatches()


# ------------------------------- 8. lattice 是坐标、clearance 是盒子空气


def test_lattice_offsets_coordinates_and_clearance_pads_boxes_only():
    template = _template(lattice=(2.0, 1.0), clearance=0.0, grid=5.0)
    parts = (
        _part("A0"),
        pl.PlacementPart("B1", _asymmetric("A1P"), (POSE,)),
        pl.PlacementPart("B2", _asymmetric("A2P"), (POSE,)),
    )
    request = _request(parts, (template,), iterations=0, restarts=1)
    seed = _seed(request)
    pitch, lane, first, second = _expected_seat(request, seed, template)

    result = pl.place(request)
    plan = result.series_plan("B")
    assert plan is not None and plan.seated
    assert plan.pitch == pytest.approx(pitch)
    assert plan.lane == pytest.approx(lane)
    assert plan.first_origin == pytest.approx(first)
    assert plan.second_origin == pytest.approx(second)
    assert plan.lattice == (2.0, 1.0)
    assert plan.clearance == 0.0

    # Both selected tips sit on the same compilation lattice, even though the
    # bodies and pin offsets are asymmetric. The test snap is its own formula,
    # not the binder's.
    for part_id in ("B1", "B2"):
        pin = request.part(part_id).profile.pin("1")
        assert pin is not None
        tip = pl.posed_tip(pin.tip, POSE, result.origins[part_id])
        for value, offset in zip(tip, template.lattice):
            assert value == pytest.approx(
                _snap(value, template.grid, offset), abs=1e-9
            )

    body = plan.to_jsonable()
    assert body["lattice"] == [2.0, 1.0]
    assert body["clearance"] == 0.0
    assert "residue" not in body
    assert not hasattr(template, "residue")

    # Clearance changes only the reserved-box padding, never the seat.
    padded_request = _request(
        parts, (_template(lattice=(2.0, 1.0), clearance=3.0, grid=5.0),),
        iterations=0, restarts=1,
    )
    padded = pl.place(padded_request).series_plan("B")
    assert padded is not None and padded.seated
    assert padded.first_origin == pytest.approx(plan.first_origin)
    assert padded.second_origin == pytest.approx(plan.second_origin)
    for tight, wide in zip(plan.reserved_boxes[:2], padded.reserved_boxes[:2]):
        assert wide == pytest.approx(
            (tight[0] - 3.0, tight[1] - 3.0, tight[2] + 3.0, tight[3] + 3.0)
        )


# ------------------------- 9. 搜索后 yield 映射重算，四者一致


def test_refresh_recomputes_yields_after_a_candidate_move():
    request = _request(
        _parts("A0", "B1", "B2", "C1"), (_template(),),
        iterations=0, restarts=1,
    )
    seed = _seed(request)
    plans = pl._bind_series_plans(request, seed)
    pl._seat_series_arms(plans, seed)
    assert plans[0].yields == ()

    state = pl._State(dict(seed.origins), dict(seed.poses))
    state.origins["B1"] = (seed.origins["B1"][0], seed.origins["B1"][1] + 40.0)
    state.origins["B2"] = (seed.origins["B2"][0], seed.origins["B2"][1] + 40.0)
    state.origins["C1"] = (190.0, 40.0)

    fresh = pl._refresh_series_plans(request, plans, state)[0]
    assert fresh.first_origin == pytest.approx(state.origins["B1"])
    assert fresh.second_origin == pytest.approx(state.origins["B2"])
    assert fresh.mismatches(state.origins, state.poses) == ()

    yields = [item for item in fresh.yields if item.part_id == "C1"]
    assert len(yields) == 1 and yields[0].direction is not None
    assert yields[0].target is not None

    after = pl._State(dict(state.origins), dict(state.poses))
    after.origins["C1"] = yields[0].target
    boxes = pl._boxes_of(request, after)
    term = pl._series_reservation_terms(request, after, (fresh,), boxes)[0]
    assert term.value == pytest.approx(0.0)


# ------------------- 10. 臂间 corridor 豁免只限共享 host pin 的必经交汇


def test_an_arm_crossing_from_a_different_host_stays_a_named_hard():
    request = _request(
        _parts("H0", "A1", "A2", "H1", "B1", "B2"),
        (
            _template("A", host_part="H0", first="A1", second="A2"),
            _template("B", host_part="H1", first="B1", second="B2"),
        ),
        iterations=0, restarts=1,
    )
    seed = _seed(request)
    plans = pl._bind_series_plans(request, seed)
    assert all(plan.seated for plan in plans)
    pl._seat_series_arms(plans, seed)

    # Put every part on explicit coordinates so the only crossing in the test is
    # the one under inspection: B's first part sits inside A's middle corridor,
    # and the two arms hang from different host pins.
    state = pl._State(dict(seed.origins), dict(seed.poses))
    state.origins.update({
        "H0": (0.0, 0.0), "A1": (60.0, 0.0), "A2": (140.0, 0.0),
        "H1": (500.0, 500.0), "B1": (100.0, 0.0), "B2": (180.0, 0.0),
    })
    boxes = pl._boxes_of(request, state)
    term = next(
        item for item in pl._series_reservation_terms(request, state, plans, boxes)
        if item.name == "series-reservation:A"
    )
    assert term.hard and term.violated
    assert "B1" in term.detail and "arm B" in term.detail
