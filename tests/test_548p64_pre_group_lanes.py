"""Known singleton label lanes must reach the original flag grouping ruler.

The fixture copies measured pin/body geometry, not native symbol artwork. It
exercises the production candidate builder and Router, without claiming a
visual or editor acceptance of the resulting LCD island.
"""
from collections import Counter
import hashlib
import json

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import ROUTE_AUTOMATIC
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from test_548j_joint_seats import _book, _circuit, _pin, _prepared, _spec, _symbol


def _lcd_case(*, renamed=False):
    host, cap = ("PORT9", "CAP8") if renamed else ("J1", "C4")
    supply, ground = ("SUPPLY", "RETURN") if renamed else ("3V3", "GND")
    signals = [f"PORT_SIGNAL_{number}" for number in range(5)] if renamed else [
        "LCD_SCK", "LCD_SDA", "LCD_RES", "LCD_DC", "LCD_BLK"]
    book = {
        "PORT": SymbolProfile.from_dict(_symbol("PORT", [-10.5, -45.5, 10.5, 45.5], [
            _pin(str(number), [-20.0, 45.0 - 10.0 * number], "left")
            for number in range(1, 9)])),
        "CAP": SymbolProfile.from_dict(_symbol("CAP", [-10.5, -8.5, 10.5, 8.5], [
            _pin("1", [-20, 0], "left"), _pin("2", [20, 0], "right")])),
        "PWR-GND": SymbolProfile.from_dict(_symbol("PWR-GND", [-10.5, 9.5, 10.5, 19.5], [])),
        f"PWR-{supply}": SymbolProfile.from_dict(_symbol(f"PWR-{supply}", [-5.5, 4.5, 5.5, 10.5], [])),
    }
    circuit = CircuitSpec.from_dict({
        "parts": [{"id": host, "symbolRef": "PORT", "value": "ST7789 8P", "provenance": "ai_asserted"},
                  {"id": cap, "symbolRef": "CAP", "value": "100nF", "provenance": "ai_asserted"}],
        "nets": [{"id": supply, "class": "power", "members": [f"{host}.1", f"{cap}.1"], "provenance": "ai_asserted"},
                 {"id": ground, "class": "gnd", "members": [f"{host}.2", f"{host}.7", f"{cap}.2"], "provenance": "ai_asserted"},
                 *[{"id": signal, "class": "signal", "members": [f"{host}.{pin}"], "provenance": "ai_asserted"}
                   for signal, pin in zip(signals, (3, 4, 5, 6, 8))]],
        "draft": True,
    })
    document = {
        "grammarRef": "ic-periphery", "textPlacement": "native-attr",
        "modules": [{"id": "display", "parts": [host, cap], "core": host, "role": "LCD boundary and its decoupling"}],
        "serviceLayout": {"pinGap": 30.0}, "partTexts": {host: "left"},
        "labelPolicy": {"local": "wire", "crossModule": "label", "highFanout": "label",
                        "stub": "straight", "stubMin": 40.0, "stubLaneReserve": True, "rowModel": "centered"},
        "sidePreferences": {"input": "left", "output": "right", "power": "top",
                            "gnd": "bottom", "load": "right", "source": "left"},
    }
    if renamed:
        document["userLocks"] = [{"partId": host, "x": 65.0, "y": 35.0}]
    spec = PresentationSpec.from_dict(document)
    binding = dc.bind_grammar(circuit, spec, book)
    binding = dc._with_series_arms(binding, spec)
    binding = dc._with_panel_groups(binding, spec, circuit)
    binding = dc._with_service_groups(binding, spec, circuit, book)
    assert binding.ok
    budget = dc.CompileBudget(page_box=None, flag_lead_limit=120.0, gnd_cluster_radius=100.0)
    prepared = dc._prepare(circuit, spec, binding, book, budget)
    assert prepared.context is not None and not prepared.failures
    return prepared.context, host, ground, signals


@pytest.mark.parametrize("renamed", [False, True])
def test_initial_grouping_sees_the_same_singleton_lanes_the_seat_pass_consumes(monkeypatch, renamed):
    ctx, host, ground, signals = _lcd_case(renamed=renamed)
    original_group = dc._flag_groups
    original_reserve = dc._reserve_label_stubs
    original_lanes = dc._lead_lane_reservations
    calls = Counter()
    recorded = {}

    def reserve(*args, **kwargs):
        calls[args[2]] += 1
        return original_reserve(*args, **kwargs)

    def group(context, expression, cls, router, *args, **kwargs):
        result = original_group(context, expression, cls, router, *args, **kwargs)
        if expression.net == ground and "group" not in recorded:
            points = dict(expression.points)
            recorded.update(group=result, taken=router.reserved,
                            lanes=dict(router.reserved), blocked=set(router.blocked),
                            calls=calls.copy(), points=points,
                            distance=dc._flag_ruler(context, router, ground)(
                                points[f"{host}.2"], points[f"{host}.7"]))
        return result

    def lanes(*args, **kwargs):
        router = args[4]
        recorded["later_taken"] = router.reserved
        recorded["later_lanes"] = dict(router.reserved)
        result = original_lanes(*args, **kwargs)
        recorded["after_taken"] = router.reserved
        return result

    monkeypatch.setattr(dc, "_reserve_label_stubs", reserve)
    monkeypatch.setattr(dc, "_flag_groups", group)
    monkeypatch.setattr(dc, "_lead_lane_reservations", lanes)
    dc._build_candidate(ctx, dc._variants(ctx)[0])

    # These assertions fail on the old sequence: the initial ruler sees zero
    # reservations, no foreign pin blockers, and a false 50-unit straight walk.
    assert {net: recorded["calls"][net] for net in signals} == dict.fromkeys(signals, 1)
    singleton_lanes = Counter(net for net in recorded["lanes"].values() if net in signals)
    assert singleton_lanes == Counter(dict.fromkeys(signals, 9))
    x, high_y = recorded["points"][f"{host}.2"]
    assert {(x, high_y - step * 10.0) for step in range(1, 5)} <= recorded["blocked"]
    assert recorded["distance"] > dc._flag_group_reach(ctx)
    assert sorted(len(cluster) for cluster in recorded["group"]) == [1, 1, 1]
    assert recorded["later_taken"] is recorded["taken"] is recorded["after_taken"]
    assert recorded["later_lanes"] == recorded["lanes"]
    assert {net: calls[net] for net in signals} == dict.fromkeys(signals, 1)


# 548P118: the old pins also held host paths five units from foreign terminal
# pins. The clearance repair changes only those paths/junctions; parts, flags,
# labels and texts are identical (`.tmp_548p117/p64-diff.log`). Pin the exact
# legal geometry rather than preserving that near-short appearance.
#
# 599 / 590: the pinned sha is the *pre-590* document. A compiled plan now also
# states `route` and `provenanceSha256` (neither is part of `geometry_json`), so
# the pin is compared against the projection with those two keys taken off; the
# keys themselves are asserted present and correct. Deleting them would fail the
# second half, and a third moving key fails the projection.
_ROUTE_KEYS = ("route", "provenanceSha256")


def _pre_590_sha(built) -> str:
    body = built.plan.to_jsonable()
    projection = {key: value for key, value in body.items() if key not in _ROUTE_KEYS}
    assert set(body) - set(projection) == set(_ROUTE_KEYS), (
        "590 must add exactly `route` and `provenanceSha256`; any other key is a "
        "changed field hiding behind the new ones"
    )
    payload = json.dumps(projection, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize("name,expected", [
    ("no_group", "3804adcec8ee430170423ecc8e8b1dbde5e4428f1bc5f8af4ed108276dc40764"),
    ("no_stubs", "88d0fc98bb39e55355b4e7dff8c532c6fdd71414e48368af3e7729f6ab8c71e7"),
])
def test_unstated_path_has_the_expected_complete_success_json(monkeypatch, name, expected):
    circuit, spec, book = _circuit(), _spec(), _book()
    if name == "no_stubs":
        document = spec.to_jsonable()
        document.update(textPlacement="native-attr", serviceLayout={"pinGap": 30.0})
        spec = PresentationSpec.from_dict(document)
    ctx = _prepared(circuit, spec, book)
    assert dc._flag_grouping(ctx) == (name == "no_stubs")
    stages = []
    original_lanes = dc._lead_lane_reservations
    original_reserve = dc._reserve_label_stubs

    def lanes(*args, **kwargs):
        stages.append("seat-pass")
        return original_lanes(*args, **kwargs)

    def reserve(*args, **kwargs):
        assert stages, "the legacy path must choose labels inside its original seat pass"
        return original_reserve(*args, **kwargs)

    monkeypatch.setattr(dc, "_lead_lane_reservations", lanes)
    monkeypatch.setattr(dc, "_reserve_label_stubs", reserve)
    built, failure, _notes = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, failure
    assert _pre_590_sha(built) == expected
    body = built.plan.to_jsonable()
    assert body["route"] == ROUTE_AUTOMATIC and built.plan.route_declared is True
    assert body["provenanceSha256"] == built.plan.provenance_sha256(), (
        "the seal is this plan's own route + geometry digest"
    )
