"""543F-2: the **final ChangePlan** has to stand inside the sheet.

543F landed P30 from this same drawing and the host called it illegal: the CC
island's `CC1` name stub left `R1.1` at `(35, 440)` and ran to `(-5, 440)` — five
units off the left edge of `0,0,1170,825` (`draw lint` L10, host DRC
`OBJECTOUTSIDESHEET`). The LayoutPlan is legal; the stub is added on the landing
path (`drawapply.module_plan(..., label_stubs=True)`), so a test that only reads
the compiled drawing cannot see it. These tests read the thing that lands.

The payload is 543D's effective specification, written inline for the same
reason `test_543d_label_layout.py` writes it: a test must not depend on an
evidence directory.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawapply
from boardwise.engines import pagecompiler as pc

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT_PATH = ROOT / "blocklib" / "specs" / "ch343_uart_534a.circuit.json"
LIBRARY_PATH = ROOT / "blocklib" / "specs" / "ch343_uart_v4.library.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)
#: The page the pre-fix build produced for the *same* payload with the straight
#: stub policy stated as `auto`: the reservation this batch adds must not move a
#: drawing that never asked for the straight stub (`v42` states `stubMin` but no
#: `stub`, so this is also its shape).
#: 543I contract upgrade: this payload states `serviceLayout` and `native-attr`,
#: so the reversible `D+`/`D-` runs now each print their own name (P32 was
#: withdrawn for the opposite rule) and the digest moved with that statement.
#: 543I-6I/J: the digest moved twice more, and each move is classified here —
#: (a) 543I-6I put the part-row ATTR target and the 543I-4A ink on one anchor
#: (`textmetrics.host_row_box`'s lower-left), so a supply run took the room that
#: changed; (b) 543I-6J keeps a carrier's name box on the carrier's **own side**
#: instead of printing it centred over the far end (`D+`'s second run ended at
#: `x = 265` with its row at `258..272`). The straight-stub question this test
#: pins is unchanged, and that is checked, not assumed: on this payload every
#: label still states `stub='auto'` (27 of 27), so nothing here is the straight
#: policy leaking into a document that did not ask for it.
#: 543I-6K: a candidate that prints a local name **centred on its own
#: carrier end** is now refused (`_riding_label_failure`), so this payload
#: lands the sibling page it already had (`D+`/`D-` off their anchors); the
#: stub field is still `auto` on every label (27/27, probe in
#: `evidence/543i6k`).
#: 543I (LED) contract upgrade: this payload states `directWiringObligations` for
#: `LED_A`, so its tap stub and printed name are gone and the indicator island's
#: frame narrowed; the page digest moved with that statement. What this test
#: pins — a document that states no straight stub is untouched by the straight-
#: stub policy — is unchanged, and the stub fields are still `auto` on every
#: label.
_BASELINE_WITHOUT_STRAIGHT_STUB = (
    "3320ee054d49281a64464030901c3f7fba0fc84ccc3b0749a418c76c607a7d7e"
)

MODULES = [
    {"id": "usb_c", "parts": ["USB1", "C1", "C2"],
     "role": "USB receptacle + +5V decoupling", "grammarRef": "ic-periphery",
     "core": "USB1",
     "presentation": {"sidePreferences": {"load": "right"}}},
    {"id": "ch343", "parts": ["U1", "C3", "C4"], "role": "CH343 core",
     "grammarRef": "ic-periphery", "core": "U1",
     "presentation": {"sidePreferences": {"load": "left"}}},
    {"id": "cc", "parts": ["R1", "R2"], "role": "CC pull-downs",
     "grammarRef": "ic-periphery"},
    {"id": "hdr", "parts": ["H1"], "role": "header", "grammarRef": "ic-periphery",
     "core": "H1"},
    {"id": "led", "parts": ["D1", "R3"], "role": "indicator",
     "grammarRef": "voltage-divider"},
]
PORT_ROLES = {
    "D+": "load", "D-": "load", "VCC": "input", "TXD": "output", "RXD": "input",
    "RTS": "output", "CTS": "input", "DTR": "output", "DSR": "input",
    "DCD": "input", "RI": "input",
}
PAYLOAD = {
    "grammarRef": "ic-periphery",
    "textPlacement": "native-attr",
    "sidePreferences": {
        "input": "left", "output": "right", "load": "left", "source": "left",
        "power": "top", "gnd": "bottom",
    },
    "portRoles": PORT_ROLES,
    "flow": [["usb_c", "ch343"], ["ch343", "hdr"]],
    "modules": MODULES,
    "labelPolicy": {
        "local": "wire", "crossModule": "label", "highFanout": "label",
        "stub": "straight", "stubMin": 40, "rowModel": "centered",
    },
    "directWiringObligations": [
        {"nets": ["LED_A"], "note": "the lamp and R3 are one conductor inside usb_c"}
    ],
    "localLabelObligations": [
        {"nets": ["D+", "D-"],
         "note": "the Type-C mirrored data pins are named on each pin instead of "
                 "being joined by a U-line"}
    ],
    "moduleOrder": ["usb_c", "ch343", "cc", "hdr", "led"],
    "moduleColumns": 2,
    "flagLeadLimit": 120,
    "partTexts": {
        "USB1": "left", "H1": "above", "U1": "above", "C3": "right",
        "C4": "right",
    },
    "gndClustering": {"radius": 100},
    "serviceLayout": {"pinGap": 30},
}

BOOK = {
    item["symbolRef"]: SymbolProfile.from_dict(item)
    for item in json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))["profiles"]
}
CIRCUIT = CircuitSpec.load(CIRCUIT_PATH)


def _presentation(payload: dict | None = None) -> PresentationSpec:
    return PresentationSpec.from_dict(copy.deepcopy(payload or PAYLOAD))


def _page(payload: dict | None = None):
    result = pc.compile_page(
        CIRCUIT, _presentation(payload), BOOK,
        pc.PageCompileBudget(page_box=PAGE_BOX),
    )
    assert result.ok, result.render_failures()
    assert result.pages
    return result.pages[0]


def _plan(page, payload: dict | None = None) -> drawapply.ChangePlan:
    return drawapply.module_plan(
        page.plan, CIRCUIT, _presentation(payload), BOOK,
        candidate_index=0,
        label_stubs=True,
        module_label="page " + "+".join(module.id for module in page.modules),
        page_box=PAGE_BOX,
    )


def _wires(plan) -> list:
    return list(plan.change.draw_wires)


def _outside(points) -> list[tuple[float, float]]:
    return [
        (float(x), float(y)) for x, y in points
        if not (
            PAGE_BOX[0] - 1e-6 <= float(x) <= PAGE_BOX[2] + 1e-6
            and PAGE_BOX[1] - 1e-6 <= float(y) <= PAGE_BOX[3] + 1e-6
        )
    ]


def _net_wire(plan, net: str, from_pin: str = ""):
    for wire in _wires(plan):
        if wire.net != net:
            continue
        if from_pin and wire.from_pin != from_pin:
            continue
        return wire
    return None


def test_every_change_plan_wire_endpoint_is_on_the_sheet():
    """The landing path, not the compiled drawing: every stub, every point."""
    plan = _plan(_page())
    offenders = [
        (wire.net, wire.from_pin, [tuple(point) for point in wire.points])
        for wire in _wires(plan)
        if _outside(wire.points)
    ]
    assert not offenders, f"wires leave {PAGE_BOX}: {offenders}"


def test_the_cc_name_stub_is_built_inside_the_page():
    """P30's exact defect: `CC1` at `R1.1` ran to `(-5, 440)`."""
    plan = _plan(_page())
    wire = _net_wire(plan, "CC1", "R1.1")
    assert wire is not None, "R1's CC1 name stub is missing from the plan"
    assert not _outside(wire.points), [tuple(point) for point in wire.points]
    other = _net_wire(plan, "CC2", "R2.1")
    assert other is not None and not _outside(other.points)


def test_service_lines_and_data_directions_survive():
    """543B/C/D must not be traded away for the page bound."""
    page = _page()
    plan = _plan(page)

    v3 = _net_wire(plan, "V3", "C3.1")
    assert v3 is not None
    points = [tuple(map(float, point)) for point in v3.points]
    assert len(points) == 2, points
    assert points[0][1] == points[1][1], f"the V3 service line is not one row: {points}"
    assert abs(points[0][0] - points[1][0]) == 30.0, points
    c4 = _net_wire(plan, "VCC", "U1.15")
    assert c4 is not None
    points = [tuple(map(float, point)) for point in c4.points]
    assert len(points) == 2, points
    assert points[0][1] == points[1][1], f"the VCC service line is not one row: {points}"
    assert abs(points[0][0] - points[1][0]) == 30.0, points

    labels = {
        (label.net, label.part_id): label for label in page.plan.labels
        if label.net in ("D+", "D-") and getattr(label, "text_mode", "") != "native-hidden"
    }
    for net in ("D+", "D-"):
        usb = labels[(net, "USB1")]
        ch = labels[(net, "U1")]
        assert (usb.bbox[0] + usb.bbox[2]) / 2 > usb.x, f"{net} at USB1 is not right of its pin"
        assert (ch.bbox[0] + ch.bbox[2]) / 2 < ch.x, f"{net} at U1 is not left of its pin"


def test_straight_stub_policy_off_keeps_the_pre_fix_page():
    """Negative control: a document that states no straight stub is untouched."""
    payload = copy.deepcopy(PAYLOAD)
    payload["labelPolicy"]["stub"] = "auto"
    page = _page(payload)
    assert page.page_geometry_sha256() == _BASELINE_WITHOUT_STRAIGHT_STUB


def test_default_call_keeps_the_old_stub_wrapper_surface(monkeypatch):
    """A caller that states no sheet sees the pre-543F five-parameter shape.

    `page_box` is an extra fact, and a wrapper written against the old signature
    (`label, built, bodies, pins, label_boxes=()`) must keep working: a default
    plan may not pass the keyword at all. `test_099d` monkeypatches exactly that
    shape, so this is the same surface.
    """
    original = drawapply._place_label_stub
    calls: list[str] = []

    def old_signature(label, built, bodies, pins, label_boxes=()):
        calls.append(str(label.net))
        return original(label, built, bodies, pins, label_boxes=label_boxes)

    monkeypatch.setattr(drawapply, "_place_label_stub", old_signature)
    page = _page()
    plan = drawapply.module_plan(
        page.plan, CIRCUIT, _presentation(), BOOK,
        candidate_index=0,
        label_stubs=True,
        module_label="page " + "+".join(module.id for module in page.modules),
    )
    assert calls, "the old-signature wrapper was never used"
    assert plan.change.draw_wires


def test_explicit_page_box_reaches_the_stub_placer(monkeypatch):
    """A stated sheet is handed down, and the run it permits stays on it."""
    original = drawapply._place_label_stub
    seen: list[dict] = []

    def wrapper(*args, **kwargs):
        seen.append(dict(kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(drawapply, "_place_label_stub", wrapper)
    plan = _plan(_page())
    assert seen, "no label asked the stub placer"
    assert all(call.get("page_box") == PAGE_BOX for call in seen), seen
    offenders = [
        (wire.net, wire.from_pin, [tuple(point) for point in wire.points])
        for wire in _wires(plan)
        if _outside(wire.points)
    ]
    assert not offenders, offenders
