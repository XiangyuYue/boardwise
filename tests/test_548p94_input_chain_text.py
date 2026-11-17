"""P94: reuse the original S20 rows only for explicitly wired input chains.

Synthetic profiles deliberately have no native text anchors. The complete
builder and ATTR consumer are exercised; body bounds are measured independently.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.geometry import transform_point
from boardwise.core.layoutplan import LayoutPlan
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawapply, drawcompiler as dc, readability


PARTS = ("AX71", "BX82", "CX93", "DX64")


def _case():
    parts = [{"id": name, "symbolRef": "TWO", "value": "7q",
              "provenance": "verified_recipe"} for name in PARTS]
    nets = [
        {"id": "FEED_A", "class": "signal", "members": ["AX71.1"]},
        {"id": "MID_A", "class": "signal", "members": ["AX71.2", "BX82.1"]},
        {"id": "FEED_B", "class": "signal", "members": ["CX93.1"]},
        {"id": "MID_B", "class": "signal", "members": ["CX93.2", "DX64.1"]},
        {"id": "GND", "class": "gnd", "members": ["BX82.2", "DX64.2"]},
    ]
    for net in nets:
        net["provenance"] = "verified_recipe"
    circuit = CircuitSpec.from_dict({"parts": parts, "nets": nets})
    spec = PresentationSpec.from_dict({
        "grammarRef": "voltage-divider",
        "modules": [{"id": "channels", "parts": list(PARTS), "role": "paired indicators"}],
        "portRoles": {"FEED_A": "input", "FEED_B": "input"},
        "serviceLayout": {"pinGap": 30}, "textPlacement": "native-attr",
        "directWiringObligations": [{"nets": ["MID_A", "MID_B"],
                                      "note": "private series joints"}],
        "labelPolicy": {"stub": "straight", "stubMin": 40},
        "sidePreferences": {"power": "top", "input": "left", "gnd": "right"},
    })
    profile = {"symbolRef": "TWO", "body": [-10, -5, 10, 5], "pins": [
        {"number": "1", "name": "1", "tip": [-20, 0], "direction": "left", "length": 10},
        {"number": "2", "name": "2", "tip": [20, 0], "direction": "right", "length": 10},
    ], "source": "P94 synthetic geometry, not a live library measurement"}
    book = {"TWO": SymbolProfile.from_dict(profile),
            "PWR-GND": SymbolProfile.from_dict({"symbolRef": "PWR-GND",
                                                 "body": [-6, 0, 6, 12], "pins": []})}
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, binding.failures
    prepared = dc._prepare(circuit, spec, binding, book, dc.CompileBudget(page_box=None))
    assert prepared.context is not None, prepared.failures
    return prepared.context


def _placed(ctx):
    placed, failure = dc._place(ctx, dc._topology_variant())
    assert placed is not None, failure
    return placed


def _body(profile, rotation, mirror, origin):
    x1, y1, x2, y2 = profile.body
    points = [transform_point(x, y, rotation=rotation, mirror=mirror,
                              ox=origin[0], oy=origin[1])
              for x, y in ((x1, y1), (x1, y2), (x2, y1), (x2, y2))]
    return (min(x for x, _ in points), min(y for _, y in points),
            max(x for x, _ in points), max(y for _, y in points))


def _placed_body(ctx, placed, name):
    pose = placed.poses[name]
    return _body(ctx.profile(name), pose.rotation, pose.mirror, placed.origins[name])


def _rows(texts, name):
    return {row.kind: row for row in texts if row.part_id == name}


def _assert_s20(rows, body):
    assert set(rows) == {"reference", "value"}
    assert rows["reference"].bbox[1] >= body[3], "reference must be above drawn body"
    assert rows["value"].bbox[3] <= body[1], "value must be below drawn body"
    assert all(row.bbox[0] == pytest.approx(body[0]) for row in rows.values())
    assert all(row.rotation == 0 for row in rows.values())


def _tuple(texts):
    return [(r.part_id, r.kind, r.text, r.bbox, r.x, r.y, r.rotation) for r in texts]


def test_complete_input_chain_build_round_trip_partition_and_actual_attr(tmp_path):
    ctx = _case()
    built, failure, violations = dc._build_candidate(ctx, dc._topology_variant())
    assert built is not None, (failure, violations)
    assert not built.checked.hard_violations
    assert not dc.check_grammar(built.plan, ctx.circuit, ctx.presentation, ctx.book)
    path = tmp_path / "synthetic-chain.json"
    built.plan.dump(path)
    loaded = LayoutPlan.load(path)
    assert loaded.to_jsonable() == built.plan.to_jsonable()
    derived = readability.derive_netlist(loaded, ctx.book)
    assert len(derived.pin_points) == len(derived.wired_pins) == 8
    assert len(ctx.circuit.nets) == 5
    for net in ctx.circuit.nets:
        for member in net.members:
            assert set(derived.group_of(member)) == set(net.members)
    change = drawapply.module_plan(loaded, ctx.circuit, ctx.presentation, ctx.book,
                                  keep_names=True,
                                  lcsc_by_part={p: "C1" for p in PARTS}).change
    standoffs = []
    for name in PARTS:
        part = loaded.part(name)
        body = _body(ctx.profile(name), part.rotation, part.mirror, (part.x, part.y))
        rows = _rows(loaded.texts, name)
        _assert_s20(rows, body)
        standoffs.append((rows["reference"].bbox[1] - body[3],
                          body[1] - rows["value"].bbox[3]))
        moves = {m.role: m for m in change.attribute_moves
                 if m.owner_kind == "part" and m.spec_id == name}
        assert set(moves) == {"reference", "value"}
        for role, move in moves.items():
            assert (move.x, move.y) == pytest.approx(rows[role].bbox[:2])
            # The existing v1 consumer requests position only. This assertion
            # does not establish the live host's current ATTR rotation.
            assert move.rotation is None
            assert move.value_visible is not False
    assert len(set(standoffs)) == 1, f"same profiles need equal text standoff: {standoffs}"
    assert all(part.value_visible for part in change.draw_parts)
    print("P94 synthetic standoffs:", standoffs)


def test_input_rows_retreat_on_same_sides_from_first_rung_wall():
    ctx = _case()
    placed = _placed(ctx)
    body = _placed_body(ctx, placed, "AX71")
    wall = (body[0], body[3] + 9, body[0] + 25, body[3] + 13)
    texts, failure = dc._part_texts(ctx, placed, [], [wall])
    assert failure is None, failure
    rows = _rows(texts, "AX71")
    _assert_s20(rows, body)
    assert rows["reference"].bbox[1] > wall[3], "first rung must yield to wall"
    assert all(not dc._overlaps(row.bbox, wall) for row in rows.values())


def test_input_rows_refuse_by_name_when_every_above_rung_is_blocked():
    ctx = _case()
    placed = _placed(ctx)
    body = _placed_body(ctx, placed, "AX71")
    wall = (body[0] - 1, body[3], body[0] + 100,
            body[3] + dc.TEXT_GAP * dc.TEXT_ESCALATION_STEPS + 40)
    _texts, failure = dc._part_texts(ctx, placed, [], [wall])
    assert failure is not None, "S20 must refuse rather than move both rows beside body"
    assert failure.category == "layout-unsat"
    assert "AX71" in failure.subject + failure.detail
    assert "part" in failure.detail


def _control(ctx, placed, name):
    spec = ctx.presentation.to_jsonable()
    if name == "native":
        spec.pop("textPlacement")
    elif name == "service":
        spec.pop("serviceLayout")
    elif name == "no-direct":
        spec.pop("directWiringObligations")
    elif name == "power":
        payload = ctx.circuit.to_jsonable()
        for net in payload["nets"]:
            if net["id"].startswith("FEED"):
                net["class"] = "power"
        ctx.circuit = CircuitSpec.from_dict(payload)
    elif name in ("source", "no-input", "conflict"):
        spec["portRoles"] = {} if name == "no-input" else {
            "FEED_A": "source" if name == "source" else "input",
            "FEED_B": "source" if name == "source" else "input"}
        if name == "conflict":
            payload = ctx.circuit.to_jsonable()
            payload["openInterfaces"] = [{"net": net, "direction": "output", "role": "conflict",
                                          "provenance": "verified_recipe"}
                                          for net in ("FEED_A", "FEED_B")]
            ctx.circuit = CircuitSpec.from_dict(payload)
    elif name == "three-pin":
        payload = ctx.book["TWO"].to_jsonable()
        payload["pins"].append({"number": "3", "name": "NC", "tip": [0, 15],
                                "direction": "up", "length": 10})
        ctx.book["TWO"] = SymbolProfile.from_dict(payload)
    elif name in ("three-arm", "wrong-role", "unbound"):
        if name == "three-arm":
            ctx.binding = replace(ctx.binding, obligations=tuple(
                replace(o, nets=(*o.nets[:-1], "EX55TRA", o.nets[-1]))
                if o.kind == dc.DIRECT_WIRE else o for o in ctx.binding.obligations))
        elif name == "wrong-role":
            for part in PARTS:
                ctx.slots[part] = replace(ctx.slots[part], role="shunt")
        else:
            ctx.binding = replace(ctx.binding, bindings=tuple(
                b for b in ctx.binding.bindings if b.role != "in"))
    elif name == "ambiguous":
        payload = ctx.circuit.to_jsonable()
        payload["parts"].append({"id": "EX55", "symbolRef": "TWO", "value": "7q",
                                 "provenance": "verified_recipe"})
        for net in payload["nets"]:
            if "AX71.1" in net["members"]:
                net["members"].append("EX55.1")
            if "AX71.2" in net["members"]:
                net["members"].append("EX55.2")
        ctx.circuit = CircuitSpec.from_dict(payload)
        ctx.slots["EX55"] = replace(ctx.slots["AX71"], part_id="EX55")
        placed.origins["EX55"] = (placed.origins["AX71"][0] - 200, placed.origins["AX71"][1])
        placed.poses["EX55"] = placed.poses["AX71"]
        # Only the ambiguous chain is controlled; the other is still eligible.
        spec["directWiringObligations"][0]["nets"] = ["MID_A"]
    elif name.startswith("explicit-"):
        spec["partTexts"] = {part: name.removeprefix("explicit-") for part in PARTS}
    elif name == "measured":
        payload = ctx.book["TWO"].to_jsonable()
        payload["texts"] = [{"kind": "reference", "x": -8, "y": 32},
                            {"kind": "value", "x": -8, "y": 22}]
        ctx.book["TWO"] = SymbolProfile.from_dict(payload)
    elif name in ("series", "single-series"):
        spec["seriesBranches"] = [
            {"id": "first", "from": "FEED_A", "to": "GND", "middleNet": "MID_A",
             "parts": ["AX71", "BX82"]}]
        if name != "single-series":
            spec["seriesBranches"].append(
                {"id": "second", "from": "FEED_B", "to": "GND", "middleNet": "MID_B",
                 "parts": ["CX93", "DX64"]})
        else:
            spec["directWiringObligations"][0]["nets"] = ["MID_A"]
    ctx.presentation = PresentationSpec.from_dict(spec)
    return ctx, placed


@pytest.mark.parametrize("name", [
    "native", "service", "no-direct", "power", "source", "no-input", "conflict",
    "three-pin", "three-arm", "wrong-role", "unbound", "ambiguous",
    "explicit-right", "explicit-above", "explicit-below", "measured",
    "series", "single-series", "panel",
])
def test_noneligible_and_higher_precedence_keep_complete_existing_rows(monkeypatch, name):
    if name == "panel":
        from test_548d_panel_base import _base, _context, _panel_payload
        ctx = _context([_panel_payload()])
        placed, failure = _base(ctx)
        assert placed is not None, failure
    else:
        ctx = _case()
        ctx, placed = _control(ctx, _placed(ctx), name)
    current, failure = dc._part_texts(ctx, deepcopy(placed), [], [])
    assert failure is None, failure
    assert len(current) >= 8
    if name in ("source", "three-pin"):
        for part in PARTS:
            extent = dc._part_box(ctx.profile(part), placed.poses[part], placed.origins[part])
            rows = _rows(current, part)
            assert all(row.bbox[0] >= extent[2] for row in rows.values())
            assert rows["reference"].bbox[1] > rows["value"].bbox[1]
    with monkeypatch.context() as legacy:
        legacy.setattr(dc, "_input_chain_s20_parts", lambda _ctx: set(), raising=False)
        original, original_failure = dc._part_texts(ctx, deepcopy(placed), [], [])
    assert original_failure is None, original_failure
    assert _tuple(current) == _tuple(original)
