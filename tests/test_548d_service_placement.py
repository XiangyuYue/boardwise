"""548D3S1：ServiceSeatTemplate 与共享 binder（draw 内部 placement 合同）。

只验 binder 层：ServiceSeatTemplate 的 left/right 单 cell 真实落位、相对 reserve、
宿主平移/换姿、mismatches、cache key、外国件/锁/非法输入的具名拒绝，以及空模板对
既有请求轨迹/成本/JSON 的零影响。不接 drawcompiler、真实 C1/R1/D、最终旗线或生产
compile；binder 绿不等于两个消费者或整图通过（S2/S3 才做）。

夹具复用 `tests/test_548d_panel_validation.py` 的真实 MCU32/C 符号与
`drawcompiler` 的 `_arm_pose`/`_line_boxes` 相对盒（生产 placement 不 import draw）。
"""

from __future__ import annotations

import dataclasses

import pytest

import test_548d_panel_validation as p32

from boardwise.engines import drawcompiler as dc
from boardwise.engines import placement

BOOK = p32._book()


def _part(part_id: str, symbol: str, **kwargs) -> placement.PlacementPart:
    profile = BOOK[symbol]
    return placement.PlacementPart(
        part_id=part_id, profile=profile, poses=tuple(profile.poses), **kwargs)


def _nets() -> tuple[placement.PlacementNet, ...]:
    return (
        placement.PlacementNet(
            net_id="3V3", members=(("U1", "VDD"), ("C1", "1")), cls="power"),
        placement.PlacementNet(
            net_id="GND", members=(("U1", "VSS"), ("C1", "2")), cls="gnd"),
    )


def _cell(
    *, host_token: str = "PA3", flag_lead=(), pose=None, side: str = "right",
) -> placement.PanelCell:
    profile = BOOK["C"]
    # `_arm_pose` states the direction the cell's *to* foot leaves by, so a
    # right-side cell (host on its left) is the (1, 0) pose.
    inward = (1.0, 0.0) if side == "right" else (-1.0, 0.0)
    pose = pose or dc._arm_pose(profile, "1", "2", inward)
    assert pose is not None, "the C symbol has no from-left/to-right pose"
    rel = placement.part_box(profile, pose, (0.0, 0.0))
    boxes = dc._line_boxes(rel, ["C1", "100nF"], "right")
    return placement.PanelCell(
        part_id="C1", from_net="3V3", to_net="GND",
        from_token="1", to_token="2", host_token=host_token,
        pose=pose, text_boxes=tuple(boxes),
        flag_box=(0.0, -50.0, 0.0, -20.0), flag_lead=flag_lead,
    )


def _template(side: str = "right", **overrides) -> placement.ServiceSeatTemplate:
    entry = dict(
        group_id="service:C1", host_part="U1", side=side,
        cell=_cell(host_token="PA3" if side == "right" else "VDD", side=side),
        grid=5.0, pitch=10.0,
    )
    entry.update(overrides)
    return placement.ServiceSeatTemplate(**entry)


def _request(**overrides) -> placement.PlacementInput:
    entry = dict(
        parts=(_part("U1", "MCU32"), _part("C1", "C")),
        nets=_nets(), grid=5.0,
        service_templates=(_template(),),
    )
    entry.update(overrides)
    return placement.PlacementInput(**entry)


def _answer(host_origin=(0.0, 0.0), host_pose=None, cell_origin=(123.0, -77.0)):
    request = _request()
    profile = BOOK["MCU32"]
    poses = {
        "U1": host_pose or profile.poses[0],
        "C1": request.service_templates[0].cell.pose,
    }
    origins = {"U1": host_origin, "C1": cell_origin}
    return request, origins, poses


def _bind(request=None, **kwargs):
    request = request or _request()
    origins, poses = _answer(**kwargs)[1:]
    return request, placement.bind_service_plans(request, origins, poses)


def test_a_right_cell_seats_outside_the_host_body():
    request, plans = _bind()
    plan = plans[0]
    assert plan.seated, plan.refusal.render() if plan.refusal else ""
    assert plan.side == "right" and plan.columns == 1
    cell = plan.cells[0]
    host_body = placement.pose_box(
        BOOK["MCU32"].body, rotation=0, mirror=False, ox=0.0, oy=0.0)
    assert cell.origin[0] > host_body[2], (cell.origin, host_body)
    assert cell.from_seat[0] < cell.to_seat[0]
    assert plan.reserved_boxes and cell.reserved
    assert plan.host_paths == (), "a service seat routes no panel channel"
    # The from foot stands on the host pin's own axis — measured against the
    # real posed pin, not against a second copy of the same expression.
    host_pin = placement._pin_for_token(BOOK["MCU32"], "PA3")
    host_tip = placement.posed_tip(
        host_pin.tip, BOOK["MCU32"].poses[0], (0.0, 0.0))
    assert abs(cell.from_seat[1] - host_tip[1]) < 1e-9, (
        cell.from_seat, host_tip)


def test_a_left_cell_seats_on_the_other_side():
    left = _request(service_templates=(_template("left"),))
    _req, plans = _bind(request=left)
    plan = plans[0]
    assert plan.seated, plan.refusal.render() if plan.refusal else ""
    cell = plan.cells[0]
    host_body = placement.pose_box(
        BOOK["MCU32"].body, rotation=0, mirror=False, ox=0.0, oy=0.0)
    assert cell.origin[0] + (cell.reserved[0][2] - cell.reserved[0][0]) < host_body[0]
    assert cell.from_seat[0] > cell.to_seat[0]
    host_pin = placement._pin_for_token(BOOK["MCU32"], "VDD")
    host_tip = placement.posed_tip(
        host_pin.tip, BOOK["MCU32"].poses[0], (0.0, 0.0))
    assert abs(cell.from_seat[1] - host_tip[1]) < 1e-9, (
        cell.from_seat, host_tip)


def test_a_host_axis_off_the_lattice_is_refused_not_shifted():
    # A lattice offset of 2.5 on grid 5: the host pin's axis (relative y = 0)
    # does not fall on the template's lattice, so the from foot cannot be both
    # coaxial with the pin and snapped — the binder must say so, not shift it.
    request = _request(service_templates=(
        _template("right", lattice=(0.0, 2.5)),))
    origins, poses = _answer()[1:]
    plan = placement.bind_service_plans(request, origins, poses)[0]
    assert not plan.seated
    assert "cannot stand on the host pin" in plan.refusal.detail


def test_the_plan_follows_the_hosts_origin():
    _request, first = _bind(host_origin=(0.0, 0.0))
    _request, moved = _bind(host_origin=(40.0, 25.0))
    delta = (40.0, 25.0)
    for base, other in ((first[0].cells[0], moved[0].cells[0]),):
        assert abs(other.origin[0] - base.origin[0] - delta[0]) < 1e-9
        assert abs(other.origin[1] - base.origin[1] - delta[1]) < 1e-9
        assert abs(other.from_seat[0] - base.from_seat[0] - delta[0]) < 1e-9
        assert abs(other.to_seat[1] - base.to_seat[1] - delta[1]) < 1e-9


def test_the_plan_rebinds_for_another_host_pose():
    profile = BOOK["MCU32"]
    turned = next(
        (pose for pose in profile.poses if pose.rotation != profile.poses[0].rotation),
        None,
    )
    if turned is None:
        pytest.skip("the fixture host declares a single pose")
    _request, first = _bind(host_pose=profile.poses[0])
    _request, second = _bind(host_pose=turned)
    assert first[0].seated
    if second[0].seated:
        assert first[0].cells[0].origin != second[0].cells[0].origin
    else:
        # A turned host may put the pin on the other side; the binder says so
        # by name instead of drawing the cell on a side the pin does not face.
        assert "faces" in second[0].refusal.detail


def test_mismatches_name_a_moved_cell():
    _request, plans = _bind()
    plan = plans[0]
    cell = plan.cells[0]
    moved = {cell.part_id: (cell.origin[0] + 10.0, cell.origin[1])}
    problems = plan.mismatches(moved, {cell.part_id: cell.pose})
    assert problems and "the plan says" in problems[0]


def test_the_cache_key_carries_the_side_and_the_flag_lead():
    plain = _template("right")
    lead = _template("right", cell=_cell(
        host_token="PA3", flag_lead=((0.0, 0.0), (0.0, -30.0))))
    left = _template("left")
    keys = {placement._service_template_key(item) for item in (plain, lead, left)}
    assert len(keys) == 3
    # same template twice: the relative solve is cached and reused
    request, origins, poses = _answer(host_origin=(0.0, 0.0))
    first = placement.bind_service_plans(request, origins, poses)[0]
    second = placement.bind_service_plans(request, origins, poses)[0]
    assert first is second


def test_a_foreign_part_in_the_room_is_a_named_refusal():
    request = _request()
    cell = request.service_templates[0].cell
    profile = BOOK["MCU32"]
    poses = {"U1": profile.poses[0], "C1": cell.pose, "D1": p32._book()["LED"].poses[0]}
    # Place a foreign LED right where the right-side cell's room will be.
    plan = placement.bind_service_plans(
        request, {"U1": (0.0, 0.0), "C1": (0.0, 0.0)},
        {"U1": poses["U1"], "C1": poses["C1"]})[0]
    spot = plan.cells[0].origin
    extra = _part("D1", "LED")
    hostile = dataclasses.replace(
        request, parts=request.parts + (extra,),
        service_templates=request.service_templates,
    )
    refused = placement.bind_service_plans(
        hostile, {"U1": (0.0, 0.0), "C1": (0.0, 0.0), "D1": spot},
        {"U1": poses["U1"], "C1": poses["C1"], "D1": poses["D1"]})[0]
    assert not refused.seated
    assert "intrudes" in refused.refusal.detail


def test_a_locked_part_is_a_named_refusal():
    locked = _part("C1", "C", locked_origin=(0.0, 0.0),
                   locked=BOOK["C"].poses[0])
    request = _request(parts=(_part("U1", "MCU32"), locked))
    origins, poses = _answer()[1:]
    plan = placement.bind_service_plans(request, origins, poses)[0]
    assert not plan.seated
    assert "user lock" in plan.refusal.detail


def test_an_unsupported_side_is_rejected_before_any_solve():
    with pytest.raises(placement.PlacementError):
        _template("top")
    with pytest.raises(placement.PlacementError):
        _template("right", host_part="C1")


def test_a_missing_host_pin_or_a_backwards_pose_is_named():
    bad_pin = _template("right", cell=_cell(host_token="NOPE"))
    origins, poses = _answer()[1:]
    plan = placement.bind_service_plans(
        _request(service_templates=(bad_pin,)), origins, poses)[0]
    assert not plan.seated and "has no pin" in plan.refusal.detail
    # a pose whose from foot faces away from the host is refused by name
    profile = BOOK["C"]
    backwards = dc._arm_pose(profile, "1", "2", (-1.0, 0.0))
    assert backwards is not None
    plan = placement.bind_service_plans(
        _request(service_templates=(_template("right", cell=_cell(pose=backwards)),)),
        origins, poses)[0]
    assert not plan.seated and "reads from the host outwards" in plan.refusal.detail


def test_an_empty_service_list_changes_nothing():
    plain = _request(service_templates=())
    result = placement.place(plain)
    assert result.service_plans == ()
    assert result.panel_plans == ()
    assert not any(term.name.startswith("service-") for term in result.costs)
    assert not any(term.name.startswith("panel-") for term in result.costs)
    again = placement.place(plain)
    assert again.origins == result.origins and again.poses == result.poses
    assert [term.name for term in again.costs] == [
        term.name for term in result.costs]


def test_a_stated_service_plan_is_separate_from_panel_plans():
    # The host keeps the pose the seat was declared against: the search may not
    # turn it into a pose whose pin faces the other way (that is a refusal).
    result = placement.place(_request(parts=(
        _part("U1", "MCU32", locked=BOOK["MCU32"].poses[0]), _part("C1", "C"))))
    assert result.panel_plans == ()
    assert len(result.service_plans) == 1
    assert result.service_plans[0].seated
    assert any(term.name == "service-reserve:service:C1" for term in result.costs)


def test_every_service_candidate_is_bound_before_it_is_evaluated(monkeypatch):
    """The anneal itself must re-bind services per candidate (548D3S2).

    Same shape as the panel test: a legal seed state and its seed-bound service
    plans come from one `place` call, then `_anneal_with_seed` runs alone with
    `bind_service_plans`/`evaluate` spied. The anneal's first evaluation is the
    seed's (no candidate bind yet); at least one later evaluation must come
    after a candidate-level bind, carry **that** bind's plans, and be measured
    on the very origins that bind was given. Dropping the per-candidate re-bind
    leaves the bind count at 0 — red.
    """
    request = _request(iterations=60)
    seeded = placement.place(request)          # only for a legal state + plans
    assert seeded.service_plans
    events: list[tuple] = []
    binds: list[tuple] = []
    real_bind = placement.bind_service_plans
    real_eval = placement.evaluate

    def spy_bind(req, origins, poses, panel_plans=()):
        out = real_bind(req, origins, poses, panel_plans)
        binds.append((origins, out))
        events.append(("bind", len(binds)))
        return out

    def spy_eval(req, state, plans=(), panels=(), *rest):
        events.append(("eval", len(binds), state.origins, rest))
        return real_eval(req, state, plans, panels, *rest)

    monkeypatch.setattr(placement, "bind_service_plans", spy_bind)
    monkeypatch.setattr(placement, "evaluate", spy_eval)
    placement._anneal_with_seed(  # noqa: SLF001 - the search under test
        request, seeded, request.seed, (), seeded.panel_plans,
        seeded.service_plans,
    )
    evals = [event for event in events if event[0] == "eval"]
    assert events[0][0] == "eval" and evals[0][1] == 0, (
        "the anneal's first evaluation is the seed's, before any candidate bind")
    later = [event for event in evals[1:] if event[1] >= 1]
    assert later, (
        "no service candidate was evaluated after a candidate-level re-bind: "
        "inside the anneal the services are still the seed's, so a moved host "
        "is priced against stale seats")
    for _kind, count, origins, rest in later:
        bound_origins, plans = binds[count - 1]
        assert rest and rest[0] is plans, (
            "the evaluation did not carry the plans the latest bind returned")
        assert origins is bound_origins, (
            "the evaluation's origins are not the ones the bind was given")
        assert len(rest) == 1, "a service request evaluates with the 5-argument call"
