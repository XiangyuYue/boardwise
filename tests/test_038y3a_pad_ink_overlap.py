"""Tests for task 038Y3A: the layer-aware ink-on-pad-copper predicate.

``pad_ink_overlap(board, pad, *, points, half_width, layers, filled, closed)``
answers exactly one question — 「does this piece of silkscreen ink share a
**positive area** with that pad's real copper」 — and answers it with a bool. It
is the primitive the silkscreen rules will sit on; no rule is registered here.

The pre-study that motivated this batch measured the pad with ``pad_corners()``
(i.e. its **bounding box**) and mixed stroke depth with fill depth into one
number. Two things are pinned below against that reading:

* ink that lies in the **ear** of a round pad's box — inside the rectangle,
  outside the disc, 6.568 mil of air from the copper — must **not** hit, while a
  stroke that really crosses the disc must;
* a filled ring's **interior** is ink, so a concave fill that surrounds a pad is
  a hit, and the same fill's notch is **not** — the negative control that
  separates 「inside the outline's box」 from 「inside the outline」.

Every pad and every ring is hand-built here; no fixture, no parser. Shapes come
from :func:`boardwise.core.measure._pad_copper` (038V), so what is under test is
the same copper the rest of ``measure`` measures: disc, stadium, rotated
rectangle, circumscribing ``ELLIPSE`` 32-gon.
"""

from __future__ import annotations

import math

import pytest

from boardwise.core.geometry import (
    BoardGeometry,
    ComponentPlacement,
    LayerInfo,
    PadGeometry,
    Point,
    StackupEntry,
)
from boardwise.core.measure import _pad_copper, pad_corners, pad_ink_overlap

#: 顶层丝印所在的铜面（surface finish 一侧），也是所有测试的默认墨迹层。
TOP = 1
#: 底层丝印所在的铜面。
BOTTOM = 2


def _pad(
    id: str,
    *,
    x: float = 0.0,
    y: float = 0.0,
    width: float = 0.0,
    height: float = 0.0,
    shape: str = "RECT",
    angle: float = 0.0,
    layer_id: int | None = TOP,
) -> PadGeometry:
    """One hand-built pad; ``angle`` is board-frame (125a's contract)."""
    return PadGeometry(
        id=id,
        footprint_layer_id=layer_id,
        x=x,
        y=y,
        width=width,
        height=height,
        shape=shape,
        angle=angle,
    )


def _board(*pads: PadGeometry, components: list[ComponentPlacement] | None = None) -> BoardGeometry:
    """A hand-built two-layer board — the layer table the readings pin."""
    layers = {
        TOP: LayerInfo(TOP, "Top Layer", "TOP"),
        BOTTOM: LayerInfo(BOTTOM, "Bottom Layer", "BOTTOM"),
    }
    stackup = [
        StackupEntry(TOP, 1000, "外层铜厚", 1.378),
        StackupEntry(BOTTOM, 9000, "外层铜厚", 1.378),
    ]
    return BoardGeometry(
        layers=layers,
        stackup=stackup,
        pads=list(pads),
        components=list(components or []),
    )


def _rect(
    id: str, x: float, y: float, width: float, height: float, *, angle: float = 0.0
) -> PadGeometry:
    return _pad(id, x=x, y=y, width=width, height=height, shape="RECT", angle=angle)


def _disc(
    id: str, x: float, y: float, diameter: float = 100.0, *, layer_id: int = TOP
) -> PadGeometry:
    return _pad(
        id, x=x, y=y, width=diameter, height=diameter, shape="ELLIPSE", layer_id=layer_id
    )


def _oval(id: str, x: float, y: float, width: float, height: float) -> PadGeometry:
    return _pad(id, x=x, y=y, width=width, height=height, shape="OVAL")


def _ellipse(id: str, x: float, y: float, width: float, height: float) -> PadGeometry:
    return _pad(id, x=x, y=y, width=width, height=height, shape="ELLIPSE")


def _pt(x: float, y: float) -> Point:
    return Point(x, y)


def _in_box(pad: PadGeometry, point: Point) -> bool:
    """Is ``point`` inside the pad's **bounding box** — the pre-study's reading?"""
    corners = pad_corners(pad)
    return (
        min(c.x for c in corners) < point.x < max(c.x for c in corners)
        and min(c.y for c in corners) < point.y < max(c.y for c in corners)
    )


def _ray_exit(polygon: list[Point], dx: float, dy: float) -> float:
    """Distance from the origin to where the ray ``t (dx, dy)`` leaves ``polygon``.

    ``origin + t d = a + s e`` is solved by cross products:
    ``t = cross(a, e) / cross(d, e)`` and ``s = cross(a, d) / cross(d, e)``. For a
    convex polygon containing the origin the largest ``t`` with ``s`` on the edge
    is the exit point.
    """
    best = 0.0
    count = len(polygon)
    for index in range(count):
        a = polygon[index]
        b = polygon[(index + 1) % count]
        ex, ey = b.x - a.x, b.y - a.y
        denom = dx * ey - dy * ex
        if abs(denom) <= 1e-15:
            continue
        t = (a.x * ey - a.y * ex) / denom
        s = (a.x * dy - a.y * dx) / denom
        if -1e-12 <= s <= 1.0 + 1e-12 and t > best:
            best = t
    return best


# ---------------------------------------------------------------------------
# the pre-study's false positive: ink in the ear of a disc's box
# ---------------------------------------------------------------------------

#: Ø100 mil disc: its box corner is 50 * sqrt(2) = 70.71 mil from the centre.
DISC_D = 100.0
DISC_R = DISC_D / 2


def test_ink_in_the_ear_of_a_disc_box_is_not_ink_on_copper():
    """The pre-study's box test would fire here; the copper says 6.568 mil of air.

    A Ø100 mil disc at the origin, and a 1 mil-wide ink dot at ``(40, 40)``. The
    dot is **inside** the pad's bounding box (``[-50, 50]`` squared), which is
    what makes the box reading tempting. It is ``40 * sqrt(2)`` = 56.568542
    mil from the centre, so it stands ``56.568542 - 50`` = **6.568542** mil off
    the copper edge — seven times its own stroke radius away, with no area in
    common.
    """
    pad = _disc("d", 0, 0, DISC_D)
    board = _board(pad)
    ink = [_pt(40.0, 40.0)]

    assert _in_box(pad, ink[0])
    assert math.hypot(40.0, 40.0) - DISC_R == pytest.approx(6.568542, abs=5e-7)

    assert pad_ink_overlap(board, pad, points=ink, half_width=1.0, layers=[TOP]) is False
    assert pad_ink_overlap(board, pad, points=ink, half_width=1.0, layers=[BOTTOM]) is False


def test_a_stroke_that_crosses_the_disc_is_ink_on_copper():
    """A 2 mil stroke straight through the disc: 100 mil of copper under it."""
    pad = _disc("d", 0, 0, DISC_D)
    board = _board(pad)

    through = [_pt(-80.0, 0.0), _pt(80.0, 0.0)]
    assert pad_ink_overlap(board, pad, points=through, half_width=2.0, layers=[TOP]) is True

    # Same stroke 80 mil up: its closest approach is (0, 80), i.e. 30 mil of air
    # from the copper edge — 28 mil more than the stroke's own radius.
    clear = [_pt(-80.0, 80.0), _pt(80.0, 80.0)]
    assert pad_ink_overlap(board, pad, points=clear, half_width=2.0, layers=[TOP]) is False


# ---------------------------------------------------------------------------
# tangency is not overlap
# ---------------------------------------------------------------------------


def test_stroke_tangent_to_a_disc_is_not_an_overlap():
    """``distance == half_width + radius`` leaves zero intersection area.

    Disc radius 50 and a 2 mil dot at ``(52, 0)``: the dot's edge kisses the
    copper at ``(50, 0)`` exactly. Moving in by half a mil gives 0.5 mil of
    interpenetration, which is a real overlap.
    """
    pad = _disc("d", 0, 0, DISC_D)
    board = _board(pad)

    assert pad_ink_overlap(
        board, pad, points=[_pt(52.0, 0.0)], half_width=2.0, layers=[TOP]
    ) is False
    assert pad_ink_overlap(
        board, pad, points=[_pt(51.5, 0.0)], half_width=2.0, layers=[TOP]
    ) is True


def test_stroke_tangent_to_a_rect_is_not_an_overlap():
    """The same statement against a polygon pad, where the edge is a line.

    A 20 x 10 mil rectangle spans ``y in [-5, 5]``; a 2 mil stroke centred on
    ``y = 7`` reaches ``y = 5`` exactly. At 2.5 mil it reaches 0.5 mil into the
    copper.
    """
    pad = _rect("r", 0, 0, 20.0, 10.0)
    board = _board(pad)

    tangent = [_pt(-2.0, 7.0), _pt(2.0, 7.0)]
    assert pad_ink_overlap(board, pad, points=tangent, half_width=2.0, layers=[TOP]) is False
    assert pad_ink_overlap(board, pad, points=tangent, half_width=2.5, layers=[TOP]) is True

    # Through the middle of the rectangle, and 35 mil clear above it.
    assert pad_ink_overlap(
        board, pad, points=[_pt(-20.0, 0.0), _pt(20.0, 0.0)], half_width=1.0, layers=[TOP]
    ) is True
    assert pad_ink_overlap(
        board, pad, points=[_pt(-20.0, 40.0), _pt(20.0, 40.0)], half_width=1.0, layers=[TOP]
    ) is False


def test_fill_tangent_to_a_rect_corner_is_not_an_overlap():
    """A filled square that only touches a corner contributes no area.

    The rectangle spans ``x in [-10, 10]``, ``y in [-5, 5]``. A 10 x 10 mil
    fill starting at ``(10, 5)`` meets it at that single point; moved to
    ``(9, 4)`` the two share the 1 x 1 mil square ``[9, 10] x [4, 5]``.
    """
    pad = _rect("r", 0, 0, 20.0, 10.0)
    board = _board(pad)

    touching = [_pt(10.0, 5.0), _pt(20.0, 5.0), _pt(20.0, 15.0), _pt(10.0, 15.0)]
    assert pad_ink_overlap(
        board, pad, points=touching, half_width=0.0, layers=[TOP], filled=True
    ) is False

    bitten = [_pt(9.0, 4.0), _pt(20.0, 4.0), _pt(20.0, 15.0), _pt(9.0, 15.0)]
    assert pad_ink_overlap(
        board, pad, points=bitten, half_width=0.0, layers=[TOP], filled=True
    ) is True


# ---------------------------------------------------------------------------
# every pad shape 038V models
# ---------------------------------------------------------------------------


def test_rotated_rect_pad():
    """A 40 x 10 mil rectangle at 45 degrees: ink follows the copper, not the box.

    Its corners are at ``x = +-20 cos45 -+ 5 sin45``, so the copper's extreme
    ``|x|`` is ``20 cos45 + 5 sin45`` = 17.677670 mil. A vertical stroke at
    ``x = 0`` crosses the pad; one at ``x = 19.5`` stands 1.822330 mil off it,
    more than its 1 mil radius.
    """
    pad = _rect("r", 0, 0, 40.0, 10.0, angle=45.0)
    board = _board(pad)
    extreme = 20 * math.cos(math.radians(45)) + 5 * math.sin(math.radians(45))
    assert extreme == pytest.approx(17.677670, abs=5e-7)
    assert max(abs(c.x) for c in pad_corners(pad)) == pytest.approx(extreme, abs=1e-9)

    assert pad_ink_overlap(
        board, pad, points=[_pt(0.0, -40.0), _pt(0.0, 40.0)], half_width=1.0, layers=[TOP]
    ) is True
    assert pad_ink_overlap(
        board, pad, points=[_pt(19.5, -40.0), _pt(19.5, 40.0)], half_width=1.0, layers=[TOP]
    ) is False


def test_oval_pad_is_a_stadium():
    """``OVAL`` 100 x 40: centreline ``(-30, 0)-(30, 0)`` plus radius 20.

    Vertically the copper reaches ``y = 20`` (0.5 mil dot at ``y = 19`` under it,
    at ``y = 21`` clear); along the long axis the cap reaches ``x = 50`` (a dot
    at ``x = 50`` is 0.5 mil inside the 20.5 mil reach, at ``x = 52`` it is out).
    """
    pad = _oval("o", 0, 0, 100.0, 40.0)
    board = _board(pad)

    def hit(point: Point) -> bool:
        return pad_ink_overlap(board, pad, points=[point], half_width=0.5, layers=[TOP])

    assert hit(_pt(0.0, 19.0)) is True
    assert hit(_pt(0.0, 21.0)) is False
    assert hit(_pt(50.0, 0.0)) is True
    assert hit(_pt(52.0, 0.0)) is False


def test_non_circular_ellipse_is_the_circumscribing_32_gon():
    """038V's bounded conservatism, measured rather than asserted.

    A 100 x 60 mil ``ELLIPSE`` is read as the 32-gon tangent to it, whose worst
    radial excess is ``sec(pi/32) - 1`` = 0.483 %. Along the 45 degree ray that
    excess is measured here, then used:

    * a dot on the true ellipse's boundary counts (it is inside the 32-gon);
    * a dot halfway through the bulge also counts — the documented **over-report**
      (it is outside the true ellipse, inside what this module measures);
    * a dot 0.5 mil beyond the 32-gon is clear, so the bound is not unbounded.
    """
    pad = _ellipse("e", 0, 0, 100.0, 60.0)
    board = _board(pad)
    polygon, radius = _pad_copper(pad)
    assert radius == 0.0 and len(polygon) == 32

    direction = (math.cos(math.radians(45)), math.sin(math.radians(45)))
    ellipse_radius = 1.0 / math.hypot(direction[0] / 50.0, direction[1] / 30.0)
    exit_radius = _ray_exit(polygon, *direction)
    ratio = exit_radius / ellipse_radius
    assert 1.0 < ratio <= 1.0 / math.cos(math.pi / 32) + 1e-12

    def hit_at(distance: float) -> bool:
        point = _pt(distance * direction[0], distance * direction[1])
        return pad_ink_overlap(board, pad, points=[point], half_width=0.05, layers=[TOP])

    assert hit_at(ellipse_radius) is True
    assert hit_at((ellipse_radius + exit_radius) / 2.0) is True
    assert hit_at(exit_radius + 0.5) is False

    # Along the axes the 32-gon is exact: the copper ends at x = 50.
    assert pad_ink_overlap(
        board, pad, points=[_pt(49.0, 0.0)], half_width=0.5, layers=[TOP]
    ) is True
    assert pad_ink_overlap(
        board, pad, points=[_pt(50.2, 0.0)], half_width=0.5, layers=[TOP]
    ) is True
    assert pad_ink_overlap(
        board, pad, points=[_pt(51.0, 0.0)], half_width=0.5, layers=[TOP]
    ) is False


# ---------------------------------------------------------------------------
# filled rings: interior is ink, the notch is not
# ---------------------------------------------------------------------------

#: A U-shaped (concave, simple) silk fill: 100 mil square with a 40 x 70 notch
#: cut from the top down to ``y = 30``. Its bottom bar is the copper-free pad
#: home below; the notch is the negative control.
U_RING = [
    _pt(0.0, 0.0),
    _pt(100.0, 0.0),
    _pt(100.0, 100.0),
    _pt(70.0, 100.0),
    _pt(70.0, 30.0),
    _pt(30.0, 30.0),
    _pt(30.0, 100.0),
    _pt(0.0, 100.0),
]


def test_concave_fill_contains_a_pad_and_its_notch_does_not():
    """Interior ink, not the outline's box: the U's bar is ink, the U's notch is not.

    A 10 x 6 mil pad at ``(50, 15)`` sits wholly inside the U's bottom bar and a
    same-sized pad at ``(50, 60)`` sits wholly inside the notch, which the fill
    does not cover. Both are inside the ring's **bounding box** — the pair is
    the concave version of the disc's ear, and the box reading gets the second
    one wrong.
    """
    pad_in = _rect("bar", 50.0, 15.0, 10.0, 6.0)
    pad_notch = _rect("notch", 50.0, 60.0, 10.0, 6.0)
    board = _board(pad_in, pad_notch)

    assert _in_box(_pad("box", width=100.0, height=100.0, x=50.0, y=50.0), _pt(50.0, 60.0))
    inside = pad_ink_overlap(
        board, pad_in, points=U_RING, half_width=0.0, layers=[TOP], filled=True
    )
    notch = pad_ink_overlap(
        board, pad_notch, points=U_RING, half_width=0.0, layers=[TOP], filled=True
    )
    assert inside is True
    assert notch is False

    # With no stroke width and no fill there is no ink area at all.
    assert pad_ink_overlap(
        board, pad_in, points=U_RING, half_width=0.0, layers=[TOP]
    ) is False


def test_filled_outline_still_carries_its_stroke():
    """``filled=True`` adds the interior; it does not replace the stroke.

    A 6 x 6 mil pad centred at ``(50, -3.5)`` lies 0.5 mil **below** the U's
    bottom edge (``y = 0``), so the fill cannot reach it. The outline's stroke
    does: 0.4 mil falls short, 0.6 mil covers it. The closing edge of the ring is
    stroked too, which is why the same ring drawn with ``closed=True`` and no
    fill behaves identically here.
    """
    pad = _rect("below", 50.0, -3.5, 6.0, 6.0)
    board = _board(pad)

    def hit(half_width: float, **kwargs: bool) -> bool:
        return pad_ink_overlap(
            board, pad, points=U_RING, half_width=half_width, layers=[TOP], **kwargs
        )

    assert hit(0.0, filled=True) is False
    assert hit(0.4, filled=True) is False
    assert hit(0.6, filled=True) is True
    assert hit(0.6, closed=True) is True


def test_collinear_fill_ring_encloses_nothing():
    """Three collinear points: zero enclosed area, so the fill is not ink."""
    pad = _rect("r", 0, 0, 40.0, 10.0)
    board = _board(pad)
    assert pad_ink_overlap(
        board,
        pad,
        points=[_pt(0.0, 0.0), _pt(10.0, 0.0), _pt(20.0, 0.0)],
        half_width=0.0,
        layers=[TOP],
        filled=True,
    ) is False


# ---------------------------------------------------------------------------
# containment both ways
# ---------------------------------------------------------------------------


def test_fill_inside_a_disc_and_a_pad_inside_a_fill():
    """The region is compared, not the outline: containment is a hit both ways."""
    disc = _disc("d", 0, 0, DISC_D)
    small_fill = [_pt(-5.0, -5.0), _pt(5.0, -5.0), _pt(5.0, 5.0), _pt(-5.0, 5.0)]
    assert pad_ink_overlap(
        _board(disc), disc, points=small_fill, half_width=0.0, layers=[TOP], filled=True
    ) is True

    pad = _rect("r", 0, 0, 20.0, 10.0)
    big_fill = [_pt(-100.0, -100.0), _pt(100.0, -100.0), _pt(100.0, 100.0), _pt(-100.0, 100.0)]
    assert pad_ink_overlap(
        _board(pad), pad, points=big_fill, half_width=0.0, layers=[TOP], filled=True
    ) is True

    far_fill = [_pt(400.0, -100.0), _pt(600.0, -100.0), _pt(600.0, 100.0), _pt(400.0, 100.0)]
    assert pad_ink_overlap(
        _board(pad), pad, points=far_fill, half_width=0.0, layers=[TOP], filled=True
    ) is False


# ---------------------------------------------------------------------------
# open vs closed, zero width, layers
# ---------------------------------------------------------------------------


def test_closed_adds_the_last_edge():
    """An L-shaped stroke with and without its closing edge.

    ``[(0, 0), (100, 0), (100, 100)]`` stroked 8 mil wide covers the two arms.
    A 6 x 6 mil pad at ``(55, 45)`` is 42 mil from either arm but only
    ``|55 - 45| / sqrt(2)`` = 7.071 mil from the diagonal that closes the path,
    so ``closed=True`` decides it.
    """
    pad = _rect("p", 55.0, 45.0, 6.0, 6.0)
    board = _board(pad)
    path = [_pt(0.0, 0.0), _pt(100.0, 0.0), _pt(100.0, 100.0)]

    assert pad_ink_overlap(board, pad, points=path, half_width=8.0, layers=[TOP]) is False
    assert pad_ink_overlap(
        board, pad, points=path, half_width=8.0, layers=[TOP], closed=True
    ) is True
    # A zero-width stroke has no area however it is drawn.
    assert pad_ink_overlap(
        board, pad, points=path, half_width=0.0, layers=[TOP], closed=True
    ) is False


def test_layers_gate_the_answer():
    """Same geometry, different faces: ink on the bottom is not on a top pad."""
    pad = _disc("d", 0, 0, DISC_D)
    board = _board(pad)
    dot = [_pt(0.0, 0.0)]

    assert pad_ink_overlap(board, pad, points=dot, half_width=2.0, layers=[TOP]) is True
    assert pad_ink_overlap(board, pad, points=dot, half_width=2.0, layers=[TOP, BOTTOM]) is True
    assert pad_ink_overlap(board, pad, points=dot, half_width=2.0, layers=[BOTTOM]) is False
    assert pad_ink_overlap(board, pad, points=dot, half_width=2.0, layers=[]) is False

    bottom_pad = _disc("b", 0, 0, DISC_D, layer_id=BOTTOM)
    assert pad_ink_overlap(
        _board(bottom_pad), bottom_pad, points=dot, half_width=2.0, layers=[TOP]
    ) is False
    assert pad_ink_overlap(
        _board(bottom_pad), bottom_pad, points=dot, half_width=2.0, layers=[BOTTOM]
    ) is True


def test_empty_ink_and_negative_width():
    """No points is no ink; a negative stroke is a caller bug, not a reading."""
    pad = _disc("d", 0, 0, DISC_D)
    board = _board(pad)
    assert pad_ink_overlap(board, pad, points=[], half_width=2.0, layers=[TOP]) is False
    with pytest.raises(ValueError):
        pad_ink_overlap(board, pad, points=[_pt(0.0, 0.0)], half_width=-1.0, layers=[TOP])
