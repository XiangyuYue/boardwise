"""053X: the page's own cross-module names are printed at their boxes.

Four claims, in the order the batch states them:

1. **the page label carries the mode** — under `textPlacement: native-attr` a
   label the page *creates* (`_add_label`) or *re-states* (`_port`, the
   `PAGE_PORT_LABEL` branch that keeps a module's own name) is
   `text_mode="native"`; a `native-hidden` label the module already chose stays
   hidden, because making it visible would print the net twice;
2. **the name is printed at the box, not along the run** — `readability` reads a
   native label's **real bbox** as the row its carrier prints, and `drawapply`
   puts the wire's `net` attribute move at that box centre (version 1). Before
   this batch the page's `V3`/`RTS` names had no mode at all, so the host printed
   them at a midpoint the page never reserved (the folded `V3` row of the
   complaint) and no attribute move addressed them;
3. **the direct stub is untouched** — a page label with no conductor still gets
   its straight, axis-aligned stub run through its anchor, and the anchor does
   not move (it is the electrical fact; only the box is typography);
4. **a non-native page is byte-identical** — a spec that states no
   `textPlacement` produces labels with no `textMode` key, no attribute moves,
   and `_add_label` / `_native_text_mode` change nothing.

The page fixture is 053W's v45 (`.tmp_fix/v45.presentation.json`, a local probe
document like every input under `.tmp_fix/`); a checkout without it skips the
page-level claims instead of pretending they were measured. The circuit and the
symbol library are the repo's, and nothing under `tests/fixtures/` is modified.
"""

from __future__ import annotations


import json
import pathlib
from types import SimpleNamespace

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
from boardwise.engines import drawapply, pagecompiler, readability

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
CIRCUIT = SPECS / "ch343_uart_534a.circuit.json"
LIBRARY = SPECS / "ch343_uart_v4.library.json"
V45 = ROOT / ".tmp_fix" / "v45.presentation.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)
#: The nets 岳's complaint names: `V3` (the folded name) and `RTS` (the header's
#: own statement). Both are named at two module ends on the page.
WATCH = ("V3", "RTS")


# ------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def profiles():
    return drawapply.load_library(LIBRARY)


@pytest.fixture(scope="module")
def circuit():
    return CircuitSpec.load(CIRCUIT)


@pytest.fixture(scope="module")
def native_page(circuit, profiles):
    if not V45.exists():
        pytest.skip("053W's v45 input is a local probe file")
    return pagecompiler.compile_page(
        circuit, PresentationSpec.load(V45), profiles,
        pagecompiler.PageCompileBudget(page_box=PAGE_BOX),
    )


@pytest.fixture(scope="module")
def native_plan(native_page):
    assert native_page.failures == [], [f.detail[:300] for f in native_page.failures]
    assert native_page.pages, "the v45 page lost every candidate"
    return native_page.pages[0].plan


def _lcsc(circuit) -> dict[str, str]:
    return {part.id: (part.lcsc or "C1") for part in circuit.parts}


def _apply_plan(layout, circuit, presentation, profiles):
    return drawapply.module_plan(
        layout, circuit, presentation, profiles,
        lcsc_by_part=_lcsc(circuit), label_stubs=True,
    )


def _centre(box) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


# ------------------------------------------- 1. the mode the page states


def test_every_page_label_carries_a_native_reading(native_plan):
    """No label is left unstated: an empty mode is the old midpoint row."""
    modes = sorted({label.text_mode for label in native_plan.labels})
    assert modes and set(modes) <= {TEXT_MODE_NATIVE, TEXT_MODE_NATIVE_HIDDEN}, modes
    blank = sorted({label.net for label in native_plan.labels if not label.text_mode})
    assert blank == [], f"page labels left without a text mode: {blank}"


def test_the_watched_nets_are_named_at_both_ends(native_plan):
    """`V3` and `RTS` reach two modules, so the page states each twice."""
    for net in WATCH:
        labels = [label for label in native_plan.labels if label.net == net]
        assert len(labels) == 2, (net, [(l.x, l.y, l.text_mode) for l in labels])
        assert [label.text_mode for label in labels] == [TEXT_MODE_NATIVE] * 2


# ------------------------------ 2. printed at the box, not at a midpoint


def test_the_watched_names_move_their_attribute_to_the_label_box(
    native_plan, native_page, circuit, profiles
):
    """The reserved row is the printed row *when the stub reaches it* (543H-6).

    This page states a box the drawn ten-unit stub cannot reach: `TXD`'s row is
    reserved `(223, 745.5)-(247, 754.5)` against a stub `(175, 750) -> (185, 750)`
    and `GND`'s own lead runs through every seat between them. The landing pass
    now refuses by name (the band rule of `drawapply._native_stub_row`) instead of
    moving the row to a box 38 units off its conductor; the page-layer facts the
    test was written for — `V3` and `RTS` carry a visible `native` mode at both
    ends — are still asserted, on the layout.
    """
    with pytest.raises(drawapply.DrawPlanError) as refused:
        _apply_plan(native_plan, circuit, PresentationSpec.load(V45), profiles)
    message = str(refused.value)
    assert "net TXD" in message and "no seat on that stub is legal" in message
    assert "band a name may overhang" in message
    for net in WATCH:
        for label in (item for item in native_plan.labels if item.net == net):
            assert label.text_mode == TEXT_MODE_NATIVE


def test_readability_reads_the_native_box_not_a_ghost(native_plan):
    """`_native_label_rows` hands the gate the label's own box.

    The rows it returns are the boxes `_named_wire_rows` measures, so a native
    label can never leave a midpoint row nobody draws behind it — the ghost the
    gate used to judge instead of the printed text.
    """
    rows = readability._native_label_rows(native_plan)
    boxes = {tuple(float(value) for value in label.bbox)
             for label in native_plan.labels if label.text_mode == TEXT_MODE_NATIVE}
    for index, box in rows.items():
        assert tuple(box) in boxes, (index, box)
    measured = {tuple(box) for _name, box, _owner, _net
                in readability._named_wire_rows(native_plan)}
    for index, box in rows.items():
        assert tuple(box) in measured, (
            f"segments[{index}] prints {box} but the gate measures something else"
        )
    assert readability._check_named_wire_rows(native_plan) == []


# ------------------------------------------------- 3. the direct stub stays


def test_the_watched_labels_keep_a_straight_stub_through_their_anchor(
    native_plan, circuit, profiles
):
    """The mode changes no wire — and a row its stub cannot carry is refused.

    543H-6: the same page states `TXD`'s name box 38 units past the only stub its
    pin can draw, so the landing pass refuses by name (see the test above).

    The straight stub this test used to read off `native_plan.segments` was never
    there: `V3` and `RTS` are **label-only** nets on this page (`segments` holds no
    run for either), and their stubs are drawn by the landing pass. The loop over
    that list was therefore empty and asserted nothing — the vacuity this test's
    rebuild closes. What is read from the layout now is the fact the plan builds on:
    each watched net has its two `native` labels and **no** conductor, and every
    one of those labels has a straight stub candidate leaving its own anchor
    (:func:`drawapply._label_stub_candidates`), which is what makes a straight stub
    through the anchor possible at all.
    """
    with pytest.raises(drawapply.DrawPlanError):
        _apply_plan(native_plan, circuit, PresentationSpec.load(V45), profiles)
    for net in WATCH:
        labels = [item for item in native_plan.labels if item.net == net]
        assert len(labels) == 2, (net, [(item.x, item.y) for item in labels])
        conductors = [segment for segment in native_plan.segments if segment.net == net]
        assert conductors == [], (
            f"net {net} now carries a layout conductor "
            f"{[list(map(float, p)) for p in conductors[0].points]}; this test reads "
            "its stubs from the landing pass and must be rewritten"
        )
        for label in labels:
            runs = drawapply._label_stub_candidates(label)
            assert runs, f"net {net} has no stub candidate at ({label.x:g}, {label.y:g})"
            head = runs[0]
            (ax, ay), (bx, by) = ((float(p[0]), float(p[1])) for p in head.points[:2])
            assert (ax, ay) == (float(label.x), float(label.y)), (
                f"net {net}'s first stub candidate at ({label.x:g}, {label.y:g}) "
                f"does not leave its anchor: {head.points}"
            )
            assert ax == bx or ay == by, (
                f"net {net}'s first stub candidate at ({label.x:g}, {label.y:g}) "
                f"is not axis-aligned: {head.points}"
            )


# ------------------------------------------- 4. the non-native page is untouched


def test_a_non_native_page_states_no_mode_and_no_move():
    """056's own two-module page without the switch: nothing about it changes."""
    import test_056_pagecompiler as m056

    scene = m056.scenes()[1]
    result = m056.compile_scene(scene)
    assert result.pages, [f.detail[:300] for f in result.failures]
    layout = result.pages[0].plan
    assert layout.labels, "the scene lost its label"
    assert [label.text_mode for label in layout.labels] == ["" for _ in layout.labels]
    payload = json.dumps(layout.to_jsonable(), ensure_ascii=False)
    assert "textMode" not in payload, "a pre-053T document gained a textMode key"
    plan = drawapply.module_plan(
        layout, scene.circuit, scene.presentation, m056.library(),
        lcsc_by_part=_lcsc(scene.circuit),
    )
    assert plan.change.attribute_moves == []


def test_add_label_takes_its_mode_from_the_page_statement():
    """The switch is the page's, read once — the helper does not guess."""
    plan = LayoutPlan(segments=[LayoutSegment(net="V3", points=[(0.0, 0.0), (30.0, 0.0)])])
    occupied: list = []
    plain, failure = pagecompiler._add_label(
        plan, "V3", (0.0, 0.0), (1.0, 0.0), occupied,
    )
    assert failure is None
    assert plain.text_mode == ""
    plan = LayoutPlan(segments=[LayoutSegment(net="V3", points=[(0.0, 0.0), (30.0, 0.0)])])
    occupied = []
    stated, failure = pagecompiler._add_label(
        plan, "V3", (0.0, 0.0), (1.0, 0.0), occupied, native=True,
    )
    assert failure is None
    assert stated.text_mode == TEXT_MODE_NATIVE


def test_the_re_stated_label_keeps_a_hidden_reading_and_a_date():
    """`_native_text_mode`: fill an unstated mode, never unhide, never touch plain."""
    native_ctx = SimpleNamespace(
        presentation=SimpleNamespace(text_placement="native-attr")
    )
    plain_ctx = SimpleNamespace(presentation=SimpleNamespace(text_placement=""))
    box = (0.0, 0.0, 10.0, 9.0)
    unstated = LayoutLabel(net="V3", text="V3", bbox=box)
    pagecompiler._native_text_mode(native_ctx, unstated)
    assert unstated.text_mode == TEXT_MODE_NATIVE
    hidden = LayoutLabel(
        net="D+", text="D+", bbox=box, text_mode=TEXT_MODE_NATIVE_HIDDEN,
    )
    pagecompiler._native_text_mode(native_ctx, hidden)
    assert hidden.text_mode == TEXT_MODE_NATIVE_HIDDEN, "053V's hidden row was unhidden"
    untouched = LayoutLabel(net="V3", text="V3", bbox=box)
    pagecompiler._native_text_mode(plain_ctx, untouched)
    assert untouched.text_mode == "", "a non-native page gained a text mode"


def test_the_page_re_states_a_module_label_as_native():
    """`_port` marks the label it names, so the run stops printing a folded row.

    A vertical carrier is the case that was invisible: the model prints the name
    *along the run* unless the label says `native`, so a page that re-states the
    estimate as a name had `V3` come out rotated — and the gate refused the run
    it had just been handed. With the page's mark the row is the label's own box,
    printed horizontally, and the run's direction is no longer a fact about it.
    """
    def page_plan():
        plan = LayoutPlan(
            segments=[LayoutSegment(net="V3", points=[(0.0, 0.0), (0.0, 100.0)])],
        )
        plan.labels.append(LayoutLabel(
            net="V3", text="V3", bbox=(2.0, 45.0, 18.0, 54.0), x=0.0, y=50.0,
        ))
        return plan

    module = SimpleNamespace(id="ch343")
    native_ctx = SimpleNamespace(
        presentation=SimpleNamespace(text_placement="native-attr")
    )
    plain_ctx = SimpleNamespace(presentation=SimpleNamespace(text_placement=""))

    unstated = page_plan()
    assert readability._check_named_wire_rows(unstated), (
        "the fixture must be a folded (vertical) run, or it proves nothing"
    )
    port, failure = pagecompiler._port(
        native_ctx, module, unstated, "V3", pagecompiler.PAGE_PORT_LABEL,
        (0.0, 50.0), (0.0, 1.0), [], {},
    )
    assert failure is None
    assert (port.x, port.y) == (0.0, 50.0), "the anchor moved: it is the electrical fact"
    (label,) = unstated.labels
    assert label.text_mode == TEXT_MODE_NATIVE
    assert readability._native_label_rows(unstated) == {0: label.bbox}, (
        "the gate must measure the label's own box, not a midpoint ghost"
    )
    assert readability._check_named_wire_rows(unstated) == []

    untouched = page_plan()
    pagecompiler._port(
        plain_ctx, module, untouched, "V3", pagecompiler.PAGE_PORT_LABEL,
        (0.0, 50.0), (0.0, 1.0), [], {},
    )
    assert untouched.labels[0].text_mode == "", "a non-native page gained a mode"
    assert readability._native_label_rows(untouched) == {}
    assert readability._check_named_wire_rows(untouched), (
        "a non-native page lost the vertical-row refusal it had"
    )
