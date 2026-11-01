"""534：名字桩的排版——两个桩的名称行不许落在同一处，名字要横着念。

525/146 之后，一枚桩的**导体**是干净的，`_name_row_clash` 也盯着它自己那个符号
（146），但有三种事实没人看：

* **两枚桩的名称行可以落在同一处**，而且那块地没有主人。CH340 页上 `CTS` 的行
  `[115,200]-[129.3,210]` 与 `RXD` 的行 `[115,205]-[130.1,215]` 真重叠 5 单位
  （`.tmp_534/header-probe/NOTES.md` sec.1），两枚桩的导体各自都查干净了；
* **行的方向由最长直段决定，不是桩的外框**：`RI` 的 15 单位折桩（横 5、竖 10）在宿主
  里是**竖排**的名字，U1-TXD 只有 5 单位的桩、名字 14.3 宽，外框比名字窄，但它也是竖排；
  短网名更骗人——`TXD` 只 14.3 宽，外框宽高猜方向会猜错；
* 桩短于名字宽是**常态**（18 枚里 13 枚如此），所以名字起点锚定后会伸出导线末端；
  「名字必须落在导线长度内」不是本批的规则，本批只看**行落在哪里**。

所以 :func:`boardwise.engines.drawapply._place_label_stub` 在「导体干净」的候选里，用
`textmetrics.wire_name_box` 量出宿主**实际**会画的那一行（方向用 `_straight_runs` 独立
算最长段，不用外框宽高猜），要求它（a）不压自己那个符号（146，保留）、（b）不与本页
**已经选定的水平行**重叠。**534 r25 起这一行以锚点居中**（横排 `y±WIRE_NAME_ROW/2`、
竖排 `x±WIRE_NAME_ROW/2`，阅读轴不变），本文件的 `_row` 返回的就是这一行；两条标签行
之间的地板是 `LABEL_ROW_FLOOR = 1`，对其余物体仍按 S-21 的 2。重叠（gap<0）不许；相切（gap 0）在 10 节距的表头列上是几何
必然（行高 10），保留并记 note；S-21 的 2 单位只作为 note 的数字，**不当通过**——本批
实测 18 枚桩里仍有 11 对行相切、1 枚竖排，见 `evidence/534/label-stub-typography.md`。

两个合成用例各钉一个缺陷形状，一个真页用例钉 18 枚桩的读数；关掉「行避让」或关掉
「水平优先」都会让对应的用例变红（变异记录见同一份 evidence）。
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import LayoutLabel
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core import textmetrics
from boardwise.engines import drawapply
from boardwise.engines import pagecompiler
from boardwise.engines.drawapply import PlanDrawWire, load_library
from boardwise.engines.readability import SOFT_FLOOR_TEXT_GAP

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"


def declared(**kwargs) -> LayoutLabel:
    """A label that **states** 534's policy (053f: both switches are opt-in).

    536 raised the ladder's head to `LABEL_STUB_MIN`, and 534 r25 moved the
    name row to the anchor's centre. 053f turned both into document statements
    (`labelPolicy.stubMin` / `labelPolicy.rowModel`) whose defaults are the
    *old* readings, so a label built with neither would be judged by the
    pre-534 gates — not what any frozen coordinate in this file measures.
    """
    kwargs.setdefault("stub_min", drawapply.LABEL_STUB_MIN)
    kwargs.setdefault("row_model", "centered")
    return LayoutLabel(**kwargs)


def _built(*wires: PlanDrawWire) -> drawapply._Built:
    built = drawapply._Built()
    built.wires.extend(wires)
    return built


def _place(label: LayoutLabel, built: drawapply._Built):
    stub, blockers = drawapply._place_label_stub(label, built, {}, [])
    assert stub is not None, (label.net, blockers)
    return tuple(tuple(point) for point in stub)


def _run(points) -> drawapply._StubRun:
    return drawapply._StubRun(
        points=tuple(points), side=(1.0, 0.0), shape="", family="",
    )


def _row(points, net: str):
    """The name row the **host** prints, as the stub chooser measures it (534 r25).

    The row is centred on its anchor — ``y ± WIRE_NAME_ROW/2`` for a horizontal
    run, ``x ± WIRE_NAME_ROW/2`` for a vertical one — the direction it reads in
    taken from the longest straight run. :func:`textmetrics.wire_name_box` still
    reports the *measured* box (start-anchored: the row **above** a horizontal
    anchor, **right of** a vertical one), so the two differ by exactly half a row
    (5 units). Every frozen coordinate in this file is the centred one, because
    that is the box ``built.label_stub_rows`` registers and ``_row_cut`` gates on;
    the measured box is only what a reader outside the chooser would see.
    """
    box = textmetrics.wire_name_box([tuple(p) for p in points], net)
    if box is None:
        return None
    half = textmetrics.WIRE_NAME_ROW / 2.0
    if _horizontal(points):
        return (box[0], box[1] - half, box[2], box[3] - half)
    return (box[0] - half, box[1], box[2] - half, box[3])


def _gap(a, b) -> float:
    """The stub chooser's own ruler: `drawapply._row_gap`, restated for the test."""
    return max(
        max(a[0], b[0]) - min(a[2], b[2]),
        max(a[1], b[1]) - min(a[3], b[3]),
    )


def _horizontal(points) -> bool:
    return drawapply._stub_row_is_horizontal(_run(points))


# --------------------------------------------------------------- 两个缺陷形状


def test_two_names_one_place_bends_the_later_stub_off_the_first():
    """CTS × RXD 的形状：两枚桩的名称行真重叠 5，谁都不属于任何器件。

    上桩的标签盒在右，而右侧的直线档被一条外来网导线挡住（099e 的现场：V3 走线占了
    那一行）——于是它能出去的第一档是 099f 的折线「上 5 再右 40」，最长直段是横的 40，
    名称行以中点 20 起铺、落在 y+5；下面 10 单位处的桩首档「右 40」同样以中点 20 起铺，
    两行重叠 5 单位，这与 CH340 页 `CTS@(110,195)` × `RXD@(110,205)` 的冻结读数同形。

    **档位换了（536）：第一档从 10 抬到 `LABEL_STUB_MIN = 40`。** 旧读数里首档是
    「上 5 再右 10」（行从 x=5 起铺）；现在首档长 40（行从 x=20 起铺），重叠仍是 5 ——
    同一缺陷形状，只是行整体右移了一个桩长。次档「右 10」也只擦到 0.09（<0）、照样不许
    取，最后落到「右 5」（行 `[2.5, 17.59]`，与上桩的行相隔 2.41）。

    534 之后：后一枚桩必须让开**行**，不是让开导体——它退到别的长度档（行整体平移），
    或者折走；两种都可接受，**不可接受的是重叠**。关掉行避让（见 evidence 的变异 1）
    这一条立刻变红，读数是 gap = -5。
    """
    blocker = PlanDrawWire(net="V3", points=[(5.0, -2.0), (5.0, 3.0)])
    upper = declared(net="CTS", text="CTS", x=0.0, y=0.0,
                        bbox=(10.0, -5.0, 30.0, 5.0))
    below = declared(net="RXD", text="RXD", x=0.0, y=10.0,
                        bbox=(10.0, 5.0, 30.0, 15.0))
    built = _built(blocker)

    first = _place(upper, built)
    second = _place(below, built)

    # 上桩确实是折线档（上 5 再右 40）：这是本用例的前提，不是结论。
    assert first == ((0.0, 0.0), (0.0, 5.0), (40.0, 5.0)), first
    assert _horizontal(first)
    first_row, second_row = _row(first, "CTS"), _row(second, "RXD")
    # 新首档「右 40」的行与上桩的行重叠 5 —— 若后桩仍选首档，这里会是 -5。
    naive = _row(((0.0, 10.0), (40.0, 10.0)), "RXD")
    assert math.isclose(_gap(first_row, naive), -5.0), (first_row, naive)
    # 旧首档「右 10」（536 之前的第一档）现在只擦到 0.09，也不许取：这条钉住
    # 「退一档还不够，得退到行真的让开」。
    old_first = _row(((0.0, 10.0), (10.0, 10.0)), "RXD")
    assert _gap(first_row, old_first) < 0.0, (first_row, old_first)
    assert second != ((0.0, 10.0), (40.0, 10.0)), second
    assert second != ((0.0, 10.0), (10.0, 10.0)), second
    assert _gap(first_row, second_row) >= 0.0, (first_row, second_row, second)
    # 而且它仍是**水平**行：让开的方式不是把名字竖起来。
    assert _horizontal(second), second


def test_a_label_whose_text_is_above_gets_a_name_that_reads_across():
    """RI / U1-TXD 的形状：标签盒在上，099d 的一档是「上 10」——竖排的名字。

    宿主沿最长直段铺名字：上 10 的桩让 `RI` 竖着落在脚边 5–12 内（冻结读数
    `[105,180]-[115,187.1]`），`TXD` 更糟——桩只有 5 单位，名字 14.3 宽，竖排后压到
    下面那枚桩的行上。534 要求先找**横着念**的档：本用例里四个直线方向都空着，
    第一个横排档（横腿与竖腿同长时，宿主取先出现的那一段，`max` 的首个最大项）是
    「右 5 再上 5」，让路的方式也仍然是横的。关掉水平优先（变异 2）时这里回到
    「上 10」，竖排，测试变红。
    """
    label = declared(net="RI", text="RI", x=0.0, y=0.0,
                        bbox=(-5.0, 5.0, 5.0, 15.0))
    stub = _place(label, _built())

    assert stub != ((0.0, 0.0), (0.0, 10.0)), stub  # 099d 的一档：竖排的「上 10」
    assert _horizontal(stub), stub
    row = _row(stub, "RI")
    # 名字行是横的：行从最长段中点起、向右铺、高是一个名称行 —— 与「竖排」的区别
    # 不在宽高比（`RI` 只有 7.15 宽，比 10 高还窄），而在起铺方向。
    # 534 r25：厚度轴改成**以锚点居中**，所以这一行是 y ∈ [-5, 5]。旧断言
    # `row[1] == 0.0 and row[3] == WIRE_NAME_ROW`（整行在锚点上方）钉的是
    # `wire_name_box` 的起点锚定盒，那是宿主实际墨迹之上的半行幽灵；等价的新断言是
    # 「高恰一行、中线恰在锚点上」，宽仍钉量出来的字宽——强度不变，位置换成真位置。
    half = textmetrics.WIRE_NAME_ROW / 2.0
    assert row[1] == -half and row[3] == half, row
    assert math.isclose(row[2] - row[0], textmetrics.render_width("RI")), row


def test_a_free_preferred_run_is_still_the_first_choice():
    """既有简单路径优先（099d 的零移动规则）没有被 534/536 改写。

    文本盒在右 ⇒ 首选就是首档；没有别的桩、没有外来物体时，桩必须逐字节是
    (0,0)→(40,0)。**档位换了（536）：旧首档 10 → 新首档 `LABEL_STUB_MIN = 40`**，
    除此之外没有变化。这条钉住「只在有冲突时才让路」。
    """
    label = declared(net="D+", text="D+", x=0.0, y=0.0,
                        bbox=(10.0, -5.0, 30.0, 5.0))
    assert _place(label, _built()) == ((0.0, 0.0), (40.0, 0.0))


# ------------------------------------------------------------------ 真页读数


def _ch343_page():
    circuit = CircuitSpec.from_dict(json.loads(
        (SPECS / "ch343_uart.circuit.json").read_text(encoding="utf-8")))
    sheet = PresentationSpec.from_dict(json.loads(
        (SPECS / "ch343_uart.presentation.json").read_text(encoding="utf-8")))
    book = load_library(SPECS / "ch343_uart.library.json")
    result = pagecompiler.compile_page(
        circuit, sheet, book,
        pagecompiler.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0)),
    )
    assert result.pages, [
        item.reason for item in getattr(result, "rejected", ())
    ]
    page = result.pages[0]
    plan = drawapply.module_plan(
        page.plan, circuit, sheet, book,
        label_stubs=True, module_label="page " + "+".join(m.id for m in page.modules),
    )
    # `purpose` also marks the cross-module carrier runs; a name stub says so.
    stubs = [
        wire for wire in plan.change.draw_wires
        if str(getattr(wire, "purpose", "") or "").startswith("name stub")
    ]
    return circuit, page, plan, stubs


def _legacy_ch343_page_readings_not_collected():  # 534 r23: superseded by the refusal test
    """当前三件套（11 件，hdr 在 C4 之后）的 18 枚桩，逐个看宿主行。

    926 冻结的旧读数（10 件版）是：18 枚桩里 **2 枚竖排**（RI 两侧、U1-TXD），
    `min pair gap = -5`（CTS × RXD 真重叠）。本用例钉的是现在的读数，并且**如实**
    记下还没做到的部分——S-21 的 2 单位没有达到，缺的不是更多 rungs 而是页级行分配：

    | 项 | 旧 | 新 |
    | --- | --- | --- |
    | 竖直行 | 2 | **1**（只剩 U1-TXD，梯子没有干净的横排档） |
    | 重叠（gap<0） | 1 对（-5） | **0 对** |
    | gap<2 的对数 | — | 11（0 或 0.35–0.70 的擦边，无一对 <0） |
    | 桩数 / 无载体的标签 | 18 / 0 | 18 / 0 |

    为什么 11 对仍是 0：名称行高 10、表头一列节距 10，两行要么正好相切，要么靠折桩的
    ±5/±10 错开；错开档**存在**，但「最简单档优先」的逐枚贪心会让先选的那枚占住整列，
    要达标得做整列的全局指派（页级行分配器）。按派单不做全局搜索，因此这里记缺口而不是
    把 fallback 当通过。
    """
    _circuit, page, plan, stubs = _ch343_page()

    # 无缺失载体：18 个标签落桩，锚点就是标签锚点；另外两枚（D+/D- 的跨模块端点）
    # 由规划导线本身承载名字（145d 的 `carried`），不走桩——这也是「无缺失载体」的
    # 另一半，必须点名验，不能只数 18。
    labels = {(float(item.x), float(item.y)) for item in page.plan.labels}
    anchors = {(float(wire.points[0][0]), float(wire.points[0][1])) for wire in stubs}
    assert anchors <= labels, sorted(anchors - labels)
    carried = labels - anchors
    assert carried == {(175.0, 680.0), (175.0, 690.0)}, carried
    for point in carried:
        assert any(
            point in [tuple(item) for item in wire.points]
            for wire in plan.change.draw_wires
        ), point
    assert len(stubs) == 18, [(w.net, w.points[0]) for w in stubs]

    rows = [(wire.net, tuple(wire.points), _row(wire.points, wire.net)) for wire in stubs]

    # 1) 没有任何两个名称行重叠。
    overlapping = [
        (a[0], a[1], b[0], b[1], _gap(a[2], b[2]))
        for a, b in itertools.combinations(rows, 2)
        if _gap(a[2], b[2]) < 0.0
    ]
    assert overlapping == [], overlapping

    # 2) 方向：17 枚横排，唯一竖排是 U1 的 TXD（(115,365)，5 单位桩、14.3 宽名字）。
    vertical = [
        (net, points[0]) for net, points, _box in rows if not _horizontal(points)
    ]
    assert vertical == [("TXD", (115.0, 365.0))], vertical

    # 3) S-21 的缺口是**相切/擦边**，不是重叠：11 对里最小 0、最大 0.70，全部 >= 0。
    under = sorted(
        _gap(a[2], b[2]) for a, b in itertools.combinations(rows, 2)
        if _gap(a[2], b[2]) < SOFT_FLOOR_TEXT_GAP
    )
    assert len(under) == 11, under
    assert under[0] >= 0.0 and under[-1] < SOFT_FLOOR_TEXT_GAP, under

    # 4) 既有简单路径优先：首选档本来就干净、横排的标签，桩逐字节不变。
    by_anchor = {(net, points[0]): points for net, points, _box in rows}
    assert by_anchor[("DCD", (105.0, 190.0))] == ((105.0, 190.0), (115.0, 190.0))
    assert by_anchor[("D+", (115.0, 395.0))] == ((115.0, 395.0), (105.0, 395.0))
    assert by_anchor[("RI", (55.0, 190.0))] == ((55.0, 190.0), (45.0, 190.0))

    # 5) 缺口有话说：U1-TXD 那枚竖排桩走的是 pre-146 fallback（每个干净候选的名字
    #    都压在 U1 自己的符号/文字上），note 里明说「不是 534 通过」；相切的行也各有
    #    一条 under-S-21 的 note。竖排/压字都不许冒充通过。
    notes = list(plan.change.draw_notes)
    assert any(
        note.startswith("net TXD:") and "not a 534 pass" in note for note in notes
    ), [note for note in notes if note.startswith("net TXD:")]
    assert sum("under S-21's" in note for note in notes) == 8, [
        note for note in notes if "under S-21's" in note
    ]

# ------------------------------------------------ 534 F1: 竖行也是纸上的墨


#: The review's own geometry, scaled to a name the font table can measure: the
#: vertical row is 10 wide and as long as its net's name (the review read
#: ``(0, 5)-(10, 111.45)``), so a later horizontal row at ``y = 60`` lands inside it.
_TALL = "CH343_UART_RXD_FROM_U1"


def _forced_vertical(built: drawapply._Built):
    """Place the tall label so only a **vertical** run is clear, and return its row.

    The label's text box is above it, and the paper one lattice step either side is
    blocked by two fake bodies — the same shape as the CH340 page's U1-TXD, where
    every horizontal rung was occupied and the kept run read down the page. The
    bodies are a call argument, not state: the next label is placed without them.

    536: the run kept is the ladder's **first rung at 40** — the old reading was
    "up 10" (the pre-536 first rung). The shape did not change (both horizontal
    sides are sealed, so the up run is the first clean candidate); the row the
    host prints moves with the rung's midpoint: ``(-5, 20)-(5, 122.87)`` instead
    of the 10-unit rung's ``(-5, 5)-(5, 107.87)``.
    """
    upper = declared(net=_TALL, text=_TALL, x=0.0, y=0.0,
                        bbox=(-5.0, 5.0, 5.0, 15.0))
    bodies = {
        "L": (-200.0, -300.0, -2.0, 300.0),
        "R": (2.0, -300.0, 200.0, 300.0),
    }
    stub, blockers = drawapply._place_label_stub(upper, built, bodies, [])
    assert stub is not None, blockers
    stub = tuple(tuple(point) for point in stub)
    assert stub == ((0.0, 0.0), (0.0, 40.0)), stub
    assert not _horizontal(stub), stub
    return stub, _row(stub, _TALL)


def test_a_vertical_row_is_registered_so_the_next_label_clears_it():
    """534 F1：竖排的名称行同样是纸上的墨，必须进入 `label_stub_rows`。

    审查实测的现场（本用例按字体表复刻）：上一枚只能竖排的桩行是
    ``(-5, 20)-(5, 122.87)``（536 的 40 桩；10 桩时代是 ``(-5, 5)-(5, 107.87)``）；
    下一枚标签的首档「右 40」行是 ``(0, 55)-(14.3, 65)``，两行真重叠 **5**，而
    ``_row_gap`` 应为 -5。旧代码只登记横排行，所以第二枚的 ``_row_clearance`` 拿空表
    比较，gap 读成 ``inf``，tier 1 把这枚重叠行当「干净」直接收下、一句不留——正是
    这条测试要钉死的静默。

    **行坐标与首档一起换（534 r25 居中、536 首档 40）。** 行以最长段中点为中点：
    旧首档「右 10」从锚点 +5 起铺，锚点 x=-5 时行正是 ``(0, 55)-(14.3, 65)``；新首档
    「右 40」从锚点 +20 起铺，要铺出**同一行**就得把锚点再左移 20 到 ``x=-20``（r25 时
    只需挪一格到 -5）。首档行的重叠仍是 5，缺陷形状不变。

    修好之后：竖行登记（条目里写明 vertical），第二枚不再吃首档「右 40」，而是退到
    不重叠的「右 60」（``(10, 55)-(24.3, 65)``，与竖行 gap 5），仍然横排——让路的
    方式不是把名字竖起来。把 `take()` 的登记退回「只登记横排」，第一条断言与
    ``second != naive`` 立刻变红。
    """
    built = _built()
    first, first_row = _forced_vertical(built)

    # 1) L1 的竖行真的进了 obstacles，并且条目自己说是竖的。
    assert len(built.label_stub_rows) == 1, built.label_stub_rows
    what, box = built.label_stub_rows[0]
    assert "vertical" in what, what
    assert box == first_row, (box, first_row)

    # 锚点 x=-20：见 docstring——新首档「右 40」的行从 x=0 起铺，与竖行在 x 上重叠 5。
    below = declared(net="TXD", text="TXD", x=-20.0, y=60.0,
                        bbox=(10.0, 55.0, 30.0, 65.0))
    second = _place(below, built)
    second_row = _row(second, "TXD")
    # 2) 首档「右 40」正是与竖行重叠 5 的那一行——修复前第二枚就选了它。
    naive = ((-20.0, 60.0), (20.0, 60.0))
    assert math.isclose(_gap(first_row, _row(naive, "TXD")), -5.0), (
        first_row, _row(naive, "TXD"))
    assert second != naive, second
    # 3) 换到的档与竖行不重叠，而且读得还是横的。
    assert _gap(first_row, second_row) >= 0.0, (first_row, second_row, second)
    assert _horizontal(second), second
    # 4) 它自己的行也登记了：后面第三枚要同时避开两行。
    assert len(built.label_stub_rows) == 2, built.label_stub_rows
    assert built.label_stub_rows[1][1] == second_row


def test_a_fallback_that_keeps_an_overlap_says_which_row_it_prints_on():
    """534 F1：所有横排档都被堵死时，fallback 必须是**具体的** overlap，不能静默。

    同一枚竖排桩（`_forced_vertical`），另在第二枚标签两侧一格放两条外来导线，把每一个
    横排首档（直线右/左，以及先上/下再右的折线第二腿）都堵掉：只剩竖排档，而每一枚竖行
    都落在上一枚竖行里。修复前，tier 2 会以 gap ``inf`` 收下「上 10」，note 只说
    「没有横排档」——重叠一个字都不提；修复后 tier 3 保留同一根桩（pre-534 的第一
    个干净档），但 note 必须点名它压在哪一行、重叠框是什么。

    锚点留在这里是 ``x=0``（上一条为重叠挪到了 x=-20）：本用例靠 ``x=±2`` 的两条竖线
    拦住所有向右的首档，第二枚的干净档是「上 40」（536 首档；旧读数「上 10」），它的
    竖行是 ``(-5, 80)-(5, 94.3)``（10 桩时代 ``(-5, 65)-(5, 79.3)``：竖行的居中在厚度轴
    x 上、中点随桩长走到 y=80，整体仍在上一枚的 ``(-5, 20)-(5, 122.87)`` 里），两行
    真重叠 10。
    """
    built = _built()
    _first, first_row = _forced_vertical(built)
    built.wires.extend([
        PlanDrawWire(net="V3", points=[(2.0, 40.0), (2.0, 80.0)]),
        PlanDrawWire(net="V4", points=[(-2.0, 40.0), (-2.0, 80.0)]),
    ])

    below = declared(net="TXD", text="TXD", x=0.0, y=60.0,
                        bbox=(10.0, 55.0, 30.0, 65.0))
    stub, blockers = drawapply._place_label_stub(below, built, {}, [])
    assert stub is not None, blockers
    stub = tuple(tuple(point) for point in stub)
    # 竖直的第一档被保留（pre-534 的 fallback 就是它，146 的「更差的图不是短路」）：
    # 536 的第一档是「上 40」（旧读数「上 10」），fallback 取的就是同一格阶梯的首档。
    assert stub == ((0.0, 60.0), (0.0, 100.0)), stub
    row = _row(stub, "TXD")

    notes = [note for note in built.notes if note.startswith("net TXD:")]
    assert len(notes) == 1, notes
    assert "overlaps" in notes[0], notes[0]
    assert "recorded as an overlap" in notes[0], notes[0]
    assert drawapply._box_text(first_row) in notes[0], (first_row, notes[0])
    assert _gap(first_row, row) < 0.0, (first_row, row)
    # 这枚被保留的行也登记了——fallback 不代表下一枚可以随便压上来。
    assert built.label_stub_rows[-1][1] == row, built.label_stub_rows
    assert "vertical" in built.label_stub_rows[-1][0], built.label_stub_rows[-1]


#: The legacy sheet's own pose freedom -- **an isolation for this page-layer test,
#: never a statement about what the host draws.**
#:
#: The shipped library declares `C0603-100nF-C1590` at rotation `0` only (the pose
#: `passive-text-profiles` measured off the render), and the pre-migration sheet puts
#: C1/C3 in `ch343` and C4 in `hdr`, a body direction that set does not cover: the
#: **module** compiler then refuses at the pose gate (`no legal pose of … puts C1's
#: pins where the drawing needs them`) and the page is never assembled. The four
#: unmirrored rotations below are handed to an in-memory copy of the book so this
#: fixture can pin what it now pins -- the page-level overflow -- while the
#: production library keeps its measured set, untouched.
LEGACY_C0603_POSES = (0, 90, 180, 270)


def _legacy_book_with_its_own_pose_freedom(book):
    """The shipped book, with the legacy sheet's pose freedom for this fixture only."""
    import dataclasses

    from boardwise.core.symbolprofile import SymbolPose

    profile = book["C0603-100nF-C1590"]
    widened = dataclasses.replace(
        profile,
        poses=[SymbolPose(rotation=rotation, mirror=False)
               for rotation in LEGACY_C0603_POSES],
    )
    out = dict(book)
    out[profile.symbol_ref] = widened
    return out


def test_the_legacy_three_island_sheet_overflows_the_stated_page_and_is_named():
    """534 r23 的旧三岛形状，现在拒绝在**页面尺寸**上，并且是具名拒绝。

    **这条测试现在钉什么。** 旧三岛 fixture（C1/C3 在 `ch343`、C4 在 `hdr`、D+/D-
    为普通 directWiring、无 localLabelObligations）在当前几何下，三个模块按刚体排出
    3 列 1146.5 x 240，而图页是 1170 x 825、四周 20 单位边距——最小排列需
    1186.5 x 280，因此整页被 `presentation-poor` 具名拒绝（行动项就是「把页面放大到
    至少 1186.5 x 280」）。数字是实测且可重复的：两次编译逐字符相同；本文件不写死
    别的口径。**536 换档带出来的数字：10 桩时代是 1176.5 x 240 / 1216.5 x 280，
    首档抬到 40 后每个模块窄 10，三列总宽少 30，高度与排列数不变。**

    **旧的 `VCC` / `pose-variant=0` 期望为什么删掉（不是被吞掉）。**
    534 r23 记录时这一页拒绝于两处模块内原因：`ch343` 的 `VCC` 旗标座位、
    `hdr` 的 readability（`text-over*`）。两者都已随主线演进消失，与姿态无关：

    * `VCC`：当前 flag 座位梯子（520b2）在同一形状上能给出合法座位，`ch343` 模块
      **整个编译通过**；任何姿态组合都不再产生含 `VCC` 的模块级拒绝（实测矩阵见
      `.tmp_534/legacy-stub-fixture-r1/findings.md` §3）。
    * `text-over*`：旧三岛把 D+/D- 画成一整根跨岛线，534 r18 之后 gate 对这种形状
      报的是 `name-row-vertical`（名字沿竖直 run 印），且只在 **1 列**排列下才走到；
      3 列排列先被页面尺寸拒掉，走不到 readability。
    * `pose-variant=0` 这个串只出现在**模块级 gate 失败**的 detail 里
      （`spacing=1 pose-variant=0: …`）；本夹具已无模块级 gate 失败，所以该断言在
      当前代码下不可达，留着只会逼我们伪造一条失败。

    **「无可用 name row 时按名拒绝」没有被这条测试丢掉**，它仍在同文件更贴近的那一层：
    `test_strict_every_row_cut_is_a_named_refusal`（每一档都被异网段穿透 → 具名拒绝）、
    `test_strict_the_labels_own_box_is_still_an_obstacle`（label box 全盖 → 无合法 run）、
    `test_the_survivors_branch_refuses_when_every_run_is_cut`、
    `test_the_end_fallback_no_longer_takes_a_run_the_box_gate_rejected`
    （末尾 fallback 不得取被闸拒的 run，返回 `(None, blockers)` 并逐条点名）。这条页面级
    测试只负责「旧三岛形状必须整体具名拒绝」，不再冒充 stub 拒绝的证据。

    **姿态环境是隔离，不是验收。** `_legacy_book_with_its_own_pose_freedom` 只改内存里
    的 book 副本（`dataclasses.replace`），生产库 `blocklib/specs/*.library.json` 不变；
    这里放开的姿态也不得被读作「宿主会这样画」——宿主文本姿态仍以正式库的实测声明集为准。
    """
    circuit = CircuitSpec.from_dict(json.loads(
        (SPECS / "ch343_uart.circuit.json").read_text(encoding="utf-8")))
    # 534 正式迁移：正式规格已是四岛，而这条回归测的是**旧三岛边界**（C1/C3 在芯片岛、
    # C4 在连接器岛、D+/D- 为普通 directWiring、无 localLabelObligations）。夹具在本
    # 测试内由正式 payload 深拷贝改造而来——显式的测试内输入，不读任何本地产物。
    sheet = PresentationSpec.from_dict(_legacy_three_island_payload(json.loads(
        (SPECS / "ch343_uart.presentation.json").read_text(encoding="utf-8"))))
    # 053f：这两个数字是 536/534r25 量出来的（首档 40、行以锚点居中），而这两条
    # 现在是**文档的语句**——不写就回到旧行为（10 单位的首档、`wire_name_box` 的
    # 原样行，也就是本文件注释里 1176.5 x 240 那一组读数）。所以夹具显式声明它们，
    # 让这条页面级回归仍然测它当初测的那张图。
    sheet.label_policy.stub_min = drawapply.LABEL_STUB_MIN
    sheet.label_policy.row_model = "centered"
    # 页面宽度这一组读数也依赖 535 的分簇（实测：半径 0 → 1176.5，半径 100 →
    # 1146.5，三个模块各差 10）。053f 之后它同样是文档的语句，所以一并声明，
    # 夹具才是它当初量出的那张图。
    sheet.gnd_cluster_radius = 100.0
    book = _legacy_book_with_its_own_pose_freedom(
        load_library(SPECS / "ch343_uart.library.json"))
    result = pagecompiler.compile_page(
        circuit, sheet, book,
        pagecompiler.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0)),
    )
    assert result.pages == [], (
        "this fixture must be refused, not drawn onto a sheet it overflows"
    )
    failures = list(result.failures)
    assert len(failures) == 1, [
        (item.category, item.subject, item.detail[:140]) for item in failures]
    failure = failures[0]
    assert failure.category == "presentation-poor", failure.category
    assert failure.subject == "page", failure.subject
    # The exact reading: 3 rigid modules in 3 columns, wider than the sheet allows.
    # 536: 10-unit stubs gave 1176.5 x 240 / 1216.5 x 280; the first rung at 40 is
    # 30 units narrower over three columns (each module 10), height and the
    # arrangement count unchanged.
    assert "the arrangement of 3 module(s) in 3 column(s)" in failure.detail
    assert "draws 1146.5 x 240 canvas units" in failure.detail
    assert "the stated page is 1170 x 825" in failure.detail
    assert "20-unit margin on each side" in failure.detail
    assert "12 arrangement(s) were built and refused inside the stated page" in failure.detail
    assert "the smallest of them needs 1186.5 x 280 canvas units" in failure.detail
    assert "1186.5 x 280" in failure.action, failure.action
    # The local pose freedom is what got the modules past their gate: if a posed
    # refusal ever comes back, this test must say so instead of silently re-reading
    # the overflow numbers as a different failure.
    assert "no legal pose" not in failure.detail, failure.detail


def test_the_end_fallback_no_longer_takes_a_run_the_box_gate_rejected():
    """534 r21/r23 回归：末尾 pre-534 fallback 不得再取被 label-box 闸拒掉的 run。

    一条 label box 盖住全部候选行时：`_place_label_stub` 必须返回 `(None, blockers)`，
    blockers 里逐条点名「layout label box」——它不是从 `clear` 里捡一条画上去。
    同一 label 不带 `label_boxes` 时仍按旧行为给出桩（默认兼容）。
    """
    from boardwise.core.layoutplan import LayoutLabel

    label = declared(
        net="SENSE", text="SENSE", bbox=(20.0, -5.0, 40.0, 5.0), x=0.0, y=0.0,
    )
    built = drawapply._Built()
    # default path (no label_boxes): the old, unchanged behaviour still draws a stub
    stub, _blockers = drawapply._place_label_stub(label, built, {}, [])
    assert stub is not None, "without label_boxes the pre-534 behaviour must stand"
    # with a box over every candidate row there is no legal run
    cover = ("the layout label box of net OTHER", (-500.0, -500.0, 500.0, 500.0))
    stub, blockers = drawapply._place_label_stub(
        label, drawapply._Built(), {}, [], label_boxes=[cover],
    )
    assert stub is None, f"a run was taken over the box anyway: {stub}"
    assert blockers, "the refusal must name what blocked it"
    assert any("layout label box" in line for line in blockers), blockers
    assert all(": " in line for line in blockers), blockers


# ---------------------------------------------------------------- 534 fix r1
# 严格模式（`label_boxes` 非空 = 页面路径）新增「宿主名称行 × 异网导体」硬档：
# 行被异网段内部穿透 >0 的档不是候选；全档耗尽返回 None 并具名。边界相切合法；
# 099d/099f 的合成调用（label_boxes 为空）保持旧梯子与旧 fallback。


def _strict(label, built, boxes=None):
    boxes = [("the layout label box of net OTHER", (40.0, 40.0, 60.0, 50.0))]         if boxes is None else boxes
    return drawapply._place_label_stub(label, built, {}, [], boxes)


# `_row` is defined once, at the top: it is the host's centred row (534 r25), and
# the duplicate that used to sit here returned the pre-r25 measured box instead.


def test_strict_a_row_cut_by_a_foreign_wire_leaves_that_rung():
    """最简横档的行被异网线穿 → 换到后面行不穿的水平档（仍横着念）。

    534 r25：行以锚点居中，``y=0`` 的桩其行是 ``y ∈ [-5, 5]``。旧用例把线放在
    ``y=5``——那正好是新行的**上边界**（旧模型的中间），只相切、不穿透，首档因此
    不再被切。线放到 ``y = WIRE_NAME_ROW/4 = 2.5``：在行内、离边界 2.5，真穿透
    （深度 14.3）。不能放到 ``y=0``：那根线落在锚点本身上，整梯子按「导体落在异网
    导线上」全灭，就看不出「换一档」了。
    """
    label = declared(net="CTS", text="CTS", x=0.0, y=0.0,
                        bbox=(10.0, -5.0, 30.0, 5.0))
    naive = ((0.0, 0.0), (10.0, 0.0))
    row = _row(naive, "CTS")
    quarter = textmetrics.WIRE_NAME_ROW / 4.0
    cutter = PlanDrawWire(net="VCC", points=[(row[0] - 20.0, quarter),
                                             (row[2] + 20.0, quarter)])
    assert drawapply._row_cut(row, "CTS", [cutter]) is not None, (row, cutter)
    stub, blockers = _strict(label, _built(cutter))
    assert stub is not None, blockers
    assert tuple(stub) != naive, stub
    assert drawapply._stub_row_is_horizontal(_run(stub))
    assert drawapply._row_cut(_row(stub, "CTS"), "CTS", [cutter]) is None, (
        stub, _row(stub, "CTS"))


def test_strict_every_row_cut_is_a_named_refusal():
    """全梯子都穿线 → None，blockers 点名「is cut … units through by net」。

    534 r25：行以锚点居中（锚点 ``y=0`` ⇒ 行 ``y ∈ [-5, 5]``），旧用例那两根
    ``y = ±5`` 的线现在正好落在两行的**边界**上，只是相切，一个档都不切；往里收到
    ``y = ±WIRE_NAME_ROW/4 = ±2.5`` 才是真穿透（深度 14.3），而且这两根线同时把竖的
    档切在导线上，梯子才真的全灭。一根线不够：「上 5 再右」的行 ``[0, 10]`` 与
    「下 5 再右」的行 ``[-10, 0]`` 分居锚点两侧，单根 ``y=2.5`` 切不到后者。
    """
    label = declared(net="CTS", text="CTS", x=0.0, y=0.0,
                        bbox=(10.0, -5.0, 30.0, 5.0))
    quarter = textmetrics.WIRE_NAME_ROW / 4.0
    above = PlanDrawWire(net="VCC", points=[(-60.0, quarter), (80.0, quarter)])
    below = PlanDrawWire(net="VCC", points=[(-60.0, -quarter), (80.0, -quarter)])
    stub, blockers = _strict(label, _built(above, below))
    assert stub is None, stub
    assert any("is cut" in line and "VCC" in line for line in blockers), blockers


def test_strict_a_touching_row_is_legal():
    """行与线只在边界相切（内部穿透 0）→ 必须接受，不是穿。

    ``_row`` 现在是宿主行（以锚点居中），``row[3]`` 就是这行墨的**上边界** y=5：
    线压在上面仍然合法。旧模型下 ``row[3]`` 是 y=10，那已经离真墨 5 单位远，本用例
    会退化成「附近有根线」而不是「边界相切」。

    536：首档从 10 抬到 40（``LABEL_STUB_MIN``），naive 跟着换；行仍以锚点居中，
    上边界还是 y=5，所以「压边界」这一刀的位置与判据都没变，只换了桩长。
    """
    label = declared(net="CTS", text="CTS", x=0.0, y=0.0,
                        bbox=(10.0, -5.0, 30.0, 5.0))
    naive = ((0.0, 0.0), (40.0, 0.0))
    row = _row(naive, "CTS")
    touching = PlanDrawWire(net="VCC", points=[(row[0] - 20.0, row[3]),
                                               (row[2] + 20.0, row[3])])
    assert drawapply._row_cut(row, "CTS", [touching]) is None, (row, touching)
    stub, blockers = _strict(label, _built(touching))
    assert stub is not None, blockers
    assert tuple(stub) == naive, stub


def test_non_strict_keeps_the_pre_534_choice():
    """label_boxes 为空（099d/099f 的合成调用）→ 旧选择与旧 fallback 不变。

    用的就是上一条严格用例会换档的那根线（``y = WIRE_NAME_ROW/4``，真穿透首档的行，
    深度 14.3）：严格路径据此换档，非严格路径不查行×线，仍逐字节给出旧选择。
    536：首档从 10 抬到 40（``LABEL_STUB_MIN``）——线仍在行内、仍真穿透，naive 换成
    40；「逐字节给出旧选择」指的是这条路径**当前**的首档，不是 10。
    """
    label = declared(net="CTS", text="CTS", x=0.0, y=0.0,
                        bbox=(10.0, -5.0, 30.0, 5.0))
    naive = ((0.0, 0.0), (40.0, 0.0))
    row = _row(naive, "CTS")
    quarter = textmetrics.WIRE_NAME_ROW / 4.0
    cutter = PlanDrawWire(net="VCC", points=[(row[0] - 20.0, quarter),
                                             (row[2] + 20.0, quarter)])
    assert drawapply._row_cut(row, "CTS", [cutter]) is not None, (row, cutter)
    stub, blockers = drawapply._place_label_stub(label, _built(cutter), {}, [])
    assert tuple(stub) == naive, (stub, blockers)


def test_strict_the_labels_own_box_is_still_an_obstacle():
    """当前 label 自己的盒仍在严格障碍里（不做归属豁免）。

    536：首档从 10 抬到 40，盒必须改成盖住**新首档**的行（旧用例盖的是旧首档 10 的
    行——那在 40 阶梯下已经盖不到首档，``stub != naive`` 会退化成恒真）。盒盖住
    「右 40」的行后，桩退到不碰盒的次档「右 10」。
    """
    label = declared(net="CTS", text="CTS", x=0.0, y=0.0,
                        bbox=(10.0, -5.0, 30.0, 5.0))
    naive = ((0.0, 0.0), (40.0, 0.0))
    row = _row(naive, "CTS")
    own = ("the layout label box of net CTS", (row[0], row[1], row[2], row[3]))
    stub, blockers = _strict(label, _built(), boxes=[own])
    assert stub is not None, blockers
    assert tuple(stub) != naive, stub


def _owned(label_boxes=True):
    """A built picture whose part U1 owns a box big enough to clash with every row."""
    built = _built()
    built.label_owner["U1"] = [("its drawn body", (-200.0, -200.0, 300.0, 300.0))]
    return built


def test_the_survivors_branch_asks_the_row_x_conductor_gate_too():
    """tiers 全被 own-symbol 挡掉后，末尾 survivors 不许把被行×线闸删的档取回来。

    没有这条时：`clear` 里的第一档（right 10）会被异网线穿过，仍被 survivors[0]
    取走 —— 这是 r21 记过的同一形状（box 闸挡住了上面、末尾又放回来）。

    534 r25：right 10 的行以锚点居中，是 ``y ∈ [-5, 5]``（旧模型 ``y ∈ [0, 10]``）。
    旧用例的 ``y=5`` 现在是这行的**上边界**，只相切、不再穿，首档会被原样取回；线收到
    ``y = WIRE_NAME_ROW/4 = 2.5`` 才是真穿透（深度 14.3）。这根线也把竖档切在导体上，
    所以 survivors 剩下的第一枚是「下 5 再右 10」（行 ``y ∈ [-10, 0]``，不穿线、水平）。
    """
    label = declared(net="CTS", text="CTS", x=0.0, y=0.0,
                        bbox=(10.0, -5.0, 30.0, 5.0), part_id="U1")
    quarter = textmetrics.WIRE_NAME_ROW / 4.0
    cutter = PlanDrawWire(net="VCC", points=[(-60.0, quarter), (80.0, quarter)])
    built = _owned()
    built.wires.append(cutter)
    naive = ((0.0, 0.0), (10.0, 0.0))
    naive_row = _row(naive, "CTS")
    assert drawapply._row_cut(naive_row, "CTS", built.wires) is not None, naive_row
    stub, blockers = _strict(label, built)
    assert stub is not None, blockers
    assert tuple(stub) != naive, (stub, blockers)
    assert drawapply._row_cut(_row(stub, "CTS"), "CTS", built.wires) is None, stub
    assert drawapply._stub_row_is_horizontal(_run(stub)), stub


def test_the_survivors_branch_refuses_when_every_run_is_cut():
    """survivors 里全档穿线 → None，且 blockers 具名。

    两根线同样从旧的 ``y = ±5``（新行边界）收到 ``y = ±WIRE_NAME_ROW/4 = ±2.5``：
    一上一下各切掉一条横档的行（``[0, 10]`` 与 ``[-10, 0]``），横的档全灭、竖的档被
    切在导体上，survivors 才真的空。
    """
    label = declared(net="CTS", text="CTS", x=0.0, y=0.0,
                        bbox=(10.0, -5.0, 30.0, 5.0), part_id="U1")
    quarter = textmetrics.WIRE_NAME_ROW / 4.0
    above = PlanDrawWire(net="VCC", points=[(-60.0, quarter), (80.0, quarter)])
    below = PlanDrawWire(net="VCC", points=[(-60.0, -quarter), (80.0, -quarter)])
    built = _owned()
    built.wires.extend([above, below])
    stub, blockers = _strict(label, built)
    assert stub is None, stub
    assert any("is cut" in line for line in blockers), blockers


def _legacy_three_island_payload(payload: dict) -> dict:
    """The pre-migration three-island sheet, derived from the shipped payload (534).

    534's formal sheet is four islands and names D+/D- by `localLabelObligations`.
    The active refusal regression is about the **old** boundary shape, so it is
    rebuilt here explicitly rather than read from any local artifact.
    """
    import copy

    legacy = copy.deepcopy(payload)
    modules = []
    for module in legacy.get("modules", []):
        if module.get("id") == "ch343_power":
            continue
        if module.get("id") == "ch343":
            module["parts"] = ["U1", "C1", "C3"]
        if module.get("id") == "hdr":
            module["parts"] = ["H1", "C4"]
        modules.append(module)
    legacy["modules"] = modules
    legacy["localLabelObligations"] = []
    # The old sheet named D+/D- by one whole wire across the boundary (the policy's
    # `crossModule` label came later); LED_A's own direct-wiring obligation stays.
    direct = [item for item in legacy.get("directWiringObligations", [])]
    direct.append({
        "nets": ["D+", "D-"],
        "note": "legacy three-island fixture: the data pair is stated by one whole "
                "wire across the boundary, not by local-label carriers",
    })
    legacy["directWiringObligations"] = direct
    return legacy
