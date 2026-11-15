"""Tests for task 038Y2: ``pcb-pad-overlap`` — 不同器件的焊盘铜面正面积重叠.

The rule is a thin consumer of 038Y1's
:func:`boardwise.core.measure.pad_copper_overlap`; every case below is either the
pre-study package's counterexample (two Ø98.425 mil discs 70 / 70 mil apart
diagonally, 0.569949 mil of real air between their edges, whose *boxes*
interpenetrate by more than 28 mil on each axis) or one of the task book's
controls. Two things are asserted that a 「rule returns one finding」 test would
miss:

* the coarse screen must not be the judge — the disc case asserts that the
  bounding boxes **do** meet (so ``pad_copper_overlap`` is what refuses), and the
  45°-rotated-rectangle case asserts the same for a box false-intersection that
  the copper does not have;
* the evidence must not carry an area the rule never computed.
"""

from __future__ import annotations

from boardwise.core.geometry import (
    BoardGeometry,
    ComponentPlacement,
    LayerInfo,
    PadGeometry,
    StackupEntry,
)
from boardwise.core.measure import pad_corners, pad_copper_overlap
from boardwise.engines import pcbreview
from boardwise.rules.pcb.base import PcbReviewContext, PcbRule
from boardwise.rules.pcb.overlap import PadOverlap

#: The counterexample's disc: Ø98.425 mil (038Y1's primary regression).
DISC = 98.425


def _pad(
    id: str,
    *,
    component: str | None = None,
    component_id: str | None = None,
    pin: str | None = None,
    net: str | None = None,
    layer_id: int | None = 1,
    x: float = 0.0,
    y: float = 0.0,
    width: float = 0.0,
    height: float = 0.0,
    shape: str = "RECT",
    angle: float = 0.0,
    effective_layers: list[int] | None = None,
) -> PadGeometry:
    """One hand-built pad; ``effective_layers`` stays ``None`` unless a test is
    pinning the parser's own reading (``[]`` = 「no copper layer」)."""
    return PadGeometry(
        id=id,
        component=component,
        component_id=component_id,
        pin_number=pin,
        net=net,
        footprint_layer_id=layer_id,
        x=x,
        y=y,
        width=width,
        height=height,
        shape=shape,
        angle=angle,
        effective_layer_ids=effective_layers,
    )


def _board(*pads: PadGeometry, components: list[ComponentPlacement] | None = None) -> BoardGeometry:
    """The same hand-built two-layer board 038Y1's tests pin."""
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


def _ctx(board: BoardGeometry, title: str = "PCB1") -> PcbReviewContext:
    return PcbReviewContext(board=board, board_title=title)


def _run(*pads: PadGeometry, board: BoardGeometry | None = None):
    return PadOverlap().check(_ctx(board if board is not None else _board(*pads)))


def _box(pad: PadGeometry) -> tuple[float, float, float, float]:
    corners = pad_corners(pad)
    return (
        min(p.x for p in corners),
        min(p.y for p in corners),
        max(p.x for p in corners),
        max(p.y for p in corners),
    )


def _boxes_meet(a: PadGeometry, b: PadGeometry) -> bool:
    ax0, ay0, ax1, ay1 = _box(a)
    bx0, by0, bx1, by1 = _box(b)
    return min(ax1, bx1) - max(ax0, bx0) > 0 and min(ay1, by1) - max(ay0, by0) > 0


def _disc(id: str, x: float, y: float, *, component: str = "D1", **kwargs) -> PadGeometry:
    return _pad(
        id, x=x, y=y, width=DISC, height=DISC, shape="ELLIPSE",
        component=component, **kwargs,
    )


# ---------------------------------------------------------------------------
# the counterexample: the pre-study rule's ERROR was a box artefact
# ---------------------------------------------------------------------------


def test_diagonal_discs_with_0_569949_of_air_are_not_reported():
    """038Y1 §1 / 预研包 refutation: boxes meet, copper does not.

    Ø98.425 discs at ``(0, 0)`` and ``(70, 70)``: centre distance
    ``70·sqrt(2)`` = 98.994949…, edge gap = 98.994949… − 98.425 = **0.569949 mil**.
    The boxes interpenetrate by ``98.425 − 70`` = 28.425 mil on each axis, so
    this pair must reach the predicate rather than be screened away.
    """
    a, b = _disc("A", 0, 0, component="D1"), _disc("B", 70, 70, component="D2")
    assert _boxes_meet(a, b), "粗筛放行——本用例要证明的是判定不是粗筛"
    assert not pad_copper_overlap(_board(a, b), a, b)
    assert _run(a, b) == []


def test_45_degree_rectangles_have_intersecting_boxes_and_no_overlap():
    """A rotated rectangle's box is not its copper.

    Two 200 × 20 mil rectangles at 45°, centres 40 mil apart along y. Both lie
    along ``(1, 1)/√2``, so the perpendicular distance between their centre
    lines is ``40/√2`` = 28.284 mil and the copper gap is that minus the two
    half-widths: 8.284 mil of air. Each box spans ±(100·cos45 + 10·sin45) =
    ±77.782 mil on both axes, so the boxes still overlap by 115.56 mil in y.
    """
    a = _pad("A", component="U1", width=200, height=20, angle=45)
    b = _pad("B", component="U2", width=200, height=20, angle=45, y=40)
    assert _boxes_meet(a, b), "粗筛放行，结论必须由铜面给出"
    assert not pad_copper_overlap(_board(a, b), a, b)
    assert _run(a, b) == []


# ---------------------------------------------------------------------------
# the rule contract: net does not exempt, same device does
# ---------------------------------------------------------------------------


def test_same_net_overlap_is_an_error():
    """同网不豁免: two GND pads pressed together are a short, not a connection.

    ``pcb-voltage-spacing`` never asks this question — it pairs *potentials* —
    which is exactly the hole the pre-study found.
    """
    a = _pad("A", component="R1", pin="1", net="GND", width=100, height=60)
    b = _pad("B", component="R2", pin="1", net="GND", width=100, height=60, x=50)
    assert pad_copper_overlap(_board(a, b), a, b)
    findings = _run(a, b)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "pcb-pad-overlap"
    assert finding.severity == "ERROR"
    assert finding.level == "L1-pcb-geometry"
    assert finding.target.component_ref == "R1"
    assert finding.target.counterpart_ref == "R2"
    assert finding.target.net_refs == ["GND"]
    # ``primitive_id`` 留空：PadGeometry.id 是**封装模板**的焊盘 id（同一封装的每个实例
    # 都叫 ``1`` / ``2`` …），不是画布 live id，也在实例间重复。
    assert finding.target.primitive_id == ""
    # ``pin_refs`` 只放 component_ref（R1）那一侧的引脚；R2 的引脚在 evidence 里。
    assert finding.target.pin_refs == ["1"]
    assert "R2.1" in finding.evidence[1]
    # 同网不是短路：理由必须是器件/封装装配冲突，ERROR 仍然照报（岳裁）。
    assert "装配冲突" in finding.message and "同名网" in finding.message


def test_different_net_overlap_is_an_error():
    a = _pad("A", component="R1", pin="1", net="+24V", width=100, height=60)
    b = _pad("B", component="R2", pin="1", net="GND", width=100, height=60, x=50)
    findings = _run(a, b)
    assert len(findings) == 1
    assert findings[0].target.net_refs == ["+24V", "GND"]


def test_unnamed_net_is_not_exempt():
    """空网不豁免: no net name is not no copper."""
    a = _pad("A", component="R1", width=100, height=60)
    b = _pad("B", component="R2", width=100, height=60, x=10)
    findings = _run(a, b)
    assert len(findings) == 1
    assert findings[0].target.net_refs == []


def test_tangent_pads_are_not_reported():
    """相切不报: zero-area contact is the predicate's strict comparison.

    Two 100 × 60 rectangles side by side at ``x = 0`` and ``x = 100`` share the
    line ``x = 50`` and no area; the same for two discs one diameter apart.
    """
    rects = (
        _pad("A", component="R1", width=100, height=60),
        _pad("B", component="R2", width=100, height=60, x=100),
    )
    assert not pad_copper_overlap(_board(*rects), *rects)
    assert _run(*rects) == []
    discs = (_disc("A", 0, 0, component="D1"), _disc("B", DISC, 0, component="D2"))
    assert _run(*discs) == []


def test_two_pads_of_one_designator_are_not_reported():
    """同一非空 designator 的封装内部焊盘不报: that is the footprint's business."""
    a = _pad("A", component="U1", pin="1", width=100, height=60)
    b = _pad("B", component="U1", pin="2", width=100, height=60, x=50)
    assert pad_copper_overlap(_board(a, b), a, b)
    assert _run(a, b) == []


def test_two_empty_designators_are_not_one_device():
    """空 designator 不得被误认为同器件 — 两个**不同封装**的无位号焊盘仍要报。

    两块焊盘都没有位号，但 ``component_id`` 不同（两个封装实例）；身份落在第二步，
    所以它们是两个器件。同一个无位号封装的两块焊盘则落在同一个 ``component_id`` 上，
    仍不报（下一条）。
    """
    a = _pad("A", component=None, component_id="fp-1", pin="1", width=100, height=60)
    b = _pad("B", component=None, component_id="fp-2", pin="1", width=100, height=60, x=50)
    assert pad_copper_overlap(_board(a, b), a, b)
    findings = _run(a, b)
    assert len(findings) == 1
    assert findings[0].target.component_ref == ""
    assert findings[0].target.counterpart_ref == ""


def test_one_unnamed_footprint_is_still_one_device():
    """同一个（无位号）封装的两块焊盘：``component_id`` 相同 ⇒ 同器件，不报。"""
    a = _pad("A", component=None, component_id="fp-1", pin="1", width=100, height=60)
    b = _pad("B", component=None, component_id="fp-1", pin="2", width=100, height=60, x=50)
    assert _run(a, b) == []


def test_pads_with_neither_designator_nor_component_id_are_their_own_devices():
    """两个身份都缺：每个焊盘自成一体，宁可多报也不把无主铜当同器件。"""
    a = _pad("A", width=100, height=60)
    b = _pad("B", width=100, height=60, x=50)
    assert len(_run(a, b)) == 1


# ---------------------------------------------------------------------------
# layers, containment, multiplicity
# ---------------------------------------------------------------------------


def test_cross_layer_pads_at_the_same_point_are_not_reported():
    """跨层不报: the same ``(x, y)`` on two faces is not a collision (127b)."""
    top = _pad("A", component="R1", net="A", width=100, height=60, layer_id=1)
    bottom = _pad("B", component="R2", net="B", width=100, height=60, layer_id=2)
    assert not pad_copper_overlap(_board(top, bottom), top, bottom)
    assert _run(top, bottom) == []


def test_through_hole_pad_reaches_a_bottom_pad():
    """通孔到底层: a plated barrel's land exists on both faces (127b reading)."""
    through = _pad(
        "A", component="J1", net="GND", width=100, height=60, effective_layers=[1, 2]
    )
    bottom = _pad(
        "B", component="R2", net="GND", width=100, height=60, layer_id=2, x=50,
        effective_layers=[2],
    )
    findings = _run(through, bottom)
    assert len(findings) == 1
    assert findings[0].evidence[2] == "共享铜层：2"  # 通孔焊盘在两层的铜，与底层焊盘在层 2 相遇


def test_a_top_pad_does_not_reach_the_same_bottom_pad():
    """The through-hole case's negative control: layer 1 only meets nothing on 2."""
    top = _pad("A", component="J1", net="GND", width=100, height=60, effective_layers=[1])
    bottom = _pad("B", component="R2", net="GND", width=100, height=60, layer_id=2, x=50)
    assert _run(top, bottom) == []


def test_full_containment_is_an_overlap():
    """完全包含: a small pad wholly inside a big one overlaps in either direction."""
    big = _pad("A", component="U1", width=200, height=200)
    small = _pad("B", component="U2", width=50, height=50, x=10, y=10)
    assert pad_copper_overlap(_board(big, small), big, small)
    assert pad_copper_overlap(_board(big, small), small, big)
    assert len(_run(big, small)) == 1


def test_one_finding_per_unordered_pair():
    """每个**无序**焊盘对一条: three mutually overlapping pads ⇒ exactly three."""
    pads = [
        _pad("A", component="R1", width=100, height=100),
        _pad("B", component="R2", width=100, height=100, x=20),
        _pad("C", component="R3", width=100, height=100, x=0, y=20),
    ]
    findings = _run(*pads)
    assert len(findings) == 3
    pairs = {
        tuple(sorted((f.target.component_ref, f.target.counterpart_ref))) for f in findings
    }
    assert pairs == {("R1", "R2"), ("R1", "R3"), ("R2", "R3")}
    for finding in findings:
        assert finding.target.component_ref != finding.target.counterpart_ref
        assert finding.target.primitive_id == ""
        assert finding.target.pin_refs == []  # 这三个焊盘都没有引脚号


def test_the_pair_order_and_the_finding_order_are_deterministic():
    """Order must not depend on the board's pad order: both sides are keyed."""
    pads = [
        _pad("z", component="R9", pin="2", width=100, height=100, x=0, y=0),
        _pad("a", component="R2", pin="1", width=100, height=100, x=20, y=0),
        _pad("m", component="R5", pin="1", width=100, height=100, x=0, y=20),
    ]
    forward = [
        (f.target.component_ref, f.target.counterpart_ref) for f in _run(*pads)
    ]
    backward = [
        (f.target.component_ref, f.target.counterpart_ref) for f in _run(*reversed(pads))
    ]
    assert forward == backward
    assert forward == [("R2", "R5"), ("R2", "R9"), ("R5", "R9")]


def test_evidence_gives_position_shape_size_angle_net_and_no_area():
    """证据给位置/形状/尺寸/角度/网名；**不写面积**（本规则不算面积）。"""
    a = _pad(
        "A", component="U1", pin="1", net="+24V", width=100, height=60, x=1.5, y=-2.5,
        effective_layers=[1],
    )
    b = _pad(
        "B", component="U2", pin="3", net="GND", width=80, height=40, angle=90, x=40,
        effective_layers=[1],
    )
    findings = _run(a, b)
    assert len(findings) == 1
    evidence = findings[0].evidence
    assert evidence[0] == "U1.1 「+24V」 RECT 100×60 mil @ (1.5, -2.5) mil, 角度 0°"
    assert evidence[1] == "U2.3 「GND」 RECT 80×40 mil @ (40, 0) mil, 角度 90°"
    assert "共享铜层：1" == evidence[2]
    assert findings[0].target.measurement is None
    assert findings[0].target.primitive_id == ""
    assert findings[0].target.pin_refs == ["1"], "只放 U1 那一侧的引脚，不混装 U2 的 3"
    joined = " ".join(evidence) + findings[0].message
    assert "mil²" not in joined and "面积：" not in joined, "面积是编造的——本规则不计算它"
    assert "1.5" in joined and "-2.5" in joined and "90" in joined


# ---------------------------------------------------------------------------
# the coarse screen must be a screen, not a judge
# ---------------------------------------------------------------------------


def test_the_coarse_screen_agrees_with_a_brute_force_sweep():
    """框粗筛只许省时间，不许改结论：与逐对直算的集合逐对相等。"""
    pads = []
    for index in range(24):
        pads.append(
            _pad(
                f"p{index}",
                component=f"R{index}",
                width=60 + (index % 3) * 10,
                height=40,
                x=(index % 6) * 55,
                y=(index // 6) * 45,
                shape="ELLIPSE" if index % 4 == 0 else "RECT",
            )
        )
    expected: set[tuple[int, int]] = set()
    board = _board(*pads)
    for i, first in enumerate(pads):
        for j, second in enumerate(pads):
            if j <= i:
                continue
            if pad_copper_overlap(board, first, second):
                expected.add((i, j))
    findings = PadOverlap().check(_ctx(board))
    # 每条样本的 component_ref / counterpart_ref 唯一（R0…R23 一焊盘一器件），所以这对
    # 字段本身就是焊盘对的身份——**不借 pin_refs 反推**（它只放一侧引脚，本就装不下对）。
    index_of = {f"R{index}": index for index in range(len(pads))}
    found = {
        tuple(sorted((index_of[f.target.component_ref], index_of[f.target.counterpart_ref])))
        for f in findings
    }
    assert all(
        len(f.target.pin_refs) <= 1 and f.target.primitive_id == "" for f in findings
    )
    assert len(expected) > 0, "样本里必须真有重叠，否则这条是空转"
    assert found == expected


# ---------------------------------------------------------------------------
# registration, owner, and the PairedRule shape the report relies on
# ---------------------------------------------------------------------------


def test_registered_after_board_off_edge_and_before_track_ampacity():
    """任务书 §规则合同: 注册位置固定 ``BoardOffEdge()`` 后 / ``TrackAmpacity()`` 前。"""
    ids = [rule.id for rule in pcbreview.BUILTIN_PCB_RULES]
    assert ids.count("pcb-pad-overlap") == 1
    position = ids.index("pcb-pad-overlap")
    assert ids[position - 1] == "pcb-component-off-board"
    assert ids[position + 1] == "pcb-track-ampacity"
    registered = pcbreview.BUILTIN_PCB_RULES[position]
    assert isinstance(registered, PadOverlap)
    assert registered.id == "pcb-pad-overlap"
    assert registered.level == "L1-pcb-geometry"
    assert registered.title
    assert registered.source and "pad_copper_overlap" in registered.source


def test_the_rule_is_a_pcb_rule_with_the_declared_four_fields():
    rule = PadOverlap()
    assert isinstance(rule, PcbRule)
    # 四条声明式属性在场，report 靠它们给行归级（钉 1 / 钉 7）。
    assert (rule.id, rule.level) == ("pcb-pad-overlap", "L1-pcb-geometry")
    assert rule.title and rule.source


def test_module_owners_lists_the_new_module_as_review():
    """``contracts/module-owners.json``: 新模块一个、且只一个 owner（review）。"""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "contracts" / "module-owners.json").read_text("utf-8"))
    assert contract["modules"]["rules/pcb/overlap.py"] == "review"
    owners = [path for path in contract["modules"] if path == "rules/pcb/overlap.py"]
    assert len(owners) == 1


def test_the_rule_reads_only_shared_measure_and_the_rule_base():
    """Owner/layer: 本模块只允许 review→shared 与 review→review 的 import。"""
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[1]
    module = source / "src" / "boardwise" / "rules" / "pcb" / "overlap.py"
    tree = ast.parse(module.read_text("utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level:
            imported.add("." * node.level + (node.module or ""))
    assert imported == {"...core.measure", "..base", ".base"}
    # 判定唯一来源：pad_copper_overlap；pad_corners 只许出现在粗筛里。
    text = module.read_text("utf-8")
    assert "pad_copper_overlap" in text
    # 预研包的 ``pad_overlap_area()`` 不移植：本模块里没有它的定义，也没有 mil²。
    assert "def pad_overlap_area" not in text and "mil²" not in text
    measure_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "core.measure"
        for alias in node.names
    }
    assert measure_names == {"pad_corners", "pad_copper_overlap"}


def test_a_board_with_no_pads_or_one_pad_is_silent():
    assert PadOverlap().check(_ctx(_board())) == []
    single = _pad("A", component="U1", width=100, height=60)
    assert _run(single) == []


def test_zero_extent_pad_contributes_no_copper():
    """零面积焊盘没有铜：判定为假，规则静默（``_polygon_has_area`` 的诚实读数）。"""
    zero = _pad("A", component="U1", width=0, height=0)
    other = _pad("B", component="U2", width=100, height=60)
    assert _run(zero, other) == []


def test_the_rule_does_not_read_the_netlist():
    """本规则不问网（同网不豁免），所以 ``pcb_model`` 与 ``intent`` 都不参与判定。"""
    a = _pad("A", component="R1", net="GND", width=100, height=60)
    b = _pad("B", component="R2", net="GND", width=100, height=60, x=50)
    board = _board(a, b)
    without = PadOverlap().check(_ctx(board))
    with_model = PadOverlap().check(
        PcbReviewContext(board=board, board_title="PCB1", model=object(), pcb_model=object())
    )
    assert len(without) == len(with_model) == 1


def test_message_names_both_parts_and_the_shared_layer():
    a = _pad(
        "A", component="U1", pin="7", net="+24V", width=100, height=60,
        effective_layers=[1],
    )
    b = _pad(
        "B", component="U2", pin="2", net="GND", width=100, height=60, x=50,
        effective_layers=[1],
    )
    finding = _run(a, b)[0]
    message = finding.message
    assert "U1.7" in message and "U2.2" in message
    assert "层 1" in message
    # 异网（+24V / GND）：这是一次直接短路，不是装配冲突的说法。
    assert "直接短路" in message and "两个不同电位" in message
    assert finding.target.pin_refs == ["7"]
