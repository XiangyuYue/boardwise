"""Tests for task 038Y1: the layer-aware positive-area pad copper predicate.

``pad_copper_overlap(board, a, b)`` answers 「do these two pads' copper bodies
really interpenetrate on a shared layer」. The case that forced it: another
device's PCB review pre-study shipped a ``pcb-pad-overlap`` rule that measured
``pad_corners()``'s **bounding box** and called it copper, so two Ø98.425 mil
discs 70 / 70 mil apart diagonally — 0.569949 mil of real air between their
edges — came out as 807.980625 mil² of ERROR. Every assertion below is either
that counterexample, a negative control from the task book's table, or a
regression pin on the readings 038V already published.

Geometry is read from :func:`boardwise.core.measure._pad_copper`, so the shapes
under test are the module's own: a disc is a disc, an ``OVAL`` a stadium, a
``RECT`` its four corners and a non-circular ``ELLIPSE`` 038V's circumscribing
32-gon. No fixture and no parser is involved — every pad here is hand-built,
and each expected number is derived in the comment next to it.
"""

from __future__ import annotations

import math

import pytest

from boardwise.core.geometry import (
    BoardGeometry,
    ComponentPlacement,
    LayerInfo,
    PadGeometry,
    StackupEntry,
)
from boardwise.core.measure import (
    component_distance,
    pad_corners,
    pad_edge_distance,
    pad_copper_overlap as overlap,
)

#: The counterexample's disc: Ø98.425 mil.
DISC = 98.425
#: Its radius, 49.2125 mil.
DISC_R = DISC / 2


def _pad(
    id: str,
    *,
    component: str | None = None,
    pin: str | None = None,
    net: str | None = None,
    layer_id: int | None = 1,
    x: float = 0.0,
    y: float = 0.0,
    width: float = 0.0,
    height: float = 0.0,
    shape: str = "RECT",
    angle: float = 0.0,
    hole: float | None = None,
    effective_layers: list[int] | None = None,
) -> PadGeometry:
    """One hand-built pad; ``angle`` is board-frame (post-125a contract).

    ``effective_layers`` is left ``None`` (「nobody read this pad」) unless a test
    wants the parser's reading — ``[]`` is 「no copper layer」, and the two must
    never be conflated (R2-2 fixA).
    """
    return PadGeometry(
        id=id,
        component=component,
        pin_number=pin,
        net=net,
        footprint_layer_id=layer_id,
        x=x,
        y=y,
        width=width,
        height=height,
        shape=shape,
        angle=angle,
        hole_diameter=hole,
        effective_layer_ids=effective_layers,
    )


def _board(*pads: PadGeometry, components: list[ComponentPlacement] | None = None) -> BoardGeometry:
    """A hand-built two-layer board (the layer reading these tests pin)."""
    layers = {
        1: LayerInfo(1, "Top Layer", "TOP"),
        2: LayerInfo(2, "Bottom Layer", "BOTTOM"),
    }
    stackup = [
        StackupEntry(1, 1000, "外层铜厚", 1.378),
        StackupEntry(2, 9000, "外层铜厚", 1.378),
    ]
    return BoardGeometry(
        layers=layers,
        stackup=stackup,
        pads=list(pads),
        components=list(components or []),
    )


def _layerless_board(*pads: PadGeometry) -> BoardGeometry:
    """A board that names **no** copper layer (the ``_comparable_layers`` widening)."""
    return BoardGeometry(pads=list(pads))


def _disc(
    id: str, x: float, y: float, *, diameter: float = DISC, layer_id: int = 1, **kwargs
) -> PadGeometry:
    return _pad(
        id, x=x, y=y, width=diameter, height=diameter, shape="ELLIPSE",
        layer_id=layer_id, **kwargs,
    )


def _box(pad: PadGeometry) -> tuple[float, float, float, float]:
    corners = pad_corners(pad)
    return (
        min(p.x for p in corners),
        min(p.y for p in corners),
        max(p.x for p in corners),
        max(p.y for p in corners),
    )


def _boxes_intersect(a: PadGeometry, b: PadGeometry) -> bool:
    ax0, ay0, ax1, ay1 = _box(a)
    bx0, by0, bx1, by1 = _box(b)
    return min(ax1, bx1) - max(ax0, bx0) > 0 and min(ay1, by1) - max(ay0, by0) > 0


# ---------------------------------------------------------------------------
# the counterexample: diagonally separated discs that boxes call a collision
# ---------------------------------------------------------------------------


def test_diagonal_discs_with_0_569949_of_air_are_not_an_overlap():
    """038Y1 §1: the pre-study package's ERROR is a **box** artefact, not copper.

    Two Ø98.425 mil discs at ``(0, 0)`` and ``(70, 70)``. Centre distance is
    ``70 * sqrt(2)`` = 98.99494936611666, so the copper gap is
    ``98.99494936611666 - 98.425`` = **0.56994936611666** mil — the reading
    038V publishes and the one the task book quotes as 0.569949. Their bounding
    boxes, on the other hand, interpenetrate by ``98.425 - 70`` = 28.425 mil on
    each axis, which is what turned 807.980625 mil² of empty air into an ERROR.

    Both facts are asserted: the copper reading must stay 0.569949 and the
    predicate must answer ``False``, while the same predicate flipped to the box
    would agree with the pre-study package.
    """
    a = _disc("a", 0, 0)
    b = _disc("b", 70, 70)
    board = _board(a, b)

    gap = pad_edge_distance(a, b)
    assert gap == pytest.approx(70 * math.sqrt(2) - DISC, abs=1e-9)
    assert gap == pytest.approx(0.569949, abs=5e-7)

    # The box reading really is the tempting one: it interpenetrates on both axes.
    assert _boxes_intersect(a, b)

    assert overlap(board, a, b) is False
    assert overlap(board, b, a) is False


# ---------------------------------------------------------------------------
# capsule / capsule: tangency, overlap, identity
# ---------------------------------------------------------------------------


def test_same_radius_discs_exactly_touching_are_not_an_overlap():
    """A kiss is not a collision: ``d == r_a + r_b`` has zero intersection area.

    ``pad_edge_distance`` cannot say this — it clamps touch and overlap to the
    same ``0.0`` — which is the whole reason the predicate exists.
    """
    a = _disc("a", 0, 0)
    b = _disc("b", DISC, 0)
    board = _board(a, b)

    assert pad_edge_distance(a, b) == pytest.approx(0.0, abs=1e-9)
    assert overlap(board, a, b) is False
    assert overlap(board, b, a) is False

    # Tangency at 45 degrees is the same statement rotated (a rotation cannot
    # change an area sign).
    turned = _disc("c", DISC / math.sqrt(2), DISC / math.sqrt(2))
    assert overlap(board, a, turned) is False


def test_discs_overlapping_by_half_a_mil_are_an_overlap():
    """A 0.425 mil interpenetration is real shared copper, however shallow.

    ``98.425 - 98.0`` = 0.425 mil of depth on the x axis. Shallow is still
    positive area, so the answer is ``True`` in both argument orders and
    ``pad_edge_distance`` reads ``0.0`` exactly as it does for the tangency
    case above — two distinct questions, two answers.
    """
    a = _disc("a", 0, 0)
    b = _disc("b", 98.0, 0)
    board = _board(a, b)

    assert pad_edge_distance(a, b) == pytest.approx(0.0, abs=1e-9)
    assert overlap(board, a, b) is True
    assert overlap(board, b, a) is True


def test_identical_pads_on_one_layer_overlap():
    """Same position, same layer: one piece of copper described twice."""
    board = _board(
        _disc("a", 10, 20),
        _disc("b", 10, 20),
        _pad("r1", x=-80, y=0, width=40, height=20),
        _pad("r2", x=-80, y=0, width=40, height=20),
    )
    pads = board.pads
    assert overlap(board, pads[0], pads[1]) is True
    assert overlap(board, pads[2], pads[3]) is True
    # …and a disc on top of a rectangle is an overlap too, both ways.
    square = _pad("sq", x=10, y=20, width=10, height=10)
    square_board = _board(pads[0], square)
    assert overlap(square_board, pads[0], square) is True
    assert overlap(square_board, square, pads[0]) is True


# ---------------------------------------------------------------------------
# polygon / polygon: rotation, containment, tangency
# ---------------------------------------------------------------------------


def test_rotated_rectangle_boxes_intersect_but_the_copper_does_not():
    """A 45° square against a small square parked beyond its corner.

    ``A`` is 100 x 100 rotated 45°, so its copper is the diamond
    ``|x| + |y| <= 100 / sqrt(2)`` = 70.71067811865476. ``B`` is 20 x 20 at
    ``(60, 60)``, whose nearest corner is ``(50, 50)``: ``|50| + |50|`` = 100,
    leaving ``(100 - 70.71067811865476) / sqrt(2)`` = **20.710678118654755** mil
    of air. Their **boxes** overlap (``A``'s box is
    ``[-70.71, 70.71]`` squared and ``B`` sits at ``[50, 70]`` squared), so a box
    test reports a collision and the copper reading does not.

    The same picture with ``B`` turned 45° as well (its nearest point moves to
    ``(50, 50)`` too) pins that the result is rotation-invariant.
    """
    a = _pad("a", width=100, height=100, angle=45)
    b = _pad("b", x=60, y=60, width=20, height=20)
    b45 = _pad("b45", x=60, y=60, width=20, height=20, angle=45)
    board = _board(a, b, b45)

    assert _boxes_intersect(a, b)
    assert pad_edge_distance(a, b) == pytest.approx(20.710678118654755, abs=1e-9)
    assert overlap(board, a, b) is False
    assert overlap(board, b, a) is False
    assert overlap(board, a, b45) is False

    # A square parked on A's own diagonal (its corner at (10, 50) is well
    # inside |x| + |y| <= 70.71) really does share copper with it.
    inside = _pad("in", x=0, y=60, width=20, height=20)
    board_inside = _board(a, inside)
    assert overlap(board_inside, a, inside) is True


def test_fully_contained_polygon_is_an_overlap():
    """Containment is positive-area intersection, in either argument order.

    ``B`` (10 x 10) sits at the centre of ``A`` (200 x 200, rotated 30° — the
    rotation is there so no edge of either is parallel to the other). A radius
    sum test would miss this; a separating-axis test cannot, because a contained
    polygon has no separating axis at all.
    """
    a = _pad("a", width=200, height=200, angle=30)
    b = _pad("b", width=10, height=10)
    board = _board(a, b)

    assert overlap(board, a, b) is True
    assert overlap(board, b, a) is True


def test_disc_wholly_inside_a_rectangle_is_an_overlap():
    """The capsule/polygon containment case a naive radius sum gets wrong.

    The disc's centre is 100 mil from the rectangle's near edge, so the
    centreline distance (100) is far larger than its radius (10) — yet the disc
    is inside the copper. The predicate compares the radius against the distance
    to the polygon's **region**, which is 0 here.
    """
    rect = _pad("r", width=200, height=200)
    disc = _disc("d", 0, 0, diameter=20)
    board = _board(rect, disc)

    assert overlap(board, rect, disc) is True
    assert overlap(board, disc, rect) is True


def test_rectangles_touching_edge_to_edge_are_not_an_overlap():
    """Shared edge, zero area: ``[0,50]`` x ``[0,50]`` against ``[50,100]`` x ``[0,50]``."""
    a = _pad("a", x=25, y=25, width=50, height=50)
    b = _pad("b", x=75, y=25, width=50, height=50)
    board = _board(a, b)
    assert pad_edge_distance(a, b) == pytest.approx(0.0, abs=1e-9)
    assert overlap(board, a, b) is False

    # Overlap it by 5 mil and the same pair is genuine shared copper.
    shifted = _pad("s", x=70, y=25, width=50, height=50)
    assert overlap(_board(a, shifted), a, shifted) is True


# ---------------------------------------------------------------------------
# layers: cross-layer, ``None`` fallback and ``[]`` "no copper"
# ---------------------------------------------------------------------------


def test_pads_on_different_layers_never_overlap():
    """Coincident discs on layer 1 and layer 2: ``0.0`` apart in plan view, no copper."""
    top = _disc("top", 0, 0, layer_id=1)
    bottom = _disc("bot", 0, 0, layer_id=2)
    board = _board(top, bottom)

    assert pad_edge_distance(top, bottom) == pytest.approx(0.0, abs=1e-9)
    assert overlap(board, top, bottom) is False
    assert overlap(board, bottom, top) is False

    # Control: the same pair on one face is an overlap.
    twin = _disc("twin", 0, 0, layer_id=1)
    assert overlap(_board(top, twin), top, twin) is True


def test_through_hole_pad_meets_every_layer():
    """A plated hole spans every copper layer, so it overlaps a bottom pad too."""
    through = _pad("th", width=40, height=40, shape="ELLIPSE", layer_id=1, hole=20)
    bottom = _pad("bot", width=20, height=20, shape="ELLIPSE", layer_id=2, x=0, y=0)
    board = _board(through, bottom)
    assert overlap(board, through, bottom) is True


def test_unread_layer_falls_back_while_an_empty_reading_is_no_copper():
    """``None`` and ``[]`` are different answers, and this is where they part.

    On a board that names **no** copper layer, :func:`_comparable_layers`'s
    narrowing widening hands ``{footprint_layer_id}`` back for a pad it cannot
    place — that is what lets two hand-built SMD pads meet. ``[]`` is the
    parser's 「this pad occupies no copper layer」 reading (a bare mechanical
    hole) and must not be rescued by that widening: R2-2 fixA's regression was
    exactly an NPTH's copper reappearing on every layer.

    So on the same layer, at the same point: two unread pads overlap, and an
    empty-reading pad overlaps nothing — not even its unread twin.
    """
    unread = _pad("unread", width=20, height=20, shape="ELLIPSE", x=0, y=0, layer_id=1)
    unread_twin = _pad("unread2", width=20, height=20, shape="ELLIPSE", x=5, y=0, layer_id=1)
    no_copper = _pad(
        "npth", width=20, height=20, shape="ELLIPSE", x=0, y=0, layer_id=1,
        effective_layers=[],
    )
    board = _layerless_board(unread, unread_twin, no_copper)

    assert overlap(board, unread, unread_twin) is True
    assert overlap(board, unread, no_copper) is False
    assert overlap(board, no_copper, unread) is False
    assert overlap(board, no_copper, no_copper) is False

    # The same ``[]`` answer holds on a board whose layer table exists.
    layered = _board(no_copper, unread)
    assert overlap(layered, no_copper, unread) is False


# ---------------------------------------------------------------------------
# capsule / polygon and capsule / capsule combinations
# ---------------------------------------------------------------------------


def test_long_round_meets_a_disc_exactly_where_the_radii_say():
    """``OVAL`` 100 x 20 (stadium: ``(+-40, 0)`` + r = 10) against a Ø40 disc.

    A disc at ``(0, 25)`` has its centre 25 from the stadium's centreline, so
    ``25 < 10 + 20`` = 30 — an overlap of 5 mil depth. A disc at ``(0, 30)`` is
    exactly ``r_a + r_b`` away: tangency, not overlap, and
    ``pad_edge_distance`` reads ``0.0`` for both — which is why the predicate
    cannot be written as ``pad_edge_distance(...) == 0``.
    """
    oval = _pad("o", width=100, height=20, shape="OVAL")
    near = _pad("near", x=0, y=25, width=40, height=40, shape="ELLIPSE")
    far = _pad("far", x=0, y=30, width=40, height=40, shape="ELLIPSE")
    board = _board(oval, near, far)

    assert overlap(board, oval, near) is True
    assert overlap(board, near, oval) is True

    assert pad_edge_distance(oval, far) == pytest.approx(0.0, abs=1e-9)
    assert overlap(board, oval, far) is False

    # Two stadiums: the same rule with two radii and a perpendicular centreline.
    # ``turned`` runs ``x = 0, y in [20, 100]`` with r = 10, so it is 20 from the
    # horizontal stadium's axis: exactly ``10 + 10``, a kiss rather than a bite.
    turned = _pad("t", x=0, y=60, width=100, height=20, shape="OVAL", angle=90)
    assert overlap(_board(oval, turned), oval, turned) is False
    assert overlap(_board(oval, near, turned), near, turned) is True


def test_crossing_stadiums_centre_lines_meet_in_their_interiors():
    """Two ``OVAL`` 100 x 20 at one origin, 0° and 90°: a copper cross, not a gap.

    Both centre lines pass through ``(0, 0)`` — ``x in [-40, 40]`` and
    ``y in [-40, 40]`` — so the copper bodies meet over a 20 x 20 square around
    the crossing. **No endpoint is near the crossing**: the four nearest
    endpoints sit 40 mil away and each side's chord is 80 apart, so a
    vertex-only scan of the centre lines reads them as separated while their
    copper plainly interpenetrates (038Y1's first cut answered ``False`` here).

    ``pad_edge_distance`` reads ``0.0``, exactly as it does for the tangency
    cases above: the distance reader cannot tell a cross from a kiss, which is
    why the predicate cannot be built on it.

    The negative control is the same pair pulled apart: parallel centre lines 25
    apart with radii 10 + 10 leave 5 mil of air, so no overlap.
    """
    horizontal = _pad("h", width=100, height=20, shape="OVAL")
    crossing = _pad("c", width=100, height=20, shape="OVAL", angle=90)
    beside = _pad("b", x=0, y=25, width=100, height=20, shape="OVAL")
    board = _board(horizontal, crossing, beside)

    assert pad_edge_distance(horizontal, crossing) == pytest.approx(0.0, abs=1e-9)
    assert overlap(board, horizontal, crossing) is True
    assert overlap(board, crossing, horizontal) is True

    assert pad_edge_distance(horizontal, beside) == pytest.approx(5.0, abs=1e-9)
    assert overlap(board, horizontal, beside) is False


def test_rotated_stadium_meets_and_misses_a_rectangle():
    """A 45° ``OVAL`` against a square: radius against distance to copper, in both directions.

    The stadium's centreline runs ``(+-28.284271247461902, +-28.284271247461902)``
    with r = 10. The square at ``(30, 30)`` has a corner at ``(20, 20)``, which
    sits **on** that centreline — so its copper is 0 from the capsule's axis and
    the capsule's disc covers it. The square at ``(100, 100)`` has its nearest
    corner ``(90, 90)``; the closest centreline point is the **endpoint**
    ``(28.284…, 28.284…)``, ``hypot(90 - 28.28…, 90 - 28.28…)`` = 87.279… away,
    so the copper gap is that minus r = 10 → **77.27922061357856** mil.
    """
    oval = _pad("o", width=100, height=20, shape="OVAL", angle=45)
    near = _pad("near", x=30, y=30, width=20, height=20)
    far = _pad("far", x=100, y=100, width=20, height=20)
    board = _board(oval, near, far)

    assert overlap(board, oval, near) is True
    assert overlap(board, near, oval) is True
    assert overlap(board, oval, far) is False
    assert overlap(board, far, oval) is False
    end = 40 / math.sqrt(2)
    assert pad_edge_distance(oval, far) == pytest.approx(
        math.hypot(90 - end, 90 - end) - 10, abs=1e-9
    )


# ---------------------------------------------------------------------------
# degenerate pads and the 32-gon disclaimer
# ---------------------------------------------------------------------------


def test_zero_area_pads_never_overlap():
    """A collapsed pad is a point or a line: no area, so no positive-area overlap.

    ``_pad_copper`` collapses a zero extent on purpose (a pad whose size did not
    parse). Every one of these sits inside the big rectangle's copper, and every
    one must answer ``False`` — 「no copper area」 rather than 「copper that
    overlaps」.
    """
    big = _pad("big", width=200, height=200)
    point_ellipse = _pad("p", width=0, height=0, shape="ELLIPSE")
    point_rect = _pad("pr", width=0, height=0)
    flat_oval = _pad("fo", width=100, height=0, shape="OVAL")
    board = _board(big, point_ellipse, point_rect, flat_oval)

    for degenerate in (point_ellipse, point_rect, flat_oval):
        assert overlap(board, big, degenerate) is False
        assert overlap(board, degenerate, big) is False


def test_non_circular_ellipse_is_exact_at_its_own_axis():
    """The inherited 32-gon touches the ellipse at 32 points; the axes are exact.

    ``ELLIPSE`` 200 x 100 has its ``+x`` tangency at ``(100, 0)`` and the 32-gon
    passes exactly through it (the first vertex is ``hw`` by construction). A
    Ø20 disc at ``(110, 0)`` therefore touches with zero depth — ``False`` —
    while one at ``(109.9, 0)`` interpenetrates by 0.1 mil — ``True``.

    Between tangency points the 32-gon bulges **outward** by at most
    ``sec(pi/32) - 1`` = 0.483 % of a semi-axis (0.483 mil here), so the
    predicate may report up to that much extra copper and never less; see the
    docstring, which states this as a bound rather than an exactness claim.
    """
    ellipse = _pad("e", width=200, height=100, shape="ELLIPSE")
    touch = _pad("t", x=110, y=0, width=20, height=20, shape="ELLIPSE")
    depth = _pad("d", x=109.9, y=0, width=20, height=20, shape="ELLIPSE")
    board = _board(ellipse, touch, depth)

    assert overlap(board, ellipse, touch) is False
    assert overlap(board, touch, ellipse) is False
    assert overlap(board, ellipse, depth) is True


# ---------------------------------------------------------------------------
# existing readings must not move (038V / 126b regression pins)
# ---------------------------------------------------------------------------


def test_existing_distance_readings_are_unchanged():
    """038Y1 adds an answer; it must not move the numbers 038V/126b published.

    * ``pad_edge_distance`` on the 60 mil diagonal-disc pair is **40.0** — the
      038V figure, and the retired rectangle model's 15.147… is asserted out;
    * ``component_distance`` on two 20 x 20 pads 100 apart reads
      ``center_distance`` 100.0 / ``edge_distance`` 80.0, the 126b reading the
      rules quote.
    """
    a = _pad("a", width=60, height=60, shape="ELLIPSE")
    b = _pad("b", x=100 / math.sqrt(2), y=100 / math.sqrt(2), width=60, height=60,
             shape="ELLIPSE")
    distance = pad_edge_distance(a, b)
    assert distance == pytest.approx(40.0, abs=1e-9)
    assert abs(distance - 15.147186257614282) > 1.0

    comp_a = ComponentPlacement(id="c-a", designator="A", x=0, y=0, layer_id=1)
    comp_b = ComponentPlacement(id="c-b", designator="B", x=100, y=0, layer_id=1)
    pads = [
        _pad("a1", component="A", pin="1", x=0, y=0, width=20, height=20),
        _pad("b1", component="B", pin="1", x=100, y=0, width=20, height=20),
    ]
    board = _board(*pads, components=[comp_a, comp_b])
    measured = component_distance(board, "A", "B")
    assert measured is not None
    assert measured.center_distance == pytest.approx(100.0, abs=1e-9)
    assert measured.edge_distance == pytest.approx(80.0, abs=1e-9)
    assert measured.pad_a == "1" and measured.pad_b == "1"
    # 80 mil apart on one layer with no net: the new predicate agrees it is not
    # an overlap, so adding it cannot flip this pin.
    assert overlap(board, pads[0], pads[1]) is False


def test_public_name_is_exported():
    """``pad_copper_overlap`` is the name the next batch's rule imports."""
    import boardwise.core.measure as measure

    assert "pad_copper_overlap" in measure.__all__
    assert measure.pad_copper_overlap is overlap
