"""Task 038k: the ``["R", x, y, w, h, rotation, radius]`` rectangle and its angle.

Before this task :func:`boardwise.parsers.epru._path_points` read ``rotation``
and threw it away, so a rotated area rectangle was expanded as an axis-aligned
box in the wrong place. 毕设FOC 1.0.0 carries three such ``POUR`` regions; two of
them (``rotation: -90``) poured real copper, and the copper is what pinned the
transform:

* pivot = the rectangle's **own stored ``(x, y)`` corner**, and
* the declared angle is applied **counter-clockwise in the y-up frame**.

Both readings come from the same measurement: the two regions' ``POURED``
points sit exactly 4 mil (the pour's edge clearance) inside the rotated
rectangle under this transform and outside it under every other pivot tried
(the rectangle's centre leaves 5 of 5 points out, 109.3 mil away). The
``POURED`` side of that evidence is asserted where the fixtures are — see
``tests/test_135_poured_result.py``; what this file pins is the **transform
itself**, on synthetic rectangles, so 90/180/270 are not hostage to the one
angle a fixture happens to carry.
"""

from __future__ import annotations

import pytest

from boardwise.parsers.epru import _path_points

#: w = 50, h = 20, pivot (100, -200) — small integers so a wrong formula cannot
#: hide inside the file's own 4-decimal noise.
BASE = (100.0, -200.0, 50.0, 20.0)

#: ``(angle, the four corners it must produce, in the order this reader emits
#: them)``. The first corner is the pivot itself under every angle — that is
#: the whole of the pivot claim, stated as the reading rather than as a comment.
#: ``0`` and ``360`` are the same square, ``270`` and ``-90`` likewise.
CASES = [
    (0.0, [(100.0, -200.0), (150.0, -200.0), (150.0, -220.0), (100.0, -220.0)]),
    (90.0, [(100.0, -200.0), (100.0, -150.0), (120.0, -150.0), (120.0, -200.0)]),
    (180.0, [(100.0, -200.0), (50.0, -200.0), (50.0, -180.0), (100.0, -180.0)]),
    (270.0, [(100.0, -200.0), (100.0, -250.0), (80.0, -250.0), (80.0, -200.0)]),
    (-90.0, [(100.0, -200.0), (100.0, -250.0), (80.0, -250.0), (80.0, -200.0)]),
    (360.0, [(100.0, -200.0), (150.0, -200.0), (150.0, -220.0), (100.0, -220.0)]),
]


def _rect(rotation: float, radius: float = 0.0) -> list:
    x, y, w, h = BASE
    return ["R", x, y, w, h, rotation, radius]


def _points(path) -> list[tuple[float, float]]:
    return [(point.x, point.y) for point in _path_points(path)]


def _area(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for index, (ax, ay) in enumerate(points):
        bx, by = points[(index + 1) % len(points)]
        total += ax * by - bx * ay
    return abs(total) / 2.0


@pytest.mark.parametrize("angle,expected", CASES)
def test_the_declared_angle_turns_the_rectangle_about_its_own_corner(angle, expected):
    """Point for point, at every right angle — pivot (first corner) and sign.

    A wrong pivot moves at least the three non-pivot corners; a flipped sign
    swaps the 90 and 270 rows (and sends 180 to ``(150, -180)`` neighbourhoods
    the table does not contain), so the table cannot be satisfied by either.
    """
    assert _points(_rect(angle)) == expected


@pytest.mark.parametrize("angle", [0.0, 30.0, 45.0, 90.0, 135.0, 180.0, 270.0, 360.0])
def test_a_rotation_preserves_the_area(angle):
    """``w * h`` is the one quantity no pivot, sign or rounding may change.

    The fixture's own two anchors are checked by containment over there; this
    is the same statement where it can be exact — and it is also the check that
    survives a future non-right angle, which no fixture supplies.
    """
    _, _, w, h = BASE
    assert _area(_points(_rect(angle))) == pytest.approx(w * h)


@pytest.mark.parametrize(
    "path",
    [
        # The four shapes that must read exactly as they did before 038k: a
        # rotation the file did not state, a stated zero, no rotation slot at
        # all, and a degenerate rectangle.
        ["R", 100.0, -200.0, 50.0, 20.0, 0.0, 0.0],
        ["R", 100.0, -200.0, 50.0, 20.0],
        ["R", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ["R", -1.811, -3.189, 6102.3622, 3149.6063, 0, 150],
    ],
)
def test_an_unrotated_rectangle_keeps_its_old_reading(path):
    """Byte for byte the pre-038k answer — including the unrounded values.

    The unrounded part is the reason this test uses a 9-decimal coordinate
    below: ``rotation == 0`` must not acquire ``COORD_PRECISION`` rounding,
    which is only there to strip the trig noise of a real turn.
    """
    x, y, w, h = (float(value) for value in path[1:5])
    assert _points(path) == [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]


def test_an_unrotated_coordinate_is_not_rounded():
    value = 0.123456789
    points = _points(["R", value, -value, 1.0, 1.0, 0.0, 0.0])
    assert points[0] == (value, -value)
    assert points[2] == (value + 1.0, -value - 1.0)


@pytest.mark.parametrize("angle", [0.0, 30.0, 90.0])
def test_the_radius_is_still_not_read(angle):
    """``radius`` (rounded corners) is ignored here and stays ignored.

    This reader flattens a rectangle to four straight corners; it never read
    ``radius`` and 038k does not start to. A rotated *rounded* rectangle has no
    reading in this function — the test says so by pinning that the radius
    changes nothing, rather than by pretending the shape is supported.
    """
    for radius in (0.0, 5.0, 500.0):
        assert _points(_rect(angle, radius)) == _points(_rect(angle, 0.0))
