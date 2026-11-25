"""611: the `patch-pin` wire contract — no drawn point is ever dropped, and the
pin report can be narrowed to the net being repaired (570-D D9).

Two defects, one function pair:

* `patchpin.wire_segments` read a **flat** host `Line` with
  ``range(0, len(coords) - 1, 2)``, so ``Line=[0,0,100,0,200]`` quietly became
  ``[(0,0),(100,0)]`` — the editor's third coordinate vanished and the canvas
  "proof" was built on a wire that is not the one on the page. An odd count no
  longer guesses: it is refused by name (wire index, primitive id, count).
* `patchpin.wires_through_pin` had no `net` argument, unlike its sibling
  `wire_endpoints_on_pin`, so a VCC wire crossing a pin mid-segment was reported
  as evidence for a GND repair. The filter is the sibling's, deliberately: an
  empty net keeps the old "any net" reading (the plan stage's refusal leans on
  it), a named net returns only that net's wires.

The CLI has exactly one production call site (`cli.py`, the patch-pin apply's
`range.wiresThroughPin`); the two fake-bridge tests below walk the real CLI flow
to prove it forwards `after_net`: a reconnect whose target net is NET_OUT must
not report a VCC wire through the pin, and a disconnect (`after_net=""`) must
keep reporting it unfiltered.
"""

from __future__ import annotations

import json

import pytest

import test_035_patchpin as t035
from boardwise import cli
from boardwise.engines.patchpin import wire_segments, wires_through_pin


# --------------------------------------------------------------------------
# 1. wire_segments: an odd flat coordinate list is refused, not truncated
# --------------------------------------------------------------------------

def _flat(primitive_id: str, net: str, coords: list) -> dict:
    return {"primitiveId": primitive_id, "state": {"Line": list(coords), "Net": net}}


def test_an_odd_flat_line_is_refused_by_name_and_yields_no_partial_segments():
    geometry = {"wires": [
        t035._wire("w-ok", "SIG", [(0.0, 0.0), (100.0, 0.0)]),
        _flat("w-bad", "SIG", [0, 0, 100, 0, 200]),
    ]}
    with pytest.raises(ValueError) as refused:
        wire_segments(geometry)
    detail = str(refused.value)
    assert "wire #1 (w-bad)" in detail, detail
    assert "5 numbers" in detail, detail
    assert "w-ok" not in detail, "the refusal names the wire it cannot read, not its neighbour"


def test_a_two_number_line_is_odd_too_and_is_refused():
    with pytest.raises(ValueError, match="wire #0"):
        wire_segments({"wires": [_flat("w-short", "SIG", [0, 0, 100])]})


def test_an_even_flat_line_keeps_every_reported_point():
    (segment,) = wire_segments({"wires": [_flat("w-even", "SIG", [0, 0, 100, 0, 200, 0])]})
    assert segment.points == ((0.0, 0.0), (100.0, 0.0), (200.0, 0.0))
    assert segment.net == "SIG"


def test_nested_points_are_still_read_pairwise():
    geometry = {"wires": [{
        "primitiveId": "w-nested",
        "state": {"Points": [[0, 0], [100, 0], [200, 0]], "Net": "SIG"},
    }]}
    (segment,) = wire_segments(geometry)
    assert segment.points == ((0.0, 0.0), (100.0, 0.0), (200.0, 0.0))


@pytest.mark.parametrize("geometry", [None, {}, {"wires": []}, {"wires": None}, []])
def test_no_geometry_and_no_wires_still_read_as_no_segments(geometry):
    assert wire_segments(geometry) == []


# --------------------------------------------------------------------------
# 2. wires_through_pin: the optional net, the same shape as its sibling
# --------------------------------------------------------------------------

def _crossing() -> dict:
    """A VCC wire through the pin and a GND wire ending on it."""
    return t035._geometry(wires=[
        t035._wire("w-vcc", "VCC", [(60.0, 200.0), (160.0, 200.0)]),
        t035._wire("w-gnd-end", "GND", [(100.0, 200.0), (100.0, 260.0)]),
        t035._wire("w-gnd-thru", "GND", [(100.0, 160.0), (100.0, 240.0)]),
    ])


def test_a_net_filter_keeps_the_crossing_wire_of_that_net_only():
    geometry = _crossing()
    assert wires_through_pin(geometry, (100.0, 200.0), "GND") == ["w-gnd-thru"]
    assert wires_through_pin(geometry, (100.0, 200.0), "VCC") == ["w-vcc"]


def test_a_foreign_net_is_not_evidence_for_this_pin():
    assert wires_through_pin(_crossing(), (100.0, 200.0), "SIG") == []


def test_an_empty_net_keeps_the_old_unfiltered_reading():
    geometry = _crossing()
    assert wires_through_pin(geometry, (100.0, 200.0)) == ["w-vcc", "w-gnd-thru"]
    assert wires_through_pin(geometry, (100.0, 200.0), "") == ["w-vcc", "w-gnd-thru"]


def test_the_net_filter_does_not_change_what_counts_as_a_T():
    """The endpoint exclusion stays: a wire *ending* on the pin is never a T."""
    assert wires_through_pin(_crossing(), (100.0, 200.0), "GND") == ["w-gnd-thru"]
    assert "w-gnd-end" not in wires_through_pin(_crossing(), (100.0, 200.0), "GND")


# --------------------------------------------------------------------------
# 3. the CLI's one call site forwards after_net (fake bridge, real flow)
# --------------------------------------------------------------------------

def _through_geometry_after() -> dict:
    return t035._geometry(wires=[
        t035._wire("w-out", "NET_OUT", [(100.0, 140.0), (160.0, 140.0)]),
        t035._wire("w-vcc", "VCC", [(60.0, 200.0), (180.0, 200.0)]),
        t035._wire("w-new", "NET_OUT", [(120.0, 200.0), (100.0, 140.0)]),
    ], components=[("U3", 90.0, 190.0)])


def test_a_reconnect_does_not_report_a_foreign_wire_through_the_pin(
    monkeypatch, tmp_path, capsys
):
    """after_net=NET_OUT: the VCC crossing wire is not part of this repair."""
    bridge = t035._FakeBridge(
        live_nets=[{"5": "VIN", "1": ""}, {"5": "NET_OUT"}, {"5": "NET_OUT"}],
        delete_reply={"deleted": ["w-attach5"], "notFound": [], "failed": []},
    )
    t035._stub_bridge(monkeypatch, bridge)
    rule = next(item for item in cli.BUILTIN_RULES if item.id == "conn-nc-and-must-connect")
    monkeypatch.setattr(rule, "_library", t035._library())
    bridge.geometry = [
        t035._geometry(wires=[
            t035._wire("w-attach5", "VIN", [(120.0, 200.0), (200.0, 200.0)]),
            t035._wire("w-out", "NET_OUT", [(100.0, 140.0), (160.0, 140.0)]),
        ], components=[("U3", 90.0, 190.0)]),
        _through_geometry_after(),
    ]
    out = tmp_path / "plan.json"
    assert cli.main([
        "edit", "plan", "--file", str(t035._snapshot(tmp_path)),
        "--rule", "conn-nc-and-must-connect", "--designator", "U3",
        "--report", str(t035._report_file(tmp_path, before="VIN", after="NET_OUT", pin="5")),
        "-o", str(out),
    ]) == 0
    capsys.readouterr()
    before = t035._model(
        pin_net={"1": "VIN", "5": "VIN"},
        nets={"VIN": [("U3", "1"), ("U3", "5")], "NET_OUT": [("U9", "1")]},
    )
    after = t035._model(
        pin_net={"1": "VIN", "5": "NET_OUT"},
        nets={"VIN": [("U3", "1")], "NET_OUT": [("U3", "5"), ("U9", "1")]},
    )
    t035._stub_models(monkeypatch, [before, after, after, after])
    bridge.reads = 0
    result = tmp_path / "apply.json"

    code = cli.main(["edit", "apply", str(out), "--json", str(result)])
    printed = capsys.readouterr().out
    assert code == 0, printed
    report = json.loads(result.read_text(encoding="utf-8"))
    assert report["form"] == "reconnect"
    assert report["range"]["wiresThroughPin"] == [], (
        "a VCC wire crossing the pin mid-segment is not evidence for the NET_OUT repair"
    )
    assert report["range"]["wireEndpointsOnPin"] == ["w-new"]


def test_a_disconnect_keeps_the_unfiltered_through_reading(monkeypatch, tmp_path, capsys):
    """after_net="" is forwarded empty: the old any-net reading is unchanged."""
    bridge = t035._FakeBridge(live_nets=[{"4": "NET4", "2": "NET4"}, {"4": "", "2": ""}])
    t035._stub_bridge(monkeypatch, bridge)
    bridge.geometry = [
        t035._geometry(wires=[
            t035._wire("w-attach", "NET4", [(100.0, 200.0), (160.0, 200.0)]),
        ], components=[("U3", 90.0, 190.0)]),
        t035._geometry(wires=[
            t035._wire("w-vcc", "VCC", [(60.0, 200.0), (160.0, 200.0)]),
        ], components=[("U3", 90.0, 190.0)]),
    ]
    out = tmp_path / "plan.json"
    assert cli.main([
        "edit", "plan", "--file", str(t035._snapshot(tmp_path)),
        "--rule", "conn-nc-and-must-connect", "--designator", "U3",
        "--report", str(t035._report_file(tmp_path)), "-o", str(out),
    ]) == 0
    capsys.readouterr()
    before = t035._model(pin_net={"4": "NET4"}, nets={"NET4": [("U3", "4"), ("U9", "1")]})
    after = t035._model(pin_net={"4": "NET12"},
                        nets={"NET12": [("U3", "4")], "NET4": [("U9", "1")]})
    t035._stub_models(monkeypatch, [before, after, after])
    bridge.reads = 0

    async def _review(*_args, **_kwargs):
        return {"state": "resolved", "reason": "the rule reports U3 pin4 as satisfied"}

    monkeypatch.setattr(cli, "_edit_post_review_pin", _review)
    result = tmp_path / "apply.json"

    code = cli.main(["edit", "apply", str(out), "--json", str(result)])
    printed = capsys.readouterr().out
    assert code == 0, printed
    report = json.loads(result.read_text(encoding="utf-8"))
    assert report["form"] == "disconnect"
    assert report["range"]["wiresThroughPin"] == ["w-vcc"], (
        "with after_net empty the net filter is off — same reading as before 611"
    )
