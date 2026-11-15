"""不同器件的焊盘铜面重叠 — ``pcb-pad-overlap`` (038Y2).

预研包 ``.tmp_pcb_review_20261115`` 证明了「同网焊盘正面积重叠」会绕过既有间距规则，
但它把 :func:`~boardwise.core.measure.pad_corners` 的**外接矩形**当铜面，于是两块
Ø98.425 mil 圆盘对角 70 / 70 mil、真实间隙 0.569949 mil 的一对读成 ERROR。本规则消费
038Y1 的 :func:`~boardwise.core.measure.pad_copper_overlap` 作**唯一最终判定**：
``pad_corners`` 的框只用来做安全的粗筛（框不交 ⇒ 铜面必不交），从不参与结论。

**判定**。同一 :class:`~boardwise.core.geometry.BoardGeometry` 内，两块**不同器件**的
焊盘只要在共享铜层有正面积交集就是 ERROR：

* **同网不豁免**（岳裁：仍报 ERROR）。两块焊盘压在同一块铜上的物理理由是**器件/封装
  装配冲突**——两个器件的封装在同一块铜上互相压占——不是一次「连接」。既有间距规则
  （``pcb-voltage-spacing``）按电位成对比较，同网对根本不在它的题目里；本规则不问网，
  只问铜面是否真的互穿。**异网**重叠在此之上还是一次**直接短路**。
* **空网不豁免**（``net`` 为 ``None`` / ``""``：没有网名不等于没有铜，也不等于同网）。
* **相切不报**：零面积交集不是重叠，正是 ``pad_copper_overlap`` 的严格比较。
* **跨层不报**：两层铜在同一个 ``(x, y)`` 上不是一次碰撞，层读数是 ``pad_copper_overlap``
  的输入。
* **同一器件内部不报**：同一个封装的焊盘本来就是一块铜的若干焊盘（一个焊盘压到隔壁焊盘
  是封装库的事，不是布局的重叠）。器件身份见 :func:`_identity`。

**器件身份**（任务书「两个空 designator 不得因此被误认为同器件」）：

1. 位号非空 → 身份是位号本身（``U1`` 的焊盘与 ``U1`` 的焊盘是同器件）；
2. 位号为空 → 身份是**封装实例** ``component_id``（文件里给的那个 uuid，两个没有位号的
   不同封装因此仍是两个器件）；
3. 位号与 ``component_id`` 都空 → 每个焊盘自成一体（手搭的、无法命名的焊盘），宁可
   多报也不把两块无主铜当成一个器件。

**输出与 target 语义**。每个**无序**焊盘对一条 Finding，两侧按 :func:`_sort_key` 排序后
determinism 地定成 ``component_ref`` / ``counterpart_ref``（双向：两边器件都点名），
evidence 给两块焊盘的位置、形状、尺寸、角度、网名，**不写面积**——本规则不计算面积，
写一个数就是编造（预研包的 ``pad_overlap_area()`` 是外接矩形面积，不移植）。

target 的三个字段各有各的边界，混装就是错：

* ``primitive_id`` **留空**。:attr:`~boardwise.core.geometry.PadGeometry.id` 是**封装模板**
  的焊盘 id（同一封装的所有实例都叫 ``1`` / ``2`` …），它既不是画布上的 live 图元 id，
  也会跨实例重复；``FindingTarget`` 的合同是「空 = 离线无法解析画布 live id」，
  所以离线规则一律不填。
* ``pin_refs`` 只放 **``component_ref`` 那一侧**焊盘的 ``pin_number``（没有引脚号就留空
  列表）。它是 *那个器件* 的引脚，不是这一对的两个引脚。
* 对方的引脚由 evidence 表达（``counterpart_ref`` 只点名器件），不塞进 ``pin_refs``。

**代价**。一块板有几千个焊盘，直接 ``O(n²)`` 次几何调用在真实工程上不可接受，所以先按
:func:`~boardwise.core.measure.pad_corners` 的框沿 x 排序扫描：只对框在 x 与 y 上都有
正长度交集的对调用 ``pad_copper_overlap``。粗筛与判定用的是同一把尺子（mils，1e-9 的
接触容差），所以「相切」在粗筛里也不会被当成重叠。
"""

from __future__ import annotations

from ...core.measure import pad_corners, pad_copper_overlap
from ..base import Finding, FindingTarget
from .base import PcbReviewContext, PcbRule

#: 粗筛的接触容差，单位 mil。与 ``core.measure`` 的 ``_OVERLAP_EPS`` 同值同义：
#: 框之间正好接触（差 0）不是正面积，``hypot`` / 三角运算的浮点噪声不改变这个事实。
_SCREEN_EPS = 1e-9

#: 焊盘没有网名时 evidence 里写这个，而不是留空（空串读起来像「没读」）。
_NO_NET = "无网"


def _identity(pad, index: int) -> tuple[str, str]:
    """The device a pad belongs to, in three falls-through steps.

    ``("designator", "U1")`` for a named part; ``("component", <uuid>)`` for an
    unnamed footprint that still has an instance identity; ``("pad", "#<n>:<id>")``
    for a pad with neither — the third case is deliberately **per pad**, so two
    nameless pads are never read as one device (see the module docstring).
    """
    designator = pad.component or ""
    if designator:
        return ("designator", designator)
    component_id = getattr(pad, "component_id", None) or ""
    if component_id:
        return ("component", component_id)
    return ("pad", f"#{index}:{pad.id}")


def _sort_key(pad, index: int) -> tuple[str, str, int]:
    """Deterministic order for one side of a pair (designator, pin/id, board index)."""
    return (pad.component or "", pad.pin_number or pad.id or "", index)


def _box(pad) -> tuple[float, float, float, float]:
    """The pad's :func:`pad_corners` box, ``(x_min, y_min, x_max, y_max)`` in mils.

    Only a **screen**: the box contains the copper of every shape
    :func:`~boardwise.core.measure.pad_copper_overlap` knows (a rotated
    rectangle *is* its corners, a disc / stadium / circumscribing 32-gon sits
    inside the rectangle of its extents), so 「boxes do not meet」 is a safe
    「copper does not meet」, and the converse is never assumed.
    """
    corners = pad_corners(pad)
    return (
        min(point.x for point in corners),
        min(point.y for point in corners),
        max(point.x for point in corners),
        max(point.y for point in corners),
    )


def _shared_layers(pad_a, pad_b) -> list[int]:
    """Copper layers both pads are read onto, sorted; empty when not nameable.

    Read through :meth:`PadGeometry.effective_layers`, which collapses ``None``
    （没人读过这块焊盘）and ``[]``（读成「没有铜层」）to the empty set. That is
    the honest answer for evidence: the rule does not re-derive a layer it was
    not given, and the predicate it delegates to is the one that decided.
    """
    return sorted(pad_a.effective_layers() & pad_b.effective_layers())


def _label(pad) -> str:
    """``U1.1`` / ``（无位号）.3`` — the pad as a reader names it."""
    designator = pad.component or "（无位号）"
    pin = pad.pin_number or pad.id
    return f"{designator}.{pin}"


def _describe(pad) -> str:
    """Position, shape, extents, angle and net of one pad — **no area**."""
    net = pad.net or _NO_NET
    return (
        f"{_label(pad)} 「{net}」 {pad.shape or '（无形状）'} "
        f"{pad.width:g}×{pad.height:g} mil @ ({pad.x:g}, {pad.y:g}) mil, "
        f"角度 {pad.angle:g}°"
    )


def _reason(pad_a, pad_b) -> str:
    """Why a positive-area overlap of two *different* devices is an ERROR.

    Two named, **different** nets: the two pieces of copper are two potentials, so
    the overlap is a **direct short**. Everything else — the same named net, or a
    pad with no net name at all — is still a **device / footprint assembly
    conflict**: two packages occupy the same copper, which is not a connection
    and which the net never justifies (岳裁: 同网不豁免, still ERROR).
    """
    net_a, net_b = pad_a.net or "", pad_b.net or ""
    if net_a and net_b and net_a != net_b:
        return f"两个不同电位（{net_a} / {net_b}）的铜压在一起，这是一次直接短路"
    if net_a and net_b:
        return (
            f"两块焊盘同名网（{net_a}）压在一起：器件/封装装配冲突（两个封装压占同一块铜），"
            f"不是一次连接；若换成异网，这里还会直接短路"
        )
    return "至少一侧没有网名，两块铜压在一起是器件/封装装配冲突；异网重叠还会直接短路"


class PadOverlap(PcbRule):
    """Two pads of **different** parts whose copper meets on a shared layer.

    ERROR with no tolerance of its own: the only length in the judgement is
    :func:`pad_copper_overlap`'s ``1e-9`` mil float-noise floor, and this rule
    quotes no threshold because a fabrication allowance for 「两块铜压在一起」
    does not exist — any positive area is already a placement / footprint defect.
    """

    id = "pcb-pad-overlap"
    title = "No two pads share the same copper"
    level = "L1-pcb-geometry"
    source = (
        "house rule（038Y2 规则合同：不同器件、同层、正面积铜面重叠即 ERROR，"
        "同网/异网/空网均不豁免，相切不报）；几何判定唯一来源 "
        "core.measure.pad_copper_overlap（038Y1），无阈值"
    )

    def _finding(self, pad_a, pad_b) -> Finding:

        shared = _shared_layers(pad_a, pad_b)
        layer_text = (
            "、".join(str(layer) for layer in shared) if shared else "不可命名（焊盘未读层）"
        )
        return Finding(
            rule_id=self.id,
            severity="ERROR",
            level=self.level,
            message=(
                f"不同器件的两块焊盘在同一铜层上正面积重叠：{_label(pad_a)} × {_label(pad_b)}"
                f"（层 {layer_text}）——{_reason(pad_a, pad_b)}"
            ),
            evidence=[
                _describe(pad_a),
                _describe(pad_b),
                f"共享铜层：{layer_text}",
                (
                    "判定：pad_copper_overlap 为真（层相交且铜面正面积互穿；"
                    "相切、跨层、无铜层都不是；本规则不计算面积，故不写面积）"
                ),
            ],
            target=FindingTarget(
                component_ref=pad_a.component or "",
                counterpart_ref=pad_b.component or "",
                # 空 = 离线规则拿不到画布 live id；PadGeometry.id 是封装模板 id，跨实例
                # 重复，不是 live id（见模块 doc「输出与 target 语义」）。
                primitive_id="",
                # 只放 component_ref 那一侧的引脚；对方引脚由 evidence 表达。
                pin_refs=[pad_a.pin_number] if pad_a.pin_number else [],
                net_refs=sorted({pad.net for pad in (pad_a, pad_b) if pad.net}),
            ),
        )

    def check(self, ctx: PcbReviewContext) -> list[Finding]:
        board = ctx.board
        pads = list(getattr(board, "pads", None) or [])
        if len(pads) < 2:
            return []
        entries = [(_box(pad), index, pad) for index, pad in enumerate(pads)]
        entries.sort(key=lambda entry: (entry[0][0], entry[1]))
        pairs: list[tuple[tuple[str, str, int], tuple[str, str, int], Finding]] = []
        for position, (box_a, index_a, pad_a) in enumerate(entries):
            for box_b, index_b, pad_b in entries[position + 1 :]:
                if box_b[0] - box_a[2] > _SCREEN_EPS:
                    # Sorted by x_min: every later box starts here or further right.
                    break
                if min(box_a[3], box_b[3]) - max(box_a[1], box_b[1]) <= _SCREEN_EPS:
                    continue
                if _identity(pad_a, index_a) == _identity(pad_b, index_b):
                    continue
                if not pad_copper_overlap(board, pad_a, pad_b):
                    continue
                first, second = (pad_a, index_a), (pad_b, index_b)
                if _sort_key(*second) < _sort_key(*first):
                    first, second = second, first
                pairs.append(
                    (
                        _sort_key(*first),
                        _sort_key(*second),
                        self._finding(first[0], second[0]),
                    )
                )
        pairs.sort(key=lambda pair: (pair[0], pair[1]))
        return [finding for _, _, finding in pairs]
