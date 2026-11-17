"""548P16: joint seats consume the existing native-label finishing passes."""

from __future__ import annotations

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawapply, drawcompiler as dc, readability
from test_548n_group_seat import _prepared
from test_548p6_service_feedback import _fixture as base_fixture


def _fixture(*, native=True, ghost=False, riding_contract=False):
    circuit, spec, book, _ctx = base_fixture(trapped_ground=False)
    host = book["HOST4"].to_jsonable()
    for number, pin in enumerate(host["pins"], 1):
        pin["number"] = str(number)
    host["pins"].append({
        "number": "6", "name": "RX", "tip": [-50.0, -25.0],
        "direction": "left", "length": 10.0, "pinType": "passive",
    })
    book["HOST4"] = SymbolProfile.from_dict(host)
    payload = circuit.to_jsonable()
    payload["nets"].append({
        "id": "SERIAL_RX" if ghost else "RX", "class": "signal",
        "members": ["U1.RX"], "provenance": "verified_recipe",
    })
    circuit = CircuitSpec.from_dict(payload)
    document = spec.to_jsonable()
    document["portRoles"] = {"TX": "output", payload["nets"][-1]["id"]: "input"}
    document["sidePreferences"]["input"] = "left"
    if riding_contract:
        document["serviceLayout"] = {"pinGap": 30.0}
        document["localLabelObligations"] = [{
            "nets": ["RX"], "note": "the left receive boundary keeps its visible name",
        }]
    if native:
        document["textPlacement"] = "native-attr"
    spec = PresentationSpec.from_dict(document)
    ctx = _prepared(circuit, spec, book)
    return circuit, spec, book, ctx


def _build(case):
    ctx = case[-1]
    return dc._build_candidate(ctx, dc._variants(ctx)[0])


def _assert_connected(circuit, book, plan):
    derived = readability.derive_netlist(plan, book)
    for net in circuit.nets:
        expected = set()
        for member in net.members:
            part, _, token = member.partition(".")
            profile = book[circuit.part(part).symbol_ref]
            expected.add(f"{part}.{dc._pin_of_token(profile, token).number}")
        for member in expected:
            assert set(derived.group_of(member)) == expected
    assert set(derived.pin_points) == set(derived.wired_pins)
    assert sum(flag.net == "PWR" for flag in plan.power_symbols) == 1
    assert sum(flag.net == "GND" for flag in plan.power_symbols) == 1


def test_native_service_labels_use_the_reserved_boxes_and_real_attr_moves():
    case = _fixture()
    circuit, spec, book, _ctx = case
    built, failure, violations = _build(case)
    assert built is not None, (failure, violations)
    plan = built.plan
    assert {label.net for label in plan.labels} == {"TX", "RX"}
    assert all(label.text_mode == "native" for label in plan.labels)
    rows = {net: box for _owner, box, _part, net in readability._named_wire_rows(plan)}
    assert rows == {label.net: label.bbox for label in plan.labels}
    _assert_connected(circuit, book, plan)
    change = drawapply.module_plan(
        plan, circuit, spec, book,
        lcsc_by_part={part.id: "C1" for part in circuit.parts}, keep_names=True,
    ).change
    moves = [move for move in change.attribute_moves if move.role == "net"]
    assert len(moves) == 2
    for label in plan.labels:
        matching = [move for move in moves
                    if change.draw_wires[move.wire_index].net == label.net]
        assert len(matching) == 1
        move = matching[0]
        assert move.owner_kind == "wire"
        assert move.value_visible is not False
        assert (move.x, move.y) == pytest.approx((
            (label.bbox[0] + label.bbox[2]) / 2.0,
            (label.bbox[1] + label.bbox[3]) / 2.0,
        ))


def test_native_service_does_not_measure_a_midpoint_name_across_its_host():
    case = _fixture(ghost=True)
    circuit, _spec, book, _ctx = case
    built, failure, violations = _build(case)
    assert built is not None, (failure, violations)
    assert not built.checked.hard_violations
    label = next(label for label in built.plan.labels if label.net == "SERIAL_RX")
    row = next(box for _owner, box, _part, net
               in readability._named_wire_rows(built.plan) if net == "SERIAL_RX")
    assert label.text_mode == "native"
    assert row == label.bbox
    # 因果压力不在这一页上（实测）：本页 open port 的清跑地板把载体锁在 60 单位，
    # 中点 220，名字行 220..259.33 与本体 x0=260 差 0.67 不相交；改名会同步把跑长
    # 抬一档，差值反而更负。所以「中点命名会横穿本体」由
    # `test_a_midpoint_name_would_cross_the_host_and_the_cover_seats_it` 用真实
    # body + 更短载体证明，这一页保留它自己的结论：
    host = next(part for part in built.plan.parts if part.part_id == "U1")
    body = dc._body_box(book[host.symbol_ref], dc.SymbolPose(host.rotation, host.mirror),
                        (host.x, host.y))
    assert not dc._overlaps(row, body)
    _assert_connected(circuit, book, built.plan)


def test_a_riding_service_label_is_refused_by_its_own_named_gate(monkeypatch):
    original = dc._reserve_open_ports

    def riding_port(ctx, placed):
        ports = original(ctx, placed)
        assert not isinstance(ports, dc.GrammarFailure), ports
        for port in ports:
            if port.net == "RX":
                label = port.label
                half_width = (label.bbox[2] - label.bbox[0]) / 2.0
                label.bbox = (label.x - half_width, label.y - 4.5,
                              label.x + half_width, label.y + 4.5)
        return ports

    # The unmodified peer must build using the same real router and hard gate.
    good, failure, violations = _build(_fixture(riding_contract=True))
    assert good is not None, (failure, violations)
    monkeypatch.setattr(dc, "_reserve_open_ports", riding_port)
    built, failure, _violations = _build(_fixture(riding_contract=True))
    assert built is None
    assert failure is not None and failure.category == "presentation-poor"
    assert failure.subject == "RX"
    assert "own carrier end" in failure.detail
    assert "on its own carrier" in failure.detail


def test_unstated_native_keeps_default_modes_and_never_calls_native_finishing(monkeypatch):
    case = _fixture(native=False)
    baseline, failure, violations = _build(case)
    assert baseline is not None, (failure, violations)
    expected = baseline.plan.to_jsonable()

    def forbidden(*_args, **_kwargs):
        pytest.fail("a non-native service page reached native finishing")

    for name in ("_native_label_dedupe", "_native_label_visibility", "_riding_label_failure"):
        monkeypatch.setattr(dc, name, forbidden)
    rebuilt, failure, violations = _build(_fixture(native=False))
    assert rebuilt is not None, (failure, violations)
    assert rebuilt.plan.to_jsonable() == expected
    assert all(not label.text_mode for label in rebuilt.plan.labels)
    _assert_connected(case[0], case[2], rebuilt.plan)


# ------------------- 中点命名的因果压力：真实 body + 短载体（434 sec.1 的实测规则）
#
# `core/textmetrics.py:433` 的实测规则是「锚在最长直跑的中点、起点锚定向右」，
# 短跑上的名字会溢出远端。本页的 port 清跑地板把载体锁在 60 单位，中点 220 与
# 本体 x0=260 只差 0.67，压力失效；这里用**同一个** U1 本体（取自真实编译结果）
# 配一条更短的横段，让中点命名真的压进本体，再跑真实的 `_native_carrier_cover`。


class _Wire:
    def __init__(self, net, points, from_pin=""):
        self.net = net
        self.points = [(float(x), float(y)) for x, y in points]
        self.from_pin = from_pin


def test_a_midpoint_name_would_cross_the_host_and_the_cover_seats_it():
    case = _fixture(ghost=True)
    built, failure, violations = _build(case)
    assert built is not None, (failure, violations)
    plan = built.plan
    host = next(part for part in plan.parts if part.part_id == "U1")
    book = case[2]
    body = dc._body_box(book[host.symbol_ref],
                        dc.SymbolPose(host.rotation, host.mirror), (host.x, host.y))

    # 一条比本页载体更短、贴着本体的真实横段：不放大任何长度。
    run = [(body[0] - 2.0, 375.0), (body[0] - 56.0, 375.0)]
    wire = _Wire("SERIAL_RX", run)
    ghost = readability.wire_name_box(wire.points, wire.net)
    assert ghost is not None and dc._overlaps(ghost, body), (ghost, body)

    label = dc.LayoutLabel(
        net="SERIAL_RX", text="SERIAL_RX", bbox=tuple(ghost),
        x=ghost[0], y=ghost[1], text_mode=dc.TEXT_MODE_NATIVE,
    )
    # 未修复时这是机器拒因：行不在它自己的载体上。
    before = drawapply.native_carrier_problems([label], [wire], (0.0, 0.0, 1170.0, 825.0))
    assert before and "is not on the x" in before[0], before

    built_cover = drawapply._Built()
    built_cover.wires.extend([wire])
    problems = drawapply._native_carrier_cover(
        built_cover, dc.LayoutPlan(labels=[label]), {}, {}, [],
        (0.0, 0.0, 1170.0, 825.0),
    )
    assert problems == []
    assert wire.points == [(float(x), float(y)) for x, y in run], wire.points
    row = built_cover.native_carrier_rows[id(label)]
    span = sorted(point[0] for point in wire.points)
    assert span[0] - 1e-9 <= row[0] and row[2] <= span[-1] + 1e-9, (row, span)
    assert not dc._overlaps(row, body), (row, body)
    assert drawapply.native_carrier_problems(
        [label], [wire], (0.0, 0.0, 1170.0, 825.0), built_cover.native_carrier_rows,
    ) == []
