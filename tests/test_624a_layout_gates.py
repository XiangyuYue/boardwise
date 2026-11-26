"""624A — legacy 直出链的三条洞：零引脚件折行、`validate_full` 的 `if p.bbox`、栅格外引脚。

来源 `outputs/hole624/a/REPRO.md`（624A-01/02/03）。三条都在 `engines/layout.py` 的
self-check 面：计划被判「可执行」而件在图纸框外，是这批最贵的错。

* **624A-01**（高）：`_pack` 的 pin-less 分支只把光标右移，从不设 `row_height`、从不问
  `wraps()`，于是 16 件线性右移、4 件出页（最远 x=1400，页右界 1159），`violations=[]`；
* **624A-02**（高）：`validate_full` 的 `boxes = [... if p.bbox]` 让缺框件对约束 1
  结构性不可见——放在页外也零 violation，只在 `plan.notes` 留一句话；
* **624A-03**（中）：引脚偏移不在 5 单位栅格上时，走线端点只能落在格点上（`U2.1` 真尖端
  `(142,160)`、端点 `(140,160)`），阻塞码 `ENDPOINT_NOT_TERMINAL` 的文案只说「不是引脚尖端」，
  根因（符号栅格）没人知道。
"""

from __future__ import annotations

import pytest

from boardwise.core.model import Component, DesignModel, Net, Pin
from boardwise.engines import generate as G
from boardwise.engines import layout as L

#: 页右界 / 上界：`SHEET_WIDTH - FRAME` 与 `SHEET_HEIGHT - FRAME`。
RIGHT = L.SHEET_WIDTH - L.FRAME
TOP = L.SHEET_HEIGHT - L.FRAME


def _zero_pin_model(n: int = 16) -> tuple[DesignModel, dict[str, dict[str, tuple[float, float]]]]:
    """``n`` 个零引脚件 + 两个正常件连成一条网（624A-01 的探针形状）。"""
    comps: dict[str, Component] = {
        f"MH{i}": Component(f"mh{i}", f"MH{i}", "HOLE", pins=[]) for i in range(n)
    }
    comps["U1"] = Component("u1", "U1", "R", pins=[Pin("1", "1", "N1")])
    comps["U2"] = Component("u2", "U2", "R", pins=[Pin("1", "1", "N1")])
    nets = {"N1": Net("N1", [("U1", "1"), ("U2", "1")])}
    offsets = {"U1": {"1": (0.0, 0.0)}, "U2": {"1": (0.0, 0.0)}}
    return DesignModel(components=comps, nets=nets), offsets


# ---------------------------------------------------------------- 624A-01


def test_pinless_parts_wrap_instead_of_walking_off_the_sheet() -> None:
    """零引脚件参与折行：16 件不再把光标推到 x=1400。

    修前读数（REPRO §624A-01）：`frame right=1159`，`placements beyond frame: 4`，
    最远 `MH9 at x=1400 y=140`，而 `violations=[]`——计划被判可执行。
    """
    model, offsets = _zero_pin_model(16)
    plan = G.generate_plan(model, offsets, None)
    beyond = [(p.designator, p.x, p.y) for p in plan.placements if p.x > RIGHT or p.y > TOP]
    assert beyond == [], f"placements outside the frame: {beyond}"
    assert [v for v in plan.violations if v.code == "OUT_OF_SHEET"] == []


def test_the_first_bounded_part_after_pinless_ones_still_judges_the_row_height() -> None:
    """pin-less 件落位后 `row_height` 不再是 0：紧随其后的有界件照样会折行。

    修前这条分支 `continue` 时不设 `row_height`，所以同一行里第一个有界件不会触发
    `wraps()`（REPRO 因果②）。
    """
    model, offsets = _zero_pin_model(30)
    plan = G.generate_plan(model, offsets, None)
    rows = {p.y for p in plan.placements}
    assert len(rows) > 1, f"30 pin-less parts must wrap, got rows at {sorted(rows)}"
    assert all(p.x <= RIGHT and p.y <= TOP for p in plan.placements)


# ---------------------------------------------------------------- 624A-02


def test_a_pinless_placement_outside_the_sheet_is_a_violation() -> None:
    """缺框件对约束 1 不再隐形：按**原点**判越界，并说清这一判据。

    修前读数（TRIAGE §0.2）：`n = 1`，唯一一条来自有框件；同一份计划里无框件放在
    x=1400 也零 violation。
    """
    model = DesignModel()
    placements = [
        # 页内的有框件：对照，不该报
        L.Placement("U1", 40.0, 140.0, L.Rect(20.0, 120.0, 120.0, 200.0)),
        # 有框、出页：修前就会报
        L.Placement("OUT1", 1400.0, 140.0, L.Rect(1380.0, 120.0, 1480.0, 200.0)),
        # 无框、同一个位置：修前整条被 `if p.bbox` 丢掉
        L.Placement("MH9", 1400.0, 140.0, None),
    ]
    violations = L.validate_full(model, placements, [], {}, annotation_anchors=[])
    out = [v for v in violations if v.code == "OUT_OF_SHEET"]
    assert sorted(v.subject for v in out) == ["component MH9", "component OUT1"]
    by_subject = {v.subject: v for v in out}
    assert "origin" in by_subject["component MH9"].detail, by_subject["component MH9"].detail


def test_a_pinless_placement_on_the_title_block_is_a_violation() -> None:
    """缺框件压在标题栏上也要说；标题栏是禁地（520o/岳的裁决）。"""
    model = DesignModel()
    placements = [L.Placement("MH9", L.TITLE_BLOCK[0] + 5.0, L.TITLE_BLOCK[1] + 5.0, None)]
    violations = L.validate_full(model, placements, [], {}, annotation_anchors=[])
    assert [v.code for v in violations] == ["PLACEMENT_ON_TITLE_BLOCK"]


def test_a_pinless_placement_inside_the_sheet_stays_clean() -> None:
    """对照：页内的缺框件不产生任何 violation（缺框本身不是错误）。"""
    model = DesignModel()
    placements = [L.Placement("MH9", 200.0, 300.0, None)]
    assert L.validate_full(model, placements, [], {}, annotation_anchors=[]) == []


# ---------------------------------------------------------------- 624A-03


def _pair(offsets: dict[str, dict[str, tuple[float, float]]]) -> DesignModel:
    comps = {
        "U1": Component("u1", "U1", "R", pins=[Pin("1", "1", "N1")]),
        "U2": Component("u2", "U2", "R", pins=[Pin("1", "1", "N1")]),
    }
    return DesignModel(components=comps, nets={"N1": Net("N1", [("U1", "1"), ("U2", "1")])})


def test_an_off_grid_pin_tip_is_named_with_its_root_cause() -> None:
    """引脚偏移不在 5 单位栅格上：点名 `OFF_GRID_SYMBOL`，而不是只说「不是引脚尖端」。

    修前读数（REPRO §624A-03）：`U2.1 true tip (142,160)`，走线端点 `(140,160)`，违规只有
    `ENDPOINT_NOT_TERMINAL`——读者看不出根因是符号栅格。
    """
    offsets = {"U1": {"1": (0.0, 0.0)}, "U2": {"1": (2.0, 0.0)}}
    plan = G.generate_plan(_pair(offsets), offsets, None)
    rows = [v for v in plan.violations if v.code == "OFF_GRID_SYMBOL"]
    assert rows, [v.code for v in plan.violations]
    assert "U2.1" in rows[0].subject, rows[0].subject
    assert "5" in rows[0].detail, rows[0].detail


def test_a_grid_aligned_symbol_adds_no_off_grid_row() -> None:
    """对照：栅格上的符号（出货库 220 个引脚尖端全是 5 的倍数）不产生这一行。"""
    offsets = {"U1": {"1": (0.0, 0.0)}, "U2": {"1": (0.0, 40.0)}}
    plan = G.generate_plan(_pair(offsets), offsets, None)
    assert [v for v in plan.violations if v.code == "OFF_GRID_SYMBOL"] == []


def test_the_off_grid_row_is_blocking() -> None:
    """它是阻塞码：一条能读出来的错位不许被当成建议。"""
    assert "OFF_GRID_SYMBOL" not in L.ADVISORY_VIOLATION_CODES
