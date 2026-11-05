"""543I-2: one grouping rule for ground and power flags, measured by walking.

`flaggroups` is the rule `boardwise-draw` §5A states: two seats may share one
flag only when a **legal orthogonal run** joins them within the document's
reach, and only when the structure allows them to ask at all. What this file
pins, on a real `_Router` wherever the point is about geometry:

* the distance is the run's Manhattan length, so an obstruction between two
  seats that a Euclidean radius calls "near" is a split — and an obstruction
  that leaves no legal run at all is ``∞``, never "merely far";
* A–B near and B–C near do **not** put A/B/C in one group (the club rule);
* a branch keeps its own flag whatever the distance says, a part with several
  pins on the net may merge with itself, and two chain pads may merge with each
  other;
* **parallel** branches (same owner, same shared net, same return net) are the
  one exception at their return end, and only the *structure* says so: branches
  whose shared nets differ still never ask (543J);
* a rule-ruler asks the router once per unordered pair.

The measured P32 page that motivated the rule is in `evidence/543i2/`: on the
CH343 page its ground splits into the seven groups this rule names (R10, R11,
C13, C14 each alone; the connector's pins by walking distance), which is more
flags than that island can seat — the production wiring is **not** in this tree
and the batch's remaining work is written up there.
"""

from __future__ import annotations

import math

import pytest

from boardwise.engines import drawcompiler as dc
from boardwise.engines import flaggroups
from boardwise.engines.router import _Router

#: The compiler's lattice, so a distance measured here is a distance the
#: compiler would route on.
GRID = 5.0


def _router(boxes=(), bounds=(0.0, 0.0, 400.0, 400.0)) -> _Router:
    return _Router(grid=GRID, residue=(0.0, 0.0), boxes=list(boxes), bounds=bounds)


def _ruler(router: _Router) -> flaggroups.RouteRuler:
    def route(start, end):
        return router.route(start, end)

    return flaggroups.RouteRuler(route)


def _seat(member: str, point, share: str = flaggroups.SHARE_CHAIN):
    return flaggroups.FlagCandidate(member=member, point=point, share=share)


def test_the_distance_is_the_run_not_the_straight_line():
    """A body between two seats: Euclidean says near, the walker says otherwise."""
    left, right = (100.0, 100.0), (160.0, 100.0)
    straight = math.dist(left, right)
    assert straight == pytest.approx(60.0)

    # A body 40 wide straddling the line between them, with 15 units of room
    # above it inside the page.
    body = (120.0, 90.0, 140.0, 110.0)
    run = _ruler(_router([body]))
    walked = run(left, right)
    assert walked > straight, walked
    # Up and over: 15 up, 60 across, 15 down — a legal orthogonal path.
    assert walked == pytest.approx(90.0), walked

    # The same two seats: a radius that a straight line would satisfy does not
    # keep them together, because the run is longer than the radius.
    reach = 75.0
    groups = flaggroups.group_flag_candidates(
        [_seat("C13.2", left), _seat("C14.2", right)], run, reach,
    )
    assert len(groups) == 2, groups
    # ... and a radius the run does satisfy does keep them together.
    groups = flaggroups.group_flag_candidates(
        [_seat("C13.2", left), _seat("C14.2", right)], run, 95.0,
    )
    assert len(groups) == 1, groups


def test_an_unreachable_seat_is_never_grouped():
    """A wall between two seats is ``∞``, not "far": no flag can serve both."""
    left, right = (100.0, 100.0), (160.0, 100.0)
    # A box that spans the whole corridor between them, top to bottom.
    wall = (120.0, 0.0, 140.0, 400.0)
    run = _ruler(_router([wall]))
    assert run(left, right) == math.inf
    groups = flaggroups.group_flag_candidates(
        [_seat("A.1", left), _seat("B.1", right)], run, 10_000.0,
    )
    assert len(groups) == 2, groups


def test_near_is_not_chaining():
    """A–B near and B–C near is not A/B/C together — every pair has to fit."""
    points = {
        "A": (0.0, 0.0),
        "B": (50.0, 0.0),
        "C": (100.0, 0.0),
    }

    def distance(start, end):
        return math.dist(start, end)

    groups = flaggroups.group_flag_candidates(
        [_seat(name, point) for name, point in points.items()], distance, 60.0,
    )
    assert [[candidate.member for candidate in group] for group in groups] == [
        ["A", "B"], ["C"],
    ], groups


def test_a_branch_keeps_its_own_flag_however_close():
    """The structure decides who may ask; zero distance is not an argument."""
    same = (100.0, 100.0)

    def distance(_start, _end):
        return 0.0

    groups = flaggroups.group_flag_candidates(
        [
            _seat("R10.2", same, flaggroups.SHARE_ALONE),
            _seat("R11.2", same, flaggroups.SHARE_ALONE),
        ],
        distance, 100.0,
    )
    assert len(groups) == 2, groups

    # Two chain pads at the same place do merge — the same measurement, a
    # different structural answer.
    groups = flaggroups.group_flag_candidates(
        [
            _seat("U1.1", same, flaggroups.SHARE_CHAIN),
            _seat("USB1.1", same, flaggroups.SHARE_CHAIN),
        ],
        distance, 100.0,
    )
    assert len(groups) == 1, groups


def test_parallel_branches_get_one_return_key_and_differing_ones_get_none():
    """543J: the key names the circuit, not the parts.

    Two branches on the same owner, supply and return net are one statement, so
    their return pads may ask for one flag. Two pull-downs on different signal
    nets share only a net *class* — they get different keys and never merge.
    """
    key = flaggroups.share_branch_return("USB1", "+5V", "GND")
    assert key != flaggroups.SHARE_ALONE
    assert key != flaggroups.SHARE_CHAIN
    # Deterministic for the same circuit, and distinct for a different one.
    assert key == flaggroups.share_branch_return("USB1", "+5V", "GND")
    assert key != flaggroups.share_branch_return("USB1", "CC1", "GND")
    assert key != flaggroups.share_branch_return("USB1", "CC2", "GND")
    assert key != flaggroups.share_branch_return("U1", "+5V", "GND")
    # No two different triples can spell the same key.
    assert flaggroups.share_branch_return("A", "B", "C") != flaggroups.share_branch_return(
        "A", "B\x1fC", ""
    )


def _branch_ctx(slots):
    from types import SimpleNamespace

    return SimpleNamespace(slots={
        part_id: dc._Slot(
            part_id=part_id, role="decoupling", kind="branch", axis="x", rank=rank,
            owner=owner, shared_net=shared, other_net=other,
            pin_shared="1", pin_other="2",
        )
        for part_id, (rank, owner, shared, other) in slots.items()
    })


def test_the_share_keys_read_the_structure_not_the_part_or_net_names():
    """543J: a decoupling pair's return pads ask together, whatever they are called."""
    # Two branches of one owner between the same two nets: parallel.
    parallel = _branch_ctx({
        "C1": (1, "USB1", "+5V", "GND"),
        "C2": (2, "USB1", "+5V", "GND"),
        # ... and two pull-downs whose shared nets differ: not parallel.
        "R1": (3, "USB1", "CC1", "GND"),
        "R2": (4, "USB1", "CC2", "GND"),
        # ... and a lone decoupling capacitor: nothing to be parallel with.
        "C3": (5, "U1", "V3", "GND"),
    })
    points = [(name + ".2", (float(index), 0.0)) for index, name in enumerate(
        ("C1", "C2", "R1", "R2", "C3"), start=1
    )]
    keys = dc._flag_share_keys(parallel, "GND", points)
    assert keys["C1.2"] == keys["C2.2"] == flaggroups.share_branch_return(
        "USB1", "+5V", "GND"
    )
    assert keys["R1.2"] == flaggroups.SHARE_ALONE
    assert keys["R2.2"] == flaggroups.SHARE_ALONE
    assert keys["C3.2"] == flaggroups.SHARE_ALONE

    # The shared end keeps the old chain answer for the pair and for the couple.
    shared = [(name + ".1", (float(index), 0.0)) for index, name in enumerate(
        ("C1", "C2", "C3"), start=1
    )]
    keys = dc._flag_share_keys(parallel, "+5V", shared[:2])
    assert keys == {"C1.1": flaggroups.SHARE_CHAIN, "C2.1": flaggroups.SHARE_CHAIN}
    keys = dc._flag_share_keys(parallel, "V3", shared[2:])
    assert keys == {"C3.1": flaggroups.SHARE_CHAIN}

    # The same structure under other names answers the same way: nothing here
    # reads a part or net name.
    renamed = _branch_ctx({
        "X1": (1, "J9", "RAIL", "RETURN"),
        "X2": (2, "J9", "RAIL", "RETURN"),
    })
    keys = dc._flag_share_keys(
        renamed, "RETURN", [("X1.2", (0.0, 0.0)), ("X2.2", (9.0, 0.0))]
    )
    assert keys["X1.2"] == keys["X2.2"]
    assert keys["X1.2"] not in (flaggroups.SHARE_ALONE, flaggroups.SHARE_CHAIN)


def test_a_parallel_return_pair_merges_only_on_a_legal_run_within_reach():
    """The structure lets them ask; the walking ruler still answers yes/no."""
    key = flaggroups.share_branch_return("USB1", "+5V", "GND")
    left, right = (100.0, 100.0), (160.0, 100.0)

    # Near and reachable: one flag for both return pads.
    open_page = _ruler(_router())
    assert open_page(left, right) == pytest.approx(60.0)
    groups = flaggroups.group_flag_candidates(
        [_seat("C1.2", left, key), _seat("C2.2", right, key)], open_page, 100.0,
    )
    assert [[c.member for c in g] for g in groups] == [["C1.2", "C2.2"]], groups

    # A body between them: the walk is 90 (up, across, down). Euclidean would
    # say 60 and call it near; the ruler's own answer decides, and a reach of 75
    # is not enough.
    detour = _ruler(_router([(120.0, 90.0, 140.0, 110.0)]))
    assert detour(left, right) == pytest.approx(90.0)
    groups = flaggroups.group_flag_candidates(
        [_seat("C1.2", left, key), _seat("C2.2", right, key)], detour, 75.0,
    )
    assert len(groups) == 2, groups

    # No legal run at all: apart, however generous the reach.
    walled = _ruler(_router([(120.0, 0.0, 140.0, 400.0)]))
    assert walled(left, right) == math.inf
    groups = flaggroups.group_flag_candidates(
        [_seat("C1.2", left, key), _seat("C2.2", right, key)], walled, 10_000.0,
    )
    assert len(groups) == 2, groups


def test_pins_of_one_part_share_one_group_key():
    key = flaggroups.share_part("USB1")
    assert key == "part:USB1"
    assert key != flaggroups.SHARE_CHAIN
    assert key != flaggroups.SHARE_ALONE

    def distance(start, end):
        return abs(start[0] - end[0]) + abs(start[1] - end[1])

    groups = flaggroups.group_flag_candidates(
        [
            _seat("USB1.1", (0.0, 0.0), key),
            _seat("USB1.2", (30.0, 0.0), key),
            _seat("USB1.A1B12", (300.0, 0.0), key),
        ],
        distance, 100.0,
    )
    assert [[candidate.member for candidate in group] for group in groups] == [
        ["USB1.1", "USB1.2"], ["USB1.A1B12"],
    ], groups


def test_a_ruler_asks_the_router_once_per_pair():
    calls = []

    def route(start, end):
        calls.append((start, end))
        return [start, end]

    ruler = flaggroups.RouteRuler(route)
    a, b = (0.0, 0.0), (40.0, 0.0)
    assert ruler(a, b) == pytest.approx(40.0)
    assert ruler(b, a) == pytest.approx(40.0)
    assert len(calls) == 1, calls
    # The length is the path's, accumulated leg by leg.
    turned = flaggroups.RouteRuler(
        lambda s, e: [s, (e[0], s[1]), e]
    )
    assert turned((0.0, 0.0), (30.0, 40.0)) == pytest.approx(70.0)


def test_a_partition_is_compared_by_its_members_not_its_order():
    left = [[_seat("A", (0.0, 0.0)), _seat("B", (1.0, 0.0))], [_seat("C", (2.0, 0.0))]]
    right = [[_seat("B", (1.0, 0.0)), _seat("A", (0.0, 0.0))], [_seat("C", (2.0, 0.0))]]
    assert flaggroups.partition_signature(left) == flaggroups.partition_signature(right)
    other = [[_seat("A", (0.0, 0.0))], [_seat("B", (1.0, 0.0)), _seat("C", (2.0, 0.0))]]
    assert flaggroups.partition_signature(left) != flaggroups.partition_signature(other)
