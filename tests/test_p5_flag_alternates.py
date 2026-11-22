"""548D3D: an alternate is not an obstacle for the next rung of the same ladder.

``_flag_alternates`` walks the ladder :func:`_flag_pin_lead` already owns: each
call gets the grades already answered added to ``blocked``, so the next answer is
the next rung the ladder itself would have drawn. Board2 P5's U30.9 (3V3) and
U30.8 (GND) put their first leads on the **same** ``x = -115`` vertical; the only
joint answer is one flag hanging up and the other down, which means each pad's
ladder must be allowed to reuse its first run / corner and turn the other way.
The old loop suppressed that rung because it added the previous candidate's
**lead lattice nodes and flag box** to ``blocked`` — treating alternatives as if
they were simultaneous copper. Only the anchor a grade already took is a real
suppression.

What this file pins:

* with a controlled ladder that refuses a rung when its first run is cut (the
  production ``_span_free`` rule, asked through the production
  ``_strictly_on_segment``), the two opposite hangs at one corner are both
  returned, and the joint pair chosen from them passes the unchanged
  :func:`_corridor_pair_clash` while the first grades do not;
* on a hand-written page the **production** ``_flag_pin_lead`` really answers
  both hangs at the same corner for U1.1, every returned candidate is one of the
  production function's own answers, the anchors are unique, and the joint pair
  (U1.1 up, U1.2 down) keeps apart;
* a **reserved seat** is replayed against the flag walls actually on the page:
  a wall cutting its lead makes the replay drop it, name it in ``notes`` and fall
  through to the ordinary ladder instead of drawing the stale seat;
* the hybrid walk keeps the **legacy** list and order first and adds only grades
  that share a legacy first run and corner and turn the opposite way;
* the ch343 four-island sheet compiles to its **8 pages / 0 failures** baseline.

Restoring the old ``extra |= _lattice_nodes(...)`` / ``_nodes_in_box(...)`` lines
in the *first* (legacy) walk makes the first two tests red. Returning the
expanded (anchor-only) walk, or appending every expanded candidate instead of
only the same-run opposite hang, makes the third test red; the ch343 page test
is red on the anchor-only walk (measured: 0 pages). The corridor predicate is
not loosened here: the first grades must still press.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_p5_flag_text_escape as p5  # noqa: E402
import test_053b_drawcompiler as t053b  # noqa: E402

from boardwise.core.symbolprofile import SymbolProfile  # noqa: E402
from boardwise.engines import drawcompiler as dc  # noqa: E402

FLAG = SymbolProfile(
    symbol_ref="PWR-3V3", title="PWR-3V3",
    body=(-6.0, 0.0, 6.0, 18.0), pins=[])


def _ladder(point, blocked):
    """The shape the real ladder offers at one corner: up, then down.

    The refusals are the production ones, not invented here: an anchor already
    taken is a wall, and a seat node anywhere *inside* the run cuts it — that is
    ``_flag_anchor``'s ``_key(anchor) in blocked`` and ``_span_free``'s
    ``_strictly_on_segment``. The two answers share ``point`` -> ``corner`` and
    differ only in the direction the flag hangs.
    """
    corner = (point[0] + 40.0, point[1])
    for hang in (1.0, -1.0):
        anchor = (corner[0], corner[1] + hang * 25.0)
        lead = (point, corner, anchor)
        if dc._key(anchor) in blocked:
            continue
        if any(dc._strictly_on_segment(node, point, corner) for node in blocked):
            continue
        if any(dc._strictly_on_segment(node, corner, anchor) for node in blocked):
            continue
        return anchor, lead, hang, []
    return dc._rounded(point), None, 1.0, []


def _stub(monkeypatch):
    def call(ctx, placed, net_id, profile, member, point, router, blocked,
             solids, bodies=None):
        return _ladder(point, blocked)

    monkeypatch.setattr(dc, "_flag_pin_lead", call)


def _legacy_walk(ctx, placed, net_id, profile, member, point, router, blocked,
                 solids, bodies):
    """The pre-548D3D enumeration: lead lattice and box suppress the next rung."""
    family = dc.flag_glyph_kind(profile)
    extra, out, seen = set(), [], set()
    while True:
        anchor, lead, hang, _crossings = dc._flag_pin_lead(
            ctx, placed, net_id, profile, member, point, router,
            blocked | extra, solids, bodies)
        if lead is None:
            break
        rotation = dc._flag_rotation((0.0, hang), family)
        box = dc._flag_box(profile, rotation, anchor, net_id)
        key = (anchor, tuple(lead), hang)
        if key not in seen:
            seen.add(key)
            out.append((anchor, lead, hang, rotation, box))
        extra.add(dc._key(anchor))
        for start, end in zip(lead, lead[1:]):
            extra |= dc._lattice_nodes(router, start, end)
        extra |= dc._nodes_in_box(router, box)
        if len(out) > 64:
            break
    return out


def _u1_context():
    ctx = p5._context(p5.FLAG_MEMBERS)
    ctx.presentation.text_placement = "native-attr"
    placed = p5._placement()
    expressions = dc._expressions(ctx, placed)
    profile, _ref = dc._flag_plan(ctx, "3V3", "power")
    router = dc._Router(grid=5.0, residue=placed.residue, boxes=[],
                        bounds=(0.0, 0.0, 800.0, 800.0))
    point = dict(expressions["3V3"].points)["U1.1"]
    blocked = dc._blocked_points(ctx, placed, "3V3", [], [], [])
    return ctx, placed, profile, router, point, blocked


# ============ 1. the causal shape: same first run, opposite hang, joint pair


def test_alternates_reuse_the_first_run_and_turn_the_other_way(monkeypatch):
    _stub(monkeypatch)
    router = dc._Router(grid=5.0, residue=(0.0, 0.0), boxes=[],
                        bounds=(0.0, 0.0, 800.0, 800.0))

    ctx = SimpleNamespace(
        presentation=SimpleNamespace(text_placement="native-attr"))

    def alternates(point, member):
        return dc._flag_alternates(
            ctx, None, "3V3", FLAG, member, point, router, set(), [], None)

    lefts = alternates((0.0, 0.0), "U1.1")
    assert len(lefts) == 2, (
        "the ladder offered both hangs at one corner; the alternate walk must "
        f"return both, got {[(item[0], item[2]) for item in lefts]}")
    assert lefts[0][1][:2] == lefts[1][1][:2], (
        "premise: the two alternates share the first run and its corner")
    assert lefts[0][2] != lefts[1][2], "premise: the two alternates hang opposite"
    assert len({dc._key(item[0]) for item in lefts}) == 2, (
        "the two anchors are distinct seats")

    rights = alternates((0.0, 10.0), "U2.1")
    assert len(rights) == 2

    # the gate this batch must not widen: the first grades still press
    assert dc._corridor_pair_clash(lefts[0], rights[0]), (
        "the first grades' vertical legs overlap on this page, so the corridor "
        "test must still refuse them")

    picked = next(
        ((left, right) for left in lefts for right in rights
         if not dc._corridor_pair_clash(left, right)), None)
    assert picked is not None, (
        "two legal alternates can keep their vertical legs apart by hanging "
        "opposite ways; the joint walk found no such pair")
    assert picked[0][2] != picked[1][2], (
        "the pair that keeps apart must be the opposite-hang pair")
    assert not dc._corridor_pair_clash(*picked)


# ========= 2. the production ladder really answers both hangs; no duplicate


def test_production_ladder_answers_both_hangs_and_the_pair_keeps_apart(
        monkeypatch):
    ctx = p5._context(p5.FLAG_MEMBERS)
    ctx.presentation.text_placement = "native-attr"
    placed = p5._placement()
    expressions = dc._expressions(ctx, placed)
    profile, _ref = dc._flag_plan(ctx, "3V3", "power")
    assert profile is not None, "premise: the book carries a PWR-3V3 flag"
    points = dict(expressions["3V3"].points)
    router = dc._Router(grid=5.0, residue=placed.residue, boxes=[],
                        bounds=(0.0, 0.0, 800.0, 800.0))
    blocked = dc._blocked_points(ctx, placed, "3V3", [], [], [])

    calls: list[tuple] = []
    original = dc._flag_pin_lead

    def spy(*args, **kwargs):
        answer = original(*args, **kwargs)
        calls.append(answer)
        return answer

    monkeypatch.setattr(dc, "_flag_pin_lead", spy)

    def alternates(member):
        return dc._flag_alternates(
            ctx, placed, "3V3", profile, member, points[member], router,
            blocked, [], None)

    lefts = alternates("U1.1")
    rights = alternates("U1.2")
    assert calls, "the production ladder was never asked"

    # every candidate is the production function's own answer, not a shape
    # rebuilt here; and the walk is finite with distinct seats.
    for item in [*lefts, *rights]:
        assert any(item[0] == call[0] and item[1] == call[1]
                   and item[2] == call[2] for call in calls), (
            f"{item[:3]} did not come from a _flag_pin_lead answer")
    for rows in (lefts, rights):
        assert len(rows) <= 65, "the walk must stay inside its 64-rung cap"
        anchors = [dc._key(item[0]) for item in rows]
        assert len(set(anchors)) == len(anchors), (
            f"the walk returned an anchor twice: {anchors}")

    # the causal fact: two rungs at the *same* corner, hanging the other way
    first = lefts[0]
    same_run = [item for item in lefts if item[1][:2] == first[1][:2]]
    assert len(same_run) == 2, (
        "U1.1's ladder turns at one corner and has a legal rung on each side; "
        f"the walk returned only {[(i[0], i[2]) for i in same_run]} there")
    assert {item[2] for item in same_run} == {1.0, -1.0}

    # and the joint pair those rungs enable keeps apart, while the first
    # grades press (so the gate is not loosened)
    assert dc._corridor_pair_clash(lefts[0], rights[0]), (
        "premise: U1.1's and U1.2's first grades cross")
    picked = next(
        ((left, right) for left in lefts for right in rights
         if not dc._corridor_pair_clash(left, right)), None)
    assert picked is not None
    assert not dc._corridor_pair_clash(*picked)


# ============ 3. a reserved seat is replayed against the flag walls on the page


def test_reserved_seat_is_dropped_when_a_flag_wall_cuts_its_lead(monkeypatch):
    ctx = p5._context(p5.FLAG_MEMBERS)
    placed = p5._placement()
    profile, _ref = dc._flag_plan(ctx, "3V3", "power")
    router = dc._Router(grid=5.0, residue=placed.residue, boxes=[],
                        bounds=(0.0, 0.0, 800.0, 800.0))
    point = dict(dc._expressions(ctx, placed)["3V3"].points)["U1.1"]
    seat = ((100.0, 75.0), 0.0,
            ((70.0, 50.0), (100.0, 50.0), (100.0, 75.0)))
    router.flag_seats[("3V3", "U1.1")] = seat
    # a flag drawn earlier in this same pass: its wall cuts the reserved lead's
    # first run. This is the picture the reservation could not see.
    router.flag_walls.append((75.0, 45.0, 85.0, 55.0))
    fallback = ((70.0, 110.0), ((70.0, 50.0), (70.0, 110.0)), 1.0, [])

    monkeypatch.setattr(dc, "_coreless_group_flag_length", lambda *a, **k: None)
    monkeypatch.setattr(dc, "_flag_pin_lead", lambda *a, **k: fallback)
    placed_flags: list[tuple] = []

    def place(net_id, profile_, ref, anchor, rotation, lead, *rest):
        placed_flags.append((net_id, anchor, rotation, lead))

    monkeypatch.setattr(dc, "_place_flag", place)
    notes: list[str] = []
    # The stricter replay is opt-in: this page explicitly asks for it rather than
    # changing every legacy page that happens to have a reserved seat.
    ctx.presentation.text_placement = "native-attr"
    failure = dc._flag_pins_seats(
        ctx, placed, "3V3", profile, "PWR-3V3", [("U1.1", point)],
        router, [], [], [], [], set(), [], family=dc.flag_glyph_kind(profile),
        ordinary_seats={("3V3", "U1.1")}, stub=False, notes=notes)

    assert failure is None, (failure.category, failure.detail)
    dropped = [note for note in notes
               if "reserved lane of U1.1 was dropped" in note]
    assert dropped, f"the stale seat was not dropped; notes={notes}"
    assert "its lead run" in dropped[0], dropped[0]
    assert placed_flags == [(
        "3V3", fallback[0],
        dc._flag_rotation((0.0, fallback[2]), dc.flag_glyph_kind(profile)),
        fallback[1])], (
        "after the drop the ordinary ladder must draw the flag; "
        f"placed={placed_flags}")


# ===== 4. the hybrid keeps the legacy list/order and only adds the missing hang


def test_hybrid_keeps_the_legacy_list_first_and_adds_only_same_run_opposites():
    ctx, placed, profile, router, point, blocked = _u1_context()
    legacy = _legacy_walk(ctx, placed, "3V3", profile, "U1.1", point, router,
                          blocked, [], None)
    hybrid = dc._flag_alternates(ctx, placed, "3V3", profile, "U1.1", point,
                                 router, blocked, [], None)

    assert hybrid[:len(legacy)] == legacy, (
        "the legacy grades and their order must come first; "
        f"legacy={[(i[0], i[2]) for i in legacy]}, "
        f"hybrid head={[(i[0], i[2]) for i in hybrid[:len(legacy)]]}")
    extras = hybrid[len(legacy):]
    assert extras, "premise: U1.1's same-corner opposite hang is the extra rung"
    keys = [(item[0], tuple(item[1]), item[2]) for item in hybrid]
    assert len(set(keys)) == len(keys), "the walk returned a duplicate grade"
    for extra in extras:
        assert any(extra[1][:2] == old[1][:2] and extra[2] != old[2]
                   for old in legacy), (
            "an extra grade may only be a legacy first run / corner turning the "
            f"other way; got {extra[:3]} against {[o[:3] for o in legacy]}")


# ============ 5. the page the hybrid exists for: ch343's eight islands


def test_ch343_four_island_sheet_compiles_with_the_hybrid_ladder():
    pagecompiler, circuit, presentation, book = t053b._four_island_sheet()
    result = pagecompiler.compile_page(
        circuit, presentation, book,
        pagecompiler.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0)))
    assert result.failures == [], [item.detail for item in result.failures]
    assert len(result.pages) == 8, (
        f"the ch343 baseline is 8 pages, got {len(result.pages)}")
