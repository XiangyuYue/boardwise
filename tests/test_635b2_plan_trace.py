"""635 缝 B 收尾：三条「写了但没人核对」的字段（635B-01 / -06 / -07）。

三条同一个形状——**计划里写了，消费端没有一处读它**：

* **635B-01**（高）`wireOps[*].net` 是**被删那条线在页面上的网名**，写入侧把它交给
  `sch.place_wire`，而回读腿（`moveblock.postcondition_problems`）只问「有没有线结束在这里」，
  从不问「是不是这个网」；网表腿读的是脚，看不见线。于是错网名一路写进去、两条腿都不报。
* **635B-06**（低）`baseline` 的五个计数器**只经由 digest 被间接比**：digest 相等时没人复算这些
  数字，所以文档写完后手改一个计数器，装载与守卫都看不出来。
* **635B-07**（低）`target.connection` 是摘要，逐条 `kind` 才是执行的那份；两者冲突**是设计允许的**
  （一份计划可以混用 wire 与 flag），但报告把摘要印出来、一个字不说。

三条都不是「收紧判据」：01 是让已有的尺子（`wire_endpoints_on_pin` 本来就收 `net`）真正接上，
06 是把「digest 相等」剩下的那点信息逐项花掉，07 按 J3 的口径**只披露不拒绝**。
"""

from __future__ import annotations

import copy

import pytest

import test_037_moveblock as mb37
import test_574_census_digest as c574
import test_634b2_changeplan_halves as halves

from boardwise.core import changeplan as cp
from boardwise.engines import drawapply, moveblock as mb

LIVE = {("U1", "5"): "GROUP_NET", ("U2", "1"): "GROUP_NET"}


# ------------------------------------------------------------------ 635B-01


def test_635b01_a_wire_op_net_that_is_not_text_is_refused_at_load():
    payload = halves._move_payload()
    payload["change"]["wireOps"] = [{
        "primitiveId": "w-1", "kind": "redraw", "net": {"a": 1},
        "pointsBefore": [[0.0, 0.0], [10.0, 0.0]],
        "pointsAfter": [[5.0, 0.0], [10.0, 0.0]],
    }]
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(payload)
    assert "change.wireOps[0].net" in str(exc.value), str(exc.value)


def test_635b01_the_page_that_matches_still_reports_nothing(tmp_path):
    """对照组：`PAGE_AFTER` 的重画线就叫 `GROUP_NET`，与计划写的一致。"""
    _path, plan = mb37._move_plan(tmp_path)
    state = mb.postcondition_problems(plan, geometry=mb37.PAGE_AFTER, live=LIVE)
    assert state == {"live": [], "canvas": []}, state


def test_635b01_a_redrawn_wire_under_another_net_is_a_canvas_problem(tmp_path):
    """错网名的实读：线在那儿、端点也对，但名字不是计划说的那个。"""
    _path, plan = mb37._move_plan(tmp_path)
    wrong = copy.deepcopy(mb37.PAGE_AFTER)
    wrong["wires"][0]["state"]["Net"] = "WRONG_NET"
    state = mb.postcondition_problems(plan, geometry=wrong, live=LIVE)
    message = " ".join(state["canvas"])
    assert "WRONG_NET" in message, message
    assert "635B-01" in message, message
    assert not mb.all_satisfied(state)


def test_635b01_a_missing_wire_keeps_the_old_sentence(tmp_path):
    """对照组：'那儿没线' 与 '那儿有线但叫别的名字' 是两句话，不许被合并掉。"""
    _path, plan = mb37._move_plan(tmp_path)
    empty = copy.deepcopy(mb37.PAGE_AFTER)
    empty["wires"] = []
    state = mb.postcondition_problems(plan, geometry=empty, live=LIVE)
    message = " ".join(state["canvas"])
    assert "no wire ends at" in message, message
    assert "635B-01" not in message, message


def test_635b01_an_unnamed_wire_op_claims_no_name(tmp_path):
    """对照组：页面上的线可以是未命名的，计划写空网名就表示不主张名字。"""
    _path, plan = mb37._move_plan(tmp_path)
    plan.change.wire_ops[0].net = ""
    unnamed = copy.deepcopy(mb37.PAGE_AFTER)
    unnamed["wires"][0]["state"]["Net"] = ""
    state = mb.postcondition_problems(plan, geometry=unnamed, live=LIVE)
    assert state == {"live": [], "canvas": []}, state


# ------------------------------------------------------------------ 635B-06


def test_635b06_the_page_the_digest_matches_reports_no_counter_problem():
    page = c574._page()
    census = drawapply.canvas_census(page)
    plan = c574._plan(census)
    assert drawapply.guard_problems(plan, geometry=copy.deepcopy(page)) == []


@pytest.mark.parametrize(
    "attribute,label",
    [
        ("wire_count", "wireCount"),
        ("netflag_count", "netflagCount"),
        ("netlabel_count", "netlabelCount"),
        ("unnumbered_count", "unnumberedCount"),
        ("pin_count", "pinCount"),
    ],
)
def test_635b06_a_counter_edited_after_the_document_was_written_is_reported(
    attribute, label
):
    """digest 相等 ⇒ 页面就是计划写的那张，所以计数器不等说的是**文档**。"""
    page = c574._page()
    census = drawapply.canvas_census(page)
    plan = c574._plan(census)
    setattr(plan.change.draw_baseline, attribute, getattr(census, attribute) + 1)
    problems = drawapply.guard_problems(plan, geometry=copy.deepcopy(page))
    assert problems, f"{label}: a hand-edited counter passed every guard"
    assert any(label in problem for problem in problems), problems


def test_635b06_a_page_that_differs_is_still_the_page_story():
    """对照组：digest 不等时不追加计数器指控——那是同一个改动的第二次指控。"""
    page = c574._page()
    census = drawapply.canvas_census(page)
    plan = c574._plan(census)
    extra = copy.deepcopy(page)
    extra["wires"].append(
        {"primitiveId": "w-extra", "state": {"Line": [0, 0, 40, 0], "Net": "GND"}}
    )
    problems = drawapply.guard_problems(plan, geometry=extra)
    assert problems and "somebody changed" in problems[0], problems
    assert not any("wireCount" in problem for problem in problems), problems


# ------------------------------------------------------------------ 635B-07


def test_635b07_a_summary_that_disagrees_with_the_connection_is_named():
    payload = halves._add_payload()
    payload["target"]["connection"] = "power-flag"
    plan = cp.ChangePlan.from_jsonable(payload)
    note = cp.connection_summary_conflict(plan)
    assert "'power-flag'" in note, note
    assert "'wire'" in note, note
    assert "635B-07" in note, note


def test_635b07_a_summary_that_matches_says_nothing():
    plan = cp.ChangePlan.from_jsonable(halves._add_payload())
    assert cp.connection_summary_conflict(plan) == ""


def test_635b07_a_mixed_plan_is_not_a_conflict_when_the_summary_is_the_first():
    """设计允许混用：摘要是**第一条**连接，第二条是 flag 不构成冲突。"""
    payload = halves._add_payload()
    payload["change"]["connections"][1]["kind"] = "power-flag"
    payload["target"]["connection"] = "wire"
    plan = cp.ChangePlan.from_jsonable(payload)
    assert cp.connection_summary_conflict(plan) == ""
