"""548D3 §24B：声明串联支路的文字归属——同型臂件联合定侧/档。

实测（548D0 MCU 岛，冻结 547A 库、`seriesBranches` 两条灯支路）：`D1` 本体在
y=35，位号/值行落在**左**侧；`D2` 本体在 y=15，同一对行却被局部的「先适配先赢」
打到**下方** y≈−24..−1 —— 正是 `S4` 值行所在的带，读起来不像 `D2` 的行，而
`partTexts` 给它声明的是 `right`（右道被 `S1`/`S2` 的本体占死，声明本身不可行）。

本文件把 `seriesBranches` 之后的文字合同钉成可从图上重算的判据：

* 同型臂件（同一 `symbolRef` 的两条臂成员）取**同一个侧**，各自按档位放下；
  同一档放不下时以最差档位、再以总档位最小者为选，不允许先到者占第 1 档、
  把另一只挤到最后一档；
* 每只的行块必须压在自己本体的行带上（侧向文字与本体 y 带相交），不许在
  别人的带里冒充可读；行块与本体、与他件、与彼此都不重叠；
* `stated side` 仍是首选：整组同一声明时先试该侧，再按 `TEXT_SIDES`；声明
  不一致时不构成组的声明；
* 没有任何合法排列时**具名拒绝**（`layout-unsat`，点名支路 id 与成员），
  而不是把字放远冒充可读；
* 未声明 `seriesBranches` 的页面走原梯级，几何与旧读数逐字节相同。

几何一律从候选自己的 `texts`/`parts` 重算，SVG 从同一份 plan 渲染后核对。
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from xml.etree import ElementTree

import test_548d_series_reservation as mcu

from boardwise.core.symbolprofile import SymbolPose
from boardwise.engines import drawcompiler as dc
from boardwise.engines import svgpreview

#: 判据容差：同一档上的两个点（≤1 单位）不算位移。
TOLERANCE = 1.0

#: `svgpreview` 的 `<text>`/`<rect>` 都在 SVG 命名空间里，ElementTree 要带前缀找。
_SVG_NS = "http://www.w3.org/2000/svg"

#: 548D3 §24B 的臂成员：两条灯支路的两只 LED 与两只限流电阻。
MEMBERS = ("D1", "D2", "R2", "R3")


def _plan():
    circuit, presentation, result = mcu._compiled()
    assert result.ok, [
        (failure.category, failure.subject, failure.detail)
        for failure in result.failures
    ]
    assert result.candidates, "ok with no candidate"
    return circuit, presentation, result.candidates[0]


def _rows(plan, part_id):
    return [text for text in plan.texts if text.part_id == part_id]


def _block(plan, part_id):
    rows = _rows(plan, part_id)
    assert rows, f"{part_id} has no reference/value rows at all"
    return (
        min(text.bbox[0] for text in rows),
        min(text.bbox[1] for text in rows),
        max(text.bbox[2] for text in rows),
        max(text.bbox[3] for text in rows),
    )


def _body(plan, book, part_id):
    part = next(item for item in plan.parts if item.part_id == part_id)
    profile = book[part.symbol_ref]
    pose = SymbolPose(rotation=int(part.rotation), mirror=part.mirror)
    box = dc._body_box(profile, pose, (part.x, part.y))
    assert box is not None, f"{part_id} draws no body"
    return box


def _extent(plan, book, part_id):
    """The box the ladder itself measures against: body **and** pin tips."""
    part = next(item for item in plan.parts if item.part_id == part_id)
    profile = book[part.symbol_ref]
    pose = SymbolPose(rotation=int(part.rotation), mirror=part.mirror)
    return dc._part_box(profile, pose, (part.x, part.y))


def _side(block, extent):
    """Which side of `extent` the whole row block sits on, or ``""`` if none."""
    candidates = {
        "right": block[0] >= extent[2] - TOLERANCE,
        "left": block[2] <= extent[0] + TOLERANCE,
        "above": block[1] >= extent[3] - TOLERANCE,
        "below": block[3] <= extent[1] + TOLERANCE,
    }
    hits = [side for side, flag in candidates.items() if flag]
    return hits[0] if len(hits) == 1 else ""


def _gap(block, extent):
    """The standoff between a block and its owner's extent, along the side."""
    if _side(block, extent) == "left":
        return extent[0] - block[2]
    if _side(block, extent) == "right":
        return block[0] - extent[2]
    if _side(block, extent) == "above":
        return block[1] - extent[3]
    if _side(block, extent) == "below":
        return extent[1] - block[3]
    return 0.0


def _overlaps(left, right):
    return (
        min(left[2], right[2]) - max(left[0], right[0]) > 0.0
        and min(left[3], right[3]) - max(left[1], right[1]) > 0.0
    )


# ------------------------------------------------------- 真实 MCU 岛：成对一致
def test_the_two_led_arms_read_from_one_side_and_stay_in_their_own_row_band():
    """D1/D2 同侧、各自贴着自己的行带——旧的「D2 掉进 S4 带」不得复现。"""
    _, _, plan = _plan()
    book = mcu._book()
    sides = {
        part_id: _side(_block(plan, part_id), _extent(plan, book, part_id))
        for part_id in ("D1", "D2")
    }
    assert set(sides.values()) == {"left"}, (
        f"the two LED arms do not read from one side: {sides}"
    )
    for part_id in ("D1", "D2"):
        block = _block(plan, part_id)
        body = _body(plan, book, part_id)
        # 行带：侧向文字的 y 带必须与本体的 y 带相交，否则它就是别人带里的字。
        assert min(block[3], body[3]) - max(block[1], body[1]) > 0.0, (
            f"{part_id}'s rows sit outside its own row band: block {block}, "
            f"body {body}"
        )
        gap = _gap(block, _extent(plan, book, part_id))
        assert dc.TEXT_GAP - TOLERANCE <= gap <= (
            dc.TEXT_GAP * dc.TEXT_ESCALATION_STEPS + TOLERANCE
        ), f"{part_id}'s rows stand {gap} from their own extent"


def test_the_two_current_limiting_resistors_read_from_one_side_too():
    """R2/R3 也是同型臂件：一侧、两支互不压、各自贴本体。"""
    _, _, plan = _plan()
    book = mcu._book()
    sides = {
        part_id: _side(_block(plan, part_id), _extent(plan, book, part_id))
        for part_id in ("R2", "R3")
    }
    assert len(set(sides.values())) == 1 and "" not in sides.values(), (
        f"the two current-limiting arms do not read from one side: {sides}"
    )
    for part_id in ("R2", "R3"):
        block = _block(plan, part_id)
        body = _body(plan, book, part_id)
        assert min(block[3], body[3]) - max(block[1], body[1]) > 0.0
        gap = _gap(block, _extent(plan, book, part_id))
        assert dc.TEXT_GAP - TOLERANCE <= gap <= (
            dc.TEXT_GAP * dc.TEXT_ESCALATION_STEPS + TOLERANCE
        ), f"{part_id}'s rows stand {gap} from their own extent"


def test_no_two_rows_of_the_declared_arms_touch_each_other_or_a_body():
    """成对与跨组的行块两两不重叠，也不压四只臂件自己的本体。"""
    _, _, plan = _plan()
    book = mcu._book()
    bodies = {part_id: _body(plan, book, part_id) for part_id in MEMBERS}
    boxes = [(part_id, text.bbox) for part_id in MEMBERS for text in _rows(plan, part_id)]
    for index, (owner, box) in enumerate(boxes):
        for other_owner, other in boxes[index + 1:]:
            assert not _overlaps(box, other), (owner, box, other_owner, other)
        for part_id, body in bodies.items():
            assert not _overlaps(box, body), (owner, box, part_id, body)


def test_the_rendered_svg_prints_the_rows_where_the_plan_measures_them():
    """SVG 印出的坐标必须就是 plan 的盒子：D2 的两行贴在自己左侧的行带上。"""
    _, _, plan = _plan()
    book = mcu._book()
    root = ElementTree.fromstring(svgpreview.render_svg(plan, book))
    printed = sorted(
        (float(node.get("x")), float(node.get("y")))
        for node in root.iter(f"{{{_SVG_NS}}}text")
        if node.text in ("D2", "LED")
    )
    assert len(printed) == 3, printed
    body = _body(plan, book, "D2")
    rows = _rows(plan, "D2")
    assert [row.text for row in rows].count("LED") == 1
    expected = sorted(
        (
            (row.bbox[0] + row.bbox[2]) / 2.0,
            (row.bbox[1] + row.bbox[3]) / 2.0,
        )
        for row in [*rows, *_rows(plan, "D1")]
        if row.text in ("D2", "LED")
    )
    assert len(expected) == 3
    # x = centre_x − box[0]，y = box[3] − centre_y + 3：两个偏移在整张图里相同，
    # 所以「印出来的点 = 量出来的盒子」等价于这两个偏移各自恒定。
    offsets_x = [px - ex for (px, _), (ex, _) in zip(printed, expected)]
    offsets_y = [py + ey for (_, py), (_, ey) in zip(printed, expected)]
    assert max(offsets_x) - min(offsets_x) <= 0.5, (printed, expected)
    assert max(offsets_y) - min(offsets_y) <= 0.5, (printed, expected)
    for row in rows:
        assert min(row.bbox[3], body[3]) - max(row.bbox[1], body[1]) > 0.0, (
            f"D2's row {row.text!r} is printed outside its own row band"
        )
        assert (row.bbox[0] + row.bbox[2]) / 2.0 <= body[0], row.text


# --------------------------------------------------- stated side：首选，不是强拆
def _seat_ctx(sides):
    circuit, presentation = mcu._documents()
    stated = dict(presentation.part_texts)
    stated.update(sides)
    document = SimpleNamespace(
        part_texts=stated,
        series_branches=presentation.series_branches,
        text_placement=presentation.text_placement,
    )
    return SimpleNamespace(presentation=document, circuit=circuit)


#: 两个相距足够远的同型件：任何一侧都可放，断言因此只测「先试哪一侧」。
_FAR_BOXES = {
    "D1": (320.0, 29.5, 360.0, 40.5),
    "D2": (320.0, -200.0, 360.0, -189.0),
}


def test_a_side_the_whole_group_states_is_tried_before_the_ladder_order():
    seats = dc._series_arm_text_seats(
        _seat_ctx({"D1": "below", "D2": "below"}), ("D1", "D2"), _FAR_BOXES, (),
    )
    assert seats is not None
    for part_id, box in _FAR_BOXES.items():
        block = (
            min(item[0] for item in seats[part_id]),
            min(item[1] for item in seats[part_id]),
            max(item[2] for item in seats[part_id]),
            max(item[3] for item in seats[part_id]),
        )
        assert block[3] <= box[1] + TOLERANCE, (part_id, block, box)


def test_statements_that_disagree_are_no_statement_and_the_ladder_order_runs():
    """D1 说 below、D2 说 right：组没有共同声明，回到 `TEXT_SIDES` 的顺序。"""
    seats = dc._series_arm_text_seats(
        _seat_ctx({"D1": "below", "D2": "right"}), ("D1", "D2"), _FAR_BOXES, (),
    )
    assert seats is not None
    for part_id, box in _FAR_BOXES.items():
        block = (
            min(item[0] for item in seats[part_id]),
            min(item[1] for item in seats[part_id]),
            max(item[2] for item in seats[part_id]),
            max(item[3] for item in seats[part_id]),
        )
        assert block[0] >= box[2] - TOLERANCE, (part_id, block, box)


# -------------------------------------------------------- 无合法排列：具名拒绝
def test_a_group_no_side_can_hold_is_refused_by_name_not_drawn_far_away():
    """四个方向到第 4 档都被占死：整页具名拒绝，不产出任何候选。"""
    from dataclasses import replace

    walls = (
        (250.0, -5.0, 320.0, 50.0),
        (366.0, -5.0, 430.0, 50.0),
        (320.0, 45.0, 360.0, 75.0),
        (320.0, -30.0, 360.0, 5.0),
    )
    circuit, presentation = mcu._documents()
    budget = replace(mcu._budget(), keepouts=walls)
    ground = frozenset(
        dc._ground_domain(net.id) for net in circuit.nets if net.cls == "gnd"
    )
    result = dc.compile(
        circuit, presentation, mcu._book(), budget, page_ground_domains=ground,
    )
    assert not result.ok
    assert not result.candidates, "a page with no legal row seat shipped a candidate"
    refused = [
        failure for failure in result.failures
        if failure.category == dc.FAILURE_LAYOUT_UNSAT
        and failure.subject.startswith("$.seriesBranches")
    ]
    assert refused, [(f.category, f.subject) for f in result.failures]
    detail = refused[0].detail
    for arm in ("led1_series", "led2_series"):
        assert arm in refused[0].subject
    for member in ("D1", "D2"):
        assert member in detail
    assert "one side" in detail and refused[0].action


# ------------------------------------------- 未声明：联合定侧一次也不许启动
def test_without_the_declaration_no_arm_group_exists_at_all():
    """`seriesBranches` 为空：分组表就是空的，联合定侧的整条路都不进入。"""
    circuit, declared = mcu._documents()
    _, bare = mcu._documents(declared=False)
    plan = _plan()[2]
    placed = SimpleNamespace(
        origins={part.part_id: (part.x, part.y) for part in plan.parts},
        poses={
            part.part_id: SymbolPose(
                rotation=int(part.rotation), mirror=part.mirror,
            )
            for part in plan.parts
        },
    )
    book = mcu._book()

    def profile(part_id):
        return book[circuit.part(part_id).symbol_ref]

    groups = dc._series_arm_text_groups(
        SimpleNamespace(presentation=declared, circuit=circuit, profile=profile),
        placed,
    )
    assert groups == {
        "D1": ("D1", "D2"), "D2": ("D1", "D2"),
        "R2": ("R2", "R3"), "R3": ("R2", "R3"),
    }
    bare_groups = dc._series_arm_text_groups(
        SimpleNamespace(presentation=bare, circuit=circuit, profile=profile),
        placed,
    )
    assert bare_groups == {}, (
        "an undeclared page entered the joint arm seating: "
        f"{sorted(bare_groups)}"
    )


def test_the_undeclared_page_keeps_its_historical_refusal_and_never_sees_this_batch():
    """未声明页今天的原始拒因（`GND` 旗落 `D1.2`）不许被本批换掉或提前吞掉。"""
    circuit, presentation = mcu._documents(declared=False)
    ground = frozenset(
        dc._ground_domain(net.id) for net in circuit.nets if net.cls == "gnd"
    )
    result = dc.compile(
        circuit, presentation, mcu._book(), mcu._budget(),
        page_ground_domains=ground,
    )
    assert not result.candidates, (
        "an undeclared page gained a candidate — the joint arm seating leaked "
        "into the no-declaration path"
    )
    assert result.failures
    assert result.failures[0].category == dc.FAILURE_LAYOUT_UNSAT
    assert result.failures[0].subject == "GND", (
        "the undeclared refusal changed shape: "
        f"{[(failure.category, failure.subject) for failure in result.failures]}"
    )
    assert not [
        failure for failure in result.failures
        if failure.subject.startswith("$.seriesBranches")
    ]
