"""Offline copper-path evidence between two pads of one net (task 550).

The question this module answers is narrow on purpose: *is there an ordered
chain of **supported copper primitives** that physically joins these two pads
on this board?* It is review evidence, not a router, and not an electrical
verdict — the verdict says what this batch's graph proved, never what the
board does.

**Verdicts are three, and the third one is the honest default.**

* :data:`CONNECTED` — breadth-first search found a real path. Every hop shares
  at least one copper layer and the pair's copper bodies meet under the
  repository's own measurement (``measure._touching``). A net *name* only
  selects which primitives may be considered; it is never evidence, because a
  name survives any number of unrouted or split connections.
* :data:`NOT_PROVEN` — no path in the supported graph **and nothing unknown**
  that could change that answer. It means 「this batch's copper inventory did
  not prove a connection」. It deliberately does not say 「开路」: pour, PLANE
  and ARC copper are outside the graph (see ``ignored`` and ``scope``), and a
  caller that reads NOT_PROVEN as an open circuit is misreading the contract.
* :data:`INDETERMINATE` — the input does not hold (bad reference, unknown pad,
  two nets, unread copper table) **or** some evidence gap could change a
  negative answer. A positive answer is never overturned by a gap: a path that
  was walked is a path, and the gaps are still disclosed beside it.

**What may be a vertex.** Pads whose existing exact model is trustworthy
(``RECT``, circular ``ELLIPSE``, ``OVAL`` — :func:`_pad_supported`), straight
``LINE`` tracks and vias. Pads whose shape only has an approximating model (a
non-circular ``ELLIPSE`` is the circumscribing 32-gon of
``measure._pad_copper``, an unknown string is a box) are **never** placed in
the graph: an approximation is fine for a conservative clearance number and is
not fine for a claim that copper joins, so it cannot manufacture a positive
path. Such a pad at an endpoint is an input error; anywhere else it is an
escalation of the negative answer to INDETERMINATE.

**What may be an edge.** ``pad↔track``, ``track↔track``, ``track↔via``,
``pad↔pad``, ``via↔via`` — measured with :func:`measure._touching` on the
same shapes the rest of the repository measures. One pair is deliberately
**not** an edge: a pad that touches a via directly (the 「via in pad」 case)
is disclosed as ``pad_via_contact`` instead, because the host's own
connectivity semantics for it have not been confirmed on a real board
(task 550 §6). A caller that needs that connection today gets INDETERMINATE,
not an invented path.

**What is excluded, on purpose, and where that is said.** ``FILL`` / ``POLY``
/ ``POUR`` / ``POURED`` copper never joins a path, and a board where only a
pour could connect the two pads answers NOT_PROVEN even though its pour is
one piece of copper — 「只有铺铜能连」 is not evidence under this contract.
Pour is therefore **not** an evidence gap: it is reported in ``ignored`` and
named in ``scope``, and it must not be used to escalate. ``PLANE`` layers are
copper and are excluded the same way (their copper, when the file stores it,
arrives as a ``POUR``/``POURED`` record anyway). What *does* escalate is
copper that could not be read at all: unparsed ``ARC`` records (the exporter
writes arc copper as its own record type and this repository does not model
it), netless tracks/vias (they could be the missing bridge), tracks/vias the
layer table cannot place, and pads whose copper layer the parser never
resolved.

**Determinism.** Vertex order is ``measure._net_shape_records``' own fixed
order (tracks, vias, pads, pours), neighbours are explored in ascending vertex
index, unknowns are appended in a fixed phase order, and the JSON projection
is ``sort_keys=True``. The same board and the same two references therefore
produce byte-identical output, which is what makes the evidence quotable.

Nothing here reads the container, the editor or the bridge: a
:class:`~boardwise.core.geometry.BoardGeometry` in, a result out. Container
and board selection belong to the assembly layer (``pcb_netpath``), which is
also the only place that may fill in :attr:`NetPathResult.source`'s container
facts.
"""

from __future__ import annotations

import json
import math
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Mapping

from .geometry import COORD_PRECISION, ArcGeometry, BoardGeometry, NetGeometry, PadGeometry
from .measure import (
    _PAD_SQUARE_EPS,
    _bbox_distance,
    _element_layers,
    _net_shape_records,
    _pad_key,
    _touching,
    read_stackup,
)

__all__ = [
    "CONNECTED",
    "INDETERMINATE",
    "NOT_PROVEN",
    "SCHEMA",
    "NetPathResult",
    "find_net_path",
]

#: The JSON contract this result projects into. Bumped only with a contract
#: change; readers pin it.
SCHEMA = "boardwise.pcbNetPath/1"

CONNECTED = "CONNECTED"
NOT_PROVEN = "NOT_PROVEN"
INDETERMINATE = "INDETERMINATE"

#: Pad shapes whose copper :func:`measure._pad_copper` models **exactly**.
#: ``RECT`` is the rotated rectangle, ``OVAL`` a stadium (a circle when the two
#: extents are equal), ``ELLIPSE`` a disc — but only while it *is* a disc; see
#: :func:`_pad_supported`.
_EXACT_PAD_SHAPES = frozenset({"RECT", "OVAL"})

#: The tolerance ``measure._touching`` itself calls 「touching」. Re-used rather
#: than re-invented so a hop in this module and a clearance reading elsewhere
#: cannot disagree about the same pair of primitives.
_TOUCH_EPS = 1e-9

#: What the graph is built from, spelled out in every result.
_SCOPE: dict[str, Any] = {
    "supports": [
        "pad RECT",
        "pad circular ELLIPSE",
        "pad OVAL",
        "straight LINE track",
        "via, including blind/buried vias through their effective layers",
    ],
    "excludes": [
        "FILL/POLY/POUR/POURED copper",
        "PLANE copper",
        "ARC copper (not modelled by this repository)",
        "direct pad<->via edges (host semantics unconfirmed)",
        "net-name-only connectivity",
        "path length, angle, impedance, width-rule or DRC conclusions",
    ],
    "note": (
        "NOT_PROVEN 只表示「未由本批支持的铜图元证明」，不是电气开路；"
        "pour/PLANE 的排除不构成 unknown，也不用于补路。"
    ),
}


def _round(value: Any) -> float:
    """A coordinate as the report writes it: rounded, never a float surprise."""
    return round(float(value), COORD_PRECISION)


def _sorted_layers(layers: Any) -> list[int]:
    """Copper layer ids as a sorted list of ``int`` (JSON-stable)."""
    return sorted(int(layer) for layer in (layers or ()))


def _issue(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """One ``errors`` / ``unknown`` / ``ignored`` row.

    ``extra`` is written in insertion order and only with JSON-safe values;
    ``sort_keys=True`` at projection time makes the bytes stable regardless.
    """
    row: dict[str, Any] = {"code": code, "message": message}
    for key, value in extra.items():
        row[key] = value
    return row


@dataclass
class NetPathResult:
    """The answer to one ``find_net_path`` question, and its JSON projection.

    ``unknown`` is never a 「maybe path」: it is the list of evidence gaps that
    would change a **negative** verdict, so an empty ``unknown`` beside
    :data:`NOT_PROVEN` is a statement that the supported copper inventory was
    complete for this question. ``ignored`` is the opposite — things this
    contract excludes by decision (pour, PLANE, non-copper records), which
    must never be used to escalate a negative answer.
    """

    verdict: str = INDETERMINATE
    source: dict[str, Any] = field(default_factory=dict)
    query: dict[str, Any] = field(default_factory=dict)
    path: list[dict[str, Any]] = field(default_factory=list)
    unknown: list[dict[str, Any]] = field(default_factory=list)
    ignored: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    scope: dict[str, Any] = field(default_factory=lambda: dict(_SCOPE))
    schema: str = SCHEMA

    @property
    def via_count(self) -> int:
        """How many vias the walked path uses (0 when nothing was walked)."""
        return sum(1 for row in self.path if row.get("kind") == "via")

    @property
    def hop_count(self) -> int:
        """Edges walked — ``len(path) - 1``, and 0 for a degenerate path."""
        return max(len(self.path) - 1, 0)

    def as_dict(self) -> dict[str, Any]:
        """The :data:`SCHEMA` payload. Every array is present, empty or not."""
        return {
            "schema": self.schema,
            "verdict": self.verdict,
            "source": dict(self.source),
            "query": dict(self.query),
            "path": [dict(row) for row in self.path],
            "hopCount": self.hop_count,
            "viaCount": self.via_count,
            "unknown": [dict(row) for row in self.unknown],
            "ignored": [dict(row) for row in self.ignored],
            "errors": [dict(row) for row in self.errors],
            "coverage": dict(self.coverage),
            "scope": dict(self.scope),
        }

    def to_json(self, *, indent: int | None = None) -> str:
        """The payload as canonical JSON (sorted keys, UTF-8 friendly)."""
        return json.dumps(
            self.as_dict(),
            sort_keys=True,
            ensure_ascii=False,
            indent=indent,
            allow_nan=False,
        )


def _parse_ref(text: Any) -> tuple[str, str] | None:
    """``"REF.PAD"`` → ``("REF", "PAD")``, or ``None`` when it is not one.

    The split is at the **last** dot: a designator may itself contain dots on
    some projects, a pad number never does in the files this repository reads.
    Both halves must be non-empty after stripping, so ``""``, ``"C1"``,
    ``".2"`` and ``"C1."`` are refusals rather than a quiet ``""`` pad.
    """
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    if "." not in cleaned:
        return None
    designator, _, pin = cleaned.rpartition(".")
    designator = designator.strip()
    pin = pin.strip()
    if not designator or not pin:
        return None
    return (designator, pin)


def _ref_payload(text: Any) -> dict[str, Any]:
    """The query's echo of one side, before any pad has been resolved.

    The keys are the contract's, written even when nothing was resolved
    (``pad``/``net``/``shape`` ``None``, ``layers`` empty): a consumer that
    reads ``query.from.net`` must not have to special-case the error paths, and
    an empty list here means 「no pad was read」 rather than 「a pad with no
    copper layer」 — the latter is an ``errors`` row of its own.
    """
    return {
        "ref": text if isinstance(text, str) else None,
        "pad": None,
        "net": None,
        "layers": [],
        "shape": None,
        "angle": None,
    }


def _pad_query(pad: PadGeometry) -> dict[str, Any]:
    """The query row for a resolved pad: ref, pad, net, layers and shape."""
    return {
        "ref": pad.component,
        "pad": pad.pin_number,
        "net": pad.net,
        "layers": _sorted_layers(pad.effective_layer_ids),
        "shape": pad.shape,
        "angle": _round(pad.angle),
    }


def _pad_finite(pad: Any) -> bool:
    """True when the pad's own numbers — place, size, angle — are finite.

    ``PadGeometry`` is normally built by the parser from floats, but a
    hand-built board (a test, a caller's own model) can carry ``NaN`` or an
    infinity. Those must reach neither :func:`_pad_query` (``round`` would keep
    the ``NaN``) nor the JSON (:func:`NetPathResult.to_json` refuses ``NaN`` by
    design), so every endpoint is checked before its query row is written and
    every middle pad is checked before it may enter the graph.
    """
    return _finite(
        getattr(pad, "x", None),
        getattr(pad, "y", None),
        getattr(pad, "width", None),
        getattr(pad, "height", None),
        getattr(pad, "angle", None),
    )


def _pad_supported(pad: PadGeometry) -> bool:
    """True when this pad's copper has an **exact** model in ``measure``.

    ``RECT`` and ``OVAL`` always do. ``ELLIPSE`` only while it is a disc —
    ``measure._pad_copper`` reads a non-circular ellipse as the *circumscribing*
    32-gon, which is the right conservative reading for a clearance number and
    the wrong one for 「this copper touches that copper」, so it is refused
    here. An empty or unknown shape string is refused too: ``pad_corners``
    would give it a box, which is an assumption this module will not turn into
    a connection. A pad whose own numbers are not finite is refused too: an
    exact model of ``NaN`` is not a model.
    """
    shape = str(pad.shape or "").upper()
    if shape in _EXACT_PAD_SHAPES:
        return True
    if shape != "ELLIPSE":
        return False
    if not _pad_finite(pad):
        return False
    width = abs(float(pad.width))
    height = abs(float(pad.height))
    return abs(width - height) <= _PAD_SQUARE_EPS


def _finite(*values: Any) -> bool:
    """True when every value is a finite number (no NaN, no infinity)."""
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(number):
            return False
    return True


def _track_usable(track: Any) -> bool:
    """A track is usable when its geometry is finite and its copper has width."""
    return (
        _finite(track.start.x, track.start.y, track.end.x, track.end.y, track.width)
        and float(track.width) > 0.0
    )


def _via_usable(via: Any) -> bool:
    """A via is usable when its barrel is finite and physically possible.

    The barrel requires ``0 <= hole_diameter < via_diameter``. A negative hole,
    or a hole as large as (or larger than) the pad, is not a barrel: the record
    contradicts itself, its annular ring would be negative, and the capsule this
    module would measure would come from a diameter the record itself refutes.
    Such a via is disclosed as invalid and kept out of the graph, never
    measured.
    """
    if not _finite(via.x, via.y, via.via_diameter, via.hole_diameter):
        return False
    outer = float(via.via_diameter)
    hole = float(via.hole_diameter)
    return outer > 0.0 and 0.0 <= hole < outer


def _stackup_source(board: BoardGeometry) -> str:
    """Which table the copper layers came from — a fact, not a guess."""
    if board.stackup:
        return "layer_phys"
    if board.layers:
        return "layer_table"
    return "empty"


def _base_coverage(board: BoardGeometry) -> dict[str, Any]:
    """The board-level half of ``coverage`` (filled further once a net is known)."""
    stackup = read_stackup(board)
    return {
        "net": None,
        "stackup": _stackup_source(board),
        "copperLayers": [info.layer_id for info in stackup.copper_layers],
        "board": {
            "pads": len(board.pads),
            "tracks": len(board.tracks),
            "vias": len(board.vias),
            "pours": len(board.pours),
            "arcs": len(board.arcs),
            "arcRecordsUnconsumed": int(board.stats.unconsumed_types.get("ARC", 0)),
            "netlessTracks": sum(1 for track in board.tracks if not track.net),
            "netlessVias": sum(1 for via in board.vias if not via.net),
        },
        "graph": {"vertices": 0, "edges": 0, "excluded": 0},
        "elements": {"pads": 0, "tracks": 0, "vias": 0, "pours": 0},
    }


def _source_payload(
    board: BoardGeometry, override: Mapping[str, Any] | None
) -> dict[str, Any]:
    """``source`` as the contract wants it: container, board count, identity.

    The board alone can only answer 「one board, read from this geometry
    object」. The assembly layer knows the container (``.epro2`` / ``.eprj3``),
    how many boards it holds and which one was selected, so it passes those in
    and they win. ``path`` is local evidence and stays local.
    """
    payload: dict[str, Any] = {
        "container": "board-geometry",
        "boardCount": 1,
        "title": board.name,
        "uuid": None,
        "path": board.source,
    }
    if override:
        for key, value in override.items():
            payload[key] = value
    return payload


@dataclass
class _Vertex:
    """One graph vertex: the measured shape plus the record it came from."""

    id: str
    shape: Any
    element: Any


def _build_vertices(
    board: BoardGeometry,
    geo: Any,
    net: str,
    unknown: list[dict[str, Any]],
    ignored: list[dict[str, Any]],
    coverage: dict[str, Any],
) -> tuple[list[_Vertex], str | None]:
    """Turn one net's copper into vertices, disclosing everything left out.

    ``error_code`` is ``None`` on success and non-``None`` when the vertex list
    could not be aligned with the measured shapes, which would make every path
    row a guess and is therefore fatal to this run.
    """
    all_pads = list(geo.pads)
    invalid_pads = [pad for pad in all_pads if not _pad_finite(pad)]
    if invalid_pads:
        # A middle pad with a non-finite number cannot even be measured:
        # `measure._pad_copper` turns the pad's angle through ``math.cos``,
        # which raises on an infinity, and every figure it would produce for a
        # ``NaN`` is unusable. So such a pad is disclosed here and removed
        # **before** the shapes are built — the endpoints were checked by the
        # caller already. The copy keeps `NetGeometry`'s own order, so the
        # vertex order (and therefore the report) stays deterministic.
        for pad in invalid_pads:
            unknown.append(
                _issue(
                    "invalid_pad_geometry",
                    "this pad's place/size/angle is not a finite number, so it has "
                    "no copper this module may measure; it takes no part in the "
                    "graph",
                    pad=_pad_key(pad),
                )
            )
        geo = NetGeometry(
            name=geo.name,
            pads=[pad for pad in all_pads if _pad_finite(pad)],
            tracks=list(geo.tracks),
            vias=list(geo.vias),
            pours=list(geo.pours),
            arcs=list(geo.arcs),
        )

    shapes_with_ids = _net_shape_records(board, geo, with_area=False)

    # The same skips `_net_shape_records` applies, replayed so each shape keeps
    # its own record: `_net_shape_records` reports ids only, and the report
    # needs width / diameters / shape / angle, which live on the record.
    pads_in = [pad for pad in geo.pads if _element_layers(board, pad)]
    tracks_in = [track for track in geo.tracks if _element_layers(board, track)]
    vias_in = [via for via in geo.vias if _element_layers(board, via, via=True)]

    pads_dropped = [pad for pad in geo.pads if not _element_layers(board, pad)]
    tracks_dropped = [
        track for track in geo.tracks if not _element_layers(board, track)
    ]
    vias_dropped = [via for via in geo.vias if not _element_layers(board, via, via=True)]

    for pad in pads_dropped:
        if pad.effective_layer_ids is None:
            unknown.append(
                _issue(
                    "pad_layer_unread",
                    "this net carries a pad whose copper layer could not be read; "
                    "it takes no part in the graph",
                    pad=_pad_key(pad),
                )
            )
        else:
            # An explicit ``[]`` is the parser's reading 「no copper layer at
            # all」 — a bare mechanical hole, or an NPTH whose land is no larger
            # than its hole. That is a **certain absence** of copper, not an
            # evidence gap, so it is disclosed as ignored and never escalates a
            # negative verdict.
            ignored.append(
                _issue(
                    "pad_without_copper_layer",
                    "this pad's reading is 「no copper layer」, so it carries no "
                    "copper that could join anything",
                    pad=_pad_key(pad),
                )
            )
    for track in tracks_dropped:
        unknown.append(
            _issue(
                "track_without_copper_layer",
                "a track of this net sits on no readable copper layer; it takes "
                "no part in the graph",
                id=track.id,
            )
        )
    for via in vias_dropped:
        unknown.append(
            _issue(
                "via_without_copper_layer",
                "a via of this net spans no readable copper layer; it takes no "
                "part in the graph",
                id=via.id,
            )
        )

    vertices: list[_Vertex] = []
    pointers = {"pad": 0, "track": 0, "via": 0}
    pools = {"pad": pads_in, "track": tracks_in, "via": vias_in}
    pad_key_counts = Counter(_pad_key(pad) for pad in all_pads)
    duplicate_pad_keys = sorted(
        key for key, count in pad_key_counts.items() if count > 1
    )
    for key in duplicate_pad_keys:
        unknown.append(
            _issue(
                "duplicate_pad_id",
                "more than one pad of this net answers to this REF.PAD key; a "
                "path through it could not say which pad it walked, so every pad "
                "sharing the key is kept out of the graph",
                pad=key,
                count=pad_key_counts[key],
            )
        )

    for element_id, shape, _area in shapes_with_ids:
        kind = shape.kind
        if kind == "pour":
            continue
        pool = pools.get(kind)
        element = None
        if pool is not None and pointers[kind] < len(pool):
            element = pool[pointers[kind]]
            pointers[kind] += 1
        if element is None:
            return vertices, "graph_alignment"

        included = True
        if kind == "pad":
            if not _pad_supported(element):
                included = False
                unknown.append(
                    _issue(
                        "unsupported_pad_shape",
                        "this pad's shape has no exact copper model in measure "
                        "(only RECT, circular ELLIPSE and OVAL do), so it can "
                        "neither join nor prove a path",
                        pad=_pad_key(element),
                        shape=element.shape,
                    )
                )
            elif element.effective_layer_ids is None:
                included = False
                unknown.append(
                    _issue(
                        "pad_layer_unread",
                        "this pad's copper layer was never read by the parser",
                        pad=_pad_key(element),
                    )
                )
            if element_id in duplicate_pad_keys:
                included = False
        elif kind == "track":
            if not _track_usable(element):
                included = False
                unknown.append(
                    _issue(
                        "invalid_track_geometry",
                        "this track's width/endpoints are not finite copper",
                        id=element.id,
                    )
                )
        elif kind == "via":
            if not _via_usable(element):
                included = False
                unknown.append(
                    _issue(
                        "invalid_via_geometry",
                        "this via's position or pad diameter is not finite copper",
                        id=element.id,
                    )
                )
        else:
            included = False
            unknown.append(
                _issue(
                    "unsupported_element_kind",
                    "an element of this net is not a pad, track or via",
                    id=element_id,
                    kind=kind,
                )
            )

        if included:
            vertices.append(_Vertex(id=element_id, shape=shape, element=element))
        else:
            coverage["graph"]["excluded"] += 1

    if any(pointers[kind] != len(pools[kind]) for kind in pools):  # pragma: no cover
        # `_net_shape_records` and this replay must agree; if they ever stop
        # agreeing, every path row would be attached to the wrong record.
        return vertices, "graph_alignment"

    coverage["graph"]["vertices"] = len(vertices)
    coverage["elements"] = {
        "pads": len(all_pads),
        "tracks": len(geo.tracks),
        "vias": len(geo.vias),
        "pours": len(geo.pours),
    }
    if geo.pours:
        ignored.append(
            _issue(
                "pour_excluded",
                "pour/fill/POLY/POURED copper is excluded by contract: it never "
                "joins a path and never turns a negative answer into a positive "
                "one",
                net=net,
                count=len(geo.pours),
                kinds=sorted({str(pour.kind) for pour in geo.pours}),
            )
        )
    return vertices, None


def _path_row(vertex: _Vertex, net: str) -> dict[str, Any]:
    """One walked hop in the report: identity, layers, and the record's figures."""
    shape = vertex.shape
    element = vertex.element
    row: dict[str, Any] = {
        "id": vertex.id,
        "kind": shape.kind,
        "layers": _sorted_layers(shape.layers),
        "net": net,
    }
    if shape.kind == "pad":
        row["ref"] = element.component
        row["pad"] = element.pin_number
        row["shape"] = element.shape
        row["angle"] = _round(element.angle)
    elif shape.kind == "track":
        row["width"] = _round(element.width)
        row["start"] = [_round(element.start.x), _round(element.start.y)]
        row["end"] = [_round(element.end.x), _round(element.end.y)]
    elif shape.kind == "via":
        row["center"] = [_round(element.x), _round(element.y)]
        row["viaDiameter"] = _round(element.via_diameter)
        row["holeDiameter"] = _round(element.hole_diameter)
    return row


def _walk(adjacency: list[list[int]], start: int, goal: int) -> list[int]:
    """Shortest-hop path by BFS, neighbours in ascending index order.

    Breadth-first rather than depth-first because the report should be the
    *shortest evidence*, and neighbours are explored in the vertex order
    ``measure._net_shape_records`` produced, so two runs on one board walk the
    same edges in the same sequence. ``parent`` is written once per vertex, so
    the answer is a path and never a walk through a cycle.
    """
    parent: dict[int, int | None] = {start: None}
    queue: deque[int] = deque([start])
    while queue:
        current = queue.popleft()
        if current == goal:
            break
        for neighbour in adjacency[current]:
            if neighbour in parent:
                continue
            parent[neighbour] = current
            queue.append(neighbour)
    if goal not in parent:
        return []
    walked: list[int] = []
    cursor: int | None = goal
    while cursor is not None:
        walked.append(cursor)
        cursor = parent[cursor]
    walked.reverse()
    return walked


def find_net_path(
    board: BoardGeometry,
    from_ref: str,
    to_ref: str,
    *,
    source: Mapping[str, Any] | None = None,
) -> NetPathResult:
    """Copper-path evidence between ``from_ref`` and ``to_ref`` on one board.

    ``from_ref`` / ``to_ref`` are ``"REF.PAD"`` strings matched against the
    pads the board actually holds (``PadGeometry.component`` +
    ``PadGeometry.pin_number``). Nothing is inferred when they do not resolve:
    an unknown pad, an ambiguous key, a pad without a net, two different nets
    or an unsupported endpoint shape all end in :data:`INDETERMINATE` with an
    ``errors`` row that names the reason — this function never raises for bad
    input and never substitutes a nearby pad (R3). Two references that resolve
    to the *same* pad are refused as well (``errors.same_pad``): one terminal is
    not a path, and a zero-hop 「CONNECTED」 would claim a walk nobody took.

    ``source`` lets the caller (assembly) state the container facts —
    ``container``, ``boardCount``, the selected ``title``/``uuid`` — that a
    bare :class:`BoardGeometry` cannot know. It is the only non-board input,
    and it never influences the verdict.
    """
    errors: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    coverage = _base_coverage(board)
    query: dict[str, Any] = {
        "from": _ref_payload(from_ref),
        "to": _ref_payload(to_ref),
    }

    def finish(verdict: str, path: list[dict[str, Any]] | None = None) -> NetPathResult:
        return NetPathResult(
            verdict=verdict,
            source=_source_payload(board, source),
            query=query,
            path=list(path or []),
            unknown=unknown,
            ignored=ignored,
            errors=errors,
            coverage=coverage,
        )

    parsed = {"from": _parse_ref(from_ref), "to": _parse_ref(to_ref)}
    for side in ("from", "to"):
        if parsed[side] is None:
            errors.append(
                _issue(
                    "bad_ref",
                    "a reference must be written REF.PAD (designator, dot, pad); "
                    "nothing was looked up",
                    side=side,
                    ref=query[side]["ref"],
                )
            )
    if errors:
        return finish(INDETERMINATE)

    # -- resolve the two pads -------------------------------------------------
    pads: dict[str, PadGeometry] = {}
    for side in ("from", "to"):
        designator, pin = parsed[side]  # type: ignore[misc]
        matches = [
            pad
            for pad in board.pads
            if (pad.component or "") == designator and (pad.pin_number or "") == pin
        ]
        if not matches:
            errors.append(
                _issue(
                    "pad_not_found",
                    "no pad with this REF.PAD exists on this board",
                    side=side,
                    ref=f"{designator}.{pin}",
                )
            )
        elif len(matches) > 1:
            errors.append(
                _issue(
                    "pad_ambiguous",
                    "more than one pad matches this REF.PAD on this board; the "
                    "question is not answerable without a unique pad",
                    side=side,
                    ref=f"{designator}.{pin}",
                    pads=[_pad_key(pad) for pad in matches],
                )
            )
        else:
            pads[side] = matches[0]
    if errors:
        return finish(INDETERMINATE)

    for side in ("from", "to"):
        pad = pads[side]
        if not _pad_finite(pad):
            errors.append(
                _issue(
                    "invalid_pad_geometry",
                    "the endpoint's place/size/angle is not a finite number, so no "
                    "copper may be measured through it",
                    side=side,
                    pad=_pad_key(pad),
                )
            )
        else:
            query[side] = _pad_query(pad)
    if errors:
        return finish(INDETERMINATE)

    if pads["from"] is pads["to"]:
        errors.append(
            _issue(
                "same_pad",
                "the two references name the same pad; a path needs two distinct "
                "copper terminals, and answering 「connected」 for one terminal "
                "would claim a search that never happened",
                pad=_pad_key(pads["from"]),
            )
        )
        return finish(INDETERMINATE)

    # -- the two pads must be one net, and both must be modellable ------------
    nets = {side: pads[side].net for side in ("from", "to")}
    for side in ("from", "to"):
        if not nets[side]:
            errors.append(
                _issue(
                    "pad_without_net",
                    "this pad carries no net, so there is no copper inventory to "
                    "search",
                    side=side,
                    pad=_pad_key(pads[side]),
                )
            )
    if not errors and nets["from"] != nets["to"]:
        errors.append(
            _issue(
                "net_mismatch",
                "the two pads are on different nets; a path between them is not a "
                "question this tool answers (it would be a short, not a route)",
                from_net=nets["from"],
                to_net=nets["to"],
            )
        )
    for side in ("from", "to"):
        pad = pads[side]
        if not _pad_supported(pad):
            errors.append(
                _issue(
                    "unsupported_pad_shape",
                    "the endpoint's shape has no exact copper model (only RECT, "
                    "circular ELLIPSE and OVAL do), so no path may be claimed "
                    "through it",
                    side=side,
                    pad=_pad_key(pad),
                    shape=pad.shape,
                )
            )
        elif pad.effective_layer_ids is None:
            errors.append(
                _issue(
                    "pad_layer_unread",
                    "the endpoint's copper layer was never read by the parser",
                    side=side,
                    pad=_pad_key(pad),
                )
            )
        elif not pad.effective_layer_ids:
            errors.append(
                _issue(
                    "pad_without_copper_layer",
                    "the endpoint's reading is 「no copper layer at all」 (a bare "
                    "mechanical hole), so it cannot start a copper path",
                    side=side,
                    pad=_pad_key(pad),
                )
            )
    if errors:
        return finish(INDETERMINATE)

    net = str(nets["from"])
    coverage["net"] = net

    # -- board-level evidence gaps -------------------------------------------
    # 550A: the parser now keeps ARC records, so the question is no longer
    # 「does the board have any」 but 「does *this net* have one」. An arc of
    # another net cannot change this net's copper, so it must not escalate.
    same_net_arcs = list(board.net(net).arcs)
    copper_ids = {info.layer_id for info in read_stackup(board).copper_layers}
    # Every same-net arc lands in exactly one bucket, and the three answer
    # different questions: blocking (this is copper we cannot measure — the
    # negative verdict may not be stated as final), unclassified (this batch
    # cannot say whether that layer is copper at all — also not final), and
    # non-copper (the board's own layer table says so — a certain absence, so
    # it is disclosed and never escalates).
    blocking_arcs: list[ArcGeometry] = []
    unclassified_arcs: list[ArcGeometry] = []
    non_copper_arcs: list[ArcGeometry] = []
    for arc in same_net_arcs:
        if arc.layer_id is None or not copper_ids or arc.layer_id in copper_ids:
            blocking_arcs.append(arc)
            continue
        # 「not in the copper set」 is not the same fact as 「not copper」: a
        # layer the table does not name (or names as copper outside the
        # stackup) leaves the arc's copper unplaced, which is an evidence gap.
        # Only a layer the board defines **and calls non-copper** may be
        # dismissed by name.
        known = board.layer(arc.layer_id)
        if known is not None and not known.is_copper:
            non_copper_arcs.append(arc)
        else:
            unclassified_arcs.append(arc)
    if blocking_arcs:
        unknown.append(
            _issue(
                "arc_geometry_unsupported",
                "this net carries ARC copper whose geometry is not modelled — the "
                "record's ``angle`` has no verified unit, so no path may be claimed "
                "through it and a negative answer cannot be stated as final",
                count=len(blocking_arcs),
                ids=[arc.id for arc in blocking_arcs],
            )
        )
    if unclassified_arcs:
        unknown.append(
            _issue(
                "arc_layer_unclassified",
                "this net names ARC records on layer ids this batch cannot classify: "
                "the board either does not define that layer or names it as copper "
                "outside the copper stackup, so its copper cannot be placed — a "
                "negative answer cannot be stated as final",
                count=len(unclassified_arcs),
                ids=[arc.id for arc in unclassified_arcs],
                layers=_sorted_layers(
                    {
                        int(arc.layer_id)
                        for arc in unclassified_arcs
                        if isinstance(arc.layer_id, int)
                    }
                ),
            )
        )
    if non_copper_arcs:
        ignored.append(
            _issue(
                "arc_on_non_copper_layer",
                "this net names ARC records on layers that are not copper; they "
                "cannot join a copper path",
                count=len(non_copper_arcs),
                ids=[arc.id for arc in non_copper_arcs],
            )
        )
    # Legacy fallback: a hand-built board (or a caller's own stats) that still
    # reports ARC as unconsumed has no modelled records at all, so nothing can
    # be attributed to a net and the board-level statement is the honest one.
    legacy_arcs = int(board.stats.unconsumed_types.get("ARC", 0))
    if legacy_arcs:
        unknown.append(
            _issue(
                "arc_copper_unparsed",
                "the board reports ARC records as unparsed, so an arc could join "
                "these pads and a negative answer cannot be stated as final",
                count=legacy_arcs,
            )
        )
    stackup = read_stackup(board)
    if not stackup.copper_layers:
        unknown.append(
            _issue(
                "copper_layers_unknown",
                "the document names no copper layer at all (no LAYER_PHYS and no "
                "usable LAYER table), so via and through-hole copper cannot be "
                "placed on any layer",
            )
        )
    else:
        plane_layers = [
            info.layer_id for info in stackup.copper_layers if info.layer_type == "PLANE"
        ]
        if plane_layers:
            ignored.append(
                _issue(
                    "plane_excluded",
                    "PLANE layers are copper but are excluded from the path by "
                    "contract; their copper reaches this reader as POUR/POURED "
                    "records when the file stores it",
                    layers=plane_layers,
                )
            )
    netless_tracks = sum(1 for track in board.tracks if not track.net)
    netless_vias = sum(1 for via in board.vias if not via.net)
    if netless_tracks or netless_vias:
        unknown.append(
            _issue(
                "netless_copper",
                "the board carries track/via copper with no net; it could be the "
                "missing bridge, so a negative answer cannot be stated as final",
                tracks=netless_tracks,
                vias=netless_vias,
            )
        )
    other_unconsumed = {
        str(rtype): int(count)
        for rtype, count in sorted(board.stats.unconsumed_types.items())
        if rtype != "ARC" and count
    }
    if other_unconsumed:
        ignored.append(
            _issue(
                "non_copper_records_unconsumed",
                "record types the board walk does not consume and that carry no "
                "copper per docs/epru-format.md; listed so nothing disappears "
                "silently",
                types=other_unconsumed,
            )
        )

    # -- the graph -----------------------------------------------------------
    geo = board.net(net)
    vertices, alignment_error = _build_vertices(
        board, geo, net, unknown, ignored, coverage
    )
    if alignment_error is not None:  # pragma: no cover
        errors.append(
            _issue(
                alignment_error,
                "the measured shapes could not be paired with their records, so no "
                "path row could be attributed honestly",
            )
        )
        return finish(INDETERMINATE)

    index_by_id: dict[str, int] = {}
    for index, vertex in enumerate(vertices):
        index_by_id.setdefault(vertex.id, index)
    endpoints: list[int] = []
    for side in ("from", "to"):
        key = _pad_key(pads[side])
        index = index_by_id.get(key)
        if index is None:  # pragma: no cover - excluded endpoints are refused above
            errors.append(
                _issue(
                    "endpoint_not_in_graph",
                    "the endpoint pad did not reach the graph; the question cannot "
                    "be answered",
                    side=side,
                    pad=key,
                )
            )
        else:
            endpoints.append(index)
    if errors:
        return finish(INDETERMINATE)

    adjacency: list[list[int]] = [[] for _ in vertices]
    edges = 0
    for first in range(len(vertices)):
        shape_a = vertices[first].shape
        for second in range(first + 1, len(vertices)):
            shape_b = vertices[second].shape
            if shape_a.bbox is None or shape_b.bbox is None:
                continue
            if _bbox_distance(shape_a.bbox, shape_b.bbox) > _TOUCH_EPS:
                continue
            if not _touching(shape_a, shape_b):
                continue
            kinds = {shape_a.kind, shape_b.kind}
            if kinds == {"pad", "via"}:
                pad_vertex = vertices[first] if shape_a.kind == "pad" else vertices[second]
                via_vertex = vertices[second] if shape_a.kind == "pad" else vertices[first]
                unknown.append(
                    _issue(
                        "pad_via_contact",
                        "a pad touches a via directly (via-in-pad). The host's own "
                        "connectivity semantics for that pair are unconfirmed, so it "
                        "is disclosed and NOT used as an edge",
                        pad=pad_vertex.id,
                        via=via_vertex.id,
                        layers=_sorted_layers(shape_a.layers & shape_b.layers),
                    )
                )
                continue
            adjacency[first].append(second)
            adjacency[second].append(first)
            edges += 1
    coverage["graph"]["edges"] = edges

    start, goal = endpoints[0], endpoints[1]
    if start == goal:
        walked = [start]
    else:
        walked = _walk(adjacency, start, goal)
    if walked:
        path = [_path_row(vertices[index], net) for index in walked]
        return finish(CONNECTED, path)
    return finish(INDETERMINATE if unknown else NOT_PROVEN)
