"""634 缝 B：`changeplan` 解析的四条高洞（634B-01…-04）。

四条同一个形状：**一个字段被读了两遍，两遍的判据不一样**。

* **B-01/-02** `attachment.at` 在 insert 路径走 `_insert_independent_point`（严查、缺了具名拒），
  在 **patch-pin 路径**是手写的 `float(at[0])`：`float("a")` 变成**裸 `ValueError`**（CLI 只 catch
  `ChangePlanError`，于是是 traceback 而不是 exit 5 的具名拒绝），`True` 变成坐标 1，
  **缺失**则存成 `None` —— 「证明这个附着物落在哪个脚上」的那个坐标，在移动引脚的分支里成了可选。
* **B-03** `draw.parts[].pins == []` 被接受。054 §一 protection 3 **就是**「拿这份偏移去和编辑器
  的脚位逐脚比」；零个期望脚不是「小的检查」，是**每只脚都通过**。
* **B-04** `target.designators` 不做类型检查就迭代：`5` 抛裸 `TypeError`，`"R1"` 被逐字符拆成
  `R` 与 `1`，变成 `'R, 1'` —— 两个假位号进了计划。
"""

from __future__ import annotations

import pytest

import test_035_patchpin as pp

from boardwise.core import changeplan as cp

SOURCE = pp._source()


def patch_pin_payload(attachment: dict) -> dict:
    plan = pp.patch_pin_plan(
        SOURCE,
        designator="U3",
        pin="4",
        before_net="NET4",
        after_net="",
        attachment=cp.PlanAttachment(
            kind="wire", primitive_id="w1", detail="endpoint on the pin", at=(10.0, 20.0)
        ),
    )
    payload = plan.to_jsonable()
    payload["change"]["attachment"] = attachment
    return payload


# ---------------------------------------------------------------- 634B-01/-02


def test_b01_an_attachment_without_its_coordinate_is_refused():
    """缺 `at` 曾被静默接受成 `None`——那个坐标正是这条附着物的全部证明。"""
    payload = patch_pin_payload({"kind": "wire", "primitiveId": "w1"})
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(payload)
    message = str(exc.value)
    assert "change.attachment.at" in message, message
    assert "coordinate that proves" in message, message


def test_b02_a_non_number_coordinate_is_a_named_refusal_not_a_value_error():
    """`float("a")` 曾抛裸 `ValueError`，而 CLI 只接 `ChangePlanError`。"""
    payload = patch_pin_payload({"kind": "wire", "primitiveId": "w1", "at": "a"})
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(payload)
    assert "change.attachment.at" in str(exc.value), str(exc.value)


def test_b02_a_bool_is_not_a_coordinate():
    """`True` 曾是坐标 1：同一个 `isinstance(x, (int, float))` 漏法。"""
    payload = patch_pin_payload({"kind": "wire", "primitiveId": "w1", "at": [True, 0.0]})
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(payload)
    assert "change.attachment.at" in str(exc.value), str(exc.value)


def test_b01_a_real_coordinate_still_round_trips():
    """对照组：合法的两点坐标不许被这次收紧挡掉。"""
    payload = patch_pin_payload(
        {"kind": "wire", "primitiveId": "w1", "at": [10.0, 20.0]}
    )
    back = cp.ChangePlan.from_jsonable(payload)
    assert back.change.attachment is not None
    assert back.change.attachment.at == (10.0, 20.0)


# ------------------------------------------------------------------ 634B-03


def test_b03_a_part_with_no_expected_pins_is_refused():
    with pytest.raises(cp.ChangePlanError) as exc:
        cp._draw_pins_from([], "draw.parts[0]")
    message = str(exc.value)
    assert "is empty" in message, message
    assert "protection 3" in message, message


def test_b03_a_missing_pins_key_still_says_it_is_missing():
    """对照组：'缺' 与 '空' 是两句不同的话，不许被这次收紧合并掉。"""
    with pytest.raises(cp.ChangePlanError) as exc:
        cp._draw_pins_from(None, "draw.parts[0]")
    assert "is missing" in str(exc.value), str(exc.value)


# ------------------------------------------------------------------ 634B-04


@pytest.mark.parametrize("raw", [5, "R1", ("U1", "U2"), [1, 2]])
def test_b04_designators_must_be_a_list_of_strings(raw):
    with pytest.raises(cp.ChangePlanError) as exc:
        cp._move_target_from({"designators": raw})
    message = str(exc.value)
    assert "must be a list of designator strings" in message, message
