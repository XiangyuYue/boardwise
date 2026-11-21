"""Task 562B1: the pure multi-hop projection over `pcb.path_probe` evidence.

Every payload is hand-built to the exact shape `connector/src/actions.ts` reports
for `pcb.path_probe` (`page`/`readOnly`/`from`/`to`/`nodes`/`edges`/`seeds`/
`frontier`/`coverage`/`unknown`/`ignored`/`errors`), so these tests pin the
*projection* contract — endpoint prerequisites, the reciprocity rule, the
classification of what may not enter a path, the shortest walk and the three
states — and not the host.

Nothing here calls the connector, the bridge, the CLI or an editor, and no
fixture file is read. The task book's §6 negative controls are the test names.
"""

from __future__ import annotations

import copy
import json
import random

import pytest

from boardwise.core.livepath import (
    CONNECTED,
    INDETERMINATE,
    NOT_PROVEN,
    SCHEMA,
    LivePathResult,
    project_live_path,
)

PAD_FROM = "pad-r1-1"
PAD_TO = "pad-j1-1"
NET = "N1"
LN1 = "ln-1"
LN2 = "ln-2"
LN3 = "ln-3"
VIA1 = "via-1"
ARC1 = "arc-1"
FILL1 = "fill-1"
POLY1 = "poly-1"
OTHER_PAD = "pad-c9-1"

PAD_KIND = "ComponentPad"
LINE = "Line"


# --------------------------------------------------------------------------
# payload builders — one per shape the collector emits
# --------------------------------------------------------------------------
def _ref(primitive_id: str, kind: str) -> dict:
    return {"primitiveId": primitive_id, "type": kind}


def _node(primitive_id: str, kind: str, net: str | None = NET) -> dict:
    return {"primitiveId": primitive_id, "type": kind, "net": net, "layer": 1}


def _item(primitive_id: str, kind: str = LINE) -> dict:
    return _ref(primitive_id, kind)


def _direct(items: list[dict], *, ok: bool = True, error: str | None = None, truncated: bool = False) -> dict:
    if not ok:
        row: dict = {"ok": False}
        if error is not None:
            row["error"] = error
        return row
    return {
        "ok": True,
        "count": len(items),
        "ids": sorted({item["primitiveId"] for item in items}),
        "truncated": truncated,
        "items": [dict(item) for item in items],
    }


class _Host:
    """Allocates `callIndex` in call order, the way the collector numbers calls."""

    def __init__(self) -> None:
        self.calls = 0
        self.edges: list[dict] = []

    def _add(self, source: dict, target: dict, method: str, kind: str, host_order: int) -> dict:
        row = {
            "from": dict(source),
            "to": dict(target),
            "method": method,
            "kind": kind,
            "callIndex": self.calls,
            "hostOrder": host_order,
        }
        self.calls += 1
        self.edges.append(row)
        return row

    def direct(self, source: dict, target: dict, kind: str = "pad-direct", host_order: int = 0) -> dict:
        return self._add(source, target, "getConnectedPrimitives", kind, host_order)

    def adjacent(self, source: dict, target: dict, kind: str = "adjacent", host_order: int = 0) -> dict:
        return self._add(source, target, "getAdjacentPrimitives", kind, host_order)


def _end(
    designator: str,
    pad: str,
    primitive_id: str,
    *,
    net: str | None = NET,
    status: str = "resolved",
    kind: str = PAD_KIND,
    direct: dict | None = None,
    error: str | None = None,
    matches: int = 1,
    candidates: list[str] | None = None,
    read_errors: list[str] | None = None,
    truncated: bool = False,
    complete: bool = True,
) -> dict:
    row: dict = {"ref": {"designator": designator, "pad": pad}, "status": status}
    if error is not None:
        row["error"] = error
    row["resolution"] = {
        "components": 2,
        "matches": matches,
        "candidates": [primitive_id] if candidates is None else list(candidates),
        "readErrors": list(read_errors or []),
        "truncated": truncated,
        "complete": complete,
    }
    row["pad"] = (
        None
        if status != "resolved"
        else {"primitiveId": primitive_id, "padNumber": pad, "net": net, "type": kind}
    )
    row["direct"] = _direct([]) if direct is None else direct
    return row


def _coverage(
    *,
    complete: bool = True,
    nodes_truncated: bool = False,
    edges_truncated: bool = False,
    per_call_truncated: int = 0,
    adjacent_calls: int = 2,
    adjacent_cap: int = 512,
    direct_truncated: tuple[bool, bool] = (False, False),
    scan_truncated: bool = False,
    scan_complete: bool = True,
    scan_read_errors: int = 0,
    budget: dict | None = None,
    nets: tuple[str | None, str | None] = (NET, NET),
    nodes_count: int = 4,
    edges_count: int = 4,
) -> dict:
    return {
        "scan": {
            "manager": "pcb_PrimitiveComponent",
            "cap": 512,
            "components": 4,
            "truncated": scan_truncated,
            "readErrors": scan_read_errors,
            "complete": scan_complete,
        },
        "direct": {
            "perCall": 64,
            "calls": 2,
            "reported": {"from": 1, "to": 1},
            "truncated": {"from": direct_truncated[0], "to": direct_truncated[1]},
        },
        "adjacent": {"perCall": 64, "calls": adjacent_calls, "cap": adjacent_cap},
        "nodes": {"count": nodes_count, "cap": 512, "truncated": nodes_truncated},
        "edges": {"count": edges_count, "cap": 2048, "truncated": edges_truncated},
        "perCallTruncated": per_call_truncated,
        "budget": budget or {"capMs": 120000, "elapsedMs": 40, "exhausted": None},
        "nets": {
            "from": nets[0],
            "to": nets[1],
            "same": nets[0] is not None and nets[0] == nets[1],
        },
        "layerUnreadable": 0,
        "seeds": 2,
        "frontier": 0,
        "unknown": 0,
        "ignored": 0,
        "errors": 0,
        "complete": complete,
    }


def _probe(
    *,
    from_end: dict | None = None,
    to_end: dict | None = None,
    nodes: list[dict] | None = None,
    edges: list[dict] | None = None,
    seeds: list[dict] | None = None,
    frontier: list[dict] | None = None,
    coverage: dict | None = None,
    page: dict | None = None,
    read_only: bool = True,
    unknown: list | None = None,
    ignored: list | None = None,
    errors: list | None = None,
) -> dict:
    return {
        "page": {"uuid": "pcb-uuid-1", "type": "pcb"} if page is None else page,
        "readOnly": read_only,
        "from": _end("R1", "1", PAD_FROM) if from_end is None else from_end,
        "to": _end("J1", "1", PAD_TO) if to_end is None else to_end,
        "nodes": list(nodes or []),
        "edges": list(edges or []),
        "seeds": list(seeds or []),
        "frontier": list(frontier or []),
        "coverage": _coverage() if coverage is None else coverage,
        "unknown": list(unknown or []),
        "ignored": list(ignored or []),
        "errors": list(errors or []),
    }


# --------------------------------------------------------------------------
# the three positive walks, built once
# --------------------------------------------------------------------------
def _pad_direct_shared_line() -> dict:
    """Both ends' own direct answer names the same Line: a two-hop walk."""
    host = _Host()
    host.direct(_ref(PAD_FROM, PAD_KIND), _ref(LN1, LINE))
    host.direct(_ref(PAD_TO, PAD_KIND), _ref(LN1, LINE))
    return _probe(
        from_end=_end("R1", "1", PAD_FROM, direct=_direct([_item(LN1)])),
        to_end=_end("J1", "1", PAD_TO, direct=_direct([_item(LN1)])),
        nodes=[_node(LN1, LINE)],
        edges=host.edges,
    )


def _two_reciprocal_lines() -> dict:
    """Pad→Line→Line→Pad, every adjacency answered in both directions."""
    host = _Host()
    host.direct(_ref(PAD_FROM, PAD_KIND), _ref(LN1, LINE))
    host.adjacent(_ref(LN1, LINE), _ref(LN2, LINE))
    host.adjacent(_ref(LN2, LINE), _ref(LN1, LINE))
    host.direct(_ref(PAD_TO, PAD_KIND), _ref(LN2, LINE))
    return _probe(
        from_end=_end("R1", "1", PAD_FROM, direct=_direct([_item(LN1)])),
        to_end=_end("J1", "1", PAD_TO, direct=_direct([_item(LN2)])),
        nodes=[_node(LN1, LINE), _node(LN2, LINE)],
        edges=host.edges,
    )


def _line_via_line() -> dict:
    """Pad→Line→Via→Line→Pad: the via is a vertex, never a pad contact."""
    host = _Host()
    host.direct(_ref(PAD_FROM, PAD_KIND), _ref(LN1, LINE))
    host.adjacent(_ref(LN1, LINE), _ref(VIA1, "Via"))
    host.adjacent(_ref(VIA1, "Via"), _ref(LN1, LINE))
    host.adjacent(_ref(VIA1, "Via"), _ref(LN2, LINE))
    host.adjacent(_ref(LN2, LINE), _ref(VIA1, "Via"))
    host.direct(_ref(PAD_TO, PAD_KIND), _ref(LN2, LINE))
    return _probe(
        from_end=_end("R1", "1", PAD_FROM, direct=_direct([_item(LN1)])),
        to_end=_end("J1", "1", PAD_TO, direct=_direct([_item(LN2)])),
        nodes=[_node(LN1, LINE), _node(VIA1, "Via"), _node(LN2, LINE)],
        edges=host.edges,
    )


def _project(payload: dict, **kwargs) -> LivePathResult:
    return project_live_path(copy.deepcopy(payload), **kwargs)


def _ids(result: LivePathResult) -> list[str]:
    return [row["primitiveId"] for row in result.path]


def _codes(rows: list) -> set[str]:
    return {str(row.get("code")) for row in rows if isinstance(row, dict)}


def _payload_bytes(payload: dict) -> str:
    return project_live_path(payload).to_json()


# --------------------------------------------------------------------------
# §6.1 positives
# --------------------------------------------------------------------------
def test_direct_pad_line_walk_is_connected_and_keeps_host_direction() -> None:
    result = _project(_pad_direct_shared_line())

    assert result.verdict == CONNECTED
    assert _ids(result) == [PAD_FROM, LN1, PAD_TO]
    assert result.hop_count == 2
    assert result.via_count == 0
    assert result.coverage["partial"] is False, "a clean payload has no gap to disclose"
    assert result.coverage["complete"] is True
    assert result.coverage["bfs"]["visited"] == 3

    first, second = result.hops
    assert first["kind"] == "pad-direct"
    assert first["from"] == _ref(PAD_FROM, PAD_KIND)
    assert first["to"] == _ref(LN1, LINE)
    assert first["evidence"] == [{
        "from": _ref(PAD_FROM, PAD_KIND),
        "to": _ref(LN1, LINE),
        "method": "getConnectedPrimitives",
        "kind": "pad-direct",
        "callIndex": 0,
        "hostOrder": 0,
    }]
    # The hop follows the path, the evidence keeps the host's own direction.
    assert second["from"] == _ref(LN1, LINE)
    assert second["to"] == _ref(PAD_TO, PAD_KIND)
    assert second["evidence"][0]["from"] == _ref(PAD_TO, PAD_KIND)
    assert second["evidence"][0]["to"] == _ref(LN1, LINE)
    assert second["evidence"][0]["callIndex"] == 1


def test_two_reciprocal_lines_are_connected_and_carry_both_directions() -> None:
    result = _project(_two_reciprocal_lines())

    assert result.verdict == CONNECTED
    assert _ids(result) == [PAD_FROM, LN1, LN2, PAD_TO]
    assert result.hop_count == 3 == len(result.path) - 1
    assert result.via_count == 0

    middle = result.hops[1]
    assert middle["kind"] == "adjacent"
    evidence = middle["evidence"]
    assert len(evidence) == 2, "a reciprocal hop keeps both directed calls"
    assert (evidence[0]["from"], evidence[0]["to"]) == (_ref(LN1, LINE), _ref(LN2, LINE))
    assert (evidence[1]["from"], evidence[1]["to"]) == (_ref(LN2, LINE), _ref(LN1, LINE))
    assert evidence[0]["callIndex"] == 1 and evidence[0]["hostOrder"] == 0
    assert evidence[1]["callIndex"] == 2 and evidence[1]["hostOrder"] == 0
    assert all(row["method"] == "getAdjacentPrimitives" for row in evidence)


def test_line_via_line_walk_counts_the_via() -> None:
    result = _project(_line_via_line())

    assert result.verdict == CONNECTED
    assert _ids(result) == [PAD_FROM, LN1, VIA1, LN2, PAD_TO]
    assert result.hop_count == 4 == len(result.path) - 1
    assert result.via_count == 1
    assert [row["type"] for row in result.path] == ["ComponentPad", "Line", "Via", "Line", "ComponentPad"]
    assert result.coverage["graph"]["proofHops"] == 4, "one hop per proven pair, not one per direction"
    assert result.coverage["graph"]["proofEdges"] == 6


def test_pad_naming_the_other_pad_directly_is_connected() -> None:
    host = _Host()
    host.direct(_ref(PAD_FROM, PAD_KIND), _ref(PAD_TO, PAD_KIND), kind="pad-direct-other-pad")
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, direct=_direct([_item(PAD_TO, PAD_KIND)])),
        to_end=_end("J1", "1", PAD_TO, direct=_direct([_item(PAD_FROM, PAD_KIND)])),
        nodes=[],
        edges=host.edges,
    )
    result = _project(payload)

    assert result.verdict == CONNECTED
    assert _ids(result) == [PAD_FROM, PAD_TO]
    assert result.hop_count == 1
    assert result.hops[0]["kind"] == "pad-direct-other-pad"
    assert result.hops[0]["evidence"][0]["method"] == "getConnectedPrimitives"


def test_seed_names_the_line_the_pad_named() -> None:
    payload = _pad_direct_shared_line()
    payload["seeds"] = [_ref(LN1, LINE)]
    result = _project(payload)

    assert result.verdict == CONNECTED
    assert result.coverage["bfs"]["seeds"] == 1


def _mutually_named_endpoints(pad_kind: str) -> dict:
    """Both ends and both Lines name each other, in both available ways.

    562D HIGH-1: `adjacent-to-endpoint-pad` (Line→pad) and `pad-direct` (pad→Line)
    describe the same pair, and the Line row sorts first. With an endpoint type of
    `Pad` the pad's own row is the last one read, so a single-pass pairing check
    reports a reciprocal pair as one-way on type spelling alone.
    """
    host = _Host()
    host.direct(_ref(PAD_FROM, pad_kind), _ref(LN1, LINE))
    host.adjacent(_ref(LN1, LINE), _ref(PAD_FROM, pad_kind), kind="adjacent-to-endpoint-pad")
    host.adjacent(_ref(LN1, LINE), _ref(LN2, LINE))
    host.adjacent(_ref(LN2, LINE), _ref(LN1, LINE))
    host.adjacent(_ref(LN2, LINE), _ref(PAD_TO, pad_kind), kind="adjacent-to-endpoint-pad")
    host.direct(_ref(PAD_TO, pad_kind), _ref(LN2, LINE))
    return _probe(
        from_end=_end("R1", "1", PAD_FROM, kind=pad_kind, direct=_direct([_item(LN1)])),
        to_end=_end("J1", "1", PAD_TO, kind=pad_kind, direct=_direct([_item(LN2)])),
        nodes=[_node(LN1, LINE), _node(LN2, LINE)],
        edges=host.edges,
    )


@pytest.mark.parametrize("pad_kind", ["Pad", "ComponentPad"])
def test_mutually_named_endpoints_are_connected_without_a_false_gap(pad_kind: str) -> None:
    result = _project(_mutually_named_endpoints(pad_kind))

    assert result.verdict == CONNECTED
    assert _ids(result) == [PAD_FROM, LN1, LN2, PAD_TO]
    assert result.hop_count == 3
    assert "non-reciprocal-adjacency" not in _codes(result.unknown), (
        f"{pad_kind}: the pad's own direct answer names that Line, so the pair is reciprocal"
    )
    assert result.unknown == [], f"{pad_kind}: a reciprocal pair is not a gap"
    assert result.coverage["partial"] is False
    assert result.coverage["complete"] is True
    assert [row["kind"] for row in result.hops] == ["pad-direct", "adjacent", "pad-direct"]


# --------------------------------------------------------------------------
# §6.2 one-way adjacency is not proof; adding the reverse gives the shortest way
# --------------------------------------------------------------------------
def _one_way() -> dict:
    host = _Host()
    host.direct(_ref(PAD_FROM, PAD_KIND), _ref(LN1, LINE))
    host.adjacent(_ref(LN1, LINE), _ref(LN2, LINE))
    host.direct(_ref(PAD_TO, PAD_KIND), _ref(LN2, LINE))
    return _probe(
        from_end=_end("R1", "1", PAD_FROM, direct=_direct([_item(LN1)])),
        to_end=_end("J1", "1", PAD_TO, direct=_direct([_item(LN2)])),
        nodes=[_node(LN1, LINE), _node(LN2, LINE)],
        edges=host.edges,
    )


def test_one_way_adjacency_is_never_connected() -> None:
    result = _project(_one_way())

    assert result.verdict != CONNECTED
    assert result.path == []
    assert result.hops == []
    assert result.hop_count == 0
    assert "non-reciprocal-adjacency" in _codes(result.unknown)


def test_one_way_adjacency_downgrades_the_negative_to_indeterminate() -> None:
    result = _project(_one_way())

    assert result.verdict == INDETERMINATE, "a one-way answer is a gap, not a fact of separation"
    assert result.coverage["complete"] is False
    assert result.coverage["partial"] is True


def test_adding_the_reverse_edge_yields_the_shortest_path() -> None:
    payload = _one_way()
    payload["edges"].append({
        "from": _ref(LN2, LINE),
        "to": _ref(LN1, LINE),
        "method": "getAdjacentPrimitives",
        "kind": "adjacent",
        "callIndex": 3,
        "hostOrder": 0,
    })
    result = _project(payload)

    assert result.verdict == CONNECTED
    assert _ids(result) == [PAD_FROM, LN1, LN2, PAD_TO]


def test_shortest_walk_wins_over_a_longer_detour() -> None:
    host = _Host()
    host.direct(_ref(PAD_FROM, PAD_KIND), _ref(LN1, LINE))
    host.adjacent(_ref(LN1, LINE), _ref(LN2, LINE))
    host.adjacent(_ref(LN2, LINE), _ref(LN1, LINE))
    host.adjacent(_ref(LN1, LINE), _ref(LN3, LINE))
    host.adjacent(_ref(LN3, LINE), _ref(LN1, LINE))
    host.adjacent(_ref(LN3, LINE), _ref(LN2, LINE))
    host.adjacent(_ref(LN2, LINE), _ref(LN3, LINE))
    host.direct(_ref(PAD_TO, PAD_KIND), _ref(LN2, LINE))
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, direct=_direct([_item(LN1)])),
        to_end=_end("J1", "1", PAD_TO, direct=_direct([_item(LN2)])),
        nodes=[_node(LN1, LINE), _node(LN2, LINE), _node(LN3, LINE)],
        edges=host.edges,
    )
    result = _project(payload)

    assert result.verdict == CONNECTED
    assert _ids(result) == [PAD_FROM, LN1, LN2, PAD_TO], "one adjacent hop, not the two-hop detour"
    assert result.hop_count == 3


# --------------------------------------------------------------------------
# §6.3 endpoint and identity refusals — none of them may produce proof
# --------------------------------------------------------------------------
def test_different_nets_are_refused() -> None:
    payload = _pad_direct_shared_line()
    payload["to"] = _end("J1", "1", PAD_TO, net="N2", direct=_direct([_item(LN1)]))
    payload["coverage"] = _coverage(nets=(NET, "N2"))
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert result.path == []
    assert "different-net" in _codes(result.errors)


def test_missing_net_on_an_end_is_refused() -> None:
    payload = _pad_direct_shared_line()
    payload["to"] = _end("J1", "1", PAD_TO, net=None, direct=_direct([_item(LN1)]))
    payload["coverage"] = _coverage(nets=(NET, None))
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert result.path == []
    assert "net-missing" in _codes(result.errors)


def test_same_pad_on_both_ends_is_refused() -> None:
    payload = _pad_direct_shared_line()
    payload["to"] = _end("R1", "1", PAD_FROM, direct=_direct([_item(LN1)]))
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert result.path == []
    assert "same-pad" in _codes(result.errors)


def test_unresolved_end_is_indeterminate() -> None:
    payload = _pad_direct_shared_line()
    payload["to"] = _end("J1", "1", PAD_TO, status="unavailable", error="pin not found")
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert result.path == []
    assert "end-not-resolved" in _codes(result.errors)
    assert result.coverage["bfs"]["started"] is False


def test_failed_direct_call_is_indeterminate() -> None:
    payload = _pad_direct_shared_line()
    payload["from"] = _end("R1", "1", PAD_FROM, direct=_direct([], ok=False, error="threw"))
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert result.path == []
    assert "direct-not-ok" in _codes(result.errors)


def test_ambiguous_pad_resolution_is_refused() -> None:
    payload = _pad_direct_shared_line()
    payload["from"] = _end("R1", "1", PAD_FROM, matches=2, direct=_direct([_item(LN1)]))
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert result.path == []
    assert "pad-not-unique" in _codes(result.errors)


def test_an_edge_naming_a_node_no_row_establishes_is_not_a_hop() -> None:
    payload = _pad_direct_shared_line()
    payload["edges"].append({
        "from": _ref(PAD_TO, PAD_KIND),
        "to": _ref("ghost-line", LINE),
        "method": "getConnectedPrimitives",
        "kind": "pad-direct",
        "callIndex": 4,
        "hostOrder": 0,
    })
    result = _project(payload)

    assert result.verdict == CONNECTED, "the proven walk is not overturned by a gap elsewhere"
    assert "edge-node-missing" in _codes(result.unknown)
    assert result.coverage["partial"] is True


def test_identity_mismatch_between_edge_and_node_is_not_a_hop() -> None:
    payload = _pad_direct_shared_line()
    # The node row says Arc; the edge claims a Line with the same id: no vertex.
    payload["nodes"] = [_node(LN1, "Arc")]
    result = _project(payload)

    assert result.verdict != CONNECTED
    assert result.path == []
    assert "edge-node-missing" in _codes(result.unknown)


def test_edge_method_mismatch_is_not_a_hop() -> None:
    payload = _pad_direct_shared_line()
    payload["edges"][0]["method"] = "getAdjacentPrimitives"
    result = _project(payload)

    assert result.verdict != CONNECTED
    assert "edge-method-mismatch" in _codes(result.unknown)


# --------------------------------------------------------------------------
# §6.4 what may not enter a path
# --------------------------------------------------------------------------
def test_pad_via_contact_is_unknown_and_never_a_hop() -> None:
    host = _Host()
    host.direct(_ref(PAD_FROM, PAD_KIND), _ref(LN1, LINE))
    host.adjacent(_ref(LN1, LINE), _ref(VIA1, "Via"))
    host.adjacent(_ref(VIA1, "Via"), _ref(LN1, LINE))
    host.adjacent(_ref(VIA1, "Via"), _ref(PAD_TO, PAD_KIND), kind="adjacent-to-endpoint-pad")
    host.direct(_ref(PAD_TO, PAD_KIND), _ref(LN2, LINE))
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, direct=_direct([_item(LN1)])),
        to_end=_end("J1", "1", PAD_TO, direct=_direct([_item(VIA1, "Via")], )),
        nodes=[_node(LN1, LINE), _node(VIA1, "Via"), _node(LN2, LINE)],
        edges=host.edges,
    )
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert result.path == []
    assert "pad-via-contact" in _codes(result.unknown)


def test_arc_is_unknown_and_cannot_be_a_seed_or_a_hop() -> None:
    payload = _pad_direct_shared_line()
    payload["nodes"].append(_node(ARC1, "Arc"))
    payload["edges"].append({
        "from": _ref(PAD_FROM, PAD_KIND),
        "to": _ref(ARC1, "Arc"),
        "method": "getConnectedPrimitives",
        "kind": "pad-direct",
        "callIndex": 4,
        "hostOrder": 0,
    })
    result = _project(payload)

    assert "arc-unverified" in _codes(result.unknown)
    assert ARC1 not in _ids(result)
    assert result.verdict == CONNECTED, "the unrelated arc gap does not overturn the proven walk"
    assert result.coverage["partial"] is True


def test_pour_is_ignored_not_unknown() -> None:
    payload = _pad_direct_shared_line()
    payload["nodes"].append(_node(FILL1, "Fill"))
    payload["edges"].append({
        "from": _ref(PAD_FROM, PAD_KIND),
        "to": _ref(FILL1, "Fill"),
        "method": "getConnectedPrimitives",
        "kind": "pad-direct",
        "callIndex": 4,
        "hostOrder": 0,
    })
    result = _project(payload)

    assert "pour-excluded" in {str(row.get("code")) for row in result.ignored}
    assert "unsupported-adjacent-type" not in _codes(result.unknown)
    assert result.verdict == CONNECTED


def test_a_bridging_unknown_type_is_unknown_not_ignored() -> None:
    payload = _pad_direct_shared_line()
    payload["nodes"].append(_node(POLY1, "Polyline"))
    payload["edges"].append({
        "from": _ref(PAD_FROM, PAD_KIND),
        "to": _ref(POLY1, "Polyline"),
        "method": "getConnectedPrimitives",
        "kind": "pad-direct",
        "callIndex": 4,
        "hostOrder": 0,
    })
    result = _project(payload)

    assert "unsupported-adjacent-type" in _codes(result.unknown)
    assert "pour-excluded" not in {str(row.get("code")) for row in result.ignored}
    assert result.coverage["partial"] is True


def test_an_intermediate_pad_is_unknown_and_never_walked() -> None:
    payload = _pad_direct_shared_line()
    payload["nodes"].append(_node(OTHER_PAD, PAD_KIND))
    payload["edges"].append({
        "from": _ref(PAD_FROM, PAD_KIND),
        "to": _ref(OTHER_PAD, PAD_KIND),
        "method": "getConnectedPrimitives",
        "kind": "pad-direct",
        "callIndex": 4,
        "hostOrder": 0,
    })
    result = _project(payload)

    assert "intermediate-pad-unsupported" in _codes(result.unknown)
    assert OTHER_PAD not in _ids(result)


def test_other_net_copper_is_ignored_and_never_traversed() -> None:
    host = _Host()
    host.direct(_ref(PAD_FROM, PAD_KIND), _ref(LN1, LINE))
    host.adjacent(_ref(LN1, LINE), _ref(LN2, LINE))
    host.adjacent(_ref(LN2, LINE), _ref(LN1, LINE))
    host.direct(_ref(PAD_TO, PAD_KIND), _ref(LN2, LINE))
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, direct=_direct([_item(LN1)])),
        to_end=_end("J1", "1", PAD_TO, direct=_direct([_item(LN2)])),
        nodes=[_node(LN1, LINE), _node(LN2, LINE, net="N2")],
        edges=host.edges,
    )
    result = _project(payload)

    assert result.verdict != CONNECTED
    assert result.path == []
    assert "other-net" in {str(row.get("code")) for row in result.ignored}
    assert LN2 not in _ids(result)


# --------------------------------------------------------------------------
# §6.5 truncation, frontier and coverage.complete all block a negative
# --------------------------------------------------------------------------
def _clean_negative() -> dict:
    """Both ends resolved, one Line each, no adjacency between them."""
    host = _Host()
    host.direct(_ref(PAD_FROM, PAD_KIND), _ref(LN1, LINE))
    host.direct(_ref(PAD_TO, PAD_KIND), _ref(LN2, LINE))
    return _probe(
        from_end=_end("R1", "1", PAD_FROM, direct=_direct([_item(LN1)])),
        to_end=_end("J1", "1", PAD_TO, direct=_direct([_item(LN2)])),
        nodes=[_node(LN1, LINE), _node(LN2, LINE)],
        edges=host.edges,
    )


def test_a_complete_negative_is_not_proven_and_that_is_not_an_open_circuit() -> None:
    result = _project(_clean_negative())

    assert result.verdict == NOT_PROVEN
    assert result.path == []
    assert result.hops == []
    assert result.coverage["complete"] is True
    assert result.coverage["partial"] is False
    assert result.coverage["truncation"] == []
    assert result.unknown == [] and result.errors == []
    assert "open" not in json.dumps(result.as_dict()["scope"]).lower().replace("open circuit", "")


def test_per_call_truncation_blocks_the_negative() -> None:
    payload = _clean_negative()
    payload["coverage"] = _coverage(per_call_truncated=1, direct_truncated=(True, False))
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert {"per-call-truncated", "coverage-direct-truncated"} <= _codes(result.unknown)
    assert result.coverage["complete"] is False
    assert result.coverage["partial"] is True
    assert len(result.coverage["truncation"]) == 2


def test_an_unexpanded_frontier_blocks_the_negative() -> None:
    payload = _clean_negative()
    payload["frontier"] = [_ref(LN1, LINE)]
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert "frontier-unexpanded" in _codes(result.unknown)
    assert result.coverage["bfs"]["frontier"] == 1


def test_coverage_complete_false_alone_blocks_the_negative() -> None:
    payload = _clean_negative()
    payload["coverage"] = _coverage(complete=False)
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert "coverage-incomplete" in _codes(result.unknown)
    assert result.coverage["complete"] is False


def test_a_budget_exhaustion_blocks_the_negative() -> None:
    payload = _clean_negative()
    payload["coverage"] = _coverage(
        budget={"capMs": 120000, "elapsedMs": 120001, "exhausted": "time"}
    )
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert "budget-exhausted" in _codes(result.unknown)


def test_exceeding_the_adjacent_call_cap_blocks_the_negative() -> None:
    payload = _clean_negative()
    payload["coverage"] = _coverage(adjacent_calls=513, adjacent_cap=512)
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert "adjacent-calls-cap" in _codes(result.unknown)


def test_using_the_call_budget_exactly_is_not_a_truncation() -> None:
    # 562D MEDIUM-3: 512 of 512 calls with an empty frontier is a **finished**
    # walk, not a cut-off one — the cap is on the count, so only > cap is a gap.
    payload = _clean_negative()
    payload["coverage"] = _coverage(adjacent_calls=512, adjacent_cap=512, nodes_count=2, edges_count=2)
    result = _project(payload)

    assert result.verdict == NOT_PROVEN
    assert "adjacent-calls-cap" not in _codes(result.unknown)
    assert result.coverage["truncation"] == []
    assert result.coverage["bfs"]["frontier"] == 0
    assert result.coverage["complete"] is True


def test_a_truncated_graph_blocks_the_negative() -> None:
    payload = _clean_negative()
    payload["coverage"] = _coverage(nodes_truncated=True, edges_truncated=True)
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert {"coverage-nodes-truncated", "coverage-edges-truncated"} <= _codes(result.unknown)


def test_a_truncated_scan_blocks_the_negative() -> None:
    payload = _clean_negative()
    payload["coverage"] = _coverage(scan_truncated=True, scan_complete=False, scan_read_errors=2)
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert "coverage-scan-truncated" in _codes(result.unknown)


# --------------------------------------------------------------------------
# §6.6 an unrelated unknown keeps the road but not the completeness claim
# --------------------------------------------------------------------------
def test_unrelated_unknown_does_not_overturn_the_path_but_stays_partial() -> None:
    payload = _two_reciprocal_lines()
    payload["unknown"] = [{"code": "per-call-truncated", "from": _ref(LN1, LINE), "reported": 70, "kept": 64}]
    result = _project(payload)

    assert result.verdict == CONNECTED
    assert result.coverage["partial"] is True
    assert result.coverage["complete"] is False
    assert result.unknown[0] == payload["unknown"][0], "the collector's row is kept verbatim"


def test_the_same_unknown_downgrades_the_negative() -> None:
    payload = _clean_negative()
    payload["unknown"] = [{"code": "net-missing", "from": _ref(LN1, LINE)}]
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert result.path == []
    assert result.unknown[0] == payload["unknown"][0]


def test_connector_errors_and_ignored_rows_are_kept_verbatim() -> None:
    payload = _clean_negative()
    payload["errors"] = ["scan: pcb_PrimitiveComponent.getAll threw"]
    payload["ignored"] = [{"code": "other-net", "net": "GND"}]
    result = _project(payload)

    assert result.errors[-1] == "scan: pcb_PrimitiveComponent.getAll threw"
    assert result.ignored[0] == {"code": "other-net", "net": "GND"}
    assert result.verdict == INDETERMINATE, "a connector error is never a clean negative"


# --------------------------------------------------------------------------
# §6.7 shape, counts, determinism
# --------------------------------------------------------------------------
def test_the_payload_always_carries_the_full_key_set() -> None:
    data = _project(_pad_direct_shared_line()).as_dict()

    assert sorted(data) == [
        "coverage", "errors", "hopCount", "hops", "ignored", "path", "query",
        "schema", "scope", "source", "unknown", "verdict", "viaCount",
    ]
    assert data["schema"] == SCHEMA == "boardwise.pcbLivePath/1"
    assert data["query"]["from"] == {
        "designator": "R1",
        "pad": "1",
        "primitiveId": PAD_FROM,
        "type": PAD_KIND,
        "net": NET,
    }
    assert data["scope"]["excludes"], "the scope states what it refuses to answer"


def test_counts_match_the_path_in_every_positive() -> None:
    for payload in (_pad_direct_shared_line(), _two_reciprocal_lines(), _line_via_line()):
        result = _project(payload)
        assert result.verdict == CONNECTED
        assert result.hop_count == len(result.hops) == len(result.path) - 1
        assert result.via_count == sum(1 for row in result.path if row["type"] == "Via")


def test_two_runs_of_the_same_payload_are_byte_identical() -> None:
    payload = _line_via_line()
    first = _payload_bytes(copy.deepcopy(payload))
    second = _payload_bytes(copy.deepcopy(payload))

    assert first == second
    assert first == _payload_bytes(payload), "the input is never mutated by the projection"


def test_the_result_does_not_depend_on_the_edge_order() -> None:
    payload = _line_via_line()
    baseline = _payload_bytes(copy.deepcopy(payload))
    shuffled = copy.deepcopy(payload)
    random.Random(7).shuffle(shuffled["edges"])

    assert _payload_bytes(shuffled) == baseline
    assert project_live_path(shuffled).to_json() == project_live_path(payload).to_json()


def test_a_supplied_source_is_copied_in_unchanged() -> None:
    result = _project(_pad_direct_shared_line(), source={"connector": "pcb.path_probe", "build": "x"})

    assert result.source == {"connector": "pcb.path_probe", "build": "x"}
    assert result.verdict == CONNECTED


def test_the_default_source_names_the_connector_and_the_page() -> None:
    result = _project(_pad_direct_shared_line())

    assert result.source["connector"] == "pcb.path_probe"
    assert result.source["page"] == {"uuid": "pcb-uuid-1", "type": "pcb"}
    assert result.source["readOnly"] is True


def test_the_canonical_json_is_sorted_and_nan_free() -> None:
    payload = _line_via_line()
    text = project_live_path(payload).to_json(indent=2)

    assert json.loads(text)["verdict"] == CONNECTED
    assert "NaN" not in text and "Infinity" not in text
    assert text == project_live_path(payload).to_json(indent=2)
    with_indent = json.loads(project_live_path(payload).to_json(indent=2))
    without = json.loads(project_live_path(payload).to_json())
    assert with_indent == without


# --------------------------------------------------------------------------
# response guards: a probe that described something else is no graph
# --------------------------------------------------------------------------
def test_a_non_object_payload_is_indeterminate() -> None:
    result = project_live_path([])  # type: ignore[arg-type]

    assert result.verdict == INDETERMINATE
    assert result.path == []
    assert "payload-not-an-object" in _codes(result.errors)


def test_a_schematic_page_is_refused() -> None:
    payload = _pad_direct_shared_line()
    payload["page"] = {"uuid": "page-1", "type": "schematic"}
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert result.path == []
    assert "page-not-pcb" in _codes(result.errors)


def test_a_writable_response_is_refused() -> None:
    payload = _pad_direct_shared_line()
    payload["readOnly"] = False
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert result.path == []
    assert "not-read-only" in _codes(result.errors)


def test_an_unreadable_edges_array_is_a_gap() -> None:
    payload = _clean_negative()
    payload["edges"] = {"not": "an array"}
    result = _project(payload)

    assert result.verdict == INDETERMINATE
    assert "edges-unreadable" in _codes(result.unknown)
