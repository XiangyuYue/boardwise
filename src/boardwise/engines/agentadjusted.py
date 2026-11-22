"""Agent-adjusted work orders, never a second live move planner.

The semantic layer names *why* a part should move and which V4 evidence owns the
part. The existing :mod:`boardwise.engines.moveblock` planner/apply path remains
the only judge of target occupancy, wire redraw, netlist identity and findings.
A work order is therefore always ``status=proposed`` with both proofs false.

When the direct move is refused for an *attachment* (a flag or label the
move-block planner will not re-attach), ``strategy="recompile-with-locks"`` adds
the same group's module locks for the existing PresentationSpec compiler. That
segment is data for the existing guards — not a planner, not an automatic step,
and the direct move stays the order's named ``nextCommand``.
"""
from __future__ import annotations

import copy
from typing import Any

from . import moveblock

SCHEMA = "boardwise.agent-adjusted-move/1"
EVIDENCE_SCHEMA = "boardwise.v4-presentation-evidence/1"

#: The direct move the work order has always named (`edit plan --move`).
STRATEGY_DIRECT = "direct-move"
#: The opt-in alternative for when that direct move is *refused* for an
#: attachment, because a lock cannot re-attach anything by itself: the group is
#: recompiled under module locks instead.
STRATEGY_RECOMPILE_WITH_LOCKS = "recompile-with-locks"
STRATEGIES: tuple[str, ...] = (STRATEGY_DIRECT, STRATEGY_RECOMPILE_WITH_LOCKS)

#: A module lock's closed key set (057 sec.3): a page lock, which states
#: `scope` and may not state a rotation, is a different shape and never this
#: segment's.
LOCK_KEYS: tuple[str, ...] = ("partId", "x", "y", "rotation")


def _number(value: Any) -> float:
    return f"{float(value):g}"


def _measured_pose(instance: dict[str, Any]) -> tuple[float, float] | None:
    """The instance's declared page pose, or ``None`` when the evidence has none.

    ``v4facts.presentation_evidence`` copies a COMPONENT record's x/y when the
    record declares them and never infers them, so evidence whose records state
    no pose has no coordinates to lock. Nothing here invents one: an unposed
    part refuses below.
    """
    x, y = instance.get("x"), instance.get("y")
    for value in (x, y):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
    return float(x), float(y)


def _recompile_with_locks(
    selected: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    names: list[str],
    dx: float,
    dy: float,
) -> dict[str, Any]:
    """The locks for recompiling this whole group, or a refusal saying why not.

    The segment is data, never a plan: it hands the moved parts' target poses to
    the existing PresentationSpec compiler, whose own layout/readability/flag
    guards judge them. It states no new device and no narrower group — the
    caller's designators *are* the group.

    ``sources`` are the evidence instances the poses are read from: the work
    order's own ``instances`` keep the identity-and-rotation shape they always
    had and are never widened with coordinates.
    """
    unposed = [name for name, part in zip(names, sources) if _measured_pose(part) is None]
    if unposed:
        raise ValueError(
            "the evidence carries no x/y pose for "
            + ", ".join(unposed)
            + ": a module lock without a measured pose would be fabricated (the "
            "v4-facts sidecar copies x/y only when the COMPONENT record declares "
            "them and never infers them); supply evidence that states the "
            "instance poses"
        )
    pages = sorted({part["pageUuid"] for part in selected if part["pageUuid"]})
    if len(pages) > 1:
        raise ValueError(
            "the selected designators span pages ("
            + ", ".join(pages)
            + "); a recompile lands on one page, so pass one page's group"
        )
    locks = []
    for part, source in zip(selected, sources):
        pose_x, pose_y = _measured_pose(source)  # type: ignore[misc]
        locks.append({
            "partId": part["designator"],
            "x": pose_x + float(dx),
            "y": pose_y + float(dy),
            "rotation": float(part["rotation"]),
        })
    page_uuid = pages[0] if pages else ""
    return {
        "strategy": STRATEGY_RECOMPILE_WITH_LOCKS,
        "automatic": False,
        "appliesOnlyWhen": (
            "the direct move was refused: `boardwise edit plan --move` reports a "
            "moved part whose flag/label or wire attachment the move-block "
            "planner will not re-attach. This is an alternative somebody "
            "chooses, never a step that runs by itself."
        ),
        "designators": list(names),
        "partIds": [part["partId"] for part in selected],
        "pageUuid": page_uuid,
        "locks": locks,
        "lockScope": "module",
        "lockContract": (
            "Every lock is a PresentationSpec.userLocks module lock: "
            "partId/x/y/rotation and no `scope` key. A page lock states "
            "scope=page and may not carry a rotation, so this segment never "
            "writes one; x/y are the measured instance pose plus the delta."
        ),
        "presentationSpecReview": [
            "Add these locks to presentationSpec.userLocks of the PresentationSpec "
            "that already describes this page.",
            "The group, not the MCU alone, is the unit: every service part, flag "
            "attachment and label relationship this group has goes through the "
            "recompile with it. `designators` is that whole group and no other "
            "part may be added on its behalf.",
            "Recompile and re-plan so the existing layout, readability and flag "
            "guards judge the locked group; a lock is an input to them, not a way "
            "past them.",
        ],
        "followUp": [
            {
                "command": [
                    "boardwise", "draw", "compile",
                    "--circuit", "<circuit.json>",
                    "--presentation", "<presentation.json>",
                    "--profiles", "<profiles.json>",
                ],
                "when": "after the locks are in the PresentationSpec",
            },
            {
                "command": [
                    "boardwise", "draw", "plan",
                    "--circuit", "<circuit.json>",
                    "--presentation", "<presentation.json>",
                    "--profiles", "<profiles.json>",
                ],
                "when": "the regenerated plan is what apply then checks",
            },
            {
                "command": [
                    "boardwise", "draw", "apply", "<plan.json>",
                    "--page", page_uuid,
                    "--circuit", "<circuit.json>",
                    "--presentation", "<presentation.json>",
                    "--profiles", "<profiles.json>",
                ],
                "when": (
                    "lands on the original pageUuid and reuses that page; the page "
                    "is never created for this and the same guarded apply path runs"
                ),
            },
        ],
        "guards": [
            "The move-block attachment refusal stays exactly as it is: this "
            "segment never asks for a flag or wire to be re-attached.",
            "The compiler's own layout and readability checks still decide whether "
            "the locked group draws, and a lock that conflicts with the grammar is "
            "reported, never dropped.",
        ],
        "doesNotProve": [
            "targetFreeProven", "netlistIdentityProven",
        ],
    }


def propose_agent_adjusted_move(
    evidence: dict[str, Any],
    designators: list[str] | tuple[str, ...],
    dx: float,
    dy: float,
    reason: str,
    *,
    strategy: str = STRATEGY_DIRECT,
) -> dict[str, Any]:
    """Validate semantic move input and return an ``agent-adjusted`` work order.

    Unknown/duplicate designators, off-grid deltas, a no-op and an empty reason
    are refused. Nothing here claims the target is free or the netlist is equal;
    those judgements belong only to the existing live move-block path.

    ``strategy`` selects the work order's alternative. It defaults to the direct
    move that the order has always named, and the returned document is then
    unchanged field for field. ``recompile-with-locks`` *adds* one segment
    (``recompileWithLocks``) for the case where the direct move is refused for an
    attachment: the same designators, as module locks for the existing
    PresentationSpec compiler. It never replaces ``nextCommand``, is marked
    ``automatic: False`` and proves neither live guard.
    """
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        raise ValueError(
            f"evidence.schema is {evidence.get('schema')!r}; expected {EVIDENCE_SCHEMA!r}"
        )
    chosen = str(strategy or STRATEGY_DIRECT).strip()
    if chosen not in STRATEGIES:
        raise ValueError(
            f"strategy is {strategy!r}; expected one of {', '.join(STRATEGIES)}"
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
    sources = []
    for name in names:
        instance = instances[name][0]
        sources.append(instance)
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
    work: dict[str, Any] = {
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
    if chosen == STRATEGY_RECOMPILE_WITH_LOCKS:
        work["recompileWithLocks"] = _recompile_with_locks(
            selected, sources, names, dx, dy,
        )
    return work
