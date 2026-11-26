"""625B — 字宽表缺的七个 ASCII 标点、声明页框下的 caption 裁切（625 缝 B 的洞）。

来源 `outputs/hole625/b/REPRO.md`（625B-04 / 625B-05）。

* 625B-05：`[ \\ ] ^ ` + 三个花括号不在 `TEXT_ADVANCE_EM` 里，`advance()` 把缺项记
  0.9 em（Arial 真值 0.278–0.469），带括号的值框虚胖 1.53 倍；
* 625B-04：声明了 page 框（`page_box` 非 None）时 caption 直接写到视口外，且没有任何
  提示。580 U-06 只修了自帧那一半（`document_width = max(width, caption)`）。

**声明页框不加宽**是既有裁定（`tests/test_580_svgpreview.py:136`，岳的「stated sheet
is the sheet」），所以 625B-04 的修法是**换行**：既不放大声明的纸，也不把字裁掉。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from boardwise.core.layoutplan import LayoutPart, LayoutPlan
from boardwise.core.symbolprofile import SymbolPin, SymbolProfile
from boardwise.core.textmetrics import TEXT_ADVANCE_EM
from boardwise.engines import svgpreview

SVG = "{http://www.w3.org/2000/svg}"

#: Arial 的 advance（units/1000 em），也就是 TEXT_ADVANCE_EM 的同一把尺。
ARIAL_MARKS = {
    "[": 0.278,
    "\\": 0.278,
    "]": 0.278,
    "^": 0.469,
    "`": 0.333,
    "{": 0.334,
    "}": 0.334,
}


def _book() -> dict[str, SymbolProfile]:
    return {
        "R-1k": SymbolProfile(
            symbol_ref="R-1k",
            body=(-10.0, -20.0, 10.0, 20.0),
            pins=[SymbolPin(number="1", tip=(0.0, 20.0))],
        ),
    }


def _plan(note: str = "") -> LayoutPlan:
    return LayoutPlan(
        parts=[LayoutPart(part_id="R1", symbol_ref="R-1k", x=0.0, y=0.0)],
        notes=[note] if note else [],
    )


def _caption(root: ET.Element) -> list[ET.Element]:
    """caption 行的 `<text>`：它们都写在 ``CAPTION_LEFT`` 那一列上。"""
    return [node for node in root.iter(f"{SVG}text") if node.get("x") == "8"]


# ---------------------------------------------------------------- 625B-05


@pytest.mark.parametrize("mark,ems", sorted(ARIAL_MARKS.items()))
def test_a_mark_the_table_lacked_is_measured_not_guessed(mark: str, ems: float) -> None:
    """七个标点走各自的 Arial 真值，不再一律按 0.9 em 兜底。"""
    assert TEXT_ADVANCE_EM[mark] == pytest.approx(ems)


def test_every_printable_ascii_character_now_has_a_measured_advance() -> None:
    """可打印 ASCII 全覆盖：兜底常量从此只对这张表以外的码点生效。"""
    missing = [ch for ch in map(chr, range(0x20, 0x7F)) if ch not in TEXT_ADVANCE_EM]
    assert missing == []


def test_a_bracketed_value_box_shrinks_towards_the_real_glyphs() -> None:
    """`[50V]` 的整框宽度按真值算——修前是 Arial 真值的 1.533 倍（0.9 em 兜底）。"""
    from boardwise.core.textmetrics import RENDER_TEXT_PX, advance

    measured = sum(TEXT_ADVANCE_EM[ch] for ch in "[50V]") * RENDER_TEXT_PX
    guessed = (2 * 0.9 + 2 * TEXT_ADVANCE_EM["5"] + TEXT_ADVANCE_EM["V"]) * RENDER_TEXT_PX
    assert advance("[50V]") == pytest.approx(measured)
    assert guessed / measured == pytest.approx(1.533, abs=1e-3)


# ---------------------------------------------------------------- 625B-04


def test_a_caption_wider_than_a_stated_sheet_is_wrapped_not_clipped() -> None:
    """200 单位的声明页装不下 439 px 的 caption：换行装进去，纸不放大。

    断言的是**没有一行字伸出视口**——按渲染自己的字宽尺量，不是数文件名。
    """
    from boardwise.core.textmetrics import advance

    svg = svgpreview.render_svg(_plan("y" * 140), _book(), page_box=(0.0, 0.0, 200.0, 150.0))
    root = ET.fromstring(svg)
    width = float(root.get("width"))
    assert width == 200.0, "a stated sheet is the sheet; the caption may not enlarge it"

    caption = _caption(root)
    assert len(caption) > 5, "the five-line caption cannot fit 200 units and must be wrapped"
    for node in caption:
        text = node.text or ""
        assert advance(text) + 2 * svgpreview.CAPTION_LEFT <= width + 1e-6, text


def test_a_caption_that_fits_a_generous_sheet_keeps_its_lines_whole() -> None:
    """1170 单位的纸装得下，就没有任何一行被切开（改动只在装不下时发生）。"""
    from boardwise.core.textmetrics import advance

    svg = svgpreview.render_svg(_plan("short note"), _book(), page_box=(0.0, 0.0, 1170.0, 825.0))
    root = ET.fromstring(svg)
    caption = _caption(root)
    assert len(caption) == 5  # four fixed lines + the plan's one note
    assert any("short note" == (node.text or "") for node in caption)
    width = float(root.get("width"))
    for node in caption:
        assert advance(node.text or "") + 2 * svgpreview.CAPTION_LEFT <= width


def test_a_self_framed_document_still_widens_instead_of_wrapping() -> None:
    """没有声明页框时仍是 580 U-06 的契约：文档自己长到 caption 的宽度。"""
    svg = svgpreview.render_svg(_plan("y" * 40), _book())
    root = ET.fromstring(svg)
    width = float(root.get("width"))
    assert width > 100.0
