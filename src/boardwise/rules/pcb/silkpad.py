"""丝印压**别的器件**的焊盘 — ``pcb-silk-on-foreign-pad`` (038Y3B)。

**问什么**。一颗器件的丝印墨迹，有没有真的落到**另一颗器件**的焊盘铜面上。不是
「离得近」，是**别人的可焊面积上盖着墨**：回流时墨会阻焊，装配后那点焊料也盖不全。
判据是几何事实（墨与铜有**正面积**交集），因此本规则没有距离阈值，只有压上 / 没压上。

**唯一最终判定**是 038Y3A 的 :func:`~boardwise.core.measure.pad_ink_overlap`：
真实墨迹 × 真实铜面（``_pad_copper`` 的圆盘 / 跑道 / 旋转矩形 / 038V 的 32 边形），
层也在谓词里。预研包（``.tmp_pcb_review_20261115``）那套口径**不移植**：

* 它拿 :func:`~boardwise.core.measure.pad_corners` 的**外接矩形**当铜面，于是圆盘
  外接框的**耳朵**（框内、盘外，实测 6.568 mil 的空气）被读成压上——本规则里那是
  **不报**的一条反例（``tests/test_038y3b_silk_on_foreign_pad.py`` 钉住它）；
* 它把描边深度与填充深度混成一个「最大深度」数——两者是不同的量，加起来就是编造。
  本规则的 evidence 只点名焊盘、图元和器件对，**不写深度、不写面积**；
* 它拿 ``layer_kind`` 之外的行程判断面——本规则的面读 ``SilkShape.layer_kind``，
  那是 162b 校正过的**物理**面（底层器件的丝印被重命名成 ``BOT_SILK``）。

**豁免**（三条，逐条都是「不是这件事」而不是「容忍」）：

* **同器件**：``pad.component == shape.component``（无位号时按 ``component_id``）跳过。
  封装自己的丝印压自己的焊盘是封装设计常态，归封装库管——本规则不判断封装库该怎么画。
* **相切**：``pad_ink_overlap`` 的每一次比较都是严格的，墨边正好碰到铜边是 ``False``。
* **跨面**：顶层丝印（面 1）只与顶层铜比，底层丝印（面 2）只与底层铜比——墨在另一面
  的焊盘上方过一遍不是压墨。

**器件身份**（与 038Y2 同一套三档，直接消费 ``overlap._identity``，不复制）：

1. 位号非空 → 身份是位号；
2. 位号为空 → 身份是**封装实例** ``component_id``（无位号的两个不同封装仍是两个器件）；
3. 两者都空 → 焊盘那侧每只焊盘自成一体（宁可多报）；丝印那侧**没有归属**——
   板级图元不是「谁的丝印」，本规则不报（任务书「无归属板级图元均不报」）。

**墨的模型**（只有 ``pad_ink_overlap`` 提供的三种，不新增）：

* 折线 / 线段 → 中心线 + 每段 ``width / 2`` 的圆头端帽；
* **单点圆**（``kind == "circle"``，一个点 + ``radius``）→ 半径 ``radius + width / 2``
  的**圆盘**（描边的内环不从盘里扣，这是本批的口径，见下「近似披露」）；
* **单环 ``filled``** → 环内整片是墨，边框照样带 ``width / 2``；环自动闭合，
  少于三点或共线围不出面积。**多环 / 镂空 / fillStyle 不支持**，本批不改 parser。

``closed`` 只按几何事实补末边：``kind in {poly, fill, rect}``、``filled``、或首尾点
重合（``1e-9`` mil 是「同一个点」的浮点门槛，不是几何容差）。

**近似披露不能静默**。parser 给的是**弦化**后的点列（``arc_count`` 数出多少段 ARC
被折成弦）和**圆角矩形的四个尖角**（``radius`` 有值但点仍是外接角）——两者都不是
解析圆弧：**弦化的偏差方向不是单向的**——弦的端点就是真实顶点，弦本身落在弧的内侧，
但那条弦相对焊盘铜面是少报还是多报，取决于弧的转向（凸弧 / 凹弧）、图元把墨画在弧的
哪一侧、以及描边内 / 外侧与铜的关系，不能一概写成「必然少报」；圆角矩形量的是四个
**外接**尖角，角上是**多报**墨（墨在尖角内侧）。本板上
凡**丝印层、有归属**的图元带这两样之一，本规则每板至多聚合**一条 INFO**，列出涉及
器件并写明「弦化 / 角点近似，非解析圆弧」——**不论它离别人的焊盘远近**，因为本规则
的**沉默**（这一对没报、这块板 0 条 WARN）同样建立在这套弦化读数上，不披露就等于
宣称全图元精确。它**不是** WARN，不计实际压铜。单点圆同理按 ``radius + width / 2``
的圆盘量（内环未扣），在命中的 evidence 里逐条注明模型，不冒充读数。

**聚合与 target**。按（丝印器件、焊盘器件）聚一条 **WARN**，每只受影响焊盘一行
evidence（引脚、位置、形状、尺寸、角度、网名，以及命中的图元 id / kind / 层）。

* ``component_ref`` 点名**焊盘那一侧**的器件（受影响的器件），``pin_refs`` 是它的
  受影响引脚、``net_refs`` 是这些焊盘的网名——与 038Y2 同一条约定：``pin_refs`` 只放
  ``component_ref`` 那一侧的引脚。丝印那一侧（要挪的墨）由 ``counterpart_ref`` 点名。
* ``primitive_id`` **留空**：``PadGeometry.id`` / ``SilkShape.id`` 都是**封装模板**的
  图元 id（同一封装的所有实例都叫 ``1`` / ``2`` …），既跨实例重复也不是画布上的 live
  id；空 = 离线无法解析 live id。图元 id 只写进 evidence 给读报告的人看。

**代价**。一块板有几千只焊盘和几千个丝印图元，所以先用 200 mil 的粗格把焊盘按
**位置**索引（面不进格键：焊盘算哪面铜由谓词自己读，粗筛不复述那份判读），再用墨迹
的 **bbox**（点列外接框外扩 ``width / 2``，单点圆即圆心 ± ``radius +
width / 2``）取候选：bbox 不交 ⇒ 墨与铜必不交（铜面永远在 ``pad_corners`` 框内），
粗筛只用来排除，从不参与结论。``_SCREEN_EPS``（1e-9 mil）与 ``core.measure`` 的
``_OVERLAP_EPS`` 同值同义：框正好接触不是正面积。
"""

from __future__ import annotations

from ...core.geometry import Point
from ...core.measure import pad_corners, pad_ink_overlap
from ..base import Finding, FindingTarget
from .base import PcbReviewContext, PcbRule
from .overlap import _identity as _pad_identity
from .silk import FACE_OF_SILK

__all__ = ["SilkOnForeignPad"]

#: 这些 ``SilkShape.kind`` 的折线是闭合环（``line`` 不闭合）。
CLOSED_KINDS = frozenset({"poly", "fill", "rect"})

#: 首尾点距离小于这个值即视为闭合环（mil）。1e-9 是「同一个点」的浮点噪声门槛，
#: 不是几何容差：闭合与否只决定补不补最后一条边。
CLOSED_GAP_MIL = 1e-9

#: 粗筛的接触容差，单位 mil。与 ``core.measure._OVERLAP_EPS`` 同值同义。
_SCREEN_EPS = 1e-9

#: 焊盘粗格边长（mil）：只决定「取哪些候选」，不参与任何判定。
_GRID_MIL = 200.0

#: 焊盘没有网名时 evidence 里写这个，而不是留空（空串读起来像「没读」）。
_NO_NET = "无网"

#: 近似类型的披露字样（INFO 里逐器件点名用）。
_CHORD_APPROX = "圆弧按端点弦化（非解析圆弧）"
_CORNER_APPROX = "圆角矩形按外接角点（非解析圆角）"

#: 墨迹类型的模型说明，写进每只命中焊盘的 evidence。
_MODEL_NOTE = {
    "stroke": "折线/线段按中心线 ± width/2 圆头端帽",
    "disc": "单点圆按 radius + width/2 的圆盘（描边内环未扣）",
    "fill": "单环 filled 按整片为墨，边框同样带 width/2",
}


def _silk_identity(shape, index: int) -> tuple[str, str] | None:
    """The device a silk primitive belongs to, or ``None`` for a board-level one.

    Two fall-through steps, the same two :func:`_.overlap._identity` uses for a
    pad: designator when there is one, then the footprint instance
    ``component_id``. The third step is **deliberately absent**: a primitive
    with neither is not an unnamed part's artwork but board-level annotation,
    and 「谁的丝印压了谁的焊盘」 has no answer for it (任务书: 无归属板级图元均不报).
    """
    designator = str(getattr(shape, "component", None) or "")
    if designator:
        return ("designator", designator)
    component_id = str(getattr(shape, "component_id", None) or "")
    if component_id:
        return ("component", component_id)
    return None


def _silk_label(shape) -> str:
    """``U1`` / ``（无位号封装 7c1a…）`` — the device as a reader names it."""
    designator = str(getattr(shape, "component", None) or "")
    if designator:
        return designator
    return f"（无位号封装 {getattr(shape, 'component_id', '') or ''}）"


def _pad_device_label(pad) -> str:
    """``U6`` / ``（无位号封装 7c1a…）`` — the pad's device as a reader names it."""
    designator = pad.component or ""
    if designator:
        return designator
    component_id = str(getattr(pad, "component_id", None) or "")
    return f"（无位号封装 {component_id}）" if component_id else "（无位号）"


def _pad_label(pad) -> str:
    """``U6.1`` / ``（无位号封装 7c1a…）.1`` — the pad as a reader names it."""
    return f"{_pad_device_label(pad)}.{pad.pin_number or pad.id}"


def _ink(shape) -> tuple[list[Point], float, bool, bool, str] | None:
    """The ink as ``(points, half_width, filled, closed, model)``, or ``None``.

    ``None`` means **this primitive carries no ink area at all**: no points, or a
    zero-width stroke on fewer than three points (a stroke of zero width has no
    area, so it is not something that can lie on copper).
    """
    points = [Point(float(p.x), float(p.y)) for p in (getattr(shape, "points", None) or [])]
    if not points:
        return None
    half = float(getattr(shape, "width", 0.0) or 0.0) / 2.0
    if half < 0.0:
        half = 0.0
    if len(points) == 1:
        radius = getattr(shape, "radius", None)
        if radius is not None:
            half += float(radius)
        if half <= 0.0:
            return None
        return points, half, False, False, "disc"
    filled = bool(getattr(shape, "filled", False)) and len(points) >= 3
    if half <= 0.0 and not filled:
        return None
    first, last = points[0], points[-1]
    closed = (
        filled
        or str(getattr(shape, "kind", "") or "") in CLOSED_KINDS
        or (
            abs(first.x - last.x) <= CLOSED_GAP_MIL
            and abs(first.y - last.y) <= CLOSED_GAP_MIL
        )
    )
    return points, half, filled, closed, "fill" if filled else "stroke"


def _ink_box(points: list[Point], half: float) -> tuple[float, float, float, float]:
    """The ink's bounding box, ``(x_min, y_min, x_max, y_max)`` in mils.

    Every point of the ink (the centreline, the interior of a ring, the stroke's
    round cap and the single-point disc) lies inside this box, so 「boxes do not
    meet」 is a safe 「ink does not meet copper」. The converse is never assumed —
    a pad's own box is the filter's other half and the predicate decides.
    """
    xs = [point.x for point in points]
    ys = [point.y for point in points]
    return (min(xs) - half, min(ys) - half, max(xs) + half, max(ys) + half)


def _pad_box(pad) -> tuple[float, float, float, float]:
    """The pad's :func:`~boardwise.core.measure.pad_corners` box — a screen only."""
    corners = pad_corners(pad)
    return (
        min(point.x for point in corners),
        min(point.y for point in corners),
        max(point.x for point in corners),
        max(point.y for point in corners),
    )


def _cells(box: tuple[float, float, float, float]):
    """The grid cells a box touches, as ``(ix, iy)`` pairs (``_GRID_MIL`` cells)."""
    x0 = int((box[0] - _SCREEN_EPS) // _GRID_MIL)
    x1 = int((box[2] + _SCREEN_EPS) // _GRID_MIL)
    y0 = int((box[1] - _SCREEN_EPS) // _GRID_MIL)
    y1 = int((box[3] + _SCREEN_EPS) // _GRID_MIL)
    return [(ix, iy) for ix in range(x0, x1 + 1) for iy in range(y0, y1 + 1)]


def _overlaps(
    box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]
) -> bool:
    """Positive-area box intersection (touching is not overlap)."""
    return (
        min(box_a[2], box_b[2]) - max(box_a[0], box_b[0]) > _SCREEN_EPS
        and min(box_a[3], box_b[3]) - max(box_a[1], box_b[1]) > _SCREEN_EPS
    )


def _approximation(shape) -> str | None:
    """How this primitive's ink had to be approximated, or ``None`` when exact.

    ``arc_count > 0`` — the parser kept the ARC endpoints and dropped the sweep,
    so the printed shape bulges outside the chords that were measured.
    ``radius`` on a multi-point primitive — a rounded rectangle, read through its
    four sharp corners (the ink is inside them, so the ear is over-reported).
    A single-point ``CIRCLE`` is *not* listed here: it is the disc the primitive
    is (``radius + width / 2``), and its inner ring is disclosed per hit instead.
    """
    try:
        arcs = int(getattr(shape, "arc_count", 0) or 0)
    except (TypeError, ValueError):
        arcs = 0
    if arcs > 0:
        return _CHORD_APPROX
    points = getattr(shape, "points", None) or []
    if getattr(shape, "radius", None) is not None and len(points) > 1:
        return _CORNER_APPROX
    return None


def _primitive(shape, model: str, approximation: str | None) -> str:
    """``#c12（poly，TOP_SILK，圆弧按端点弦化…）`` — one hit primitive, named."""
    name = str(getattr(shape, "id", "") or "（无图元 id）")
    kind = str(getattr(shape, "kind", "") or "（无 kind）")
    layer_kind = str(getattr(shape, "layer_kind", "") or "（无层）")
    parts = [f"#{name}", kind, layer_kind, _MODEL_NOTE[model]]
    if approximation is not None:
        parts.append(approximation)
    return "（" + "，".join(parts) + "）"


def _describe(pad) -> str:
    """Position, shape, extents, angle and net of one hit pad — **no depth**."""
    net = pad.net or _NO_NET
    return (
        f"{_pad_label(pad)} 「{net}」 {pad.shape or '（无形状）'} "
        f"{pad.width:g}×{pad.height:g} mil @ ({pad.x:g}, {pad.y:g}) mil, "
        f"角度 {pad.angle:g}°"
    )


class SilkOnForeignPad(PcbRule):
    """One part's silk ink lying on **another** part's pad copper.

    WARN with no tolerance of its own: the only length in the judgement is
    :func:`~boardwise.core.measure.pad_ink_overlap`'s ``1e-9`` mil float-noise
    floor. A fabrication allowance for 「丝印印在别人焊盘上」 does not exist — any
    positive area already costs solderability — but it is a readability /
    assembly **cost**, not an electrical defect, so it grades WARN like the rest
    of the silk family (``pcb-silk-designator``, ``pcb-silk-under-body``).
    """

    id = "pcb-silk-on-foreign-pad"
    title = "Silkscreen does not sit on another component's pads"
    level = "L1-pcb-geometry"
    source = (
        "house rule（038Y3B 规则合同：异器件、同面、真实墨迹与真实铜面正面积相交即 WARN；"
        "同器件/相切/跨面/无归属板级图元不报）；墨与铜的唯一判定来源 "
        "core.measure.pad_ink_overlap（038Y3A），无阈值，不写深度与面积"
    )

    # -- the pass ---------------------------------------------------------

    def check(self, ctx: PcbReviewContext) -> list[Finding]:
        board = ctx.board
        pads = list(getattr(board, "pads", None) or [])
        shapes = list(getattr(board, "silk_shapes", None) or [])
        if not pads or not shapes:
            return []

        grid: dict[tuple[int, int], list[int]] = {}
        pad_boxes: list[tuple[float, float, float, float]] = []
        pad_ids: list[tuple[str, str]] = []
        for index, pad in enumerate(pads):
            box = _pad_box(pad)
            pad_boxes.append(box)
            pad_ids.append(_pad_identity(pad, index))
            # 格只按**位置**索引，面不进格键：焊盘的面由 ``pad_ink_overlap`` 自己
            # 读（``core.measure._pad_copper_layers`` 是它的私货），粗筛不复述那份
            # 判读，否则「哪面算铜」就出现了第二个说法。
            for cell in _cells(box):
                grid.setdefault(cell, []).append(index)

        #: ``(丝印身份, 焊盘身份) -> {焊盘: {命中图元}}``
        groups: dict[tuple, dict] = {}
        #: 丝印器件 -> {近似类型}（本板上带圆弧/圆角的丝印图元都登记，见模块 doc）
        approximated: dict[tuple[str, str], dict[str, str]] = {}

        for shape_index, shape in enumerate(shapes):
            face = FACE_OF_SILK.get(str(getattr(shape, "layer_kind", "") or ""))
            if face is None:
                continue
            silk_identity = _silk_identity(shape, shape_index)
            if silk_identity is None:
                continue
            ink = _ink(shape)
            if ink is None:
                continue
            points, half, filled, closed, model = ink
            box = _ink_box(points, half)
            approximation = _approximation(shape)
            if approximation is not None:
                # 登记在粗筛之前：本规则的**沉默**（这一对没报）也建立在这套弦化 /
                # 角点读数上，只有披露它才不算宣称精确（见模块 doc「近似披露」）。
                approximated.setdefault(silk_identity, {})[approximation] = _silk_label(shape)

            candidates: set[int] = set()
            for cell in _cells(box):
                candidates.update(grid.get(cell, ()))

            for pad_index in sorted(candidates):
                if not _overlaps(box, pad_boxes[pad_index]):
                    continue
                if silk_identity == pad_ids[pad_index]:
                    continue
                pad = pads[pad_index]
                if not pad_ink_overlap(
                    board,
                    pad,
                    points=points,
                    half_width=half,
                    layers={face},
                    filled=filled,
                    closed=closed,
                ):
                    continue
                group = groups.setdefault((silk_identity, pad_ids[pad_index]), {})
                group.setdefault(pad_index, set()).add(
                    _primitive(shape, model, approximation)
                )

        findings: list[Finding] = []
        ordered = sorted(
            groups.items(),
            key=lambda item: (
                item[0][0][1],
                item[0][1][1],
                min(item[1]),
            ),
        )
        for (silk_identity, _pad_identity_value), hits in ordered:
            findings.append(self._warn(ctx, pads, silk_identity, hits))
        if approximated:
            findings.append(self._approximation_note(ctx, approximated))
        return findings

    # -- the two findings -------------------------------------------------

    def _warn(self, ctx, pads, silk_identity, hits) -> Finding:
        """One WARN for the pair, one evidence line per affected pad."""
        pad_indexes = sorted(hits)
        first = pads[pad_indexes[0]]
        silk_label = _silk_label(_ShapeRef(silk_identity))
        evidence = [f"器件对：{silk_label} 的丝印 × {_pad_device_label(first)} 的焊盘"]
        for pad_index in pad_indexes:
            pad = pads[pad_index]
            primitives = "；".join(sorted(hits[pad_index]))
            evidence.append(f"{_describe(pad)} ← 命中图元 {primitives}")
        nets = sorted({pads[index].net for index in pad_indexes if pads[index].net})
        pins = sorted(
            {pads[index].pin_number for index in pad_indexes if pads[index].pin_number}
        )
        evidence.append(
            "判定：pad_ink_overlap（038Y3A）为真——墨迹与焊盘**真实铜面**（圆盘 / 跑道 / "
            "旋转矩形 / 038V 的 32 边形）在该面有正面积交集；相切、跨面、同器件都不是。"
            "本规则不计算深度、不计算面积：描边半宽与填充深度是不同的量，写成一个数就是编造"
        )
        evidence.append(
            "框只做粗筛：pad_corners 的外接框与墨迹 bbox 不交才排除候选，"
            "圆盘外接框的耳朵（框内、盘外）不会因为落进框里就被判成压上"
        )
        return Finding(
            rule_id=self.id,
            severity="WARN",
            level=self.level,
            message=(
                f"丝印压在别的器件的焊盘上：{silk_label} 的丝印墨迹压到 "
                f"{_pad_device_label(first)} 的 {len(pad_indexes)} 只焊盘"
                f"（{_pad_label(first)} 等）——丝印盖在可焊面积上，回流时阻焊、"
                "装配后焊料也盖不全"
            ),
            evidence=evidence,
            target=FindingTarget(
                # 焊盘那一侧：受影响的器件与它的引脚/网，与 038Y2 同一约定
                # （pin_refs 只放 component_ref 那一侧的引脚）。
                component_ref=first.component or "",
                counterpart_ref=silk_label if silk_identity[0] == "designator" else "",
                # 空 = 离线拿不到画布 live id；模板图元 id（1 / 2 …）跨实例重复。
                primitive_id="",
                pin_refs=pins,
                net_refs=nets,
            ),
        )

    def _approximation_note(self, ctx, approximated) -> Finding:
        """At most one INFO per board: chord / corner readings, not real arcs."""
        rows = []
        for (kind, value), reasons in sorted(
            approximated.items(), key=lambda item: item[0][1]
        ):
            label = value if kind == "designator" else f"（无位号封装 {value}）"
            rows.append(f"{label}：{'、'.join(sorted(reasons))}")
        return Finding(
            rule_id=self.id,
            severity="INFO",
            level=self.level,
            message=(
                f"{len(rows)} 个器件的丝印含圆弧或圆角，本规则只能按 parser 的"
                "弦化 / 角点近似测量（**非解析圆弧**）——这条是范围披露，不是压铜读数"
            ),
            evidence=rows
            + [
                "圆弧：parser 保留 ARC 端点、丢掉扫角，量的是端点之间的弦——弦化相对"
                "焊盘铜面的偏差方向取决于弧的转向（凸 / 凹）、图元把墨画在弧的哪一侧、"
                "以及描边内 / 外侧与铜的关系，**不能一概说是少报**；圆角矩形：parser 给的"
                "是四个外接尖角，角上多报墨。任何一条都不许被读成「全图元精确」",
                "单点圆（pin-1 点）另按 radius + width/2 的圆盘量，描边内环未从盘中扣；"
                "多环 / 镂空填充与 fillStyle 仍不支持，本批不改 parser——"
                "两个既有归档的多环 FILL=0 只是这两块板的局部证据，不是全称结论",
                "每板至多这一条 INFO：它不升级为 WARN，不计入本规则的实际压铜条数，"
                "也不改变任何一条 WARN 的判定",
            ],
        )


class _ShapeRef:
    """A device identity dressed as the minimal shape ``_silk_label`` reads.

    The aggregation happens on identities (no shape survives the loop), so the
    label is rebuilt from the identity alone; this keeps the pair's message
    wording identical to the per-shape one.
    """

    def __init__(self, identity: tuple[str, str]):
        kind, value = identity
        self.component = value if kind == "designator" else ""
        self.component_id = value if kind != "designator" else ""
