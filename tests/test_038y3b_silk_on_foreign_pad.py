"""Tests for task 038Y3B: ``pcb-silk-on-foreign-pad`` — 丝印墨迹压到**别的器件**的焊盘.

The rule is a consumer of 038Y3A's
:func:`boardwise.core.measure.pad_ink_overlap`; every case below is either one of
the task book's controls or the pre-study's own counterexample. Three things are
asserted that a 「a crossing stroke returns one WARN」 test would miss:

* the **screen must not be the judge**: the round pad's box **does** contain the
  ink in the pin-1-dot case (and the C-fill's box contains the pad in the notch
  case), and the predicate is what refuses — the pre-study's box geometry would
  have reported both;
* **no fabricated numbers**: the evidence names pads, primitives and the device
  pair, and carries neither an area nor a mixed stroke/fill 「depth」;
* the **approximation disclosure** is one INFO per board, never a WARN, and the
  chorded point list is still measured as the parser's chords.
"""

from __future__ import annotations

from boardwise.core.geometry import (
    BoardGeometry,
    LayerInfo,
    PadGeometry,
    Point,
    SilkShape,
    StackupEntry,
)
from boardwise.core.measure import pad_corners, pad_ink_overlap
from boardwise.engines import pcbreview
from boardwise.rules.pcb.base import PcbReviewContext, PcbRule
from boardwise.rules.pcb.silkpad import SilkOnForeignPad

#: Copper faces the hand-built board declares.
TOP = 1
BOTTOM = 2


# ---------------------------------------------------------------------------
# hand-built boards — no fixture, no parser
# ---------------------------------------------------------------------------


def _pad(
    id: str,
    *,
    component: str | None = "U6",
    component_id: str | None = None,
    pin: str | None = "1",
    net: str | None = None,
    x: float = 0.0,
    y: float = 0.0,
    width: float = 40.0,
    height: float = 20.0,
    shape: str = "RECT",
    angle: float = 0.0,
    layers: tuple[int, ...] = (TOP,),
) -> PadGeometry:
    """One placed pad on the faces ``layers`` (read through 127b's field)."""
    return PadGeometry(
        id=id,
        component=component,
        component_id=component_id,
        pin_number=pin,
        net=net,
        footprint_layer_id=layers[0],
        x=x,
        y=y,
        width=width,
        height=height,
        shape=shape,
        angle=angle,
        effective_layer_ids=list(layers),
    )


def _shape(
    points,
    *,
    kind: str = "poly",
    width: float = 8.0,
    layer_kind: str = "TOP_SILK",
    component: str | None = "U1",
    component_id: str | None = None,
    filled: bool = False,
    radius: float | None = None,
    arc_count: int = 0,
    id: str = "p1",
) -> SilkShape:
    """One instantiated silk primitive, already in board coordinates."""
    coords = [point if isinstance(point, Point) else Point(float(point[0]), float(point[1])) for point in points]
    return SilkShape(
        id=id,
        component=component,
        component_id=component_id,
        kind=kind,
        layer_id=3 if layer_kind == "TOP_SILK" else 4,
        layer_kind=layer_kind,
        declared_layer_kind=layer_kind,
        effective_layer_id=3 if layer_kind == "TOP_SILK" else 4,
        face=TOP if layer_kind == "TOP_SILK" else BOTTOM,
        points=coords,
        local_points=list(coords),
        width=width,
        filled=filled,
        radius=radius,
        arc_count=arc_count,
    )


def _board(*pads: PadGeometry, shapes=()) -> BoardGeometry:
    return BoardGeometry(
        layers={
            TOP: LayerInfo(TOP, "Top Layer", "TOP"),
            BOTTOM: LayerInfo(BOTTOM, "Bottom Layer", "BOTTOM"),
        },
        stackup=[
            StackupEntry(TOP, 1000, "外层铜厚", 1.378),
            StackupEntry(BOTTOM, 9000, "外层铜厚", 1.378),
        ],
        pads=list(pads),
        silk_shapes=list(shapes),
    )


def _run(*pads: PadGeometry, shapes=(), title: str = "PCB1"):
    board = _board(*pads, shapes=shapes)
    return SilkOnForeignPad().check(PcbReviewContext(board=board, board_title=title))


def _warns(findings):
    return [finding for finding in findings if finding.severity == "WARN"]


def _infos(findings):
    return [finding for finding in findings if finding.severity == "INFO"]


def _pad_lines(finding):
    return [line for line in finding.evidence if "命中图元" in line]


def _pad_box(pad: PadGeometry) -> tuple[float, float, float, float]:
    corners = pad_corners(pad)
    return (
        min(point.x for point in corners),
        min(point.y for point in corners),
        max(point.x for point in corners),
        max(point.y for point in corners),
    )


# ---------------------------------------------------------------------------
# the hit: a real stroke across another part's pad
# ---------------------------------------------------------------------------


def test_a_real_stroke_across_another_parts_pad_is_one_warn():
    pad = _pad("1", component="U6", pin="1", net="VBUS")
    silk = _shape([(-40.0, 0.0), (40.0, 0.0)], id="p7")
    findings = _run(pad, shapes=[silk])

    assert len(findings) == 1
    (finding,) = findings
    assert finding.rule_id == "pcb-silk-on-foreign-pad"
    assert finding.severity == "WARN"
    assert finding.level == "L1-pcb-geometry"
    # both sides named, in the two structured slots the report and the canvas read
    assert finding.target.component_ref == "U6"
    assert finding.target.counterpart_ref == "U1"
    # 空 = 离线拿不到画布 live id；封装模板 id 不许冒充
    assert finding.target.primitive_id == ""
    assert finding.target.pin_refs == ["1"]
    assert finding.target.net_refs == ["VBUS"]
    # 本规则不量深度、不量面积 → target 里也没有 measurement
    assert finding.target.measurement is None

    (pad_line,) = _pad_lines(finding)
    assert "U6.1" in pad_line and "VBUS" in pad_line
    assert "#p7" in pad_line and "poly" in pad_line and "TOP_SILK" in pad_line
    joined = "\n".join(finding.evidence)
    for fabricated in ("mil²", "mm²", "深度："):
        assert fabricated not in joined


def test_one_warn_per_device_pair_with_one_evidence_line_per_pad():
    pads = [
        _pad("1", component="U6", pin="1", net="A", y=0.0),
        _pad("2", component="U6", pin="2", net="B", y=60.0),
        _pad("1", component="U7", pin="1", y=120.0),
    ]
    shapes = [
        _shape([(-40.0, 0.0), (40.0, 0.0)], id="s1"),
        _shape([(-40.0, 60.0), (40.0, 60.0)], id="s2"),
        _shape([(-40.0, 120.0), (40.0, 120.0)], id="s3"),
    ]
    findings = _run(*pads, shapes=shapes)

    warns = _warns(findings)
    assert len(warns) == 2, "one WARN per (silk part, pad part) — 2 pads of U6 still one"
    by_pad_part = {finding.target.component_ref: finding for finding in warns}
    assert set(by_pad_part) == {"U6", "U7"}
    u6 = by_pad_part["U6"]
    assert len(_pad_lines(u6)) == 2
    assert u6.target.pin_refs == ["1", "2"]
    assert u6.target.net_refs == ["A", "B"]
    assert [finding.target.component_ref for finding in warns] == ["U6", "U7"]

    # a part with no pad hit here is not named at all
    assert all(finding.target.counterpart_ref == "U1" for finding in warns)


# ---------------------------------------------------------------------------
# the exemptions: same part, tangency, the other face, board-level artwork
# ---------------------------------------------------------------------------


def test_a_part_does_not_cover_its_own_pads():
    pad = _pad("1", component="U6")
    own = _shape([(-40.0, 0.0), (40.0, 0.0)], component="U6")
    assert _run(pad, shapes=[own]) == []


def test_an_unnamed_parts_identity_is_its_component_id():
    pad = _pad("1", component=None, component_id="pad-uuid", pin=None)
    other = _shape([(-40.0, 0.0), (40.0, 0.0)], component=None, component_id="silk-uuid")
    findings = _run(pad, shapes=[other])

    warns = _warns(findings)
    assert len(warns) == 1
    (finding,) = warns
    # 两侧都没有位号：structured 的 designator 槽留空，component_id 写进 evidence
    assert finding.target.component_ref == ""
    assert finding.target.counterpart_ref == ""
    joined = "\n".join(finding.evidence)
    assert "pad-uuid" in joined and "silk-uuid" in joined

    # the same unnamed instance on both sides is the same device
    same = _shape(
        [(-40.0, 0.0), (40.0, 0.0)], component=None, component_id="pad-uuid"
    )
    assert _run(pad, shapes=[same]) == []


def test_a_stroke_that_only_touches_the_pad_edge_is_not_overlap():
    pad = _pad("1", component="U6")
    # pad is 40×20 at the origin (top edge y = 10), ink half-width is 4:
    # the ink's lower edge is exactly the pad's top edge — contact, not area.
    tangent = _shape([(-40.0, 14.0), (40.0, 14.0)])
    assert _run(pad, shapes=[tangent]) == []
    # one mil further in is already a positive area
    inside = _shape([(-40.0, 13.0), (40.0, 13.0)])
    assert len(_warns(_run(pad, shapes=[inside]))) == 1


def test_bottom_silk_is_not_on_a_top_pad_and_vice_versa():
    top_pad = _pad("1", component="U6", layers=(TOP,))
    bottom_pad = _pad("1", component="U6", layers=(BOTTOM,))
    bottom_ink = _shape([(-40.0, 0.0), (40.0, 0.0)], layer_kind="BOT_SILK")

    assert _run(top_pad, shapes=[bottom_ink]) == []
    assert len(_warns(_run(bottom_pad, shapes=[bottom_ink]))) == 1

    top_ink = _shape([(-40.0, 0.0), (40.0, 0.0)])
    assert len(_warns(_run(top_pad, shapes=[top_ink]))) == 1
    assert _run(bottom_pad, shapes=[top_ink]) == []


def test_board_level_artwork_belongs_to_nobody():
    pad = _pad("1", component="U6")
    unowned = _shape([(-40.0, 0.0), (40.0, 0.0)], component=None, component_id=None)
    assert _run(pad, shapes=[unowned]) == []
    # control: the same geometry with a device on it does report
    owned = _shape([(-40.0, 0.0), (40.0, 0.0)], component="U1")
    assert len(_warns(_run(pad, shapes=[owned]))) == 1


# ---------------------------------------------------------------------------
# the screen is not the judge: the ear of a round pad's box, a fill's notch
# ---------------------------------------------------------------------------


def test_the_ear_of_a_round_pads_box_is_not_copper():
    disc = _pad("1", component="U6", width=100.0, height=100.0, shape="ELLIPSE")
    x0, y0, x1, y1 = _pad_box(disc)
    dot = _shape([(49.0, 49.0)], kind="circle", width=0.0, radius=1.0)
    # the ink is inside the pad's *box*: the screen lets it through …
    assert x0 <= 49.0 <= x1 and y0 <= 49.0 <= y1
    # … and the predicate refuses it: the disc's corner is 19.3 mil away from it
    assert _run(disc, shapes=[dot]) == []
    # control: the same dot at the disc's centre is a real hit
    centre = _shape([(0.0, 0.0)], kind="circle", width=0.0, radius=1.0)
    assert len(_warns(_run(disc, shapes=[centre]))) == 1


C_FILL = [
    (-100.0, -100.0),
    (100.0, -100.0),
    (100.0, 100.0),
    (-100.0, 100.0),
    (-100.0, 30.0),
    (-20.0, 30.0),
    (-20.0, -30.0),
    (-100.0, -30.0),
]


def test_a_concave_fill_is_ink_and_its_notch_is_not():
    fill = _shape(C_FILL, kind="fill", width=0.0, filled=True, id="f1")
    inside = _pad("1", component="U6", x=50.0, y=0.0)
    notch = _pad("1", component="U6", x=-60.0, y=0.0)

    findings = _run(inside, shapes=[fill])
    (finding,) = _warns(findings)
    assert "单环 filled" in "\n".join(finding.evidence)

    # the pad in the notch is inside the fill's box but outside its interior
    x0, y0, x1, y1 = _pad_box(notch)
    assert x0 >= -100.0 and x1 <= -20.0
    assert _run(notch, shapes=[fill]) == []


def test_a_zero_width_stroke_has_no_area_but_a_fill_still_does():
    pad = _pad("1", component="U6")
    hairline = _shape([(-40.0, 0.0), (40.0, 0.0)], width=0.0)
    assert _run(pad, shapes=[hairline]) == []
    filled = _shape(
        [(-40.0, -20.0), (40.0, -20.0), (40.0, 20.0), (-40.0, 20.0)],
        kind="fill",
        width=0.0,
        filled=True,
    )
    assert len(_warns(_run(pad, shapes=[filled]))) == 1


# ---------------------------------------------------------------------------
# closed, single-point circles, chords
# ---------------------------------------------------------------------------


def test_closed_only_adds_the_geometric_last_edge():
    pad = _pad("1", component="U6", x=-10.0, y=0.0, width=20.0, height=20.0)
    triangle = [(0.0, 60.0), (60.0, -40.0), (-20.0, -40.0)]
    # the closing edge (-20,-40) -> (0,60) crosses the pad at (-12, 0);
    # the two explicit edges stay clear of it.
    closed = _shape(triangle, kind="poly", id="c1")
    assert len(_warns(_run(pad, shapes=[closed]))) == 1
    open_line = _shape(triangle, kind="line", id="c2")
    assert _run(pad, shapes=[open_line]) == []

    # a ring whose last vertex repeats the first is closed too
    repeated = _shape(list(triangle) + [triangle[0]], kind="poly")
    assert len(_warns(_run(pad, shapes=[repeated]))) == 1


def test_a_single_point_circle_is_a_disc_of_radius_plus_half_width():
    pad = _pad("1", component="U6")
    # radius 2.361 + width/2 1.5 = 3.861 below the pad's top edge (y = 10)
    dot = _shape([(0.0, 0.0)], kind="circle", width=3.0, radius=2.361)
    findings = _run(pad, shapes=[dot])
    (finding,) = _warns(findings)
    assert "单点圆按 radius + width/2 的圆盘" in "\n".join(finding.evidence)

    # 7.9 mil above the pad's top edge: farther than 3.861 = radius + width/2
    outside = _shape([(0.0, 17.9)], kind="circle", width=3.0, radius=2.361)
    assert _run(pad, shapes=[outside]) == []
    through = _shape([(0.0, 13.0)], kind="circle", width=3.0, radius=2.361)
    assert len(_warns(_run(pad, shapes=[through]))) == 1


def test_a_chorded_arc_is_measured_as_the_chord_it_is():
    pad = _pad("1", component="U6")
    chord = _shape([(-40.0, 0.0), (40.0, 0.0)], arc_count=3, id="a1")
    findings = _run(pad, shapes=[chord])
    warns, infos = _warns(findings), _infos(findings)
    assert len(warns) == 1, "the chord is the ink the parser gives us — it is measured"
    assert len(infos) == 1
    assert "圆弧按端点弦化" in "\n".join(warns[0].evidence)


# ---------------------------------------------------------------------------
# the approximation disclosure: one INFO per board, never a WARN
# ---------------------------------------------------------------------------


def test_the_approximation_disclosure_is_one_info_per_board():
    pads = [
        _pad("1", component="U6", pin="1"),
        _pad("1", component="U7", pin="1", y=200.0),
    ]
    shapes = [
        _shape([(-40.0, 0.0), (40.0, 0.0)], component="U1", arc_count=2, id="a1"),
        _shape(
            [(-15.0, 192.0), (15.0, 192.0), (15.0, 208.0), (-15.0, 208.0)],
            kind="rect",
            component="U2",
            radius=3.0,
            width=6.0,
            id="r1",
        ),
        # far from every pad, yet still an approximated reading of this board
        _shape([(900.0, 900.0), (960.0, 900.0)], component="U3", arc_count=1),
    ]
    findings = _run(*pads, shapes=shapes)

    warns, infos = _warns(findings), _infos(findings)
    assert len(infos) == 1, "at most one INFO per board"
    assert len(warns) == 2, "the disclosure neither suppresses nor inflates the WARNs"
    info = infos[0]
    assert info.rule_id == "pcb-silk-on-foreign-pad"
    assert info.severity == "INFO"
    joined = "\n".join(info.evidence)
    for device in ("U1", "U2", "U3"):
        assert device in joined
    assert "弦化" in joined and "角点" in joined
    assert "非解析圆弧" in info.message

    # the INFO is not counted as ink on copper
    assert [finding.target.component_ref for finding in warns] == ["U6", "U7"]


def test_a_board_without_approximated_ink_has_no_info():
    pad = _pad("1", component="U6")
    plain = _shape([(-40.0, 0.0), (40.0, 0.0)])
    findings = _run(pad, shapes=[plain])
    assert len(_warns(findings)) == 1
    assert _infos(findings) == []


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------


def test_the_rule_is_registered_right_after_the_designator_rule():
    ids = [rule.id for rule in pcbreview.BUILTIN_PCB_RULES]
    assert "pcb-silk-designator" in ids
    # 038Y4 inserted `pcb-silk-under-body` right after the designator rule, so
    # this one is now two positions along — the family order is unchanged.
    assert ids.index("pcb-silk-under-body") == ids.index("pcb-silk-designator") + 1
    assert ids.index("pcb-silk-on-foreign-pad") == ids.index("pcb-silk-designator") + 2
    rule = pcbreview.BUILTIN_PCB_RULES[ids.index("pcb-silk-on-foreign-pad")]
    assert isinstance(rule, SilkOnForeignPad)
    assert isinstance(rule, PcbRule)
    assert rule.level == "L1-pcb-geometry"
    assert rule.title and rule.source


def test_an_empty_board_returns_nothing():
    assert _run() == []


# ---------------------------------------------------------------------------
# the 200 mil position grid is a screen, not a judgement
# ---------------------------------------------------------------------------


def _screen_board():
    """A board that exercises the grid: negative coordinates, several cells, both
    pad shapes, a stroke longer than the board, and pads on cell boundaries.

    Cell size is 200 mil and cell edges are multiples of it, so the sample has a
    pad centred **exactly** on ``x = 200``, a pad row centred on ``y = -200``, a
    filled ring whose edges coincide with ``x = 150`` / ``x = 250`` and a
    1400-mil stroke crossing seven cells. Two devices are unnamed (identified by
    ``component_id``) so the identity fall-through is inside the comparison too.
    """
    pads = [
        _pad("1", component="U6", pin="1"),                                  # cell 0,0
        _pad("2", component="U6", pin="2", y=-200.0),                        # row on a cell edge
        _pad("1", component="U8", pin="1", x=200.0, width=100.0,
             height=100.0, shape="ELLIPSE"),                                 # centre on a cell edge
        _pad("1", component="U9", pin="1", x=-420.0, y=130.0, width=100.0,
             height=100.0, shape="ELLIPSE"),                                 # negative cells
        _pad("1", component="U7", pin="1", x=610.0, y=610.0),                # untouched
        _pad("1", component=None, component_id="pm-c", pin="1", y=400.0),    # unnamed part
    ]
    shapes = [
        _shape([(-700.0, 0.0), (700.0, 0.0)], id="long"),                     # 7 cells wide
        _shape([(250.0, -200.0), (350.0, -200.0)], id="row"),
        _shape(
            [(150.0, -60.0), (250.0, -60.0), (250.0, 60.0), (150.0, 60.0)],
            kind="fill",
            width=0.0,
            filled=True,
            component="U3",
            id="ring",
        ),
        # a pin-1 dot in the ear of U9's round pad: the boxes meet, the copper is
        # 19.3 mil away — the negative control that keeps the sweep honest.
        _shape([(-371.0, 179.0)], kind="circle", width=0.0, radius=1.0,
               component="U2", id="dot"),
        _shape([(-40.0, 400.0), (40.0, 400.0)], component=None,
               component_id="sl-c", id="unnamed"),
    ]
    return _board(*pads, shapes=shapes)


def _gridless_pairs(board):
    """Every hit by brute force: each shape against **every** pad, no screen."""
    from boardwise.rules.pcb.silkpad import FACE_OF_SILK, _ink, _pad_identity, _silk_identity

    pairs = set()
    screened_out = 0
    for index, shape in enumerate(board.silk_shapes):
        face = FACE_OF_SILK.get(str(shape.layer_kind or ""))
        if face is None:
            continue
        silk_identity = _silk_identity(shape, index)
        if silk_identity is None:
            continue
        ink = _ink(shape)
        if ink is None:
            continue
        points, half, filled, closed, _model = ink
        for pad_index, pad in enumerate(board.pads):
            if silk_identity == _pad_identity(pad, pad_index):
                continue
            hit = pad_ink_overlap(
                board, pad, points=points, half_width=half, layers={face},
                filled=filled, closed=closed,
            )
            if hit:
                pairs.add((pad.component or "", shape.component or ""))
            else:
                screened_out += 1
    return pairs, screened_out


def test_the_position_grid_agrees_with_a_gridless_sweep():
    """The grid + bbox screen must only *skip* work, never change an answer.

    Same ``pad_ink_overlap`` calls, same identity rules, same ink model — the one
    difference is that the rule walks cells instead of the whole board. If a
    screen ever dropped a real hit (or invented one), the two pair sets would
    differ here.
    """
    board = _screen_board()
    findings = SilkOnForeignPad().check(
        PcbReviewContext(board=board, board_title="PCB1")
    )
    produced = {
        (finding.target.component_ref, finding.target.counterpart_ref)
        for finding in _warns(findings)
    }
    expected, screened_out = _gridless_pairs(board)

    assert expected, "the fixture must produce hits, or this test asserts nothing"
    assert produced == expected
    assert len(produced) == len(_warns(findings)), "one WARN per device pair"
    # non-empty in all three ways the sample was built for
    assert ("U6", "U1") in produced   # a 1400-mil stroke across two pads of one part
    assert ("U8", "U1") in produced   # …including the pad centred on a cell edge
    assert ("U8", "U3") in produced   # a filled ring whose edges sit on cell edges
    assert ("U6", "U1") in produced and ("", "") in produced  # unnamed pair
    # and the negative control really was a box-overlap that the copper refused
    assert screened_out > 0
    dot, disc = board.silk_shapes[3], board.pads[3]
    x0, y0, x1, y1 = _pad_box(disc)
    dot_box = _pad_box_of_shape(dot)
    assert x0 < dot_box[2] and dot_box[0] < x1 and y0 < dot_box[3] and dot_box[1] < y1
    assert not pad_ink_overlap(
        board, disc, points=dot.points, half_width=1.0, layers={TOP}, filled=False, closed=False
    )
    assert ("U9", "U2") not in produced


def _pad_box_of_shape(shape) -> tuple[float, float, float, float]:
    """The ink box the screen would compute for one primitive."""
    from boardwise.rules.pcb.silkpad import _ink, _ink_box

    points, half, _filled, _closed, _model = _ink(shape)
    return _ink_box(points, half)


def test_the_same_board_twice_gives_the_same_findings():
    board = _screen_board()
    first = SilkOnForeignPad().check(PcbReviewContext(board=board, board_title="PCB1"))
    second = SilkOnForeignPad().check(PcbReviewContext(board=board, board_title="PCB1"))
    assert [(f.severity, f.message, f.evidence) for f in first] == [
        (f.severity, f.message, f.evidence) for f in second
    ]
