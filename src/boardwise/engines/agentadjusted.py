"""Agent-adjusted work orders, never a second live move planner.

The semantic layer names *why* a part should move and which V4 evidence owns the
part. The existing :mod:`boardwise.engines.moveblock` planner/apply path remains
the only judge of target occupancy, wire redraw, netlist identity and findings.
A work order is therefore always ``status=proposed`` with both proofs false.
"""
from __future__ import annotations

import copy
from typing import Any

from . import moveblock

SCHEMA = "boardwise.agent-adjusted-move/1"
EVIDENCE_SCHEMA = "boardwise.v4-presentation-evidence/1"


def _number(value: Any) -> float:
    return f"{float(value):g}"


def propose_agent_adjusted_move(
    evidence: dict[str, Any],
    designators: list[str] | tuple[str, ...],
    dx: float,
    dy: float,
    reason: str,
) -> dict[str, Any]:
    """Validate semantic move input and return an ``agent-adjusted`` work order.

    Unknown/duplicate designators, off-grid deltas, a no-op and an empty reason
    are refused. Nothing here claims the target is free or the netlist is equal;
    those judgements belong only to the existing live move-block path.
    """
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        raise ValueError(
            f"evidence.schema is {evidence.get('schema')!r}; expected {EVIDENCE_SCHEMA!r}"
        )
    names = [str(name).strip().upper() for name in designators if str(name).strip()]
    if not names:
        raise ValueError("designators must name at least one part")
    if len(set(names)) != len(names):
        raise ValueError("designators contains a duplicate part")
    if not moveblock.on_grid(dx) or not moveblock.on_grid(dy):
        raise ValueError(
            f"the delta ({dx:g}, {dy:g}) is not a multiple of the "
            f"{moveblock.GRID:g}-unit grid"
        )
    if float(dx) == 0.0 and float(dy) == 0.0:
        raise ValueError("a move needs a non-zero delta")
    semantic_reason = str(reason).strip()
    if not semantic_reason:
        raise ValueError("an agent-adjusted move needs a semantic reason")

    instances: dict[str, list[dict[str, Any]]] = {}
    for group in evidence.get("pageGroups", []):
        for instance in group.get("instances", []):
            if instance.get("designator"):
                name = str(instance["designator"]).upper()
                instances.setdefault(name, []).append(instance)
    ambiguous = sorted(name for name in names if len(instances.get(name, [])) > 1)
    if ambiguous:
        raise ValueError(
            "ambiguous designator(s) in the V4 evidence: " + ", ".join(ambiguous)
        )
    missing = [name for name in names if name not in instances]
    if missing:
        raise ValueError(
            "designator(s) absent from the V4 evidence: " + ", ".join(missing)
        )

    selected = []
    for name in names:
        instance = instances[name][0]
        selected.append({
            "partId": instance.get("partId", ""),
            "designator": name,
            "symbolUuid": instance.get("symbolUuid", ""),
            "symbolTitle": instance.get("symbolTitle", ""),
            "pageUuid": instance.get("pageUuid", ""),
            "page": instance.get("page", ""),
            "rotation": instance.get("rotation", 0),
            "isMirror": bool(instance.get("isMirror", False)),
        })
    next_command = [
        "boardwise", "edit", "plan", "--move",
        "--designators", ",".join(names),
        "--dx", _number(dx), "--dy", _number(dy),
    ]
    return {
        "schema": SCHEMA,
        "mode": "agent-adjusted",
        "status": "proposed",
        "source": evidence.get("source", ""),
        "evidenceSchema": EVIDENCE_SCHEMA,
        "designators": names,
        "delta": {"dx": float(dx), "dy": float(dy)},
        "semanticReason": semantic_reason,
        "instances": selected,
        "targetFreeProven": False,
        "netlistIdentityProven": False,
        "openQuestions": copy.deepcopy(evidence.get("openQuestions") or []),
        "guards": [
            "The live move-block planner must still prove the target is free.",
            "Attached wires are deleted and redrawn orthogonally; the host does not drag them.",
            "The live per-pin net partition must be identical after the move.",
            "Stale plans, changed findings and unreadable postconditions refuse the write.",
        ],
        "nextCommand": next_command,
    }
