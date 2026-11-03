"""053R: optional attribute moves in a `draw-module` plan and its apply.

What is pinned here, in the order the shared contract (`tasks/shared-platform.md`
§6) states it:

1. **Nothing changes for a plan without moves** — the document has no
   `attributeMoves` key at all, and apply makes exactly the calls it always made
   (no `sch.list_attributes`, no `sys.probe`, no `sch.move_attribute`).
2. **The row contract is closed** — `moveVersion` 1 only, `owner` a part of this
   plan or a wire index, `role` the one its owner allows, `to` only
   x/y/rotation/alignMode. Every other key or value is refused at load, so an
   illegal plan cannot reach apply at all.
3. **Apply resolves the target, it does not trust ids** — the parent is the id
   the host returned, the expected value is read back from the page (a part's
   real designator; the wire's net), two candidates or none are refused, and a
   move the host did not take is `applied: false`, stops the run and saves
   nothing.

The editor fake is the 054 one plus the four actions 053Q measured, so these
tests exercise the same flow the landed drawing uses.
"""

import json
import re

import pytest

from boardwise import cli
from boardwise.core.changeplan import (
    PLAN_VERSION,
    ChangePlan,
    ChangePlanError,
    PlanChange,
    PlanAttributeMove,
    PlanDrawPart,
    PlanDrawWire,
)

import test_054_draw_cli as base


class _AttrEditor(base._FakeEditor):
    """The 054 fake with an attribute table and the 053Q actions."""

    def __init__(self, *args, attributes=(), probe_status="function",
                 move_fails=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.attributes = [dict(row) for row in attributes]
        self.probe_status = probe_status
        self.move_fails = move_fails
        self.attr_calls = []

    async def call(self, action, params=None, **_route):
        params = params or {}
        if action == "sch.list_attributes":
            self.attr_calls.append(action)
            self.calls.append(action)
            parent = params.get("parentPrimitiveId")
            rows = [
                dict(row) for row in self.attributes
                if not parent or row.get("parentPrimitiveId") == parent
            ]
            return {"pageUuid": params.get("pageUuid"), "parentPrimitiveId": parent,
                    "count": len(rows), "attributes": rows, "readErrors": []}
        if action == "sys.probe":
            self.attr_calls.append(action)
            self.calls.append(action)
            return {"version": "4.1.93", "checks": {"sch_PrimitiveAttribute": {
                "present": True, "kind": "object", "checked": 1,
                "missing": 0 if self.probe_status == "function" else 1,
                "status": {"modify": self.probe_status}, "arity": {},
            }}}
        if action == "sch.move_attribute":
            self.attr_calls.append(action)
            self.calls.append(action)
            self.writes.append((action, dict(params)))
            row = next(
                (item for item in self.attributes
                 if item.get("primitiveId") == params.get("primitiveId")),
                None,
            )
            answered = {"applied": False, "mismatched": [
                {"field": "x", "expected": params.get("x"), "actual": None}]}
            if self.move_fails:
                return answered
            if row is not None and row.get("key") == params.get("expectedKey") \
                    and row.get("value") == params.get("expectedValue"):
                for wire_key, field in (("x", "x"), ("y", "y"),
                                        ("rotation", "rotation"),
                                        ("alignMode", "alignMode"),
                                        ("valueVisible", "valueVisible")):
                    if wire_key in params:
                        wanted = params[wire_key]
                        if self.probe_status != "function":
                            continue
                        row[field] = wanted
                after = {name: row.get(name) for name in
                         ("x", "y", "rotation", "alignMode", "valueVisible")
                         if name in params}
                answered = {"applied": True, "after": after, "mismatched": []}
            return answered
        return await super().call(action, params, **_route)


def _attributes(plan: ChangePlan, *, duplicates=0, hidden=False, wire_offset=1):
    """The page's attribute rows for a freshly landed plan."""
    rows = []
    for part in plan.change.draw_parts:
        rows.append({
            "primitiveId": f"a-ref-{part.spec_id}", "parentPrimitiveId": f"c-{part.designator}",
            "key": "Designator", "value": part.designator, "x": part.x, "y": part.y + 20,
            "rotation": 0, "alignMode": 2, "valueVisible": True,
        })
        if not hidden:
            # The host renders a part's value through its own formula: a real
            # R900 shows ``Name.value == "={Value}"`` while the plan says ``1k``.
            rows.append({
                "primitiveId": f"a-val-{part.spec_id}",
                "parentPrimitiveId": f"c-{part.designator}",
                "key": "Name", "value": "={Value}", "x": part.x, "y": part.y + 40,
                "rotation": 0, "alignMode": 2, "valueVisible": True,
            })
    duplicate_at = _label_wire(plan) if duplicates else -1
    for index, wire in enumerate(plan.change.draw_wires):
        count = 2 if index == duplicate_at else 1
        for copy in range(count):
            rows.append({
                "primitiveId": f"a-net-{index}-{copy}",
                "parentPrimitiveId": f"w-{index + wire_offset}",
                "key": "Name", "value": wire.net, "x": 370, "y": 300,
                "rotation": None, "alignMode": None, "valueVisible": True,
            })
    return rows


def _with_moves(tmp_path, plan, moves):
    plan.change.attribute_moves = list(moves)
    path = tmp_path / "moves.json"
    plan.dump(path)
    return path


def _reference_move(plan, spec_id=None, **to):
    part = next(item for item in plan.change.draw_parts
                if spec_id is None or item.spec_id == spec_id)
    fields = {"x": part.x, "y": part.y + 70}
    fields.update(to)
    return PlanAttributeMove(owner_kind="part", spec_id=part.spec_id,
                             role="reference", **fields)


def _label_wire(plan):
    """The index of the wire that **is** the label (the only one carrying its name)."""
    from boardwise.engines import drawapply
    return next(index for index, wire in enumerate(plan.change.draw_wires)
                if drawapply.wire_carries_its_name(wire))


def _net_move(plan, index=None, **to):
    wire = plan.change.draw_wires[_label_wire(plan) if index is None else index]
    fields = {"x": wire.points[0][0], "y": wire.points[0][1] - 20}
    fields.update(to)
    return PlanAttributeMove(
        owner_kind="wire", wire_index=_label_wire(plan) if index is None else index,
        role="net", **fields)


def _value_move(plan, spec_id=None, **to):
    part = next(item for item in plan.change.draw_parts
                if spec_id is None or item.spec_id == spec_id)
    fields = {"x": part.x, "y": part.y + 90}
    fields.update(to)
    return PlanAttributeMove(owner_kind="part", spec_id=part.spec_id,
                             role="value", **fields)


def _apply(monkeypatch, tmp_path, editor, plan_path, report_name="apply.json"):
    base._stub_editor(monkeypatch, editor)
    base._stub_export(monkeypatch, components={}, findings=[])
    report = tmp_path / report_name
    code = cli.main([
        "draw", "apply", str(plan_path), "--project", "test", "--new-page",
        "--page-name", "534R", "--json", str(report),
    ])
    return code, json.loads(report.read_text(encoding="utf-8"))


# --------------------------------------------------------- the row contract
def test_a_plan_without_moves_serialises_exactly_as_before():
    change = PlanChange(kind="draw-module")
    payload = ChangePlan(change=change).to_jsonable()
    assert "attributeMoves" not in payload["change"]
    assert "attributeMoves" not in json.dumps(payload)


def test_moves_round_trip_and_only_requested_fields_are_written(tmp_path):
    _path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    plan.change.attribute_moves = [
        PlanAttributeMove(owner_kind="part", spec_id=plan.change.draw_parts[0].spec_id,
                          role="reference", x=280.0, y=335.0),
        PlanAttributeMove(owner_kind="wire", wire_index=0, role="net",
                          x=370.0, y=320.0, align_mode=2),
    ]
    payload = plan.to_jsonable()
    spec_id = plan.change.draw_parts[0].spec_id
    assert payload["change"]["attributeMoves"] == [
        {"moveVersion": 1, "owner": {"kind": "part", "specId": spec_id},
         "role": "reference", "to": {"x": 280.0, "y": 335.0}},
        {"moveVersion": 1, "owner": {"kind": "wire", "index": 0},
         "role": "net", "to": {"x": 370.0, "y": 320.0, "alignMode": 2}},
    ]
    read = ChangePlan.from_jsonable(payload)
    assert read.change.attribute_moves == plan.change.attribute_moves


def _real_plan(tmp_path):
    _path, plan = base._plan(tmp_path)
    return ChangePlan.from_jsonable(plan.to_jsonable())


def _invalid_payload(tmp_path, row):
    """A plan that loads cleanly, with **one** illegal `attributeMoves` row added.

    The fixture is the real compiled plan (`base._plan`), not a hand-written
    minimum: the earlier minimal document was refused by an unrelated guard
    (empty `profiles`) before the row was ever read, so the negative contract
    looked green while testing nothing. Everything here is valid except the row.
    """
    payload = json.loads(json.dumps(_real_plan(tmp_path).to_jsonable()))
    payload["change"]["attributeMoves"] = [row]
    return payload


def _part_row(plan, **overrides):
    row = {"moveVersion": 1,
           "owner": {"kind": "part", "specId": plan.change.draw_parts[0].spec_id},
           "role": "reference", "to": {"x": 1, "y": 2}}
    row.update(overrides)
    return row


@pytest.mark.parametrize("mutate,reason", [
    (lambda row: dict(row, moveVersion=3), "moveVersion"),
    (lambda row: dict(row, moveVersion=True), "moveVersion"),
    (lambda row: dict(row, owner={"kind": "component", "specId": "R1"}), r"owner\.kind"),
    (lambda row: dict(row, owner={"kind": "part", "primitiveId": "p-1"}), "primitiveId"),
    (lambda row: dict(row, role="net"), "role"),
    (lambda row: dict(row, to={}), "at least one"),
    (lambda row: dict(row, to={"x": 1, "key": "Name"}), "carries key"),
    (lambda row: dict(row, to={"alignMode": 10}), "alignMode"),
    (lambda row: dict(row, to={"x": "left"}), "finite number"),
    (lambda row: dict(row, owner={"kind": "wire", "index": 99}, role="net"),
     "outside this plan"),
    (lambda row: dict(row, owner={"kind": "part", "specId": "R9"}), "does not"),
])
def test_a_row_outside_the_contract_is_refused_at_load(tmp_path, mutate, reason):
    payload = _invalid_payload(tmp_path, mutate(_part_row(_real_plan(tmp_path))))
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.from_jsonable(payload)
    message = str(caught.value)
    assert "attributeMoves[0]" in message, message
    assert re.search(reason, message), message


def test_an_extra_row_key_is_refused_by_name(tmp_path):
    row = _part_row(_real_plan(tmp_path), value="R9")
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.from_jsonable(_invalid_payload(tmp_path, row))
    message = str(caught.value)
    assert "attributeMoves[0]" in message and "carries value" in message, message


# ------------------------------------------------------------ empty moves
def test_a_plan_without_moves_makes_no_attribute_call(monkeypatch, tmp_path):
    plan_path, plan = base._plan(tmp_path)
    editor = _AttrEditor(exists=False,
                         netlists=[{"components": {}}, base._live_netlist_for(plan)])
    code, payload = _apply(monkeypatch, tmp_path, editor, plan_path)
    assert code == 0, payload
    assert editor.attr_calls == [], (
        "an empty move list must not add a list_attributes / probe / move call"
    )
    assert "attributeMoves" not in payload
    assert "sch.doc.save" in [action for action, _params in editor.writes]


# ------------------------------------------------------------- non-empty
def test_two_moves_resolve_the_page_and_land(monkeypatch, tmp_path):
    plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    moves = [_reference_move(plan), _net_move(plan)]
    plan.change.attribute_moves = moves
    path = tmp_path / "moves.json"
    plan.dump(path)
    editor = _AttrEditor(exists=False, attributes=_attributes(plan),
                         netlists=[{"components": {}}, base._live_netlist_for(plan)])
    code, payload = _apply(monkeypatch, tmp_path, editor, path, "moves-apply.json")
    assert code == 0, payload
    move_writes = [params for action, params in editor.writes
                   if action == "sch.move_attribute"]
    assert len(move_writes) == 2
    part = plan.change.draw_parts[0]
    assert move_writes[0]["parentPrimitiveId"] == f"c-{part.designator}"
    assert move_writes[0]["expectedKey"] == "Designator"
    assert move_writes[0]["expectedValue"] == part.designator, (
        "the reference value is read back from the page, not assumed"
    )
    assert "primitiveId" not in move_writes[0] or move_writes[0]["primitiveId"]
    net_write = move_writes[1]
    assert net_write["parentPrimitiveId"] == f"w-{_label_wire(plan) + 1}"
    assert net_write["expectedKey"] == "Name"
    assert net_write["expectedValue"] == plan.change.draw_wires[_label_wire(plan)].net
    # The capability check runs before the first part is written.
    assert editor.calls.index("sch.list_attributes") < editor.calls.index(
        "sch.place_component")
    assert editor.calls.count("sys.probe") == 1
    assert payload["attributeMoves"]["applied"] is True
    assert [item["role"] for item in payload["attributeMoves"]["moves"]] == [
        "reference", "net"]
    assert all(item["applied"] for item in payload["attributeMoves"]["moves"])
    assert "sch.doc.save" in [action for action, _params in editor.writes]


def test_a_move_the_host_did_not_take_stops_the_run_and_saves_nothing(
    monkeypatch, tmp_path
):
    plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    plan.change.attribute_moves = [_reference_move(plan)]
    path = tmp_path / "moves.json"
    plan.dump(path)
    editor = _AttrEditor(exists=False, attributes=_attributes(plan), move_fails=True,
                         netlists=[{"components": {}}, base._live_netlist_for(plan)])
    code, payload = _apply(monkeypatch, tmp_path, editor, path, "noop.json")
    assert code != 0
    assert payload["outcome"] == "unknown" or code == 4
    assert "sch.doc.save" not in [action for action, _params in editor.writes]


def test_two_candidate_name_rows_are_refused_and_nothing_moves(monkeypatch, tmp_path):
    plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    plan.change.attribute_moves = [_net_move(plan)]
    path = tmp_path / "moves.json"
    plan.dump(path)
    editor = _AttrEditor(exists=False, attributes=_attributes(plan, duplicates=1),
                         netlists=[{"components": {}}, base._live_netlist_for(plan)])
    code, payload = _apply(monkeypatch, tmp_path, editor, path, "dupes.json")
    assert code != 0
    assert not [params for action, params in editor.writes
                if action == "sch.move_attribute"], "no candidate is picked"
    assert "sch.doc.save" not in [action for action, _params in editor.writes]


def test_a_missing_name_row_is_refused_and_nothing_moves(monkeypatch, tmp_path):
    plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    plan.change.attribute_moves = [_net_move(plan)]
    path = tmp_path / "moves.json"
    plan.dump(path)
    editor = _AttrEditor(exists=False, attributes=[],
                         netlists=[{"components": {}}, base._live_netlist_for(plan)])
    code, payload = _apply(monkeypatch, tmp_path, editor, path, "missing.json")
    assert code != 0
    assert not [params for action, params in editor.writes
                if action == "sch.move_attribute"]
    assert "sch.doc.save" not in [action for action, _params in editor.writes]


def test_a_host_without_modify_is_refused_before_any_part_is_written(
    monkeypatch, tmp_path
):
    plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    plan.change.attribute_moves = [_reference_move(plan)]
    path = tmp_path / "moves.json"
    plan.dump(path)
    editor = _AttrEditor(exists=False, attributes=_attributes(plan),
                         probe_status="undefined",
                         netlists=[{"components": {}}, base._live_netlist_for(plan)])
    code, payload = _apply(monkeypatch, tmp_path, editor, path, "noapi.json")
    assert code == 4
    assert payload["reason"] == "attribute_api_missing"
    assert not [params for action, params in editor.writes
                if action == "sch.move_attribute"]
    assert "sch.doc.save" not in [action for action, _params in editor.writes]


# ------------------------------------------------------------ idempotence
def _snap_attributes(rows, plan):
    """Move the table's rows to the positions the plan asks for."""
    by_id = {row["primitiveId"]: row for row in rows}
    parts = {part.spec_id: part for part in plan.change.draw_parts}
    for index, move in enumerate(plan.change.attribute_moves):
        if move.owner_kind == "part":
            part = parts[move.spec_id]
            row = by_id.get(f"a-ref-{move.spec_id}" if move.role == "reference"
                            else f"a-val-{move.spec_id}")
        else:
            row = by_id.get(f"a-net-{move.wire_index}-0")
        assert row is not None, (index, move)
        for field, column in (("x", "x"), ("y", "y"),
                              ("rotation", "rotation"), ("alignMode", "alignMode")):
            if field in move.to_fields():
                row[column] = move.to_fields()[field]
    return rows


def _apply_on_existing_page(monkeypatch, tmp_path, editor, plan_path, name):
    base._stub_editor(monkeypatch, editor)
    base._stub_export(monkeypatch, components={}, findings=[])
    report = tmp_path / name
    code = cli.main([
        "draw", "apply", str(plan_path), "--project", "test", "--page", editor.page,
        "--json", str(report),
    ])
    return code, json.loads(report.read_text(encoding="utf-8"))


def _plan_with_moves(tmp_path, plan, moves, name="moves.json"):
    plan.change.attribute_moves = list(moves)
    path = tmp_path / name
    plan.dump(path)
    return path


def test_attributes_not_moved_are_not_already_applied(monkeypatch, tmp_path):
    """Parts, wires and the netlist can all hold while the text has not moved."""
    _plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    path = _plan_with_moves(
        tmp_path, plan, [_reference_move(plan), _net_move(plan)], "stale.json"
    )
    # The table sits where a pre-053R build left it: the plan's *old* positions.
    editor = _attr_page(plan)
    editor.attributes = _attributes(plan, wire_offset=0)
    editor.calls.clear()
    code, payload = _apply_on_existing_page(
        monkeypatch, tmp_path, editor, path, "stale-apply.json"
    )
    assert payload["outcome"] != "already_applied", payload.get("reason")
    assert payload["attributeMoves"]["probe"]["checked"] is True
    assert payload["attributeMoves"]["probe"]["problems"], (
        "the probe names what is not in place instead of answering 'already applied'"
    )
    assert not [params for action, params in editor.writes
                if action == "sch.move_attribute"], "the probe itself never moves text"
    assert "sch.doc.save" not in [action for action, _params in editor.writes]


def test_attributes_in_place_are_already_applied_with_zero_writes(monkeypatch, tmp_path):
    _plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    moves = [_reference_move(plan), _net_move(plan)]
    path = _plan_with_moves(tmp_path, plan, moves, "done.json")
    editor = _attr_page(plan)
    editor.attributes = _snap_attributes(_attributes(plan, wire_offset=0), plan)
    editor.calls.clear()
    code, payload = _apply_on_existing_page(
        monkeypatch, tmp_path, editor, path, "done-apply.json"
    )
    assert code == 0, payload
    assert payload["outcome"] == "already_applied"
    actions = [action for action, _params in editor.writes]
    assert "sch.move_attribute" not in actions
    assert "sch.place_component" not in actions
    assert "sch.place_wire" not in actions
    assert "sch.doc.save" not in actions
    assert payload["attributeMoves"]["probe"]["problems"] == []


def test_a_moved_value_is_already_applied_though_its_name_is_the_host_formula(
    monkeypatch, tmp_path
):
    """A real part's visible ``Name`` is ``={Value}``, never the design value.

    The probe used to compare a ``value`` move's row content against
    ``part.value`` (``1k``), so a page where the value *had* been moved answered
    "not in place" forever and re-runs fell through to the write path.
    """
    _plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    part = plan.change.draw_parts[0]
    assert part.value and part.value != "={Value}"
    moves = [_reference_move(plan), _net_move(plan), _value_move(plan, part.spec_id)]
    path = _plan_with_moves(tmp_path, plan, moves, "value-done.json")
    editor = _attr_page(plan)
    editor.attributes = _snap_attributes(_attributes(plan, wire_offset=0), plan)
    editor.calls.clear()
    code, payload = _apply_on_existing_page(
        monkeypatch, tmp_path, editor, path, "value-done-apply.json"
    )
    assert code == 0, payload
    assert payload["outcome"] == "already_applied"
    assert payload["attributeMoves"]["probe"]["problems"] == []
    actions = [action for action, _params in editor.writes]
    assert "sch.move_attribute" not in actions
    assert "sch.doc.save" not in actions


def test_a_value_that_has_not_moved_is_not_already_applied(monkeypatch, tmp_path):
    """Same page, same formula — only the value row still sits at its old spot."""
    _plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    part = plan.change.draw_parts[0]
    moves = [_reference_move(plan), _net_move(plan), _value_move(plan, part.spec_id)]
    path = _plan_with_moves(tmp_path, plan, moves, "value-stale.json")
    editor = _attr_page(plan)
    rows = _snap_attributes(_attributes(plan, wire_offset=0), plan)
    for row in rows:
        if row["primitiveId"] == f"a-val-{part.spec_id}":
            row["x"], row["y"] = part.x, part.y + 40
    editor.attributes = rows
    editor.calls.clear()
    code, payload = _apply_on_existing_page(
        monkeypatch, tmp_path, editor, path, "value-stale-apply.json"
    )
    assert payload["outcome"] != "already_applied", payload.get("reason")
    problems = payload["attributeMoves"]["probe"]["problems"]
    assert any("attributeMoves[2]" in problem for problem in problems), problems
    assert not [params for action, params in editor.writes
                if action == "sch.move_attribute"], "the probe itself never moves text"


def _attr_page(plan):
    """`base._page_with(plan)`, but the fake also answers the 053Q actions."""
    import boardwise.engines.drawapply as drawapply
    editor = _AttrEditor(page="page-1", netlists=[base._live_netlist_for(plan)])
    for part in plan.change.draw_parts:
        editor.add(part.designator, part.x, part.y, rotation=part.rotation,
                   mirror=part.mirror, lcsc=part.lcsc,
                   value=part.value if part.value_key else None)
    for wire in plan.change.draw_wires:
        editor.wire(wire.net if drawapply.wire_carries_its_name(wire) else "",
                    wire.points)
    for flag in plan.change.draw_flags:
        editor.flag(flag.net, flag.x, flag.y)
    return editor


def test_a_reference_move_uses_the_designator_the_host_placed(monkeypatch, tmp_path):
    """specId R1 can land as R7 — the move must follow the page, not the plan.

    `primitive_ids` is keyed by the designator the host answered, and an allocated
    plan numbers parts from the project pool: here the pool holds R1..R6, so the
    plan's spec ids R1/R2 are placed as R7/R8. Looking the parent up by spec id
    therefore found nothing on the real host, while the fake — whose designators
    happened to equal its spec ids — stayed green. The move has to land on `c-R7`
    with `expectedValue: "R7"`, never on a guessed `c-R1`.
    """
    _plan_path, plan = base._plan(tmp_path, pool=[f"R{index}" for index in range(1, 7)])
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    placed = {part.spec_id: part.designator for part in plan.change.draw_parts}
    assert placed == {"R1": "R7", "R2": "R8"}, placed
    moves = [_reference_move(plan, spec_id="R1"), _net_move(plan)]
    path = _plan_with_moves(tmp_path, plan, moves, "renamed.json")

    editor = _AttrEditor(exists=False, attributes=_attributes(plan),
                         netlists=[{"components": {}}, base._live_netlist_for(plan)])
    base._stub_editor(monkeypatch, editor)
    base._stub_export(
        monkeypatch,
        components={f"R{index}": object() for index in range(1, 7)},
        findings=[],
    )
    report = tmp_path / "renamed-apply.json"
    code = cli.main(["draw", "apply", str(path), "--project", "test", "--new-page",
                     "--page-name", "534R", "--json", str(report)])
    payload = json.loads(report.read_text(encoding="utf-8"))

    assert code == 0, payload
    reference = [params for action, params in editor.writes
                 if action == "sch.move_attribute"][0]
    assert reference["parentPrimitiveId"] == "c-R7"
    assert reference["expectedValue"] == "R7"
    assert reference["parentPrimitiveId"] != "c-R1"
    assert [item["applied"] for item in payload["attributeMoves"]["moves"]] == [True, True]
    assert payload["attributeMoves"]["applied"] is True
    assert payload["outcome"] != "already_applied"


# ---------------------------------------------------------------------------
# 053U: version-2 `valueVisible` — hide one duplicate net name, touch nothing else
# ---------------------------------------------------------------------------


def _hide_move(plan, **extra):
    return PlanAttributeMove(
        owner_kind="wire", wire_index=_label_wire(plan), role="net",
        move_version=2, value_visible=False, **extra,
    )


def _wire_row(plan):
    return next(
        row for row in _attributes(plan, wire_offset=0)
        if row["primitiveId"] == f"a-net-{_label_wire(plan)}-0"
    )


def test_a_row_without_moveVersion_is_refused(tmp_path):
    plan = _real_plan(tmp_path)
    payload = json.loads(json.dumps(plan.to_jsonable()))
    payload["change"]["attributeMoves"] = [{
        "owner": {"kind": "wire", "index": _label_wire(plan)},
        "role": "net", "to": {"x": 1, "y": 2},
    }]
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.from_jsonable(payload)
    assert "attributeMoves[0]" in str(caught.value)
    assert re.search("no moveVersion", str(caught.value))


def test_an_explicit_version_1_round_trips_and_writes_it_back(tmp_path):
    plan = _real_plan(tmp_path)
    payload = json.loads(json.dumps(plan.to_jsonable()))
    payload["change"]["attributeMoves"] = [{
        "moveVersion": 1,
        "owner": {"kind": "wire", "index": _label_wire(plan)},
        "role": "net", "to": {"x": 1, "y": 2},
    }]
    read = ChangePlan.from_jsonable(payload)
    assert read.change.attribute_moves[0].move_version == 1
    assert read.change.attribute_moves[0].value_visible is None
    assert read.to_jsonable()["change"]["attributeMoves"][0]["moveVersion"] == 1


def test_a_v2_hide_round_trips_and_may_stand_alone(tmp_path):
    plan = _real_plan(tmp_path)
    plan.change.attribute_moves = [_hide_move(plan)]
    payload = plan.to_jsonable()
    assert payload["change"]["attributeMoves"] == [{
        "moveVersion": 2,
        "owner": {"kind": "wire", "index": _label_wire(plan)},
        "role": "net", "to": {"valueVisible": False},
    }]
    assert ChangePlan.from_jsonable(payload).change.attribute_moves == plan.change.attribute_moves


def test_v2_visibility_on_a_part_is_refused(tmp_path):
    plan = _real_plan(tmp_path)
    row = {"moveVersion": 2,
           "owner": {"kind": "part", "specId": plan.change.draw_parts[0].spec_id},
           "role": "value", "to": {"valueVisible": False}}
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.from_jsonable(_invalid_payload(tmp_path, row))
    assert "wire/'net' only" in str(caught.value)


@pytest.mark.parametrize("bad", ["false", 0, 1, None])
def test_v2_valueVisible_must_be_a_boolean(tmp_path, bad):
    plan = _real_plan(tmp_path)
    row = {"moveVersion": 2,
           "owner": {"kind": "wire", "index": _label_wire(plan)},
           "role": "net", "to": {"valueVisible": bad}}
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.from_jsonable(_invalid_payload(tmp_path, row))
    assert "must be a boolean" in str(caught.value)


def test_version_1_may_not_carry_valueVisible(tmp_path):
    plan = _real_plan(tmp_path)
    row = {"moveVersion": 1,
           "owner": {"kind": "wire", "index": _label_wire(plan)},
           "role": "net", "to": {"valueVisible": False}}
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.from_jsonable(_invalid_payload(tmp_path, row))
    assert "moveVersion 2" in str(caught.value)


def test_a_hide_lands_and_the_wire_keeps_its_name_and_netlist(monkeypatch, tmp_path):
    _plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    path = _plan_with_moves(tmp_path, plan, [_hide_move(plan)], "hide.json")
    rows = _attributes(plan)
    editor = _AttrEditor(exists=False, attributes=rows,
                         netlists=[{"components": {}}, base._live_netlist_for(plan)])
    target = next(row for row in editor.attributes
                  if row["primitiveId"] == f"a-net-{_label_wire(plan)}-0")
    assert target["valueVisible"] is True
    before_row = dict(target)
    live = base._live_netlist_for(plan)
    netlist_before = json.dumps(live, sort_keys=True, default=str)
    editor.calls.clear()

    code, payload = _apply(monkeypatch, tmp_path, editor, path, "hide-apply.json")

    assert code == 0, payload
    assert payload["attributeMoves"]["applied"] is True
    requests = [params for action, params in editor.writes if action == "sch.move_attribute"]
    assert len(requests) == 1, requests
    assert requests[0]["valueVisible"] is False
    assert "x" not in requests[0] and "y" not in requests[0]
    assert requests[0]["expectedKey"] == "Name"
    assert target["valueVisible"] is False
    # The row is the same ATTR carrying the same net — nothing deleted, renamed
    # or moved, and no label/wire primitive was created to "replace" it.
    assert target["primitiveId"] == before_row["primitiveId"]
    assert target["value"] == before_row["value"]
    assert (target["x"], target["y"]) == (before_row["x"], before_row["y"])
    actions = [action for action, _params in editor.writes]
    for forbidden in ("sch.place_netlabel", "sch.create_net_label",
                      "sch.delete_primitives", "sch.set_attribute"):
        assert forbidden not in actions, actions
    assert actions.count("sch.place_wire") == len(plan.change.draw_wires), (
        "no extra wire may be drawn across pins to replace the hidden text"
    )
    assert json.dumps(editor.netlists[-1], sort_keys=True, default=str) == netlist_before
    assert "sch.doc.save" in actions


def test_a_hidden_row_is_already_applied_with_zero_writes(monkeypatch, tmp_path):
    _plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    path = _plan_with_moves(tmp_path, plan, [_hide_move(plan)], "hide-done.json")
    editor = _attr_page(plan)
    rows = _snap_attributes(_attributes(plan, wire_offset=0), plan)
    for row in rows:
        if row["primitiveId"] == f"a-net-{_label_wire(plan)}-0":
            row["valueVisible"] = False
    editor.attributes = rows
    editor.calls.clear()

    code, payload = _apply_on_existing_page(
        monkeypatch, tmp_path, editor, path, "hide-done-apply.json"
    )

    assert code == 0, payload
    assert payload["outcome"] == "already_applied"
    assert payload["attributeMoves"]["probe"]["problems"] == []
    actions = [action for action, _params in editor.writes]
    assert "sch.move_attribute" not in actions
    assert "sch.doc.save" not in actions


def test_a_visible_row_is_not_already_applied_for_a_hide(monkeypatch, tmp_path):
    _plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    path = _plan_with_moves(tmp_path, plan, [_hide_move(plan)], "hide-visible.json")
    editor = _attr_page(plan)
    editor.attributes = _snap_attributes(_attributes(plan, wire_offset=0), plan)
    editor.calls.clear()

    _code, payload = _apply_on_existing_page(
        monkeypatch, tmp_path, editor, path, "hide-visible-apply.json"
    )

    assert payload["outcome"] != "already_applied"
    problems = payload["attributeMoves"]["probe"]["problems"]
    assert any("attributeMoves[0]" in problem for problem in problems), problems


def test_a_duplicated_net_name_is_not_picked_for_a_hide(monkeypatch, tmp_path):
    _plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    path = _plan_with_moves(tmp_path, plan, [_hide_move(plan)], "hide-dup.json")
    editor = _AttrEditor(exists=False, attributes=_attributes(plan, duplicates=1),
                         netlists=[{"components": {}}, base._live_netlist_for(plan)])

    code, payload = _apply(monkeypatch, tmp_path, editor, path, "hide-dup-apply.json")

    assert code != 0, payload
    requests = [params for action, params in editor.writes if action == "sch.move_attribute"]
    assert requests == [], "two Name=net rows are a refusal, never a pick"
    actions = [action for action, _params in editor.writes]
    assert "sch.doc.save" not in actions


def test_a_missing_valueVisible_read_port_refuses_before_any_write(monkeypatch, tmp_path):
    _plan_path, plan = base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    path = _plan_with_moves(tmp_path, plan, [_hide_move(plan)], "hide-noport.json")
    rows = _attributes(plan)
    for row in rows:
        row.pop("valueVisible", None)
    editor = _AttrEditor(exists=False, attributes=rows,
                         netlists=[{"components": {}}, base._live_netlist_for(plan)])

    code, payload = _apply(monkeypatch, tmp_path, editor, path, "hide-noport-apply.json")

    assert code == 4, payload
    assert payload["attributeMoves"]["capability"]["ok"] is False
    actions = [action for action, _params in editor.writes]
    assert "sch.place_component" not in actions
    assert "sch.move_attribute" not in actions
    assert "sch.doc.save" not in actions
