"""053S: `textPlacement: native-attr` — compiler-generated `attributeMoves`.

Four claims, in the order the batch states them:

1. **the switch is optional and closed** — a spec that does not state it
   serialises exactly as before (the key is not written), a value outside
   `native-attr` is refused by name, and a page compile hands the switch to
   every module's sub-spec;
2. **`partTexts` wins where it is stated** — under `native-attr` a stated side
   overrides the symbol's own declared rows (the landing can move them there);
   a part the document does not name keeps its declared anchor, and the
   non-native path is untouched;
3. **moves are the layout's boxes** — reference/value rows and a label wire's
   name become `PlanAttributeMove`s at the layout's x/y (bbox centre when the
   text states none), with no rotation/align invented. A net move addresses the
   wire **after** `_drop_covered_runs` / `_cut_at_flag_attachments`, never the
   stale layout index;
4. **ambiguity is a refusal** — a label with no carrier, two carriers, or two
   labels on one wire raises `DrawPlanError`; the pass never picks the first.

The division fixtures are the existing `tests/fixtures/drawapply/` ones (053d's
hand-written divider for the text rows); nothing under `tests/fixtures/` is
modified.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import LayoutLabel, LayoutSegment
from boardwise.core.presentationspec import PresentationSpec, PresentationSpecError
from boardwise.core.symbolprofile import SymbolProfile, SymbolText
from boardwise.engines import drawapply, drawcompiler, pagecompiler

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
def profiles() -> dict[str, SymbolProfile]:
    return drawapply.load_library(LIBRARY)


@pytest.fixture(scope="module")
def plain() -> PresentationSpec:
    return PresentationSpec.load(PRESENTATION)


@pytest.fixture(scope="module")
def native(plain) -> PresentationSpec:
    stated = PresentationSpec.from_dict({
        **json.loads(json.dumps(plain.to_jsonable())),
        "textPlacement": "native-attr",
    })
    return stated


@pytest.fixture(scope="module")
def compiled(circuit, plain, profiles):
    return drawcompiler.compile(
        circuit, plain, profiles, drawcompiler.CompileBudget(page_box=PAGE_BOX)
    )


def _plan(layout, circuit, presentation, profiles):
    return drawapply.module_plan(
        layout, circuit, presentation, profiles, lcsc_by_part=LCSC,
    )


def _label_wire_indices(plan) -> list[int]:
    return [
        index for index, wire in enumerate(plan.change.draw_wires)
        if drawapply.is_label_wire(wire)
    ]


# -------------------------------------------------------------------- schema


def test_a_spec_that_states_no_placement_writes_no_key_and_keeps_its_bytes(
    plain, tmp_path
):
    assert plain.text_placement == ""
    written = json.dumps(plain.to_jsonable(), ensure_ascii=False, indent=2) + "\n"
    assert "textPlacement" not in written
    path = tmp_path / "legacy.presentation.json"
    plain.dump(path)
    assert path.read_text(encoding="utf-8") == written
    assert PresentationSpec.load(path).to_jsonable() == plain.to_jsonable()


def test_native_round_trips_and_is_the_only_stated_value(native):
    assert native.text_placement == "native-attr"
    payload = native.to_jsonable()
    assert payload["textPlacement"] == "native-attr"
    again = PresentationSpec.from_dict(json.loads(json.dumps(payload)))
    assert again.text_placement == "native-attr"
    assert again.to_jsonable() == payload


@pytest.mark.parametrize("value", ["native", "NATIVE-ATTR", 1, True, {"mode": "native"}])
def test_an_unknown_placement_is_refused_by_name(value):
    with pytest.raises(PresentationSpecError) as caught:
        PresentationSpec.from_dict({
            "modules": [{"id": "m-core", "parts": ["U1"], "role": "ic"}],
            "textPlacement": value,
        })
    assert "$.textPlacement" in str(caught.value)


def test_the_page_compiler_hands_the_switch_to_every_module(plain):
    spec = PresentationSpec.from_dict({
        **json.loads(json.dumps(plain.to_jsonable())),
        "textPlacement": "native-attr",
        "modules": [
            {"id": "a", "parts": ["R1"], "role": "divider"},
            {"id": "b", "parts": ["R2"], "role": "divider"},
        ],
    })
    full = CircuitSpec.load(CIRCUIT)
    for module in spec.modules:
        _sub_circuit, sub = pagecompiler._module_view(full, spec, module)
        assert sub.text_placement == "native-attr"


# -------------------------------------------------- part text rows (053d rung)


def _rows(plan, part_id):
    return {
        text.kind: tuple(text.bbox) for text in plan.texts
        if text.part_id == part_id
    }


def _declared_book() -> dict[str, SymbolProfile]:
    """The 053d divider's library, with the resistor stating its own two rows."""
    import test_053d_part_texts as base

    book = base._book()
    book["R0402"].texts = [
        SymbolText(kind="reference", x=-10.0, y=5.0),
        SymbolText(kind="value", x=-10.0, y=-15.0),
    ]
    return book


def _compiled_053d(presentation):
    import test_053d_part_texts as base

    result = drawcompiler.compile(
        base._divider_circuit(), presentation, _declared_book(),
        drawcompiler.CompileBudget(page_box=base.PAGE),
    )
    assert result.ok, result.failures
    return result.candidates[0]


def test_native_lets_a_stated_side_override_the_symbols_declared_rows():
    import test_053d_part_texts as base

    default = _compiled_053d(base._divider_presentation())
    stated_plain = _compiled_053d(
        base._divider_presentation(partTexts={"R1": "left"})
    )
    stated_native = _compiled_053d(
        base._divider_presentation(
            partTexts={"R1": "left"}, textPlacement="native-attr",
        )
    )
    declared = _rows(default, "R1")
    # 053d's own promise: without the switch the symbol's declared rows win.
    assert _rows(stated_plain, "R1") == declared
    # 053S: with it, the stated side is actually where the rows go.
    moved = _rows(stated_native, "R1")
    assert moved != declared
    part = next(item for item in stated_native.parts if item.part_id == "R1")
    assert moved["reference"][2] <= part.x and moved["value"][2] <= part.x
    # A part the document does not name keeps its declared anchor.
    assert _rows(stated_native, "R2") == _rows(default, "R2")


def test_a_native_plan_moves_the_stated_rows_and_keeps_the_unnamed_anchor(
    compiled, circuit, profiles
):
    import test_053d_part_texts as base

    layout = _compiled_053d(
        base._divider_presentation(
            partTexts={"R1": "left"}, textPlacement="native-attr",
        )
    )
    plan = drawapply.module_plan(
        layout, base._divider_circuit(), base._divider_presentation(
            partTexts={"R1": "left"}, textPlacement="native-attr",
        ), _declared_book(), lcsc_by_part={"R1": "C1", "R2": "C1"},
    )
    moves = plan.change.attribute_moves
    part_moves = {(move.spec_id, move.role): move for move in moves
                  if move.owner_kind == "part"}
    assert set(part_moves) == {("R1", "reference"), ("R1", "value")}
    for text in layout.texts:
        if text.part_id != "R1":
            continue
        move = part_moves[("R1", text.kind)]
        # 543I-6I/K: a part's `reference`/`value` ATTR move targets the row's
        # **lower-left** corner — `textmetrics.host_row_box`'s own contract, and
        # the box `drawlint`/`readability` measure the landed page with. It used to
        # target `text.x/text.y`, which the layout sets to the reserved box's
        # *centre*, so the printed ink and the write disagreed by half a row (and
        # on a rotated symbol the derived ink covered the part's own pad).
        assert (move.x, move.y) == (text.bbox[0], text.bbox[1])
        assert move.rotation is None and move.align_mode is None


# --------------------------------------------------------------- net moves


def test_a_net_move_targets_the_final_wire_and_the_label_box_centre(
    compiled, circuit, native, profiles
):
    plan = _plan(compiled.candidates[0], circuit, native, profiles)
    label = next(item for item in compiled.candidates[0].labels if item.net == "TAP")
    net_moves = [
        move for move in plan.change.attribute_moves if move.role == "net"
    ]
    assert len(net_moves) == 1
    move = net_moves[0]
    assert move.owner_kind == "wire"
    assert (move.x, move.y) == (
        (label.bbox[0] + label.bbox[2]) / 2.0,
        (label.bbox[1] + label.bbox[3]) / 2.0,
    )
    carriers = _label_wire_indices(plan)
    assert move.wire_index in carriers
    carrier = plan.change.draw_wires[move.wire_index]
    assert carrier.net == "TAP"
    # The plan's own row is what apply resolves; every other row is untouched.
    assert move.rotation is None and move.align_mode is None


def test_a_dropped_run_does_not_leave_a_stale_wire_index(
    compiled, circuit, native, profiles
):
    layout = replace(
        compiled.candidates[0],
        segments=[
            LayoutSegment(net="VIN", points=[(95.0, -80.0), (95.0, -70.0)]),
            *compiled.candidates[0].segments,
        ],
    )
    stale = next(
        index for index, segment in enumerate(layout.segments)
        if any(point == (125.0, -200.0) for point in segment.points)
    )
    plan = _plan(layout, circuit, native, profiles)
    move = next(item for item in plan.change.attribute_moves if item.role == "net")
    assert move.wire_index != stale, "the layout's index is the one the drop removed"
    assert move.wire_index == _label_wire_indices(plan)[0]
    assert drawapply.is_label_wire(plan.change.draw_wires[move.wire_index])


# --------------------------------------------------------------- ambiguity


def _native_with(label_mutator, segment=()):
    def build(compiled, circuit, native, profiles):
        layout = replace(
            compiled.candidates[0],
            labels=list(label_mutator(list(compiled.candidates[0].labels))),
            segments=[*compiled.candidates[0].segments, *segment],
        )
        return _plan(layout, circuit, native, profiles)

    return build


def test_a_label_with_no_carrier_is_refused(compiled, circuit, native, profiles):
    def stray(labels):
        return [
            replace(label, x=300.0, y=-200.0) if label.net == "TAP" else label
            for label in labels
        ]

    with pytest.raises(drawapply.DrawPlanError) as caught:
        _native_with(stray)(compiled, circuit, native, profiles)
    message = str(caught.value)
    assert "native label ambiguity" in message and "TAP" in message


def test_a_label_on_two_label_wires_is_refused(compiled, circuit, native, profiles):
    crossing = (LayoutSegment(net="TAP", points=[(125.0, -180.0), (125.0, -220.0)]),)
    with pytest.raises(drawapply.DrawPlanError) as caught:
        _native_with(lambda labels: labels, crossing)(
            compiled, circuit, native, profiles
        )
    message = str(caught.value)
    assert "native label ambiguity" in message and "wire[" in message


def test_two_labels_on_one_wire_are_refused(compiled, circuit, native, profiles):
    def second(labels):
        first = next(label for label in labels if label.net == "TAP")
        return [*labels, replace(first, x=100.0, bbox=(100.0, -204.5, 124.0, -195.5))]

    with pytest.raises(drawapply.DrawPlanError) as caught:
        _native_with(second)(compiled, circuit, native, profiles)
    message = str(caught.value)
    assert "native label ambiguity" in message and "both land" in message


# ------------------------------------------------------- the default is silent


def test_a_non_native_plan_has_no_moves_and_makes_no_attribute_call(
    monkeypatch, compiled, circuit, plain, profiles, tmp_path
):
    plan = _plan(compiled.candidates[0], circuit, plain, profiles)
    assert plan.change.attribute_moves == []
    payload = plan.to_jsonable()
    assert "attributeMoves" not in json.dumps(payload)

    import test_534r_attribute_moves as attr
    import test_054_draw_cli as base

    path = tmp_path / "plain.plan.json"
    plan.dump(path)
    editor = attr._AttrEditor()
    base._stub_editor(monkeypatch, editor)
    base._stub_export(monkeypatch, components={}, findings=[])
    report = tmp_path / "apply.json"
    from boardwise import cli

    cli.main([
        "draw", "apply", str(path), "--project", "test", "--new-page",
        "--page-name", "534S", "--json", str(report),
    ])
    # The landing itself ran (parts were written); what this pins is that a plan
    # without moves asks the host for no attribute work at all.
    assert editor.writes, "the landing has to reach the writes for this to mean anything"
    assert "sch.list_attributes" not in editor.calls
    assert "sch.move_attribute" not in editor.calls
