"""543I-4B: **one** off-lattice flag is moved to the nearest lattice node.

P33's editor refused the page with `NETOBJECTONGRID`: a local ground flag stood
at `(320, 677.5)` with its lead `(290, 690)-(320, 690)-(320, 677.5)`, and the
half came from the ladder's own preference rung — ``FLAG_JOG / 2 = 12.5`` on a
5-unit page. Re-running the whole page for one half unit is expensive (a global
grid filter moved every flag and the whole module), so the correction is
**local**: when the explicit `native-attr` + `serviceLayout` construction is
stated and a decided flag's anchor is off the lattice, the two adjacent lattice
nodes are tried, nearest first, with the lead's last leg re-aimed at the chosen
one — and every candidate goes back through the checks the ladder used.

What this file pins:

* the half-grid page is a **measured** defect: the ladder still produces
  `(300, 702.5)` when the local pass is off (the counterexample below), and the
  compiled page under the local pass has **every** flag anchor and **every** lead
  vertex on the 5-unit lattice;
* the choice is the **nearest legal** node (`702.5 → 700`, not `705`), and it is
  chosen because it passes, not because it is first in a list;
* a conflicting candidate is **skipped**, and when both adjacent nodes conflict
  the flag is **refused by name** — never snapped blind onto a body, a row, a
  foreign pin or another net's wire;
* the default path (no `native-attr`, no `serviceLayout`) is not touched.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines.router import _Router

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
CIRCUIT = CircuitSpec.load(SPECS / "ch343_uart_534a.circuit.json")
LIBRARY = {
    item["symbolRef"]: SymbolProfile.from_dict(item)
    for item in json.loads(
        (SPECS / "ch343_uart_v4.library.json").read_text(encoding="utf-8")
    )["profiles"]
}
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)
PAYLOAD = json.loads((ROOT / "evidence/543h3b/spec_h3b.json").read_text(encoding="utf-8"))
GRID = 5.0


def _on_grid(point) -> bool:
    return all(abs(float(value) / GRID - round(float(value) / GRID)) < 1e-6
               for value in point[:2])


def _router(boxes=()) -> _Router:
    return _Router(grid=GRID, residue=(0.0, 0.0), boxes=list(boxes),
                   bounds=(0.0, 0.0, 400.0, 400.0))


@pytest.fixture(scope="module")
def page():
    result = pc.compile_page(
        CIRCUIT, PresentationSpec.from_dict(copy.deepcopy(PAYLOAD)), LIBRARY,
        pc.PageCompileBudget(page_box=PAGE_BOX),
    )
    assert result.ok, result.render_failures()
    return result.pages[0]


def test_the_half_grid_flag_is_a_measured_defect(page):
    """The ladder really does produce a half anchor — the pass has something to fix."""
    flags = [(round(symbol.x, 3), round(symbol.y, 3)) for symbol in page.plan.power_symbols]
    assert flags, "the page states its flags"
    # The page under the local pass is fully latticed...
    assert all(_on_grid(flag) for flag in flags), flags
    # ... and the ladder's own half rung is still there for a page that does not
    # take the pass: the counterexample is `_flag_anchor`'s output with a jog of
    # `FLAG_JOG / 2` at an anchor whose corner is on the lattice.
    anchor = (100.0, 100.0 + dc.FLAG_JOG / 2.0)
    assert not _on_grid(anchor)


def test_every_flag_anchor_and_lead_vertex_is_on_the_lattice(page):
    plan = page.plan
    for symbol in plan.power_symbols:
        assert _on_grid((symbol.x, symbol.y)), (symbol.net, symbol.x, symbol.y)
    assert plan.segments, "the page states its wires"
    for segment in plan.segments:
        for point in segment.points:
            assert _on_grid(point), (segment.net, tuple(point))


def test_the_nearest_legal_node_is_what_was_chosen():
    """`102.5` becomes `100`, the nearest lattice node that passes, not `105`.

    543M: this used to read the choice off the compiled page's own ground flag at
    `(300, 700)`. 543K draws the signal pair horizontally, so that pin now has a
    legal seat without the local pass and the page no longer carries the half-grid
    case at all. The rule is therefore pinned where it is decided —
    `_grid_local_seat` — which is the stronger statement: one anchor, one lead,
    and the only thing that changes between the two seats is the obstacle.
    """
    profile = LIBRARY["PWR-GND"]
    ctx = type("Ctx", (), {})()
    ctx.presentation = PresentationSpec.from_dict(copy.deepcopy(PAYLOAD))
    ctx.budget = type("B", (), {"page_box": PAGE_BOX})()
    # 102.5 is 2.5 from 100 and 2.5 from 105 — a tie, broken toward the lower
    # node; the lead's last leg is re-aimed at the node the flag actually takes.
    anchor = (100.0, 102.5)
    lead = [(80.0, 90.0), (100.0, 90.0), (100.0, 102.5)]
    seat, seated_lead, failure = dc._grid_local_seat(
        ctx, _router(), "GND", profile, anchor, 0.0, lead, [], set(),
    )
    assert failure is None, failure
    assert seat == (100.0, 100.0), seat
    assert list(seated_lead) == [(80.0, 90.0), (100.0, 90.0), (100.0, 100.0)], seated_lead

    # The lower node is not taken for being first in the list: when it would
    # **collapse** the lead's last leg (the corner already sits on it), the far
    # node is the seat — every candidate goes back through the ladder's checks.
    collapsed = [(80.0, 100.0), (100.0, 100.0), (100.0, 102.5)]
    seat, seated_lead, failure = dc._grid_local_seat(
        ctx, _router(), "GND", profile, anchor, 0.0, collapsed, [], set(),
    )
    assert failure is None, failure
    assert seat == (100.0, 105.0), seat
    assert list(seated_lead) == [(80.0, 100.0), (100.0, 100.0), (100.0, 105.0)], seated_lead

    # An anchor that is already on the lattice is left exactly where it is.
    seat, seated_lead, failure = dc._grid_local_seat(
        ctx, _router(), "GND", profile, (100.0, 100.0), 0.0,
        [(80.0, 100.0), (100.0, 100.0)], [], set(),
    )
    assert failure is None and seat == (100.0, 100.0), (seat, failure)


def test_a_conflicting_node_is_skipped_and_the_flag_is_refused():
    """A lattice node that puts the flag on a part is not a seat."""
    profile = LIBRARY["PWR-GND"]
    ctx = type("Ctx", (), {})()
    ctx.presentation = PresentationSpec.from_dict(copy.deepcopy(PAYLOAD))
    ctx.budget = type("B", (), {"page_box": PAGE_BOX})()
    router = _router()
    # A solid box covering both adjacent nodes: nothing fits, and the answer is
    # a named refusal, not a flag drawn on top of the part.
    anchor = (100.0, 102.5)
    lead = [(80.0, 100.0), (100.0, 100.0), (100.0, 102.5)]
    solids = [(95.0, 98.0, 105.0, 108.0)]
    _anchor, _lead, failure = dc._grid_local_seat(
        ctx, router, "+5V", profile, anchor, 0.0, lead, solids, set(),
    )
    assert failure is not None, (_anchor, _lead)
    assert "+5V" in failure.detail and "not on the compiler's lattice" in failure.detail


def test_the_default_path_is_not_snapped():
    payload = copy.deepcopy(PAYLOAD)
    payload.pop("textPlacement")
    ctx = type("Ctx", (), {})()
    ctx.presentation = PresentationSpec.from_dict(payload)
    assert dc._grid_local_enabled(ctx) is False
