"""570 W-A: a page is proven empty by **every** namespace, and proved again before a write.

566-A found three holes in the empty-page reuse path, and each one is pinned here
through the seam it broke at:

* **A-1** — `_draw_geometry_readable` refused only ``available.components is
  False``, so a page whose wires/pins/net labels could not be read was counted as
  an all-zero empty page, reused, and written to (the 566-A P3 flow: exit 0,
  ``reused: true``, ``censusBefore.wireCount: 1``). The fake editors are 054's
  (imported, not copied); the unreadable-namespace editor is the probe's shape.
* **A-2** — `sch.geometry` dumped four namespaces and the census counted six
  electrical numbers, so a page holding only a text (or a bus, circle, rectangle,
  arc, polygon) was "provably empty". The six drawing sections are real host
  namespaces — `sch_PrimitiveLine` is not, and is not invented here.
* **A-3** — the pre-write ``page_not_empty`` guard ran only for ``created`` pages,
  so a reused page's scan was the only proof. Both the scan and the pre-write
  guard now ask one helper (`drawapply.page_is_not_empty`), and a page that grew
  a wire or a drawing primitive between the two reads is refused with exit 4.

The expectation is written out (``EXPECTED_SECTIONS``, the six keys, the exit
codes) rather than derived from the implementation: deriving it would be the
second judgement this repo forbids.
"""

from __future__ import annotations

import copy
import json

import pytest

import test_054_draw_cli as m054
from boardwise import cli
from boardwise.engines import drawapply

#: Every section a `sch.geometry` answer must carry — and report as available —
#: before an empty page may be **proven** empty. The first four are the
#: electrical census (`GEOMETRY_SECTIONS`), the last six the drawing primitives.
EXPECTED_SECTIONS = (
    "components", "wires", "pins", "netlabels",
    "texts", "buses", "circles", "rectangles", "arcs", "polygons",
)

#: The `censusBefore` key each drawing section is reported under.
DRAWING_REPORT_KEYS = {
    "texts": "textCount",
    "buses": "busCount",
    "circles": "circleCount",
    "rectangles": "rectangleCount",
    "arcs": "arcCount",
    "polygons": "polygonCount",
}

#: The noun a refusal uses for each section's count.
DRAWING_NOUNS = {
    "texts": "text(s)",
    "buses": "bus(es)",
    "circles": "circle(s)",
    "rectangles": "rectangle(s)",
    "arcs": "arc(s)",
    "polygons": "polygon(s)",
}

#: A primitive per drawing section, in the shape `sch.geometry` dumps one.
DRAWING_ITEM = {
    "texts": {"primitiveId": "text-1", "state": {"Text": "REV A", "X": 10, "Y": 10}},
    "buses": {"primitiveId": "bus-1", "state": {"Line": [0, 0, 100, 0]}},
    "circles": {"primitiveId": "circle-1", "state": {"X": 5, "Y": 5, "Radius": 10}},
    "rectangles": {"primitiveId": "rect-1", "state": {"X": 0, "Y": 0, "Width": 40}},
    "arcs": {"primitiveId": "arc-1", "state": {"X": 0, "Y": 0, "StartAngle": 0}},
    "polygons": {"primitiveId": "poly-1", "state": {"Line": [0, 0, 10, 0, 10, 10]}},
}


def _blank_geometry() -> dict:
    """A provably empty page: every section an empty list, every one available."""
    geometry: dict = {key: [] for key in EXPECTED_SECTIONS}
    geometry["bboxes"] = {}
    geometry["meta"] = {
        "available": {key: True for key in (*EXPECTED_SECTIONS, "bboxes")},
    }
    return geometry


# ---------------------------------------------------------------- A-1: the gate


@pytest.mark.parametrize("key", EXPECTED_SECTIONS)
def test_a_namespace_that_could_not_be_read_is_not_provable(key):
    """``available.<key> = False`` must never leave the page "provably empty"."""
    geometry = _blank_geometry()
    assert cli._draw_geometry_readable(geometry) is True, (
        "the control: every namespace read, so the dump may be judged"
    )
    geometry["meta"]["available"][key] = False
    assert cli._draw_geometry_readable(geometry) is False, (
        f"a page whose {key} could not be read is unproven, not empty (566-A-1)"
    )


@pytest.mark.parametrize("key", EXPECTED_SECTIONS)
def test_an_absent_or_mis_shaped_section_is_not_provable(key):
    """A section the dump omits, or answers as a dict, is a read nobody can judge."""
    missing = _blank_geometry()
    del missing[key]
    assert cli._draw_geometry_readable(missing) is False

    drifted = _blank_geometry()
    drifted[key] = {"items": []}
    assert cli._draw_geometry_readable(drifted) is False


@pytest.mark.parametrize("key", EXPECTED_SECTIONS)
def test_a_missing_availability_flag_is_not_provable(key):
    """Silence is not ``true``: the connector has to say it read the namespace."""
    geometry = _blank_geometry()
    del geometry["meta"]["available"][key]
    assert cli._draw_geometry_readable(geometry) is False


def test_no_meta_at_all_is_not_provable():
    geometry = _blank_geometry()
    del geometry["meta"]
    assert cli._draw_geometry_readable(geometry) is False
    assert cli._draw_geometry_readable({"components": [], "wires": []}) is False


def test_the_old_connector_shape_loses_only_the_auto_proof():
    """Four sections and four flags (the shipped 0.6.3 connector) is unproven."""
    old = {
        "components": [], "wires": [], "pins": [], "netlabels": [],
        "bboxes": {},
        "meta": {"available": {
            "components": True, "wires": True, "pins": True,
            "netlabels": True, "bboxes": True,
        }},
    }
    assert cli._draw_geometry_readable(old) is False


# ------------------------------------------- A-2: text and the drawing primitives


@pytest.mark.parametrize("key", tuple(DRAWING_REPORT_KEYS))
def test_a_drawing_primitive_is_not_a_blank_page(key):
    geometry = _blank_geometry()
    geometry[key] = [copy.deepcopy(DRAWING_ITEM[key])]

    assert cli._draw_geometry_readable(geometry) is True
    census = drawapply.canvas_census(geometry)
    # The electrical census must stay electrical — a text is not a net label.
    assert cli._census_is_not_empty(census) is False
    # The whole-page judgement sees it.
    assert cli._census_is_not_empty(census, geometry) is True
    assert drawapply.drawing_section_counts(geometry)[key] == 1
    assert f"1 {DRAWING_NOUNS[key]}" in drawapply.page_phrase(census, geometry)


def test_a_page_with_nothing_at_all_is_still_reusable():
    """The positive control: empty is still empty, or every reuse test is a lie."""
    geometry = _blank_geometry()
    census = drawapply.canvas_census(geometry)
    assert cli._draw_geometry_readable(geometry) is True
    assert cli._census_is_not_empty(census, geometry) is False


# ------------------------------------------------------- A-1 at the flow level


class _WiresUnreadable(m054._FakeEditor):
    """The scan's `sch.geometry` reports the wires namespace as unreadable."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scan_failures = 1

    async def call(self, action, params=None, **_route):
        payload = await super().call(action, params, **_route)
        if action == "sch.geometry" and self.scan_failures > 0:
            self.scan_failures -= 1
            payload = copy.deepcopy(payload)
            payload["wires"] = []
            payload["meta"] = dict(payload.get("meta") or {})
            payload["meta"]["available"] = dict(
                payload["meta"].get("available") or {}
            )
            payload["meta"]["available"]["wires"] = False
            payload["meta"]["reasons"] = {
                "wires": "call sch_PrimitiveWire.getAll(): the read broke",
            }
        return payload


class _OldConnectorShape(m054._FakeEditor):
    """A host answering the four-section dump the shipped connector sends."""

    def geometry(self):
        payload = super().geometry()
        payload = copy.deepcopy(payload)
        for key in DRAWING_REPORT_KEYS:
            payload.pop(key, None)
        payload["meta"]["available"] = {
            key: True for key in ("components", "wires", "pins", "netlabels")
        }
        payload["meta"]["available"]["bboxes"] = True
        return payload


def _apply(monkeypatch, tmp_path, plan_path, editor, *extra):
    m054._stub_editor(monkeypatch, editor)
    m054._stub_export(monkeypatch, components={}, findings=[])
    report = tmp_path / "apply.json"
    code = cli.main([
        "draw", "apply", str(plan_path), "--project", "test",
        "--json", str(report), *extra,
    ])
    return code, json.loads(report.read_text(encoding="utf-8")), editor


def test_a_page_whose_wires_could_not_be_read_is_never_reused(
    monkeypatch, tmp_path, capsys,
):
    """566-A P3, as a regression: one wire, wires unreadable, exit 0/applied was the hole."""
    plan_path, plan = m054._plan(tmp_path)
    editor = _WiresUnreadable(
        page="page-wired",
        pages=[m054._page_row("page-wired")],
        # The page really holds a wire; only the read of the namespace breaks.
        page_primitives={"page-wired": {
            "wires": [{"net": "GND", "points": [[0, 0], [100, 0]]}],
        }},
        netlists=[{"components": {}}, m054._live_netlist_for(plan)],
    )
    code, payload, editor = _apply(monkeypatch, tmp_path, plan_path, editor)
    printed = capsys.readouterr().out

    assert code == 5, printed
    assert payload["reason"] == "page_required"
    assert payload["page"]["reused"] is False
    assert payload["page"]["created"] is False
    assert editor.writes == [], "zero writes: the page was never proven empty"
    assert "sch.doc.new" not in editor.calls
    assert any("could not be proven empty" in note for note in payload["notes"])


def test_a_page_read_by_the_old_connector_is_refused_not_reused(
    monkeypatch, tmp_path, capsys,
):
    """The old dump cannot prove a page empty; it must lose the reuse, not gain it."""
    plan_path, _plan_ = m054._plan(tmp_path)
    editor = _OldConnectorShape(
        page="page-empty",
        pages=[m054._page_row("page-empty")],
    )
    code, payload, editor = _apply(monkeypatch, tmp_path, plan_path, editor)
    printed = capsys.readouterr().out

    assert code == 5, printed
    assert payload["reason"] == "page_required"
    assert payload["page"]["reused"] is False
    assert editor.writes == []


def test_an_explicit_page_still_reads_with_the_old_connector(
    monkeypatch, tmp_path, capsys,
):
    """The gate is the scan's admission test only: ``--page`` reads as before."""
    plan_path, plan = m054._plan(tmp_path)
    editor = _OldConnectorShape(
        page="page-explicit",
        netlists=[{"components": {}}, m054._live_netlist_for(plan)],
    )
    code, payload, editor = _apply(
        monkeypatch, tmp_path, plan_path, editor, "--page", "page-explicit",
    )
    printed = capsys.readouterr().out

    assert code == 0, printed
    assert payload["page"]["reused"] is False
    assert payload["page"]["uuid"] == "page-explicit"
    assert "sch.place_component" in [action for action, _params in editor.writes]


def test_a_text_only_page_is_occupied_and_the_empty_one_is_reused(
    monkeypatch, tmp_path, capsys,
):
    """A hand-written comment is content: the scan must not pick that page."""
    plan_path, plan = m054._plan(tmp_path)
    editor = m054._FakeEditor(
        page="page-text",
        pages=[
            m054._page_row("page-text", "boardwise draw"),
            m054._page_row("page-empty", "boardwise draw"),
        ],
        page_primitives={"page-text": {
            "texts": [copy.deepcopy(DRAWING_ITEM["texts"])],
        }},
        netlists=[{"components": {}}, m054._live_netlist_for(plan)],
    )
    code, payload, editor = _apply(monkeypatch, tmp_path, plan_path, editor)
    printed = capsys.readouterr().out

    assert code == 0, printed
    assert payload["page"]["reused"] is True
    assert payload["page"]["uuid"] == "page-empty"
    assert editor.page == "page-empty", (
        "the text-only page is content, so it cannot be the one reused"
    )
    assert {part.designator for part in plan.change.draw_parts} <= set(editor.components)


# ------------------------------------------- A-3: the second gate before a write


class _GrowsBeforeWrite(m054._FakeEditor):
    """Empty on the scan's read, non-empty on every later `sch.geometry`."""

    def __init__(self, *args, late=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.late = dict(late or {})
        self.geometry_reads = 0

    def geometry(self):
        payload = super().geometry()
        self.geometry_reads += 1
        if self.geometry_reads > 1:
            payload.update(copy.deepcopy(self.late))
        return payload


@pytest.mark.parametrize("key", ("wires", "texts", "rectangles"))
def test_a_reused_page_that_is_no_longer_empty_is_refused_before_the_first_write(
    monkeypatch, tmp_path, capsys, key,
):
    plan_path, _plan_ = m054._plan(tmp_path)
    late = (
        {"wires": [{"primitiveId": "w-late",
                    "state": {"Line": [0, 0, 100, 0], "Net": "GND"}}]}
        if key == "wires" else {key: [copy.deepcopy(DRAWING_ITEM[key])]}
    )
    editor = _GrowsBeforeWrite(
        page="page-late",
        pages=[m054._page_row("page-late")],
        late=late,
    )
    code, payload, editor = _apply(monkeypatch, tmp_path, plan_path, editor)
    printed = capsys.readouterr().out

    assert code == 4, printed
    assert payload["reason"] == "page_not_empty"
    assert editor.writes == [], (
        "the page was empty at scan time and is not empty now — nothing may be written"
    )
    before = payload["page"]["censusBefore"]
    if key == "wires":
        assert before["wireCount"] == 1
    else:
        assert before[DRAWING_REPORT_KEYS[key]] == 1, (
            "the refusal must name the section that made the page non-empty, "
            f"not report an all-zero census: {before}"
        )
    phrase = " ".join(payload["notes"])
    assert "not empty" in phrase
    assert f"1 {'wire(s)' if key == 'wires' else DRAWING_NOUNS[key]}" in phrase


class _NewPageComesBackWithText(m054._FakeEditor):
    """`sch.doc.new` lands a page that already shows a text (a host side effect)."""

    async def call(self, action, params=None, **_route):
        payload = await super().call(action, params, **_route)
        if action == "sch.doc.new":
            page = str((payload or {}).get("pageUuid") or "")
            store = self._store_for(page)
            store["drawing"]["texts"].append(
                copy.deepcopy(DRAWING_ITEM["texts"])
            )
        return payload


def test_a_created_page_that_already_holds_a_text_is_still_refused(
    monkeypatch, tmp_path, capsys,
):
    """The created leg keeps its guard, and it now sees the drawing sections too."""
    plan_path, _plan_ = m054._plan(tmp_path)
    editor = _NewPageComesBackWithText(page="page-taken", pages=[])
    code, payload, editor = _apply(
        monkeypatch, tmp_path, plan_path, editor, "--new-page",
    )
    printed = capsys.readouterr().out

    assert code == 4, printed
    assert payload["reason"] == "page_not_empty"
    assert payload["page"]["created"] is True
    assert [action for action, _params in editor.writes] == ["sch.doc.new"], (
        "the page was created, then refused before any drawing write landed"
    )
    assert payload["page"]["censusBefore"]["textCount"] == 1
