"""053Z: a printed `native` name lives on its own conductor, or it is a defect.

Six claims, in the order the batch states them:

1. **P27 reproduces** — `CTS` at 40 units and `RI` at 55 from the 5-unit leads
   the live page carries (`evidence/534y/p27_attr.json`), measured as *box to
   polyline*, are reported as `native-label-off-carrier`. Before this batch both
   parsed clean and the host printed the rows on `RXD`/`DSR`, which
   `check_wire_multiname` then called a second name of those nets.
2. **The accepted page stays legal** — the v46 candidate the line already draws
   has every visible label on its anchor's row or column, so the new gate adds
   nothing to it (`4` candidates, `0` failures, `0` violations).
3. **A candidate seat clears foreign nets** — `pagecompiler._native_label_seat`
   skips a seat whose box stands under one grid step from another net's
   conductor, keeps the text's size and horizontal reading, and puts the box
   centre on the anchor's axis so one straight stub reaches it.
4. **No legal seat is a refusal** — `_add_label(native=True)` returns
   `layout-unsat` rather than an off-carrier box.
5. **One position, three readers** — the box the re-seat leaves is the box the
   attribute move targets (`drawapply._native_attribute_moves`), the box the gate
   measures (`readability._native_label_rows`) and the box the stub is drawn to.
6. **A non-native page is byte-identical** and **H1's long value row does not
   cross the `x = 140` ground lead** under v47 (`partTexts.H1 = right`).

The page fixtures are the repo's own circuit/library plus the local probe specs
(`.tmp_fix/v46…`, `.tmp_534z/v47…`); a checkout without them skips the page-level
claims instead of pretending they were measured, and nothing under
`tests/fixtures/` is touched.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import (
    LayoutLabel,
    LayoutPlan,
    LayoutSegment,
    TEXT_MODE_NATIVE,
    TEXT_MODE_NATIVE_HIDDEN,
)
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler, pagecompiler, readability

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
CIRCUIT = SPECS / "ch343_uart_534a.circuit.json"
LIBRARY = SPECS / "ch343_uart_v4.library.json"
V46 = ROOT / ".tmp_fix" / "v46.presentation.json"
V47 = ROOT / ".tmp_534z" / "v47.presentation.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)


# ------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def profiles():
    return drawapply.load_library(LIBRARY)


@pytest.fixture(scope="module")
def circuit():
    return CircuitSpec.load(CIRCUIT)


def _compile(path, circuit, profiles):
    if not path.exists():
        pytest.skip(f"{path.name} is a local probe document")
    result = pagecompiler.compile_page(
        circuit, PresentationSpec.load(path), profiles,
        pagecompiler.PageCompileBudget(page_box=PAGE_BOX),
    )
    return result


def _p27_plan() -> LayoutPlan:
    """P27's two off-carrier names, at the coordinates the live page measured.

    `evidence/534y/p27_attr.json` / `p27_geo.json`: the `CTS` wire is
    `110,485 → 110,480`, its `Name` row prints at `(150,480)-(160,494.3)`; the
    `RI` wire is `105,460 → 110,460`, its row at `(165,460)-(172.1,470)`. Both
    boxes are 40 and 55 units from the wire that carries the name.
    """
    return LayoutPlan(
        segments=[
            LayoutSegment(net="CTS", points=[(110.0, 485.0), (110.0, 480.0)]),
            LayoutSegment(net="RI", points=[(105.0, 460.0), (110.0, 460.0)]),
        ],
        labels=[
            LayoutLabel(
                net="CTS", text="CTS", bbox=(150.0, 480.0, 160.0, 494.3),
                x=110.0, y=480.0, text_mode=TEXT_MODE_NATIVE,
            ),
            LayoutLabel(
                net="RI", text="RI", bbox=(165.0, 460.0, 172.1, 470.0),
                x=110.0, y=460.0, text_mode=TEXT_MODE_NATIVE,
            ),
        ],
    )


# ------------------------------------------------ 1. P27 reproduces, with numbers


def test_p27_cts_still_reads_40_units_off_its_carrier():
    plan = _p27_plan()
    violations = readability._check_native_label_carriers(plan, [], {})
    cts = [item for item in violations if "CTS" in item.evidence]
    assert len(cts) == 1, [item.render() for item in violations]
    assert cts[0].kind == readability.KIND_NATIVE_LABEL_OFF_CARRIER
    assert "40 units" in cts[0].evidence, cts[0].evidence
    assert "labels[0]" in cts[0].objects


def test_p27_ri_still_reads_55_units_off_its_carrier():
    plan = _p27_plan()
    violations = readability._check_native_label_carriers(plan, [], {})
    ri = [item for item in violations if "RI" in item.evidence]
    assert len(ri) == 1, [item.render() for item in violations]
    assert "55 units" in ri[0].evidence, ri[0].evidence


def test_the_distance_is_box_to_polyline_not_box_to_anchor():
    """The anchor sits *on* the wire; only the box is away from it.

    A check that measured the anchor would call both names fine — that is the
    reading this batch replaces.
    """
    plan = _p27_plan()
    for label in plan.labels:
        assert readability._on_polyline(
            (label.x, label.y),
            [tuple(point) for point in plan.segments[plan.labels.index(label)].points],
        )
    measured = {
        label.net: readability.native_label_carrier_gap(plan, label, [], {})
        for label in plan.labels
    }
    assert measured["CTS"][0] == pytest.approx(40.0)
    assert measured["RI"][0] == pytest.approx(55.0)


def test_a_hidden_label_is_not_judged_and_a_stated_page_is_untouched():
    """`native-hidden` prints nothing; an empty mode is the old midpoint row."""
    plan = _p27_plan()
    for label, mode in zip(plan.labels, (TEXT_MODE_NATIVE_HIDDEN, "")):
        label.text_mode = mode
    assert readability._check_native_label_carriers(plan, [], {}) == []


def test_a_label_on_its_carrier_is_clean():
    plan = LayoutPlan(
        segments=[LayoutSegment(net="D+", points=[(0.0, 0.0), (40.0, 0.0)])],
        labels=[LayoutLabel(
            net="D+", text="D+", bbox=(0.0, 0.0, 16.0, 9.0),
            x=0.0, y=0.0, text_mode=TEXT_MODE_NATIVE,
        )],
    )
    assert readability._check_native_label_carriers(plan, [], {}) == []


# ------------------------------------------- 2. the accepted page is not hurt


def test_the_accepted_v46_page_has_no_off_carrier_name(circuit, profiles):
    result = _compile(V46, circuit, profiles)
    assert result.failures == [], [f.detail[:200] for f in result.failures]
    assert result.pages, "v46 lost every candidate"
    checked = readability._profile_map(profiles)
    for candidate in result.pages:
        plan = candidate.plan
        placed = readability._placed_parts(plan, checked)
        assert readability._check_native_label_carriers(
            plan, placed, checked
        ) == [], "the accepted page gained an off-carrier finding"


# --------------------------------------- 3. a candidate seat clears foreign nets


def _seat_wires(*runs):
    return [(net, tuple(points)) for net, points in runs]


def test_a_candidate_seat_clears_a_foreign_conductor():
    """The near seat would stand on `RXD`; the next one is taken instead.

    The page's own two-column ladder is tried in the order the compass gives
    (preferred first), and a seat under one grid step from another net's
    conductor is skipped rather than reserved.
    """
    anchor = (110.0, 480.0)
    near = drawcompiler.font_text_box(
        "CTS", x=anchor[0] + drawcompiler.text_width("CTS") / 2.0
        + drawcompiler.TEXT_GAP, y=anchor[1],
    )
    # A foreign run straight through the near seat's band, one lattice step away.
    foreign = [("RXD", ((near[0], near[3] + 5.0), (near[2] + 40.0, near[3] + 5.0)))]
    seat = pagecompiler._native_label_seat(
        "CTS", anchor, (1.0, 0.0), [], _seat_wires(*foreign),
    )
    assert seat is not None, "the seat ladder gave up instead of stepping out"
    assert seat != near, "the blocked near seat was returned"
    for _net, points in foreign:
        assert readability._box_run_gap(seat, points) >= (
            readability.NATIVE_LABEL_CARRIER_LIMIT
        )
    assert (seat[2] - seat[0], seat[3] - seat[1]) == (near[2] - near[0], near[3] - near[1])


def test_a_candidate_seat_can_be_reached_by_one_straight_stub():
    """Every seat the ladder offers is on the anchor's row or column."""
    anchor = (110.0, 480.0)
    for preferred in ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0)):
        seat = pagecompiler._native_label_seat("RI", anchor, preferred, [], [])
        assert seat is not None, preferred
        centre = ((seat[0] + seat[2]) / 2.0, (seat[1] + seat[3]) / 2.0)
        assert (
            abs(centre[0] - anchor[0]) <= readability.TOL
            or abs(centre[1] - anchor[1]) <= readability.TOL
        ), (preferred, anchor, centre)


def test_the_seat_ladder_is_fixed_and_two_columns_wide():
    """The rungs are stated, not searched: near, then the second column."""
    assert pagecompiler._NATIVE_LABEL_SEATS == (1.0, 2.0)


# ----------------------------------------------------- 4. no seat is a refusal


def test_add_label_refuses_rather_than_keeping_an_off_carrier_box():
    plan = LayoutPlan(segments=[
        LayoutSegment(net="V3", points=[(0.0, 0.0), (10.0, 0.0)]),
    ])
    occupied: list = []
    label, failure = pagecompiler._add_label(
        plan, "V3", (10.0, 0.0), (0.0, 1.0), occupied, native=True,
    )
    assert failure is None and label is not None
    # Now every seat is taken: the refusal is a grammar failure, not a stub.
    blocked = _block_every_seat("V3", (10.0, 0.0))
    label, failure = pagecompiler._add_label(
        plan, "V3", (10.0, 0.0), (0.0, 1.0), blocked, native=True,
    )
    assert label is None
    assert failure is not None
    assert failure.category == "layout-unsat", failure
    assert "native-attr" in failure.action


def _block_every_seat(net: str, anchor: tuple[float, float]) -> list:
    """A box under every seat the ladder can offer, so none is free."""
    half_x = drawcompiler.text_width(net) / 2.0 + drawcompiler.TEXT_GAP
    half_y = drawcompiler.TEXT_SIZE / 2.0 + drawcompiler.TEXT_GAP
    boxes = []
    for ring in pagecompiler._NATIVE_LABEL_SEATS:
        for direction in pagecompiler._directions((1.0, 0.0)):
            offset = (
                (direction[0] * half_x, 0.0) if direction[0] != 0.0
                else (0.0, direction[1] * half_y)
            )
            centre = (anchor[0] + offset[0] * ring, anchor[1] + offset[1] * ring)
            boxes.append(drawcompiler.font_text_box(net, x=centre[0], y=centre[1]))
    return boxes


def test_the_historical_label_box_path_is_unchanged():
    """`native=False` still lays the box out with `_label_box`, byte for byte."""
    plan = LayoutPlan(segments=[
        LayoutSegment(net="V3", points=[(0.0, 0.0), (10.0, 0.0)]),
    ])
    occupied: list = []
    expected = pagecompiler._label_box("V3", (10.0, 0.0), (0.0, 1.0), occupied)
    label, failure = pagecompiler._add_label(
        plan, "V3", (10.0, 0.0), (0.0, 1.0), occupied, native=False,
    )
    assert failure is None and label is not None
    assert tuple(label.bbox) == tuple(expected)
    assert label.text_mode == ""


# ------------------------------------- 5. one position, three readers agree


def test_the_move_target_the_gate_and_the_stub_read_one_box(circuit, profiles):
    """The one position the three readers share is now refused when it is off-carrier.

    543H-6: this page reserves `CTS`'s row 58 units out of a **10-unit** stub
    (`(205, 730) -> (215, 730)`, with `C4`'s body 6 units further on), so the row
    cannot be put on the conductor it is supposed to name. The landing pass now
    says that by name instead of writing the reservation and calling it a move
    (`drawapply._native_stub_row`'s band rule). What this test still pins is the
    half that was true: the **page** layer's gate accepts the box (one straight,
    axis-aligned run reaches it), so the disagreement is the plan layer's to
    catch — and it is caught with the measured numbers, not a silent `ok`.
    """
    result = _compile(V46, circuit, profiles)
    assert result.pages, [f.detail[:200] for f in result.failures]
    plan = result.pages[0].plan
    checked = readability._profile_map(profiles)
    placed = readability._placed_parts(plan, checked)
    lcsc = {part.id: (part.lcsc or "C1") for part in circuit.parts}
    with pytest.raises(drawapply.DrawPlanError) as refused:
        drawapply.module_plan(
            plan, circuit, PresentationSpec.load(V46), profiles,
            lcsc_by_part=lcsc, label_stubs=True,
        )
    message = str(refused.value)
    assert "net CTS" in message
    assert "no seat on that stub is legal" in message
    assert "band a name may overhang" in message
    assert readability._check_native_label_carriers(plan, placed, checked) == []


# -------------------------------------- 6. non-native bytes, and H1's value row


def test_a_non_native_page_states_no_mode_and_no_reseat():
    plan = LayoutPlan(segments=[
        LayoutSegment(net="V3", points=[(0.0, 0.0), (10.0, 0.0)]),
    ])
    occupied: list = []
    pagecompiler._add_label(
        plan, "V3", (10.0, 0.0), (0.0, 1.0), occupied, native=False,
    )
    payload = json.dumps(plan.to_jsonable(), ensure_ascii=False)
    assert "textMode" not in payload


def test_h1_value_row_clears_the_ground_flag_lead(circuit, profiles):
    """v47's `partTexts.H1 = right`: the long model string stays off `x = 140`.

    The lead is P27's own defect (`evidence/534y` §1.1): the `GND` flag at
    `(140,425)` with its vertical run `140,425 → 140,450`, printed through the
    value row. The check is geometric, not "the compile exited 0": the row's box
    and that run must not touch, and the value row must be the one the document
    states.
    """
    result = _compile(V47, circuit, profiles)
    assert result.failures == [], [f.detail[:200] for f in result.failures]
    assert result.pages, [f.detail[:200] for f in result.failures]
    plan = result.pages[0].plan
    values = [text for text in plan.texts if text.part_id == "H1" and text.kind == "value"]
    assert len(values) == 1, [(text.part_id, text.kind) for text in plan.texts]
    value_box = tuple(float(item) for item in values[0].bbox)
    lead = ((140.0, 450.0), (140.0, 425.0))
    assert readability._box_run_gap(value_box, list(lead)) > 0.0, (
        f"H1's value row {value_box} is crossed by the ground flag's lead {lead}"
    )
    leads = [
        segment for segment in plan.segments
        if any(
            abs(start[0] - 140.0) < 1e-6 and abs(stop[0] - 140.0) < 1e-6
            and min(start[1], stop[1]) <= 425.0 and max(start[1], stop[1]) >= 450.0
            for start, stop in readability._edges(
                [tuple(point) for point in segment.points]
            )
        )
    ]
    assert leads, "the ground flag's lead at x = 140 is not in this page any more"
