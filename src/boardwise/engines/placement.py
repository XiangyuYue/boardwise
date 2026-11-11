"""Topology-aware placement: where every part goes, and how it is turned.

Why this module exists (201B). The compiler's own placement
(:func:`boardwise.engines.drawcompiler._place`) is a *constructive chain*: the
grammar's ranks are laid on one line, each branch is hung off the pin it shares a
net with, and a part the grammar bound to nothing goes on a shelf. It is fast,
deterministic and easy to explain — and it is also a sequential greedy that has
no way to *trade* one part's position against another's, so a relation two parts
have to keep between their **pins** can be unreachable no matter how many poses
are tried: the flagship input of this batch (the flyback, `blocklib/specs/
flyback_uc3845.*`) compiles to **zero candidates today**, every variant refused
by the single relation ``same-column(Q1, R5)``, because the chain pitch and the
sense resistor's ~20-unit pin offset never line up.

This module is the search that greedy never was. Five concepts, which the old
stage had none of:

1. **A direction to the drawing.** ``progress`` is the unit vector rank grows
   along — derived by the caller from the presentation's own side preferences
   (power/input at one end, ground/output at the other). The constructive seed
   lays the ranked parts along it, and every side preference a net's class
   implies (``power`` up, ``gnd`` down, ``input`` left, ``output`` right) is a
   named cost term, so "left in, right out" is *priced* rather than assumed.
2. **Clusters, not shelves.** Parts are pulled together by the nets they share
   (``wire-length``: HPWL, the half-perimeter of each net's member pins), so the
   parts around a power device land near it because they are *electrically* near
   it, never because they came next in a list.
3. **The pose is a search variable.** Every legal pose of every part is a
   dimension of the search space (:attr:`PlacementPart.poses` — the caller
   passes the symbol's whole accepted set). A part is free to turn so its pins
   face what it connects to; nothing here picks "pose 0 and pose 1".
4. **Relations are soft, the page is hard.** ``same-column`` / ``right-of`` /
   ``near`` … become priced misses (:func:`relation_miss` — the distance by which
   the pair misses the relation, measured between the very points the compiler's
   own ruler measures: the two pins on the shared net where the kind says so).
   A miss is *repaired* — the search translates the offending endpoint to where
   the relation holds — instead of killing the candidate. Only three things are
   hard: off the page, on a keep-out, and overlapping each other.
5. **A search anyone can audit.** Deterministic simulated annealing with a fixed
   seed (same input, same output — measured by re-running), and a cost function
   that is a *list of named terms with values* (:class:`CostTerm`), printed into
   the result. Nothing is a single opaque "score"; the 052 sec.6 reading rule
   ("keep the raw metric and the reason, never just `aesthetics=4.2`") is the
   shape of :attr:`PlacementResult.costs`.

What this module deliberately does **not** do: routing, flag *drawing*, labels,
text and the readability contract all live downstream (they need the plan, not
the placement). The output is what the task book asks for — ``(x, y, rotation,
mirror)`` per part, plus the numbers the decision was made from. The one flag
thing it does own is **room**, not drawing: a declared series arm
(:class:`SeriesSeatTemplate`) or a joint flag corridor
(:class:`FlagCorridorTemplate`) is bound against the answer and reported as the
boxes it needs plus the ordinary parts that had to yield, so the layer that
draws the flag and the layer that reserved its room read one geometry.

The ruler is the grammar's own. :func:`relation_holds` implements the ten kinds
of ``grammar/base.py:CONSTRAINT_KINDS`` with the same words the compiler's
``_relation_holds`` uses (same slack = grid/2, same near limit, same lateral and
progress vectors). One difference is stated rather than hidden: this module
imports nothing from ``drawcompiler``, so the two implementations are two copies
of one rule; 201B's stage 2 reconciles them (the compiler will call *this*
module, and its own copy is what retires).
"""

from __future__ import annotations

import itertools
import math
import random
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Mapping, Sequence

from ..core.geometry import transform_point
from ..core.symbolprofile import Box, SymbolPin, SymbolPose, SymbolProfile, pose_box
from ..core import textmetrics
from . import router as _router

#: What a caller writes into a report that names the placement it used.
PLACEMENT_NAME = "boardwise-placement/1"

#: How close two points must be before they are the same point when a bound
#: series seat is compared with the answer the search returned.
SERIES_EPS = 1e-9

#: The lattice every coordinate lands on, and the "same column or row" slack it
#: implies (the checker's own reading: ``readability.DEFAULT_GRID``).
DEFAULT_GRID = 5.0

#: How far apart two pins may be and still count as "near" (``drawcompiler.
#: NEAR_LIMIT`` — the number the compiled flyback page is read at).
DEFAULT_NEAR_LIMIT = 300.0

#: The seed of the constructive layout's chain pitch: the wiring channel between
#: two facing pin tips (``drawcompiler.CHANNEL``).
DEFAULT_CHANNEL = 40.0

#: How far a branch hangs off the node it belongs to (``drawcompiler.LANE``).
DEFAULT_LANE = 60.0

#: Cost weights. Named, because a weight nobody can read is a weight nobody can
#: argue with. Relations are the grammar's promises and are priced first; the
#: wiring and side terms shape the drawing around them; compactness breaks ties.
W_RELATION = 10.0
W_WIRE = 1.0
W_FACING = 1.0
W_SIDE = 2.0
W_SPREAD = 0.5
#: Missing air between two parts, in canvas units per unit of shortfall. The
#: clearance itself is :data:`TEXT_CLEARANCE`.
W_CLEARANCE = 1.5
#: Taken room inside a flag's reservation, per **square unit**. The reservation is
#: an area and the other weights are lengths, so this one is read at its own scale:
#: a part standing fully inside a 20 x 60 reservation (1200 units²) costs 240,
#: about as much as missing a relation by 24 units — enough to move a part out of
#: a flag's way, not enough to outbid the grammar.
W_FLAG_ROOM = 0.2

#: How much air two parts' extents leave each other, in canvas units.
#:
#: Not aesthetics — the plan prints each part's designator and value **beside its
#: body**, and the readability contract refuses a drawing where that text lands on
#: another part or on a conductor (`text-overlap`, `text-on-wire`). Measured on
#: the flyback 2026-10-17: a placement that kept all 33 relations with nothing
#: overlapping was still refused by the gate for **14** text collisions, every one
#: of them a pair of parts closer than the text they carry. The search cannot see
#: where stage 3b will print (that is downstream of it), so it reserves the room
#: instead: one designator row plus a little air.
TEXT_CLEARANCE = 15.0
#: What one unit of a **hard** violation costs. Large on purpose (an overlapping
#: or off-page drawing is not a drawing), but finite: a search that refuses to
#: move through a hard-violating state at all cannot get out of one.
W_HARD = 200.0

#: The least air between two pin tips **of different nets**, in canvas units.
#:
#: Not aesthetics either, and this one is worse than a crowded drawing: two tips
#: of different nets on the same point is a **short** that the plan cannot draw
#: around. The router treats a foreign tip as a wall (`_blocked_points`: a wire
#: vertex landing on one joins two nets the CircuitSpec keeps apart), so a net
#: whose obligation runs through that point is refused outright, and a wire that
#: did run through it would be the short itself.
#:
#: Measured on the flyback 2026-10-18: `Q1.3` (net SRC) and `R5.2` (net PGND) at
#: the same (75, 165), and `SRC`'s direct-wire obligation refused for it — "could
#: not be joined ... without a wire crossing a body, a text box or a foreign
#: connection". The term list could not see it: `overlap` and `clearance` measure
#: part **bodies**, and a pin tip is a point on a body's boundary.
#:
#: The reason the number is a **multiple of the lattice**: two tips one lattice
#: step apart are still one lattice step apart, so any wire drawn on the lattice
#: between them lands on a lattice node — an arrangement the router has to dodge,
#: not one it can pass through. Two steps leaves a lattice node on either side of
#: the pair, which is the least that is worth asking for; `grid * 3` and `grid * 4`
#: were measured and rejected — at 15 and 20 units the repair pass cannot reach
#: zero on the flyback at any weight (30 units of shortfall left at `grid * 4`), and
#: the wider the band, the more of the drawing's own spacing it fights. Two steps
#: reaches 0.0 on the flyback and leaves every published baseline untouched.
#:
#: Measured on the flyback 2026-10-18, all on the topology request:
#:
#: | axis | reading |
#: |---|---|
#: | `pin-clearance` before this term | 12 pairs of foreign tips inside 25 units, `Q1.3` (SRC) 15 from `R5.2` (PGND) |
#: | `grid * 2` = 10, `W` 20 / 30 / 40 / 50 / 80 | term 0.0, every relation kept |
#: | `grid * 2` = 10, `W` 120 | term 0.0 but `right-of(C10, U5)` missed by 2.5 |
#: | `grid * 3` = 15, `W` 12 / 15 / 20 / 30 | term 0.0, every relation kept, **but** `098` scene 08's published refusal report moved |
#: | `grid * 4` = 20, `W` 10 | term 30.0 — not reachable |
#:
#: The `grid * 3` note is the one that decided the number. That threshold is
#: **reachable** on the flyback and still wrong, because it changes the answer to
#: a page that was never crowded: `098` scene 8's refusal report is held to a
#: byte-for-byte baseline (`tests/test_116_ordinal_consumption.py`), and its
#: topology answer's own smallest foreign-tip distance is **20.6** units — so at a
#: 15-unit threshold the repair pass ran there for a problem that did not exist
#: and the report moved. At `grid * 2` it does not run, and every one of `098`'s
#: twelve published products comes out byte-identical. A spacing rule that fires
#: on drawings it has nothing to say about is the wrong rule.
PIN_CLEARANCE_GRID = 2.0

#: What one unit of the pin-tip shortfall costs. Between :data:`W_RELATION` and
#: :data:`W_HARD`: a short is a **worse** fault than a crowded drawing, so this is
#: the one soft term priced above the grammar's own promises — but it stays soft,
#: because a drawing with one is still a drawing and the gate downstream is the
#: place that names it (`foreign connection`).
#:
#: The value comes from the band the two regressions leave open, measured by
#: sweeping it against the published topology request at `grid * 2`:
#:
#: * `W` 20 / 30 / 40 / 50 / 80 all reach `pin-clearance` 0.0 with every relation
#:   kept, so the term is not a tuning knob anywhere in that band;
#: * `W` 120 breaks `right-of(C10, U5)` by 2.5 — that is the ceiling, and it is
#:   where the term starts outbidding the grammar rather than repairing the short;
#: * `W` 20 is the floor: the repair pass starts from the first answer and cannot
#:   clear the last 5 units of shortfall there; `W` 30 and above do clear it.
#:
#: 40 is the geometric middle of the band with a factor of three of headroom to
#: the ceiling. Read it against the relation weight: one 10-unit shortfall costs as
#: much as four relations missed by 10 units — deliberate, since the short is the
#: one fault the plan cannot draw past.
W_PIN_CLEARANCE = 40.0

#: What it costs for a pin tip to sit **inside another part's text row**, per
#: unit of burial depth.
#:
#: The second obstacle the term list could not see, and it is the one that
#: mattered most. A part's designator and value are drawn at anchors its
#: **symbol** declares, and the host does not turn those rows with the pose
#: (`drawcompiler._declared_rows`, 147's measurement; the offsets are read off
#: the part's origin in the page frame). `placement.part_box` is
#: "drawn body + every pin tip" — it carries no texts — so two parts can keep
#: every body box apart, keep every relation, and still have a neighbour's value
#: row land exactly on a pin tip. That tip is then a wall for the router
#: (`_blocked_points`), and the net that owns it can never be drawn: measured
#: 2026-10-19 on the flyback, **21 of 21** buried tips were inside another
#: part's value row, and every one of them belonged to a net whose direct-wire
#: obligation was then refused.
#:
#: Depth, not a flat penalty: the search needs a gradient to push a tip out of a
#: 40–85 unit wide row, and a flat cost gives it the same reading at the middle
#: of the row as at its edge.
#:
#: The row's height is :data:`TEXT_ROW_HEIGHT`, which **must** equal
#: `drawcompiler.TEXT_ROW_HEIGHT` (10.0) — a test pins the two together
#: (`test_525_pin_text_row.test_the_two_text_row_heights_agree`), because a box
#: that is taller than the drawn row prices a collision no reader can see.
#:
#: **Below** :data:`W_RELATION` on purpose. The relations are the grammar's
#: promises and the term list's own doctrine is that compactness "must never
#: outbid a relation"; a burial is a *downstream* obstruction (the router cannot
#: land on the tip) while a missed relation is the drawing saying the wrong thing
#: about the circuit. Measured 2026-10-19 on the flyback: at 20.0 the search
#: cleared every burial but traded `right-of(C10, U5)` away by 2.5 units (one
#: half-lattice) to do it — 25 units of relation bought with a term worth 20 per
#: unit of depth. At 8.0 a 10-unit burial costs less than one relation missed by
#: 10 units, so the relation is repaired first and the burial is cleared out of
#: what remains.
W_PIN_TEXT = 8.0

#: The height of one symbol text row. Same number as
#: `drawcompiler.TEXT_ROW_HEIGHT`; see :data:`W_PIN_TEXT`.
TEXT_ROW_HEIGHT = 10.0

#: What a pin tip **on** a row's edge counts as, in units of burial depth (see
#: :func:`_burial_depth`). The router's wall test includes the far edge, so an
#: edge tip cannot receive a wire end; a bare depth of 0 would read as "free" and
#: leave the search no gradient at all. Half a lattice step: an edge tip prices
#: below one a unit inside the row, and far below a missed relation.
#:
#: Small because it has to be, not because the edge is harmless. Measured
#: 2026-10-19 on the flyback: at 0.5 the search leaves 3 tips on edges
#: (`pin-text` 1.5 of a 33-relation-keeping answer); at 2.0 it leaves 4
#: (`pin-text` 8.0) — the relations hold both times, so the tips are pinned by
#: the grammar, not by the weight. What the term buys at this value is honest
#: **bookkeeping**: an answer that keeps tips off edges reads 0, and one that
#: does not says so in its cost list instead of looking clean.
PIN_TEXT_EDGE = 0.5

#: The sides a net class prefers, when the caller states nothing (053 sec.2's
#: presentation defaults).
DEFAULT_SIDE_PREFERENCES: Mapping[str, str] = {
    "input": "left", "output": "right", "power": "top", "gnd": "bottom",
}

_SIDE_VECTORS: Mapping[str, tuple[float, float]] = {
    "top": (0.0, 1.0), "bottom": (0.0, -1.0),
    "left": (-1.0, 0.0), "right": (1.0, 0.0),
}

#: The relation kinds this module can measure, in ``grammar/base.py``'s spelling.
SAME_COLUMN = "same-column"
SAME_ROW = "same-row"
ABOVE = "above"
BELOW = "below"
LEFT_OF = "left-of"
RIGHT_OF = "right-of"
ADJACENT = "adjacent"
NEAR = "near"
HORIZONTAL_TAP = "horizontal-tap"
VERTICAL_TAP = "vertical-tap"

#: The two kinds measured between the pair's **pins on the net they share** (a
#: branch belongs to the node it hangs off; a tap is a junction between two arm
#: pins), and the two order kinds measured between origins. Same split, and the
#: same reason, as the compiler's ``_points_for_relation``.
_PIN_KINDS = (SAME_ROW, SAME_COLUMN, HORIZONTAL_TAP, VERTICAL_TAP, NEAR)

_ORDER_KINDS = (ABOVE, BELOW, LEFT_OF, RIGHT_OF)


class PlacementError(ValueError):
    """The request is not one this module can search."""


# ------------------------------------------------------------------ the input


@dataclass(frozen=True)
class FlagReservation:
    """One pin the plan will hang a flag on, and the room that flag needs.

    201B stage 2's last piece. The compiler hangs a rail's own flag at the pin the
    rail *supplies* (:func:`boardwise.engines.drawcompiler._power_flag_pin`) and
    draws it as a **vertical run** out of that pin, with the glyph, the host's own
    name row and :data:`FLAG_CLEARANCE` beyond it. The placement search cannot see
    any of that — flags are stage 3b — so the room is handed to it as a box
    measured **by the compiler's own model**
    (:func:`drawcompiler._flag_box`), stated relative to the pin.

    Relative on purpose: the search moves parts, so the only thing it can use is
    "this much room, this far out, in this direction from this pin" — and the
    caller that owns the flag geometry is the one that says how much.
    """

    part_id: str
    token: str
    net_id: str
    #: The room the flag needs, ``(x0, y0, x1, y1)`` **relative to the pin**:
    #: the lead's run out of the pin plus the glyph, the name row and the
    #: clearance, as one box.
    box: tuple[float, float, float, float]

    def box_at(self, pin: tuple[float, float]) -> Box:
        """The reservation in page coordinates, for a pin at this point."""
        return (
            pin[0] + self.box[0], pin[1] + self.box[1],
            pin[0] + self.box[2], pin[1] + self.box[3],
        )


@dataclass(frozen=True)
class PlacementPart:
    """One part to place: its symbol, its legal poses, and its lock.

    ``poses`` is the symbol's **whole** accepted set — this module searches it
    (concept 3). ``locked`` is the pose an engineer's ``userLocks[]`` entry pins
    the part to; a locked part keeps that pose exactly and is never a candidate
    for a repair or a flip (052's escape hatch, honoured or reported, never
    silently snapped).
    """

    part_id: str
    profile: SymbolProfile
    poses: tuple[SymbolPose, ...]
    locked: SymbolPose | None = None
    #: The origin an engineer's lock pins this part to, **exactly** (515A hole
    #: 3). The pose alone tells the search *how* the part faces; without the
    #: point too, the seed snaps the locked origin onto the grid and the search
    #: translates it like any other part — so a lock whose point sits off the
    #: lattice, or beside the seed, was guaranteed to be refused downstream by
    #: the lock checker (``user-lock-violated``): the one input the compiler
    #: may not quietly ignore, broken by the solver that never read it. Set
    #: together with ``locked``; ``None`` poses the part free.
    locked_origin: tuple[float, float] | None = None
    #: The part's value string (``"17.8k 1% TH"``), used **only** to size its
    #: value row for :func:`_pin_text_term`. Empty means the caller did not
    #: state one, and that row is then not measured — the same reading
    #: `drawcompiler._declared_rows` makes (a row with no text has no box).
    value: str = ""

    def __post_init__(self) -> None:
        if not self.part_id:
            raise PlacementError("a part needs an id")
        if not self.poses:
            raise PlacementError(
                f"{self.part_id}: no legal pose was passed, and a part with no "
                "pose is a part this search cannot place — the caller's own "
                "pose filter refused every pose its symbol declares"
            )
        if self.locked is not None and self.locked not in self.poses:
            # A lock whose rotation the symbol cannot be drawn in at all is a
            # fact worth reporting, not a reason to refuse: the pose is used and
            # the relations it breaks come out of the cost list as misses.
            pass


@dataclass(frozen=True)
class PlacementNet:
    """One net of the netlist: its members, as ``(part_id, pin token)``.

    ``cls`` is the CircuitSpec's own net class (``power`` / ``gnd`` /
    ``signal``, empty when the circuit states none) and is what the side
    preferences are read through — the same reading the presentation makes for
    the roles it names.
    """

    net_id: str
    members: tuple[tuple[str, str], ...] = ()
    cls: str = ""

    def __post_init__(self) -> None:
        if not self.net_id:
            raise PlacementError("a net needs an id")


@dataclass(frozen=True)
class PlacementRelation:
    """One relation two parts must keep — the grammar's, verbatim.

    Deliberately the same four fields as
    ``grammar.base.RelativeConstraint`` (kind, subject, object, reason) and no
    more: a relation is not a coordinate, and this module is the layer that turns
    it into one.
    """

    kind: str
    subject: str
    object: str
    reason: str = ""

    def __post_init__(self) -> None:
        if self.kind not in _PIN_KINDS + _ORDER_KINDS + (ADJACENT,):
            raise PlacementError(
                f"unknown relation kind {self.kind!r}; this module knows "
                f"{sorted(_PIN_KINDS + _ORDER_KINDS + (ADJACENT,))}"
            )
        if not self.subject or not self.object:
            raise PlacementError(
                f"the {self.kind} relation names an empty endpoint — a relation "
                "names both parts"
            )

    def label(self) -> str:
        return f"{self.kind}({self.subject}, {self.object})"


# ------------------------------------------------------- the declared series seats

#: The category a refused series seat reports. It is the compiler's existing
#: ``layout-unsat`` class — the document's arm is legal, what fails is the
#: geometry this request can build — not a fifth kind invented here.
SERIES_SEAT_REFUSAL = "layout-unsat"


@dataclass(frozen=True)
class SeriesSeatRefusal:
    """Why a declared series arm could not be seated, in the compiler's words.

    The same shape as the compiler's own ``GrammarFailure`` fields, so the
    topology consumer can turn it into its existing refusal without inventing a
    new category or losing the branch id it has to name.
    """

    branch_id: str
    subject: str
    detail: str
    action: str
    category: str = SERIES_SEAT_REFUSAL

    def __post_init__(self) -> None:
        if not self.branch_id:
            raise PlacementError("a series seat refusal needs its branch id")
        if not self.detail:
            raise PlacementError(
                f"series branch {self.branch_id}: a refusal without a detail is "
                "not a report"
            )

    def render(self) -> str:
        tail = f" — {self.action}" if self.action else ""
        return f"{self.category} {self.subject}: {self.detail}{tail}"

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "branchId": self.branch_id, "category": self.category,
            "subject": self.subject, "detail": self.detail, "action": self.action,
        }


@dataclass(frozen=True)
class SeriesSeatYield:
    """One ordinary part asked to move out of a series arm's reserved box.

    The mapping is **named** rather than a global spacing change: it says which
    part yields, which branch's box it yields to, the direction it leaves in and
    the point the binder moved it to. A part the seat may not move — an engineer
    lock, or a member of another arm — carries ``refusal`` instead of a
    direction, and the reservation stays a hard violation for the caller to
    refuse by name.
    """

    part_id: str
    branch_id: str
    box_index: int
    direction: tuple[float, float] | None = None
    target: tuple[float, float] | None = None
    refusal: str = ""

    def __post_init__(self) -> None:
        if not self.part_id or not self.branch_id:
            raise PlacementError("a series seat yield names both a part and a branch")
        if self.box_index < 0:
            raise PlacementError("a series seat yield names a reserved box index")
        if self.direction is None and not self.refusal:
            raise PlacementError(
                f"{self.part_id}: a yield either states a direction or states why "
                "it cannot move"
            )
        if self.direction is not None and self.refusal:
            raise PlacementError(
                f"{self.part_id}: a yield with a direction cannot also refuse it"
            )

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "partId": self.part_id, "branchId": self.branch_id,
            "boxIndex": self.box_index,
            "direction": list(self.direction) if self.direction is not None else None,
            "target": list(self.target) if self.target is not None else None,
            "refusal": self.refusal,
        }


@dataclass(frozen=True)
class LabelCorridor:
    """One label's default seat, stated in **pin-relative** terms (548D3B).

    A label the compiler will print hangs off a pin the plan does not own, and
    the box it takes is decided *after* the placement has finished — which is
    how LED2_K's run ended up across ESP_EN's name (structural-findings sec.2).
    This is the missing half: the box the label takes when nothing gets in its
    way, given as data the placement can transform.

    It carries **no coordinate** — the pin tip is wherever the answer puts that
    part. ``local_direction`` is the pin's escape in the *symbol's* frame (the
    profile's own ``left/right/up/down``); the placement turns it into a page
    direction with the pose and then places the box. ``reach_x`` / ``reach_y``
    are the compiler's two half-reaches (a horizontal escape steps by the text's
    half-width, a vertical one by the text row's half-height) and ``width`` /
    ``height`` are the box's own extents — text is **always horizontal**, so the
    width is always along x: the box is centred, never rotated with the symbol.
    """

    part_id: str
    token: str
    local_direction: str
    width: float
    height: float
    reach_x: float
    reach_y: float
    net_id: str = ""

    def __post_init__(self) -> None:
        if not self.part_id or not self.token:
            raise PlacementError("a label corridor names both a part and a pin")
        if self.local_direction not in ("left", "right", "up", "down"):
            raise PlacementError(
                f"{self.part_id}.{self.token}: a label corridor's direction must be "
                f"one of left/right/up/down, got {self.local_direction!r}"
            )
        if self.width <= 0 or self.height <= 0:
            raise PlacementError(
                f"{self.part_id}.{self.token}: a label box needs a positive extent"
            )
        if self.reach_x < 0 or self.reach_y < 0:
            raise PlacementError(
                f"{self.part_id}.{self.token}: a label reach cannot be negative"
            )

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "partId": self.part_id, "token": self.token, "netId": self.net_id,
            "localDirection": self.local_direction,
            "width": self.width, "height": self.height,
            "reachX": self.reach_x, "reachY": self.reach_y,
        }


@dataclass(frozen=True)
class SeriesSeatArmPart:
    """One of the two parts of an arm, and the pins that read it in order.

    ``from_token`` is the pin against the host end, ``middle_token`` the pin
    against the other part and ``to_token`` the pin against the terminal end.
    The first part needs ``from`` and ``middle``; the second needs ``middle`` and
    ``to``; the unused one stays empty rather than being guessed. Tokens resolve
    by pin number first, then by pin name — the same rule the compiler's own
    ``_pin_of_token`` applies.
    """

    part_id: str
    from_token: str = ""
    middle_token: str = ""
    to_token: str = ""

    def __post_init__(self) -> None:
        if not self.part_id:
            raise PlacementError("a series arm part needs an id")


@dataclass(frozen=True)
class SeriesSeatTemplate:
    """A declared two-part series arm, before the host's own seat is known.

    Pure data: the branch, the host pin the arm hangs from, the two parts and the
    pins that make the chain, the poses the arm is drawn in, the chain axis, the
    lattice and the air its reserved boxes keep. It carries **no absolute
    coordinate** — the host's pin tip is not known until the ordinary seed has
    placed the page, and inventing one here would be a second, false engineer
    lock. ``pitch_source`` names where the frozen pair pitch comes from; the
    number itself is measured from the ordinary seed at binding time.
    """

    branch_id: str
    host_part: str
    host_token: str
    first: SeriesSeatArmPart
    second: SeriesSeatArmPart
    first_pose: SymbolPose
    second_pose: SymbolPose
    progress: tuple[float, float] = (1.0, 0.0)
    lateral: tuple[float, float] = (0.0, 1.0)
    grid: float = DEFAULT_GRID
    #: The compilation lattice's offset per axis — the same ``residue`` the
    #: compiler's ``_snap`` uses (``round((value - lattice[i]) / grid) * grid +
    #: lattice[i]``). It is a **coordinate** offset, not air between boxes.
    lattice: tuple[float, float] = (0.0, 0.0)
    #: The air every reserved box keeps around its geometry, and the gap a
    #: yielding ordinary part leaves beyond it. It is **padding**, not a lattice
    #: offset; the two are deliberately separate fields.
    clearance: float = 0.0
    #: The foreign parts a yield may move. ``None`` — the default, and every
    #: caller that states no policy — lets the binder move any un-locked part.
    #: The draw consumers state the **ordinary signal branches** here: a rail's
    #: decoupling part is not something an arm's reserve may push aside, and
    #: leaving it in place keeps the hard violation and the named refusal.
    yield_parts: frozenset[str] | None = None
    pitch_source: str = "ordinary-seed"

    def __post_init__(self) -> None:
        if not self.branch_id:
            raise PlacementError("a series seat template needs a branch id")
        if not self.host_part or not self.host_token:
            raise PlacementError(
                f"series branch {self.branch_id}: the template names both the "
                "host part and the host pin token"
            )
        if self.first.part_id == self.second.part_id:
            raise PlacementError(
                f"series branch {self.branch_id}: both seats name the same part "
                f"{self.first.part_id!r}; an arm is two parts"
            )
        if self.host_part in (self.first.part_id, self.second.part_id):
            raise PlacementError(
                f"series branch {self.branch_id}: the host part "
                f"{self.host_part!r} is also one of the arm's two parts"
            )
        if not self.first.from_token or not self.first.middle_token:
            raise PlacementError(
                f"series branch {self.branch_id}: {self.first.part_id} needs a "
                "from pin (host side) and a middle pin"
            )
        if not self.second.middle_token or not self.second.to_token:
            raise PlacementError(
                f"series branch {self.branch_id}: {self.second.part_id} needs a "
                "middle pin and a to pin (terminal side)"
            )
        if self.grid <= 0:
            raise PlacementError(
                f"series branch {self.branch_id}: grid must be positive, got "
                f"{self.grid!r}"
            )
        for axis, offset in zip(("x", "y"), self.lattice):
            if not (0.0 <= offset < self.grid):
                raise PlacementError(
                    f"series branch {self.branch_id}: lattice offset {offset!r} on "
                    f"{axis} must lie in [0, grid) = [0, {self.grid}); an offset "
                    "outside one lattice step is a different grid, not a residue"
                )
        if self.clearance < 0:
            raise PlacementError(
                f"series branch {self.branch_id}: clearance cannot be negative"
            )
        if not self.pitch_source:
            raise PlacementError(
                f"series branch {self.branch_id}: the template does not say where "
                "its pair pitch comes from"
            )


@dataclass(frozen=True)
class BoundSeriesSeatPlan:
    """A template materialised against the host's actual pin tip.

    Produced once, when the ordinary seed exists, by the one binder that knows
    the seat equation: the first part's ``from`` pin faces the host, the second
    part's ``middle`` pin faces the first, and the two **origins** sit one frozen
    ``pitch`` apart along ``progress`` — the same reading
    ``drawcompiler._seat_series_arms`` makes of the ordinary seed. The plan is
    immutable; a moved arm is a new plan, never a rewritten one, so a cached
    result cannot be polluted by a later consumer.

    ``reserved_boxes`` are the two part boxes plus the host-to-first and
    first-to-second corridors, all measured with ``clearance`` air. ``lattice``
    is the coordinate offset the two origins are snapped to; the two fields are
    never interchangeable. ``yields`` names every ordinary part the binder moved
    out of them, and ``refusal`` is the structured ``layout-unsat`` report when
    the seat could not be built.
    """

    branch_id: str
    host_part: str
    host_token: str
    first_part: str
    second_part: str
    first_origin: tuple[float, float] | None
    second_origin: tuple[float, float] | None
    first_pose: SymbolPose | None
    second_pose: SymbolPose | None
    first_from_token: str = ""
    first_middle_token: str = ""
    second_middle_token: str = ""
    second_to_token: str = ""
    pitch: float = 0.0
    lane: float = 0.0
    pitch_source: str = "ordinary-seed"
    progress: tuple[float, float] = (1.0, 0.0)
    lateral: tuple[float, float] = (0.0, 1.0)
    grid: float = DEFAULT_GRID
    lattice: tuple[float, float] = (0.0, 0.0)
    clearance: float = 0.0
    yield_parts: frozenset[str] | None = None
    #: The arm's **walkable** reserve: two part boxes, the orthogonal legs of the
    #: host lead, the middle link. This is the geometry an ordinary branch yields
    #: to (548D3B).
    reserved_boxes: tuple[Box, ...] = ()
    #: The **conservative** boxes an unyieldable part is refused on: the same two
    #: part boxes and middle link, but the host lead as the whole AABB between
    #: the two feet. A power/decoupling part or an engineer lock is judged here,
    #: so its hard survives while an ordinary branch is no longer pushed by air
    #: the wire never crosses. Empty on a plan with no host pin.
    guard_boxes: tuple[Box, ...] = ()
    #: The point sequence the host lead means: host foot -> lane corner -> first
    #: ``from`` foot (the corner is dropped on a straight run). The compiler
    #: checks its own routed wire against this, so a reservation and a wire can
    #: never be two different drawings.
    host_path: tuple[tuple[float, float], ...] = ()
    yields: tuple[SeriesSeatYield, ...] = ()
    refusal: SeriesSeatRefusal | None = None

    @property
    def seated(self) -> bool:
        return (
            self.refusal is None
            and self.first_origin is not None
            and self.second_origin is not None
            and self.first_pose is not None
            and self.second_pose is not None
        )

    def owned_parts(self) -> frozenset[str]:
        """The three parts this plan owns: the host and the arm's two parts."""
        return frozenset((self.host_part, self.first_part, self.second_part))

    def mismatches(
        self,
        origins: Mapping[str, tuple[float, float]],
        poses: Mapping[str, SymbolPose],
    ) -> tuple[str, ...]:
        """Every way the answer disagrees with this plan, as printable lines.

        Empty means the two origins and poses are the plan's, exactly. A
        consumer that requires the arm to be where the plan says (the compiler's
        ``_topology_placement`` in the next batch) checks this rather than
        trusting the search to have kept its own promise.
        """
        if self.refusal is not None:
            return (f"{self.branch_id}: {self.refusal.render()}",)
        out: list[str] = []
        if self.host_part not in origins:
            out.append(f"{self.branch_id}: host {self.host_part} is absent from the result")
        for part_id, origin, pose in (
            (self.first_part, self.first_origin, self.first_pose),
            (self.second_part, self.second_origin, self.second_pose),
        ):
            if origin is None or pose is None:
                out.append(f"{self.branch_id}: {part_id} has no bound seat")
                continue
            at = origins.get(part_id)
            if at is None:
                out.append(f"{self.branch_id}: {part_id} is absent from the result")
                continue
            if abs(at[0] - origin[0]) > SERIES_EPS or abs(at[1] - origin[1]) > SERIES_EPS:
                out.append(
                    f"{self.branch_id}: {part_id} sits at "
                    f"({at[0]:g}, {at[1]:g}), the plan says "
                    f"({origin[0]:g}, {origin[1]:g})"
                )
            if poses.get(part_id) != pose:
                out.append(
                    f"{self.branch_id}: {part_id} is drawn in pose "
                    f"{poses.get(part_id)}, the plan says {pose.label()}"
                )
        return tuple(out)

    def origin_pitch(self, origins: Mapping[str, tuple[float, float]]) -> float | None:
        """The measured origin distance between the two seated parts.

        ``pitch`` is the **nominal** distance the ordinary seed stated and is
        kept as the plan's source of truth even when snapping the two origins
        onto ``grid + lattice`` quantizes the measured distance a little. This
        method is the final-geometry reading: a consumer checks it rather than
        assuming the snap preserved the nominal number.
        """
        first = origins.get(self.first_part)
        second = origins.get(self.second_part)
        if first is None or second is None:
            return None
        return math.hypot(second[0] - first[0], second[1] - first[1])

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "branchId": self.branch_id,
            "hostPart": self.host_part, "hostToken": self.host_token,
            "firstPart": self.first_part, "secondPart": self.second_part,
            "firstOrigin": list(self.first_origin) if self.first_origin else None,
            "secondOrigin": list(self.second_origin) if self.second_origin else None,
            "firstPose": self.first_pose.to_jsonable() if self.first_pose else None,
            "secondPose": self.second_pose.to_jsonable() if self.second_pose else None,
            "pitch": self.pitch, "lane": self.lane,
            "pitchSource": self.pitch_source,
            "grid": self.grid, "lattice": list(self.lattice),
            "clearance": self.clearance,
            "yieldParts": (
                None if self.yield_parts is None else sorted(self.yield_parts)
            ),
            "reservedBoxes": [list(box) for box in self.reserved_boxes],
            "yields": [item.to_jsonable() for item in self.yields],
            "refusal": self.refusal.to_jsonable() if self.refusal else None,
        }

    def translated(
        self,
        delta: tuple[float, float],
        lattice: tuple[float, float] | None = None,
    ) -> BoundSeriesSeatPlan:
        """This plan after the whole drawing moved by ``delta``.

        The page anchor translates every origin by one vector; the plan's two
        origins and all reserved boxes move with it, and the lattice field is
        optionally restated in the anchored frame. The pitch and lane do not
        change — a translation is not a re-seat.
        """
        def move(point: tuple[float, float]) -> tuple[float, float]:
            return (point[0] + delta[0], point[1] + delta[1])

        def move_box(box: Box) -> Box:
            return (
                box[0] + delta[0], box[1] + delta[1],
                box[2] + delta[0], box[3] + delta[1],
            )

        return replace(
            self,
            first_origin=move(self.first_origin) if self.first_origin else None,
            second_origin=move(self.second_origin) if self.second_origin else None,
            reserved_boxes=tuple(move_box(box) for box in self.reserved_boxes),
            guard_boxes=tuple(move_box(box) for box in self.guard_boxes),
            host_path=tuple(move(point) for point in self.host_path),
            lattice=self.lattice if lattice is None else lattice,
        )


# ------------------------------------------------- the declared flag corridors


#: The category a refused flag corridor reports. ``layout-unsat`` is the
#: compiler's own class for "the document is legal, this geometry is not", so a
#: corridor refusal is the same noun a series seat refusal already uses.
FLAG_CORRIDOR_REFUSAL = SERIES_SEAT_REFUSAL


def _finite(value: float) -> bool:
    """Is this a finite number? A NaN/inf coordinate is not a seat."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


@dataclass(frozen=True)
class FlagCorridorCandidate:
    """One real seat for one flag of a corridor, stated **relative to its pin**.

    The flag is drawn after the placement, in page coordinates, so a candidate is
    a page-frame shape hung off the pin tip: ``anchor`` is the point the glyph is
    attached at, ``rotation`` the glyph's own rotation, ``lead`` the orthogonal
    run from the pin to the anchor (``[(0, 0), (dx, dy), ...]``, the first point
    always the pin) and ``box`` the real room the drawn flag needs — the lead's
    run plus the glyph, its name row and the clearance, exactly the box
    :class:`FlagReservation` carries. Nothing here is a new reach or a new
    shape: a caller builds these from the geometry it already measured
    (``drawcompiler._flag_box`` and the flag direction/grade it already uses),
    and names that provenance in ``source``.

    A candidate is *one* way to seat *that* flag; alternates of the same pin are
    what the joint selection trades against each other. They never merge two
    nets' flags, and they never re-point a flag at a different pin.
    """

    anchor: tuple[float, float]
    rotation: float
    lead: tuple[tuple[float, float], ...]
    box: tuple[float, float, float, float]
    source: str = "flag-grade"

    def __post_init__(self) -> None:
        if not (len(self.anchor) == 2 and all(_finite(v) for v in self.anchor)):
            raise PlacementError(
                f"a flag corridor candidate anchor must be one finite point, got "
                f"{self.anchor!r}"
            )
        if not (len(self.box) == 4 and all(_finite(v) for v in self.box)):
            raise PlacementError(
                f"a flag corridor candidate box must be four finite numbers, got "
                f"{self.box!r}"
            )
        if self.box[2] <= self.box[0] or self.box[3] <= self.box[1]:
            raise PlacementError(
                f"a flag corridor candidate box must have a positive extent, got "
                f"{self.box!r}"
            )
        rotation = float(self.rotation)
        if not math.isfinite(rotation) or rotation % 90.0 != 0.0 or not (
            0.0 <= rotation < 360.0
        ):
            raise PlacementError(
                f"a flag corridor candidate rotation must be a multiple of 90 in "
                f"[0, 360), got {self.rotation!r}"
            )
        if len(self.lead) < 2:
            raise PlacementError(
                "a flag corridor candidate lead is the run from the pin to the "
                "anchor; it needs at least one segment"
            )
        for point in self.lead:
            if not (len(point) == 2 and all(_finite(v) for v in point)):
                raise PlacementError(
                    f"a flag corridor candidate lead holds one finite point per "
                    f"vertex, got {point!r}"
                )
        if any(abs(v) > SERIES_EPS for v in self.lead[0]):
            raise PlacementError(
                f"a flag corridor candidate lead starts at its own pin, so its "
                f"first point must be (0, 0), got {self.lead[0]!r}"
            )
        for start, end in zip(self.lead, self.lead[1:]):
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            if abs(dx) <= SERIES_EPS and abs(dy) <= SERIES_EPS:
                raise PlacementError(
                    f"a flag corridor candidate lead has a zero-length segment at "
                    f"{start!r}; a lead that goes nowhere is not a lead"
                )
            if abs(dx) > SERIES_EPS and abs(dy) > SERIES_EPS:
                raise PlacementError(
                    f"a flag corridor candidate lead runs orthogonally, but "
                    f"{start!r} -> {end!r} is a diagonal"
                )
        if (
            abs(self.lead[-1][0] - self.anchor[0]) > SERIES_EPS
            or abs(self.lead[-1][1] - self.anchor[1]) > SERIES_EPS
        ):
            raise PlacementError(
                f"a flag corridor candidate lead ends at {self.lead[-1]!r}, not at "
                f"its anchor {self.anchor!r}"
            )
        if not self.source:
            raise PlacementError(
                "a flag corridor candidate names where its geometry comes from"
            )

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "anchor": list(self.anchor),
            "rotation": self.rotation,
            "lead": [list(point) for point in self.lead],
            "box": list(self.box),
            "source": self.source,
        }


@dataclass(frozen=True)
class FlagCorridorPin:
    """One pin of a corridor that needs a flag, and the real seats it may take."""

    part_id: str
    token: str
    net_id: str
    candidates: tuple[FlagCorridorCandidate, ...]

    def __post_init__(self) -> None:
        if not self.part_id or not self.token or not self.net_id:
            raise PlacementError(
                "a flag corridor pin names its part, its pin token and its net"
            )
        if not self.candidates:
            raise PlacementError(
                f"flag corridor pin {self.part_id}.{self.token} declares no "
                "candidate; a pin with no real seat cannot be seated jointly"
            )

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "partId": self.part_id, "token": self.token, "netId": self.net_id,
            "candidates": [item.to_jsonable() for item in self.candidates],
        }


@dataclass(frozen=True)
class ServicePinGap:
    """One service interval a corridor yield may not break.

    ``part_id.token`` is the shunt's **service pin** (the one on the served net),
    ``host_part.host_token`` the host pin it is served from, and ``gap`` the
    distance the drawing keeps between those two page pin points. This is data,
    not a coordinate: the points come from the answer's origins and poses, and
    the binder reads the **actual** pins after a proposed move.
    """

    part_id: str
    token: str
    host_part: str
    host_token: str
    gap: float

    def __post_init__(self) -> None:
        if not self.part_id or not self.token or not self.host_part or not self.host_token:
            raise PlacementError(
                "a service pin gap names the shunt's pin and its host pin"
            )
        if not _finite(self.gap) or self.gap <= 0.0:
            raise PlacementError(
                f"service pin gap {self.part_id}.{self.token}: the gap must be a "
                f"positive length, got {self.gap!r}"
            )

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "partId": self.part_id, "token": self.token,
            "hostPart": self.host_part, "hostToken": self.host_token,
            "gap": self.gap,
        }


@dataclass(frozen=True)
class FlagCorridorTemplate:
    """The pins that must be seated **jointly**, stated without a coordinate.

    A corridor is a group of flags on one host whose real seats press on the same
    escape room — the WiFi connector's same-side ``3V3`` / ``GND`` pins are the
    measured case. Seating them one at a time is what failed: each flag is legal
    alone and the pair is not. This template carries no absolute coordinate and
    no lock — the host's own pin tips are only known once the ordinary layout
    exists, and inventing them here would be a false engineer lock.

    ``yield_parts`` is the same policy field :class:`SeriesSeatTemplate` carries,
    with the same reading: ``None`` lets the binder move any un-locked ordinary
    part (service branches included), a stated set narrows that, and a part
    outside it keeps the hard violation and the named refusal. ``candidate_source``
    names where the finite candidates came from; it is provenance, not geometry.
    """

    group_id: str
    host_part: str
    pins: tuple[FlagCorridorPin, ...]
    grid: float = DEFAULT_GRID
    lattice: tuple[float, float] = (0.0, 0.0)
    clearance: float = 0.0
    yield_parts: frozenset[str] | None = None
    candidate_source: str = "flag-grades"
    #: The service intervals a yield may not break (548D3G batch 2). A service
    #: shunt's seat is not a free seat: its service pin stands one stated
    #: ``gap`` from its host pin (the compiler's own ``serviceLayout.pinGap``
    #: reading, ``drawcompiler._service_pin_gap``), and a corridor that moved it
    #: would keep the netlist right while breaking the service the branch was
    #: drawn for. The caller states the gap it measured; the binder checks the
    #: **final page pin points** — not a ``near`` relation — and refuses by name
    #: when the only exits would break it. Appended last: every earlier
    #: constructor keeps its meaning.
    service_gaps: tuple[ServicePinGap, ...] = ()

    def __post_init__(self) -> None:
        if not self.group_id:
            raise PlacementError("a flag corridor needs a group id")
        if not self.host_part:
            raise PlacementError(
                f"flag corridor {self.group_id}: the template names its host part"
            )
        if len(self.pins) < 2:
            raise PlacementError(
                f"flag corridor {self.group_id}: a joint seat is at least two "
                "pins; a single pin belongs to flagSeats"
            )
        seen: set[tuple[str, str]] = set()
        for pin in self.pins:
            key = (pin.part_id, pin.token)
            if key in seen:
                raise PlacementError(
                    f"flag corridor {self.group_id}: pin {pin.part_id}.{pin.token} "
                    "is declared twice"
                )
            seen.add(key)
        if self.grid <= 0:
            raise PlacementError(
                f"flag corridor {self.group_id}: grid must be positive, got "
                f"{self.grid!r}"
            )
        for axis, offset in zip(("x", "y"), self.lattice):
            if not (0.0 <= offset < self.grid):
                raise PlacementError(
                    f"flag corridor {self.group_id}: lattice offset {offset!r} on "
                    f"{axis} must lie in [0, grid) = [0, {self.grid})"
                )
        if self.clearance < 0:
            raise PlacementError(
                f"flag corridor {self.group_id}: clearance cannot be negative"
            )
        if not self.candidate_source:
            raise PlacementError(
                f"flag corridor {self.group_id}: the template does not say where "
                "its candidates come from"
            )


@dataclass(frozen=True)
class BoundFlagCorridorSeat:
    """One flag of the corridor, seated: where its pin is and the room it takes."""

    part_id: str
    token: str
    net_id: str
    origin: tuple[float, float]
    pose: SymbolPose
    pin: tuple[float, float]
    anchor: tuple[float, float]
    rotation: float
    lead: tuple[tuple[float, float], ...]
    box: Box
    source: str = "flag-grade"

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "partId": self.part_id, "token": self.token, "netId": self.net_id,
            "origin": list(self.origin), "pose": self.pose.to_jsonable(),
            "pin": list(self.pin), "anchor": list(self.anchor),
            "rotation": self.rotation,
            "lead": [list(point) for point in self.lead],
            "box": list(self.box), "source": self.source,
        }


@dataclass(frozen=True)
class BoundFlagCorridorPlan:
    """A template materialised against the host's actual pin tips.

    The plan is immutable and is **not** a drawing of its own: the seats are the
    pages' pin tips once the ordinary layout exists, plus the page-frame room each
    flag takes and the lead it draws. ``reserved_boxes`` is every chosen flag box
    and every lead segment as a box — the footprint an ordinary part must yield
    to. ``yields`` uses :class:`SeriesSeatYield` unchanged, so a reader has one
    report shape and not two; a yield with ``refusal`` set is a part the corridor
    may not move, and the plan is then refused by name (``refusal``) rather than
    seating over it.

    ``mismatches`` is the final-geometry check: a consumer that moved the host or
    a member since binding (or that hands over a different answer) gets the
    disagreement, not a silent re-read.
    """

    group_id: str
    host_part: str
    host_origin: tuple[float, float] | None
    host_pose: SymbolPose | None
    seats: tuple[BoundFlagCorridorSeat, ...] = ()
    grid: float = DEFAULT_GRID
    lattice: tuple[float, float] = (0.0, 0.0)
    clearance: float = 0.0
    yield_parts: frozenset[str] | None = None
    candidate_source: str = "flag-grades"
    #: The service intervals this corridor's yields must keep (548D3G batch 2).
    #: Copied from the template so a consumer checks the final pin points
    #: against the same numbers the binder used.
    service_gaps: tuple[ServicePinGap, ...] = ()
    reserved_boxes: tuple[Box, ...] = ()
    lead_paths: tuple[tuple[tuple[float, float], ...], ...] = ()
    yields: tuple[SeriesSeatYield, ...] = ()
    refusal: SeriesSeatRefusal | None = None

    @property
    def seated(self) -> bool:
        return (
            self.refusal is None
            and self.host_origin is not None
            and self.host_pose is not None
            and bool(self.seats)
        )

    def owned_parts(self) -> frozenset[str]:
        """The host and every member part: parts this corridor does not move."""
        return frozenset(
            {self.host_part} | {seat.part_id for seat in self.seats}
        )

    def mismatches(
        self,
        origins: Mapping[str, tuple[float, float]],
        poses: Mapping[str, SymbolPose],
    ) -> tuple[str, ...]:
        """Every way the answer disagrees with this plan, as printable lines."""
        if self.refusal is not None:
            return (f"{self.group_id}: {self.refusal.render()}",)
        out: list[str] = []
        if self.host_origin is None or self.host_pose is None:
            out.append(f"{self.group_id}: no host seat was bound")
        else:
            at = origins.get(self.host_part)
            if at is None:
                out.append(
                    f"{self.group_id}: host {self.host_part} is absent from the result"
                )
            elif (
                abs(at[0] - self.host_origin[0]) > SERIES_EPS
                or abs(at[1] - self.host_origin[1]) > SERIES_EPS
            ):
                out.append(
                    f"{self.group_id}: host {self.host_part} sits at "
                    f"({at[0]:g}, {at[1]:g}), the plan says "
                    f"({self.host_origin[0]:g}, {self.host_origin[1]:g})"
                )
            if poses.get(self.host_part) != self.host_pose:
                seen = poses.get(self.host_part)
                out.append(
                    f"{self.group_id}: host {self.host_part} is drawn in pose "
                    f"{seen.label() if isinstance(seen, SymbolPose) else seen}, "
                    f"the plan says {self.host_pose.label()}"
                )
        for seat in self.seats:
            if seat.part_id == self.host_part:
                continue
            at = origins.get(seat.part_id)
            if at is None:
                out.append(
                    f"{self.group_id}: {seat.part_id} is absent from the result"
                )
                continue
            if (
                abs(at[0] - seat.origin[0]) > SERIES_EPS
                or abs(at[1] - seat.origin[1]) > SERIES_EPS
            ):
                out.append(
                    f"{self.group_id}: {seat.part_id} sits at "
                    f"({at[0]:g}, {at[1]:g}), the plan says "
                    f"({seat.origin[0]:g}, {seat.origin[1]:g})"
                )
            if poses.get(seat.part_id) != seat.pose:
                out.append(
                    f"{self.group_id}: {seat.part_id} is drawn in pose "
                    f"{poses.get(seat.part_id)}, the plan says {seat.pose.label()}"
                )
        return tuple(out)

    def translated(
        self,
        delta: tuple[float, float],
        lattice: tuple[float, float] | None = None,
    ) -> BoundFlagCorridorPlan:
        """This plan after the whole drawing moved by ``delta``.

        Every point — host, pin tips, anchors, lead vertices, boxes — moves by
        one vector; rotation, group shape and yield records do not change. A
        translation is not a re-seat.
        """
        def move(point: tuple[float, float]) -> tuple[float, float]:
            return (point[0] + delta[0], point[1] + delta[1])

        def move_box(box: Box) -> Box:
            return (
                box[0] + delta[0], box[1] + delta[1],
                box[2] + delta[0], box[3] + delta[1],
            )

        return replace(
            self,
            host_origin=move(self.host_origin) if self.host_origin else None,
            seats=tuple(
                replace(
                    seat,
                    origin=move(seat.origin),
                    pin=move(seat.pin),
                    anchor=move(seat.anchor),
                    lead=tuple(move(point) for point in seat.lead),
                    box=move_box(seat.box),
                )
                for seat in self.seats
            ),
            reserved_boxes=tuple(move_box(box) for box in self.reserved_boxes),
            lead_paths=tuple(
                tuple(move(point) for point in path) for path in self.lead_paths
            ),
            lattice=self.lattice if lattice is None else lattice,
        )

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "groupId": self.group_id,
            "hostPart": self.host_part,
            "hostOrigin": list(self.host_origin) if self.host_origin else None,
            "hostPose": self.host_pose.to_jsonable() if self.host_pose else None,
            "seats": [seat.to_jsonable() for seat in self.seats],
            "grid": self.grid, "lattice": list(self.lattice),
            "clearance": self.clearance,
            "yieldParts": (
                None if self.yield_parts is None else sorted(self.yield_parts)
            ),
            "candidateSource": self.candidate_source,
            "serviceGaps": [item.to_jsonable() for item in self.service_gaps],
            "reservedBoxes": [list(box) for box in self.reserved_boxes],
            "leadPaths": [
                [list(point) for point in path] for path in self.lead_paths
            ],
            "yields": [item.to_jsonable() for item in self.yields],
            "refusal": self.refusal.to_jsonable() if self.refusal else None,
        }


@dataclass(frozen=True)
class PlacementInput:
    """Everything the search reads: parts, netlist, relations, and the frame.

    The four inputs the task book names — a part list, a netlist, each part's
    legal pose set, the relations — plus the numbers the measurement needs
    (``grid``, ``near_limit``), the direction the drawing runs in (``progress`` /
    ``lateral``, from the presentation's side preferences), the page it must stay
    inside, and the search's own budget.
    """

    parts: tuple[PlacementPart, ...]
    nets: tuple[PlacementNet, ...] = ()
    relations: tuple[PlacementRelation, ...] = ()
    #: The parts that form the drawing's **chain** (one node per rank, read along
    #: ``progress``). Empty — the default — keeps the historical seed: every part
    #: on one line, which is what every page that compiles today was drawn by.
    #:
    #: When it is stated, :func:`_seed` walks the chain in rank order and **folds**
    #: it: a ``right-of`` / ``left-of`` between the next chain node and the one just
    #: placed turns the walking direction from ``progress`` onto ``lateral``. The
    #: flyback needs exactly this — its chain runs vertically (Q1's column), and
    #: ``right-of(D3, T1)`` asks the secondary branch to leave that column
    #: sideways, which a one-dimensional line cannot do at any weight or pose
    #: (measured: ``outputs/algo_eval/DIAGNOSIS_same_column.md`` §7).
    chain: frozenset[str] = frozenset()
    #: The pins that must keep room for the flag the plan will hang there (201B
    #: stage 2). Empty is a legitimate request — a circuit whose rails carry no
    #: flag symbols states none — and the term is then not evaluated at all.
    flag_seats: tuple[FlagReservation, ...] = ()
    #: Whether two pin tips of **different nets** must keep :data:`PIN_CLEARANCE_GRID`
    #: lattice steps apart (:func:`_pin_clearance_term`). Off by default, because
    #: turning it on for every page is a different question from the bug that put
    #: it here: the topology round is the round that draws a whole circuit from a
    #: grammar, and that is the round whose answer had two foreign tips on one
    #: point. The ladder's pages are drawn by the constructive solver and are not
    #: searched through this term until a batch measures what it costs them.
    #:
    #: Two tips of the **same** net may share a point: a two-pin part joining both
    #: ends to one net is a real (if silly) circuit, and nothing is joined that was
    #: not already joined.
    pin_clearance: bool = False
    #: Price a pin tip sitting inside **another part's** text row
    #: (:func:`_pin_text_term`). Off by default for the same reason
    #: ``pin_clearance`` is: only the topology round states it, so every page the
    #: ladder already draws keeps its cost list — and its answer — byte for byte
    #: (`tools/116_no_move.py` measures exactly that).
    #:
    #: A part's **own** row may cover its own tip and is not priced: a symbol's
    #: anchors and its pins are the library's geometry, not a placement decision.
    #: Measured 2026-10-19: C5, C10, D1 and D3 each declare one legal pose, and
    #: their own value rows already cover their own tips — pricing that is
    #: infeasible on the request's own terms (`experiments/textfit/self_burial.txt`).
    pin_text: bool = False
    progress: tuple[float, float] = (1.0, 0.0)
    lateral: tuple[float, float] = (0.0, 1.0)
    side_preferences: Mapping[str, str] = field(
        default_factory=lambda: dict(DEFAULT_SIDE_PREFERENCES)
    )
    page_box: Box | None = None
    keepouts: tuple[Box, ...] = ()
    grid: float = DEFAULT_GRID
    near_limit: float = DEFAULT_NEAR_LIMIT
    channel: float = DEFAULT_CHANNEL
    lane: float = DEFAULT_LANE
    #: Annealing budget. ``iterations`` is the ceiling per restart; the search
    #: stops early when a sweep makes no progress (see :func:`_anneal`), so a
    #: converged input costs a fraction of it.
    iterations: int = 6000
    #: How many independent searches are run; the best drawing is kept. One
    #: annealing run is a local optimisation and *is* the thing that can get stuck
    #: — three restarts from a fixed ladder of seeds is the cheapest honest answer
    #: to that (and still deterministic: same input, same three seeds, same
    #: answer). ``1`` is one run, for a caller that wants the raw trace.
    restarts: int = 3
    seed: int = 201
    #: The declared two-part series arms this request must seat (548D3). Empty —
    #: the default — is the historical request: no plan is bound, no cost term is
    #: added, and the seed, moves and random trajectory are exactly what they
    #: were. A stated template is a *draw internal* contract, not a public
    #: CircuitSpec/PresentationSpec field: it names the branch, the host pin, the
    #: two parts and their pins, and no absolute coordinate at all. Appended last
    #: on purpose: every existing positional constructor keeps its meaning.
    series_templates: tuple[SeriesSeatTemplate, ...] = ()
    #: The labels' default seats the arm's lane and an ordinary part's yield must
    #: keep out of (548D3B). Empty — the default, and every request that states
    #: none — leaves the lane and the yields exactly as they were: no corridor is
    #: transformed, no candidate is rejected. Appended last for the same reason
    #: ``series_templates`` is.
    label_corridors: tuple[LabelCorridor, ...] = ()
    #: The same-side pin groups whose flags must be seated **jointly** (548D3G).
    #: Empty — the default, and every request that states none — is the historical
    #: request: no corridor is bound, no cost term is added, and the seed, moves
    #: and random trajectory are exactly what they were. A stated template is a
    #: *draw internal* contract like ``series_templates``: it names the group, the
    #: host and the pins, and carries pin-relative real seats only — no absolute
    #: coordinate, no user lock and no invented reach. Appended last for the same
    #: reason the two fields above are.
    flag_corridors: tuple[FlagCorridorTemplate, ...] = ()
    #: The declared reading panels this request must seat (548D3X3C). Empty —
    #: the default — is the historical request: no plan is bound, no cost term is
    #: added, and the seed, the moves and the random trajectory are exactly what
    #: they were. A stated template is a *draw internal* contract: it names the
    #: group, the host, the cells and their pins, and carries measured relative
    #: boxes only — no absolute coordinate and no user lock. Appended last for
    #: the same reason the three fields above are.
    panel_templates: tuple[PanelSeatTemplate, ...] = ()
    #: The service branches this request seats beside their hosts (548D3S1).
    #: Empty — the default — is the historical request: no plan is bound, no
    #: cost term is added, no move is excluded and the seed/trajectory are
    #: exactly what they were. A stated template is a *draw internal* contract:
    #: one cell, its real pins/net/pose/text/flag boxes and the side it reads
    #: on — no absolute coordinate and no user lock.
    service_templates: tuple[ServiceSeatTemplate, ...] = ()
    #: Whether the service seats may be **re-ordered** against each other and
    #: whether one seat's room may treat another seat's branch as its own
    #: (§548D3C1's joint seat). Off — the default, and every page that does not
    #: state it — is the legacy binder byte for byte: the declared
    #: ``service_templates`` order, the legacy rung, and a foreign part judged
    #: only against the host and the cell itself. On is the draw layer's own
    #: statement (``serviceLayout`` page settings); it is a placement-internal
    #: contract like the templates themselves, never read from a presentation
    #: here and never serialised: this request carries no ``to_jsonable``.
    service_joint_order: bool = False

    def __post_init__(self) -> None:
        if not self.parts:
            raise PlacementError("a placement request with no parts has no answer")
        ids = [part.part_id for part in self.parts]
        if len(set(ids)) != len(ids):
            raise PlacementError("two parts share one id in this request")
        if self.grid <= 0:
            raise PlacementError(f"grid must be positive, got {self.grid!r}")
        if self.iterations < 0:
            raise PlacementError("iterations cannot be negative")
        for part in self.parts:
            for token, net_id in _part_nets(self, part.part_id).items():
                if not net_id:
                    raise PlacementError(f"{part.part_id}.{token} names no net")
        _check_series_templates(self)
        _check_flag_corridors(self)
        _check_service_templates(self)

    def part(self, part_id: str) -> PlacementPart:
        for part in self.parts:
            if part.part_id == part_id:
                return part
        raise PlacementError(f"{part_id} is not one of this request's parts")

    def part_ids(self) -> tuple[str, ...]:
        return tuple(sorted(part.part_id for part in self.parts))

    def locked_origins(self) -> dict[str, tuple[float, float]]:
        """``part id -> the point its lock pins it to``, for the parts that name one.

        Read once by the seed's snap and by the moves themselves; a part absent
        here is a part the search may place.
        """
        return {
            part.part_id: part.locked_origin
            for part in self.parts
            if part.locked_origin is not None
        }


def _part_nets(request: PlacementInput, part_id: str) -> dict[str, str]:
    """``pin token -> net id`` for one part, read off the netlist.

    The same reading the grammar makes (``grammar.base.pins_of_part``): one
    source — the netlist — so the pins the relations are measured between and the
    pins the wiring term pulls together can never be two different sets.
    """
    out: dict[str, str] = {}
    for net in request.nets:
        for owner, pin in net.members:
            if owner == part_id and pin:
                out.setdefault(pin, net.net_id)
    return out


# ----------------------------------------------------------------- the output


@dataclass(frozen=True)
class CostTerm:
    """One named term of the cost function: what it is, what it is worth, why.

    The report shape 052 sec.6 fixes: a raw value and a reason, in one line, with
    no cross-layer total hidden inside. ``hard`` says which side of the contract
    the term sits on — the three that may veto a drawing (page, keep-out,
    overlap) are hard; everything else is a promise being *traded*, not checked.
    """

    name: str
    value: float
    detail: str = ""
    hard: bool = False

    @property
    def violated(self) -> bool:
        return self.value > 1e-9

    def render(self) -> str:
        flag = "hard" if self.hard else "soft"
        line = f"[{flag}] {self.name} = {self.value:g}"
        return f"{line} — {self.detail}" if self.detail else line

    def to_jsonable(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "detail": self.detail,
                "hard": self.hard}


@dataclass
class PlacementResult:
    """Where every part went, and the numbers the decision was made from."""

    origins: dict[str, tuple[float, float]]
    poses: dict[str, SymbolPose]
    costs: list[CostTerm] = field(default_factory=list)
    iterations: int = 0
    accepted: int = 0
    seed: int = 201
    notes: list[str] = field(default_factory=list)
    #: The frozen seat plans this answer was searched under (548D3). Empty on
    #: every request that declares no series arm, which is every historical
    #: request. A stated plan carries the final origins/poses the answer must
    #: match (:meth:`series_mismatches`), the reserved boxes and who yielded.
    series_plans: tuple[BoundSeriesSeatPlan, ...] = ()
    #: The joint flag seats bound against this answer (548D3G). Empty on every
    #: request that declares no corridor, which is every historical request. A
    #: stated plan carries the chosen seats, their real boxes, the ordinary parts
    #: that yielded and the structured refusal when the group could not be
    #: seated (:meth:`flag_corridor_mismatches`).
    flag_corridors: tuple[BoundFlagCorridorPlan, ...] = ()
    #: The panel seats bound against this answer (548D3X3C). Empty on every
    #: request that declares no panel, which is every historical request. A
    #: stated plan carries each cell's origin/pose/seat points, its reserved
    #: part/text/flag room and the host leads, or a structured refusal
    #: (:meth:`panel_mismatches`).
    panel_plans: tuple[BoundPanelSeatPlan, ...] = ()
    #: The service seats bound against this answer (548D3S1). Empty on every
    #: request that declares none, which is every historical request. The plans
    #: have the panel plan's shape but are never mixed into ``panel_plans``: the
    #: draw consumer must not mistake a service branch for a panel terminal.
    service_plans: tuple[BoundPanelSeatPlan, ...] = ()

    def term(self, name: str) -> CostTerm | None:
        for item in self.costs:
            if item.name == name:
                return item
        return None

    def series_plan(self, branch_id: str) -> BoundSeriesSeatPlan | None:
        for plan in self.series_plans:
            if plan.branch_id == branch_id:
                return plan
        return None

    def series_mismatches(self) -> tuple[str, ...]:
        """Every way the answer disagrees with its bound seat plans.

        Empty is the only answer a consumer may treat as seated. A refusal plan
        reports its own ``layout-unsat`` line here, so a caller never sees an
        empty list for an arm that was not built.
        """
        out: list[str] = []
        for plan in self.series_plans:
            out.extend(plan.mismatches(self.origins, self.poses))
        return tuple(out)

    def flag_corridor(self, group_id: str) -> BoundFlagCorridorPlan | None:
        for plan in self.flag_corridors:
            if plan.group_id == group_id:
                return plan
        return None

    def flag_corridor_mismatches(self) -> tuple[str, ...]:
        """Every way the answer disagrees with its bound corridors.

        Empty is the only answer a consumer may treat as seated. A refused plan
        reports its own ``layout-unsat`` line here, so a caller never sees an
        empty list for a group that was not seated.
        """
        out: list[str] = []
        for plan in self.flag_corridors:
            out.extend(plan.mismatches(self.origins, self.poses))
        return tuple(out)

    def panel_plan(self, group_id: str) -> BoundPanelSeatPlan | None:
        for plan in self.panel_plans:
            if plan.group_id == group_id:
                return plan
        return None

    def panel_mismatches(self) -> tuple[str, ...]:
        """Every way the answer disagrees with its bound panel seats.

        Empty means every cell sits at its plan's origin, in its plan's pose; a
        refusal plan reports its own named line here, so "no mismatches" can
        never be read off a panel that was not built.
        """
        out: list[str] = []
        for plan in self.panel_plans:
            out.extend(plan.mismatches(self.origins, self.poses))
        return tuple(out)

    @property
    def hard(self) -> list[CostTerm]:
        return [item for item in self.costs if item.hard and item.violated]

    @property
    def soft(self) -> list[CostTerm]:
        return [item for item in self.costs if not item.hard and item.violated]

    @property
    def relations_held(self) -> bool:
        return not any(
            item.violated for item in self.costs if item.name.startswith("relation:")
        )

    def placement(self) -> dict[str, tuple[float, float, float, bool]]:
        """``part_id -> (x, y, rotation, mirror)`` — the task book's own answer."""
        return {
            part_id: (
                self.origins[part_id][0], self.origins[part_id][1],
                float(self.poses[part_id].rotation), self.poses[part_id].mirror,
            )
            for part_id in sorted(self.origins)
        }

    def to_jsonable(self) -> dict[str, Any]:
        body = {
            "kind": PLACEMENT_NAME,
            "seed": self.seed,
            "iterations": self.iterations,
            "accepted": self.accepted,
            "placement": [
                {"partId": part_id, "x": x, "y": y, "rotation": rotation,
                 "mirror": mirror}
                for part_id, (x, y, rotation, mirror)
                in sorted(self.placement().items())
            ],
            "costs": [item.to_jsonable() for item in self.costs],
            "hardViolations": [item.render() for item in self.hard],
            "softViolations": [item.render() for item in self.soft],
            "notes": list(self.notes),
        }
        # A request that declares no arm keeps its published JSON byte for byte:
        # the key appears only when there is a plan to report.
        if self.series_plans:
            body["seriesPlans"] = [plan.to_jsonable() for plan in self.series_plans]
        if self.flag_corridors:
            body["flagCorridors"] = [
                plan.to_jsonable() for plan in self.flag_corridors
            ]
        if self.panel_plans:
            body["panelPlans"] = [
                {
                    "groupId": plan.group_id,
                    "hostPart": plan.host_part,
                    "side": plan.side,
                    "columns": plan.columns,
                    "cells": [
                        {
                            "partId": cell.part_id,
                            "origin": None if cell.origin is None else list(cell.origin),
                            "pose": None if cell.pose is None else cell.pose.label(),
                            "fromSeat": None if cell.from_seat is None else list(cell.from_seat),
                            "toSeat": None if cell.to_seat is None else list(cell.to_seat),
                            "reserved": [list(box) for box in cell.reserved],
                            "hostPath": [list(point) for point in cell.host_path],
                        }
                        for cell in plan.cells
                    ],
                    "refusal": (
                        None if plan.refusal is None
                        else {"detail": plan.refusal.detail,
                              "action": plan.refusal.action}
                    ),
                }
                for plan in self.panel_plans
            ]
        return body


# ------------------------------------------------------------- the geometry


def posed_tip(
    pin_tip: tuple[float, float], pose: SymbolPose, origin: tuple[float, float]
) -> tuple[float, float]:
    """A pin's tip in page coordinates — ``core.geometry``'s one transform."""
    return transform_point(
        pin_tip[0], pin_tip[1], rotation=pose.rotation, mirror=pose.mirror,
        ox=origin[0], oy=origin[1],
    )


def part_box(
    profile: SymbolProfile, pose: SymbolPose, origin: tuple[float, float]
) -> Box:
    """What the part occupies: its drawn body and every pin tip, bounded.

    The same box ``drawcompiler._part_box`` builds, for the same reason: the body
    is what may not overlap another body, and the pin tips are where the wires
    arrive.
    """
    xs: list[float] = []
    ys: list[float] = []
    body = pose_box(profile.body, rotation=pose.rotation, mirror=pose.mirror,
                    ox=origin[0], oy=origin[1])
    if body is not None:
        xs.extend((body[0], body[2]))
        ys.extend((body[1], body[3]))
    for pin in profile.pins:
        point = posed_tip(pin.tip, pose, origin)
        xs.append(point[0])
        ys.append(point[1])
    if not xs:
        return (origin[0], origin[1], origin[0], origin[1])
    return (min(xs), min(ys), max(xs), max(ys))


def _boxes_overlap(first: Box, second: Box) -> float:
    """The area two boxes share, or 0.0 — touching is not overlapping."""
    width = min(first[2], second[2]) - max(first[0], second[0])
    height = min(first[3], second[3]) - max(first[1], second[1])
    if width <= 0.0 or height <= 0.0:
        return 0.0
    return width * height


# --------------------------------------------------------------- the ruler


def shared_net_order(
    nets_here: Iterable[str],
    nets_there: Iterable[str],
    class_of: Callable[[str], str] | None = None,
) -> list[str]:
    """The nets two parts share, in the order this compiler reads them (547S).

    A two-terminal branch frequently shares **two** nets with its owner: the
    signal it serves and the rail it returns to. Reading the sorted first one
    picked the rail on every page whose rail id sorts first — ``3V3`` before
    ``KEY1``, ``GND`` before ``LED1`` — and that single reading is used for
    everything downstream: which pin the branch is seated from, which pin its
    ``near`` is measured on, and which pin its lane edge is levelled on. Two of
    those three used to be computed inline in `drawcompiler` with the same
    ``sorted(...)[0]``, so the seat and the ruler could disagree about the same
    branch.

    **The contract**, in three bands:

    1. a net the circuit declares as a signal (a class that is neither
       ``power``, ``gnd`` nor undeclared) comes first;
    2. then every **other non-``gnd``** common net, in the old sorted order —
       this is what keeps ``VCC``+``GND`` on ``VCC`` and an undeclared net +
       ``GND`` on the undeclared one, exactly as the old ``_shared_nets``
       "prefer a non-return net" rule did;
    3. **``gnd`` last**, whatever it sorts as.

    With no class declared at all (``class_of`` answering nothing) the answer is
    the old ``sorted(...)`` list band for band, which is the "undeclared keeps
    the old behaviour" half of the contract and what keeps the pages without a
    rail/signal ambiguity byte-identical.

    The mistake this shape fixes: a first version returned sorted order whenever
    no *signal* net was in common, which silently swapped ``VCC``+``GND`` to
    ``GND`` — a decoupling anchor on the wrong node. "No signal" is not "no
    preference": the old rule preferred any non-ground, and that half is kept.

    ``class_of`` is ``None`` only for callers that hold no netlist; those get the
    old order verbatim, which is the behaviour this batch must not change for
    anything that does not pass a resolver.
    """
    common = sorted(set(nets_here) & set(nets_there))
    if class_of is None:
        return common
    signal = [net for net in common if _is_signal_class(class_of(net))]
    other = [
        net for net in common
        if net not in signal and class_of(net) != "gnd"
    ]
    ground = [
        net for net in common
        if net not in signal and class_of(net) == "gnd"
    ]
    return signal + other + ground


def _is_signal_class(cls: str) -> bool:
    """Is this declared class a *signal* (never a rail, never undeclared)?"""
    return bool(cls) and cls not in ("power", "gnd")


def relation_points(
    request: PlacementInput,
    relation: PlacementRelation,
    pins: Mapping[str, Mapping[str, tuple[float, float]]],
    origins: Mapping[str, tuple[float, float]],
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """The two points a relation is measured between, for one in-module search.

    A thin reading of :func:`relation_points_between` over this module's own
    state: one implementation, two ways of handing it the parts (the search has a
    state, the compiler has two callables). 547S: the search passes the netlist's
    own classes, so the net it measures a branch on is the net the compiler
    seated it from — the two readings of one sentence cannot diverge.
    """
    classes = {net.net_id: net.cls for net in request.nets}
    return relation_points_between(
        relation,
        nets_of=lambda part_id: _part_nets(request, part_id),
        origin_of=lambda part_id: origins.get(part_id),
        pin_of=lambda part_id, token: (pins.get(part_id) or {}).get(token),
        class_of=lambda net_id: classes.get(net_id, ""),
    )


def relation_points_between(
    relation: Any,
    *,
    nets_of: Any,
    origin_of: Any,
    pin_of: Any,
    class_of: Callable[[str], str] | None = None,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """The two points a relation is measured between — **the one reading**.

    Origins, except for the five kinds ``grammar/base.py`` measures between the
    pair's **pins on the net they share** — a branch belongs to the node its own
    pin sits on, and a tap is a junction between two arm pins. This is
    ``drawcompiler._points_for_relation``'s own rule, moved here in 201B so that
    the layer that *places* the parts and the layer that *grades* the finished
    plan cannot be two rulers for one word (they were for the length of stage 1:
    the same sentence measured twice by two copies of one rule).

    The three callables are the whole interface because the two callers hold
    their parts differently — the search holds a state, the compiler holds the
    CircuitSpec and a profile — and a signature that took either would have made
    the other convert, which is how a second rule grows back.
    ``nets_of(part_id)`` is that part's ``pin token -> net id``; ``origin_of``
    and ``pin_of(part_id, token)`` are the two points.

    Which pin pair a kind is measured between is part of the answer, so it is
    written out exactly as the compiler wrote it: the **first** token in sorted
    order on the **first net in :func:`shared_net_order`** that has a point at
    each end. A version that kept looking for a token whose point existed would
    be more forgiving than the compiler by exactly the cases this rule is most
    likely to be asked about.

    547S: ``class_of`` is the netlist's declared class, and it is what makes
    this ruler read the *same* shared net the placement seated the branch from —
    a branch that shares its signal and a rail is measured on the signal, not on
    whichever id sorts first. ``None`` keeps the old sorted reading for any
    caller that has no netlist to hand.
    """
    if relation.kind in _PIN_KINDS:
        subject_nets = nets_of(relation.subject)
        object_nets = nets_of(relation.object)
        shared = shared_net_order(
            subject_nets.values(), object_nets.values(), class_of,
        )
        for net_id in shared:
            here = _pin_on_net(subject_nets, relation.subject, net_id, pin_of)
            there = _pin_on_net(object_nets, relation.object, net_id, pin_of)
            if here is not None and there is not None:
                return (here, there)
    here = origin_of(relation.subject)
    there = origin_of(relation.object)
    if here is None or there is None:
        return None
    return (here, there)


def _pin_on_net(
    nets: Mapping[str, str],
    part_id: str,
    net_id: str,
    pin_of: Any,
) -> tuple[float, float] | None:
    """This part's pin on that net — the **lowest-numbered** one when it has two.

    One pin per (part, net) is a promise the grammar makes, not a hope here — and
    when it is broken this picks the same one the compiler's ``_token_on`` picks
    (the first in sorted-token order), so the two readings cannot disagree about
    which pin a ``same-column`` is measured between.
    """
    for token in sorted(nets):
        if nets[token] == net_id:
            return pin_of(part_id, token)
    return None


def relation_holds(
    kind: str,
    points: tuple[tuple[float, float], tuple[float, float]],
    *,
    grid: float,
    near_limit: float,
    lateral: tuple[float, float],
    progress: tuple[float, float],
) -> bool:
    """Does one relation hold between two points?

    Every kind is read through ``grammar/base.py``'s own definition, with the
    grid tolerance the readability checker treats as "the same column or row"
    (``grid / 2``) — the same number the compiler's ``_relation_holds`` uses, so a
    relation this module keeps is never reported broken by the layer measuring
    the finished plan.
    """
    (ax, ay), (bx, by) = points
    slack = grid / 2.0
    if kind in (SAME_COLUMN, HORIZONTAL_TAP):
        return abs(ax - bx) <= slack
    if kind in (SAME_ROW, VERTICAL_TAP):
        return abs(ay - by) <= slack
    if kind == ABOVE:
        return ay >= by + slack
    if kind == BELOW:
        return ay <= by - slack
    if kind == LEFT_OF:
        return ax <= bx - slack
    if kind == RIGHT_OF:
        return ax >= bx + slack
    if kind == ADJACENT:
        gap = (ax - bx, ay - by)
        return abs(_dot(gap, lateral)) <= slack and not _close(
            _dot(gap, progress), 0.0
        )
    if kind == NEAR:
        return math.hypot(ax - bx, ay - by) <= near_limit
    return False


def relation_miss(
    kind: str,
    points: tuple[tuple[float, float], tuple[float, float]],
    *,
    grid: float,
    near_limit: float,
    lateral: tuple[float, float],
    progress: tuple[float, float],
) -> float:
    """How far apart the pair is from keeping the relation — 0.0 when it holds.

    A **distance in canvas units**, not a flag: "20 units to the left of where
    ``same-column`` wants it" is an instruction the repair move can act on and a
    reader can check, while "violated" is not. It is defined so that
    ``relation_miss(...) == 0`` is exactly ``relation_holds(...)``: the two are
    computed from the same branch of the same kind, and the test file pins that
    equivalence across all ten kinds.
    """
    (ax, ay), (bx, by) = points
    slack = grid / 2.0
    if kind in (SAME_COLUMN, HORIZONTAL_TAP):
        return max(0.0, abs(ax - bx) - slack)
    if kind in (SAME_ROW, VERTICAL_TAP):
        return max(0.0, abs(ay - by) - slack)
    if kind == ABOVE:
        return max(0.0, (by + slack) - ay)
    if kind == BELOW:
        return max(0.0, ay + slack - by)
    if kind == LEFT_OF:
        return max(0.0, (ax + slack) - bx)
    if kind == RIGHT_OF:
        return max(0.0, (bx + slack) - ax)
    if kind == ADJACENT:
        gap = (ax - bx, ay - by)
        along = abs(_dot(gap, lateral))
        if along > slack:
            return along - slack
        # The line coordinate uses the same sign convention the four order kinds
        # keep: the miss is the distance *out of* the half-plane the relation
        # asks for, so 0 is exactly `holds` true and a positive number is `holds`
        # false — the two functions cannot disagree at the boundary any more.
        return 0.0 if not _close(_dot(gap, progress), 0.0) else 1.0
    if kind == NEAR:
        return max(0.0, math.hypot(ax - bx, ay - by) - near_limit)
    return float("inf")


def _dot(first: tuple[float, float], second: tuple[float, float]) -> float:
    return first[0] * second[0] + first[1] * second[1]


def _close(first: float, second: float, tolerance: float = 10.0 ** -9) -> bool:
    return abs(first - second) <= tolerance


# ------------------------------------------------------------ the cost list


@dataclass
class _State:
    """One point in the search: where each part's origin is, and its pose."""

    origins: dict[str, tuple[float, float]]
    poses: dict[str, SymbolPose]


def _pins_of(
    request: PlacementInput, state: _State
) -> dict[str, dict[str, tuple[float, float]]]:
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for part in request.parts:
        profile = part.profile
        pose = state.poses[part.part_id]
        origin = state.origins[part.part_id]
        out[part.part_id] = {
            pin.number: posed_tip(pin.tip, pose, origin) for pin in profile.pins
        }
    return out


def _boxes_of(request: PlacementInput, state: _State) -> dict[str, Box]:
    return {
        part.part_id: part_box(
            part.profile, state.poses[part.part_id], state.origins[part.part_id]
        )
        for part in request.parts
    }


def _net_pin_points(
    request: PlacementInput,
    pins: Mapping[str, Mapping[str, tuple[float, float]]],
) -> dict[str, list[tuple[float, float]]]:
    """``net -> the pin points on it``, for the nets the wiring term measures.

    A net with one connected pin says nothing about wiring (there is nothing to
    connect it to), so it is not a term at all — the same reason the compiler's
    own obligation checker exempts a one-pin net.
    """
    out: dict[str, list[tuple[float, float]]] = {}
    for net in request.nets:
        points = [
            pins[owner][pin]
            for owner, pin in net.members
            if owner in pins and pin in pins[owner]
        ]
        if len(points) >= 2:
            out.setdefault(net.net_id, []).extend(points)
    return out


def _side_goals(request: PlacementInput) -> dict[str, str]:
    """``part_id -> the one side its nets agree on``, from their own classes.

    Concept 1's price list. A ``power`` rail's parts are pulled up and a ``gnd``
    family's down (060's flag convention); a part whose nets disagree — the
    transformer belongs to both a rail and a ground family by construction — has
    **no** goal and is placed by its relations alone, which is the honest answer:
    the drawing, not this term, decides where the middle of a converter goes.

    The specification's own ``portRoles`` were tried here (HVDC is an *input*,
    so its parts want the left) and **measured worse**: on the flyback it fought
    the relations' own statement of the same thing and the drawing's spread grew
    from 478 to 824 units with the wiring from 1595 to 3240. A term that loses to
    the rule it was meant to sharpen is not kept because it sounds right.
    """
    goals: dict[str, str] = {}
    for part in request.parts:
        votes: dict[str, int] = {}
        for token, net_id in sorted(_part_nets(request, part.part_id).items()):
            side = request.side_preferences.get(_net_class(request, net_id), "")
            if side:
                votes[side] = votes.get(side, 0) + 1
        if not votes:
            continue
        best = max(sorted(votes), key=lambda side: votes[side])
        if list(votes.values()).count(votes[best]) == 1:
            goals[part.part_id] = best
    return goals


def _net_class(request: PlacementInput, net_id: str) -> str:
    for net in request.nets:
        if net.net_id == net_id:
            return net.cls
    return ""


def _escapes(
    request: PlacementInput, state: _State
) -> dict[str, dict[str, tuple[float, float]]]:
    """``part -> pin -> the unit direction that pin leaves its body in``.

    Read from the symbol's own ``direction`` and turned by the part's pose (the
    linear half of the one transform every coordinate goes through), because a
    pin's direction is geometry the library already stated. A pin whose direction
    the profile does not state falls back to the radial direction — from the
    part's **body centre** to the tip — which is what "which way does this pad
    leave the package" means when the file does not say.
    """
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for part in request.parts:
        pose = state.poses[part.part_id]
        origin = state.origins[part.part_id]
        body = pose_box(part.profile.body, rotation=pose.rotation,
                        mirror=pose.mirror, ox=origin[0], oy=origin[1])
        centre = (
            ((body[0] + body[2]) / 2.0, (body[1] + body[3]) / 2.0)
            if body is not None else origin
        )
        here: dict[str, tuple[float, float]] = {}
        for pin in part.profile.pins:
            local = {
                "left": (-1.0, 0.0), "right": (1.0, 0.0),
                "up": (0.0, 1.0), "down": (0.0, -1.0),
            }.get(pin.direction)
            if local is None:
                tip = posed_tip(pin.tip, pose, origin)
                local = (tip[0] - centre[0], tip[1] - centre[1])
            sideways = posed_tip(local, pose, (0.0, 0.0))
            length = math.hypot(sideways[0], sideways[1])
            here[pin.number] = (
                (sideways[0] / length, sideways[1] / length)
                if length > 0.0 else (0.0, 0.0)
            )
        out[part.part_id] = here
    return out


def _facing_term(
    request: PlacementInput,
    state: _State,
    pins: Mapping[str, Mapping[str, tuple[float, float]]],
) -> CostTerm:
    """How much of a part's own wiring leaves its **back** — concept 3, priced.

    The wiring term above measures where a net's pins are, and a pin set's extent
    does not care which pin is which: an optocoupler mirrored or not has the same
    half-perimeter, so a search that only minimised wiring would never turn it
    round, and the drawing would show its LED side plugged into the primary. This
    term reads the **pin identity**: for every pin on a net with something else on
    it, the vector to the other pins' centroid is compared with the direction the
    pin leaves its body in, and a pin pointing away pays the distance it is from
    what it connects to.

    Weighted like the wiring term, because it is the same question asked the other
    way round ("is this pin *facing* the node" against "is this node *small*") —
    and, like every soft term here, it can never outbid a relation (10 per unit).
    """
    escapes = _escapes(request, state)
    net_points = _net_pin_points(request, pins)
    total = 0.0
    worst = ("", 0.0)
    for net in request.nets:
        points = net_points.get(net.net_id)
        if not points or len(points) < 2:
            continue
        members = [
            (owner, pin) for owner, pin in net.members
            if owner in pins and pin in pins[owner]
        ]
        for owner, pin in members:
            others = [
                pins[other][other_pin]
                for other, other_pin in members
                if (other, other_pin) != (owner, pin)
            ]
            if not others:
                continue
            centroid = (
                sum(point[0] for point in others) / len(others),
                sum(point[1] for point in others) / len(others),
            )
            tip = pins[owner][pin]
            gap = (centroid[0] - tip[0], centroid[1] - tip[1])
            distance = math.hypot(gap[0], gap[1])
            if distance <= request.grid:
                continue
            escape = escapes.get(owner, {}).get(pin, (0.0, 0.0))
            cos = _dot(escape, (gap[0] / distance, gap[1] / distance))
            if cos >= 0.0:
                continue
            total += -cos * distance
            if -cos * distance > worst[1]:
                worst = (f"{owner}.{pin} on {net.net_id}", -cos * distance)
    return CostTerm(
        "pin-facing", total,
        "how far the pins that leave a part's back are from what they connect to "
        + (f"— the worst is {worst[0]} at {worst[1]:g} units" if worst[1] > 0.0
           else "— every pin faces its own net"),
    )


def _drawing_box(boxes: Mapping[str, Box]) -> Box | None:
    if not boxes:
        return None
    return (
        min(box[0] for box in boxes.values()),
        min(box[1] for box in boxes.values()),
        max(box[2] for box in boxes.values()),
        max(box[3] for box in boxes.values()),
    )


def _middle_of(request: PlacementInput, boxes: Mapping[str, Box]) -> tuple[float, float]:
    """What "its own side" is measured against.

    The **sheet's** middle when a page is stated, and the **drawing's own** middle
    otherwise — the compiler's own reading of a budget with no page
    (``CompileBudget.page_box = None`` means "the drawing defines its own frame,
    and the page half is not evaluated"), kept as one rule rather than two
    definitions of "the middle".
    """
    frame = request.page_box if request.page_box is not None else _drawing_box(boxes)
    if frame is None:
        return (0.0, 0.0)
    return ((frame[0] + frame[2]) / 2.0, (frame[1] + frame[3]) / 2.0)


def evaluate(
    request: PlacementInput,
    state: _State,
    plans: Sequence[BoundSeriesSeatPlan] = (),
    panels: Sequence[BoundPanelSeatPlan] = (),
    services: Sequence[BoundPanelSeatPlan] = (),
) -> list[CostTerm]:
    """The whole cost function, as named terms.

    Every term is returned — including the ones at zero — because "which promise
    did not cost anything" is part of what a reader is checking. The search sums
    them through :func:`_energy`; nothing else reads the sum.

    ``plans`` are the seat plans bound once after the ordinary seed
    (:func:`_bind_series_plans`). They are passed in rather than rebound here on
    purpose: the pitch is frozen for every restart, so re-measuring it from the
    state being evaluated would be a second seat equation. The default is empty,
    and an empty list adds no term at all — the historical cost list is
    unchanged.
    """
    pins = _pins_of(request, state)
    boxes = _boxes_of(request, state)
    out: list[CostTerm] = []

    # 1. the relations: the grammar's promises, priced one by one.
    for relation in request.relations:
        points = relation_points(request, relation, pins, state.origins)
        if points is None:
            out.append(CostTerm(
                name=f"relation:{relation.label()}", value=0.0,
                detail="not measurable — one endpoint is not placed",
            ))
            continue
        miss = relation_miss(
            relation.kind, points, grid=request.grid,
            near_limit=request.near_limit, lateral=request.lateral,
            progress=request.progress,
        )
        detail = (
            "kept: measured between " + _point_text(points[0]) + " and "
            + _point_text(points[1])
            if miss <= 0.0 else
            f"missed by {miss:g} units between {_point_text(points[0])} and "
            f"{_point_text(points[1])} — the grammar's reason is "
            f"{relation.reason!r}"
        )
        out.append(CostTerm(f"relation:{relation.label()}", miss, detail))

    # 2. the wiring: every net's own spread (concept 2 — clusters, not shelves).
    net_points = _net_pin_points(request, pins)
    total_wire = 0.0
    worst = ("", 0.0)
    for net_id in sorted(net_points):
        points = net_points[net_id]
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        reach = (max(xs) - min(xs)) + (max(ys) - min(ys))
        total_wire += reach
        if reach > worst[1]:
            worst = (net_id, reach)
    out.append(CostTerm(
        "wire-length", total_wire,
        f"half-perimeter of every net with two or more pins, summed over "
        f"{len(net_points)} net(s); the widest is {worst[0] or '—'} at "
        f"{worst[1]:g} units",
    ))

    # 2b. the poses: does each pin point at what it connects to? (concept 3)
    out.append(_facing_term(request, state, pins))

    # 3. the direction: each part's own side, from its nets' statements.
    goals = _side_goals(request)
    total_side = 0.0
    offenders: list[str] = []
    middle = _middle_of(request, boxes)
    for part_id in sorted(goals):
        side = goals[part_id]
        box = boxes[part_id]
        centre = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
        vector = _SIDE_VECTORS[side]
        depth = _dot((centre[0] - middle[0], centre[1] - middle[1]), vector)
        if depth < 0.0:
            total_side += -depth
            offenders.append(f"{part_id} ({side}, {abs(depth):g} units short)")
    out.append(CostTerm(
        "flow-side", total_side,
        "how far the parts whose nets name a side sit from that side "
        + ("— " + "; ".join(sorted(offenders)[:5]) if offenders
           else "— every side-preferring part is on its own side"),
    ))

    # 4. compactness: the drawing's own extent, a tie-breaker with a small
    #    weight (it must never outbid a relation).
    drawn = _drawing_box(boxes)
    spread = (
        math.hypot(drawn[2] - drawn[0], drawn[3] - drawn[1])
        if drawn is not None else 0.0
    )
    out.append(CostTerm("spread", spread, "the drawn extent's diagonal"))

    # 4b. the air the plan's own text needs (see TEXT_CLEARANCE).
    out.append(_clearance_term(boxes))

    # 4c. the room the plan's own flags need at the pins they hang from.
    out.append(_flag_room_term(request, pins, boxes))

    # 4d. the air two **foreign** pin tips need (see PIN_CLEARANCE_GRID). Only
    #     when the request asks for it: the topology round does, and every page
    #     the ladder draws keeps its cost list byte for byte.
    if request.pin_clearance:
        out.append(_pin_clearance_term(request, pins))

    # 4e. the same tip test, against **text rows** instead of tips (see
    #     W_PIN_TEXT). A neighbour's designator/value row is drawn where its
    #     symbol says, so a tip inside one is a tip the router cannot land on.
    if request.pin_text:
        out.append(_pin_text_term(request, state, pins))

    # 5. the three hard ones.
    out.append(_page_term(request, boxes))
    out.append(_keepout_term(request, boxes))
    out.append(_overlap_term(boxes))

    # 6. a declared series arm's reserved boxes are hard too: an ordinary part
    #    standing in one is not a crowded drawing to trade, it is a drawing that
    #    contradicts its own declaration. No plan, no term — the historical cost
    #    list ends at the three above.
    out.extend(_series_reservation_terms(request, state, plans, boxes))
    # 7. the same for a declared panel (548D3X3C): its reserved part/text/flag
    #    room is hard, so a foreign part standing in it is a refusal to name, not
    #    a crowded drawing to trade. No plan, no term.
    out.extend(_panel_reservation_terms(request, boxes, panels))
    out.extend(_panel_reservation_terms(request, boxes, services, kind="service"))
    return out


def _page_term(request: PlacementInput, boxes: Mapping[str, Box]) -> CostTerm:
    if request.page_box is None:
        return CostTerm(
            "page", 0.0, "no page was stated, so the page half is not evaluated",
            hard=True,
        )
    page = request.page_box
    total = 0.0
    worst = ""
    for part_id in sorted(boxes):
        box = boxes[part_id]
        out = (
            max(0.0, page[0] - box[0]) + max(0.0, box[2] - page[2])
            + max(0.0, page[1] - box[1]) + max(0.0, box[3] - page[3])
        )
        if out > 0.0:
            total += out
            if not worst:
                worst = f"{part_id} by {out:g} units"
    return CostTerm(
        "out-of-page", total,
        "nothing leaves the sheet" if total <= 0.0
        else f"outside {list(map(float, page))}: {worst}",
        hard=True,
    )


def _keepout_term(request: PlacementInput, boxes: Mapping[str, Box]) -> CostTerm:
    total = 0.0
    worst = ""
    for part_id in sorted(boxes):
        for keep in request.keepouts:
            area = _boxes_overlap(boxes[part_id], keep)
            if area > 0.0:
                total += area
                if not worst:
                    worst = f"{part_id} against {list(map(float, keep))}"
    return CostTerm(
        "keepout", total,
        "nothing sits on a keep-out" if total <= 0.0 else f"on a keep-out: {worst}",
        hard=True,
    )


def _overlap_term(boxes: Mapping[str, Box]) -> CostTerm:
    ids = sorted(boxes)
    total = 0.0
    worst = ""
    for index, first in enumerate(ids):
        for second in ids[index + 1:]:
            area = _boxes_overlap(boxes[first], boxes[second])
            if area > 0.0:
                total += area
                if not worst:
                    worst = f"{first}/{second} by {area:g} units²"
    return CostTerm(
        "overlap", total,
        "no two parts share area" if total <= 0.0 else f"overlapping: {worst}",
        hard=True,
    )


def _priced_seats(
    seats: tuple[FlagReservation, ...],
) -> tuple[FlagReservation, ...]:
    """One seat per net: its ladder's head, in the order the request states it.

    The compiler states every rung of a net's seat ladder (515A-⑥); a net's later
    rungs are the fallbacks for the *same* flag, so the room is priced once, at
    the rung the ladder prefers. Order-preserving on purpose: the request is
    built net-by-net in the compiler's own ladder order, so the first statement
    of a net is the head of the same ladder the draw pass walks.
    """
    seen: set[str] = set()
    out: list[FlagReservation] = []
    for seat in seats:
        if seat.net_id in seen:
            continue
        seen.add(seat.net_id)
        out.append(seat)
    return tuple(out)


def _flag_room_term(
    request: PlacementInput,
    pins: Mapping[str, Mapping[str, tuple[float, float]]],
    boxes: Mapping[str, Box],
) -> CostTerm:
    """How much of the room the plan's own flags need is taken by parts.

    The compiler hangs a rail's flag at the pin the rail supplies and draws it as
    a vertical run out of that pin; the placement search cannot see the flag (it
    is stage 3b's), so the room is handed to it as data
    (:class:`FlagReservation`) and priced here: **the area of other parts that
    stands inside the reservation**.

    Measured, and the reason this term exists: on the flyback the search reached a
    drawing with *zero* readability violations and the flag stage then refused it
    — `HVDC`'s flag had no legal seat at `T1.1`, because parts stood in the lead's
    corridor and in the glyph's box. Three global-spacing settings were tried
    instead of this term (15 / 25 / 40 units of clearance: "0 violations but no seat",
    "23 text overlaps", "the direct wire no longer routes") — a global scale cannot
    make room at one pin, which is what a reservation at that pin is for.

    Soft, like every other term but the three hard ones: a crowded flag position
    is a drawing the plan then refuses, and that refusal is the gate's to make —
    this prices it so the search can move the part that is in the way.

    **One seat per net is priced (515A-⑥ follow-up).** The compiler hands over
    **every** rung of its seat ladder (`drawcompiler._flag_seats`), because the
    rung is chosen at draw time on the placed coordinates and nothing may stand
    in the chosen pin's corridor. Those rungs are alternatives for one flag, not
    N flags: pricing each of them would price a room the plan will not use and
    would move drawings that were never crowded (measured: the flyback's topology
    answer moved all 19 parts the moment the extra rungs were summed). So the
    term reads the **first** statement per net, which is the rung the compiler's
    own ladder prefers — the same order the flag pass walks — and prices that.
    Keeping the whole list is not a second judgement: it is the same ladder's own
    fallback, and the list is what lets a drawing whose first rung turns out
    illegal still find its reserved room. One ruler, two uses: the head is priced,
    the tail is covered.
    """
    seats = _priced_seats(request.flag_seats)
    if not seats:
        return CostTerm(
            "flag-room", 0.0,
            "this request states no flag seat, so nothing is reserved",
        )
    total = 0.0
    worst = ("", 0.0)
    for seat in seats:
        pin = (pins.get(seat.part_id) or {}).get(seat.token)
        if pin is None:
            total += 0.0
            continue
        reserved = seat.box_at(pin)
        taken = 0.0
        for part_id in sorted(boxes):
            if part_id == seat.part_id:
                continue
            taken += _boxes_overlap(reserved, boxes[part_id])
        if not taken:
            continue
        total += taken
        if taken > worst[1]:
            worst = (f"{seat.net_id} at {seat.part_id}.{seat.token}", taken)
    return CostTerm(
        "flag-room", total,
        "the area of the parts standing in the room the plan's own flags need "
        + (f"— the worst is {worst[0]} at {worst[1]:g} units² over "
           f"{len(seats)} reserved seat(s)"
           if worst[1] > 0.0 else
           f"— every one of the {len(seats)} seat(s) is clear"),
    )


def _clearance_term(boxes: Mapping[str, Box]) -> CostTerm:
    """How much air neighbouring parts are short of — priced, not enforced.

    Two parts whose extents are closer than :data:`TEXT_CLEARANCE` **along one
    axis** while their spans along the other still face each other have no room
    between them for the designator and value the plan will print beside their
    bodies. This term measures the shortfall and prices it; it is soft because a
    crowded drawing is a *worse* drawing, not an illegal one, and because a hard
    version would refuse every input whose parts genuinely fit no further apart —
    at which point the gate's own text rules are the honest place to say so
    (they measure where the text actually landed; this measures where it *can*).

    Measured on the flyback: without it the search kept all 33 relations with
    nothing overlapping and the readability gate still refused the drawing for 14
    text collisions, every one of them a pair of parts closer than the text they
    carry.
    """
    ids = sorted(boxes)
    total = 0.0
    worst = ("", 0.0)
    for index, first in enumerate(ids):
        for second in ids[index + 1:]:
            a, b = boxes[first], boxes[second]
            gap_x = max(a[0] - b[2], b[0] - a[2])
            gap_y = max(a[1] - b[3], b[1] - a[3])
            if gap_x > 0.0 and gap_y > 0.0:
                continue  # diagonal neighbours: nothing is between them
            short = TEXT_CLEARANCE - max(gap_x, gap_y)
            if short <= 0.0 or gap_x > TEXT_CLEARANCE or gap_y > TEXT_CLEARANCE:
                continue
            total += short
            if short > worst[1]:
                worst = (f"{first}/{second}", short)
    return CostTerm(
        "clearance", total,
        f"how far the neighbouring pairs are short of the {TEXT_CLEARANCE:g} units "
        "the plan's own designator and value rows need "
        + (f"— the tightest is {worst[0]} by {worst[1]:g} units" if worst[0]
           else "— every pair has room"),
    )


def _pin_clearance_term(
    request: PlacementInput,
    pins: Mapping[str, Mapping[str, tuple[float, float]]],
) -> CostTerm:
    """How close two **foreign** pin tips are to sharing a point — priced.

    The one obstacle the term list could not see. ``overlap`` and ``clearance``
    above measure part **bodies**; a pin tip is a point that may sit on another
    part's body boundary without the boxes sharing any area at all. Two tips of
    different nets on one point is a node the editor reads as a connection, so
    the plan can neither wire through it (`drawcompiler._blocked_points` treats a
    foreign tip as a wall, and a wire vertex on one joins two nets) nor pass
    beside it.

    Measured on the flyback 2026-10-18: `Q1.3` (SRC) and `R5.2` (PGND) at the same
    (75, 165), which is why the `SRC` obligation could not be drawn — "could not
    be joined ... without a wire crossing a body, a text box or a foreign
    connection". Every term in the list read 0 on that answer.

    Two tips on the **same** net are not a short (the connection already exists),
    so they are skipped: a two-pin part with both ends on one net is legal, and
    charging it would make the search move a part for a non-problem. A tip whose
    net the netlist does not state is treated as foreign to everything, the
    conservative reading — nothing in the netlist joins it.
    """
    threshold = request.grid * PIN_CLEARANCE_GRID
    owners: list[tuple[str, str, tuple[float, float], str]] = []
    assignment: dict[tuple[str, str], str] = {}
    for net in request.nets:
        for owner, pin in net.members:
            if owner in pins and pin in pins.get(owner, {}):
                assignment.setdefault((owner, pin), net.net_id)
    for owner in sorted(pins):
        for pin in sorted(pins[owner]):
            owners.append((owner, pin, pins[owner][pin], assignment.get((owner, pin), "")))
    total = 0.0
    worst = ("", 0.0)
    for index, (a_owner, a_pin, a_point, a_net) in enumerate(owners):
        for b_owner, b_pin, b_point, b_net in owners[index + 1:]:
            if a_owner == b_owner:
                # Two pins of one **symbol**: their distance is symbol geometry,
                # not a placement decision — rotation and mirror conserve it and
                # translation cannot change it, so pricing it would put a constant
                # into the energy and buy the search nothing. Measured: the
                # flyback's own transformer keeps `T1.1` and `T1.2` 10 units
                # apart with nothing the placement can do about it, which is what
                # capped the threshold at `grid * 2` while the pair was still
                # counted. The library is the owner of that number, and it is
                # where a drawing that cannot route between them has to be fixed.
                continue
            if a_net and a_net == b_net:
                continue  # the same net may share a point
            gap = math.hypot(a_point[0] - b_point[0], a_point[1] - b_point[1])
            short = threshold - gap
            if short <= 0.0:
                continue
            total += short
            if short > worst[1]:
                pair = (
                    f"{a_owner}.{a_pin} ({a_net or '?'}) and "
                    f"{b_owner}.{b_pin} ({b_net or '?'})"
                )
                worst = (
                    f"{pair} on the same point {_point_text(a_point)}"
                    if gap <= 0.0 else f"{pair} by {gap:g} units",
                    short,
                )
    return CostTerm(
        "pin-clearance", total,
        f"how far the pin tips of different nets are short of the {threshold:g} units "
        "they must keep apart "
        + (f"— the tightest is {worst[0]} ({worst[1]:g} units short)" if worst[0]
           else "— every pair of foreign tips has room"),
    )


def text_rows(
    request: PlacementInput,
    part_id: str,
    origin: tuple[float, float],
    pose: SymbolPose | None = None,
) -> list[tuple[str, str, Box]]:
    """``(kind, text, box)`` for every row this part's **symbol** declares.

    The same reading `drawcompiler._declared_rows` makes, and deliberately so:
    one model of where the host paints, in the module that has to move parts away
    from those rows. The anchor is an offset from the part's origin in the
    **page frame** — the host does not turn a row with the pose (147's
    measurement, `outputs/147/20_text_row_pose.txt`) — and the row is
    :data:`TEXT_ROW_HEIGHT` tall and as wide as the host's own ruler says
    (:func:`boardwise.core.textmetrics.render_width`).

    531 routed the box itself through
    :func:`boardwise.core.textmetrics.symbol_rows` so the three callers of this
    rule (this one, the compiler's, and the island layout's) cannot drift apart:
    the island path had its own invented-position model and its boxes sat 50+
    units from where the host prints (`evidence/531/report.md` §2). The output is
    unchanged, row for row.

    A symbol that declares no anchors returns nothing, and every profile written
    before 146 does: a library without measurements compiles exactly as it did.
    """
    part = request.part(part_id)
    return [
        (kind, text, box)
        for kind, text, box in textmetrics.symbol_rows(
            part.profile, origin, reference=part_id, value=part.value,
            pose=pose,
        )
    ]


def _burial_depth(point: tuple[float, float], box: Box) -> float:
    """How deep inside ``box`` the point sits; ``0`` when it is outside.

    The **least** distance to the four edges: a tip in the row's middle is buried
    by half the row's short side. That gradient is what the search needs (see
    :data:`W_PIN_TEXT`); a flat cost reads the same at every depth.

    A tip **on an edge** counts, at :data:`PIN_TEXT_EDGE`. The router's
    ``_wall`` is `box0 - 1e-6 < x < box2 + 1e-6` — the far edge included — so a
    tip exactly on a row's edge is a wall node there and cannot receive a wire
    end, even though the depth is zero. Measured 2026-10-19: `C5.1` sits on its
    own row's lower edge, and the edge case is what `experiments/textfit/
    self_burial.txt` reports for four symbols. Without the bump the term would
    read 0 for a tip the router refuses, and the search would have no gradient
    to move it (a bare `depth` is 0 at the edge, so the cost would be 0 and the
    move free to ignore).
    """
    depth = min(
        point[0] - box[0], box[2] - point[0],
        point[1] - box[1], box[3] - point[1],
    )
    if depth < 0.0:
        return 0.0
    return depth + PIN_TEXT_EDGE


def _pin_text_term(
    request: PlacementInput,
    state: _State,
    pins: Mapping[str, Mapping[str, tuple[float, float]]],
) -> CostTerm:
    """How deep the pin tips are buried in **another part's** text rows — priced.

    The measured root of "no layout routes". `part_box` is "drawn body + every
    pin tip", so the term list above sees no texts at all and two parts can keep
    every body apart, keep all 33 relations, and still have a neighbour's value
    row cover a pin tip. A tip the router's `_blocked_points` calls a wall can
    never receive a wire end, so the net that owns it is refused however the
    parts are arranged (measured 2026-10-19: **21 of 21** buried tips in another
    part's value row, every one on an obligated net).

    A part's **own** row is not priced: its anchors and its pins are the
    library's geometry, rotation and mirror conserve the relation between them,
    and four of the flyback's symbols (C5, C10, D1, D3) declare one legal pose
    each and already cover their own tips — pricing that is infeasible on the
    request's own terms.
    """
    rows: dict[str, list[tuple[str, str, Box]]] = {}
    for part in request.parts:
        origin = state.origins.get(part.part_id)
        if origin is None:
            rows[part.part_id] = []
            continue
        rows[part.part_id] = text_rows(
            request, part.part_id, origin, pose=state.poses.get(part.part_id),
        )
    if not any(rows.values()):
        return CostTerm(
            "pin-text", 0.0,
            "no part's symbol declares a text row, so there is nothing for a pin "
            "tip to be buried in (the pre-146 library)",
        )
    total = 0.0
    worst = ("", 0.0)
    for owner in sorted(pins):
        for pin in sorted(pins[owner]):
            point = pins[owner][pin]
            for other in sorted(rows):
                if other == owner:
                    # A part's own row may cover its own tip: the anchors and the
                    # pins are the library's geometry, and four symbols of the
                    # flyback declare one pose each with their own row over their
                    # own tip (see the docstring above).
                    continue
                for kind, text, box in rows[other]:
                    depth = _burial_depth(point, box)
                    if depth <= 0.0:
                        continue
                    total += depth
                    if depth > worst[1]:
                        worst = (
                            f"{owner}.{pin} {_point_text(point)} sits {depth:g} units "
                            f"inside {other}'s {kind} row {text!r}",
                            depth,
                        )
    return CostTerm(
        "pin-text", total,
        "how deep the pin tips sit inside another part's text row — a tip the "
        "router's walls name can never receive a wire end, so the net that owns "
        "it is refused however the parts are arranged "
        + (f"— the worst is {worst[0]}" if worst[0]
           else "— every tip is clear of every other part's rows"),
    )


def _point_text(point: tuple[float, float]) -> str:
    return f"({point[0]:g}, {point[1]:g})"


def _energy(terms: Iterable[CostTerm]) -> float:
    """The scalar the search minimises.

    Every term carries its own weight; a hard term is multiplied by
    :data:`W_HARD` so a drawing that leaves the page or overlaps itself is never
    preferred to one that does not, while still being *reachable* — a search that
    refuses to visit a bad state cannot climb out of one.
    """
    total = 0.0
    for item in terms:
        if item.hard:
            total += item.value * W_HARD
        elif item.name.startswith("relation:"):
            total += item.value * W_RELATION
        elif item.name == "wire-length":
            total += item.value * W_WIRE
        elif item.name == "pin-facing":
            total += item.value * W_FACING
        elif item.name == "flow-side":
            total += item.value * W_SIDE
        elif item.name == "spread":
            total += item.value * W_SPREAD
        elif item.name == "clearance":
            total += item.value * W_CLEARANCE
        elif item.name == "flag-room":
            total += item.value * W_FLAG_ROOM
        elif item.name == "pin-clearance":
            total += item.value * W_PIN_CLEARANCE
        elif item.name == "pin-text":
            total += item.value * W_PIN_TEXT
    return total


# ------------------------------------------------------- the constructive seed


def _ranks(
    relations: Sequence[PlacementRelation], part_ids: Sequence[str]
) -> dict[str, int]:
    """``part_id -> its depth`` in the order the relations state.

    The order kinds are the grammar's "which way the drawing runs" statement, so
    the seed reads them the way the compiler's own ``_ranks`` does: ``left-of``
    and ``above`` say the subject is nearer the power/input end, and the depth is
    the longest path — a part with no order relation gets rank 0 (it will be
    hung off whatever it shares a net with).

    A relation with an endpoint this request has no part for is **skipped here**,
    and the skip is deliberate rather than defensive. A grammar may name a
    **net** where a part could stand (`ic_periphery`'s ports do: the relation is
    about the net's own inlet, not about a component), and such a relation has no
    bearing on which part is nearer the power end. It is also unmeasurable
    everywhere else in this module — :func:`relation_points_between` falls back to
    the endpoint's origin, a net has none, and the pair comes back ``None`` — so
    the compiler's own checker skips it the same way: two layers agreeing that a
    net-endpoint relation is not a statement about part positions. This mattered
    in practice: the zero-move gate's 088/098 previews compile ports stated that
    way, and an earlier version of this function raised ``KeyError`` on the first
    one it met.
    """
    after: dict[str, set[str]] = {part_id: set() for part_id in part_ids}
    for relation in relations:
        if relation.subject not in after or relation.object not in after:
            continue
        if relation.kind == LEFT_OF or relation.kind == ABOVE:
            after[relation.subject].add(relation.object)
        elif relation.kind == RIGHT_OF or relation.kind == BELOW:
            after[relation.object].add(relation.subject)
    ranks: dict[str, int] = {}

    def depth(part_id: str, seen: frozenset[str]) -> int:
        if part_id in ranks:
            return ranks[part_id]
        if part_id in seen:
            return 0  # a cycle the grammar should not state: stop, do not hang
        best = 0
        for other in sorted(after[part_id]):
            best = max(best, depth(other, seen | {part_id}) + 1)
        ranks[part_id] = best
        return best

    for part_id in sorted(part_ids):
        depth(part_id, frozenset())
    return ranks


def _seed(request: PlacementInput, ranks: Mapping[str, int]) -> _State:
    """The constructive first guess: ranked parts on the line, branches on their node.

    Deliberately as boring as it can be — the search is what makes the drawing,
    and a clever seed only makes a failure harder to attribute. What it does
    contribute is concept 1's direction: rank grows along ``progress``.
    """
    poses: dict[str, SymbolPose] = {}
    for part in request.parts:
        if part.locked is not None:
            poses[part.part_id] = part.locked
            continue
        poses[part.part_id] = _compact_pose(request, part)

    pinned = request.locked_origins()
    if request.chain:
        return _seed_folding(request, ranks, poses, pinned)
    chain = sorted(
        (part.part_id for part in request.parts),
        key=lambda part_id: (ranks.get(part_id, 0), part_id),
    )
    progress = _unit(request.progress)
    origins: dict[str, tuple[float, float]] = {}
    cursor = 0.0
    for part_id in chain:
        part = request.part(part_id)
        if part_id in pinned:
            # 515A hole 3: a lock's origin is stated, not derived — the chain's
            # own spacing runs around it (the compiler's constructive solver
            # has anchored the chain on its locks this way since 053).
            origins[part_id] = pinned[part_id]
            continue
        half = _extent_along(
            part, poses[part_id], progress
        ) / 2.0
        at = cursor + half
        origins[part_id] = (progress[0] * at, progress[1] * at)
        cursor = at + half + request.channel

    # every part the seed has not placed yet hangs off the neighbour it shares
    # the most pins with — concept 2, read off the netlist rather than a list.
    placed = set(origins)
    for part_id in sorted(set(request.part_ids()) - placed):
        if part_id in pinned:
            continue
        owner = _owner_for(request, part_id, placed, ranks)
        side = _branch_side(request, part_id, owner)
        base = origins.get(owner, (0.0, 0.0))
        distance = request.lane + _extent_along(
            request.part(part_id), poses[part_id], request.lateral
        ) / 2.0
        origins[part_id] = (
            base[0] + side[0] * distance, base[1] + side[1] * distance,
        )
        placed.add(part_id)
    return _State(origins=_snap(request, origins), poses=poses)


def _seed_folding(
    request: PlacementInput,
    ranks: Mapping[str, int],
    poses: dict[str, SymbolPose],
    pinned: Mapping[str, tuple[float, float]],
) -> _State:
    """The chain walked as a **path that may turn**, not as one line.

    Rank still grows along ``progress`` — that is concept 1, and the reason the
    drawing reads in flow order. What a line cannot express is a relation that
    asks the *next* chain node to leave the current walk direction **sideways**:
    the flyback states ``right-of(D3, T1)`` between two chain nodes, so the
    secondary upright sits beside the transformer's column instead of below it.
    A line puts every chain node on one axis, so that statement is unreachable at
    any weight, any pose and any search budget (measured:
    ``outputs/algo_eval/DIAGNOSIS_same_column.md`` §7).

    An order kind between two chain parts is exactly the statement "turn here",
    and :func:`_turns_after` reads it off the grammar rather than off a constant —
    so a grammar that states no such relation gets the same straight line the
    historical seed draws.

    Parts outside the chain hang off their busiest neighbour
    (:func:`_owner_for`), the branch rule the one-line seed could never reach
    because every part used to be in the line.
    """
    known = set(request.part_ids())
    chain = sorted(
        (part_id for part_id in request.chain if part_id in known),
        key=lambda part_id: (ranks.get(part_id, 0), part_id),
    )
    lateral = _unit(request.lateral)
    origins: dict[str, tuple[float, float]] = {}
    at = (0.0, 0.0)
    direction = _chain_direction(request, ranks, _unit(request.progress))
    for index, part_id in enumerate(chain):
        if part_id in pinned:
            # A lock's coordinate is the engineer's: the walk resumes from it
            # rather than stepping past it, so the chain reads through the lock.
            origins[part_id] = pinned[part_id]
            at = pinned[part_id]
            continue
        half = _extent_along(
            request.part(part_id), poses[part_id], direction
        ) / 2.0
        origin = (
            at[0] + direction[0] * half,
            at[1] + direction[1] * half,
        )
        origins[part_id] = origin
        at = (
            origin[0] + direction[0] * (half + request.channel),
            origin[1] + direction[1] * (half + request.channel),
        )
        if index + 1 < len(chain) and _turns_after(
            request, part_id, chain[index + 1]
        ):
            direction = _turn_direction(request, part_id, chain[index + 1], lateral)

    placed = set(origins)
    for part_id in sorted(known - placed):
        if part_id in pinned:
            # A locked part outside the chain still has to end up in the state:
            # `_seed` never met this case because its "chain" held every part.
            origins[part_id] = pinned[part_id]
            placed.add(part_id)
            continue
        owner = _owner_for(request, part_id, placed, ranks, order_first=True)
        side = _branch_side(request, part_id, owner)
        base = origins.get(owner, (0.0, 0.0))
        distance = request.lane + _extent_along(
            request.part(part_id), poses[part_id], request.lateral
        ) / 2.0
        origins[part_id] = (
            base[0] + side[0] * distance, base[1] + side[1] * distance,
        )
        placed.add(part_id)
    return _State(origins=_snap(request, origins), poses=poses)


def _chain_direction(
    request: PlacementInput,
    ranks: Mapping[str, int],
    progress: tuple[float, float],
) -> tuple[float, float]:
    """Which way the chain runs: ``progress``, unless a stated order says otherwise.

    ``_ranks`` puts a ``below``'s subject **after** its object, so the walk
    reaches it later; if the kind then says that later node sits *below*, the walk
    has to descend along y, not climb. Without this the flyback's ``below(R5, Q1)``
    is broken at the seed by construction — the search can still repair it, but a
    seed that starts on the wrong side of every vertical order pays for it at every
    restart (measured: ``outputs/algo_eval/DIAGNOSIS_same_column.md`` §7).
    """
    for relation in request.relations:
        if relation.kind not in (ABOVE, BELOW):
            continue
        if relation.subject not in request.chain or relation.object not in request.chain:
            continue
        if progress[1] == 0.0:
            continue
        # ``_ranks`` gives the part drawn **first** the smaller rank (it is a
        # distance to the end of the chain), so ``ranks[subject] < ranks[object]``
        # means the subject is painted earlier in the walk. A subject that is
        # painted earlier must sit **lower** to satisfy ``below``, which means the
        # walk itself has to climb — the sign applied here is the one the produced
        # drawing needs, not the one the word "below" suggests.
        earlier = ranks.get(relation.subject, 0) < ranks.get(relation.object, 0)
        wanted = 1.0 if (relation.kind == BELOW) == earlier else -1.0
        if wanted * progress[1] > 0:
            return progress
        return (progress[0], -progress[1])
    return progress


def _turns_after(request: PlacementInput, here: str, following: str) -> bool:
    """Does the grammar ask ``following`` to leave ``here`` sideways?

    Read off the stated order kinds, not off a layout constant: a ``right-of`` or
    ``left-of`` whose subject is the next chain node and whose object is the one
    just placed is the grammar saying "this node continues beside, not beyond".
    """
    for relation in request.relations:
        if relation.subject != following or relation.object != here:
            continue
        if relation.kind in (LEFT_OF, RIGHT_OF):
            return True
    return False


def _turn_direction(
    request: PlacementInput,
    here: str,
    following: str,
    lateral: tuple[float, float],
) -> tuple[float, float]:
    """Which way the walk turns: the side the order kind names, on ``lateral``.

    ``right-of`` asks for a larger x, so the turn takes whichever sign of
    ``lateral`` points that way; ``left-of`` the other. The caller has already
    established that one of the two is stated (:func:`_turns_after`).
    """
    for relation in request.relations:
        if relation.subject != following or relation.object != here:
            continue
        if relation.kind == RIGHT_OF:
            return lateral if lateral[0] > 0 else (-lateral[0], -lateral[1])
        if relation.kind == LEFT_OF:
            return lateral if lateral[0] < 0 else (-lateral[0], -lateral[1])
    return lateral


def _compact_pose(request: PlacementInput, part: PlacementPart) -> SymbolPose:
    """The pose whose box is smallest along the chain — the seed's own choice.

    Nothing more clever: this is the first guess, and concept 3 is the *search*
    being free to turn a part, not the seed knowing which way it should face. A
    part with one dimension of freedom (a two-pin chip) gets the rung that keeps
    it shortest along the chain; the search is free to change it immediately.
    """
    progress = _unit(request.progress)
    best = part.poses[0]
    best_size = None
    for pose in part.poses:
        size = _extent_along(part, pose, progress)
        key = (size, pose.rotation, pose.mirror, pose.label())
        if best_size is None or key < best_size:
            best_size = key
            best = pose
    return best


def _extent_along(
    part: PlacementPart, pose: SymbolPose, axis: tuple[float, float]
) -> float:
    box = part_box(part.profile, pose, (0.0, 0.0))
    corners = [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]
    projections = [_dot(corner, axis) for corner in corners]
    return max(projections) - min(projections)


def _owner_for(
    request: PlacementInput,
    part_id: str,
    placed: set[str],
    ranks: Mapping[str, int],
    *,
    order_first: bool = False,
) -> str:
    """The neighbour this part should hang off: most shared pins, then rank, then id.

    ``order_first`` (D1, the folding seed only) reads an ``above`` / ``below`` /
    ``left-of`` / ``right-of`` the grammar states about this part **before** the
    pin count: that relation names the node the branch is drawn against, so
    hanging it off any other neighbour is how ``below(C10, U5)`` ends up measured
    between C10 and whatever happened to share the most pins.
    """
    if order_first:
        for relation in request.relations:
            if relation.kind not in (ABOVE, BELOW, LEFT_OF, RIGHT_OF):
                continue
            if relation.subject == part_id and relation.object in placed:
                return relation.object
            if relation.object == part_id and relation.subject in placed:
                return relation.subject
    mine = _part_nets(request, part_id)
    best: tuple[tuple[int, int, str], str] | None = None
    for owner in sorted(placed):
        theirs = _part_nets(request, owner)
        shared = len(set(mine.values()) & set(theirs.values()))
        if shared == 0:
            continue
        key = (-shared, ranks.get(owner, 0), owner)
        if best is None or key < best[0]:
            best = (key, owner)
    if best is None:
        # Nothing to hang off: place it farthest along the chain, so it is still
        # on the drawing and its relations can pull it into place.
        return max(sorted(placed), key=lambda name: (ranks.get(name, 0), name))
    return best[1]


def _branch_side(
    request: PlacementInput, part_id: str, owner: str
) -> tuple[float, float]:
    """Which way a hung part leaves its owner: its own rail's side, else lateral.

    The branch's "other net" — the one it does not share with its owner — is what
    says which way its body goes, which is the reading ``_branch_slot`` makes and
    the reason a decoupling capacitor sits between a pin and its rail.

    An ``above`` / ``below`` the grammar states about **this** part is read first
    (D1): it names the side outright, which outranks a net-class preference. The
    flyback's ``below(C10, U5)`` is the case — C10 hangs off the feedback node,
    its own net's class says nothing about which way, and the one-line seed never
    read the statement at all.
    """
    lateral = _unit(request.lateral)
    for relation in request.relations:
        if relation.kind in (ABOVE, BELOW):
            if relation.subject == part_id:
                return (0.0, 1.0) if relation.kind == ABOVE else (0.0, -1.0)
            if relation.object == part_id:
                return (0.0, -1.0) if relation.kind == ABOVE else (0.0, 1.0)
            continue
        if relation.kind in (LEFT_OF, RIGHT_OF):
            # ``x`` is whether the *subject* sits on the +lateral side of the
            # object; a part named as the object wants the opposite side.
            wanted = 1.0 if relation.kind == RIGHT_OF else -1.0
            if relation.subject == part_id:
                sign = wanted
            elif relation.object == part_id:
                sign = -wanted
            else:
                continue
            return lateral if sign * lateral[0] > 0 else (-lateral[0], -lateral[1])
    mine = _part_nets(request, part_id)
    theirs = _part_nets(request, owner) if owner else {}
    own = sorted(set(mine.values()) - set(theirs.values()))
    for net_id in own:
        side = request.side_preferences.get(_net_class(request, net_id), "")
        if side:
            return _SIDE_VECTORS[side]
    return _unit(request.lateral)


def _unit(vector: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(vector[0], vector[1])
    if length == 0.0:
        raise PlacementError("a direction of (0, 0) is not a direction")
    return (vector[0] / length, vector[1] / length)


def _snap(
    request: PlacementInput, origins: Mapping[str, tuple[float, float]]
) -> dict[str, tuple[float, float]]:
    grid = request.grid
    return {
        part_id: (
            origins[part_id]
            if part_id in request.locked_origins()
            else (round(point[0] / grid) * grid, round(point[1] / grid) * grid)
        )
        for part_id, point in sorted(origins.items())
    }


# --------------------------------------------------- the declared series seats


def _pin_for_token(profile: SymbolProfile, token: str) -> SymbolPin | None:
    """The profile pin a token names: by number first, then by name.

    The same rule `drawcompiler._pin_of_token` and `grammar.base.profile_pin_for`
    apply, so a token copied out of a spec resolves here exactly as it does there.
    """
    if not token:
        return None
    found = profile.pin(token)
    if found is not None:
        return found
    for pin in profile.pins:
        if pin.name == token:
            return pin
    return None


def _check_series_templates(request: PlacementInput) -> None:
    """Refuse a template whose references or conflicts cannot be seated.

    Runs at request construction — before any geometry — because a branch that
    names a part this request does not carry, a pin its symbol does not have, or
    a pose its part was not given is not a search question: it is a typo or a
    disagreement between two documents, and naming it here is the honest answer.
    """
    templates = request.series_templates
    if not templates:
        return
    known = {part.part_id: part for part in request.parts}
    branches: set[str] = set()
    arm_owner: dict[str, str] = {}
    for template in templates:
        spot = f"seriesTemplates entry {template.branch_id!r}"
        if template.branch_id in branches:
            raise PlacementError(f"{spot}: two templates share one branch id")
        branches.add(template.branch_id)
        if template.host_part not in known:
            raise PlacementError(
                f"{spot}: host part {template.host_part!r} is not in this request"
            )
        host = known[template.host_part]
        if _pin_for_token(host.profile, template.host_token) is None:
            raise PlacementError(
                f"{spot}: host pin {template.host_part}.{template.host_token} is "
                "not a pin of that symbol"
            )
        for role, arm, pose in (
            ("first", template.first, template.first_pose),
            ("second", template.second, template.second_pose),
        ):
            if arm.part_id not in known:
                raise PlacementError(
                    f"{spot}: {role} part {arm.part_id!r} is not in this request"
                )
            if arm.part_id in arm_owner:
                raise PlacementError(
                    f"{spot}: part {arm.part_id!r} is already in series branch "
                    f"{arm_owner[arm.part_id]!r}; one part belongs to one arm"
                )
            arm_owner[arm.part_id] = template.branch_id
            part = known[arm.part_id]
            for label, token in (
                ("from", arm.from_token), ("middle", arm.middle_token),
                ("to", arm.to_token),
            ):
                if token and _pin_for_token(part.profile, token) is None:
                    raise PlacementError(
                        f"{spot}: {role} part pin "
                        f"{arm.part_id}.{token} ({label}) is not a pin of that symbol"
                    )
            if pose not in part.poses:
                raise PlacementError(
                    f"{spot}: {role} part {arm.part_id} is not legal in pose "
                    f"{pose.label()}; its accepted poses are "
                    f"{sorted(item.label() for item in part.poses)}"
                )
            if part.locked_origin is not None:
                raise PlacementError(
                    f"{spot}: {arm.part_id} carries an engineer origin lock "
                    f"({part.locked_origin[0]:g}, {part.locked_origin[1]:g}); a "
                    "series seat is derived from the host and cannot honour it"
                )
            if part.locked is not None and part.locked != pose:
                raise PlacementError(
                    f"{spot}: {arm.part_id} is pose-locked to "
                    f"{part.locked.label()}, the template draws it in "
                    f"{pose.label()}"
                )
        progress = _unit(template.progress)
        lateral = _unit(template.lateral)
        if abs(_dot(progress, lateral)) > 1e-6:
            raise PlacementError(
                f"{spot}: progress {template.progress!r} and lateral "
                f"{template.lateral!r} are not perpendicular"
            )
    host_parts = {template.host_part for template in templates}
    for part_id, branch in arm_owner.items():
        if part_id in host_parts:
            raise PlacementError(
                f"seriesTemplates: part {part_id!r} is an arm part of branch "
                f"{branch!r} and also a host of another arm; nested arms are not "
                "a seat this contract expresses"
            )


def _check_flag_corridors(request: PlacementInput) -> None:
    """Refuse a corridor whose references or pin nets cannot be seated.

    The same reading as :func:`_check_series_templates`: a group that names a
    part this request does not carry, a pin its symbol does not have, or a net
    that disagrees with the netlist is not a search question — it is a
    disagreement between two documents, and naming it here is the honest answer.
    """
    templates = request.flag_corridors
    if not templates:
        return
    known = {part.part_id: part for part in request.parts}
    groups: set[str] = set()
    owners: dict[tuple[str, str], str] = {}
    for template in templates:
        spot = f"flagCorridors entry {template.group_id!r}"
        if template.group_id in groups:
            raise PlacementError(f"{spot}: two corridors share one group id")
        groups.add(template.group_id)
        if template.host_part not in known:
            raise PlacementError(
                f"{spot}: host part {template.host_part!r} is not in this request"
            )
        for pin in template.pins:
            key = (pin.part_id, pin.token)
            if pin.part_id not in known:
                raise PlacementError(
                    f"{spot}: pin {pin.part_id}.{pin.token} names a part that is "
                    "not in this request"
                )
            if key in owners:
                raise PlacementError(
                    f"{spot}: pin {pin.part_id}.{pin.token} is already in corridor "
                    f"{owners[key]!r}; one pin is seated by one corridor"
                )
            owners[key] = template.group_id
            profile = known[pin.part_id].profile
            if _pin_for_token(profile, pin.token) is None:
                raise PlacementError(
                    f"{spot}: pin {pin.part_id}.{pin.token} is not a pin of that "
                    "symbol"
                )
            actual = _part_nets(request, pin.part_id).get(pin.token)
            if actual is None:
                raise PlacementError(
                    f"{spot}: pin {pin.part_id}.{pin.token} is on no net in this "
                    "request's netlist"
                )
            if actual != pin.net_id:
                raise PlacementError(
                    f"{spot}: pin {pin.part_id}.{pin.token} is declared on net "
                    f"{pin.net_id!r}, the netlist says {actual!r}"
                )
        seen_gaps: set[str] = set()
        for gap in template.service_gaps:
            if gap.part_id in seen_gaps:
                raise PlacementError(
                    f"{spot}: part {gap.part_id!r} states two service pin gaps"
                )
            seen_gaps.add(gap.part_id)
            for label, part_id, token in (
                ("service", gap.part_id, gap.token),
                ("host", gap.host_part, gap.host_token),
            ):
                if part_id not in known:
                    raise PlacementError(
                        f"{spot}: service gap {label} part {part_id!r} is not in "
                        "this request"
                    )
                if _pin_for_token(known[part_id].profile, token) is None:
                    raise PlacementError(
                        f"{spot}: service gap {label} pin {part_id}.{token} is not "
                        "a pin of that symbol"
                    )


def _series_centre(box: Box) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def _pad_box(box: Box, pad: float) -> Box:
    if pad <= 0.0:
        return box
    return (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)


def _series_snap(value: float, grid: float, offset: float) -> float:
    """One coordinate on the compilation lattice ``grid + offset``.

    The same formula as ``drawcompiler._snap``: the offset is a **coordinate**
    residue, so a point one lattice step away stays exactly one step away. It is
    deliberately not the box padding — that is ``clearance`` and never enters
    this function.
    """
    return round((value - offset) / grid) * grid + offset


def _series_snap_point(
    point: tuple[float, float], grid: float, lattice: tuple[float, float]
) -> tuple[float, float]:
    return (
        _series_snap(point[0], grid, lattice[0]),
        _series_snap(point[1], grid, lattice[1]),
    )


def _span_box(a: tuple[float, float], b: tuple[float, float], pad: float) -> Box:
    """The corridor between two points, widened by ``pad`` on every side."""
    return (
        min(a[0], b[0]) - pad, min(a[1], b[1]) - pad,
        max(a[0], b[0]) + pad, max(a[1], b[1]) + pad,
    )


def _overlap_area(first: Box, second: Box) -> float:
    width = min(first[2], second[2]) - max(first[0], second[0])
    height = min(first[3], second[3]) - max(first[1], second[1])
    if width <= 0.0 or height <= 0.0:
        return 0.0
    return width * height


def _axis_interval(box: Box, axis: tuple[float, float]) -> tuple[float, float]:
    corners = (
        (box[0], box[1]), (box[0], box[3]),
        (box[2], box[1]), (box[2], box[3]),
    )
    values = [point[0] * axis[0] + point[1] * axis[1] for point in corners]
    return (min(values), max(values))


def _series_local_centre(profile: SymbolProfile, pose: SymbolPose) -> tuple[float, float]:
    return _series_centre(part_box(profile, pose, (0.0, 0.0)))


def _series_local_tip(
    profile: SymbolProfile, token: str, pose: SymbolPose
) -> tuple[float, float] | None:
    pin = _pin_for_token(profile, token)
    if pin is None:
        return None
    return posed_tip(pin.tip, pose, (0.0, 0.0))


def _series_pin_point(
    request: PlacementInput, part_id: str, token: str, state: _State
) -> tuple[float, float] | None:
    part = request.part(part_id)
    pin = _pin_for_token(part.profile, token)
    if pin is None:
        return None
    return posed_tip(pin.tip, state.poses[part_id], state.origins[part_id])


def _series_axis_problem(
    template: SeriesSeatTemplate, first: SymbolProfile, second: SymbolProfile
) -> str | None:
    """Why the template's poses do not read along the arm, or ``None``.

    The seat equation is one: the first part's ``from`` foot faces the host, its
    ``middle`` foot faces the second part, and the second part's ``middle`` foot
    faces the first while its ``to`` foot faces the terminal. A pose that puts
    any of those feet on the wrong side would make the drawing double back, and
    a bottom-up search would have to repair a decision that was stated wrongly.
    """
    progress = _unit(template.progress)
    first_centre = _series_local_centre(first, template.first_pose)
    second_centre = _series_local_centre(second, template.second_pose)
    first_from = _series_local_tip(first, template.first.from_token, template.first_pose)
    first_middle = _series_local_tip(first, template.first.middle_token, template.first_pose)
    second_middle = _series_local_tip(second, template.second.middle_token, template.second_pose)
    second_to = _series_local_tip(second, template.second.to_token, template.second_pose)
    if any(point is None for point in (first_from, first_middle, second_middle, second_to)):
        return "one of the arm's pins could not be resolved on its symbol"
    assert first_from is not None and first_middle is not None
    assert second_middle is not None and second_to is not None
    for tip, centre, side, label in (
        (first_from, first_centre, -1.0, f"{template.first.part_id}'s from pin"),
        (first_middle, first_centre, 1.0, f"{template.first.part_id}'s middle pin"),
        (second_middle, second_centre, -1.0, f"{template.second.part_id}'s middle pin"),
        (second_to, second_centre, 1.0, f"{template.second.part_id}'s to pin"),
    ):
        along = _dot((tip[0] - centre[0], tip[1] - centre[1]), progress)
        if side > 0 and along <= SERIES_EPS:
            return f"{label} does not sit on the far side of its part along progress"
        if side < 0 and along >= -SERIES_EPS:
            return f"{label} does not sit on the host side of its part along progress"
    if _dot(
        (first_middle[0] - first_from[0], first_middle[1] - first_from[1]), progress
    ) <= SERIES_EPS:
        return (
            f"{template.first.part_id}'s from -> middle pins do not run along progress"
        )
    if _dot(
        (second_to[0] - second_middle[0], second_to[1] - second_middle[1]), progress
    ) <= SERIES_EPS:
        return (
            f"{template.second.part_id}'s middle -> to pins do not run along progress"
        )
    return None


def _series_geometry(
    request: PlacementInput,
    plan: BoundSeriesSeatPlan,
    host_origin: tuple[float, float],
    host_pose: SymbolPose,
    first_origin: tuple[float, float],
    second_origin: tuple[float, float],
) -> tuple[
    tuple[Box, ...], tuple[str, ...],
    tuple[Box, ...], tuple[str, ...],
    tuple[tuple[float, float], ...],
]:
    """The two geometries this seat needs, and the path it means (548D3B).

    **Reserved** is where the arm's wires really go: the two part boxes, the
    two orthogonal legs of the host lead (escape along the lane, then walk the
    pair axis to the first part's ``from`` foot) and the middle link. Only this
    geometry may move an ordinary branch aside, because only this geometry is
    the space the arm actually takes.

    **Guard** is the conservative reading the unyieldable parts keep: the same
    two part boxes and middle link, but the host lead as the whole AABB between
    the host foot and the first part — the box that must stay clear of a
    power/decoupling part or an engineer lock. A part the seat may not move is
    refused on *this* box, which is why the old negative case still refuses by
    name while an ordinary branch is no longer pushed by air the wire never
    crosses.

    Roles travel with the boxes ("part0", "part1", "host", "middle") so a reader
    never has to know an index to know what it is looking at.

    The **path** is the point sequence the host lead means: host foot → lane
    corner → first ``from`` foot, with the corner dropped when the two feet are
    already on one axis. It is recorded on the plan and is what the compiler
    checks its own routed wire against.
    """
    first_part = request.part(plan.first_part)
    second_part = request.part(plan.second_part)
    first_pose = plan.first_pose
    second_pose = plan.second_pose
    if first_pose is None or second_pose is None:
        return (), (), (), (), ()
    part_boxes = (
        _pad_box(part_box(first_part.profile, first_pose, first_origin), plan.clearance),
        _pad_box(part_box(second_part.profile, second_pose, second_origin), plan.clearance),
    )
    part_roles = ("part0", "part1")
    host_pin = _pin_for_token(request.part(plan.host_part).profile, plan.host_token)
    first_from_pin = _pin_for_token(first_part.profile, plan.first_from_token)
    first_middle_pin = _pin_for_token(first_part.profile, plan.first_middle_token)
    second_middle_pin = _pin_for_token(second_part.profile, plan.second_middle_token)
    if None in (host_pin, first_from_pin, first_middle_pin, second_middle_pin):
        return part_boxes, part_roles, part_boxes, part_roles, ()
    assert host_pin is not None and first_from_pin is not None
    assert first_middle_pin is not None and second_middle_pin is not None
    host_tip = posed_tip(host_pin.tip, host_pose, host_origin)
    first_from = posed_tip(first_from_pin.tip, first_pose, first_origin)
    first_middle = posed_tip(first_middle_pin.tip, first_pose, first_origin)
    second_middle = posed_tip(second_middle_pin.tip, second_pose, second_origin)
    corridor_pad = max(plan.clearance, plan.grid / 2.0)
    middle_box = _span_box(first_middle, second_middle, corridor_pad)
    # The lane corner is measured from the two feet themselves rather than from
    # the stored lane, so a plan that was translated (or whose lane was restated)
    # still names the same channel.
    lateral = _unit(plan.lateral)
    progress = _unit(plan.progress)
    # The lead leaves the pin along the pin's own axis first: a side-facing pin
    # (the MCU's right-hand row is one) has its neighbours on that same line, and
    # a run that turns off it at the tip stands a vertex on a foreign pin, which
    # is a connection. One lattice step is the stated clearance, and half the
    # distance to the first part when the seat is tighter than that.
    along = _dot((first_from[0] - host_tip[0], first_from[1] - host_tip[1]), progress)
    stub = min(plan.grid, along / 2.0) if along > SERIES_EPS else 0.0
    stub_point = (
        (host_tip[0] + progress[0] * stub, host_tip[1] + progress[1] * stub)
        if stub > SERIES_EPS else host_tip
    )
    escape = _dot(
        (first_from[0] - stub_point[0], first_from[1] - stub_point[1]), lateral
    )
    corner = (
        stub_point[0] + lateral[0] * escape,
        stub_point[1] + lateral[1] * escape,
    )
    points = [host_tip]
    if stub_point != host_tip:
        points.append(stub_point)
    if abs(escape) > SERIES_EPS:
        points.append(corner)
    points.append(first_from)
    path = tuple(points)
    legs = tuple(
        _span_box(start, end, corridor_pad)
        for start, end in zip(path, path[1:])
        if start != end
    )
    reserved = part_boxes + legs + (middle_box,)
    reserved_roles = part_roles + ("host",) * len(legs) + ("middle",)
    guard = part_boxes + (
        _span_box(host_tip, first_from, corridor_pad), middle_box,
    )
    guard_roles = part_roles + ("host", "middle")
    return reserved, reserved_roles, guard, guard_roles, path


def _series_boxes(
    request: PlacementInput,
    plan: BoundSeriesSeatPlan,
    host_origin: tuple[float, float],
    host_pose: SymbolPose,
    first_origin: tuple[float, float],
    second_origin: tuple[float, float],
) -> tuple[Box, ...]:
    """The plan's **walkable** reserved boxes at these origins (548D3B)."""
    reserved, _roles, _guard, _guard_roles, _path = _series_geometry(
        request, plan, host_origin, host_pose, first_origin, second_origin,
    )
    return reserved


def _series_guards(
    request: PlacementInput,
    plan: BoundSeriesSeatPlan,
    host_origin: tuple[float, float],
    host_pose: SymbolPose,
    first_origin: tuple[float, float],
    second_origin: tuple[float, float],
) -> tuple[Box, ...]:
    """The **conservative** boxes an unyieldable part is refused on (548D3B)."""
    _reserved, _roles, guard, _guard_roles, _path = _series_geometry(
        request, plan, host_origin, host_pose, first_origin, second_origin,
    )
    return guard


def _series_roles(
    request: PlacementInput,
    plan: BoundSeriesSeatPlan,
    host_origin: tuple[float, float],
    host_pose: SymbolPose,
    first_origin: tuple[float, float],
    second_origin: tuple[float, float],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """``(reserved roles, guard roles)`` for the boxes above them."""
    _reserved, roles, _guard, guard_roles, _path = _series_geometry(
        request, plan, host_origin, host_pose, first_origin, second_origin,
    )
    return roles, guard_roles


def _label_corridor_box(
    request: PlacementInput,
    corridor: LabelCorridor,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
) -> Box | None:
    """The box a label takes by default, in page coordinates (548D3B).

    The pin tip comes from the answer's own pose and origin; the escape is the
    profile's direction turned by the pose and snapped to one page axis (the
    reading ``drawcompiler._pin_escape`` makes). The box is then **horizontal**:
    a horizontal escape steps by ``reach_x`` along x, a vertical one by
    ``reach_y`` along y, and the text's width always runs along x — a label is
    never rotated with its symbol, so neither is its box.
    """
    if corridor.part_id not in origins or corridor.part_id not in poses:
        return None
    profile = request.part(corridor.part_id).profile
    pin = _pin_for_token(profile, corridor.token)
    if pin is None:
        return None
    pose = poses[corridor.part_id]
    tip = posed_tip(pin.tip, pose, origins[corridor.part_id])
    local = {
        "left": (-1.0, 0.0), "right": (1.0, 0.0),
        "up": (0.0, 1.0), "down": (0.0, -1.0),
    }[corridor.local_direction]
    directed = transform_point(
        local[0], local[1], rotation=pose.rotation, mirror=pose.mirror,
        ox=0.0, oy=0.0,
    )
    if abs(directed[0]) >= abs(directed[1]):
        direction = (math.copysign(1.0, directed[0]), 0.0)
    else:
        direction = (0.0, math.copysign(1.0, directed[1]))
    if direction[0] != 0.0:
        centre = (tip[0] + direction[0] * corridor.reach_x, tip[1])
    else:
        centre = (tip[0], tip[1] + direction[1] * corridor.reach_y)
    half_w = corridor.width / 2.0
    half_h = corridor.height / 2.0
    return (
        centre[0] - half_w, centre[1] - half_h,
        centre[0] + half_w, centre[1] + half_h,
    )


def _foreign_labels(
    request: PlacementInput,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
    owned: frozenset[str],
) -> tuple[tuple[LabelCorridor, Box], ...]:
    """Every label corridor this seat must keep out of, with its box.

    A label on a part the plan owns is that part's own name: it travels with the
    part, so no lane could ever clear it and asking would refuse every page.
    """
    out: list[tuple[LabelCorridor, Box]] = []
    for corridor in request.label_corridors:
        if corridor.part_id in owned:
            continue
        box = _label_corridor_box(request, corridor, origins, poses)
        if box is not None:
            out.append((corridor, box))
    return tuple(out)


def _series_lead_boxes(
    request: PlacementInput, plan: BoundSeriesSeatPlan, seed: _State
) -> tuple[Box, ...]:
    """The legs of the arm's **planned** host lead, as boxes.

    The legs are the recorded path's own segments — the host escapes along the
    lane, then walks the pair axis to the first part — so a lane check and the
    reserve it is compared with can never be two geometries (548D3B).
    """
    path = plan.host_path
    if not path and plan.first_origin is not None and plan.first_pose is not None:
        path = _series_geometry(
            request, plan, seed.origins[plan.host_part],
            seed.poses[plan.host_part], plan.first_origin, plan.second_origin,
        )[4] if plan.second_origin is not None else ()
    return tuple(
        _span_box(start, end, 0.0)
        for start, end in zip(path, path[1:])
    )


def _lane_on_grid(value: float, grid: float) -> float:
    return round(value / grid) * grid


def _point_on_link(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    """Is ``point`` on the closed segment ``start``-``end`` (lattice exact)?"""
    if abs(start[0] - end[0]) <= SERIES_EPS:
        if abs(point[0] - start[0]) > SERIES_EPS:
            return False
        low, high = sorted((start[1], end[1]))
        return low - SERIES_EPS <= point[1] <= high + SERIES_EPS
    if abs(start[1] - end[1]) <= SERIES_EPS:
        if abs(point[1] - start[1]) > SERIES_EPS:
            return False
        low, high = sorted((start[0], end[0]))
        return low - SERIES_EPS <= point[0] <= high + SERIES_EPS
    return False


def _pin_walls(
    request: PlacementInput, state: _State, owned: frozenset[str]
) -> tuple[tuple[tuple[float, float], ...], tuple[Box, ...]]:
    """Every **foreign** pin tip and pin lead, as walls for an arm's lead (548D3B).

    A run whose vertex stands on another net's pin is a connection in the editor's
    model, and a run along a pin's own lead is the same defect a reader sees as a
    short. Both are read off the request's profiles, the answer's poses and the
    origins — the same three facts the router checks, with no copy of readability:
    a lead runs from the tip **into** its own symbol by the pin's stated length.
    """
    tips: list[tuple[float, float]] = []
    leads: list[Box] = []
    for part in request.parts:
        if part.part_id in owned:
            continue
        pose = state.poses.get(part.part_id)
        origin = state.origins.get(part.part_id)
        if pose is None or origin is None:
            continue
        for pin in part.profile.pins:
            tip = posed_tip(pin.tip, pose, origin)
            tips.append(tip)
            length = float(getattr(pin, "length", 0.0) or 0.0)
            if length <= SERIES_EPS:
                continue
            away = {
                "left": (-1.0, 0.0), "right": (1.0, 0.0),
                "up": (0.0, 1.0), "down": (0.0, -1.0),
            }.get(getattr(pin, "direction", ""))
            if away is None:
                continue
            inner = posed_tip(
                (pin.tip[0] - away[0] * length, pin.tip[1] - away[1] * length),
                pose, origin,
            )
            leads.append(_span_box(tip, inner, 0.0))
    return tuple(tips), tuple(leads)


def _path_hits_walls(
    path: Sequence[tuple[float, float]],
    tips: Sequence[tuple[float, float]],
    leads: Sequence[Box],
) -> bool:
    """Does any leg of this path stand on a foreign tip or run along a lead?"""
    for start, end in zip(path, path[1:]):
        for tip in tips:
            if _point_on_link(tip, start, end):
                return True
        box = _span_box(start, end, 0.0)
        horizontal = (box[2] - box[0]) >= (box[3] - box[1])
        for lead in leads:
            if _overlap_area(box, lead) <= 0.0:
                continue
            # A crossing is legal (074: an ordinary wire may cross another), a
            # run *along* a lead reads as the short it is. Same axis + overlap
            # is exactly that reading.
            if ((lead[2] - lead[0]) >= (lead[3] - lead[1])) == horizontal:
                return True
    return False


def _choose_series_lane(
    request: PlacementInput,
    template: SeriesSeatTemplate,
    seed: _State,
    build: Callable[[float], BoundSeriesSeatPlan],
    seed_lane: float,
) -> tuple[float, tuple[str, str, str] | None]:
    """The shortest legal lane for this arm, or the named reason there is none.

    The legal domain is the page's own labels: an arm may not put its reserved
    boxes **or its two planned leads** across a label box. The candidates are
    exactly ``0``, the seed lane, and — for every label the arm's progress span
    actually meets — the two lateral edges of that label projected onto the
    grid. Ordering is "closest to the seat the ordinary layout already chose",
    then closest to the no-lane equation, then the smaller lane: a shortest
    escape, never a weight.
    """
    # Only the arm's **two parts** carry their labels with them: the host is a
    # part the plan pins the seat to, but its labels do not move with the arm, so
    # the arm has to keep out of them like any other name on the page.
    owned = frozenset((template.first.part_id, template.second.part_id))
    labels = _foreign_labels(request, seed.origins, seed.poses, owned)
    tips, leads = _pin_walls(
        request, seed,
        frozenset((
            template.host_part, template.first.part_id, template.second.part_id,
        )),
    )
    if not labels and not tips and not leads:
        return seed_lane, None
    lateral = _unit(template.lateral)
    progress = _unit(template.progress)
    base = build(0.0)
    if not base.reserved_boxes:
        return seed_lane, None
    lateral_spans = [_axis_interval(box, lateral) for box in base.reserved_boxes]
    low = min(span[0] for span in lateral_spans)
    high = max(span[1] for span in lateral_spans)
    progress_spans = [_axis_interval(box, progress) for box in base.reserved_boxes]
    p_low = min(span[0] for span in progress_spans)
    p_high = max(span[1] for span in progress_spans)
    # The obstacles the candidate edges come from: the labels' default boxes and
    # the foreign pin tips/leads, as the same lattice projections. A tip is a
    # point obstacle, so it becomes a grid-sized box: its two lateral edges are
    # exactly "one grid step short of it" and "one grid step past it".
    obstacles = [box for _corridor, box in labels]
    obstacles.extend(leads)
    obstacles.extend(
        (tip[0] - template.grid / 2.0, tip[1] - template.grid / 2.0,
         tip[0] + template.grid / 2.0, tip[1] + template.grid / 2.0)
        for tip in tips
    )
    candidates = [seed_lane, 0.0]
    for box in obstacles:
        span = _axis_interval(box, progress)
        if span[1] < p_low or span[0] > p_high:
            continue
        lateral_span = _axis_interval(box, lateral)
        candidates.append(_lane_on_grid(lateral_span[0] - template.grid - high, template.grid))
        candidates.append(_lane_on_grid(lateral_span[1] + template.grid - low, template.grid))
    # Ties break towards the **+lateral** side: that is the side the joint lane
    # allocation has always moved the later arm to, so an arm keeps the lane a
    # reader of the older drawing expects whenever both sides are equally legal.
    ordered = sorted(
        set(candidates), key=lambda lane: (abs(lane - seed_lane), abs(lane), -lane)
    )
    for lane in ordered:
        plan = build(lane)
        footprint = plan.reserved_boxes + _series_lead_boxes(request, plan, seed)
        if any(
            _overlap_area(box, label) > 0.0
            for box in footprint for _corridor, label in labels
        ):
            continue
        if _path_hits_walls(plan.host_path, tips, leads):
            continue
        return lane, None
    probe = build(seed_lane).reserved_boxes
    named = ""
    seat = (0.0, 0.0)
    for corridor, box in labels:
        if any(_overlap_area(item, box) > 0.0 for item in probe):
            named = corridor.net_id or f"{corridor.part_id}.{corridor.token}"
            seat = _series_centre(box)
            break
    if not named:
        base_plan = build(seed_lane)
        for start, end in zip(base_plan.host_path, base_plan.host_path[1:]):
            box = _span_box(start, end, 0.0)
            hit = next(
                (tip for tip in tips if _point_on_link(tip, start, end)), None
            )
            if hit is not None:
                named = f"the pin at ({hit[0]:g}, {hit[1]:g})"
                seat = hit
                break
            lead = next((item for item in leads if _overlap_area(box, item) > 0.0), None)
            if lead is not None:
                named = f"the lead at ({_series_centre(lead)[0]:g}, {_series_centre(lead)[1]:g})"
                seat = _series_centre(lead)
                break
    name = named or "another part's pin"
    return -1.0, (
        f"{template.first.part_id} -> {template.second.part_id}",
        f"every lane this arm may take puts its lead across {name!r} "
        f"at ({seat[0]:g}, {seat[1]:g}) — a vertex on a foreign pin is a "
        "connection, and a run along a lead reads as a short",
        "move the arm's host, clear the row the label sits in, or drop the entry",
    )


def _series_refusal_plan(
    template: SeriesSeatTemplate, subject: str, detail: str, action: str
) -> BoundSeriesSeatPlan:
    return BoundSeriesSeatPlan(
        branch_id=template.branch_id, host_part=template.host_part,
        host_token=template.host_token,
        first_part=template.first.part_id, second_part=template.second.part_id,
        first_origin=None, second_origin=None,
        first_pose=template.first_pose, second_pose=template.second_pose,
        first_from_token=template.first.from_token,
        first_middle_token=template.first.middle_token,
        second_middle_token=template.second.middle_token,
        second_to_token=template.second.to_token,
        pitch_source=template.pitch_source,
        progress=template.progress, lateral=template.lateral,
        grid=template.grid, lattice=template.lattice,
        clearance=template.clearance, yield_parts=template.yield_parts,
        refusal=SeriesSeatRefusal(
            branch_id=template.branch_id, subject=subject,
            detail=detail, action=action,
        ),
    )


def _bind_one_series_plan(
    request: PlacementInput,
    template: SeriesSeatTemplate,
    seed: _State,
    pitch_origins: Mapping[str, tuple[float, float]] | None = None,
) -> BoundSeriesSeatPlan:
    """Materialise one template against the ordinary seed's host pin tip."""
    branch = template.branch_id
    host_part = request.part(template.host_part)
    if _pin_for_token(host_part.profile, template.host_token) is None:
        return _series_refusal_plan(
            template, template.host_part,
            f"host pin {template.host_part}.{template.host_token} is not a pin of "
            "that symbol",
            "state a pin the host symbol carries, or drop the arm",
        )
    first_part = request.part(template.first.part_id)
    second_part = request.part(template.second.part_id)
    missing = [
        part_id for part_id in (
            template.host_part, template.first.part_id, template.second.part_id,
        )
        if part_id not in seed.origins or part_id not in seed.poses
    ]
    if missing:
        return _series_refusal_plan(
            template, missing[0],
            f"the ordinary seed did not place {missing[0]!r}, so the arm has no "
            "host or seat to be measured from",
            "place the part first, or drop the arm",
        )
    first_pose = template.first_pose
    second_pose = template.second_pose
    first_seed_origin = seed.origins[template.first.part_id]
    second_seed_origin = seed.origins[template.second.part_id]
    # The compiler's own seat reads the ordinary seed's part **origins**, not
    # their box centres: `_seat_series_arms` measures `was_first`/`was_second`
    # and freezes that number. The same reading here keeps the two seats one
    # equation instead of two. When the caller states the construction seed
    # (`pitch_origins`) the pitch is measured there and nowhere else, so a pass
    # that ran between the seed and this call cannot change it.
    if pitch_origins is not None:
        first_seed_origin = pitch_origins.get(
            template.first.part_id, first_seed_origin
        )
        second_seed_origin = pitch_origins.get(
            template.second.part_id, second_seed_origin
        )
    pitch = math.hypot(
        second_seed_origin[0] - first_seed_origin[0],
        second_seed_origin[1] - first_seed_origin[1],
    )
    if pitch <= SERIES_EPS:
        return _series_refusal_plan(
            template,
            f"{template.first.part_id} and {template.second.part_id}",
            "the ordinary seed put both arm parts on one origin, so there is no "
            "pair pitch to freeze",
            "place the two parts apart, or drop the arm",
        )
    problem = _series_axis_problem(template, first_part.profile, second_part.profile)
    if problem:
        return _series_refusal_plan(
            template, f"{template.first.part_id} -> {template.second.part_id}",
            problem,
            "choose a pose whose from -> middle -> to pins run along the chain "
            "axis, or state the other chain axis",
        )
    progress = _unit(template.progress)
    lateral = _unit(template.lateral)
    host_tip = _series_pin_point(
        request, template.host_part, template.host_token, seed
    )
    assert host_tip is not None
    lead = _series_local_tip(
        first_part.profile, template.first.from_token, first_pose
    )
    assert lead is not None
    # The no-lane seat is the compiler's equation exactly: half a pair pitch
    # beyond the host foot, with the first part's posed from tip as the lead.
    no_lane_first = (
        host_tip[0] + progress[0] * pitch / 2.0 - lead[0],
        host_tip[1] + progress[1] * pitch / 2.0 - lead[1],
    )
    lane = _dot(
        (first_seed_origin[0] - no_lane_first[0],
         first_seed_origin[1] - no_lane_first[1]),
        lateral,
    )

    def build(seat_lane: float) -> BoundSeriesSeatPlan:
        # Both ends use the same grid+lattice snap. If that quantization makes
        # the measured origin distance differ from the nominal pitch, the
        # nominal number stays the plan's source (`pitch`); `origin_pitch()` is
        # the final-geometry reading, never a replacement source.
        seat_first = _series_snap_point(
            (
                no_lane_first[0] + lateral[0] * seat_lane,
                no_lane_first[1] + lateral[1] * seat_lane,
            ),
            template.grid, template.lattice,
        )
        seat_second = _series_snap_point(
            (
                seat_first[0] + progress[0] * pitch,
                seat_first[1] + progress[1] * pitch,
            ),
            template.grid, template.lattice,
        )
        seated = BoundSeriesSeatPlan(
            branch_id=branch, host_part=template.host_part,
            host_token=template.host_token,
            first_part=template.first.part_id, second_part=template.second.part_id,
            first_origin=seat_first, second_origin=seat_second,
            first_pose=first_pose, second_pose=second_pose,
            first_from_token=template.first.from_token,
            first_middle_token=template.first.middle_token,
            second_middle_token=template.second.middle_token,
            second_to_token=template.second.to_token,
            pitch=pitch, lane=seat_lane, pitch_source=template.pitch_source,
            progress=template.progress, lateral=template.lateral,
            grid=template.grid, lattice=template.lattice,
            clearance=template.clearance, yield_parts=template.yield_parts,
        )
        reserved, _roles, guard, _guard_roles, path = _series_geometry(
            request, seated, seed.origins[template.host_part],
            seed.poses[template.host_part], seat_first, seat_second,
        )
        return replace(
            seated, reserved_boxes=reserved, guard_boxes=guard, host_path=path,
        )

    # 548D3B: the arm's lane is a **legal-domain** choice, not a read-back of
    # whatever the seed happened to say. The labels this page will print are
    # boxes the plan does not own, and a lane that puts the arm's reserve or its
    # two planned leads across one of them is the defect that refused the
    # topology page at `labels[3]`. With no corridor stated the seed lane is the
    # only candidate and the answer is the pre-548D3B one, value for value.
    chosen, refusal = _choose_series_lane(
        request, template, seed, build, lane,
    )
    if refusal is not None:
        return _series_refusal_plan(template, *refusal)
    plan = build(chosen)
    return plan


def _current_series_boxes(
    request: PlacementInput, plan: BoundSeriesSeatPlan, seed: _State
) -> tuple[Box, ...]:
    assert plan.first_origin is not None and plan.second_origin is not None
    return _series_boxes(
        request, plan, seed.origins[plan.host_part], seed.poses[plan.host_part],
        plan.first_origin, plan.second_origin,
    )


def _current_series_guards(
    request: PlacementInput, plan: BoundSeriesSeatPlan, seed: _State
) -> tuple[Box, ...]:
    assert plan.first_origin is not None and plan.second_origin is not None
    return _series_guards(
        request, plan, seed.origins[plan.host_part], seed.poses[plan.host_part],
        plan.first_origin, plan.second_origin,
    )


def _current_series_path(
    request: PlacementInput, plan: BoundSeriesSeatPlan, seed: _State
) -> tuple[tuple[float, float], ...]:
    assert plan.first_origin is not None and plan.second_origin is not None
    return _series_geometry(
        request, plan, seed.origins[plan.host_part], seed.poses[plan.host_part],
        plan.first_origin, plan.second_origin,
    )[4]


def _current_series_roles(
    request: PlacementInput, plan: BoundSeriesSeatPlan, seed: _State
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    assert plan.first_origin is not None and plan.second_origin is not None
    return _series_roles(
        request, plan, seed.origins[plan.host_part], seed.poses[plan.host_part],
        plan.first_origin, plan.second_origin,
    )


def _separate_series_plan_lanes(
    request: PlacementInput,
    seed: _State,
    plans: Sequence[BoundSeriesSeatPlan],
) -> list[BoundSeriesSeatPlan]:
    """Allocate the arms' lanes jointly so two arms do not press on each other.

    A single arm keeps the lateral the ordinary seed gave it. When a second arm
    would share that lane, the later arm — declaration order, so the answer is
    deterministic — moves as one whole arm (both parts by the same vector) until
    its two **part boxes** clear the earlier one's. Only the part bodies are
    compared: two arms hanging from the same host pin necessarily share that pin,
    so their host corridors meet there and are not a conflict. The shift is the
    measured lateral overlap plus one lattice step, not a tuned spacing.
    """
    current = list(plans)
    if len(current) < 2:
        return current
    for _ in range(max(1, len(current) * 2)):
        shifted = False
        for i in range(len(current)):
            if not current[i].seated:
                continue
            for j in range(i + 1, len(current)):
                if not current[j].seated:
                    continue
                left = _current_series_boxes(request, current[i], seed)[:2]
                right = _current_series_boxes(request, current[j], seed)[:2]
                overlap: tuple[Box, Box] | None = None
                for first_box in left:
                    for second_box in right:
                        if _overlap_area(first_box, second_box) > 0.0:
                            overlap = (first_box, second_box)
                            break
                    if overlap is not None:
                        break
                if overlap is None:
                    continue
                axis = _unit(current[j].lateral)
                left_span = _axis_interval(overlap[0], axis)
                right_span = _axis_interval(overlap[1], axis)
                overlap_span = min(left_span[1], right_span[1]) - max(
                    left_span[0], right_span[0]
                )
                if overlap_span <= 0.0:
                    overlap_span = 0.0
                left_centre = _series_centre(overlap[0])
                right_centre = _series_centre(overlap[1])
                sign = 1.0 if _dot(
                    (right_centre[0] - left_centre[0],
                     right_centre[1] - left_centre[1]), axis
                ) >= 0.0 else -1.0
                # The joint lane move is a coordinate step: round it up to the
                # shared lattice, or a second arm's origin leaves the grid and
                # the topology round's own lattice check refuses the answer.
                step = math.ceil(
                    (overlap_span + current[j].grid + current[j].clearance)
                    / current[j].grid
                ) * current[j].grid
                shift = (axis[0] * sign * step, axis[1] * sign * step)
                assert current[j].first_origin is not None
                assert current[j].second_origin is not None
                # 548D3B: a joint lane move is a **seat** move, so it lands in
                # the same legal domain the binding used. A move that walks the
                # arm onto a label is not taken; the opposite side is tried
                # before the pair is refused, so the search can never quietly
                # re-adopt an illegal lane.
                moved = _lane_shift_is_legal(request, current[j], shift, seed)
                if not moved:
                    back = (-shift[0], -shift[1])
                    if _lane_shift_is_legal(request, current[j], back, seed):
                        shift = back
                        moved = True
                if not moved:
                    continue
                current[j] = replace(
                    current[j],
                    first_origin=(
                        current[j].first_origin[0] + shift[0],
                        current[j].first_origin[1] + shift[1],
                    ),
                    second_origin=(
                        current[j].second_origin[0] + shift[0],
                        current[j].second_origin[1] + shift[1],
                    ),
                )
                shifted = True
        if not shifted:
            break
    for i in range(len(current)):
        if not current[i].seated:
            continue
        for j in range(i + 1, len(current)):
            if not current[j].seated:
                continue
            left = _current_series_boxes(request, current[i], seed)[:2]
            right = _current_series_boxes(request, current[j], seed)[:2]
            if any(_overlap_area(a, b) > 0.0 for a in left for b in right):
                current[j] = replace(
                    current[j], first_origin=None, second_origin=None,
                    reserved_boxes=(),
                    refusal=SeriesSeatRefusal(
                        branch_id=current[j].branch_id,
                        subject=f"{current[i].branch_id} and {current[j].branch_id}",
                        detail=(
                            "the two arms' reserved boxes still overlap after the "
                            "joint lane allocation"
                        ),
                        action=(
                            "move the arms to different lanes, shorten an arm, or "
                            "drop one seriesBranches entry"
                        ),
                    ),
                )
    return current


def _lane_shift_is_legal(
    request: PlacementInput,
    plan: BoundSeriesSeatPlan,
    shift: tuple[float, float],
    seed: _State,
) -> bool:
    """Would this whole-arm shift keep the seat out of every label box?

    The same footprint the binding used — reserved boxes plus the two planned
    legs — measured at the shifted origins. With no corridor stated the answer
    is ``True`` and the historical lane allocation is untouched.
    """
    labels = _foreign_labels(
        request, seed.origins, seed.poses,
        frozenset((plan.first_part, plan.second_part)),
    )
    if not labels:
        return True
    if plan.first_origin is None or plan.second_origin is None:
        return True
    moved = replace(
        plan,
        first_origin=(
            plan.first_origin[0] + shift[0], plan.first_origin[1] + shift[1],
        ),
        second_origin=(
            plan.second_origin[0] + shift[0], plan.second_origin[1] + shift[1],
        ),
        lane=plan.lane + _dot(shift, _unit(plan.lateral)),
    )
    boxes = _series_boxes(
        request, moved, seed.origins[moved.host_part],
        seed.poses[moved.host_part], moved.first_origin, moved.second_origin,
    )
    footprint = boxes + _series_lead_boxes(request, moved, seed)
    if any(
        _overlap_area(box, label) > 0.0
        for box in footprint for _corridor, label in labels
    ):
        return False
    tips, leads = _pin_walls(
        request, seed, frozenset((moved.host_part, moved.first_part, moved.second_part)),
    )
    return not _path_hits_walls(moved.host_path, tips, leads)


def _series_yield_step(
    origin: tuple[float, float],
    box: Box,
    hits: Sequence[Box],
    axis: tuple[float, float],
    grid: float,
    clearance: float,
    sign: float | None = None,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """The deterministic move that clears a foreign part from these boxes.

    ``sign`` states which way the move leaves; ``None`` — the historical reading
    — takes the side the part is already on. 548D3B asks for **both** sides,
    because the side the part happens to be on is not always a legal seat: the
    MCU's `S1` was pushed into the LCD_SCK label row by exactly that default.
    """
    spans = [_axis_interval(item, axis) for item in hits]
    low = min(span[0] for span in spans)
    high = max(span[1] for span in spans)
    part_low, part_high = _axis_interval(box, axis)
    union = (
        min(item[0] for item in hits), min(item[1] for item in hits),
        max(item[2] for item in hits), max(item[3] for item in hits),
    )
    part_centre = _series_centre(box)
    union_centre = _series_centre(union)
    if sign is None:
        side = _dot(
            (part_centre[0] - union_centre[0], part_centre[1] - union_centre[1]), axis
        )
        sign = 1.0 if side >= 0.0 else -1.0
    needed = (high - part_low) if sign > 0 else (part_high - low)
    step = max(grid, math.ceil((needed + grid + clearance) / grid) * grid)
    shift = (axis[0] * sign * step, axis[1] * sign * step)
    target = (origin[0] + shift[0], origin[1] + shift[1])
    return (axis[0] * sign, axis[1] * sign), target, shift


def _series_yield_options(
    origin: tuple[float, float],
    box: Box,
    hits: Sequence[Box],
    axis: tuple[float, float],
    grid: float,
    clearance: float,
) -> list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]]:
    """Both ways out of these boxes, nearer one first."""
    out = [
        _series_yield_step(origin, box, hits, axis, grid, clearance, sign=sign)
        for sign in (1.0, -1.0)
    ]
    return sorted(out, key=lambda item: math.hypot(item[2][0], item[2][1]))


def _yield_target_is_legal(
    request: PlacementInput,
    part_id: str,
    pose: SymbolPose,
    origin: tuple[float, float],
    target: tuple[float, float],
    others: Mapping[str, Box],
    labels: Sequence[Box],
    pins: Sequence[tuple[float, float]],
) -> bool:
    """Is this a seat the part may actually take, and a way it may take it?

    Three readings, all of them geometry the plan already has: the part's box at
    the target may not overlap another part's box, a label's default box or a
    foreign pin tip; and the sweep from where it stands to where it would stand
    — the leads that move with it — may not cross a label box either. A pin
    joining another net is a short, so a tip inside the new box is refused for
    the same reason a body is.
    """
    profile = request.part(part_id).profile
    before = part_box(profile, pose, origin)
    after = part_box(profile, pose, target)
    sweep = (
        min(before[0], after[0]), min(before[1], after[1]),
        max(before[2], after[2]), max(before[3], after[3]),
    )
    for box in labels:
        if _overlap_area(after, box) > 0.0 or _overlap_area(sweep, box) > 0.0:
            return False
    for other_id, other in others.items():
        if other_id == part_id:
            continue
        if _overlap_area(after, other) > 0.0:
            return False
    for point in pins:
        if after[0] < point[0] < after[2] and after[1] < point[1] < after[3]:
            return False
    return True


def _foreign_pin_points(
    request: PlacementInput, state: _State, owned: frozenset[str]
) -> tuple[tuple[float, float], ...]:
    """Every pin tip of a part this seat may not touch, in page coordinates."""
    out: list[tuple[float, float]] = []
    for part in request.parts:
        if part.part_id in owned:
            continue
        pose = state.poses.get(part.part_id)
        origin = state.origins.get(part.part_id)
        if pose is None or origin is None:
            continue
        out.extend(posed_tip(pin.tip, pose, origin) for pin in part.profile.pins)
    return tuple(out)


def _series_yields_for(
    request: PlacementInput,
    plan: BoundSeriesSeatPlan,
    seed: _State,
    boxes: Mapping[str, Box],
    arm_owner: Mapping[str, str],
    host_owner: Mapping[str, str],
) -> list[SeriesSeatYield]:
    """Who the binder asked to move, from where, and where to.

    548D3B splits the two questions: a part the seat **may** move is asked
    against the walkable reserve (where the arm's wires really go), a part it may
    **not** move — a power/decoupling branch or an engineer lock — is asked
    against the conservative guard. Same rule in
    :func:`_series_reservation_terms` and :func:`_repair_series_yields`, so no
    reader can hold one geometry and another the other.
    """
    if not plan.seated:
        return []
    reserved = _current_series_boxes(request, plan, seed)
    guards = _current_series_guards(request, plan, seed)
    owned = plan.owned_parts()
    axis = _unit(plan.lateral)
    out: list[SeriesSeatYield] = []
    for part in request.parts:
        part_id = part.part_id
        if part_id in owned:
            continue
        box = boxes[part_id]
        movable = (
            part.locked_origin is None
            and part.locked is None
            and part_id not in arm_owner
            and part_id not in host_owner
            and (plan.yield_parts is None or part_id in plan.yield_parts)
        )
        probe = reserved if movable or part_id in arm_owner else guards
        hits = [
            (index, item) for index, item in enumerate(probe)
            if _overlap_area(box, item) > 0.0
        ]
        if not hits:
            continue
        if part.locked_origin is not None or part.locked is not None:
            out.append(SeriesSeatYield(
                part_id=part_id, branch_id=plan.branch_id,
                box_index=hits[0][0],
                refusal=(
                    "the part carries an engineer lock; a series seat may not "
                    "move it"
                ),
            ))
            continue
        if part_id in arm_owner:
            # A member of another arm is not an ordinary part: the two arms are
            # allocated lanes as wholes, and the lanes' host corridors may meet
            # at the shared host pin. Its part boxes are kept apart by
            # `_separate_series_plan_lanes`, not by a yield entry.
            continue
        if part_id in host_owner:
            out.append(SeriesSeatYield(
                part_id=part_id, branch_id=plan.branch_id,
                box_index=hits[0][0],
                refusal=(
                    f"the part is the host of series branch "
                    f"{host_owner[part_id]!r}; moving it would move that arm"
                ),
            ))
            continue
        if plan.yield_parts is not None and part_id not in plan.yield_parts:
            out.append(SeriesSeatYield(
                part_id=part_id, branch_id=plan.branch_id,
                box_index=hits[0][0],
                refusal=(
                    "the part is not an ordinary signal branch this seat may "
                    "move; its reserved-box hard is kept for the caller"
                ),
            ))
            continue
        direction, target, _ = _series_yield_step(
            seed.origins[part_id], box, [item for _, item in hits],
            axis, plan.grid, plan.clearance,
        )
        # 548D3B: the part must be able to **stand** where the yield puts it, and
        # to get there without dragging its leads across something it must not
        # touch. Both ways out are tried, the nearer legal one wins; when neither
        # is legal the seat names that instead of moving the part anyway.
        labels = tuple(
            item for _corridor, item in _foreign_labels(
                request, seed.origins, seed.poses,
                frozenset((plan.first_part, plan.second_part, part_id)),
            )
        )
        pins = _foreign_pin_points(
            request, seed, frozenset((plan.first_part, plan.second_part, part_id)),
        )
        for candidate_direction, candidate_target, _shift in _series_yield_options(
            seed.origins[part_id], box, [item for _, item in hits],
            axis, plan.grid, plan.clearance,
        ):
            if _yield_target_is_legal(
                request, part_id, seed.poses[part_id], seed.origins[part_id],
                candidate_target, boxes, labels, pins,
            ):
                direction, target = candidate_direction, candidate_target
                break
        else:
            out.append(SeriesSeatYield(
                part_id=part_id, branch_id=plan.branch_id,
                box_index=hits[0][0],
                refusal=(
                    "neither way out of the reserved box is a seat this branch "
                    "may take — both would put it on a label, another part or a "
                    "foreign pin"
                ),
            ))
            continue
        out.append(SeriesSeatYield(
            part_id=part_id, branch_id=plan.branch_id,
            box_index=hits[0][0], direction=direction, target=target,
        ))
    return out


def _series_plan_lane(
    request: PlacementInput, plan: BoundSeriesSeatPlan, seed: _State
) -> float:
    """The lane read back from the first origin, against the no-lane seat.

    The no-lane seat is the compiler equation with ``lane = 0``: the host foot
    plus half a pitch along progress, minus the first part's posed from tip.
    The lane is the lateral component of the first origin's offset from that
    point, so a single arm keeps exactly the lateral the ordinary seed gave its
    first part.
    """
    assert plan.first_origin is not None
    assert plan.first_pose is not None
    host_tip = _series_pin_point(request, plan.host_part, plan.host_token, seed)
    if host_tip is None:
        return plan.lane
    first_part = request.part(plan.first_part)
    lead = _series_local_tip(
        first_part.profile, plan.first_from_token, plan.first_pose
    )
    if lead is None:
        return plan.lane
    progress = _unit(plan.progress)
    no_lane = (
        host_tip[0] + progress[0] * plan.pitch / 2.0 - lead[0],
        host_tip[1] + progress[1] * plan.pitch / 2.0 - lead[1],
    )
    return _dot(
        (plan.first_origin[0] - no_lane[0], plan.first_origin[1] - no_lane[1]),
        _unit(plan.lateral),
    )


def _bind_series_plans(
    request: PlacementInput,
    seed: _State,
    pitch_origins: Mapping[str, tuple[float, float]] | None = None,
) -> tuple[BoundSeriesSeatPlan, ...]:
    """Bind every template once, after the ordinary seed and before evaluation.

    The pair pitch is measured here from the seed's own two **origins** and never
    again: every restart receives this tuple, and the move projection below
    preserves it. Snapping may quantize the measured distance; the nominal pitch
    stays the plan's source and :meth:`BoundSeriesSeatPlan.origin_pitch` is the
    final-geometry reading. With no template the result is the empty tuple and
    the caller takes the historical path unchanged.
    """
    if not request.series_templates:
        return ()
    boxes = _boxes_of(request, seed)
    plans = [
        _bind_one_series_plan(request, template, seed, pitch_origins)
        for template in request.series_templates
    ]
    plans = _separate_series_plan_lanes(request, seed, plans)
    arm_owner = {
        template.first.part_id: template.branch_id
        for template in request.series_templates
    }
    arm_owner.update({
        template.second.part_id: template.branch_id
        for template in request.series_templates
    })
    host_owner = {
        template.host_part: template.branch_id
        for template in request.series_templates
    }
    out: list[BoundSeriesSeatPlan] = []
    for plan in plans:
        if not plan.seated:
            out.append(plan)
            continue
        plan = replace(
            plan,
            lane=_series_plan_lane(request, plan, seed),
            reserved_boxes=_current_series_boxes(request, plan, seed),
            guard_boxes=_current_series_guards(request, plan, seed),
            host_path=_current_series_path(request, plan, seed),
        )
        yields = _series_yields_for(
            request, plan, seed, boxes, arm_owner, host_owner,
        )
        out.append(replace(plan, yields=tuple(yields)))
    return tuple(out)


def _seat_series_arms(
    plans: Sequence[BoundSeriesSeatPlan], state: _State
) -> None:
    """Put both parts of every bound arm on its seat, before evaluation.

    The ordinary seed placed the two parts wherever the chain line left them;
    the plan is the seat the search must start from. This is the one write that
    makes the seed and every restart share the same frozen pitch.
    """
    for plan in plans:
        if not plan.seated:
            continue
        assert plan.first_origin is not None and plan.second_origin is not None
        assert plan.first_pose is not None and plan.second_pose is not None
        state.origins[plan.first_part] = plan.first_origin
        state.origins[plan.second_part] = plan.second_origin
        state.poses[plan.first_part] = plan.first_pose
        state.poses[plan.second_part] = plan.second_pose


def _apply_series_yields(
    plans: Sequence[BoundSeriesSeatPlan], state: _State
) -> None:
    """Move the named ordinary parts to the points their plan recorded."""
    for plan in plans:
        for item in plan.yields:
            if item.refusal or item.target is None:
                continue
            state.origins[item.part_id] = item.target


def _repair_series_yields(
    request: PlacementInput,
    plans: Sequence[BoundSeriesSeatPlan],
    state: _State,
) -> None:
    """Deterministically move ordinary parts out of reserved boxes.

    A repair-by-name, not a random walk: the part's own box and the reserved box
    measure the shortest lateral escape, and the part is put on the next lattice
    point beyond it. Locked parts and any part a plan owns do not move — their
    hard violation is what the caller sees and refuses.
    """
    usable = [plan for plan in plans if plan.seated]
    if not usable:
        return
    owned: set[str] = set()
    for plan in usable:
        owned.update(plan.owned_parts())
    boxes = _boxes_of(request, state)
    for _ in range(2):
        moved = False
        for plan in usable:
            reserved = _series_boxes(
                request, plan, state.origins[plan.host_part],
                state.poses[plan.host_part],
                state.origins[plan.first_part], state.origins[plan.second_part],
            )
            axis = _unit(plan.lateral)
            for part in request.parts:
                part_id = part.part_id
                if part_id in owned:
                    continue
                if part.locked_origin is not None or part.locked is not None:
                    continue
                if (
                    plan.yield_parts is not None
                    and part_id not in plan.yield_parts
                ):
                    continue
                hits = [
                    item for item in reserved
                    if _overlap_area(boxes[part_id], item) > 0.0
                ]
                if not hits:
                    continue
                # 548D3B: the same legal domain the bound yields use. Both ways
                # out are tried and only a legal seat is taken; a part with no
                # legal way out keeps its hard violation for the caller to name.
                labels = tuple(
                    item for _corridor, item in _foreign_labels(
                        request, state.origins, state.poses,
                        frozenset((plan.first_part, plan.second_part, part_id)),
                    )
                )
                pins = _foreign_pin_points(
                    request, state, frozenset((plan.first_part, plan.second_part, part_id)),
                )
                for _direction, target, _shift in _series_yield_options(
                    state.origins[part_id], boxes[part_id], hits,
                    axis, plan.grid, plan.clearance,
                ):
                    if not _yield_target_is_legal(
                        request, part_id, state.poses[part_id],
                        state.origins[part_id], target, boxes, labels, pins,
                    ):
                        continue
                    state.origins[part_id] = target
                    boxes[part_id] = part_box(
                        part.profile, state.poses[part_id], state.origins[part_id]
                    )
                    moved = True
                    break
        if not moved:
            break


def _project_series(
    request: PlacementInput,
    plans: Sequence[BoundSeriesSeatPlan],
    before: _State,
    candidate: _State,
) -> _State:
    """Carry every bound arm with the move just made.

    Three statements, applied after **any** candidate move:

    * a host that translated or turned carries its whole arm — both parts move
      by the host pin's own delta, so the seat stays measured from the pin;
    * an arm part may only move the arm **jointly**; the move is projected onto
      ``lateral``, so the seat along ``progress`` and the frozen pitch stay put;
    * the arm's poses are the template's, never a turned or swapped one.

    With no plan the function is not called at all, so an undeclared request
    consumes the same random numbers and produces the same answer it always did.
    """
    usable = [plan for plan in plans if plan.seated]
    if not usable:
        return candidate
    for plan in usable:
        host = plan.host_part
        first = plan.first_part
        second = plan.second_part
        if any(
            part_id not in before.origins or part_id not in candidate.origins
            for part_id in (host, first, second)
        ):
            continue
        delta_first = (
            candidate.origins[first][0] - before.origins[first][0],
            candidate.origins[first][1] - before.origins[first][1],
        )
        delta_second = (
            candidate.origins[second][0] - before.origins[second][0],
            candidate.origins[second][1] - before.origins[second][1],
        )
        host_moved = (
            candidate.origins[host] != before.origins[host]
            or candidate.poses[host] != before.poses[host]
        )
        arm_moved = delta_first != (0.0, 0.0) or delta_second != (0.0, 0.0)
        if arm_moved:
            axis = _unit(plan.lateral)
            delta = delta_first if delta_first != (0.0, 0.0) else delta_second
            along = _dot(delta, axis)
            joint = (axis[0] * along, axis[1] * along)
            candidate.origins[first] = (
                before.origins[first][0] + joint[0],
                before.origins[first][1] + joint[1],
            )
            candidate.origins[second] = (
                before.origins[second][0] + joint[0],
                before.origins[second][1] + joint[1],
            )
        elif host_moved:
            old_tip = _series_pin_point(request, host, plan.host_token, before)
            new_tip = _series_pin_point(request, host, plan.host_token, candidate)
            if old_tip is not None and new_tip is not None:
                delta = (new_tip[0] - old_tip[0], new_tip[1] - old_tip[1])
                candidate.origins[first] = (
                    before.origins[first][0] + delta[0],
                    before.origins[first][1] + delta[1],
                )
                candidate.origins[second] = (
                    before.origins[second][0] + delta[0],
                    before.origins[second][1] + delta[1],
                )
        candidate.poses[first] = plan.first_pose
        candidate.poses[second] = plan.second_pose
    _repair_series_yields(request, plans, candidate)
    return candidate


def _series_reservation_terms(
    request: PlacementInput,
    state: _State,
    plans: Sequence[BoundSeriesSeatPlan],
    boxes: Mapping[str, Box],
) -> list[CostTerm]:
    """The named hard terms: an ordinary part inside an arm's reserved boxes."""
    if not plans:
        return []
    series_members: set[str] = set()
    member_owner: dict[str, BoundSeriesSeatPlan] = {}
    for plan in plans:
        for part_id in (plan.first_part, plan.second_part):
            series_members.add(part_id)
            member_owner[part_id] = plan
    hosts = {plan.host_part: plan.branch_id for plan in plans}
    out: list[CostTerm] = []
    for plan in plans:
        if not plan.seated:
            detail = (
                plan.refusal.render() if plan.refusal is not None
                else f"series branch {plan.branch_id} has no bound seat"
            )
            out.append(CostTerm(
                f"series-seat:{plan.branch_id}", 1.0, detail, hard=True,
            ))
            continue
        # Measured on the **answer's** origins, not on the plan's own record: this
        # term is about where the parts stand in this answer, and a plan bound
        # before the search is exactly what that term has to disagree with.
        current = replace(
            plan,
            first_origin=state.origins.get(plan.first_part, plan.first_origin),
            second_origin=state.origins.get(plan.second_part, plan.second_origin),
        )
        reserved = _current_series_boxes(request, current, state)
        guards = _current_series_guards(request, current, state)
        reserved_roles, guard_roles = _current_series_roles(request, current, state)
        owned = plan.owned_parts()
        total = 0.0
        offenders: list[str] = []
        for part_id, box in boxes.items():
            if part_id in owned:
                continue
            part = request.part(part_id)
            # The ownership rule, stated once: a part this seat may move (or a
            # member of another arm, which is separated by lane allocation) is
            # measured against the walkable reserve; anything else — a
            # power/decoupling branch, an engineer lock, another arm's host — is
            # measured against the conservative guard, so its hard stays.
            movable = (
                part.locked_origin is None
                and part.locked is None
                and part_id not in series_members
                and part_id not in hosts
                and (plan.yield_parts is None or part_id in plan.yield_parts)
            )
            if movable or part_id in series_members:
                probe, roles = reserved, reserved_roles
            else:
                probe, roles = guards, guard_roles
            hits: list[tuple[int, float]] = []
            for index, item in enumerate(probe):
                area = _overlap_area(box, item)
                if area <= 0.0:
                    continue
                if part_id in series_members:
                    other = member_owner[part_id]
                    # The single structural exemption: two arms hanging from
                    # the **same host pin** necessarily share the host-to-first
                    # corridor at that pin. Any other crossing — a part box, the
                    # middle corridor, or a different host pin — stays hard, so
                    # an inter-arm crossing is never silently called clear.
                    shared_pin = (
                        roles[index] == "host"
                        and other.host_part == plan.host_part
                        and other.host_token == plan.host_token
                    )
                    if shared_pin:
                        continue
                hits.append((index, area))
            if not hits:
                continue
            total += sum(area for _, area in hits)
            if part_id in series_members:
                other = member_owner[part_id]
                offenders.append(
                    f"{part_id} (arm {other.branch_id}) in box(es) "
                    + ", ".join(str(i) for i, _ in hits)
                )
            else:
                offenders.append(
                    f"{part_id} in box(es) " + ", ".join(str(i) for i, _ in hits)
                )
        detail = (
            "reserved boxes are clear" if not offenders
            else "parts inside the arm's reserved boxes: "
                 + "; ".join(sorted(offenders))
        )
        out.append(CostTerm(
            f"series-reservation:{plan.branch_id}", total, detail, hard=True,
        ))
    return out


def _refresh_series_plans(
    request: PlacementInput,
    plans: Sequence[BoundSeriesSeatPlan],
    state: _State,
) -> tuple[BoundSeriesSeatPlan, ...]:
    """Re-seat the plan's own report on the answer the search returned.

    The pitch never changes; origins, lane, reserved boxes **and the yield
    mapping** do, because that is where the arm and the ordinary parts ended up.
    Recomputing yields here is what keeps the four readings one report: a part
    the search moved away is no longer listed as yielding, and a part the search
    moved into a box is listed with a target measured from the final state.
    """
    if not plans:
        return ()
    arm_owner: dict[str, str] = {}
    host_owner: dict[str, str] = {}
    for plan in plans:
        arm_owner[plan.first_part] = plan.branch_id
        arm_owner[plan.second_part] = plan.branch_id
        host_owner[plan.host_part] = plan.branch_id
    boxes = _boxes_of(request, state)
    seated: list[BoundSeriesSeatPlan] = []
    for plan in plans:
        if not plan.seated:
            seated.append(plan)
            continue
        first_origin = state.origins[plan.first_part]
        second_origin = state.origins[plan.second_part]
        candidate = replace(
            plan, first_origin=first_origin, second_origin=second_origin,
        )
        seated.append(replace(
            candidate,
            lane=_series_plan_lane(request, candidate, state),
            reserved_boxes=_current_series_boxes(request, candidate, state),
            guard_boxes=_current_series_guards(request, candidate, state),
            host_path=_current_series_path(request, candidate, state),
        ))
    out: list[BoundSeriesSeatPlan] = []
    for plan in seated:
        if not plan.seated:
            out.append(plan)
            continue
        out.append(replace(
            plan,
            yields=tuple(_series_yields_for(
                request, plan, state, boxes, arm_owner, host_owner,
            )),
        ))
    return tuple(out)


# ------------------------------------------------------- the draw consumers


def bind_series(
    request: PlacementInput,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
    pitch_origins: Mapping[str, tuple[float, float]] | None = None,
) -> tuple[BoundSeriesSeatPlan, ...]:
    """Bind the declared arms once against an existing ordinary layout.

    The draw consumers (``drawcompiler._place_chain_and_shelf`` and
    ``_topology_placement``) call this with the layout they already have; it is
    the same :func:`_bind_series_plans` the search uses, not a second seat
    equation. Empty templates return the empty tuple.

    ``pitch_origins`` is the **ordinary construction seed** the pair pitch is
    measured on, when that seed is no longer what the caller hands in: the base
    consumer runs its bound-order pass first, and the pair pitch belongs to the
    construction, not to a layout a later pass has already walked (548D3B,
    structural-findings sec.1). ``None`` — every other caller — measures on the
    origins given, exactly as before.
    """
    return _bind_series_plans(
        request, _State(dict(origins), dict(poses)), pitch_origins,
    )


def series_lane_options(
    request: PlacementInput,
    plan: BoundSeriesSeatPlan,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
) -> tuple[float, ...]:
    """The lanes this bound arm may be re-seated on, shortest escape first (548D3B).

    Enumeration only: it seats nothing and ranks no page. The domain is the
    plan's own geometry — ``0`` and the lane the binder chose — plus the lateral
    edges of the real obstacles on this page: the label boxes the binder already
    reads, every foreign pin tip and lead, and the boxes of the ordinary parts.
    Each obstacle edge is projected onto the shared lattice the way
    :func:`_choose_series_lane` projects a label, so a candidate lane is "this
    arm one grid step past a thing that is really there", never a scan of
    numbers. Ordering is the shortest escape: ``0`` (the host row) first, then
    smaller magnitudes, ties towards ``+lateral``; the caller decides which of
    them actually builds.

    The seed lane is **not** returned: that seat is the plan the placement
    already carries, and re-offering it would spend a whole build on it.
    """
    if not plan.seated or plan.first_origin is None or plan.second_origin is None:
        return ()
    state = _State(dict(origins), dict(poses))
    lateral = _unit(plan.lateral)
    progress = _unit(plan.progress)
    owned = frozenset((plan.first_part, plan.second_part))
    labels = _foreign_labels(request, origins, poses, owned)
    tips, leads = _pin_walls(
        request, state,
        frozenset((plan.host_part, plan.first_part, plan.second_part)),
    )
    ordinary = [
        box for part_id, box in _boxes_of(request, state).items()
        if part_id not in owned and part_id != plan.host_part
    ]
    # The arm's own extent at lane 0: the obstacle edges are projected off this,
    # exactly as the binder projects them off its no-lane seat.
    zero_first = (
        plan.first_origin[0] - lateral[0] * plan.lane,
        plan.first_origin[1] - lateral[1] * plan.lane,
    )
    zero_second = (
        plan.second_origin[0] - lateral[0] * plan.lane,
        plan.second_origin[1] - lateral[1] * plan.lane,
    )
    base = _series_boxes(
        request, plan, state.origins[plan.host_part], state.poses[plan.host_part],
        zero_first, zero_second,
    )
    if not base:
        return ()
    grid = plan.grid
    lateral_spans = [_axis_interval(box, lateral) for box in base]
    low = min(span[0] for span in lateral_spans)
    high = max(span[1] for span in lateral_spans)
    progress_spans = [_axis_interval(box, progress) for box in base]
    p_low = min(span[0] for span in progress_spans)
    p_high = max(span[1] for span in progress_spans)
    obstacles = [box for _corridor, box in labels]
    obstacles.extend(leads)
    obstacles.extend(ordinary)
    obstacles.extend(
        (tip[0] - grid / 2.0, tip[1] - grid / 2.0,
         tip[0] + grid / 2.0, tip[1] + grid / 2.0)
        for tip in tips
    )
    lanes = [0.0, plan.lane]
    for box in obstacles:
        span = _axis_interval(box, progress)
        if span[1] < p_low or span[0] > p_high:
            continue
        lateral_span = _axis_interval(box, lateral)
        lanes.append(_lane_on_grid(lateral_span[0] - grid - high, grid))
        lanes.append(_lane_on_grid(lateral_span[1] + grid - low, grid))
    ordered = sorted(set(lanes), key=lambda lane: (abs(lane), -lane))
    return tuple(lane for lane in ordered if abs(lane - plan.lane) > SERIES_EPS)


def separate_series_lanes(
    request: PlacementInput,
    plans: Sequence[BoundSeriesSeatPlan],
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
) -> tuple[BoundSeriesSeatPlan, ...]:
    """Apply the binder's joint lane allocation to already-bound plans (548D3B).

    A re-seat that moves one arm's lane has to keep the page's own rule about two
    arms pressing on each other, and that rule lives in
    :func:`_separate_series_plan_lanes` — the same one :func:`bind_series` runs.
    Only the arms' origins move here; the caller re-seats them through
    :func:`place_series_seats`, which is what restates the boxes, the lane and
    the yields.
    """
    if len(plans) < 2:
        return tuple(plans)
    return tuple(_separate_series_plan_lanes(
        request, _State(dict(origins), dict(poses)), plans,
    ))


def place_series_seats(
    request: PlacementInput,
    plans: Sequence[BoundSeriesSeatPlan],
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
) -> tuple[tuple[BoundSeriesSeatPlan, ...], _State]:
    """Seat the arms, apply their yields, then report the final plans.

    Returns the refreshed plans and a **new** state; the caller decides when to
    copy the state back into its placement. This is the one consumer path: the
    base layout and the topology answer both use it, so neither can invent its
    own pitch or its own yield rule.
    """
    state = _State(dict(origins), dict(poses))
    if not plans:
        return (), state
    _seat_series_arms(plans, state)
    _apply_series_yields(plans, state)
    _repair_series_yields(request, plans, state)
    return _refresh_series_plans(request, plans, state), state


# ------------------------------------------------- the flag corridor binder


def _flag_box_at(pin: tuple[float, float], box: Box) -> Box:
    return (
        pin[0] + box[0], pin[1] + box[1], pin[0] + box[2], pin[1] + box[3],
    )


def _flag_path_at(
    pin: tuple[float, float], path: Sequence[tuple[float, float]]
) -> tuple[tuple[float, float], ...]:
    return tuple((pin[0] + point[0], pin[1] + point[1]) for point in path)


def _flag_lead_boxes(
    path: Sequence[tuple[float, float]]
) -> tuple[Box, ...]:
    return tuple(_span_box(start, end, 0.0) for start, end in zip(path, path[1:]))


def _flag_segments_cross(
    first: tuple[tuple[float, float], tuple[float, float]],
    second: tuple[tuple[float, float], tuple[float, float]],
) -> bool:
    """Do two axis-aligned segments share at least one point (touching included)?"""
    fx0, fx1 = sorted((first[0][0], first[1][0]))
    fy0, fy1 = sorted((first[0][1], first[1][1]))
    sx0, sx1 = sorted((second[0][0], second[1][0]))
    sy0, sy1 = sorted((second[0][1], second[1][1]))
    return (
        max(fx0, sx0) <= min(fx1, sx1) + SERIES_EPS
        and max(fy0, sy0) <= min(fy1, sy1) + SERIES_EPS
    )


def _flag_segment_hits_box(
    segment: tuple[tuple[float, float], tuple[float, float]], box: Box
) -> bool:
    """Does this axis-aligned lead leg run **through** the box?

    A lead is a line, not an area, so the box test cannot be an area overlap — a
    zero-width leg against a box always has zero area and would let every lead
    run straight through every flag. Touching an edge is not entering it; the
    readings match :func:`_overlap_area`'s "touching is not overlapping".
    """
    (ax, ay), (bx, by) = segment
    low_x, high_x = sorted((ax, bx))
    low_y, high_y = sorted((ay, by))
    return (
        low_x < box[2] and high_x > box[0]
        and low_y < box[3] and high_y > box[1]
    )


def _flag_seat_conflict(
    first: BoundFlagCorridorSeat, second: BoundFlagCorridorSeat
) -> str:
    """Why these two seats cannot both be drawn, or ``""``.

    Same-net flags are exempt: one net's own flags are one connection repeated,
    and the page may draw them as close as it likes. The exemption stops there —
    two **different** nets may share neither a flag box, nor a lead running into
    the other's box, nor a lead crossing the other's lead.
    """
    if first.net_id == second.net_id:
        return ""
    if _overlap_area(first.box, second.box) > 0.0:
        return (
            f"the {first.net_id} and {second.net_id} flag boxes overlap"
        )
    for segment in zip(first.lead, first.lead[1:]):
        if _flag_segment_hits_box(segment, second.box):
            return (
                f"the {first.net_id} lead runs into the {second.net_id} flag box"
            )
    for segment in zip(second.lead, second.lead[1:]):
        if _flag_segment_hits_box(segment, first.box):
            return (
                f"the {second.net_id} lead runs into the {first.net_id} flag box"
            )
    for left in zip(first.lead, first.lead[1:]):
        for right in zip(second.lead, second.lead[1:]):
            if _flag_segments_cross(left, right):
                return (
                    f"the {first.net_id} and {second.net_id} flag leads cross"
                )
    return ""


def _flag_page_problem(
    box: Box, page_box: Box | None, keepouts: Sequence[Box]
) -> str:
    if page_box is not None and (
        box[0] < page_box[0] - SERIES_EPS
        or box[1] < page_box[1] - SERIES_EPS
        or box[2] > page_box[2] + SERIES_EPS
        or box[3] > page_box[3] + SERIES_EPS
    ):
        return "the flag leaves the page box"
    for keepout in keepouts:
        if _overlap_area(box, keepout) > 0.0:
            return "the flag stands on a keep-out"
    return ""


def _flag_seat_problem(
    seat: BoundFlagCorridorSeat,
    obstacles: "_FlagObstacles",
    movable: frozenset[str],
    blocked: Mapping[str, str],
    occupied_boxes: Sequence[Box],
    occupied_paths: Sequence[Sequence[tuple[float, float]]],
) -> str:
    """Why this seat may not be drawn where it stands, or ``""``.

    A part the corridor may move is **not** an obstacle: its body is exactly what
    the yield pass pushes out of the reserved footprint, so refusing the seat over
    it would refuse the corridor for the thing the corridor is for. Everything
    else is a hard veto — a locked part, a part outside the yield policy, another
    corridor's part, a label box, another corridor's flags, the page edge and a
    keep-out — because none of them can be moved out of the way by this binder,
    and the refusal says which of them it is.
    """
    problem = _flag_page_problem(seat.box, obstacles.page_box, obstacles.keepouts)
    if problem:
        return problem
    for part_id, box in obstacles.boxes.items():
        if part_id in obstacles.owned or part_id in movable:
            continue
        if _overlap_area(seat.box, box) > 0.0:
            tail = f": {blocked[part_id]}" if part_id in blocked else ""
            return f"the flag box overlaps {part_id}{tail}"
    for point in obstacles.tips:
        if (
            seat.box[0] < point[0] < seat.box[2]
            and seat.box[1] < point[1] < seat.box[3]
        ):
            return "the flag box stands on a foreign pin tip"
    for box in obstacles.labels:
        if _overlap_area(seat.box, box) > 0.0:
            return "the flag box stands on a label's own box"
    for box in occupied_boxes:
        if _overlap_area(seat.box, box) > 0.0:
            return "the flag box overlaps another corridor's flags"
    for path in occupied_paths:
        for start, end in zip(path, path[1:]):
            if _flag_segment_hits_box((start, end), seat.box):
                return "the flag box stands on another corridor's lead"
    if _path_hits_walls(seat.lead, obstacles.tips, obstacles.leads):
        return "the flag lead runs along a foreign pin or pin lead"
    for start, end in zip(seat.lead, seat.lead[1:]):
        leg = _span_box(start, end, 0.0)
        problem = _flag_page_problem(leg, obstacles.page_box, obstacles.keepouts)
        if problem:
            return problem
        for part_id, box in obstacles.boxes.items():
            if part_id in obstacles.owned or part_id in movable:
                continue
            if _flag_segment_hits_box((start, end), box):
                tail = f": {blocked[part_id]}" if part_id in blocked else ""
                return f"the flag lead runs through {part_id}{tail}"
        for box in obstacles.labels:
            if _flag_segment_hits_box((start, end), box):
                return "the flag lead runs through a label's own box"
        for box in occupied_boxes:
            if _flag_segment_hits_box((start, end), box):
                return "the flag lead runs through another corridor's flags"
        for path in occupied_paths:
            for other in zip(path, path[1:]):
                if _flag_segments_cross((start, end), other):
                    return "the flag lead crosses another corridor's lead"
    return ""


@dataclass(frozen=True)
class _FlagObstacles:
    """The page as the corridor binder reads it, measured once per template."""

    owned: frozenset[str]
    boxes: dict[str, Box]
    tips: tuple[tuple[float, float], ...]
    leads: tuple[Box, ...]
    labels: tuple[Box, ...]
    page_box: Box | None
    keepouts: tuple[Box, ...]


def _flag_obstacles(
    request: PlacementInput,
    state: _State,
    owned: frozenset[str],
    movable: frozenset[str],
) -> _FlagObstacles:
    """The page as the corridor reads it. A part the corridor may move is not a
    wall — the yield pass takes its body, its pins and its leads out of the
    reserved room, so they cannot veto the seat the yield exists for."""
    tips, leads = _pin_walls(request, state, owned | movable)
    return _FlagObstacles(
        owned=owned,
        boxes=_boxes_of(request, state),
        tips=tips,
        leads=leads,
        labels=tuple(
            box for _corridor, box in _foreign_labels(
                request, state.origins, state.poses, owned,
            )
        ),
        page_box=request.page_box,
        keepouts=request.keepouts,
    )


def _flag_corridor_seats(
    request: PlacementInput,
    template: FlagCorridorTemplate,
    state: _State,
) -> tuple[tuple[BoundFlagCorridorSeat, ...], ...]:
    """Every declared candidate of every pin, as a page-frame seat.

    Ordered exactly as the template lists them: the caller hands over its real
    seats nearest-first, and the joint selection reads that order as the
    preference. Nothing is sorted by a weight here.
    """
    out: list[tuple[BoundFlagCorridorSeat, ...]] = []
    for pin in template.pins:
        part = request.part(pin.part_id)
        pose = state.poses[pin.part_id]
        origin = state.origins[pin.part_id]
        profile_pin = _pin_for_token(part.profile, pin.token)
        if profile_pin is None:
            return ()
        tip = posed_tip(profile_pin.tip, pose, origin)
        out.append(tuple(
            BoundFlagCorridorSeat(
                part_id=pin.part_id, token=pin.token, net_id=pin.net_id,
                origin=origin, pose=pose, pin=tip,
                anchor=(tip[0] + candidate.anchor[0], tip[1] + candidate.anchor[1]),
                rotation=candidate.rotation,
                lead=_flag_path_at(tip, candidate.lead),
                box=_flag_box_at(tip, candidate.box),
                source=candidate.source,
            )
            for candidate in pin.candidates
        ))
    return tuple(out)


def _flag_part_block_reason(
    request: PlacementInput,
    template: FlagCorridorTemplate,
    part_id: str,
    others: Mapping[str, str],
) -> str:
    """Why this part may not yield, or ``""`` when it may.

    ``others`` is ``part id -> corridor group`` for every *other* declared
    corridor, so a second corridor's member is refused by the corridor that owns
    it rather than moved out from under it.
    """
    part = request.part(part_id)
    if part.locked_origin is not None or part.locked is not None:
        return (
            "the part carries an engineer lock; a flag corridor may not move it"
        )
    arm_owner: dict[str, str] = {}
    for other in request.series_templates:
        arm_owner[other.first.part_id] = other.branch_id
        arm_owner[other.second.part_id] = other.branch_id
        arm_owner[other.host_part] = other.branch_id
    if part_id in arm_owner:
        return (
            f"the part is part of declared series branch {arm_owner[part_id]!r}; "
            "moving it would move that arm"
        )
    if part_id in others:
        return (
            f"the part belongs to flag corridor {others[part_id]!r}; that corridor "
            "owns its pose"
        )
    if template.yield_parts is not None and part_id not in template.yield_parts:
        return (
            "the part is not an ordinary branch this corridor may move; its "
            "hard conflict is kept for the caller"
        )
    return ""


def _flag_yield_axis(
    request: PlacementInput,
    state: _State,
    escapes: Mapping[str, Mapping[str, tuple[float, float]]],
    part_id: str,
    nets: frozenset[str],
) -> tuple[float, float]:
    """The page axis this part leaves along, read from its own branch escape.

    The escape of the pin the part shares with the corridor is the existing
    branch reading (``_escapes``); a part that shares no net with the corridor
    falls back to the drawing's reading axis. Either way the yield moves along
    one page axis of the drawing that already exists, not along a new corridor.
    """
    mapping = _part_nets(request, part_id)
    profile = request.part(part_id).profile
    for token in sorted(mapping):
        if mapping[token] not in nets:
            continue
        pin = _pin_for_token(profile, token)
        if pin is None:
            continue
        direction = escapes.get(part_id, {}).get(pin.number)
        if direction is None or direction == (0.0, 0.0):
            continue
        if abs(direction[0]) >= abs(direction[1]):
            return (math.copysign(1.0, direction[0]), 0.0)
        return (0.0, math.copysign(1.0, direction[1]))
    lateral = _unit(request.lateral)
    if abs(lateral[0]) >= abs(lateral[1]):
        return (math.copysign(1.0, lateral[0]), 0.0)
    return (0.0, math.copysign(1.0, lateral[1]))


def _flag_yield_keeps_relations(
    request: PlacementInput,
    state: _State,
    pins: Mapping[str, Mapping[str, tuple[float, float]]],
    origins: Mapping[str, tuple[float, float]],
    part_id: str,
    target: tuple[float, float],
) -> bool:
    """Would the part still keep every relation that names it at ``target``?

    The binder may move an ordinary branch, but it may not buy a flag seat by
    breaking a promise the page already makes — a ``near`` to its host is the
    service relationship a decoupling branch exists to keep.
    """
    relevant = [
        relation for relation in request.relations
        if part_id in (relation.subject, relation.object)
    ]
    if not relevant:
        return True
    moved_origins = dict(origins)
    moved_origins[part_id] = target
    moved_pins = dict(pins)
    pose = state.poses[part_id]
    moved_pins[part_id] = {
        pin.number: posed_tip(pin.tip, pose, target)
        for pin in request.part(part_id).profile.pins
    }
    for relation in relevant:
        points = relation_points(request, relation, moved_pins, moved_origins)
        if points is None:
            continue
        if not relation_holds(
            relation.kind, points,
            grid=request.grid, near_limit=request.near_limit,
            lateral=request.lateral, progress=request.progress,
        ):
            return False
    return True


def _flag_service_gap_holds(
    request: PlacementInput,
    state: _State,
    gap: ServicePinGap,
    target: tuple[float, float],
) -> bool:
    """Would the shunt's service pin still stand ``gap`` from its host pin?

    Measured on the **actual page pin points** after the proposed move — the
    compiler's own reading (``drawcompiler._service_pin_gap``) is a distance
    between two pins, and a ``near`` relation is not that number. The lattice
    tolerance is the same ``grid / 2`` every other "same point" reading uses.
    """
    if gap.part_id not in state.poses or gap.host_part not in state.origins:
        return False
    part = request.part(gap.part_id)
    host = request.part(gap.host_part)
    pin = _pin_for_token(part.profile, gap.token)
    host_pin = _pin_for_token(host.profile, gap.host_token)
    if pin is None or host_pin is None:
        return False
    here = posed_tip(pin.tip, state.poses[gap.part_id], target)
    there = posed_tip(
        host_pin.tip, state.poses[gap.host_part], state.origins[gap.host_part],
    )
    distance = math.hypot(here[0] - there[0], here[1] - there[1])
    return abs(distance - gap.gap) <= request.grid / 2.0


def _flag_corridor_yields(
    request: PlacementInput,
    template: FlagCorridorTemplate,
    seats: Sequence[BoundFlagCorridorSeat],
    state: _State,
    obstacles: _FlagObstacles,
    movable: frozenset[str],
    blocked: Mapping[str, str],
) -> tuple[tuple[SeriesSeatYield, ...], bool]:
    """Who must move out of the chosen seats, and whether every one of them can.

    The move is measured from the real boxes — the part's own box against the
    flags' reserved boxes and lead legs — and takes the nearest exit along the
    part's own branch axis, both directions tried. There is no step cap: a seat
    that needs four lattice steps gets four, and one that needs twenty gets
    twenty, because the distance is the geometry's, not a constant.

    Returns the yield records and whether all of them are actual moves. A refusal
    record names the part and the reason; the caller turns that into the plan's
    refusal instead of seating over it.
    """
    flag_boxes = [seat.box for seat in seats]
    legs = [
        segment for seat in seats for segment in zip(seat.lead, seat.lead[1:])
    ]
    origins = dict(state.origins)
    boxes = dict(obstacles.boxes)
    pins = _pins_of(request, state)
    escapes = _escapes(request, state)
    nets = frozenset(seat.net_id for seat in seats)
    labels = tuple(obstacles.labels)
    gaps = {item.part_id: item for item in template.service_gaps}
    out: list[SeriesSeatYield] = []
    clean = True
    for part in request.parts:
        part_id = part.part_id
        if part_id in obstacles.owned:
            continue
        box = boxes[part_id]
        hits = [
            (index, item) for index, item in enumerate(flag_boxes)
            if _overlap_area(box, item) > 0.0
        ]
        for offset, segment in enumerate(legs):
            if _flag_segment_hits_box(segment, box):
                hits.append(
                    (len(flag_boxes) + offset, _span_box(*segment, 0.0))
                )
        if not hits:
            continue
        if part_id in blocked:
            out.append(SeriesSeatYield(
                part_id=part_id, branch_id=template.group_id,
                box_index=hits[0][0], refusal=blocked[part_id],
            ))
            clean = False
            continue
        if part_id not in movable:
            # A part that is neither owned nor movable is not an obstacle the
            # binder knows how to report; keeping the hard conflict is the
            # honest answer and the caller meets it as a refusal.
            out.append(SeriesSeatYield(
                part_id=part_id, branch_id=template.group_id,
                box_index=hits[0][0],
                refusal="the part is not a branch this corridor may move",
            ))
            clean = False
            continue
        axis = _flag_yield_axis(request, state, escapes, part_id, nets)
        pose = state.poses[part_id]
        origin = origins[part_id]
        pin_points = _foreign_pin_points(
            request, _State(dict(origins), dict(state.poses)),
            obstacles.owned | {part_id},
        )
        for direction, target, _shift in _series_yield_options(
            origin, box, [item for _index, item in hits],
            axis, template.grid, template.clearance,
        ):
            after = part_box(part.profile, pose, target)
            if any(_overlap_area(after, item) > 0.0 for item in flag_boxes):
                continue
            if any(_flag_segment_hits_box(segment, after) for segment in legs):
                continue
            problem = _flag_page_problem(after, request.page_box, request.keepouts)
            if problem:
                continue
            if not _yield_target_is_legal(
                request, part_id, pose, origin, target, boxes, labels, pin_points,
            ):
                continue
            if not _flag_yield_keeps_relations(
                request, state, pins, origins, part_id, target,
            ):
                continue
            if part_id in gaps and not _flag_service_gap_holds(
                request, state, gaps[part_id], target,
            ):
                continue
            out.append(SeriesSeatYield(
                part_id=part_id, branch_id=template.group_id,
                box_index=hits[0][0], direction=direction, target=target,
            ))
            origins[part_id] = target
            boxes[part_id] = after
            break
        else:
            detail = (
                "neither way out of the flag's reserved room is a seat this "
                "branch may take — both land on a label, another part, a "
                "foreign pin, or would break a relation it keeps"
            )
            if part_id in gaps:
                detail += (
                    f"; or they would break its service pin gap "
                    f"({gaps[part_id].gap:g} from "
                    f"{gaps[part_id].host_part}.{gaps[part_id].host_token})"
                )
            out.append(SeriesSeatYield(
                part_id=part_id, branch_id=template.group_id,
                box_index=hits[0][0], refusal=detail,
            ))
            clean = False
    return tuple(out), clean


def _flag_refusal_plan(
    template: FlagCorridorTemplate,
    detail: str,
    action: str,
    host_origin: tuple[float, float] | None = None,
    host_pose: SymbolPose | None = None,
    subject: str = "",
) -> BoundFlagCorridorPlan:
    return BoundFlagCorridorPlan(
        group_id=template.group_id, host_part=template.host_part,
        host_origin=host_origin, host_pose=host_pose,
        grid=template.grid, lattice=template.lattice,
        clearance=template.clearance, yield_parts=template.yield_parts,
        candidate_source=template.candidate_source,
        service_gaps=template.service_gaps,
        refusal=SeriesSeatRefusal(
            branch_id=template.group_id, subject=subject or template.group_id,
            detail=detail, action=action, category=FLAG_CORRIDOR_REFUSAL,
        ),
    )


#: What one full joint assignment is: the seats chosen and the yields it needs.
_FlagJointSeat = tuple[
    tuple[BoundFlagCorridorSeat, ...], tuple[SeriesSeatYield, ...],
]


def _bind_one_flag_corridor(
    request: PlacementInput,
    template: FlagCorridorTemplate,
    state: _State,
    occupied_boxes: Sequence[Box],
    occupied_paths: Sequence[Sequence[tuple[float, float]]],
    others: Mapping[str, str],
) -> BoundFlagCorridorPlan:
    """Seat one corridor's pins jointly, then ask the ordinary parts to yield."""
    host_origin = state.origins.get(template.host_part)
    host_pose = state.poses.get(template.host_part)
    if host_origin is None or host_pose is None:
        return _flag_refusal_plan(
            template,
            f"the host {template.host_part} has no seat in this layout",
            "seat the host before binding the corridor",
        )
    seats_by_pin = _flag_corridor_seats(request, template, state)
    if not seats_by_pin:
        return _flag_refusal_plan(
            template,
            "a declared pin of the corridor is not a pin of its symbol",
            "fix the corridor's pin tokens",
            host_origin, host_pose,
        )
    owned = frozenset({template.host_part} | {
        pin.part_id for pin in template.pins
    })
    blocked: dict[str, str] = {}
    for part in request.parts:
        if part.part_id in owned:
            continue
        reason = _flag_part_block_reason(request, template, part.part_id, others)
        if reason:
            blocked[part.part_id] = reason
    movable = frozenset(
        part.part_id for part in request.parts
        if part.part_id not in owned and part.part_id not in blocked
    )
    obstacles = _flag_obstacles(request, state, owned, movable)
    chosen: list[BoundFlagCorridorSeat] = []
    failure: list[str] = []

    def walk(index: int) -> _FlagJointSeat | None:
        if index == len(seats_by_pin):
            yields, clean = _flag_corridor_yields(
                request, template, chosen, state, obstacles, movable, blocked,
            )
            if clean:
                return tuple(chosen), yields
            failure.append(
                "no joint seat survives the yields: " + "; ".join(
                    f"{item.part_id}: {item.refusal}" for item in yields
                    if item.refusal
                )
            )
            return None
        for seat in seats_by_pin[index]:
            problem = _flag_seat_problem(
                seat, obstacles, movable, blocked, occupied_boxes, occupied_paths,
            )
            if problem:
                failure.append(f"{seat.part_id}.{seat.token}: {problem}")
                continue
            clash = next(
                (text for other in chosen
                 if (text := _flag_seat_conflict(other, seat))),
                "",
            )
            if clash:
                failure.append(f"{seat.part_id}.{seat.token}: {clash}")
                continue
            chosen.append(seat)
            found = walk(index + 1)
            if found is not None:
                return found
            chosen.pop()
        return None

    found = walk(0)
    if found is None:
        detail = (
            "the declared real candidates admit no joint seat: "
            + (failure[0] if failure else "every combination collides")
        )
        return _flag_refusal_plan(
            template, detail,
            "add a real flag grade for a pin this corridor seats, or move the "
            "part that blocks every combination",
            host_origin, host_pose,
        )
    seats, yields = found
    # The yields were computed against the binder's working copy; commit them so
    # the next corridor on this page sees where the parts actually stand.
    for item in yields:
        if item.direction is not None and item.target is not None:
            state.origins[item.part_id] = item.target
    return BoundFlagCorridorPlan(
        group_id=template.group_id, host_part=template.host_part,
        host_origin=host_origin, host_pose=host_pose,
        seats=seats, grid=template.grid, lattice=template.lattice,
        clearance=template.clearance, yield_parts=template.yield_parts,
        candidate_source=template.candidate_source,
        service_gaps=template.service_gaps,
        reserved_boxes=tuple(
            box for seat in seats for box in (seat.box,)
        ) + tuple(
            leg for seat in seats for leg in _flag_lead_boxes(seat.lead)
        ),
        lead_paths=tuple(seat.lead for seat in seats),
        yields=yields,
    )


def _bind_flag_corridor_plans(
    request: PlacementInput, state: _State
) -> tuple[BoundFlagCorridorPlan, ...]:
    """Bind every declared corridor in request order, one shared working state.

    Binding is pure from the caller's point of view: the yields it computes are
    written into the **local** working copy the binder was handed, and the plan
    carries them so the caller can apply exactly those moves
    (:func:`place_flag_corridors`). Empty templates return the empty tuple.
    """
    if not request.flag_corridors:
        return ()
    others: dict[str, str] = {}
    for template in request.flag_corridors:
        for pin in template.pins:
            others[pin.part_id] = template.group_id
        others.setdefault(template.host_part, template.group_id)
    plans: list[BoundFlagCorridorPlan] = []
    occupied_boxes: list[Box] = []
    occupied_paths: list[tuple[tuple[float, float], ...]] = []
    for template in request.flag_corridors:
        plan = _bind_one_flag_corridor(
            request, template, state, tuple(occupied_boxes),
            tuple(occupied_paths), others,
        )
        plans.append(plan)
        if plan.seated:
            occupied_boxes.extend(plan.reserved_boxes)
            occupied_paths.extend(plan.lead_paths)
    return tuple(plans)


def bind_flag_corridors(
    request: PlacementInput,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
) -> tuple[BoundFlagCorridorPlan, ...]:
    """Bind the declared flag corridors once against an existing layout.

    The draw consumers call this with the layout they already have, exactly as
    they call :func:`bind_series`; it is the same :func:`_bind_flag_corridor_plans`
    the search uses, not a second seat rule. The caller's mappings are not
    mutated — a yield is a record on the plan, applied by
    :func:`place_flag_corridors`. Empty templates return the empty tuple.
    """
    return _bind_flag_corridor_plans(
        request, _State(dict(origins), dict(poses)),
    )


def place_flag_corridors(
    request: PlacementInput,
    plans: Sequence[BoundFlagCorridorPlan],
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
) -> tuple[tuple[BoundFlagCorridorPlan, ...], _State]:
    """Apply the corridor yields, then report the plans and the new state.

    Returns the plans unchanged and a **new** state; the caller decides when to
    copy the state back into its placement. The moves applied are the plan's own
    records — no second search, no second yield rule.
    """
    state = _State(dict(origins), dict(poses))
    if not plans:
        return (), state
    for plan in plans:
        if not plan.seated:
            continue
        for item in plan.yields:
            if item.direction is None or item.target is None:
                continue
            state.origins[item.part_id] = item.target
    return tuple(plans), state




# ------------------------------------------------------------- the search


def _repair_delta(
    request: PlacementInput,
    relation: PlacementRelation,
    pins: Mapping[str, Mapping[str, tuple[float, float]]],
    origins: Mapping[str, tuple[float, float]],
    which: int,
) -> tuple[float, float] | None:
    """The translation that would make this relation hold, for one endpoint.

    This is concept 4 made mechanical: a soft constraint is not "rejected", it is
    *repaired*. The delta is computed from the very points the ruler measures, so
    the move that the search believes fixes a relation is the move the gate will
    see as fixing it — a repair that measured origins would leave the pin
    misaligned and the candidate refused, which is exactly the failure mode the
    flagship flyback is in today.
    """
    points = relation_points(request, relation, pins, origins)
    if points is None:
        return None
    (ax, ay), (bx, by) = points
    slack = request.grid / 2.0
    kind = relation.kind
    if kind in (SAME_COLUMN, HORIZONTAL_TAP):
        delta = (bx - ax, 0.0)
    elif kind in (SAME_ROW, VERTICAL_TAP):
        delta = (0.0, by - ay)
    elif kind == ABOVE:
        delta = (0.0, (by + slack) - ay)
    elif kind == BELOW:
        delta = (0.0, (by - slack) - ay)
    elif kind == LEFT_OF:
        delta = ((bx - slack) - ax, 0.0)
    elif kind == RIGHT_OF:
        delta = ((bx + slack) - ax, 0.0)
    elif kind == ADJACENT:
        gap = (ax - bx, ay - by)
        lateral = _dot(gap, request.lateral)
        delta = (-request.lateral[0] * lateral, -request.lateral[1] * lateral)
    elif kind == NEAR:
        distance = math.hypot(ax - bx, ay - by)
        if distance <= request.near_limit:
            return None
        step = distance - request.near_limit + request.grid
        delta = (
            (bx - ax) / distance * step, (by - ay) / distance * step,
        )
    else:
        return None
    if which == 1:
        delta = (-delta[0], -delta[1])
    # Grid-aligned, and never a no-op: a repair that rounds to nothing would
    # burn an iteration and report progress it did not make.
    snapped = (
        round(delta[0] / request.grid) * request.grid,
        round(delta[1] / request.grid) * request.grid,
    )
    if snapped == (0.0, 0.0):
        return None
    return snapped


def _violated_relations(
    request: PlacementInput, terms: Sequence[CostTerm]
) -> list[PlacementRelation]:
    names = {
        item.name for item in terms
        if item.name.startswith("relation:") and item.violated
    }
    return [
        relation for relation in request.relations
        if f"relation:{relation.label()}" in names
    ]


def _anneal_with_seed(
    request: PlacementInput,
    state: _State,
    seed: int,
    plans: Sequence[BoundSeriesSeatPlan] = (),
    panels: Sequence[BoundPanelSeatPlan] = (),
    services: Sequence[BoundPanelSeatPlan] = (),
) -> tuple[_State, int, int]:
    """One annealing run from the fixed seed. See :func:`_anneal` for the moves.

    The seed is a parameter rather than ``request.seed`` because ``place`` runs
    the whole search several times and keeps the best drawing; each restart uses
    its own seed, and none of them is random.

    **515A hole 7**: an input whose parts are **all** pinned (every origin a
    lock's) has no move the search can even propose — translate, turn and swap
    each roll a locked part, and the repair move has no free endpoint — so the
    loop would burn the full iteration budget idling. The run answers with the
    seed state immediately and the stop rule is never reached the dishonest
    way (by counting nothing); a *partially* locked input keeps the original
    move flow byte for byte, so every drawing it drew before this batch it
    draws again identically.
    """
    rng = random.Random(seed)
    current = _State(dict(state.origins), dict(state.poses))
    terms = evaluate(request, current, plans, panels)
    energy = _energy(terms)
    best = _State(dict(current.origins), dict(current.poses))
    best_energy = energy
    ids = request.part_ids()
    certainty = {part.part_id for part in request.parts if part.locked is not None}
    #: Parts whose *origin* is a lock's (515A hole 3): never translated, never
    #: swapped, never re-seeded — the point is the engineer's, the same contract
    #: the pose-only half of the lock has always had.
    pinned = set(request.locked_origins())
    #: The two parts of every bound arm. They move as one arm: never turned,
    #: never swapped, and never translated on their own. Empty on an undeclared
    #: request, which is what keeps the historical move flow byte for byte.
    arm_plan: dict[str, BoundSeriesSeatPlan] = {}
    for plan in plans:
        if plan.seated:
            arm_plan[plan.first_part] = plan
            arm_plan[plan.second_part] = plan
    #: Every panel cell (548D3X3C): never translated, turned, swapped or repaired
    #: on its own. The binder owns them; the host moving re-binds the whole panel
    #: after the search (`place`), so a move on a cell would be a seat the plan
    #: discarded. Empty on a request that declares no panel, which keeps the
    #: historical move flow byte for byte.
    panel_parts = panel_parts_of(panels) | service_parts_of(services)
    if ids and all(part_id in pinned for part_id in ids):
        return best, 0, 0
    ladder = (1, 2, 4, 8)
    #: Temperature: starts at a few grid units' worth of relation miss and cools
    #: geometrically to nearly nothing, so the tail is a hill climb.
    temperature = 40.0
    cooling = 0.9995
    accepted = 0
    stall = 0
    iterations = 0
    for iterations in range(1, request.iterations + 1):
        candidate = _State(dict(current.origins), dict(current.poses))
        roll = rng.random()
        if roll < 0.30 or not ids:
            part_id = ids[rng.randrange(len(ids))]
            if part_id in pinned or part_id in panel_parts:
                continue
            if part_id in certainty and part_id not in arm_plan:
                continue
            rung = ladder[rng.randrange(len(ladder))] * request.grid
            dx = rng.choice((-rung, 0.0, rung))
            dy = rng.choice((-rung, 0.0, rung))
            if part_id in arm_plan:
                # A whole arm slides together, and only across its lane: the
                # seat along ``progress`` and the frozen pitch do not change.
                plan = arm_plan[part_id]
                axis = _unit(plan.lateral)
                along = _dot((dx, dy), axis)
                if abs(along) <= SERIES_EPS:
                    continue
                shift = (axis[0] * along, axis[1] * along)
                for member in (plan.first_part, plan.second_part):
                    at = candidate.origins[member]
                    candidate.origins[member] = (
                        at[0] + shift[0], at[1] + shift[1],
                    )
            else:
                at = candidate.origins[part_id]
                candidate.origins[part_id] = (at[0] + dx, at[1] + dy)
        elif roll < 0.50:
            part_id = ids[rng.randrange(len(ids))]
            part = request.part(part_id)
            if (part_id in certainty or len(part.poses) < 2
                    or part_id in arm_plan or part_id in panel_parts):
                continue
            candidate.poses[part_id] = part.poses[rng.randrange(len(part.poses))]
        elif roll < 0.65 and len(ids) >= 2:
            first = ids[rng.randrange(len(ids))]
            second = ids[rng.randrange(len(ids))]
            if (
                first == second
                or first in certainty or second in certainty
                or first in pinned or second in pinned
                or first in arm_plan or second in arm_plan
                or first in panel_parts or second in panel_parts
            ):
                continue
            candidate.origins[first], candidate.origins[second] = (
                candidate.origins[second], candidate.origins[first],
            )
        else:
            pending = _violated_relations(request, terms)
            if not pending:
                continue
            relation = pending[rng.randrange(len(pending))]
            endpoints = [relation.subject, relation.object]
            rng.shuffle(endpoints)
            moved = False
            for index, part_id in enumerate(endpoints):
                if part_id in certainty or part_id in arm_plan or part_id in panel_parts:
                    continue
                delta = _repair_delta(
                    request, relation, _pins_of(request, candidate),
                    candidate.origins, index,
                )
                if delta is None:
                    continue
                at = candidate.origins[part_id]
                candidate.origins[part_id] = (at[0] + delta[0], at[1] + delta[1])
                moved = True
                break
            if not moved:
                continue

        if plans:
            candidate = _project_series(request, plans, current, candidate)
        # 548D3X3C fix: the panels are re-bound **per candidate**, from this
        # candidate's own host origin and pose, and the cells are re-seated onto
        # that answer before it is evaluated. Binding only at the seed (and again
        # at the very end) left every intermediate candidate priced against the
        # seed's seats while its host had moved — a cell and its host-path drifting
        # together was invisible to the cost list. Empty on a request that
        # declares no panel, which is every historical request, so the move
        # flow and the cost list keep their bytes.
        candidate_panels = panels
        if panels:
            candidate_panels = bind_panel_plans(
                request, candidate.origins, candidate.poses)
            seat_panel_plans(candidate_panels, candidate.origins, candidate.poses)
        candidate_services = services
        if services:
            candidate_services = bind_service_plans(
                request, candidate.origins, candidate.poses, candidate_panels)
            seat_service_plans(
                candidate_services, candidate.origins, candidate.poses)
        if candidate.origins == current.origins and candidate.poses == current.poses:
            continue
        new_terms = (
            evaluate(request, candidate, plans, candidate_panels)
            if not candidate_services else
            evaluate(request, candidate, plans, candidate_panels,
                     candidate_services)
        )
        new_energy = _energy(new_terms)
        delta_energy = new_energy - energy
        if delta_energy <= 0.0 or rng.random() < math.exp(
            -delta_energy / max(temperature, 1e-9)
        ):
            current, terms, energy = candidate, new_terms, new_energy
            accepted += 1
            if energy < best_energy - 1e-9:
                best = _State(dict(current.origins), dict(current.poses))
                best_energy = energy
                stall = 0
            else:
                stall += 1
        else:
            stall += 1
        temperature *= cooling
        # "No progress for two thousand moves" is the stop rule: an input whose
        # relations are all kept and whose wiring has converged stops paying for
        # iterations it is not using (the 19-part performance budget is 30 s).
        if stall >= 2000:
            break
    return best, iterations, accepted


def _anneal(
    request: PlacementInput,
    state: _State,
    plans: Sequence[BoundSeriesSeatPlan] = (),
    panels: Sequence[BoundPanelSeatPlan] = (),
    services: Sequence[BoundPanelSeatPlan] = (),
) -> tuple[_State, int, int]:
    """Deterministic simulated annealing over translations, poses and swaps.

    The move set is four, and each one is a concept:

    * **translate** — a part moves by a rung of a small ladder, so the search can
      slide things apart without a global reshuffle;
    * **turn** — a part takes another of its accepted poses (concept 3);
    * **swap** — two parts exchange origins, which is the one move that can undo
      a chain order decided early;
    * **repair** — a violated relation is picked and an endpoint translated by
      exactly the delta :func:`_repair_delta` computes. It reads the miss off the
      ruler instead of hoping the walk stumbles onto it: a 5-unit lattice has to
      find a 20-unit pin offset by luck otherwise.

    How much the repair move is worth is **measured, not asserted** (201B): with
    it disabled the flyback still reaches a drawing that keeps all 30 relations,
    but a worse one — wiring 2780 units against 1595, pin-facing 1091 against
    445, spread 825 against 478. Feasibility comes from the pose search and the
    translations; the *quality* of the flyback drawing comes from the repair
    move, and ``tests/test_201b_placement.py`` pins those two readings so the
    claim cannot quietly stop being true.

    Determinism is a fixed seed on a single :class:`random.Random`: the same
    request produces the same sequence of moves and therefore the same drawing,
    which the acceptance test measures by running the search twice.
    """
    return _anneal_with_seed(request, state, request.seed, plans, panels, services)


# ------------------------------------------------- the declared reading panels
#
# 548D3X3C (33C1): the placement layer's own seat plan for a declared panel.
# Pure data in, pure geometry out — the binder reads the host's real body box
# and each cell's real part/text/flag reserve, never a same-side host-pin mean
# (those feet share one x and could not form two columns). Nothing here imports
# `drawcompiler`: the text rows arrive as measured relative boxes from the
# caller (its `_line_boxes`), and the terminal flag's room arrives as a
# `FlagReservation.box`, which this module materialises with `box_at`.


PANEL_SIDE_BOTTOM = "bottom"


@dataclass(frozen=True)
class PanelCell:
    """One panel cell: its part, nets, pins, pose and measured relative room."""

    part_id: str
    from_net: str
    to_net: str
    from_token: str
    to_token: str
    host_token: str
    pose: SymbolPose
    #: The part's printed rows, relative to its own origin (the caller's
    #: `_line_boxes` at a part box built from origin ``(0, 0)``).
    text_boxes: tuple[Box, ...] = ()
    #: The terminal flag's room, relative to the part's ``to`` pin — the same
    #: box a :class:`FlagReservation` carries, materialised with `box_at`.
    flag_box: Box | None = None
    #: The terminal flag's **lead**, relative to the part's ``to`` pin and in
    #: page axes (548D3S1). Empty — the default — is the historical panel
    #: reading: the flag hangs straight down, which is what
    #: ``drawcompiler._panel_terminal_seats`` states. The binder never consumes
    #: it; it exists so a side cell's lead can be replayed by the draw consumer
    #: without inventing a second geometry rule there.
    flag_lead: tuple[tuple[float, float], ...] = ()

    def __post_init__(self) -> None:
        if not self.part_id or not self.from_net or not self.to_net:
            raise PlacementError("a panel cell names its part and both nets")
        if not self.from_token or not self.to_token:
            raise PlacementError(
                f"{self.part_id}: a panel cell states the pin on each of its nets")


@dataclass(frozen=True)
class PanelSeatTemplate:
    """A declared reading panel before the host's origin is known.

    No absolute coordinate: the grid is solved when the host is placed, from the
    host's body box and the cells' real reserves. ``pitch`` is the placement's
    own channel constant — no scene constant is introduced.
    """

    group_id: str
    host_part: str
    cells: tuple[PanelCell, ...]
    columns: int
    side: str = PANEL_SIDE_BOTTOM
    grid: float = DEFAULT_GRID
    lattice: tuple[float, float] = (0.0, 0.0)
    clearance: float = 0.0
    pitch: float = DEFAULT_CHANNEL

    def __post_init__(self) -> None:
        if not self.group_id or not self.host_part:
            raise PlacementError("a panel template names its group and host part")
        if not self.cells:
            raise PlacementError(f"panel {self.group_id}: no cells were passed")
        if self.columns < 1 or self.columns > len(self.cells):
            raise PlacementError(
                f"panel {self.group_id}: columns must lie in 1..{len(self.cells)}, "
                f"got {self.columns!r}")
        if self.host_part in {cell.part_id for cell in self.cells}:
            raise PlacementError(
                f"panel {self.group_id}: the host {self.host_part!r} is also a cell")
        if self.grid <= 0.0 or self.pitch < 0.0:
            raise PlacementError(f"panel {self.group_id}: grid/pitch out of range")


@dataclass(frozen=True)
class BoundPanelSeat:
    """One cell materialised: origin, pose, both seat points and its reserve."""

    part_id: str
    host_token: str
    origin: tuple[float, float] | None
    pose: SymbolPose | None
    from_seat: tuple[float, float] | None
    to_seat: tuple[float, float] | None
    reserved: tuple[Box, ...] = ()
    host_path: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class PanelSeatRefusal:
    """Why a declared panel could not be seated, in printable words."""

    group_id: str
    detail: str
    action: str

    def render(self) -> str:
        return f"panel {self.group_id}: {self.detail}"


@dataclass(frozen=True)
class BoundPanelSeatPlan:
    """A panel template materialised against the host's real body box."""

    group_id: str
    host_part: str
    side: str
    columns: int
    cells: tuple[BoundPanelSeat, ...] = ()
    reserved_boxes: tuple[Box, ...] = ()
    host_paths: tuple[tuple[tuple[float, float], ...], ...] = ()
    grid: float = DEFAULT_GRID
    lattice: tuple[float, float] = (0.0, 0.0)
    refusal: PanelSeatRefusal | None = None

    @property
    def seated(self) -> bool:
        return (
            self.refusal is None
            and bool(self.cells)
            and all(
                cell.origin is not None and cell.pose is not None
                and cell.from_seat is not None and cell.to_seat is not None
                for cell in self.cells
            )
        )

    @property
    def owned_parts(self) -> frozenset[str]:
        return frozenset((self.host_part, *(cell.part_id for cell in self.cells)))

    def mismatches(
        self,
        origins: Mapping[str, tuple[float, float]],
        poses: Mapping[str, SymbolPose],
    ) -> tuple[str, ...]:
        """Every way the answer disagrees with this plan (empty = seated)."""
        if self.refusal is not None:
            return (self.refusal.render(),)
        out: list[str] = []
        for cell in self.cells:
            if cell.origin is None or cell.pose is None:
                out.append(f"{self.group_id}: {cell.part_id} has no bound seat")
                continue
            at = origins.get(cell.part_id)
            if at is None:
                out.append(f"{self.group_id}: {cell.part_id} is absent")
                continue
            if (abs(at[0] - cell.origin[0]) > SERIES_EPS
                    or abs(at[1] - cell.origin[1]) > SERIES_EPS):
                out.append(
                    f"{self.group_id}: {cell.part_id} sits at "
                    f"({at[0]:g}, {at[1]:g}), the plan says "
                    f"({cell.origin[0]:g}, {cell.origin[1]:g})")
            if poses.get(cell.part_id) != cell.pose:
                out.append(
                    f"{self.group_id}: {cell.part_id} is drawn in pose "
                    f"{poses.get(cell.part_id)}, the plan says {cell.pose.label()}")
        return tuple(out)

    def translated(self, delta: tuple[float, float]) -> "BoundPanelSeatPlan":
        """The same plan moved rigidly (the page anchor's translation)."""
        if delta == (0.0, 0.0):
            return self

        def move_point(point: tuple[float, float] | None):
            return None if point is None else (
                point[0] + delta[0], point[1] + delta[1])

        def move_box(box: Box) -> Box:
            return (box[0] + delta[0], box[1] + delta[1],
                    box[2] + delta[0], box[3] + delta[1])

        return replace(
            self,
            cells=tuple(replace(
                cell,
                origin=move_point(cell.origin),
                from_seat=move_point(cell.from_seat),
                to_seat=move_point(cell.to_seat),
                reserved=tuple(move_box(box) for box in cell.reserved),
                host_path=tuple(move_point(point) for point in cell.host_path),
            ) for cell in self.cells),
            reserved_boxes=tuple(move_box(box) for box in self.reserved_boxes),
            host_paths=tuple(
                tuple(move_point(point) for point in path)
                for path in self.host_paths),
        )


def _panel_refusal(template: PanelSeatTemplate, detail: str, action: str) -> BoundPanelSeatPlan:
    return BoundPanelSeatPlan(
        group_id=template.group_id, host_part=template.host_part,
        side=template.side, columns=template.columns,
        grid=template.grid, lattice=template.lattice,
        refusal=PanelSeatRefusal(template.group_id, detail, action),
    )


# ------------------------------------------------- 548D3S1: service seats

PANEL_SIDE_LEFT = "left"
PANEL_SIDE_RIGHT = "right"
#: The sides a **service** cell may take (548D3S1). A panel stays bottom-only;
#: these two are the reading sides a decoupling branch, a pull-down or an
#: indicator sits on beside its host, and adding them here changes no panel.
SERVICE_SIDES = (PANEL_SIDE_LEFT, PANEL_SIDE_RIGHT)


@dataclass(frozen=True)
class ServiceSeatTemplate:
    """One service branch's seat beside its host — draw internal (548D3S1).

    Not a ``panelGroups`` statement and never parsed from a presentation: the
    draw consumer builds it from its own slots. It reuses :class:`PanelCell` for
    the branch's real part, its two nets/pins, its pose, its printed rows and its
    terminal flag box, and adds nothing but the side the cell is read on. There
    is no absolute coordinate and no lock: the origin is solved against the
    host's own body and pins, exactly as a panel's cells are.
    """

    group_id: str
    host_part: str
    side: str
    cell: PanelCell
    grid: float = DEFAULT_GRID
    lattice: tuple[float, float] = (0.0, 0.0)
    clearance: float = 0.0
    pitch: float = DEFAULT_CHANNEL

    def __post_init__(self) -> None:
        if not self.group_id or not self.host_part:
            raise PlacementError(
                "a service seat names its group and its host part")
        if self.side not in SERVICE_SIDES:
            raise PlacementError(
                f"service seat {self.group_id}: side must be one of "
                f"{SERVICE_SIDES}, got {self.side!r}")
        if self.host_part == self.cell.part_id:
            raise PlacementError(
                f"service seat {self.group_id}: the host {self.host_part!r} "
                "is also its cell")
        if self.grid <= 0.0 or self.pitch < 0.0:
            raise PlacementError(
                f"service seat {self.group_id}: grid/pitch out of range")
        for axis, offset in zip(("x", "y"), self.lattice):
            if not (0.0 <= offset < self.grid):
                raise PlacementError(
                    f"service seat {self.group_id}: lattice offset {offset!r} "
                    f"on {axis} must lie in [0, {self.grid})")


def _service_template_key(template: ServiceSeatTemplate) -> tuple:
    return (
        template.group_id, template.host_part, template.side,
        float(template.grid),
        (float(template.lattice[0]), float(template.lattice[1])),
        float(template.clearance), float(template.pitch),
        _panel_cell_key(template.cell),
    )


def _service_refusal(
    template: ServiceSeatTemplate, detail: str, action: str,
) -> BoundPanelSeatPlan:
    return BoundPanelSeatPlan(
        group_id=template.group_id, host_part=template.host_part,
        side=template.side, columns=1,
        grid=template.grid, lattice=template.lattice,
        refusal=PanelSeatRefusal(template.group_id, detail, action),
    )


#: The room a drawn lead claims around itself: the same ``1.0`` the compiler's
#: ``PIN_TEXT_WALL`` reuses for a scalar stride. Stated here as this layer's own
#: copy so a panel host lead and a service seat are measured with one ruler.
SERVICE_WALL_PAD = 1.0


def _panel_service_walls(
    panel_plans: Sequence[BoundPanelSeatPlan],
) -> tuple[Box, ...]:
    """Every panel reserve and every host-lead leg as a positive box (§35C).

    The panel's own room is what the placement already promised a declared cell;
    the host lead is a *drawn* run, so its legs become boxes grown by
    :data:`SERVICE_WALL_PAD` — the same shape
    ``drawcompiler._seat_first_channel_walls`` builds, measured here so a service
    seat can yield to it before the drawing has to refuse.
    """
    walls: list[Box] = []
    for plan in panel_plans:
        walls.extend(plan.reserved_boxes)
        for path in plan.host_paths:
            for start, stop in zip(path, path[1:]):
                walls.append((
                    min(start[0], stop[0]) - SERVICE_WALL_PAD,
                    min(start[1], stop[1]) - SERVICE_WALL_PAD,
                    max(start[0], stop[0]) + SERVICE_WALL_PAD,
                    max(start[1], stop[1]) + SERVICE_WALL_PAD,
                ))
    return tuple(walls)


def _service_foreign_refusal(
    request: PlacementInput,
    template: ServiceSeatTemplate,
    plan: BoundPanelSeatPlan,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
    walls: Sequence[Box] = (),
) -> BoundPanelSeatPlan:
    """A foreign part standing in the cell's room is a named hard refusal.

    The same measurement the panel binder makes: the real part box of every part
    that is not the host and not the cell, against every reserved box, positive
    area only. No weight, no tolerance and no "it is only a sliver" exemption.

    A part a **service seat of this same request** places is not foreign: its
    entry in the answer is provisional (the seat may come later in the order, or
    may move with it), and the seats measure each other through their rooms and
    their recorded leads, not through whichever origin the answer happened to
    hold when the order was tried (§548D3C1 — measured: the reversed order was
    refused for a not-yet-seated cell still standing at its old origin).

    ``walls`` is the panel's promise — its reserves and host-lead legs (§35C): a
    cell whose own room still stands on one of them has no seat this page can
    state, and the refusal names the wall rather than shipping an overlap.
    """
    owned = {template.host_part, template.cell.part_id}
    if request.service_joint_order:
        # §548D3C1: a part this same request's service seats place is not
        # foreign — its answer entry is provisional, and the seats measure each
        # other through their rooms and recorded leads instead. Legacy pages
        # (the default) keep the historical reading: only the host and the
        # branch itself are exempt.
        owned |= {item.cell.part_id for item in request.service_templates}
    for other in request.parts:
        if other.part_id in owned:
            continue
        if other.part_id not in origins or other.part_id not in poses:
            continue
        foreign = part_box(
            other.profile, poses[other.part_id], origins[other.part_id])
        for reserve_box in plan.reserved_boxes:
            if _boxes_overlap(foreign, reserve_box) > 0.0:
                return replace(plan, refusal=PanelSeatRefusal(
                    template.group_id,
                    f"foreign part {other.part_id!r} at {foreign} intrudes on "
                    f"service cell {template.cell.part_id}'s reserved "
                    f"part/text/flag room {reserve_box} — the seat's room is not "
                    "taken from another part",
                    "move the foreign part out of the cell's room, or drop the "
                    "service seat",
                ))
    if plan.seated:
        for reserve_box in plan.reserved_boxes:
            for wall in walls:
                if _boxes_overlap(reserve_box, wall) > 0.0:
                    return replace(plan, refusal=PanelSeatRefusal(
                        template.group_id,
                        f"service cell {template.cell.part_id}'s reserved "
                        f"part/text/flag room {reserve_box} stands on the "
                        f"panel's own room or host lead at {wall} — the panel "
                        "was promised that lane first, and the service seat "
                        "yields to it or is refused",
                        "move the panel host or the branch, or drop the "
                        "service seat",
                    ))
    return plan


def _service_direct_path(
    host_tip: tuple[float, float], from_seat: tuple[float, float],
) -> tuple[tuple[float, float], ...]:
    """The direct orthogonal run from the host pin's tip to the branch's foot.

    The binder puts the from foot on the host pin's own axis (§548D3S1), so on
    every answer it seats the run is **one** segment. The bend is kept for the
    answer that ever arrives off axis: a recorded lead must still be a path this
    module can measure, and a diagonal would be neither an orthogonal run nor a
    leg a drawing could draw. A foot that stands on the pin's own tip has no run
    to record and states the point alone. This is a record of the span the branch
    will claim, not a route — nothing here chooses a way around an obstacle.
    """
    if (abs(host_tip[0] - from_seat[0]) <= SERIES_EPS
            and abs(host_tip[1] - from_seat[1]) <= SERIES_EPS):
        return (host_tip,)
    if abs(host_tip[1] - from_seat[1]) <= SERIES_EPS:
        return (host_tip, (from_seat[0], host_tip[1]))
    return (host_tip, (from_seat[0], host_tip[1]), from_seat)


def _service_lead_legs(
    path: Sequence[tuple[float, float]],
) -> tuple[Box, ...]:
    """Every drawn leg of a recorded lead, widened by the Service wall pad."""
    return tuple(
        _span_box(start, stop, SERVICE_WALL_PAD)
        for start, stop in zip(path, path[1:])
    )


def _service_host_path(
    plan: BoundPanelSeatPlan, host_tip: tuple[float, float],
) -> BoundPanelSeatPlan:
    """Attach the recorded host lead to a seated plan, in the answer's frame.

    The path is the host pin's **real** posed tip to the cell's from foot, so it
    is re-attached after the outward ladder has moved the cell: the first point is
    the host's, never the seat's. A plan that already carries exactly this span
    is returned as it stands — the relative solve states it in its own frame, and
    an untouched seat must stay the same object (`_SERVICE_SOLVE_CACHE` identity).
    """
    if not plan.seated or not plan.cells:
        return plan
    cell = plan.cells[0]
    assert cell.from_seat is not None
    path = _service_direct_path(host_tip, cell.from_seat)
    if plan.host_paths == (path,) and cell.host_path == path:
        return plan
    return replace(
        plan, cells=(replace(cell, host_path=path),), host_paths=(path,))


def _service_lead_rooms(
    request: PlacementInput,
    template: ServiceSeatTemplate,
    plan: BoundPanelSeatPlan,
) -> tuple[Box, ...]:
    """The seat's own drawn geometry: its body and its terminal flag's room.

    The printed rows are deliberately **not** here. Where a part's text is
    printed is the drawing's own decision — §35D's text pass places it against
    the very leads this binder records — while a lead through a component's body
    or through a flag's glyph is geometry no text pass can undo. Measured on the
    real four-service page: with the rows counted, D1's and D2's two-row blocks
    are 23 units tall on rows ten apart, so neither order can seat the pair and
    the whole page refuses; with the rows left to the drawing, the low-row-first
    order seats both and only the flag room (C1/R1) is the seat's business.
    """
    if not plan.seated or not plan.cells:
        return ()
    cell = plan.cells[0]
    rooms: list[Box] = []
    if cell.origin is not None and cell.pose is not None:
        body = part_box(
            request.part(cell.part_id).profile, cell.pose, cell.origin)
        rooms.append(_grow_box(body, template.clearance))
    if template.cell.flag_box is not None and cell.to_seat is not None:
        rooms.append(_grow_box(
            _flag_box_at(cell.to_seat, template.cell.flag_box),
            template.clearance))
    return tuple(rooms)


def _service_joint_refusal(
    request: PlacementInput,
    template: ServiceSeatTemplate,
    plan: BoundPanelSeatPlan,
    siblings: Sequence[tuple[BoundPanelSeatPlan, ServiceSeatTemplate]],
) -> BoundPanelSeatPlan | None:
    """Does this seat and an earlier one stand on each other's drawn lead?

    Both facts are geometric and both are positive area: every leg of an earlier
    seat's recorded host lead against this cell's body and terminal flag room,
    and every leg of this cell's own lead against an earlier cell's body and flag
    room (:func:`_service_lead_rooms` — the printed rows are the text pass's).
    A leg is widened by :data:`SERVICE_WALL_PAD` — the same ruler the panel walls
    use — because a drawn run has thickness even though its centre line does not.

    The netlist is not consulted. Two seats on the **same** net are still two
    runs: one branch's lead through another branch's body or flag is unreadable
    whether or not it is electrically legal, so connectivity is not an exemption
    here.
    """
    if not plan.seated or not plan.cells:
        return None
    rooms = _service_lead_rooms(request, template, plan)
    for prior, prior_template in siblings:
        if not prior.seated:
            continue
        for path in prior.host_paths:
            for leg in _service_lead_legs(path):
                for box in rooms:
                    if _boxes_overlap(leg, box) > 0.0:
                        return replace(plan, refusal=PanelSeatRefusal(
                            template.group_id,
                            f"{template.cell.part_id}'s body/terminal flag room "
                            f"{box} stands on the host lead of "
                            f"{prior.group_id} ({path}) — a lead runs inside its "
                            "own branch's room and nowhere else",
                            "seat the branch whose terminal flag hangs towards "
                            "that row first, or move the two branches apart",
                        ))
        for path in plan.host_paths:
            for leg in _service_lead_legs(path):
                for box in _service_lead_rooms(
                        request, prior_template, prior):
                    if _boxes_overlap(leg, box) > 0.0:
                        return replace(plan, refusal=PanelSeatRefusal(
                            template.group_id,
                            f"the host lead of {template.cell.part_id} ({path}) "
                            f"runs through {prior.group_id}'s body/terminal flag "
                            f"room {box} — a lead must not cross another seated "
                            "branch's room",
                            "seat the branch on the lower row first, or move the "
                            "two branches apart",
                        ))
    return None


def _solve_service_relative(
    request: PlacementInput,
    template: ServiceSeatTemplate,
    host_pose: SymbolPose,
) -> BoundPanelSeatPlan:
    """One service cell beside the host, in **host-relative** coordinates.

    The geometry is the panel's own: the cell's real part/text/flag reserve is
    the room (``_panel_relative_reserve``), the origin is snapped by the same
    ``_series_snap`` lattice and the host's body box is the reference. What
    changes with the side is only which body edge the reserve is placed against
    and which axis the from→to reading runs along — a frame change, not a second
    seat equation. No host lead is routed here — routing an obstacle stays the
    drawing's work — but the **direct span** from the host pin's real tip to the
    from foot is recorded in this same relative frame (:func:`_service_direct_path`),
    so the rigid translation that places the host places the recorded lead with
    it. A ladder rung then re-attaches it in the answer's frame.
    """
    cell = template.cell
    host_profile = request.part(template.host_part).profile
    host_origin = (0.0, 0.0)
    body = pose_box(
        host_profile.body, rotation=host_pose.rotation, mirror=host_pose.mirror,
        ox=host_origin[0], oy=host_origin[1],
    )
    if body is None:
        return _service_refusal(
            template,
            f"the host {template.host_part!r} draws no body, so there is no "
            "body box to place the service cell against",
            "give the host a symbol with a body, or drop the service seat")
    host_pin = _pin_for_token(host_profile, cell.host_token)
    if host_pin is None:
        return _service_refusal(
            template,
            f"the host {template.host_part!r} has no pin {cell.host_token!r}",
            "correct the host token, or drop the service seat")
    reserve = _panel_relative_reserve(request, cell)
    if reserve is None:
        return _service_refusal(
            template,
            f"{cell.part_id}: its symbol has no pin {cell.to_token!r}, so the "
            "terminal flag's room cannot be placed",
            "correct the terminal token, or drop the flag reservation")
    union, boxes = reserve
    profile = request.part(cell.part_id).profile
    from_pin = _pin_for_token(profile, cell.from_token)
    to_pin = _pin_for_token(profile, cell.to_token)
    if from_pin is None or to_pin is None:
        return _service_refusal(
            template,
            f"{cell.part_id}: its symbol has no pin {cell.from_token!r} / "
            f"{cell.to_token!r}, so the cell's two ends cannot be seated",
            "correct the tokens, or drop the seat")
    host_tip = posed_tip(host_pin.tip, host_pose, host_origin)
    right = template.side == PANEL_SIDE_RIGHT
    # 548D3S2: the side is a template fact, and the host may be searched in any
    # of its poses. A pose that turns the host pin's own outward direction away
    # from the declared reading side is a named refusal — the cell must not be
    # drawn on the side the pin does not face.
    local_out = _panel_pin_direction(host_pin)
    if local_out is None:
        return _service_refusal(
            template,
            f"{cell.part_id}: the host pin {cell.host_token!r} of "
            f"{template.host_part!r} states no drawable direction "
            f"({host_pin.direction!r}), so the reading side cannot be checked",
            "give that library pin a left/right/up/down direction, or drop the "
            "service seat")
    outward = transform_point(
        *local_out, rotation=host_pose.rotation, mirror=host_pose.mirror,
        ox=0.0, oy=0.0,
    )
    want = (1.0, 0.0) if right else (-1.0, 0.0)
    if abs(outward[0] - want[0]) > 1e-6 or abs(outward[1] - want[1]) > 1e-6:
        return _service_refusal(
            template,
            f"the host pin {cell.host_token!r} faces "
            f"({'right' if outward[0] > 0 else 'left'}) in this host pose, "
            f"while the seat is declared on the {template.side!r} side — the "
            "cell cannot be drawn on a side its pin does not face",
            "drop the host pose that turns the pin away, or declare the seat on "
            "the side the pin faces")

    edge = body[2] if right else body[0]
    # The reserve's host-side edge stands one pitch off the body; the cell is
    # centred on the host pin along the other axis, which is the reading side's
    # own answer (a panel centres the grid under the body because it is a row).
    raw_x = (
        edge + template.pitch - union[0] if right
        else edge - template.pitch - union[2]
    )
    # The **from foot** is what must stand on the host pin's axis: a service
    # branch reads as one run out of that pin, so its own foot has to be at the
    # pin's y, not the reserve's centre. The relative tip is read from the cell's
    # real pose (no second geometry rule), and the lattice snap is then checked:
    # if the pin's axis does not fall on this template's lattice, the binder
    # refuses by name rather than silently shifting the foot off the pin.
    relative_from = posed_tip(from_pin.tip, cell.pose, (0.0, 0.0))
    raw_y = host_tip[1] - relative_from[1]
    ox = _series_snap(raw_x, template.grid, template.lattice[0])
    oy = _series_snap(raw_y, template.grid, template.lattice[1])
    if abs(oy - raw_y) > SERIES_EPS:
        return _service_refusal(
            template,
            f"{cell.part_id}: its from foot {cell.from_token} cannot stand on "
            f"the host pin {cell.host_token}'s axis — the pin is at "
            f"y={host_tip[1]:g}, which needs origin y={raw_y:g}, and this "
            f"template's lattice (grid {template.grid:g}, offset "
            f"{template.lattice[1]:g}) would put it at y={oy:g}",
            "state a grid/lattice the host pin's axis falls on, or drive the "
            "cell from a pin whose axis does")
    origin = (ox, oy)
    from_seat = posed_tip(from_pin.tip, cell.pose, origin)
    to_seat = posed_tip(to_pin.tip, cell.pose, origin)
    if abs(from_seat[1] - host_tip[1]) > SERIES_EPS:
        return _service_refusal(
            template,
            f"{cell.part_id}: its from foot {cell.from_token} stands at "
            f"y={from_seat[1]:g} while the host pin {cell.host_token} is at "
            f"y={host_tip[1]:g} — a service cell reads out of its host foot, "
            "and this binder does not draw that branch off-axis",
            "state a grid/lattice the host pin's axis falls on, or drop the "
            "service seat")
    # The from foot must be the host-side foot on the reading axis: a cell whose
    # pose faces the terminal towards its host would draw the branch backwards.
    if right and not (from_seat[0] < to_seat[0] - SERIES_EPS):
        return _service_refusal(
            template,
            f"{cell.part_id}: the chosen pose puts its from foot "
            f"{cell.from_token} at x={from_seat[0]:g} and its to foot "
            f"{cell.to_token} at x={to_seat[0]:g} — a right-side cell reads "
            "from the host outwards",
            "use a pose whose from foot faces the host, or drop the seat")
    if not right and not (from_seat[0] > to_seat[0] + SERIES_EPS):
        return _service_refusal(
            template,
            f"{cell.part_id}: the chosen pose puts its from foot "
            f"{cell.from_token} at x={from_seat[0]:g} and its to foot "
            f"{cell.to_token} at x={to_seat[0]:g} — a left-side cell reads "
            "from the host outwards",
            "use a pose whose from foot faces the host, or drop the seat")
    moved = [
        _grow_box((box[0] + ox, box[1] + oy, box[2] + ox, box[3] + oy),
                  template.clearance)
        for box in boxes
    ]
    # §548D3C1: the span this seat will have drawn, in the **same relative
    # frame** as everything else here — the host's own posed tip is ``(0, 0)``'s
    # pin tip, so the rigid translation that places the host places this too.
    # Recorded on every answer, joint or not: the span is the seat's own
    # geometry, and the two consumers that read it (the spread pass and the text
    # walls) need it whatever ordering decided the seat.
    host_path = _service_direct_path(host_tip, from_seat)
    seat = BoundPanelSeat(
        part_id=cell.part_id, host_token=cell.host_token, origin=origin,
        pose=cell.pose, from_seat=from_seat, to_seat=to_seat,
        reserved=tuple(moved), host_path=host_path,
    )
    return BoundPanelSeatPlan(
        group_id=template.group_id, host_part=template.host_part,
        side=template.side, columns=1, cells=(seat,),
        reserved_boxes=tuple(moved), host_paths=(host_path,),
        grid=template.grid, lattice=template.lattice,
    )


#: Service solves, keyed by template (side, pose, text/flag and ``flag_lead``
#: included) and the host's own geometry/pose — never by the host origin, which
#: is the rigid translation applied afterwards. Empty templates never enter it.
_SERVICE_SOLVE_CACHE: dict[tuple, BoundPanelSeatPlan] = {}
_SERVICE_SOLVE_CACHE_LIMIT = 64


def _bind_one_service(
    request: PlacementInput,
    template: ServiceSeatTemplate,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
    siblings: Sequence[tuple[BoundPanelSeatPlan, ServiceSeatTemplate]] = (),
    panel_walls: Sequence[Box] = (),
) -> BoundPanelSeatPlan:
    """One service template -> one bound plan, or a named refusal."""
    return _bind_one_service_joint(
        request, template, origins, poses, siblings, panel_walls)[0]


def _bind_one_service_joint(
    request: PlacementInput,
    template: ServiceSeatTemplate,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
    siblings: Sequence[tuple[BoundPanelSeatPlan, ServiceSeatTemplate]] = (),
    panel_walls: Sequence[Box] = (),
) -> tuple[BoundPanelSeatPlan, bool]:
    """One service template -> one bound plan, or a named refusal.

    The second value says whether the **joint** seat test of §548D3C1 changed this
    answer — a rung the crossing refused, or a crossing that refused the seat.
    That is the only fact the caller's order search is about; a ladder rung taken
    for an earlier branch's *printed/part room* (or for a panel channel) is the
    old behaviour and is not reported as joint.
    """
    if template.host_part not in origins or template.host_part not in poses:
        return _service_refusal(
            template,
            f"the host {template.host_part!r} is not part of this request's answer",
            "name a host that is in the request, or drop the seat"), False
    locked = request.locked_origins()
    for name in (template.host_part, template.cell.part_id):
        if name in locked:
            return _service_refusal(
                template,
                f"{name!r} is pinned by a user lock, and a service seat is a "
                "computed origin — the two cannot both hold",
                "drop the lock on this part, or drop the service seat and place "
                "it by hand"), False
    host_profile = request.part(template.host_part).profile
    host_pose = poses[template.host_part]
    host_origin = origins[template.host_part]
    key = (
        _service_template_key(template),
        _panel_host_geometry_key(host_profile),
        _panel_pose_key(host_pose),
        # §548D3C1: the relative solve records the host span only under the joint
        # contract, so the two answers must not share a cache entry.
        request.service_joint_order,
    )
    relative = _SERVICE_SOLVE_CACHE.get(key)
    if relative is None:
        relative = _solve_service_relative(request, template, host_pose)
        if len(_SERVICE_SOLVE_CACHE) >= _SERVICE_SOLVE_CACHE_LIMIT:
            _SERVICE_SOLVE_CACHE.clear()
        _SERVICE_SOLVE_CACHE[key] = relative
    if relative.refusal is not None:
        return relative, False
    plan = relative.translated(host_origin)
    host_pin = _pin_for_token(host_profile, template.cell.host_token)
    host_tip = (
        None if host_pin is None else
        posed_tip(host_pin.tip, host_pose, host_origin))
    if host_tip is not None:
        # §548D3C1: the span this seat will have drawn, from the host's own tip.
        plan = _service_host_path(plan, host_tip)
    # A second cell on the same side (two LEDs off adjacent host pins) cannot
    # take the same column: it is stepped **outwards** along the reading axis,
    # which keeps its from foot on its own host pin's axis. A bounded ladder, and
    # a named refusal when no rung is clear — never a silent overlap.
    #
    # §35C: the same ladder yields to the **panel's** room as well — its reserves
    # and every host-lead leg (as boxes). A panel channel was promised that lane
    # first, so a service cell steps outwards until it is clear of it, and the
    # ladder never clears a part while leaving the channel it shares unmeasured.
    #
    # §548D3C1: a rung must clear an earlier branch's **drawn lead** as well, in
    # both directions — this cell's room off that lead, and this cell's lead out
    # of that room. Stepping outwards is the whole answer to a lead that lies
    # between the host and this seat, because the lead only gets longer with the
    # step, never shorter.
    #
    # The rung itself still clears the earlier branch's whole reserved room,
    # printed rows included. A lead through a **flag's own lead** is not a box
    # overlap this layer can see, and measured on the real MCU page, dropping the
    # rows from the ladder let the declared order "succeed" with the BOOT0 lead
    # drawn straight through the decoupling's flag lead at x=-150 — a seat that
    # is legal by area and wrong on the page. The rows stay an obstacle here; the
    # drawing is the layer that may move them.
    taken = [
        box for other, _ in siblings for box in other.reserved_boxes
    ] + list(panel_walls)
    joint = False
    if taken and plan.seated and plan.cells:
        step = max(template.pitch, template.grid, DEFAULT_GRID)
        sign = 1.0 if template.side == PANEL_SIDE_RIGHT else -1.0
        base = plan
        crossed: str | None = None
        # The ladder's length is the page's own size, not a constant: a page
        # with N parts cannot need more than N distinct columns on one side.
        for rung in range(0, max(1, len(request.parts))):
            moved = base if rung == 0 else base.translated(
                (sign * step * rung, 0.0))
            if host_tip is not None:
                moved = _service_host_path(moved, host_tip)
            padded = [
                _grow_box(box, template.clearance)
                for box in moved.reserved_boxes
            ]
            if any(
                _boxes_overlap(box, other) > 0.0
                for box in padded for other in taken
            ):
                continue
            clash = (
                _service_joint_refusal(request, template, moved, siblings)
                if request.service_joint_order else None)
            if clash is not None:
                joint = True
                crossed = (
                    clash.refusal.render() if clash.refusal is not None else None)
                continue
            plan = moved
            break
        else:
            return _service_refusal(
                template,
                f"{template.cell.part_id}: every rung outwards on the "
                f"{template.side!r} side still stands on another service cell's "
                "reserved room or host lead, or on the panel's own room/host "
                "lead"
                + (f"; the widest rung was refused by: {crossed}"
                   if crossed else ""),
                "give the two branches more room, move the panel host, or drop "
                "one of them"), joint
    clash = (
        _service_joint_refusal(request, template, plan, siblings)
        if request.service_joint_order else None)
    if clash is not None:
        return clash, True
    return _service_foreign_refusal(
        request, template, plan, origins, poses, panel_walls), joint


#: The page's own service count bounds the joint-order search. Three seats are
#: six orders and the two flag-stated orders already answer the two-ended cases,
#: so that is where permuting stops; a larger page uses the declared order and
#: the two reading orders only. The cost is measured, not assumed: the real
#: four-service page's *refusing* candidate search re-binds 3 sequences per
#: candidate rather than 27 (the 24-permutation page took ~70 s per compile,
#: 3 sequences take ~5 s), and a page that cannot seat is searched on every
#: candidate, so the bound is a runtime fact and not only a tidiness one.
SERVICE_ORDER_PERMUTATION_LIMIT = 3


def _service_flag_axis(template: ServiceSeatTemplate) -> int:
    """``-1`` for a terminal flag that hangs down, ``1`` for one that rises.

    Read off the cell's own ``flag_lead`` — the compiler's stated lead, in page
    axes — so the order is the page's fact and not a second reading of the flag
    box. ``0`` is a branch with no stated lead: it states no preference.
    """
    lead = template.cell.flag_lead
    if len(lead) < 2:
        return 0
    drop = lead[-1][1] - lead[0][1]
    if drop < -SERIES_EPS:
        return -1
    return 1 if drop > SERIES_EPS else 0


def _service_host_row(
    request: PlacementInput,
    template: ServiceSeatTemplate,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
) -> float:
    """The host pin's own row in this answer (``0`` when it is not in hand)."""
    if template.host_part not in origins or template.host_part not in poses:
        return 0.0
    pin = _pin_for_token(
        request.part(template.host_part).profile, template.cell.host_token)
    if pin is None:
        return 0.0
    return posed_tip(
        pin.tip, poses[template.host_part], origins[template.host_part])[1]


def _service_seat_orders(
    request: PlacementInput,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
) -> tuple[tuple[ServiceSeatTemplate, ...], ...]:
    """The orders a joint seat conflict may be asked to settle (§548D3C1).

    The declared order comes first and is the answer unless the joint test had
    to move or refuse a cell (:func:`_bind_one_service`'s second value). Behind
    it stand the orders the branches' **terminal flags** state: a flag that hangs
    down claims the rows below it, so the branch on the **low** host row takes
    its near seat first and the branch above it yields outwards; a flag that
    rises states the mirror, and the high row goes first. Which of the two comes
    first is decided by the flags present (a downward flag present = low row
    first), ties break on the template key, so two branches on the same row or
    with the same flag are still one deterministic order.

    On a page with at most :data:`SERVICE_ORDER_PERMUTATION_LIMIT` seats every
    remaining permutation follows, in the templates' own order — the search is
    bounded by the page's own count, never open-ended.
    """
    templates = request.service_templates
    if len(templates) < 2:
        return (templates,)

    def row(template: ServiceSeatTemplate) -> tuple[float, tuple]:
        return (
            _service_host_row(request, template, origins, poses),
            _service_template_key(template),
        )

    low_first = tuple(sorted(templates, key=row))
    high_first = tuple(sorted(
        templates, key=lambda template: (-row(template)[0], row(template)[1])))
    reading = (
        (low_first, high_first)
        if any(_service_flag_axis(template) < 0 for template in templates)
        else (high_first, low_first)
    )
    orders: list[tuple[ServiceSeatTemplate, ...]] = []
    seen: set[tuple] = set()

    def keep(order: tuple[ServiceSeatTemplate, ...]) -> None:
        key = tuple(_service_template_key(template) for template in order)
        if key not in seen:
            seen.add(key)
            orders.append(order)

    keep(templates)
    for order in reading:
        keep(order)
    if len(templates) <= SERVICE_ORDER_PERMUTATION_LIMIT:
        for order in itertools.permutations(templates):
            keep(order)
    return tuple(orders)


def _bind_service_sequence(
    request: PlacementInput,
    templates: Sequence[ServiceSeatTemplate],
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
    walls: Sequence[Box],
    *,
    stop_at_refusal: bool = False,
) -> tuple[tuple[BoundPanelSeatPlan, ...], bool]:
    """One order of the page's service seats, and whether the joint test bit.

    The cells are seated one after another against the seats already taken; the
    caller's mappings are copied, not mutated. ``True`` means at least one cell
    had a rung refused by, or was refused by, the joint lead test — the fact
    :func:`bind_service_plans` re-orders for.

    ``stop_at_refusal`` is the trial's shape: an order that already has a refused
    cell cannot be the answer, so the remaining (and most expensive) cells are
    not bound for it. The declared order is always bound in full, because its
    plans are what the caller receives when no order seats the page.
    """
    out: list[BoundPanelSeatPlan] = []
    pairs: list[tuple[BoundPanelSeatPlan, ServiceSeatTemplate]] = []
    joint = False
    local_origins = dict(origins)
    local_poses = dict(poses)
    for template in templates:
        # Every plan so far is a sibling, refused ones included: a refusal that
        # still carries its seats (a foreign part in the room) keeps its reserved
        # boxes, and the ladder below must see them — that is the legacy answer,
        # measured (one rung per refused-but-placed cell).
        plan, moved = _bind_one_service_joint(
            request, template, local_origins, local_poses, tuple(pairs), walls)
        out.append(plan)
        pairs.append((plan, template))
        joint = joint or moved
        if not plan.seated:
            if stop_at_refusal:
                break
            continue
        cell = plan.cells[0]
        if cell.origin is not None and cell.pose is not None:
            local_origins[cell.part_id] = cell.origin
            local_poses[cell.part_id] = cell.pose
    return tuple(out), joint


def bind_service_plans(
    request: PlacementInput,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
    panel_plans: Sequence[BoundPanelSeatPlan] = (),
) -> tuple[BoundPanelSeatPlan, ...]:
    """The one binder for every declared service seat, against this answer.

    Empty on every request that declares none, so a historical request makes no
    call at all (``place`` guards on the field), adds no cost term and keeps its
    seed, moves and trajectory.

    ``panel_plans`` is the panel bound against **the same answer** (§35C). Its
    reserves and host-lead legs become the lane the service cells yield to, both
    in the outward ladder and in the final foreign re-check. Empty — the default
    — is every pre-S4 call shape, byte for byte: no wall, no extra rung, no new
    refusal.

    §548D3C1: the declared order is answered unchanged unless a cell's **drawn
    lead** and another cell's room forced a rung or a refusal. Only then is the
    order searched — the two flag-stated reading orders and, on a page with at
    most :data:`SERVICE_ORDER_PERMUTATION_LIMIT` seats, the remaining
    permutations — and the seats are the winning order's. The plans still come
    back **one per declared seat, in the declared order**: the order is a fact
    about which seat was taken first, not about which template owns which plan.
    Every cell of that order is seated, and no plan leans on the joint test; when
    no order manages that, the declared order's own named refusals are returned
    rather than a silent free seat. This whole paragraph is gated on
    :attr:`PlacementInput.service_joint_order`: on a page that does not state it
    (the default, and every legacy ``panelGroups`` page) the declared order is
    returned as it stands.
    """
    if not request.service_templates:
        return ()
    walls = _panel_service_walls(panel_plans)
    # Sequential on purpose: one service cell's seat is another's foreign part
    # until it is placed, so every later cell is measured against the seats the
    # earlier ones already took. The caller's mappings are not mutated here.
    plans, joint = _bind_service_sequence(
        request, request.service_templates, origins, poses, walls)
    if not request.service_joint_order:
        # Legacy page (the default): the declared order is the answer, however
        # many cells it seats. No re-ordering, no joint rung, no extra refusal —
        # every page that does not state the joint contract keeps the seats it
        # always had, and its ``host_paths`` only gains the recorded span.
        return plans
    if not joint and all(plan.seated for plan in plans):
        # The declared order is the page's own statement and the answer stands:
        # no crossing forced a rung, no cell was refused, so nothing is
        # re-ordered and the seats are the ones this binder always produced.
        return plans
    # §548D3C1: the declared order needed the joint test to move a cell, or could
    # not seat one at all, so the branches' own terminal flags are asked for an
    # order. A refusal alone is the trigger on purpose: the measured MCU page's
    # declared order dies on an earlier branch's *printed rows* in the outward
    # lane (a rung-exhaustion, not a lead crossing), and the reversed order seats
    # both cells with every lead one straight run.
    for order in _service_seat_orders(request, origins, poses)[1:]:
        attempt, moved = _bind_service_sequence(
            request, order, origins, poses, walls, stop_at_refusal=True)
        if (not moved and len(attempt) == len(order)
                and all(plan.seated for plan in attempt)):
            by_group = {plan.group_id: plan for plan in attempt}
            return tuple(
                by_group[template.group_id]
                for template in request.service_templates)
    return plans


def seat_service_plans(
    plans: Sequence[BoundPanelSeatPlan],
    origins: dict[str, tuple[float, float]],
    poses: dict[str, SymbolPose],
) -> None:
    """Write every seated service cell's origin and pose into the answer."""
    for plan in plans:
        if not plan.seated:
            continue
        for cell in plan.cells:
            assert cell.origin is not None and cell.pose is not None
            origins[cell.part_id] = cell.origin
            poses[cell.part_id] = cell.pose


def service_parts_of(plans: Sequence[BoundPanelSeatPlan]) -> frozenset[str]:
    """Every part a service seat owns — never moved on its own by the search."""
    return frozenset(
        cell.part_id for plan in plans for cell in plan.cells
    )


def _check_service_templates(request: PlacementInput) -> None:
    """The request's service templates, checked once before any solve.

    Only the facts the binder would otherwise discover per candidate: the parts
    exist, one group id each, and no part is seated twice (by two service seats,
    or by a panel and a service seat). Tokens and poses are checked by the
    binder itself, where the symbol is in hand.
    """
    if not request.service_templates:
        return
    ids = {part.part_id for part in request.parts}
    panel_cells = {
        cell.part_id
        for template in request.panel_templates for cell in template.cells
    }
    groups: set[str] = set()
    seated: set[str] = set()
    for template in request.service_templates:
        if not isinstance(template, ServiceSeatTemplate):
            raise PlacementError(
                "service_templates takes ServiceSeatTemplate entries only")
        if template.group_id in groups:
            raise PlacementError(
                f"two service seats share the group id {template.group_id!r}")
        groups.add(template.group_id)
        for name in (template.host_part, template.cell.part_id):
            if name not in ids:
                raise PlacementError(
                    f"service seat {template.group_id!r} names {name!r}, which "
                    "is not one of this request's parts")
        if template.cell.part_id in panel_cells:
            raise PlacementError(
                f"service seat {template.group_id!r} seats "
                f"{template.cell.part_id!r}, which a panel already seats")
        if template.cell.part_id in seated:
            raise PlacementError(
                f"{template.cell.part_id!r} is seated by two service seats")
        seated.add(template.cell.part_id)


def _panel_relative_reserve(
    request: PlacementInput, cell: PanelCell,
) -> tuple[Box, tuple[Box, ...]] | None:
    """The cell's own room, relative to its origin; ``None`` on a bad token."""
    profile = request.part(cell.part_id).profile
    boxes: list[Box] = [part_box(profile, cell.pose, (0.0, 0.0))]
    boxes.extend(tuple(cell.text_boxes))
    if cell.flag_box is not None:
        pin = _pin_for_token(profile, cell.to_token)
        if pin is None:
            return None
        at = posed_tip(pin.tip, cell.pose, (0.0, 0.0))
        boxes.append(FlagReservation(
            part_id=cell.part_id, token=cell.to_token, net_id=cell.to_net,
            box=cell.flag_box,
        ).box_at(at))
    return (
        (min(box[0] for box in boxes), min(box[1] for box in boxes),
         max(box[2] for box in boxes), max(box[3] for box in boxes)),
        tuple(boxes),
    )


def _panel_pin_direction(pin: SymbolPin) -> tuple[float, float] | None:
    """The pin's own outward direction in the symbol's frame, or ``None``.

    Only the four directions a pin can be drawn by are known. Anything else
    (empty, a family name, a diagonal) is a pin whose side this binder cannot
    read, and picking one would be a guessed escape route: the caller refuses
    the cell by name instead.
    """
    return {
        "left": (-1.0, 0.0), "right": (1.0, 0.0),
        "up": (0.0, 1.0), "down": (0.0, -1.0),
    }.get(pin.direction)


def _panel_path_crosses(
    path: Sequence[tuple[float, float]], box: Box, pad: float,
) -> bool:
    """Does this orthogonal path touch (or cross) the padded box?

    A path segment is a **line**: a zero-height box would never overlap another
    box under the strict area test, so each segment is given the thinnest
    thickness this module reserves for a drawn stroke (``PIN_TEXT_WALL`` is the
    compiler's, ``1.0`` here) before the test.
    """
    grown = _grow_box(box, pad)
    thickness = 1.0
    for start, stop in zip(path, path[1:]):
        seg = (
            min(start[0], stop[0]) - thickness, min(start[1], stop[1]) - thickness,
            max(start[0], stop[0]) + thickness, max(start[1], stop[1]) + thickness,
        )
        if _boxes_overlap(seg, grown) > 0.0:
            return True
    return False


def _grow_box(box: Box, pad: float) -> Box:
    return (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)


@dataclass(frozen=True)
class _PanelLeadRoute:
    """One cell's lead as the layout pass knows it, before any path is routed."""

    cell: PanelCell
    host_pin_tip: tuple[float, float]
    stub: tuple[float, float]
    entry: tuple[float, float]
    from_seat: tuple[float, float]
    to_seat: tuple[float, float]
    own_body: Box | None
    moved: tuple[Box, ...]


def _panel_lead_bounds(
    body: Box, leads: Sequence[_PanelLeadRoute], pitch: float,
) -> Box:
    """The search box the joint lead pass is allowed to use.

    The union of the host body, every stub/entry/seat and every cell's reserved
    room, grown by one pitch. It is the panel's own strip — not the whole host
    height with a blind ``4 * pitch`` on top, which made the router's cost field
    the dominant cost of a bind.
    """
    xs = [body[0], body[2]]
    ys = [body[1], body[3]]
    for lead in leads:
        for point in (lead.host_pin_tip, lead.stub, lead.entry,
                      lead.from_seat, lead.to_seat):
            xs.append(point[0])
            ys.append(point[1])
        for box in lead.moved:
            xs.extend((box[0], box[2]))
            ys.extend((box[1], box[3]))
    pad = max(pitch, 2.0 * DEFAULT_GRID)
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def _panel_lattice_points(
    start: tuple[float, float], stop: tuple[float, float], grid: float,
) -> list[tuple[float, float]]:
    """The lattice nodes on one axis-aligned lead leg (endpoints included)."""
    if grid <= 0.0:
        return [start, stop]
    dx = stop[0] - start[0]
    dy = stop[1] - start[1]
    steps = int(round(max(abs(dx), abs(dy)) / grid))
    if steps == 0:
        return [start]
    return [
        (round(start[0] + dx * index / steps, 6),
         round(start[1] + dy * index / steps, 6))
        for index in range(steps + 1)
    ]


def _panel_leads_meet(
    left: Sequence[tuple[float, float]],
    right: Sequence[tuple[float, float]],
) -> bool:
    """Do two routed leads share a node, or run collinearly on one line?

    The router already treats an earlier lead as walls and foreign edges; this is
    the post-check §30C asks for, written against the two finished polylines
    rather than trusting the search's own bookkeeping.
    """
    if {_router._rounded(point) for point in left} & {
            _router._rounded(point) for point in right}:
        return True
    for start, stop in zip(left, left[1:]):
        for other_start, other_stop in zip(right, right[1:]):
            if _router._collinear_overlap(start, stop, other_start, other_stop):
                return True
            if (_router._strictly_on_segment(start, other_start, other_stop)
                    or _router._strictly_on_segment(
                        other_start, start, stop)):
                return True
    return False


#: Host-relative panel solves, keyed by the immutable template geometry, the
#: host profile's own geometry and the host pose. A panel's seats and leads are
#: a function of exactly those three things plus a rigid translation: the search
#: re-binds the same panel for many candidates of one pose, and routing it again
#: is the per-candidate cost that made the joint pass unaffordable.
#:
#: The cache holds **template geometry only** — never a foreign part, a lock or a
#: candidate's own reserves. Those are checked on the translated answer of every
#: call (see :func:`_bind_one_panel`), so a cached solve cannot excuse a part
#: that has since moved onto the panel.
_PANEL_SOLVE_CACHE: dict[tuple, "BoundPanelSeatPlan"] = {}
_PANEL_SOLVE_CACHE_LIMIT = 64


def _panel_pose_key(pose: SymbolPose) -> tuple:
    return (int(pose.rotation), bool(pose.mirror))


def _panel_cell_key(cell: PanelCell) -> tuple:
    """Everything about one cell a solve depends on, floats normalised (§35)."""
    return (
        cell.part_id, cell.from_net, cell.to_net, cell.from_token,
        cell.to_token, cell.host_token, _panel_pose_key(cell.pose),
        tuple(tuple(float(v) for v in box) for box in cell.text_boxes),
        None if cell.flag_box is None
        else tuple(float(v) for v in cell.flag_box),
        tuple((float(point[0]), float(point[1])) for point in cell.flag_lead),
    )


def _panel_template_key(template: PanelSeatTemplate) -> tuple:
    return (
        template.group_id, template.host_part, template.side,
        int(template.columns), float(template.grid),
        (float(template.lattice[0]), float(template.lattice[1])),
        float(template.clearance), float(template.pitch),
        tuple(_panel_cell_key(cell) for cell in template.cells),
    )


def _panel_host_geometry_key(profile: SymbolProfile) -> tuple:
    """The host's own geometry — not its origin (the solve is relative to it)."""
    return (
        profile.symbol_ref,
        None if profile.body is None else tuple(float(v) for v in profile.body),
        tuple(
            (pin.number, pin.direction,
             None if pin.tip is None
             else (float(pin.tip[0]), float(pin.tip[1])))
            for pin in profile.pins
        ),
    )


def _bind_one_panel(
    request: PlacementInput,
    template: PanelSeatTemplate,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
) -> BoundPanelSeatPlan:
    """One template -> one bound plan (or a named refusal, never an exception).

    The geometry is solved **once per host pose** in host-relative coordinates
    and then translated by the host's origin; the per-candidate environment
    (foreign parts, and their room) is re-checked on every call, because that is
    the one thing a cache must never answer for.
    """
    if template.side != PANEL_SIDE_BOTTOM:
        return _panel_refusal(
            template,
            f"side {template.side!r} is not a panel this build can seat: the "
            "grid under the host body is the only side with a solved equation",
            "state side='bottom', or wait for the other sides to be implemented",
        )
    if template.host_part not in origins or template.host_part not in poses:
        return _panel_refusal(
            template,
            f"the host {template.host_part!r} is not part of this request's answer",
            "name a host that is in the request, or drop the panel",
        )
    locked = request.locked_origins()
    for name in (template.host_part, *(cell.part_id for cell in template.cells)):
        if name in locked:
            return _panel_refusal(
                template,
                f"{name!r} is pinned by a user lock, and a panel seat is a "
                "computed origin — the two cannot both hold",
                "drop the lock on this part, or drop the panel and place it by hand",
            )
    host_profile = request.part(template.host_part).profile
    host_pose = poses[template.host_part]
    host_origin = origins[template.host_part]
    key = (
        _panel_template_key(template),
        _panel_host_geometry_key(host_profile),
        _panel_pose_key(host_pose),
    )
    relative = _PANEL_SOLVE_CACHE.get(key)
    if relative is None:
        relative = _solve_panel_relative(request, template, host_pose)
        if len(_PANEL_SOLVE_CACHE) >= _PANEL_SOLVE_CACHE_LIMIT:
            _PANEL_SOLVE_CACHE.clear()
        _PANEL_SOLVE_CACHE[key] = relative
    if relative.refusal is not None:
        return relative
    plan = relative.translated(host_origin)
    if plan.refusal is not None:
        return plan
    cell_ids = {cell.part_id for cell in template.cells}
    for other in request.parts:
        if other.part_id in cell_ids | {template.host_part}:
            continue
        if other.part_id not in origins or other.part_id not in poses:
            continue
        foreign = part_box(
            other.profile, poses[other.part_id], origins[other.part_id])
        for name, reserve_box in zip(
            (cell.part_id for cell in plan.cells), plan.reserved_boxes):
            if _boxes_overlap(foreign, reserve_box) > 0.0:
                # The seats and reserved boxes travel with the refusal: the cost
                # term prices this plan by how much room the foreign part takes.
                return replace(plan, refusal=PanelSeatRefusal(
                    template.group_id,
                    f"foreign part {other.part_id!r} at {foreign} intrudes on "
                    f"cell {name}'s reserved part/text/flag room {reserve_box} — "
                    "the panel's room is not taken from another part",
                    "move the foreign part out of the panel's rows, or drop the panel",
                ))
    return plan


def _solve_panel_relative(
    request: PlacementInput,
    template: PanelSeatTemplate,
    host_pose: SymbolPose,
) -> BoundPanelSeatPlan:
    """The panel's seats and leads in **host-relative** coordinates.

    Called only through :func:`_bind_one_panel`'s cache. Everything it reads is
    template geometry or the host's own profile/pose; the host's origin is
    ``(0, 0)`` here and the answer is translated afterwards.
    """
    host_profile = request.part(template.host_part).profile
    host_origin = (0.0, 0.0)
    body = pose_box(
        host_profile.body, rotation=host_pose.rotation, mirror=host_pose.mirror,
        ox=host_origin[0], oy=host_origin[1],
    )
    if body is None:
        return _panel_refusal(
            template,
            f"the host {template.host_part!r} draws no body, so there is no "
            "body box to solve the panel's columns against",
            "give the host a symbol with a body, or drop the panel",
        )
    reserves: list[tuple[Box, tuple[Box, ...]]] = []
    for cell in template.cells:
        reserve = _panel_relative_reserve(request, cell)
        if reserve is None:
            return _panel_refusal(
                template,
                f"{cell.part_id}: its symbol has no pin {cell.to_token!r}, so the "
                "terminal flag's room cannot be placed",
                "correct the terminal token, or drop the flag reservation",
            )
        reserves.append(reserve)
    columns = template.columns
    rows = math.ceil(len(template.cells) / columns)
    col_width = [
        max((reserves[index][0][2] - reserves[index][0][0])
            for index in range(len(template.cells)) if index % columns == column)
        for column in range(columns)
    ]
    row_height = [
        max((reserves[index][0][3] - reserves[index][0][1])
            for index in range(len(template.cells))
            if index // columns == row)
        for row in range(rows)
    ]
    total = sum(col_width) + template.pitch * (columns - 1)
    centre = (body[0] + body[2]) / 2.0
    left = centre - total / 2.0
    top = body[1] - template.pitch
    seats: list[BoundPanelSeat] = []
    host_pin = _pin_for_token(host_profile, template.cells[0].host_token)
    if host_pin is None:
        return _panel_refusal(
            template,
            f"the host {template.host_part!r} has no pin "
            f"{template.cells[0].host_token!r}",
            "correct the host token, or drop the panel",
        )
    lane = body[1] - template.pitch / 2.0
    # Each host foot leaves the body along its own outward direction, and the
    # feet that share a side get **nested** exit channels: the foot nearer the
    # top (or the right) takes the farther channel, so no exit runs across
    # another one. The old corridor gave every foot the same escape column —
    # four nets on one x, which is the short the joint pass exists to remove.
    host_stubs: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    exit_sides: dict[
        tuple[float, float], list[tuple[float, str, tuple[float, float]]]
    ] = {}
    for cell in template.cells:
        pin = _pin_for_token(host_profile, cell.host_token)
        if pin is None:
            continue  # the cell loop refuses this by name
        local_out = _panel_pin_direction(pin)
        if local_out is None:
            return _panel_refusal(
                template,
                f"{cell.part_id}: the host pin {cell.host_token!r} of "
                f"{template.host_part!r} states no drawable direction "
                f"({pin.direction!r}), so the lead has no side to escape by and "
                "this binder will not guess one",
                "give that library pin a left/right/up/down direction, or drive "
                "the cell from another host foot",
            )
        outward = transform_point(
            *local_out, rotation=host_pose.rotation,
            mirror=host_pose.mirror, ox=0.0, oy=0.0,
        )
        tip = posed_tip(pin.tip, host_pose, host_origin)
        exit_sides.setdefault(
            (round(outward[0], 6), round(outward[1], 6)), [],
        ).append((tip[1] if abs(outward[0]) >= abs(outward[1]) else tip[0],
                  cell.part_id, tip))
    for outward_key, members in exit_sides.items():
        members.sort(key=lambda item: (-item[0], item[1]))
        clearance = template.pitch / 2.0
        count = len(members)
        for rank, (_key_value, part_id, tip) in enumerate(members, start=1):
            # The foot nearest the top (right) gets the **farthest** channel; the
            # nested order is what lets every later exit leave inboard without
            # crossing an earlier one's run.
            offset = clearance * (count - rank + 1)
            if abs(outward_key[0]) >= abs(outward_key[1]):
                stub_x = (body[2] + offset if outward_key[0] > 0
                          else body[0] - offset)
                stub = (stub_x, tip[1])
            else:
                stub_y = (body[3] + offset if outward_key[1] > 0
                          else body[1] - offset)
                stub = (tip[0], stub_y)
            host_stubs[part_id] = (tip, stub)
    all_reserved: list[Box] = []
    pending: list[_PanelLeadRoute] = []
    cell_ids = {cell.part_id for cell in template.cells}
    for index, cell in enumerate(template.cells):
        row, column = divmod(index, columns)
        reserve, boxes = reserves[index]
        width = reserve[2] - reserve[0]
        height = reserve[3] - reserve[1]
        x0 = left + sum(col_width[:column]) + template.pitch * column
        y1 = top - sum(row_height[:row]) - template.pitch * row
        ox = _series_snap(
            x0 + (col_width[column] - width) / 2.0 - reserve[0],
            template.grid, template.lattice[0])
        oy = _series_snap(
            y1 - height - reserve[1], template.grid, template.lattice[1])
        origin = (ox, oy)
        profile = request.part(cell.part_id).profile
        from_pin = _pin_for_token(profile, cell.from_token)
        to_pin = _pin_for_token(profile, cell.to_token)
        if from_pin is None or to_pin is None:
            return _panel_refusal(
                template,
                f"{cell.part_id}: its symbol has no pin {cell.from_token!r} / "
                f"{cell.to_token!r}, so the cell's two ends cannot be seated",
                "correct the tokens, or drop the panel",
            )
        from_seat = posed_tip(from_pin.tip, cell.pose, origin)
        to_seat = posed_tip(to_pin.tip, cell.pose, origin)
        if (from_seat[1] - to_seat[1]) <= SERIES_EPS:
            return _panel_refusal(
                template,
                f"{cell.part_id}: the chosen pose does not put its from foot "
                f"({cell.from_token}) above its to foot ({cell.to_token}), so the "
                "cell has no legal panel pose",
                "use a symbol whose feet can run from-host-to-terminal, or drop "
                "the panel",
            )
        moved = [
            _grow_box((box[0] + ox, box[1] + oy, box[2] + ox, box[3] + oy),
                      template.clearance)
            for box in boxes
        ]
        pin = _pin_for_token(host_profile, cell.host_token)
        if pin is None:
            return _panel_refusal(
                template,
                f"{cell.part_id}: the host {template.host_part!r} has no pin "
                f"{cell.host_token!r} for this cell, so its lead has no start",
                "correct the host token, or drop the cell",
            )
        host_pin_tip = posed_tip(pin.tip, host_pose, host_origin)
        # The lead walks a **corridor**, not a diagonal: first it leaves the pin
        # along the pin's own outward direction, posed by the host's rotation and
        # mirror (the same `core.geometry` transform every other point uses), out
        # past the host body; only then does it drop to the row's lane, cross to
        # the column gap nearest the cell, and enter the from foot. A straight
        # drop from a pin that sits over the body would cross it, which is the
        # refusal a whole class of host poses used to hit.
        local_out = _panel_pin_direction(pin)
        if local_out is None:
            return _panel_refusal(
                template,
                f"{cell.part_id}: the host pin {cell.host_token!r} of "
                f"{template.host_part!r} states no drawable direction "
                f"({pin.direction!r}), so the lead has no side to escape by and "
                "this binder will not guess one",
                "give that library pin a left/right/up/down direction, or drive "
                "the cell from another host foot",
            )
        outward = transform_point(
            *local_out, rotation=host_pose.rotation,
            mirror=host_pose.mirror, ox=0.0, oy=0.0,
        )
        clearance = template.pitch / 2.0
        if abs(outward[0]) >= abs(outward[1]):
            escape = (
                (body[2] + clearance if outward[0] > 0 else body[0] - clearance),
                host_pin_tip[1],
            )
        else:
            escape = (
                host_pin_tip[0],
                (body[3] + clearance if outward[1] > 0 else body[1] - clearance),
            )
        row_lane = top - sum(row_height[:row]) - template.pitch / 2.0
        row_lane = max(row_lane, from_seat[1] + template.pitch / 2.0)
        if template.grid > 0.0:
            # The router's nodes are `residue + n * grid`; an entry off that
            # lattice would be rounded by the search to a neighbour, and the last
            # leg into the foot would then not be vertical (or would land on a
            # sibling's lane). Snap it **up**, towards the host, so the leg still
            # enters the foot from above.
            row_lane = (math.floor(
                (row_lane - template.lattice[1]) / template.grid + 1e-9
            ) * template.grid + template.lattice[1])
        own_body = pose_box(
            profile.body, rotation=cell.pose.rotation, mirror=cell.pose.mirror,
            ox=origin[0], oy=origin[1],
        )
        for other_index, other in enumerate(seats):
            if any(_boxes_overlap(box, moved_box) > 0.0
                   for box in moved for moved_box in other.reserved):
                return _panel_refusal(
                    template,
                    f"{cell.part_id}'s reserved part/text/flag room collides with "
                    f"cell {other.part_id}",
                    "state fewer columns, a wider pitch, or drop a branch",
                )
        pending.append(_PanelLeadRoute(
            cell=cell, host_pin_tip=host_pin_tip,
            stub=host_stubs.get(cell.part_id, (host_pin_tip, escape))[1],
            entry=(from_seat[0], row_lane), from_seat=from_seat,
            to_seat=to_seat, own_body=own_body, moved=tuple(moved),
        ))
        seats.append(BoundPanelSeat(
            part_id=cell.part_id, host_token=cell.host_token, origin=origin,
            pose=cell.pose, from_seat=from_seat, to_seat=to_seat,
            reserved=tuple(moved), host_path=(),
        ))
        all_reserved.extend(moved)
    # 548D3X3C-33C2: the leads are routed **together**, in one pass over the
    # panel's own lattice, instead of each from a lane of its own. The old
    # corridor gave every cell the same escape column (all host pins on one side
    # leave at one x) and the same row lane, so two nets' leads could run
    # collinearly along it: the drawing then refused one of them as blocked, and
    # the panel was undeliverable without a shared x. Here an earlier cell's
    # nodes are walls and its legs are foreign edges for the next cell, so this
    # binder never emits two leads that touch or overlap — and when the search
    # has no orthogonal way, the refusal is named instead of narrowing a gap.
    lead_bounds = _panel_lead_bounds(body, pending, template.pitch)
    centre_x = (body[0] + body[2]) / 2.0
    routed: dict[str, tuple[tuple[float, float], ...]] = {}
    for index, lead in sorted(
        enumerate(pending), key=lambda pair: -abs(pair[1].stub[0] - centre_x)
    ):
        others = [
            box for position, item in enumerate(pending) if position != index
            for box in item.moved
        ]
        # Every sibling's endpoints are paper other leads already hold: its host
        # foot, its exit channel, its entry and its from foot. A route that ran
        # through one of them would put two nets on one node even before the
        # post-check saw it.
        guards = [
            (point[0] - 1.0, point[1] - 1.0, point[0] + 1.0, point[1] + 1.0)
            for position, item in enumerate(pending) if position != index
            for point in (item.host_pin_tip, item.stub, item.entry, item.from_seat)
        ]
        search = _router._Router(
            grid=template.grid, residue=template.lattice,
            boxes=others + guards + [body] + (
                [lead.own_body] if lead.own_body is not None else []),
            bounds=lead_bounds,
        )
        for path in routed.values():
            for point in path:
                search.blocked.add(_router._rounded(point))
            for start_point, stop_point in zip(path, path[1:]):
                search.add_edge(start_point, stop_point)
        # Every sibling's **whole exit leg** is paper this lead may not cross or
        # run along either — a later horizontal run through an earlier stub's
        # interior is the same short as a shared node. (Endpoint guards alone
        # missed it once one host pin left vertically.)
        for position, item in enumerate(pending):
            if position == index:
                continue
            for point in _panel_lattice_points(
                    item.host_pin_tip, item.stub, template.grid):
                search.blocked.add(_router._rounded(point))
            search.add_edge(item.host_pin_tip, item.stub)
        # The exit leg is part of *this* lead: its nodes are this lead's own paper
        # and its run is this lead's own edge, so the search may not travel back
        # along it (a doubled-back prefix would draw the same net twice).
        for point in _panel_lattice_points(
                lead.host_pin_tip, lead.stub, template.grid):
            search.blocked.add(_router._rounded(point))
        search.add_edge(lead.host_pin_tip, lead.stub)
        found = search.route(lead.stub, lead.entry)
        if found is None:
            return _panel_refusal(
                template,
                f"{lead.cell.part_id}: no orthogonal host lead from "
                f"{lead.cell.host_token!r} to its from foot was found on the "
                "panel's lattice without touching another cell's room or another "
                "net's lead — the two would be one drawing with two paths",
                "state fewer columns, a wider pitch, or drive the cell from "
                "another host foot",
            )
        path: list[tuple[float, float]] = [lead.host_pin_tip, lead.stub]
        for point in found:
            if path[-1] != point:
                path.append(point)
        if abs(path[-1][0] - lead.from_seat[0]) > SERIES_EPS:
            return _panel_refusal(
                template,
                f"{lead.cell.part_id}: the routed lead reaches "
                f"{path[-1]} and the from foot is at {lead.from_seat}, so the "
                "last leg would not be vertical — a panel lead enters its from "
                "foot from above, never diagonally",
                "state a pitch that puts the from foot on the compilation "
                "lattice, or drive the cell from another host foot",
            )
        if path[-1] != lead.from_seat:
            path.append(lead.from_seat)
        path = tuple(path)
        if lead.own_body is not None and _panel_path_crosses(
                path, lead.own_body, 0.0):
            return _panel_refusal(
                template,
                f"{lead.cell.part_id}: the host lead would pass through the "
                f"cell's own body {lead.own_body} on its way to the from foot",
                "state a wider pitch or a different pose, or drop the branch",
            )
        if _panel_path_crosses(path, body, 0.0):
            return _panel_refusal(
                template,
                f"{lead.cell.part_id}: the host lead from {lead.cell.host_token} "
                "to the cell's from foot would cross the host's own body",
                "move the panel to another side (not implemented), or state a "
                "host whose panel-side pins are on that side",
            )
        for prior in routed.values():
            if _panel_leads_meet(path, prior):
                return _panel_refusal(
                    template,
                    f"{lead.cell.part_id}'s host lead touches another cell's lead "
                    "— two nets on one node or one collinear run is the short the "
                    "panel's own channels must not make",
                    "state fewer columns or a wider pitch, or drop a branch",
                )
        routed[lead.cell.part_id] = path
    seats = [
        replace(seat, host_path=routed[seat.part_id]) for seat in seats
    ]
    for cell in seats:
        for other in seats:
            if other.part_id == cell.part_id:
                continue
            if any(
                _panel_path_crosses(other.host_path, box, template.clearance)
                for box in cell.reserved
            ):
                return _panel_refusal(
                    template,
                    f"cell {other.part_id}'s host lead crosses cell "
                    f"{cell.part_id}'s reserved part/text/flag room",
                    "state fewer columns or a wider pitch, or drop a branch",
                )
    plan = BoundPanelSeatPlan(
        group_id=template.group_id, host_part=template.host_part,
        side=template.side, columns=template.columns, cells=tuple(seats),
        reserved_boxes=tuple(all_reserved),
        host_paths=tuple(cell.host_path for cell in seats),
        grid=template.grid, lattice=template.lattice,
    )
    return plan


def bind_panel_plans(
    request: PlacementInput,
    origins: Mapping[str, tuple[float, float]],
    poses: Mapping[str, SymbolPose],
) -> tuple[BoundPanelSeatPlan, ...]:
    """The one binder: every declared panel, solved against this answer."""
    return tuple(
        _bind_one_panel(request, template, origins, poses)
        for template in request.panel_templates
    )


def seat_panel_plans(
    plans: Sequence[BoundPanelSeatPlan],
    origins: dict[str, tuple[float, float]],
    poses: dict[str, SymbolPose],
) -> None:
    """Write every seated cell's origin and pose into the answer, in place."""
    for plan in plans:
        if not plan.seated:
            continue
        for cell in plan.cells:
            assert cell.origin is not None and cell.pose is not None
            origins[cell.part_id] = cell.origin
            poses[cell.part_id] = cell.pose


def panel_parts_of(plans: Sequence[BoundPanelSeatPlan]) -> frozenset[str]:
    """Every part the binder owns — never moved on its own by the search."""
    return frozenset(
        cell.part_id for plan in plans for cell in plan.cells
    )


def _panel_reservation_terms(
    request: PlacementInput, boxes: Mapping[str, Box],
    plans: Sequence[BoundPanelSeatPlan],
    kind: str = "panel",
) -> list[CostTerm]:
    """Hard: a panel that is not seated, and no foreign part in its room.

    A refused plan is a hard **cost**, not an absence: a plan the binder could not
    seat has no reserved boxes, so skipping it would price an illegal answer at
    exactly zero and let the search prefer "panel ignored" over "panel seated".
    Both states therefore report: a refusal one term (`panel-plan:<id>`, the
    refusal in the detail) and a seated plan one term per group
    (`panel-reserve:<id>`). A refusal that still carries its seats and reserved
    boxes (a foreign part standing in the room) is priced at ``1 + the intruded
    area``; a refusal with no seats at all is priced at ``1``. Both stay hard, so
    "not seated" is always worse than any seated answer while the search still
    gets the same continuous area gradient the seated reserve has.

    The reserve's value is the **intersected area** a foreign part shares with the
    group's reserved boxes, summed over every part and every box — not a count of
    parts. A count is binary: a sliver and a deep burial cost the same, so a search
    that prices it has no direction along which to leave the sliver. The area is
    the geometry the reservation is about, it is still hard for any positive value
    (and the consumers still refuse the answer), and zero means no intrusion at
    all — no weight, threshold, near limit or page box changes.
    """
    out: list[CostTerm] = []
    for plan in plans:
        if not plan.seated:
            # A refusal that still carries its seats (a foreign intrusion) is
            # priced by the intruded area as well: 1 + area keeps "not seated"
            # strictly worse than any seated answer while giving the search the
            # same continuous gradient the seated reserve has.
            intruded = 0.0
            if plan.reserved_boxes:
                owned = plan.owned_parts
                for part_id, box in boxes.items():
                    if part_id in owned:
                        continue
                    intruded += sum(
                        _boxes_overlap(box, reserve)
                        for reserve in plan.reserved_boxes)
            out.append(CostTerm(
                name=f"{kind}-plan:{plan.group_id}", value=1.0 + intruded,
                hard=True,
                detail=(
                    plan.refusal.render() if plan.refusal is not None else
                    f"{kind} {plan.group_id}: the binder returned no seat"
                ),
            ))
            continue
        owned = plan.owned_parts
        area = 0.0
        hits: list[str] = []
        for part_id in sorted(boxes):
            if part_id in owned:
                continue
            shared = sum(
                _boxes_overlap(boxes[part_id], reserve)
                for reserve in plan.reserved_boxes
            )
            if shared > 0.0:
                area += shared
                hits.append(part_id)
        out.append(CostTerm(
            name=f"{kind}-reserve:{plan.group_id}", value=area, hard=True,
            detail=(
                f"{kind} {plan.group_id}: "
                + (f"{', '.join(hits)} share {area:g} square units with the "
                   f"{kind}'s reserved part/text/flag room"
                   if hits else "no foreign part touches the reserved room")
            ),
        ))
    return out


# ------------------------------------------------------------------ entry


def place(request: PlacementInput) -> PlacementResult:
    """Place every part of one request. Deterministic in ``request.seed``.

    The stages are the five concepts in order: rank the parts from the relations
    (:func:`_ranks`), seed a constructive drawing along ``progress``
    (:func:`_seed`), search it (:func:`_anneal`) — from ``request.restarts``
    independent seeds, the best drawing winning — then report the cost list of
    where it ended up (:func:`evaluate`). A hard violation is **not** a reason to
    return nothing: the caller gets the best drawing the search found together
    with its own account of what is wrong with it, which is the opposite of the
    silent zero-candidate answer the compiler gives today.

    **The pin-tip repair is a second pass, not a term in the first one**
    (:attr:`PlacementInput.pin_clearance`). The search runs exactly as it always
    has with the term switched off, and only an answer that still puts two
    foreign tips too close is searched again with the term priced. That shape is
    deliberate, and it is the difference between fixing a bug and re-drawing every
    page: a first-pass search that *carried* the term would perturb answers that
    were never crowded, because annealing is a trajectory and a cost that is 0 at
    the optimum is still not 0 along the way. Measured: with the term in the first
    pass, `098` scene 08's refusal report moved (its own answer reads
    `pin-clearance` 0 either way — the search simply took a different path), and
    `tests/test_116_ordinal_consumption.py` holds that report to a published
    byte-for-byte baseline. Two passes keep every such baseline intact and still
    repair the drawing that needs it.
    """
    if not isinstance(request, PlacementInput):
        raise PlacementError(
            f"PlacementInput expected, got {type(request).__name__}"
        )
    ranks = _ranks(request.relations, request.part_ids())
    seed = _seed(request, ranks)
    #: Bound **once**, after the ordinary seed and before the first evaluation:
    #: the pitch is the seed's own pair distance, and every restart below receives
    #: this same tuple. Empty on a request that declares no arm, in which case
    #: none of the series code runs at all.
    plans = _bind_series_plans(request, seed) if request.series_templates else ()
    if plans:
        _seat_series_arms(plans, seed)
        _apply_series_yields(plans, seed)
        _repair_series_yields(request, plans, seed)
    #: 548D3X3C: the panels are bound **once** from the ordinary seed and seated
    #: into it, so the search starts from a page whose cells already sit on their
    #: grid. The move set never touches a cell (`panel_parts_of`); the host's own
    #: moves are handled **per candidate** inside the search below, which re-binds
    #: the whole panel from that candidate's host with this same binder before the
    #: candidate is evaluated. Empty on every request that declares none, so the
    #: historical seed, trajectory and answer are byte for byte what they were.
    panel_plans: tuple[BoundPanelSeatPlan, ...] = ()
    if request.panel_templates:
        panel_plans = bind_panel_plans(request, seed.origins, seed.poses)
        seat_panel_plans(panel_plans, seed.origins, seed.poses)
    #: The historical request: the same cost list, the same moves, the same
    #: answer. `pin_clearance` is the only thing switched off.
    plain = (
        replace(request, pin_clearance=False)
        if request.pin_clearance else request
    )
    service_plans: tuple[BoundPanelSeatPlan, ...] = ()
    if request.service_templates:
        service_plans = bind_service_plans(
            request, seed.origins, seed.poses, panel_plans)
        seat_service_plans(service_plans, seed.origins, seed.poses)
    energy, state, iterations, accepted, attempt = _best_of(
        plain, seed, plans, panel_plans, service_plans)
    if request.pin_clearance:
        short = _pin_clearance_term(request, _pins_of(request, state))
        if short.value > 0.0:
            # A second pass from the answer, with the term priced. It keeps the
            # relation costs as they are, so it cannot buy spacing by breaking a
            # promise — `_energy` still sums them at `W_RELATION`. The same bound
            # plans are handed over: a repair pass is not a second seat search.
            healed, more, taken = _anneal_with_seed(
                request, state, attempt, plans, panel_plans, service_plans)
            healed_energy = _energy(
                evaluate(request, healed, plans, panel_plans)
                if not service_plans else
                evaluate(request, healed, plans, panel_plans, service_plans))
            if healed_energy < energy - 1e-9:
                state, energy = healed, healed_energy
                iterations += more
                accepted += taken
            seed_note = (
                f" — the pin-tip repair pass ran: {short.value:g} units of foreign "
                f"tip shortfall on the first answer, "
                + (f"the second pass found one with none"
                   if _pin_clearance_term(request, _pins_of(request, state)).value
                   <= 0.0 else
                   f"{_pin_clearance_term(request, _pins_of(request, state)).value:g} "
                   "units left (the budget ran out before it could be cleared)")
            )
        else:
            seed_note = ""
    else:
        seed_note = ""
    #: The joint flag seats are bound against the **finished** answer: a corridor
    #: names pin-relative real seats, so the only thing it needs is where the pins
    #: ended up. Empty on every request that declares none, in which case no
    #: corridor code runs and the answer is the historical one. The yields the
    #: binder records are applied here — the same records, not a second pass —
    #: and the cost list below is measured on the drawing that actually stands.
    corridor_plans: tuple[BoundFlagCorridorPlan, ...] = ()
    if request.flag_corridors:
        corridor_plans = bind_flag_corridors(
            request, state.origins, state.poses,
        )
        corridor_plans, state = place_flag_corridors(
            request, corridor_plans, state.origins, state.poses,
        )
    #: 548D3X3C: the host may have moved during the search, so the panels are
    #: re-bound **once** against the finished answer with the same binder, and the
    #: cells are re-seated onto that plan. A foreign part that wandered into the
    #: reserve is then a refusal, not an overlap: the binder names it.
    if request.panel_templates:
        panel_plans = bind_panel_plans(request, state.origins, state.poses)
        seat_panel_plans(panel_plans, state.origins, state.poses)
    if request.service_templates:
        service_plans = bind_service_plans(
            request, state.origins, state.poses, panel_plans)
        seat_service_plans(service_plans, state.origins, state.poses)
    costs = (
        evaluate(request, state, plans, panel_plans)
        if not service_plans else
        evaluate(request, state, plans, panel_plans, service_plans)
    )
    result = PlacementResult(
        origins=dict(state.origins), poses=dict(state.poses), costs=costs,
        iterations=iterations, accepted=accepted, seed=attempt,
        series_plans=(
            _refresh_series_plans(request, plans, state) if plans else ()
        ),
        flag_corridors=corridor_plans,
        panel_plans=panel_plans,
        service_plans=service_plans,
    )
    result.notes.append(
        f"{PLACEMENT_NAME}: {len(request.parts)} part(s), "
        f"{len(request.relations)} relation(s), {request.restarts} restart(s), "
        f"{iterations} iteration(s) on the winning one, {accepted} accepted, "
        f"seed {attempt}" + seed_note
    )
    if panel_plans:
        seated = [item for item in panel_plans if item.seated]
        refused = [item for item in panel_plans if not item.seated]
        result.notes.append(
            f"{len(seated)} panel(s) bound against the answer"
            + (
                "; refused: " + ", ".join(item.group_id for item in refused)
                if refused else ""
            )
        )
    if plans:
        refused = [plan for plan in plans if not plan.seated]
        result.notes.append(
            f"{len(plans)} series arm(s) bound once from the ordinary seed"
            + (
                "; refused: " + ", ".join(plan.branch_id for plan in refused)
                if refused else ""
            )
        )
    if corridor_plans:
        refused = [plan for plan in corridor_plans if not plan.seated]
        result.notes.append(
            f"{len(corridor_plans)} flag corridor(s) bound against the answer"
            + (
                "; refused: " + ", ".join(plan.group_id for plan in refused)
                if refused else ""
            )
        )
    hard = result.hard
    if hard:
        result.notes.append(
            "the search could not remove every hard violation: "
            + "; ".join(item.render() for item in hard)
        )
    return result


def _best_of(
    request: PlacementInput,
    seed: _State,
    plans: Sequence[BoundSeriesSeatPlan] = (),
    panels: Sequence[BoundPanelSeatPlan] = (),
    services: Sequence[BoundPanelSeatPlan] = (),
) -> tuple[float, _State, int, int, int]:
    """Every restart searched, the best drawing kept — ``place``'s own search."""
    best: tuple[float, _State, int, int, int] | None = None
    for index in range(max(1, request.restarts)):
        attempt = request.seed + index
        state, iterations, accepted = _anneal_with_seed(
            request, seed, attempt, plans, panels, services)
        energy = _energy(
            evaluate(request, state, plans, panels)
            if not services else
            evaluate(request, state, plans, panels, services))
        if best is None or energy < best[0] - 1e-9:
            best = (energy, state, iterations, accepted, attempt)
    assert best is not None
    return best
