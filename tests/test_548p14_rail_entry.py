"""548P14: both existing rail ends use the same production router and walls."""

from __future__ import annotations

import copy

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import readability
from test_548j_joint_seats import _profile_payloads
from test_548n_group_seat import _prepared
from test_548p6_service_feedback import _fixture as base_fixture


def _fixture(*, blocked="inner", second_supply=False):
    circuit, spec, book, _ctx = base_fixture()
    payload = circuit.to_jsonable()
    for part in payload["parts"]:
        part["provenance"] = "ai_asserted"
    for net in payload["nets"]:
        net["provenance"] = "ai_asserted"
    for part in ("C1", "C2"):
        payload["parts"].append({"id": part, "symbolRef": "C", "value": "100n",
                                 "provenance": "ai_asserted"})
    for net in payload["nets"]:
        if net["id"] == "PWR":
            net["members"].extend(("C1.1", "C2.1"))
            if second_supply:
                net["members"].append("U1.VDD2")
        if net["id"] == "GND":
            net["members"].extend(("C1.2", "C2.2"))
    payload.pop("draft", None)
    circuit = CircuitSpec.from_dict(payload)
    host = book["HOST4"].to_jsonable()
    for index, pin in enumerate(host["pins"], 1):
        pin["number"] = str(index)
        if pin["name"] == "GND":
            pin.update(tip=[-50.0, -35.0], direction="left")
    if second_supply:
        host["pins"].append({"number": "6", "name": "VDD2", "tip": [50.0, 55.0],
                              "direction": "right", "length": 10.0, "pinType": "passive"})
    host["texts"] = [{"kind": "reference", "x": -40.0, "y": 50.0},
                      {"kind": "value", "x": -40.0, "y": -60.0}]
    host["source"] = "548P14 synthetic numeric-pin host; not live measured"
    book["HOST4"] = SymbolProfile.from_dict(host)
    book["C"] = SymbolProfile.from_dict(copy.deepcopy(_profile_payloads()["C"]))
    document = spec.to_jsonable()
    document.pop("partTexts", None)
    document["textPlacement"] = "native-attr"
    document["modules"][0]["parts"].extend(("C1", "C2"))
    document["serviceGroups"].append({"id": "decouple", "branches": [
        {"part": "C1", "from": "PWR", "to": "GND"},
        {"part": "C2", "from": "PWR", "to": "GND"}]})
    spec = PresentationSpec.from_dict(document)
    ctx = _prepared(circuit, spec, book)
    variant = dc._variants(ctx)[0]
    placed, failure = dc._place(ctx, variant, seat_service_groups=False)
    assert placed is not None, failure
    # These pending decouplers still occupy their base-layout positions while
    # config is routed. The later existing decouple seat moves them normally;
    # the config router must keep both bodies as walls throughout its attempts.
    placed.origins["C1"] = (370.0, 460.0) if blocked != "none" else (700.0, 500.0)
    placed.origins["C2"] = (750.0, 500.0)
    return circuit, spec, book, ctx, variant, placed


def _seat_with_observation(monkeypatch, fixture, *, block_outer_after_flag=False):
    circuit, _spec, _book, ctx, _variant, placed = fixture
    original_group, original_route = dc._joint_route_group, dc._Router.route
    active = None
    calls = []

    def group(*args, **kwargs):
        nonlocal active
        active = args if args[1] == "$.serviceGroups['config']" else None
        if active is not None and block_outer_after_flag:
            # Isolate the router's negative case after the rail flag exists.
            # Blocking this endpoint earlier correctly fails the flag ladder,
            # before host-to-rail routing can examine either endpoint.
            active[6].origins["C2"] = (440.0, 460.0)
        try:
            return original_group(*args, **kwargs)
        finally:
            active = None

    def route(router, start, end, *args, **kwargs):
        if active is None:
            return original_route(router, start, end, *args, **kwargs)
        _ctx, _spot, _prepared, _cells, rails, host, placement, sign, _kind = active[:9]
        feet = [dc._pin_point(ctx, host, token, placement.poses, placement.origins)
                for token in dc._service_group_side_tokens(ctx, host, "PWR")]
        result = original_route(router, start, end, *args, **kwargs)
        if start in feet:
            trunk = next(rail.runs[0] for rail in rails if rail.net == "PWR")
            calls.append({"start": start, "target": end, "trunk": trunk,
                          "path": result, "walls": tuple(router.boxes),
                          "blocked": frozenset(router.blocked),
                          "edges": copy.deepcopy(router.edges)})
        return result

    monkeypatch.setattr(dc, "_joint_route_group", group)
    monkeypatch.setattr(dc._Router, "route", route)
    refusal = dc._seat_service_groups(ctx, placed, row_offsets={"config": 80.0})
    return refusal, calls


def _assert_canonical_connectivity(circuit, book, plan):
    derived = readability.derive_netlist(plan, book)
    expected = {}
    for net in circuit.nets:
        canonical = set()
        for member in net.members:
            part, _, token = member.partition(".")
            profile = book[circuit.part(part).symbol_ref]
            canonical.add(f"{part}.{dc._pin_of_token(profile, token).number}")
        expected[net.id] = canonical
        for member in canonical:
            assert set(derived.group_of(member)) == canonical, (member, canonical)
    assert set(derived.pin_points) == set(derived.wired_pins)
    return expected


def _assert_visible_host_runs(placed, plan, calls):
    rail = next(rail for record in placed.service_group_plans
                if record.group_id == "config" for rail in record.rails
                if rail.net == "PWR")
    feet = {call["start"] for call in calls if call["path"] is not None}
    for foot in feet:
        # The final geometry may replace the provisional route after another
        # group moves. Its host-foot identity and visible rail connection stay.
        matching = [run for run in rail.runs[1:]
                    if run[0] == foot and run[-1] in (rail.runs[0][0], rail.runs[0][-1])]
        assert len(matching) == 1, "each host foot needs one final run to its own trunk"
        run = matching[0]
        assert any(segment.net == "PWR" and tuple(segment.points) == run
                   for segment in plan.segments)


def test_blocked_inner_end_uses_the_existing_outer_end_and_full_builder(monkeypatch):
    fixture = _fixture()
    circuit, _spec, book, ctx, variant, placed = fixture
    refusal, calls = _seat_with_observation(monkeypatch, fixture)
    assert refusal is None, refusal
    assert len(calls) == 2
    assert calls[0]["path"] is None and calls[1]["path"] is not None
    assert calls[0]["target"] == calls[0]["trunk"][0]
    assert calls[1]["target"] == calls[0]["trunk"][-1]
    for key in ("walls", "blocked", "edges"):
        assert calls[1][key] == calls[0][key], key
    built, failure, violations = dc._build_one_variant(ctx, variant, [], placement_override=placed)
    assert built is not None, (failure, violations)
    _assert_visible_host_runs(placed, built.plan, calls)
    _assert_canonical_connectivity(circuit, book, built.plan)
    assert not built.checked.hard_violations
    assert {text.part_id for text in built.plan.texts} == {part.id for part in circuit.parts}


def test_two_blocked_ends_keep_the_named_refusal(monkeypatch):
    fixture = _fixture()
    refusal, calls = _seat_with_observation(monkeypatch, fixture, block_outer_after_flag=True)
    assert isinstance(refusal, dc.GrammarFailure)
    assert "VDD" in refusal.detail and "PWR" in refusal.detail
    assert len(calls) == 2 and all(call["path"] is None for call in calls)
    assert calls[1]["walls"] == calls[0]["walls"]


def test_a_successful_inner_entry_routes_once_and_keeps_its_geometry(monkeypatch):
    fixture = _fixture(blocked="none")
    refusal, calls = _seat_with_observation(monkeypatch, fixture)
    assert refusal is None, refusal
    assert len(calls) == 1 and calls[0]["path"] is not None
    assert calls[0]["target"] == (365.0, 460.0)
    assert tuple(dc._compress(calls[0]["path"])) == (
        (350.0, 430.0), (350.0, 460.0), (365.0, 460.0))


def test_each_supply_foot_reaches_the_rail(monkeypatch):
    fixture = _fixture(second_supply=True)
    circuit, _spec, book, ctx, variant, placed = fixture
    refusal, calls = _seat_with_observation(monkeypatch, fixture)
    assert refusal is None, refusal
    assert {call["start"] for call in calls if call["path"] is not None} == {
        (350.0, 430.0), (350.0, 455.0)}
    built, failure, violations = dc._build_one_variant(ctx, variant, [], placement_override=placed)
    assert built is not None, (failure, violations)
    _assert_visible_host_runs(placed, built.plan, calls)
    expected = _assert_canonical_connectivity(circuit, book, built.plan)
    assert {"U1.1", "U1.6"} <= expected["PWR"]
