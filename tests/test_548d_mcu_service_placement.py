"""548D3C1：服务座位的联合顺序 —— 宿主直接引线不得穿别的支路房间。

只验 `placement` 这一域：宿主引线按**真实 pin tip** 记录、两个方向的正面积
穿越测试、原顺序优先（无冲突逐字节不变）、冲突时按终端旗方向给联合顺序、
确实无解时具名拒绝。夹具复用 `tests/test_548d_panel_validation.py` 的
MCU32/C/R 符号（行距与生产 MCU 页同形：VDD=70、VSS=60、VBAT=50、BOOT0=40）。

不接 drawcompiler 的 `serviceLayout` 门，不画整页、不落画布、不声称整图通过：
本文件绿只证明座位层的判据，整图可读性由第二域与视觉闸另判。
"""

from __future__ import annotations

import test_548d_panel_validation as p32

from boardwise.engines import drawcompiler as dc
from boardwise.engines import placement

BOOK = p32._book()
GRID = 5.0
#: 生产 `_service_templates` 给服务 cell 的终端旗姿态：旗杆竖直，预留盒把
#: 杆也折进盒内（`_flag_box` + `FLAG_LEAD`），所以盒从 to 脚向下一整段。
FLAG_LEAD = ((0.0, 0.0), (0.0, -30.0))
FLAG_BOX = (-8.0, -75.0, 8.0, 0.0)


def _part(part_id: str, symbol: str) -> placement.PlacementPart:
    profile = BOOK[symbol]
    return placement.PlacementPart(
        part_id=part_id, profile=profile, poses=tuple(profile.poses))


def _nets(cells) -> tuple[placement.PlacementNet, ...]:
    members: dict[str, list[tuple[str, str]]] = {"3V3": [], "BOOT0": [], "GND": []}
    for cell in cells:
        members[cell.from_net].append((cell.part_id, cell.from_token))
        members[cell.to_net].append((cell.part_id, cell.to_token))
    classes = {"3V3": "power", "BOOT0": "", "GND": "gnd"}
    return tuple(
        placement.PlacementNet(
            net_id=net_id, members=tuple(members[net_id]), cls=classes[net_id])
        for net_id in ("3V3", "BOOT0", "GND")
    )


def _cell(part_id: str, symbol: str, host_token: str, shared: str,
          side: str, *, value: str, flag: bool = True,
          flag_box: tuple[float, float, float, float] = FLAG_BOX,
          ) -> placement.PanelCell:
    profile = BOOK[symbol]
    outward = (-1.0, 0.0) if side == "left" else (1.0, 0.0)
    pose = dc._arm_pose(profile, "1", "2", outward)
    assert pose is not None, f"{symbol} has no pose that reads from {side}"
    relative = placement.part_box(profile, pose, (0.0, 0.0))
    rows = dc._line_boxes(relative, [part_id, value], side)
    return placement.PanelCell(
        part_id=part_id, from_net=shared, to_net="GND",
        from_token="1", to_token="2", host_token=host_token, pose=pose,
        text_boxes=tuple(rows),
        flag_box=flag_box if flag else None,
        flag_lead=FLAG_LEAD if flag else (),
    )


def _decoupling(host_token: str = "VDD", part_id: str = "C1",
                flag: bool = True) -> placement.PanelCell:
    return _cell(part_id, "C", host_token, "3V3", "left",
                 value="100nF", flag=flag)


def _boot_pulldown(part_id: str = "R1") -> placement.PanelCell:
    return _cell(part_id, "R", "BOOT0", "BOOT0", "left", value="10k")


def _template(cell: placement.PanelCell,
              side: str = "left") -> placement.ServiceSeatTemplate:
    return placement.ServiceSeatTemplate(
        group_id=f"service:{cell.part_id}", host_part="U1", side=side,
        cell=cell, grid=GRID)


def _request(cells, templates, *, joint: bool = True) -> placement.PlacementInput:
    parts = [_part("U1", "MCU32")] + [
        _part(cell.part_id, "C" if cell.part_id.startswith("C") else "R")
        for cell in cells
    ]
    return placement.PlacementInput(
        parts=tuple(parts), nets=_nets(cells), grid=GRID,
        service_templates=tuple(templates),
        service_joint_order=joint)


def _answer(request, host_origin=(0.0, 0.0)):
    poses = {"U1": BOOK["MCU32"].poses[0]}
    origins = {"U1": host_origin}
    for template in request.service_templates:
        poses[template.cell.part_id] = template.cell.pose
        origins[template.cell.part_id] = (123.0, -77.0)
    return origins, poses


def _bind(request):
    origins, poses = _answer(request)
    return placement.bind_service_plans(request, origins, poses)


def _host_tip(token: str, origin=(0.0, 0.0)) -> tuple[float, float]:
    pin = placement._pin_for_token(BOOK["MCU32"], token)
    return placement.posed_tip(pin.tip, BOOK["MCU32"].poses[0], origin)


def _legs(plan):
    return [
        leg for path in plan.host_paths
        for leg in placement._service_lead_legs(path)
    ]


def _crossings(plan, other):
    """The other plan's reserves this plan's lead runs through (positive area)."""
    return [
        box for box in other.reserved_boxes
        if any(placement._boxes_overlap(leg, box) > 0.0 for leg in _legs(plan))
    ]


def _straight(plan) -> bool:
    (path,) = plan.host_paths
    return len(path) == 2 and abs(path[0][1] - path[1][1]) < 1e-9


# --------------------------------------------------------------- 负：原顺序
def test_the_declared_order_puts_the_decoupling_room_on_the_boot0_lead():
    """C1 先座时，R1 的 BOOT0 引线无论站哪一级都要穿过 C1 的旗预留（具名拒绝）。"""
    cell_c, cell_r = _decoupling(), _boot_pulldown()
    request = _request((cell_c, cell_r), (_template(cell_c), _template(cell_r)))
    origins, poses = _answer(request)
    plans, joint = placement._bind_service_sequence(
        request, request.service_templates, origins, poses, ())

    assert joint, "the declared order must report the joint crossing"
    by_group = {plan.group_id: plan for plan in plans}
    assert by_group["service:C1"].seated
    refused = by_group["service:R1"]
    assert not refused.seated
    detail = refused.refusal.render()
    assert "R1" in detail, detail
    assert "host lead" in detail, detail
    assert "service:C1" in detail, detail


def test_every_declared_rung_is_refused_because_the_lead_keeps_crossing():
    """同一条 40 单位的梯子，站多远都改不了引线跨过 C1 的旗列。"""
    cell_c, cell_r = _decoupling(), _boot_pulldown()
    request = _request((cell_c, cell_r), (_template(cell_c), _template(cell_r)))
    origins, poses = _answer(request)
    plans, _ = placement._bind_service_sequence(
        request, request.service_templates, origins, poses, ())
    r1 = plans[1]
    assert not r1.seated
    # ...and its refusal names the reference, not a silent free seat.
    detail = r1.refusal.render()
    assert "every rung outwards" in detail
    assert "service:C1" in detail, "the crossing refusal names the other branch"


# --------------------------------------------------------------- 正：联合顺序
def test_the_joint_order_seats_the_low_row_first_and_yields_the_decoupling_outwards():
    cell_c, cell_r = _decoupling(), _boot_pulldown()
    request = _request((cell_c, cell_r), (_template(cell_c), _template(cell_r)))
    plans = _bind(request)

    assert [plan.group_id for plan in plans] == ["service:C1", "service:R1"], (
        "one plan per declared seat, in the declared order")
    for plan in plans:
        assert plan.seated, plan.refusal.render() if plan.refusal else ""
        assert _straight(plan), plan.host_paths
    by_group = {plan.group_id: plan for plan in plans}
    r1, c1 = by_group["service:R1"], by_group["service:C1"]

    # The recorded lead is the host pin's real tip to the branch's own foot.
    assert r1.host_paths[0][0] == _host_tip("BOOT0")
    assert c1.host_paths[0][0] == _host_tip("VDD")
    assert r1.host_paths[0][1] == r1.cells[0].from_seat
    assert c1.host_paths[0][1] == c1.cells[0].from_seat

    # Neither lead runs through the other branch's part/text/flag room.
    assert _crossings(r1, c1) == []
    assert _crossings(c1, r1) == []

    # R1 keeps the near seat the low row owns; the decoupling yields outwards.
    alone = _bind(_request((cell_r,), (_template(cell_r),)))[0]
    assert r1.cells[0].origin == alone.cells[0].origin, (
        "the BOOT0 branch is the near seat, not a stepped-out one")
    assert r1.cells[0].from_seat[0] > c1.cells[0].from_seat[0]
    assert c1.cells[0].origin[0] < r1.cells[0].origin[0]


def test_the_winning_order_is_the_one_the_terminal_flags_state():
    """两支路都是向下旗：低 host 行先，就是 BOOT0（y=40）先于 VDD（y=70）。"""
    cell_c, cell_r = _decoupling(), _boot_pulldown()
    request = _request((cell_c, cell_r), (_template(cell_c), _template(cell_r)))
    origins, poses = _answer(request)
    orders = placement._service_seat_orders(request, origins, poses)
    assert orders[0] is request.service_templates, "the declared order leads"
    assert [t.cell.part_id for t in orders[1]] == ["R1", "C1"]
    assert placement._service_flag_axis(_template(cell_c)) == -1


def test_the_order_search_is_bounded_by_the_page_own_service_count():
    cells = (_decoupling("VDD", "C1"), _decoupling("VBAT", "C2"),
             _decoupling("PA13", "C3"), _boot_pulldown())
    request = _request(cells, tuple(_template(cell) for cell in cells))
    origins, poses = _answer(request)
    orders = placement._service_seat_orders(request, origins, poses)
    limit = placement.SERVICE_ORDER_PERMUTATION_LIMIT
    assert limit == 3, "permuting stops at three seats"
    # Four seats: the declared order plus the two flag-stated reading orders,
    # never 24 permutations — a refusing page is searched on every candidate.
    assert len(orders) == 3, [len(order) for order in orders]
    assert [order[0].cell.part_id for order in orders[1:]] == ["C3", "C1"]

    small = _request((_decoupling(), _boot_pulldown()),
                     (_template(_decoupling()), _template(_boot_pulldown())))
    small_orders = placement._service_seat_orders(small, *_answer(small))
    assert len(small_orders) <= 1 + 2 + 6, len(small_orders)
    assert len({tuple(placement._service_template_key(t) for t in order)
                for order in small_orders}) == len(small_orders), (
        "no order is tried twice")


# --------------------------------------------------------- 无冲突：原顺序不动
def test_a_page_with_no_joint_conflict_keeps_its_declared_order():
    left = _decoupling()
    right = _cell("C2", "C", "PA3", "3V3", "right", value="100nF")
    request = _request((left, right), (_template(left), _template(right, "right")))
    plans = _bind(request)

    assert [plan.group_id for plan in plans] == ["service:C1", "service:C2"]
    assert all(plan.seated for plan in plans)
    for template in request.service_templates:
        alone = _request(
            (template.cell,), (template,))
        single = _bind(alone)[0]
        bound = next(plan for plan in plans
                     if plan.group_id == template.group_id)
        assert bound.cells[0].origin == single.cells[0].origin, template.group_id
        assert bound.cells[0].from_seat == single.cells[0].from_seat


def test_no_service_templates_binds_nothing():
    request = _request((), ())
    origins, poses = _answer(request)
    assert placement.bind_service_plans(request, origins, poses) == ()
    assert placement.service_parts_of(()) == frozenset()


def test_one_ordinary_service_still_records_its_direct_host_lead():
    cell = _cell("C1", "C", "PA3", "3V3", "right", value="100nF")
    request = _request((cell,), (_template(cell, "right"),))
    (plan,) = _bind(request)

    assert plan.seated, plan.refusal.render() if plan.refusal else ""
    (path,) = plan.host_paths
    assert len(path) == 2 and path[0][1] == path[1][1]
    assert path[0] == _host_tip("PA3")
    assert path[1] == plan.cells[0].from_seat
    assert abs(path[0][1] - plan.cells[0].from_seat[1]) < 1e-9
    # The ordinary ladder still owns the near seat: nothing was re-ordered.
    assert plan.cells[0].from_seat[0] > path[0][0]


# ------------------------------------------------------------ 负：确实无空间
def test_two_branches_that_can_never_clear_each_other_are_refused_by_name():
    """同一 host 行上的两支路：谁后座，谁的引线都跨过先座者的房间 —— 无解。"""
    first = _decoupling("VDD", "C1")
    second = _decoupling("VDD", "C2")
    request = _request(
        (first, second), (_template(first), _template(second)))
    plans = _bind(request)

    seated = [plan for plan in plans if plan.seated]
    refused = [plan for plan in plans if not plan.seated]
    assert len(seated) == 1, [plan.group_id for plan in seated]
    assert len(refused) == 1, [plan.group_id for plan in plans]
    detail = refused[0].refusal.render()
    assert refused[0].group_id in detail, detail
    assert "host lead" in detail, detail
    assert len(plans) == 2, "a refused seat is still reported, never dropped"


# ------------------------------------------- patch10 的真实行距：VBAT50 / BOOT0 40
#: `drawcompiler` patch10 在真实姿态下给 C1 选同网最外侧脚 VBAT(y=50)，且旗预留
#: 按 C0 修好（`_flag_box` 已折杆，盒高 28、贴在 to 脚下方 25–53）。C1 与 R1 的
#: host 行只差 10，是本批唯一由真实页测出来的近行场景。
VBAT_FLAG_BOX = (-11.0, -53.0, 11.0, -25.0)


def _vbat_pair(*, joint: bool = True):
    cell_c = _cell("C1", "C", "VBAT", "3V3", "left", value="100nF",
                   flag_box=VBAT_FLAG_BOX)
    cell_r = _boot_pulldown()
    request = _request((cell_c, cell_r), (_template(cell_c), _template(cell_r)),
                       joint=joint)
    return request, cell_c, cell_r


def test_the_vbat_row_pair_declared_order_dies_on_a_room_not_a_lead():
    """声明序里 R1 被 C1 的房间逐级挡住（不是引线判据），必须触发换序。"""
    request, _c, _r = _vbat_pair()
    origins, poses = _answer(request)
    declared, joint = placement._bind_service_sequence(
        request, request.service_templates, origins, poses, ())

    assert [plan.seated for plan in declared] == [True, False]
    assert joint is False, (
        "a rung-exhaustion is not a lead crossing; the re-order must trigger on "
        "the refusal itself")
    detail = declared[1].refusal.render()
    assert "R1" in detail and "every rung outwards" in detail, detail


def test_the_vbat_row_pair_seats_r1_near_and_puts_c1_above_and_outboard():
    request, cell_c, cell_r = _vbat_pair()
    plans = _bind(request)

    assert [plan.group_id for plan in plans] == ["service:C1", "service:R1"]
    for plan in plans:
        assert plan.seated, plan.refusal.render() if plan.refusal else ""
        assert _straight(plan), plan.host_paths
    by_group = {plan.group_id: plan for plan in plans}
    r1, c1 = by_group["service:R1"], by_group["service:C1"]

    # R1 keeps the near seat the low row owns; C1 yields outwards.
    alone_r1 = _bind(_request((cell_r,), (_template(cell_r),)))[0]
    assert r1.cells[0].origin == alone_r1.cells[0].origin
    assert c1.cells[0].origin[0] < r1.cells[0].origin[0]

    # The decoupling's lead is the upper one and goes straight to its own foot.
    assert r1.host_paths[0][0] == _host_tip("BOOT0")
    assert c1.host_paths[0][0] == _host_tip("VBAT")
    assert r1.host_paths[0][0][1] == 40.0
    assert c1.host_paths[0][0][1] == 50.0
    assert c1.host_paths[0][1] == c1.cells[0].from_seat
    assert r1.host_paths[0][1] == r1.cells[0].from_seat

    # …and its terminal flag room is further out than the pull-down's.
    def flag_room(plan, template):
        rooms = placement._service_lead_rooms(request, template, plan)
        return rooms[-1]

    template_c = next(t for t in request.service_templates
                      if t.cell.part_id == "C1")
    template_r = next(t for t in request.service_templates
                      if t.cell.part_id == "R1")
    assert flag_room(c1, template_c)[2] <= flag_room(r1, template_r)[0], (
        "the decoupling's flag room stands outboard of the pull-down's")

    def rooms_crossed(plan, other, other_template):
        rooms = placement._service_lead_rooms(request, other_template, other)
        return [room for room in rooms
                if any(placement._boxes_overlap(leg, room) > 0.0
                       for leg in _legs(plan))]

    # No body or flag room of either seat is drawn through (the seat's own
    # geometry). The one remaining overlap is a **printed row**:
    assert rooms_crossed(r1, c1, template_c) == []
    assert rooms_crossed(c1, r1, template_r) == []
    assert _crossings(c1, r1) == [(-173.0, 42.5, -158.0, 51.5)], (
        "the decoupling's lead crosses the pull-down's printed 'R1' row — the "
        "text pass must see service leads (draw-side), not the seat")


def test_the_vbat_row_pair_refuses_nothing_outside_the_two_seats():
    """换序只改座位，不新增成本项、不改页面尺寸、不动第三方件。"""
    request, _c, _r = _vbat_pair()
    origins, poses = _answer(request)
    plans = placement.bind_service_plans(request, origins, poses)
    assert all(plan.seated for plan in plans)
    assert placement.service_parts_of(plans) == {"C1", "R1"}
    assert set(origins) == {"U1", "C1", "R1"}, "binding never mutates the answer"

# ---------------------------------------------- 默认关：旧 panelGroups 页的语义
#: `service_joint_order` 默认 False = 历史 binder：声明序、旧 rung、foreign 只看
#: host + 本 cell。draw 下一批才会从 `serviceLayout` 页设置里把它打开，旧
#: panelGroups 页在这之前必须与开工前的座位逐字一致。

def test_the_default_request_keeps_the_declared_order_and_its_legacy_refusal():
    request, _c, _r = _vbat_pair(joint=False)
    origins, poses = _answer(request)
    plans = placement.bind_service_plans(request, origins, poses)

    assert [plan.group_id for plan in plans] == ["service:C1", "service:R1"]
    assert plans[0].seated
    assert not plans[1].seated, "the declared order is not re-ordered"
    assert "every rung outwards" in plans[1].refusal.render()
    # A legacy seat keeps the near column; its recorded span is shared data
    # (the draw side reads it), while only the ordering and the joint rules
    # are gated on the switch.
    assert plans[0].cells[0].origin == (-130.0, 50.0)
    assert plans[0].host_paths == (((-80.0, 50.0), (-110.0, 50.0)),)


def test_the_default_request_keeps_a_lone_seat_and_its_direct_span():
    cell = _cell("C1", "C", "PA3", "3V3", "right", value="100nF")
    legacy = _bind(_request((cell,), (_template(cell, "right"),), joint=False))[0]
    joint = _bind(_request((cell,), (_template(cell, "right"),)))[0]
    assert legacy.seated and joint.seated
    assert legacy.cells[0].origin == joint.cells[0].origin, (
        "the switch only adds the joint rules; it never moves a lone seat")
    assert legacy.host_paths == joint.host_paths
    assert len(legacy.host_paths[0]) == 2, legacy.host_paths[0]


def test_the_default_request_still_calls_a_pending_branch_foreign():
    request, cell_c, cell_r = _vbat_pair(joint=False)
    origins, poses = _answer(request)
    # C1 stands where the pull-down's room is: legacy reads it as a foreign part.
    origins["C1"] = (-140.0, 40.0)
    r1 = request.service_templates[1]
    legacy = placement._bind_one_service(request, r1, origins, poses)
    assert not legacy.seated
    assert "foreign part 'C1'" in legacy.refusal.render()

    joint_request = _request((cell_c, cell_r), (request.service_templates), joint=True)
    joint_plan = placement._bind_one_service(joint_request, r1, origins, poses)
    assert joint_plan.seated, (
        joint_plan.refusal.render() if joint_plan.refusal else "")
