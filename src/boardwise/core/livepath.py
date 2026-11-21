"""Online multi-hop copper path over ``pcb.path_probe`` evidence (task 562B1).

The 562 contract asks a question 559 cannot: *are these two ``REF.PAD`` ends
joined by an ordered, hop-by-hop sourced copper path?* 562A's ``pcb.path_probe``
is the collector — typed ``nodes[]``, **directed** ``edges[]``, ``seeds[]``,
``frontier[]``, ``coverage``, ``unknown``/``ignored``/``errors`` — and it carries
no verdict on purpose. This module is the other half: a pure function over that
response that builds the legal graph, refuses what is not proof, walks the graph
and answers in three states. No host call, no bridge, no file, no clipboard.

**Only reciprocal adjacency is proof (562 §5.2).** ``getAdjacentPrimitives`` is
read once per direction and the two answers are stored as two edges, so a
``Line`` that names a neighbour which does not name it back is
``unknown:non-reciprocal-adjacency`` and never a hop. This is conservative by
design: it cannot turn a directionality of the host API into an undirected copper
claim. Endpoint ``pad-direct`` and ``pad-direct-other-pad`` use the pad's own
direct answer and therefore need no fabricated reverse call (562 §5.2).

**What can appear in a path.** Only ``Line`` and ``Via`` vertices plus the two
query ends, every one carrying a non-empty net that equals both ends' net. ``Arc``
is ``unknown:arc-unverified`` (no real-board sample pins its adjacency identity,
562 §4.8), ``Pad``↔``Via`` is ``unknown:pad-via-contact`` (§4.7), poured copper is
``ignored:pour-excluded`` (§4.5), ``Polyline``/``Region``/anything else that could
bridge is ``unknown:unsupported-adjacent-type`` (§4.6) and an intermediate pad is
``unknown:intermediate-pad-unsupported`` (§4.4). ``ignored`` is what this contract
excludes by decision and never escalates; ``unknown`` is what could change a
negative answer.

**Three states, and the third one is the honest default.** ``CONNECTED`` requires
a walk whose every hop is sourced; an unrelated gap does not overturn it but is
still disclosed and sets ``coverage.partial``. ``NOT_PROVEN`` needs the whole
reachable legal graph to be exhausted *and* no unknown, no error, no per-call or
graph truncation, no budget exhaustion, no unexpanded ``frontier`` and both ends
complete — and even then it means 「在这张已证图上没有找到路径」, **not** 「开路」.
Anything else is ``INDETERMINATE``.

**``coverage.complete`` is a hint, never a premise.** Every truncation and every
gap is re-derived from the individual readings (the same stance 559 took), so the
connector's one summary bit is never accepted in place of them and cannot on its
own let a negative through.

**Determinism.** Nodes are keyed by ``(type, primitiveId)``; the directed edge
list is normalised into ``(from, to, callIndex, hostOrder)`` order before anything
is derived, so the result never depends on the order the collector happened to
emit edges in; neighbours are visited in ``(type, primitiveId)`` order; hops carry
the host's own direction in ``evidence`` while ``hop.from``/``hop.to`` follow the
path; JSON is written with ``sort_keys=True``. The same payload therefore projects
to byte-identical JSON.
"""

from __future__ import annotations

import copy
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Mapping

__all__ = [
    "CONNECTED",
    "INDETERMINATE",
    "NOT_PROVEN",
    "SCHEMA",
    "LivePathResult",
    "project_live_path",
]

#: The JSON contract this result projects into. Bumped only with a contract
#: change; readers pin it.
SCHEMA = "boardwise.pcbLivePath/1"

CONNECTED = "CONNECTED"
NOT_PROVEN = "NOT_PROVEN"
INDETERMINATE = "INDETERMINATE"

#: The two ends, in the order the probe reports them.
_ENDS: tuple[str, str] = ("from", "to")

#: Types that can be a query end.
_ENDPOINT_PAD_TYPES = frozenset({"Pad", "ComponentPad"})

#: Types this contract may walk through (562 §4.8 keeps ``Arc`` out).
_WALKABLE_TYPES = frozenset({"Line", "Via"})

#: Deliberate exclusions, never escalated (562 §4.5).
_POUR_TYPES = frozenset({"Fill", "Pour", "Poured", "PLANE"})

_METHOD_DIRECT = "getConnectedPrimitives"
_METHOD_ADJACENT = "getAdjacentPrimitives"

_KIND_PAD_DIRECT = "pad-direct"
_KIND_PAD_PAIR = "pad-direct-other-pad"
_KIND_ADJACENT = "adjacent"
_KIND_ADJACENT_PAD = "adjacent-to-endpoint-pad"

_KINDS = frozenset({_KIND_PAD_DIRECT, _KIND_PAD_PAIR, _KIND_ADJACENT, _KIND_ADJACENT_PAD})

#: ``(type, primitiveId)`` — an id alone does not say what it is (562 §4.1).
Key = tuple[str, str]

#: What the evidence covers and what it refuses to answer, spelled out.
_SCOPE: dict[str, Any] = {
    "supports": [
        "both query ends resolved by one bounded scan, direct.ok and one shared non-empty net",
        "pad-direct: a query end's own getConnectedPrimitives(false) naming a Line, used undirected",
        "pad-direct-other-pad: one query end directly naming the other end's pad, used undirected",
        "adjacent: Line/Via pairs where both sides' getAdjacentPrimitives() name each other",
        "adjacent-to-endpoint-pad: a Line naming a query end, paired with that end's pad-direct",
        "shortest walk by hop count, every hop carrying its own callIndex and hostOrder",
    ],
    "excludes": [
        "Arc as proof or as a followed vertex (no real-board adjacency sample) — unknown:arc-unverified",
        "Pad↔Via contact — unknown:pad-via-contact, never a seed and never a hop",
        "poured copper Fill/Pour/Poured/PLANE — ignored:pour-excluded",
        "Polyline/Region/other bridging types — unknown:unsupported-adjacent-type",
        "any pad other than the two query ends — unknown:intermediate-pad-unsupported",
        "a net name, a shared id set or an id without a type as connectivity evidence",
        "other nets — ignored:other-net, never traversed",
        "DRC, trace length, impedance, current, clearance and electrical rules",
        "NOT_PROVEN as an open circuit; V3 or other board families",
    ],
    "order": "neighbours by (type, primitiveId); shortest hop count; canonical JSON with sort_keys",
}


def _text(value: Any) -> str | None:
    """A non-empty string, or ``None`` — never a coerced ``""``."""
    return value if isinstance(value, str) and value else None


def _count(value: Any) -> int | None:
    """A non-negative int, or ``None`` when the counter was not a number."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def _issue(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """One ``unknown`` / ``ignored`` / ``errors`` row; ``sort_keys`` sorts it."""
    row: dict[str, Any] = {"code": code, "message": message}
    for key, value in extra.items():
        row[key] = value
    return row


def _ref_of(key: Key) -> dict[str, str]:
    """One vertex reference, in the order the schema writes it."""
    return {"primitiveId": key[1], "type": key[0]}


def _key_of(value: Any) -> Key | None:
    """Read ``{primitiveId, type}`` into the node key, or ``None``."""
    if not isinstance(value, Mapping):
        return None
    primitive_id = _text(value.get("primitiveId"))
    kind = _text(value.get("type"))
    if primitive_id is None or kind is None:
        return None
    return (kind, primitive_id)


def _end_query(raw: Any) -> dict[str, Any]:
    """One end's identity as ``query`` writes it (nulls where nothing was read)."""
    row = raw if isinstance(raw, Mapping) else {}
    ref = row.get("ref") if isinstance(row.get("ref"), Mapping) else {}
    pad = row.get("pad") if isinstance(row.get("pad"), Mapping) else {}
    return {
        "designator": _text(ref.get("designator")),
        "pad": _text(ref.get("pad")),
        "primitiveId": _text(pad.get("primitiveId")),
        "type": _text(pad.get("type")),
        "net": _text(pad.get("net")),
    }


@dataclass(frozen=True)
class _End:
    """One query end after every prerequisite held: pad vertex and its net."""

    side: str
    pad: Key
    net: str


@dataclass(frozen=True)
class _Hop:
    """One undirected proof between two vertices, with the host's own directions.

    ``a``/``b`` are in ``(type, primitiveId)`` order; ``evidence`` holds the
    original directed rows, each still pointing the way the host answered.
    """

    a: Key
    b: Key
    kind: str
    evidence: tuple[dict[str, Any], ...]

    def order(self) -> tuple[Any, ...]:
        """The one order hops are compared in — never the collector's."""
        return (
            _KIND_PRIORITY.get(self.kind, 99),
            self.kind,
            tuple((row.get("callIndex"), row.get("hostOrder")) for row in self.evidence),
            self.a,
            self.b,
        )


#: Which proof kind a hop prefers when two kinds describe the same pair.
_KIND_PRIORITY = {
    _KIND_PAD_DIRECT: 0,
    _KIND_PAD_PAIR: 0,
    _KIND_ADJACENT_PAD: 1,
    _KIND_ADJACENT: 2,
}


@dataclass
class LivePathResult:
    """The answer to one ``pcb.path_probe`` response, and its JSON form.

    ``unknown`` is never a 「maybe connected」: it is what could change a
    **negative** verdict, and beside a proven path it still shows up (with
    ``coverage.partial`` true). ``ignored`` is the opposite — what this contract
    excludes by decision — and it is never escalated. ``path``/``hops`` are the
    positive evidence and are empty whenever the walk did not hold, so no verdict
    can be built on a graph the payload did not establish.
    """

    verdict: str = INDETERMINATE
    source: dict[str, Any] = field(default_factory=dict)
    query: dict[str, Any] = field(default_factory=dict)
    path: list[dict[str, Any]] = field(default_factory=list)
    hops: list[dict[str, Any]] = field(default_factory=list)
    hop_count: int = 0
    via_count: int = 0
    unknown: list[Any] = field(default_factory=list)
    ignored: list[Any] = field(default_factory=list)
    errors: list[Any] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    scope: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(_SCOPE))
    schema: str = SCHEMA

    def as_dict(self) -> dict[str, Any]:
        """The :data:`SCHEMA` payload. Every array is present, empty or not."""
        return {
            "schema": self.schema,
            "verdict": self.verdict,
            "source": dict(self.source),
            "query": copy.deepcopy(self.query),
            "path": [dict(row) for row in self.path],
            "hops": copy.deepcopy(self.hops),
            "hopCount": self.hop_count,
            "viaCount": self.via_count,
            "unknown": copy.deepcopy(self.unknown),
            "ignored": copy.deepcopy(self.ignored),
            "errors": copy.deepcopy(self.errors),
            "coverage": copy.deepcopy(self.coverage),
            "scope": copy.deepcopy(self.scope),
        }

    def to_json(self, *, indent: int | None = None) -> str:
        """The payload as canonical JSON (sorted keys, no NaN)."""
        return json.dumps(
            self.as_dict(),
            sort_keys=True,
            ensure_ascii=False,
            indent=indent,
            allow_nan=False,
        )


class _Gaps:
    """Every gap the projection finds, kept in the shape it will be reported in."""

    def __init__(self) -> None:
        self.hard: list[dict[str, Any]] = []
        self.unknown_rows: list[dict[str, Any]] = []
        self.ignored_rows: list[dict[str, Any]] = []
        self.connector_unknown: list[Any] = []
        self.connector_ignored: list[Any] = []
        self.connector_errors: list[Any] = []
        self.truncation_codes: list[str] = []

    def refuse(self, code: str, message: str, **extra: Any) -> None:
        """A prerequisite that does not hold: no answer but INDETERMINATE."""
        self.hard.append(_issue(code, message, **extra))

    def unknown(self, code: str, message: str, **extra: Any) -> None:
        """A reading that could change a negative answer."""
        self.unknown_rows.append(_issue(code, message, **extra))

    def truncation(self, code: str, message: str, **extra: Any) -> None:
        """A cap or budget the collector hit: never a complete traversal."""
        if code not in self.truncation_codes:
            self.truncation_codes.append(code)
        self.unknown_rows.append(_issue(code, message, budget="truncation", **extra))

    def ignore(self, code: str, message: str, **extra: Any) -> None:
        """A deliberate exclusion — never escalated to a gap."""
        self.ignored_rows.append(_issue(code, message, **extra))

    def has_gap(self) -> bool:
        """Whether a negative answer would be a guess rather than a fact."""
        return bool(
            self.hard
            or self.unknown_rows
            or self.connector_unknown
            or self.connector_errors
        )


def _check_resolution(raw: Mapping[str, Any], side: str, gaps: _Gaps) -> None:
    """One end's ``resolution`` block: a unique pad, and nothing withheld."""
    resolution = raw.get("resolution")
    if not isinstance(resolution, Mapping):
        gaps.unknown(
            "resolution-missing",
            f"{side}: the probe reported no resolution block, so an absent pad is not a fact",
            end=side,
        )
        return
    read_errors = resolution.get("readErrors")
    if not isinstance(read_errors, list):
        gaps.unknown(
            "resolution-read-errors-unreadable",
            f"{side}: resolution.readErrors is {type(read_errors).__name__}, not an array",
            end=side,
        )
    elif read_errors:
        gaps.unknown(
            "resolution-read-errors",
            f"{side}: {len(read_errors)} component/pad read(s) failed during the scan",
            end=side,
            readErrors=[str(line) for line in read_errors],
        )
    if resolution.get("truncated") is not False:
        gaps.unknown(
            "resolution-truncated",
            f"{side}: the component scan did not report truncated=false",
            end=side,
            truncated=resolution.get("truncated"),
        )
    if resolution.get("complete") is not True:
        gaps.unknown(
            "resolution-incomplete",
            f"{side}: the component scan did not report complete=true",
            end=side,
            complete=resolution.get("complete"),
        )
    if _count(resolution.get("matches")) != 1:
        gaps.refuse(
            "pad-not-unique",
            f"{side}: {resolution.get('matches')!r} component pads answered this REF.PAD — "
            "a walk needs exactly one",
            end=side,
            matches=resolution.get("matches"),
        )
    candidates = resolution.get("candidates")
    if isinstance(candidates, list):
        unique = sorted({c for c in candidates if _text(c)})
        if len(unique) > 1:
            gaps.refuse(
                "pad-not-unique",
                f"{side}: {len(unique)} distinct pad primitive ids were candidates — "
                "taking one would be a guess",
                end=side,
                candidates=unique,
            )


def _read_end(raw: Any, side: str, gaps: _Gaps) -> _End | None:
    """One end: resolved, fully identified, ``direct.ok`` and a non-empty net."""
    if not isinstance(raw, Mapping):
        gaps.refuse(
            "end-missing",
            f"{side}: the probe reported no end object ({type(raw).__name__})",
            end=side,
        )
        return None
    status = raw.get("status")
    if status != "resolved":
        detail = raw.get("error") if isinstance(raw.get("error"), str) else None
        gaps.refuse(
            "end-not-resolved",
            f"{side}: status is {status!r}" + (f" — {detail}" if detail else ""),
            end=side,
            status=status if isinstance(status, str) else None,
        )
        return None
    pad = raw.get("pad") if isinstance(raw.get("pad"), Mapping) else {}
    primitive_id = _text(pad.get("primitiveId"))
    kind = _text(pad.get("type"))
    net = _text(pad.get("net"))
    if primitive_id is None:
        gaps.refuse(
            "pad-id-missing",
            f"{side}: the resolved pad has no readable primitive id, so no walk can start or end at it",
            end=side,
        )
        return None
    if kind is None or kind not in _ENDPOINT_PAD_TYPES:
        gaps.refuse(
            "pad-type-missing",
            f"{side}: the resolved pad reports type {kind!r}, which is not a Pad/ComponentPad — "
            "its vertex identity is incomplete",
            end=side,
            type=kind,
        )
        return None
    if net is None:
        gaps.refuse(
            "net-missing",
            f"{side}: the resolved pad reports no net — every vertex of a walk carries the net",
            end=side,
        )
        return None
    direct = raw.get("direct")
    if not isinstance(direct, Mapping):
        gaps.refuse(
            "direct-missing",
            f"{side}: the probe reported no direct getConnectedPrimitives(false) answer",
            end=side,
        )
        return None
    if direct.get("ok") is not True:
        detail = direct.get("error") if isinstance(direct.get("error"), str) else None
        gaps.refuse(
            "direct-not-ok",
            f"{side}: direct.ok is {direct.get('ok')!r}" + (f" — {detail}" if detail else ""),
            end=side,
        )
        return None
    _check_resolution(raw, side, gaps)
    return _End(side=side, pad=(kind, primitive_id), net=net)


def _read_graph_nodes(
    box: Mapping[str, Any],
    query_net: str | None,
    endpoints: dict[str, _End],
    gaps: _Gaps,
) -> dict[Key, dict[str, Any]]:
    """Every vertex the payload names, keyed by ``(type, primitiveId)``.

    A candidate whose id, type or net will not read is not a vertex (562 §4.2);
    another net is ``ignored:other-net`` and is never traversed (562 §4.3).
    """
    nodes: dict[Key, dict[str, Any]] = {}
    for end in endpoints.values():
        nodes[end.pad] = {"net": end.net, "traversable": query_net is None or end.net == query_net}

    raw_nodes = box.get("nodes")
    if not isinstance(raw_nodes, list):
        gaps.unknown(
            "nodes-unreadable",
            f"nodes is {type(raw_nodes).__name__}, not an array — the graph has no vertices",
        )
        raw_nodes = []
    for index, row in enumerate(raw_nodes):
        key = _key_of(row)
        if key is None:
            gaps.unknown(
                "node-identity-unreadable",
                "a node row carries no readable (primitiveId, type) pair, so it is not a vertex",
                nodeIndex=index,
            )
            continue
        if key in nodes:
            continue
        net = _text(row.get("net")) if isinstance(row, Mapping) else None
        if net is None:
            gaps.unknown(
                "node-net-missing",
                f"{key[0]} {key[1]} reports no net — a vertex without a net cannot be walked",
                **{"from": _ref_of(key)},
            )
            continue
        if query_net is not None and net != query_net:
            gaps.ignore(
                "other-net",
                f"{key[0]} {key[1]} is on net {net!r}, not the query net {query_net!r}; it is not traversed",
                **{"from": _ref_of(key), "net": net},
            )
            nodes[key] = {"net": net, "traversable": False}
            continue
        nodes[key] = {"net": net, "traversable": True}
    return nodes


def _read_edges(box: Mapping[str, Any], gaps: _Gaps) -> list[dict[str, Any]]:
    """Every directed edge, validated and put in the one canonical order.

    The collector's emission order is a host detail; deriving anything from it
    would make the projection depend on it (562 §5.3), so the list is sorted on
    ``(from, to, callIndex, hostOrder)`` after the rows are read.
    """
    raw_edges = box.get("edges")
    if not isinstance(raw_edges, list):
        gaps.unknown(
            "edges-unreadable",
            f"edges is {type(raw_edges).__name__}, not an array — there is no graph to walk",
        )
        return []
    directed: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for index, row in enumerate(raw_edges):
        if not isinstance(row, Mapping):
            gaps.unknown(
                "edge-unreadable",
                f"an edge row is {type(row).__name__}, not an object",
                edgeIndex=index,
            )
            continue
        source = _key_of(row.get("from"))
        target = _key_of(row.get("to"))
        if source is None or target is None:
            gaps.unknown(
                "edge-ref-unreadable",
                "an edge names a from/to that has no readable (primitiveId, type) pair",
                edgeIndex=index,
            )
            continue
        method = _text(row.get("method"))
        kind = _text(row.get("kind"))
        call_index = _count(row.get("callIndex"))
        host_order = _count(row.get("hostOrder"))
        location = {"from": _ref_of(source), "to": _ref_of(target), "edgeIndex": index}
        if method not in {_METHOD_DIRECT, _METHOD_ADJACENT}:
            gaps.unknown(
                "edge-method-unknown",
                f"the edge names method {method!r}, which is neither of the two read seams",
                method=method,
                **location,
            )
            continue
        if kind not in _KINDS:
            gaps.unknown(
                "edge-kind-unknown",
                f"the edge names kind {kind!r}, which this contract does not classify",
                kind=kind,
                **location,
            )
            continue
        if call_index is None or host_order is None:
            gaps.unknown(
                "edge-call-index-missing",
                "the edge carries no non-negative callIndex/hostOrder, so no hop could be traced to a call",
                callIndex=row.get("callIndex"),
                hostOrder=row.get("hostOrder"),
                **location,
            )
            continue
        if source == target:
            gaps.ignore(
                "self-reference",
                f"{source[0]} {source[1]} names itself; a self edge is not a hop",
                **location,
            )
            continue
        signature = (source, target, method, kind, call_index, host_order)
        if signature in seen:
            gaps.ignore(
                "duplicate-edge",
                "a second, identical edge row was dropped; the first one is kept as the evidence",
                method=method,
                kind=kind,
                callIndex=call_index,
                hostOrder=host_order,
                **location,
            )
            continue
        seen.add(signature)
        directed.append(
            {
                "from": source,
                "to": target,
                "method": method,
                "kind": kind,
                "callIndex": call_index,
                "hostOrder": host_order,
            }
        )
    directed.sort(
        key=lambda row: (
            row["from"],
            row["to"],
            row["method"],
            row["kind"],
            row["callIndex"],
            row["hostOrder"],
        )
    )
    return directed


def _evidence(row: Mapping[str, Any]) -> dict[str, Any]:
    """The directed edge exactly as the host answered it — never re-oriented."""
    return {
        "from": _ref_of(row["from"]),
        "to": _ref_of(row["to"]),
        "method": row["method"],
        "kind": row["kind"],
        "callIndex": row["callIndex"],
        "hostOrder": row["hostOrder"],
    }


def _reclassify(
    key: Key, location: dict[str, Any], gaps: _Gaps, method: str, kind: str
) -> None:
    """Name why one endpoint-adjacent candidate is not a hop (562 §4.4–§4.8)."""
    other = _ref_of(key)
    extra = {**location, "method": method, "kind": kind}
    if key[0] == "Arc":
        gaps.unknown(
            "arc-unverified",
            "an Arc is not proof under this contract: no real-board sample pins its adjacency "
            "identity (562 §4.8), so it is neither evidence nor a followed vertex",
            **extra,
        )
    elif key[0] == "Via":
        gaps.unknown(
            "pad-via-contact",
            "a pad meets a Via directly; that contact is not a claim this contract may make (562 §4.7)",
            other=other,
            **extra,
        )
    elif key[0] in _POUR_TYPES:
        gaps.ignore(
            "pour-excluded",
            f"{key[0]} is poured copper — excluded on purpose, like the offline 550 model (562 §4.5)",
            other=other,
            **extra,
        )
    elif key[0] in _ENDPOINT_PAD_TYPES:
        gaps.unknown(
            "intermediate-pad-unsupported",
            "a pad that is not one of the two query ends is not expanded in this batch (562 §4.4)",
            other=other,
            **extra,
        )
    else:
        gaps.unknown(
            "unsupported-adjacent-type",
            f"{key[0]} could bridge copper but this contract has no proof rule for it (562 §4.6)",
            other=other,
            **extra,
        )


def _build_hops(
    directed: list[dict[str, Any]],
    nodes: dict[Key, dict[str, Any]],
    ends: dict[str, _End],
    gaps: _Gaps,
) -> list[_Hop]:
    """Classify every directed edge, then keep only the reciprocal proofs."""
    endpoint_keys = frozenset(end.pad for end in ends.values())
    pad_direct: dict[tuple[Key, Key], dict[str, Any]] = {}
    pad_pairs: list[dict[str, Any]] = []
    adjacent: dict[tuple[Key, Key], dict[str, Any]] = {}
    pending_pairs: list[dict[str, Any]] = []
    adjacent_to_pad: list[dict[str, Any]] = []

    for row in directed:
        source, target = row["from"], row["to"]
        location = {"from": _ref_of(source), "to": _ref_of(target)}
        source_node = nodes.get(source)
        target_node = nodes.get(target)
        if source_node is None or target_node is None:
            missing = "from" if source_node is None else "to"
            gaps.unknown(
                "edge-node-missing",
                f"the edge names a {missing} vertex that no node row establishes; it cannot be a hop",
                missing=missing,
                method=row["method"],
                kind=row["kind"],
                **location,
            )
            continue
        if not source_node["traversable"] or not target_node["traversable"]:
            gaps.ignore(
                "other-net",
                "the edge touches a vertex outside the query net; it is not traversed",
                net=target_node["net"] if not target_node["traversable"] else source_node["net"],
                method=row["method"],
                kind=row["kind"],
                **location,
            )
            continue
        if source_node["net"] != target_node["net"]:
            gaps.unknown(
                "edge-net-mismatch",
                f"the edge joins net {source_node['net']!r} to net {target_node['net']!r} — "
                "a cross-net edge is not a hop and not a short circuit to report",
                fromNet=source_node["net"],
                toNet=target_node["net"],
                method=row["method"],
                kind=row["kind"],
                **location,
            )
            continue

        kind, method = row["kind"], row["method"]
        expected_method = _METHOD_DIRECT if kind in {_KIND_PAD_DIRECT, _KIND_PAD_PAIR} else _METHOD_ADJACENT
        if method != expected_method:
            gaps.unknown(
                "edge-method-mismatch",
                f"a {kind} edge must come from {expected_method}(), not {method}()",
                method=method,
                kind=kind,
                **location,
            )
            continue

        if kind == _KIND_PAD_DIRECT:
            if source not in endpoint_keys:
                gaps.unknown(
                    "edge-endpoint-unexpected",
                    "a pad-direct edge must start at one of the two query ends, whose own "
                    "getConnectedPrimitives(false) answered it",
                    method=method,
                    kind=kind,
                    **location,
                )
            elif target in endpoint_keys:
                gaps.unknown(
                    "pad-direct-other-pad-mismatch",
                    "one query end named the other; that is pad-direct-other-pad, not pad-direct",
                    method=method,
                    kind=kind,
                    **location,
                )
            elif target[0] == "Line":
                pad_direct[(source, target)] = row
            else:
                _reclassify(target, location, gaps, method, kind)
        elif kind == _KIND_PAD_PAIR:
            if {source, target} != endpoint_keys:
                gaps.unknown(
                    "pad-direct-other-pad-not-endpoint",
                    "a pad-direct-other-pad edge must join the two query ends and nothing else (562 §4.4)",
                    method=method,
                    kind=kind,
                    **location,
                )
            else:
                pad_pairs.append(row)
        elif kind == _KIND_ADJACENT:
            if source[0] not in _WALKABLE_TYPES or target[0] not in _WALKABLE_TYPES:
                other = target if source[0] in _WALKABLE_TYPES else source
                if other[0] == "Via":
                    _reclassify(other, location, gaps, method, kind)
                elif other[0] in _ENDPOINT_PAD_TYPES:
                    gaps.unknown(
                        "adjacent-to-pad-kind-mismatch",
                        "a Line naming a pad is adjacent-to-endpoint-pad, not adjacent",
                        method=method,
                        kind=kind,
                        **location,
                    )
                else:
                    _reclassify(other, location, gaps, method, kind)
            else:
                adjacent[(source, target)] = row
        else:  # _KIND_ADJACENT_PAD
            if target not in endpoint_keys:
                gaps.unknown(
                    "pad-endpoint-unexpected",
                    "an adjacent-to-endpoint-pad edge must end at one of the two query ends (562 §4.6)",
                    method=method,
                    kind=kind,
                    **location,
                )
            elif source[0] == "Via":
                gaps.unknown(
                    "pad-via-contact",
                    "a Via meets a pad directly; that contact is not a hop under this contract (562 §4.7)",
                    other=_ref_of(source),
                    method=method,
                    kind=kind,
                    **location,
                )
            elif source[0] != "Line":
                _reclassify(source, location, gaps, method, kind)
            else:
                # Pairing is decided in a second pass: a `Pad` endpoint sorts
                # after the `Line` that names it, so looking the pad-direct row
                # up here would report a reciprocal pair as one-way whenever the
                # endpoint's type sorts late. The answer must not depend on type
                # spelling (562D HIGH-1).
                pending_pairs.append(row)

    # ---- second pass: every pad-direct answer is in hand ------------------
    for row in pending_pairs:
        target, source = row["to"], row["from"]
        if (target, source) in pad_direct:
            adjacent_to_pad.append(row)
        else:
            gaps.unknown(
                "non-reciprocal-adjacency",
                f"{source[0]} {source[1]} names pad {target[1]}, but that pad's own direct answer "
                "does not name it — one direction is not proof (562 §5.2)",
                method=row["method"],
                kind=row["kind"],
                **{"from": _ref_of(source), "to": _ref_of(target)},
            )

    hops: list[_Hop] = []
    for (pad, line), row in pad_direct.items():
        a, b = sorted((pad, line))
        hops.append(_Hop(a=a, b=b, kind=_KIND_PAD_DIRECT, evidence=(_evidence(row),)))
    for row in pad_pairs:
        a, b = sorted((row["from"], row["to"]))
        hops.append(_Hop(a=a, b=b, kind=_KIND_PAD_PAIR, evidence=(_evidence(row),)))
    for row in sorted(adjacent.values(), key=lambda r: (r["from"], r["to"], r["callIndex"], r["hostOrder"])):
        reverse = adjacent.get((row["to"], row["from"]))
        if reverse is None:
            gaps.unknown(
                "non-reciprocal-adjacency",
                f"{row['from'][0]} {row['from'][1]} names {row['to'][0]} {row['to'][1]}, which does not "
                "name it back — a one-way answer is not an undirected copper claim (562 §5.2)",
                method=row["method"],
                kind=row["kind"],
                **{"from": _ref_of(row["from"]), "to": _ref_of(row["to"])},
            )
            continue
        if row["to"] < row["from"]:
            continue  # the same pair is emitted once, from its smaller end
        a, b = row["from"], row["to"]
        evidence = (_evidence(row), _evidence(reverse))
        hops.append(_Hop(a=a, b=b, kind=_KIND_ADJACENT, evidence=evidence))
    for row in adjacent_to_pad:
        pad_row = pad_direct[(row["to"], row["from"])]
        a, b = sorted((row["to"], row["from"]))
        hops.append(
            _Hop(
                a=a,
                b=b,
                kind=_KIND_ADJACENT_PAD,
                evidence=(_evidence(pad_row), _evidence(row)),
            )
        )
    hops.sort(key=_Hop.order)
    unique: list[_Hop] = []
    proven: set[tuple[Key, Key]] = set()
    for hop in hops:
        if (hop.a, hop.b) in proven:
            continue
        proven.add((hop.a, hop.b))
        unique.append(hop)
    return unique


def _adjacency(hops: list[_Hop]) -> dict[Key, list[tuple[Key, _Hop]]]:
    """The undirected walk: both directions of every proof, first hop wins."""
    chosen: dict[tuple[Key, Key], _Hop] = {}
    for hop in hops:
        pair = (hop.a, hop.b)
        current = chosen.get(pair)
        if current is None or hop.order() < current.order():
            chosen[pair] = hop
    adjacent: dict[Key, list[tuple[Key, _Hop]]] = {}
    for (a, b), hop in chosen.items():
        adjacent.setdefault(a, []).append((b, hop))
        adjacent.setdefault(b, []).append((a, hop))
    for neighbours in adjacent.values():
        neighbours.sort(key=lambda item: (item[0][0], item[0][1], item[1].order()))
    return adjacent


def _walk(
    adjacent: dict[Key, list[tuple[Key, _Hop]]], start: Key, target: Key
) -> tuple[list[Key], list[_Hop], set[Key]]:
    """Breadth-first, neighbours in ``(type, primitiveId)`` order, shortest path."""
    seen: set[Key] = {start}
    previous: dict[Key, tuple[Key, _Hop]] = {}
    queue: deque[Key] = deque([start])
    while queue:
        current = queue.popleft()
        for neighbour, hop in adjacent.get(current, ()):
            if neighbour in seen:
                continue
            seen.add(neighbour)
            previous[neighbour] = (current, hop)
            queue.append(neighbour)
    if target not in seen:
        return [], [], seen
    chain: list[Key] = [target]
    hops: list[_Hop] = []
    while chain[-1] != start:
        parent, hop = previous[chain[-1]]
        hops.append(hop)
        chain.append(parent)
    chain.reverse()
    hops.reverse()
    return chain, hops, seen


def _check_coverage(box: Mapping[str, Any], gaps: _Gaps) -> dict[str, Any]:
    """Re-derive every truncation and gap from the readings, never from the bit."""
    coverage = box.get("coverage")
    if not isinstance(coverage, Mapping):
        gaps.unknown("coverage-missing", "the response carried no coverage block")
        return {}
    if coverage.get("complete") is not True:
        gaps.unknown(
            "coverage-incomplete",
            "coverage.complete is not true — the collector itself says something was withheld",
            complete=coverage.get("complete"),
        )
    scan = coverage.get("scan")
    if not isinstance(scan, Mapping):
        gaps.unknown("coverage-scan-missing", "coverage.scan is not an object")
    else:
        if scan.get("truncated") is not False:
            gaps.truncation(
                "coverage-scan-truncated",
                "coverage.scan.truncated is not false — the component walk was capped",
                truncated=scan.get("truncated"),
            )
        if scan.get("complete") is not True:
            gaps.unknown(
                "coverage-scan-incomplete",
                "coverage.scan.complete is not true",
                complete=scan.get("complete"),
            )
        read_errors = _count(scan.get("readErrors")) or 0
        if read_errors:
            gaps.unknown(
                "coverage-scan-read-errors",
                f"coverage.scan.readErrors is {read_errors}",
                readErrors=read_errors,
            )
    direct = coverage.get("direct")
    if isinstance(direct, Mapping):
        truncated = direct.get("truncated")
        if isinstance(truncated, Mapping):
            for side in _ENDS:
                if side in truncated and truncated.get(side) is not False:
                    gaps.truncation(
                        "coverage-direct-truncated",
                        f"coverage.direct.truncated.{side} is not false — that answer was capped",
                        end=side,
                        truncated=truncated.get(side),
                    )
    adjacent = coverage.get("adjacent")
    if isinstance(adjacent, Mapping):
        calls = _count(adjacent.get("calls"))
        cap = _count(adjacent.get("cap"))
        if calls is not None and cap is not None and calls > cap:
            gaps.truncation(
                "adjacent-calls-cap",
                f"{calls} getAdjacentPrimitives() calls exceeded the cap of {cap} — the walk was cut short",
                calls=calls,
                cap=cap,
            )
    per_call = _count(coverage.get("perCallTruncated")) or 0
    if per_call:
        gaps.truncation(
            "per-call-truncated",
            f"{per_call} direct/adjacent answer(s) exceeded the per-call cap, so candidates were withheld",
            answers=per_call,
        )
    nodes = coverage.get("nodes")
    if isinstance(nodes, Mapping) and nodes.get("truncated") is not False:
        gaps.truncation(
            "coverage-nodes-truncated",
            "coverage.nodes.truncated is not false — vertices were dropped",
            truncated=nodes.get("truncated"),
        )
    edges = coverage.get("edges")
    if isinstance(edges, Mapping) and edges.get("truncated") is not False:
        gaps.truncation(
            "coverage-edges-truncated",
            "coverage.edges.truncated is not false — candidate edges were dropped",
            truncated=edges.get("truncated"),
        )
    budget = coverage.get("budget")
    if isinstance(budget, Mapping) and budget.get("exhausted") is not None:
        gaps.truncation(
            "budget-exhausted",
            f"a fixed budget ran out: {budget.get('exhausted')!r}",
            budgetName=budget.get("exhausted"),
        )
    return copy.deepcopy(dict(coverage))


def _check_frontier(box: Mapping[str, Any], gaps: _Gaps) -> int:
    """An unexpanded frontier means the collector stopped before the graph did."""
    frontier = box.get("frontier")
    if not isinstance(frontier, list):
        gaps.unknown(
            "frontier-unreadable",
            f"frontier is {type(frontier).__name__}, not an array — whether anything was left "
            "unexpanded is unknown",
        )
        return 0
    if frontier:
        gaps.truncation(
            "frontier-unexpanded",
            f"{len(frontier)} vertex(es) were never expanded, so the reachable graph is not exhausted",
            frontier=len(frontier),
        )
    return len(frontier)


def _read_connector_rows(box: Mapping[str, Any], gaps: _Gaps) -> None:
    """Keep the collector's own ``unknown``/``ignored``/``errors`` verbatim."""
    for key, sink in (
        ("unknown", gaps.connector_unknown),
        ("ignored", gaps.connector_ignored),
    ):
        raw = box.get(key)
        if not isinstance(raw, list):
            gaps.unknown(
                f"response-{key}-unreadable",
                f"{key} is {type(raw).__name__}, not an array",
            )
            continue
        for row in raw:
            sink.append(copy.deepcopy(row) if isinstance(row, Mapping) else _issue(
                f"{key}-row-unreadable",
                f"a {key} row is {type(row).__name__}, not an object",
            ))
    raw_errors = box.get("errors")
    if not isinstance(raw_errors, list):
        gaps.unknown(
            "response-errors-unreadable",
            f"errors is {type(raw_errors).__name__}, not an array",
        )
        return
    for line in raw_errors:
        # The collector reports errors as plain lines; they are kept as sent.
        gaps.connector_errors.append(copy.deepcopy(line))


def _default_source(box: Mapping[str, Any], page: Mapping[str, Any]) -> dict[str, Any]:
    """The provenance a projection can state on its own, deterministically."""
    return {
        "host": "easyeda-pro",
        "connector": "pcb.path_probe",
        "page": {"uuid": _text(page.get("uuid")), "type": _text(page.get("type"))},
        "readOnly": box.get("readOnly") is True,
        "projection": "boardwise.core.livepath",
    }


def project_live_path(
    payload: Mapping[str, Any],
    *,
    source: Mapping[str, Any] | None = None,
) -> LivePathResult:
    """Read one ``pcb.path_probe`` response and project its path and verdict.

    Pure and read-only: the response is copied, never mutated, and no host call,
    bridge, file or clipboard is touched. A response that does not hold (wrong
    page, not read-only, an end not resolved, no readable pad id/type/net,
    ``direct.ok`` false, the same pad, differing nets, a non-unique pad) yields
    :data:`INDETERMINATE` with the reason in ``errors`` and no ``path``. Otherwise
    the legal graph is built, one-way adjacency and every unproven type are
    refused into ``unknown``/``ignored``, and the shortest reciprocal walk decides
    the verdict. ``source`` is caller provenance: omitted, a deterministic default
    is derived from the payload; supplied, it is copied in unchanged.
    """
    gaps = _Gaps()
    result = LivePathResult()
    payload_is_object = isinstance(payload, Mapping)
    box: Mapping[str, Any] = payload if payload_is_object else {}
    if not payload_is_object:
        gaps.refuse(
            "payload-not-an-object",
            f"the response is {type(payload).__name__}, not a pcb.path_probe object",
        )

    # ---- page identity: the same second gate 559 uses ---------------------
    page = box.get("page")
    page = page if isinstance(page, Mapping) else {}
    page_type = _text(page.get("type"))
    if page_type is None or page_type.strip().lower() != "pcb":
        gaps.refuse(
            "page-not-pcb",
            f"the probe did not report a PCB page (page.type {page_type!r}) — a copper walk needs "
            "the focused PCB, not 「a PCB exists」",
            pageType=page_type,
        )
    if box.get("readOnly") is not True:
        gaps.refuse(
            "not-read-only",
            f"readOnly is {box.get('readOnly')!r}; this contract only reads and only accepts a "
            "read-only probe",
        )

    result.source = (
        copy.deepcopy(dict(source)) if isinstance(source, Mapping) else _default_source(box, page)
    )
    result.query = {"from": _end_query(box.get("from")), "to": _end_query(box.get("to"))}

    # ---- the collector's own rows, verbatim ------------------------------
    _read_connector_rows(box, gaps)

    # ---- both ends --------------------------------------------------------
    ends: dict[str, _End] = {}
    for side in _ENDS:
        end = _read_end(box.get(side), side, gaps)
        if end is not None:
            ends[side] = end
    left, right = ends.get("from"), ends.get("to")
    query_net: str | None = None
    if left is not None and right is not None:
        query_net = left.net
        if left.pad == right.pad:
            gaps.refuse(
                "same-pad",
                f"both ends resolve to pad {left.pad[1]} — a pad is not on a path to itself",
                primitiveId=left.pad[1],
            )
        elif left.net != right.net:
            gaps.refuse(
                "different-net",
                f"the ends are on different nets ({left.net!r} vs {right.net!r}) — a cross-net walk "
                "is an input error, not a connection",
                fromNet=left.net,
                toNet=right.net,
            )
    elif left is not None:
        query_net = left.net
    elif right is not None:
        query_net = right.net

    # ---- coverage and frontier: re-derived, never trusted as a bit --------
    connector_coverage = _check_coverage(box, gaps)
    frontier_count = _check_frontier(box, gaps)
    nets = connector_coverage.get("nets") if isinstance(connector_coverage, Mapping) else None
    if isinstance(nets, Mapping):
        nets_from = _text(nets.get("from"))
        nets_to = _text(nets.get("to"))
        if nets_from is not None and nets_to is not None and nets_from != nets_to:
            gaps.refuse(
                "coverage-nets-differ",
                f"coverage.nets reports {nets_from!r} and {nets_to!r} — the two ends' nets must agree "
                "before anything can be CONNECTED",
                fromNet=nets_from,
                toNet=nets_to,
            )
        elif left is not None and right is not None and nets.get("same") is not True:
            gaps.refuse(
                "coverage-nets-differ",
                "coverage.nets.same is not true, so the collector did not read one shared net",
                fromNet=nets_from,
                toNet=nets_to,
            )

    # ---- the graph -------------------------------------------------------
    nodes = _read_graph_nodes(box, query_net, ends, gaps)
    directed = _read_edges(box, gaps)
    hops = _build_hops(directed, nodes, ends, gaps)

    # ---- the walk --------------------------------------------------------
    chain: list[Key] = []
    walked: list[_Hop] = []
    seen: set[Key] = set()
    started = bool(not gaps.hard and left is not None and right is not None)
    if started:
        adjacent = _adjacency(hops)
        chain, walked, seen = _walk(adjacent, left.pad, right.pad)

    path_out: list[dict[str, Any]] = []
    hops_out: list[dict[str, Any]] = []
    if chain:
        for key in chain:
            path_out.append(
                {
                    "primitiveId": key[1],
                    "type": key[0],
                    "net": nodes.get(key, {}).get("net"),
                }
            )
        for position, hop in enumerate(walked):
            parent, child = chain[position], chain[position + 1]
            hops_out.append(
                {
                    "from": _ref_of(parent),
                    "to": _ref_of(child),
                    "kind": hop.kind,
                    "evidence": [copy.deepcopy(row) for row in hop.evidence],
                }
            )
    via_count = sum(1 for key in chain if key[0] == "Via")

    # ---- the verdict -----------------------------------------------------
    endpoints_ok = left is not None and right is not None
    partial = bool(gaps.has_gap() or not started)
    if gaps.hard:
        verdict = INDETERMINATE
    elif chain:
        verdict = CONNECTED
    elif partial:
        verdict = INDETERMINATE
    else:
        verdict = NOT_PROVEN

    result.verdict = verdict
    result.path = path_out
    result.hops = hops_out
    result.hop_count = len(hops_out)
    result.via_count = via_count
    result.unknown = [*gaps.connector_unknown, *gaps.unknown_rows]
    result.ignored = [*gaps.connector_ignored, *gaps.ignored_rows]
    result.errors = [*gaps.hard, *gaps.connector_errors]
    result.coverage = {
        "connector": connector_coverage,
        "endpoints": {
            "from": left is not None,
            "to": right is not None,
            "resolved": endpoints_ok,
            "sameNet": bool(left is not None and right is not None and left.net == right.net),
            "distinctPads": bool(left is not None and right is not None and left.pad != right.pad),
        },
        "nets": {
            "from": left.net if left is not None else None,
            "to": right.net if right is not None else None,
            "same": bool(left is not None and right is not None and left.net == right.net),
        },
        "graph": {
            "nodes": len(nodes),
            "nodesExcluded": sum(1 for node in nodes.values() if not node["traversable"]),
            "edges": len(directed),
            "proofHops": len(hops),
            "proofEdges": sum(len(hop.evidence) for hop in hops),
        },
        "bfs": {
            "started": started,
            "visited": len(seen),
            "targetFound": bool(chain),
            "exhausted": started,
            "frontier": frontier_count,
            "seeds": len(box.get("seeds")) if isinstance(box.get("seeds"), list) else None,
        },
        "gaps": {
            "unknown": len(result.unknown),
            "rejectedByPython": len(gaps.unknown_rows),
            "ignored": len(result.ignored),
            "errors": len(result.errors),
            "refusals": len(gaps.hard),
            "truncation": len(gaps.truncation_codes),
        },
        "truncation": sorted(gaps.truncation_codes),
        "partial": partial,
        "complete": bool(not partial and endpoints_ok and started),
    }
    return result
