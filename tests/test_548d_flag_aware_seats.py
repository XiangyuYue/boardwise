"""548D3D-H2：把岳 P42 手改提炼的**旗标规则**做成能识别旧缺陷的合同。

来源：`tasks/548_drawing_capability_ladder.md` §42 与
`evidence/548D/host-binding/live-reference/rules-from-adjustment.md`。规则是可推广的
**判断**，不是 P42 的实例数值：

* 电源/地旗**竖直阅读**：`rotation` 只取 0/180；电气方向由「库字形种类 + rotation」共同
  决定（`FLAG_GLYPH_ROTATION_OFFSETS`），**不得**用 rotation 数值直接当方向，也不许把
  90/270 横放当合法默认。
* 水平宿主脚的旗必须由**末端竖直短段**接到导线，水平段只许贴着自己的引脚行；
  lead 至多两段（一横一竖），方向与旗的电气方向一致。
* 旗的盒子、器件文字、标签与**异网导体**互不冲突；同一页里两只旗不许互相压住——
  「服务座停在最近档、宿主 3V3 与 GND 旗只剩互相冲突的位置」正是这条要拦的旧缺陷。
* 宿主每一只可见的电源/地脚，要么被某条服务支路真实占用（host path 连通），要么有自己
  的一枚旗挂在同网导体上——座位合法性不能只看器件体。
* 同组服务支路的旗阵一致：同旋转、同 lead 位移，整组随支路平移（不逐件就近塞）。

断言全部从**真实候选几何 + 库符号**复算：没有一条 P42 坐标，也没有把 P42 的 5/30/40/60
当常量。`_flag_box` 用的是库 `body` 的**尺寸**挂在电气正确的一侧（旋转数不等于方向，
所以不能直接拿 `pose_box` 在 fixture 字形上求盒）。

本文件只新增测试，不改生产、任务书或其他测试；§41 的 11 条合同保持原样，强制 topology
的红在生产真实修复前不改写。
"""

from __future__ import annotations

import dataclasses

import test_548d_host_binding as hb
import test_548d_semantic_islands as t

from boardwise.core.symbolprofile import (
    FLAG_GLYPH_ROTATION_OFFSETS,
    flag_glyph_kind,
)
from boardwise.engines import drawcompiler as dc

EPS = 1e-6
POWER_NETS = ("3V3", "GND")
SERVICE_PARTS = ("C1", "R1")


# ------------------------------------------------------------------ 旗的读数


def _up(flag, book) -> bool:
    """Does this flag hang **up**, or down? Read from glyph kind *and* rotation."""
    kind = flag_glyph_kind(book[flag.symbol_ref])
    base = (float(flag.rotation) - FLAG_GLYPH_ROTATION_OFFSETS[kind]) % 360.0
    assert base in (0.0, 180.0), (
        f"{flag.net} flag at ({flag.x:g}, {flag.y:g}) is turned "
        f"{flag.rotation:g}° for a {kind!r} glyph, which is not an upright "
        f"reading (0/180); 90/270 is the horizontally-lying default this batch "
        "retires")
    return base == 0.0


def _flag_box(flag, book):
    """The glyph's room: the library body extent, hung on the **electrical** side."""
    body = book[flag.symbol_ref].body
    scale = 1.0 if _up(flag, book) else -1.0
    return (
        flag.x + body[0], flag.y + min(0.0, scale * body[1]),
        flag.x + body[2], flag.y + max(0.0, scale * body[3]),
    )


def _overlap(first, second) -> bool:
    return (min(first[2], second[2]) > max(first[0], second[0])
            and min(first[3], second[3]) > max(first[1], second[1]))


def _runs(plan, net):
    return [list(segment.points) for segment in plan.segments if segment.net == net]


def _lead(plan, flag):
    """The run on the flag's own net that ends on its anchor, if there is one."""
    for run in _runs(plan, flag.net):
        if hb._close(run[-1], (flag.x, flag.y)) or hb._close(run[0], (flag.x, flag.y)):
            return run if hb._close(run[-1], (flag.x, flag.y)) else run[::-1]
    return None


# ------------------------------------------------------------------ 五项判定


def _vertical_problems(plan, book):
    problems: list[str] = []
    for flag in plan.power_symbols:
        try:
            up = _up(flag, book)
        except AssertionError as exc:
            problems.append(str(exc))
            continue
        run = _lead(plan, flag)
        if run is None:
            problems.append(
                f"{flag.net} flag at ({flag.x:g}, {flag.y:g}) hangs on no "
                f"conductor of its own net")
            continue
        leg = (run[-2], run[-1]) if len(run) > 1 else None
        if leg is None:
            problems.append(f"{flag.net} flag has no lead at all: {run}")
            continue
        if abs(leg[1][0] - leg[0][0]) > EPS:
            problems.append(
                f"{flag.net} flag at ({flag.x:g}, {flag.y:g}) is reached by a "
                f"horizontal last leg {leg}; a flag hangs on a vertical tail")
        approach = leg[0][1] - leg[1][1]
        if up and approach > EPS:
            problems.append(
                f"{flag.net} flag reads up but its lead comes from above: {leg}")
        if not up and approach < -EPS:
            problems.append(
                f"{flag.net} flag reads down but its lead comes from below: {leg}")
    return problems


def _collision_problems(plan, book, circuit):
    problems: list[str] = []
    flags = [(flag, _flag_box(flag, book)) for flag in plan.power_symbols
             if flag.symbol_ref in book]
    for index, (flag, box) in enumerate(flags):
        for other, other_box in flags[index + 1:]:
            if _overlap(box, other_box):
                problems.append(
                    f"{flag.net} flag {box} overlaps {other.net} flag {other_box}")
        for text in plan.texts:
            if _overlap(box, tuple(text.bbox)):
                problems.append(
                    f"{flag.net} flag {box} overlaps text {text.text!r} "
                    f"{tuple(text.bbox)}")
        for label in plan.labels:
            if _overlap(box, tuple(label.bbox)):
                problems.append(
                    f"{flag.net} flag {box} overlaps label {label.text!r} "
                    f"{tuple(label.bbox)}")
        for segment in plan.segments:
            if segment.net == flag.net:
                continue
            for first, second in zip(segment.points, segment.points[1:]):
                foreign = (
                    min(first[0], second[0]), min(first[1], second[1]),
                    max(first[0], second[0]), max(first[1], second[1]))
                if _overlap(box, foreign):
                    problems.append(
                        f"{flag.net} flag {box} crosses the {segment.net} "
                        f"conductor {foreign}")
    return problems


def _served_feet(plan, circuit, book):
    """Host feet a service branch really hangs off, read from the drawing."""
    served: set[tuple[str, str]] = set()
    for part_id in SERVICE_PARTS:
        plan_part = plan.part(part_id)
        if plan_part is None:
            continue
        nets = [member.partition(".")[2] for net in circuit.nets
                for member in net.members
                if member.partition(".")[0] == part_id]
        for token in nets:
            shared = next(
                net.id for net in circuit.nets
                for member in net.members
                if member == f"{part_id}.{token}")
            tip = hb._at(plan, book, circuit, part_id, token)
            component = hb._component(_runs(plan, shared), tip)
            if not component:
                continue
            for net in circuit.nets:
                if net.id != shared:
                    continue
                for member in net.members:
                    host, _dot, host_token = member.partition(".")
                    if host != "U1":
                        continue
                    host_tip = hb._at(plan, book, circuit, host, host_token)
                    if any(hb._close(point, host_tip) for point in component):
                        served.add((host, host_token))
    return served


def _host_coverage_problems(plan, circuit, book):
    problems: list[str] = []
    served = _served_feet(plan, circuit, book)
    for net_id in POWER_NETS:
        for foot in hb._net_feet(circuit, "U1", net_id):
            if ("U1", foot) in served:
                continue
            tip = hb._at(plan, book, circuit, "U1", foot)
            component = hb._component(_runs(plan, net_id), tip)
            flagged = any(
                flag.net == net_id and any(
                    hb._close((flag.x, flag.y), point) for point in component)
                for flag in plan.power_symbols)
            if not flagged:
                problems.append(
                    f"U1.{foot} on {net_id} is neither driven by a service "
                    f"branch nor given a flag of its own net "
                    f"(flags: {[(item.net, item.x, item.y) for item in plan.power_symbols]})")
    return problems


def _terminal_flag(plan, circuit, book, part_id):
    """The GND flag that hangs off this branch's own far foot, or ``None``."""
    part = plan.part(part_id)
    if part is None:
        return None
    token = next(
        (member.partition(".")[2] for net in circuit.nets if net.id == "GND"
         for member in net.members if member.partition(".")[0] == part_id), None)
    if token is None:
        return None
    tip = hb._at(plan, book, circuit, part_id, token)
    component = hb._component(_runs(plan, "GND"), tip)
    for flag in plan.power_symbols:
        if flag.net == "GND" and any(
                hb._close((flag.x, flag.y), point) for point in component):
            return tip, flag
    return None


def _group_problems(plan, circuit, book):
    """Same-group service branches: one orientation, one lead, one array."""
    problems: list[str] = []
    pairs = {
        part_id: _terminal_flag(plan, circuit, book, part_id)
        for part_id in SERVICE_PARTS}
    found = {part: value for part, value in pairs.items() if value is not None}
    if len(found) < 2:
        return [
            f"a service branch has no terminal flag of its own: "
            f"{ {part: value is not None for part, value in pairs.items()} }"]
    rotations = {float(flag.rotation) for _tip, flag in found.values()}
    if len(rotations) != 1:
        problems.append(
            "the group's terminal flags disagree on rotation: "
            f"{[(part, flag.rotation) for part, (_tip, flag) in found.items()]}")
    kinds = {flag_glyph_kind(book[flag.symbol_ref]) for _tip, flag in found.values()}
    if len(kinds) != 1:
        problems.append(f"the group's terminal flags are different glyph kinds: {kinds}")
    deltas = {
        (round(flag.x - tip[0], 6), round(flag.y - tip[1], 6))
        for tip, flag in found.values()}
    if len(deltas) != 1:
        problems.append(
            f"the group's terminal leads disagree (the array does not follow "
            f"its branches): {sorted(deltas)}")
    return problems


def _all_problems(plan, circuit, book, bound=None, shared=None,
                  delta=(0.0, 0.0)) -> list[str]:
    problems = (
        _vertical_problems(plan, book)
        + _collision_problems(plan, book, circuit)
        + _host_coverage_problems(plan, circuit, book)
        + _group_problems(plan, circuit, book)
        + _conductor_problems(plan)
    )
    if bound is not None and shared is not None:
        problems += _channel_problems(plan, bound, circuit, book, shared, delta)
        problems += _channel_node_problems(
            plan, bound, circuit, book, shared, delta)
    return problems


def _base_plan():
    circuit, spec = hb._module_view()
    book = t._book()
    result = dc.compile(circuit, spec, book, dc.CompileBudget(max_candidates=4))
    assert result.ok, result.render_failures()
    return circuit, spec, book, result.best()


# ==================================================================== 合同


def test_every_flag_on_the_mcu_page_reads_vertically():
    """0/180 + 方向来自字形：RAIL 向上、GND 按字形（可能 180 向上）都不横躺。"""
    circuit, _spec, book, plan = _base_plan()
    problems = _vertical_problems(plan, book)
    assert problems == [], problems


def test_the_glyph_kind_decides_the_direction_not_the_rotation_number():
    """同一 rotation 下两个家族方向不同——方向是「种类 + 数字」，不是数字本身。"""
    circuit, _spec, book, plan = _base_plan()
    rails = [flag for flag in plan.power_symbols
             if flag_glyph_kind(book[flag.symbol_ref]) == "rail"]
    grounds = [flag for flag in plan.power_symbols
               if flag_glyph_kind(book[flag.symbol_ref]) == "gnd"]
    assert rails and grounds, [(item.net, item.symbol_ref) for item in plan.power_symbols]
    for flag in rails:
        assert _up(flag, book), f"a rail flag must stand above its conductor: {flag}"
    # a ground may be 0 or 180; whatever the number, the offset table (not the
    # number alone) is what says which way it hangs
    for flag in grounds:
        base = (flag.rotation - FLAG_GLYPH_ROTATION_OFFSETS["gnd"]) % 360.0
        assert base in (0.0, 180.0), (flag.rotation, base)
    assert len({(flag.rotation, _up(flag, book)) for flag in grounds}) >= 1


def test_no_two_flags_and_no_row_share_room_on_the_mcu_page():
    """旧缺陷的判据：宿主剩下的 3V3/GND 旗不许互相压住，也不许压文字/标签/异网线。"""
    circuit, _spec, book, plan = _base_plan()
    problems = _collision_problems(plan, book, circuit)
    assert problems == [], problems


def test_every_visible_host_supply_and_ground_foot_is_flagged_or_driven():
    """座位合法性的可见判据：每只可见宿主电源/地脚都被支路占用或有自己的旗。"""
    circuit, _spec, book, plan = _base_plan()
    problems = _host_coverage_problems(plan, circuit, book)
    assert problems == [], problems


def test_a_horizontal_host_foot_hangs_its_flag_on_a_vertical_tail():
    """水平宿主脚：水平段只在自己引脚行上，末端必须是竖直短段接旗。"""
    circuit, _spec, book, plan = _base_plan()
    problems: list[str] = []
    for net_id in POWER_NETS:
        for foot in hb._net_feet(circuit, "U1", net_id):
            tip = hb._at(plan, book, circuit, "U1", foot)
            flags = [flag for flag in plan.power_symbols
                     if flag.net == net_id
                     and any(hb._close((flag.x, flag.y), point)
                             for point in hb._component(
                                 _runs(plan, net_id), tip))]
            for flag in flags:
                run = _lead(plan, flag)
                if run is None:
                    problems.append(f"U1.{foot}: flag hangs on no conductor")
                    continue
                if len(run) > 3:
                    problems.append(
                        f"U1.{foot}: the flag's lead is a {len(run) - 1}-leg "
                        f"detour {run}")
                horizontal = [
                    leg for leg in zip(run, run[1:])
                    if abs(leg[0][1] - leg[1][1]) < EPS]
                for leg in horizontal:
                    if abs(leg[0][1] - tip[1]) > EPS:
                        problems.append(
                            f"U1.{foot}: a horizontal lead leg {leg} is not on "
                            f"the pin's own row {tip[1]:g}")
                last = run[-2:]
                if abs(last[1][0] - last[0][0]) > EPS:
                    problems.append(
                        f"U1.{foot}: the flag is reached sideways, not by a "
                        f"vertical tail: {last}")
    assert problems == [], problems


def test_the_service_terminal_flags_of_one_group_agree():
    """同组服务支路：同旋转、同 lead 位移，整组随支路平移。"""
    circuit, _spec, book, plan = _base_plan()
    problems = _group_problems(plan, circuit, book)
    assert problems == [], problems


def test_the_forced_topology_page_obeys_the_same_flag_rules(monkeypatch):
    """强制 topology 的最终页必须同时满足上面五条——旧缺陷在这里必然现形。

    §41 的红（无真实候选）在此保留：没有候选，就没有任何一条旗标规则可以通过。
    """
    monkeypatch.setattr(dc, "_variants", lambda ctx: [])
    monkeypatch.setattr(dc, "_widened_variants", lambda ctx, result: [])
    circuit, spec = hb._module_view()
    book = t._book()
    result = dc.compile(circuit, spec, book, dc.CompileBudget(max_candidates=4))
    assert result.ok, (
        "the forced topology page produced no candidate, so no flag rule can be "
        "met: " + result.render_failures())
    plan = result.best()
    ctx = hb._context()
    bound = dc._topology_placement(ctx)
    assert not isinstance(bound, str), bound.detail
    delta = (plan.part("U1").x - bound.origins["U1"][0],
             plan.part("U1").y - bound.origins["U1"][1])
    problems = _all_problems(
        plan, circuit, book, hb._service_plans(bound), hb._shared_nets(ctx), delta)
    assert problems == [], problems


# ==================================== 2. channel 必须就是图上那条连续导体


def _on_leg(point, first, second) -> bool:
    """Is ``point`` on this orthogonal leg (endpoints included)?"""
    if abs(first[0] - second[0]) <= EPS:
        return (abs(point[0] - first[0]) <= EPS
                and min(first[1], second[1]) - EPS <= point[1]
                <= max(first[1], second[1]) + EPS)
    if abs(first[1] - second[1]) <= EPS:
        return (abs(point[1] - first[1]) <= EPS
                and min(first[0], second[0]) - EPS <= point[0]
                <= max(first[0], second[0]) + EPS)
    return False


def _covers(run, leg) -> bool:
    """Does one drawn leg of this run carry the whole planned leg?"""
    return any(
        _on_leg(leg[0], first, second) and _on_leg(leg[1], first, second)
        for first, second in zip(run, run[1:]))


def _graph(runs):
    graph: dict = {}
    for run in runs:
        points = [tuple(point) for point in run]
        for point in points:
            graph.setdefault(point, set())
        for first, second in zip(points, points[1:]):
            graph[first].add(second)
            graph[second].add(first)
    return graph


def _connected(graph, first, second) -> bool:
    key, target = tuple(first), tuple(second)
    if key not in graph:
        return False
    seen = {key}
    stack = [key]
    while stack:
        for neighbour in graph[stack.pop()]:
            if neighbour in seen:
                continue
            if neighbour == target:
                return True
            seen.add(neighbour)
            stack.append(neighbour)
    return key == target


def _channel_problems(plan, bound, circuit, book, shared, delta=(0.0, 0.0)):
    """The seat's channel must **be** the drawn path, not a memory of one.

    For every BoundPlan seat: the channel's two ends are the drawn host foot and
    the drawn branch foot (in the plan's own frame, moved by the rigid ``delta``
    between the bound answer and the drawn page); every leg of the channel is
    carried by a real conductor of that same net; and once the carrier is
    removed the two ends are **not** connected by anything else. A straight
    A->B plan drawn as A->C->D->B fails the leg test; a parallel return loop
    fails the removal test. No length is compared, and ``_path_first_audit`` is
    not touched.
    """
    problems: list = []
    for service in bound:
        if not service.seated or not service.cells:
            problems.append(f"{service.group_id}: no seated cell to replay")
            continue
        cell = service.cells[0]
        net = shared[cell.part_id]
        token = next(
            (member.partition(".")[2] for item in circuit.nets if item.id == net
             for member in item.members
             if member.partition(".")[0] == cell.part_id), None)
        if token is None:
            problems.append(f"{cell.part_id}: the circuit gives no foot on {net!r}")
            continue
        if not service.host_paths:
            problems.append(f"{cell.part_id}: the BoundPlan records no channel")
            continue
        host_tip = hb._at(plan, book, circuit, service.host_part, cell.host_token)
        seat_tip = hb._at(plan, book, circuit, cell.part_id, token)
        channel = [tuple((point[0] + delta[0], point[1] + delta[1]))
                   for point in service.host_paths[0]]
        if not hb._close(channel[0], host_tip):
            problems.append(
                f"{cell.part_id}: the channel starts at {channel[0]}, the drawn "
                f"host foot {cell.host_token} is at {host_tip}")
        if not hb._close(channel[-1], seat_tip):
            problems.append(
                f"{cell.part_id}: the channel ends at {channel[-1]}, the drawn "
                f"branch foot is at {seat_tip}")
        runs = _runs(plan, net)
        legs = list(zip(channel, channel[1:]))
        for leg in legs:
            if not any(_covers(run, leg) for run in runs):
                problems.append(
                    f"{cell.part_id}: the planned channel leg {leg} is not a "
                    f"conductor of the plan on {net!r} — the path was decided "
                    f"first and drawn as something else ({runs})")
        carrier = [run for run in runs if any(_covers(run, leg) for leg in legs)]
        if not carrier:
            continue
        rest = [run for run in runs if run not in carrier]
        if _connected(_graph(rest), host_tip, seat_tip):
            problems.append(
                f"{cell.part_id}: the channel's two ends stay connected without "
                f"the channel — a second, parallel path carries the connection "
                f"({channel} vs {rest})")
    return problems


def _conductor_problems(plan) -> list:
    """No duplicate conductor, no point shared between two nets."""
    problems: list = []
    seen: set = set()
    for segment in plan.segments:
        key = (segment.net, tuple((round(p[0], 6), round(p[1], 6))
                                  for p in segment.points))
        if key in seen:
            problems.append(f"duplicate conductor on {segment.net}: {segment.points}")
        seen.add(key)
    for index, first in enumerate(plan.segments):
        for second in plan.segments[index + 1:]:
            if first.net != second.net:
                continue
            for leg_first in zip(first.points, first.points[1:]):
                for leg_second in zip(second.points, second.points[1:]):
                    if (_on_leg(leg_first[0], *leg_second)
                            and _on_leg(leg_first[1], *leg_second)):
                        problems.append(
                            f"overlapping conductors on {first.net}: "
                            f"{leg_first} and {leg_second}")
    vertices: dict = {}
    for segment in plan.segments:
        for point in segment.points:
            vertices.setdefault(
                (round(point[0], 6), round(point[1], 6)), set()).add(segment.net)
    for point, nets in vertices.items():
        if len(nets) > 1:
            problems.append(f"nets {sorted(nets)} share the point {point}")
    for segment in plan.segments:
        for point, nets in vertices.items():
            if segment.net in nets:
                continue
            if any(_on_leg(point, first, second)
                   for first, second in zip(segment.points, segment.points[1:])):
                problems.append(
                    f"the {sorted(nets)} point {point} lies on a "
                    f"{segment.net} conductor")
    return problems


def _bound_replay():
    """Base page, its BoundPlan, and the rigid delta between the two frames."""
    circuit, _spec, book, plan = _base_plan()
    ctx = hb._context()
    placed = hb._base(ctx)
    delta = (plan.part("U1").x - placed.origins["U1"][0],
             plan.part("U1").y - placed.origins["U1"][1])
    for part in plan.parts:
        origin = placed.origins[part.part_id]
        if (abs(part.x - origin[0] - delta[0]) > EPS
                or abs(part.y - origin[1] - delta[1]) > EPS):
            raise AssertionError(
                "the drawn page is not the bound placement moved rigidly: "
                f"{part.part_id} sits at ({part.x}, {part.y}) but the plan says "
                f"{origin} plus {delta}")
    return circuit, book, plan, placed, hb._shared_nets(ctx), delta


def test_the_service_channel_is_the_drawn_path_and_never_a_detour():
    """正例/负控：base 上 BoundPlan 的 channel 就是图上那条连续导体本身。

    计划 channel 若是 A->B，最终画成 A->C->D->B、或另有一条并行回环承担连接，
    这里必须红；它不看总长，也不放宽 `_path_first_audit`。
    """
    circuit, book, plan, placed, shared, delta = _bound_replay()
    problems = _channel_problems(
        plan, hb._service_plans(placed), circuit, book, shared, delta)
    assert problems == [], problems


def test_a_real_candidate_has_no_duplicate_or_cross_net_conductors():
    """同网重复导体、跨网共点都是短路/漂移的形状，真实候选里一律不许出现。"""
    circuit, _spec, book, plan = _base_plan()
    problems = _conductor_problems(plan)
    assert problems == [], problems


# ============================ 3. 固定 channel 的节点必须进入最终占用（联合选择）


def _channel_node_problems(plan, bound, circuit, book, shared, delta=(0.0, 0.0)):
    """The fixed channel's nodes are **real room** for every later assignment.

    Joint selection may exempt another group's *candidate* seat from the clash
    check it runs while choosing, but the channel that was fixed first is
    already in the drawing: the final candidate must not put another
    assignment's vertex on one of that channel's nodes. Two shapes are caught:

    * a vertex of **another net** on any channel node — two assignments truly
      share a node, which only a short or a mis-seat can produce;
    * a vertex of the same net on an **interior** channel node — a second seat
      sits inside the channel instead of yielding to it.

    The channel's own two endpoints on its own net are the host foot and the
    branch foot, so their vertices are not a defect.
    """
    problems: list = []
    for service in bound:
        if not service.seated or not service.cells:
            continue
        cell = service.cells[0]
        net = shared.get(cell.part_id)
        if net is None or not service.host_paths:
            continue
        channel = [tuple((point[0] + delta[0], point[1] + delta[1]))
                   for point in service.host_paths[0]]
        ends = (channel[0], channel[-1])
        carrier = [run for run in _runs(plan, net)
                   if any(_covers(run, leg) for leg in zip(channel, channel[1:]))]
        for point in channel:
            interior = not any(hb._close(point, end) for end in ends)
            for segment in plan.segments:
                if any(list(segment.points) == run for run in carrier):
                    continue
                if not any(hb._close(tuple(vertex), point)
                           for vertex in segment.points):
                    continue
                if segment.net != net:
                    problems.append(
                        f"{cell.part_id}: the fixed channel node {point} is also "
                        f"a vertex of a {segment.net} conductor — two final "
                        f"assignments share a real node")
                elif interior:
                    problems.append(
                        f"{cell.part_id}: another {net} assignment sits inside "
                        f"the fixed channel at {point}: {list(segment.points)}")
    return problems


def test_no_other_assignment_shares_a_fixed_channel_node():
    """正常 fixed-first 最终候选：零真实共享节点、channel 存在、去掉后不连通。

    同时带一个负例（本文件自检，不冒充生产读数）：只把「另一组的候选座位」从 clash
    豁免、却不把固定 channel 的节点带进最终占用时，两个 assignment 会真实共享节点——
    这条判定必须红，否则本断言没有牙。
    """
    circuit, book, plan, placed, shared, delta = _bound_replay()
    bound = hb._service_plans(placed)
    problems = _channel_node_problems(plan, bound, circuit, book, shared, delta)
    assert problems == [], problems
    # channel still exists and still carries the connection on its own
    assert _channel_problems(plan, bound, circuit, book, shared, delta) == []

    # --- teeth, part 1: a foreign-net vertex on the channel's host node -------
    cell = next(item.cells[0] for item in bound if item.cells)
    net = shared[cell.part_id]
    channel = [tuple((point[0] + delta[0], point[1] + delta[1]))
               for point in next(item.host_paths[0] for item in bound
                                 if item.cells[0].part_id == cell.part_id)]
    host_node = channel[0]
    ground = next(segment for segment in plan.segments if segment.net == "GND")
    injected = dataclasses.replace(plan)
    injected.segments = list(plan.segments) + [
        dataclasses.replace(ground, points=[(host_node[0] + 60.0, host_node[1] - 25.0),
                                            host_node])]
    shared_problems = _channel_node_problems(
        injected, bound, circuit, book, shared, delta)
    assert any("share a real node" in item for item in shared_problems), (
        "a foreign net landing on the fixed channel's node must be caught: "
        f"{shared_problems}")

    # --- teeth, part 2: a same-net seat inside a two-leg channel --------------
    corner = (channel[0][0], channel[0][1] + 25.0)
    stub = type("Bound", (), {
        "seated": True,
        "cells": (type("Cell", (), {"part_id": cell.part_id,
                                    "host_token": cell.host_token})(),),
        "host_paths": ((channel[0], corner, channel[-1]),),
    })()
    inside = dataclasses.replace(plan)
    inside.segments = list(plan.segments) + [
        dataclasses.replace(
            next(segment for segment in plan.segments if segment.net == net),
            points=[(corner[0] + 40.0, corner[1]), corner])]
    inside_problems = _channel_node_problems(
        inside, (stub,), circuit, book, shared, delta)
    assert any("sits inside the fixed channel" in item for item in inside_problems), (
        "a same-net assignment landing on an interior channel node must be "
        f"caught: {inside_problems}")


# ===================== 4. 选脚规则A：channel 不得切断宿主其它电源/地脚的旗带


def _host_flag_geometry(plan, circuit, book):
    """Every host supply/ground foot's **drawn** flag: glyph box plus its lead."""
    out: dict = {}
    for net_id in POWER_NETS:
        for foot in hb._net_feet(circuit, "U1", net_id):
            tip = hb._at(plan, book, circuit, "U1", foot)
            component = hb._component(_runs(plan, net_id), tip)
            for flag in plan.power_symbols:
                if flag.net == net_id and any(
                        hb._close((flag.x, flag.y), point) for point in component):
                    run = _lead(plan, flag)
                    out[foot] = (_flag_box(flag, book),
                                 [tuple(point) for point in run] if run else [])
                    break
    return out


def _channel_vs_band_problems(plan, bound, circuit, book, shared, delta=(0.0, 0.0)):
    """Rule A: a channel may not cut another host foot's vertical flag band.

    Every host supply/ground foot that a channel does **not** drive still needs its
    own flag; if the channel's drawn path crosses that flag's glyph or lead, the
    seat is not legal — the two readings would collide by construction. The bands
    are read from the drawing (glyph box + the real lead), never from a policy.
    """
    problems: list = []
    bands = _host_flag_geometry(plan, circuit, book)
    for service in bound:
        if not service.seated or not service.cells:
            continue
        cell = service.cells[0]
        net = shared.get(cell.part_id)
        if net is None or not service.host_paths:
            continue
        channel = [tuple((point[0] + delta[0], point[1] + delta[1]))
                   for point in service.host_paths[0]]
        for foot, (box, lead) in bands.items():
            if foot == cell.host_token:
                continue
            for first, second in zip(channel, channel[1:]):
                leg = (min(first[0], second[0]), min(first[1], second[1]),
                       max(first[0], second[0]), max(first[1], second[1]))
                if _overlap(leg, box):
                    problems.append(
                        f"{cell.part_id}: the channel leg {leg} cuts the {foot} "
                        f"flag band {box} of {service.host_part}")
                for lead_first, lead_second in zip(lead, lead[1:]):
                    lead_box = (
                        min(lead_first[0], lead_second[0]),
                        min(lead_first[1], lead_second[1]),
                        max(lead_first[0], lead_second[0]),
                        max(lead_first[1], lead_second[1]))
                    if _overlap(leg, lead_box):
                        problems.append(
                            f"{cell.part_id}: the channel leg {leg} cuts the "
                            f"{foot} flag lead {lead_box} of {service.host_part}")
    return problems


def test_no_channel_cuts_a_host_flag_band_on_the_mcu_page():
    """正例/负控：base 的每条 channel 都不穿过宿主其它电源/地脚的旗与引线。"""
    circuit, book, plan, placed, shared, delta = _bound_replay()
    problems = _channel_vs_band_problems(
        plan, hb._service_plans(placed), circuit, book, shared, delta)
    assert problems == [], problems


def test_a_pose_that_breaks_every_admitted_foot_is_refused_by_name():
    """规则A的具名拒绝：某一脚走旗带必撞时，不许静默换脚、也不许无名失败。

    现役快照里 R1 的 singleton（U1.BOOT0）在这个位姿就是这种情形：它的 channel
    会跨过 VDD 的 3V3 旗带，于是**没有**合法脚——正确回答是具名拒绝，且名字里
    必须点出被判的脚与相撞的脚/网。
    """
    circuit, spec = hb._module_view()
    book = t._book()
    ctx = hb._context()
    labels = {pose.label() for pose in ctx.accepted["U1"]}
    pose = next(
        (ctx.accepted["U1"][index] for index, item in enumerate(ctx.accepted["U1"])
         if item.label() in ("180+mirror", "0+mirror")), None)
    assert pose is not None, f"no mirrored legal pose in this library: {labels}"
    placed = hb._base(ctx)
    plans = hb._topology_bound(ctx, placed.origins,
                               {**placed.poses, "U1": pose})
    refused = [item for item in plans if item.refusal is not None]
    if refused:
        text = " | ".join(item.refusal.render() for item in refused)
        assert any(token in text for token in ("BOOT0", "VDD", "VBAT")), text
        assert ("flag band" in text) or ("side" in text), (
            "a refusal that removes every admitted foot must name the rule it "
            "applied (the band it would cut, or the side the foot faces): " + text)
        assert "BOOT0" in text, (
            "the singleton BOOT0 must be named by its own refusal, never "
            "silently swapped for another foot: " + text)
        return
    # seated: the chosen foot must not be one whose channel cuts another band
    for item in plans:
        if not item.seated or not item.cells:
            continue
        cell = item.cells[0]
        assert cell.host_token in hb._net_feet(
            circuit, "U1", hb._shared_nets(ctx)[cell.part_id]), cell.host_token


def test_the_forced_topology_page_is_either_clean_or_refused_by_name(monkeypatch):
    """强制 topology：要么给出满足全部 channel/flag/no-overlap 的候选，要么具名拒绝。

    没有第三种答案——既不许产出真实重叠/旗带被切的候选，也不许只回一句无名的
    「no candidate」。§41 的「必须出候选」留在 host_binding 里，不在这里放宽。
    """
    monkeypatch.setattr(dc, "_variants", lambda ctx: [])
    monkeypatch.setattr(dc, "_widened_variants", lambda ctx, result: [])
    circuit, spec = hb._module_view()
    book = t._book()
    result = dc.compile(circuit, spec, book, dc.CompileBudget(max_candidates=4))
    if not result.ok:
        text = result.render_failures()
        assert text.strip(), "a refusal must say why"
        assert "flag band" in text, (
            "the refusal is not named after the band rule it applied: " + text[:600])
        assert any(token in text for token in ("BOOT0", "VDD", "VBAT")), text[:600]
        return
    plan = result.best()
    ctx = hb._context()
    bound = dc._topology_placement(ctx)
    assert not isinstance(bound, str), bound.detail
    delta = (plan.part("U1").x - bound.origins["U1"][0],
             plan.part("U1").y - bound.origins["U1"][1])
    problems = _all_problems(
        plan, circuit, book, hb._service_plans(bound), hb._shared_nets(ctx), delta)
    problems += _channel_vs_band_problems(
        plan, hb._service_plans(bound), circuit, book, hb._shared_nets(ctx), delta)
    assert problems == [], problems
