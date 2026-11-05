"""543I-4A: a supply run may not print through a part's own `native` text row.

543I-3 landed P33 and `draw lint` refused it with one ERROR: `L1-text-on-wire`,
`'C21'` at (372, 742) crossed by a `+5V` run for 13 units. The rail was not
routed through a text on purpose — the compiler's obstacle table held the box it
had **reserved**, and the host does not draw that box: under `native-attr` the
row is printed from the reserved box's centre as a baseline-left anchor, so its
ink runs one row *down* and one render width right of that point. The +5V run
passed 3.5 units under the reservation and 3.5 units through the ink.

What this file pins (and what it refuses to accept):

* every part `reference`/`value` row's **printed** box (anchor + the host's own
  row model, :func:`textmetrics.host_row_box`) is crossed by **no** wire — the
  same segment-vs-box test `drawlint` L1 uses, with L1's own 10-unit threshold,
  applied to the final `ChangePlan`'s wires;
* the measured row that failed on the landed page — `C1`'s reference at
  (372, 742), with the 13-unit `+5V` penetration — is the case this fix answers:
  the run that used to sit at `y = 750` no longer crosses the row at all;
* 543I-1's reversible runs, 543I-2D's straight `CC1`/`CC2` and its local ground
  flags are unchanged: this batch moves the supply rail, not the drawing's
  subject.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.core import textmetrics
from boardwise.engines import drawapply
from boardwise.engines import pagecompiler as pc

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
CIRCUIT = CircuitSpec.load(SPECS / "ch343_uart_534a.circuit.json")
LIBRARY = {
    item["symbolRef"]: SymbolProfile.from_dict(item)
    for item in json.loads(
        (SPECS / "ch343_uart_v4.library.json").read_text(encoding="utf-8")
    )["profiles"]
}
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)
#: `evidence/543h3b/spec_h3b.json`, inline (a test may not read evidence).
PAYLOAD = {
    "kind": "boardwise-presentation-spec",
    "specVersion": 1,
    "grammarRef": "ic-periphery",
    "textPlacement": "native-attr",
    "sidePreferences": {
        "input": "left", "output": "right", "load": "left", "source": "left",
        "power": "top", "gnd": "bottom",
    },
    "portRoles": {
        "D+": "load", "D-": "load", "VCC": "input", "TXD": "output",
        "RXD": "input", "RTS": "output", "CTS": "input", "DTR": "output",
        "DSR": "input", "DCD": "input", "RI": "input",
    },
    "flow": [["usb_c", "ch343"], ["ch343", "hdr"]],
    "modules": [
        {
            "id": "usb_c", "parts": ["USB1", "C1", "C2", "R1", "R2"],
            "role": "USB-C receptacle, VBUS bulk/decoupling and CC sink pull-downs",
            "grammarRef": "ic-periphery", "core": "USB1",
            "presentation": {"sidePreferences": {"load": "right"}},
        },
        {
            "id": "ch343", "parts": ["U1", "C3", "C4"],
            "role": "CH343 USB-UART bridge with V3 and VCC decoupling",
            "grammarRef": "ic-periphery", "core": "U1",
            "presentation": {"sidePreferences": {"load": "left"}},
        },
        {
            "id": "hdr", "parts": ["H1"],
            "role": "2x5 UART header to the peer board",
            "grammarRef": "ic-periphery", "core": "H1",
            "presentation": {"sidePreferences": {"input": "left", "output": "left"}},
        },
        {
            "id": "led", "parts": ["D1", "R3"],
            "role": "VBUS presence indicator",
            "grammarRef": "voltage-divider",
            "attach": {"to": "usb_c", "side": "bottom", "gap": 10},
        },
    ],
    "labelPolicy": {
        "local": "wire", "crossModule": "label", "highFanout": "label",
        "stub": "straight", "stubMin": 40, "rowModel": "centered",
    },
    "directWiringObligations": [
        {"nets": ["LED_A"], "note": "lamp cathode and R3 are one conductor"}
    ],
    "localLabelObligations": [
        {"nets": ["D+", "D-"], "note": "Type-C mirrored data pairs named per pin"}
    ],
    "moduleOrder": ["usb_c", "ch343", "hdr", "led"],
    "flagLeadLimit": 120,
    "partTexts": {
        "USB1": "left", "U1": "above", "H1": "above", "C3": "right",
        "C4": "right", "C1": "right",
    },
    "gndClustering": {"radius": 100},
    "serviceLayout": {"pinGap": 30},
}


def _chord(a, b, box) -> float:
    """The chord of an axis-aligned segment **inside** the box.

    The same measurement `drawlint` L1 makes: the segment's own run, not its
    bounding box. A horizontal run at a y strictly inside the box counts the
    x-overlap; a run on the box's edge does not (touching ink is not printing
    through it).
    """
    if abs(a[1] - b[1]) < 1e-9:
        if not (box[1] < a[1] < box[3]):
            return 0.0
        low, high = sorted((a[0], b[0]))
        return max(0.0, min(high, box[2]) - max(low, box[0]))
    if abs(a[0] - b[0]) < 1e-9:
        if not (box[0] < a[0] < box[2]):
            return 0.0
        low, high = sorted((a[1], b[1]))
        return max(0.0, min(high, box[3]) - max(low, box[1]))
    return 0.0


@pytest.fixture(scope="module")
def compiled():
    result = pc.compile_page(
        CIRCUIT, PresentationSpec.from_dict(PAYLOAD), LIBRARY,
        pc.PageCompileBudget(page_box=PAGE_BOX),
    )
    assert result.ok, result.render_failures()
    page = result.pages[0]
    plan = drawapply.module_plan(
        page.plan, CIRCUIT, PresentationSpec.from_dict(PAYLOAD), LIBRARY,
        candidate_index=0, label_stubs=True, page_box=PAGE_BOX,
        module_label="page " + "+".join(module.id for module in page.modules),
    )
    texts = {}
    _layout_bbox.clear()
    for text in page.plan.texts:
        texts[(getattr(text, "part_id", ""), text.kind)] = text.text
        _layout_bbox[(getattr(text, "part_id", ""), text.kind)] = text.bbox
    return page, plan, texts


#: The row the layout reserved, per (part, kind) — the floor of the printed width.
_layout_bbox: dict[tuple[str, str], tuple[float, float, float, float]] = {}


def _printed_rows(plan, texts):
    rows = []
    for move in plan.change.attribute_moves:
        if getattr(move, "owner_kind", "") != "part":
            continue
        label = texts.get((move.spec_id, move.role), "")
        if not label:
            continue
        box = textmetrics.host_row_box((move.x, move.y), label)
        # The host prints the **pool's** designator (`C1` landed as `C21` on
        # P33), which is never narrower than the row the layout reserved; the
        # wider of the two is the ink a reader sees, so the check uses it.
        laid = _layout_bbox.get((move.spec_id, move.role))
        if laid is not None:
            box = (box[0], box[1], max(box[2], box[0] + (laid[2] - laid[0])), box[3])
        rows.append((move.spec_id, move.role, label, box))
    return rows


def test_no_wire_prints_through_a_part_row(compiled):
    _page, plan, texts = compiled
    rows = _printed_rows(plan, texts)
    assert rows, "the page states its part rows"
    assert len(rows) >= 10, f"the plan states {len(rows)} part rows"
    assert plan.change.draw_wires, "the plan states its wires"
    offenders = []
    for spec_id, role, label, box in rows:
        for wire in plan.change.draw_wires:
            points = [(float(p[0]), float(p[1])) for p in wire.points]
            for start, stop in zip(points, points[1:]):
                chord = _chord(start, stop, box)
                if chord >= 10.0:  # drawlint L1_TEXT_WIRE_PENETRATION
                    offenders.append(
                        (spec_id, role, label, box, str(wire.net), start, stop)
                    )
    assert offenders == [], offenders


def test_the_measurement_itself_sees_the_landed_p33_crossing():
    """The check is sensitive: the *landed* geometry must measure 13 units.

    `C21` printed at (372, 742) with a +5V run at y = 750 — the row's ink is
    `(372, 742)-(386, 752)`, so the run crosses it for 13 units, exactly the
    ERROR `draw lint` reported on P33. A test whose chord were computed from a
    segment's bounding box reads 0 here (a horizontal run has no height), which
    is why this counterexample is pinned separately: with a box narrower than
    L1's 10-unit threshold the whole file would pass while measuring nothing.
    """
    row = (372.0, 742.0, 386.0, 752.0)
    run = ((350.0, 750.0), (410.0, 750.0))
    assert _chord(run[0], run[1], row) == pytest.approx(14.0)
    assert _chord(*run, (372.0, 752.0, 386.0, 762.0)) == 0.0  # on the edge, not through
    assert _chord((380.0, 730.0), (380.0, 770.0), row) == pytest.approx(10.0)


def test_the_landed_p33_case_is_gone(compiled):
    """C1's reference at (372,742) with the 13-unit +5V penetration (543I-3)."""
    _page, plan, texts = compiled
    reference = [
        item for item in _printed_rows(plan, texts)
        if item[0] == "C1" and item[1] == "reference"
    ]
    assert reference, "C1's reference row is stated"
    box = reference[0][3]
    for wire in plan.change.draw_wires:
        if str(wire.net) != "+5V":
            continue
        points = [(float(p[0]), float(p[1])) for p in wire.points]
        for start, stop in zip(points, points[1:]):
            assert _chord(start, stop, box) == 0.0, (box, start, stop)


def test_the_subject_of_543i_is_unchanged(compiled):
    """543I-1's runs, 543I-2D's straight CC pair — this batch moved the rail only."""
    _page, plan, _texts = compiled
    runs = {}
    for wire in plan.change.draw_wires:
        points = [(round(float(p[0]), 1), round(float(p[1]), 1)) for p in wire.points]
        runs.setdefault(str(wire.net), []).append(points)
    for net in ("CC1", "CC2"):
        assert len(runs[net]) == 1 and len(runs[net][0]) == 2, runs[net]
        assert abs(runs[net][0][0][1] - runs[net][0][1][1]) < 1e-9, runs[net]
    spans = sorted(
        abs(points[0][0] - points[-1][0])
        for net in ("D+", "D-") for points in runs[net]
    )
    # 543L/543M: `B6`/`B7` are one mirrored pair of the same
    # `localLabelObligations` entry and the straight-stub contract draws both at
    # 60 (`55` was the pair drawn one rung apart). `CC1`/`CC2` keep their
    # horizontal two-point runs, undisturbed by that change.
    assert spans == [40.0, 40.0, 40.0, 40.0, 60.0, 60.0], spans
