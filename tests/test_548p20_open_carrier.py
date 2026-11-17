"""548P20: native open carriers collapse grid vertices, preserving their route."""

from __future__ import annotations

import math

import pytest

from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler as dc
from test_548n_group_seat import _prepared
from test_548p16_native_service import _assert_connected, _fixture as native_fixture


def _fixture(*, native=True, service=True):
    circuit, spec, book, _ctx = native_fixture(native=native)
    document = spec.to_jsonable()
    if service:
        document["serviceLayout"] = {"pinGap": 30.0}
    document["localLabelObligations"] = [{
        "nets": ["TX", "RX"],
        "note": "both UART boundaries retain their own visible outward names",
    }]
    spec = PresentationSpec.from_dict(document)
    return circuit, spec, book, _prepared(circuit, spec, book)


def _length(points):
    return sum(math.dist(start, stop) for start, stop in zip(points, points[1:]))


def _draw_plan():
    circuit, spec, book, ctx = _fixture()
    built, failure, violations = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, (failure, violations)
    change = drawapply.module_plan(
        built.plan, circuit, spec, book,
        lcsc_by_part={part.id: "C1" for part in circuit.parts}, keep_names=True,
    )
    return circuit, spec, book, ctx, built.plan, change


def test_complete_native_service_plan_keeps_each_name_on_its_original_carrier():
    circuit, spec, book, _ctx, layout, planned = _draw_plan()
    assert spec.text_placement == "native-attr"
    assert spec.service_layout is not None
    assert dc.local_label_nets(spec) == {"TX", "RX"}
    assert {label.net for label in layout.labels} == {"TX", "RX"}
    assert all(label.text_mode == "native" for label in layout.labels)
    _assert_connected(circuit, book, layout)

    moves = [move for move in planned.change.attribute_moves if move.role == "net"]
    assert len(moves) == 2
    rows = {}
    for label in layout.labels:
        before = next(run for run in layout.segments if run.net == label.net)
        assert len(before.points) == 2, "collinear grid vertices are not carrier ends"
        assert _length(before.points) == pytest.approx(40.0)
        assert before.points[-1] == (label.x, label.y)
        own_moves = [move for move in moves
                     if planned.change.draw_wires[move.wire_index].net == label.net]
        assert len(own_moves) == 1
        move = own_moves[0]
        assert move.value_visible is not False
        carrier = planned.change.draw_wires[move.wire_index]
        # Seating the name must reuse the existing reach, never grow the wire.
        assert carrier.points == before.points
        assert _length(carrier.points) == pytest.approx(40.0)
        row = dc.font_text_box(label.text, x=move.x, y=move.y)
        xs = [point[0] for point in carrier.points]
        assert min(xs) <= row[0] <= row[2] <= max(xs)
        rows[id(label)] = row
    assert drawapply.native_carrier_problems(
        layout.labels, planned.change.draw_wires, None, rows,
    ) == []


def _routed(monkeypatch, ctx, boxes=()):
    captured = []
    original = dc._Router.route

    def measured(router, *args, **kwargs):
        route = original(router, *args, **kwargs)
        captured.append(route)
        return route

    monkeypatch.setattr(dc._Router, "route", measured)
    run = dc._joint_open_far(ctx, (100.0, 100.0), (1.0, 0.0), 40.0, boxes, [])
    assert len(captured) == 1 and captured[0] is not None
    assert run is not None
    raw = [tuple(point) for point in captured[0]]
    return raw, run


def test_compression_preserves_the_real_routers_required_bend(monkeypatch):
    ctx = _fixture()[-1]
    # Block all four straight exits while leaving diagonal quadrants open.
    # The router may choose any legal quadrant, but every 40-unit path bends.
    walls = [(115.0, 95.0, 135.0, 105.0), (65.0, 95.0, 85.0, 105.0),
             (95.0, 115.0, 105.0, 135.0), (95.0, 65.0, 105.0, 85.0)]
    raw, compressed = _routed(monkeypatch, ctx, walls)
    assert raw[0][0] != raw[-1][0] and raw[0][1] != raw[-1][1]
    assert compressed[0] == raw[0] and compressed[-1] == raw[-1]
    for start, stop in zip(compressed, compressed[1:]):
        assert start[0] == stop[0] or start[1] == stop[1], "a bend became a diagonal"
        assert all(not dc._segment_hits_box(start, stop, wall) for wall in walls)
    assert _length(raw) == pytest.approx(40.0)
    assert _length(compressed) == pytest.approx(_length(raw))
    assert len(raw) > len(compressed) >= 3


@pytest.mark.parametrize("native,service", [(False, True), (True, False)])
def test_missing_either_opt_in_keeps_the_router_point_sequence(monkeypatch, native, service):
    ctx = _fixture(native=native, service=service)[-1]
    raw, unchanged = _routed(monkeypatch, ctx)
    assert len(raw) > 2
    assert unchanged == raw
    assert _length(unchanged) == pytest.approx(40.0)
