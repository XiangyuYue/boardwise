"""548D3D-H：宿主脚绑定统一（允许脚集合 → 一次选脚 → 同源回放）的**合同验收**。

任务书：`tasks/548_drawing_capability_ladder.md` §41；集成锁
`tasks/shared-platform.md` §19；根因证据
`evidence/548D/service-seat/mcu-local/topology-host-boundary.log`
（同一颗 MCU：base 有位姿时 C1 = VBAT，topology 无位姿时提前固定 VDD）。

本文件只钉**可观察的事实**，不钉私有实现的名字：

* 允许脚集合不允许在缺位姿时退化成一个「首脚」：真实 base 答案与 topology 模板必须落到
  同一个宿主脚；
* 同一位姿下，base（`_place_chain_and_shelf` 的真实答案）与 topology（`_topology_request`
  的真实模板）在 binder 里选出**同一个**宿主脚，并给出同一座位与同一 host path；
* 平移、宿主 pin 列表重排之后，选脚仍按同一条几何规则（本文件自己用 posed pin tip 复算：
  「终端旗向下 ⇒ 最低的合法同网脚」，不拿实现函数的返回值当期望）；
* 位姿把声明的阅读侧翻走时，必须**具名拒绝**，不能静默保留旧座位（§41-3）；
* 每一次绑定之后的 host path 起点都等于该 plan 自己声明的 `host_token` 在当前位姿下的
  真实 pin tip，且该脚确实在支路的 shared net 上（宿主端点审计）；
* 最终图纸消费的是同一次选脚：C1 的导线连到选定的那只脚，另一只同网脚不在同一段导体上；
  GND 旗站在 plan 自己的 `to_seat` 上；
* 当前 MCU 在 `_variants` 与 `_widened_variants` 都为空、base 无法兜底时，forced topology
  必须真实产出候选，并通过独立逐脚、grammar 与 readability；
* 显式 singleton（宿主在该网上只有一脚，U1.BOOT0）在任何扰动下都不被同网其它脚替换。

**不测什么**：右侧端口列、整页 packing、KEY/LED 岛形、旧 panelGroups 页的逐候选轨迹
（那是 `test_548d_panel_*` 与本批生产侧负控的账）；本文件不写代理坐标、不改生产。

几何期望全部由本文件从冻结电路（`test_548d_semantic_islands`）+ 符号库重算：
`transform_point` 把符号脚按 plan 自己的位姿落到页面，规则是「终端旗向下的支路取最低的
合法宿主脚，tie 按 token」——两枚 3V3 脚在本库里同属 `left` 阅读侧，所以这条规则无歧义。
"""

from __future__ import annotations

import dataclasses

import test_548d_semantic_islands as t

from boardwise.core.geometry import transform_point
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines import placement
from boardwise.engines import readability

SHARED_NET = "3V3"
SINGLETON_NET = "BOOT0"
EPS = 1e-6


# --------------------------------------------------------------- 夹具与入口


def _module_view(local_seats: bool = True):
    """The MCU island alone, as the page compiler hands it to the module build."""
    circuit = t._circuit()
    spec = t._island_spec()
    module = next(item for item in spec.modules if item.id == "mcu")
    sub_circuit, sub_spec = pc._module_view(circuit, spec, module)
    sub_spec = dataclasses.replace(
        sub_spec,
        service_layout=dataclasses.replace(
            sub_spec.service_layout, local_seats=local_seats),
    )
    return sub_circuit, sub_spec


def _context(book=None, local_seats: bool = True) -> dc._Context:
    """The prepared compile context, through the existing ladder entries."""
    circuit, spec = _module_view(local_seats)
    book = t._book() if book is None else book
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, spec, circuit)
    prepared = dc._prepare(
        circuit, spec, binding, book, dc.CompileBudget(max_candidates=4))
    assert prepared.context is not None, [f.detail for f in prepared.failures]
    return prepared.context


def _base(ctx: dc._Context):
    """The ladder's own first answer — a real placement, not a spelling of one."""
    first = None
    for variant in dc._variants(ctx):
        placed, failure = dc._place_chain_and_shelf(ctx, variant)
        if failure is None:
            return placed
        if first is None:
            first = failure
    raise AssertionError(
        "no ladder variant placed the MCU island: "
        + (first.detail if first is not None else "no variant"))


def _topology_bound(ctx, origins, poses):
    """The topology consumer's own templates, bound against the given answer."""
    request = dc._topology_request(ctx)
    return placement.bind_service_plans(request, origins, poses)


def _seat(plans, part_id):
    plan = next(
        (item for item in plans
         if item.cells and item.cells[0].part_id == part_id), None)
    assert plan is not None, (
        f"no plan for {part_id!r}: "
        f"{[(item.group_id, item.refusal.render() if item.refusal else 'seated') for item in plans]}")
    assert plan.seated, plan.refusal.render() if plan.refusal else part_id
    return plan, plan.cells[0]


def _plans_by_part(plans):
    return {item.cells[0].part_id: item for item in plans if item.cells}


# ----------------------------------------------------------------- 独立几何


def _profile(book, circuit, part_id):
    return book[circuit.part(part_id).symbol_ref]


def _pin(profile, token):
    pin = next(
        (item for item in profile.pins
         if item.number == token or item.name == token), None)
    assert pin is not None, token
    return pin


def _tip(book, circuit, part_id, token, pose, origin):
    """One pin's tip in the answer's own pose/origin — the same transform the
    plan is drawn with, computed here rather than read back from the engine."""
    pin = _pin(_profile(book, circuit, part_id), token)
    return transform_point(
        pin.tip[0], pin.tip[1], rotation=pose.rotation, mirror=pose.mirror,
        ox=origin[0], oy=origin[1])


def _net_feet(circuit, part_id: str, net_id: str) -> tuple[str, ...]:
    """The host's feet on one net, in the circuit's own member order."""
    net = next(item for item in circuit.nets if item.id == net_id)
    return tuple(
        member.partition(".")[2] for member in net.members
        if member.partition(".")[0] == part_id)


def _outermost_host(book, circuit, part_id, net_id, pose, origin) -> str:
    """The host foot the branch's downward terminal flag reads from (the rule)."""
    profile = _profile(book, circuit, part_id)
    feet = _net_feet(circuit, part_id, net_id)
    assert feet, (part_id, net_id)
    sides = {_pin(profile, token).direction for token in feet}
    assert len(sides) == 1, (
        f"{part_id}'s feet {feet!r} on {net_id!r} do not share one reading side "
        f"({sides!r}), so the outer-foot rule would be ambiguous")
    return min(
        feet, key=lambda token: (
            _tip(book, circuit, part_id, token, pose, origin)[1], token))


def _close(first, second) -> bool:
    return (
        abs(first[0] - second[0]) <= EPS and abs(first[1] - second[1]) <= EPS)


def _service_plans(placed):
    return tuple(getattr(placed, "service_plans", ()))


def _shared_nets(ctx) -> dict[str, str]:
    """Which net each declared service branch shares with its host."""
    return {
        template.cell.part_id: template.cell.from_net
        for template in dc._topology_request(ctx).service_templates
    }


def _illegal_pose(ctx, label: str):
    """The accepted host pose whose label the caller names."""
    return next(pose for pose in ctx.accepted["U1"] if pose.label() == label)


# =================================================== 1. 选脚：一个集合，一次选择


def test_the_base_answer_hangs_the_decoupling_branch_on_the_outer_shared_foot():
    """base 的答案本身就是规则的正读（对照臂；不是本批新行为）。"""
    ctx = _context()
    circuit, _spec = _module_view()
    book = t._book()
    placed = _base(ctx)
    plan, cell = _seat(_service_plans(placed), "C1")
    expected = _outermost_host(
        book, circuit, "U1", SHARED_NET, placed.poses["U1"], placed.origins["U1"])
    assert cell.host_token == expected, (
        f"base chose {cell.host_token!r}, the pose reads {expected!r} "
        f"(feet on {SHARED_NET}: {_net_feet(circuit, 'U1', SHARED_NET)!r})")
    assert _close(plan.host_paths[0][0], _tip(
        book, circuit, "U1", cell.host_token, placed.poses["U1"],
        placed.origins["U1"]))
    _r1, r1 = _seat(_service_plans(placed), "R1")
    assert r1.host_token == "BOOT0", r1.host_token


def test_the_topology_request_binds_the_same_foot_and_seat_at_the_same_pose():
    """同一位姿：base 与 topology 两个真实消费者的选脚、座位与 host path 一致。

    这正是 `topology-host-boundary.log` 的缺口：topology 的模板在没有位姿时就把宿主
    脚固定成首脚（VDD），于是同一份答案上 C1 被坐到另一行，host path 起点也换了脚。
    """
    ctx = _context()
    placed = _base(ctx)
    base_plans = _service_plans(placed)
    base_c1_plan, base_c1 = _seat(base_plans, "C1")
    _base_r1_plan, base_r1 = _seat(base_plans, "R1")

    bound = _topology_bound(ctx, placed.origins, placed.poses)
    topo_c1_plan, topo_c1 = _seat(bound, "C1")
    _topo_r1_plan, topo_r1 = _seat(bound, "R1")

    assert topo_c1.host_token == base_c1.host_token, (
        "the two consumers read one answer and must hang C1 on one foot: "
        f"base {base_c1.host_token!r}, topology {topo_c1.host_token!r}")
    assert topo_c1.origin == base_c1.origin, (
        f"C1's seat: base {base_c1.origin}, topology {topo_c1.origin}")
    assert topo_c1.from_seat == base_c1.from_seat
    assert topo_c1.to_seat == base_c1.to_seat
    assert topo_c1_plan.host_paths == base_c1_plan.host_paths, (
        f"host path: base {base_c1_plan.host_paths}, "
        f"topology {topo_c1_plan.host_paths}")
    assert topo_r1.host_token == base_r1.host_token == "BOOT0"
    assert topo_r1.origin == base_r1.origin


def test_a_translation_keeps_the_choice_and_moves_the_seat_rigidly():
    """平移：选的还是那只脚，座位与 host path 跟着整体平移。"""
    ctx = _context()
    circuit, _spec = _module_view()
    book = t._book()
    placed = _base(ctx)
    delta = (40.0, -30.0)
    origins = {part: (x + delta[0], y + delta[1])
               for part, (x, y) in placed.origins.items()}
    moved = _topology_bound(ctx, origins, placed.poses)
    before_plan, before = _seat(_service_plans(placed), "C1")
    after_plan, after = _seat(moved, "C1")

    assert after.host_token == before.host_token, (
        f"a rigid translation changed the host foot: {before.host_token!r} -> "
        f"{after.host_token!r}")
    expected = _outermost_host(
        book, circuit, "U1", SHARED_NET, placed.poses["U1"], origins["U1"])
    assert after.host_token == expected
    assert _close(after.origin, (
        before.origin[0] + delta[0], before.origin[1] + delta[1]))
    assert _close(after.from_seat, (
        before.from_seat[0] + delta[0], before.from_seat[1] + delta[1]))
    for old, new in zip(before_plan.host_paths[0], after_plan.host_paths[0]):
        assert _close(new, (old[0] + delta[0], old[1] + delta[1])), (old, new)


def test_a_pose_that_turns_the_foot_away_is_refused_by_name():
    """非法换姿：声明侧被翻走时具名拒绝，不静默保留旧座位、也不猜一只脚。

    §41-3：位姿变化后非法必须具名拒绝。同一颗 MCU 的 180° 位姿把两枚 3V3 脚与 BOOT0
    都翻到宿主另一侧，模板声明的阅读侧随之不成立——这里量的是那条拒绝真的发生。
    """
    ctx = _context()
    placed = _base(ctx)
    poses = {**placed.poses, "U1": _illegal_pose(ctx, "180")}
    plans = _topology_bound(ctx, placed.origins, poses)
    assert plans, "the binder answered nothing at all"
    for plan in plans:
        assert not plan.seated, (
            f"{plan.group_id} seated a branch on an illegal pose: "
            f"{[(cell.part_id, cell.host_token) for cell in plan.cells]}")
        assert plan.refusal is not None, plan
        assert plan.cells == (), plan.cells
    text = " | ".join(plan.refusal.render() for plan in plans if plan.refusal)
    assert "left" in text or "right" in text, (
        "the refusal must name the reading side the seat asked for: " + text)
    for token in ("VDD", "VBAT", "BOOT0"):
        assert token in text, (token, text)
    # the legal pose still answers the rule — the refusal is about the pose, not
    # about the binder giving up on this page
    _plan, _cell = _seat(_topology_bound(ctx, placed.origins, placed.poses), "C1")


def test_a_reordered_host_pin_list_does_not_change_the_choice():
    """宿主 pin 列表重排：允许集合与选脚都不动（不按脚序取首脚）。"""
    circuit, _spec = _module_view()
    normal_ctx = _context()
    normal_placed = _base(normal_ctx)
    _normal_plan, normal_cell = _seat(_service_plans(normal_placed), "C1")

    book = t._book()
    profile = _profile(book, circuit, "U1")
    reversed_book = dict(book)
    reversed_book[profile.symbol_ref] = dataclasses.replace(
        profile, pins=tuple(reversed(profile.pins)))
    reversed_ctx = _context(book=reversed_book)
    reversed_placed = _base(reversed_ctx)
    _rev_plan, reversed_cell = _seat(_service_plans(reversed_placed), "C1")
    bound = _topology_bound(
        reversed_ctx, normal_placed.origins, normal_placed.poses)
    _bound_plan, bound_cell = _seat(bound, "C1")

    expected = _outermost_host(
        book, circuit, "U1", SHARED_NET, normal_placed.poses["U1"],
        normal_placed.origins["U1"])
    assert normal_cell.host_token == expected
    assert reversed_cell.host_token == expected, (
        "the base binder always read the pose, so a reordered pin list must not "
        f"move it: {normal_cell.host_token!r} -> {reversed_cell.host_token!r}")
    assert bound_cell.host_token == expected, (
        "the topology consumer still takes the first foot of the list: "
        f"{bound_cell.host_token!r} (expected {expected!r})")


# ==================================================== 2. 宿主端点审计与回放


def _audit(plans, shared, book, circuit, poses, origins):
    """Every bound seat's host lead starts on the foot the plan itself names."""
    members = {
        net.id: {(member.partition(".")[0], member.partition(".")[2])
                 for member in net.members}
        for net in circuit.nets
    }
    problems: list[str] = []
    for plan in plans:
        if not plan.seated:
            problems.append(
                f"{plan.group_id}: not seated "
                f"({plan.refusal.render() if plan.refusal else 'no seats'})")
            continue
        cell = plan.cells[0]
        net_id = shared[cell.part_id]
        feet = _net_feet(circuit, plan.host_part, net_id)
        if cell.host_token not in feet:
            problems.append(
                f"{cell.part_id}: host foot {plan.host_part}."
                f"{cell.host_token} is not on {net_id!r} ({feet!r})")
        if not plan.host_paths:
            problems.append(f"{cell.part_id}: no host path recorded")
            continue
        tip = _tip(book, circuit, plan.host_part, cell.host_token,
                   poses[plan.host_part], origins[plan.host_part])
        start = plan.host_paths[0][0]
        if not _close(start, tip):
            problems.append(
                f"{cell.part_id}: host path starts at {start}, the chosen foot "
                f"{cell.host_token} is at {tip}")
        if not _close(plan.host_paths[0][-1], cell.from_seat):
            problems.append(
                f"{cell.part_id}: host path ends at {plan.host_paths[0][-1]}, "
                f"the branch's from seat is {cell.from_seat}")
        if (plan.host_part, cell.host_token) not in members[net_id]:
            problems.append(
                f"{cell.part_id}: the chosen foot is not a member of the shared "
                f"net {net_id!r}")
    return problems


def test_every_bound_seat_starts_its_host_path_on_the_foot_it_names():
    """审计：base、topology 与平移三种答案上，host path 起点都是选定脚的 tip。"""
    ctx = _context()
    circuit, _spec = _module_view()
    book = t._book()
    shared = _shared_nets(ctx)
    placed = _base(ctx)
    what = _audit(_service_plans(placed), shared, book, circuit,
                  placed.poses, placed.origins)
    assert what == [], what

    topology = dc._topology_placement(ctx)
    assert not isinstance(topology, str), topology.detail
    what = _audit(_service_plans(topology), shared, book, circuit,
                  topology.poses, topology.origins)
    assert what == [], what

    delta = (35.0, 25.0)
    moved = {part: (x + delta[0], y + delta[1])
             for part, (x, y) in placed.origins.items()}
    what = _audit(_topology_bound(ctx, moved, placed.poses), shared, book,
                  circuit, placed.poses, moved)
    assert what == [], what


def _at(plan, book, circuit, part_id, token):
    part = plan.part(part_id)
    return _tip(book, circuit, part_id, token,
                dc.SymbolPose(rotation=int(part.rotation),
                              mirror=bool(part.mirror)),
                (part.x, part.y))


def _component(runs, start):
    """Every point connected to ``start`` through the given runs."""
    key = (round(start[0], 6), round(start[1], 6))
    joined: dict[tuple, set] = {}
    for run in runs:
        points = [(round(point[0], 6), round(point[1], 6)) for point in run]
        for point in points:
            joined.setdefault(point, set())
        for first, second in zip(points, points[1:]):
            joined[first].add(second)
            joined[second].add(first)
    if key not in joined:
        return set()
    seen = {key}
    stack = [key]
    while stack:
        for neighbour in joined[stack.pop()]:
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    return seen


def test_the_final_drawing_wires_the_branch_to_the_selected_foot():
    """最终图纸消费同一次选脚：C1 连到选定脚，另一只 3V3 脚不在同一段导体上。"""
    circuit, spec = _module_view()
    book = t._book()
    result = dc.compile(circuit, spec, book, dc.CompileBudget(max_candidates=4))
    assert result.ok, result.render_failures()
    plan = result.best()
    u1 = plan.part("U1")
    assert u1 is not None
    expected = _outermost_host(
        book, circuit, "U1", SHARED_NET,
        dc.SymbolPose(rotation=int(u1.rotation), mirror=bool(u1.mirror)),
        (u1.x, u1.y))
    feet = _net_feet(circuit, "U1", SHARED_NET)
    assert len(feet) > 1, feet

    runs = [list(segment.points) for segment in plan.segments
            if segment.net == SHARED_NET]
    branch_tip = _at(plan, book, circuit, "C1", "1")
    component = _component(runs, branch_tip)
    assert component, (
        f"the branch's 3V3 foot {branch_tip} is on no {SHARED_NET} conductor: "
        f"{runs}")
    selected = {foot: _at(plan, book, circuit, "U1", foot) for foot in feet}
    assert any(_close(point, selected[expected]) for point in component), (
        f"the drawing does not reach the chosen foot {expected!r} "
        f"({selected[expected]}); the branch's conductor is {sorted(component)} "
        f"and the feet are {selected}")
    for foot, point in selected.items():
        if foot == expected:
            continue
        assert not any(_close(item, point) for item in component), (
            f"the branch is drawn on {foot!r} ({point}) instead of the chosen "
            f"{expected!r}: {sorted(component)}")


def test_the_terminal_flag_stands_on_the_seat_it_was_bound_to():
    """旗标同源：C1 的 GND 旗挂在 plan 自己声明的 to_seat 上，不是另一处脚。"""
    circuit, spec = _module_view()
    book = t._book()
    ctx = _context()
    placed = _base(ctx)
    _plan, cell = _seat(_service_plans(placed), "C1")

    result = dc.compile(circuit, spec, book, dc.CompileBudget(max_candidates=4))
    assert result.ok, result.render_failures()
    plan = result.best()
    u1 = plan.part("U1")
    c1 = plan.part("C1")
    assert u1 is not None and c1 is not None
    # The drawing's own frame may be anchored; the seat is compared relative to
    # the host, so the page anchor cannot make this a false hit.
    drawn = (c1.x - u1.x, c1.y - u1.y)
    bound = (cell.origin[0] - placed.origins["U1"][0],
             cell.origin[1] - placed.origins["U1"][1])
    assert _close(drawn, bound), (
        f"the drawn seat is not the seat the binder reported: drawing {drawn}, "
        f"bound {bound}")

    to_tip = _at(plan, book, circuit, "C1", "2")
    anchor = (to_tip[0], to_tip[1] - dc.FLAG_LEAD)
    flags = [item for item in plan.power_symbols
             if item.net == "GND" and _close((item.x, item.y), anchor)]
    assert flags, (
        f"no GND flag at the seat's own lead end {anchor}; flags are "
        f"{[(item.net, item.x, item.y) for item in plan.power_symbols]}")
    lead = [list(segment.points) for segment in plan.segments
            if segment.net == "GND" and len(segment.points) == 2
            and _close(segment.points[0], to_tip)]
    assert lead and _close(lead[0][1], anchor), (
        f"the flag has no lead from the seat's to pin {to_tip}: {lead}")


# ============================================== 3. 强制 topology 与单选脚边界


def test_the_forced_topology_round_draws_the_mcu_page(monkeypatch):
    """`_variants` 与 `_widened_variants` 都为空时，真实候选只能来自 topology。

    base 兜底在这里结构上不可能：两轮都没有变体可建。任务书要求当前 MCU 在这种
    前置下真实产出候选，并通过独立逐脚、grammar 与 readability。
    """
    monkeypatch.setattr(dc, "_variants", lambda ctx: [])
    monkeypatch.setattr(dc, "_widened_variants", lambda ctx, result: [])
    circuit, spec = _module_view()
    book = t._book()
    result = dc.compile(circuit, spec, book, dc.CompileBudget(max_candidates=4))

    assert result.ok, (
        "the forced topology round produced no candidate: "
        + result.render_failures()
        + (" | rounds: " + "; ".join(
            f"{item.round}: {item.failure.detail}"
            for item in result.failure_rounds) if result.failure_rounds else ""))
    assert any("topology search was run" in note for note in result.notes), (
        result.notes)
    assert {item.variant for item in result.rejected} <= {"topology-search"}, (
        "a candidate was built by something other than the topology round: "
        f"{[(item.variant, item.reason[:80]) for item in result.rejected]}")

    plan = result.best()
    assert plan.evidence.grammar_findings == [], plan.evidence.grammar_findings
    problems = t._per_pin_problems(plan, circuit, book)
    assert problems == [], problems
    checked = readability.check(plan, circuit, spec, book)
    assert checked.hard_violations == [], [
        item.render() for item in checked.hard_violations]

    # 548D3D-H2e: the topology round's expectation is a **legal contract**, not a
    # named foot. The old "lowest same-net tip" rule is the base page's rule and
    # stays there; on a pose where that foot's channel would cut another host
    # foot's flag band (rule A), the legal foot is a different member of the same
    # allowed set — so what is pinned here is legality, proved independently:
    #   (1) the foot is one the circuit allows on this net;
    #   (2) the BoundPlan's foot is the foot the final drawing actually reaches;
    #   (3) the drawn channel is the planned channel and no flag band is cut.
    u1 = plan.part("U1")
    feet = _net_feet(circuit, "U1", SHARED_NET)
    ctx = _context()
    bound = dc._topology_placement(ctx)
    assert not isinstance(bound, str), bound.detail
    bound_plans = _service_plans(bound)
    _c1_plan, c1 = _seat(bound_plans, "C1")
    assert c1.host_token in feet, (
        f"the topology seat hangs off {c1.host_token!r}, which the circuit does "
        f"not put on {SHARED_NET!r} ({feet!r})")
    branch_tip = _at(plan, book, circuit, "C1", "1")
    runs = [list(segment.points) for segment in plan.segments
            if segment.net == SHARED_NET]
    component = _component(runs, branch_tip)
    selected_tip = _at(plan, book, circuit, "U1", c1.host_token)
    assert any(_close(point, selected_tip) for point in component), (
        f"the BoundPlan says {c1.host_token!r} but the drawing reaches no such "
        f"foot ({selected_tip}): {sorted(component)}")
    # legality, from independent geometry (the flag bands and the channel are
    # read off the drawing; nothing here calls the production selector)
    import test_548d_flag_aware_seats as fa
    delta = (plan.part("U1").x - bound.origins["U1"][0],
             plan.part("U1").y - bound.origins["U1"][1])
    shared = {template.cell.part_id: template.cell.from_net
              for template in dc._topology_request(ctx).service_templates}
    illegal = fa._channel_vs_band_problems(
        plan, bound_plans, circuit, book, shared, delta)
    assert illegal == [], illegal
    detour = fa._channel_problems(
        plan, bound_plans, circuit, book, shared, delta)
    assert detour == [], detour


def test_a_singleton_host_foot_is_never_replaced():
    """显式 singleton（U1 在 BOOT0 上只有一脚）不受平移/重排影响。"""
    circuit, _spec = _module_view()
    book = t._book()
    ctx = _context()
    placed = _base(ctx)
    _plan, r1 = _seat(_service_plans(placed), "R1")
    assert _net_feet(circuit, "U1", SINGLETON_NET) == ("BOOT0",)
    assert r1.host_token == "BOOT0"

    delta = (-25.0, 15.0)
    moved = {part: (x + delta[0], y + delta[1])
             for part, (x, y) in placed.origins.items()}
    _moved_plan, moved_r1 = _seat(_topology_bound(ctx, moved, placed.poses), "R1")
    assert moved_r1.host_token == "BOOT0", moved_r1.host_token

    profile = _profile(book, circuit, "U1")
    reversed_book = dict(book)
    reversed_book[profile.symbol_ref] = dataclasses.replace(
        profile, pins=tuple(reversed(profile.pins)))
    _rev_plan, rev_r1 = _seat(
        _topology_bound(_context(book=reversed_book),
                        placed.origins, placed.poses), "R1")
    assert rev_r1.host_token == "BOOT0", rev_r1.host_token

    # the multi-foot branch never leaves the net's real feet, and the singleton
    # branch is never swapped for another same-net foot
    feet = set(_net_feet(circuit, "U1", SHARED_NET))
    for plans in (_service_plans(placed),
                  _topology_bound(ctx, placed.origins, placed.poses)):
        _c1_plan, c1 = _seat(plans, "C1")
        assert c1.host_token in feet, (c1.host_token, feet)
        _r1_plan, seeded = _seat(plans, "R1")
        assert seeded.host_token == "BOOT0", seeded.host_token


def test_a_page_without_local_seats_states_no_service_foot():
    """未开启 localSeats 的页面不进入新绑定：没有 service 座位，只有旧图。"""
    ctx = _context(local_seats=False)
    placed = _base(ctx)
    assert _service_plans(placed) == ()
