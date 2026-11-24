"""Agent-adjusted work orders, never a second live move planner.

The semantic layer names *why* a part should move and which V4 evidence owns the
part. The existing :mod:`boardwise.engines.moveblock` planner/apply path remains
the only judge of target occupancy, wire redraw, netlist identity and findings.
A work order is therefore always ``status=proposed`` with both proofs false.

When the direct move is refused for an *attachment* (a flag or label the
move-block planner will not re-attach), ``strategy="recompile-with-locks"`` adds
the same group's **page** locks for the existing PresentationSpec compiler. That
segment is data for the existing guards — not a planner, not an automatic step,
and the direct move stays the order's named ``nextCommand``.

The locks are page locks because the pose the evidence carries is a page pose:
``pagecompiler.page_presentation_view`` translates a *module* lock by its
module's offset before the page's checks see it, so a module-scope segment would
land every part at pose + delta + offset on any page whose module is not at the
origin. A page lock (057 sec.3) is already in page coordinates and is passed as
it is, and the pose it may not state stays the module drawing's.

A page lock is also why this segment cannot be trusted with a subset of a module:
the page compiler derives a module's **origin** from a page lock point
(``pagecompiler._page_origins``), so locking one part moves every companion in
that module, and the page packer re-places the modules the group does not name.
Nothing in the evidence sidecar proves module membership — pages are attribution
boundaries — so the caller supplies the page's ``PresentationSpec`` and the
group is refused unless every member of each module it touches is named. And a
page lock pins a position, never a pose: a measured rotation that is not a
multiple of 360, or a mirror, is refused rather than silently re-posed.
"""
from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from typing import Any

from ..core.presentationspec import PresentationSpec
from . import moveblock

SCHEMA = "boardwise.agent-adjusted-move/1"
EVIDENCE_SCHEMA = "boardwise.v4-presentation-evidence/1"

#: The direct move the work order has always named (`edit plan --move`).
STRATEGY_DIRECT = "direct-move"
#: The opt-in alternative for when that direct move is *refused* for an
#: attachment, because a lock cannot re-attach anything by itself: the group is
#: recompiled under page locks instead.
STRATEGY_RECOMPILE_WITH_LOCKS = "recompile-with-locks"
STRATEGIES: tuple[str, ...] = (STRATEGY_DIRECT, STRATEGY_RECOMPILE_WITH_LOCKS)

#: A page lock's closed key set (057 sec.3): `scope` says the coordinates are the
#: page's and a page lock carries no rotation — the pose stays the module
#: drawing's. This segment states page locks only: a module lock states a
#: rotation and is translated by its module's offset on the page
#: (``pagecompiler.page_presentation_view``), which would move a measured page
#: pose a second time.
PAGE_LOCK_KEYS: tuple[str, ...] = ("partId", "x", "y", "scope")


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


def _module_members(module: Any) -> list[str]:
    """A module's parts, in the spec's order, normalised for comparison."""
    return [str(part).strip().upper() for part in module.parts if str(part).strip()]


def _member_proof(spec: PresentationSpec, names: list[str]) -> tuple[list[str], list[str]]:
    """The modules the group touches, and the ones it leaves alone.

    A page lock derives its module's origin, so the module is a rigid body: the
    group is only honest when every member of every module it touches is named.
    Raises a :class:`ValueError` that names each missing companion, and refuses
    a named part no module claims — an unproven part is not "probably alone".
    """
    member_of: dict[str, list[str]] = {}
    members_of: dict[str, list[str]] = {}
    order: list[str] = []
    for module in spec.modules:
        members = _module_members(module)
        members_of[module.id] = members
        order.append(module.id)
        for member in members:
            member_of.setdefault(member, []).append(module.id)
    unowned = [name for name in names if name not in member_of]
    if unowned:
        raise ValueError(
            "the PresentationSpec gives no module for " + ", ".join(unowned)
            + ": a recompile-with-locks group must be the members of a module, "
            "and a part no module claims has no member proof to offer (name its "
            "module in the spec, or use the direct move)"
        )
    chosen = set(names)
    claimed = [mid for mid in order if any(member in chosen for member in members_of[mid])]
    incomplete = [
        (mid, [member for member in members_of[mid] if member not in chosen])
        for mid in claimed
    ]
    incomplete = [(mid, missing) for mid, missing in incomplete if missing]
    if incomplete:
        detail = "; ".join(
            f"module {mid!r} also contains " + ", ".join(missing)
            for mid, missing in incomplete
        )
        raise ValueError(
            "the group names only part of a rigid module: " + detail
            + ". A page lock pins one part's position and the page compiler "
            "derives the whole module's origin from it, so the recompile would "
            "move every member while the work order names only "
            + ", ".join(names)
            + ". Name every member of the module(s) it touches, or use the "
            "direct move, which moves exactly the named parts"
        )
    claimed_set = set(claimed)
    return claimed, [mid for mid in order if mid not in claimed_set]


def _pose_refusal(name: str, detail: str) -> ValueError:
    return ValueError(
        f"{name} {detail}: a page lock pins a position, not a pose, so a "
        "recompile would land the part in the module drawing's pose and the "
        "page-level lock check would not see the change — it reads a page "
        "lock's rotation off the drawing it is checking. Use the direct move "
        "(`boardwise edit plan --move`), which moves the part as it stands, or "
        "state the pose in the module drawing."
    )


def _refuse_a_pose_a_lock_cannot_keep(
    names: list[str], selected: list[dict[str, Any]],
) -> None:
    """A page lock cannot state rotation or mirror: refuse rather than re-pose.

    ``rotation`` must be a finite number and a multiple of 360 to be the same
    pose a page lock can keep; NaN, inf, a string, a bool and a missing value
    are all unreadable and refuse rather than pass through. ``isMirror`` true
    is refused outright. The direct move is untouched by this: it moves the
    part as it stands.
    """
    for name, part in zip(names, selected):
        if bool(part.get("isMirror", False)):
            raise _pose_refusal(name, "is measured mirrored (isMirror=true)")
        rotation = part.get("rotation", 0)
        if isinstance(rotation, bool) or not isinstance(rotation, (int, float)):
            raise _pose_refusal(
                name, f"has no finite measured rotation ({rotation!r})"
            )
        if not math.isfinite(float(rotation)):
            raise _pose_refusal(
                name, f"has no finite measured rotation ({rotation!r})"
            )
        if float(rotation) % 360:
            raise _pose_refusal(name, f"is measured at rotation {_number(rotation)}")


def _recompile_with_locks(
    selected: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    names: list[str],
    dx: float,
    dy: float,
    presentation: PresentationSpec | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The locks for recompiling this whole group, or a refusal saying why not.

    The segment is data, never a plan: it hands the moved parts' target poses to
    the existing PresentationSpec compiler, whose own layout/readability/flag
    guards judge them. It states no new device and no narrower group — the
    caller's designators *are* the group, and its modules must prove it.

    Each lock is a **page** lock: the measured page pose plus the delta, in page
    coordinates, exactly as ``presentation_evidence`` read them off the COMPONENT
    record. A module lock would be the same numbers read in its module's drawing,
    and the page would then translate them by the module's offset — the part
    would land one module offset away from where it was measured. No rotation is
    stated: a page lock pins a position, and the pose it lands in is the module
    drawing's (057 sec.3).

    ``sources`` are the evidence instances the poses are read from: the work
    order's own ``instances`` keep the identity-and-rotation shape they always
    had and are never widened with coordinates.

    ``presentation`` is the page's PresentationSpec, and it is **required**: it
    is the only document that says which parts form a module, and a page lock
    moves a whole module. Its members prove the group (no subset, no unclaimed
    part), and the measured pose must be one a page lock can keep.
    """
    if presentation is None:
        raise ValueError(
            "recompile-with-locks needs the page's PresentationSpec to prove the "
            "group: a page lock pins one part's position and the page compiler "
            "derives that part's whole module origin from it, so every member the "
            "group does not name still moves. Pass `--presentation "
            "<presentation.json>` (CLI) or `presentation=` (this API); without it "
            "the work order could name one part and move its companions."
        )
    if isinstance(presentation, PresentationSpec):
        spec = presentation
    elif isinstance(presentation, Mapping):
        spec = PresentationSpec.from_dict(presentation)
    else:
        raise TypeError(
            "presentation must be a PresentationSpec or its JSON object, not "
            f"{type(presentation).__name__}"
        )
    claimed_ids, other_ids = _member_proof(spec, names)
    _refuse_a_pose_a_lock_cannot_keep(names, selected)
    unposed = [name for name, part in zip(names, sources) if _measured_pose(part) is None]
    if unposed:
        raise ValueError(
            "the evidence carries no x/y pose for "
            + ", ".join(unposed)
            + ": a page lock without a measured pose would be fabricated (the "
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
            "scope": "page",
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
        "lockScope": "page",
        "lockContract": (
            "Every lock is a PresentationSpec.userLocks page lock (057 sec.3): "
            "partId/x/y/scope=page and no rotation — a page lock pins a position, "
            "and the pose it lands in is the module drawing's, so this segment "
            "never writes one and refuses a measured pose it cannot keep (a "
            "rotation that is not a multiple of 360, a mirror, or no readable "
            "rotation). x/y are the measured page pose plus the delta, already in "
            "page coordinates: the page compiler passes a page lock through "
            "untranslated, derives the module's origin from it, and the nine "
            "re-check it on the merged drawing. A module lock would be translated "
            "by its module's offset and land one offset away. Because the origin "
            "is derived from the lock, a page lock moves the part's whole module."
        ),
        "presentationSpecReview": [
            "Add these locks to presentationSpec.userLocks of the PresentationSpec "
            "that already describes this page. They are page locks: the page "
            "passes them through untranslated and re-checks them on the merged "
            "drawing.",
            "The group, not the MCU alone, is the unit: every service part, flag "
            "attachment and label relationship this group has goes through the "
            "recompile with it. `designators` is that whole group and no other "
            "part may be added on its behalf.",
            (
                "The member proof is the PresentationSpec supplied with this "
                "order: module(s) " + ", ".join(claimed_ids) + " claim exactly "
                "the parts in `designators`, and every member of each claimed "
                "module is named — a page lock derives the whole module's "
                "origin, so a subset would move unnamed companions."
            ),
            "Only the module(s) named above are proven complete, not the page: the "
            "page packer also re-packs "
            + (
                "module(s) " + ", ".join(other_ids) + ", which this group does not name, "
                if other_ids
                else "every module the spec does not put in this group "
                "(this spec declares none outside it), "
            )
            + "so read the whole recompiled plan before applying it. This work "
            "order does not claim that only " + ", ".join(names) + " move.",
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
    presentation: PresentationSpec | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate semantic move input and return an ``agent-adjusted`` work order.

    Unknown/duplicate designators, off-grid deltas, a no-op and an empty reason
    are refused. Nothing here claims the target is free or the netlist is equal;
    those judgements belong only to the existing live move-block path.

    ``strategy`` selects the work order's alternative. It defaults to the direct
    move that the order has always named, and the returned document is then
    unchanged field for field. ``recompile-with-locks`` *adds* one segment
    (``recompileWithLocks``) for the case where the direct move is refused for an
    attachment: the same designators, as page locks for the existing
    PresentationSpec compiler. It never replaces ``nextCommand``, is marked
    ``automatic: False`` and proves neither live guard.

    ``presentation`` is only read by that alternative, and only there is it
    required: a page lock moves the named part's whole module, so the group's
    members and a keepable pose must be proven before a lock is written. A
    direct move never consults it and its document is unchanged.
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
            selected, sources, names, dx, dy, presentation,
        )
    return work
