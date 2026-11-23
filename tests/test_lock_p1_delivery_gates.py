"""P1 delivery gates: the machine gates the pre-fix P1 page walked past.

The original session placed P1's wires foot by foot, and the page shipped with
facts no predicate could state: one conductor carrying GND *and* +5V, a wire
naming a rail the page has no flag for, two symbols' bodies stacked on the
canvas (U1/Q1 11×21, U1/R4 21×9), and a netlist in which U1's VSSA/VSS/VDD all
sit on +3V3 and C3/C4's two pins are shorted to each other — with **no GND net
at all** while the page's labels said GND.

This module pins those causal items one by one, and pins the legal shapes they
must never touch (a one-name carrier, a flagged MCU minimal system, a
two-terminal part with two different nets). Every assertion names the object it
is about; a mutated call site must turn the matching test red instead of merely
changing a total.

Nothing here touches the editor: every case is a synthetic snapshot, and the
netlist is a synthetic `sch.netlist` document in the host's own shape.
"""

from __future__ import annotations

import json

from boardwise.engines import drawlint

BLUE = drawlint.FILL_VALUE


# ------------------------------------------------------------------ builders


def _sheet_box() -> dict:
    return {
        "primitiveId": "sheet1",
        "state": {
            "PrimitiveType": "Component",
            "ComponentType": "sheet",
            "PrimitiveId": "sheet1",
        },
    }


def _part(designator: str, x: float, y: float, primitive: str = "") -> dict:
    primitive = primitive or f"part-{designator}"
    return {
        "primitiveId": primitive,
        "state": {
            "PrimitiveType": "Component",
            "ComponentType": "part",
            "PrimitiveId": primitive,
            "Designator": designator,
            "X": x,
            "Y": y,
            "Rotation": 0,
            "Mirror": False,
        },
    }


def _flag(net: str, x: float, y: float) -> dict:
    return {
        "primitiveId": f"flag-{net}-{x}-{y}",
        "state": {
            "PrimitiveType": "Component",
            "ComponentType": "netflag",
            "PrimitiveId": f"flag-{net}-{x}-{y}",
            "X": x,
            "Y": y,
            "Rotation": 0,
            "Net": net,
        },
    }


def _wire(primitive: str, net: str, *points: float) -> dict:
    return {
        "primitiveId": primitive,
        "state": {
            "PrimitiveType": "Wire",
            "PrimitiveId": primitive,
            "Net": net,
            "Line": list(points),
        },
    }


def _snapshot(*components: dict, wires: list[dict] | None = None) -> dict:
    return {
        "components": [_sheet_box(), *components],
        "wires": wires or [],
        "pins": [],
        "netlabels": [],
        "bboxes": {"sheet1": {"minX": 0, "minY": 0, "maxX": 1170, "maxY": 825}},
        "meta": {"sheets": ["sheet1"]},
    }


def _text_node(x: float, y_svg: float, text: str) -> str:
    return (
        f'<text style="font-family:\'Arial\';font-size:7.148342059336824px;'
        f'font-style:normal;font-weight:normal;fill:{BLUE};stroke:none;"'
        f' x="{x}" y="{y_svg}" text-anchor="start" '
        f'transform="rotate(0, {x}, {y_svg})" '
        f'dominant-baseline="ideographic"><tspan xml:space="preserve" '
        f'x="{x}" dx="0" dy="0">{text}</tspan></text>'
    )


def _svg(*nodes: str) -> str:
    return "<svg>" + "".join(nodes) + "</svg>"


def _netlist_doc(components: dict[str, dict[str, tuple[str, str]]]) -> dict:
    """An `sch.netlist` answer: {type, text} with the host's EasyEDA shape.

    ``components`` maps a designator to ``{pin_number: (pin_name, net)}``.
    """
    body = {}
    for index, (designator, pins) in enumerate(components.items()):
        body[f"gge{index}"] = {
            "props": {"Designator": designator},
            "altLibs": {"devices": [], "footprints": []},
            "pinInfoMap": {
                str(number): {"name": name, "number": str(number), "net": net}
                for number, (name, net) in pins.items()
            },
        }
    return {"type": "EasyEDA", "text": json.dumps({"version": "2.0.0", "components": body})}


def _lint(snapshot: dict, svg: str | None = None, **kwargs):
    return drawlint.run_lint(snapshot, svg, **kwargs)


def _by_predicate(findings) -> dict[str, list]:
    out: dict[str, list] = {}
    for finding in findings:
        out.setdefault(finding.predicate, []).append(finding)
    return out


def _errors(findings) -> list:
    return [f for f in findings if f.severity == "ERROR"]


# -------------------------------------------------- L11-part-overlap (P1 body)


def test_part_overlap_reports_the_p1_body_collisions():
    """P1's measured bodies: U1/Q1 overlap 11×21, U1/R4 21×9 — ERROR, with
    designators, primitives and the overlap size in the message."""
    snapshot = _snapshot(
        _part("U1", 700, 780, "prim-u1"),
        _part("Q1", 760, 700, "prim-q1"),
        _part("R4", 700, 700, "prim-r4"),
    )
    bodies = {
        "prim-u1": (624.5, 654.5, 775.5, 905.5),
        "prim-q1": (759.5, 689.5, 770.5, 710.5),
        "prim-r4": (689.5, 695.5, 710.5, 704.5),
    }
    hits = _by_predicate(_lint(snapshot, bodies=bodies)).get("L11-part-overlap", [])
    pairs = {frozenset((h.objects[0], h.objects[1])): h for h in hits}
    assert frozenset(("U1", "Q1")) in pairs, f"U1/Q1 collision lost: {sorted(pairs, key=sorted)}"
    assert frozenset(("U1", "R4")) in pairs, f"U1/R4 collision lost: {sorted(pairs, key=sorted)}"
    q1 = pairs[frozenset(("Q1", "U1"))]
    assert q1.severity == "ERROR"
    assert "prim-u1" in q1.message and "prim-q1" in q1.message, q1.message
    assert "11.0×21.0" in q1.message, q1.message
    r4 = pairs[frozenset(("U1", "R4"))]
    assert "21.0×9.0" in r4.message, r4.message


def test_part_overlap_spares_edge_contact_and_unmeasured_parts():
    """Two bodies sharing exactly one edge do not overlap (正面积相交才算),
    and a run that measured no body claims no collision."""
    snapshot = _snapshot(
        _part("C1", 200, 100, "prim-c1"),
        _part("C2", 220, 100, "prim-c2"),
    )
    bodies = {
        "prim-c1": (190.0, 90.0, 210.0, 110.0),
        "prim-c2": (210.0, 90.0, 230.0, 110.0),
    }
    findings = _lint(snapshot, bodies=bodies)
    assert _by_predicate(findings).get("L11-part-overlap") is None, (
        "edge contact is not an overlap"
    )
    assert _by_predicate(_lint(snapshot)).get("L11-part-overlap") is None, (
        "no measured body — the predicate must answer 'unreadable', not guess"
    )


# --------------------------------------- L11-rail-without-flag (P1 has none)


def test_rail_without_flag_fires_when_the_page_carries_no_flag():
    """P1 states GND/+3V3 on its conductors and carries no netflag at all."""
    snapshot = _snapshot(
        wires=[
            _wire("wGND", "GND", 100, 100, 160, 100),
            _wire("w3V3", "+3V3", 100, 200, 160, 200),
            _wire("wSig", "LED_A", 100, 300, 160, 300),
        ]
    )
    hits = _by_predicate(_lint(snapshot)).get("L11-rail-without-flag", [])
    nets = {h.objects[0] for h in hits}
    assert nets == {"GND", "+3V3"}, f"rails reported {nets} != GND/+3V3"
    assert all(h.severity == "ERROR" for h in hits)
    assert all("flag" in h.message for h in hits)


def test_rail_without_flag_spares_a_legal_flagged_mcu_minimal_system():
    """A stocked MCU minimal system: GND and +3V3 both flagged, one name per
    conductor — nothing to report, geometry or netlist."""
    snapshot = _snapshot(
        _part("U1", 700, 780, "prim-u1"),
        _flag("GND", 100, 120),
        _flag("+3V3", 100, 220),
        wires=[
            _wire("wGND", "GND", 100, 100, 160, 100),
            _wire("w3V3", "+3V3", 100, 200, 160, 200),
        ],
    )
    netlist = _netlist_doc(
        {
            "U1": {
                8: ("VSSA", "GND"),
                9: ("VDDA", "+3V3"),
                23: ("VSS_1", "GND"),
                24: ("VDD_1", "+3V3"),
            },
            "C1": {1: ("1", "+3V3"), 2: ("2", "GND")},
        }
    )
    findings = _lint(snapshot, netlist=netlist)
    assert not _errors(findings), [f.message for f in _errors(findings)]


# ------------------------------------- L5 rail name conflict on one conductor


def test_one_conductor_naming_gnd_and_5v_is_an_error():
    """P1's exact shape: the same wire primitive backs a GND name and a +5V
    name. The ordinary same-name repeat keeps its WARN; the rail conflict is
    its own ERROR row."""
    snapshot = _snapshot(wires=[_wire("w1", "GND", 100, 100, 160, 100)])
    svg = _svg(_text_node(110, -100, "GND"), _text_node(140, -100, "+5V"))
    by_predicate = _by_predicate(_lint(snapshot, svg))
    conflict = by_predicate.get("L5-wire-rail-conflict", [])
    assert len(conflict) == 1, f"one conductor, one conflict row: {len(conflict)}"
    assert conflict[0].severity == "ERROR"
    assert "GND" in conflict[0].message and "+5V" in conflict[0].message
    assert conflict[0].objects[0] == "w1"
    # L5b's own row is not silently promoted — the existing WARN calibration
    # (111a's accepted-page pins) stays exactly as it was; the escalation is the
    # ERROR row above.
    for row in by_predicate.get("L5-wire-multiname", []):
        assert row.severity == "WARN", row.severity


def test_one_conductor_with_one_repeated_name_is_not_a_rail_conflict():
    """The legal carrier: two labels of the *same* signal name (P22's TAP
    shape) stays L5b's WARN — no ERROR is invented."""
    snapshot = _snapshot(wires=[_wire("w1", "TAP", 100, 100, 160, 100)])
    svg = _svg(_text_node(110, -100, "TAP"), _text_node(140, -100, "TAP"))
    by_predicate = _by_predicate(_lint(snapshot, svg))
    assert "L5-wire-rail-conflict" not in by_predicate
    assert by_predicate.get("L5-wire-multiname"), "the ordinary WARN must stay"
    assert all(h.severity == "WARN" for h in by_predicate["L5-wire-multiname"])


# ------------------------------------------------- netlist electrical gates


def test_netlist_catches_the_p1_shorts_and_spares_legal_two_terminal_parts():
    """C3/C4's two pins on one net and U1's VSS/VDD family on +3V3 are ERRORs;
    R4's two different nets, Q1's named pins and a one-pin part are not."""
    snapshot = _snapshot(
        _part("U1", 700, 780, "prim-u1"),
        _part("R4", 700, 700, "prim-r4"),
    )
    netlist = _netlist_doc(
        {
            "U1": {
                8: ("VSSA", "+3V3"),
                9: ("VDDA", "+3V3"),
                23: ("VSS_1", "+3V3"),
                24: ("VDD_1", "+3V3"),
            },
            "C3": {1: ("1", "+3V3"), 2: ("2", "+3V3")},
            "R4": {1: ("1", "BEEP"), 2: ("2", "BEEP_BASE")},
            "Q1": {1: ("B", "BEEP_BASE"), 2: ("E", "+3V3"), 3: ("C", "BEEP_C")},
            "TP1": {1: ("1", "+3V3")},
        }
    )
    hits = _by_predicate(_lint(snapshot, netlist=netlist))
    shorts = hits.get("L12-two-pin-same-net", [])
    assert [h.objects[0] for h in shorts] == ["C3"], [h.objects[0] for h in shorts]
    assert shorts[0].severity == "ERROR"
    assert "+3V3" in shorts[0].message
    rail = hits.get("L12-ground-supply-pin-short", [])
    assert [h.objects[0] for h in rail] == ["U1"], [h.objects[0] for h in rail]
    assert rail[0].severity == "ERROR"
    assert "VSSA" in rail[0].message and "VDDA" in rail[0].message


def test_netlist_ground_flag_needs_a_net_of_that_name():
    """A Ground flag states a net; when the netlist has no such net the page
    and the netlist disagree about the return path (P1: labels said GND, the
    netlist had no GND)."""
    snapshot = _snapshot(_flag("GND", 100, 120), _wire("w1", "GND", 100, 100, 160, 100))
    absent = _netlist_doc({"U1": {8: ("VSSA", "+3V3"), 9: ("VDDA", "+3V3")}})
    hits = _by_predicate(_lint(snapshot, netlist=absent)).get(
        "L12-ground-flag-absent-from-netlist", []
    )
    assert len(hits) == 1, f"the missing GND net must report: {len(hits)}"
    assert hits[0].severity == "ERROR"
    assert "GND" in hits[0].message

    present = _netlist_doc({"U1": {8: ("VSSA", "GND"), 9: ("VDDA", "+3V3")}})
    assert (
        _by_predicate(_lint(snapshot, netlist=present)).get(
            "L12-ground-flag-absent-from-netlist"
        )
        is None
    ), "a netlist that carries the page's ground net is consistent"


def test_without_a_netlist_no_netlist_check_is_claimed():
    """No --netlist = the netlist predicates did not run (never 'passed')."""
    snapshot = _snapshot(
        _flag("GND", 100, 120),
        _wire("w1", "GND", 100, 100, 160, 100),
    )
    findings = _lint(snapshot)
    netlist_predicates = [f for f in findings if f.predicate.startswith("L12-")]
    assert netlist_predicates == []


def test_netlist_reader_accepts_the_wrapper_and_the_raw_document():
    """`sch.netlist` answers {type, text}; a captured EasyEDA netlist is the
    raw document. Both parse; garbage is refused instead of skipped."""
    wrapper = _netlist_doc({"C3": {1: ("1", "+3V3"), 2: ("2", "+3V3")}})
    parsed = drawlint.read_netlist_document(wrapper)
    part = parsed.parts[0]
    assert part.designator == "C3"
    assert [p.net for p in part.pins] == ["+3V3", "+3V3"]

    raw = json.loads(wrapper["text"])
    again = drawlint.read_netlist_document(raw)
    assert again.parts[0].designator == "C3"

    for broken in ({"text": "{not json"}, {"nope": 1}, 42):
        try:
            drawlint.read_netlist_document(broken)
        except ValueError:
            continue
        raise AssertionError(f"{broken!r} must be refused, not skipped")


# --------------------------------------------------------------- CLI shape


def test_cli_bodies_file_reaches_the_overlap_gate(tmp_path):
    """The replay path's `--bodies` file (the captured ``bboxIds`` probe form:
    ``{"minX": …}``, not the documented list) must reach L11-part-overlap —
    the body gate is only as good as the wiring that feeds it."""
    from boardwise import cli as cli_module

    snapshot = _snapshot(
        _part("U1", 700, 780, "prim-u1"),
        _part("Q1", 760, 700, "prim-q1"),
    )
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(snapshot), encoding="utf-8")
    bodies = tmp_path / "bboxes.json"
    bodies.write_text(
        json.dumps(
            {
                "prim-u1": {"minX": 624.5, "minY": 654.5, "maxX": 775.5, "maxY": 905.5},
                "prim-q1": {"minX": 759.5, "minY": 689.5, "maxX": 770.5, "maxY": 710.5},
            }
        ),
        encoding="utf-8",
    )
    parser = cli_module.build_parser()
    args = parser.parse_args(
        [
            "draw", "lint", "--snapshot", str(snap), "--bodies", str(bodies),
            "--json", str(tmp_path / "report.json"),
        ]
    )
    assert cli_module._cmd_draw_lint(args) == 1
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["predicates"]["L11-part-overlap"] == 1, report["predicates"]
    assert "netlist" in report and report["netlist"]["provided"] is False


def test_cli_netlist_is_a_gate_not_a_note(tmp_path, capsys):
    """`draw lint --netlist` reads the file on the replay path, exits 1 when
    the netlist gate fires, and refuses an unreadable netlist with exit 2."""
    from boardwise import cli as cli_module

    snapshot = _snapshot()
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(snapshot), encoding="utf-8")
    broken = tmp_path / "broken-netlist.json"
    broken.write_text("{}", encoding="utf-8")
    netlist = tmp_path / "netlist.json"
    netlist.write_text(
        json.dumps(
            _netlist_doc(
                {
                    "C3": {1: ("1", "+3V3"), 2: ("2", "+3V3")},
                    "U1": {8: ("VSSA", "+3V3"), 9: ("VDDA", "+3V3")},
                }
            )
        ),
        encoding="utf-8",
    )

    parser = cli_module.build_parser()
    args = parser.parse_args(
        [
            "draw", "lint", "--snapshot", str(snap), "--netlist", str(netlist),
            "--json", str(tmp_path / "report.json"),
        ]
    )
    assert cli_module._cmd_draw_lint(args) == 1
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["netlist"]["provided"] is True
    assert report["netlist"]["predicates"]["L12-two-pin-same-net"] == 1
    assert report["netlist"]["predicates"]["L12-ground-supply-pin-short"] == 1
    printed = capsys.readouterr().out
    assert "netlist" in printed.lower()

    args = parser.parse_args(
        ["draw", "lint", "--snapshot", str(snap), "--netlist", str(broken)]
    )
    assert cli_module._cmd_draw_lint(args) == 2

    args = parser.parse_args(
        ["draw", "lint", "--snapshot", str(snap), "--netlist", str(tmp_path / "absent.json")]
    )
    assert cli_module._cmd_draw_lint(args) == 2
