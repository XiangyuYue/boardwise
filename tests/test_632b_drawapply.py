"""632 缝 B：`drawapply` 的六条纯函数洞（632B-01…-06）。

每条对应 `outputs/hole632/b/REPRO.md` 里那一节，断言钉在**结构化读数或那一句
特定文本**上，不钉「有没有报错」这种在变异下仍然绿的东西：

* **B-01**（高）kept-name 计划的**计划内重名**位号：`designator_problems` 曾对
  两件都叫 `C10` 的计划返回 `[]`，apply 于是两件一起落图；
* **B-02**（中）CJK 前缀曾让 `allocate_designator` 抛裸 `ValueError`，CLI 七处
  `except drawapply.DrawPlanError` 全部接不住；
* **B-03**（中）符号只认 `PWR-` 前缀，宿主自带的 `GND` 让 `("VCC","GND")` 静默判 Power；
* **B-04**（中）`int(rotation)` 把 90.7 截成 90，`nan` 抛裸 `ValueError`；
* **B-05**（低）摘要描述的是库的**写法顺序**，`int(True)` 还是 1 号候选；
* **B-06**（低）`_prefix_of` 取全串字母（`Q1_b` -> `QB`），与自己的 docstring 相反。
"""

from __future__ import annotations

import dataclasses

import pytest

from boardwise.core import symbolprofile as sp
from boardwise.core.changeplan import DRAW_MODULE_KIND, ChangePlan, PlanChange, PlanDrawPart
from boardwise.core.layoutplan import LayoutPart
from boardwise.engines import drawapply


def _build(cls, **values):
    names = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in values.items() if k in names})


def _plan(parts, keep_names):
    return ChangePlan(
        change=_build(
            PlanChange,
            kind=DRAW_MODULE_KIND,
            candidate=0,
            draw_parts=parts,
            draw_keep_names=keep_names,
        )
    )


def _draw_part(spec_id, designator, prefix="C", symbol_ref="R0402"):
    return _build(
        PlanDrawPart,
        spec_id=spec_id,
        designator=designator,
        prefix=prefix,
        symbol_ref=symbol_ref,
        part_id=spec_id,
        x=0.0,
        y=0.0,
        rotation=0,
        mirror=False,
        lcsc="C25744",
        value="10n",
        pins=[],
    )


def _layout_part(part_id, symbol_ref="R0402"):
    return _build(
        LayoutPart,
        part_id=part_id,
        spec_id=part_id,
        symbol_ref=symbol_ref,
        x=0.0,
        y=0.0,
        rotation=0,
        mirror=False,
    )


PROFILE = sp.SymbolProfile.from_dict(
    {
        "symbolRef": "R0402",
        "body": (-10.0, -5.0, 10.0, 5.0),
        "pins": [
            {"number": "1", "name": "A", "tip": (-20.0, 0.0), "direction": "left"},
            {"number": "2", "name": "B", "tip": (20.0, 0.0), "direction": "right"},
        ],
    }
)
PROFILES = {"R0402": PROFILE}


# ------------------------------------------------------------------ 632B-01


def test_b01_two_parts_under_one_kept_name_are_named_as_a_plan_defect():
    """keep_names 的两件 `C10`：问题表必须非空，并且说的是**计划内**重名。

    旧读数 `('return', [])`；对照（非 keep 的同构输入）走分配腿，报的是
    「the pool now allocates C2 …」——两条腿各说各的，不能互相顶替。
    """
    problems = drawapply.designator_problems(
        _plan([_draw_part("C10", "C10"), _draw_part("C10", "C10")], True), []
    )
    assert len(problems) == 1, problems
    message = problems[0]
    assert "C10" in message
    assert "for both" in message, message
    assert "kept-name plan" in message, message


def test_b01_the_allocation_leg_still_says_its_own_sentence():
    """对照组：非 keep 计划不许被新的计划内重名腿改口径。"""
    problems = drawapply.designator_problems(
        _plan([_draw_part("C1", "C1"), _draw_part("C1", "C1")], False), []
    )
    assert problems and "the pool now allocates C2" in problems[0], problems


# ------------------------------------------------------------------ 632B-02


def test_b02_a_cjk_spec_id_does_not_escape_as_a_bare_value_error():
    """`电阻1` 曾抛 `ValueError`（`_DESIGNATOR_PREFIX_RE`），CLI 接不住。

    修法是只认 ASCII 字母，于是落到符号自己的前缀（`R0402` -> `R`）。
    """
    assigned = drawapply.assign_designators(
        [_layout_part("电阻1")], PROFILES, [], keep_names=False
    )
    assert assigned == [("电阻1", "R", "R1")], assigned


# ------------------------------------------------------------------ 632B-03


def test_b03_a_ground_symbol_beside_a_power_name_is_refused():
    """`("VCC", "GND")`：符号说地、网名说电源——143d 判据不该依赖 `PWR-` 拼写。"""
    with pytest.raises(drawapply.DrawPlanError) as exc:
        drawapply.flag_kind("VCC", "GND")
    assert "GND" in str(exc.value) and "Power" in str(exc.value), str(exc.value)

    # 同族：`PWR-GND` 仍然拒（143d 原样），地网配地符号仍然放行
    with pytest.raises(drawapply.DrawPlanError):
        drawapply.flag_kind("VCC", "PWR-GND")
    assert drawapply.flag_kind("GND", "GND") == drawapply.DRAW_FLAG_GROUND
    # 无符号时不变：网名自己说话，认不出的名字仍然返回空串交给调用方拒
    assert drawapply.flag_kind("VCC", "") == drawapply.DRAW_FLAG_POWER
    assert drawapply.flag_kind("XYZ", "") == ""


# ------------------------------------------------------------------ 632B-04


def test_b04_a_fractional_rotation_is_refused_not_truncated():
    """90.7 曾与 90 **逐字相同**：期望坐标描述的是一套编辑器的角度，不是它画的那个。"""
    with pytest.raises(drawapply.DrawPlanError) as exc:
        drawapply.posed_pin_offsets(PROFILE, 90.7, False)
    assert "90.7" in str(exc.value), str(exc.value)

    assert drawapply.posed_pin_offsets(PROFILE, 90, False) == (
        drawapply.posed_pin_offsets(PROFILE, 90.0, False)
    )
    # -90 与 270 是同一个朝向：折到同一格，不许因为写法被拒
    assert drawapply.posed_pin_offsets(PROFILE, -90, False) == (
        drawapply.posed_pin_offsets(PROFILE, 270, False)
    )


def test_b04_a_nan_rotation_is_a_plan_error_not_a_value_error():
    """`float('nan')` 曾抛裸 `ValueError`，而 CLI 只 catch `DrawPlanError`。"""
    with pytest.raises(drawapply.DrawPlanError):
        drawapply.posed_pin_offsets(PROFILE, float("nan"), False)
    with pytest.raises(drawapply.DrawPlanError):
        drawapply.posed_pin_offsets(PROFILE, 45, False)


# ------------------------------------------------------------------ 632B-05


def test_b05_the_digest_describes_the_library_not_the_order_it_arrived_in():
    """同一张库表，两种写法 → 一个 `inputSha256`（`SOURCE_BASIS` 说「one string」）。"""
    pairs = [("R0402", "a" * 64), ("C0603", "b" * 64)]
    forward = drawapply.source_digest("c" * 64, "d" * 64, "e" * 64, 1, pairs)
    reversed_ = drawapply.source_digest("c" * 64, "d" * 64, "e" * 64, 1, list(reversed(pairs)))
    assert forward == reversed_


def test_b05_a_bool_candidate_is_not_candidate_one():
    """`int(True) == 1`，于是 `candidate=True` 与 `candidate=1` 曾同一份摘要。"""
    with pytest.raises(ValueError) as exc:
        drawapply.source_digest("c" * 64, "d" * 64, "e" * 64, True, [])
    assert "bool" in str(exc.value), str(exc.value)


# ------------------------------------------------------------------ 632B-06


def test_b06_the_prefix_is_the_leading_letters_not_every_letter():
    """`Q1_b -> QB` 让工程师在图上找不到 `Q1_b`；docstring 一直写的是前导字母。"""
    assert drawapply._prefix_of("Q1_b", PROFILE) == "Q"
    assert drawapply._prefix_of("R_EXT1", PROFILE) == "R"
    assert drawapply._prefix_of("U1_RX", PROFILE) == "U"
    # 纯数字开头的 spec id 仍然落回符号自己的前缀（既有行为）
    assert drawapply._prefix_of("10R", PROFILE) == "R"
