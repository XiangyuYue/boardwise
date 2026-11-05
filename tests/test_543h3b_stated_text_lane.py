"""543H-3B: a stated `partTexts` side keeps its reading direction.

`spec_v1` + `partTexts.C1 = "right"` asks C1's designator and value to print to
the **right** of the capacitor, in the lane between C1 and C2, away from R1's
value row (the pair sat 4.99 units apart, face to face, on the H2 page).
Measured: C1's extent ends at `x = 358.5`, C2's body starts at `x = 401.5` — a
lane 43 units wide — while the first standard rung needs `TEXT_GAP 8 + "100nF"
37 = 45`. Every standard rung was blocked by C2's body, so the declaration fell
back to the *left*: the statement was inert and the face-off stayed.

The rule pinned here (543H-3B): under `textPlacement: native-attr`, when every
standard rung of a **stated** side is blocked, the standoff is tightened before
the side is abandoned — widest first, never shrinking the text, never closer
than S-21's two units, and `None` (the historical ladder, unchanged) when even
the floor does not fit.

Two different "old page" contracts are pinned here, and they are not the same
statement:

* **Undefined text, native page** — dropping the C1 statement from a
  `native-attr` payload leaves C1 on the historical ladder (its rounded rows on
  the symbol's own left side). That ladder never changed.
* **Non-native page** — without `textPlacement: native-attr` the tightened tier
  never runs, so each non-native scene keeps its own full-page geometry, pinned
  by its own digest below. `legacy` and `legacy_bare` differ from each other (a
  stated `partTexts` entry still routes through the non-native ladder), and what
  is contracted is that neither digest moves.

Page geometry and the C1 ladder are separate facts: 543J's parallel-decoupling
co-grounding is a native opt-in geometry change (it moves the native page digest
while this file's standoff rule is untouched), and it must not touch either
non-native page.

The payload below is `evidence/543g_skill_trial/spec_v1.json` with only
`partTexts.C1 = "right"` added — C2 is deliberately **not** declared (its symbol
already draws its rows on the right; declaring it switched the row model and
reflowed the page by 15 units for nothing, 543H-3).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawapply
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
CIRCUIT_PATH = SPECS / "ch343_uart_534a.circuit.json"
LIBRARY_PATH = SPECS / "ch343_uart_v4.library.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)

#: The page `spec_v1` compiles to on this tree (`evidence/543h1b/page/cand1.page.json`,
#: reproduced byte for byte by `draw compile --page-box 0,0,1170,825`).
#: 543I-4B contract upgrade: one ground flag's anchor moved from 702.5 to 700
#: (the local lattice pass), so the page digest moved with that one symbol.
#: 543I-4A contract upgrade: a `native` part row is a **baseline-left** box one
#: row below the reserved centre (the host's own model), so the supply rail that
#: ran there moved; the page moved with it and the digest was re-read.
#: 543I-2D contract upgrade: the P32 page's flag groups are now decided by the
#: walking rule (ground and power alike), so the page moved and the digest with
#: it. What this file pins — the tightened standoff — is unchanged; the measured
#: boxes below were re-read on the new page.
#: 543I contract upgrade: a name per **non-continuous** run under
#: `native-attr` + `serviceLayout` (P32 was withdrawn for hiding `B6`/`B7`), so
#: the reversible `D+`/`D-` runs each keep a visible name and the page digest
#: moved with that statement. The tightened standoff this test pins is unchanged.
#: 543I contract upgrade: the `LED_A` tap is stated by `directWiringObligations`
#: as one island-local conductor, so its stub and printed name are gone and the
#: indicator island's own frame narrowed (the page digest moved with it). The
#: tightened standoff this test pins is unchanged.
#: 543J contract upgrade: parallel-decoupling branches that share both nets are
#: now allowed into one ground cluster (a stated, opt-in co-grounding), so the
#: native page digest moved from
#: `8ac92853924e6d8ba950dff8a3aa8f6abcd857370698a8b6176263db93fd3837` to the
#: value below — the same digest that comes back when the branch threshold is
#: >1. That is an intentional native-only geometry change: the text-tightening
#: contract in this file is unchanged, and both non-native digests below stay
#: byte-identical.
#: 543K contract upgrade: an opt-in **signal** pair is drawn as two horizontal
#: parts (the Type-C sink pair), and the bay is laid inside out so the pair keeps
#: the inner band — the bulk pair behind it moved 50 out. Both keys are the same
#: opt-in this file already carries, so the native page digest moved and the two
#: non-native digests below are still untouched.
#: 543L contract upgrade: `B6`/`B7` — one mirrored pair of the same
#: `localLabelObligations` entry — are chosen together and both carry the 60-unit
#: run (`B7` used to stop at 55), so the native page digest moved again. The
#: tightening contract in this file is unchanged, and both non-native digests
#: below stay byte-identical (the pairing is `native-attr` only).
SPEC_V1_PAGE_SHA = "1a9d231069026f1c0513daf41d5dd5a34fe6198fca85c9099f9f7dd92f25d2ef"

#: Full-page digests of the **non-native** scenes. They differ from each other
#: (a stated `partTexts` entry still reaches the non-native ladder) and neither
#: is allowed to move: 543J is a native opt-in and has no business here.
LEGACY_PAGE_SHA = "d1fd62a77009e1e4cdb2ff5263c618a56fe909519679db350b4b9a995c06a23a"
LEGACY_BARE_PAGE_SHA = "5f0f670ed11bed50078db6b0cb800cceb1d1bcc97afeec2e18ed6a3857965b8b"

PAYLOAD = {
    "kind": "boardwise-presentation-spec",
    "specVersion": 1,
    "grammarRef": "ic-periphery",
    "textPlacement": "native-attr",
    "sidePreferences": {
        "input": "left",
        "output": "right",
        "load": "left",
        "source": "left",
        "power": "top",
        "gnd": "bottom"
    },
    "portRoles": {
        "D+": "load",
        "D-": "load",
        "VCC": "input",
        "TXD": "output",
        "RXD": "input",
        "RTS": "output",
        "CTS": "input",
        "DTR": "output",
        "DSR": "input",
        "DCD": "input",
        "RI": "input"
    },
    "flow": [
        [
            "usb_c",
            "ch343"
        ],
        [
            "ch343",
            "hdr"
        ]
    ],
    "modules": [
        {
            "id": "usb_c",
            "parts": [
                "USB1",
                "C1",
                "C2",
                "R1",
                "R2"
            ],
            "role": "USB-C receptacle, VBUS bulk/decoupling and CC sink pull-downs",
            "grammarRef": "ic-periphery",
            "core": "USB1",
            "presentation": {
                "sidePreferences": {
                    "load": "right"
                }
            }
        },
        {
            "id": "ch343",
            "parts": [
                "U1",
                "C3",
                "C4"
            ],
            "role": "CH343 USB-UART bridge with V3 and VCC decoupling",
            "grammarRef": "ic-periphery",
            "core": "U1",
            "presentation": {
                "sidePreferences": {
                    "load": "left"
                }
            }
        },
        {
            "id": "hdr",
            "parts": [
                "H1"
            ],
            "role": "2x5 UART header to the peer board",
            "grammarRef": "ic-periphery",
            "core": "H1",
            "presentation": {
                "sidePreferences": {
                    "input": "left",
                    "output": "left"
                }
            }
        },
        {
            "id": "led",
            "parts": [
                "D1",
                "R3"
            ],
            "role": "VBUS presence indicator",
            "grammarRef": "voltage-divider",
            "attach": {
                "to": "usb_c",
                "side": "bottom",
                "gap": 10
            }
        }
    ],
    "labelPolicy": {
        "local": "wire",
        "crossModule": "label",
        "highFanout": "label",
        "stub": "straight",
        "stubMin": 40,
        "rowModel": "centered"
    },
    "directWiringObligations": [
        {
            "nets": [
                "LED_A"
            ],
            "note": "lamp cathode and R3 are one conductor inside the indicator island"
        }
    ],
    "localLabelObligations": [
        {
            "nets": [
                "D+",
                "D-"
            ],
            "note": "Type-C data pins are mirrored pairs (A6/B6, A7/B7): each pin takes its own short stub and the same-named label instead of a U-line that would present one pin as the other; the pair reaches U1.5/U1.6 by name"
        }
    ],
    "moduleOrder": [
        "usb_c",
        "ch343",
        "hdr",
        "led"
    ],
    "flagLeadLimit": 120,
    "partTexts": {
        "USB1": "left",
        "U1": "above",
        "H1": "above",
        "C3": "right",
        "C4": "right",
        "C1": "right"
    },
    "gndClustering": {
        "radius": 100
    },
    "serviceLayout": {
        "pinGap": 30
    }
}

CIRCUIT = CircuitSpec.load(CIRCUIT_PATH)
PROFILES = {
    item["symbolRef"]: SymbolProfile.from_dict(item)
    for item in json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))["profiles"]
}


def payload_without_c1() -> dict:
    body = copy.deepcopy(PAYLOAD)
    body["partTexts"].pop("C1", None)
    return body


def compile_page(body: dict):
    spec = PresentationSpec.from_dict(body)
    result = pc.compile_page(CIRCUIT, spec, PROFILES, pc.PageCompileBudget(page_box=PAGE_BOX))
    assert result.ok and result.pages, result
    return result.pages[0]


def c1_rows(page):
    return {
        text.kind: tuple(text.bbox) for text in page.plan.texts if text.part_id == "C1"
    }


def test_the_declared_side_takes_the_widest_legal_standoff():
    """The lane is 43 wide and the standard rung needs 45: tighten to 6, keep right."""
    page = compile_page(PAYLOAD)
    rows = c1_rows(page)
    part = next(item for item in page.plan.parts if item.part_id == "C1")
    profile = PROFILES[part.symbol_ref]
    extent = dc._part_box(profile, dc.SymbolPose(int(part.rotation), part.mirror), (part.x, part.y))

    value = rows["value"]
    assert value[0] == pytest.approx(extent[2] + dc.TEXT_GAP_TIGHTENED[0])
    # 543I-4A: the usb_c pair moved 40 units right (the +5V run clears the
    # printed row); the value row keeps its 6-unit standoff from C2 body edge.
    # 543K: the inside-out bay moved the bulk pair 50 more (the sink pair now
    # takes the inner band), so the row's right edge follows C2 to 451.5.
    assert value[2] == pytest.approx(451.5)
    assert value[2] <= 451.5 + 1e-9
    assert rows["reference"][0] == pytest.approx(value[0])
    assert value[0] > part.x and rows["reference"][0] > part.x


def test_the_tightening_never_overlaps_and_stops_at_the_floor():
    part = (341.5, 630.0, 358.5, 660.0)
    lines = ["C1", "100nF"]
    blocked = [(401.5, 620.0, 418.5, 660.0)]
    boxes = dc._tightened_side_boxes(part, lines, "right", blocked)
    assert boxes is not None
    for box in boxes:
        for other in blocked:
            assert not dc._overlaps(box, other)
    assert min(box[0] for box in boxes) == pytest.approx(358.5 + dc.TEXT_GAP_TIGHTENED[0])

    # Two units narrower and even the floor would land inside C2's body:
    # no seat, and the caller's historical ladder runs instead.
    assert dc._tightened_side_boxes(part, lines, "right", [(396.0, 620.0, 418.5, 660.0)]) is None
    assert min(dc.TEXT_GAP_TIGHTENED) >= dc.TEXT_GAP_FLOOR == 2.0


def test_an_undeclared_part_and_a_non_native_page_keep_the_old_ladder():
    baseline = compile_page(payload_without_c1())
    assert baseline.page_geometry_sha256() == SPEC_V1_PAGE_SHA
    left = c1_rows(baseline)
    # 543I-4A moved the usb_c pair 40 units right (the +5V run had to clear the
    # printed row); the row still sits on the symbol's own left side.
    # 543K: the inside-out bay moved that pair 50 more, so the bound follows it.
    assert left["reference"][2] < 430.0

    # Without `textPlacement: native-attr` the tightened tier does not run at
    # all: declaring C1 or leaving it undeclared gives the same C1 rows. Each
    # scene's full-page digest is pinned separately below.
    legacy = copy.deepcopy(PAYLOAD)
    legacy.pop("textPlacement")
    legacy_bare = copy.deepcopy(legacy)
    legacy_bare["partTexts"].pop("C1")
    page = compile_page(legacy)
    bare = compile_page(legacy_bare)
    assert c1_rows(page) == c1_rows(bare)
    assert c1_rows(page)["value"][0] != pytest.approx(364.5)

    # 543J is a native opt-in: the co-grounding that moved the native digest
    # must leave each non-native page exactly where it was. The two digests are
    # pinned separately (they are not equal, and that is contracted too).
    assert page.page_geometry_sha256() == LEGACY_PAGE_SHA
    assert bare.page_geometry_sha256() == LEGACY_BARE_PAGE_SHA


def test_the_statement_moves_no_other_part_and_no_module():
    baseline = compile_page(payload_without_c1())
    page = compile_page(PAYLOAD)
    assert [(m.id, m.origin) for m in page.modules] == [(m.id, m.origin) for m in baseline.modules]
    for before, after in zip(baseline.plan.parts, page.plan.parts):
        assert (before.part_id, before.x, before.y) == (after.part_id, after.x, after.y)


def test_the_page_keeps_its_machine_facts():
    page = compile_page(PAYLOAD)
    plan = drawapply.module_plan(
        page.plan, CIRCUIT, PresentationSpec.from_dict(PAYLOAD), PROFILES,
        candidate_index=0, label_stubs=True, page_box=PAGE_BOX,
        module_label="page " + "+".join(module.id for module in page.modules),
    )
    parts = {item.part_id: item for item in page.plan.parts}
    assert (parts["R1"].x, parts["R1"].rotation, parts["R1"].mirror) == (
        parts["R2"].x, parts["R2"].rotation, parts["R2"].mirror
    )

    wires = plan.change.draw_wires
    for net in ("CC1", "CC2"):
        runs = [wire for wire in wires if str(wire.net) == net]
        assert len(runs) == 1 and len(runs[0].points) == 2

    c1 = next(t for t in page.plan.texts if t.part_id == "C1" and t.kind == "value")
    c2 = next(t for t in page.plan.texts if t.part_id == "C2" and t.kind == "value")
    assert c1.bbox[0] > parts["C1"].x and c2.bbox[0] > parts["C2"].x

    moves = {m.wire_index: m for m in plan.change.attribute_moves if m.owner_kind == "wire"}
    for index, move in moves.items():
        if getattr(move, "move_version", 1) == 2:
            continue
        if str(wires[index].net) == "RXD":
            xs = [float(point[0]) for point in wires[index].points]
            assert min(xs) - 1e-9 <= move.x <= max(xs) + 1e-9
            break
    else:
        pytest.fail("no visible RXD carrier")


def test_no_two_text_rows_intersect():
    page = compile_page(PAYLOAD)
    rows = [tuple(t.bbox) for t in page.plan.texts]
    rows += [tuple(label.bbox) for label in page.plan.labels if getattr(label, "text_mode", "") != "native-hidden"]
    for index, first in enumerate(rows):
        for second in rows[index + 1:]:
            assert not dc._overlaps(first, second), (first, second)
