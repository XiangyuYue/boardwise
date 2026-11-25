"""571F: constraint 4's pin-tip exemption belongs to a sub-edge, not a segment.

Before 571F `readability._check_bodies` asked "is either *outer end* of this
polyline on one of that part's pin tips?" and, when the answer was yes, skipped
the whole polyline against that part. A conductor that leaves a part's own pin,
loops back and crosses that same part's drawn body therefore passed: 571's
reproduction (`outputs/hole571/f/REPRO.md`, `probes/probe_own_body.py`) rerouted
scene-1's VIN segment into a loop whose middle sub-edge runs 16.0u through C1's
own body `(22, 683, 38, 707)` — exactly across both plates — and `check()` said
`ok=True`, 0 findings.

The four tests here pin the fixed ruler on that same scene:

* the 571 loop is reported as ``wire-through-body`` on ``parts[C1]`` (red before
  the fix, because the old exemption swallowed it);
* a wire that arrives at a pin tip and only *touches* the body boundary is not
  reported (the box is inset by `TOL`, so a boundary ride has no interior);
* an L-shaped detour whose bounding box covers the body but whose sub-edges do
  not is not reported (the clip is per sub-edge — a bbox test would fire);
* a wire crossing *another* part's body is still reported while both its ends
  are on pins (the exemption must not leak out of the part that owns the tip).

The fixture is 056's scene 1, compiled in memory and rerouted with
``dataclasses.replace`` — the same construction the 571 probe used, with no
import from ``outputs/`` and nothing written to disk.
"""
from __future__ import annotations

import dataclasses

import pytest

import test_056_pagecompiler as m056

from boardwise.engines import readability

#: C1 in 056 scene 1, asserted at the fixture rather than trusted: if the layout
#: moves, these tests fail where the geometry is read instead of somewhere
#: downstream with a different number.
C1_BODY = (22.0, 683.0, 38.0, 707.0)
C1_1 = (30.0, 735.0)
C1_2 = (30.0, 655.0)
U1_3 = (90.0, 735.0)
C2_BODY = (262.0, 683.0, 278.0, 707.0)


@pytest.fixture(scope="module")
def scene1():
    """056 scene 1, compiled: ``(scene, plan, profiles)``."""
    scene = m056.scenes()[1]
    result = m056.compile_scene(scene)
    assert result.ok, m056.render(result)
    return scene, result.pages[0].plan, m056.library()


@pytest.fixture(scope="module")
def c1(scene1):
    _, plan, profiles = scene1
    placed = readability._placed_parts(plan, readability._profile_map(profiles))
    part = next(p for p in placed if p.part_id == "C1")
    assert part.body == C1_BODY, part.body
    assert part.pins == {"1": C1_1, "2": C1_2}, part.pins
    return part


def _reroute(plan, points):
    """The same page with segment 0's own points replaced; nothing else moves."""
    segment = dataclasses.replace(plan.segments[0], points=[tuple(p) for p in points])
    return dataclasses.replace(plan, segments=[segment, *plan.segments[1:]])


def _check(scene, plan, profiles):
    return readability.check(
        plan, scene.circuit, scene.presentation, profiles,
        page_box=scene.budget.page_box, keepouts=scene.budget.keepouts,
        grid=scene.budget.grid,
    )


def _bodies(checked):
    """Every ``wire-through-body`` finding as ``(kind, objects)``."""
    return [
        (item.kind, item.objects)
        for item in checked.hard_violations
        if item.kind == readability.KIND_WIRE_THROUGH_BODY
    ]


def test_571f_a_loop_through_its_own_parts_body_is_reported(scene1, c1):
    """571's own reproduction: both ends on pins, middle sub-edge through C1."""
    scene, plan, profiles = scene1
    assert plan.segments[0].net == "VIN"
    loop = [C1_1, (10.0, 735.0), (10.0, 695.0), (60.0, 695.0), U1_3]
    # Precondition of the defect, measured with the module's own ruler: the
    # middle sub-edge runs exactly 16.0u inside C1's body, over both plates.
    assert readability._box_chord(loop[2], loop[3], c1.body) == pytest.approx(16.0)

    checked = _check(scene, _reroute(plan, loop), profiles)

    assert _bodies(checked) == [
        (readability.KIND_WIRE_THROUGH_BODY, ("segments[0]", "parts[C1]")),
    ]
    assert checked.ok is False


def test_571f_arriving_at_a_pin_and_touching_only_the_body_edge_is_clean(scene1, c1):
    """The sub-edge that reaches the tip is exempt, but a boundary ride is no crossing."""
    scene, plan, profiles = scene1
    # (30,735) -> (30,707): stops exactly on the body's top edge; then the wire
    # rides that edge to U1 and arrives at U1.3 from outside the symbol.
    path = [C1_1, (30.0, 707.0), (90.0, 707.0), U1_3]
    # Precondition: it really runs along C1's boundary, with no strict-interior
    # chord — the inset ruler constraint 4 uses, not the inset=0 one.
    assert readability._clip_to_box(path[1], path[2], c1.body) is None

    checked = _check(scene, _reroute(plan, path), profiles)

    assert _bodies(checked) == []
    assert checked.hard_violations == []
    assert checked.ok is True


def test_571f_an_l_shaped_detour_around_the_body_is_clean(scene1, c1):
    """The detour's bbox covers the body; every sub-edge misses it — not a crossing."""
    scene, plan, profiles = scene1
    path = [
        C1_1, (10.0, 735.0), (10.0, 680.0), (50.0, 680.0), (50.0, 735.0), U1_3,
    ]
    # Precondition: a bbox-based test would fire against exactly this body.
    xs = [point[0] for point in path]
    ys = [point[1] for point in path]
    assert min(xs) < c1.body[0] and max(xs) > c1.body[2]
    assert min(ys) < c1.body[1] and max(ys) > c1.body[3]

    checked = _check(scene, _reroute(plan, path), profiles)

    assert _bodies(checked) == []
    assert checked.hard_violations == []
    assert checked.ok is True


def test_571f_crossing_another_parts_body_is_still_reported(scene1):
    """Both ends on pins of C1/U1, the wire threads C2's body: C2 is not exempt."""
    scene, plan, profiles = scene1
    # The long middle sub-edge at y=695 runs 16.0u through C2's body; it ends on
    # no C2 pin tip, and C2 owns none of this segment's ends.
    path = [
        C1_1, (70.0, 735.0), (70.0, 695.0), (290.0, 695.0), (90.0, 695.0), U1_3,
    ]
    assert readability._box_chord(path[2], path[3], C2_BODY) == pytest.approx(16.0)

    checked = _check(scene, _reroute(plan, path), profiles)

    assert _bodies(checked) == [
        (readability.KIND_WIRE_THROUGH_BODY, ("segments[0]", "parts[C2]")),
    ]
    assert checked.ok is False
