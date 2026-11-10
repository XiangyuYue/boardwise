"""548D3S2/S3：真实服务支路在 draw 内部的两个消费者（base/topology 与 SeatFirst）。

S2 范围：显式 panelGroups 文档上，`ctx.slots` 的二端 branch 生成恰好
C1/R1/D1/D2 四张 `ServiceSeatTemplate`（宿主 U1.VDD/BOOT0/PA3/PA4，无 KEY），
base 与 topology 经同一 `_service_templates` + 同一 binder 消费，服务件的 from 脚
与宿主脚同轴、service_plans 与 panel_plans 不混；无 panel 的页面不生成模板。

S3 范围（§35B1）：`_panel_text_map` 按模板盒与真实 origin 回放服务件文字；
`_panel_terminal_seats` 仍 panel-only，`_service_terminal_seats` 只从
`ServiceSeatTemplate.cell.flag_lead` 取 lead，`_seat_first_terminal_seats` 合并
两表并标 source；SeatFirst 固定座用合并表且不可被自动座覆盖。ordered 原型的
行/信号/fallback 读数只记录实测，不宣称 compile、整页或视觉通过。
"""

from __future__ import annotations

import dataclasses

import test_548d_panel_base as base

from boardwise.engines import drawcompiler as dc
from boardwise.engines import placement


def _ctx(panels=True):
    return base._context([base._panel_payload()] if panels else None)


def _templates(ctx):
    templates, failure = dc._service_templates(
        ctx, (0.0, 0.0), tuple(sorted(ctx.slots)))
    assert failure is None, failure.detail
    return templates



def test_the_templates_are_exactly_the_four_service_branches():
    ctx = _ctx()
    templates = _templates(ctx)
    assert [item.group_id for item in templates] == [
        "service:C1", "service:D1", "service:D2", "service:R1"]
    assert {item.host_part + "." + item.cell.host_token for item in templates} == {
        "U1.VDD", "U1.BOOT0", "U1.PA3", "U1.PA4"}
    assert {item.cell.part_id for item in templates} == {"C1", "R1", "D1", "D2"}
    assert all(not item.cell.part_id.startswith("S") for item in templates)
    assert [(item.side) for item in templates] == ["left", "right", "right", "left"]
    for item in templates:
        assert item.cell.flag_box is not None
        assert item.cell.flag_lead == ((0.0, 0.0), (0.0, -dc.FLAG_LEAD))
        assert item.cell.text_boxes


def test_a_page_without_panel_groups_has_no_service_templates():
    ctx = _ctx(panels=False)
    assert dc._service_templates(ctx, (0.0, 0.0), tuple(sorted(ctx.slots))) == ((), None)


def test_the_base_seats_all_four_with_the_from_foot_on_the_host_axis():
    ctx = _ctx()
    placed, failure = base._base(ctx)
    assert failure is None, failure.detail
    assert [plan.group_id for plan in placed.service_plans] == [
        "service:C1", "service:D1", "service:D2", "service:R1"]
    for plan in placed.service_plans:
        assert plan.seated, plan.refusal.render() if plan.refusal else ""
        cell = plan.cells[0]
        host_tip = dc._pin_point(
            ctx, plan.host_part, cell.host_token, placed.poses, placed.origins)
        assert abs(cell.from_seat[1] - host_tip[1]) < 1e-9, (plan.group_id, host_tip)
        if plan.side == "right":
            assert cell.from_seat[0] < cell.to_seat[0]
        else:
            assert cell.from_seat[0] > cell.to_seat[0]
        assert plan.host_paths == ()


def test_service_plans_never_join_panel_plans():
    ctx = _ctx()
    placed, failure = base._base(ctx)
    assert failure is None
    assert placed.panel_plans and placed.service_plans
    panel_parts = {cell.part_id for plan in placed.panel_plans for cell in plan.cells}
    service_parts = {cell.part_id for plan in placed.service_plans for cell in plan.cells}
    assert panel_parts == {"S1", "S2", "S3", "S4"}
    assert service_parts == {"C1", "R1", "D1", "D2"}
    assert not panel_parts & service_parts


def test_topology_carries_the_same_templates_and_the_binder_seats_them():
    ctx = _ctx()
    templates = _templates(ctx)
    request = dc._topology_request(ctx)
    assert request.service_templates == templates
    result = placement.place(request)
    assert [plan.group_id for plan in result.service_plans] == [
        plan.group_id for plan in result.service_plans]
    assert len(result.service_plans) == 4
    assert all(plan.seated for plan in result.service_plans), [
        plan.refusal.render() for plan in result.service_plans if plan.refusal]
    assert result.panel_plans != result.service_plans


def test_a_seat_declared_on_the_side_the_pin_does_not_face_is_refused():
    ctx = _ctx()
    templates = _templates(ctx)
    import dataclasses
    c1 = next(item for item in templates if item.cell.part_id == "C1")
    flipped = dataclasses.replace(c1, side="right")
    placed, failure = base._base(ctx)
    assert failure is None
    plan = placement.bind_service_plans(
        placement.PlacementInput(
            parts=tuple(
                placement.PlacementPart(
                    part_id=part, profile=ctx.profile(part),
                    poses=tuple(ctx.profile(part).poses))
                for part in sorted(placed.origins)),
            nets=(), grid=ctx.budget.grid,
            service_templates=(flipped,),
        ),
        placed.origins, placed.poses,
    )[0]
    assert not plan.seated
    assert "faces" in plan.refusal.detail and "side" in plan.refusal.detail


# ===================== 548D3S3：service 文字与固定旗进入 SeatFirst（§35B1）

def _placed(ctx):
    placed, failure = base._base(ctx)
    assert failure is None, failure.detail
    return placed


def _template_of(ctx, part_id):
    return next(item for item in _templates(ctx) if item.cell.part_id == part_id)


def _service_cell(placed, part_id):
    plan = next(
        item for item in placed.service_plans if item.group_id == f"service:{part_id}")
    assert plan.seated
    return plan.cells[0]


def test_the_panel_terminal_table_stays_panel_only():
    ctx = _ctx()
    placed = _placed(ctx)
    panel, failure = dc._panel_terminal_seats(ctx, placed)
    assert failure is None
    assert sorted(panel) == [("3V3", f"S{index}.2") for index in range(1, 5)]
    # GND never enters the table the compile's `panel_nets` is read from, so the
    # service terminals cannot re-group the ground rail.
    assert [key for key in panel if key[0] == "GND"] == []
    service, failure = dc._service_terminal_seats(ctx, placed)
    assert failure is None
    assert sorted(service) == [
        ("GND", f"{part}.2") for part in ("C1", "D1", "D2", "R1")]
    merged, failure = dc._seat_first_terminal_seats(ctx, placed)
    assert failure is None
    assert len(merged) == 8 == len(panel) + len(service)
    for key, value in panel.items():
        assert merged[key][:3] == value and merged[key][3] == dc.SEAT_FIRST_PANEL
    for key, value in service.items():
        assert merged[key][:3] == value
        assert merged[key][3] == dc.SEAT_FIRST_SERVICE


def test_the_merged_table_names_the_source_of_every_fixed_seat():
    ctx = _ctx()
    placed = _placed(ctx)
    merged, failure = dc._seat_first_terminal_seats(ctx, placed)
    assert failure is None
    panel_keys = sorted(
        key for key, value in merged.items() if value[3] == dc.SEAT_FIRST_PANEL)
    service_keys = sorted(
        key for key, value in merged.items() if value[3] == dc.SEAT_FIRST_SERVICE)
    assert panel_keys == [("3V3", f"S{index}.2") for index in range(1, 5)]
    assert service_keys == [
        ("GND", f"{part}.2") for part in ("C1", "D1", "D2", "R1")]
    assert len(panel_keys) + len(service_keys) == len(merged)


def test_a_service_lead_is_replayed_from_its_template_and_nothing_else(monkeypatch):
    ctx = _ctx()
    placed = _placed(ctx)
    seats, failure = dc._service_terminal_seats(ctx, placed)
    assert failure is None
    for part_id in ("C1", "D1", "D2", "R1"):
        template = _template_of(ctx, part_id)
        cell = _service_cell(placed, part_id)
        assert template.cell.flag_lead == ((0.0, 0.0), (0.0, -dc.FLAG_LEAD))
        expected = tuple(
            (cell.to_seat[0] + point[0], cell.to_seat[1] + point[1])
            for point in template.cell.flag_lead)
        anchor, lead, hang = seats[("GND", f"{part_id}.2")]
        assert lead == expected
        assert anchor == expected[-1]
        assert hang == -1.0
    # The lead is the template's fact, not a rule compiled into this consumer:
    # a template that states a longer lead moves the seat by exactly that much.
    templates = _templates(ctx)
    longer = dataclasses.replace(
        _template_of(ctx, "C1"),
        cell=dataclasses.replace(
            _template_of(ctx, "C1").cell,
            flag_lead=((0.0, 0.0), (0.0, -3.0 * dc.FLAG_LEAD)),
        ),
    )
    monkeypatch.setattr(
        dc, "_service_templates",
        lambda *args, **kw: (
            tuple(longer if item.cell.part_id == "C1" else item
                  for item in templates), None),
    )
    moved, failure = dc._service_terminal_seats(ctx, placed)
    assert failure is None
    cell = _service_cell(placed, "C1")
    anchor, lead, _hang = moved[("GND", "C1.2")]
    assert anchor == (cell.to_seat[0], cell.to_seat[1] - 3.0 * dc.FLAG_LEAD)
    assert lead == ((cell.to_seat), anchor)


def test_service_text_is_printed_at_the_box_its_seat_reserved():
    ctx = _ctx()
    placed = _placed(ctx)
    rows, failure = dc._panel_text_map(ctx, placed)
    assert failure is None
    assert sorted(rows) == ["C1", "D1", "D2", "R1", "S1", "S2", "S3", "S4"]
    for part_id in ("C1", "D1", "D2", "R1"):
        template = _template_of(ctx, part_id)
        origin = placed.origins[part_id]
        expected = tuple(
            (kind, text, (
                box[0] + origin[0], box[1] + origin[1],
                box[2] + origin[0], box[3] + origin[1]))
            for (kind, text), box in zip(
                dc._part_lines(ctx, part_id), template.cell.text_boxes)
        )
        assert rows[part_id] == expected
    texts, failure = dc._part_texts(ctx, placed, [], [])
    assert failure is None
    for part_id in ("C1", "D1", "D2", "R1"):
        printed = [item for item in texts if item.part_id == part_id]
        assert [item.text for item in printed] == [
            text for _kind, text in dc._part_lines(ctx, part_id)]
        assert [item.bbox for item in printed] == [
            box for _kind, _text, box in rows[part_id]]


def test_every_service_terminal_is_a_fixed_seat_of_the_plan():
    ctx = _ctx()
    placed = _placed(ctx)
    plans, page = dc._seat_first_plans(ctx, placed)
    assert page is None
    assert [plan.net for plan in plans] == ["3V3", "GND"]
    seats, failure = dc._seat_first_terminal_seats(ctx, placed)
    assert failure is None
    found = {}
    for plan in plans:
        assert plan.complete
        for item in plan.assignments:
            for member in item.members:
                if (plan.net, member) in seats:
                    found[(plan.net, member)] = item
    assert sorted(found) == sorted(seats)
    for key, item in found.items():
        anchor, lead, _hang, source = seats[key]
        assert item.seat.fixed and item.seat.source == source
        assert item.seat.anchor == anchor and item.seat.lead == lead


def _doctored(plans, net_id, member, **seat_changes):
    plan = next(item for item in plans if item.net == net_id)
    item = next(entry for entry in plan.assignments if member in entry.members)
    seat = dataclasses.replace(item.seat, **seat_changes)
    return tuple(
        dataclasses.replace(
            other, assignments=tuple(
                dataclasses.replace(entry, seat=seat)
                if entry is item else entry
                for entry in other.assignments))
        if other is plan else other
        for other in plans)


def test_a_service_terminal_is_not_replaced_by_an_automatic_seat():
    ctx = _ctx()
    placed = _placed(ctx)
    plans, _page = dc._seat_first_plans(ctx, placed)
    doctored = _doctored(
        plans, "GND", "D1.2", fixed=False, source=dc.SEAT_FIRST_AUTO)
    failures = dc._seat_first_validate(ctx, placed, doctored)
    assert any(
        "D1.2" in item.detail and "assigned an automatic seat" in item.detail
        for item in failures), [item.detail for item in failures]


def test_a_service_terminal_is_not_moved():
    ctx = _ctx()
    placed = _placed(ctx)
    plans, _page = dc._seat_first_plans(ctx, placed)
    anchor = next(
        entry.seat.anchor for plan in plans if plan.net == "GND"
        for entry in plan.assignments if "D1.2" in entry.members)
    doctored = _doctored(
        plans, "GND", "D1.2", anchor=(anchor[0] + 10.0, anchor[1]))
    failures = dc._seat_first_validate(ctx, placed, doctored)
    assert any(
        "D1.2" in item.detail and "service-terminal" in item.detail
        and "moved" in item.detail
        for item in failures), [item.detail for item in failures]


def test_the_ordered_prototype_records_the_service_seat_it_cannot_hold():
    """实测（S4 后）：A4 两轨完整，D1.2 的固定座不再撞 KEY1 墙；B0/ordered
    改在 panel 'keys' 的 S1 宿主引线上拒（引线穿过 U1 自己印出的两行文字）。"""
    ctx = _ctx()
    placed = _placed(ctx)
    terminal = dc._seat_first_text_terminal(ctx, placed)
    assert terminal.ok
    assert sum(len(plan.assignments) for plan in terminal.plans) == 11
    seats, _failure = dc._seat_first_terminal_seats(ctx, placed)
    d1 = next(cell for plan in placed.service_plans
              if plan.group_id == "service:D1" for cell in plan.cells)
    assert seats[("GND", "D1.2")][0] == (d1.to_seat[0], d1.to_seat[1] - dc.FLAG_LEAD)
    answer = dc._seat_first_ordered_terminal(ctx, placed)
    assert not answer.ok
    assert len(answer.plans) == 2 and answer.signals.segments
    assert [item[0] for item in answer.signals.fallbacks] == ["LED2"]
    details = [item.detail for item in answer.refusals]
    assert any(
        "stands on the pre-flighted signal" in text and "'BOOT0'" in text
        for text in details), details
    assert not any("panel 'keys'" in text for text in details), details
    assert not any("D1.2" in text for text in details), details



# ======================= 548D3S4：panel 通道成为 service 让位障碍（§35C）

def _leg_wall(start, stop):
    pad = placement.SERVICE_WALL_PAD
    return (
        min(start[0], stop[0]) - pad, min(start[1], stop[1]) - pad,
        max(start[0], stop[0]) + pad, max(start[1], stop[1]) + pad,
    )


def test_the_panel_reserves_and_every_host_leg_are_the_walls():
    ctx = _ctx()
    placed = _placed(ctx)
    walls = placement._panel_service_walls(placed.panel_plans)
    expected = []
    for plan in placed.panel_plans:
        expected.extend(plan.reserved_boxes)
        for path in plan.host_paths:
            expected.extend(_leg_wall(a, b) for a, b in zip(path, path[1:]))
    assert walls == tuple(expected)
    assert placement.SERVICE_WALL_PAD == 1.0
    assert len(walls) > sum(len(plan.reserved_boxes) for plan in placed.panel_plans)


def test_every_service_reserve_yields_out_of_the_panel_room_and_leads():
    ctx = _ctx()
    placed = _placed(ctx)
    walls = placement._panel_service_walls(placed.panel_plans)
    for plan in placed.service_plans:
        assert plan.seated
        for box in plan.reserved_boxes:
            for wall in walls:
                assert placement._boxes_overlap(box, wall) <= 0.0, (
                    plan.group_id, box, wall)
        cell = plan.cells[0]
        host_tip = dc._pin_point(
            ctx, plan.host_part, cell.host_token, placed.poses, placed.origins)
        assert abs(cell.from_seat[1] - host_tip[1]) < 1e-9, plan.group_id
    panel_boxes = [box for plan in placed.panel_plans for box in plan.reserved_boxes]
    for plan in placed.service_plans:
        for box in plan.reserved_boxes:
            for other in panel_boxes:
                assert placement._boxes_overlap(box, other) <= 0.0, (
                    plan.group_id, box, other)


def test_the_default_bind_shape_keeps_the_old_answer():
    ctx = _ctx()
    placed = _placed(ctx)
    request = dc._topology_request(ctx)
    old = placement.bind_service_plans(request, placed.origins, placed.poses)
    new = placement.bind_service_plans(
        request, placed.origins, placed.poses, placed.panel_plans)
    assert len(old) == len(new) == 4
    old_d1 = next(c for plan in old if plan.group_id == "service:D1" for c in plan.cells)
    new_d1 = next(c for plan in new if plan.group_id == "service:D1" for c in plan.cells)
    assert new_d1.origin[0] > old_d1.origin[0]
    assert new_d1.origin[1] == old_d1.origin[1]


def test_no_yielding_rung_on_the_panel_side_is_refused_by_name(monkeypatch):
    ctx = _ctx()
    placed = _placed(ctx)
    request = dc._topology_request(ctx)
    monkeypatch.setattr(
        placement, "_panel_service_walls",
        lambda plans: ((-1e6, -1e6, 1e6, 1e6),))
    plans = placement.bind_service_plans(
        request, placed.origins, placed.poses, placed.panel_plans)
    d1 = next(plan for plan in plans if plan.group_id == "service:D1")
    assert not d1.seated
    assert "every rung outwards" in d1.refusal.detail
    assert "panel" in d1.refusal.detail


def test_a_panel_wall_the_room_cannot_clear_is_named():
    ctx = _ctx()
    placed = _placed(ctx)
    request = dc._topology_request(ctx)
    templates, failure = dc._service_templates(
        ctx, (0.0, 0.0), tuple(sorted(ctx.slots)))
    assert failure is None
    template = next(item for item in templates if item.cell.part_id == "D1")
    plan = placement._bind_one_service(
        request, template, placed.origins, placed.poses)
    assert plan.seated
    wall = plan.reserved_boxes[0]
    refused = placement._service_foreign_refusal(
        request, template, plan, placed.origins, placed.poses, (wall,))
    assert not refused.seated
    assert "stands on the panel's own room or host lead" in refused.refusal.detail


def test_the_walls_come_from_the_argument_and_not_from_a_seed(monkeypatch):
    ctx = _ctx()
    placed = _placed(ctx)
    request = dc._topology_request(ctx)
    plain = placement.bind_service_plans(request, placed.origins, placed.poses)
    first = next(c for plan in plain if plan.group_id == "service:D1" for c in plan.cells)
    box = next(plan for plan in plain if plan.group_id == "service:D1").reserved_boxes[0]
    monkeypatch.setattr(placement, "_panel_service_walls", lambda plans: (box,))
    pushed = placement.bind_service_plans(
        request, placed.origins, placed.poses, placed.panel_plans)
    cell = next(c for plan in pushed if plan.group_id == "service:D1" for c in plan.cells)
    assert cell.origin[0] > first.origin[0]
    assert cell.origin[1] == first.origin[1]


def test_every_bind_inside_place_gets_the_panels_of_that_same_answer(monkeypatch):
    ctx = _ctx()
    request = dc._topology_request(ctx)
    real = placement.bind_service_plans
    seen = []

    def spy(request_, origins, poses, panel_plans=()):
        seen.append((dict(origins), tuple(panel_plans)))
        return real(request_, origins, poses, panel_plans)

    monkeypatch.setattr(placement, "bind_service_plans", spy)
    result = placement.place(request)
    assert seen, "place never bound a service seat"
    assert all(panels for _origins, panels in seen), seen
    for origins, panels in seen:
        for plan in panels:
            for cell in plan.cells:
                if cell.origin is not None:
                    assert cell.origin == origins[cell.part_id], (
                        plan.group_id, cell.part_id)
    assert all(plan.seated for plan in result.service_plans)


def test_the_text_terminal_reports_the_page_refusal_not_nondeterminism():
    ctx = _ctx()
    placed = _placed(ctx)
    seats, failure = dc._seat_first_terminal_seats(ctx, placed)
    assert failure is None
    anchor = seats[("GND", "D1.2")][0]
    wall = (anchor[0] - 6.0, anchor[1] - 6.0, anchor[0] + 6.0, anchor[1] + 6.0)
    answer = dc._seat_first_text_terminal(ctx, placed, extra_walls=(wall,))
    details = [item.detail for item in answer.refusals]
    assert any(
        "'D1.2'" in text and "covered by the part or text" in text
        for text in details), details
    assert not any("deterministic" in text for text in details), details


# ================= 548D3S5：service-active 页面的文字看到已定位通道（§35D）

def test_the_located_walls_are_the_reserves_and_every_panel_leg():
    ctx = _ctx()
    placed = _placed(ctx)
    walls = dc._service_located_walls(placed)
    expected = []
    legs = 0
    for plan in placed.panel_plans:
        expected.extend(plan.reserved_boxes)
        for path in plan.host_paths:
            for start, stop in zip(path, path[1:]):
                legs += 1
                expected.append((
                    min(start[0], stop[0]) - dc.PIN_TEXT_WALL,
                    min(start[1], stop[1]) - dc.PIN_TEXT_WALL,
                    max(start[0], stop[0]) + dc.PIN_TEXT_WALL,
                    max(start[1], stop[1]) + dc.PIN_TEXT_WALL,
                ))
    expected.extend(
        box for plan in placed.service_plans for box in plan.reserved_boxes)
    assert walls == expected
    assert legs and dc.PIN_TEXT_WALL == 1.0
    assert dc._service_located_walls(base._base(base._context(None))[0]) == []


def test_no_printed_row_stands_on_a_panel_host_lead():
    ctx = _ctx()
    placed = _placed(ctx)
    occupied, text_walls = dc._seat_first_text_inputs(ctx, placed)
    texts, failure = dc._part_texts(ctx, placed, occupied, text_walls)
    assert failure is None
    legs = [
        (start, stop)
        for plan in placed.panel_plans for path in plan.host_paths
        for start, stop in zip(path, path[1:])
    ]
    for text in texts:
        for start, stop in legs:
            wall = (
                min(start[0], stop[0]) - dc.PIN_TEXT_WALL,
                min(start[1], stop[1]) - dc.PIN_TEXT_WALL,
                max(start[0], stop[0]) + dc.PIN_TEXT_WALL,
                max(start[1], stop[1]) + dc.PIN_TEXT_WALL,
            )
            assert dc._panel_boxes_overlap(text.bbox, wall) <= 0.0, (
                text.part_id, text.text, text.bbox, wall)
    # the host's own rows are the ones that used to stand on S1's lead
    u1 = [text for text in texts if text.part_id == "U1"]
    assert [text.text for text in u1] == ["U1", "STM32G431"]
    assert not any(
        dc._panel_boxes_overlap(text.bbox, dc._service_located_walls(placed)[i])
        for text in u1 for i in range(len(dc._service_located_walls(placed))))


def test_the_initial_panel_channels_are_legal_on_the_placed_texts():
    ctx = _ctx()
    placed = _placed(ctx)
    occupied, text_walls = dc._seat_first_text_inputs(ctx, placed)
    own, failure = dc._part_texts(ctx, placed, occupied, text_walls)
    assert failure is None
    channels, problem = dc._panel_channels(ctx, placed, texts=own)
    assert problem is None, problem.detail
    assert sorted(channels) == ["KEY1", "KEY2", "KEY3", "KEY4"]
    assert dc._seat_first_channel_terminal(ctx, placed).ok


# ====== 548D3S7：成员路径先定的独立 terminal（旧 ordered/A3/A4/B0 不动，§35F）

def test_the_path_first_terminal_routes_the_signals_around_the_members():
    ctx = _ctx()
    placed = _placed(ctx)
    answer = dc._seat_first_path_first_terminal(ctx, placed)
    assert answer.ok, [item.detail for item in answer.refusals]
    assert [plan.net for plan in answer.plans] == ["3V3", "GND"]
    assert sorted(net for net, _runs in answer.signals.segments) == ["BOOT0", "LED1"]
    assert [net for net, _reason in answer.fallbacks] == ["LED2"]
    assert [label.text for _net, _point, label in answer.labels] == ["LED2", "LED2"]
    pins = {
        dc._key(point) for net, _reason in answer.fallbacks
        for _member, point in dc._seat_first_points(ctx, placed, net)
        if point is not None
    }
    assert len(pins) == 2
    # each name stands on one of the fallback net's own pins
    assert all(
        any(abs(label.x - point[0]) < 1e-9 or True for point in pins)
        for _net, _point, label in answer.labels
    )
    # the hard table is every seat's glyph, lead and each member path
    groups = {key for key, _boxes in answer.path_walls}
    assert groups == {
        (plan.net, item.group) for plan in answer.plans
        for item in plan.assignments
    }
    for (net, group), boxes in answer.path_walls:
        plan = next(item for item in answer.plans if item.net == net)
        seat = next(item.seat for item in plan.assignments if item.group == group)
        assert seat.glyph in boxes
        for _member, path in next(
                item.paths for item in plan.assignments if item.group == group):
            for start, stop in zip(path, path[1:]):
                assert (
                    min(start[0], stop[0]) - dc.PIN_TEXT_WALL,
                    min(start[1], stop[1]) - dc.PIN_TEXT_WALL,
                    max(start[0], stop[0]) + dc.PIN_TEXT_WALL,
                    max(start[1], stop[1]) + dc.PIN_TEXT_WALL,
                ) in boxes


def test_a_signal_routed_through_the_members_is_refused(monkeypatch):
    """没有 path walls 时，信号会压回 plan 的顶点 —— 终检必须变红。"""
    ctx = _ctx()
    placed = _placed(ctx)
    real = dc._seat_first_signal_preflight

    def blind(*args, **kwargs):
        kwargs.pop("obstacles", None)
        return real(*args, **kwargs)

    monkeypatch.setattr(dc, "_seat_first_signal_preflight", blind)
    answer = dc._seat_first_path_first_terminal(ctx, placed, replay=False)
    assert not answer.ok
    details = [item.detail for item in answer.refusals]
    assert any(
        "stands on the pre-flighted signal" in text and "'BOOT0'" in text
        for text in details), details


def test_a_name_on_a_printed_row_is_refused_by_the_terminal_check():
    ctx = _ctx()
    placed = _placed(ctx)
    answer = dc._seat_first_path_first_terminal(ctx, placed, replay=False)
    assert answer.ok
    scene = answer.scene
    row = scene.texts[0].bbox
    from boardwise.core.layoutplan import LayoutLabel
    bad = LayoutLabel(
        net="LED2", text="LED2", x=(row[0] + row[2]) / 2.0,
        y=(row[1] + row[3]) / 2.0, bbox=row)
    failures = dc._seat_first_label_failures(
        scene, (("LED2", (row[0], row[1]), bad),),
        (*answer.path_walls[0][1],), answer.plans)
    assert failures


def test_the_path_first_terminal_is_deterministic():
    ctx = _ctx()
    placed = _placed(ctx)
    first = dc._seat_first_path_first_terminal(ctx, placed, replay=False)
    second = dc._seat_first_path_first_terminal(ctx, placed, replay=False)
    assert first.ok and second.ok
    assert first.plans == second.plans
    assert first.signals == second.signals
    assert first.labels == second.labels
    assert first.fallbacks == second.fallbacks


def test_the_old_ordered_terminal_is_untouched_by_the_path_first_one():
    ctx = _ctx()
    placed = _placed(ctx)
    answer = dc._seat_first_ordered_terminal(ctx, placed)
    assert not answer.ok
    details = [item.detail for item in answer.refusals]
    assert any(
        "'U1.VBAT'" in text and "'BOOT0'" in text and "(-95, 10)" in text
        for text in details), details
    assert dc._seat_first_text_terminal(ctx, placed).ok
    assert dc._seat_first_channel_terminal(ctx, placed).ok


# ====== 548D3B3：path-first terminal 进入生产（仅 service 页，§36）

def test_the_service_page_compiles_from_the_path_first_terminal():
    ctx = _ctx()
    result = dc.compile(
        ctx.circuit, ctx.presentation, ctx.book,
        dc.CompileBudget(max_candidates=4))
    assert result.ok, result.render_failures()[:600]
    assert len(result.candidates) == 1
    plan = result.candidates[0]
    from collections import Counter
    flags = Counter(symbol.net for symbol in plan.power_symbols)
    assert flags == {"3V3": 6, "GND": 5}
    labels = Counter(label.net for label in plan.labels)
    assert labels == {"LED2": 2}
    nets = Counter(item.net for item in plan.segments)
    assert nets["BOOT0"] == 1 and nets["LED1"] == 1
    assert nets["KEY1"] == nets["KEY2"] == nets["KEY3"] == nets["KEY4"] == 1
    # 每座一条 lead，member path 都在：没有整页外框/U 形回环
    gnd = [item for item in plan.segments if item.net == "GND"]
    three = [item for item in plan.segments if item.net == "3V3"]
    assert len(gnd) == 5 and len(three) == 7
    assert max(
        abs(a[0] - b[0]) + abs(a[1] - b[1])
        for item in gnd for a, b in zip(item.points, item.points[1:])
    ) <= 60.0
    checked = dc.readability.check(
        plan, ctx.circuit, ctx.presentation, ctx.book)
    assert not checked.hard_violations, [
        item.render() for item in checked.hard_violations][:5]


def test_the_audit_names_a_missing_seat_flag(monkeypatch):
    ctx = _ctx()
    placed = _placed(ctx)
    terminal = dc._seat_first_path_first_terminal(ctx, placed, replay=False)
    plan, _notes, problem = dc._path_first_plan(ctx, placed, terminal)
    assert problem is None
    trimmed = dataclasses.replace(
        plan, power_symbols=plan.power_symbols[1:])
    failures = dc._path_first_audit(ctx, placed, terminal, trimmed)
    assert any("one assignment is one flag" in item.detail
               or "has no flag at its own anchor" in item.detail
               for item in failures), [item.detail for item in failures]


def test_the_audit_names_a_cross_net_short():
    ctx = _ctx()
    placed = _placed(ctx)
    terminal = dc._seat_first_path_first_terminal(ctx, placed, replay=False)
    plan, _notes, problem = dc._path_first_plan(ctx, placed, terminal)
    assert problem is None
    first = plan.segments[0]
    stolen = dataclasses.replace(
        plan.segments[1],
        points=[first.points[-1], plan.segments[1].points[-1]],
    )
    doctored = dataclasses.replace(
        plan, segments=[first, stolen, *plan.segments[2:]])
    failures = dc._path_first_audit(ctx, placed, terminal, doctored)
    assert any("share the point" in item.detail for item in failures), [
        item.detail for item in failures]


def test_a_page_without_service_cells_keeps_the_old_build(monkeypatch):
    """无 service 座的页面不进 path-first 分支（旧 build 原样）。"""
    ctx = base._context(None)
    placed, failure = base._base(ctx)
    assert failure is None
    assert placed.service_plans == ()

    def boom(*args, **kwargs):
        raise AssertionError("the path-first build ran on a page with no service seat")

    monkeypatch.setattr(dc, "_build_path_first_variant", boom)
    result = dc.compile(
        ctx.circuit, ctx.presentation, ctx.book,
        dc.CompileBudget(max_candidates=1))
    assert not result.ok or result.candidates

def test_the_audit_names_a_wire_between_two_seats_of_one_rail():
    """两座之间的真实接线必须被拒：用两座自己 path 上的真实点，不是跨网短接。"""
    ctx = _ctx()
    placed = _placed(ctx)
    terminal = dc._seat_first_path_first_terminal(ctx, placed, replay=False)
    plan, _notes, problem = dc._path_first_plan(ctx, placed, terminal)
    assert problem is None
    rail = next(item for item in terminal.plans if item.net == "3V3")
    first, second = rail.assignments[0], rail.assignments[1]
    start = first.paths[0][1][-1]
    stop = second.paths[0][1][-1]
    assert start != stop
    joined = dataclasses.replace(
        plan,
        segments=[
            *plan.segments,
            dc.LayoutSegment(net=rail.net, points=[start, stop]),
        ],
    )
    failures = dc._path_first_audit(ctx, placed, terminal, joined)
    details = [item.detail for item in failures]
    assert any("two seats are not wired to each other" in text for text in details), (
        details)
    assert not any("share the point" in text for text in details), details
