"""634 缝 A：`pageframe.py` 的七条（634A-01/02/03/04/05/06/07/08）。

**634A-09 不在这里**：它是 legacy `engines.layout.TITLE_BLOCK` 常量，岳 J2.3 裁的是
「停用那条链」而不是改常量，属于另一批。

本批的共同形状是「一个**假设**被当成**读数**写进跨运行的证据」：

* **634A-01/-07** keepouts 只接页框，声明角永远回落 3，而回落值与真 `3` 逐值相同；
  现在 `position=` / `border=` 可以传进来，传不进来时 `notes` 里写明是假设。
* **634A-02/-03** 块比纸大时既不裁剪也不告警，`(0,0,560,450)` 会拿到一条伸出纸外的矩形；
  现在 `title_block_fits` / `MINIMUM_TITLE_BLOCK_PAGE` 给出测量，越界写进 note。
  拒绝落在编译入口（那一批会动 `pagecompiler`/`cli`），不在几何助手里硬拒。
* **634A-04** 边距只读 `Blade Width`：页面只声明 `Border=20` 时块越出图框 10；
  现在回退 `Border` 并说明「块距是按图框推的」。
* **634A-05** `Title Block=0` 的同一张纸，两个 API 一个说没块、一个保留 700×180；
  现在 `has_title_block=False` 是显式输入，两个入口同答。
* **634A-06** note 写「anchored to the declared corner」，而保留角从未被声明；
  现在写的是角号 + `position not read at compile time` + `fits yes/no`。
* **634A-08** 映射表的自述栅格序与表本身冲突（3/4 互换）；现在注释只声称
  「表是按声明写的，只有 3 有渲染实测」，不再声称任何栅格序。
"""

from __future__ import annotations

import pytest

from boardwise.core.pageframe import (
    DEFAULT_TITLE_BLOCK_POSITION,
    MINIMUM_TITLE_BLOCK_PAGE,
    TITLE_BLOCK_SIZE,
    keep_out_note,
    page_keep_out_from_notes,
    title_block_box,
    title_block_fits,
    title_block_from_sheet_attrs,
    title_block_keepouts,
)

A4 = (0.0, 0.0, 1170.0, 825.0)


# ---------------------------------------------------------------- 634A-02/03


def test_a02_a_sheet_smaller_than_the_block_says_so():
    """400×450 会拿到一条左越 310 的矩形；现在同一句话进 notes。"""
    notes: list[str] = []
    keepouts = title_block_keepouts((0.0, 0.0, 400.0, 450.0), notes=notes)
    assert keepouts and keepouts[0][0] < 0, "夹具本身就该是越界的矩形"
    text = " ".join(notes)
    assert "smaller than the block" in text, text
    assert "reaches outside the drawing" in text, text


def test_a03_the_minimum_page_is_the_block_plus_two_insets():
    assert MINIMUM_TITLE_BLOCK_PAGE == (
        TITLE_BLOCK_SIZE[0] + 20.0,
        TITLE_BLOCK_SIZE[1] + 20.0,
    )
    assert title_block_fits(A4) is True
    assert title_block_fits((0.0, 0.0, 400.0, 450.0)) is False
    assert title_block_fits((0.0, 0.0, MINIMUM_TITLE_BLOCK_PAGE[0], MINIMUM_TITLE_BLOCK_PAGE[1])) is True


# ---------------------------------------------------------------- 634A-01/07


def test_a01_a_declared_corner_can_be_handed_in():
    """位置本来只有 `title_block_from_sheet_attrs` 能读到；现在 keepouts 也收。"""
    default = title_block_keepouts(A4)[0]
    declared = title_block_keepouts(A4, position="2")[0]
    assert default != declared, "声明角与默认角必须落成不同矩形，否则这条没接线"
    assert declared == title_block_box(A4, position="2")


def test_a07_an_unread_position_is_marked_as_an_assumption():
    notes: list[str] = []
    rect = title_block_keepouts(A4, position="9", notes=notes)[0]
    assert rect == title_block_keepouts(A4)[0], "矩形仍回落实测角（安全方向）"
    text = " ".join(notes)
    assert "'9' is not a position this build reads" in text, text
    assert "assumed" in text, text


def test_a07_a_declared_three_is_not_an_assumption():
    notes: list[str] = []
    title_block_keepouts(A4, position="3", notes=notes)
    # 没有 attrs 时那条「角是假设的」note 仍然正确；这里否的是**这个值不可读**
    assert not [n for n in notes if "not a position this build reads" in n], notes


# ---------------------------------------------------------------- 634A-04


def test_a04_border_is_the_fallback_when_blade_width_is_not_stated():
    """只声明 `Border=20`：块内边跟随图框内边，而不是默认的 10。"""
    notes: list[str] = []
    box = title_block_from_sheet_attrs({"Width": "1170", "Height": "825", "Border": "20"}, notes=notes)
    assert box is not None
    assert box == (450.0, 20.0, 1150.0, 200.0), box
    assert "`Border`" in " ".join(notes), notes


def test_a04_blade_width_still_wins_when_it_is_stated():
    """对照：`Blade Width=10` 与 `Border=1`（实测页面的常态）不许互相覆盖。"""
    box = title_block_from_sheet_attrs(
        {"Width": "1655", "Height": "1170", "Border": "1", "Blade Width": "10"}
    )
    assert box == (945.0, 10.0, 1645.0, 190.0), box


def test_a04_a_stated_zero_blade_width_is_not_stated():
    """635A-02 的同一条：注释说 non-positive 视为未声明，实现曾经当真值 0。"""
    box = title_block_from_sheet_attrs(
        {"Width": "1170", "Height": "825", "Blade Width": "0", "Border": "20"}
    )
    assert box == (450.0, 20.0, 1150.0, 200.0), box


# ---------------------------------------------------------------- 634A-05


def test_a05_the_two_apis_agree_when_the_page_draws_no_block():
    attrs = {"Width": "900", "Height": "825", "Title Block": "0"}
    assert title_block_from_sheet_attrs(attrs) is None
    notes: list[str] = []
    assert title_block_keepouts((0.0, 0.0, 900.0, 825.0), has_title_block=False, notes=notes) == ()
    assert "no title-block keep-out was reserved" in " ".join(notes), notes


def test_a05_an_unknown_page_still_reserves_the_block_and_says_so():
    notes: list[str] = []
    keepouts = title_block_keepouts(A4, notes=notes)
    assert keepouts, "不知道就保留——这是安全方向"
    assert "assumed" in " ".join(notes), notes


# ---------------------------------------------------------------- 634A-06


def test_a06_the_note_states_what_was_actually_read():
    """note 是跨运行的唯一证据：它不许声称「声明的角」。"""
    note = keep_out_note(A4, title_block_keepouts(A4))
    assert "declared corner" not in note, note
    assert f"corner {DEFAULT_TITLE_BLOCK_POSITION}" in note, note
    assert "position not read at compile time" in note, note
    assert "fits yes" in note, note

    small = keep_out_note((0.0, 0.0, 400.0, 450.0), title_block_keepouts((0.0, 0.0, 400.0, 450.0)))
    assert "fits no" in small, small


def test_a06_the_note_still_parses_back():
    """改的是语义不是格式：landing 侧仍按同一对矩形读回。"""
    page = A4
    keepouts = title_block_keepouts(page)
    assert page_keep_out_from_notes([keep_out_note(page, keepouts)]) == (page, keepouts[0])


# ---------------------------------------------------------------- 634A-08


@pytest.mark.parametrize("position,corner", [("1", (10.0, 635.0)), ("2", (10.0, 10.0)), ("4", (460.0, 635.0))])
def test_a08_the_table_is_read_as_declared(position, corner):
    """表仍是「按声明」，本批只把注释里的栅格序主张去掉；3 是唯一有实测的角。"""
    box = title_block_box(A4, position=position)
    assert (box[0], box[1]) == corner, box
