"""543H-2: a visible `native` name prints on the stub the **final plan** draws.

The page compiled from `spec_v1` reserves `U1.RXD`'s name box at
`(527, 735.5)-(551, 744.5)` — 96 units out of the pin — while the landing pass
draws a 40-unit stub `(635, 740) -> (595, 740)`. `attributeMoves` moved the row
to the reservation's centre `x = 539`, so the name printed on no conductor of
its own, one row away from `C3`'s designator `(552, 732.5)-(567, 741.5)`, and the
page read `RXD C3`. Every other left-going name (TXD, D+, D-) printed on its own
stub, which is what makes this a locatable layer gap and not "RXD has no room":
the page's reserved box and the plan's carrier disagreed, and only the plan
decides what lands (`evidence/543g_skill_trial/README.md` sec.6.2/6.3).

The rule pinned here is the carrier's: **once the stub is drawn, a visible
native row must print on it.** The row keeps its size and its reading direction
and only its centre moves; a row already on its run is untouched (byte for
byte), a row that cannot be seated is a named refusal. Both facts are measured
twice: in process on :func:`drawapply._native_stub_row` (left, right, page edge,
neighbouring ink, a foreign conductor), and end to end on the page `spec_v1`
compiles to.

`spec_v1` is written inline — a test may not depend on an evidence directory —
and pinned by the presentation digest its page records
(`0a1d7acb…`, the same one `evidence/543h1b/page/cand1.page.json` states), so a
drifted copy cannot pass quietly.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from boardwise.core.changeplan import PlanDrawWire
from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import LayoutLabel
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawapply
from boardwise.engines import pagecompiler as pc

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
CIRCUIT_PATH = SPECS / "ch343_uart_534a.circuit.json"
LIBRARY_PATH = SPECS / "ch343_uart_v4.library.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)
#: The digest `evidence/543h1b/page/cand1.page.json` records for this payload's
#: fine print (`source.presentationSha256`): the inline copy below is that
#: document, not a paraphrase of it.
SPEC_V1_PRESENTATION_SHA = (
    "0a1d7acbe35790c57b5933a6ed45244ae86d42ee0015a3f3e0a73fa9db95dc6a"
)

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
            "id": "usb_c",
            "parts": ["USB1", "C1", "C2", "R1", "R2"],
            "role": "USB-C receptacle, VBUS bulk/decoupling and CC sink pull-downs",
            "grammarRef": "ic-periphery",
            "core": "USB1",
            "presentation": {"sidePreferences": {"load": "right"}},
        },
        {
            "id": "ch343",
            "parts": ["U1", "C3", "C4"],
            "role": "CH343 USB-UART bridge with V3 and VCC decoupling",
            "grammarRef": "ic-periphery",
            "core": "U1",
            "presentation": {"sidePreferences": {"load": "left"}},
        },
        {
            "id": "hdr",
            "parts": ["H1"],
            "role": "2x5 UART header to the peer board",
            "grammarRef": "ic-periphery",
            "core": "H1",
            "presentation": {"sidePreferences": {"input": "left", "output": "left"}},
        },
        {
            "id": "led",
            "parts": ["D1", "R3"],
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
        {
            "nets": ["LED_A"],
            "note": "lamp cathode and R3 are one conductor inside the indicator island",
        },
    ],
    "localLabelObligations": [
        {
            "nets": ["D+", "D-"],
            "note": (
                "Type-C data pins are mirrored pairs (A6/B6, A7/B7): each pin takes "
                "its own short stub and the same-named label instead of a U-line "
                "that would present one pin as the other; the pair reaches "
                "U1.5/U1.6 by name"
            ),
        },
    ],
    "moduleOrder": ["usb_c", "ch343", "hdr", "led"],
    "flagLeadLimit": 120,
    "partTexts": {
        "USB1": "left", "U1": "above", "H1": "above", "C3": "right", "C4": "right",
    },
    "gndClustering": {"radius": 100},
    "serviceLayout": {"pinGap": 30},
}


# ------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def circuit() -> CircuitSpec:
    return CircuitSpec.load(CIRCUIT_PATH)


@pytest.fixture(scope="module")
def profiles():
    payload = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    return {
        item["symbolRef"]: SymbolProfile.from_dict(item) for item in payload["profiles"]
    }


@pytest.fixture(scope="module")
def presentation() -> PresentationSpec:
    return PresentationSpec.from_dict(copy.deepcopy(PAYLOAD))


@pytest.fixture(scope="module")
def page(circuit, presentation, profiles):
    result = pc.compile_page(
        circuit, presentation, profiles,
        pc.PageCompileBudget(page_box=PAGE_BOX),
    )
    assert result.pages, [failure.detail[:200] for failure in result.failures]
    return result.pages[0]


@pytest.fixture(scope="module")
def plan(page, circuit, presentation, profiles):
    return drawapply.module_plan(
        page.plan, circuit, presentation, profiles,
        candidate_index=0, label_stubs=True, page_box=PAGE_BOX,
        module_label="page " + "+".join(module.id for module in page.modules),
    )


# ------------------------------------------------------------ the unit rule


def _label(net, x, y, box, *, stub="straight") -> LayoutLabel:
    return LayoutLabel(
        net=net, text=net, bbox=box, x=float(x), y=float(y),
        part_id="U1", stub=stub,
    )


def _row(label, points, ink=(), page_box=None, wires=()):
    return drawapply._native_stub_row(
        label, points, list(ink), page_box, list(wires),
    )


def test_a_left_going_row_is_moved_onto_its_stub():
    """The measured RXD shape, as a number: 96 out reserved, 40 drawn."""
    label = _label("RXD", 635.0, 740.0, (527.0, 735.5, 551.0, 744.5))
    row, note = _row(label, [(635.0, 740.0), (595.0, 740.0)])
    assert row is not None, "a row 96 units out of a 40-unit stub must move"
    # the row is on the run: inside its ends, on its own y, same size
    assert 595.0 - 1e-9 <= row[0] and row[2] <= 635.0 + 1e-9
    assert (row[1], row[3]) == (735.5, 744.5)
    assert (row[0] + row[2]) / 2.0 > 600.0      # not the 539 the page reserved
    assert "re-seated" in note and "(635, 740)" in note


def test_a_right_going_row_is_moved_onto_its_stub_too():
    """The same rule on the other side of the part: no direction is special."""
    label = _label("CTS", 725.0, 730.0, (838.0, 725.5, 862.0, 734.5))
    row, note = _row(label, [(725.0, 730.0), (765.0, 730.0)])
    assert row is not None
    assert 725.0 - 1e-9 <= row[0] and row[2] <= 765.0 + 1e-9
    assert (row[0] + row[2]) / 2.0 > 740.0
    assert "re-seated" in note


def test_a_row_already_on_its_stub_is_left_alone():
    """Byte-identical: the pass has nothing to say about a consistent row."""
    label = _label("TXD", 635.0, 750.0, (599.0, 745.5, 623.0, 754.5))
    row, note = _row(label, [(635.0, 750.0), (595.0, 750.0)])
    assert (row, note) == (None, "")


def test_the_nearest_seat_that_fits_is_taken():
    """The outermost seat is skipped when another part's text is already there."""
    label = _label("CTS", 725.0, 730.0, (838.0, 725.5, 862.0, 734.5))
    ink = [("the reference text 'C4' of C4", (762.0, 724.5, 764.0, 734.5))]
    row, _ = _row(label, [(725.0, 730.0), (765.0, 730.0)], ink=ink)
    assert row is not None
    assert row[2] <= 762.0 + 1e-9        # the seat that would touch C4's row
    assert row[0] >= 725.0 - 1e-9


def test_a_foreign_conductor_pushes_the_row_in_under_it():
    """A name printed across another net's wire is the 053Z defect."""
    label = _label("CTS", 725.0, 730.0, (838.0, 725.5, 862.0, 734.5))
    wires = [PlanDrawWire(net="V3", points=[(764.0, 720.0), (764.0, 740.0)])]
    row, _ = _row(label, [(725.0, 730.0), (765.0, 730.0)], wires=wires)
    assert row is not None
    assert row[2] < 764.0                # clear of the V3 run
    assert row[0] >= 725.0 - 1e-9


def test_a_seat_off_the_sheet_is_not_a_seat():
    """543F: the row may not leave the stated page, so a page with no seat refuses."""
    label = _label("CTS", 30.0, 100.0, (-40.0, 95.5, -16.0, 104.5))
    with pytest.raises(drawapply.DrawPlanError) as refused:
        _row(label, [(30.0, 100.0), (0.0, 100.0)], page_box=(10.0, 0.0, 1170.0, 825.0))
    assert "CTS" in str(refused.value)
    assert "sheet" in str(refused.value)


def test_no_legal_seat_is_a_named_refusal_with_every_blocker():
    label = _label("CTS", 725.0, 730.0, (838.0, 725.5, 862.0, 734.5))
    ink = [("the reference text 'C4' of C4", (726.0, 725.0, 770.0, 735.0))]
    with pytest.raises(drawapply.DrawPlanError) as refused:
        _row(label, [(725.0, 730.0), (765.0, 730.0)], ink=ink)
    message = str(refused.value)
    assert "no seat on that stub is legal" in message
    assert "C4" in message


# ------------------------------------------------------- end to end: the page


def _net_moves(plan):
    return {
        move.wire_index: move
        for move in plan.change.attribute_moves
        if move.owner_kind == "wire" and move.role == "net"
    }


def _run_of(wire):
    """The name stub's own points, as floats."""
    return [(float(point[0]), float(point[1])) for point in wire.points]


def test_the_page_spec_is_the_one_the_evidence_recorded(page):
    source = page.plan.source
    assert source.presentation_sha256 == SPEC_V1_PRESENTATION_SHA


def test_every_visible_name_prints_on_the_stub_that_carries_it(plan):
    """Not only RXD: every visible native row of the final plan is checked."""
    moves = _net_moves(plan)
    wires = plan.change.draw_wires
    checked = 0
    for index, move in moves.items():
        if getattr(move, "move_version", 1) == 2:
            continue
        wire = wires[index]
        if "name stub" not in str(wire.purpose):
            continue
        points = _run_of(wire)
        low, high = sorted((points[0][0], points[-1][0]))
        assert points[0][1] == points[-1][1], (wire.net, points)
        assert low - 1e-9 <= move.x <= high + 1e-9, (
            f"net {wire.net}'s row prints at x = {move.x:g}, off its "
            f"{low:g}..{high:g} stub {points}"
        )
        assert abs(move.y - points[0][1]) <= 1e-9, (wire.net, move.y)
        checked += 1
    assert checked >= 15, f"only {checked} visible stub rows were read"


def test_the_rxd_row_is_on_its_stub_and_clear_of_c3(plan, page):
    """The reported defect, read off the final plan: `RXD` is not `C3`'s name."""
    moves = _net_moves(plan)
    rxd = [
        (index, move) for index, move in moves.items()
        if plan.change.draw_wires[index].net == "RXD"
        and "name stub" in str(plan.change.draw_wires[index].purpose)
        and 600.0 < plan.change.draw_wires[index].points[0][0] < 900.0
    ]
    assert len(rxd) == 1
    index, move = rxd[0]
    points = _run_of(plan.change.draw_wires[index])
    low, high = sorted((points[0][0], points[-1][0]))
    assert low <= move.x <= high, (move.x, points)
    # the row it actually prints: same size as the reservation, moved
    label = next(
        item for item in page.plan.labels
        if item.net == "RXD" and (item.x, item.y) == (points[0][0], points[0][1])
    )
    width = float(label.bbox[2]) - float(label.bbox[0])
    height = float(label.bbox[3]) - float(label.bbox[1])
    row = (
        move.x - width / 2.0, move.y - height / 2.0,
        move.x + width / 2.0, move.y + height / 2.0,
    )
    c3 = next(item for item in page.plan.texts if item.text == "C3")
    assert not (
        min(row[2], c3.bbox[2]) - max(row[0], c3.bbox[0]) > 0.0
        and min(row[3], c3.bbox[3]) - max(row[1], c3.bbox[1]) > 0.0
    ), f"the RXD row {row} still lands on C3's designator {c3.bbox}"
    # and no other part's text row is on it either
    for text in page.plan.texts:
        assert not (
            min(row[2], text.bbox[2]) - max(row[0], text.bbox[0]) > 0.0
            and min(row[3], text.bbox[3]) - max(row[1], text.bbox[1]) > 0.0
        ), f"the RXD row {row} lands on {text.part_id}'s {text.kind} row {text.bbox}"
    assert move.x > 600.0, "the row went back to the 539 the page reserved"


def test_the_consistent_rows_are_not_moved(plan, page):
    """Every label whose reservation already sits on its stub is byte-identical."""
    moves = _net_moves(plan)
    same = 0
    for index, move in moves.items():
        if getattr(move, "move_version", 1) == 2:
            continue
        wire = plan.change.draw_wires[index]
        if "name stub" not in str(wire.purpose):
            continue
        label = next(
            item for item in page.plan.labels
            if item.net == wire.net
            and (item.x, item.y) == _run_of(wire)[0]
        )
        centre = (
            (float(label.bbox[0]) + float(label.bbox[2])) / 2.0,
            (float(label.bbox[1]) + float(label.bbox[3])) / 2.0,
        )
        points = _run_of(wire)
        low, high = sorted((points[0][0], points[-1][0]))
        if low <= centre[0] <= high:
            assert (move.x, move.y) == centre, (wire.net, move.x, centre)
            same += 1
    assert same >= 12


def test_each_non_continuous_run_keeps_a_visible_name(plan):
    """543I contract upgrade: P32's hidden duplicates are no longer legal.

    The withdrawn page hid `B6`/`B7`'s names, which left their 60/55-unit
    carriers as bare wires, while the printed `A6`/`A7` row stood off a 5-unit
    lead. Under `native-attr` **and** `serviceLayout` every non-continuous run of
    a named net prints its own name and the row sits inside its carrier, so this
    page states no version-2 hide at all and all six D+/D- rows share one rule.
    """
    hidden = [
        move for move in plan.change.attribute_moves
        if move.owner_kind == "wire" and getattr(move, "move_version", 1) == 2
    ]
    assert hidden == [], "a suppressed duplicate leaves a bare carrier (543I)"

    visible = [
        (index, move) for index, move in _net_moves(plan).items()
        if getattr(move, "move_version", 1) == 1
        and plan.change.draw_wires[index].net in ("D+", "D-")
    ]
    assert len(visible) == 6, "one name per reversible run (A6, B6, A7, B7, U1.5, U1.6)"
    for index, move in visible:
        points = _run_of(plan.change.draw_wires[index])
        xs = sorted(point[0] for point in points)
        low, high = xs[0], xs[-1]
        assert low - 1e-9 <= move.x <= high + 1e-9, (
            f"{plan.change.draw_wires[index].net} row x={move.x} is off its "
            f"{low:g}..{high:g} carrier"
        )


def test_a_spec_without_native_text_states_no_moves(
    page, circuit, profiles, presentation,
):
    """The old path: no `textPlacement`, no attribute rows, no re-seat."""
    payload = copy.deepcopy(PAYLOAD)
    payload.pop("textPlacement")
    plain = PresentationSpec.from_dict(payload)
    result = pc.compile_page(
        circuit, plain, profiles, pc.PageCompileBudget(page_box=PAGE_BOX),
    )
    assert result.pages
    candidate = result.pages[0]
    assert all(
        getattr(label, "text_mode", "") == "" for label in candidate.plan.labels
    )
    built = drawapply.module_plan(
        candidate.plan, circuit, plain, profiles,
        candidate_index=0, label_stubs=True, page_box=PAGE_BOX,
    )
    assert built.change.attribute_moves == []
