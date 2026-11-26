"""The order pass may not land a movable part on a sibling's real box.

History, because the file name is older than what it now guards. It started as a
550 evidence record: the radar MCU slice's five decoupling shunts take five host
feet. That test could only be read against ``.tmp_us_radar_*`` documents (not
part of the tree) and it measured a fact that already held, so it could not go
red on the defect it pointed at. The 550/551 handoff
(``.tmp_us_radar_band_fix/HANDOFF.md``) then measured where the slice really
fails: the band ladder hands the five shunts rungs **60 units apart**
(``C72`` -265, ``C73`` -325, ``C74`` -385, ``C75`` -445) and
``_honour_bound_orders`` is the only stage that moves them — ``near(C75, U63)``
drags ``C75`` -445 -> -380, which is inside ``C74``'s box ``-393.5 .. -376.5``,
and ``near(C69, U63)`` drags the OSC_IN load capacitor -765 -> -400 across
everything in between. One thing is wrong there and it is the one thing pinned
here: the order pass moved a part **onto a sibling's body**, and neither the
pass nor anything after it said so.

So this file is now a self-contained, red-first regression on that single
invariant. Everything it needs is in this file — the circuit, the symbol
profile, the presentation and the relations — so it runs on any checkout with no
``.tmp_*`` document and no import of another test module:

* a ``near`` trim and a ``left-of`` walk that would land the movable part's
  :func:`boardwise.engines.drawcompiler._part_box` (body **and** pin tips) on a
  **same-service-owner sibling's** box are **refused**, the coordinate is left
  alone, and the relation stays in
  :func:`boardwise.engines.drawcompiler._bound_orders` for the existing relation
  checker / refusal chain to name — never accepted silently as a stacked drawing;
* a walk whose landing really is free moves **exactly** as it did before
  (the historical legal moves are not touched);
* a pre-existing overlap does not block a walk *away* from it: the guard reads
  "this landing would put me on somebody", not "somebody is near me";
* and the guard is **narrow**, not wide: a landing on a part that is not a
  served sibling — no host, or a different host — still moves. This is the
  assertion that keeps the next batch from sliding back to "refuse every box
  overlap", which changed four parts of the flyback page for no reason
  (``.tmp_us_radar_owner_recon/REPORT.md`` sec.3).

The fixture therefore carries a real service relationship rather than bare
parts. ``U1`` declares ``core`` of the module ``A1``/``P1`` sit in and has a pin
on the ``VCC`` rail, so those two read ``STATUS_SERVED`` with ``host_id=U1`` —
the radar's ``C74``/``C75`` shape (both ``served``, ``host_id=U63``). ``U1``
itself is not a capacitor, ``R1`` is the reference the relations name, ``P2`` is
a capacitor with no host, and ``Q1`` is a capacitor served by a *different* core
(``U2``). Every test that depends on the guard firing opens with
:func:`_assert_the_fixture_is_served`, so the file cannot quietly go back to
``no_host`` and pass by never reaching the guard.

The measurement is the compiler's own two functions — ``_part_box`` and
``_overlaps``, the same pair :func:`boardwise.engines.drawcompiler._stack_is_clear`
and the readability contract read — so a test cannot agree with the pass while
disagreeing with the gate.
"""

from __future__ import annotations

import dataclasses
import math

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines.grammar.base import LEFT_OF, NEAR, RelativeConstraint
from boardwise.engines.layoutroles import STATUS_SERVED
from boardwise import cli

#: One two-terminal symbol, big enough that a lattice step (``grid`` 5) cannot
#: hide a body on body: 20 x 10 with the pin tips on the body's own sides.
PROFILE = {
    "kind": "boardwise-symbol-profile",
    "profileVersion": 1,
    "symbolRef": "R0402",
    "title": "R0402",
    "body": [-10.0, -5.0, 10.0, 5.0],
    "pins": [
        {"number": "1", "name": "1", "tip": [-10.0, 0.0], "direction": "left",
         "directionSource": "body-box", "electricalRole": "", "roleSource": "",
         "pinType": "Undefined", "length": None},
        {"number": "2", "name": "2", "tip": [10.0, 0.0], "direction": "right",
         "directionSource": "body-box", "electricalRole": "", "roleSource": "",
         "pinType": "Undefined", "length": None},
    ],
    "poses": [{"rotation": 0, "mirror": False}],
    "poseSource": "declared",
    "valueRow": "",
    "texts": [],
    "pinTexts": {"offsets": {}, "pins": {}},
    "source": "inline:test",
    "notes": [],
}

#: ``A1`` is the movable side in every case; ``R1`` is the reference the
#: relation names; ``P1`` is the third part nobody's relation mentions and the
#: **same-host sibling** a careless walk lands on. ``U1`` is the core that makes
#: ``A1``/``P1`` a served pair; ``P2`` is a capacitor with no host and ``Q1`` a
#: capacitor served by the other core ``U2`` — the two "not a sibling" controls.
VALUES = [
    ("U1", "CH343G"),
    ("A1", "100nF"),
    ("P1", "10uF"),
    ("R1", "10k"),
    ("P2", "1uF"),
    ("U2", "CH343G"),
    ("Q1", "100nF"),
]

PARTS = [
    {"id": part, "symbolRef": "R0402", "value": value,
     "provenance": "verified_recipe"}
    for part, value in VALUES
]

NETS = [
    # The served rail: the only net on which ``A1``/``P1``/``Q1`` are shunts, and
    # each core has a pin on it, which is what ``analyze_decoupling`` reads as
    # ``module-core``.
    {"id": "VCC", "class": "power", "members": ["U1.1", "A1.1", "P1.1", "U2.1", "Q1.1"],
     "provenance": "verified_recipe", "scope": "page"},
    {"id": "GND", "class": "gnd",
     "members": ["A1.2", "P1.2", "R1.2", "U1.2", "P2.2", "U2.2", "Q1.2"],
     "provenance": "verified_recipe", "scope": "project"},
    {"id": "SIG", "class": "signal", "members": ["R1.1"],
     "provenance": "verified_recipe", "scope": "page"},
    # ``P2``'s live terminal sits on a signal no core touches, so it is a
    # capacitor with **no host** — the "non-service" control.
    {"id": "ISO", "class": "signal", "members": ["P2.1"],
     "provenance": "verified_recipe", "scope": "page"},
]

POSES = {part["id"]: dc.SymbolPose(0.0, False) for part in PARTS}


def _context(*extra):
    """A real :class:`_Context` for the inline documents.

    Built through the same ``bind_grammar`` + ``_prepare`` pair every compile
    uses, so the pass reads the production context rather than a stub. The
    relations are added to the binding afterwards: a two-part page states no
    grammar the binder reads, and what this file measures is the **order pass**,
    not the binder (the binder's own near/left-of statements are pinned by
    ``tests/test_116_ordinal_consumption.py``).
    """
    circuit = CircuitSpec.from_dict({"parts": PARTS, "nets": NETS})
    presentation = PresentationSpec.from_dict({
        "modules": [
            {"id": "m", "role": "core", "core": "U1",
             "parts": ["U1", "A1", "P1", "R1", "P2"]},
            {"id": "m2", "role": "core", "core": "U2", "parts": ["U2", "Q1"]},
        ],
    })
    book = {"R0402": SymbolProfile.from_dict(PROFILE)}
    binding = dc.bind_grammar(circuit, presentation, book)
    if extra:
        binding = dataclasses.replace(
            binding, constraints=(*binding.constraints, *extra))
    prepared = dc._prepare(circuit, presentation, binding, book,
                           dc.CompileBudget(max_candidates=8))
    assert prepared.context is not None, [f.detail for f in prepared.failures]
    return prepared.context


def _assert_the_fixture_is_served(ctx):
    """Guard against a fixture that reads ``no_host`` and never reaches the gate.

    A narrow guard fires only for a **served** walking part landing on a
    **served** sibling with the same ``host_id``. If the fixture loses its
    ``core`` declaration the service analysis answers ``no_host`` for everything
    and both blocked tests below would pass for the wrong reason — the guard was
    never consulted. These readings are the fixture's own contract, measured by
    ``analyze_decoupling`` through the compiler's cached ``ctx.services()``.
    """
    services = ctx.services()
    a1 = services.for_part("A1")
    p1 = services.for_part("P1")
    assert a1 is not None and a1.status == STATUS_SERVED and a1.host_id == "U1", (
        f"the movable fixture part A1 is not served by U1: {a1}")
    assert p1 is not None and p1.status == STATUS_SERVED and p1.host_id == "U1", (
        f"the sibling fixture part P1 is not served by U1: {p1}")
    q1 = services.for_part("Q1")
    assert q1 is not None and q1.status == STATUS_SERVED and q1.host_id == "U2", (
        f"the different-host control Q1 is not served by U2: {q1}")
    p2 = services.for_part("P2")
    assert p2 is not None and p2.status != STATUS_SERVED, (
        f"the no-host control P2 is served after all: {p2}")
    u1 = services.for_part("U1")
    assert u1 is not None and u1.status != STATUS_SERVED, (
        f"the core U1 reads as a decoupling shunt: {u1}")


def _boxes(ctx, origins):
    return {
        part: dc._part_box(ctx.profile(part), POSES[part], origin)
        for part, origin in origins.items()
    }


def _collisions(ctx, origins):
    boxes = _boxes(ctx, origins)
    ids = sorted(boxes)
    return [
        (left, right)
        for index, left in enumerate(ids)
        for right in ids[index + 1:]
        if dc._overlaps(boxes[left], boxes[right])
    ]


#: Where the fixture parks everything the relations do not walk: far enough
#: apart that ``_collisions`` is empty by construction, and far enough from the
#: landing spots below that only the part a test names can be landed on.
def _parked(a1, r1, p1, p2, q1):
    return {
        "A1": a1, "R1": r1, "P1": p1, "P2": p2, "Q1": q1,
        "U1": (0.0, 400.0), "U2": (0.0, 800.0),
    }


# ==================================================== a blocked near trim


def test_a_near_trim_does_not_land_the_movable_part_on_a_neighbours_box():
    """``near(A1, R1)`` trimmed toward ``R1`` must not stop **on** ``P1``.

    Measured on the unfixed tree (the red-first reading this test was written
    against): ``A1`` -400 -> **-295**, and -295 is ``P1``'s own coordinate, so
    the two boxes are ``(-305, -5, -285, 5)`` apiece and overlap fully. That is
    the radar slice's exact failure one order of magnitude smaller
    (``near(C75, U63)``: -445 -> -380, inside ``C74``'s ``-393.5 .. -376.5``).
    ``A1`` and ``P1`` are both decoupling shunts of ``U1`` on ``VCC``, so this
    is the guarded shape. The pass must refuse the move instead: the drawable
    answer to "these two bodies collide" is the relation checker naming the
    relation, never a silently stacked drawing.
    """
    relation = RelativeConstraint(
        kind=NEAR, subject="A1", object="R1", reason="test: near trim")
    ctx = _context(relation)
    _assert_the_fixture_is_served(ctx)
    origins = _parked((-400.0, 0.0), (0.0, 0.0), (-295.0, 0.0),
                      (-900.0, 0.0), (900.0, 0.0))
    before = dict(origins)
    relation_reading = ("near", "A1", "R1")
    assert relation_reading in {
        (item.kind, item.subject, item.object)
        for item in dc._bound_orders(ctx, origins, POSES, None)
    }, "the relation is not broken before the pass, so this test measures nothing"

    moved = dc._order_step(ctx, relation, "A1", "R1", origins, POSES)

    boxes = _boxes(ctx, origins)
    assert not dc._overlaps(boxes["A1"], boxes["P1"]), (
        "the near trim landed the movable part on a neighbour's box: A1 at "
        f"{origins['A1']} spans {boxes['A1']}, P1 at {origins['P1']} spans "
        f"{boxes['P1']} — the pass slid a body onto a body it was never asked "
        "about"
    )
    assert moved is False, f"the walk reported a move it must not make: {origins}"
    assert origins == before, (
        f"a refused walk still moved something: {origins} vs {before}")
    assert relation_reading in {
        (item.kind, item.subject, item.object)
        for item in dc._bound_orders(ctx, origins, POSES, None)
    }, (
        "the blocked relation is no longer in the checker's list: it must be "
        "left for the relation checker to name, not dropped on the floor"
    )


# ==================================================== a blocked order walk


def test_a_left_of_walk_does_not_land_the_movable_part_on_a_neighbours_box():
    """``left-of(A1, R1)`` walked past ``R1`` must not stop **on** ``P1``.

    The 120 rule already keeps a walk one lattice step clear of the parts it can
    *see* on the target coordinate (``_contended_landing``), which is why the
    landing here is -105 rather than -5 — and why ``P1`` is put exactly there.
    That rule reads **origins**; a box is 20 units wide in this fixture, so a
    part can be clear by origin and covered by body. Measured on the unfixed
    tree: ``A1`` 100 -> **-105**, both boxes ``(-115, -5, -95, 5)``. ``A1`` and
    ``P1`` are same-host served shunts, so this landing is the guarded one.
    """
    relation = RelativeConstraint(
        kind=LEFT_OF, subject="A1", object="R1", reason="test: left-of walk")
    ctx = _context(relation)
    _assert_the_fixture_is_served(ctx)
    origins = _parked((100.0, 0.0), (0.0, 0.0), (-105.0, 0.0),
                      (-900.0, 0.0), (900.0, 0.0))
    before = dict(origins)
    assert ("left-of", "A1", "R1") in {
        (item.kind, item.subject, item.object)
        for item in dc._bound_orders(ctx, origins, POSES, None)
    }, "the relation is not broken before the pass, so this test measures nothing"

    moved = dc._order_step(ctx, relation, "A1", "R1", origins, POSES)

    boxes = _boxes(ctx, origins)
    assert not dc._overlaps(boxes["A1"], boxes["P1"]), (
        "the left-of walk landed the movable part on a neighbour's box: A1 at "
        f"{origins['A1']} spans {boxes['A1']}, P1 at {origins['P1']} spans "
        f"{boxes['P1']}"
    )
    assert moved is False, f"the walk reported a move it must not make: {origins}"
    assert origins == before, (
        f"a refused walk still moved something: {origins} vs {before}")


# ============================================ the legal moves are untouched


def test_a_walk_that_lands_on_nobody_moves_exactly_as_before():
    """The identity half: with nothing on the landing spot both kinds still walk.

    Pinned to the **coordinates**, not to a boolean: a guard that refuses too
    much would pass every test above and quietly stop consuming relations on
    every page (098/116 read this pass to satisfy ``near``/order relations, and
    :func:`_order_baseline` exists precisely so they can be consumed). These are
    the same two walks the blocked cases above reproduce, with ``P1`` moved out
    of the way — the numbers are what the pass wrote before the guard existed.
    """
    near = RelativeConstraint(
        kind=NEAR, subject="A1", object="R1", reason="test: near trim")
    ctx = _context(near)
    _assert_the_fixture_is_served(ctx)
    origins = _parked((-400.0, 0.0), (0.0, 0.0), (-900.0, 0.0),
                      (900.0, 0.0), (1800.0, 0.0))
    assert dc._order_step(ctx, near, "A1", "R1", origins, POSES) is True, (
        "a near trim with a free landing spot was refused — the guard is "
        "refusing more than a collision")
    assert origins["A1"] == (-295.0, 0.0), (
        f"the historical near trim moved to {origins['A1']} instead of -295")
    assert _collisions(ctx, origins) == [], (
        f"the historical near trim left a collision: {_collisions(ctx, origins)}")

    order = RelativeConstraint(
        kind=LEFT_OF, subject="A1", object="R1", reason="test: left-of walk")
    ctx = _context(order)
    _assert_the_fixture_is_served(ctx)
    origins = _parked((100.0, 0.0), (0.0, 0.0), (-900.0, 0.0),
                      (900.0, 0.0), (1800.0, 0.0))
    assert dc._order_step(ctx, order, "A1", "R1", origins, POSES) is True, (
        "a left-of walk with a free landing spot was refused")
    assert origins["A1"] == (-105.0, 0.0), (
        f"the historical left-of walk moved to {origins['A1']} instead of -105")
    assert _collisions(ctx, origins) == []


def test_an_existing_overlap_does_not_block_a_walk_that_keeps_it_smaller():
    """The guard asks "would this landing put me on somebody **new**".

    Read literally, "refuse a walk whose box overlaps another box" also refuses
    the walk that **leaves** an overlap the page already had, and a page whose
    parts are already stacked then keeps them stacked — worse than the defect,
    and it breaks the historical moves, which never asked to be collision-free
    (the pass repairs *relations*, and the collision is reported around it).

    Here ``A1`` starts 20 units inside its same-host sibling ``P1`` and the legal
    ``near`` trim moves it 15 units out of it: the landing still overlaps by 10,
    so a guard that reads "the arriving box overlaps somebody" refuses a move
    that makes the drawing **strictly better**. Only a landing that adds overlap
    is refused.
    """
    near = RelativeConstraint(
        kind=NEAR, subject="A1", object="R1", reason="test: near trim")
    ctx = _context(near)
    _assert_the_fixture_is_served(ctx)
    origins = _parked((-400.0, 0.0), (-90.0, 0.0), (-395.0, 0.0),
                      (-900.0, 0.0), (900.0, 0.0))
    boxes = _boxes(ctx, origins)
    assert dc._overlaps(boxes["A1"], boxes["P1"]), (
        "the fixture no longer starts from an overlap, so this test does not "
        "measure what it claims")

    moved = dc._order_step(ctx, near, "A1", "R1", origins, POSES)

    assert moved is True, (
        "the walk that shrinks a pre-existing overlap was refused: the guard is "
        "reading 'my arriving box overlaps somebody' instead of 'this landing "
        f"adds an overlap' — origins {origins}")
    after = _boxes(ctx, origins)
    assert dc._overlaps(after["A1"], after["P1"]), (
        f"the move was reported but the boxes no longer overlap: {after}")
    assert abs(origins["A1"][0] - (-385.0)) < 1e-9, (
        f"the walk wrote {origins['A1']} instead of the historical -385")


# ==================================== the guard is narrow, not wide


def test_a_landing_on_a_non_sibling_still_moves():
    """A body on the landing spot is only a defect when it is a served sibling.

    The wide reading ("do not land any body on any body") was measured on the
    flyback page and rewrote four parts that are not decoupling branches at all
    (``.tmp_us_radar_owner_recon/REPORT.md`` sec.3: 14 refusals, 4 parts moved,
    every pair ``same_owner=false``). The guard must stay the narrow one:

    * ``P2`` is a capacitor with **no host** (its live terminal sits on a signal,
      not a rail), so it is not a service owner's sibling;
    * ``Q1`` is a capacitor served by **another** core, ``U2``, so it is a
      sibling of a different owner, not of ``A1``.

    Both landings still have to move. Under the wide guard, or under a guard that
    forgot the ``host_id`` comparison, the first or the second case below turns
    red — which is exactly what makes this test the anti-wide-gate control.
    """
    near = RelativeConstraint(
        kind=NEAR, subject="A1", object="R1", reason="test: near trim")

    ctx = _context(near)
    _assert_the_fixture_is_served(ctx)
    origins = _parked((-400.0, 0.0), (0.0, 0.0), (-900.0, 0.0),
                      (-295.0, 0.0), (1800.0, 0.0))
    moved = dc._order_step(ctx, near, "A1", "R1", origins, POSES)
    assert moved is True and origins["A1"] == (-295.0, 0.0), (
        "the landing on the no-host capacitor P2 was refused — the guard is "
        f"reading a bare box collision: moved={moved}, origins={origins}")
    assert dc._overlaps(_boxes(ctx, origins)["A1"], _boxes(ctx, origins)["P2"]), (
        "the fixture no longer lands A1 on P2, so the no-host case is vacuous")

    ctx = _context(near)
    _assert_the_fixture_is_served(ctx)
    origins = _parked((-400.0, 0.0), (0.0, 0.0), (-900.0, 0.0),
                      (900.0, 0.0), (-295.0, 0.0))
    moved = dc._order_step(ctx, near, "A1", "R1", origins, POSES)
    assert moved is True and origins["A1"] == (-295.0, 0.0), (
        "the landing on Q1 was refused although Q1 is served by another core "
        f"(U2, not U1) — the guard forgot the host comparison: moved={moved}, "
        f"origins={origins}")
    assert dc._overlaps(_boxes(ctx, origins)["A1"], _boxes(ctx, origins)["Q1"]), (
        "the fixture no longer lands A1 on Q1, so the different-host case is "
        "vacuous")


# ======================= the one-pad fan-out the rescue round had no answer for


#: The radar slice's own shape, one order of magnitude down: six shunts of one
#: core, all hanging off **one** host pin, so the ladder's index staircase is the
#: only thing separating them — 60, 120, ... 360 along the escape axis, and
#: ``near_limit`` is 300. The measured refusal on the radar was exactly this:
#: ``near(C75, U63)`` — the host pad at ``(-85, 115)`` and the fourth shunt at
#: ``(-445, 115)``, 360 units out.
SHUNT_IDS = ("C72", "C73", "C74", "C75", "C76", "C77")

#: Short value rows on purpose: the rescue pass's own escape test charges the
#: **text** (`base + Σ(width + TEXT_GAP)`, 257 of the 300 available), so a
#: fixture with long rows would make the containing predicate — not the missing
#: one-pad reading — the reason nothing happens.
SHUNT_VALUES = {"C72": "100nF", "C73": "100nF", "C74": "1uF",
                "C75": "10uF", "C76": "22nF", "C77": "470nF"}

#: A two-terminal part standing **vertically**, served pad on top: the pose
#: ``ic-periphery`` accepts for a shunt hanging off a core pin that leaves
#: upward (``_accepted_poses`` reads the body direction through the profile).
SHUNT_PROFILE = {
    "kind": "boardwise-symbol-profile",
    "profileVersion": 1,
    "symbolRef": "C0402",
    "title": "C0402",
    "body": [-10.0, -10.0, 10.0, 10.0],
    "pins": [
        {"number": "1", "name": "1", "tip": [0.0, 10.0], "direction": "up",
         "directionSource": "body-box", "electricalRole": "", "roleSource": "",
         "pinType": "Undefined", "length": None},
        {"number": "2", "name": "2", "tip": [0.0, -10.0], "direction": "down",
         "directionSource": "body-box", "electricalRole": "", "roleSource": "",
         "pinType": "Undefined", "length": None},
    ],
    "poses": [{"rotation": 0, "mirror": False}],
    "poseSource": "declared",
    "valueRow": "",
    "texts": [],
    "pinTexts": {"offsets": {}, "pins": {}},
    "source": "inline:test",
    "notes": [],
}

#: The core the shunts hang off. Eight pins so the binder reads it as a core at
#: all (two stated pins is itself a peripheral, `_prepare` refuses it), pin 1 the
#: one pad every shunt shares.
SHUNT_CORE_PROFILE = {
    "kind": "boardwise-symbol-profile",
    "profileVersion": 1,
    "symbolRef": "CORE8",
    "title": "CORE8",
    "body": [-40.0, -40.0, 40.0, 40.0],
    "pins": [
        {"number": number, "name": number, "tip": tip, "direction": side,
         "directionSource": "body-box", "electricalRole": "", "roleSource": "",
         "pinType": "Undefined", "length": None}
        for number, tip, side in (
            ("1", [0.0, 60.0], "up"), ("2", [0.0, -60.0], "down"),
            ("3", [-60.0, 0.0], "left"), ("4", [60.0, 0.0], "right"),
            ("5", [-60.0, 20.0], "left"), ("6", [60.0, 20.0], "right"),
            ("7", [-60.0, -20.0], "left"), ("8", [60.0, -20.0], "right"),
        )
    ],
    "poses": [{"rotation": 0, "mirror": False}],
    "poseSource": "declared",
    "valueRow": "",
    "texts": [],
    "pinTexts": {"offsets": {}, "pins": {}},
    "source": "inline:test",
    "notes": [],
}


def _fan_out(identifiers):
    """``(context, circuit, presentation, book)`` for one core and its shunts.

    The presentation states the grammar at the **top level** (``grammarRef`` plus
    ``sidePreferences``), which is what makes ``ic-periphery`` bind ``C7x`` as
    ``kind="branch", role="shunt", owner="U1"`` and fill ``ctx.chain`` — the same
    production path 547A/548C's islands take. ``serviceLayout`` is deliberately
    absent: the radar slice's shunts go through the ordinary ladder, not 543B's
    fixed service interval (``_service_pin_gap`` answers ``None`` for them, which
    the tests below pin so the rescue can never be confused with that path).
    """
    identifiers = tuple(identifiers)
    circuit_payload = {
        "parts": [
            {"id": "U1", "symbolRef": "CORE8", "value": "U1",
             "provenance": "verified_recipe"},
            *({"id": part, "symbolRef": "C0402", "value": SHUNT_VALUES[part],
               "provenance": "verified_recipe"} for part in identifiers),
        ],
        "nets": [
            {"id": "VCC", "class": "power",
             "members": ["U1.1", *(f"{part}.1" for part in identifiers)],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "GND", "class": "gnd",
             "members": ["U1.2", "U1.3", "U1.4", "U1.5", "U1.6",
                         *(f"{part}.2" for part in identifiers)],
             "provenance": "verified_recipe", "scope": "page"},
        ],
    }
    presentation_payload = {
        "kind": "boardwise-presentation-spec",
        "specVersion": 1,
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right", "load": "right",
                            "source": "left", "power": "top", "gnd": "bottom"},
        "modules": [
            {"id": "m", "role": "host island", "grammarRef": "ic-periphery",
             "core": "U1", "parts": ["U1", *identifiers]},
        ],
    }
    circuit = CircuitSpec.from_dict(circuit_payload)
    presentation = PresentationSpec.from_dict(presentation_payload)
    book = {
        "C0402": SymbolProfile.from_dict(SHUNT_PROFILE),
        "CORE8": SymbolProfile.from_dict(SHUNT_CORE_PROFILE),
    }
    binding = dc.bind_grammar(circuit, presentation, book)
    assert binding.ok, binding.failures
    prepared = dc._prepare(circuit, presentation, binding, book,
                           dc.CompileBudget(max_candidates=8))
    assert prepared.context is not None, [f.detail for f in prepared.failures]
    return prepared.context, circuit, presentation, book


def _runged_layout(ctx, two_dimensional):
    """One ladder walk, with the rungs it handed the rescue pass recorded.

    The rungs are read through an **observation-only** wrapper around
    :func:`boardwise.engines.drawcompiler._seat_branch_stack`, the same way
    ``test_548c6_two_dimensional_seats`` records what the bay pass was given: the
    seat's own inputs are the production ladder's, never hand-built here.
    """
    seen: dict = {}
    original = dc._seat_branch_stack

    def record(context, origins, poses, boxes, rungs, residue):
        seen["rungs"] = dict(rungs)
        seen["before"] = dict(origins)
        seen["residue"] = residue
        return original(context, origins, poses, boxes, rungs, residue)

    dc._seat_branch_stack = record
    try:
        ctx.two_dimensional_seats = two_dimensional
        origins, poses, residue = dc._chain_and_shelf_layout(
            ctx, dc._variants(ctx)[0])
    finally:
        dc._seat_branch_stack = original
        ctx.two_dimensional_seats = False
    return dict(origins), dict(poses), residue, seen


def _posed_pins(ctx, poses, origins, part):
    """Every pin tip of ``part`` at ``origins[part]``, as absolute points."""
    profile = ctx.profile(part)
    origin = origins[part]
    return [
        (origin[0] + tip[0], origin[1] + tip[1])
        for tip in (
            dc._posed(pin.tip, poses[part], (0.0, 0.0)) for pin in profile.pins
        )
    ]


def test_a_one_pad_fan_out_past_near_is_seated_along_the_line():
    """The rescue round's own gap: a same-pad group was skipped outright.

    Measured on the tree this test was written against (the radar slice's shape):

    * the ladder hands ``C72..C77`` one rung each, 60 units apart, so the group
      reaches ``base + step*index = 360`` along the escape axis while
      ``near_limit`` is 300, and ``compile`` refuses with
      ``presentation-poor: near(C77, U1)`` — 0 candidates;
    * the rescue round runs (no candidate), and
      :func:`boardwise.engines.drawcompiler._seat_branch_stack` **skips the whole
      group** on ``spread <= BAY_SAME_PAD`` — every member hangs off one pad, so
      the line coordinate cannot order them and the pass had no second axis to
      offer. The page stays refused.

    What must hold after the gap is closed, and is pinned here:

    * the group is the one-pad touching shape and **not** a 543B service group
      (``_service_pin_gap`` is ``None`` for every member) — the rescue answers
      the ladder's silence, never a stated service interval;
    * every member is seated, every member's own pad stays inside
      ``near_limit`` of the host pin it hangs off (the pass's own ruler,
      ``hypot(root - anchor)``) and so does its origin (the ruler the gate's
      ``near`` uses);
    * no two members share an origin, no body overlaps another body, and no pin
      tip lands on another part's pin tip — the staircase is a set of rows, not
      a stack;
    * the relation the page was refused for is honoured in the seated layout:
      :func:`boardwise.engines.drawcompiler._bound_orders` comes back empty.
    """
    ctx, circuit, presentation, book = _fan_out(SHUNT_IDS)
    for part in SHUNT_IDS:
        slot = ctx.slots[part]
        assert (slot.kind, slot.role, slot.owner) == ("branch", "shunt", "U1"), (
            f"{part} is not a branch shunt of the core: {slot}")
        assert dc._service_pin_gap(ctx, slot) is None, (
            f"{part} carries a stated service interval, so this fixture is the "
            "543B path and not the one-pad ladder shape being pinned")

    ladder, ladder_poses, residue, _off = _runged_layout(ctx, False)
    seated, seated_poses, _seated_residue, seen = _runged_layout(ctx, True)
    rungs = seen["rungs"]
    assert seen["before"] == ladder, (
        "the two ladder walks disagree before the rescue pass runs")
    anchors = {rungs[part].anchor for part in SHUNT_IDS}
    assert len(anchors) == 1, (
        f"the fixture is not a one-pad fan-out: anchors {sorted(anchors)}")
    anchor = anchors.pop()
    line = (-rungs[SHUNT_IDS[0]].direction[1], rungs[SHUNT_IDS[0]].direction[0])
    spread = max(dc._dot(rungs[part].anchor, line) for part in SHUNT_IDS) - min(
        dc._dot(rungs[part].anchor, line) for part in SHUNT_IDS)
    assert spread <= dc.BAY_SAME_PAD, (
        f"the group's pads do not coincide along the line (spread {spread})")
    escape_need = max(rungs[part].base + rungs[part].step * rungs[part].index
                      for part in SHUNT_IDS)
    assert escape_need > ctx.budget.near_limit, (
        "the ladder's own staircase already fits inside near, so this fixture "
        f"does not measure the starved group: {escape_need}")
    assert ctx.budget.near_limit == dc.NEAR_LIMIT, (
        "this test is written against the shipped near budget")

    refused = dc.compile(circuit, presentation, book)
    assert not refused.ok and not refused.candidates, (
        "the island compiles on the unfixed tree, so the rescue round — the "
        "only round that runs this pass — is never entered and the fixture "
        "measures nothing")
    assert f"near(C{SHUNT_IDS[-1][1:]}, U1)" in refused.render_failures(), (
        "the refusal is not the near relation this test is about: "
        f"{refused.render_failures()[:400]}")

    moved = {part for part in SHUNT_IDS if seated[part] != ladder[part]}
    assert moved == set(SHUNT_IDS), (
        "the one-pad fan-out was not seated on its line axis — the rescue round "
        f"still has no answer for it: moved {sorted(moved)} of {list(SHUNT_IDS)}")

    boxes = {
        part: dc._part_box(ctx.profile(part), seated_poses[part], seated[part])
        for part in seated
    }
    assert len({seated[part] for part in SHUNT_IDS}) == len(SHUNT_IDS), (
        f"two members share an origin: {[seated[p] for p in SHUNT_IDS]}")
    for part in SHUNT_IDS:
        shared = dc._pin_local(ctx, part, ctx.slots[part].pin_shared, seated_poses)
        assert shared is not None
        root = (seated[part][0] + shared[0], seated[part][1] + shared[1])
        distance = math.hypot(root[0] - anchor[0], root[1] - anchor[1])
        assert distance <= ctx.budget.near_limit, (
            f"{part}'s own pad is {distance:.1f} from the host pin it hangs off, "
            f"past near_limit {ctx.budget.near_limit}: root {root}, anchor {anchor}")
        page = math.hypot(seated[part][0] - seated["U1"][0],
                          seated[part][1] - seated["U1"][1])
        assert page <= ctx.budget.near_limit, (
            f"{part} sits {page:.1f} from U1, past near_limit "
            f"{ctx.budget.near_limit}: {seated[part]}")
    for index, here in enumerate(SHUNT_IDS):
        for there in SHUNT_IDS[index + 1:]:
            assert not dc._overlaps(boxes[here], boxes[there]), (
                f"{here} and {there} overlap after the seat: "
                f"{boxes[here]} vs {boxes[there]}")
            assert not set(_posed_pins(ctx, seated_poses, seated, here)) & set(
                _posed_pins(ctx, seated_poses, seated, there)), (
                f"{here} and {there} land a pin tip on one another")
    readings = dc._bound_orders(ctx, seated, seated_poses, boxes)
    assert list(readings) == [], (
        "the seated layout still breaks a relation, so the rescue bought a row "
        f"with a broken one: {[(r.kind, r.subject, r.object) for r in readings]}")


def test_a_one_pad_fan_out_inside_near_keeps_the_ladder_staircase():
    """The control: a same-pad group the escape axis can hold is left alone.

    Five shunts on one pad reach ``lane + step*4 = 300``, which is exactly
    ``near_limit``: the ladder's staircase is an answer, so the rescue pass must
    not touch it (the power_entry_xt30 shape — ``D1``/``C115``/``C116`` in a row
    after the connector — and the reason this predicate was ever conservative).
    Pinned as coordinates, not as "no crash": the two-dimensional walk must hand
    back the ladder's own seats byte for byte.
    """
    ctx, _circuit, _presentation, _book = _fan_out(SHUNT_IDS[:5])
    for part in SHUNT_IDS[:5]:
        assert dc._service_pin_gap(ctx, ctx.slots[part]) is None, (
            f"{part} is a service shunt, so the group is not the ladder shape")

    ladder, ladder_poses, residue, _off = _runged_layout(ctx, False)
    seated, seated_poses, _seated_residue, seen = _runged_layout(ctx, True)
    rungs = seen["rungs"]
    assert seen["before"] == ladder, (
        "the two ladder walks disagree before the rescue pass runs")
    assert len({rungs[part].anchor for part in SHUNT_IDS[:5]}) == 1, (
        "the fixture is not a one-pad fan-out")
    escape_need = max(rungs[part].base + rungs[part].step * rungs[part].index
                      for part in SHUNT_IDS[:5])
    assert escape_need <= ctx.budget.near_limit, (
        f"the ladder staircase already passes near ({escape_need}), so the "
        "control does not measure the guarded shape")

    assert seated == ladder, (
        "the rescue pass moved a one-pad group the ladder already draws: "
        f"{sorted(p for p in seated if seated[p] != ladder[p])}")
    boxes = {
        part: dc._part_box(ctx.profile(part), ladder_poses[part], ladder[part])
        for part in ladder
    }
    assert list(dc._bound_orders(ctx, ladder, ladder_poses, boxes)) == [], (
        "the ladder's own seats break a relation, so keeping them is not legal")


# ================= the declared pair inside a group may not veto its siblings
#
# The US-radar slice's measured shape (548E, ``U63``): eleven siblings hang off
# one owner, and the only relation the grammar states **between two of them** is
# ``adjacent(Y61, C69)`` — the crystal and its load, emitted by the 098 cluster.
# `_share_one_bay` asked that question for the whole group, so one stated pair
# sent all eleven back to the ladder's staircase, including the five decoupling
# shunts that are the reason the page has no candidate at all. The fixture below
# is that shape one order of magnitude down and self-contained: a core with six
# distinct pads, a crystal across two of them with its two loads, and three
# ordinary shunts — six siblings, one declared pair (``adjacent(Y1, C5)``).

CLUSTER_IDS = ("Y1", "C5", "C6", "C1", "C2", "C3")

#: Six pads on the core's left edge, 30 units apart, so the group's pads span
#: 150 — more than one ``lane`` (60), which is what puts it in the bay pass's
#: hands rather than the rescue round's (``_share_one_bay``'s ``spread < lane``
#: guard, unchanged).
CLUSTER_CORE_PROFILE = {
    "kind": "boardwise-symbol-profile",
    "profileVersion": 1,
    "symbolRef": "CORE8",
    "title": "CORE8",
    "body": [-40.0, -40.0, 40.0, 40.0],
    "pins": [
        *({"number": number, "name": number, "tip": tip, "direction": "left",
           "directionSource": "body-box", "electricalRole": "", "roleSource": "",
           "pinType": "Undefined", "length": None}
          for number, tip in (
              ("1", [-60.0, 60.0]), ("2", [-60.0, 30.0]), ("3", [-60.0, 0.0]),
              ("4", [-60.0, -30.0]), ("5", [-60.0, -60.0]),
              ("6", [-60.0, -90.0]))),
        {"number": "7", "name": "7", "tip": [0.0, 60.0], "direction": "up",
         "directionSource": "body-box", "electricalRole": "", "roleSource": "",
         "pinType": "Undefined", "length": None},
        {"number": "8", "name": "8", "tip": [0.0, -60.0], "direction": "down",
         "directionSource": "body-box", "electricalRole": "", "roleSource": "",
         "pinType": "Undefined", "length": None},
    ],
    "poses": [{"rotation": 0, "mirror": False}],
    "poseSource": "declared",
    "valueRow": "",
    "texts": [],
    "pinTexts": {"offsets": {}, "pins": {}},
    "source": "inline:test",
    "notes": [],
}

#: A two-terminal crystal lying horizontally, with the four poses the seat is
#: allowed to choose from (the drawing picks the one that puts its feet where the
#: nets are; a single declared pose is refused as ``layout-unsat``, measured).
CRYSTAL_PROFILE = {
    "kind": "boardwise-symbol-profile",
    "profileVersion": 1,
    "symbolRef": "Y0402",
    "title": "Y0402",
    "body": [-10.0, -7.5, 10.0, 7.5],
    "pins": [
        {"number": "1", "name": "1", "tip": [-10.0, 0.0], "direction": "left",
         "directionSource": "body-box", "electricalRole": "", "roleSource": "",
         "pinType": "Undefined", "length": None},
        {"number": "2", "name": "2", "tip": [10.0, 0.0], "direction": "right",
         "directionSource": "body-box", "electricalRole": "", "roleSource": "",
         "pinType": "Undefined", "length": None},
    ],
    "poses": [{"rotation": rotation, "mirror": False}
              for rotation in (0, 90, 180, 270)],
    "poseSource": "declared",
    "valueRow": "",
    "texts": [],
    "pinTexts": {"offsets": {}, "pins": {}},
    "source": "inline:test",
    "notes": [],
}


def _cluster_documents():
    """``(circuit, presentation, book)``: the six-sibling group and its pair.

    The declared pair is the **grammar's**, not this file's: ``ic-periphery`` emits
    ``adjacent(Y1, C5)`` for a bridge and the load on the net it anchors on (the
    098 cluster, ``grammar/ic_periphery.py``), which is exactly how the radar
    slice gets ``adjacent(Y61, C69)``. Adding a ``RelativeConstraint`` by hand
    would not survive the compile — :func:`boardwise.engines.drawcompiler.compile`
    binds the grammar from the documents again — so the fixture states the
    circuit the cluster is read off instead.
    """
    circuit = CircuitSpec.from_dict({
        "parts": [
            {"id": "U1", "symbolRef": "CORE8", "value": "U1",
             "provenance": "verified_recipe"},
            {"id": "Y1", "symbolRef": "Y0402", "value": "12MHz",
             "provenance": "verified_recipe"},
            *({"id": part, "symbolRef": "C0402", "value": "100nF",
               "provenance": "verified_recipe"}
              for part in ("C5", "C6", "C1", "C2", "C3")),
        ],
        "nets": [
            {"id": "OSC_IN", "class": "signal",
             "members": ["U1.1", "Y1.1", "C5.1"],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "OSC_OUT", "class": "signal",
             "members": ["U1.2", "Y1.2", "C6.1"],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "VCC", "class": "power", "members": ["U1.3", "C1.1"],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "N4", "class": "signal", "members": ["U1.4", "C2.1"],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "N5", "class": "signal", "members": ["U1.5", "C3.1"],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "GND", "class": "gnd",
             "members": ["U1.8", *(f"{part}.2" for part in
                                    ("C5", "C6", "C1", "C2", "C3"))],
             "provenance": "verified_recipe", "scope": "project"},
        ],
    })
    presentation = PresentationSpec.from_dict({
        "kind": "boardwise-presentation-spec",
        "specVersion": 1,
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right", "load": "right",
                            "source": "left", "power": "top", "gnd": "bottom"},
        "modules": [
            {"id": "m", "role": "host island", "grammarRef": "ic-periphery",
             "core": "U1", "parts": ["U1", *CLUSTER_IDS]},
        ],
    })
    book = {
        "C0402": SymbolProfile.from_dict(SHUNT_PROFILE),
        "Y0402": SymbolProfile.from_dict(CRYSTAL_PROFILE),
        "CORE8": SymbolProfile.from_dict(CLUSTER_CORE_PROFILE),
    }
    return circuit, presentation, book


def _cluster_layout(circuit, presentation, book, two_dimensional=False):
    """The production seat, with what the bay pass was handed recorded.

    Read through an **observation-only** wrapper around ``_share_one_bay`` — the
    same way :func:`_runged_layout` records the rescue pass's inputs — so the
    rungs, the group, the units and the pre-seat origins are the production
    ladder's, never hand-built here. ``two_dimensional`` walks the **rescue**
    round's variant (the one :func:`boardwise.engines.drawcompiler.compile`
    reaches after the constructive variants refuse), which is the walk that owns
    a mixed group's same-pad fan-out; it defaults to the constructive walk so the
    548E test above keeps measuring exactly what it always did.
    """
    binding = dc.bind_grammar(circuit, presentation, book)
    assert binding.ok, binding.failures
    prepared = dc._prepare(circuit, presentation, binding, book,
                           dc.CompileBudget(max_candidates=8))
    assert prepared.context is not None, [f.detail for f in prepared.failures]
    ctx = prepared.context
    seen: dict = {}
    original = dc._share_one_bay

    def record(context, origins, poses, boxes, rungs, residue):
        groups: dict = {}
        for part_id in sorted(rungs):
            rung = rungs[part_id]
            groups.setdefault((rung.owner, rung.direction), []).append(part_id)
        for _key, members in sorted(groups.items()):
            if len(members) < 2:
                continue
            seen["group"] = list(members)
            seen["units"] = dc._declared_units(context, members, rungs)
            seen["rungs"] = {part: rungs[part] for part in members}
            seen["before"] = {part: origins[part] for part in members}
        return original(context, origins, poses, boxes, rungs, residue)

    dc._share_one_bay = record
    try:
        ctx.two_dimensional_seats = two_dimensional
        origins, poses, residue = dc._chain_and_shelf_layout(
            ctx, dc._variants(ctx)[0])
    finally:
        dc._share_one_bay = original
        ctx.two_dimensional_seats = False
    return ctx, dict(origins), dict(poses), seen


def _cluster_violations(ctx, origins, poses):
    """Every relation the placement breaks, read by the compiler's own ruler.

    The same call, the same lambdas and the same ``_relation_violations`` that
    :func:`boardwise.engines.drawcompiler._bound_orders` makes, but without that
    function's kind filter — an ``adjacent`` is another subsystem's to act on,
    which is why the pass ignores it, but it is still a relation the gate reads
    and this test must not skip.
    """
    return {
        (item.kind, item.subject, item.object)
        for item, _points in dc._relation_violations(
            ctx.circuit, ctx.binding,
            origin_of=lambda part_id: origins.get(part_id),
            pin_of=lambda part_id, token: dc._pin_point(
                ctx, part_id, token, poses, origins),
            grid=ctx.budget.grid, near_limit=ctx.budget.near_limit,
            lateral=ctx.lateral(), progress=ctx.progress,
            escape_of=lambda part_id, token: dc._pin_direction(
                ctx, part_id, token, poses),
            frame_of=lambda part_id, token: dc._pin_escape(
                ctx.profile(part_id), token, dc.SymbolPose(0.0, False)),
            pair_reading=dc._pair_bands(ctx),
        )
    }


def test_a_declared_pair_in_a_group_does_not_veto_the_other_siblings():
    """One stated pair must not send the whole group back to the staircase.

    Measured on the unfixed tree (the red-first reading this test was written
    against, reproduced by mutating the fix back to the whole-group veto): the
    group's ladder is ``base + step*index``, so ``C5`` is seated 360 units out
    from the pad it hangs off — past ``near_limit`` 300 — and because the blend
    of the group holds ``adjacent(Y1, C5)``, ``_declared_among`` answered *true
    for the group* and ``_share_one_bay`` skipped all six: ``dc.compile``
    answered 0 candidates and ``compile_page`` 0 pages, the relation named
    ``near(C5, U1)``.

    What must hold after the fix, and is pinned here:

    * the declared pair is a **rigid unit**: ``Y1`` and ``C5`` keep the exact
      offset the ladder gave them (``(-130, 0)``), while the four unrelated
      siblings are bay'd on their own — a group half-ordered by the grammar is
      not a group the grammar ordered;
    * the whole group is seated (every member moved), each member's own pad stays
      inside ``near_limit`` of the host pin it hangs off and its pin tip stays on
      that pin's row, so the leg from the pad is one straight run;
    * no two members share an origin and no body overlaps another body;
    * the production preparation really produces a candidate: ``dc.compile`` and
      ``compile_page`` both come back with one, and the compiler's own ruler finds
      no broken relation in the seated layout.
    """
    circuit, presentation, book = _cluster_documents()
    declared = {
        (item.kind, item.subject, item.object)
        for item in dc.bind_grammar(circuit, presentation, book).constraints
    }
    assert ("adjacent", "Y1", "C5") in declared, (
        "the fixture no longer carries the grammar's own declared pair, so the "
        f"whole-group reading is never reached: {sorted(declared)}")

    ctx, seated, seated_poses, seen = _cluster_layout(circuit, presentation, book)
    members = seen["group"]
    assert sorted(members) == sorted(CLUSTER_IDS), (
        f"the fixture is not one sibling group: {members}")
    units = seen["units"]
    assert sorted(len(unit) for unit in units) == [1, 1, 1, 1, 2], (
        "the declared pair was not read as one component among singletons: "
        f"{units}")
    pair = next(unit for unit in units if len(unit) == 2)
    assert set(pair) == {"Y1", "C5"}, f"the rigid unit is not the declared pair: {pair}"

    ladder = {
        part: seen["rungs"][part].base + seen["rungs"][part].step * seen["rungs"][part].index
        for part in members
    }
    assert max(ladder.values()) > ctx.budget.near_limit, (
        "the group's ladder already fits inside near, so this fixture does not "
        f"measure the starved group: {ladder}")
    # Every member is measured from **its own pad** along its own escape
    # direction. The group's reach is what the refusal was about: left on the
    # staircase it spends ``base + step*index`` and the outermost member is past
    # ``near_limit``; bayed, no member spends the last rung at all. The one band
    # (plus, for the declared pair, the offset the ladder gave it) is the reading
    # asserted below.
    escapes = {}
    for part in members:
        rung = seen["rungs"][part]
        shared = dc._pin_local(ctx, part, ctx.slots[part].pin_shared, seated_poses)
        assert shared is not None, f"{part} has no shared pin to measure"
        root = (seated[part][0] + shared[0], seated[part][1] + shared[1])
        escapes[part] = dc._dot(
            (root[0] - rung.anchor[0], root[1] - rung.anchor[1]), rung.direction)
        assert escapes[part] <= ctx.budget.near_limit, (
            f"{part} sits {escapes[part]:.1f} out from its own pad, past "
            f"near_limit {ctx.budget.near_limit}")
    outermost = max(ladder, key=lambda part: ladder[part])
    assert max(escapes.values()) <= ladder[outermost] - seen["rungs"][outermost].step, (
        "the group still spends the staircase's outermost rung "
        f"({max(escapes.values()):.1f} of {ladder[outermost]:.1f}): it was left "
        "on the ladder")

    for index, here in enumerate(members):
        for there in members[index + 1:]:
            assert seated[here] != seated[there], (
                f"{here} and {there} share one origin: {seated[here]}")
    boxes = {
        part: dc._part_box(ctx.profile(part), seated_poses[part], seated[part])
        for part in seated
    }
    for index, here in enumerate(members):
        for there in members[index + 1:]:
            assert not dc._overlaps(boxes[here], boxes[there]), (
                f"{here} and {there} overlap after the seat: "
                f"{boxes[here]} vs {boxes[there]}")

    # the pair's own distance is the ladder's, to the unit: translation only
    for part in pair:
        delta = (
            seated[part][0] - seen["before"][part][0],
            seated[part][1] - seen["before"][part][1],
        )
        first = (
            seated[pair[0]][0] - seen["before"][pair[0]][0],
            seated[pair[0]][1] - seen["before"][pair[0]][1],
        )
        assert delta == first, (
            f"{part} moved by {delta} while its declared partner moved by "
            f"{first}: the pair was not seated as one rigid body")
    before_gap = (
        seen["before"]["C5"][0] - seen["before"]["Y1"][0],
        seen["before"]["C5"][1] - seen["before"]["Y1"][1],
    )
    after_gap = (
        seated["C5"][0] - seated["Y1"][0],
        seated["C5"][1] - seated["Y1"][1],
    )
    assert after_gap == before_gap, (
        "the declared pair's own offset changed at the seat, so the relation the "
        f"grammar stated is not the one drawn: {before_gap} -> {after_gap}")

    for part in members:
        rung = seen["rungs"][part]
        shared = dc._pin_local(ctx, part, ctx.slots[part].pin_shared, seated_poses)
        assert shared is not None, f"{part} has no shared pin to measure"
        root = (seated[part][0] + shared[0], seated[part][1] + shared[1])
        distance = math.hypot(root[0] - rung.anchor[0], root[1] - rung.anchor[1])
        assert distance <= ctx.budget.near_limit, (
            f"{part}'s own pad is {distance:.1f} from the host pin it hangs off, "
            f"past near_limit {ctx.budget.near_limit}: root {root}")
        across = root[0] * (-rung.direction[1]) + root[1] * rung.direction[0]
        anchor_across = (
            rung.anchor[0] * (-rung.direction[1]) + rung.anchor[1] * rung.direction[0]
        )
        assert abs(across - anchor_across) <= ctx.budget.grid / 2.0, (
            f"{part}'s pin tip is off its own pad's row ({across} vs "
            f"{anchor_across}), so the run from the pad is not one straight leg")

    assert dc._stack_is_clear(ctx, seated_poses, seated, set(members)), (
        "a seated member has no free side left for its value row — the seat is "
        "not readable")

    violations = _cluster_violations(ctx, seated, seated_poses)
    assert not violations, (
        "the seated layout breaks a relation the gate reads: "
        f"{sorted(violations)}")

    compiled = dc.compile(circuit, presentation, book)
    assert compiled.ok and compiled.candidates, (
        "the production preparation refuses the group the seat just answered: "
        f"{[(f.category, f.subject) for f in compiled.failures]}")
    page = pc.compile_page(circuit, presentation, book,
                           cli._draw_page_budget((0.0, 0.0, 1170.0, 825.0)))
    assert page.pages and not page.failures, (
        "the page compiler refuses the module the slice compiles: "
        f"{[(f.category, f.subject) for f in page.failures]}")


# ========= a same-pad five inside a declared-pair group (548F, the radar shape)
#
# The radar slice's *real* group is both shapes at once: eleven siblings of U63,
# the stated pair ``adjacent(Y61, C69)``, and the five decoupling shunts
# ``C72..C76`` on **one** pad. The 548E test above pins the declared unit; the
# one-pad tests above pin the same-pad seat; neither has a page that must carry
# both. This fixture is that mixed group and it is the red-first record of the
# 548F reading: on the shipped tree it has **no** candidate and the refusal is
# ``near(C9, U1)`` — the bay's outward pile hands the middle of the five
# ``(-420, 0)`` against ``near_limit`` 300, exactly the radar's ``near(C75)``
# reading one order of magnitude down.
#
# Flag geometry is part of the fixture, not a relaxed gate: the real rail/ground
# glyphs (534's measured 10-high pennant, 143C's 19-high ground) are carried by
# the library, and the rail is stated on the core's **quiet top pad** (``U1.7``)
# with the ground on its bottom pad, so the verified glyphs stand clear of the
# same-pad fan-out's trunk. That is what a readable sheet does; a flag glyph on
# the trunk is a fixture defect (it measures as ``wire-through-body``), and the
# readability gate is never widened to accept it.

MIXED_FIVE = ("C7", "C8", "C9", "C10", "C11")

#: 534's measured rail pennant: 5-unit lead, 10-high body, hung off the pad.
MIXED_RAIL_PROFILE = {
    "kind": "boardwise-symbol-profile",
    "profileVersion": 1,
    "symbolRef": "PWR-VCC",
    "title": "Power-VCC (534-measured rail pennant)",
    "body": [-5.0, 0.0, 5.0, 10.0],
    "pins": [],
    "texts": [],
    "source": "inline:test flag glyph",
    "notes": ["rail flag"],
}

#: The ground family's 19-high bars, same convention (no printed name row).
MIXED_GND_PROFILE = {
    "kind": "boardwise-symbol-profile",
    "profileVersion": 1,
    "symbolRef": "PWR-GND",
    "title": "Power-GND (measured ground bars)",
    "body": [-10.0, 0.0, 10.0, 19.0],
    "pins": [],
    "texts": [],
    "source": "inline:test flag glyph",
    "notes": ["ground flag"],
}


def _mixed_documents():
    """``(circuit, presentation, book)``: the radar's mixed sibling group.

    One core, six sibling pads: ``U1.1``/``U1.2`` carry the crystal and its two
    loads (so ``ic-periphery`` states ``adjacent(Y1, C5)``, the radar's
    ``adjacent(Y61, C69)``), ``U1.3`` is the **one** pad the five shunts share,
    ``U1.7``/``U1.8`` are the quiet pads the rail and ground flags hang from, and
    ``C12`` is the rail's own decoupling load. The five shunts sit on a signal
    net on purpose: the same pad is what makes them a fan-out, and putting the
    rail flag on that pad would hand the drawn trunk a glyph to cross — a
    fixture defect, not a drawing the gate should accept.
    """
    circuit = CircuitSpec.from_dict({
        "parts": [
            {"id": "U1", "symbolRef": "CORE8", "value": "U1",
             "provenance": "verified_recipe"},
            {"id": "Y1", "symbolRef": "Y0402", "value": "12MHz",
             "provenance": "verified_recipe"},
            *({"id": part, "symbolRef": "C0402", "value": "100nF",
               "provenance": "verified_recipe"}
              for part in ("C5", "C6", "C12", *MIXED_FIVE, "C13")),
        ],
        "nets": [
            {"id": "OSC_IN", "class": "signal",
             "members": ["U1.1", "Y1.1", "C5.1"],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "OSC_OUT", "class": "signal",
             "members": ["U1.2", "Y1.2", "C6.1"],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "DEC", "class": "signal",
             "members": ["U1.3", *(f"{part}.1" for part in MIXED_FIVE)],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "DEC2", "class": "signal",
             "members": ["U1.4", "C13.1"],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "VCC", "class": "power", "members": ["U1.7", "C12.1"],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "GND", "class": "gnd",
             "members": ["U1.8", "C12.2",
                         *(f"{part}.2" for part in ("C5", "C6", "C13", *MIXED_FIVE))],
             "provenance": "verified_recipe", "scope": "page"},
        ],
    })
    presentation = PresentationSpec.from_dict({
        "kind": "boardwise-presentation-spec",
        "specVersion": 1,
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right", "load": "right",
                            "source": "left", "power": "top", "gnd": "bottom"},
        "modules": [
            {"id": "m", "role": "host island", "grammarRef": "ic-periphery",
             "core": "U1",
             "parts": ["U1", "Y1", "C5", "C6", "C12", *MIXED_FIVE, "C13"]},
        ],
    })
    book = {
        "C0402": SymbolProfile.from_dict(SHUNT_PROFILE),
        "Y0402": SymbolProfile.from_dict(CRYSTAL_PROFILE),
        "CORE8": SymbolProfile.from_dict(CLUSTER_CORE_PROFILE),
        "PWR-VCC": SymbolProfile.from_dict(MIXED_RAIL_PROFILE),
        "PWR-GND": SymbolProfile.from_dict(MIXED_GND_PROFILE),
    }
    return circuit, presentation, book


def test_a_same_pad_five_inside_a_declared_pair_group_still_compiles():
    """The mixed group: one stated pair **and** five shunts on one pad.

    Measured on the tree this test was written against (the red-first reading,
    reproduced by restoring ``drawcompiler`` to its pre-548F hash): the bay sees
    one group of nine siblings; the declared pair is one rigid unit, the five
    same-pad shunts are singletons whose pads coincide, so the one-band loop
    piles them outward and ``dc.compile`` answers 0 candidates with
    ``presentation-poor: near(C9, U1)`` — ``C9`` at ``(-420, 0)`` against the
    ``near_limit`` 300 (``compile_page``: 0 pages, the same refusal).

    What must hold after the fix, pinned here:

    * the fixture really is both shapes — ``adjacent(Y1, C5)`` in the grammar's
      own binding, the five shunts ``branch/shunt/owner=U1`` sharing one pad;
    * the production seat moves the five onto the line: every member's own pad
      comes back inside ``near_limit`` of the host pin it hangs off, no two
      members share an origin, no bodies overlap, the declared pair keeps the
      ladder's exact offset, and the compiler's own ruler finds no broken
      relation;
    * the verified rail/ground glyphs are carried by the library and the seat is
      clear of them (no ``wire-through-body``): the candidate the gate accepts
      is the proof, not a hand-built plan;
    * ``dc.compile`` and ``compile_page`` both answer: one candidate, one page,
      no failures — the page the radar slice is refused for.
    """
    circuit, presentation, book = _mixed_documents()
    declared = {
        (item.kind, item.subject, item.object)
        for item in dc.bind_grammar(circuit, presentation, book).constraints
    }
    assert ("adjacent", "Y1", "C5") in declared, (
        "the fixture no longer carries the grammar's declared pair, so this is "
        f"not the mixed group: {sorted(declared)}")
    for part in MIXED_FIVE:
        assert f"near({part}, U1)" in {
            f"near({item.subject}, {item.object})" for item in
            dc.bind_grammar(circuit, presentation, book).constraints
            if item.kind == "near"
        }, f"{part} carries no near relation, so the pile is not priced"

    ctx, seated, seated_poses, seen = _cluster_layout(circuit, presentation, book, two_dimensional=True)
    members = seen["group"]
    assert sorted(members) == sorted(("Y1", "C5", "C6", "C13", *MIXED_FIVE)), (
        f"the fixture is not one sibling group: {members}")
    for part in MIXED_FIVE:
        slot = ctx.slots[part]
        assert (slot.kind, slot.role, slot.owner) == ("branch", "shunt", "U1"), (
            f"{part} is not a branch shunt of the core: {slot}")
        assert dc._service_pin_gap(ctx, slot) is None, (
            f"{part} carries a stated service interval, so the group is not the "
            "ordinary ladder shape")
    units = seen["units"]
    assert sorted(len(unit) for unit in units) == [1, 1, 1, 1, 1, 1, 1, 2], (
        "the mixed group was not read as one declared pair plus singletons: "
        f"{units}")
    pair = next(unit for unit in units if len(unit) == 2)
    assert set(pair) == {"Y1", "C5"}, f"the rigid unit is not the declared pair: {pair}"
    anchors = {seen["rungs"][part].anchor for part in MIXED_FIVE}
    assert len(anchors) == 1, (
        f"the five shunts do not share one pad: {sorted(anchors)}")

    ladder = {
        part: seen["rungs"][part].base + seen["rungs"][part].step * seen["rungs"][part].index
        for part in members
    }
    assert max(ladder.values()) > ctx.budget.near_limit, (
        "the ladder already fits inside near, so the fixture does not measure "
        f"the starved group: {ladder}")

    for part in members:
        rung = seen["rungs"][part]
        shared = dc._pin_local(ctx, part, ctx.slots[part].pin_shared, seated_poses)
        assert shared is not None, f"{part} has no shared pin to measure"
        root = (seated[part][0] + shared[0], seated[part][1] + shared[1])
        distance = math.hypot(root[0] - rung.anchor[0], root[1] - rung.anchor[1])
        assert distance <= ctx.budget.near_limit, (
            f"{part}'s own pad is {distance:.1f} from the host pin it hangs off, "
            f"past near_limit {ctx.budget.near_limit}: root {root}")

    boxes = {
        part: dc._part_box(ctx.profile(part), seated_poses[part], seated[part])
        for part in seated
    }
    for index, here in enumerate(members):
        for there in members[index + 1:]:
            assert seated[here] != seated[there], (
                f"{here} and {there} share one origin: {seated[here]}")
            assert not dc._overlaps(boxes[here], boxes[there]), (
                f"{here} and {there} overlap after the seat: "
                f"{boxes[here]} vs {boxes[there]}")
    for part in pair:
        delta = (seated[part][0] - seen["before"][part][0],
                 seated[part][1] - seen["before"][part][1])
        first = (seated[pair[0]][0] - seen["before"][pair[0]][0],
                 seated[pair[0]][1] - seen["before"][pair[0]][1])
        assert delta == first, (
            f"{part} moved by {delta} while its declared partner moved by "
            f"{first}: the pair was not seated as one rigid body")

    violations = _cluster_violations(ctx, seated, seated_poses)
    assert not violations, (
        "the seated mixed group breaks a relation the gate reads: "
        f"{sorted(violations)}")

    compiled = dc.compile(circuit, presentation, book)
    assert compiled.ok and compiled.candidates, (
        "the production preparation refuses the mixed group the seat answered: "
        f"{[(f.category, f.subject) for f in compiled.failures]}")
    page = pc.compile_page(circuit, presentation, book,
                           cli._draw_page_budget((0.0, 0.0, 1170.0, 825.0)))
    assert page.pages and not page.failures, (
        "the page compiler refuses the module the slice compiles: "
        f"{[(f.category, f.subject) for f in page.failures]}")



# ========= one line block and the sibling band it may not sit on (548H, E shape)
#
# The radar slice's last refusal is *joint*: the six decoupling shunts on U63's
# one pad must take six rows on the line axis, while the rest of the same
# sibling group is bayed at its own one-rung band. Measured on the clean tree
# (D43027B5): the rows are proposed at the group's mean line coordinate, land
# on a sibling's ladder box, and `_stack_is_clear` refuses; the rolled-back
# ACE7D74C prototype (propose without a line side) instead makes the bay push
# the remaining units out one after another (pair band 320, C70 230) and the
# page is refused on `near`. Neither half alone answers it.
#
# This fixture is that shape one order of magnitude down: six shunts on one pad
# (``C7..C12``), five distinct-pad siblings whose one-rung bay band sits
# *inside* the centred block's line span, and the grammar's declared pair on a
# third pad. The ladder already hands the six rungs past ``near`` (the six-pad
# one-pad test above is the same reading), so the rescue round runs.
#
# What the seat must do (pinned below): choose a **line side** for the block
# that clears the band the bay is about to give the siblings, so the bay never
# has to push a unit past ``near``; then the same pass, with its overlap and
# text guards on, accepts the rows against the seats the bay really took. A
# proposal is not a seat and no old or new coordinate is exempt.

E_SHUNTS = ("C7", "C8", "C9", "C10", "C11", "C12")
E_SIBLINGS = ("C13", "C6", "C14", "C15", "C16")

E_VALUES = {
    "C7": "100nF", "C8": "100nF", "C9": "1uF", "C10": "10uF",
    "C11": "22nF", "C12": "470nF",
    "C13": "100nF", "C6": "100nF", "C14": "1uF", "C15": "10uF",
    "C16": "22nF", "C5": "100nF",
}

#: Seven left pads 10 units apart (the six shunts' one pad plus five sibling
#: pads), a crystal pad pair above them, and the rail/ground pads. 10 < one
#: ``lane`` (60) is what keeps the pads' span under a lane while still being
#: five distinct pads (``_share_one_bay``'s ``spread < lane`` arm).
E_CORE_PROFILE = {
    "kind": "boardwise-symbol-profile",
    "profileVersion": 1,
    "symbolRef": "CORE8",
    "title": "CORE8 (548H left-pad band)",
    "body": [-40.0, -40.0, 40.0, 40.0],
    "pins": [
        *({"number": number, "name": number, "tip": tip, "direction": "left",
           "directionSource": "body-box", "electricalRole": "", "roleSource": "",
           "pinType": "Undefined", "length": None}
          for number, tip in (
              ("1", [-60.0, 60.0]), ("2", [-60.0, 30.0]),
              ("3", [-60.0, 20.0]), ("4", [-60.0, 10.0]),
              ("5", [-60.0, 0.0]), ("6", [-60.0, -10.0]),
              ("7", [-60.0, -20.0]), ("8", [-60.0, -30.0]))),
        {"number": "9", "name": "9", "tip": [0.0, 60.0], "direction": "up",
         "directionSource": "body-box", "electricalRole": "", "roleSource": "",
         "pinType": "Undefined", "length": None},
        {"number": "10", "name": "10", "tip": [0.0, -60.0], "direction": "down",
         "directionSource": "body-box", "electricalRole": "", "roleSource": "",
         "pinType": "Undefined", "length": None},
    ],
    "poses": [{"rotation": 0, "mirror": False}],
    "poseSource": "declared",
    "valueRow": "",
    "texts": [],
    "pinTexts": {"offsets": {}, "pins": {}},
    "source": "inline:test",
    "notes": [],
}


def _joint_documents():
    """``(circuit, presentation, book)``: six on one pad, five on their own.

    The declared pair is the grammar's own: ``ic-periphery`` emits
    ``adjacent(Y1, C5)`` for the crystal and the load on the net it anchors on,
    the radar's ``adjacent(Y61, C69)`` shape. The five siblings sit on five
    distinct pads **inside one lane** of the six's pad, so the bay reads them as
    one band and the block's centred line span covers every one of them.
    """
    circuit = CircuitSpec.from_dict({
        "parts": [
            {"id": "U1", "symbolRef": "CORE8", "value": "U1",
             "provenance": "verified_recipe"},
            {"id": "Y1", "symbolRef": "Y0402", "value": "12MHz",
             "provenance": "verified_recipe"},
            *({"id": part, "symbolRef": "C0402", "value": E_VALUES[part],
               "provenance": "verified_recipe"}
              for part in ("C5", *E_SHUNTS, *E_SIBLINGS)),
        ],
        "nets": [
            {"id": "OSC_IN", "class": "signal",
             "members": ["U1.1", "Y1.1", "C5.1"],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "OSC_OUT", "class": "signal",
             "members": ["U1.2", "Y1.2", "C6.1"],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "DEC", "class": "signal",
             "members": ["U1.5", *(f"{part}.1" for part in E_SHUNTS)],
             "provenance": "verified_recipe", "scope": "page"},
            *({"id": f"SB{index}", "class": "signal",
               "members": [f"U1.{pin}", f"{part}.1"],
               "provenance": "verified_recipe", "scope": "page"}
              for index, (pin, part) in enumerate(
                  (("3", "C13"), ("4", "C14"), ("6", "C15"), ("7", "C16")))),
            {"id": "VCC", "class": "power", "members": ["U1.9"],
             "provenance": "verified_recipe", "scope": "page"},
            {"id": "GND", "class": "gnd",
             "members": ["U1.10", *(f"{part}.2" for part in
                                    ("C5", *E_SHUNTS, *E_SIBLINGS))],
             "provenance": "verified_recipe", "scope": "project"},
        ],
    })
    presentation = PresentationSpec.from_dict({
        "kind": "boardwise-presentation-spec",
        "specVersion": 1,
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right", "load": "right",
                            "source": "left", "power": "top", "gnd": "bottom"},
        "modules": [
            {"id": "m", "role": "host island", "grammarRef": "ic-periphery",
             "core": "U1",
             "parts": ["U1", "Y1", "C5", *E_SHUNTS, *E_SIBLINGS]},
        ],
    })
    book = {
        "C0402": SymbolProfile.from_dict(SHUNT_PROFILE),
        "Y0402": SymbolProfile.from_dict(CRYSTAL_PROFILE),
        "CORE8": SymbolProfile.from_dict(E_CORE_PROFILE),
    }
    return circuit, presentation, book


def _seat_band(origins, ids):
    """The line span of ``ids`` at the seats ``origins`` hands them, measured
    as their own ``_part_box`` bodies (the gate's ruler, not the bay's)."""
    rows = [origins[part] for part in ids]
    return (min(point[1] for point in rows), max(point[1] for point in rows))



def test_the_line_block_takes_the_side_that_clears_the_sibling_band():
    """The joint seat: six rows **and** the siblings, each inside ``near``.

    Red-first reading (the clean tree this test was written against, D43027B5):
    the fixture has no candidate. ``dc.compile`` answers 0 candidates and the
    first refusal is the six shunts' own ladder (``near(C12, U1)``, the sixth
    rung at 360 against ``near_limit`` 300). A line block proposed at the
    group's mean line coordinate does not help either: it lands across the
    siblings' one-rung band, so the bay stops being able to place them inside
    ``near``.

    What must hold after the joint seat, and is pinned here:

    * the fixture really is the E shape — six shunts on **one** pad
      (``branch/shunt/owner=U1``), five distinct-pad siblings inside one lane of
      that pad, and the grammar's own ``adjacent(Y1, C5)`` pair;
    * the six rows stand on **one side** of the siblings' band: the block's
      line span and the band's own do not overlap at all (the line side was
      chosen from existing geometry, not the centred coordinate);
    * every unit's own pad is inside ``near_limit`` of the host pin it hangs
      off — the bay never had to buy a row with an out-of-budget seat;
    * no two members share an origin, no bodies overlap, the declared pair
      keeps its ladder offset, and the compiler's own ruler finds no broken
      relation;
    * ``dc.compile`` and ``compile_page`` both answer: one candidate, one page.
    """
    circuit, presentation, book = _joint_documents()
    binding = dc.bind_grammar(circuit, presentation, book)
    declared = {(item.kind, item.subject, item.object) for item in binding.constraints}
    assert ("adjacent", "Y1", "C5") in declared, (
        f"the fixture lost the grammar's declared pair: {sorted(declared)}")

    ctx, seated, seated_poses, seen = _cluster_layout(
        circuit, presentation, book, two_dimensional=True)
    members = seen["group"]
    assert sorted(members) == sorted(
        ("Y1", "C5", "C6", "C13", "C14", "C15", "C16", *E_SHUNTS)), (
        f"the fixture is not one sibling group: {members}")
    rungs = seen["rungs"]
    anchors = {rungs[part].anchor for part in E_SHUNTS}
    assert len(anchors) == 1, (
        f"the six shunts do not share one pad: {sorted(anchors)}")
    for part in E_SHUNTS:
        slot = ctx.slots[part]
        assert (slot.kind, slot.role, slot.owner) == ("branch", "shunt", "U1"), (
            f"{part} is not a branch shunt of the core: {slot}")
    units = seen["units"]
    pairs = [unit for unit in units if len(unit) == 2]
    assert len(pairs) == 1 and set(pairs[0]) == {"Y1", "C5"}, (
        f"the group was not read as one declared pair plus singletons: {units}")

    # The block's ladder is what the page was refused for: the rows must be
    # the six's, and their escape staircase alone is past `near`.
    ladder = {
        part: rungs[part].base + rungs[part].step * rungs[part].index
        for part in members
    }
    assert max(ladder[part] for part in E_SHUNTS) > ctx.budget.near_limit, (
        "the six shunts' ladder already fits inside near, so this is not the "
        f"starved block: {ladder}")

    boxes = {
        part: dc._part_box(ctx.profile(part), seated_poses[part], seated[part])
        for part in seated
    }
    for part in members:
        rung = rungs[part]
        shared = dc._pin_local(ctx, part, ctx.slots[part].pin_shared, seated_poses)
        assert shared is not None, f"{part} has no shared pin to measure"
        root = (seated[part][0] + shared[0], seated[part][1] + shared[1])
        distance = math.hypot(root[0] - rung.anchor[0], root[1] - rung.anchor[1])
        assert distance <= ctx.budget.near_limit, (
            f"{part}'s own pad is {distance:.1f} from the host pin it hangs off, "
            f"past near_limit {ctx.budget.near_limit}: root {root}")

    siblings = [part for part in members if part not in E_SHUNTS]
    row_low = min(boxes[part][1] for part in E_SHUNTS)
    row_high = max(boxes[part][3] for part in E_SHUNTS)
    band_low = min(boxes[part][1] for part in siblings)
    band_high = max(boxes[part][3] for part in siblings)
    assert row_low >= band_high or row_high <= band_low, (
        "the six-row block still sits on the siblings' band: rows "
        f"{row_low:.1f}..{row_high:.1f} vs band {band_low:.1f}..{band_high:.1f}")

    for index, here in enumerate(members):
        for there in members[index + 1:]:
            assert seated[here] != seated[there], (
                f"{here} and {there} share one origin: {seated[here]}")
            assert not dc._overlaps(boxes[here], boxes[there]), (
                f"{here} and {there} overlap after the seat: "
                f"{boxes[here]} vs {boxes[there]}")
    pair = next(unit for unit in units if len(unit) == 2)
    for part in pair:
        delta = (seated[part][0] - seen["before"][part][0],
                 seated[part][1] - seen["before"][part][1])
        first = (seated[pair[0]][0] - seen["before"][pair[0]][0],
                 seated[pair[0]][1] - seen["before"][pair[0]][1])
        assert delta == first, (
            f"{part} moved by {delta} while its declared partner moved by "
            f"{first}: the pair was not seated as one rigid body")

    violations = _cluster_violations(ctx, seated, seated_poses)
    assert not violations, (
        "the seated joint group breaks a relation the gate reads: "
        f"{sorted(violations)}")

    compiled = dc.compile(circuit, presentation, book)
    assert compiled.ok and compiled.candidates, (
        "the production preparation refuses the joint group the seat answered: "
        f"{[(f.category, f.subject) for f in compiled.failures]}")
    page = pc.compile_page(circuit, presentation, book,
                           cli._draw_page_budget((0.0, 0.0, 1170.0, 825.0)))
    assert page.pages and not page.failures, (
        "the page compiler refuses the module the slice compiles: "
        f"{[(f.category, f.subject) for f in page.failures]}")


def test_the_centred_block_alone_hands_the_siblings_back_past_near():
    """The other half of the E shape, pinned as a mutation of the seat itself.

    With the line candidates reduced to the centred one (the rolled-back
    ACE7D74C prototype's behaviour), the block lands across the siblings'
    one-rung band and the bay pushes them out one after another; the last unit
    leaves ``near`` and ``dc.compile`` answers no candidate. The line side is
    therefore what the joint seat is, not an optional extra: this test is the
    red-first record of that half on the fixed tree.
    """
    original = dc._stack_line_shift_candidates
    dc._stack_line_shift_candidates = lambda *args, **kwargs: [0.0]
    try:
        circuit, presentation, book = _joint_documents()
        compiled = dc.compile(circuit, presentation, book)
    finally:
        dc._stack_line_shift_candidates = original
    assert not compiled.ok, (
        "with no line side the centred block still compiles, so the fixture no "
        "longer measures the joint half: "
        f"{[(f.category, f.subject) for f in compiled.failures]}")
    # U-09: "refused" has to be *this* refusal — one `presentation-poor` failure on
    # C16 naming the `near` relation the joint seat exists to keep (measured
    # 2026-11-26). Any other refusal is a different answer, not this half.
    assert len(compiled.failures) == 1, [f.category for f in compiled.failures]
    failure = compiled.failures[0]
    assert failure.category == "presentation-poor"
    assert failure.subject == "C16"
    assert "near(C16, U1)" in failure.detail, failure.detail
