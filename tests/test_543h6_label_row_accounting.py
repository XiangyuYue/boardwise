"""543H-6: the seat a re-seated row takes must be **on** its carrier, and it is
the row the rest of the plan then has to live with.

Two gaps closed here, both found by a read-only review of 543H-2's landing rule:

1. **A short stub let the name drift.** The short-run ladder marched out to the
   box the layout reserved, and nothing asked the far end of that ladder whether
   it was still on the carrier. A 30-unit stub with a reservation 96 units out
   put the name 54 units past its own conductor and the plan's own sentence said
   it had been re-seated "onto the stub". Every seat is now held to the band
   :data:`textmetrics.WIRE_NAME_ROW` — a name may hang off a stub's end the way
   the host's own short-wire row does, but no further — and a stub with no such
   seat is refused by name instead.
2. **The re-seated row was the plan's silent secret.** ``label_stub_rows`` and
   ``name_carriers`` were written by ``_place_label_stub`` before the row moved,
   and ``_hard_ink_boxes`` kept handing the next label the box the layout had
   reserved. So the next label stepped around paper nobody prints on while the
   row that *is* printed was worth no clearance at all. The final row now
   replaces both books for that label and is the ink the following labels see.
   ``LayoutLabel.bbox`` is not touched: it is the layout's own digest.

The two-label regression is a hand-built divider (two axial resistors, no
conductors) so the geometry is stated here and not inherited from a page: the
first label's reservation sits where the second label's stub has to pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import LayoutLabel, LayoutPart, LayoutPlan, LayoutSource
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.textmetrics import WIRE_NAME_ROW
from boardwise.engines import drawapply

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "drawapply"
CIRCUIT = FIXTURES / "divider.circuit.json"
LIBRARY = FIXTURES / "library.json"
PRESENTATION = FIXTURES / "divider.presentation.json"
PAGE_BOX = (0.0, -400.0, 600.0, 400.0)


# ------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def circuit() -> CircuitSpec:
    return CircuitSpec.load(CIRCUIT)


@pytest.fixture(scope="module")
def profiles():
    return drawapply.load_library(LIBRARY)


@pytest.fixture(scope="module")
def presentation() -> PresentationSpec:
    plain = PresentationSpec.load(PRESENTATION)
    return PresentationSpec.from_dict({
        **json.loads(json.dumps(plain.to_jsonable())),
        "textPlacement": "native-attr",
        "labelPolicy": {
            "local": "wire", "crossModule": "label", "highFanout": "label",
            "stub": "straight", "stubMin": 40, "rowModel": "centered",
        },
    })


def _label(net, x, y, box, part_id="") -> LayoutLabel:
    return LayoutLabel(
        net=net, text=net, bbox=box, x=float(x), y=float(y),
        part_id=part_id, stub="straight", stub_min=40.0,
        row_model="centered", text_mode="native",
    )


def _row(label, points, ink=(), page_box=None, wires=()):
    return drawapply._native_stub_row(
        label, points, list(ink), page_box, list(wires),
    )


def _gap_to_run(box, points) -> float:
    """How far the box stands off the run's own row band (0 when it overlaps)."""
    (x1, y1), (x2, y2) = points[0], points[-1]
    if abs(y1 - y2) <= 1e-9:
        low, high = sorted((x1, x2))
        return max(low - box[2], box[0] - high, 0.0)
    low, high = sorted((y1, y2))
    return max(low - box[3], box[1] - high, 0.0)


# ------------------------------------------------ 1. a short stub cannot drift


def test_a_short_stub_keeps_the_name_within_the_band():
    """30 units of stub, a reservation 96 out, nothing in the way (543H-6 #1)."""
    label = _label("A", 0.0, 0.0, (-108.0, -4.5, -84.0, 4.5))
    stub = [(0.0, 0.0), (-30.0, 0.0)]
    row, note = _row(label, stub)
    assert row is not None
    assert _gap_to_run(row, stub) <= WIRE_NAME_ROW + 1e-9, (
        f"the re-seated row {row} still stands "
        f"{_gap_to_run(row, stub):g} units off its 30-unit stub"
    )
    # the seat is on the stub's own line, and the name is not straddling the pin
    assert row[1] < 0.0 < row[3]
    assert row[0] < 0.0
    # and it is not the reservation it started from
    assert row != (-108.0, -4.5, -84.0, 4.5)
    assert "re-seated" in note


def test_the_band_is_not_just_a_sentence():
    """The same stub, every in-band seat taken: a named refusal, not a drift."""
    label = _label("A", 0.0, 0.0, (-108.0, -4.5, -84.0, 4.5))
    stub = [(0.0, 0.0), (-30.0, 0.0)]
    ink = [("the reference text 'R9' of R9", (-72.0, -6.0, -18.0, 6.0))]
    with pytest.raises(drawapply.DrawPlanError) as refused:
        _row(label, stub, ink=ink)
    message = str(refused.value)
    assert "no seat on that stub is legal" in message
    assert "band a name may overhang" in message
    assert "A" in message


# ------------------------------------------------- 2. two labels, one row band


def _two_label_layout(circuit, presentation, profiles) -> LayoutPlan:
    """R1 at x=0, R2 at x=200, both axial; the names are stated, not compiled.

    ``R1.2``'s reservation sits at ``x = 146``; the second label's pin is at
    ``x = 150`` and its own left-hand stub is the run ``150 -> 110`` — i.e. the
    stub has to pass straight through the space the first reservation occupied.
    """
    axial = profiles["R-AXIAL"]
    return LayoutPlan(
        source=LayoutSource(
            circuit_sha256=circuit.sha256(),
            presentation_sha256=presentation.sha256(),
        ),
        parts=[
            LayoutPart(part_id="R1", symbol_ref="R-AXIAL",
                       symbol_hash=axial.geometry_hash(), x=0.0, y=0.0),
            LayoutPart(part_id="R2", symbol_ref="R-AXIAL",
                       symbol_hash=axial.geometry_hash(), x=200.0, y=0.0),
        ],
        segments=[],
        labels=[
            _label("TAP", 50.0, 0.0, (134.0, -4.5, 158.0, 4.5), part_id="R1"),
            _label("VIN", 150.0, 0.0, (114.0, -4.5, 138.0, 4.5), part_id="R2"),
        ],
    )


def test_the_next_label_may_use_the_space_the_reseat_freed(
    circuit, presentation, profiles,
):
    """The vacated reservation is no longer ink; the printed row is (543H-6 #2)."""
    layout = _two_label_layout(circuit, presentation, profiles)
    plan = drawapply.module_plan(
        layout, circuit, presentation, profiles,
        keep_names=True, label_stubs=True, page_box=PAGE_BOX,
    )
    wires = plan.change.draw_wires
    stubs = {
        wire.net: [tuple(float(value) for value in point) for point in wire.points]
        for wire in wires if "name stub" in str(wire.purpose)
    }
    # the first label was re-seated off its 96-unit reservation onto its stub
    assert stubs["TAP"] == [(50.0, 0.0), (90.0, 0.0)]
    # and the second label's stub is the left run **through the old reservation**
    assert stubs["VIN"] == [(150.0, 0.0), (110.0, 0.0)], (
        "the VIN stub did not take the run through the vacated TAP reservation: "
        f"{stubs['VIN']}"
    )
    rows = {}
    for move in plan.change.attribute_moves:
        if move.owner_kind != "wire" or getattr(move, "move_version", 1) == 2:
            continue
        wire = wires[move.wire_index]
        if "name stub" not in str(wire.purpose):
            continue
        label = next(
            item for item in layout.labels
            if item.net == wire.net
            and (float(item.x), float(item.y))
            == (float(wire.points[0][0]), float(wire.points[0][1]))
        )
        half_w = (float(label.bbox[2]) - float(label.bbox[0])) / 2.0
        half_h = (float(label.bbox[3]) - float(label.bbox[1])) / 2.0
        rows[wire.net] = (
            move.x - half_w, move.y - half_h, move.x + half_w, move.y + half_h,
        )
    assert set(rows) == {"TAP", "VIN"}
    # two printed rows on one band, and they do not overlap
    assert not (
        min(rows["TAP"][2], rows["VIN"][2]) - max(rows["TAP"][0], rows["VIN"][0]) > 0.0
        and min(rows["TAP"][3], rows["VIN"][3]) - max(rows["TAP"][1], rows["VIN"][1]) > 0.0
    ), (rows["TAP"], rows["VIN"])
    # and every printed row is on its own carrier
    for net, box in rows.items():
        assert _gap_to_run(box, stubs[net]) <= WIRE_NAME_ROW + 1e-9, (net, box)


def test_the_re_seated_row_is_the_ink_the_next_label_sees(
    circuit, presentation, profiles,
):
    """`_hard_ink_boxes` states the printed row, not the reservation (543H-6 #2)."""
    layout = _two_label_layout(circuit, presentation, profiles)
    plan = drawapply.module_plan(
        layout, circuit, presentation, profiles,
        keep_names=True, label_stubs=True, page_box=PAGE_BOX,
    )
    tap = layout.labels[0]
    final = (66.0, -4.5, 90.0, 4.5)
    built = drawapply._Built()
    built.native_stub_rows[id(tap)] = (((50.0, 0.0), (90.0, 0.0)), final)
    boxes = drawapply._hard_ink_boxes(
        layout, profiles, built, subject=layout.labels[1],
    )
    boxes = [box for _what, box in boxes]
    assert final in boxes, "the re-seated row is not ink for the next label"
    assert (134.0, -4.5, 158.0, 4.5) not in boxes, (
        "the vacated reservation is still ink"
    )
    assert plan.change.draw_wires  # the plan itself was built from the same layout
