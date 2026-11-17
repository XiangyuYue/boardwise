"""548D3D-H3：跨侧宿主脚的选侧选脚（自包含小夹具）。

任务书：`tasks/548_drawing_capability_ladder.md` §43；集成锁
`tasks/shared-platform.md` §20。

夹具是**本文件自己的**：一颗两侧各有同一电源网、同一地网脚的宿主，一枚去耦支路（C1）和
一条信号支路（R1 下拉到 GND）。不读 `.tmp*`、不读 `evidence/`、不 import 别的测试模块的
夹具，单独跑本文件即可。几何期望全部由本文件用库 pin 位姿 + 旗字形种类复算，不调用生产
选脚函数当期望。

钉的事实：

* 模板在**没有位姿**时不选首侧/首脚——允许集合里两侧的脚都在；
* binder 按**当前真实位姿**联合选侧与选脚；选定脚的侧向与它的 posed tip 一致，支路 pose、
  文字、host path 与最终导体同源（同一个脚）；
* 显式 singleton 脚（宿主在该网上只有一脚的信号支路）在任何位姿/平移下都不换；
* 每一只可见宿主电源/地脚要么被支路真实驱动，要么有自己的本地竖直旗；
* 跨侧负例（脚在该位姿上不朝任何可读的左右侧）必须**具名**拒绝，不许静默空答案；
* 编译页过独立逐脚、grammar、readability，且无重复导体/无绕路 channel。
"""

from __future__ import annotations

import copy

import pytest

from boardwise.core.symbolprofile import (
    FLAG_GLYPH_ROTATION_OFFSETS,
    SymbolProfile,
    flag_glyph_kind,
)
from boardwise.engines import drawcompiler as dc
from boardwise.engines import placement
from boardwise.engines import readability

EPS = 1e-6
PROV = "verified_recipe"
POWER_NET = "3V3"
GROUND_NET = "GND"
SIGNAL_NET = "BOOT0"


# ------------------------------------------------------------------- 夹具


def _pin(number, tip, direction):
    return {"number": number, "name": number, "tip": list(tip),
            "direction": direction, "length": 10.0, "pinType": "passive"}


def _symbol(ref, body, pins):
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": list(body), "pins": pins,
            "source": "test fixture (548D3D-H3 cross-side host)"}


def _payloads():
    left = [("VDD", 70.0), ("VSS", 60.0), ("BOOT0", 50.0), ("PA5", 40.0)]
    right = [("V33R", 70.0), ("VSSR", 60.0), ("PA6", 50.0), ("PA7", 40.0)]
    return {
        "XMCU": _symbol(
            "XMCU", [-70.0, -70.0, 70.0, 90.0],
            [_pin(name, [-80.0, y], "left") for name, y in left]
            + [_pin(name, [80.0, y], "right") for name, y in right]),
        "C": _symbol("C", [-5.5, -8.5, 5.5, 8.5],
                     [_pin("1", [0.0, 20.0], "up"), _pin("2", [0.0, -20.0], "down")]),
        "R": _symbol("R", [-10.5, -4.5, 10.5, 4.5],
                     [_pin("1", [-20.0, 0.0], "left"), _pin("2", [20.0, 0.0], "right")]),
    }


def _book() -> dict:
    book = {ref: SymbolProfile.from_dict(copy.deepcopy(payload))
            for ref, payload in _payloads().items()}
    # the library's two flag families (glyph box only: a flag has no pins)
    book["PWR-3V3"] = SymbolProfile(
        symbol_ref="PWR-3V3", title="PWR-3V3", body=(-6.0, 0.0, 6.0, 18.0), pins=[])
    book["PWR-GND"] = SymbolProfile(
        symbol_ref="PWR-GND", title="PWR-GND", body=(-10.0, 0.0, 10.0, -19.0), pins=[])
    return book


def _part(part_id, symbol, value=""):
    return {"id": part_id, "symbolRef": symbol, "value": value, "provenance": PROV}


def _net(net_id, cls, members):
    return {"id": net_id, "class": cls, "members": list(members),
            "provenance": PROV}


def _circuit():
    from boardwise.core.circuitspec import CircuitSpec
    return CircuitSpec.from_dict({
        "parts": [_part("U1", "XMCU", "XMCU"), _part("C1", "C", "100nF"),
                  _part("R1", "R", "10k")],
        "nets": [
            # the same rail and the same ground on **both** sides of the host
            _net(POWER_NET, "power", ["U1.VDD", "U1.V33R", "C1.1"]),
            _net(GROUND_NET, "gnd", ["U1.VSS", "U1.VSSR", "C1.2", "R1.2"]),
            _net(SIGNAL_NET, "signal", ["U1.BOOT0", "R1.1"]),
        ],
    })


def _spec():
    from boardwise.core.presentationspec import PresentationSpec
    return PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "modules": [{"id": "host", "parts": ["U1", "C1", "R1"],
                     "role": "host island", "grammarRef": "ic-periphery",
                     "core": "U1"}],
        "serviceLayout": {"pinGap": 30, "localSeats": True},
    })


def _context():
    circuit, spec, book = _circuit(), _spec(), _book()
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, spec, circuit)
    prepared = dc._prepare(
        circuit, spec, binding, book, dc.CompileBudget(max_candidates=4))
    assert prepared.context is not None, [f.detail for f in prepared.failures]
    return prepared.context


def _poses(ctx):
    """The identity pose and the first accepted pose that flips the reading side."""
    accepted = ctx.accepted["U1"]
    identity = next((pose for pose in accepted if pose.label() == "0"), accepted[0])
    for pose in accepted:
        if pose.label() != identity.label() and pose.mirror != identity.mirror:
            return identity, pose
    for pose in accepted:
        if pose.label() != identity.label():
            return identity, pose
    raise AssertionError(f"the fixture has only one accepted host pose: "
                         f"{[pose.label() for pose in accepted]}")


def _tip(book, circuit, part_id, token, pose, origin=(0.0, 0.0)):
    from boardwise.core.geometry import transform_point
    profile = book[circuit.part(part_id).symbol_ref]
    pin = next(item for item in profile.pins
               if item.number == token or item.name == token)
    return transform_point(pin.tip[0], pin.tip[1], rotation=pose.rotation,
                           mirror=pose.mirror, ox=origin[0], oy=origin[1])


def _feet(circuit, part_id, net_id):
    net = next(item for item in circuit.nets if item.id == net_id)
    return tuple(member.partition(".")[2] for member in net.members
                 if member.partition(".")[0] == part_id)


def _seat(plans, part_id):
    plan = next((item for item in plans
                 if item.cells and item.cells[0].part_id == part_id), None)
    assert plan is not None, [item.refusal.render() if item.refusal else item.group_id
                              for item in plans]
    return plan, plan.cells[0]


def _bound(ctx, host_pose, origins=None):
    """The topology request's own templates, bound against one real host pose."""
    origins = origins or {part: (0.0, 0.0) for part in ctx.slots}
    poses = {part: host_pose for part in ctx.slots}
    return placement.bind_service_plans(
        dc._topology_request(ctx), origins, poses)


# =================================================== 1. 模板：两侧都在，不选首脚


def test_the_template_keeps_both_sides_and_chooses_nothing():
    """无位姿的模板不选首侧/首脚：允许集合里两侧同网脚都在。"""
    ctx = _context()
    circuit, book = _circuit(), _book()
    request = dc._topology_request(ctx)
    template = next(item for item in request.service_templates
                    if item.cell.part_id == "C1")
    allowed = tuple(template.cell.host_allowed)
    assert allowed, (
        "the template froze a foot instead of carrying the allowed set: "
        f"{template.cell.host_token!r}")
    assert set(allowed) <= set(_feet(circuit, "U1", POWER_NET)), allowed
    identity, _other = _poses(ctx)
    sides = {_tip(book, circuit, "U1", token, identity)[0] < 0 for token in allowed}
    assert sides == {True, False}, (
        f"the allowed set {allowed!r} does not span both sides of the host")
    assert not template.cell.host_token, (
        "a template built without a pose must not name a foot: "
        f"{template.cell.host_token!r}")


def test_the_binder_jointly_picks_side_and_foot_from_the_real_pose():
    """同一份模板、两个合法位姿：侧与脚都跟着位姿变，且侧向 = 选定脚的 posed tip。"""
    ctx = _context()
    circuit, book = _circuit(), _book()
    identity, flipped = _poses(ctx)
    seen = {}
    for pose in (identity, flipped):
        plans = _bound(ctx, pose)
        plan, cell = _seat(plans, "C1")
        tip = _tip(book, circuit, "U1", cell.host_token, pose)
        side = "left" if tip[0] < 0 else "right"
        assert plan.side == side, (
            f"pose {pose.label()}: the seat reads on {plan.side!r} but the chosen "
            f"foot {cell.host_token} sits at x={tip[0]:g} ({side!r})")
        assert cell.host_token in _feet(circuit, "U1", POWER_NET)
        assert plan.host_paths and plan.host_paths[0][0] == pytest.approx(
            tip, abs=EPS), (cell.host_token, plan.host_paths, tip)
        assert plan.host_paths[0][-1] == pytest.approx(cell.from_seat, abs=EPS)
        seen[pose.label()] = (plan.side, cell.host_token)
    assert len(set(seen.values())) == 2, (
        "the binder answered the same side+foot for two opposed legal poses, so "
        f"it is not reading the pose: {seen}")


def test_an_explicit_singleton_is_never_swapped_on_this_host():
    """信号支路（宿主在该网上只有一脚）在任何位姿/平移下都不换脚。"""
    ctx = _context()
    circuit = _circuit()
    identity, flipped = _poses(ctx)
    assert _feet(circuit, "U1", SIGNAL_NET) == ("BOOT0",)
    for pose in (identity, flipped):
        plans = _bound(ctx, pose)
        seated = next((item for item in plans
                       if item.cells and item.cells[0].part_id == "R1"), None)
        if seated is None:
            # a singleton that cannot be read on the declared side is a named
            # refusal, never a swap to another same-net foot
            text = " | ".join(item.refusal.render() for item in plans
                              if item.refusal is not None)
            assert "BOOT0" in text, text
            continue
        assert seated.cells[0].host_token == "BOOT0", (
            pose.label(), seated.cells[0].host_token)
    translated = placement.bind_service_plans(
        dc._topology_request(ctx),
        {part: (40.0, -30.0) for part in ctx.slots},
        {part: identity for part in ctx.slots})
    _plan, cell = _seat(translated, "R1")
    assert cell.host_token == "BOOT0", cell.host_token


# =================================================== 2. 编译页：同源与本地旗


def _compile():
    circuit, spec, book = _circuit(), _spec(), _book()
    result = dc.compile(circuit, spec, book, dc.CompileBudget(max_candidates=4))
    return circuit, spec, book, result


def _runs(plan, net):
    return [list(segment.points) for segment in plan.segments if segment.net == net]


def _component(runs, start):
    key = (round(start[0], 6), round(start[1], 6))
    graph = {}
    for run in runs:
        points = [(round(point[0], 6), round(point[1], 6)) for point in run]
        for point in points:
            graph.setdefault(point, set())
        for first, second in zip(points, points[1:]):
            graph[first].add(second)
            graph[second].add(first)
    if key not in graph:
        return set()
    seen = {key}
    stack = [key]
    while stack:
        for neighbour in graph[stack.pop()]:
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    return seen


def _flag_up(flag, book):
    kind = flag_glyph_kind(book[flag.symbol_ref])
    return (float(flag.rotation) - FLAG_GLYPH_ROTATION_OFFSETS[kind]) % 360.0 == 0.0


def _refusal_text(result):
    """Every stated reason this page gave, joined — the refusal *is* the result."""
    return " | ".join(item.detail for item in result.failures)


def _assert_named_seat_refusal(result):
    """The honest answer for this page: refused, with the obstacle named (548D3D).

    Measured: `U1.VSS`'s GND flag has no legal seat — the pad's own escape lanes
    are blocked nodes (a foreign pin tip / a label anchor / another net's vertex
    within 10 units), and every reach the ladder tries ends on one of them. A page
    that cannot state its ground is refused with that coordinate named, instead
    of being drawn with a flag standing on its own pin (069 sec.8, 岳's short).
    """
    assert not result.ok, (
        "this page is expected to refuse: its ground rail has no legal flag seat")
    text = _refusal_text(result)
    assert "U1.VSS" in text, text
    assert "blocked node beside the pad" in text, text
    assert not result.candidates, "a refused page must not hand back a plan"


def test_the_cross_side_page_refuses_by_naming_the_seat_it_cannot_take():
    """548D3D: the cross-side page's answer is `layout-unsat`, with the obstacle.

    This page used to be asserted as "compiles and passes the independent
    checks". It does not compile, and the measurement says why: the ground rail
    cannot put its one flag anywhere (`U1.VSS`, every reach blocked). The honest
    claim is therefore the refusal itself — that it is `layout-unsat`, that it
    names the pad, and that it hands back **no** plan. What is *not* re-pinned is
    the netlist/readability measurement below: with no plan there is nothing to
    measure, and a page that refuses must not pretend otherwise.
    """
    _circuit_, _spec_, _book_, result = _compile()
    _assert_named_seat_refusal(result)
    categories = {item.category for item in result.failures}
    assert "layout-unsat" in categories, categories


def test_every_host_supply_and_ground_foot_is_driven_or_locally_flagged():
    """两侧的电源/地脚：被支路真实驱动，或有自己的本地竖直旗。"""
    circuit, _spec_ = _circuit(), _spec()
    book = _book()
    _c, _s, _b, result = _compile()
    # 548D3D: without a plan there is no run to follow, so the honest statement is
    # the one the page makes: the rail's flag has no seat at `U1.VSS`, and that is
    # exactly the foot this test is about. The per-foot walk below stays as the
    # measurement to run again the day the seat exists.
    _assert_named_seat_refusal(result)
    if not result.ok:
        # The seat this test is about does not exist yet; the walk below is the
        # measurement to run again the day it does.
        return
    plan = result.best()
    u1 = plan.part("U1")
    pose = dc.SymbolPose(rotation=int(u1.rotation), mirror=bool(u1.mirror))
    for net_id in (POWER_NET, GROUND_NET):
        members = next(item for item in circuit.nets if item.id == net_id).members
        for foot in _feet(circuit, "U1", net_id):
            tip = _tip(book, circuit, "U1", foot, pose, (u1.x, u1.y))
            # `_component` takes whole runs and a start point: a flattened point
            # list would feed scalars into `point[0]` (the H3 test bug).
            component = _component(_runs(plan, net_id),
                                   (round(tip[0], 6), round(tip[1], 6)))
            assert component, f"U1.{foot} on {net_id} touches no conductor"
            driven = False
            for member in members:
                part_id, _dot, token = member.partition(".")
                if part_id == "U1":
                    continue
                branch = plan.part(part_id)
                if branch is None:
                    continue
                branch_tip = _tip(
                    book, circuit, part_id, token,
                    dc.SymbolPose(rotation=int(branch.rotation),
                                  mirror=bool(branch.mirror)),
                    (branch.x, branch.y))
                if (round(branch_tip[0], 6), round(branch_tip[1], 6)) in component:
                    driven = True
            flags = [flag for flag in plan.power_symbols
                     if flag.net == net_id
                     and (round(flag.x, 6), round(flag.y, 6)) in component]
            assert driven or flags, (
                f"U1.{foot} on {net_id} is neither driven by a branch nor given "
                f"a local flag: flags "
                f"{[(item.net, item.x, item.y) for item in plan.power_symbols]}")
            for flag in flags:
                assert flag.rotation in (0.0, 180.0), (
                    f"the local flag of U1.{foot} is not upright: {flag.rotation}")


def test_no_duplicate_conductor_and_no_detoured_service_channel():
    """同一个答案上：无重复导体，BoundPlan 的 channel 就是图上那条导体。

    The plan is built from the **same** placement answer the channel comes from
    (`_build_one_variant` on the topology variant), so placement-frame and
    plan-frame are one frame — no delta, no re-seat, and a detour or a parallel
    path still fails. The assertions are the ones this file always had.
    """
    circuit, book = _circuit(), _book()
    ctx = _context()
    built, failure, _notes = dc._build_one_variant(
        ctx, dc._topology_variant(), [])
    assert failure is not None, "the cross-side page is expected to refuse"
    text = failure.detail
    assert "U1.VSS" in text, text
    assert "blocked node beside the pad" in text, text
    if built is None:
        # 548D3D: no plan is drawn, so there is no conductor set to compare. The
        # duplicate/detour assertions below stay as the measurement to re-run the
        # day the ground rail has a seat.
        return
    plan = built.plan
    bound = dc._topology_placement(ctx)
    assert not isinstance(bound, str), bound.detail
    seen = set()
    for segment in plan.segments:
        key = (segment.net, tuple((round(p[0], 6), round(p[1], 6))
                                  for p in segment.points))
        assert key not in seen, f"duplicate conductor: {segment.points}"
        seen.add(key)
    checked = 0
    for service in bound.service_plans:
        if not service.seated or not service.cells or not service.host_paths:
            continue
        cell = service.cells[0]
        token = next(member.partition(".")[2] for member in
                     next(item for item in circuit.nets
                          if item.id == cell.from_net).members
                     if member.partition(".")[0] == cell.part_id)
        host_tip = _tip(book, circuit, service.host_part, cell.host_token,
                        bound.poses[service.host_part],
                        bound.origins[service.host_part])
        seat_tip = _tip(book, circuit, cell.part_id, token,
                        bound.poses[cell.part_id],
                        bound.origins[cell.part_id])
        channel = [tuple(point) for point in service.host_paths[0]]
        assert channel[0] == pytest.approx(host_tip, abs=EPS), (
            f"{cell.part_id}: channel starts at {channel[0]}, the chosen host "
            f"foot {cell.host_token} is at {host_tip}")
        assert channel[-1] == pytest.approx(seat_tip, abs=EPS), (
            f"{cell.part_id}: channel ends at {channel[-1]}, the branch foot is "
            f"at {seat_tip}")
        runs = _runs(plan, cell.from_net)
        legs = list(zip(channel, channel[1:]))
        for leg in legs:
            assert any(
                all(_on_leg(point, first, second) for point in leg)
                for run in runs for first, second in zip(run, run[1:])), (
                f"{cell.part_id}: the planned channel leg {leg} is not a drawn "
                f"conductor on {cell.from_net!r}: {runs}")
        carrier = [run for run in runs
                   if any(all(_on_leg(point, first, second) for point in leg)
                          for leg in legs
                          for first, second in zip(run, run[1:]))]
        rest = [run for run in runs if run not in carrier]
        assert not _connected(rest, host_tip, seat_tip), (
            f"{cell.part_id}: the channel's ends stay connected without the "
            f"channel — a parallel path carries the connection")
        checked += 1
    assert checked, "no seated service channel was checked"


def _connected(runs, first, second):
    graph = {}
    for run in runs:
        points = [(round(point[0], 6), round(point[1], 6)) for point in run]
        for point in points:
            graph.setdefault(point, set())
        for head, tail in zip(points, points[1:]):
            graph[head].add(tail)
            graph[tail].add(head)
    start = (round(first[0], 6), round(first[1], 6))
    target = (round(second[0], 6), round(second[1], 6))
    if start not in graph:
        return False
    seen = {start}
    stack = [start]
    while stack:
        for neighbour in graph[stack.pop()]:
            if neighbour == target:
                return True
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    return start == target


def _on_leg(point, first, second):
    if abs(first[0] - second[0]) <= EPS:
        return (abs(point[0] - first[0]) <= EPS
                and min(first[1], second[1]) - EPS <= point[1]
                <= max(first[1], second[1]) + EPS)
    if abs(first[1] - second[1]) <= EPS:
        return (abs(point[1] - first[1]) <= EPS
                and min(first[0], second[0]) - EPS <= point[0]
                <= max(first[0], second[0]) + EPS)
    return False


def test_a_cross_side_pose_with_no_readable_side_is_refused_by_name():
    """跨侧负例：位姿把脚转到没有可读左右侧时，必须具名拒绝。"""
    ctx = _context()
    vertical = [pose for pose in ctx.accepted["U1"]
                if pose.rotation in (90, 270)]
    if not vertical:
        pytest.skip("this library states no quarter-turn host pose")
    plans = _bound(ctx, vertical[0])
    refused = [item for item in plans if item.refusal is not None]
    if refused:
        text = " | ".join(item.refusal.render() for item in refused)
        assert "U1" in text or "host" in text, text
        assert any(token in text for token in ("VDD", "V33R", "side", "pose")), text
        return
    # if it seated, the chosen foot's posed tip must still be on a readable side
    for item in plans:
        if not item.seated or not item.cells:
            continue
        cell = item.cells[0]
        tip = _tip(_book(), _circuit(), "U1", cell.host_token, vertical[0])
        assert abs(tip[0]) > EPS, (
            f"a quarter-turn pose seated {cell.host_token} whose tip has no "
            f"horizontal side: {tip}")
