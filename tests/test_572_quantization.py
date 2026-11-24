"""572 / W-E3: the page's 0.01 reading and the half-cent boundary.

567-E-3 (``outputs/hole567/e/REPRO.md``) measured the failure: the page reports
coordinates at 0.01, the tolerance was exactly the rounding step's half (0.005),
and when the binary difference lands a hair above it — `0.0050000000000008` —
`_near` / `_near_polyline` call the plan's own landed point a miss. 348 of the
4001 half-cent readings in `[-20, 20]` fail that way, so a legal plan's
`postcondition_problems` is not empty and a repeat `draw apply` never reaches
`already_applied`.

The fix is not a wider tolerance (0.006 would swallow the neighbouring grid
step): at the page's own precision "the same point" is *the same 0.01 cell*,
compared after rounding both readings, and the polyline test quantizes first and
then reuses the exact :func:`_on_polyline`. Every other tolerance keeps the
old real-distance comparison, which these tests pin as well.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from boardwise.core.changeplan import ChangePlan
from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "drawapply"
CIRCUIT = FIXTURES / "divider.circuit.json"
PRESENTATION = FIXTURES / "divider.presentation.json"
LIBRARY = FIXTURES / "library.json"
PAGE_BOX = (0.0, -1000.0, 1200.0, 0.0)
LCSC = {"R1": "C25744", "R2": "C25744"}

#: Half a page step, the tolerance `_near`/`_near_polyline` default to.
HALF_STEP = drawapply.PAGE_POINT_PRECISION / 2.0

#: A translation that moves the divider's `-70` to `-63.985`, one of the
#: half-cent readings whose float difference is `0.0050000000000026 > 0.005`.
HALF_CENT_DY = 6.015


# ------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def circuit() -> CircuitSpec:
    return CircuitSpec.load(CIRCUIT)


@pytest.fixture(scope="module")
def presentation() -> PresentationSpec:
    return PresentationSpec.load(PRESENTATION)


@pytest.fixture(scope="module")
def profiles() -> dict:
    return drawapply.load_library(LIBRARY)


@pytest.fixture(scope="module")
def compiled(circuit, presentation, profiles):
    return drawcompiler.compile(
        circuit, presentation, profiles, drawcompiler.CompileBudget(page_box=PAGE_BOX)
    )


@pytest.fixture()
def plan(compiled, circuit, presentation, profiles) -> ChangePlan:
    return drawapply.module_plan(
        compiled.candidates[0], circuit, presentation, profiles,
        lcsc_by_part=LCSC,
        notes=["plan built by test_572"],
    )


# ------------------------------------------------------------------ helpers


def _live() -> dict[tuple[str, str], str]:
    """The divider's own live netlist, in `patchpin.live_pin_nets`' shape."""
    return {
        ("R1", "1"): "VIN", ("R1", "2"): "TAP",
        ("R2", "1"): "TAP", ("R2", "2"): "GND",
    }


def _page(plan: ChangePlan) -> dict:
    """The page the plan landed on: every coordinate the host's 0.01 reading.

    `round(v, 2)` is the read-back the module measured
    (:data:`drawapply.PAGE_POINT_PRECISION`; `candidate.py` reads the same way).
    """
    components = [
        (part.designator, round(part.x, 2), round(part.y, 2), part.rotation, part.mirror)
        for part in plan.change.draw_parts
    ]
    named = [drawapply.wire_carries_its_name(wire) for wire in plan.change.draw_wires]
    wires = [
        (f"w-{index}", wire.net if carries else "",
         [(round(float(point[0]), 2), round(float(point[1]), 2)) for point in wire.points])
        for index, (wire, carries) in enumerate(zip(plan.change.draw_wires, named))
    ]
    netflags = [(flag.net, round(flag.x, 2), round(flag.y, 2))
                for flag in plan.change.draw_flags]
    values = {
        part.designator: part.value
        for part in plan.change.draw_parts if part.value_key
    }
    return {
        "components": [
            {"primitiveId": f"p-{name}",
             "state": {"Designator": name, "X": x, "Y": y, "ComponentType": "part",
                       "Rotation": rotation, "Mirror": mirror,
                       **({"OtherProperty": {"Value": values[name]}}
                          if name in values else {})}}
            for name, x, y, rotation, mirror in components
        ]
        + [{"primitiveId": "sheet-1",
            "state": {"ComponentType": "sheet", "Designator": "", "X": 0, "Y": 0}}]
        + [
            {"primitiveId": f"flag-{index}",
             "state": {"ComponentType": "netflag", "Designator": None, "Net": net,
                       "X": x, "Y": y}}
            for index, (net, x, y) in enumerate(netflags)
        ],
        "wires": [
            {"primitiveId": primitive_id,
             "state": {"Line": [c for pair in points for c in pair], "Net": net}}
            for primitive_id, net, points in wires
        ],
        "netlabels": [],
        "bboxes": {"sheet-1": {"minX": 0, "minY": -1000, "maxX": 1200, "maxY": 0}},
        "meta": {"available": {"components": True, "wires": True, "bboxes": True}},
    }


def _pins(plan: ChangePlan) -> dict[tuple[str, str], tuple[float, float]]:
    return {
        (part.designator, pin.number): (part.x + pin.dx, part.y + pin.dy)
        for part in plan.change.draw_parts
        for pin in part.pins
    }


def _translated(plan: ChangePlan, dx: float, dy: float) -> ChangePlan:
    """The same drawing, translated — a legal plan whose points moved.

    A translation, not a hand-edited point, so every relative position (pin to
    wire end, flag to wire end) stays exactly what the drawing asked for; only
    the page's 0.01 reading then has to round.
    """
    payload = copy.deepcopy(plan.to_jsonable())
    change = payload["change"]
    for part in change["parts"]:
        part["x"] += dx
        part["y"] += dy
    for flag in change["flags"]:
        flag["x"] += dx
        flag["y"] += dy
    for wire in change["wires"]:
        wire["points"] = [[point[0] + dx, point[1] + dy] for point in wire["points"]]
    return ChangePlan.from_jsonable(payload)


def _float_difference_exceeds_half_step(value: float) -> bool:
    """Is this reading's own float difference *above* the half step?"""
    return not abs(value - round(value, 2)) <= HALF_STEP


# ------------------------------------------- 1. every half-cent reading, once


def test_every_half_cent_reading_on_the_page_is_the_same_point() -> None:
    """The exhaustive form of 567-E-3: all 4001 half-cent values in [-20, 20].

    Before the fix the float comparison failed for 348 of them; the assertion on
    the count keeps this test from going vacuous if the arithmetic ever changes.
    """
    failing = []
    for step in range(-2000, 2001):
        value = step / 100 + 0.005
        page = round(value, 2)
        assert drawapply._near((value, 0.0), (page, 0.0), HALF_STEP), (
            f"{value!r} reads back as {page!r} and must be the same point"
        )
        assert drawapply._near_polyline((value, 0.0), [(page, -1.0), (page, 1.0)]), (
            f"{value!r} reads back as {page!r} and must be on the page's own line"
        )
        if _float_difference_exceeds_half_step(value):
            failing.append(value)
    assert len(failing) == 348, (
        "the reproduced population: 348 of 4001 half-cent readings have a float "
        f"difference above the half step, got {len(failing)}"
    )


def test_the_neighbouring_grid_step_is_not_the_same_point() -> None:
    """Negative control: the fix is grid identity, not a wider tolerance."""
    assert not drawapply._near((0.0, 0.0), (0.01, 0.0), HALF_STEP)
    assert not drawapply._near((0.0, 0.0), (0.0, 0.01), HALF_STEP)
    assert not drawapply._near_polyline((0.0, 0.0), [(0.01, -1.0), (0.01, 1.0)])
    # A tolerance of 0.006 would have called this one point; grid identity does not.
    assert abs(0.006) <= 0.006
    assert not drawapply._near((0.0, 0.0), (0.006, 0.0), HALF_STEP)


# ------------------------------------- 2. a real plan, landed and satisfied


def test_a_legal_plan_becomes_fully_satisfied_on_its_half_cent_page(plan: ChangePlan) -> None:
    """567-E-3's consequence: `all_satisfied` must be True for a real landing.

    The divider plan is translated by `HALF_CENT_DY` so its wire ends and flags
    sit on half-cent readings; the page is that plan read back at 0.01. Both the
    `_near` leg (flag anchors) and the `_near_polyline` leg (wire ends on page
    segments) see a float difference above 0.005 on this page.
    """
    shifted = _translated(plan, 0.0, HALF_CENT_DY)
    ends = [
        (float(wire.points[index][0]), float(wire.points[index][1]))
        for wire in shifted.change.draw_wires
        for index in (0, -1)
    ]
    anchors = [(float(flag.x), float(flag.y)) for flag in shifted.change.draw_flags]
    assert any(_float_difference_exceeds_half_step(y) for _x, y in ends + anchors), (
        "the chosen translation must actually put a point on a half-cent reading "
        "whose float difference is above 0.005, or this test proves nothing"
    )

    state = drawapply.postcondition_problems(
        shifted,
        live=_live(),
        geometry=_page(shifted),
        pins=_pins(shifted),
    )
    assert state["canvas"] == []
    assert drawapply.all_satisfied(state)

    # The untranslated plan still passes: the fix did not trade one page for another.
    state = drawapply.postcondition_problems(
        plan, live=_live(), geometry=_page(plan), pins=_pins(plan)
    )
    assert state == {"live": [], "canvas": []}


# ------------------------------------ 3. every other tolerance is unchanged


def test_a_non_default_tolerance_keeps_the_real_distance_reading() -> None:
    """Only `PAGE_POINT_PRECISION / 2` takes the grid path; 1e-6 and HALF_GRID do not."""
    point = (95.005, -80.0)
    line = [(95.0, -80.0), (95.0, -70.0)]
    # The page's precision: the same 0.01 cell.
    assert drawapply._near(point, (95.0, -80.0), HALF_STEP)
    assert drawapply._near_polyline(point, line)
    # Exact-ish tolerance: half a hundredth is not the same point.
    assert not drawapply._near(point, (95.0, -80.0), 1e-6)
    assert not drawapply._near_polyline(point, line, 1e-6)
    # The drawing lattice's half step (2.5) is untouched.
    assert drawapply._near(point, (95.0, -80.0), drawapply.HALF_GRID)
    # A page point one grid step away is not swallowed by any of them.
    assert not drawapply._near((95.0, -80.0), (95.01, -80.0), HALF_STEP)
    assert not drawapply._near_polyline((95.01, -80.0), line, HALF_STEP)
