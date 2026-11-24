"""574 / 567-E-1: the C5 digest speaks for **every primitive**, not six counters.

567-E's reproduction (`outputs/hole567/e/REPRO.md`, E-1) measured the hole: the
census digest carried the designator set and six numbers, so four real hand edits
— a part moved 30 units, an existing wire re-routed, a flag moved 20 units, a
value changed — produced a byte-identical digest and `--expect-census` reported
zero problems. The counts were never wrong; they were all the digest *looked at*.

What is pinned here, in the task book's own order:

1. the four original variants (plus a positive control that adds a primitive);
2. coverage of the sections the census gained since — `pins` and the six drawing
   sections (570) — with `sheet` staying the page rather than a primitive;
3. determinism: section order, entry order and dict key order do not move the
   digest, and neither do `bboxes` / `meta.available` (measurement, not content);
4. the old counts-only digest is *recognised and refused* with a reason that says
   "regenerate / take a fresh digest" — never accepted, never blamed on a hand
   edit it cannot see;
5. `canvas_census`'s digest is `census_digest(census, geometry)`, the new one.

The plan carrier is a document, not a compiled drawing (143d's reading): the C5
guard is a function of the baseline, and compiling the divider here would only add
the compiler's own reasons to fail.
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

import test_054_draw_cli as m054

from boardwise import cli
from boardwise.core.changeplan import DRAW_MODULE_KIND, ChangePlan, PlanDrawBaseline
from boardwise.engines import drawapply

#: Every section a `sch.geometry` dump carries, in the order the census reads them.
ALL_SECTIONS = drawapply.GEOMETRY_SECTIONS + drawapply.DRAWING_SECTIONS


def _page() -> dict:
    """A page with one of everything: part, flags, wire, pin, label and drawings."""
    return {
        "components": [
            {"primitiveId": "sheet-1",
             "state": {"ComponentType": "sheet", "Designator": "", "X": 0, "Y": 0}},
            {"primitiveId": "p-R1", "state": {
                "ComponentType": "part", "Designator": "R1", "X": 95, "Y": 100,
                "Rotation": 0, "Mirror": False, "SupplierId": "C25744",
                "OtherProperty": {"Value": "10k"}}},
            {"primitiveId": "flag-vin", "state": {
                "ComponentType": "netflag", "Net": "VIN", "X": 95, "Y": 150}},
            {"primitiveId": "flag-gnd", "state": {
                "ComponentType": "netflag", "Net": "GND", "X": 95, "Y": 50}},
        ],
        "wires": [
            {"primitiveId": "w-0", "state": {"Line": [95, 100, 95, 50], "Net": "TAP"}},
        ],
        "pins": [
            {"primitiveId": "pin-1", "state": {
                "PinNumber": "1", "X": 95, "Y": 150, "Net": "VIN"}},
        ],
        "netlabels": [
            {"primitiveId": "nl-1", "state": {
                "Net": "TAP", "Text": "TAP", "X": 60, "Y": 100}},
        ],
        "texts": [
            {"primitiveId": "t-1", "state": {"Text": "REV A", "X": 10, "Y": 10}},
        ],
        "buses": [{"primitiveId": "bus-1", "state": {"Line": [0, 0, 100, 0]}}],
        "circles": [{"primitiveId": "circle-1", "state": {"X": 5, "Y": 5, "Radius": 10}}],
        "rectangles": [
            {"primitiveId": "rect-1", "state": {
                "X": 0, "Y": 0, "Width": 40, "Height": 20, "Text": "PWR"}},
        ],
        "arcs": [{"primitiveId": "arc-1", "state": {"X": 0, "Y": 0, "StartAngle": 0}}],
        "polygons": [
            {"primitiveId": "poly-1", "state": {"Line": [0, 0, 10, 0, 10, 10]}},
        ],
        "bboxes": {"sheet-1": {"minX": 0, "minY": -1000, "maxX": 1200, "maxY": 0}},
        "meta": {"available": {key: True for key in (*ALL_SECTIONS, "bboxes")}},
    }


def _plan(baseline: PlanDrawBaseline | None = None) -> ChangePlan:
    """A draw-module plan carrying a census, without compiling anything."""
    change: dict = {
        "kind": DRAW_MODULE_KIND,
        "layoutSha256": "1" * 64,
        "circuitSha256": "2" * 64,
        "presentationSha256": "3" * 64,
        "profiles": [{"symbolRef": "R0402", "geometryHash": "4" * 64}],
        "parts": [{
            "specId": "R1", "designator": "R1", "prefix": "R",
            "lcsc": "C25744", "value": "10k", "valueKey": "Value",
            "symbolRef": "R0402", "symbolHash": "4" * 64, "x": 95.0, "y": 100.0,
            "pins": [{"number": "1", "dx": 0.0, "dy": 50.0}],
        }],
        "wires": [{"net": "TAP", "points": [[95.0, 100.0], [95.0, 50.0]]}],
    }
    if baseline is not None:
        change["baseline"] = {
            "pageUuid": baseline.page_uuid,
            "components": list(baseline.components),
            "wireCount": baseline.wire_count,
            "netflagCount": baseline.netflag_count,
            "netlabelCount": baseline.netlabel_count,
            "unnumberedCount": baseline.unnumbered_count,
            "pinCount": baseline.pin_count,
            "digest": baseline.digest,
            "findingsRead": baseline.findings_read,
        }
    return ChangePlan.from_jsonable({
        "planVersion": 1,
        "source": {"inputSha256": "0" * 64},
        "target": {"module": "574 census digest test"},
        "change": change,
    })


def _component(page: dict, primitive_id: str) -> dict:
    for entry in page["components"]:
        if entry["primitiveId"] == primitive_id:
            return entry
    raise AssertionError(f"no {primitive_id} on the page")


# ------------------------------------------------- 1. the four original variants


def _moved_part(page: dict) -> dict:
    _component(page, "p-R1")["state"]["X"] = 125
    return page


def _rerouted_wire(page: dict) -> dict:
    page["wires"][0]["state"]["Line"] = [95, 100, 105, 100, 105, 50]
    return page


def _moved_flag(page: dict) -> dict:
    _component(page, "flag-vin")["state"]["Y"] = 170
    return page


def _changed_value(page: dict) -> dict:
    _component(page, "p-R1")["state"]["OtherProperty"]["Value"] = "22k"
    return page


ORIGINAL_VARIANTS = {
    "a part moved 30 units": _moved_part,
    "an existing wire re-routed": _rerouted_wire,
    "a flag moved 20 units": _moved_flag,
    "a value changed": _changed_value,
}


@pytest.mark.parametrize("name", sorted(ORIGINAL_VARIANTS))
def test_each_original_hand_edit_moves_the_digest_and_is_refused(name):
    """567-E-1: the four edits that were invisible; the digest and C5 must see them."""
    base = drawapply.canvas_census(_page())
    variant_page = ORIGINAL_VARIANTS[name](copy.deepcopy(_page()))
    variant = drawapply.canvas_census(variant_page)

    assert variant.components == base.components, (
        "the control: these edits keep the designator set, which is exactly why "
        "the counts-only digest used to call them no change"
    )
    assert variant.wire_count == base.wire_count
    assert variant.digest != base.digest, (
        f"{name}: the census digest cannot tell this page from the plan's"
    )
    problems = drawapply.guard_problems(_plan(), geometry=variant_page,
                                        expect_census=base.digest)
    assert problems, f"{name}: --expect-census was told the old digest and passed"
    assert "somebody changed" in problems[0]


def test_the_same_page_still_reports_no_problem_and_an_added_primitive_does():
    """The positive control: the guard is not simply refusing everything."""
    page = _page()
    digest = drawapply.canvas_census(page).digest
    assert drawapply.guard_problems(_plan(), geometry=copy.deepcopy(page),
                                    expect_census=digest) == []

    extra = copy.deepcopy(page)
    extra["wires"].append(
        {"primitiveId": "w-extra", "state": {"Line": [0, 0, 40, 0], "Net": "GND"}}
    )
    problems = drawapply.guard_problems(_plan(), geometry=extra, expect_census=digest)
    assert problems and "somebody changed" in problems[0]


# ------------------------------------------------------------- 2. the coverage


def _append(section: str, entry: dict):
    def apply(page: dict) -> dict:
        page[section].append(copy.deepcopy(entry))
        return page
    return apply


COVERAGE_VARIANTS = {
    "a pin added": _append("pins", {"primitiveId": "pin-2", "state": {
        "PinNumber": "2", "X": 95, "Y": 50, "Net": "GND"}}),
    "a pin moved": lambda page: (
        page["pins"][0]["state"].update({"X": 100}) or page),
    "a text added": _append("texts", {"primitiveId": "t-2", "state": {
        "Text": "REV B", "X": 20, "Y": 20}}),
    "a rectangle's geometry changed": lambda page: (
        page["rectangles"][0]["state"].update({"Width": 60}) or page),
    "a rectangle's text changed": lambda page: (
        page["rectangles"][0]["state"].update({"Text": "GND"}) or page),
    "a net label moved": lambda page: (
        page["netlabels"][0]["state"].update({"X": 70}) or page),
    "a net label re-texted": lambda page: (
        page["netlabels"][0]["state"].update({"Text": "TAP_IN"}) or page),
}


@pytest.mark.parametrize("name", sorted(COVERAGE_VARIANTS))
def test_every_section_the_census_reads_is_in_the_digest(name):
    """570's sections and 143d's `pins` are content, so they are fingerprinted."""
    base = drawapply.canvas_census(_page())
    changed = drawapply.canvas_census(COVERAGE_VARIANTS[name](copy.deepcopy(_page())))
    assert changed.digest != base.digest, f"{name}: the digest did not move"


def test_the_sheet_is_the_page_and_not_a_primitive_in_the_digest():
    """A title-block text on the sheet is content; the sheet itself is identity."""
    page = _page()
    base = drawapply.canvas_census(page)
    moved_sheet = copy.deepcopy(page)
    _component(moved_sheet, "sheet-1")["state"]["X"] = 40
    assert drawapply.canvas_census(moved_sheet).digest == base.digest, (
        "the sheet is the page the drawing lands on; its anchor is not a change "
        "the drawing is made against"
    )
    fingerprints = drawapply.primitive_fingerprint(page)
    assert all(row["id"] != "sheet-1" for row in fingerprints)


# ------------------------------------------------------- 3. determinism/serialisation


def test_section_entry_and_dict_key_order_do_not_move_the_digest():
    page = _page()
    digest = drawapply.canvas_census(page).digest

    shuffled = {}
    for section in reversed(list(page)):
        items = page[section]
        if isinstance(items, list):
            shuffled[section] = [
                {key: item[key] for key in reversed(list(item))} for item in reversed(items)
            ]
        else:
            shuffled[section] = items
    assert drawapply.canvas_census(shuffled).digest == digest, (
        "a re-read of the same page must hash the same"
    )

    assert drawapply.census_digest(drawapply.canvas_census(page), page) == (
        drawapply.census_digest(drawapply.canvas_census(copy.deepcopy(page)),
                                copy.deepcopy(page))
    )


def test_measurements_and_availability_are_not_primitive_content():
    """`bboxes` and `meta.available` are how the page was measured, not what is on it."""
    page = _page()
    digest = drawapply.canvas_census(page).digest
    remeasured = copy.deepcopy(page)
    remeasured["bboxes"]["p-R1"] = {"minX": 80, "minY": 90, "maxX": 110, "maxY": 210}
    remeasured["meta"]["available"]["pins"] = False
    assert drawapply.canvas_census(remeasured).digest == digest

    fingerprint = json.dumps(drawapply.primitive_fingerprint(page), sort_keys=True)
    assert "bboxes" not in fingerprint and "available" not in fingerprint


def test_the_fingerprint_is_sorted_by_section_and_id():
    rows = drawapply.primitive_fingerprint(_page())
    keys = [(row["section"], row["id"]) for row in rows]
    assert keys == sorted(keys)
    assert {row["section"] for row in rows} == set(ALL_SECTIONS)


def test_the_baseline_shape_and_round_trip_are_unchanged():
    """570's public baseline keeps its fields; only ``digest`` gained coverage."""
    assert [field.name for field in PlanDrawBaseline.__dataclass_fields__.values()] == [
        "page_uuid", "components", "wire_count", "netflag_count", "netlabel_count",
        "unnumbered_count", "pin_count", "digest", "findings_read",
    ]
    page = _page()
    census = drawapply.canvas_census(page)
    census.page_uuid = "page-1"
    plan = _plan(census)
    assert plan.change.draw_baseline.digest == census.digest
    again = ChangePlan.from_jsonable(plan.to_jsonable())
    assert again.change.draw_baseline == plan.change.draw_baseline


# ------------------------------------------------------- 4. the old digest


def _counts_only(census: PlanDrawBaseline) -> str:
    """The digest a build before 574 wrote (the counts-only algorithm)."""
    return drawapply.census_digest(census)


def test_the_counts_only_digest_is_a_different_string():
    """The control for the two tests below: the old algorithm is still there."""
    census = drawapply.canvas_census(_page())
    old = _counts_only(census)
    assert old != census.digest
    assert len(old) == 64 and len(census.digest) == 64


def test_the_counts_only_digest_is_still_the_pre_574_algorithm_byte_for_byte():
    """Recognition depends on reproducing an old plan's digest exactly.

    The payload is written out here rather than imported from the module: an
    "old algorithm" that drifts with the code it is meant to recognise would
    recognise nothing, and a second copy of the rule is what makes the drift
    visible.
    """
    census = drawapply.canvas_census(_page())
    payload = json.dumps({
        "components": sorted(census.components),
        "wireCount": int(census.wire_count),
        "netflagCount": int(census.netflag_count),
        "netlabelCount": int(census.netlabel_count),
        "pinCount": int(census.pin_count),
        "unnumberedCount": int(census.unnumbered_count),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert drawapply.census_digest(census) == hashlib.sha256(
        payload.encode("utf-8")).hexdigest()


def test_an_old_counts_only_expectation_is_refused_with_its_own_reason():
    """It cannot prove the page unchanged, so it is rejected — and said so."""
    page = _page()
    old = _counts_only(drawapply.canvas_census(page))
    problems = drawapply.guard_problems(_plan(), geometry=page, expect_census=old)
    assert problems, "a counts-only expectation must never pass"
    assert "counts-only" in problems[0]
    assert "--expect-census" in problems[0], (
        "the refusal has to say how to get a usable digest"
    )
    assert "somebody changed" not in problems[0], (
        "an old summary is not evidence that a hand edited the page"
    )


def canvas_census_for(page: dict) -> PlanDrawBaseline:
    census = drawapply.canvas_census(page)
    census.page_uuid = "page-1"
    return census


def test_a_plan_that_recorded_a_counts_only_digest_must_be_regenerated():
    page = _page()
    census = drawapply.canvas_census(page)
    census.page_uuid = "page-1"
    old = _counts_only(census)
    bound = _plan(PlanDrawBaseline(
        page_uuid="page-1", components=list(census.components),
        wire_count=census.wire_count, netflag_count=census.netflag_count,
        netlabel_count=census.netlabel_count, unnumbered_count=census.unnumbered_count,
        pin_count=census.pin_count, digest=old,
    ))
    problems = drawapply.guard_problems(bound, page_uuid="page-1", geometry=page)
    assert problems, "an old plan's baseline cannot be waved through"
    assert "counts-only" in problems[0]
    assert "regenerate" in problems[0]
    assert "somebody changed" not in problems[0]

    current = _plan(canvas_census_for(page))
    assert drawapply.guard_problems(
        current, page_uuid="page-1", geometry=page
    ) == [], "a plan that recorded the new digest still passes"


def test_a_genuine_new_digest_mismatch_keeps_the_page_changed_reason():
    page = _page()
    problems = drawapply.guard_problems(_plan(), geometry=page, expect_census="3" * 64)
    assert problems and "expected" in problems[0]
    assert "counts-only" not in problems[0]


def test_the_cli_refuses_an_old_counts_only_expect_census(
    tmp_path, monkeypatch, capsys,
):
    """End to end: not exit 0, not "somebody changed", but "take a fresh digest"."""
    plan_path, plan = m054._plan(tmp_path, page="page-1")
    editor = m054._page_with(plan)
    old = drawapply.census_digest(drawapply.canvas_census(editor.geometry()))
    m054._stub_editor(monkeypatch, editor)
    m054._stub_export(monkeypatch, components={}, findings=[])
    report = tmp_path / "apply.json"
    code = cli.main([
        "draw", "apply", str(plan_path), "--page", "page-1",
        f"--expect-census={old}", "--json", str(report),
    ])
    capsys.readouterr()
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert code == 4, payload
    assert payload["reason"] == "guard_refused"
    problems = payload["guards"]["problems"]
    assert any("counts-only" in line for line in problems), problems
    assert not any("somebody changed" in line for line in problems), problems
    assert editor.writes == [], "an old expectation must be refused before any write"


# ------------------------------------------------------- 5. the census self-proof


def test_the_census_digest_is_the_per_primitive_one():
    """054's self-proof has to ask the same algorithm the guard asks."""
    page = _page()
    census = drawapply.canvas_census(page)
    assert census.digest == drawapply.census_digest(census, page)
    assert census.digest != drawapply.census_digest(census)
