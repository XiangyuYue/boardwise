"""548J-B1：`serviceGroups` 的最小合成联合座位（真实电路、真实生产尺）。

夹具是一颗真实双侧 8 脚宿主、三颗同型上拉和一对去耦：右侧两个配置上拉共组，
左侧一颗上拉服务两个共享启动脚，去耦对自组。组由文档 + CircuitSpec + profile
判真：宿主由电路事实解析（不是位号），同组二端件同向、共享共同端子行，成员列序
由真实脚位决定，共同终端轨各挂一枚本地旗；宿主 GND 另挂就近旗；开放 TX/RX 用
`labelPolicy.stubMin` 的可见等长名字桩。

断言全部走生产尺：`drawcompiler.compile` 的最终 LayoutPlan 由
`readability.check` 过闸，逐脚/分区用 `readability.derive_netlist` 独立读出，
几何由 plan 自己的位姿与 profile 重算，不写坐标表。本批不接真实 WiFi、不声称
548J 完成；真机、页面、placement/shared 合同都不碰。
"""

from __future__ import annotations

import copy

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile, SymbolPose
from boardwise.engines import drawcompiler as dc
from boardwise.engines import readability

PROV = "verified_recipe"
PAGE = (0.0, 0.0, 1170.0, 825.0)
PARTS = ["U1", "R1", "R2", "R3", "C1", "C2"]


# ------------------------------------------------------------------ 真实夹具


def _pin(number: str, tip, direction: str) -> dict:
    return {"number": number, "name": number, "tip": list(tip),
            "direction": direction, "length": 10.0, "pinType": "passive"}


def _symbol(ref: str, body, pins) -> dict:
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": list(body), "pins": pins,
            "source": "test fixture (548J-B1)"}


def _profile_payloads() -> dict[str, dict]:
    return {
        # 8 脚双侧宿主：右 VDD/CFG_A/CFG_B/RX，左 GND/BOOT0/BOOT1/TX。
        "HOST8": _symbol("HOST8", [-70.0, -60.0, 70.0, 60.0], [
            _pin("VDD", [80.0, 45.0], "right"),
            _pin("CFG_A", [80.0, 15.0], "right"),
            _pin("CFG_B", [80.0, 5.0], "right"),
            _pin("RX", [-80.0, 55.0], "left"),
            _pin("GND", [-80.0, -45.0], "left"),
            _pin("BOOT0", [-80.0, -15.0], "left"),
            _pin("BOOT1", [-80.0, -5.0], "left"),
            _pin("TX", [-80.0, 35.0], "left"),
        ]),
        "R": _symbol("R", [-10.5, -4.5, 10.5, 4.5], [
            _pin("1", [-20.0, 0.0], "left"),
            _pin("2", [20.0, 0.0], "right"),
        ]),
        "C": _symbol("C", [-5.5, -8.5, 5.5, 8.5], [
            _pin("1", [0.0, 20.0], "up"),
            _pin("2", [0.0, -20.0], "down"),
        ]),
        "PWR-PWR": _symbol("PWR-PWR", [-6.0, 0.0, 6.0, 18.0], []),
        "PWR-GND": _symbol("PWR-GND", [-6.0, 0.0, 6.0, 18.0], []),
    }


def _book() -> dict[str, SymbolProfile]:
    return {
        ref: SymbolProfile.from_dict(copy.deepcopy(payload))
        for ref, payload in _profile_payloads().items()
    }


def _part(part_id: str, symbol: str, value: str = "") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value,
            "provenance": PROV}


def _net(net_id: str, cls: str, members) -> dict:
    return {"id": net_id, "class": cls, "members": list(members),
            "provenance": PROV}


def _parts() -> list[dict]:
    return [
        _part("U1", "HOST8", "HOST"),
        _part("R1", "R", "10k"), _part("R2", "R", "10k"),
        _part("R3", "R", "10k"),
        _part("C1", "C", "100n"), _part("C2", "C", "100n"),
    ]


def _nets() -> list[dict]:
    return [
        _net("CFG_A", "signal", ["U1.CFG_A", "R1.1"]),
        _net("CFG_B", "signal", ["U1.CFG_B", "R2.1"]),
        # 共享启动脚：同一个启动网落在宿主两个脚上。
        _net("BOOT", "signal", ["U1.BOOT0", "U1.BOOT1", "R3.1"]),
        _net("PWR", "power",
             ["U1.VDD", "R1.2", "R2.2", "R3.2", "C1.1", "C2.1"]),
        _net("GND", "gnd", ["U1.GND", "C1.2", "C2.2"]),
        # 开放信号：单脚网，只能由可见名字表达。
        _net("TX", "signal", ["U1.TX"]),
        _net("RX", "signal", ["U1.RX"]),
    ]


def _circuit(parts=None, nets=None) -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": copy.deepcopy(parts if parts is not None else _parts()),
        "nets": copy.deepcopy(nets if nets is not None else _nets()),
    })


def _groups() -> list[dict]:
    return [
        {"id": "config-right", "branches": [
            {"part": "R1", "from": "CFG_A", "to": "PWR"},
            {"part": "R2", "from": "CFG_B", "to": "PWR"},
        ]},
        {"id": "boot-left", "branches": [
            {"part": "R3", "from": "BOOT", "to": "PWR"},
        ]},
        {"id": "decoupling", "branches": [
            {"part": "C1", "from": "PWR", "to": "GND"},
            {"part": "C2", "from": "PWR", "to": "GND"},
        ]},
    ]


def _document(groups=_groups(), modules=None) -> dict:
    payload = {
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right",
                            "load": "right", "source": "left",
                            "power": "top", "gnd": "bottom"},
        "modules": modules if modules is not None else [{
            "id": "m", "parts": list(PARTS),
            "role": "host island", "grammarRef": "ic-periphery", "core": "U1",
        }],
        "labelPolicy": {"local": "wire", "crossModule": "label",
                        "highFanout": "label", "stubMin": 40.0},
    }
    if groups is not None:
        payload["serviceGroups"] = copy.deepcopy(groups)
    return payload


def _spec(groups=_groups(), modules=None) -> PresentationSpec:
    return PresentationSpec.from_dict(
        copy.deepcopy(_document(groups, modules)))


def _budget(keepouts=()) -> dc.CompileBudget:
    return dc.CompileBudget(
        max_candidates=4, page_box=PAGE, keepouts=tuple(keepouts))


def _compile(*, groups=_groups(), circuit=None, spec=None, keepouts=()):
    circuit = circuit if circuit is not None else _circuit()
    spec = spec if spec is not None else _spec(groups)
    book = _book()
    result = dc.compile(circuit, spec, book, _budget(keepouts))
    return circuit, spec, book, result


def _plan_or_fail(**kwargs):
    circuit, spec, book, result = _compile(**kwargs)
    assert result.ok, [
        (item.category, item.subject, item.detail, item.action)
        for item in result.failures
    ]
    return circuit, spec, book, result.best()


def _prepared(circuit, spec, book, keepouts=()) -> dc._Context:
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, spec, circuit)
    binding = dc._with_service_groups(binding, spec, circuit, book)
    prepared = dc._prepare(circuit, spec, binding, book, _budget(keepouts))
    assert prepared.context is not None, [
        item.detail for item in prepared.failures]
    return prepared.context


def _tip(plan, book, member: str) -> tuple[float, float]:
    part_id, _, token = member.partition(".")
    part = plan.part(part_id)
    assert part is not None, member
    profile = book[part.symbol_ref]
    pin = next(item for item in profile.pins
               if item.number == token or item.name == token)
    return transform_point(
        pin.tip[0], pin.tip[1], rotation=part.rotation, mirror=part.mirror,
        ox=part.x, oy=part.y,
    )


def _near(point, points) -> bool:
    return any(
        abs(point[0] - other[0]) <= 1e-6 and abs(point[1] - other[1]) <= 1e-6
        for other in points
    )


def _token_on(circuit, part_id: str, net_id: str) -> str:
    return dc._arm_token_on(dc._part_nets(circuit, part_id), net_id)


# ------------------------------------------------------------ 走通与逐脚


def test_the_joint_page_compiles_and_every_pin_is_one_node():
    circuit, spec, book, plan = _plan_or_fail()
    assert {part.part_id for part in plan.parts} == set(PARTS)
    derived = readability.derive_netlist(plan, book)
    for net in circuit.nets:
        groups = {frozenset(derived.group_of(member)) for member in net.members}
        assert len(groups) == 1, (net.id, groups)
        assert groups == {frozenset(net.members)}, (net.id, groups)
    assert set(derived.pin_points) == set(derived.wired_pins)


def test_no_drawing_node_carries_two_net_names():
    circuit, spec, book, plan = _plan_or_fail()
    derived = readability.derive_netlist(plan, book)
    for node, names in derived.node_names.items():
        assert len(set(names)) <= 1, (node, names)
    for net in circuit.nets:
        for member in net.members:
            names = derived.names_of(member)
            assert not names or names == (net.id,), (member, names)


def test_the_boot_net_shares_one_branch_and_two_host_pins():
    circuit, spec, book, plan = _plan_or_fail()
    derived = readability.derive_netlist(plan, book)
    node = derived.group_of("R3.1")
    assert set(node) == {"R3.1", "U1.BOOT0", "U1.BOOT1"}, node
    assert [item for item in plan.segments if item.net == "BOOT"]


# ------------------------------------------------- 同向、共同端子行、列序


def test_group_branches_share_one_pose_and_one_terminal_row():
    circuit, spec, book, plan = _plan_or_fail()
    for group in spec.service_groups:
        parts = [plan.part(branch.part) for branch in group.branches]
        poses = {(round(part.rotation, 6), part.mirror) for part in parts}
        assert len(poses) == 1, (group.id, poses)
        seats = [
            _tip(plan, book, f"{branch.part}."
                 f"{_token_on(circuit, branch.part, branch.to_net)}")
            for branch in group.branches
        ]
        rows = {round(seat[1], 6) for seat in seats}
        assert len(rows) == 1, (group.id, rows)


def test_pull_columns_follow_the_host_feet_not_the_declaration():
    circuit, spec, book, plan = _plan_or_fail()
    group = next(g for g in spec.service_groups if g.id == "config-right")
    feet = {
        branch.part: _tip(plan, book, f"U1.{_token_on(circuit, 'U1', branch.from_net)}")
        for branch in group.branches
    }
    # CFG_A 的宿主脚更高：离共同端子行更远，列更外（右组是 x 更大）。
    assert feet["R1"][1] > feet["R2"][1]
    assert plan.part("R2").x < plan.part("R1").x


def test_every_pull_branch_has_a_real_host_path():
    circuit, spec, book, plan = _plan_or_fail()
    for group in spec.service_groups:
        if group.id == "decoupling":
            continue
        for branch in group.branches:
            runs = [item for item in plan.segments
                    if item.net == branch.from_net]
            assert runs, (group.id, branch.part)
            ends = {tuple(run.points[0]) for run in runs} | {
                tuple(run.points[-1]) for run in runs}
            host_tips = [
                _tip(plan, book, member)
                for member in next(
                    net for net in circuit.nets if net.id == branch.from_net
                ).members if member.startswith("U1.")
            ]
            branch_tip = _tip(
                plan, book,
                f"{branch.part}.{_token_on(circuit, branch.part, branch.from_net)}")
            for tip in host_tips:
                assert _near(tip, ends), (branch.part, tip, ends)
            assert _near(branch_tip, ends), (branch.part, branch_tip, ends)


# --------------------------------------------------------------- 旗域


def test_each_terminal_family_has_one_local_flag_per_group():
    _c, _s, book, plan = _plan_or_fail()
    power = [symbol for symbol in plan.power_symbols if symbol.net == "PWR"]
    ground = [symbol for symbol in plan.power_symbols if symbol.net == "GND"]
    # 右侧配置上拉、左侧启动上拉、去耦对：三个 PWR 旗。
    assert len(power) == 3, power
    # 去耦对的 GND 旗 + 宿主 GND 的就近旗：两个，不是一条全板母线。
    assert len(ground) == 2, ground
    assert len({(round(s.x, 6), round(s.y, 6)) for s in power}) == 3
    for symbol in power + ground:
        assert symbol.symbol_ref in book
        assert symbol.rotation % 180.0 == 0.0


def test_no_bus_is_drawn_between_the_two_ground_flags():
    _c, _s, _book, plan = _plan_or_fail()
    ground = [symbol for symbol in plan.power_symbols if symbol.net == "GND"]
    xs = sorted(symbol.x for symbol in ground)
    assert xs[1] > xs[0]
    for run in (item for item in plan.segments if item.net == "GND"):
        low, high = sorted((run.points[0][0], run.points[-1][0]))
        assert not (low <= xs[0] and xs[1] <= high), (
            "GND 两组之间不许拉母线", run)


def _seated():
    circuit, spec, book = _circuit(), _spec(), _book()
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    assert failure is None, failure.detail
    return circuit, spec, book, ctx, placed


def _page_walls(ctx, placed):
    """The page's own obstacle sets, as `_build_service_group_variant` builds them."""
    occupied = list(ctx.budget.keepouts)
    solids = list(ctx.budget.keepouts)
    for part_id in sorted(placed.origins):
        profile = ctx.profile(part_id)
        pose = placed.poses[part_id]
        origin = placed.origins[part_id]
        occupied.append(dc._part_box(profile, pose, origin))
        body = dc._body_box(profile, pose, origin)
        if body is not None:
            solids.append(body)
        solids.extend(dc._pin_walls(profile, pose, origin))
    for record in placed.service_group_plans:
        for cell in record.cells:
            for _kind, _text, box in cell.text_boxes:
                occupied.append(box)
                solids.append(box)
        for rail in record.rails:
            solids.append(rail.flag_box)
    return occupied, solids


def test_an_ordinary_signal_routes_around_the_seated_copper():
    """普通多成员 signal 走 `_joint_route_net`：不穿异网已落铜、不落异网脚。"""
    nets = _nets()
    for net in nets:
        if net["id"] == "BOOT":
            # 同一条启动网按「脚 → 支路脚 → 另一只脚」排队，前一段从脚外侧出发。
            net["members"] = ["U1.BOOT0", "R3.1", "U1.BOOT1"]
    circuit = _circuit(nets=nets)
    spec, book = _spec(), _book()
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    assert failure is None, failure.detail
    occupied, solids = _page_walls(ctx, placed)
    segments = []
    for record in placed.service_group_plans:
        for cell in record.cells:
            for path in cell.host_paths:
                segments.append(dc.LayoutSegment(
                    net=cell.from_net, points=[dc._point(p) for p in path]))
        for rail in record.rails:
            for run in rail.runs:
                segments.append(dc.LayoutSegment(
                    net=rail.net, points=[dc._point(p) for p in run]))
    before = list(segments)
    assert dc._joint_route_net(
        ctx, "BOOT", placed, solids, segments, occupied) is None
    fresh = segments[len(before):]
    assert fresh and {item.net for item in fresh} == {"BOOT"}
    boot = next(net for net in circuit.nets if net.id == "BOOT")
    tips = {
        dc._key(value)
        for member in boot.members
        for part_id, _sep, token in [member.partition(".")]
        for value in [dc._pin_point(
            ctx, part_id, token, placed.poses, placed.origins)]
        if value is not None
    }
    ends = {dc._key(item.points[0]) for item in fresh} | {
        dc._key(item.points[-1]) for item in fresh}
    assert tips <= ends, (sorted(tips), sorted(ends))
    foreign = [(item.net, a, b) for item in before if item.net != "BOOT"
               for a, b in zip(item.points, item.points[1:])]
    foreign_tips = {
        dc._key(value)
        for part_id in placed.origins
        for pin in ctx.profile(part_id).pins
        if f"{part_id}.{pin.number}" not in set(boot.members)
        for value in [dc._pin_point(
            ctx, part_id, pin.number, placed.poses, placed.origins)]
        if value is not None
    }
    for item in fresh:
        for point in item.points:
            assert dc._key(point) not in foreign_tips, point
        for a, b in zip(item.points, item.points[1:]):
            for _net, c, d in foreign:
                assert not dc._collinear_overlap(a, b, c, d), (a, b, c, d)
                assert not dc._strictly_on_segment(a, c, d), a
                assert not dc._strictly_on_segment(b, c, d), b


def test_no_two_nets_cross_inside_the_seat():
    """组内不同 net 的铜严格内部交叉 = 0，readability 的 crossings 读数也是 0。"""
    circuit, spec, book, plan = _plan_or_fail()
    edges = [(item.net, a, b) for item in plan.segments
             for a, b in zip(item.points, item.points[1:])]
    assert len(edges) > 1
    for index, (net, a, b) in enumerate(edges):
        for other, c, d in edges[index + 1:]:
            if net == other:
                continue
            assert dc._proper_crossing(a, b, c, d) is None, (net, other)
    checked = readability.check(
        plan, circuit, spec, book, page_box=PAGE, grid=_budget().grid)
    assert checked.soft_metrics.get("crossings", 0.0) == 0.0, (
        checked.soft_reasons)
    assert checked.hard_violations == [], [
        item.render() for item in checked.hard_violations]


def test_a_shared_rail_flag_points_off_its_row():
    """共享轨旗只认一种朝向：power 从端子行向上、gnd 向下，且 lead 与朝向一致。"""
    _c, _s, _book_, ctx, placed = _seated()
    assert placed.service_group_plans
    checked = 0
    for record in placed.service_group_plans:
        for rail in record.rails:
            row_y = rail.runs[0][0][1]
            lead = rail.lead
            rise = lead[-1][1] - lead[0][1]
            assert abs(rise) > 0.0, (record.group_id, rail.net)
            assert abs(lead[0][1] - row_y) <= 1e-6, (record.group_id, rail.net)
            assert abs(lead[-1][1] - rail.anchor[1]) <= 1e-6
            if rail.cls == "power":
                assert rail.anchor[1] >= row_y, (record.group_id, rail.net)
            elif rail.cls == "gnd":
                assert rail.anchor[1] <= row_y, (record.group_id, rail.net)
            assert (rise > 0) == (rail.anchor[1] >= row_y), (
                record.group_id, rail.net)
            for cell in record.cells:
                body = dc._body_box(
                    ctx.profile(cell.part_id), cell.pose, cell.origin)
                if body is None:
                    continue
                assert not (body[0] < rail.anchor[0] < body[2]
                            and body[1] < rail.anchor[1] < body[3]), (
                    record.group_id, rail.net)
            checked += 1
    assert checked >= 3


def test_every_flag_stands_clear_of_bodies_and_foreign_copper():
    """每枚旗：连接点不落任何 part body，整段 lead 不跨异网 segment、不压他脚。"""
    _c, _s, book, plan = _plan_or_fail()
    poses = {part.part_id: SymbolPose(
        rotation=int(part.rotation), mirror=part.mirror)
        for part in plan.parts}
    origins = {part.part_id: (part.x, part.y) for part in plan.parts}
    bodies = {}
    walls = {}
    for part in plan.parts:
        profile = book[part.symbol_ref]
        body = dc._body_box(profile, poses[part.part_id], origins[part.part_id])
        if body is not None:
            bodies[part.part_id] = body
        walls[part.part_id] = dc._pin_walls(
            profile, poses[part.part_id], origins[part.part_id])
    foreign: dict[str, list] = {}
    for segment in plan.segments:
        foreign.setdefault(segment.net, []).extend(
            (a, b) for a, b in zip(segment.points, segment.points[1:]))
    assert plan.power_symbols
    for symbol in plan.power_symbols:
        for part_id, body in bodies.items():
            assert not (body[0] < symbol.x < body[2]
                        and body[1] < symbol.y < body[3]), (symbol.net, part_id)
        leads = [item for item in plan.segments if item.net == symbol.net
                 and dc._key(item.points[-1]) == dc._key((symbol.x, symbol.y))]
        assert leads, (symbol.net, symbol.x, symbol.y)
        for a, b in zip(leads[0].points, leads[0].points[1:]):
            for net, edges in foreign.items():
                if net == symbol.net:
                    continue
                for c, d in edges:
                    assert not dc._collinear_overlap(a, b, c, d), (
                        symbol.net, net)
                    assert dc._proper_crossing(a, b, c, d) is None, (
                        symbol.net, net)
            for part_id, boxes in walls.items():
                for box in boxes:
                    assert not dc._segment_hits_box(a, b, box), (
                        symbol.net, part_id)


# ------------------------------------------------------------------ 文字


def test_every_group_branch_prints_its_reference_and_value():
    _c, spec, _b, plan = _plan_or_fail()
    for group in spec.service_groups:
        for branch in group.branches:
            mine = [text for text in plan.texts if text.part_id == branch.part]
            assert branch.part in {text.text for text in mine}, branch.part
            assert "value" in {text.kind for text in mine}, branch.part


def test_no_text_boxes_overlap_on_the_finished_page():
    _c, _s, _b, plan = _plan_or_fail()
    kinds = {(text.part_id, text.kind) for text in plan.texts}
    for part in plan.parts:
        assert (part.part_id, "reference") in kinds, part.part_id
    boxes = [box for _label, box in plan.all_text_boxes()]
    for index, left in enumerate(boxes):
        for right in boxes[index + 1:]:
            assert not (
                min(left[2], right[2]) - max(left[0], right[0]) > 0
                and min(left[3], right[3]) - max(left[1], right[1]) > 0
            ), (left, right)


# ------------------------------------------------------------------ frame


def test_the_group_frame_holds_its_parts_text_paths_and_flags():
    circuit = _circuit()
    spec = _spec()
    book = _book()
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    assert failure is None, failure.detail
    assert placed.service_group_plans
    part_members = {member for net in circuit.nets for member in net.members}
    for record in placed.service_group_plans:
        frame = record.frame
        for cell in record.cells:
            box = dc._part_box(ctx.profile(cell.part_id), cell.pose, cell.origin)
            assert _inside_box(frame, box), (record.group_id, cell.part_id)
            for _kind, _text, text_box in cell.text_boxes:
                assert _inside_box(frame, text_box), (record.group_id, text_box)
            for path in record.host_paths:
                for point in path:
                    assert _inside(frame, point), (record.group_id, point)
        for rail in record.rails:
            assert _inside_box(frame, rail.flag_box), (record.group_id, rail.net)
            for run in rail.runs:
                for point in run:
                    assert _inside(frame, point), (record.group_id, point)
    assert part_members


def _inside(frame, point) -> bool:
    return frame[0] <= point[0] <= frame[2] and frame[1] <= point[1] <= frame[3]


def _inside_box(frame, box) -> bool:
    return (
        frame[0] <= box[0] and frame[1] <= box[1]
        and box[2] <= frame[2] and box[3] <= frame[3]
    )


# ------------------------------------------------------------- 开放端口列


def test_open_ports_are_visible_equal_length_names():
    _c, _s, _b, plan = _plan_or_fail()
    lengths = {}
    for net_id in ("TX", "RX"):
        labels = [item for item in plan.labels if item.net == net_id]
        assert len(labels) == 1, (net_id, labels)
        runs = [item for item in plan.segments if item.net == net_id]
        assert len(runs) == 1, (net_id, runs)
        points = runs[0].points
        length = (
            abs(points[-1][0] - points[0][0])
            + abs(points[-1][1] - points[0][1])
        )
        lengths[net_id] = round(length, 6)
        assert abs(labels[0].x - points[-1][0]) <= 1e-6
        assert abs(labels[0].y - points[-1][1]) <= 1e-6
        assert labels[0].stub_min == round(length, 6)
    assert set(lengths.values()) == {40.0}, lengths


# ------------------------------------------------------------- 默认关闭


def test_a_page_without_the_key_draws_no_joint_seat():
    circuit = _circuit()
    spec = _spec(groups=None)
    book = _book()
    assert spec.service_groups == []
    result = dc.compile(circuit, spec, book, _budget())
    assert result.ok, [item.detail for item in result.failures]
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    assert failure is None
    assert placed.service_group_plans == ()
    assert dc._seat_service_groups(ctx, placed) is None
    assert placed.service_group_plans == ()


def test_the_empty_list_is_the_same_page_as_no_key():
    _c1, _s1, _b1, none_result = _compile(groups=None)
    _c2, _s2, _b2, empty_result = _compile(groups=[])
    assert none_result.ok and empty_result.ok
    assert none_result.best().to_jsonable() == empty_result.best().to_jsonable()


# ------------------------------------------------------------- topology 合同


def test_a_forced_topology_round_seats_the_same_groups_once(monkeypatch):
    """201B 的 topology 轮：构造梯子为空时真实出候选，组级记录只落一次。

    强制 `_variants`/`_widened_variants` 为空，`_place_chain_and_shelf` 一次
    都不许跑：候选只能来自 placement 搜索。同一 `Placement` clone 上重落一次
    座位，组级记录必须与已落的那一份逐项相同——座位是一次写入，不是二次搬动。
    这里不比较不同合法宿主姿态的脚位（姿态是每种答案自己的事实）。
    """
    circuit = _circuit()
    spec = _spec()
    book = _book()
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    assert failure is None, failure.detail
    clone = copy.deepcopy(placed)
    assert dc._seat_service_groups(ctx, clone) is None
    # 组级事实逐项相同：组、宿主、侧、种类、成员、端子网。座位坐标是每种合法
    # 宿主姿态自己的事实，这里不要求两份答案同脚位。
    def group_facts(records):
        return [
            (record.group_id, record.host_part, record.side, record.kind,
             tuple(cell.part_id for cell in record.cells),
             tuple(rail.net for rail in record.rails))
            for record in records
        ]

    assert group_facts(clone.service_group_plans) == group_facts(
        placed.service_group_plans)

    groups = {group.id: group for group in spec.service_groups}
    assert {record.group_id for record in placed.service_group_plans} == set(
        groups)
    for record in placed.service_group_plans:
        declared = groups[record.group_id]
        assert {cell.part_id for cell in record.cells} == {
            branch.part for branch in declared.branches}
        assert record.host_paths == tuple(
            path for cell in record.cells for path in cell.host_paths)

    calls = []

    def no_ladder(ctx, variant):
        calls.append(variant)
        raise AssertionError("the constructive ladder must not run")

    monkeypatch.setattr(dc, "_variants", lambda ctx: ())
    monkeypatch.setattr(dc, "_widened_variants", lambda ctx, result: ())
    monkeypatch.setattr(dc, "_place_chain_and_shelf", no_ladder)
    result = dc.compile(circuit, spec, book, _budget())
    assert calls == []
    assert result.ok, [item.detail for item in result.failures]
    plan = result.best()
    assert {part.part_id for part in plan.parts} == set(PARTS)


# ------------------------------------------------------- 不可满足/冲突负例


def test_a_group_spanning_both_host_sides_is_refused_by_name():
    nets = _nets()
    for net in nets:
        if net["id"] == "CFG_B":
            net["members"] = ["U1.BOOT0", "R2.1"]
        if net["id"] == "BOOT":
            net["members"] = ["U1.BOOT1", "R3.1"]
    spec = _spec(groups=[{
        "id": "mixed-sides", "branches": [
            {"part": "R1", "from": "CFG_A", "to": "PWR"},
            {"part": "R2", "from": "CFG_B", "to": "PWR"},
        ],
    }])
    result = dc.compile(
        _circuit(nets=nets), spec, _book(), _budget())
    assert not result.ok and result.candidates == []
    text = " ".join(
        item.detail + " " + item.action for item in result.failures)
    assert "mixed-sides" in text
    assert "face" in text or "side" in text


def test_a_three_foot_branch_is_refused_before_geometry():
    parts = _parts() + [_part("R9", "HOST8", "bad")]
    nets = _nets()
    for net in nets:
        if net["id"] == "CFG_B":
            net["members"] = ["U1.CFG_B", "R9.CFG_B"]
        if net["id"] == "PWR":
            net["members"].append("R9.VDD")
        if net["id"] == "GND":
            net["members"].append("R9.GND")
    spec = _spec(
        groups=[{"id": "three-foot", "branches": [
            {"part": "R9", "from": "CFG_B", "to": "PWR"}]}],
        modules=[{
            "id": "m", "parts": PARTS + ["R9"],
            "role": "host island", "grammarRef": "ic-periphery", "core": "U1",
        }])
    result = dc.compile(
        _circuit(parts=parts, nets=nets), spec, _book(), _budget())
    assert not result.ok
    text = " ".join(item.detail for item in result.failures)
    assert "three-foot" in text and "two-foot" in text


def test_a_page_keepout_on_the_seat_is_a_named_group_refusal():
    """C8 冲突：座位被外物占住时具名拒绝该组，不回旧散姿。"""
    circuit = _circuit()
    spec = _spec()
    book = _book()
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    assert failure is None, failure.detail
    frame = placed.service_group_plans[0].frame
    blocked = _prepared(circuit, spec, book, keepouts=(frame,))
    refusal = dc._seat_service_groups(blocked, placed)
    assert isinstance(refusal, dc.GrammarFailure)
    assert "serviceGroups" in (refusal.subject or "")
    assert "keep-out" in refusal.detail or "serviceGroups" in refusal.detail
    # The page itself stays unbuildable rather than falling back to the ladder.
    result = dc.compile(circuit, spec, book, _budget((frame,)))
    assert not result.ok and result.candidates == []
