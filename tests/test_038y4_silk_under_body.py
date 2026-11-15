"""Tests for task 038Y4: ``pcb-silk-under-body`` — 封装丝印文字被真实本体多边形压住.

Every case is hand-built (no fixture, no parser), because the question is a
geometric predicate over two objects the parser already hands over. Three things
are asserted that a 「one WARN on overlap」 test would miss:

* the **body is the real polygon, not its bbox** — the U-shaped control's notch
  is inside the body's box and the rule still says nothing, and a text straddling
  the notch edge is reported as **partial**;
* the **text box is the project's own reading**, not a fixed 0.62 advance: a
  measured box wins in **both** directions, and the estimated evidence says
  「估算值」 while the measured one says 「实测」;
* the **area floor is `>= 80000 mil²` of the real polygon** (79999 no, 80001
  yes), the same part is **not exempt**, and the aggregation is one row per
  (mark, body device) pair.
"""

from __future__ import annotations

from boardwise.core.geometry import (
    BoardGeometry,
    ComponentPlacement,
    LayerInfo,
    Point,
    SilkShape,
    SilkText,
)
from boardwise.engines import pcbreview
from boardwise.rules.pcb.base import PcbReviewContext, PcbRule
from boardwise.rules.pcb.silkbody import MIN_BODY_AREA_MIL2, SilkUnderBody

TOP = 1
BOTTOM = 2

RULE_ID = "pcb-silk-under-body"


# ---------------------------------------------------------------------------
# hand-built boards
# ---------------------------------------------------------------------------


def _square(side: float, *, x0: float = 0.0, y0: float = 0.0):
    return [(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side)]


def _rect(width: float, height: float, *, x0: float = 0.0, y0: float = 0.0):
    return [(x0, y0), (x0 + width, y0), (x0 + width, y0 + height), (x0, y0 + height)]


def _shape(
    points,
    *,
    component: str | None = "U1",
    component_id: str | None = None,
    kind: str = "poly",
    arc_count: int = 0,
    radius: float | None = None,
    face: int | None = TOP,
    layer_kind: str = "COMPONENT_SHAPE",
    id: str = "1",
) -> SilkShape:
    """One instantiated body primitive, already in board coordinates."""
    coords = [
        point if isinstance(point, Point) else Point(float(point[0]), float(point[1]))
        for point in points
    ]
    return SilkShape(
        id=id,
        component=component,
        component_id=component_id or (f"c{component}" if component else None),
        kind=kind,
        layer_id=48,
        layer_kind=layer_kind,
        declared_layer_kind=layer_kind,
        face=face,
        points=coords,
        local_points=list(coords),
        width=6.0,
        radius=radius,
        arc_count=arc_count,
    )


def _text(
    text: str = "1",
    *,
    x: float = 0.0,
    y: float = 0.0,
    component: str | None = "U2",
    component_id: str | None = None,
    source: str = "footprint",
    angle: float = 0.0,
    origin: str = "LEFT_BOTTOM",
    layer_kind: str = "TOP_SILK",
    layer_id: int | None = 3,
    font_size: float = 45.0,
    visible: bool = True,
    mirror: bool = False,
    reverse: bool = False,
) -> SilkText:
    return SilkText(
        component=component,
        component_id=component_id or (f"c{component}" if component else None),
        text=text,
        source=source,
        x=x,
        y=y,
        local_x=x,
        local_y=y,
        angle=angle,
        stored_angle=angle,
        layer_id=layer_id,
        layer_kind=layer_kind,
        declared_layer_kind=layer_kind,
        font_size=font_size,
        origin=origin,
        visible=visible,
        mirror=mirror,
        reverse=reverse,
    )


def _board(*texts: SilkText, shapes=(), placements=()) -> BoardGeometry:
    designators = []
    for item in list(texts) + list(shapes):
        name = getattr(item, "component", None)
        if name and name not in designators:
            designators.append(name)
    given = {str(item.designator) for item in placements}
    components = [
        ComponentPlacement(id=f"c{name}", designator=name, layer_id=TOP)
        for name in designators
        if name not in given
    ]
    components.extend(placements)
    return BoardGeometry(
        layers={
            TOP: LayerInfo(TOP, "Top Layer", "TOP"),
            BOTTOM: LayerInfo(BOTTOM, "Bottom Layer", "BOTTOM"),
        },
        components=components,
        silk_shapes=list(shapes),
        silk_texts=list(texts),
    )


def _run(*texts: SilkText, shapes=(), placements=(), measured=None, title: str = "PCB1"):
    board = _board(*texts, shapes=shapes, placements=placements)
    rule = SilkUnderBody(measured)
    return rule.check(PcbReviewContext(board=board, board_title=title))


def _warns(findings):
    return [finding for finding in findings if finding.severity == "WARN"]


def _infos(findings):
    return [finding for finding in findings if finding.severity == "INFO"]


# ---------------------------------------------------------------------------
# the area floor: 79999 vs 80001
# ---------------------------------------------------------------------------


def test_a_body_one_square_mil_under_the_floor_is_not_a_body():
    """200 × 399.995 = 79999 mil² — the body is real, but it is not big enough."""
    findings = _run(
        _text("1", x=10, y=10),
        shapes=[_shape(_rect(200, 399.995))],
    )
    assert _warns(findings) == []
    assert _infos(findings) == []


def test_a_body_one_square_mil_over_the_floor_is_a_body():
    """200 × 400.005 = 80001 mil² — the floor is inclusive at the contract's number."""
    findings = _run(
        _text("1", x=10, y=10),
        shapes=[_shape(_rect(200, 400.005))],
    )
    warns = _warns(findings)
    assert len(warns) == 1
    assert "80000" in "".join(warns[0].evidence)
    assert MIN_BODY_AREA_MIL2 == 80000.0


def test_the_floor_uses_the_real_polygon_and_not_the_box():
    """A bbox-based area would make a thin L-shape big; the shoelace does not."""
    # bbox 400 × 400 = 160000 mil², real polygon 200 × 400 + 200 × 40 = 88000.
    l_shape = [(0, 0), (200, 0), (200, 360), (400, 360), (400, 400), (0, 400)]
    findings = _run(_text("1", x=10, y=10), shapes=[_shape(l_shape)])
    assert len(_warns(findings)) == 1
    # The same polygon scaled down is under the floor even though its box is large.
    small = [(x * 0.4, y * 0.4) for x, y in l_shape]  # 14080 mil²
    assert _run(_text("1", x=10, y=10), shapes=[_shape(small)]) == []


# ---------------------------------------------------------------------------
# concave body: the polygon is the judge, the box is only a screen
# ---------------------------------------------------------------------------

#: Outer 400 × 400 (160000 mil²) minus a 100 × 200 notch cut from the top edge:
#: real area 140000 mil², and the notch is well inside the body's own bbox.
_U_SHAPE = [
    (0, 0), (400, 0), (400, 400), (250, 400),
    (250, 200), (150, 200), (150, 400), (0, 400),
]


def test_a_text_inside_the_notch_is_not_covered():
    """The notch is inside the body's **bbox** and outside its polygon — the control.

    A rule that intersected the two boxes would report this: the text box at
    (180, 300)–(216, 345) is entirely within (0, 0)–(400, 400). The polygon says
    no area is shared, and that is the answer.
    """
    findings = _run(_text("1", x=180, y=300), shapes=[_shape(_U_SHAPE, arc_count=0)])
    assert _warns(findings) == []
    assert _infos(findings) == []


def test_a_text_straddling_the_notch_edge_is_partially_covered():
    """Box (140, 300)–(176, 345) crosses x = 150, so one side is real body."""
    findings = _run(_text("1", x=140, y=300), shapes=[_shape(_U_SHAPE)])
    warns = _warns(findings)
    assert len(warns) == 1
    assert "部分压住" in warns[0].message
    assert "完全" not in warns[0].message.split("部分压住")[0].split("本体")[-1]


# ---------------------------------------------------------------------------
# full vs partial wording
# ---------------------------------------------------------------------------


def test_a_box_wholly_inside_the_body_is_reported_as_fully_covered():
    findings = _run(_text("1", x=100, y=100), shapes=[_shape(_square(300))])
    warns = _warns(findings)
    assert len(warns) == 1
    assert "完全压住" in warns[0].message
    assert "四角全落在" in warns[0].message


def test_a_box_only_clipping_the_body_edge_is_reported_as_partial():
    findings = _run(_text("1", x=270, y=100), shapes=[_shape(_square(300))])
    warns = _warns(findings)
    assert len(warns) == 1
    assert "部分压住" in warns[0].message
    assert "完全压住" not in warns[0].message


def test_a_tangent_box_is_not_coverage():
    """Box starts exactly at the body's right edge: contact is not positive area."""
    findings = _run(_text("1", x=300, y=100), shapes=[_shape(_square(300))])
    assert _warns(findings) == []


# ---------------------------------------------------------------------------
# faces
# ---------------------------------------------------------------------------


def test_a_body_on_the_other_face_is_not_compared():
    findings = _run(
        _text("1", x=100, y=100, layer_kind="TOP_SILK"),
        shapes=[_shape(_square(300), face=BOTTOM)],
    )
    assert _warns(findings) == []


def test_a_bottom_text_meets_a_bottom_body():
    findings = _run(
        _text("1", x=100, y=100, layer_kind="BOT_SILK", layer_id=4),
        shapes=[_shape(_square(300), face=BOTTOM)],
    )
    assert len(_warns(findings)) == 1


def test_the_body_face_falls_back_to_the_placement_when_the_primitive_states_none():
    """162b's ``face`` is the first reading; a shape without it reads its part's."""
    bottom_part = ComponentPlacement(id="cU1", designator="U1", layer_id=BOTTOM)
    findings = _run(
        _text("1", x=100, y=100, layer_kind="BOT_SILK", layer_id=4),
        shapes=[_shape(_square(300), face=None)],
        placements=[bottom_part],
    )
    assert len(_warns(findings)) == 1


# ---------------------------------------------------------------------------
# text pose: angle and anchor decide where the ink is
# ---------------------------------------------------------------------------


def test_a_text_rotated_180_degrees_is_measured_in_its_own_frame():
    """At 180° the box runs **−x** from the anchor: body on the left, not the right."""
    left = _run(
        _text("12", x=300, y=300, angle=180.0),
        shapes=[_shape(_rect(400, 400, x0=0, y0=0))],
    )
    assert len(_warns(left)) == 1
    right = _run(
        _text("12", x=300, y=300, angle=180.0),
        shapes=[_shape(_rect(100, 100, x0=300, y0=300))],
    )
    assert _warns(right) == []


def test_right_and_center_anchors_place_the_box_on_the_other_side_of_the_anchor():
    # The mark is "12" at 45 mil: LEFT box x 300–372, RIGHT x 228–300, CENTER 264–336.
    # Tall narrow bodies (60 × 1400 = 84000 mil²) so the x band is what decides.
    body_low = _shape(_rect(60, 1400, x0=200, y0=280))    # x 200–260
    body_high = _shape(_rect(60, 1400, x0=310, y0=280))   # x 310–370
    assert _warns(_run(_text("12", x=300, y=300), shapes=[body_low])) == []      # LEFT runs right
    assert _warns(_run(_text("12", x=300, y=300), shapes=[body_high]))          # LEFT meets it
    assert _warns(_run(_text("12", x=300, y=300, origin="RIGHT_BOTTOM"), shapes=[body_low]))
    assert _warns(_run(_text("12", x=300, y=300, origin="RIGHT_BOTTOM"), shapes=[body_high])) == []
    # CENTER straddles the anchor: it meets the high body, the low one stays clear.
    assert _warns(_run(_text("12", x=300, y=300, origin="CENTER_BOTTOM"), shapes=[body_high]))
    assert _warns(_run(_text("12", x=300, y=300, origin="CENTER_BOTTOM"), shapes=[body_low])) == []


# ---------------------------------------------------------------------------
# scope: which text is this rule about
# ---------------------------------------------------------------------------


def test_designator_free_and_hidden_texts_are_out_of_scope():
    body = _shape(_square(400))
    findings = _run(
        _text("1", x=100, y=100, source="designator"),
        _text("2", x=100, y=100, source="board"),
        _text("3", x=100, y=100, visible=False),
        _text("4", x=100, y=100, source="designator-unparented"),
        shapes=[body],
    )
    assert findings == []


def test_a_print_on_a_non_silk_layer_is_out_of_scope():
    findings = _run(
        _text("1", x=100, y=100, layer_kind="TOP_ASSEMBLY", layer_id=49),
        shapes=[_shape(_square(400))],
    )
    assert findings == []


# ---------------------------------------------------------------------------
# width provenance: measured first, estimate disclosed (172)
# ---------------------------------------------------------------------------


def test_a_measured_box_wins_over_the_estimate_in_both_directions():
    """The host's reading replaces the band: it can add a hit and it can remove one."""
    text = _text("+", x=0, y=0)
    # Estimate: 1 × 0.8 × 45 = 36 mil wide from x = 0, so the body at 100 is far.
    far = _shape(_rect(400, 400, x0=100, y0=0))
    assert _warns(_run(text, shapes=[far])) == []
    measured = {("PCB1", "+"): (90.0, 0.0, 200.0, 45.0)}
    warns = _warns(_run(text, shapes=[far], measured=measured))
    assert len(warns) == 1
    assert "实测" in "".join(warns[0].evidence)
    # …and the other way round: a measured box that misses the estimate's hit.
    near = _shape(_rect(400, 400, x0=20, y0=0))
    assert len(_warns(_run(text, shapes=[near]))) == 1
    away = {("PCB1", "+"): (500.0, 500.0, 560.0, 545.0)}
    assert _warns(_run(text, shapes=[near], measured=away)) == []


def test_the_estimate_is_labelled_as_an_estimate_and_no_area_is_fabricated():
    findings = _run(_text("1", x=100, y=100), shapes=[_shape(_square(300))])
    evidence = "".join(_warns(findings)[0].evidence)
    assert "估算值" in evidence
    assert "实测" not in evidence.split("宽度来源")[0]
    assert "0.62" not in evidence
    # The body's own area is a reading and may be stated; the ink's is not.
    assert "实际面积" in evidence


# ---------------------------------------------------------------------------
# aggregation and target
# ---------------------------------------------------------------------------


def test_one_warn_per_mark_and_body_device_pair_even_with_two_body_primitives():
    """Two COMPONENT_SHAPE records of one part covering one mark = one row."""
    findings = _run(
        _text("1", x=100, y=100),
        shapes=[
            _shape(_rect(400, 250, x0=0, y0=0), id="1"),
            _shape(_rect(400, 250, x0=0, y0=-100), id="2"),
        ],
    )
    warns = _warns(findings)
    assert len(warns) == 1
    assert "".join(warns[0].evidence).count("本体图元 #") == 2


def test_two_marks_of_one_device_each_get_their_own_row():
    findings = _run(
        _text("1", x=100, y=100),
        _text("2", x=150, y=100),
        shapes=[_shape(_square(300))],
    )
    assert len(_warns(findings)) == 2


def test_the_same_device_is_not_exempt_and_the_target_names_both_sides():
    findings = _run(
        _text("1", x=100, y=100, component="U1"),
        shapes=[_shape(_square(300), component="U1")],
    )
    warns = _warns(findings)
    assert len(warns) == 1
    assert warns[0].target.component_ref == "U1"
    assert warns[0].target.counterpart_ref == "U1"
    assert warns[0].target.primitive_id == ""
    assert "同器件不豁免" in "".join(warns[0].evidence)


def test_the_target_points_at_the_mark_side_and_the_body_side():
    findings = _run(
        _text("1", x=100, y=100, component="U2"),
        shapes=[_shape(_square(300), component="U1")],
    )
    target = _warns(findings)[0].target
    assert target.component_ref == "U2"
    assert target.counterpart_ref == "U1"


# ---------------------------------------------------------------------------
# the approximation disclosure: at most one INFO per board
# ---------------------------------------------------------------------------


def test_chorded_and_rounded_bodies_are_disclosed_once_per_board():
    findings = _run(
        _text("1", x=100, y=100),
        shapes=[
            _shape(_square(300), component="U1", arc_count=4),
            _shape(_square(300, x0=500), component="U3", radius=10.0),
        ],
    )
    infos = _infos(findings)
    assert len(infos) == 1
    assert infos[0].rule_id == RULE_ID
    joined = "".join(infos[0].evidence)
    assert "弦化" in joined and "圆角" in joined
    assert "U1" in joined and "U3" in joined
    # The disclosure never becomes a WARN and never changes the hit count.
    assert len(_warns(findings)) == 1


def test_the_disclosure_appears_even_when_nothing_is_covered():
    findings = _run(_text("1", x=2000, y=2000), shapes=[_shape(_square(300), arc_count=2)])
    assert _warns(findings) == []
    assert len(_infos(findings)) == 1


def test_a_circle_body_is_disclosed_as_its_24_gon():
    """A single-point CIRCLE is read as an **inscribed** 24-gon: also not exact."""
    circle = _shape([(0.0, 0.0)], kind="circle", radius=200.0, id="7")
    findings = _run(_text("1", x=5000, y=5000), shapes=[circle])
    assert _warns(findings) == []
    infos = _infos(findings)
    assert len(infos) == 1
    joined = "".join(infos[0].evidence)
    assert "24 边形" in joined and "非解析圆" in joined
    # …and the same circle is a judgeable body when a mark does sit on it.
    covered = _run(_text("1", x=0, y=0), shapes=[circle])
    assert len(_warns(covered)) == 1
    assert len(_infos(covered)) == 1


def test_a_small_chorded_body_does_not_swallow_the_disclosure():
    """No body clears the area floor, but the chorded reading still happened."""
    small = _shape(_rect(100, 100), arc_count=2, id="9")  # 10000 mil² < 80000
    findings = _run(_text("1", x=10, y=10), shapes=[small])
    assert _warns(findings) == []
    infos = _infos(findings)
    assert len(infos) == 1
    assert "弦化" in "".join(infos[0].evidence)


def test_no_body_primitive_is_no_finding():
    assert _run(_text("1", x=0, y=0)) == []
    assert _run() == []


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------


def test_the_rule_is_registered_between_the_designator_and_the_foreign_pad_rules():
    ids = [rule.id for rule in pcbreview.BUILTIN_PCB_RULES]
    assert ids.index(RULE_ID) == ids.index("pcb-silk-designator") + 1
    assert ids.index("pcb-silk-on-foreign-pad") == ids.index(RULE_ID) + 1
    rule = pcbreview.BUILTIN_PCB_RULES[ids.index(RULE_ID)]
    assert isinstance(rule, SilkUnderBody)
    assert isinstance(rule, PcbRule)
    assert rule.level == "L1-pcb-geometry"
    assert rule.title and rule.source
    assert rule.id == RULE_ID
