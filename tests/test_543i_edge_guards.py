"""543I-5: edge guards around the 543H-I passes — no new behaviour, only proof.

The independent review of P34 found no input that changes the delivered page, but
three places where the code's *edge* was only asserted from the happy side, plus
one debug hook that shipped in `_no_candidate_failures`. This file pins what the
fixes had to keep true:

* **no debug stream**.  `_no_candidate_failures` carried an `import os as _os /
  BW_D / print("DBGVAR", …)` hook. It is gone, and a compile whose every variant
  is refused prints nothing even with `BW_D` set — checked end to end on the
  flyback page whose sheet is too short (a real zero-candidate refusal, 530G's
  own scene), and at the function itself.
* **a middle run grows by insertion, never by moving its corner**. `543I-1` grew
  a short carrier by re-aiming the vertex at `far`. When that vertex is a corner
  of a longer polyline, re-aiming it swings the *next* leg onto a diagonal. The
  legal repair is to insert the far end between the corner and its outward
  neighbour, and where that neighbour turns (or would be passed) the answer is a
  named refusal. The carrier gate itself is not widened.
* **`_grid_local_seat` moves one coordinate**.  The candidate replaces the lead's
  end and keeps the rest, so trying the cartesian product of both off-lattice
  halves could aim the last leg at a diagonal. Only the axis the last leg runs
  along may move; a half that lies *across* that leg has no seat at all (the pass
  exists to put the flag on the lattice) and is refused by name. P34's own
  single-axis case (`702.5 → 700`, `x` untouched) is unchanged.
* **the flag-group audit refuses**.  `543I-2`'s re-measure had only ever been
  observed passing (17 calls, 0 refusals on P34). A body that stands in the
  corridor between two grouped seats after the wiring must produce the named
  `layout-unsat` refusal — otherwise the audit is decoration.

Every geometry here is inline: a test does not read an evidence directory.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from boardwise.core import pageframe
from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import LayoutLabel, LayoutPlan
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawapply
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines.router import _Router

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)
GRID = 5.0

CIRCUIT = CircuitSpec.load(SPECS / "ch343_uart_534a.circuit.json")
LIBRARY = {
    item["symbolRef"]: SymbolProfile.from_dict(item)
    for item in json.loads(
        (SPECS / "ch343_uart_v4.library.json").read_text(encoding="utf-8")
    )["profiles"]
}
PAYLOAD = json.loads(
    (ROOT / "evidence/543h3b/spec_h3b.json").read_text(encoding="utf-8")
)


class _Wire:
    def __init__(self, net: str, points):
        self.net = net
        self.points = [(float(x), float(y)) for x, y in points]


class _Label:
    def __init__(self, net: str, x: float, y: float, bbox, mode: str = "native"):
        self.net = net
        self.x = float(x)
        self.y = float(y)
        self.bbox = tuple(float(value) for value in bbox)
        self.text_mode = mode


def _axis_aligned(points) -> bool:
    return all(
        abs(start[0] - stop[0]) <= 1e-9 or abs(start[1] - stop[1]) <= 1e-9
        for start, stop in zip(points, points[1:])
    )


# --------------------------------------------------------------- 1 · no debug


def _flyback():
    circuit = CircuitSpec.load(SPECS / "flyback_uc3845.circuit.json")
    presentation = PresentationSpec.load(SPECS / "flyback_uc3845.presentation.json")
    book = {
        profile.symbol_ref: profile
        for profile in (
            SymbolProfile.from_dict(item)
            for item in json.loads(
                (SPECS / "flyback_uc3845.library.json").read_text(encoding="utf-8")
            )["profiles"]
        )
    }
    return circuit, presentation, book


def test_a_refusal_prints_nothing_even_with_the_debug_switch_on(
    monkeypatch, capsys
):
    """Every variant refused is the one path the debug hook used to write on."""
    circuit, presentation, book = _flyback()
    short = (0.0, 0.0, 1170.0, 500.0)
    budget = dc.CompileBudget(
        page_box=short, keepouts=pageframe.title_block_keepouts(short),
    )

    monkeypatch.setenv("BW_D", "1")
    with_debug = dc.compile(circuit, presentation, book, budget)
    captured = capsys.readouterr()

    assert with_debug.ok is False and with_debug.candidates == [], with_debug.pages
    assert with_debug.rejected, "the zero-candidate path reads its rejections"
    assert captured.out == "" and captured.err == "", captured
    assert "DBGVAR" not in captured.out
    rendered = with_debug.render_failures()
    assert "1 variant(s) were built and refused" in rendered, rendered

    monkeypatch.delenv("BW_D", raising=False)
    without_debug = dc.compile(circuit, presentation, book, budget)
    quiet = capsys.readouterr()
    assert quiet.out == "" and quiet.err == "", quiet
    assert without_debug.render_failures() == rendered


def test_the_no_candidate_reason_reads_the_rejections(monkeypatch, capsys):
    """The function itself: three refused variants, one named summary, no print."""
    monkeypatch.setenv("BW_D", "1")
    failure = dc.GrammarFailure(
        category=dc.FAILURE_LAYOUT_UNSAT,
        subject="U1",
        detail="the module needs 300 units of height and the sheet states 200",
        action="state a taller sheet",
    )
    result = dc.CompileResult(
        rejected=[
            dc.RejectedCandidate(
                variant=f"spacing=1 pose-variant={index}",
                reason="refused",
                failure=failure,
            )
            for index in range(3)
        ]
    )
    failures = dc._no_candidate_failures(result)
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "", captured
    assert len(failures) == 1
    assert failures[0].subject == "U1"
    assert "300 units of height" in failures[0].detail
    assert "3 variant(s) were built and refused" in failures[0].detail


def test_no_debug_hook_is_left_in_the_draw_engines():
    """A source pin: the hook is gone, not merely quiet."""
    for name in ("drawcompiler.py", "drawapply.py", "flaggroups.py"):
        text = (ROOT / "src" / "boardwise" / "engines" / name).read_text(
            encoding="utf-8"
        )
        assert "DBGVAR" not in text, name
        assert "BW_D" not in text, name


# ------------------------------------------------------- 2 · middle-run cover


def _cover(wires, labels):
    built = drawapply._Built()
    built.wires.extend(wires)
    problems = drawapply._native_carrier_cover(
        built, LayoutPlan(labels=list(labels)), {}, {}, [], PAGE_BOX,
    )
    return built, problems


def test_a_middle_run_that_turns_is_refused_rather_than_bent():
    """P32's 5-unit lead on a polyline: the corner may not move to `far`.

    `(215, 700)-(205, 700)-(205, 680)` is the counterexample. Growing the
    10-unit horizontal run at its corner used to rewrite the corner to
    `(175, 700)`, which swings the vertical leg into the diagonal
    `(175, 700)-(205, 680)` — an off-axis conductor nothing measured.
    """
    wires = [
        _Wire("D+", [(215, 700), (205, 700), (205, 680)]),
        _Wire("D+", [(300, 600), (340, 600)]),
    ]
    label = _Label("D+", 205, 700, (188, 700.5, 202, 709.5))
    built, problems = _cover(wires, [label])

    assert problems, "a corner the name cannot reach is refused, not bent"
    assert "diagonal" in problems[0], problems
    assert "D+" in problems[0]
    assert built.wires[0].points == [
        (215.0, 700.0), (205.0, 700.0), (205.0, 680.0),
    ], built.wires[0].points
    assert _axis_aligned(built.wires[0].points)


def test_a_middle_run_that_would_double_back_is_refused():
    """A collinear outward vertex *inside* the grown span is not a seat either.

    Reaching past it would make the polyline run forward and back over the same
    line; the carrier is a conductor, not a spur.
    """
    wires = [
        _Wire("D+", [(215, 700), (205, 700), (220, 700), (220, 680)]),
        _Wire("D+", [(300, 600), (340, 600)]),
    ]
    label = _Label("D+", 205, 700, (188, 700.5, 202, 709.5))
    built, problems = _cover(wires, [label])

    assert problems, "the doubling-back growth is refused"
    assert "doubling back" in problems[0], problems
    assert built.wires[0].points == [
        (215.0, 700.0), (205.0, 700.0), (220.0, 700.0), (220.0, 680.0),
    ], built.wires[0].points


def test_a_carrier_end_at_the_polyline_terminus_still_grows():
    """543I-1's own repair is untouched: a free end simply gets the new vertex."""
    wires = [
        _Wire("D+", [(200, 700), (205, 700), (240, 700)]),
        _Wire("D+", [(300, 600), (340, 600)]),
    ]
    label = _Label("D+", 200, 700, (172, 695.5, 186, 704.5))
    built, problems = _cover(wires, [label])

    assert problems == [], problems
    points = built.wires[0].points
    assert len(points) == 4, points
    assert points[0] == (155.0, 700.0), points
    assert _axis_aligned(points)


# ---------------------------------------------------- 3 · the half-grid seat


def _seat_ctx():
    ctx = type("Ctx", (), {})()
    ctx.presentation = PresentationSpec.from_dict(copy.deepcopy(PAYLOAD))
    ctx.budget = type("B", (), {"page_box": PAGE_BOX})()
    return ctx


def _router():
    return _Router(
        grid=GRID, residue=(0.0, 0.0), boxes=[], bounds=(0.0, 0.0, 400.0, 400.0),
    )


def test_the_grid_seat_never_aims_the_last_leg_off_its_axis():
    """A half in both coordinates: an older candidate moved x and y together.

    The lead's last leg runs along x here, so only x may move. There is no seat
    that keeps the lead orthogonal **and** puts the flag on the lattice, and a
    flag seated at `(100, 100)` would have a diagonal lead *and* still be off-grid
    in `y` — so the answer is the named refusal, never the diagonal `(100, 100)`.
    """
    anchor = (102.5, 102.5)
    lead = [(80.0, 102.5), (102.5, 102.5)]
    seat, moved, failure = dc._grid_local_seat(
        _seat_ctx(), _router(), "+5V", LIBRARY["PWR-GND"], anchor, 0.0, lead, [], set(),
    )

    assert failure is not None, (seat, moved)
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT
    assert "across the lead's last leg" in failure.detail, failure.detail
    assert [tuple(map(float, point)) for point in moved] == [
        (80.0, 102.5), (102.5, 102.5),
    ], moved
    assert _axis_aligned([(float(x), float(y)) for x, y in moved])


def test_a_half_along_the_last_leg_with_no_free_node_is_refused_by_name():
    """The ordinary half: both lattice nodes on the leg are taken."""
    anchor = (102.5, 100.0)
    lead = [(80.0, 100.0), (102.5, 100.0)]
    solids = [(95.0, 95.0, 110.0, 108.0)]
    seat, kept, failure = dc._grid_local_seat(
        _seat_ctx(), _router(), "+5V", LIBRARY["PWR-GND"], anchor, 0.0, lead,
        solids, set(),
    )

    assert failure is not None, (seat, kept)
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT
    assert "+5V" in failure.detail
    assert "(100, 100) puts the flag on a part or a row" in failure.detail, failure.detail
    assert "(105, 100) puts the flag on a part or a row" in failure.detail, failure.detail
    assert seat == anchor and list(kept) == lead


def test_the_single_axis_nearest_node_is_still_the_seat():
    """P34's own shape: `(100, 102.5)` becomes `(100, 105)`, x untouched."""
    seat, moved, failure = dc._grid_local_seat(
        _seat_ctx(), _router(), "+5V", LIBRARY["PWR-GND"], (100.0, 102.5), 0.0,
        [(80.0, 100.0), (100.0, 100.0), (100.0, 102.5)], [], set(),
    )

    assert failure is None, (seat, failure)
    assert seat == (100.0, 105.0), (seat, moved)
    assert moved == [(80.0, 100.0), (100.0, 100.0), (100.0, 105.0)], moved


# ------------------------------------------------- 4 · the audit can refuse


@pytest.fixture(scope="module")
def audit_scene():
    """One real page compile, with the audit's own arguments kept."""
    scenes: list[tuple] = []
    outcomes: list = []
    original = dc._flag_group_audit

    def audit(ctx, placed, router, expressions, order, segments, labels, symbols):
        out = original(ctx, placed, router, expressions, order, segments, labels,
                       symbols)
        scenes.append(
            (ctx, placed, router, expressions, order, list(segments),
             list(labels), list(symbols))
        )
        outcomes.append(out)
        return out

    dc._flag_group_audit = audit
    try:
        result = pc.compile_page(
            CIRCUIT, PresentationSpec.from_dict(copy.deepcopy(PAYLOAD)), LIBRARY,
            pc.PageCompileBudget(page_box=PAGE_BOX),
        )
    finally:
        dc._flag_group_audit = original

    assert result.ok, result.render_failures()
    assert scenes, "the page runs the re-measure"
    assert all(outcome is None for outcome in outcomes), [
        outcome.detail for outcome in outcomes if outcome is not None
    ]
    return scenes[0]


def test_the_audit_refuses_a_grouping_the_finished_ink_breaks(audit_scene):
    """The passing state is not the only state the audit can answer with.

    `+5V`'s `C1.1`/`C2.1` share one flag on P34 because a legal run still joins
    them. A body standing in that corridor after the wiring is exactly the
    "final obstruction" 543I-2 refuses: the seats no longer measure the same way,
    and the answer is a named `layout-unsat` — never a silent re-group and never
    a wider reach.

    The wall spans the page, so it cuts more than the pair it was aimed at —
    since 543J the `C1`/`C2` ground pads share a flag too, and the ground comes
    first in the audit's own order. What is pinned is therefore the shape of the
    answer: it names a net whose grouping the ink really changed, and a seat of
    that grouping. Which of the two nets answers first is not the contract.
    """
    ctx, placed, router, expressions, order, segments, labels, symbols = audit_scene
    expression = expressions["+5V"]
    pair = [group for group in expression.clusters if len(group) >= 2][0]
    (first, first_point), (second, second_point) = pair[0], pair[1]
    assert abs(first_point[0] - second_point[0]) > 1e-9, pair

    wall_x = (first_point[0] + second_point[0]) / 2.0
    router.boxes.append(
        (wall_x - 5.0, router.bounds[1] - 50.0, wall_x + 5.0, router.bounds[3] + 50.0)
    )
    failure = dc._flag_group_audit(
        ctx, placed, router, expressions, order, segments, labels, symbols,
    )

    assert failure is not None, "the finished ink has to be re-measured"
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT
    # The nets whose pre-wiring grouping the wall actually cuts.
    straddled = {
        net_id: [
            group for group in (expressions[net_id].clusters or ())
            if min(point[0] for _member, point in group)
            < wall_x
            < max(point[0] for _member, point in group)
        ]
        for net_id in order
        if expressions[net_id].clusters
    }
    straddled = {net: cuts for net, cuts in straddled.items() if cuts}
    assert failure.subject in straddled, (failure.subject, sorted(straddled))
    seats = {
        member for group in straddled[failure.subject] for member, _point in group
    }
    assert any(member in failure.detail for member in seats), (seats, failure.detail)
    assert "no longer measure the same way" in failure.detail, failure.detail
    # The pair the wall was aimed at is one of the broken groupings, so the
    # computed set is not empty and the assertion above has something to name.
    assert "+5V" in straddled, sorted(straddled)
    members = {member for group in straddled["+5V"] for member, _point in group}
    assert {first, second} <= members, (first, second, members)
