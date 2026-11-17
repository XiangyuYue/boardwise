"""548P40: long joint-port names fit their reserved native carrier.

Synthetic numeric-pin symbols exercise the original service builder and apply
planner. They are regression fixtures, not measured EasyEDA symbol profiles.
"""

from __future__ import annotations

from functools import partial

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import LayoutPlan
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler as dc, readability
from test_548n_group_seat import _prepared
from test_548p16_native_service import _assert_connected, _fixture as native_fixture


def _case(*, native=True, long_names=True, groups=True, obligations=False):
    circuit, original, book, _ctx = native_fixture(native=native)
    names = {"TX": "ESP_TXD", "RX": "ESP_RXD"} if long_names else {}
    payload = circuit.to_jsonable()
    for net in payload["nets"]:
        net["id"] = names.get(net["id"], net["id"])
    circuit = CircuitSpec.from_dict(payload)
    document = original.to_jsonable()
    document["serviceLayout"] = {"pinGap": 30.0}
    document["portRoles"] = {
        names.get(net, net): role for net, role in document["portRoles"].items()
    }
    if obligations:
        document["localLabelObligations"] = [{
            "nets": [names.get("TX", "TX"), names.get("RX", "RX")],
            "note": "UART boundaries keep the original electrical names",
        }]
    if not groups:
        document.pop("serviceGroups", None)
    spec = PresentationSpec.from_dict(document)
    return circuit, spec, book, _prepared(circuit, spec, book)


def _build(case, tmp_path):
    circuit, spec, book, ctx = case
    built, failure, violations = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, (failure, violations)
    assert not built.checked.hard_violations
    path = tmp_path / "native-port-layout.json"
    built.plan.dump(path)
    layout = LayoutPlan.load(path)
    assert layout.to_jsonable() == built.plan.to_jsonable()
    planned = drawapply.module_plan(
        layout, circuit, spec, book, keep_names=True, page_box=ctx.budget.page_box,
        lcsc_by_part={part.id: "C1" for part in circuit.parts},
    )
    return layout, planned


@pytest.mark.parametrize("obligations", [False, True])
def test_long_names_complete_builder_roundtrip_and_plan_share_covered_carriers(tmp_path, obligations):
    case = _case(obligations=obligations)
    circuit, spec, book, ctx = case
    layout, planned = _build(case, tmp_path)
    assert {label.net for label in layout.labels} == {"ESP_TXD", "ESP_RXD"}
    assert all(label.text == label.net for label in layout.labels)
    assert all(dc.text_width(label.text) > spec.label_policy.stub_min for label in layout.labels)
    # The compiler reserves the original outward box. The existing apply pass
    # seats the printed ATTR row inside that already long-enough conductor.
    rows = {}
    for label in layout.labels:
        before = next(wire for wire in layout.segments if wire.net == label.net)
        after = next(wire for wire in planned.change.draw_wires if wire.net == label.net)
        assert before.points[-1] == (label.x, label.y), "the far endpoint keeps its electrical name"
        assert label.stub_min == spec.label_policy.stub_min, "the stated minimum is preserved"
        assert sum(abs(b[0] - a[0]) + abs(b[1] - a[1])
                   for a, b in zip(before.points, before.points[1:])) >= dc.text_width(label.text)
        assert after.points == before.points, "apply must consume the reserved carrier unchanged"
        move = next(move for move in planned.change.attribute_moves
                    if move.role == "net" and planned.change.draw_wires[move.wire_index].net == label.net)
        assert move.value_visible is not False
        rows[id(label)] = dc.font_text_box(label.text, x=move.x, y=move.y)
        assert rows[id(label)] != label.bbox, "the reservation and final printed row are different stages"
    assert drawapply.native_carrier_problems(
        layout.labels, planned.change.draw_wires, ctx.budget.page_box, rows,
    ) == []
    checked = readability.check(
        layout, circuit, spec, book, grammar_checker=partial(dc.check_grammar, budget=ctx.budget),
        page_box=ctx.budget.page_box, keepouts=ctx.budget.keepouts, grid=ctx.budget.grid,
    )
    assert not checked.hard_violations and not checked.grammar_findings
    _assert_connected(circuit, book, layout)
    derived = readability.derive_netlist(layout, book)
    assert len(derived.pin_points) == len(derived.wired_pins) == 10


def test_short_native_names_keep_the_existing_forty_unit_plan(tmp_path):
    case = _case(long_names=False)
    layout, planned = _build(case, tmp_path)
    assert {label.text for label in layout.labels} == {"TX", "RX"}
    for label in layout.labels:
        wire = next(wire for wire in layout.segments if wire.net == label.net)
        assert wire.points[-1] == (label.x, label.y)
        assert sum(abs(b[0] - a[0]) + abs(b[1] - a[1])
                   for a, b in zip(wire.points, wire.points[1:])) == 40.0
        assert next(wire2 for wire2 in planned.change.draw_wires if wire2.net == label.net).points == wire.points
    _assert_connected(case[0], case[2], layout)


def test_non_native_long_names_reserve_for_the_host_name_row():
    _circuit, _spec, _book, ctx = _case(native=False)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0], seat_service_groups=False)
    assert placed is not None, failure
    ports = dc._reserve_open_ports(ctx, placed)
    assert not isinstance(ports, dc.GrammarFailure), ports
    assert {port.net for port in ports} == {"ESP_TXD", "ESP_RXD"}
    lengths = {}
    for port in ports:
        assert port.run[-1] == (port.label.x, port.label.y)
        length = sum(abs(b[0] - a[0]) + abs(b[1] - a[1])
                     for a, b in zip(port.run, port.run[1:]))
        lengths[port.net] = length
        row = dc.textmetrics.wire_name_box(
            [list(point) for point in port.run], port.net)
        body = dc._body_box(
            ctx.profile(port.part_id), placed.poses[port.part_id],
            placed.origins[port.part_id])
        assert row is not None and body is not None
        assert not dc._overlaps(row, body), (port.net, row, body)
    # The old assertion required 40 for both, although ESP_RXD's host-printed
    # row then landed on U1. TXD's 40 was already clear and must not move;
    # RXD takes only the next existing grid rung that clears the same body.
    assert lengths == {"ESP_TXD": 40.0, "ESP_RXD": 50.0}


def test_no_service_group_keeps_the_original_placement_path(monkeypatch):
    _circuit, _spec, _book, ctx = _case(groups=False)

    def forbidden(*_args, **_kwargs):
        pytest.fail("a page without serviceGroups reserved joint ports")

    monkeypatch.setattr(dc, "_reserve_open_ports", forbidden)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    assert placed is not None, failure
    assert not placed.service_group_plans
    assert not placed.service_group_ports
