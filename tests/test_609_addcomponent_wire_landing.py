"""609 — add-component's wire *segments* and finite landing spots (570-D1/D2/D3).

The three holes are one domain: the placement geometry treats a wire as a pair
of vertices. A wire that passes through the spot is 0 units away yet refused
(D1); a long wire's middle is "free", so a capacitor lands on copper it does not
touch (D2); and a non-finite coordinate is either silently "free" or silently
turns every rung into "occupied" (D3).

The negative controls are the behaviour that must not move: a vertex connection,
a cross-net refusal, a one-cell boundary and the plain finite ladder.
"""

from __future__ import annotations

import math

import pytest

from boardwise.core import changeplan
from boardwise.engines import addcomponent


def _geometry(wires=(), components=()):
    """A `sch.geometry` dump with the measured wire shape (`Line` + `Net`)."""
    return {
        "components": [
            {"primitiveId": f"p-{name}", "state": {"Designator": name, "X": x, "Y": y}}
            for name, x, y in components
        ],
        "wires": [
            {"primitiveId": f"w-{index}",
             "state": {"Line": [c for pair in points for c in pair], "Net": net}}
            for index, (net, points) in enumerate(wires)
        ],
        "netlabels": [],
        "meta": {"available": {"components": True}},
    }


def _close(a, b, tol=1e-9):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


# ---------------------------------------------------------------- D1: nearest


def test_a_wire_through_the_spot_is_zero_units_away():
    geometry = _geometry(wires=[("SIG", [(-200.0, 0.0), (200.0, 0.0)])])
    near = addcomponent.nearest_wire_point((0.0, 0.0), geometry, "SIG")
    assert near is not None
    assert _close(near[:2], (0.0, 0.0)), near
    assert near[2] == pytest.approx(0.0)


def test_choose_connection_accepts_a_wire_that_passes_through_the_spot():
    geometry = _geometry(wires=[("SIG", [(-200.0, 0.0), (200.0, 0.0)])])
    choice = addcomponent.choose_connection("SIG", (0.0, 0.0), geometry)
    assert choice.kind == changeplan.CONNECTION_WIRE
    assert _close(choice.to, (0.0, 0.0))


def test_the_second_segment_of_a_polyline_is_measured_not_only_its_vertices():
    # (-200,0) -> (0,0) -> (0,200): the point (0,120) lies on the *second* run,
    # far from every reported vertex.
    geometry = _geometry(
        wires=[("SIG", [(-200.0, 0.0), (0.0, 0.0), (0.0, 200.0)])]
    )
    near = addcomponent.nearest_wire_point((0.0, 120.0), geometry, "SIG")
    assert near is not None
    assert _close(near[:2], (0.0, 120.0)), near
    assert near[2] == pytest.approx(0.0)


def test_a_reversed_wire_and_a_zero_length_wire_are_projected_correctly():
    reversed_line = _geometry(wires=[("SIG", [(200.0, 0.0), (-200.0, 0.0)])])
    near = addcomponent.nearest_wire_point((50.0, 0.0), reversed_line, "SIG")
    assert _close(near[:2], (50.0, 0.0)) and near[2] == pytest.approx(0.0)

    degenerate = _geometry(wires=[("SIG", [(50.0, 50.0), (50.0, 50.0)])])
    near = addcomponent.nearest_wire_point((50.0, 50.0), degenerate, "SIG")
    assert _close(near[:2], (50.0, 50.0)) and near[2] == pytest.approx(0.0)


def test_the_projection_is_clamped_to_the_segment_ends():
    geometry = _geometry(wires=[("SIG", [(0.0, 0.0), (100.0, 0.0)])])
    near = addcomponent.nearest_wire_point((-40.0, 0.0), geometry, "SIG")
    assert _close(near[:2], (0.0, 0.0))
    assert near[2] == pytest.approx(40.0)


def test_cross_net_and_out_of_radius_keep_their_refusals():
    geometry = _geometry(wires=[("SIG", [(-200.0, 0.0), (200.0, 0.0)])])
    assert addcomponent.nearest_wire_point((0.0, 0.0), geometry, "VCC") is None
    # A foreign, non-rail net: no wire, no flag, no label -> a named refusal.
    with pytest.raises(addcomponent.NoConnectionOption):
        addcomponent.choose_connection("SIG2", (0.0, 0.0), geometry)

    far = _geometry(wires=[("SIG", [(500.0, 0.0), (500.0, 400.0)])])
    with pytest.raises(addcomponent.NoConnectionOption):
        addcomponent.choose_connection("SIG", (0.0, 0.0), far)


def test_a_non_finite_spot_or_wire_produces_no_nearest_point():
    geometry = _geometry(wires=[("SIG", [(-200.0, 0.0), (200.0, 0.0)])])
    assert addcomponent.nearest_wire_point((math.nan, 0.0), geometry, "SIG") is None
    assert addcomponent.nearest_wire_point((0.0, math.inf), geometry, "SIG") is None

    broken = _geometry(wires=[("SIG", [(math.nan, 0.0), (200.0, 0.0)])])
    assert addcomponent.nearest_wire_point((0.0, 0.0), broken, "SIG") is None


# -------------------------------------------------------------- D2: occupied


def test_a_wires_midpoint_is_occupied_not_free():
    geometry = _geometry(wires=[("GND", [(-200.0, 0.0), (200.0, 0.0)])])
    occupied = addcomponent.occupied_points(geometry)
    assert isinstance(occupied, list)
    assert all(isinstance(point, tuple) and len(point) == 2 for point in occupied)
    assert addcomponent.is_free(0.0, 0.0, occupied) is False


def test_a_spot_on_a_wire_mid_segment_does_not_land_there():
    geometry = _geometry(wires=[("GND", [(-200.0, 0.0), (200.0, 0.0)])])
    spot = addcomponent.landing_spot((0.0, 0.0), addcomponent.occupied_points(geometry))
    assert spot.offset != (0, 0)
    assert abs(spot.y) >= addcomponent.LANDING_CLEARANCE, spot  # the wire is at y=0
    assert addcomponent.is_free(spot.x, spot.y, addcomponent.occupied_points(geometry))


def test_off_midpoint_positions_on_a_long_wire_are_covered_too():
    geometry = _geometry(wires=[("GND", [(0.0, 0.0), (800.0, 0.0)])])
    occupied = addcomponent.occupied_points(geometry)
    for x in (0.0, 37.5, 123.4, 400.0, 743.7, 800.0):
        assert addcomponent.is_free(x, 0.0, occupied) is False, x
    # One clearance away is still free — the sampler must not blanket the page.
    assert addcomponent.is_free(400.0, 5.0, occupied) is True


def test_the_second_run_of_a_polyline_is_occupied_as_well():
    geometry = _geometry(
        wires=[("GND", [(0.0, 0.0), (100.0, 0.0), (100.0, 600.0)])]
    )
    occupied = addcomponent.occupied_points(geometry)
    for y in (37.5, 300.0, 543.2):
        assert addcomponent.is_free(100.0, y, occupied) is False, y


def test_the_plain_boundary_and_far_points_stay_free():
    assert addcomponent.is_free(5.0, 0.0, [(0.0, 0.0)]) is True
    geometry = _geometry(wires=[("GND", [(0.0, 0.0), (200.0, 0.0)])])
    occupied = addcomponent.occupied_points(geometry)
    assert addcomponent.is_free(100.0, 12.0, occupied) is True


# ---------------------------------------------------------------- D3: finite


def test_is_free_refuses_non_finite_candidates():
    assert addcomponent.is_free(math.nan, math.nan, []) is False
    assert addcomponent.is_free(math.inf, 0.0, []) is False
    assert addcomponent.is_free(0.0, -math.inf, []) is False


def test_is_free_refuses_non_finite_occupants_instead_of_faking_a_full_page():
    assert addcomponent.is_free(0.0, 0.0, [(math.nan, 0.0)]) is False
    assert addcomponent.is_free(0.0, 0.0, [(0.0, math.inf)]) is False


def test_landing_spot_refuses_a_non_finite_origin_instead_of_returning_nan():
    with pytest.raises(ValueError):
        addcomponent.landing_spot((math.nan, 1.0), [])
    with pytest.raises(ValueError):
        addcomponent.landing_spot((0.0, math.inf), [])


def test_landing_spot_refuses_a_non_positive_or_non_finite_grid():
    for grid in (0.0, -5.0, math.nan, math.inf):
        with pytest.raises(ValueError):
            addcomponent.landing_spot((0.0, 0.0), [], ladder=[(1, 0)], grid=grid)


def test_landing_spot_refuses_a_rung_that_overflows_to_infinity():
    with pytest.raises(ValueError):
        addcomponent.landing_spot((0.0, 0.0), [], ladder=[(10, 0)], grid=1e308)


def test_the_finite_ladder_is_unchanged():
    spot = addcomponent.landing_spot((0.0, 0.0), [])
    assert (spot.x, spot.y, spot.offset, spot.index) == (0.0, 0.0, (0, 0), 0)
    with pytest.raises(addcomponent.LadderExhausted):
        addcomponent.landing_spot((0.0, 0.0), [(dx * 5.0, dy * 5.0) for dx, dy in addcomponent.LADDER])
