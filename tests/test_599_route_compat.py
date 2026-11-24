"""599: the route/provenance compatibility split, and the lint predicate counts.

Two guards live here, both about text that had drifted from the machine source:

* **The lint counts** in `commands/draw.py`'s `lint` help, `cli.py`'s
  `_cmd_draw_lint` docstring and this suite's `test_111` docstring. They once
  said "nine"/"eleven" while `drawlint.PREDICATES` was running 19 (16 geometric
  + 3 netlist-only); this test reads the table and refuses a stale number.
* **The route split's own helper**: `route`/`provenanceSha256` are the only two
  keys 590 adds, and the pre-590 shas in `test_520j_islands`,
  `test_p5_flag_group_scope` and `test_548p64_pre_group_lanes` are compared
  against the document with exactly those two keys taken off. A third moving key
  — a real geometry change — must fail the projection, not hide behind the pin.
"""

from __future__ import annotations

import json
from pathlib import Path

from boardwise.core.layoutplan import (
    LayoutPart,
    LayoutPlan,
    LayoutSource,
    ROUTE_AUTOMATIC,
    ROUTE_REFERENCE_REPLAY,
)
from boardwise.engines import drawlint

REPO = Path(__file__).resolve().parents[1]


def _chunk(text: str, anchor: str, length: int = 400) -> str:
    start = text.index(anchor)
    return text[start:start + length]


def test_the_lint_predicate_counts_are_the_machine_tables():
    total = len(drawlint.PREDICATES)
    netlist = set(drawlint.NETLIST_PREDICATES)
    geometry = {predicate for predicate, _ in drawlint.PREDICATES} - netlist
    assert (total, len(geometry), len(netlist)) == (19, 16, 3)
    assert geometry.isdisjoint(netlist)
    assert geometry | netlist == {predicate for predicate, _ in drawlint.PREDICATES}


def test_the_lint_help_and_docstrings_state_the_machine_counts():
    total = len(drawlint.PREDICATES)
    netlist = len(drawlint.NETLIST_PREDICATES)
    geometry = total - netlist

    draw = (REPO / "src" / "boardwise" / "commands" / "draw.py").read_text(
        encoding="utf-8")
    help_chunk = _chunk(draw, "Read-only readability lint of one page")
    assert f"{total} predicates" in help_chunk, help_chunk
    assert f"{geometry} geometric" in help_chunk, help_chunk
    assert f"{netlist} netlist-only" in help_chunk, help_chunk
    assert "nine geometric" not in help_chunk, help_chunk

    cli = (REPO / "src" / "boardwise" / "cli.py").read_text(encoding="utf-8")
    docstring = _chunk(cli, "def _cmd_draw_lint", 500)
    assert f"{total} read-only readability predicates" in docstring, docstring
    assert f"{geometry} geometric" in docstring, docstring
    assert f"{netlist} that run only when a netlist" in docstring, docstring
    assert "eleven" not in docstring, docstring

    review = (REPO / "tests" / "test_111_draw_lint.py").read_text(encoding="utf-8")
    header = review[:1200]
    assert f"{total} readability predicates" in header, header
    assert f"{geometry} geometric" in header, header
    assert f"{netlist} that run only when a netlist" in header, header
    assert "Nine geometric" not in header, header


# ------------------------------------------------- the route split's contract

_ROUTE_KEYS = ("route", "provenanceSha256")


def _plan() -> LayoutPlan:
    return LayoutPlan(
        source=LayoutSource(circuit_sha256="a" * 64, presentation_sha256="b" * 64),
        parts=[LayoutPart(part_id="R1", reference="R101", symbol_ref="R0402",
                          symbol_hash="c" * 64, x=0.0, y=0.0)],
    )


def test_the_projection_the_pins_use_differs_by_exactly_the_two_route_keys():
    body = _plan().to_jsonable()
    projection = {key: value for key, value in body.items() if key not in _ROUTE_KEYS}
    assert set(body) - set(projection) == set(_ROUTE_KEYS)
    assert body["route"] == ROUTE_AUTOMATIC
    assert projection["geometrySha256"] == body["geometrySha256"], (
        "the geometry digest is route-independent, so a pre-590 pin still binds")


def test_a_pre_590_document_gains_the_keys_only_when_the_route_is_stated():
    body = _plan().to_jsonable()
    projection = json.loads(json.dumps(
        {key: value for key, value in body.items() if key not in _ROUTE_KEYS}))
    old = LayoutPlan.from_dict(projection)
    assert old.route == ROUTE_REFERENCE_REPLAY and old.route_declared is False
    written = old.to_jsonable()
    assert "route" not in written and "provenanceSha256" not in written
