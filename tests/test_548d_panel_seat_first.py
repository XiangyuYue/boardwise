"""548D3X4D（34D-A）：seat-first 地/电源旗座分配的内部计划。

本批只做**枚举与计划**：语义分组（`_flag_share_keys`）、panel terminal 固定座
（`_panel_terminal_seats`）、真实可用座与全 member 正交路径、具名拒绝。本批**不接**
最终接线/旗标回放，也不宣称 `dc.compile` 或视觉有改善——这里的每个断言只读计划
自身的几何与当前 placement 的真实证据。

夹具复用 `tests/test_548d_panel_base.py` 的真实 MCU32/KEY 电路与真实 2×2 panel
placement：不伪造坐标、不伪造成功。
"""

from __future__ import annotations

import dataclasses

import pytest

import test_548d_panel_base as base

from boardwise.engines import drawcompiler as dc


@pytest.fixture(autouse=True)
def _no_service_seats(monkeypatch):
    """§35B1: this book's pages state no ServiceSeat at all.

    Every expectation below was measured before a service seat existed, and the
    book is the algorithm's own: a panel page, its keys and the ordinary branch
    parts, no declared branch beside a host. The service path is measured in
    ``tests/test_548d_service_consumers.py`` instead, so this book keeps its
    scenarios, their fixtures and their twenty-odd answers untouched rather than
    being re-measured one assertion at a time.
    """
    monkeypatch.setattr(dc, "_service_templates", lambda *args, **kw: ((), None))
    monkeypatch.setattr(dc, "_service_branch_parts", lambda *args, **kw: frozenset())


def _plans(ctx=None, placed=None, **kwargs):
    ctx = base._context([base._panel_payload()]) if ctx is None else ctx
    if placed is None:
        placed, failure = base._base(ctx)
        assert failure is None, failure.detail
    return ctx, placed, dc._seat_first_plans(ctx, placed, **kwargs)


def _pin_of(ctx, placed, member: str) -> tuple[float, float]:
    part_id, _, token = member.partition(".")
    point = dc._pin_point(ctx, part_id, token, placed.poses, placed.origins)
    assert point is not None, member
    return point


# ======================================= 1. 只对写了 panelGroups 的文档生效

def test_a_page_without_panel_groups_keeps_the_old_path():
    ctx = base._context(None)
    placed, failure = base._base(ctx)
    assert failure is None
    assert dc._seat_first_plans(ctx, placed) == ((), None)
    assert dc._flag_grouping(ctx) is False


def test_a_panel_page_allocates_both_rails():
    _ctx, _placed, (plans, page) = _plans()
    assert page is None
    assert [plan.net for plan in plans] == ["3V3", "GND"]
    assert all(plan.cls in ("gnd", "power") for plan in plans)


# ============================== 2. 语义分组只来自 share key，不按距离合并

def test_the_groups_are_the_share_keys_and_nothing_else():
    ctx, placed, (plans, _page) = _plans()
    for plan in plans:
        points = tuple(
            (member, point)
            for member, point in dc._seat_first_points(ctx, placed, plan.net)
            if point is not None
        )
        keys = dc._flag_share_keys(ctx, plan.net, points)
        by_member = {
            member: f"share:{keys[member]}" if keys[member] else f"alone:{member}"
            for member, _point in points
        }
        seen: dict[str, str] = {}
        for assignment in plan.assignments:
            for member in assignment.members:
                seen[member] = assignment.group
        for member, group in by_member.items():
            if member in seen:
                assert seen[member] == group, (plan.net, member, group)
        # a group that could not be settled is refused, never re-grouped
        for candidate in plan.candidates:
            if candidate.refusal is not None:
                assert candidate.group in set(by_member.values()), (
                    plan.net, candidate.group)
        # Two independent key branches near each other are still two groups:
        # each S*.2 has its own local seat, never one shared 3V3 flag.
        three = next(p for p in plans if p.net == "3V3")
        groups = {a.group: a.members for a in three.assignments}
        for index in range(1, 5):
            assert groups[f"alone:S{index}.2"] == (f"S{index}.2",)
        assert groups["share:part:U1"] == ("U1.VBAT", "U1.VDD")
        ground = next(p for p in plans if p.net == "GND")
        alone = sorted(
            a.members[0] for a in ground.assignments
            if a.group.startswith("alone:")
        )
        assert alone == ["D1.2", "D2.2", "R1.2"]


# ================================ 3. 每座都是真实几何（lead/anchor/rotation）

def test_every_seat_is_real_geometry_on_the_placement():
    ctx, placed, (plans, _page) = _plans()
    solids, _bodies, failure = dc._seat_first_scene(ctx, placed)
    assert failure is None
    for plan in plans:
        profile, _ref = dc._flag_plan(
            ctx, plan.net, ctx.circuit.net(plan.net).cls,
        )
        for assignment in plan.assignments:
            seat = assignment.seat
            assert seat.rotation in (0.0, 180.0), seat
            assert seat.lead[0] == _pin_of(ctx, placed, seat.owner), seat
            assert seat.anchor == seat.lead[-1], seat
            assert len(seat.lead) >= 2
            for start, end in zip(seat.lead, seat.lead[1:]):
                assert (
                    abs(start[0] - end[0]) <= 1e-9
                    or abs(start[1] - end[1]) <= 1e-9
                ), seat.lead
            expected = dc._flag_box(
                profile, seat.rotation, seat.anchor, plan.net,
            )
            assert seat.glyph == expected
            router, _blocked = dc._seat_first_router(
                ctx, placed, plan.net, solids,
                dc._seat_first_points(ctx, placed, plan.net),
            )
            assert seat.occupancy == dc._seat_first_seat_nodes(
                router, seat.lead, seat.glyph,
            )
            # the flag's box stands on no part and no text row of this page
            for box in solids:
                assert not dc._panel_boxes_overlap(seat.glyph, box), (
                    plan.net, seat.owner, seat.glyph, box)


# ================= 4. 每个 member 一条真实正交 path，起点/终点都在自己身上

def test_every_member_has_its_own_orthogonal_path_to_the_seat():
    ctx, placed, (plans, _page) = _plans()
    for plan in plans:
        expected = {
            member for member, point in dc._seat_first_points(ctx, placed, plan.net)
            if point is not None
        }
        assigned = plan.assigned_members()
        assert len(assigned) == len(set(assigned))
        assert set(assigned) <= expected
        for assignment in plan.assignments:
            seat = assignment.seat
            for member in assignment.members:
                path = assignment.path_of(member)
                assert path is not None, (plan.net, member)
                assert path[0] == _pin_of(ctx, placed, member)
                assert path[-1] == seat.lead[0], (plan.net, member, path)
                for start, end in zip(path, path[1:]):
                    assert (
                        abs(start[0] - end[0]) <= 1e-9
                        or abs(start[1] - end[1]) <= 1e-9
                    ), (plan.net, member, path)
                if member == seat.owner:
                    assert path == (seat.lead[0],)
                else:
                    assert len(path) > 1
        # no run of one seat stands on another seat's lead or glyph
        for first in plan.assignments:
            for second in plan.assignments:
                if first is second:
                    continue
                assert not (first.lanes & second.seat.occupancy), (
                    first.group, second.group)


def test_the_three_volt_rail_is_complete_on_this_placement():
    _ctx, _placed, (plans, _page) = _plans()
    three = next(plan for plan in plans if plan.net == "3V3")
    assert three.complete, [item.detail for item in three.refusals]
    assert sorted(three.assigned_members()) == [
        "C1.1", "S1.2", "S2.2", "S3.2", "S4.2", "U1.VBAT", "U1.VDD",
    ]
    # the panel's four terminal seats are the seats of the four key cells
    fixed = {item.seat.owner for item in three.assignments if item.seat.fixed}
    assert fixed == {"S1.2", "S2.2", "S3.2", "S4.2"}


# ================== 5. 固定 panel terminal：逐点回放，不被自动座覆盖

def test_panel_terminals_are_fixed_and_replayed_point_for_point():
    ctx, placed, (plans, _page) = _plans()
    seats, failure = dc._panel_terminal_seats(ctx, placed)
    assert failure is None and seats
    for (net_id, member), (anchor, lead, hang) in seats.items():
        plan = next(item for item in plans if item.net == net_id)
        assignment = next(
            item for item in plan.assignments if member in item.members
        )
        assert assignment.seat.fixed
        assert assignment.seat.source == dc.SEAT_FIRST_PANEL
        assert assignment.seat.anchor == anchor
        assert list(assignment.seat.lead) == [tuple(point) for point in lead]
        assert assignment.seat.rotation == dc._flag_rotation(
            (0.0, hang),
            dc.flag_glyph_kind(dc._flag_plan(ctx, net_id, "power")[0]),
        )
    # a fixed terminal is never offered as an automatic candidate result
    three = next(item for item in plans if item.net == "3V3")
    for candidate in three.candidates:
        if candidate.accepted and candidate.seat is not None:
            if candidate.owner in {"S1.2", "S2.2", "S3.2", "S4.2"}:
                assert candidate.seat.fixed


# ================= 6. 负例：固定 terminal 被盖住 = 具名拒绝，不搬座

def test_a_covered_panel_terminal_is_refused_by_name_and_not_moved():
    ctx, placed, _ = _plans()
    anchor = dc._panel_terminal_seats(ctx, placed)[0][("3V3", "S2.2")][0]
    cover = (anchor[0] - 4.0, anchor[1] - 4.0, anchor[0] + 4.0, anchor[1] + 4.0)
    plans, page = dc._seat_first_plans(ctx, placed, obstacles=(cover,))
    assert page is not None
    assert page.category == "layout-unsat"
    assert "S2.2" in page.detail and "covered" in page.detail
    assert "3V3" in page.subject
    # the seat is neither moved nor replaced by an automatic one
    three = next(item for item in plans if item.net == "3V3")
    for assignment in three.assignments:
        if "S2.2" in assignment.members:
            assert assignment.seat.anchor == anchor
    assert not any(
        candidate.accepted and candidate.owner == "S2.2"
        for candidate in three.candidates
    )


# ========= 7. 负例：member 不在页面上 = 具名拒绝，不编造一座

def test_a_member_that_is_not_on_the_page_is_refused_by_name():
    ctx, placed, _ = _plans()
    origins = {
        part_id: origin for part_id, origin in placed.origins.items()
        if part_id != "C1"
    }
    trimmed = dataclasses.replace(placed, origins=origins)
    plans, page = dc._seat_first_plans(ctx, trimmed)
    assert page is None
    details = [item.detail for plan in plans for item in plan.refusals]
    assert any("C1.1" in line or "C1.2" in line for line in details), details
    for plan in plans:
        assert "C1.1" not in plan.assigned_members()
        assert "C1.2" not in plan.assigned_members()


# ================= 8. 当前 placement 的 GND 缺口：具名 + obstacle 证据

def test_the_ground_rail_reports_its_measured_gap_instead_of_a_fallback():
    """The honest reading of this fixture: GND has two named gaps.

    ``C1.2``'s own foot has no legal seat at all (its up run and its down run
    both leave through C1's printed rows), and ``U1.VSS``'s only seat's lead
    stands on the lane the 3V3 pair already claims. Neither is answered by a
    far-away trunk, by merging the branches, or by a moved fixed terminal.
    """
    ctx, placed, (plans, _page) = _plans()
    ground = next(plan for plan in plans if plan.net == "GND")
    assert ground.complete is False
    points = tuple(
        (member, point)
        for member, point in dc._seat_first_points(ctx, placed, "GND")
        if point is not None
    )
    groups = {
        group for _share, group, _members in dc._seat_first_groups(
            ctx, "GND", points)
    }
    assert groups - {item.group for item in ground.assignments} == {
        "alone:C1.2",
    }
    assert len(ground.refusals) == 1, [item.detail for item in ground.refusals]
    by_group = {candidate.group: candidate for candidate in ground.candidates}
    c1 = by_group["alone:C1.2"]
    assert c1.seat is None and c1.refusal is not None
    assert "C1.2" in c1.refusal.detail
    assert "part or text at (" in c1.refusal.detail
    # the order gap is closed: U1.VSS is placed by the joint selection
    assert sorted(ground.assigned_members()) == [
        "D1.2", "D2.2", "R1.2", "U1.VSS",
    ]
    failure = dc._seat_first_validate(ctx, placed, plans)
    missing = {item.detail for item in failure}
    assert any("C1.2" in line and "no seat" in line for line in missing), missing
    assert not any("U1.VSS" in line for line in missing), missing


# =========================================== 9. 确定性：同一页两次同图

def test_the_plan_is_deterministic():
    ctx, placed, (first, _page) = _plans()
    again = dc._seat_first_plans(ctx, placed)
    assert again == (first, None)


# ================= 10. 独立复核：缺座 / 跨座 / 覆盖固定座都变红

def test_the_validator_names_a_missing_assignment():
    ctx, placed, (plans, _page) = _plans()
    three = next(plan for plan in plans if plan.net == "3V3")
    dropped = dataclasses.replace(three, assignments=three.assignments[1:])
    failures = dc._seat_first_validate(
        ctx, placed, [dropped if plan.net == "3V3" else plan for plan in plans],
    )
    assert any(
        "S1.2" in item.detail and "has no seat" in item.detail
        for item in failures
    ), [item.detail for item in failures]
    assert any(
        "S1.2" in item.detail and "fixed terminal was dropped" in item.detail
        for item in failures
    ), [item.detail for item in failures]


def test_the_validator_names_a_run_that_stands_on_another_seat():
    ctx, placed, (plans, _page) = _plans()
    three = next(plan for plan in plans if plan.net == "3V3")
    first, second = three.assignments[0], three.assignments[1]
    broken = dataclasses.replace(
        first, lanes=frozenset(first.lanes | second.seat.occupancy),
    )
    replaced = dataclasses.replace(
        three, assignments=(broken,) + three.assignments[1:],
    )
    failures = dc._seat_first_validate(
        ctx, placed, [replaced if plan.net == "3V3" else plan for plan in plans],
    )
    assert any(
        "share" in item.detail and second.group in item.detail
        for item in failures
    ), [item.detail for item in failures]


def test_the_validator_names_a_member_moved_to_another_seat():
    """The misassignment the validator has to catch: S1.2 pushed into S2.2's seat."""
    ctx, placed, (plans, _page) = _plans()
    three = next(plan for plan in plans if plan.net == "3V3")
    alone1 = next(item for item in three.assignments if item.group == "alone:S1.2")
    alone2 = next(item for item in three.assignments if item.group == "alone:S2.2")
    mixed = dataclasses.replace(
        alone2, members=("S1.2", "S2.2"),
        paths=tuple((member, alone1.path_of(member) or alone2.path_of(member))
                    for member in ("S1.2", "S2.2")),
    )
    replaced = dataclasses.replace(
        three,
        assignments=tuple(
            mixed if item is alone2 else item
            for item in three.assignments if item is not alone1
        ),
    )
    failures = dc._seat_first_validate(
        ctx, placed, [replaced if plan.net == "3V3" else plan for plan in plans],
    )
    details = [item.detail for item in failures]
    assert any(
        "S1.2" in line and "misplaced" in line for line in details
    ), details


def test_the_validator_names_a_cross_rail_seat_conflict():
    """Two rails' real seats on one spot: both directions, all nets."""
    ctx, placed, (plans, _page) = _plans()
    three = next(plan for plan in plans if plan.net == "3V3")
    ground = next(plan for plan in plans if plan.net == "GND")
    donor = three.assignments[0]
    victim = ground.assignments[0]
    broken = dataclasses.replace(victim, seat=donor.seat)
    replaced_ground = dataclasses.replace(
        ground,
        assignments=tuple(
            broken if item is victim else item for item in ground.assignments
        ),
    )
    failures = dc._seat_first_validate(
        ctx, placed,
        [replaced_ground if plan.net == "GND" else plan for plan in plans],
    )
    details = [item.detail for item in failures]
    assert any(
        "3V3" in line and "GND" in line and "share" in line
        for line in details
    ), details


def test_the_validator_names_a_path_through_a_real_body():
    """A path re-run across U1's real body box is not a legal run."""
    ctx, placed, (plans, _page) = _plans()
    three = next(plan for plan in plans if plan.net == "3V3")
    pair = next(
        item for item in three.assignments if item.group == "share:part:U1"
    )
    through = ((-80.0, 50.0), (-60.0, 50.0), (-60.0, 70.0), (-80.0, 70.0))
    moved = tuple(
        (member, through if member == "U1.VBAT" else path)
        for member, path in pair.paths
    )
    broken = dataclasses.replace(pair, paths=moved)
    replaced = dataclasses.replace(
        three,
        assignments=tuple(
            broken if item is pair else item for item in three.assignments
        ),
    )
    failures = dc._seat_first_validate(
        ctx, placed, [replaced if plan.net == "3V3" else plan for plan in plans],
    )
    details = [item.detail for item in failures]
    assert any(
        "U1.VBAT" in line and "crosses the part or text at" in line
        for line in details
    ), details


def test_the_validator_names_a_path_that_ends_elsewhere():
    ctx, placed, (plans, _page) = _plans()
    three = next(plan for plan in plans if plan.net == "3V3")
    pair = next(
        item for item in three.assignments if item.group == "share:part:U1"
    )
    moved = tuple(
        (member, path if member != "U1.VBAT" else path[:-1])
        for member, path in pair.paths
    )
    broken = dataclasses.replace(pair, paths=moved)
    replaced = dataclasses.replace(
        three,
        assignments=tuple(
            broken if item is pair else item for item in three.assignments
        ),
    )
    failures = dc._seat_first_validate(
        ctx, placed, [replaced if plan.net == "3V3" else plan for plan in plans],
    )
    assert any(
        "U1.VBAT" in item.detail and "does not end on the seat's foot" in item.detail
        for item in failures
    ), [item.detail for item in failures]


def test_the_validator_names_a_fixed_terminal_that_was_overridden():
    ctx, placed, (plans, _page) = _plans()
    three = next(plan for plan in plans if plan.net == "3V3")
    fixed = next(item for item in three.assignments if item.seat.fixed)
    auto = dataclasses.replace(fixed.seat, fixed=False, source=dc.SEAT_FIRST_AUTO)
    broken = dataclasses.replace(fixed, seat=auto)
    replaced = dataclasses.replace(
        three,
        assignments=tuple(
            broken if item is fixed else item for item in three.assignments
        ),
    )
    failures = dc._seat_first_validate(
        ctx, placed, [replaced if plan.net == "3V3" else plan for plan in plans],
    )
    assert any(
        "automatic seat" in item.detail for item in failures
    ), [item.detail for item in failures]
    assert any(
        "never enters the automatic selection" in item.detail
        for item in failures
    ), [item.detail for item in failures]


def test_a_detached_pad_is_excluded_by_name_and_never_silently_dropped(monkeypatch):
    """069 sec.2's detached pads keep their existing local flag.

    The plan says so in ``excluded`` (a named fact taken from the expression),
    never as a missing seat; the validator checks the list against the
    expression and refuses an assignment that puts the pad back into a seat.
    """
    ctx, placed, _ = _plans()
    base_plans, _page = dc._seat_first_plans(ctx, placed)
    three_base = next(plan for plan in base_plans if plan.net == "3V3")
    chain = next(
        item for item in three_base.assignments if item.group == "share:chain"
    )
    real = dc._expressions

    def marked(*args, **kwargs):
        found = dict(real(*args, **kwargs))
        found["3V3"] = dataclasses.replace(found["3V3"], detached=("C1.1",))
        return found

    monkeypatch.setattr(dc, "_expressions", marked)
    plans, page = dc._seat_first_plans(ctx, placed)
    assert page is None
    three = next(plan for plan in plans if plan.net == "3V3")
    assert [member for member, _why in three.excluded] == ["C1.1"]
    reason = dict(three.excluded)["C1.1"]
    assert "069" in reason and "detached" in reason
    assert "C1.1" not in three.assigned_members()
    assert not any("C1.1" in item.detail for item in three.refusals)
    failures = dc._seat_first_validate(ctx, placed, plans)
    assert not any(
        "'C1.1'" in item.detail and "has no seat" in item.detail
        for item in failures
    ), [item.detail for item in failures]
    # Negative: an assignment that seats the detached pad again is red by name.
    put_back = dataclasses.replace(three, excluded=(), assignments=(
        three.assignments + (chain,)
    ))
    failures = dc._seat_first_validate(
        ctx, placed,
        [put_back if plan.net == "3V3" else plan for plan in plans],
    )
    assert any(
        "C1.1" in item.detail and "detached pad" in item.detail
        for item in failures
    ), [item.detail for item in failures]


def test_the_validator_names_a_moved_fixed_terminal():
    ctx, placed, (plans, _page) = _plans()
    three = next(plan for plan in plans if plan.net == "3V3")
    fixed = next(item for item in three.assignments if item.seat.fixed)
    moved = dataclasses.replace(
        fixed.seat,
        anchor=(fixed.seat.anchor[0] + 20.0, fixed.seat.anchor[1]),
    )
    broken = dataclasses.replace(fixed, seat=moved)
    replaced = dataclasses.replace(
        three,
        assignments=tuple(
            broken if item is fixed else item for item in three.assignments
        ),
    )
    failures = dc._seat_first_validate(
        ctx, placed, [replaced if plan.net == "3V3" else plan for plan in plans],
    )
    assert any(
        "moved" in item.detail and fixed.seat.owner in item.detail
        for item in failures
    ), [item.detail for item in failures]

# ================================= 11. 34D-A2：跨网联合选择（候选固定后）

def _assignments(plans):
    return {
        plan.net: {item.group: item for item in plan.assignments}
        for plan in plans
    }


def test_the_joint_selection_places_u1_vss_and_the_three_volt_host_group():
    _ctx, _placed, (plans, _page) = _plans()
    answer = _assignments(plans)
    assert "share:chain" in answer["GND"]
    assert answer["GND"]["share:chain"].seat.anchor == (-110.0, 85.0)
    assert "share:part:U1" in answer["3V3"]
    assert answer["3V3"]["share:part:U1"].seat.anchor == (-80.0, 95.0)
    # The two coexist: no node of one seat/lane is a node of the other.
    for first in plans:
        for item in first.assignments:
            for second in plans:
                for other in second.assignments:
                    if item is other:
                        continue
                    assert not (
                        (item.lanes | item.seat.occupancy)
                        & (other.lanes | other.seat.occupancy)
                    ), (first.net, item.group, second.net, other.group)


def test_the_joint_answer_does_not_depend_on_the_net_order():
    ctx, placed, (forward, _page) = _plans()
    reverse, page = dc._seat_first_plans(ctx, placed, order=("GND", "3V3"))
    assert page is None

    def shape(plans):
        return {
            plan.net: sorted(
                (item.group, item.seat.owner, item.seat.anchor,
                 tuple((member, tuple(path)) for member, path in item.paths))
                for item in plan.assignments
            )
            for plan in plans
        }

    assert shape(forward) == shape(reverse)


def test_the_joint_selection_calls_no_route(monkeypatch):
    ctx, placed, _ = _plans()
    real = dc._seat_first_joint

    def guarded(jobs, taken, **kwargs):
        def boom(*args, **kwargs):
            raise AssertionError("the joint selection called _Router.route")
        monkeypatch.setattr(dc._Router, "route", boom)
        return real(jobs, taken, **kwargs)

    monkeypatch.setattr(dc, "_seat_first_joint", guarded)
    plans, page = dc._seat_first_plans(ctx, placed)
    assert page is None and plans


def test_a_page_with_no_joint_solution_is_refused_by_name(monkeypatch):
    ctx, placed, (plans, _page) = _plans()
    three = next(plan for plan in plans if plan.net == "3V3")
    fixed = three.assignments[0]
    base = dc._SeatFirstJob(
        net="3V3", cls="power", share="", group="dup-a",
        members=fixed.members,
        candidates=(dc._SeatFirstCandidate(
            "3V3", "dup-a", fixed.seat.owner, fixed.members, fixed.seat,
            fixed.paths, None, False, fixed.lanes, 0.0,
        ),),
    )
    twin = dataclasses.replace(base, group="dup-b")
    ok, chosen, limit_hit, expansions = dc._seat_first_joint((base, twin), {})
    assert ok is False and chosen == {}
    assert limit_hit is False and expansions <= 2

    def fake_jobs(*args, **kwargs):
        return dc._SeatFirstEnumeration(
            "3V3", "power", (), (base, twin), (), ())

    monkeypatch.setattr(dc, "_seat_first_net_jobs", fake_jobs)
    broken, page = dc._seat_first_plans(ctx, placed)
    assert page is None
    plan = next(item for item in broken if item.net == "3V3")
    assert any(
        "no joint seat allocation exists" in item.detail
        for item in plan.refusals
    ), [item.detail for item in plan.refusals]


def test_the_expansion_limit_is_fixed_and_refused_by_name(monkeypatch):
    assert dc.SEAT_FIRST_EXPANSIONS == 4096
    ctx, placed, _ = _plans()
    monkeypatch.setattr(dc, "SEAT_FIRST_EXPANSIONS", 1)
    plans, page = dc._seat_first_plans(ctx, placed)
    assert page is None
    details = [item.detail for plan in plans for item in plan.refusals]
    assert any("fixed expansion limit (1)" in line for line in details), details


def test_fixed_terminals_and_c1_2_are_unchanged_by_the_joint_selection():
    ctx, placed, (plans, _page) = _plans()
    seats, _failure = dc._panel_terminal_seats(ctx, placed)
    three = next(plan for plan in plans if plan.net == "3V3")
    for (_net, member), (anchor, _lead, _hang) in seats.items():
        item = next(
            assignment for assignment in three.assignments
            if member in assignment.members
        )
        assert item.seat.fixed and item.seat.anchor == anchor
    ground = next(plan for plan in plans if plan.net == "GND")
    assert "C1.2" not in ground.assigned_members()
    assert any("C1.2" in item.detail for item in ground.refusals)

# ================================= 12. 34D-A3：独立支路假设座与一次文字让位

def _text_answer(ctx=None, placed=None):
    ctx = base._context([base._panel_payload()]) if ctx is None else ctx
    if placed is None:
        placed, failure = base._base(ctx)
        assert failure is None, failure.detail
    return ctx, placed, dc._seat_first_text_plan(ctx, placed)


def test_the_one_relayout_makes_the_missing_branch_complete_on_real_texts():
    ctx, placed, answer = _text_answer()
    assert tuple(plan.net for plan in answer.plans) == ("3V3", "GND")
    assert all(plan.complete for plan in answer.plans), [
        item.detail for plan in answer.plans for item in plan.refusals]
    ground = next(plan for plan in answer.plans if plan.net == "GND")
    assert "C1.2" in ground.assigned_members()
    failures = dc._seat_first_validate(ctx, placed, answer.plans,
                                       scene=answer.scene)
    assert not any("C1.2" in item.detail for item in failures), [
        item.detail for item in failures]


def test_the_hypothetical_seat_is_never_written_into_an_assignment():
    _ctx, _placed, answer = _text_answer()
    assert [(net, group) for net, group, _seat in answer.hypothetical] == [
        ("GND", "alone:C1.2"),
    ]
    hypothetical = answer.hypothetical[0][2]
    ground = next(plan for plan in answer.plans if plan.net == "GND")
    item = next(
        assignment for assignment in ground.assignments
        if "C1.2" in assignment.members
    )
    assert item.seat is not hypothetical
    assert item.seat.anchor != hypothetical.anchor, (
        "the real re-enumeration happens to match the hypothesis; this fixture "
        "was expected not to converge — re-check the acceptance rule")


def test_the_relayout_moves_real_text_and_reserves_the_hypothetical_flag():
    ctx, placed, answer = _text_answer()
    occupied, text_walls = dc._seat_first_text_inputs(ctx, placed)
    first, failure = dc._part_texts(ctx, placed, occupied, text_walls)
    assert failure is None
    assert tuple(text.bbox for text in first) != tuple(
        text.bbox for text in answer.scene.texts), (
        "the one re-layout did not move any printed row")
    hypothetical = answer.hypothetical[0][2]
    for text in answer.scene.texts:
        assert not dc._panel_boxes_overlap(text.bbox, hypothetical.glyph), (
            text.text, text.bbox, hypothetical.glyph)


def test_the_final_texts_and_the_plan_use_one_and_the_same_scene():
    ctx, placed, answer = _text_answer()
    for text in answer.scene.texts:
        assert text.bbox in answer.scene.solids
    plans, page = dc._seat_first_plans(ctx, placed, scene=answer.scene)
    assert page is None
    assert plans == answer.plans


def test_a_non_converging_relayout_is_refused_by_name():
    _ctx, _placed, answer = _text_answer()
    assert answer.ok is False
    details = [item.detail for item in answer.refusals]
    assert any(
        "hypothetical seat of 'alone:C1.2'" in line
        and "moved in the real scene" in line
        for line in details
    ), details
    assert any(
        "may not move a seat the page already had" in line for line in details
    ), details


def test_fixed_terminals_are_untouched_by_the_relayout():
    ctx, placed, answer = _text_answer()
    seats, failure = dc._panel_terminal_seats(ctx, placed)
    assert failure is None
    three = next(plan for plan in answer.plans if plan.net == "3V3")
    for (_net, member), (anchor, lead, _hang) in seats.items():
        item = next(
            assignment for assignment in three.assignments
            if member in assignment.members
        )
        assert item.seat.fixed
        assert item.seat.anchor == anchor
        assert list(item.seat.lead) == [tuple(point) for point in lead]


def test_a_page_without_panel_groups_has_no_text_plan():
    ctx = base._context(None)
    placed, failure = base._base(ctx)
    assert failure is None
    answer = dc._seat_first_text_plan(ctx, placed)
    assert answer.plans == () and answer.hypothetical == ()
    assert answer.scene.texts == ()

# =========================== 13. 34D-A4：重排终态独立验收（A3 不改）

def _terminal(ctx=None, placed=None):
    ctx = base._context([base._panel_payload()]) if ctx is None else ctx
    if placed is None:
        placed, failure = base._base(ctx)
        assert failure is None, failure.detail
    return ctx, placed, dc._seat_first_text_terminal(ctx, placed)


def test_a3_still_refuses_while_the_terminal_scene_is_complete():
    ctx, placed, terminal = _terminal()
    assert terminal.discovery.ok is False, (
        "A4 must not turn A3 green")
    assert len(terminal.discovery.refusals) == 3
    assert terminal.ok is True, [item.detail for item in terminal.refusals]
    assert all(plan.complete for plan in terminal.plans)
    ground = next(plan for plan in terminal.plans if plan.net == "GND")
    item = next(a for a in ground.assignments if "C1.2" in a.members)
    # the real natural seat, not the hypothesis
    assert item.seat.anchor == (-140.0, -15.0)
    hypothetical = terminal.discovery.hypothetical[0][2]
    assert item.seat is not hypothetical
    assert item.seat.anchor != hypothetical.anchor


def test_the_terminal_plan_is_freshly_enumerated_and_replays_its_scene():
    ctx, placed, terminal = _terminal()
    fresh, page = dc._seat_first_plans(ctx, placed, scene=terminal.scene)
    assert page is None
    assert fresh == terminal.plans
    again = dc._seat_first_text_terminal(ctx, placed)
    assert again.plans == terminal.plans
    assert again.ok == terminal.ok
    assert [item.detail for item in again.refusals] == [
        item.detail for item in terminal.refusals]


def test_a_text_collision_on_the_terminal_scene_is_refused_by_name():
    ctx, placed, terminal = _terminal()
    reference = next(t for t in terminal.scene.texts if t.part_id == "U1")
    body = dc._body_box(
        ctx.profile("U1"), placed.poses["U1"], placed.origins["U1"],
    )
    moved = dataclasses.replace(
        reference, bbox=(body[0] + 1.0, body[1] + 1.0,
                         body[0] + 6.0, body[1] + 6.0),
    )
    bad_scene = dataclasses.replace(
        terminal.scene,
        texts=tuple(moved if t is reference else t for t in terminal.scene.texts),
    )
    failures = dc._seat_first_text_box_failures(
        ctx, placed, bad_scene, terminal.plans)
    assert any(
        "overlaps a part or a keep-out" in item.detail for item in failures
    ), [item.detail for item in failures]
    doubled = dataclasses.replace(
        terminal.scene,
        texts=terminal.scene.texts + (reference,),
    )
    failures = dc._seat_first_text_box_failures(
        ctx, placed, doubled, terminal.plans)
    assert any(
        "printed rows" in item.detail and "overlap" in item.detail
        for item in failures
    ), [item.detail for item in failures]


def test_a_moved_fixed_terminal_on_the_terminal_plan_is_refused_by_name():
    ctx, placed, terminal = _terminal()
    three = next(plan for plan in terminal.plans if plan.net == "3V3")
    fixed = next(item for item in three.assignments if item.seat.fixed)
    moved = dataclasses.replace(
        fixed.seat,
        anchor=(fixed.seat.anchor[0] + 20.0, fixed.seat.anchor[1]),
    )
    doctored = dataclasses.replace(terminal.plans[0], assignments=tuple(
        dataclasses.replace(item, seat=moved) if item is fixed else item
        for item in three.assignments
    ))
    failures = dc._seat_first_terminal_fixed_failures(
        ctx, placed, (doctored, *terminal.plans[1:]))
    assert any(
        "moved on the final text scene" in item.detail
        and fixed.seat.owner in item.detail
        for item in failures
    ), [item.detail for item in failures]


def test_an_incomplete_terminal_plan_is_refused_by_name(monkeypatch):
    ctx, placed, answer = _terminal()
    broken = tuple(
        dataclasses.replace(
            plan, assignments=plan.assignments[:-1],
            refusals=(dc._seat_first_refusal(plan.net, "incomplete (test)"),),
        )
        for plan in answer.plans
    )
    real_text = dc._seat_first_text_plan

    def trimmed(*args, **kwargs):
        return dataclasses.replace(real_text(*args, **kwargs), plans=broken)

    monkeypatch.setattr(dc, "_seat_first_text_plan", trimmed)
    monkeypatch.setattr(dc, "_seat_first_plans", lambda *a, **k: (broken, None))
    terminal = dc._seat_first_text_terminal(ctx, placed)
    assert terminal.ok is False
    assert any(
        "is not complete on the final text scene" in item.detail
        for item in terminal.refusals
    ), [item.detail for item in terminal.refusals]

# ============ 14. 34D-B：terminal 终态与 panel 宿主引线的接口缺口（实测反证）

def test_the_terminal_text_layout_breaks_the_panel_host_channel_today():
    """34D-B is blocked here: same-source replay needs a scene the host accepts.

    The one re-layout that makes C1.2 complete on the real texts moves U1's own
    rows above the part (y > 90), and the panel host-lead channel for cell S3
    then meets them. With the page's own texts the same channel is clean, so
    this is the final scene, not the channel, and production replay of that
    scene (`_build_one_variant`) refuses the page by name. Until the terminal's
    single re-layout knows the panel host corridors, the plan's texts and the
    drawing's leads cannot be one answer.
    """
    ctx, placed, terminal = _terminal()
    assert terminal.ok is True
    occupied, walls = dc._seat_first_text_inputs(ctx, placed)
    own_texts, failure = dc._part_texts(ctx, placed, occupied, walls)
    assert failure is None
    _channels, own_problem = dc._panel_channels(ctx, placed, texts=own_texts)
    assert own_problem is None
    _channels, problem = dc._panel_channels(
        ctx, placed, texts=list(terminal.scene.texts))
    assert problem is not None and problem.category == "layout-unsat"
    assert "S3" in problem.detail
    assert any(
        text.part_id == "U1" and text.bbox[1] > 90.0
        for text in terminal.scene.texts
    ), [(text.part_id, text.bbox) for text in terminal.scene.texts]

# ====== 15. 34D-B0：宿主通道进入 terminal 场景（生产入口，未接 build）

def _channel_terminal(ctx=None, placed=None):
    ctx = base._context([base._panel_payload()]) if ctx is None else ctx
    if placed is None:
        placed, failure = base._base(ctx)
        assert failure is None, failure.detail
    return ctx, placed, dc._seat_first_channel_terminal(ctx, placed)


def test_the_channel_aware_terminal_keeps_the_channels_and_completes_c1():
    ctx, placed, answer = _channel_terminal()
    assert answer.ok, [item.detail for item in answer.refusals]
    assert answer.terminal.discovery_ok is False, "A3 must still refuse"
    assert [plan.net for plan in answer.terminal.plans] == ["3V3", "GND"]
    assert all(plan.complete for plan in answer.terminal.plans)
    ground = next(plan for plan in answer.terminal.plans if plan.net == "GND")
    item = next(a for a in ground.assignments if "C1.2" in a.members)
    assert item.seat.anchor == (-170.0, -15.0)
    # channels: same drawing before and after, and the S3 refusal is gone
    final, problem = dc._panel_channels(
        ctx, placed, texts=list(answer.terminal.scene.texts))
    assert problem is None
    assert dc._seat_first_channel_drift(answer.channels, final) is None
    assert set(final) == {"KEY1", "KEY2", "KEY3", "KEY4"}
    # fixed terminals untouched; no text and no run on a channel wall
    seats, failure = dc._panel_terminal_seats(ctx, placed)
    assert failure is None
    three = next(plan for plan in answer.terminal.plans if plan.net == "3V3")
    for (_net, member), (anchor, lead, _hang) in seats.items():
        found = next(a for a in three.assignments if member in a.members)
        assert found.seat.fixed and found.seat.anchor == anchor
    assert dc._seat_first_channel_text_failures(
        answer.terminal.scene, answer.walls) == []
    assert dc._seat_first_channel_seat_failures(
        answer.terminal.plans, answer.walls) == []


def test_a_text_row_on_a_host_channel_is_refused_by_name():
    ctx, placed, answer = _channel_terminal()
    wall = answer.walls[0]
    text = answer.terminal.scene.texts[0]
    moved = dataclasses.replace(text, bbox=(
        wall[0] + 0.5, wall[1] + 0.5, wall[2] - 0.5, wall[3] - 0.5,
    ))
    bad = dataclasses.replace(
        answer.terminal.scene,
        texts=tuple(moved if t is text else t
                    for t in answer.terminal.scene.texts),
    )
    failures = dc._seat_first_channel_text_failures(bad, answer.walls)
    assert any(
        "stands on a panel host channel" in item.detail for item in failures
    ), [item.detail for item in failures]


def test_a_seat_run_on_a_host_channel_is_refused_by_name():
    _ctx, _placed, answer = _channel_terminal()
    ground = next(plan for plan in answer.terminal.plans if plan.net == "GND")
    item = ground.assignments[0]
    wall = answer.walls[0]
    through = (
        (wall[0] - 1.0, (wall[1] + wall[3]) / 2.0),
        (wall[2] + 1.0, (wall[1] + wall[3]) / 2.0),
    )
    doctored_seat = dataclasses.replace(item.seat, lead=through)
    doctored = dataclasses.replace(
        ground, assignments=(
            dataclasses.replace(item, seat=doctored_seat),
        ) + ground.assignments[1:],
    )
    failures = dc._seat_first_channel_seat_failures(
        (doctored, *answer.terminal.plans[1:]), answer.walls)
    assert any(
        "stands on a panel host channel" in item.detail for item in failures
    ), [item.detail for item in failures]


def test_a_changed_host_channel_after_the_relayout_is_refused_by_name():
    _ctx, _placed, answer = _channel_terminal()
    net = sorted(answer.channels)[0]
    moved = tuple(
        dataclasses.replace(
            segment,
            points=[(segment.points[0][0], segment.points[0][1] + 5.0),
                    (segment.points[-1][0], segment.points[-1][1] + 5.0)],
        )
        for segment in answer.channels[net]
    )
    doctored = dict(answer.channels)
    doctored[net] = moved
    drift = dc._seat_first_channel_drift(answer.channels, doctored)
    assert drift is not None and drift.category == "layout-unsat"
    assert "changed after the text re-layout" in drift.detail


# ====== 16. 34D-B1：label 座位进入 terminal 场景（生产入口，未接 build）

def _label_terminal(ctx=None, placed=None, named=()):
    ctx = base._context([base._panel_payload()]) if ctx is None else ctx
    if placed is None:
        placed, failure = base._base(ctx)
        assert failure is None, failure.detail
    return ctx, placed, dc._seat_first_label_terminal(ctx, placed, named=named)


def _named_box_labels(ctx, placed, answer, net_id):
    """The names a build would print for one net, seated by the real ladder.

    The compiler's own `_label_for` is the only ladder used: the obstacles are
    the B0 texts, the B0 host-channel walls and every part extent, exactly the
    ones the label-aware terminal would hand it.
    """
    occupied = [
        dc._part_box(ctx.profile(part_id), placed.poses[part_id],
                     placed.origins[part_id])
        for part_id in sorted(placed.origins)
    ]
    occupied.extend(text.bbox for text in answer.scene.texts)
    occupied.extend(answer.walls)
    expressions = dc._expressions(ctx, placed)
    out = []
    for member, point in sorted(expressions[net_id].points):
        part_id, _, token = member.partition(".")
        label = dc._label_for(ctx, net_id, part_id, token, point, placed, occupied)
        occupied.append(label.bbox)
        out.append(label)
    return tuple(out)


def test_the_fixture_names_no_net_by_label_so_the_map_is_empty():
    _ctx, _placed, answer = _label_terminal()
    assert answer.ok, [item.detail for item in answer.refusals]
    assert answer.labels == ()
    assert all(plan.complete for plan in answer.plans)
    # the B0 answer is unchanged by an empty label map
    _ctx2, _placed2, b0 = _channel_terminal()
    assert answer.plans == b0.terminal.plans


def test_a_printed_name_is_seated_before_the_plan_and_the_plan_moves_off_it():
    ctx, placed, b0 = _label_terminal()
    named = _named_box_labels(ctx, placed, b0, "BOOT0")
    boxes = sorted(label.bbox for label in named)
    assert (-127.0, 35.5, -88.0, 44.5) in boxes
    _ctx, _placed, answer = _label_terminal(ctx, placed, named=named)
    assert answer.ok, [item.detail for item in answer.refusals]
    assert all(plan.complete for plan in answer.plans)
    # the name boxes are on the scene the plan was measured on
    for label in named:
        assert label.bbox in answer.scene.solids
    # no run or lead touches a name
    assert dc._seat_first_label_failures(
        answer.scene, answer.labels, answer.walls, answer.plans) == []
    # U1.VSS may not keep the seat the BOOT0 name stands in: it re-enumerates
    ground = next(plan for plan in answer.plans if plan.net == "GND")
    item = next(a for a in ground.assignments if "U1.VSS" in a.members)
    assert item.seat.anchor == (-110.0, 85.0)


def test_the_label_aware_plan_is_the_same_answer_twice():
    ctx, placed, b0 = _label_terminal()
    named = _named_box_labels(ctx, placed, b0, "BOOT0")
    _ctx, _placed, first = _label_terminal(ctx, placed, named=named)
    _ctx2, _placed2, again = _label_terminal(ctx, placed, named=named)
    assert first.plans == again.plans
    assert [box for _net, _point, box in first.labels] == [
        box for _net, _point, box in again.labels]


def test_a_name_standing_on_a_printed_row_is_refused_by_name():
    ctx, placed, b0 = _label_terminal()
    named = _named_box_labels(ctx, placed, b0, "BOOT0")
    text = b0.scene.texts[0]
    landed = tuple(
        dataclasses.replace(label, bbox=text.bbox) if index == 0 else label
        for index, label in enumerate(named)
    )
    answer = dc._seat_first_label_terminal(ctx, placed, named=landed)
    assert not answer.ok
    assert any(
        "stands on the printed row" in item.detail for item in answer.refusals
    ), [item.detail for item in answer.refusals]


def test_a_name_standing_on_a_host_channel_is_refused_by_name():
    ctx, placed, b0 = _label_terminal()
    named = _named_box_labels(ctx, placed, b0, "BOOT0")
    wall = b0.walls[0]
    landed = tuple(
        dataclasses.replace(label, bbox=wall) if index == 0 else label
        for index, label in enumerate(named)
    )
    answer = dc._seat_first_label_terminal(ctx, placed, named=landed)
    assert not answer.ok
    assert any(
        "stands on a panel host channel" in item.detail
        for item in answer.refusals
    ), [item.detail for item in answer.refusals]


def test_a_run_through_a_name_is_refused_by_name():
    ctx, placed, b0 = _label_terminal()
    named = _named_box_labels(ctx, placed, b0, "BOOT0")
    _ctx, _placed, answer = _label_terminal(ctx, placed, named=named)
    label = named[1]
    ground = next(plan for plan in answer.plans if plan.net == "GND")
    item = ground.assignments[0]
    through = (
        (label.bbox[0] - 1.0, (label.bbox[1] + label.bbox[3]) / 2.0),
        (label.bbox[2] + 1.0, (label.bbox[1] + label.bbox[3]) / 2.0),
    )
    doctored = dataclasses.replace(
        item, seat=dataclasses.replace(item.seat, lead=through))
    failures = dc._seat_first_label_failures(
        answer.scene, answer.labels, answer.walls,
        (dataclasses.replace(ground, assignments=(
            doctored,) + ground.assignments[1:]), *answer.plans[1:]),
    )
    assert any(
        "runs through the label" in failure.detail for failure in failures
    ), [failure.detail for failure in failures]


# ====== 17. 34D-B2a：信号 preflight 与真实 fallback（未接 build）

def _signals(ctx=None, placed=None):
    ctx = base._context([base._panel_payload()]) if ctx is None else ctx
    if placed is None:
        placed, failure = base._base(ctx)
        assert failure is None, failure.detail
    base_answer = dc._seat_first_channel_terminal(ctx, placed)
    assert base_answer.ok
    signals = dc._seat_first_signal_preflight(
        ctx, placed, base_answer.terminal.scene, base_answer.channels)
    return ctx, placed, base_answer, signals


def test_the_signal_preflight_routes_what_it_can_and_names_what_it_cannot():
    _ctx, _placed, _base, signals = _signals()
    assert [net for net, _runs in signals.segments] == ["BOOT0", "LED2"]
    assert [net for net, _reason in signals.fallbacks] == ["LED1"]
    reason = signals.fallbacks[0][1]
    assert reason.startswith("trunk:") and "no free run" in reason
    assert all(run.points for _net, runs in signals.segments for run in runs)
    assert signals.walls and all(
        box[2] > box[0] and box[3] > box[1] for box in signals.walls)


def test_a_real_fallback_net_gets_a_name_at_every_pin():
    ctx, placed, b0, signals = _signals()
    answer = dc._seat_first_label_terminal(
        ctx, placed, extra_walls=signals.walls,
        fallback_nets=tuple(net for net, _reason in signals.fallbacks),
        signal_segments=tuple(
            item for _net, runs in signals.segments for item in runs),
    )
    assert answer.ok, [item.detail for item in answer.refusals]
    named = [(net, box) for net, _point, box in answer.labels]
    assert [net for net, _box in named] == ["LED1", "LED1"]
    expressions = dc._expressions(ctx, placed)
    assert len(expressions["LED1"].points) == 2
    for _net, _point, label in answer.labels:
        assert label.text == "LED1"
        assert label.bbox in answer.scene.solids


def test_a_plan_vertex_on_a_pre_flighted_signal_is_refused_by_name():
    _ctx, _placed, _b0, signals = _signals()
    plan = dc._SeatFirstPlan("GND", "gnd", (), (), ())
    run = signals.segments[0][1][0]
    vertex = run.points[1]
    seat = dc._SeatFirstSeat(
        net="GND", owner="U1.VSS", anchor=vertex, rotation=0.0,
        lead=(vertex,), fixed=False, source=dc.SEAT_FIRST_AUTO,
        glyph=(vertex[0], vertex[1], vertex[0], vertex[1]),
        occupancy=frozenset(),
    )
    assignment = dc._SeatFirstAssignment(
        net="GND", share="", group="alone:U1.VSS",
        members=("U1.VSS",), seat=seat, paths=(("U1.VSS", (vertex,)),),
    )
    doctored = dataclasses.replace(plan, assignments=(assignment,))
    failures = dc._seat_first_signal_failures(
        signals, dc._SeatFirstScene((), (), ()), (), (doctored,))
    assert any(
        "stands on the pre-flighted signal" in item.detail
        for item in failures
    ), [item.detail for item in failures]


def test_the_signal_terminal_reports_the_measured_lead_clash_today():
    """The current placement cannot hold both: named, not papered over."""
    ctx = base._context([base._panel_payload()])
    placed, failure = base._base(ctx)
    assert failure is None
    answer = dc._seat_first_signal_terminal(ctx, placed)
    assert all(plan.complete for plan in answer.plans)
    assert [plan.net for plan in answer.plans] == ["3V3", "GND"]
    details = [item.detail for item in answer.refusals]
    assert any("stands on the pre-flighted signal" in text for text in details), details
    assert any("'LED2'" in text or "'BOOT0'" in text for text in details), details


def test_the_default_label_terminal_ignores_the_signal_inputs():
    ctx, placed, b0 = _label_terminal()
    _ctx, _placed, b1 = _label_terminal()
    assert b1.plans == b0.plans
    assert b1.labels == ()
    assert b1.extra_walls == ()


# ====== 18. 34D-B2b：座位先行、信号绕座、只重求 member paths（原型）

def _ordered(ctx=None, placed=None):
    ctx = base._context([base._panel_payload()]) if ctx is None else ctx
    if placed is None:
        placed, failure = base._base(ctx)
        assert failure is None, failure.detail
    return ctx, placed, dc._seat_first_ordered_terminal(ctx, placed)


def test_the_ordered_pass_takes_the_b0_seats_and_builds_their_walls():
    ctx, placed, answer = _ordered()
    b0 = dc._seat_first_channel_terminal(ctx, placed)
    assert answer.seat_walls
    groups = {key for key, _boxes in answer.seat_walls}
    assert groups == {
        (plan.net, item.group)
        for plan in b0.terminal.plans for item in plan.assignments
    }
    for (net, group), boxes in answer.seat_walls:
        plan = next(item for item in b0.terminal.plans if item.net == net)
        seat = next(item.seat for item in plan.assignments if item.group == group)
        assert seat.glyph in boxes
    assert answer.signals.segments


def test_the_ordered_terminal_names_the_member_and_seat_it_cannot_reach():
    """B2b's stop rule: the same seat, re-solved, has no legal path here."""
    _ctx, _placed, answer = _ordered()
    assert not answer.ok
    details = [item.detail for item in answer.refusals]
    assert any(
        "'U1.VBAT'" in text and "share:part:U1" in text and "no legal path" in text
        for text in details
    ), details
    assert any("(-80, 95)" in text for text in details), details
    # no seat is invented or moved: the failing group has no assignment, the
    # other ten keep their B0 seats
    three = next(plan for plan in answer.plans if plan.net == "3V3")
    assert "share:part:U1" not in {item.group for item in three.assignments}
    assert len(three.assignments) == 5
    ground = next(plan for plan in answer.plans if plan.net == "GND")
    assert len(ground.assignments) == 5


def test_the_ordered_pass_refuses_a_seat_that_is_not_the_b0_seat():
    ctx, placed, answer = _ordered()
    baseline = dc._seat_first_label_terminal(ctx, placed).plans
    plan = next(item for item in baseline if item.net == "GND")
    item = plan.assignments[0]
    moved = dataclasses.replace(
        item, seat=dataclasses.replace(item.seat, anchor=(
            item.seat.anchor[0] + 10.0, item.seat.anchor[1])))
    failures = dc._seat_first_ordered_failures(
        (dataclasses.replace(plan, assignments=(moved,) + plan.assignments[1:]),
         *baseline[1:]),
        baseline, answer.signals, answer.labels, answer.scene, answer.walls,
    )
    assert any("moved from the B0" in f.detail for f in failures), [
        f.detail for f in failures]


def test_the_ordered_pass_refuses_a_path_vertex_on_a_signal_run():
    _ctx, _placed, answer = _ordered()
    plan = next(item for item in answer.plans if item.net == "GND")
    item = plan.assignments[0]
    run = answer.signals.segments[0][1][0]
    vertex = run.points[1]
    doctored = dataclasses.replace(
        item, paths=((item.members[0], (vertex, item.seat.lead[0])),))
    failures = dc._seat_first_ordered_failures(
        (dataclasses.replace(plan, assignments=(doctored,) + plan.assignments[1:]),
         *answer.plans[1:]),
        answer.plans, answer.signals, answer.labels, answer.scene, answer.walls,
    )
    assert any(
        "shares the vertex" in f.detail for f in failures
    ), [f.detail for f in failures]
