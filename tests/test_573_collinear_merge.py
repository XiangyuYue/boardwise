"""573 / W-E2: the two legal host merges of 567-E-2, and the narrow range gate.

`outputs/hole567/e/REPRO.md` E-2 measured two shapes that the landing's own
postconditions refused although the plan had landed:

1. **two collinear plan wires** of one net merged by the host (pit 32) into one
   two-point primitive: the joint between them stops being a vertex, and
   `_page_segment_holds_end` demanded *both* ends of the page segment on this
   wire's own polyline — so the unnamed wire reported "no wire vertex" at its
   joint, and the length bucket reported a segment that did not land;
2. **a plan wire landing onto copper that was already there**, collinear and of
   the same net: the merged primitive contains the existing wire and reaches
   past it, which `census_changes` at the range gate read as "an existing
   primitive was changed" — exit 2 `range_out_of_scope`, no save.

The exemption is narrow on purpose: same net, one straight line, the existing
wire completely contained, and a planned wire that really extends beyond it.
A foreign net, a re-routed (elbow) primitive, an existing wire no longer
contained, or a merge with no planned extension are all still refused — the
057 negative (`test_e2_a_landing_that_changes_an_existing_wire_is_not_saved`)
is run beside this file for exactly that reason.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from boardwise.core.changeplan import ChangePlan
from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler

from test_057_draw_page_cli import (
    _PageEditor,
    _netlist_for,
    _stub_editor,
    _stub_export,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "drawapply"
CIRCUIT = FIXTURES / "divider.circuit.json"
PRESENTATION = FIXTURES / "divider.presentation.json"
LIBRARY = FIXTURES / "library.json"
PAGE_BOX = (0.0, -1000.0, 1200.0, 0.0)
LCSC = {"R1": "C25744", "R2": "C25744"}


# ------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def plan() -> ChangePlan:
    circuit = CircuitSpec.load(CIRCUIT)
    presentation = PresentationSpec.load(PRESENTATION)
    profiles = drawapply.load_library(LIBRARY)
    compiled = drawcompiler.compile(
        circuit, presentation, profiles,
        drawcompiler.CompileBudget(page_box=PAGE_BOX),
    )
    return drawapply.module_plan(
        compiled.candidates[0], circuit, presentation, profiles,
        lcsc_by_part=LCSC,
        notes=["plan built by test_573"],
    )


# ------------------------------------------------------------------ helpers


def _live() -> dict[tuple[str, str], str]:
    return {
        ("R1", "1"): "VIN", ("R1", "2"): "TAP",
        ("R2", "1"): "TAP", ("R2", "2"): "GND",
    }


def _page(plan: ChangePlan) -> dict:
    """The page the plan lands on, reported at the host's 0.01 reading."""
    components = [
        (part.designator, round(part.x, 2), round(part.y, 2), part.rotation, part.mirror)
        for part in plan.change.draw_parts
    ]
    named = [drawapply.wire_carries_its_name(wire) for wire in plan.change.draw_wires]
    wires = [
        (f"w-{index}", wire.net if carries else "",
         [(round(float(point[0]), 2), round(float(point[1]), 2)) for point in wire.points])
        for index, (wire, carries) in enumerate(zip(plan.change.draw_wires, named))
    ]
    netflags = [(flag.net, round(flag.x, 2), round(flag.y, 2))
                for flag in plan.change.draw_flags]
    values = {
        part.designator: part.value
        for part in plan.change.draw_parts if part.value_key
    }
    return {
        "components": [
            {"primitiveId": f"p-{name}",
             "state": {"Designator": name, "X": x, "Y": y, "ComponentType": "part",
                       "Rotation": rotation, "Mirror": mirror,
                       **({"OtherProperty": {"Value": values[name]}}
                          if name in values else {})}}
            for name, x, y, rotation, mirror in components
        ]
        + [{"primitiveId": "sheet-1",
            "state": {"ComponentType": "sheet", "Designator": "", "X": 0, "Y": 0}}]
        + [
            {"primitiveId": f"flag-{index}",
             "state": {"ComponentType": "netflag", "Designator": None, "Net": net,
                       "X": x, "Y": y}}
            for index, (net, x, y) in enumerate(netflags)
        ],
        "wires": [
            {"primitiveId": primitive_id,
             "state": {"Line": [c for pair in points for c in pair], "Net": net}}
            for primitive_id, net, points in wires
        ],
        "netlabels": [],
        "bboxes": {"sheet-1": {"minX": 0, "minY": -1000, "maxX": 1200, "maxY": 0}},
        "meta": {"available": {"components": True, "wires": True, "bboxes": True}},
    }


def _pins(plan: ChangePlan) -> dict[tuple[str, str], tuple[float, float]]:
    return {
        (part.designator, pin.number): (part.x + pin.dx, part.y + pin.dy)
        for part in plan.change.draw_parts
        for pin in part.pins
    }


def _unnamed_wire(plan: ChangePlan, net: str):
    return next(
        wire for wire in plan.change.draw_wires
        if wire.net == net and not drawapply.wire_carries_its_name(wire)
    )


def _vin_tail(plan: ChangePlan) -> tuple[tuple[float, float], tuple[float, float]]:
    """The VIN conductor's two ends: ``(free end, flag end)``.

    The free end is the one no flag sits on — the place the host merges the
    copper that was already there into.
    """
    wire = _unnamed_wire(plan, "VIN")
    first = (float(wire.points[0][0]), float(wire.points[0][1]))
    last = (float(wire.points[-1][0]), float(wire.points[-1][1]))
    anchors = {
        (round(float(flag.x), 6), round(float(flag.y), 6))
        for flag in plan.change.draw_flags
    }
    if (round(first[0], 6), round(first[1], 6)) in anchors:
        return last, first
    return first, last


def _beyond(point, tail) -> tuple[float, float]:
    """One wire length past `point`, away from `tail`."""
    return (point[0] + (point[0] - tail[0]), point[1] + (point[1] - tail[1]))


def _flat(points) -> list[float]:
    return [coordinate for point in points for coordinate in point]


def _wire_rows(ident: str, net: str, points) -> dict:
    return {"wires": [{"primitiveId": ident,
                       "state": {"Line": _flat(points), "Net": net}}]}


def _two_wire_plan(plan: ChangePlan) -> ChangePlan:
    """The divider plus one collinear continuation of its own VIN conductor."""
    payload = copy.deepcopy(plan.to_jsonable())
    free, tail = _vin_tail(plan)
    payload["change"]["wires"].append(
        {"net": "VIN", "points": [list(tail), list(_beyond(tail, free))],
         "fromPin": "", "purpose": "573 collinear continuation"}
    )
    return ChangePlan.from_jsonable(payload)


def _merged_page(two: ChangePlan, net: str) -> dict:
    """`_page`, with the two VIN primitives merged into one two-point segment.

    The joint is dropped — the shape `drawapply.py` says the host produces.
    """
    page = _page(two)
    free, tail = _vin_tail(two)
    far = _beyond(tail, free)
    kept = [
        row for row in page["wires"]
        if row["primitiveId"] not in ("w-0", f"w-{len(two.change.draw_wires) - 1}")
    ]
    page["wires"] = kept + [{
        "primitiveId": "w-merged",
        "state": {"Line": _flat([free, far]), "Net": net},
    }]
    return page


# --------------------- 1. two collinear plan wires, the host drops the joint


def test_the_host_merging_two_collinear_plan_wires_is_a_clean_landing(
    plan: ChangePlan,
) -> None:
    """567-E-2 shape 1: the joint is interior to the merged page segment.

    Measured before the fix (`outputs/hole567/e/REPRO.md` E-2, section B):
    two "no wire vertex" problems and one "a segment did not land".
    """
    two = _two_wire_plan(plan)
    page = _merged_page(two, net="VIN")
    state = drawapply.postcondition_problems(
        two, live=_live(), geometry=page, pins=_pins(two)
    )
    assert state["canvas"] == []
    assert drawapply.all_satisfied(state)


def test_a_merged_segment_of_a_foreign_net_is_still_a_problem(plan: ChangePlan) -> None:
    """The exemption is the net's copper, not any page segment through the point."""
    two = _two_wire_plan(plan)
    page = _merged_page(two, net="GND")
    state = drawapply.postcondition_problems(
        two, live=_live(), geometry=page, pins=_pins(two)
    )
    free, tail = _vin_tail(two)
    assert any(
        f"no wire vertex at ({tail[0]:g}, {tail[1]:g})" in line
        for line in state["canvas"]
    ), state["canvas"]


def test_a_same_net_segment_at_an_angle_does_not_answer_for_the_end(
    plan: ChangePlan,
) -> None:
    """Same net alone is not enough: the merged segment has to be on this line."""
    two = _two_wire_plan(plan)
    page = _page(two)
    free, tail = _vin_tail(two)
    sideways = [(free[0] - 30.0, tail[1]), (free[0] + 30.0, tail[1])]
    page["wires"] = [
        row for row in page["wires"]
        if row["primitiveId"] not in ("w-0", f"w-{len(two.change.draw_wires) - 1}")
    ] + [{"primitiveId": "w-sideways",
          "state": {"Line": _flat(sideways), "Net": "VIN"}}]
    state = drawapply.postcondition_problems(
        two, live=_live(), geometry=page, pins=_pins(two)
    )
    assert any(
        f"({tail[0]:g}, {tail[1]:g})" in line for line in state["canvas"]
    ), state["canvas"]


# ---------------------------- 2. the range helper's own judgement, item by item


def _merge_rows(plan: ChangePlan, *, before_net="VIN", after_net="VIN",
                after_points=None, before_points=None):
    free, tail = _vin_tail(plan)
    outer = _beyond(free, tail)
    before = before_points or [outer, free]
    after = after_points if after_points is not None else [outer, tail]
    return (
        drawapply.census_items(_wire_rows("w-0", before_net, before)),
        drawapply.census_items(_wire_rows("w-0", after_net, after)),
    )


def test_the_helper_exempts_exactly_the_proven_host_merge(plan: ChangePlan) -> None:
    """Same net, one straight line, before contained, and a planned extension."""
    before, after = _merge_rows(plan)
    rows = drawapply.host_merges(plan, before, after)
    assert [row["id"] for row in rows] == ["w-0"]
    assert rows[0]["net"] == "VIN"
    # Without the exemption the same pair is a change — the helper is the whole
    # reason this landing can be saved.
    assert drawapply.census_changes(before, after) != []
    assert drawapply.census_changes(
        before, after, ignore_ids=[row["id"] for row in rows]
    ) == []


def test_a_foreign_net_merge_is_not_exempt(plan: ChangePlan) -> None:
    before, after = _merge_rows(plan, after_net="GND")
    assert drawapply.host_merges(plan, before, after) == []


def test_a_re_routed_merge_is_not_exempt(plan: ChangePlan) -> None:
    """The merged primitive is a polyline with an elbow: not one straight line."""
    free, tail = _vin_tail(plan)
    outer = _beyond(free, tail)
    before, after = _merge_rows(
        plan,
        before_points=[outer, free],
        after_points=[outer, free, (free[0] - 20.0, free[1])],
    )
    assert drawapply.host_merges(plan, before, after) == []


def test_a_merge_that_no_longer_contains_the_existing_wire_is_not_exempt(
    plan: ChangePlan,
) -> None:
    free, tail = _vin_tail(plan)
    outer = _beyond(free, tail)
    short = ((free[0] + tail[0]) / 2.0, (free[1] + tail[1]) / 2.0)
    before, after = _merge_rows(
        plan,
        before_points=[outer, free],
        after_points=[outer, short],
    )
    assert drawapply.host_merges(plan, before, after) == []


def test_a_merge_with_no_planned_extension_is_not_exempt(plan: ChangePlan) -> None:
    """The planned wire is already inside the existing one — nothing of ours
    extends it, so the page's change is somebody else's."""
    free, tail = _vin_tail(plan)
    outer = _beyond(free, tail)
    far = (outer[0] + (outer[0] - tail[0]), outer[1] + (outer[1] - tail[1]))
    before = [far, tail]
    after = [outer, tail]
    before_rows = drawapply.census_items(_wire_rows("w-0", "VIN", before))
    after_rows = drawapply.census_items(_wire_rows("w-0", "VIN", after))
    assert drawapply.host_merges(plan, before_rows, after_rows) == []


def test_a_merge_between_two_named_nets_is_not_exempt(plan: ChangePlan) -> None:
    """A net that changed name is not the stable merge: '' -> 'VIN' stays a change."""
    before, after = _merge_rows(plan, before_net="", after_net="VIN")
    assert drawapply.host_merges(plan, before, after) == []


# ------------------------------- 3. the whole `draw apply`, page and range leg


class _MergeEditor(_PageEditor):
    """057's fake page plus pit 32: a placed wire that touches existing copper
    becomes **one** primitive with it.

    ``drop_joint`` is the shape `drawapply.py` states the host produces for two
    collinear wires (a two-point segment spanning both, the joint gone);
    otherwise the joint is kept and the polyline carries it, which is what a
    bent merge looks like. Either way the primitive keeps the existing wire's id
    and net — the host merged *into* it.
    """

    def __init__(self, *, merge_into: str = "", drop_joint: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.merge_into = merge_into
        self.drop_joint = drop_joint
        self.merged = 0

    async def call(self, action, params=None, **_route):
        params = params or {}
        if action == "sch.place_wire" and self.merge_into:
            target = self.items.get(self.merge_into)
            incoming = [(float(point[0]), float(point[1]))
                        for point in params.get("points") or []]
            if target is not None and incoming and _touches(target["points"], incoming):
                self.calls.append(action)
                self.writes.append((action, params))
                target["points"] = _host_union(
                    target["points"], incoming, drop_joint=self.drop_joint
                )
                self.merged += 1
                return {"uuid": self.merge_into}
        return await super().call(action, params, **_route)


def _touches(existing, incoming) -> bool:
    return any(
        abs(existing_point[0] - incoming_point[0]) < 1e-6
        and abs(existing_point[1] - incoming_point[1]) < 1e-6
        for existing_point in existing
        for incoming_point in (incoming[0], incoming[-1])
    )


def _host_union(existing, incoming, *, drop_joint: bool):
    """The merged point list: both wires, the shared point once.

    With ``drop_joint`` and one straight line, the middle points go too — the
    two collinear wires are one segment (the shape E-2 measured).
    """
    merged = [tuple(map(float, point)) for point in existing]
    for point in incoming:
        if merged and abs(point[0] - merged[-1][0]) < 1e-6 and abs(point[1] - merged[-1][1]) < 1e-6:
            continue
        merged.append(point)
    if not drop_joint or len(merged) < 3:
        return merged
    start, stop = merged[0], merged[-1]
    if all(drawapply._on_polyline(point, (start, stop)) for point in merged):
        return [start, stop]
    return merged


def _plan_file(tmp_path: Path, plan: ChangePlan) -> Path:
    path = tmp_path / "plan.json"
    plan.dump(path)
    return path


def _apply(editor, plan_path, tmp_path, *extra):
    from boardwise import cli

    report = tmp_path / "apply.json"
    code = cli.main([
        "draw", "apply", str(plan_path), "--project", "test", "--page", editor.page,
        "--circuit", str(CIRCUIT), "--presentation", str(PRESENTATION),
        "--profiles", str(LIBRARY), "--json", str(report), *extra,
    ])
    return code, json.loads(report.read_text(encoding="utf-8"))


def _seed_existing(editor: _PageEditor, plan: ChangePlan, net: str) -> tuple:
    """The copper that was on the page before: one straight wire the plan joins."""
    free, tail = _vin_tail(plan)
    outer = _beyond(free, tail)
    editor.add_wire(net, [outer, free], ident="w-0")
    return free, tail, outer


def test_a_landing_that_merges_into_preexisting_collinear_copper_is_saved(
    monkeypatch, tmp_path, capsys
) -> None:
    """567-E-2 shape 2, end to end: exit 0, saved, nothing out of range.

    The pre-existing wire carries the net the plan draws; the host merges the
    planned conductor into it and drops the joint. Before the fix the range gate
    read that as "an existing primitive was changed" (exit 2, no save).
    """
    plan = _module_plan()
    editor = _MergeEditor(page="page-1", merge_into="w-0")
    _seed_existing(editor, plan, "VIN")
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch, components={}, findings=[])
    editor.netlists = [{"components": {}}, _netlist_for(plan)]

    code, report = _apply(editor, _plan_file(tmp_path, plan), tmp_path)
    assert code == 0, report["notes"]
    assert editor.merged == 1, "the fake host merged the planned conductor in"
    assert report["persistence"] == "saved_unverified"
    assert report["range"]["outOfScope"]["changed"] == []
    merges = report["range"]["outOfScope"]["hostMerges"]
    assert [row["id"] for row in merges] == ["w-0"]
    assert merges[0]["net"] == "VIN"
    free, tail = _vin_tail(plan)
    outer = _beyond(free, tail)
    assert editor.items["w-0"]["points"] == [outer, tail], (
        "the merged primitive spans the existing wire and the plan's own end — "
        "one two-point segment, the joint gone"
    )


def test_a_landing_that_merges_into_a_foreign_net_wire_is_not_saved(
    monkeypatch, tmp_path
) -> None:
    """Negative control: same geometry, a wire of another net — still exit 2."""
    plan = _module_plan()
    editor = _MergeEditor(page="page-1", merge_into="w-0", drop_joint=False)
    _seed_existing(editor, plan, "GND")
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch, components={}, findings=[])
    editor.netlists = [{"components": {}}, _netlist_for(plan)]

    code, report = _apply(editor, _plan_file(tmp_path, plan), tmp_path)
    assert code == 2, report["notes"]
    assert report["reason"] == "range_out_of_scope"
    assert any("w-0" in line for line in report["range"]["outOfScope"]["changed"])
    assert "hostMerges" not in report["range"]["outOfScope"]
    assert "sch.doc.save" not in [action for action, _params in editor.writes]


def test_a_landing_that_merges_into_a_bent_wire_is_not_saved(
    monkeypatch, tmp_path
) -> None:
    """Negative control: same net, but the merge keeps the joint at an elbow."""
    plan = _module_plan()
    free, tail = _vin_tail(plan)
    editor = _MergeEditor(page="page-1", merge_into="w-0", drop_joint=False)
    editor.add_wire("VIN", [(free[0] - 30.0, free[1]), free], ident="w-0")
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch, components={}, findings=[])
    editor.netlists = [{"components": {}}, _netlist_for(plan)]

    code, report = _apply(editor, _plan_file(tmp_path, plan), tmp_path)
    assert code == 2, report["notes"]
    assert report["reason"] == "range_out_of_scope"
    assert any("w-0" in line for line in report["range"]["outOfScope"]["changed"])
    assert "sch.doc.save" not in [action for action, _params in editor.writes]


def _module_plan() -> ChangePlan:
    """The offline divider plan (054's fixture drawing, 054's page box)."""
    circuit = CircuitSpec.load(CIRCUIT)
    presentation = PresentationSpec.load(PRESENTATION)
    profiles = drawapply.load_library(LIBRARY)
    compiled = drawcompiler.compile(
        circuit, presentation, profiles,
        drawcompiler.CompileBudget(page_box=PAGE_BOX),
    )
    return drawapply.module_plan(
        compiled.candidates[0], circuit, presentation, profiles,
        lcsc_by_part=LCSC, notes=["plan built by test_573 (CLI)"],
    )
