"""053T: one name per **continuous** run, straight stubs, and the real text model.

The batch has five claims, and each has a test here:

1. **a continuous conductor run is named once** — two wires of one net that meet
   at a shared vertex, or with a vertex landing mid-span of the other (a T), are
   one run and print one name; nothing is drawn to join anything;
2. **a net is not a run** — two conductors that only share a name each keep one
   name (the Type-C's reversible pins), and the pass never adds a wire between
   them;
3. **a flag-covered net is left alone** — the flag carries that name and no
   attribute row moves; the label is not marked native and not dropped;
4. **native stubs are straight only** — the bent rungs stay in the ladder for
   every other label (byte for byte) and are absent for a `native` one, so a pin
   with no free straight run is refused rather than bent into place;
5. **the text is where the plan says** — the readability gate models a `native`
   label as the attribute row at the label's own box (never a ghost row at the
   wire's midpoint) and does not judge a horizontal attribute row by the
   direction of the wire it rides.

Nothing under ``tests/fixtures/`` is modified: the divider fixtures are read as
they are and the synthetic layouts are built in process.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import LayoutLabel, LayoutPlan, LayoutSegment
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler, readability

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "drawapply"
CIRCUIT = FIXTURES / "divider.circuit.json"
PRESENTATION = FIXTURES / "divider.presentation.json"
LIBRARY = FIXTURES / "library.json"
PAGE_BOX = (0.0, -1000.0, 1200.0, 0.0)
LCSC = {"R1": "C25744", "R2": "C25744"}


# ------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def circuit() -> CircuitSpec:
    return CircuitSpec.load(CIRCUIT)


@pytest.fixture(scope="module")
def profiles():
    return drawapply.load_library(LIBRARY)


@pytest.fixture(scope="module")
def plain() -> PresentationSpec:
    return PresentationSpec.load(PRESENTATION)


@pytest.fixture(scope="module")
def native(plain) -> PresentationSpec:
    return PresentationSpec.from_dict({
        **json.loads(json.dumps(plain.to_jsonable())),
        "textPlacement": "native-attr",
    })


def _label(net, x, y, bbox=None, **kwargs) -> LayoutLabel:
    box = bbox or (x + 8.0, y - 4.5, x + 30.0, y + 4.5)
    return LayoutLabel(net=net, text=net, bbox=box, x=x, y=y, **kwargs)


def _dedupe(labels, segments, flag_nets=()):
    return drawcompiler._native_label_dedupe(labels, segments, set(flag_nets))


# ------------------------------------------------------- one name per run


def test_two_wires_sharing_an_endpoint_print_one_name():
    labels = [_label("D+", 0.0, 0.0), _label("D+", 60.0, 0.0)]
    segments = [
        LayoutSegment(net="D+", points=[(0.0, 0.0), (30.0, 0.0)]),
        LayoutSegment(net="D+", points=[(30.0, 0.0), (60.0, 0.0)]),
    ]
    note = _dedupe(labels, segments)
    assert len(labels) == 1
    assert labels[0].text_mode == "native"
    assert "dropped" in note
    # no conductor was added: the dedupe is a naming decision, not a wiring one.
    assert len(segments) == 2


def test_a_tee_is_one_run():
    labels = [_label("D-", 0.0, 0.0), _label("D-", 0.0, -40.0)]
    segments = [
        LayoutSegment(net="D-", points=[(0.0, 0.0), (40.0, 0.0)]),
        # the branch's end lies mid-span of the trunk: a T, i.e. continuity.
        LayoutSegment(net="D-", points=[(0.0, -40.0), (0.0, 40.0)]),
    ]
    _dedupe(labels, segments)
    assert len(labels) == 1
    assert labels[0].x == 0.0 and labels[0].y == 0.0


def test_disconnected_runs_of_one_net_each_keep_a_name():
    labels = [_label("D+", 0.0, 0.0), _label("D+", 0.0, -60.0)]
    segments = [
        LayoutSegment(net="D+", points=[(0.0, 0.0), (30.0, 0.0)]),
        # parallel, no shared vertex, no vertex on the other: two runs.
        LayoutSegment(net="D+", points=[(0.0, -60.0), (30.0, -60.0)]),
    ]
    _dedupe(labels, segments)
    assert len(labels) == 2
    assert all(label.text_mode == "native" for label in labels)


def test_a_label_on_no_conductor_is_left_alone():
    labels = [_label("VIN", 0.0, 0.0)]
    segments = [LayoutSegment(net="VIN", points=[(0.0, -80.0), (0.0, -60.0)])]
    _dedupe(labels, segments)
    assert len(labels) == 1
    assert labels[0].text_mode == ""


def test_a_flag_covered_net_is_not_touched():
    labels = [_label("GND", 0.0, 0.0), _label("GND", 30.0, 0.0)]
    segments = [
        LayoutSegment(net="GND", points=[(0.0, 0.0), (30.0, 0.0)]),
    ]
    _dedupe(labels, segments, {"GND"})
    assert len(labels) == 2
    assert all(label.text_mode == "" for label in labels)


# ------------------------------------------------------ native straight only


def test_native_candidates_are_straight_only():
    native_label = _label("TXD", 100.0, 100.0, text_mode="native")
    plain_label = _label("TXD", 100.0, 100.0)
    native_runs = drawapply._label_stub_candidates(native_label)
    legacy_runs = drawapply._label_stub_candidates(plain_label)
    assert native_runs
    assert all(len(run.points) == 2 for run in native_runs)
    # the bent rungs are still in the ladder for a label that did not ask for
    # native text: the old candidate list is untouched.
    assert any(len(run.points) > 2 for run in legacy_runs)
    # and every native run is one the legacy ladder already offered, in order.
    legacy_points = [run.points for run in legacy_runs]
    assert [run.points for run in native_runs] == [
        points for points in legacy_points if len(points) == 2
    ]


def test_legacy_labels_carry_no_text_mode_key():
    label = _label("VIN", 0.0, 0.0)
    payload = LayoutPlan(segments=[], labels=[label])._geometry_payload()
    assert "textMode" not in payload["labels"][0]
    native_label = _label("VIN", 0.0, 0.0, text_mode="native")
    payload = LayoutPlan(segments=[], labels=[native_label])._geometry_payload()
    assert payload["labels"][0]["textMode"] == "native"


# ---------------------------------------------------- readability text model


def test_a_native_label_has_no_ghost_midpoint_row():
    label = _label("D+", 0.0, 0.0, text_mode="native")
    plan = LayoutPlan(
        segments=[LayoutSegment(net="D+", points=[(0.0, 0.0), (0.0, -100.0)])],
        labels=[label],
    )
    rows = readability._named_wire_rows(plan)
    assert len(rows) == 1
    name, box, _text, net = rows[0]
    assert net == "D+"
    assert box == tuple(float(value) for value in label.bbox)
    # the ghost was the midpoint row of the *longest run*, which for this wire
    # would sit 50 units down the page; the label's box is at the anchor.
    assert box != (0.0, -55.0, 10.0, -45.0)


def test_a_native_horizontal_attr_is_not_a_vertical_row():
    label = _label("D+", 0.0, 0.0, text_mode="native")
    plan = LayoutPlan(
        segments=[LayoutSegment(net="D+", points=[(0.0, 0.0), (0.0, -100.0)])],
        labels=[label],
    )
    kinds = {item.kind for item in readability._check_named_wire_rows(plan)}
    assert readability.KIND_NAME_ROW_VERTICAL not in kinds


def test_the_old_vertical_row_is_still_refused():
    label = _label("D+", 0.0, 0.0)
    plan = LayoutPlan(
        segments=[LayoutSegment(net="D+", points=[(0.0, 0.0), (0.0, -100.0)])],
        labels=[label],
    )
    kinds = {item.kind for item in readability._check_named_wire_rows(plan)}
    assert readability.KIND_NAME_ROW_VERTICAL in kinds


# ------------------------------------------------- end to end: plan + moves


def _plan(layout, circuit, presentation, profiles):
    return drawapply.module_plan(
        layout, circuit, presentation, profiles, lcsc_by_part=LCSC,
    )


def test_a_spec_without_the_switch_still_has_no_moves(circuit, plain, profiles):
    layout = drawcompiler.compile(
        circuit, plain, profiles, drawcompiler.CompileBudget(page_box=PAGE_BOX)
    ).best()
    assert all(label.text_mode == "" for label in layout.labels)
    plan = _plan(layout, circuit, plain, profiles)
    assert plan.change.attribute_moves == []


def test_one_move_per_run_after_the_dedupe(circuit, native, profiles):
    layout = drawcompiler.compile(
        circuit, native, profiles, drawcompiler.CompileBudget(page_box=PAGE_BOX)
    ).best()
    original = list(layout.labels)
    assert original and all(label.text_mode == "native" for label in original)
    # a second name on the same continuous run — the shape 053S refused.
    tap = original[0]
    segments = list(layout.segments)
    reach = [
        index for index, segment in enumerate(segments)
        if segment.net == tap.net
        and readability._on_polyline((tap.x, tap.y), segment.points)
    ]
    assert reach  # the retained label sits on a conductor of its run
    other = [
        (index, segment) for index, segment in enumerate(segments)
        if segment.net == tap.net and index not in reach
    ]
    assert other, "the fixture's label net should have a second conductor"
    index, segment = other[0]
    duplicate = _label(
        tap.net, float(segment.points[0][0]), float(segment.points[0][1]),
    )
    layout.labels = [*original, duplicate]
    before = _plan(layout, circuit, native, profiles)
    assert len([
        item for item in before.change.attribute_moves
        if item.owner_kind == "wire" and item.role == "net"
    ]) == 2          # two names, two rows: the row the batch removes
    _dedupe(layout.labels, layout.segments)
    assert len(layout.labels) == 1

    plan = _plan(layout, circuit, native, profiles)
    net_moves = [
        item for item in plan.change.attribute_moves
        if item.owner_kind == "wire" and item.role == "net"
    ]
    assert len(net_moves) == 1
    index_of = net_moves[0].wire_index
    wired = plan.change.draw_wires[index_of]
    assert drawapply.is_label_wire(wired)
    assert wired.net == tap.net
    # the wire the move addresses is the run's own conductor: the retained
    # label's anchor is on it, and it meets the rest of the run.
    assert any(
        readability._on_polyline((tap.x, tap.y), wire.points)
        for wire in plan.change.draw_wires if wire.net == tap.net
    )
    # the dedupe dropped a name and drew nothing: the plan's conductors are the
    # ones it had before, wire for wire.
    assert [list(wire.points) for wire in plan.change.draw_wires] == [
        list(wire.points) for wire in before.change.draw_wires
    ]
