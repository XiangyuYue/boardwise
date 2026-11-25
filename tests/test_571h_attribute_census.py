"""571-H-1: an attribute primitive is visible to the census and to the digest.

`attributeMoves` writes an `ISCH_PrimitiveAttribute`, which the host reports
through `sch.list_attributes` — a namespace `sch.geometry` does not carry. So
`primitive_fingerprint` and `census_items` (both geometry-only) could not see a
moved attribute at all: the same page with one ATTR moved `x 10 -> 40` had a
byte-identical digest and `census_changes == 0`, and the only evidence was
`move_attribute`'s own `applied` verdict.

What is pinned here:

1. **the unit** — the same geometry plus two attribute listings that differ in
   one row's `x` must produce different fingerprints, a `section: "attributes"`
   row, and exactly one `census_changes` line naming the parent and the role;
2. **the digest** — hashed through `census_digest(..., attributes=...)`, an
   attribute-only edit moves the digest, while the same listing twice (or no
   listing at all) stays byte-identical, so "different" is never unconditional;
3. **the apply path** — a real plan with one `attributeMoves` row, run through
   the 053R fake editor (`tests/test_534r_attribute_moves.py`'s `_AttrEditor`,
   reused rather than re-built), must report an `attributeMoves.census` ledger:
   one changed row and two digests of the same post-write geometry that differ;
4. **the negative control** — a plan without moves adds no attribute field to
   the report and no attribute bridge call (the comparison is scoped to the
   attribute keys of the report JSON plus `_AttrEditor.attr_calls`; the exact
   whole-report shape and call order for a no-move plan stay pinned by
   `test_534r_attribute_moves.py`).
"""

from boardwise.core.changeplan import ChangePlan
from boardwise.engines import drawapply

import test_534r_attribute_moves as base534r


def _geometry():
    """One part on the page; the attribute rows live outside this dump."""
    return {
        "components": [{
            "primitiveId": "c1",
            "state": {
                "ComponentType": "part", "Designator": "R1", "Value": "1k",
                "X": 100, "Y": 100, "Rotation": 0, "Mirror": False,
            },
        }],
        "wires": [], "pins": [], "netlabels": [],
    }


def _listing(x):
    return {
        "pageUuid": "p1",
        "count": 1,
        "attributes": [{
            "primitiveId": "a1", "parentPrimitiveId": "c1", "key": "Name",
            "value": "1k", "x": x, "y": 120.0, "rotation": 0, "alignMode": 2,
            "keyVisible": True, "valueVisible": True,
        }],
        "readErrors": [],
    }


def test_a_moved_attribute_moves_the_fingerprint_and_one_census_line():
    geometry = _geometry()
    before, after = _listing(10.0), _listing(40.0)

    fingerprint_before = drawapply.primitive_fingerprint(geometry, attributes=before)
    fingerprint_after = drawapply.primitive_fingerprint(geometry, attributes=after)
    assert fingerprint_before != fingerprint_after, (
        "an ATTR moved x 10 -> 40 changed no fingerprint row — 571-H-1"
    )
    attribute_rows = [row for row in fingerprint_before if row["section"] == "attributes"]
    assert len(attribute_rows) == 1, fingerprint_before
    assert attribute_rows[0]["id"] == "a1"
    assert attribute_rows[0]["state"]["kind"] == "attribute"

    changes = drawapply.census_changes(
        drawapply.census_items(geometry, attributes=before),
        drawapply.census_items(geometry, attributes=after),
    )
    assert len(changes) == 1, changes
    line = changes[0]
    assert "c1" in line and "Name" in line, line
    assert "x 10.0 → 40.0" in line, line


def test_the_digest_sees_an_attribute_only_edit_and_clean_pages_still_match():
    geometry = _geometry()
    census = drawapply.canvas_census(geometry)
    same = drawapply.census_digest(census, geometry, attributes=_listing(10.0))
    assert same == drawapply.census_digest(census, geometry, attributes=_listing(10.0))
    assert same != drawapply.census_digest(census, geometry, attributes=_listing(40.0))
    # No listing means the pre-571 payload, byte for byte: a plan's recorded
    # digest is still recognised, so "different" is not made unconditional.
    assert drawapply.census_digest(census, geometry) == drawapply.census_digest(
        census, geometry
    )


def _apply_with_one_reference_move(monkeypatch, tmp_path, report_name):
    plan_path, plan = base534r.base._plan(tmp_path)
    plan = ChangePlan.from_jsonable(plan.to_jsonable())
    plan.change.attribute_moves = [base534r._reference_move(plan)]
    path = tmp_path / "571h-moves.json"
    plan.dump(path)
    editor = base534r._AttrEditor(
        exists=False,
        attributes=base534r._attributes(plan),
        netlists=[{"components": {}}, base534r.base._live_netlist_for(plan)],
    )
    code, payload = base534r._apply(monkeypatch, tmp_path, editor, path, report_name)
    return plan, editor, code, payload


def test_apply_reports_the_attribute_census_ledger(monkeypatch, tmp_path):
    plan, _editor, code, payload = _apply_with_one_reference_move(
        monkeypatch, tmp_path, "571h-apply.json"
    )
    assert code == 0, payload
    ledger = payload["attributeMoves"]["census"]
    expected = len(base534r._attributes(plan))
    assert ledger["before"] == expected and ledger["after"] == expected, ledger
    assert len(ledger["changes"]) == 1, ledger
    assert "Designator" in ledger["changes"][0], ledger
    assert "c-" in ledger["changes"][0], ledger
    assert ledger["digestBefore"] != ledger["digestAfter"], ledger


def test_a_plan_without_moves_gains_no_attribute_field_or_call(monkeypatch, tmp_path):
    plan_path, plan = base534r.base._plan(tmp_path)
    editor = base534r._AttrEditor(
        exists=False,
        netlists=[{"components": {}}, base534r.base._live_netlist_for(plan)],
    )
    code, payload = base534r._apply(monkeypatch, tmp_path, editor, plan_path, "571h-plain.json")
    assert code == 0, payload
    # Scope: attribute keys only (the whole-report shape for a no-move plan is
    # pinned by test_534r_attribute_moves.py), plus the bridge call list.
    keys = _keys(payload)
    assert [key for key in keys if "attribute" in key.lower()] == []
    assert editor.attr_calls == []


def _keys(value):
    """Every key of a report JSON, recursively (the field set, not the text)."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.append(str(key))
            found.extend(_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_keys(item))
    return found
