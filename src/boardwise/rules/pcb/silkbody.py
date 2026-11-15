"""丝印被**器件本体**压住 — ``pcb-silk-under-body`` (038Y4)。

**问什么**。一颗器件（或封装）自己印在板上的**可见丝印文字**，有没有落进
**同面、另一块足够大的真实本体多边形**里——也就是说，摆完之后这串字被壳子压住。
不是「离得近」，是文字盒与真实本体多边形有**正面积**交集：装配后看不见（或看不全）
那串字。

**为什么不复用预研包 ``.tmp_pcb_review_20261115`` 的 ``silkbody``**（逐条都是口径
问题，不是口味）：

* 它按 ``(x, y, x + 0.62w, y + h)`` 造文字盒——0.62 是**固定字宽比**，而本仓库的
  当前口径是**实测优先 + 字宽比带降级**（172：``SilkText.corners`` +
  :data:`~boardwise.rules.pcb.silk.WIDE_ADVANCE`）。移植它等于在同一份报告里造出
  第二把文字尺；
* 它拿**本体 bbox** 当本体，于是凹形本体的凹口里也「被压住」——本规则里那是
  **不报**的一条反例（``tests/test_038y4_silk_under_body.py`` 钉住它）；
* 它**跨面不过滤**（顶层丝印与底层器件本体照样比）——墨在另一面的本体下方过一遍
  不是被压住。

**范围的三个限定**（每条都是「不是这件事」）：

* 只审 ``source == "footprint"`` 的**可见**丝印文字。**位号**（``designator`` /
  ``designator-unparented``）仍归 :class:`~boardwise.rules.pcb.silk.SilkDesignator`
  的「位号被器件本体压住」那一条；板级自由文字（``source == "board"``）不是封装
  印字，也不归本规则——它本来就画在本体底下，这是标注的常态，没有可查的判据；
* 本体必须是 ``COMPONENT_SHAPE`` 层上的**单个**简单多边形，且**实际多边形面积**
  （shoelace，含 24 边形化后的圆）``>= 80000 mil²``。不用 bbox 面积，也不把一颗
  器件的多条本体记录**合并**成一个 bbox——一片 20000 mil² 的矩形四条加起来 80000
  也不算「一块 80000 mil² 的本体」；
* 面按 ``SilkShape.face``（162b 的物理面；``COMPONENT_SHAPE`` 这类 id 表达不了面的
  层由 parser 按摆件面补上）读，缺了才退到 ``placement.layer_id``；与文字的
  ``SilkText.layer_kind`` 面对不上就不比。**跨面不报**。

**同器件不豁免**：封装把自己的字画进自己的本体里，同样是「印出来看不见」。本规则
不是封装库设计审查，它只陈述「这块板上这串字被这块本体压住」这件事；异器件/同器件
一视同仁。

**文字几何完全复用现有口径**（不另写一套）：盒来自
:meth:`boardwise.core.geometry.SilkText.corners`（:func:`text_box`），宽度两态与
172 一致——**:class:`SilkDesignator` 的宿主实测盒优先**（``self.measured``，键
``(板名, 文字)``，走它的 ``_measured_box``），测不到用**最宽**档
:data:`~boardwise.rules.pcb.silk.WIDE_ADVANCE`（这里问的是「有没有被压住」，宽
估计才不会漏报；与 ``SilkDesignator._covered`` 同一选择）。每条 finding 的
evidence 逐条写明是「实测」还是「估算值」——**不谎称所有 footprint 文字都有宿主
实测盒**：``.epru`` 不带字形步进，离线 ``--file`` 路径上绝大多数封装印字只有估算值。

**相交判定不退化成两个 bbox 相交**。判据是四条**充分**条件，任一条成立即有正面积
交集（因此 OR 起来不会造出假阳性）：

1. 文字盒四角任一**严格**落在本体多边形内部（不在边上）；
2. 本体多边形任一顶点**严格**落在文字盒内部（盒是凸的，直接判凸包含）；
3. 文字盒任一边与本体任一边**真穿越**（严格跨越，端点相碰/共线不算）；
4. 文字盒**中心**严格落在本体内部。

这四条合起来对「凸盒 × 任意简单多边形」是**完备**的：有正面积交集时，交集区域的
边界必由两个多边形的边段组成——要么某个顶点严格落在对方内部，要么两条边真穿越；
两者都没有时交集只能退化成点/线（相切），那正是「不报」。bbox 只做**粗筛**：框不交
⇒ 一定不交，粗筛从不参与结论。

**为什么不直接借 ``core.measure._intersection_area``**（038Y3A 那套 Sutherland–Hodgman
交集面积）：它是**私有**函数，而 ``tests/test_layer_rules.py`` 的层闸禁止规则层引用
core 的私有名，本批的文件域又**不含** ``core/measure.py``（不能把它升成公开名）。
所以判定只用上面四条见证件，并在 evidence 里说清它们是充分条件；本批不复制一份
裁剪算法进来——那会造出「同一件事的第二把尺」。

**完全 / 部分覆盖的措辞如实**。「完全」= 四角**全部**严格落在**同一个**本体多边形
内，**且**该多边形没有任何一条边与文字盒真穿越——凹形本体的凹口切过文字盒时，四角
可能都在多边形内而盒子中间那段其实悬空，这一条边穿越就是把它排除的读法。
其余有正面积交集的情形一律「部分」。

**ARC / 圆角 / 圆近似每板至多一条 INFO**。``arc_count > 0`` 的本体是**弦化**点列，
``radius`` 多点多边形是圆角矩形的**外接尖角**，单点 ``CIRCLE`` 本体被
:meth:`SilkDesignator._shape_polygon` 展开成**内接 24 边形**——三者都不是解析曲线，
且偏差方向各不相同（弦看弧向与内外侧，尖角外接，24 边形内接）。本规则每板把
**在射程内的本体图元**（有归属、``>= 3`` 点，也就是面积门槛本可以判的那些）里带
这两样的登记进**一条** INFO，逐器件点名。它不是 WARN，不计压住，也不改变任何一条
WARN 的判定；但本规则的**沉默**同样建立在这套弦化读数上，不披露就等于宣称精确。

**继承边界（未另校准，不发明修正）**：``mirror`` / ``reverse`` 两个记录标志只原样
写进 evidence，字形镜像的几何语义未校准；多环 / 自交本体不在本规则口径内（parser
只给单环点列）；文字宽度仍是模型（估算态）。这些都在 evidence 里说出来，而不是让
读者以为哪一项是量过的。

**聚合与 target**。每个（文字、本体器件）对**一条** WARN，每块命中本体的图元一行
evidence。``component_ref`` 是**文字那一侧**的器件（印字被压住的那个），
``counterpart_ref`` 是**本体那一侧**的器件——同器件时两个字段指向同一个位号，这不是
矛盾，是本规则明确不豁免的那一档。``primitive_id`` 留空：``SilkShape.id`` 是**封装
模板**的图元 id，跨实例重复，不是画布上的 live id。
"""

from __future__ import annotations

from ...core.geometry import Point
from ..base import Finding, FindingTarget
from .base import PcbReviewContext, PcbRule
from .silk import (
    BODY_KIND,
    ESTIMATED_WIDTH,
    FACE_OF_SILK,
    WIDTH_SOURCE_LABEL,
    WIDE_ADVANCE,
    SilkDesignator,
    _as_xy,
    _point_in_polygon,
    _segment_distance,
    text_box,
)

__all__ = [
    "MIN_BODY_AREA_MIL2",
    "SilkUnderBody",
]


#: 本体多边形的面积门槛，单位 mil²（038Y4 规则合同）。
#:
#: 80000 mil² ≈ 283 × 283 mil（≈ 7.2 × 7.2 mm）。它区分的是「一块真的本体」与
#: 「一颗 0402 / 0603 的小器件」：0603 的占位外形约 63 × 33 mil（≈ 2000 mil²），
#: SOT-23 约 110 × 60 mil（≈ 6600 mil²），而 283 mil 见方正好落在「能压住一串字的
#: 器件」这一档（继电器、电解电容、蜂鸣器、连接器、散热片）。这是**合同给的数**，
#: 不是从本仓库任何一块板上量出来再拟合的阈值。
MIN_BODY_AREA_MIL2 = 80000.0

#: 面积判据的浮点噪声底，单位 mil²。与 ``core.measure._INK_AREA_EPS`` /
#: ``_OVERLAP_EPS`` 同值同义：1 mil 长、1e-9 mil 宽的碎片，比切点残留的浮点误差
#: （坐标是几十到几千 mil，交点误差约 1e-14 mil）高好几个量级。它是**判读门槛**，
#: 不是工艺余量——丝印被本体压住没有「工艺余量」这一说。
_AREA_EPS = 1e-9

#: 长度判据（「点在边上」的排除）用的浮点噪声底，单位 mil。同上，不是容差。
_LENGTH_EPS = 1e-9

#: 粗筛接触容差（mil）：框正好接触不是交集。
_SCREEN_EPS = 1e-9

#: 近似类型的披露字样（INFO 里逐器件点名用）。
_CHORD_APPROX = "圆弧按端点弦化（非解析圆弧）"
_CORNER_APPROX = "圆角矩形按外接角点（非解析圆角）"
_CIRCLE_APPROX = "圆按 24 边形近似（非解析圆）"


def _body_identity(shape) -> tuple[str, str] | None:
    """The device a body primitive belongs to, or ``None``.

    Two steps, the same two 038Y2/038Y3B use: designator when there is one, then
    the footprint instance ``component_id``. Nothing lower: a ``COMPONENT_SHAPE``
    with neither is not a device's body but a board-level drawing, and
    「谁的丝印被谁的本体压住」 has no answer for it.
    """
    designator = str(getattr(shape, "component", None) or "")
    if designator:
        return ("designator", designator)
    component_id = str(getattr(shape, "component_id", None) or "")
    if component_id:
        return ("component", component_id)
    return None


def _identity_label(identity: tuple[str, str] | None) -> str:
    """``U6`` / ``（无位号封装 7c1a…）`` — the device as a reader names it."""
    if identity is None:
        return "（无归属）"
    kind, value = identity
    return value if kind == "designator" else f"（无位号封装 {value}）"


def _text_label(text) -> str:
    """The printed mark as a reader names it: ``U6 的 "+"``."""
    designator = str(getattr(text, "component", None) or "")
    if designator:
        return f"{designator} 的 {text.text!r}"
    component_id = str(getattr(text, "component_id", None) or "")
    if component_id:
        return f"（无位号封装 {component_id}）的 {text.text!r}"
    return repr(text.text)


def _text_identity(text) -> tuple:
    """A stable key for one printed mark (a device may carry several).

    Two footprint ``STRING`` records can share their text (``"1"`` twice on a
    connector) and differ only by pose, so the pose is part of the identity; it
    is the same reading :class:`~boardwise.core.geometry.SilkText` carries for a
    footprint primitive (anchor posed by the placement transform, angle composed
    with it).
    """
    return (
        str(getattr(text, "source", "") or ""),
        str(getattr(text, "component", "") or ""),
        str(getattr(text, "component_id", "") or ""),
        str(getattr(text, "text", "") or ""),
        round(float(getattr(text, "x", 0.0)), 6),
        round(float(getattr(text, "y", 0.0)), 6),
        round(float(getattr(text, "angle", 0.0)), 6),
    )


def _text_face(text) -> int | None:
    return FACE_OF_SILK.get(str(getattr(text, "layer_kind", "") or ""))


def _body_face(ctx, shape) -> int | None:
    """The physical face of a body primitive (162b's field, then the placement)."""
    face = getattr(shape, "face", None)
    if face is not None:
        try:
            return int(face)
        except (TypeError, ValueError):
            pass
    placement = ctx.board.component(str(getattr(shape, "component", "") or ""))
    if placement is None:
        return None
    try:
        return int(getattr(placement, "layer_id", 1) or 1)
    except (TypeError, ValueError):
        return None


def _polygon(shape) -> list[Point]:
    """The body's **real** polygon, through the designator rule's own reader.

    Reused, not re-implemented: :meth:`SilkDesignator._shape_polygon` is the
    reading 152 already publishes (a single-point ``CIRCLE`` becomes a 24-gon,
    any other primitive keeps its points when there are at least three). A
    caller that wrote a second expansion here would be a second answer waiting
    to drift.
    """
    return [Point(*_as_xy(point)) for point in SilkDesignator._shape_polygon(shape)]


def _shoelace(points: list[Point]) -> float:
    """Shoelace area of a polygon outline in mil², positive counter-clockwise.

    Written here rather than borrowed from :mod:`boardwise.core.measure`, whose
    shoelace is a private name (the layer gate forbids rules→core privates and
    this batch may not widen that module's public surface). Five lines of the
    textbook formula, not a second geometry model: the **callers** are what
    matters and they read 「本体多边形的实际面积」, which is this number.
    """
    total = 0.0
    count = len(points)
    for index in range(count):
        a = points[index]
        b = points[(index + 1) % count]
        total += a.x * b.y - b.x * a.y
    return total / 2.0


def _area_ok(points: list[Point], minimum: float = MIN_BODY_AREA_MIL2) -> bool:
    """``abs(shoelace)`` of the **real** polygon against the contract's area."""
    if len(points) < 3:
        return False
    return abs(_shoelace(points)) >= minimum


def _bbox(points: list[Point]) -> tuple[float, float, float, float]:
    xs = [point.x for point in points]
    ys = [point.y for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _boxes_meet(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> bool:
    """Positive-area box intersection — the **screen only** (touching is not it)."""
    return (
        min(a[2], b[2]) - max(a[0], b[0]) > _SCREEN_EPS
        and min(a[3], b[3]) - max(a[1], b[1]) > _SCREEN_EPS
    )


def _cross(ox: float, oy: float, ax: float, ay: float, bx: float, by: float) -> float:
    return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)


def _strictly_inside(point: Point, polygon: list[Point]) -> bool:
    """Point **inside** the polygon, and not on one of its edges.

    The even-odd test is :func:`~boardwise.rules.pcb.silk._point_in_polygon`, the
    house reading (no snap band); 「in」 is then made **strict** by refusing any
    point whose distance to an edge is at or below :data:`_LENGTH_EPS`. That
    distinction is the whole point: a box corner that merely grazes a body edge
    is a tangent reading, and tangency is not coverage.
    """
    coords = [_as_xy(vertex) for vertex in polygon]
    if not _point_in_polygon(point.x, point.y, coords):
        return False
    count = len(coords)
    for index in range(count):
        gap = _segment_distance(
            point.x, point.y, coords[index], coords[(index + 1) % count]
        )
        if gap <= _LENGTH_EPS:
            return False
    return True


def _inside_convex(point: Point, box: list[Point]) -> bool:
    """Strict containment in a **convex** ring (the text box)."""
    count = len(box)
    sign = 0.0
    for index in range(count):
        a, b = box[index], box[(index + 1) % count]
        value = _cross(a.x, a.y, b.x, b.y, point.x, point.y)
        if abs(value) <= _AREA_EPS:
            return False  # on the edge
        if sign == 0.0:
            sign = value
        elif value * sign < 0.0:
            return False
    return True


def _proper_crossing(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    """Two segments crossing **transversally** (endpoint contact is not a crossing).

    Both endpoints of each segment must fall on strictly opposite sides of the
    other's line — ``|cross| > _AREA_EPS`` on every one of the four orientation
    values. Collinear overlap, a shared endpoint and a T-junction therefore read
    as no crossing, which is what keeps the 「相切不报」 contract and the
    「完全盖住」 wording honest.
    """
    o1 = _cross(a1.x, a1.y, a2.x, a2.y, b1.x, b1.y)
    o2 = _cross(a1.x, a1.y, a2.x, a2.y, b2.x, b2.y)
    o3 = _cross(b1.x, b1.y, b2.x, b2.y, a1.x, a1.y)
    o4 = _cross(b1.x, b1.y, b2.x, b2.y, a2.x, a2.y)
    if not (
        (o1 > _AREA_EPS and o2 < -_AREA_EPS)
        or (o1 < -_AREA_EPS and o2 > _AREA_EPS)
    ):
        return False
    return (o3 > _AREA_EPS and o4 < -_AREA_EPS) or (o3 < -_AREA_EPS and o4 > _AREA_EPS)


def _any_crossing(box: list[Point], polygon: list[Point]) -> bool:
    count_a, count_b = len(box), len(polygon)
    for index in range(count_a):
        a1, a2 = box[index], box[(index + 1) % count_a]
        for other in range(count_b):
            if _proper_crossing(a1, a2, polygon[other], polygon[(other + 1) % count_b]):
                return True
    return False


def _centre(box: list[Point]) -> Point:
    return Point(
        sum(point.x for point in box) / len(box),
        sum(point.y for point in box) / len(box),
    )


def _covers(box: list[Point], polygon: list[Point]) -> tuple[bool, bool]:
    """``(meets, full)`` for one text box × one body polygon.

    ``meets`` is the positive-area answer; ``full`` is 「四角全在**这同一个**多边形
    内，且它没有一条边真穿越文字盒」——凹形本体的凹口切过盒子时四角可能都在多边形
    内，那条穿越就是把它判成「部分」的依据。
    """
    if len(polygon) < 3 or len(box) != 4:
        return False, False
    corners_inside = [corner for corner in box if _strictly_inside(corner, polygon)]
    crossing = _any_crossing(box, polygon)
    meets = (
        bool(corners_inside)
        or any(_inside_convex(vertex, box) for vertex in polygon)
        or crossing
        or _strictly_inside(_centre(box), polygon)
    )
    full = len(corners_inside) == 4 and not crossing
    return meets, full and meets


def _approximation(shape) -> str | None:
    """How this body's polygon had to be approximated, or ``None`` when exact.

    Three approximations, one word each:

    * ``arc_count > 0`` — the parser kept the ARC endpoints and dropped the sweep,
      so the measured outline is the chord polyline, not the arc. **Which way the
      chord deviates is not one-directional**: it depends on the arc's sweep
      direction, on which side of the arc the primitive draws its ink, and on
      where the stroke's inner / outer side falls — it is neither always narrow
      nor always wide, and this module does not claim either;
    * ``radius`` on a multi-point primitive — a rounded rectangle read through its
      four sharp corners (the corners' ears are outside the fillets);
    * a single-point ``CIRCLE`` — :meth:`SilkDesignator._shape_polygon` expands it
      to its **24-gon**, which is an *inscribed* polygon of the circle: it is no
      more the circle than a chord is its arc, and on this reading it is smaller
      than the circle everywhere except at the vertices.
    """
    try:
        arcs = int(getattr(shape, "arc_count", 0) or 0)
    except (TypeError, ValueError):
        arcs = 0
    if arcs > 0:
        return _CHORD_APPROX
    points = getattr(shape, "points", None) or []
    if getattr(shape, "radius", None) is not None:
        if len(points) == 1:
            return _CIRCLE_APPROX
        if len(points) > 1:
            return _CORNER_APPROX
    return None


class SilkUnderBody(PcbRule):
    """Visible footprint silk text lying **under** a same-face real body polygon.

    One WARN per (printed mark, body device) pair; at most one INFO per board for
    the chord / rounded-corner / 24-gon readings. See the module docstring for the scope
    (footprint text only, body area ``>= 80000 mil²`` of the **real** polygon,
    same face, no same-part exemption) and for the four sufficient conditions the
    positive-area judgement rests on.
    """

    id = "pcb-silk-under-body"
    title = "Visible footprint silkscreen is not buried under a device body"
    level = "L1-pcb-geometry"
    source = (
        "house rule（038Y4 规则合同：footprint 可见丝印文字 × 同面 COMPONENT_SHAPE "
        "单个简单多边形、实际多边形面积 >= 80000 mil²、正面积交集即 WARN；"
        "相切 / 跨面 / 位号 / 自由文字 / 隐藏文字不报，同器件不豁免）；文字几何复用 "
        "SilkText.corners + 172 实测盒通道与 WIDE_ADVANCE 估算，不写第二把文字尺"
    )

    def __init__(self, measured=None):
        #: 复用 172 的实测盒通道：同一个 ``measured`` 映射、同一套
        #: ``(板名, 文字)`` 键。**本规则不调用它的 ``check()``**——这里只借
        #: ``_measured_box`` 这一个读法，位号规则本身的行为一个字节都不动。
        self._designator = SilkDesignator(measured)

    # -- the pass ---------------------------------------------------------

    def check(self, ctx: PcbReviewContext) -> list[Finding]:
        board = ctx.board
        if board is None:
            return []
        texts = self._texts(board)
        if not texts:
            return []
        bodies, approximated = self._bodies(ctx)
        if not bodies:
            # 面积门槛把每一块本体都筛掉了，但 `_bodies` 收集的近似披露**已经发生**
            # ——它登记在门槛之前，正是为了说明「这块板的本体读数有多可信」。没有
            # 可判本体不代表没有可披露的事：texts 存在、approximated 非空，就交这一
            # 条 INFO（「没判」不等于「精确地判了没压住」）。
            return [self._approximation_note(ctx, approximated)] if approximated else []

        #: ``(文字身份, 本体器件身份) -> {"text": SilkText, "box": 四角,
        #: "measured": 是否有实测盒, "hits": [(本体图元描述, 角点落体数, 是否完全)]}``
        groups: dict[tuple, dict] = {}
        for text in texts:
            face = _text_face(text)
            measured = self._designator._measured_box(ctx, text)
            if measured is not None:
                box = [Point(*_as_xy(corner)) for corner in measured]
            else:
                box = [Point(*_as_xy(corner)) for corner in text_box(text, WIDE_ADVANCE)]
            box_box = _bbox(box)
            for body in bodies:
                if body["face"] != face:
                    continue
                if not _boxes_meet(box_box, body["bbox"]):
                    # 粗筛只排除：框不交 ⇒ 一定不交（本体多边形永远在自己的框内）。
                    continue
                meets, full = _covers(box, body["polygon"])
                if not meets:
                    continue
                group = groups.setdefault(
                    (_text_identity(text), body["identity"]),
                    {
                        "text": text,
                        "body": body["identity"],
                        "box": box,
                        "measured": measured is not None,
                        "hits": [],
                        "full": False,
                    },
                )
                inside = sum(
                    1 for corner in box if _strictly_inside(corner, body["polygon"])
                )
                group["hits"].append((body["label"], inside, full))
                group["full"] = group["full"] or full

        findings = [
            self._warn(ctx, group)
            for _key, group in sorted(
                groups.items(),
                key=lambda item: (item[0][0][1], item[0][1][1], item[0][0][3]),
            )
        ]
        if approximated:
            findings.append(self._approximation_note(ctx, approximated))
        return findings

    # -- inputs -----------------------------------------------------------

    def _texts(self, board) -> list:
        """The printed marks this rule is about: **footprint** silk, visible."""
        return [
            text
            for text in (getattr(board, "silk_texts", None) or [])
            if str(getattr(text, "source", "") or "") == "footprint"
            and bool(getattr(text, "visible", False))
            and bool(str(getattr(text, "text", "") or ""))
            and float(getattr(text, "font_size", 0.0) or 0.0) > 0.0
            and _text_face(text) is not None
        ]

    def _bodies(self, ctx) -> tuple[list[dict], dict]:
        """``(judgeable bodies, approximation registry)`` for this board.

        A body is judgeable when it is a ``COMPONENT_SHAPE`` primitive with a
        device identity, a real polygon of ``>= 3`` points and an area
        ``>= MIN_BODY_AREA_MIL2``. **Each record is judged on its own** — no
        merging of a part's several body records into one outline or one box.

        The approximation registry is filled **before** the area filter: the
        rule's silence over a body that the chorded reading left just under the
        threshold rests on that same approximation, so it may not be disclosed
        only for the bodies that made it.
        """
        bodies: list[dict] = []
        approximated: dict[tuple[str, str], dict[str, str]] = {}
        for shape in getattr(ctx.board, "silk_shapes", None) or []:
            if str(getattr(shape, "layer_kind", "") or "") != BODY_KIND:
                continue
            identity = _body_identity(shape)
            if identity is None:
                continue
            polygon = _polygon(shape)
            if len(polygon) < 3:
                continue
            approximation = _approximation(shape)
            if approximation is not None:
                approximated.setdefault(identity, {})[approximation] = (
                    _identity_label(identity)
                )
            if not _area_ok(polygon):
                continue
            face = _body_face(ctx, shape)
            if face is None:
                continue
            bodies.append({
                "identity": identity,
                "face": face,
                "polygon": polygon,
                "bbox": _bbox(polygon),
                "area": abs(_shoelace(polygon)),
                "label": self._body_label(shape, polygon, approximation),
            })
        return bodies, approximated

    @staticmethod
    def _body_label(shape, polygon: list[Point], approximation: str | None) -> str:
        """``#12（poly，COMPONENT_SHAPE，384 边形…）`` — one hit primitive, named."""
        name = str(getattr(shape, "id", "") or "（无图元 id）")
        kind = str(getattr(shape, "kind", "") or "（无 kind）")
        parts = [
            f"本体图元 #{name}",
            kind,
            f"{len(polygon)} 点",
            f"实际面积 {abs(_shoelace(polygon)):.1f} mil²",
        ]
        if approximation is not None:
            parts.append(approximation)
        return "（" + "，".join(parts) + "）"

    # -- the two findings -------------------------------------------------

    def _warn(self, ctx, group) -> Finding:
        text = group["text"]
        body_identity = group["body"]
        full = bool(group["full"])
        body_labels = "；".join(sorted({hit[0] for hit in group["hits"]}))
        if group["measured"]:
            width_note = self._designator._measured_note(ctx, text, group["box"])
        else:
            width_note = (
                f"宽度来源：{WIDTH_SOURCE_LABEL[ESTIMATED_WIDTH]}——.epru 不带字形步进，"
                f"文字盒按 字符数 × 字宽比 {WIDE_ADVANCE:g} × fontSize"
                f"({float(text.font_size):g} mil) 估，位置按角度与 origin 旋转/摆放"
                "；**这条文字没有宿主实测盒**，所以它是模型，不是读数"
            )
        evidence = [
            f"器件对：{_text_label(text)} × 本体 "
            f"{_identity_label(body_identity)}（同为"
            f"{'顶层' if _text_face(text) == 1 else '底层'}）",
            f"文字记录：layer {text.layer_id}（{text.layer_kind}），锚点 "
            f"({float(text.x):.1f}, {float(text.y):.1f})，角度 {float(text.angle):g}°"
            f"（文件原值 {float(getattr(text, 'stored_angle', 0.0)):g}），"
            f"fontSize {float(text.font_size):g} mil，origin {text.origin or '(空)'}，"
            f"mirror {bool(getattr(text, 'mirror', False))}、"
            f"reverse {bool(getattr(text, 'reverse', False))}（只原样记录：字形镜像的"
            "几何语义未另校准，本规则不发明修正）",
            width_note,
            "命中本体：" + body_labels,
            "判定：文字盒与本体**真实多边形**有正面积交集（严格内点 / 本体顶点落入"
            "盒内 / 真边穿越 / 盒心落体四条见证件，任一成立即可；每一条都是正面积的"
            "充分条件，所以不会因为 OR 起来而多报）；两个 bbox 只做粗筛，从不参与"
            "结论",
            (
                "覆盖程度：文字盒四角**全部**严格落在同一个本体多边形内、且它没有边"
                "真穿越文字盒 → 完全压住；否则是部分压住（凹形本体的凹口可以切过"
                "盒子而四角仍在内，所以单看角点不够）"
            ),
            "同器件不豁免：封装把自己的字画进自己的本体里，板上同样看不见这串字——"
            "本规则陈述几何事实，不判断封装库该怎么画；异器件照审",
            f"面积门槛 {MIN_BODY_AREA_MIL2:g} mil² 用的是**实际多边形面积**"
            "（shoelace；单点圆按 24 边形展开），不是 bbox 面积，也没有把一颗器件的"
            "多条本体记录合并成一个框",
        ]
        return Finding(
            rule_id=self.id,
            severity="WARN",
            level=self.level,
            message=(
                f"{ctx.board_title} {_text_label(text)} 的封装丝印被 "
                f"{_identity_label(body_identity)} 的本体"
                + (
                    "完全压住：文字盒四角全落在对方本体多边形内，摆完之后板上看不见"
                    "这串字"
                    if full
                    else "部分压住：文字盒与对方本体多边形有正面积交集，但不是四角全落"
                    "——字还露着一部分"
                )
            ),
            evidence=evidence,
            target=FindingTarget(
                # 文字那一侧是「被压住的印字」，本体那一侧是对手件：双向都写，
                # 同器件时两个字段指向同一个位号（明确不豁免的那一档）。
                component_ref=(
                    str(text.component)
                    if str(getattr(text, "component", None) or "")
                    else ""
                ),
                counterpart_ref=(
                    str(body_identity[1])
                    if body_identity is not None and body_identity[0] == "designator"
                    else ""
                ),
                primitive_id="",
            ),
        )

    def _approximation_note(self, ctx, approximated) -> Finding:
        """At most one INFO per board: chord / corner readings, not real arcs."""
        rows = [
            f"{next(iter(reasons.values()))}：{'、'.join(sorted(reasons))}"
            for _identity, reasons in sorted(
                approximated.items(), key=lambda item: item[0][1]
            )
        ]
        return Finding(
            rule_id=self.id,
            severity="INFO",
            level=self.level,
            message=(
                f"{len(rows)} 个器件的本体轮廓含圆弧或圆角，本规则只能按 parser 的"
                "弦化 / 角点近似测量（**非解析圆弧**）——这条是范围披露，不是压住读数"
            ),
            evidence=rows
            + [
                "圆弧：parser 保留 ARC 端点、丢掉扫角，量的是端点之间的弦。弦相对真实"
                "圆弧的偏差**方向不单一**——取决于弧的转向（凸 / 凹）、图元把墨画在弧的"
                "哪一侧、以及描边内 / 外侧与文字盒的关系，既可能少报也可能多报，本规则"
                "不对任何一条弧断定方向",
                "圆角矩形：parser 给的是四个**外接尖角**，角上落在圆角外侧；单点圆本体按"
                "**内接** 24 边形量，多边形在圆内（只有顶点落在圆上）。三种近似的偏差"
                "方向不同，逐条披露、不折中成一个数",
                "登记范围是**在射程内的本体图元**（有归属、>= 3 点）：面积门槛本可以"
                "判的那些。每板至多这一条 INFO，它不升级为 WARN、不计入压住的条数，"
                "也不改变任何一条 WARN 的判定",
                "多环 / 自交本体与文字字形的 mirror / reverse 语义不在本口径内——"
                "parser 只给单环点列，字形镜像几何未另校准；本批不发明修正",
            ],
        )
