"""Rigid frames packed into one page rectangle (548D3X §30B).

This module answers one geometric question and nothing else: given a page box, a
set of module frames (each a rigid rectangle with a caller-chosen priority
order), a clear-space ``gap``, a lattice ``grid`` and optional keep-out boxes,
where does each frame go?  It never looks at a circuit, a net, a module name, a
reference drawing or a coordinate table: the caller hands over the local frames
it already compiled, and gets back the translation the page compiler would
apply.  It deliberately does **not** import ``drawcompiler``, ``placement`` or
``pagecompiler``, and it has no notion of islands, ports or electrical meaning.

The contract, stated because every clause is a place where a caller could
otherwise be surprised:

* **y grows upwards.**  A box is ``(x0, y0, x1, y1)`` in absolute canvas units,
  with ``x1 > x0`` and ``y1 > y0``.  The same shape as
  :data:`boardwise.core.symbolprofile.Box`.
* **Frames are rigid.**  Width and height are preserved exactly; nothing is
  rotated, scaled or re-ordered.  The returned ``origin`` is the translation
  applied to the *given* local frame, so ``final = local + (ox, oy)`` component
  by component.
* **``order`` is a priority sequence, not coordinates.**  Frames are placed in
  that order; a caller that wants to express a position must express it as a
  reading priority, and the packer decides the coordinates.
* **``gap`` is the page compiler's own measure.**  The edge-to-edge distance is
  ``hypot(dx, dy)`` with each axis clamped at zero, exactly
  ``pagecompiler._frame_gap`` and ``readability._box_gap``.  A pair is accepted
  only when that distance is ``> gap - 1e-6``; 40.0 is legal at ``gap=40`` and
  39.x is not.
* **The lattice never narrows a gap.**  Only the frame's lower-left corner is
  snapped, upwards to the next absolute multiple of ``grid`` (measured on the
  page's own axes); the snapped position is then checked against the page,
  every keep-out and every placed frame again, so snapping can move a frame
  away from a neighbour but never closer than ``gap``.
* **Keep-outs are absolute page boxes.**  A frame's interior may not intersect a
  keep-out's interior; sharing an edge is legal.  A keep-out's own edges are
  offered as candidate positions, which is what lets a frame sit beside one.
* **The answer is exhaustive or truncated, never `best effort`.**  The search
  is a bounded depth-first backtrack over a finite corner-candidate space
  (page origin, the right/top edges of placed frames plus ``gap``, keep-out
  edges).  Exhausting that space reports ``unsat``; hitting ``max_nodes``
  reports ``truncated`` with a different code.  A packing that is not found is
  never returned as overlapping frames.

The candidate space is a corner construction, not a proof over the continuum:
``unsat`` means "no packing in this module's discrete space", and the docstring
of :func:`pack_frames` says so.  It is deliberately *not* a shelf: candidate
``x`` values come from one frame and candidate ``y`` values from another, so a
short frame may fill the space under a tall neighbour instead of inheriting its
row height.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

Box = tuple[float, float, float, float]

#: The page compiler's `PAGE_MODULE_GAP`; the caller may pass its own budget gap.
DEFAULT_GAP = 40.0
#: The compilation lattice; 0 disables snapping.
DEFAULT_GRID = 5.0
#: Candidate placements one call may test before it reports truncation.
DEFAULT_MAX_NODES = 20000

#: ``gap`` is compared with the same tolerance the page compiler uses, so this
#: module and the checker cannot disagree about a pair that is exactly at 40.
GAP_EPSILON = 1e-6

STATUS_PACKED = "packed"
STATUS_UNSAT = "unsat"
STATUS_TRUNCATED = "truncated"
STATUS_REJECTED = "rejected"

FAILURE_INVALID_ARGUMENT = "invalid-argument"
FAILURE_INVALID_PAGE = "invalid-page"
FAILURE_INVALID_KEEPOUT = "invalid-keepout"
FAILURE_INVALID_FRAME = "invalid-frame"
FAILURE_INVALID_ORDER = "invalid-order"
FAILURE_UNKNOWN_ORDER = "unknown-order"
FAILURE_DUPLICATE_ORDER = "duplicate-order"
FAILURE_MISSING_ORDER = "missing-order"
FAILURE_TOO_MANY_FRAMES = "too-many-frames"
FAILURE_UNSAT = "unsat"
FAILURE_BUDGET_EXHAUSTED = "budget-exhausted"

#: A structural guard against unbounded recursion; frames per page are tiny.
MAX_FRAMES = 256

_PAGE_EPSILON = 1e-9
_OVERLAP_EPSILON = 1e-9
_SNAP_EPSILON = 1e-9


@dataclass(frozen=True)
class PackingFailure:
    """Why a call did not return a packing, in words a caller can print."""

    code: str
    detail: str
    subject: str | None = None


@dataclass(frozen=True)
class FramePlacement:
    """One frame's final box and the translation that produced it."""

    name: str
    frame: Box
    origin: tuple[float, float]

    @property
    def width(self) -> float:
        return self.frame[2] - self.frame[0]

    @property
    def height(self) -> float:
        return self.frame[3] - self.frame[1]


@dataclass(frozen=True)
class PackingResult:
    """Structured answer: placements, occupied extent, cost and reason.

    ``placements`` is empty unless ``status == "packed"``; on a refusal the
    result carries ``failure`` and never a partial (overlapping) page.
    ``width``/``height`` are the extent of the placed frames themselves, not of
    the page, so a caller can compare a layout against the page it was given.
    """

    status: str
    placements: tuple[FramePlacement, ...]
    frames: dict[str, Box]
    width: float
    height: float
    nodes: int
    failure: PackingFailure | None = None

    @property
    def ok(self) -> bool:
        return self.status == STATUS_PACKED

    @property
    def truncated(self) -> bool:
        return self.status == STATUS_TRUNCATED

    @property
    def origins(self) -> dict[str, tuple[float, float]]:
        return {placement.name: placement.origin for placement in self.placements}


def frame_gap(left: Box, right: Box) -> float:
    """Edge-to-edge distance between two boxes (the checker's own measure).

    Each axis contributes ``max(left_min - right_max, right_min - left_max, 0)``
    and the two are combined with ``hypot``; overlapping boxes score 0.  This is
    the arithmetic of ``pagecompiler._frame_gap`` copied on purpose — the
    threshold this module enforces is the checker's, so the measure must not
    drift from it.
    """

    dx = max(left[0] - right[2], right[0] - left[2], 0.0)
    dy = max(left[1] - right[3], right[1] - left[3], 0.0)
    return math.hypot(dx, dy)


def pack_frames(
    frames: Mapping[str, Box],
    order: Sequence[str],
    page: Box,
    *,
    gap: float = DEFAULT_GAP,
    grid: float = DEFAULT_GRID,
    keepouts: Sequence[Box] = (),
    max_nodes: int = DEFAULT_MAX_NODES,
) -> PackingResult:
    """Place every frame of ``order`` inside ``page`` without enlarging any.

    ``frames`` maps each module name to its **local** frame; ``order`` must list
    every name exactly once, in reading priority (never a coordinate table).
    ``page`` and ``keepouts`` are absolute page boxes.  ``grid=0`` disables
    snapping.

    The search is finite and deterministic: candidate positions are the page's
    lower-left corner, the right and top edges of already placed frames plus
    ``gap``, and the edges of keep-outs; the cross product is tried bottom-left
    first with backtracking, and at most ``max_nodes`` candidates are tested.
    ``unsat`` therefore means "this discrete corner space has no packing", and
    ``truncated`` means the node budget ran out first — the two are reported
    separately on purpose.  Invalid input is refused as ``rejected`` rather
    than raised, so every outcome has the same shape.

    Determinism: nothing depends on mapping insertion order, set iteration or
    the hash seed; equal inputs give byte-identical placements and node counts.
    """

    refusal = _validate(frames, order, page, gap, grid, keepouts, max_nodes)
    if refusal is not None:
        return _refuse(refusal)

    if not order:
        return PackingResult(
            status=STATUS_PACKED,
            placements=(),
            frames={},
            width=0.0,
            height=0.0,
            nodes=0,
        )

    try:
        placements, nodes = _search(
            frames, list(order), page, float(gap), float(grid), tuple(keepouts),
            int(max_nodes),
        )
    except _Truncated as stop:
        return _refuse(
            PackingFailure(
                code=FAILURE_BUDGET_EXHAUSTED,
                detail=(
                    f"no packing was found within max_nodes={max_nodes}; the "
                    "candidate space was not exhausted, so this is a budget "
                    "stop and not a proof that no packing exists"
                ),
            ),
            status=STATUS_TRUNCATED,
            nodes=stop.nodes,
        )
    if placements is None:
        return _refuse(
            PackingFailure(
                code=FAILURE_UNSAT,
                detail=(
                    "no placement of the given frames inside the page was found "
                    "in the corner-candidate space, with every gap, keep-out "
                    "and page bound respected"
                ),
            ),
            status=STATUS_UNSAT,
        )

    return PackingResult(
        status=STATUS_PACKED,
        placements=tuple(placements),
        frames={placement.name: placement.frame for placement in placements},
        width=max(p.frame[2] for p in placements) - min(p.frame[0] for p in placements),
        height=max(p.frame[3] for p in placements) - min(p.frame[1] for p in placements),
        nodes=nodes,
    )


class _Truncated(Exception):
    """Internal signal: the node budget ran out before the space was exhausted."""

    def __init__(self, nodes: int) -> None:
        super().__init__(nodes)
        self.nodes = nodes


def _search(
    frames: Mapping[str, Box],
    order: list[str],
    page: Box,
    gap: float,
    grid: float,
    keepouts: tuple[Box, ...],
    max_nodes: int,
) -> tuple[list[FramePlacement] | None, int]:
    placed: list[FramePlacement] = []
    nodes = 0

    def visit(index: int) -> bool:
        nonlocal nodes
        if index == len(order):
            return True
        name = order[index]
        local = frames[name]
        width = local[2] - local[0]
        height = local[3] - local[1]
        for x, y in _candidates(placed, keepouts, page, gap, grid):
            if nodes >= max_nodes:
                raise _Truncated(nodes)
            nodes += 1
            box = (x, y, x + width, y + height)
            if (
                box[0] < page[0] - _PAGE_EPSILON
                or box[2] > page[2] + _PAGE_EPSILON
                or box[1] < page[1] - _PAGE_EPSILON
                or box[3] > page[3] + _PAGE_EPSILON
            ):
                continue
            if any(_overlaps(box, keepout) for keepout in keepouts):
                continue
            if any(_overlaps(box, other.frame) for other in placed):
                continue
            # Re-checked after snapping: the lattice may move a frame, but it
            # may not buy space by narrowing a gap.
            if any(frame_gap(box, other.frame) <= gap - GAP_EPSILON for other in placed):
                continue
            placed.append(
                FramePlacement(name, box, (box[0] - local[0], box[1] - local[1]))
            )
            if visit(index + 1):
                return True
            placed.pop()
        return False

    found = visit(0)
    return (list(placed) if found else None), nodes


def _candidates(
    placed: Sequence[FramePlacement],
    keepouts: Sequence[Box],
    page: Box,
    gap: float,
    grid: float,
) -> list[tuple[float, float]]:
    """Bottom-left-first candidate origins, snapped to the lattice.

    ``x`` values come from one frame and ``y`` values from another: a short
    frame can therefore fill the space under a tall neighbour instead of
    inheriting the tall frame's row, which is the difference between this
    search and a shelf.
    """

    xs = [page[0]]
    ys = [page[1]]
    for placement in placed:
        xs.append(placement.frame[2] + gap)
        ys.append(placement.frame[3] + gap)
    for keepout in keepouts:
        xs.extend((keepout[0], keepout[2]))
        ys.extend((keepout[1], keepout[3]))
    return [
        (x, y)
        for y in _snap_sorted(ys, grid)
        for x in _snap_sorted(xs, grid)
    ]


def _snap_sorted(values: Sequence[float], grid: float) -> list[float]:
    snapped = [_snap_up(value, grid) for value in values]
    return sorted(dict.fromkeys(snapped))


def _snap_up(value: float, grid: float) -> float:
    if grid <= 0.0:
        return value
    return math.ceil(value / grid - _SNAP_EPSILON) * grid


def _overlaps(left: Box, right: Box) -> bool:
    return (
        min(left[2], right[2]) - max(left[0], right[0]) > _OVERLAP_EPSILON
        and min(left[3], right[3]) - max(left[1], right[1]) > _OVERLAP_EPSILON
    )


def _refuse(
    failure: PackingFailure,
    *,
    status: str = STATUS_REJECTED,
    nodes: int = 0,
) -> PackingResult:
    return PackingResult(
        status=status,
        placements=(),
        frames={},
        width=0.0,
        height=0.0,
        nodes=nodes,
        failure=failure,
    )


def _validate(
    frames: object,
    order: object,
    page: object,
    gap: object,
    grid: object,
    keepouts: object,
    max_nodes: object,
) -> PackingFailure | None:
    if not _is_finite_number(gap):
        return PackingFailure(FAILURE_INVALID_ARGUMENT, f"gap must be a finite number, got {gap!r}")
    if float(gap) < 0.0:
        return PackingFailure(FAILURE_INVALID_ARGUMENT, f"gap must not be negative, got {gap!r}")
    if not _is_finite_number(grid):
        return PackingFailure(FAILURE_INVALID_ARGUMENT, f"grid must be a finite number, got {grid!r}")
    if float(grid) < 0.0:
        return PackingFailure(FAILURE_INVALID_ARGUMENT, f"grid must not be negative, got {grid!r}")
    if isinstance(max_nodes, bool) or not isinstance(max_nodes, int) or max_nodes < 1:
        return PackingFailure(
            FAILURE_INVALID_ARGUMENT, f"max_nodes must be a positive integer, got {max_nodes!r}"
        )

    page_box = _as_box(page)
    if page_box is None:
        return PackingFailure(FAILURE_INVALID_PAGE, f"page is not a box: {page!r}")
    if page_box[2] <= page_box[0] or page_box[3] <= page_box[1]:
        return PackingFailure(FAILURE_INVALID_PAGE, f"page has no area: {page!r}")

    if isinstance(keepouts, (str, bytes)) or not isinstance(keepouts, Sequence):
        return PackingFailure(
            FAILURE_INVALID_KEEPOUT, f"keepouts must be a sequence of boxes, got {keepouts!r}"
        )
    for index, keepout in enumerate(keepouts):
        box = _as_box(keepout)
        if box is None:
            return PackingFailure(
                FAILURE_INVALID_KEEPOUT, f"keepouts[{index}] is not a box: {keepout!r}"
            )

    if not isinstance(frames, Mapping):
        return PackingFailure(FAILURE_INVALID_FRAME, f"frames must be a mapping, got {frames!r}")
    for name, local in frames.items():
        if not isinstance(name, str) or not name:
            return PackingFailure(
                FAILURE_INVALID_FRAME, f"frame name must be a non-empty string, got {name!r}"
            )
        box = _as_box(local)
        if box is None:
            return PackingFailure(
                FAILURE_INVALID_FRAME, f"frames[{name!r}] is not a box: {local!r}", subject=name
            )
        if box[2] <= box[0] or box[3] <= box[1]:
            return PackingFailure(
                FAILURE_INVALID_FRAME,
                f"frames[{name!r}] has no extent: {local!r}",
                subject=name,
            )

    if isinstance(order, (str, bytes)) or not isinstance(order, Sequence):
        return PackingFailure(
            FAILURE_INVALID_ORDER, f"order must be a sequence of names, got {order!r}"
        )
    seen: set[str] = set()
    for index, name in enumerate(order):
        if not isinstance(name, str) or not name:
            return PackingFailure(
                FAILURE_INVALID_ORDER, f"order[{index}] is not a name: {name!r}"
            )
        if name in seen:
            return PackingFailure(
                FAILURE_DUPLICATE_ORDER, f"order names {name!r} twice", subject=name
            )
        seen.add(name)
        if name not in frames:
            return PackingFailure(
                FAILURE_UNKNOWN_ORDER, f"order names {name!r}, which is not a frame", subject=name
            )
    missing = sorted(name for name in frames if name not in seen)
    if missing:
        return PackingFailure(
            FAILURE_MISSING_ORDER,
            f"order omits frame(s): {', '.join(missing)}",
            subject=missing[0],
        )
    if len(order) > MAX_FRAMES:
        return PackingFailure(
            FAILURE_TOO_MANY_FRAMES,
            f"order has {len(order)} frames; this packer's bound is {MAX_FRAMES}",
        )
    return None


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _as_box(value: object) -> Box | None:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 4
        or any(
            isinstance(item, bool) or not isinstance(item, (int, float))
            for item in value
        )
    ):
        return None
    try:
        box = (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
    except (OverflowError, ValueError):
        return None
    if not all(math.isfinite(item) for item in box):
        return None
    return box


__all__ = [
    "Box",
    "DEFAULT_GAP",
    "DEFAULT_GRID",
    "DEFAULT_MAX_NODES",
    "FAILURE_BUDGET_EXHAUSTED",
    "FAILURE_DUPLICATE_ORDER",
    "FAILURE_INVALID_ARGUMENT",
    "FAILURE_INVALID_FRAME",
    "FAILURE_INVALID_KEEPOUT",
    "FAILURE_INVALID_ORDER",
    "FAILURE_INVALID_PAGE",
    "FAILURE_MISSING_ORDER",
    "FAILURE_TOO_MANY_FRAMES",
    "FAILURE_UNKNOWN_ORDER",
    "FAILURE_UNSAT",
    "FramePlacement",
    "GAP_EPSILON",
    "MAX_FRAMES",
    "PackingFailure",
    "PackingResult",
    "STATUS_PACKED",
    "STATUS_REJECTED",
    "STATUS_TRUNCATED",
    "STATUS_UNSAT",
    "frame_gap",
    "pack_frames",
]
