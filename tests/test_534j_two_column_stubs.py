"""053J/534B 续六：相邻引脚的名字桩交替取首档与第二列，名字落进两条 x 带。

CH343 页（`evidence/534i/render_p13.png`）的 U1 左列 RI/CTS/DSR/RTS/DTR/DCD 六枚
桩都取 40 直桩，六行名字挤在同一个 x 带里（`evidence/534i/changeplan.json`
`wires[34,37,38,39,40,41]` 全是 470→430）。本批只在
:func:`boardwise.engines.drawapply._label_stub_candidates` 的档位分配上动手：页面
严格路径（`near_stagger`）且图面声明了 `stubMin` 与 `rowModel=centered`、标签盒在
引脚**水平**一侧时，按引脚自身所在行（`WIRE_NAME_ROW` 的奇偶，偶数行先深）交替
把「首档」与「第二列档」（首档 +
:data:`boardwise.engines.drawapply.LABEL_STUB_COLUMN_PITCH`，40 → 100）排进首选
直桩的前两位。

钉住四件事：

1. 相邻引脚的**首选**直桩长交替，页面上真的画成两条带；
2. 默认/非严格路径（`near_stagger=False`）的直桩候选逐点不变，100 不出现；
3. `stubMin`/`rowModel` 未声明（或不齐）时严格路径也保持旧序列，100 不出现；
4. 旧候选全部保留、相对顺序不变——100 只增补，不替换；100 被挡时 40 与原有短桩
   仍由**现有** chooser 选中（chooser 本身不改）。
"""

from __future__ import annotations

import types

import pytest

from boardwise.core.changeplan import PlanDrawWire
from boardwise.core.layoutplan import LayoutLabel
from boardwise.engines import drawapply

#: 053J: pins on the left of U1 at x = 470, the compiler's text box 50 units to
#: their left, the document's stated floor 40 and a centred row.
X = 470.0
FLOOR = 40.0
DEEP = 100.0
#: The rungs the ladder carries below/above the head, in the ladder's own order
#: (`LABEL_STUB_LENGTHS`, then 12 and 16 lattice steps).
RUNGS = (10.0, 5.0, 15.0, 20.0, 30.0, 40.0, 60.0, 80.0)
OLD_RUNGS = (40.0, 10.0, 5.0, 15.0, 20.0, 30.0, 60.0, 80.0)


def _old_order(head: float) -> list[float]:
    """The ladder a label with this head had before 053J — unchanged."""
    return [head] + [rung for rung in RUNGS if rung != head]


def _label(y: float, net: str = "RI", **kwargs) -> LayoutLabel:
    kwargs.setdefault("stub_min", FLOOR)
    kwargs.setdefault("row_model", "centered")
    return LayoutLabel(
        net=net, text=net, x=X, y=float(y),
        bbox=(420.0, y - 5.0, 430.0, y + 5.0), **kwargs,
    )


def _preferred(runs) -> list[float]:
    """The straight runs on the label's own side, as stub lengths."""
    return [
        run.points[-1][0] - X
        for run in runs
        if len(run.points) == 2 and run.side == (-1.0, 0.0)
    ]


def _preferred_abs(runs) -> list[float]:
    return [abs(length) for length in _preferred(runs)]


# ------------------------------------------------ 1. the page: two bands, in turn

#: The CH343's left column, top to bottom, as the plan states it
#: (`evidence/534i/changeplan.json`): adjacent rows are one text row apart.
COLUMN = (("RI", 740.0), ("RTS", 710.0), ("DSR", 720.0),
          ("CTS", 730.0), ("DTR", 700.0), ("DCD", 690.0))


def test_adjacent_pins_take_the_head_and_the_deep_rung_in_turn():
    """相邻同侧引脚的首选直桩 40/100 交替，页面上是两条 x 带。"""
    firsts = []
    for net, y in COLUMN:
        runs = drawapply._label_stub_candidates(_label(y, net), near_stagger=True)
        lead = _preferred_abs(runs)[:2]
        assert set(lead) == {FLOOR, DEEP}, (net, y, lead)
        firsts.append(lead[0])
    for before, after in zip(firsts, firsts[1:]):
        assert before != after, firsts
    assert sorted(set(firsts)) == [FLOOR, DEEP], firsts


def test_the_page_draws_the_two_bands():
    """整列一起选（现有 chooser 不动）：选中的桩长交替，名字行落进两条带。"""
    boxes = [
        (f"the layout label box of net {net}",
         (420.0, y - 5.0, 430.0, y + 5.0))
        for net, y in COLUMN
    ]
    built = drawapply._Built()
    chosen = []
    for net, y in COLUMN:
        mine = (420.0, y - 5.0, 430.0, y + 5.0)
        stub, blockers = drawapply._place_label_stub(
            _label(y, net), built, {}, [],
            [box for box in boxes if box[1] != mine],
        )
        assert stub is not None, (net, blockers)
        far = tuple(stub[-1])
        assert far[1] == y
        chosen.append(X - far[0])
    # Empty page (no foreign ink): the even rows go deep first, so the column
    # reads 100/40/100/40/100/40 top to bottom.
    assert chosen == [DEEP, FLOOR, DEEP, FLOOR, DEEP, FLOOR], chosen
    # Two bands, half a column pitch apart: the shift is not a rounding wobble.
    bands = sorted({length for length in chosen})
    assert bands == [FLOOR, DEEP]
    assert (bands[1] - bands[0]) / 2.0 == drawapply.LABEL_STUB_COLUMN_PITCH / 2.0


# ------------------------------- 2. the default path keeps the pre-053J ladder


def test_the_default_path_keeps_every_rung_point_for_point():
    """非严格路径（099d/099f 合成调用）的直桩候选逐点仍是旧序列。"""
    assert _preferred_abs(drawapply._label_stub_candidates(_label(740.0))) == (
        list(OLD_RUNGS)
    )


def test_the_default_path_never_buys_the_second_column():
    """非严格路径不出现 100：整条阶梯里没有任何候选的端点落在 370。"""
    for y in (740.0, 730.0):
        runs = drawapply._label_stub_candidates(_label(y))
        assert all(abs(run.points[-1][0] - X) != DEEP for run in runs), y


# --------------------------- 3. undeclared switches keep the strict ladder too


@pytest.mark.parametrize("kwargs", [
    {"stub_min": 0.0, "row_model": "centered"},
    {"stub_min": FLOOR, "row_model": "anchored"},
    {"stub_min": 0.0, "row_model": "anchored"},
])
def test_undeclared_policy_keys_keep_the_old_order(kwargs):
    """只写一个（或不写）开关：严格路径也保持旧序列，100 不出现。"""
    runs = drawapply._label_stub_candidates(
        _label(730.0, **kwargs), near_stagger=True,
    )
    assert DEEP not in _preferred_abs(runs), kwargs
    # With no stated floor the head is the box's own reach (two lattice steps,
    # 10) — 057's rung, unchanged.
    head = FLOOR if kwargs["stub_min"] else 2.0 * drawapply.DRAW_GRID
    assert _preferred_abs(runs) == _old_order(head), kwargs


@pytest.mark.parametrize("floor", [10.0, 30.0, 60.0, 80.0])
def test_other_stated_floors_keep_their_old_ladder(floor):
    """别的 stubMin 档（10/30/60/80）：严格路径与默认路径逐点一致，无第二列。

    053J 的两列只在本批声明的 40 楼层上测过；60 的头 + pitch = 120、80 的头 +
    pitch = 140 都不是旧阶梯里的档，若按「写了 floor 就分两列」放行，等于给这些
    既有文档新增首选——任务书要求它们的旧候选序列逐点不动。
    """
    plain = _preferred(drawapply._label_stub_candidates(_label(730.0, stub_min=floor)))
    strict = _preferred(
        drawapply._label_stub_candidates(
            _label(730.0, stub_min=floor), near_stagger=True,
        )
    )
    assert strict == plain, floor
    assert [abs(length) for length in strict] == _old_order(floor), floor
    assert DEEP not in [abs(length) for length in strict], floor


def test_a_label_without_the_keys_reads_as_the_old_drawing():
    """连属性都没有的对象（旧 plan、SimpleNamespace）：首档 10，无 100。"""
    legacy = types.SimpleNamespace(
        net="RI", text="RI", x=X, y=730.0,
        bbox=(420.0, 725.0, 430.0, 735.0),
    )
    runs = drawapply._label_stub_candidates(legacy, near_stagger=True)
    assert _preferred_abs(runs) == [10.0, 5.0, 15.0, 20.0, 30.0, 40.0, 60.0, 80.0]


# ------------------------------------- 4. old rungs survive, order and fallback


@pytest.mark.parametrize("y", [740.0, 730.0])
def test_every_old_rung_survives_in_its_old_order(y):
    """100 是**增补**：去掉它以后，序列与默认路径逐项相同。"""
    plain = _preferred(drawapply._label_stub_candidates(_label(y)))
    strict = _preferred(drawapply._label_stub_candidates(_label(y), near_stagger=True))
    assert [length for length in strict if length != -DEEP] == plain
    assert len(strict) == len(plain) + 1


@pytest.mark.parametrize("y", [740.0, 730.0])
def test_a_blocked_second_column_falls_back_to_the_head(y):
    """100 被挡时，现有 chooser 仍能选到 40（及原有短桩）——chooser 不改。"""
    label = _label(y)
    built = drawapply._Built()
    built.wires.append(PlanDrawWire(
        net="V3", points=[(400.0, 760.0), (400.0, 680.0)],
    ))
    stub, blockers = drawapply._place_label_stub(
        label, built, {}, [], [("a box elsewhere", (0.0, 0.0, 10.0, 10.0))],
    )
    assert stub is not None, blockers
    assert tuple(tuple(point) for point in stub) == (
        (X, y), (X - FLOOR, y),
    )
    assert any(reason.startswith("left 100") for reason in blockers), blockers


def test_a_free_second_column_is_written_without_a_blocker():
    """无遮挡时深先行真的走到 100：不是「只排了队、chooser 永远不选」。"""
    built = drawapply._Built()
    stub, blockers = drawapply._place_label_stub(
        _label(740.0), built, {}, [],
        [("a box elsewhere", (0.0, 0.0, 10.0, 10.0))],
    )
    assert stub is not None, blockers
    assert tuple(tuple(point) for point in stub) == (
        (X, 740.0), (X - DEEP, 740.0),
    )


def test_the_real_page_column_falls_back_only_where_the_100_is_blocked():
    """真页（P14 plan）的一整列：谁拿到了干净的 100，谁被墨挡回 40。

    `evidence/534j/plan-inverted.json` 的读数（未 apply）：RI740=40、CTS730=40、
    DSR720=100、RTS710=40、DTR700=100、DCD690=40。**DSR/DTR 这两枚 100 落在干净
    走廊**（没有任何墨与导体挡它）；CTS/RI 的 100 候选被 VCC 竖线
    `(410,750)-(410,725)` 挡回 40，RTS 的 100 候选被 VCC 旗标名字盒
    `(402.455,705)-(417.545,715)` 挡回 40。所以这不是「六枚都能 100」的合成空场景，
    而是「空地深先行、被挡才回 40」的落档证据。
    """
    boxes = [
        (f"the layout label box of net {net}",
         (420.0, y - 5.0, 430.0, y + 5.0))
        for net, y in COLUMN
    ]
    boxes.append(("the flag name row of VCC", (402.455, 705.0, 417.545, 715.0)))
    built = drawapply._Built()
    built.wires.append(PlanDrawWire(
        net="VCC", points=[(410.0, 750.0), (410.0, 725.0)],
    ))
    chosen = []
    for net, y in COLUMN:
        mine = (420.0, y - 5.0, 430.0, y + 5.0)
        stub, blockers = drawapply._place_label_stub(
            _label(y, net), built, {}, [],
            [box for box in boxes if box[1] != mine],
        )
        assert stub is not None, (net, blockers)
        chosen.append((net, X - tuple(stub[-1])[0]))
    assert dict(chosen) == {
        "RI": FLOOR, "CTS": FLOOR, "DSR": DEEP,
        "RTS": FLOOR, "DTR": DEEP, "DCD": FLOOR,
    }, chosen


# ------------------------------ 5. the sheet's left edge bounds the second column


def _label_at(x: float, y: float, net: str = "CTS") -> LayoutLabel:
    """A label of the page's shape whose text box is 20–30 units left of its pin."""
    return LayoutLabel(
        net=net, text=net, x=float(x), y=float(y),
        bbox=(x - 30.0, y - 5.0, x - 20.0, y + 5.0),
        stub_min=FLOOR, row_model="centered",
    )


def _preferred_from(runs, x: float) -> list[float]:
    return [
        run.points[-1][0] - x
        for run in runs
        if len(run.points) == 2 and run.side == (-1.0, 0.0)
    ]


@pytest.mark.parametrize("y", [360.0, 350.0])
def test_a_column_too_close_to_the_left_edge_never_buys_the_second_column(y):
    """H3 的形状（x=60，左列）：100 的落点会是 x=-40，图幅外——候选根本不新增。

    真机 lint 读数（`evidence/534j/lint.json`，L10-out-of-bounds）：H3 左列
    CTS/DSR/RI/RXD 在 x=60，偶数行的 100 深档把桩尾画到 x=-40。两列是版式收益，
    不是电气事实，越出图幅的候选连排队都不该排——整条阶梯回到旧序列。
    """
    x = 60.0
    assert x < DEEP, "the fixture must be within one pitch of the origin"
    plain = _preferred_from(drawapply._label_stub_candidates(_label_at(x, y)), x)
    strict = _preferred_from(
        drawapply._label_stub_candidates(_label_at(x, y), near_stagger=True), x,
    )
    assert strict == plain, y
    assert DEEP not in [abs(length) for length in strict], y


def test_the_left_edge_is_about_room_not_about_the_part():
    """x=100 恰好留够一个 pitch：偶数行首档就是 100，桩尾正落在 x=0。"""
    runs = drawapply._label_stub_candidates(_label_at(100.0, 360.0), near_stagger=True)
    first = _preferred_from(runs, 100.0)[0]
    assert first == -DEEP
    assert 100.0 + first == 0.0
