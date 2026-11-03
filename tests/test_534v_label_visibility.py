"""053V: one **visible** name per net per module view; the rest are hidden.

053T keeps one label per *continuous* conductor run, so a net whose runs do not
meet (the Type-C's reversible `D+`/`D-` pins) still carried one printed name per
run — and two implemented rows 8.5 units apart is the L5 duplicate the page
cannot hold. 053U measured that a wire's own `Name` row can be hidden
(`valueVisible: false`) without changing one byte of the netlist. This batch
joins the two facts, and the claims are:

1. **one visible name per net per module view** — after the physical dedupe, the
   remaining disconnected labels of one net keep the net and lose only their
   text (`text_mode="native-hidden"`);
2. **the visible one is the clearer position** — the label whose box sits
   farthest from the pin its run leaves (the long stub), never the 5-unit one
   beside a reversible pin; ties keep the original order;
3. **a hidden label still names its net** — it stays in the plan, its carrier
   wire is still the drawing's label wire, and nothing is cleared, deleted or
   joined across runs;
4. **a hidden label prints nothing** — it states a version-2 move with
   `to.valueVisible: false` and no pose, registers no name row and no carrier,
   and is not measured as ink (no ghost midpoint row, no vertical-row verdict,
   no layout-label obstacle);
5. **the old drawing is untouched** — a spec without `textPlacement` writes no
   `textMode` and no `attributeMoves`, byte for byte.

Nothing under ``tests/fixtures/`` is modified: the divider fixtures are read as
they are and the synthetic layouts are built in process.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.changeplan import ChangePlan
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


def _visibility(labels, segments, flag_nets=()):
    return drawcompiler._native_label_visibility(
        labels, segments, set(flag_nets)
    )


def _two_runs(net: str = "D+"):
    """Two labels of one net on two parallel runs that do **not** meet."""
    labels = [_label(net, 0.0, 0.0), _label(net, 0.0, -60.0)]
    segments = [
        LayoutSegment(net=net, points=[(0.0, 0.0), (30.0, 0.0)]),
        LayoutSegment(net=net, points=[(0.0, -60.0), (30.0, -60.0)]),
    ]
    return labels, segments


# --------------------------------------------- one visible name per view


def test_disconnected_runs_of_one_net_keep_one_visible_name():
    labels, segments = _two_runs()
    _dedupe(labels, segments)
    assert len(labels) == 2  # the physical dedupe keeps one per run (053T)
    note = _visibility(labels, segments)
    modes = [label.text_mode for label in labels]
    assert modes.count("native") == 1
    assert modes.count("native-hidden") == 1
    # the label is kept — the net stays named — and no conductor was added.
    assert len(labels) == 2
    assert len(segments) == 2
    assert "hidden" in note


def test_the_long_stub_keeps_the_name_and_the_five_unit_one_is_hidden():
    # The measured shape: a reversible pin with a 5-unit stub next to a pin with
    # a 60-unit run. The 5-unit box is the position nobody can read.
    short = _label("D+", 485.0, 705.0, bbox=(463.0, 700.5, 477.0, 709.5))
    long = _label("D+", 430.0, 685.0, bbox=(408.0, 680.5, 422.0, 689.5))
    segments = [
        LayoutSegment(net="D+", points=[(490.0, 705.0), (485.0, 705.0)]),
        LayoutSegment(net="D+", points=[(490.0, 685.0), (430.0, 685.0)]),
    ]
    labels = [short, long]
    _dedupe(labels, segments)
    _visibility(labels, segments)
    assert short.text_mode == "native-hidden"
    assert long.text_mode == "native"


def test_a_tie_keeps_the_first_label():
    # Same box offset on both runs: the distances are equal, so the original
    # order decides and the pass stays deterministic.
    labels, segments = _two_runs("D-")
    _dedupe(labels, segments)
    _visibility(labels, segments)
    assert labels[0].text_mode == "native"
    assert labels[1].text_mode == "native-hidden"


def test_a_flag_covered_net_is_not_hidden():
    labels = [_label("GND", 0.0, 0.0), _label("GND", 0.0, -60.0)]
    segments = [
        LayoutSegment(net="GND", points=[(0.0, 0.0), (30.0, 0.0)]),
        LayoutSegment(net="GND", points=[(0.0, -60.0), (30.0, -60.0)]),
    ]
    note = _visibility(labels, segments, {"GND"})
    assert note == ""
    assert all(label.text_mode == "" for label in labels)


def test_a_label_the_dedupe_left_alone_is_not_hidden():
    # The dedupe never marked it (no conductor of its net reaches it), so this
    # pass may not decide anything about its name.
    lonely = _label("VIN", 0.0, 0.0)
    marked = _label("VIN", 0.0, -60.0, text_mode="native")
    segments = [LayoutSegment(net="VIN", points=[(0.0, -60.0), (30.0, -60.0)])]
    labels = [lonely, marked]
    note = _visibility(labels, segments)
    assert note == ""
    assert lonely.text_mode == ""
    assert marked.text_mode == "native"


# ------------------------------------------------ a hidden name still counts


def test_a_hidden_label_is_still_the_drawing_label():
    label = _label("D+", 0.0, 0.0, text_mode="native-hidden")
    plan = LayoutPlan(
        segments=[LayoutSegment(net="D+", points=[(0.0, 0.0), (0.0, -100.0)])],
        labels=[label],
    )
    # the carrier is still a label wire: the net's name rides it into the
    # editor's netlist even though no text is printed.
    from boardwise.core.layoutplan import label_wire_indices

    assert label_wire_indices(plan) == frozenset({0})
    assert plan.labels[0].net == "D+"


def test_a_hidden_label_has_no_ghost_midpoint_row():
    label = _label("D+", 0.0, 0.0, text_mode="native-hidden")
    plan = LayoutPlan(
        segments=[LayoutSegment(net="D+", points=[(0.0, 0.0), (0.0, -100.0)])],
        labels=[label],
    )
    assert readability._named_wire_rows(plan) == []


def test_a_hidden_label_is_not_judged_as_a_vertical_row():
    label = _label("D+", 0.0, 0.0, text_mode="native-hidden")
    plan = LayoutPlan(
        segments=[LayoutSegment(net="D+", points=[(0.0, 0.0), (0.0, -100.0)])],
        labels=[label],
    )
    kinds = {item.kind for item in readability._check_named_wire_rows(plan)}
    assert readability.KIND_NAME_ROW_VERTICAL not in kinds


def test_a_hidden_label_box_is_not_ink():
    hidden = _label("D+", 0.0, 0.0, text_mode="native-hidden")
    shown = _label("D-", 0.0, -60.0, text_mode="native")
    layout = LayoutPlan(segments=[], labels=[hidden, shown], texts=[], parts=[])
    boxes = drawapply._hard_ink_boxes(layout, {}, drawapply._Built(), subject=None)
    what = [name for name, _box in boxes]
    assert not any("D+" in name for name in what)
    assert any("D-" in name for name in what)


def test_native_hidden_still_offers_straight_stubs_only():
    hidden = _label("TXD", 100.0, 100.0, text_mode="native-hidden")
    native_runs = drawapply._label_stub_candidates(hidden)
    assert native_runs
    assert all(len(run.points) == 2 for run in native_runs)
    assert native_runs == [
        run for run in drawapply._label_stub_candidates(
            _label("TXD", 100.0, 100.0)
        ) if len(run.points) == 2
    ]


# ------------------------------------------------ the plan's moves, end to end


def _divider_layout(circuit, presentation, profiles) -> LayoutPlan:
    return drawcompiler.compile(
        circuit, presentation, profiles,
        drawcompiler.CompileBudget(page_box=PAGE_BOX),
    ).best()


def _two_names_plan(layout, circuit, presentation, profiles) -> ChangePlan:
    return drawapply.module_plan(
        layout, circuit, presentation, profiles, lcsc_by_part=LCSC,
    )


def test_two_names_eight_and_a_half_units_apart_are_refused_until_one_is_hidden(
    circuit, native, profiles,
):
    layout = _divider_layout(circuit, native, profiles)
    assert [label.text_mode for label in layout.labels] == ["native"]
    original = layout.labels[0]
    shown = _label(
        original.net, float(original.x), float(original.y),
        bbox=tuple(float(value) for value in original.bbox),
        text_mode="native",
    )
    # 8.5 units under the first row — the measured CH343 gap that refused the
    # plan in 053T.
    second = _label(
        original.net, 95.0, -180.0,
        bbox=(133.0, -222.0, 157.0, -213.0), text_mode="native",
    )
    layout.labels = [shown, second]
    with pytest.raises(drawapply.DrawPlanError) as caught:
        _two_names_plan(layout, circuit, native, profiles)
    assert "duplicate-carrier" in str(caught.value)

    second.text_mode = "native-hidden"
    plan = _two_names_plan(layout, circuit, native, profiles)
    wire_moves = [
        move for move in plan.change.attribute_moves if move.owner_kind == "wire"
    ]
    assert len(wire_moves) == 2


def test_a_hidden_label_states_a_version_two_hide_move(circuit, native, profiles):
    layout = _divider_layout(circuit, native, profiles)
    original = layout.labels[0]
    shown = _label(
        original.net, float(original.x), float(original.y),
        bbox=tuple(float(value) for value in original.bbox),
        text_mode="native",
    )
    hidden = _label(
        original.net, 95.0, -180.0,
        bbox=(133.0, -240.0, 157.0, -231.0), text_mode="native-hidden",
    )
    layout.labels = [shown, hidden]
    plan = _two_names_plan(layout, circuit, native, profiles)
    wire_moves = [
        move for move in plan.change.attribute_moves if move.owner_kind == "wire"
    ]
    assert len(wire_moves) == 2
    by_version = {move.move_version: move for move in wire_moves}
    visible = by_version[1]
    assert visible.value_visible is None
    # the visible name still moves to its own box centre (053S/053T).
    assert visible.x == pytest.approx(
        (shown.bbox[0] + shown.bbox[2]) / 2.0
    )
    assert visible.y == pytest.approx(
        (shown.bbox[1] + shown.bbox[3]) / 2.0
    )
    hide = by_version[2]
    assert hide.value_visible is False
    # a hide states **no** pose: the row stays where the host put it.
    assert hide.to_fields() == {"valueVisible": False}


def test_the_hide_move_round_trips_through_the_plan_reader(
    circuit, native, profiles,
):
    layout = _divider_layout(circuit, native, profiles)
    original = layout.labels[0]
    hidden = _label(
        original.net, float(original.x), float(original.y),
        bbox=tuple(float(value) for value in original.bbox),
        text_mode="native-hidden",
    )
    layout.labels = [hidden]
    plan = _two_names_plan(layout, circuit, native, profiles)
    payload = json.loads(json.dumps(plan.to_jsonable()))
    rows = [
        row for row in payload["change"]["attributeMoves"] if row["role"] == "net"
    ]
    assert [row["moveVersion"] for row in rows] == [2]
    assert rows[0]["to"] == {"valueVisible": False}
    # the reader accepts it, so a plan written by this build is one it can run.
    again = ChangePlan.from_jsonable(payload)
    assert again.change.attribute_moves[-1].value_visible is False
    assert again.change.attribute_moves[-1].move_version == 2


# ------------------------------------------------------ the old drawing stays


def test_a_spec_without_the_switch_is_byte_identical(circuit, plain, profiles):
    layout = _divider_layout(circuit, plain, profiles)
    assert all(label.text_mode == "" for label in layout.labels)
    payload = LayoutPlan(
        segments=[], labels=list(layout.labels),
    )._geometry_payload()
    assert all("textMode" not in label for label in payload["labels"])
    plan = _two_names_plan(layout, circuit, plain, profiles)
    assert plan.change.attribute_moves == []
    assert "attributeMoves" not in plan.to_jsonable()["change"]


def test_the_compiled_native_plan_marks_the_visibility(circuit, native, profiles):
    layout = _divider_layout(circuit, native, profiles)
    # one run, one name: nothing is hidden on this fixture.
    assert [label.text_mode for label in layout.labels] == ["native"]
    payload = LayoutPlan(
        segments=[], labels=[_label("VIN", 0.0, 0.0, text_mode="native-hidden")],
    )._geometry_payload()
    assert payload["labels"][0]["textMode"] == "native-hidden"
