"""548P38: declared service cores keep their visible reference above and value below.

These are synthetic test symbols, not measured library anchors. The positive
case uses the complete production builder, parser, netlist reader and ATTR plan.
The narrow text cases inject real boxes as walls to isolate row selection.
"""

from __future__ import annotations

import pytest

from boardwise.core.layoutplan import LayoutPlan
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawapply, drawcompiler as dc, readability
from test_548n_group_seat import _prepared
from test_548p16_native_service import _fixture as native_fixture


def _case(*, native=True, groups=True, declared_core=True, side=None, anchors=False):
    circuit, original, book, _ctx = native_fixture(native=native)
    document = original.to_jsonable()
    document.pop("partTexts", None)
    if side is not None:
        document["partTexts"] = {"U1": side}
    if not groups:
        document.pop("serviceGroups", None)
    if not declared_core:
        document["modules"][0].pop("core", None)
    if anchors:
        host = book["HOST4"].to_jsonable()
        host["texts"] = [
            {"kind": "reference", "x": -33.0, "y": 12.0},
            {"kind": "value", "x": -31.0, "y": -12.0},
        ]
        host["source"] = "548P38 synthetic declared-anchor control; not a live measurement"
        book["HOST4"] = SymbolProfile.from_dict(host)
    spec = PresentationSpec.from_dict(document)
    return circuit, spec, book, _prepared(circuit, spec, book)


def _placement(case):
    ctx = case[-1]
    placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    assert placed is not None, failure
    return placed


def _body(case, placed):
    return dc._body_box(
        case[2]["HOST4"], placed.poses["U1"], placed.origins["U1"],
    )


def _rows(texts, owner="U1"):
    return {row.kind: row for row in texts if row.part_id == owner}


def _assert_s20(rows, body):
    assert set(rows) == {"reference", "value"}, "both host rows stay visible"
    assert rows["reference"].bbox[1] >= body[3], "S20 reference must be above the body"
    assert rows["value"].bbox[3] <= body[1], "S20 value must be below the body"
    for row in rows.values():
        assert row.bbox[0] == pytest.approx(body[0]), "S20 uses the drawn body's left edge"
        assert row.rotation == 0.0


def _assert_partition(circuit, book, plan):
    derived = readability.derive_netlist(plan, book)
    for net in circuit.nets:
        expected = set()
        for member in net.members:
            owner, _, token = member.partition(".")
            profile = book[circuit.part(owner).symbol_ref]
            expected.add(f"{owner}.{dc._pin_of_token(profile, token).number}")
        for member in expected:
            assert set(derived.group_of(member)) == expected
    assert len(derived.pin_points) == len(derived.wired_pins) == 10


def test_complete_service_core_build_round_trips_connects_and_plans_both_attr_rows(tmp_path):
    case = _case()
    circuit, spec, book, ctx = case
    built, failure, violations = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, (failure, violations)
    assert not built.checked.hard_violations
    plan = LayoutPlan.from_dict(built.plan.to_jsonable())
    path = tmp_path / "core-rows.json"
    plan.dump(path)
    loaded = LayoutPlan.load(path)
    assert loaded.to_jsonable() == built.plan.to_jsonable()
    _assert_partition(circuit, book, loaded)
    host = loaded.part("U1")
    body = dc._body_box(book[host.symbol_ref], dc.SymbolPose(host.rotation, host.mirror),
                        (host.x, host.y))
    extent = dc._part_box(book[host.symbol_ref], dc.SymbolPose(host.rotation, host.mirror),
                          (host.x, host.y))
    assert extent[0] < body[0], "pin extent and drawn body are different rulers"
    rows = _rows(loaded.texts)
    _assert_s20(rows, body)
    change = drawapply.module_plan(
        loaded, circuit, spec, book, keep_names=True,
        lcsc_by_part={part.id: "C1" for part in circuit.parts},
    ).change
    moves = {move.role: move for move in change.attribute_moves
             if move.owner_kind == "part" and move.spec_id == "U1"}
    assert set(moves) == {"reference", "value"}
    for role, move in moves.items():
        assert (move.x, move.y) == pytest.approx(rows[role].bbox[:2])
        assert move.value_visible is not False
    assert all(part.value_visible for part in change.draw_parts)


def test_core_rows_keep_their_sides_and_retreat_from_a_first_rung_wall():
    case = _case()
    placed = _placement(case)
    body = _body(case, placed)
    # Above rung 1 occupies body.top+10.5 .. +19.5. This wall clips it;
    # rung 2 on the same side is clear. Its x starts at the actual body edge.
    wall = (body[0], body[3] + 9.0, body[0] + 80.0, body[3] + 13.0)
    texts, failure = dc._part_texts(case[-1], placed, [], [wall])
    assert failure is None, failure
    rows = _rows(texts)
    _assert_s20(rows, body)
    assert rows["reference"].bbox[1] > body[3] + 13.0, "first rung cannot cross the wall"
    assert all(not dc._overlaps(row.bbox, wall) for row in rows.values())


def test_core_rows_refuse_by_name_when_every_above_rung_is_blocked():
    case = _case()
    placed = _placement(case)
    body = _body(case, placed)
    wall = (body[0] - 1.0, body[3], body[0] + 200.0,
            body[3] + dc.TEXT_GAP * dc.TEXT_ESCALATION_STEPS + 40.0)
    _texts, failure = dc._part_texts(case[-1], placed, [], [wall])
    assert failure is not None, "blocked S20 rows must not fall back to a side block"
    assert failure.category == "layout-unsat"
    assert "U1" in failure.subject + failure.detail


@pytest.mark.parametrize("settings", [
    {"native": False}, {"groups": False}, {"declared_core": False},
])
def test_noneligible_core_keeps_the_existing_side_block(settings):
    case = _case(**settings)
    placed = _placement(case)
    extent = dc._part_box(case[2]["HOST4"], placed.poses["U1"], placed.origins["U1"])
    texts, failure = dc._part_texts(case[-1], placed, [], [])
    assert failure is None, failure
    rows = _rows(texts)
    assert set(rows) == {"reference", "value"}
    assert all(row.bbox[0] >= extent[2] for row in rows.values())
    assert rows["reference"].bbox[1] > rows["value"].bbox[1]


def test_explicit_below_keeps_both_rows_below():
    case = _case(side="below")
    placed = _placement(case)
    extent = dc._part_box(case[2]["HOST4"], placed.poses["U1"], placed.origins["U1"])
    texts, failure = dc._part_texts(case[-1], placed, [], [])
    assert failure is None, failure
    rows = _rows(texts)
    assert set(rows) == {"reference", "value"}
    assert all(row.bbox[3] < extent[1] for row in rows.values())


def test_synthetic_declared_anchors_are_not_replaced_by_s20_fallback():
    case = _case(anchors=True)
    placed = _placement(case)
    texts, failure = dc._part_texts(case[-1], placed, [], [])
    assert failure is None, failure
    rows = _rows(texts)
    x, y = placed.origins["U1"]
    assert rows["reference"].bbox[:2] == pytest.approx((x - 33.0, y + 12.0))
    assert rows["value"].bbox[:2] == pytest.approx((x - 31.0, y - 12.0))


def test_noncore_service_branch_keeps_its_existing_rows():
    eligible = _case()
    explicit = _case(side="below")
    outputs = []
    for case in (eligible, explicit):
        texts, failure = dc._part_texts(case[-1], _placement(case), [], [])
        assert failure is None, failure
        outputs.append({row.kind: row.bbox for row in texts if row.part_id == "R1"})
    assert outputs[0] == outputs[1]
    assert set(outputs[0]) == {"reference", "value"}
