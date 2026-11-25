"""565g — the L12 / rail-name holes S2-H3/H4/H5/H6 of ``engines.drawlint``.

Every fixture here is built in memory from the same shapes
``outputs/hole565/s2/probes/probe_s2.py`` replays, so a test fails exactly when
the predicate's reading does.  Deliberately **no** ``tmp_path``: this host's
CPython 3.14 turns ``os.mkdir(mode=0o700)`` into a real DACL the sandbox cannot
list, so the fixture would fail for reasons that have nothing to do with the
predicate.  No daemon, no editor, no network, no files.

One causal case per hole (S2-H3/H4/H5/H6), each red before the fix, plus the
negative controls that keep the fix from becoming "report everything":

* H3 — a two-pin part is shorted by its *nets*, not by its pin names (A/K,
  ``1.1/1.2``), and a >2-pin passive whose pins are all numeric is read too;
  a named-pin multi-pin device stays out of the two-pin gate and keeps
  ``L12-ground-supply-pin-short``.
* H4 — one net identity inside L12 is ``strip().upper()`` (three places: the
  two-pin set, the per-net grouping, the netlist membership test), while the
  message keeps the netlist's own spelling.
* H5 — the rail vocabulary carries ``HVDC`` and ``SEC_\\d+V\\d*`` (AGENTS'
  drawing red line names them), and only those two.
* H6 — a flag's own name glyph is exempt only when its text *is* that flag's
  net; a different rail name beside a flag is a real conflict.
"""

from __future__ import annotations

import json

from boardwise.engines import drawlint

BLUE = drawlint.FILL_VALUE


# --------------------------------------------------------------------- builders
def sheet_box() -> dict:
    return {
        "primitiveId": "sheet1",
        "state": {
            "PrimitiveType": "Component",
            "ComponentType": "sheet",
            "PrimitiveId": "sheet1",
        },
    }


def part(designator: str, x: float = 700, y: float = 780) -> dict:
    primitive = f"part-{designator}"
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


def flag(net: str, x: float, y: float) -> dict:
    primitive = f"flag-{net}-{x}-{y}"
    return {
        "primitiveId": primitive,
        "state": {
            "PrimitiveType": "Component",
            "ComponentType": "netflag",
            "PrimitiveId": primitive,
            "X": x,
            "Y": y,
            "Rotation": 0,
            "Net": net,
        },
    }


def wire(primitive: str, net: str, *points: float) -> dict:
    return {
        "primitiveId": primitive,
        "state": {
            "PrimitiveType": "Wire",
            "PrimitiveId": primitive,
            "Net": net,
            "Line": list(points),
        },
    }


def snapshot(*components: dict, wires: list[dict] | None = None) -> dict:
    return {
        "components": [sheet_box(), *components],
        "wires": wires or [],
        "pins": [],
        "netlabels": [],
        "bboxes": {"sheet1": {"minX": 0, "minY": 0, "maxX": 1170, "maxY": 825}},
        "meta": {"sheets": ["sheet1"]},
    }


def text_node(x: float, y_svg: float, text: str) -> str:
    return (
        f'<text style="font-family:\'Arial\';font-size:7.148342059336824px;'
        f'font-style:normal;font-weight:normal;fill:{BLUE};stroke:none;"'
        f' x="{x}" y="{y_svg}" text-anchor="start" '
        f'transform="rotate(0, {x}, {y_svg})" '
        f'dominant-baseline="ideographic"><tspan xml:space="preserve" '
        f'x="{x}" dx="0" dy="0">{text}</tspan></text>'
    )


def svg(*nodes: str) -> str:
    return "<svg>" + "".join(nodes) + "</svg>"


def netlist_doc(components: dict[str, dict[int, tuple[str, str]]]) -> dict:
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


# ---------------------------------------------------------------------- helpers
def lint(snapshot_doc, svg_doc=None, **kwargs):
    return drawlint.run_lint(snapshot_doc, svg_doc, **kwargs)


def hits(findings, predicate: str) -> list:
    return [finding for finding in findings if finding.predicate == predicate]


# ---------------------------------------------------------------- S2-H3 (pin shape)
def test_h3_two_pin_named_ak_same_net_is_reported():
    """A diode's ``A``/``K`` both on one net is a short, not a legal part."""
    doc = netlist_doc({"D1": {1: ("A", "VBUS"), 2: ("K", "VBUS")}})
    found = hits(lint(snapshot(), netlist=doc), "L12-two-pin-same-net")
    assert len(found) == 1
    assert "D1" in found[0].message and "VBUS" in found[0].message


def test_h3_two_pin_dotted_names_same_net_is_reported():
    """``1.1``/``1.2`` is the same two-terminal shape as ``1``/``2``."""
    doc = netlist_doc({"D4": {1: ("1.1", "VBUS"), 2: ("1.2", "VBUS")}})
    found = hits(lint(snapshot(), netlist=doc), "L12-two-pin-same-net")
    assert len(found) == 1
    assert "D4" in found[0].message


def test_h3_three_pin_passive_with_two_ends_on_one_net_is_reported():
    """A power package carrying a third pin is still one shorted two-terminal part."""
    doc = netlist_doc(
        {"C10": {1: ("1", "VBUS"), 2: ("2", "VBUS"), 3: ("3", "GND")}}
    )
    found = hits(lint(snapshot(), netlist=doc), "L12-two-pin-same-net")
    assert len(found) == 1
    assert "C10" in found[0].message
    assert "VBUS" in found[0].message


def test_h3_named_multipin_device_stays_out_of_the_two_pin_gate():
    """A named-pin IC is not a passive: its VDD/VSSAA pair is the supply gate's case."""
    doc = netlist_doc(
        {
            "U1": {
                1: ("VDD", "+3V3"),
                2: ("VSSA", "+3V3"),
                3: ("PB0", "LED_A"),
                4: ("PB1", "GND"),
            }
        }
    )
    findings = lint(snapshot(), netlist=doc)
    assert hits(findings, "L12-two-pin-same-net") == []
    assert len(hits(findings, "L12-ground-supply-pin-short")) == 1


# ---------------------------------------------------------------- S2-H4 (net case)
def test_h4_a_lowercase_flag_and_an_uppercase_netlist_agree():
    """The page side already upper-cases; L12 must not call this a disagreement."""
    page = snapshot(flag("gnd", 100, 120), wires=[wire("w1", "GND", 100, 100, 160, 100)])
    doc = netlist_doc({"U1": {8: ("VSSA", "GND")}})
    assert hits(lint(page, netlist=doc), "L12-ground-flag-absent-from-netlist") == []


def test_h4_two_pin_different_spellings_are_one_net():
    page = snapshot()
    doc = netlist_doc({"C9": {1: ("1", "GND"), 2: ("2", "gnd")}})
    found = hits(lint(page, netlist=doc), "L12-two-pin-same-net")
    assert len(found) == 1
    assert "C9" in found[0].message
    # the message keeps the netlist's own spelling, it does not print an invention
    assert "GND" in found[0].message


def test_h4_supply_pin_short_groups_nets_case_insensitively():
    doc = netlist_doc({"U1": {1: ("VDD", "+3v3"), 2: ("VSS", "+3V3")}})
    found = hits(lint(snapshot(), netlist=doc), "L12-ground-supply-pin-short")
    assert len(found) == 1
    assert "U1" in found[0].message


def test_h4_ground_flag_still_fires_when_the_netlist_has_no_such_net():
    """Negative control: normalisation must not silence the real disagreement."""
    page = snapshot(flag("GND", 100, 120), wires=[wire("w1", "GND", 100, 100, 160, 100)])
    doc = netlist_doc({"U1": {8: ("VSSA", "+3V3")}})
    found = hits(lint(page, netlist=doc), "L12-ground-flag-absent-from-netlist")
    assert len(found) == 1
    assert "GND" in found[0].message


# ------------------------------------------------------------------ S2-H5 (rails)
def test_h5_agents_supply_names_are_power_rails():
    assert drawlint._rail_kind("HVDC") == "Power"
    assert drawlint._rail_kind("SEC_12V") == "Power"
    assert drawlint._rail_kind("SEC_5V0") == "Power"
    assert drawlint._rail_kind("GND") == "Ground"


def test_h5_only_the_two_named_families_were_added():
    """The vocabulary is widened by the two AGENTS names, not by whatever looks like one."""
    assert drawlint._rail_kind("VIN") == ""
    assert drawlint._rail_kind("3V3") == ""
    assert drawlint._rail_kind("SEC_12") == ""


def test_h5_hvdc_and_secondary_wires_without_a_flag_are_reported():
    page = snapshot(
        wires=[
            wire("wHVDC", "HVDC", 100, 100, 160, 100),
            wire("wSEC", "SEC_12V", 100, 200, 160, 200),
        ]
    )
    found = hits(lint(page), "L11-rail-without-flag")
    assert {finding.objects[0] for finding in found} == {"HVDC", "SEC_12V"}


def test_h5_a_flagged_hvdc_rail_is_silent():
    """Negative control: the flag is the legal shape, so widening must spare it."""
    page = snapshot(
        flag("HVDC", 100, 120),
        flag("SEC_12V", 100, 220),
        wires=[
            wire("wHVDC", "HVDC", 100, 100, 160, 100),
            wire("wSEC", "SEC_12V", 100, 200, 160, 200),
        ],
    )
    assert hits(lint(page), "L11-rail-without-flag") == []


# -------------------------------------------------------------- S2-H6 (near flag)
def test_h6_a_different_rail_name_beside_a_flag_is_a_real_conflict():
    """Causal case: the flag sits 8 units from the ``+5V`` label, but its text is GND."""
    page = snapshot(flag("GND", 125, 108), wires=[wire("w1", "GND", 100, 100, 200, 100)])
    render = svg(text_node(125, -100, "+5V"), text_node(150, -100, "GND"))
    found = hits(lint(page, render), "L5-wire-rail-conflict")
    assert len(found) == 1
    assert "+5V" in found[0].message and "GND" in found[0].message


def test_h6_the_same_conflict_far_from_a_flag_still_reports():
    """Negative control kept from the probe: distance was never the only evidence."""
    page = snapshot(flag("GND", 700, 700), wires=[wire("w1", "GND", 100, 100, 200, 100)])
    render = svg(text_node(125, -100, "+5V"), text_node(150, -100, "GND"))
    assert len(hits(lint(page, render), "L5-wire-rail-conflict")) == 1


def test_h6_a_glyph_that_is_the_flag_own_name_is_not_a_second_name():
    """Negative control: the exemption stays, or every flag would report itself."""
    page = snapshot(flag("GND", 100, 108), wires=[wire("w1", "GND", 100, 100, 400, 100)])
    render = svg(text_node(100, -100, "GND"), text_node(300, -100, "+5V"))
    assert hits(lint(page, render), "L5-wire-rail-conflict") == []


def test_h6_the_same_name_beyond_the_gap_counts_as_a_name():
    """Distance is the secondary bound: a same-name glyph far away is a statement."""
    page = snapshot(flag("GND", 100, 108), wires=[wire("w1", "GND", 100, 100, 400, 100)])
    render = svg(text_node(300, -100, "GND"), text_node(350, -100, "+5V"))
    assert len(hits(lint(page, render), "L5-wire-rail-conflict")) == 1
