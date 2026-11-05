"""543I-2: **one** grouping rule for a net's flags, ground and power alike.

Before this module the two classes were drawn by two rules: a high-fan-out rail
was stated by a flag at *every* pin (053 sec.7), while a ground was grouped by
the Euclidean distance between pads (535's :func:`drawcompiler._gnd_clusters`)
and each neighbourhood got one symbol. 岳's ruling (`boardwise-draw` §5A) closes
that split: both classes ask the same question — *can one flag serve these
seats?* — and the answer is a **walking** distance between the points the flags
would hang from, not a straight line across the page.

What is measured
----------------

A candidate is a **seat**: the pin (and point) a flag would hang off, i.e. the
start of the lead the flag stands on. Two seats may share one flag only when a
legal orthogonal run joins them, so the distance is the length of that run as
:class:`drawcompiler._Router` finds it — obstacles, blocked points, foreign
wires and reservations all respected. Unreachable is ``math.inf`` and never
joins. Euclidean distance, the nearest point of two wires, and chaining
(A–B near, B–C near, so A/B/C together) are all excluded by construction: the
first two are not the question, the third is not a fact.

The club rule
-------------

A group is only formed when **every pair** in it is within the reach and
reachable — the same refusal of single linkage 535 measured on the CH343 island
(a 500-unit bus that chained hop by hop). The grouping is greedy in the order
the candidates arrive (the stable member order the rest of the compiler uses),
so the same page always draws the same flags.

Who may share at all
--------------------

The distance only decides *whether* two candidate seats are near enough; the
**structure** decides whether they are allowed to ask:

* a part with several pins on the net is one shape inside the symbol, so its
  pins are candidate mates (``part:<id>``);
* a chain part's rail is the drawing's own trunk, so two chain parts on one net
  are candidate mates (``chain``);
* a **branch** part — a pull-down, a decoupling capacitor, an indicator — is a
  circuit of its own: :data:`SHARE_ALONE` means it keeps its own local flag, and
  the owner it hangs off is used for its pose, never to force a shared flag
  (`boardwise-draw` §5A: 成对但独立的支路默认各自本地旗);
* branches that are **electrically in parallel** — same owner, same shared net,
  same return net — are the two ends of one statement, so each end may ask for
  a shared flag (``share_branch_return``): 岳's ruling that a decoupling pair
  gets the same policy at both ends. Two pull-downs on *different* signal nets
  share only their return net's *class*, not its circuit, so they never get the
  same key (543J).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Callable, Iterable, Sequence

#: The share key of a seat that may never be merged with another: a branch
#: part's own flag, and the conservative answer for a part the layout does not
#: know.
SHARE_ALONE = ""

#: Share key of two chain parts' pads on one net (the drawing's own trunk).
SHARE_CHAIN = "chain"


def share_part(part_id: str) -> str:
    """Share key of several pins of **one** part on one net."""
    return f"part:{part_id}"


#: Separator of the parallel-branch key. Net ids and part ids never carry a
#: unit separator, so ``owner``/``shared_net``/``other_net`` can be joined
#: without one triple standing in for another.
_BRANCH_KEY_SEP = "\x1f"


def share_branch_return(owner: str, shared_net: str, other_net: str) -> str:
    """Share key of **parallel** branches' common end (543J).

    The three facts are the whole of "these branches are one circuit": both hang
    off the same owner, both take their supply from the same net and both return
    to the same net. A pull-down and a decoupling capacitor on different nets
    have different keys and keep their own flags, whatever the ruler says.
    """
    return _BRANCH_KEY_SEP.join(("branch-return", owner, shared_net, other_net))


@dataclass(frozen=True)
class FlagCandidate:
    """One seat a flag could hang from, and what it is allowed to share with.

    ``member`` names the pin (``"R10.2"``) so a refusal can point at it, and
    ``point`` is the seat itself — the end of the flag's own lead, not a point
    somewhere along a wire that does not exist yet.
    """

    member: str
    point: tuple[float, float]
    share: str = SHARE_ALONE


#: What the caller measures: `distance(a, b)` is the length of the cheapest
#: legal orthogonal run between two seats, ``math.inf`` when there is none.
Distance = Callable[[tuple[float, float], tuple[float, float]], float]


class RouteRuler:
    """Cached walking distance between seats, over a caller's router.

    ``route`` is the compiler's own search (``_Router.route``): it answers the
    node list of the cheapest legal run, or ``None``. The cost accumulated here
    is the path's **Manhattan length**, the run a reader would actually see. The
    cache is keyed in both directions because the search is symmetric in cost
    but not guaranteed to answer the same way round; measuring one order twice
    is the waste this avoids, and one measurement is never reused across a
    different obstacle set (the caller builds one ruler per pass).
    """

    def __init__(self, route: Callable[[tuple[float, float], tuple[float, float]], Sequence[tuple[float, float]] | None]) -> None:
        self._route = route
        self._cache: dict[
            tuple[tuple[float, float], tuple[float, float]], float
        ] = {}
        self.calls = 0

    def __call__(
        self, start: tuple[float, float], end: tuple[float, float]
    ) -> float:
        key = (start, end) if start <= end else (end, start)
        if key in self._cache:
            return self._cache[key]
        self.calls += 1
        path = self._route(start, end)
        if path is None:
            cost = math.inf
        else:
            cost = sum(
                abs(right[0] - left[0]) + abs(right[1] - left[1])
                for left, right in zip(path, path[1:])
            )
        self._cache[key] = cost
        return cost


def group_flag_candidates(
    candidates: Sequence[FlagCandidate],
    distance: Distance,
    reach: float,
) -> tuple[tuple[FlagCandidate, ...], ...]:
    """Split candidates into the groups one flag each can serve.

    Greedy in the given order: a candidate joins the first group of its own
    share key that stays within ``reach`` **for every pair** once it is added
    (能并就并), and starts a new group when none does. ``SHARE_ALONE`` never
    joins anything, so a branch keeps its own flag whatever the distance says.

    ``reach`` ≤ 0 means "nothing may share", which is the honest reading of a
    document that stated no reach at all.
    """
    groups: list[list[FlagCandidate]] = []
    for candidate in candidates:
        if candidate.share != SHARE_ALONE and reach > 0.0:
            for group in groups:
                if group[0].share != candidate.share:
                    continue
                if all(
                    distance(candidate.point, other.point) <= reach
                    for other in group
                ):
                    group.append(candidate)
                    break
            else:
                groups.append([candidate])
        else:
            groups.append([candidate])
    return tuple(tuple(group) for group in groups)


def group_pairs(
    groups: Iterable[Sequence[FlagCandidate]],
    distance: Distance,
    reach: float,
) -> tuple[tuple[str, str, float], ...]:
    """``(member, member, cost)`` for every pair that a group keeps together.

    The audit's raw material: re-measuring these pairs after the wiring says
    whether the grouping the page was drawn with still holds. Only pairs are
    reported — a group is a set of pairwise promises, which is exactly what the
    club rule claims.
    """
    out: list[tuple[str, str, float]] = []
    for group in groups:
        for index, left in enumerate(group):
            for right in group[index + 1:]:
                out.append((left.member, right.member, distance(left.point, right.point)))
    return tuple(out)


def partition_signature(
    groups: Iterable[Sequence[FlagCandidate]],
) -> frozenset[frozenset[str]]:
    """A comparable form of a grouping: the member sets, order-free."""
    return frozenset(
        frozenset(candidate.member for candidate in group) for group in groups
    )
