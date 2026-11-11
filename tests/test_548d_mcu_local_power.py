"""548D3C1：MCU 本地供电 / BOOT0 / GND 的**正向结构验收**。

任务书：`evidence/548D/service-seat/mcu-local-readability-charter.md`；集成锁
`tasks/shared-platform.md` §16/§17；证据 `evidence/548D/service-seat/mcu-local/draw-c1.md`。

页面用 `semantic-islands-spec.json` 的同一份形状（三岛 + 顶层 `serviceLayout.pinGap=30`）：
service 座位把 C1/R1 放在宿主脚边，host 引线是固定通道，终端旗就近挂在自己的脚上。

本文件只钉**读得懂**这一层：三张网没有外框、BOOT0 是直线、每枚本地旗有自己的载体、
跨岛只有名字没有导线，以及 service 文本行与通道相遇时的重排（重排后仍无 text-on-wire）。
它不写参考坐标，也不复述编译器状态：几何只从 plan 与冻结电路读。
"""

from __future__ import annotations

import dataclasses

import pytest

import test_548d_panel_base as pb
import test_548d_semantic_islands as t
import test_548d_service_consumers as sc

from boardwise.core import presentationspec as pspec

from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines import readability

SERVICE_LAYOUT = {"pinGap": 30, "localSeats": True}
STUB = dc.STUB


def _spec():
    payload = {
        "grammarRef": "ic-periphery",
        "modules": [
            t._module("mcu", ["U1", "C1", "R1"], "host island", core="U1"),
            t._module("keys", t.KEY_PARTS, "key inputs", t.KEY_SIDES),
            t._module("led", ["D1", "D2"], "indicators", t.LED_SIDES),
        ],
        "moduleOrder": ["mcu", "keys", "led"],
        "flow": [{"from": "mcu", "to": "keys"}, {"from": "mcu", "to": "led"}],
        "serviceLayout": dict(SERVICE_LAYOUT),
    }
    return PresentationSpec.from_dict(payload)


def _page():
    board = t._circuit()
    return board, _spec(), pc.compile_page(board, _spec(), t._book(), t.PAGE)


def _mcu(result):
    module = result.modules["mcu"]
    assert module.ok, [str(item) for item in module.failures]
    best = module.best()
    return getattr(best, "plan", best)


def _pin(part, token):
    """The placed tip of one pin, found by number or name."""
    profile = t._book()[part.symbol_ref]
    pin = next(
        (item for item in profile.pins
         if item.number == token or item.name == token), None)
    assert pin is not None, token
    return transform_point(pin.tip[0], pin.tip[1], rotation=part.rotation,
                           mirror=part.mirror, ox=part.x, oy=part.y)


def _bounds(points):
    xs = [item[0] for item in points]
    ys = [item[1] for item in points]
    return min(xs), min(ys), max(xs), max(ys)


def _runs(plan, net):
    return [list(segment.points) for segment in plan.segments if segment.net == net]


def _bends(points):
    return max(0, len(points) - 2)


# --------------------------------------------------------------- 1. 正向结构


def test_the_three_island_page_and_the_mcu_island_compile():
    """三岛页与 MCU 单岛都出候选，逐脚分区与页闸全过。"""
    board, spec, result = _page()
    assert result.ok, result.render_failures()
    page = result.best()
    assert t._per_pin_problems(page.plan, board, t._book()) == []
    assert readability.check_page(page, board, spec, t._book()).hard_violations == []


def test_the_rails_stay_inside_their_own_pad_box():
    """3V3 / GND 没有外框：每条导线的拐点都在本网引脚外包框 ± STUB 内。"""
    board, spec, result = _page()
    plan = _mcu(result)
    parts = {part.part_id: part for part in plan.parts}
    for net in ("3V3", "GND"):
        pads = [
            _pin(parts[member.split(".")[0]], member.split(".")[1])
            for circuit_net in board.nets if circuit_net.id == net
            for member in circuit_net.members
            if member.split(".")[0] in parts
        ]
        low = _bounds(pads)
        for run in _runs(plan, net):
            for point in run:
                assert low[0] - STUB <= point[0] <= low[2] + STUB, (net, point, low)
                assert low[1] - STUB <= point[1] <= low[3] + STUB, (net, point, low)


def test_the_boot0_wire_is_one_straight_run():
    """BOOT0→R1.1 是一条直线：0 个拐点，两端就是两个脚。"""
    board, spec, result = _page()
    plan = _mcu(result)
    parts = {part.part_id: part for part in plan.parts}
    runs = _runs(plan, "BOOT0")
    assert len(runs) == 1, runs
    assert _bends(runs[0]) == 0, runs[0]
    ends = {tuple(runs[0][0]), tuple(runs[0][-1])}
    assert ends == {
        tuple(_pin(parts["U1"], "BOOT0")), tuple(_pin(parts["R1"], "1")),
    }, ends


def test_every_local_flag_stands_on_its_own_pad():
    """C1.2 与 R1.2 各自一枚 GND 旗，各有从该脚竖直出发的两点导线。"""
    board, spec, result = _page()
    plan = _mcu(result)
    parts = {part.part_id: part for part in plan.parts}
    used = set()
    for part_id in ("C1", "R1"):
        tip = _pin(parts[part_id], "2")
        leads = [
            list(segment.points) for segment in plan.segments
            if segment.net == "GND" and len(segment.points) == 2
            and abs(segment.points[0][0] - tip[0]) < 1e-9
            and abs(segment.points[0][1] - tip[1]) < 1e-9
            and abs(segment.points[1][0] - tip[0]) < 1e-9
        ]
        assert leads, (part_id, tip, [list(s.points) for s in plan.segments
                                      if s.net == "GND"])
        end_point = tuple(leads[0][1])
        flags = [
            symbol for symbol in plan.power_symbols
            if symbol.net == "GND"
            and abs(symbol.x - end_point[0]) < 1e-9
            and abs(symbol.y - end_point[1]) < 1e-9
        ]
        assert len(flags) == 1, (part_id, end_point, flags)
        key = (flags[0].x, flags[0].y)
        assert key not in used, "each branch keeps its own flag"
        used.add(key)
    assert len(used) == 2


def test_the_islands_are_joined_by_names_not_wires():
    """跨岛只有名字：3V3/GND 不出现在标签里，KEY*/LED* 不出现在导线里。"""
    board, spec, result = _page()
    page = result.best()
    named = [item.net for item in page.plan.labels]
    assert "3V3" not in named and "GND" not in named, named
    cross = [f"KEY{index}" for index in range(1, 5)] + ["LED1", "LED2"]
    assert not [item for item in page.plan.segments if item.net in cross]


# ------------------------------------------- 2. service 文本行与通道相遇


def test_a_service_row_that_met_a_channel_is_re_seated_without_text_on_wire():
    """① R1 的固定行压在 3V3 通道上时被重排，最终没有 text-on-wire。"""
    board, spec, result = _page()
    assert result.ok, result.render_failures()
    hard = readability.check_page(result.best(), board, spec, t._book())
    assert hard.hard_violations == [], [item.render() for item in hard.hard_violations]
    plan = _mcu(result)
    rows = [item for item in plan.texts if item.part_id == "R1"]
    channels = [
        (min(run[0][0], run[-1][0]) - dc.PIN_TEXT_WALL,
         min(run[0][1], run[-1][1]) - dc.PIN_TEXT_WALL,
         max(run[0][0], run[-1][0]) + dc.PIN_TEXT_WALL,
         max(run[0][1], run[-1][1]) + dc.PIN_TEXT_WALL)
        for run in _runs(plan, "3V3")
    ]
    for row in rows:
        for wall in channels:
            assert not dc._overlaps(tuple(row.bbox), wall), (row.text, row.bbox, wall)


def _fake_placed(*cells):
    """A placement-shaped stub: one service plan per (part, from_seat) cell."""
    plans = []
    for part_id, from_seat, to_seat, host in cells:
        cell = type("C", (), {
            "part_id": part_id, "from_seat": from_seat, "to_seat": to_seat,
            "from_net": "3V3", "host_path": host})()
        plans.append(type("P", (), {
            "group_id": f"service:{part_id}", "cells": (cell,),
            "host_paths": (host,)})())
    return type("P", (), {"service_plans": tuple(plans), "panel_plans": ()})()


def test_the_re_seat_gate_fires_on_another_seats_channel_and_not_on_its_own():
    """② 门槛只认**别的** service 支路真实 host 路径；自己的通道不触发。"""
    _board, spec, _result = _page()
    ctx = type("Ctx", (), {"presentation": spec})()
    placed = _fake_placed(
        ("R1", (-110.0, 40.0), (-150.0, 40.0), ((-80.0, 40.0), (-110.0, 40.0))),
        ("C1", (-190.0, 50.0), (-230.0, 50.0), ((-80.0, 50.0), (-190.0, 50.0))),
    )
    row = [("reference", "R1", (-173.0, 42.5, -158.0, 51.5))]
    own = [("reference", "R1", (-120.0, 35.0, -105.0, 44.0))]
    assert dc._service_rows_need_reseat(ctx, placed, "R1", row) is True, (
        "C1's 3V3 channel crosses R1's row: it must be re-seated")
    assert dc._service_rows_need_reseat(ctx, placed, "R1", own) is False, (
        "a row clear of every other channel keeps its fixed box")
    walls = dc._service_host_wall_boxes(placed, "C1")
    assert walls, "another seat's lead is R1's wall"
    assert all(wall[1] < 45.0 or wall[3] > 45.0 for wall in walls), walls
    own_channel = (-191.0, 49.0, -79.0, 51.0)
    assert own_channel not in walls, (
        "a seat's own lead is never a wall for its own rows")


def test_a_panel_cell_is_never_in_the_re_seat_set():
    """③ 实际门槛函数：panel cell（无 service 座位）永远不重排。"""
    _board, spec, _result = _page()
    ctx = type("Ctx", (), {"presentation": spec})()
    placed = _fake_placed(
        ("C1", (-190.0, 50.0), (-230.0, 50.0), ((-80.0, 50.0), (-190.0, 50.0))),
    )
    row = [("reference", "U1", (-173.0, 42.5, -158.0, 51.5))]
    assert dc._service_rows_need_reseat(ctx, placed, "U1", row) is False
    panel_ctx = type("Ctx", (), {"presentation": PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "modules": [{"id": "mcu", "parts": ["U1", "C1", "R1"],
                     "role": "host", "core": "U1"}],
        "panelGroups": [{"id": "g", "side": "left", "columns": 2, "branches": [
            {"from": "BOOT0", "to": "GND", "part": "R1"},
            {"from": "3V3", "to": "GND", "part": "C1"}]}],
    })})()
    assert dc._service_rows_need_reseat(panel_ctx, placed, "C1", row) is False, (
        "a page that states panelGroups keeps the old fixed rows")


def test_the_page_is_deterministic():
    """④ 同一文档两次编译给同一张图。"""
    board, spec, first = _page()
    _board2, _spec2, second = _page()
    assert first.ok and second.ok
    assert first.best().plan.geometry_sha256() == second.best().plan.geometry_sha256()


def _mcu_module_view(local_seats: bool):
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


def _mcu_context(local_seats: bool):
    circuit, spec = _mcu_module_view(local_seats)
    book = t._book()
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, spec, circuit)
    prepared = dc._prepare(
        circuit, spec, binding, book, dc.CompileBudget(max_candidates=4))
    assert prepared.context is not None, [f.detail for f in prepared.failures]
    return prepared.context


def test_base_and_topology_read_the_same_service_switch():
    """竖直开关：同一颗 MCU 上 base 与 topology 两个真实消费者读同一个值。"""
    for value in (False, True):
        ctx = _mcu_context(value)
        assert dc._service_layout_page(ctx.presentation) is value
        assert dc._topology_request(ctx).service_joint_order is value
        placed, failure = pb._base(ctx)
        assert failure is None, getattr(failure, "detail", failure)
        assert dc._series_placement_request(
            ctx, (), placed.poses).service_joint_order is value


# ------------------------------------------------- 3. localSeats 子开关 schema


def _one_module_payload(service_layout):
    payload = {
        "grammarRef": "ic-periphery",
        "modules": [{"id": "mcu", "parts": ["U1"], "role": "host", "core": "U1"}],
    }
    if service_layout is not None:
        payload["serviceLayout"] = service_layout
    return payload


def test_local_seats_defaults_off_and_is_not_written():
    """默认关闭：只写 pinGap 的旧文档字节/语义不变，localSeats 不落盘。"""
    spec = PresentationSpec.from_dict(_one_module_payload({"pinGap": 30}))
    assert spec.service_layout is not None
    assert spec.service_layout.local_seats is False
    assert spec.to_jsonable()["serviceLayout"] == {"pinGap": 30.0}
    restored = PresentationSpec.from_dict(spec.to_jsonable())
    assert restored.service_layout.local_seats is False
    assert restored.to_jsonable() == spec.to_jsonable()


def test_local_seats_true_roundtrips_and_opens_the_page():
    """显式 true：只写 localSeats:true，并且新路径开关读它。"""
    spec = PresentationSpec.from_dict(
        _one_module_payload({"pinGap": 30, "localSeats": True}))
    assert spec.service_layout.local_seats is True
    assert spec.to_jsonable()["serviceLayout"] == {
        "pinGap": 30.0, "localSeats": True}
    assert dc._service_layout_page(spec) is True
    assert dc._service_seats_stated(spec) is True
    old = PresentationSpec.from_dict(_one_module_payload({"pinGap": 30}))
    assert dc._service_layout_page(old) is False
    assert dc._service_seats_stated(old) is False


def test_local_seats_refuses_non_boolean_and_unknown_keys():
    """非布尔（含 0/1）与未知键都具名拒绝。"""
    from boardwise.core.presentationspec import PresentationSpecError
    for value in (0, 1, "true", None):
        with pytest.raises(PresentationSpecError):
            PresentationSpec.from_dict(
                _one_module_payload({"pinGap": 30, "localSeats": value}))
    with pytest.raises(PresentationSpecError):
        PresentationSpec.from_dict(
            _one_module_payload({"pinGap": 30, "localSeats": True, "x": 1}))


def test_a_refusal_on_a_local_seats_page_names_that_key():
    """F2：座位拒绝点名页面上真实存在的键，不点不存在的 panelGroups。"""
    ctx = _mcu_context(True)
    locked = dataclasses.replace(
        ctx,
        presentation=dataclasses.replace(
            ctx.presentation, user_locks=(pspec.UserLock(part_id="C1"),)),
    )
    placed, failure = pb._base(locked)
    assert failure is not None, placed
    assert failure.subject == "$.serviceLayout.localSeats", failure.subject
    assert "panelGroups" not in failure.subject
    # The same page with the sub-key off states no service seat at all, so the
    # spot reader answers the object it would have to be written in.
    off = _mcu_context(False)
    assert dc._service_seat_spot(off.presentation) == "$.serviceLayout"
    panels = PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "modules": [{"id": "mcu", "parts": ["U1", "C1", "R1"],
                     "role": "host", "core": "U1"}],
        "panelGroups": [{"id": "g", "side": "left", "columns": 2, "branches": [
            {"from": "BOOT0", "to": "GND", "part": "R1"},
            {"from": "3V3", "to": "GND", "part": "C1"}]}],
    })
    assert dc._service_seat_spot(panels) == "$.panelGroups"


def test_panel_groups_and_local_seats_together_are_refused():
    """F3：两种构造并存具名拒绝；panelGroups + pinGap 仍接受。"""
    from boardwise.core.presentationspec import PresentationSpecError
    payload = {
        "grammarRef": "ic-periphery",
        "modules": [{"id": "mcu", "parts": ["U1", "C1", "R1"],
                     "role": "host", "core": "U1"}],
        "panelGroups": [{"id": "g", "side": "left", "columns": 2, "branches": [
            {"from": "BOOT0", "to": "GND", "part": "R1"},
            {"from": "3V3", "to": "GND", "part": "C1"}]}],
    }
    with pytest.raises(PresentationSpecError):
        PresentationSpec.from_dict({
            **payload,
            "serviceLayout": {"pinGap": 30, "localSeats": True}})
    # The old combination (panels + the 543B interval, no sub-key) is accepted.
    old = PresentationSpec.from_dict({
        **payload, "serviceLayout": {"pinGap": 30}})
    assert old.service_layout.local_seats is False
