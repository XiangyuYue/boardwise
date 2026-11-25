"""`add-component`: placing the part a `decap-required-caps` finding is missing (029-a).

016 changed a string; this slice **creates** a part and connects it, so the
questions change shape: where does it land, what number does it get, how is it
joined to its net, and how does a second run know the work is already done. All
four are decided here, offline and pure, so they can be tested — and refused —
without an editor, a daemon or a socket.

Three rules the rest of the slice leans on:

* **The idempotence probe is the rule's own judgement** (§二.5). It is not
  re-implemented here: :func:`probe_already_applied` calls
  `core.decap.cap_candidates_on` (the rule's inventory of grounded capacitors
  on a net) and `core.decap.decide_required_cap` (the rule's comparison). A
  second, similar-looking judgement is exactly what the task book forbids, and
  "the two agreed last week" is not a property either of them can hold.
* **Determinism, never convenience.** The designator is the lowest free number
  for its prefix, the landing spot is a fixed ladder from the anchor, and the
  connection is decided by three named rules rather than by whichever call would
  succeed. Two runs of the same plan therefore produce the same numbers, and a
  reviewer can predict both before reading the code.
* **Refusals say what is missing.** An exhausted ladder names the positions it
  tried and what occupies them; a net that cannot be connected names all three
  options that were checked. No fallback to the origin, no unannounced label and
  no dangling named wire: every mechanism is a named outcome of
  `choose_connection` (a wire to that net's own segment, a flag on the pin for a
  rail, a label only where the page already names the net), never something apply
  slips in when a wire would not reach. The M2 rules ("don't connect by label and
  call it done", "don't quietly choose") are enforced by the shape of that
  decision, not by a comment.

Nothing here talks to the bridge: the geometry it reads is a `sch.geometry`
dump, which the CLI fetches.

It lives in `engines/` rather than `core/` for the layer rule's sake
(`tests/test_layer_rules.py`): it *uses* a rule's judgement (§二.5) and a plan's
types, and `core` is allowed to import nothing from inside the package.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..core.changeplan import resolve_on_page
from ..core.decap import CapDecision, CapCandidate, cap_candidates_on, decide_required_cap

#: The landing ladder's step, in canvas units. Deliberately the same 5-unit grid
#: `engines/layout.py` routes on (asserted in the tests): placing a part off the
#: grid would make every later wire either diagonal or off-grid, and this slice
#: inherits draw.py's wiring discipline rather than inventing one.
LANDING_GRID = 5.0

#: How far apart two component origins must be for the further one to count as
#: free space. One grid: a part whose origin sits *on* another part's cell is a
#: collision, and 5 units away is close enough to be suspicious.
LANDING_CLEARANCE = 5.0

#: The fixed ladder (§二.4), as grid offsets in the order the task book names:
#: the ideal spot, then up / down / left / right one grid, then the same at two
#: grids. Written down once, in one place, because "deterministic" is only true
#: if the order is data rather than a loop that someone later reorders.
LADDER: tuple[tuple[int, int], ...] = (
    (0, 0),
    (0, -1),
    (0, 1),
    (-1, 0),
    (1, 0),
    (0, -2),
    (0, 2),
    (-2, 0),
    (2, 0),
)

#: How close an existing piece of the target net must be to the landing spot for
#: a short wire to be an honest connection option, in canvas units. 100 units is
#: 1 inch at 0.01-inch schematic units — the distance at which a decoupling
#: capacitor stops being a decoupling capacitor, which is the same engineering
#: limit the facts shelf quotes ("within 0.5 inch of the pin").
CONNECT_RADIUS = 100.0

#: How far beyond everything it walls off a wire's search may go (112). The
#: lattice search has to be able to step *around* the last obstacle, so the
#: corridor cannot be the obstacles' own bounding box; four grids of room is
#: enough to turn a corner past any of them without wandering.
ROUTE_MARGIN = 20.0

_DESIGNATOR_RE = re.compile(r"^([A-Za-z]+)(\d+)$")

#: The only shape `allocate_designator` accepts for the *prefix*: the letters of a
#: designator, with the number left to the allocator. "C1" is not a prefix — it is
#: a whole designator that already has its number (570-D7).
_DESIGNATOR_PREFIX_RE = re.compile(r"^[A-Za-z]+$")


class LadderExhausted(Exception):
    """No position in the ladder is free.

    Carries what it tried and what got in the way: a refusal that cannot name
    the conflict is a refusal the operator cannot act on, and acting on it by
    hand is the whole point of the message.
    """

    def __init__(self, tried: Sequence[tuple[float, float]], occupied: Sequence[tuple[float, float]]):
        self.tried = list(tried)
        self.occupied = list(occupied)
        super().__init__(
            "every position in the landing ladder is occupied "
            f"({len(self.tried)} tried: "
            + ", ".join(f"({x:g}, {y:g})" for x, y in self.tried)
            + ")"
            + (
                "; nearest occupied: "
                + ", ".join(f"({x:g}, {y:g})" for x, y in self.occupied[:3])
                if self.occupied
                else ""
            )
        )


class LandingRefused(ValueError):
    """The ladder cannot even be walked: a coordinate or step is not finite.

    A landing spot is only meaningful on a finite canvas. ``nan``/``inf`` in an
    origin, a grid or a computed rung used to leave :func:`landing_spot` with a
    ``nan`` spot (or a bare ``OverflowError``), and the caller then planned a
    part at a place that does not exist. Refusing here names the reason instead:
    a value error, never a fallback and never a fabricated spot.
    """


class NoConnectionOption(Exception):
    """No nearby wire of that net, not a rail (so no flag), no label of it.

    All three checks are named in the message (029-d made the rail check the
    second one), because the operator's next move — which wire to draw, or which
    rail to name — depends on knowing which of them failed.
    """

    def __init__(self, net: str, detail: str):
        self.net = net
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class LandingSpot:
    """Where the part goes, and which rung of the ladder it took."""

    x: float
    y: float
    offset: tuple[int, int]
    index: int

    @property
    def stepped(self) -> bool:
        return self.index > 0


@dataclass(frozen=True)
class ConnectionChoice:
    """How the new part joins its net, and the evidence for that choice."""

    kind: str  # changeplan.CONNECTION_WIRE / CONNECTION_LABEL
    detail: str
    #: Where the wire ends, for a `wire` choice (a vertex of that net).
    to: tuple[float, float] | None = None


def _state_of(entry: Any) -> dict[str, Any]:
    state = (entry or {}).get("state") if isinstance(entry, dict) else None
    return state if isinstance(state, dict) else {}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _designator_name(state: dict[str, Any]) -> str:
    """The name a page part carries: ``Designator``, else ``OtherProperty.Designator``."""
    other = state.get("OtherProperty")
    return _text(state.get("Designator")) or _text(
        other.get("Designator") if isinstance(other, dict) else ""
    )


def component_origins(geometry: Any) -> dict[str, tuple[float, float]]:
    """``designator -> (x, y)`` for every component the page reports.

    Designators ending in ``?`` are skipped: that is the editor's own notation
    for a part that has not been numbered, and half-placed parts are not
    occupancy evidence ("the spot is free") nor designator evidence.
    """
    origins: dict[str, tuple[float, float]] = {}
    if not isinstance(geometry, dict):
        return origins
    for entry in geometry.get("components") or []:
        state = _state_of(entry)
        name = _designator_name(state)
        x, y = _number(state.get("X")), _number(state.get("Y"))
        if not name or name.endswith("?") or x is None or y is None:
            continue
        origins.setdefault(name, (x, y))
    return origins


def primitive_id_of(geometry: Any, designator: str) -> str:
    """The canvas id of one component, from a `sch.geometry` dump (029-c).

    Needed for the branch where the placement's outcome went unknown but the
    read-back shows the part anyway: the write's own answer carried no id, and
    the part's pins can only be read by id (`sch.component_pins`).

    *Which* part that is, is not decided here: `core.changeplan.resolve_on_page`
    is the same reader the connector applies (`Designator`, else
    `OtherProperty.Designator`, folded to case), and it counts the page parts
    that carry the name. A page with two ``R1``s is a state it can really be in,
    and the honest answer to "which id?" is none: the callers refuse on ``""``
    instead of acting on a part picked by position (570-D6). Non-finite/no
    match, two matches, and unreadable input all return ``""`` — this function
    introduces no exception of its own.

    `resolve_on_page` reads the *top-level* ``primitiveId``. A read-back can
    report the id on ``state.PrimitiveId`` instead (the channel 029 relied on),
    so after the ambiguity verdict the one matching entry is re-walked only for
    that fallback — never to override the verdict.
    """
    if not isinstance(geometry, dict) or not isinstance(designator, str):
        return ""
    lookup = resolve_on_page(geometry, designator)
    if lookup.component is None or lookup.ambiguous:
        return ""
    primitive = str(lookup.component.primitive_id or "")
    if primitive:
        return primitive
    wanted = designator.strip().upper()
    if not wanted:
        return ""
    for entry in geometry.get("components") or []:
        if not isinstance(entry, dict):
            continue
        state = _state_of(entry)
        if _designator_name(state).upper() != wanted:
            continue
        # `resolve_on_page` counted exactly one match; the id it could not read
        # is this entry's state-side id, if it has one.
        return str(state.get("PrimitiveId") or "")
    return ""


def pin_points(payload: Any) -> dict[str, tuple[float, float]]:
    """``pinNumber -> (x, y)`` from a `sch.component_pins` answer (029-c).

    This is the coordinate a wire has to *start* at. Measured on 3.2.186: a
    placed capacitor's pins sit **20 units either side of its origin**, so a wire
    drawn from the landing spot (which is the origin) touches neither — 029-b
    read `1→NET4 ok` off one export and 029-c re-measured the same page as the
    part sitting on its own auto net, which is what a wire that reaches nothing
    looks like. The pin's reported `X`/`Y` is the connection end (the outer end
    of the pin's own length), which is the point the editor joins wires to.
    """
    points: dict[str, tuple[float, float]] = {}
    if not isinstance(payload, dict):
        return points
    for item in payload.get("pins") or []:
        if not isinstance(item, dict):
            continue
        number = _text(item.get("PinNumber")) or _text(item.get("PinName"))
        x, y = _number(item.get("X")), _number(item.get("Y"))
        if number and x is not None and y is not None:
            points.setdefault(number, (x, y))
    return points


def power_flag_kind(net: str) -> str:
    """The net-flag kind a rail net gets (`'Ground'`/`'Power'`), or ``''``.

    A *rail* — ground or a supply — is the one thing that may be created where
    the page has nothing, because a flag is a real library component and the
    editor's own netlist carries it (measured 2026-09-24: placing
    ``kind=Ground, net=GND`` on a capacitor's pin moved that pin onto net GND in
    the exported netlist, twice in a row, with no wire anywhere).

    The judgement of "is this name a rail" is **not re-made here**: it is
    ``layout._net_kind``, the same function the draw flow names nets with (which
    itself defers ground to `core.model.is_ground_net`). A second regex beside
    this one is how ``VEE`` and the SGND/EGND spellings drifted apart before.
    """
    from .layout import _net_kind

    kind = _net_kind(net or "")
    return kind if kind in ("Ground", "Power") else ""


def netflag_count(geometry: Any) -> int:
    """How many net flags (ground/power symbols) the page reports.

    Counted from `sch.geometry`, where a flag is a component with
    ``ComponentType: "netflag"`` and an **empty Designator** — which is exactly
    why the designator-set range diff never sees it, and why 029-d's acceptance
    ("+1 part +1 flag") needs this second count.
    """
    if not isinstance(geometry, dict):
        return 0
    return sum(
        1
        for entry in geometry.get("components") or []
        if _text(_state_of(entry).get("ComponentType")) == "netflag"
    )


class ObstacleField:
    """What a wire must route around, as far as the page can actually say (112).

    Four lists, and each is *only* what the host measures — this type never
    invents geometry, because an invented obstacle is a wire refused for a body
    that is not on the page (坑 9: a `sch.geometry` snapshot carries no per-part
    extent, so ``boxes`` is empty unless a caller probed one).

    * ``boxes`` — solid extents, ``(x0, y0, x1, y1)``. A step cutting one is
      refused. **Empty by default**, which is the honest reading of a snapshot.
    * ``blocked`` — points a vertex of this wire may not land on: another net's
      pin tip, its flag anchor, its wire vertex. A vertex there *is* a
      connection in the editor's model, so it is a short.
    * ``edges`` — another net's runs. Their interiors may be crossed
      perpendicularly; they may never be run along or turned on, because that
      would put a vertex of this wire on the other, which does join.
    * ``own_vertices`` / ``own_edges`` — this net's own geometry, which is
      **legal**: the goal is a vertex of it, so treating that vertex as a wall
      would refuse the connection the wire exists to make. The two are what the
      router must *not* be handed as obstacles, so they are carried separately
      rather than being filtered out of the obstacle lists at the call site.
    """

    __slots__ = ("boxes", "blocked", "edges", "own_vertices", "own_edges")

    def __init__(
        self,
        *,
        boxes: Sequence[tuple[float, float, float, float]] = (),
        blocked: Iterable[tuple[float, float]] = (),
        edges: Iterable[tuple[float, float, float, float]] = (),
        own_vertices: Iterable[tuple[float, float]] = (),
        own_edges: Iterable[tuple[float, float, float, float]] = (),
    ) -> None:
        self.boxes: tuple[tuple[float, float, float, float], ...] = tuple(
            (float(b[0]), float(b[1]), float(b[2]), float(b[3])) for b in boxes
        )
        self.blocked: tuple[tuple[float, float], ...] = tuple(
            (float(p[0]), float(p[1])) for p in blocked
        )
        self.edges: tuple[tuple[float, float, float, float], ...] = tuple(
            (float(e[0]), float(e[1]), float(e[2]), float(e[3])) for e in edges
        )
        self.own_vertices: tuple[tuple[float, float], ...] = tuple(
            (float(p[0]), float(p[1])) for p in own_vertices
        )
        self.own_edges: tuple[tuple[float, float, float, float], ...] = tuple(
            (float(e[0]), float(e[1]), float(e[2]), float(e[3])) for e in own_edges
        )

    @property
    def empty(self) -> bool:
        """Nothing to avoid — the caller should take the old straight/L path.

        A field carrying no boxes, no blocked points and no foreign runs has
        nothing to say about this wire, and a search over an empty field would
        still bend for a reason no one can see. ``None`` and this are the same
        instruction, stated as data so no caller has to re-derive it.
        """
        return not (self.boxes or self.blocked or self.edges)

    def extents(self, *points: tuple[float, float]) -> tuple[float, float, float, float] | None:
        """The bounding box of everything this field walls off, or ``None``.

        ``points`` are the wire's own two ends, and they belong in the corridor:
        a search bounded by the *obstacles* alone refuses the very first step,
        because the anchor is normally outside the walls. A field with nothing in
        it and no points has no corridor to state.
        """
        here: list[tuple[float, float]] = list(self.blocked) + list(self.own_vertices)
        here += list(points)
        for edge in self.edges + self.own_edges:
            here.append((edge[0], edge[1]))
            here.append((edge[2], edge[3]))
        for box in self.boxes:
            here.append((box[0], box[1]))
            here.append((box[2], box[3]))
        if not here:
            return None
        xs = [p[0] for p in here]
        ys = [p[1] for p in here]
        return (min(xs), min(ys), max(xs), max(ys))


def avoid_from_geometry(geometry: Any, net: str) -> ObstacleField:
    """Read one net's obstacle field out of a ``sch.geometry`` snapshot (112).

    What the snapshot **does** carry, and is therefore read:

    * every component's origin — including an unnumbered one, which
      :func:`component_origins` skips for the landing ladder on purpose (a
      half-placed part is not *free space*, but it is still something a wire
      may not land on) — the only extent a component has here, so it is a
      **blocked point** (a wire may not end on it) and never a box;
    * every wire's vertices, split by net: another net's are walls, this net's
      are its own legal geometry;
    * every wire's runs, split the same way — another net's are edges the wire
      may cross but not run along.

    What it does **not** carry is a per-part body box, so ``boxes`` comes back
    empty. That is not a gap to paper over: a box invented from a designator
    would refuse a wire for a body nobody measured. Callers that *do* have body
    boxes (the compiler, from the symbol profile) pass them in themselves.

    ``net=''`` — the unjudged spelling, kept for the diagnostics that ask
    "what would the field look like" without owning a net — treats every wire on
    the page as foreign.
    """
    field_own_vertices: list[tuple[float, float]] = []
    field_own_edges: list[tuple[float, float, float, float]] = []
    field_blocked: list[tuple[float, float]] = []
    field_edges: list[tuple[float, float, float, float]] = []
    for point in component_origins(geometry).values():
        field_blocked.append(point)
    for entry in (geometry or {}).get("wires") or []:
        state = _state_of(entry)
        net_name = _text(state.get("Net"))
        line = state.get("Line") or state.get("Points") or state.get("points") or []
        points: list[tuple[float, float]] = []
        if isinstance(line, (list, tuple)) and line and not isinstance(line[0], (list, tuple)):
            coords = list(line)
            for index in range(0, len(coords) - 1, 2):
                x, y = _number(coords[index]), _number(coords[index + 1])
                if x is not None and y is not None:
                    points.append((x, y))
        else:
            for pair in line:
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    x, y = _number(pair[0]), _number(pair[1])
                    if x is not None and y is not None:
                        points.append((x, y))
        mine = bool(net) and net_name == net
        for point in points:
            (field_own_vertices if mine else field_blocked).append(point)
        for start, end in zip(points, points[1:]):
            if start == end:
                continue
            (field_own_edges if mine else field_edges).append(
                (start[0], start[1], end[0], end[1])
            )
    return ObstacleField(
        blocked=field_blocked,
        edges=field_edges,
        own_vertices=field_own_vertices,
        own_edges=field_own_edges,
    )


def route_orthogonal(
    anchor: tuple[float, float],
    target: tuple[float, float],
    field: ObstacleField,
    *,
    grid: float = LANDING_GRID,
    bounds: tuple[float, float, float, float] | None = None,
) -> list[tuple[float, float]] | None:
    """The cheapest orthogonal path around ``field``, or ``None``.

    A thin wrapper over :class:`boardwise.engines.router.Router` — the same
    search, the same walls, the same costs the drawing compiler routes on, so
    the interactive flows cannot draw something the checker would refuse.

    Two lattice facts, spelled out because they are where a diagonal would sneak
    back in (029-c: a diagonal `sch.place_wire` hangs the host, measured 2/2):

    * the lattice's residue is taken from ``anchor``, so the **first** point of
      the path is the anchor itself and the wire leaves the pin on-grid;
    * ``target`` need not be on the lattice — a pin is wherever the editor put
      it. The search therefore aims at the nearest lattice node to the target
      and joins the target as a final leg. Of the two legs that final join
      needs, one is always a straight run and the other a single bend, so every
      emitted segment is axis-aligned; the corner goes at ``(node.x, target.y)``,
      which is the old L's rule (the run *into* the pin is the one along it).
      A target that is already a lattice point gets no extra points at all.
    """
    from . import router

    ax, ay = float(anchor[0]), float(anchor[1])
    tx, ty = float(target[0]), float(target[1])
    if field.empty:
        if ax == tx or ay == ty:
            return [(ax, ay), (tx, ty)]
        return [(ax, ay), (ax, ty), (tx, ty)]
    corridor = bounds if bounds is not None else field.extents((ax, ay), (tx, ty))
    if corridor is None:
        return None
    if bounds is not None:
        search_box = bounds
    else:
        search_box = (
            corridor[0] - ROUTE_MARGIN, corridor[1] - ROUTE_MARGIN,
            corridor[2] + ROUTE_MARGIN, corridor[3] + ROUTE_MARGIN,
        )
    residue = (ax % grid, ay % grid)
    lattice = router.Router(
        grid=grid, residue=residue, boxes=field.boxes, bounds=search_box,
    )
    for point in field.blocked:
        lattice.blocked.add((round(point[0], 6), round(point[1], 6)))
    for edge in field.edges:
        lattice.add_edge((edge[0], edge[1]), (edge[2], edge[3]))
    # The search's goal is the lattice node nearest the target. `Router.route`
    # ends the walk as soon as it pops a goal node, and a node inside a wall
    # (the target vertex of a net whose own geometry is excluded from `blocked`
    # can still sit on a foreign body) is never reached as a step, so the
    # nearest *free* node along one of the two axes is taken when the exact one
    # is a wall. A target already on the lattice is its own node, unchanged.
    goal = _goal_node(lattice, target)
    if goal is None:
        return None
    goal_point = lattice.point(goal)
    path = lattice.route(anchor, goal_point, targets=[goal_point])
    if path is None:
        return None
    tail_point = (round(float(path[-1][0]), 6), round(float(path[-1][1]), 6))
    return _as_bends([tuple(point) for point in path], (tx, ty), tail_point)


def _as_bends(
    path: Sequence[tuple[float, float]],
    target: tuple[float, float],
    tail: tuple[float, float],
) -> list[tuple[float, float]]:
    """The lattice path as a wire: straight runs collapsed, then the target.

    The final leg into a target that is not on the lattice is appended **before**
    the collapse, so the run leading to the pin and the run leaving the last
    lattice node are each judged on their own. Exactly one of the two extra legs
    is a straight run and the other is a single bend, so every emitted segment
    stays axis-aligned; the corner is placed on the target's own x, which is the
    old path's rule (the run into the pin is the one along it).

    The collapse itself is **the compiler's own** :func:`drawcompiler._compress`,
    called here rather than restated: a wire's vertices must be its bends for the
    same reason on both paths (the readability checker reads a vertex inside
    another wire's span as a tee that needs a junction, while a proper crossing
    is not a connection at all), and two copies of that rule would eventually
    disagree. The import is function-local so this module keeps no load-time edge
    on the whole compiler.
    """
    from .drawcompiler import _compress

    points = [tuple(point) for point in path]
    if tail != target:
        if abs(tail[0] - target[0]) > 1e-6 and abs(tail[1] - target[1]) > 1e-6:
            points.append((tail[0], target[1]))
        points.append(target)
    return _compress(points)


def _goal_node(lattice: Any, target: tuple[float, float]) -> tuple[int, int] | None:
    """The lattice node the search aims at, or ``None`` if the target is walled in.

    The target's own node first, then the nearest free node along each axis, in
    increasing distance — a target that happens to sit inside a body must not
    make the whole wire unroutable, but it must not be routed *through* it
    either, so the fallback is a node the search may legally stand on.
    """
    exact = lattice.node(target)
    if not lattice._wall(exact) and lattice._in_bounds(exact):
        return exact
    steps = (1, -1, 2, -2, 3, -3, 4, -4)
    for distance in steps:
        for dx, dy in ((distance, 0), (0, distance)):
            candidate = (exact[0] + dx, exact[1] + dy)
            if lattice._in_bounds(candidate) and not lattice._wall(candidate):
                return candidate
    return None


def wire_route(
    anchor: tuple[float, float],
    target: tuple[float, float],
    *,
    avoid: ObstacleField | None = None,
    grid: float = LANDING_GRID,
    bounds: tuple[float, float, float, float] | None = None,
) -> list[tuple[float, float]] | None:
    """The polyline from a pin to its target, **orthogonal** by construction (029-c).

    Measured on 3.2.186: `sch.place_wire` with a diagonal segment never returns —
    the call hangs until the daemon's 30 s timeout, twice out of twice, while the
    same call with an axis-aligned segment answers in ~0.4 s. The corner goes at
    ``(anchor.x, target.y)``: the first run leaves the pin along the axis it points
    at, which keeps it clear of the neighbouring pin (a run along the pin row would
    cross the part's own body). Same discipline `engines/layout.py` routes on.

    **112: the L is now the fallback, not the method.** With ``avoid`` the wire is
    routed around what the page says is in the way, on the same lattice search the
    drawing compiler uses (:func:`route_orthogonal`). Three outcomes, and the
    third is the point of the batch:

    * ``avoid=None``, or a field with nothing in it → **exactly** the straight/L
      polyline this function has always returned, byte for byte;
    * a path is found → the searched route, orthogonal, cleared of every box,
      blocked point and foreign run in the field;
    * no path is found → ``None``. The caller reports 「无净通路」 and exits the
      way that flow already reports a failure. It does **not** fall back to the
      L: a wire pressed through a part body is a drawing that looks connected
      and is not, which is a worse lie than a connection that was not drawn.
    """
    if avoid is None or avoid.empty:
        ax, ay = float(anchor[0]), float(anchor[1])
        tx, ty = float(target[0]), float(target[1])
        if ax == tx or ay == ty:
            return [(ax, ay), (tx, ty)]
        return [(ax, ay), (ax, ty), (tx, ty)]
    return route_orthogonal(anchor, target, avoid, grid=grid, bounds=bounds)


#: The longest step between two occupancy samples on a wire, in canvas units.
#: Half the clearance: a candidate closer to a segment than the clearance then
#: always has a sample inside its own exclusion box, so "free" cannot mean "on
#: copper in the middle of a long wire" (570-D2).
_SAMPLE_STEP = LANDING_CLEARANCE / 2.0

#: Safety bound on one segment's sampling: a corrupt (but finite) coordinate far
#: outside any sheet must not turn into millions of points. Real wires are
#: thousands of units at most, where the step stays `_SAMPLE_STEP`.
_MAX_SAMPLES_PER_SEGMENT = 20_000


def _is_finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _finite_pair(point: Any) -> bool:
    return (
        isinstance(point, (tuple, list))
        and len(point) >= 2
        and _is_finite(point[0])
        and _is_finite(point[1])
    )


def _wire_segments(
    geometry: Any, net: str = ""
) -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
    """``(net, start, end)`` for every consecutive pair of a wire's points.

    The host reports one wire as a **point list** (``state.Line``), and a wire
    touching another is merged into a primitive that carries several runs — the
    same shape :func:`boardwise.engines.patchpin.wire_segments` reads. Reading
    pairs here (rather than only vertices, as 029 did) is what makes a
    mid-segment T visible at all. Non-finite coordinates are dropped: a segment
    the page cannot place is not evidence of copper anywhere.
    """
    from .patchpin import wire_segments as patchpin_wire_segments

    found: list[tuple[str, tuple[float, float], tuple[float, float]]] = []
    for wire in patchpin_wire_segments(geometry):
        if net and wire.net != net:
            continue
        for start, end in zip(wire.points, wire.points[1:]):
            if not (_finite_pair(start) and _finite_pair(end)):
                continue
            found.append((wire.net, (start[0], start[1]), (end[0], end[1])))
    return found


def _project_on_segment(
    spot: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float, float]:
    """The point of the segment closest to ``spot``, and its distance.

    t is clamped to ``[0, 1]`` (the projection of a spot beside the segment is
    its nearer end, not a point on the infinite line), and a zero-length segment
    degenerates to its own point — the two cases a vertex-only reading used to
    get right by accident.
    """
    dx, dy = end[0] - start[0], end[1] - start[1]
    span = dx * dx + dy * dy
    if span == 0.0:
        x, y = start
    elif not math.isfinite(span):
        # Coordinates so large their square overflows: the ends are the only
        # answers that stay finite, and one of them is the nearest of the two.
        x, y = min((start, end), key=lambda p: math.hypot(p[0] - spot[0], p[1] - spot[1]))
    else:
        t = ((spot[0] - start[0]) * dx + (spot[1] - start[1]) * dy) / span
        t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
        x, y = start[0] + t * dx, start[1] + t * dy
    return x, y, math.hypot(x - spot[0], y - spot[1])


def _segment_samples(
    start: tuple[float, float], end: tuple[float, float]
) -> list[tuple[float, float]]:
    """Points along the segment at most :data:`_SAMPLE_STEP` apart, ends included."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0.0:
        return [(start[0], start[1])]
    step = max(_SAMPLE_STEP, length / _MAX_SAMPLES_PER_SEGMENT)
    count = int(math.ceil(length / step))
    return [
        (start[0] + dx * index / count, start[1] + dy * index / count)
        for index in range(count + 1)
    ]


def occupied_points(geometry: Any) -> list[tuple[float, float]]:
    """Every occupied page point a landing spot must not collide with.

    Component origins *and* copper: a spot sitting on a wire is not free
    either — the part would land on top of the routing and the wire would look
    like it connected something it does not touch. A wire's **whole run** is
    occupied, not just its reported vertices: a 200-unit wire's midpoint is
    copper too, and reading only its ends let a decoupling capacitor land on it
    (570-D2). Samples are deterministic and at most ``LANDING_CLEARANCE / 2``
    apart; the returned shape is still the ``list[(x, y)]`` every caller walks.
    A coordinate the page reports as ``nan``/``inf`` is dropped rather than
    carried into the list: :func:`is_free` refuses such an occupant outright
    (570-D3), and one corrupt point must not make every rung look taken.
    """
    points: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()

    def add(x: float, y: float) -> None:
        point = (x, y)
        if point not in seen:
            seen.add(point)
            points.append(point)

    for x, y in component_origins(geometry).values():
        if _is_finite(x) and _is_finite(y):
            add(x, y)
    for x, y, _net in wire_vertices(geometry):
        if _is_finite(x) and _is_finite(y):
            add(x, y)
    for _net, start, end in _wire_segments(geometry):
        for x, y in _segment_samples(start, end):
            add(x, y)
    return points


def is_free(x: float, y: float, occupied: Iterable[tuple[float, float]]) -> bool:
    """Is ``(x, y)`` clear of every occupied point by :data:`LANDING_CLEARANCE`?

    A non-finite candidate is never free — it is not a place on the page — and a
    non-finite occupant refuses rather than answering "free" for everything or
    pretending the whole ladder is full (570-D3): occupancy we cannot read is
    not evidence that the spot is safe.
    """
    if not (_is_finite(x) and _is_finite(y)):
        return False
    for ox, oy in occupied:
        if not (_is_finite(ox) and _is_finite(oy)):
            return False
        if abs(x - ox) < LANDING_CLEARANCE and abs(y - oy) < LANDING_CLEARANCE:
            return False
    return True


def landing_spot(
    origin: tuple[float, float],
    occupied: Sequence[tuple[float, float]],
    ladder: Sequence[tuple[int, int]] = LADDER,
    grid: float = LANDING_GRID,
) -> LandingSpot:
    """The first free rung of the fixed ladder from ``origin``.

    Raises :class:`LadderExhausted` when none is free — **never** falls back to
    the page origin: a decoupling capacitor dropped at (0, 0) is not a repaired
    board, it is a part in the corner, and the far end of that mistake is a
    design that looks fixed and is not (xianyuyijinban M2 red line, §二.4).

    Raises :class:`LandingRefused` (a ``ValueError``) when the ladder cannot be
    walked at all: a non-finite origin or grid, a non-positive grid, or a rung
    that overflows to infinity. Returning a ``nan`` spot or letting the bare
    arithmetic error escape would both leave the caller planning a part at a
    coordinate that does not exist (570-D3).
    """
    if not (_is_finite(origin[0]) and _is_finite(origin[1])):
        raise LandingRefused(
            f"landing origin ({origin[0]!r}, {origin[1]!r}) is not finite — "
            "a part cannot be placed at a coordinate the page does not hold"
        )
    if not _is_finite(grid) or grid <= 0:
        raise LandingRefused(
            f"landing grid {grid!r} must be a positive finite step — "
            "the ladder would not advance"
        )
    tried: list[tuple[float, float]] = []
    for index, (dx, dy) in enumerate(ladder):
        x, y = origin[0] + dx * grid, origin[1] + dy * grid
        if not (_is_finite(x) and _is_finite(y)):
            raise LandingRefused(
                f"ladder rung {index} at offset ({dx}, {dy}) leaves the finite "
                f"canvas: ({x!r}, {y!r}) — refusing instead of planning at infinity"
            )
        tried.append((x, y))
        if is_free(x, y, occupied):
            return LandingSpot(x=x, y=y, offset=(dx, dy), index=index)
    raise LadderExhausted(tried, occupied)


def designator_pool(geometry: Any, model: Any = None) -> list[str]:
    """Every designator a plan must avoid: the page's **and the project's** (036b).

    ``allocate_designator`` picks the lowest free number from the names it is
    given, so what counts as "used" is whatever this pool holds. The page alone is
    not enough, and that is measured rather than assumed: on 2026-09-25 the host
    honoured a requested ``R2`` only when nothing **in the project** already had it
    — asking for R2 on a page with no R2 produced ``R3``, because another page
    carried an R2 — and it made the rename **mid-run**, so the plan's own
    postconditions ("R2 is on the page at …") stopped holding and the run reported
    `verification_disagrees` for a circuit that was electrically right.

    ``model`` is the project export the caller already reads (029's snapshot,
    036's live export); ``None`` degrades to the page alone, which the caller is
    expected to *say* rather than leave implicit.
    """
    names = list(component_origins(geometry))
    # 040b's multi-board façade: ``ProjectModel.components`` **raises** on a
    # project with more than one board (first-board-wins is the silent loss that
    # batch removed), and a `getattr(..., None)` does not catch it because the
    # property raises a ValueError, not AttributeError. A draw plan on a
    # two-board project therefore died with a traceback before this branch —
    # measured on a live Board1+Board2 project (515C). ``designators()`` is the
    # board-aware read that answers for every board, which is also the more
    # conservative pool: a number used anywhere in the project is avoided.
    board_aware = getattr(model, "designators", None)
    if callable(board_aware):
        project_names = board_aware()
    elif model is not None:
        project_names = getattr(model, "components", None) or {}
    else:
        project_names = ()
    for designator in project_names:
        if str(designator) not in names:
            names.append(str(designator))
    return names


def allocate_designator(names: Iterable[str], prefix: str) -> str:
    """The lowest free ``<prefix><n>`` (n >= 1) among ``names`` (§二.3).

    The pool is what the page shows, so the number is reproducible from the
    page alone; apply re-checks it before writing, because a human may have
    placed a part in between.

    ``prefix`` is the **letters** of a designator; the number is this function's
    to choose. A prefix that already carries a number (``"C1"``) used to be
    compared, digits and all, against the pool entry's letters (``"C"``), which
    never matched — so ``allocate_designator(["C11"], "C1")`` returned ``C11``,
    a name the page already had (570-D7). Such an input is refused by name
    rather than reinterpreted as "C from 1". The returned name is additionally
    checked against the whole (case-folded) pool, so a caller cannot be handed
    a spelling the page already carries either way.
    """
    if not isinstance(prefix, str) or not _DESIGNATOR_PREFIX_RE.match(prefix):
        raise ValueError(
            f"cannot allocate a designator for prefix {prefix!r}: the prefix of "
            "<prefix><n> must be letters only (e.g. 'C', 'R', 'TP') — the number is "
            "chosen by the allocator, so a prefix that already has one would produce "
            "a name the page may already carry"
        )
    wanted = prefix.upper()
    folded = {name.strip().casefold() for name in names if isinstance(name, str)}
    used: set[int] = set()
    for name in folded:
        match = _DESIGNATOR_RE.match(name)
        if not match:
            continue
        if match.group(1).upper() != wanted:
            continue
        used.add(int(match.group(2)))
    number = 1
    while number in used or f"{prefix}{number}".casefold() in folded:
        number += 1
    return f"{prefix}{number}"


def net_label_names(geometry: Any) -> set[str]:
    """The net names this page already carries as labels (case-sensitive as written)."""
    names: set[str] = set()
    if not isinstance(geometry, dict):
        return names
    for entry in geometry.get("netlabels") or []:
        state = _state_of(entry)
        name = _text(state.get("Net")) or _text(state.get("Text")) or _text(
            state.get("Name")
        )
        if name:
            names.add(name)
        label = state.get("Label")
        if isinstance(label, dict):
            inner = _text(label.get("Net")) or _text(label.get("Text"))
            if inner:
                names.add(inner)
    return names


def wire_vertices(geometry: Any) -> list[tuple[float, float, str]]:
    """``(x, y, net)`` for every wire vertex, in the shape the host actually sends.

    Measured on 3.2.186 (029-b, 2026-09-23): a wire's state is
    ``{PrimitiveType: "Wire", Line: [x1, y1, x2, y2, …], Net: "NET4", …}`` — a
    **flat** coordinate list, and the net **is** carried by the wire. The earlier
    reading (``state.Points``, "wires carry no net") was wrong, and it made both
    the occupancy test and the wire option blind: a page with a wire in hand
    looked wire-less. Reading the real shape here is what lets the connection
    choice demand the *right* net instead of settling for the nearest one.
    """
    found: list[tuple[float, float, str]] = []
    if not isinstance(geometry, dict):
        return found
    for entry in geometry.get("wires") or []:
        state = _state_of(entry)
        net = _text(state.get("Net"))
        line = state.get("Line") or state.get("Points") or state.get("points") or []
        if isinstance(line, (list, tuple)) and line and not isinstance(line[0], (list, tuple)):
            coords = list(line)
            for index in range(0, len(coords) - 1, 2):
                x, y = _number(coords[index]), _number(coords[index + 1])
                if x is not None and y is not None:
                    found.append((x, y, net))
        else:
            for pair in line:
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    x, y = _number(pair[0]), _number(pair[1])
                    if x is not None and y is not None:
                        found.append((x, y, net))
    return found


def nearest_wire_point(
    spot: tuple[float, float], geometry: Any, net: str = ""
) -> tuple[float, float, float] | None:
    """The closest point **of ``net``'s own wiring** to ``spot``, or ``None``.

    ``net`` is required by every real caller: a wire of another net is not a
    connection option, it is the mistake this function used to be able to make
    (029 §六 verdict 3). Passing an empty ``net`` keeps the old, unjudged
    behaviour for diagnostics, and no flow uses it.

    The wire is measured as **segments**, not vertices (570-D1): a 200-unit wire
    drawn through the spot is 0 units away, and answering with its far end (200
    units) refused a connection the page can actually make. The answer is the
    projection on the nearest run, clamped to its ends; a non-finite spot or a
    segment the page cannot place yields ``None`` rather than a NaN distance.
    """
    if not (_is_finite(spot[0]) and _is_finite(spot[1])):
        return None
    best: tuple[float, float, float] | None = None
    for _segment_net, start, end in _wire_segments(geometry, net):
        x, y, distance = _project_on_segment(spot, start, end)
        if not math.isfinite(distance):
            continue
        if best is None or distance < best[2]:
            best = (x, y, distance)
    return best


def choose_connection(net: str, spot: tuple[float, float], geometry: Any):
    """How **one** declared connection is made (029-c §①, 029-d §①), or a refusal.

    Four outcomes, in the order the task books fix:

    1. **wire** — a vertex of *that net's own* wiring is within
       :data:`CONNECT_RADIUS`. Short loop, no name to invent.
    2. **power-flag** — the net is a rail (ground or a supply, decided by
       :func:`power_flag_kind`) and the page has no geometry of it to reach: the
       flag is placed **on the part's own pin**, which is the one way to create a
       rail connection where the page has none that the editor's netlist actually
       carries. A dangling wire named after the rail is *not* an option (029-d
       forbids it by name): copper that reaches nothing is not a connection.
    3. **label** — the page already names that net with a label, so the connection
       copies a convention instead of inventing one. (Not for rails: a rail gets
       the flag, and the host's net-label API is measured unusable anyway — 029-c.)
    4. neither → :class:`NoConnectionOption`, naming all three checks.
    """
    from ..core.changeplan import CONNECTION_LABEL, CONNECTION_POWER_FLAG, CONNECTION_WIRE

    near = nearest_wire_point(spot, geometry, net)
    if near is not None and near[2] <= CONNECT_RADIUS:
        return ConnectionChoice(
            kind=CONNECTION_WIRE,
            detail=(
                f"a short wire to the existing {net!r} segment at ({near[0]:g}, {near[1]:g}), "
                f"{near[2]:.0f} units away (limit {CONNECT_RADIUS:g})"
            ),
            to=(near[0], near[1]),
        )
    flag = power_flag_kind(net)
    if flag:
        return ConnectionChoice(
            kind=CONNECTION_POWER_FLAG,
            detail=(
                f"a {flag} flag named {net!r} placed on the part's own pin: the page has "
                f"no {net!r} geometry within {CONNECT_RADIUS:g} units to reach, and a flag "
                "is a library component the editor's netlist carries (029-d, measured)"
            ),
        )
    labels = net_label_names(geometry)
    if net in labels:
        return ConnectionChoice(
            kind=CONNECTION_LABEL,
            detail=(
                f"a label named {net!r}, the way this page already names that net "
                f"({len(labels)} label name(s) on the page)"
            ),
        )
    raise NoConnectionOption(
        net,
        f"net {net!r} cannot be connected at ({spot[0]:g}, {spot[1]:g}): no wire "
        f"point within {CONNECT_RADIUS:g} units "
        + (
            f"(nearest is {near[2]:.0f} units away at ({near[0]:g}, {near[1]:g}))"
            if near is not None
            else "(the page has no wire points at all)"
        )
        + f", this page uses no label named {net!r}, and the net is not a rail "
        f"(a ground or supply name, which would have allowed a flag) — 三种连接手段"
        "都不成立，拒绝建 plan（不用悬空名线、也不用全脚标签假装连通）",
    )


def choose_connections(
    pairs: Sequence[tuple[str, str]], spot: tuple[float, float], geometry: Any
) -> list[Any]:
    """One :class:`~boardwise.core.changeplan.PlanConnection` per declared pin.

    Every declared connection decides for itself, and a refusal on any of them
    refuses the whole plan: a part placed with three of its four pins connected
    is exactly the half-done state 029-b's case a produced, and it is worse than
    no plan because it looks finished.
    """
    from ..core.changeplan import PlanConnection

    chosen = []
    for pin, net in pairs:
        choice = choose_connection(net, spot, geometry)
        chosen.append(
            PlanConnection(
                pin=pin, net=net, kind=choice.kind, detail=choice.detail,
                to=getattr(choice, "to", None),
            )
        )
    return chosen


def probe_already_applied(
    model: Any,
    net_name: str,
    recipe: str,
    library: Any = None,
) -> CapDecision:
    """Is this decoupling requirement already satisfied on the live board?

    **The rule's own two functions**, called on a model parsed from the live
    project export: :func:`cap_candidates_on` for the inventory (which
    capacitors sit on this net, grounded) and :func:`decide_required_cap` for
    the comparison. §二.5 asks for exactly this and forbids the alternative; a
    probe that re-derived the answer from geometry would be a second judgement
    that agrees until the day it does not.
    """
    return decide_required_cap(
        recipe, cap_candidates_on(model, net_name, library), library
    )


@dataclass(frozen=True)
class RangeDiff:
    """What the page gained between two reads — the acceptance's `+1 +k` (§一)."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    unchanged: int
    expected_added: str

    @property
    def ok(self) -> bool:
        return self.added == (self.expected_added,) and not self.removed

    def describe(self) -> str:
        bits = [
            f"added {list(self.added) or 'nothing'}",
            f"removed {list(self.removed) or 'nothing'}",
            f"unchanged {self.unchanged}",
        ]
        return ", ".join(bits)


def range_diff(before: Iterable[str], after: Iterable[str], expected_added: str) -> RangeDiff:
    """Compare two designator sets, so "exactly one part appeared" is a reading.

    The obligation is deliberately set-theoretic and narrow: the plan promises
    *one* new part, so anything else — a part that vanished, a designator that
    moved, two parts appearing because a previous run was half-done — is an
    accident report rather than a success (029 §一: a difference that is not
    exactly +1 is an accident even when the board looks better).
    """
    before_set, after_set = set(before), set(after)
    return RangeDiff(
        added=tuple(sorted(after_set - before_set)),
        removed=tuple(sorted(before_set - after_set)),
        unchanged=len(before_set & after_set),
        expected_added=expected_added,
    )
