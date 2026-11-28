"""631 缝 B：`pagecompiler` 的输入校验四条（631B-01 / -04 / -05 / -07）。

这四条只对**非法输入**生效，所以它们不动任何合法页的几何——这是本批与
631B-02/-03 分开做的原因。

* **B-01**（高）`grid` / `gap_ladder` / `module_gap` / `frame_padding` 收 `NaN`：
  `v <= 0` 对 NaN 恒 False，于是 NaN 穿到 `_snap` 的 `round()`，抛**未捕获**
  `ValueError` —— 与本编译器「输入问题永不抛」的契约相反。
* **B-04**（低）`max_candidates` / `max_variants` 只比 `< 1`，`3.5` 也是一个「页数」。
* **B-05**（低）`relocate_around_keepouts` 零类型校验，字符串 `"yes"` 等价开启。
* **B-07**（低）`frame_padding` 超过 `PAGE_MARGIN` 时在纸边被钳制、且**静默**
  —— 钳制保留（534 的规矩），但 `compile_page` 的 notes 要说出来。
"""

from __future__ import annotations

import math

import pytest
import test_056_pagecompiler as base

import boardwise.engines.pagecompiler as pc


def budget(**over) -> pc.PageCompileBudget:
    values = {"page_box": (0.0, 0.0, 1170.0, 825.0)}
    values.update(over)
    return pc.PageCompileBudget(**values)


# ------------------------------------------------------------------ 631B-01


@pytest.mark.parametrize(
    "over,expected",
    [
        ({"grid": math.nan}, "nan"),
        ({"module_gap": math.nan}, "nan"),
        ({"frame_padding": math.nan}, "nan"),
        ({"gap_ladder": (math.nan,)}, "nan"),
        ({"gap_ladder": (1.0, math.inf)}, "inf"),
    ],
)
def test_b01_a_non_finite_budget_number_is_refused_by_name(over, expected):
    with pytest.raises(pc.PageCompileError) as exc:
        pc._check_budget(budget(**over))
    assert expected in str(exc.value).lower(), str(exc.value)


def test_b01_the_contract_holds_end_to_end_a_nan_budget_is_a_named_refusal():
    """契约要的是**具名拒绝**，不是 `_snap` 里那条「cannot convert float NaN to integer」。

    修前这条路径抛的是裸 `ValueError`，CLI 只能当崩溃处理；现在抛的是
    `PageCompileError`，也就是这个引擎唯一一种对外的拒绝。
    """
    scene = base.scenes()[1]
    with pytest.raises(pc.PageCompileError) as exc:
        pc.compile_page(
            scene.circuit,
            base.regulator_plus_divider_spec(),
            base.library(),
            budget(grid=math.nan),
        )
    message = str(exc.value)
    assert "finite" in message, message
    assert "NaN to integer" not in message, "这正是修前那条裸 ValueError"


# ------------------------------------------------------------------ 631B-04


@pytest.mark.parametrize("over", [{"max_candidates": 3.5}, {"max_variants": 2.5}])
def test_b04_a_fractional_count_of_pages_is_refused(over):
    with pytest.raises(pc.PageCompileError) as exc:
        pc._check_budget(budget(**over))
    assert "whole number" in str(exc.value), str(exc.value)


def test_b04_true_is_not_a_count_of_pages():
    """`True` 以前只是**碰巧**被拒——它撞的是 floor，不是类型。"""
    with pytest.raises(pc.PageCompileError) as exc:
        pc._check_budget(budget(max_candidates=True))
    assert "whole number" in str(exc.value), str(exc.value)


# ------------------------------------------------------------------ 631B-05


def test_b05_a_switch_that_is_not_a_bool_is_refused():
    with pytest.raises(pc.PageCompileError) as exc:
        pc._check_budget(budget(relocate_around_keepouts="yes"))
    assert "True or False" in str(exc.value), str(exc.value)


def test_b05_a_real_bool_still_passes():
    pc._check_budget(budget(relocate_around_keepouts=True))
    pc._check_budget(budget(relocate_around_keepouts=False))


# ------------------------------------------------------------------ 631B-07


def test_b07_a_padding_the_page_cannot_honour_is_disclosed():
    """钳制照旧，但读者必须知道「多给的那部分没有效果」，而不是自己去量。"""
    scene = base.scenes()[1]
    result = pc.compile_page(
        scene.circuit,
        base.regulator_plus_divider_spec(),
        base.library(),
        budget(frame_padding=1e6),
    )
    text = " ".join(result.notes)
    assert "frame is inset by" in text, text
    assert "no effect" in text, text


def test_b07_the_default_padding_says_nothing_extra():
    """对照组：默认值不该冒出一条「你没兑现」的 note。"""
    scene = base.scenes()[1]
    result = pc.compile_page(
        scene.circuit,
        base.regulator_plus_divider_spec(),
        base.library(),
        budget(),
    )
    assert "no effect" not in " ".join(result.notes), result.notes
