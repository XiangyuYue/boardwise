"""Opt-in plain cross-island carriers must be executable after compile.

Three synthetic parts, two ordinary ic-periphery modules, no serviceGroups.
The contract follows the real builder and checks its actual wire geometry;
scalar/translation checks alone cannot establish a connected drawing.
"""
from copy import deepcopy

import pytest

from boardwise.cli import _draw_plan_from_page
from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import LayoutSegment
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import pagecompiler, readability

PAGE = (0., 0., 1170., 825.)


def case(signal_names=("DATA_BUS", "CLOCKBUS")):
    def pin(n, x, y, direction):
        return {"number": str(n), "name": str(n), "tip": [x, y],
                "direction": direction, "length": 10., "pinType": "passive"}
    def symbol(ref, box, pins):
        return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
                "symbolRef": ref, "title": ref, "body": box, "pins": pins,
                "source": "synthetic offline carrier contract, not live calibrated"}
    payloads = [
        symbol("HOST8", [-40., -30., 40., 30.], [
            pin(1, -50., 25., "left"), pin(2, -50., 15., "left"),
            pin(3, -50., 5., "left"), pin(4, -50., -5., "left"),
            pin(5, 50., 25., "right"), pin(6, 50., 15., "right"),
            pin(7, 50., -15., "right"), pin(8, 50., -25., "right")]),
        symbol("HOST4", [-20., -25., 20., 25.], [
            pin(1, 30., 15., "right"), pin(2, 30., 5., "right"),
            pin(3, 30., -5., "right"), pin(4, 30., -15., "right")]),
        symbol("C", [-5.5, -8.5, 5.5, 8.5], [
            pin(1, -20., 0., "left"), pin(2, 20., 0., "right")]),
        symbol("PWR-PWR", [-6., 0., 6., 18.], []),
        symbol("PWR-GND", [-6., 0., 6., 18.], []),
    ]
    parts = [{"id": p, "symbolRef": s, "lcsc": lcsc, "value": v,
              "provenance": "verified_recipe"} for p,s,lcsc,v in (
                  ("U1", "HOST8", "C10001", "HOST8"),
                  ("U2", "HOST4", "C10002", "HOST4"),
                  ("C1", "C", "C14663", "100n"))]
    circuit = CircuitSpec.from_dict({"parts": parts, "nets": [
        {"id": n, "class": cls, "members": members, "provenance": "verified_recipe"}
        for n,cls,members in (
            ("PWR", "power", ["U1.1", "U2.3", "C1.1"]),
            ("GND", "gnd", ["U1.2", "U1.7", "U2.4", "C1.2"]),
            (signal_names[0], "signal", ["U1.4", "U2.1"]),
            (signal_names[1], "signal", ["U1.3", "U2.2"]))],
        "nc": ["U1.5", "U1.6", "U1.8"]})
    presentation = PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "left", "output": "right", "load": "right",
                            "source": "left", "power": "top", "gnd": "bottom"},
        "modules": [
            {"id": "sensor", "role": "sensor with local decoupling", "parts": ["U1", "C1"], "grammarRef": "ic-periphery", "core": "U1"},
            {"id": "interface", "role": "cross-island interface", "parts": ["U2"], "grammarRef": "ic-periphery", "core": "U2"}],
        "moduleOrder": ["sensor", "interface"], "moduleColumns": 2,
        "labelPolicy": {"local": "wire", "crossModule": "label", "highFanout": "label",
                        "stub": "straight", "stubMin": 40., "rowModel": "centered"}})
    return circuit, presentation, {p["symbolRef"]: SymbolProfile.from_dict(p) for p in payloads}


@pytest.fixture(scope="module", params=[
    (40., ("DATA_BUS", "CLOCKBUS")),
    (60., ("PAYLOAD1", "TIMING01")),
])
def compiled(request):
    floor, names = request.param
    circuit, spec, book = case(names)
    payload = spec.to_jsonable()
    payload["labelPolicy"]["stubLaneReserve"] = True
    payload["labelPolicy"]["stubMin"] = floor
    spec = PresentationSpec.from_dict(payload)
    result = pagecompiler.compile_page(
        circuit, spec, book, pagecompiler.PageCompileBudget(page_box=PAGE),
    )
    assert result.ok, result.render_failures()
    assert result.pages, "the compiler produced no actual page"
    return circuit, spec, book, result, result.pages[0]


def test_plain_carrier_policy_and_module_translation_survive(compiled):
    circuit, spec, book, result, page = compiled
    assert len(circuit.parts) == 3 and len(page.modules) == 2
    assert spec.label_policy.stub_lane_reserve
    assert not spec.service_groups
    assert page.verdict == "pass"
    assert page.plan.evidence.hard_violations == []
    assert page.page_evidence.hard_violations == []
    signals = {net.id for net in circuit.nets if net.cls == "signal"}
    labels = [item for item in page.plan.labels if item.net in signals]
    assert len(labels) == 4
    for label in labels:
        module = next(module for module in page.modules if label.part_id in module.parts)
        dx, dy = module.origin
        matches = [
            source for candidate in result.modules[module.id].candidates
            for source in candidate.labels
            if source.net == label.net and source.part_id == label.part_id
            and (source.x + dx, source.y + dy) == (label.x, label.y)
            and tuple(value + delta for value, delta in zip(source.bbox, (dx, dy, dx, dy)))
                == label.bbox
        ]
        assert matches, "a page label is not a translated module answer"
        assert (label.stub, label.stub_min, label.row_model) == (
            "straight", spec.label_policy.stub_min, "centered")
        assert any((source.stub, source.stub_min, source.row_model)
                   == (label.stub, label.stub_min, label.row_model) for source in matches)
    derived = readability.derive_netlist(page.plan, book)
    for net in circuit.nets:
        for member in net.members:
            assert derived.pin_group[member] == tuple(sorted(net.members))


def test_reserved_plain_cross_island_carriers_are_executable(compiled):
    circuit, spec, book, _result, page = compiled
    plan = _draw_plan_from_page(page, circuit, spec, book, keep_names=True)
    # These checks deliberately follow the real plan builder. Retaining policy
    # fields alone cannot satisfy the actual conductor/partition requirement.
    final = deepcopy(page.plan)
    final.segments = [LayoutSegment(net=wire.net, points=list(wire.points))
                      for wire in plan.change.draw_wires]
    signals = {net.id for net in circuit.nets if net.cls == "signal"}
    carriers = [wire for wire in plan.change.draw_wires if wire.net in signals]
    assert len(carriers) == 4
    compiled_carriers = [wire for wire in page.plan.segments if wire.net in signals]
    assert len(compiled_carriers) == 4
    assert sorted((wire.net, tuple(wire.points)) for wire in compiled_carriers) == sorted(
        (wire.net, tuple(wire.points)) for wire in carriers
    ), "the builder must consume the compiler's actual reserved carriers"
    for wire in carriers:
        assert len(wire.points) == 2, "straight policy must draw one straight carrier"
        start, stop = wire.points
        assert start[0] == stop[0] or start[1] == stop[1]
        assert abs(start[0] - stop[0]) + abs(start[1] - stop[1]) >= spec.label_policy.stub_min
    rows = readability._named_wire_rows(final)
    assert len(rows) == 4 and {row[3] for row in rows} == signals
    rails = {net.id for net in circuit.nets if net.cls != "signal"}
    assert not any(label.net in rails for label in final.labels)
    assert {symbol.net for symbol in final.power_symbols} == rails
    derived = readability.derive_netlist(final, book)
    for net in circuit.nets:
        for member in net.members:
            assert derived.pin_group[member] == tuple(sorted(net.members))
            if net.cls == "signal":
                x, y = derived.pin_points[member]
                assert any(
                    wire.net == net.id and any(
                        abs((b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])) < 1e-6
                        and min(a[0], b[0]) - 1e-6 <= x <= max(a[0], b[0]) + 1e-6
                        and min(a[1], b[1]) - 1e-6 <= y <= max(a[1], b[1]) + 1e-6
                        for a, b in zip(wire.points, wire.points[1:]))
                    for wire in plan.change.draw_wires
                ), f"{member} has a name but no actual carrier wire"
    # Run the existing production geometric rules on the wires the plan will
    # actually draw. No relaxed checker or altered candidate is used to get here.
    checked = readability.check(final, circuit, spec, book, page_box=PAGE)
    assert not checked.hard_violations, [item.render() for item in checked.hard_violations]


def test_plain_carrier_default_off_geometry_is_unchanged():
    circuit, spec, book = case()
    result = pagecompiler.compile_page(
        circuit, spec, book, pagecompiler.PageCompileBudget(page_box=PAGE),
    )
    assert result.ok, result.render_failures()
    assert [page.page_geometry_sha256() for page in result.pages] == [
        "87ed5f493683ae410a8fd6503f337ae46de3bf8b9c3ee55f606cb0b79111a0a6",
        "33ec83820bc62612d443689283e9d5a88e929387f29feec85fb570203f4c879c",
        "3dfd252b1aba079c64c0a77485141b29f52d853c0b2510ef02b084ad05e38198",
        "76e6d8556168565260d2f95a31d212f85be32c161a7ee57f55fcab3a5cfe85c4",
    ]
