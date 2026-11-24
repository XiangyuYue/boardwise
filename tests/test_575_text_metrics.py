"""575 / W-G: the fullwidth advance floor and the render's declared font size.

Two holes from 567-G, both in the text metrics and both measured in
`outputs/hole567/g/REPRO.md`:

- **G-1**: an untabled code point was charged 0.9 em, below a fullwidth glyph's
  1.0 em, so a 20-character CJK/全角 name measured 14.297 canvas units short —
  past L1's 10-unit penetration floor. The floor covers fullwidth scripts and
  colour emoji; every **tabled** advance, ASCII included, is unchanged.
- **G-2**: ``_svg_text_nodes`` parsed each node's own ``font-size`` and dropped
  it, so ``render_box`` always modelled the box at ``RENDER_TEXT_PX``: a 2x node
  and a 1x node measured the same. The declared size now reaches the box and
  scales both dimensions; a node that declares nothing reads exactly as before.

G-3 (same-name labels on one carrier run) is out of this batch.
"""

from __future__ import annotations

import pytest

from boardwise.core import textmetrics
from boardwise.engines import drawlint

RENDER_TEXT_PX = textmetrics.RENDER_TEXT_PX
CANVAS_TEXT_UNITS = textmetrics.CANVAS_TEXT_UNITS


# --------------------------------------------------------------- G-1: the floor

#: One code point per wide class the old 0.9 em charge measured short: CJK
#: ideographs (EAW=W), fullwidth Latin (EAW=F), an ideographic space, and an
#: astral colour emoji.
WIDE_CODE_POINTS = ["电", "容", "Ａ", "Ｂ", "\u3000", "😀"]


def test_fullwidth_code_points_cost_at_least_one_em():
    """G-1: a fullwidth glyph occupies a whole em square; 0.9 em was short."""
    for char in WIDE_CODE_POINTS:
        assert textmetrics.render_width(char) >= RENDER_TEXT_PX, repr(char)


def test_two_character_cjk_name_is_at_least_two_ems():
    """The task's stated lower bound, straight from the repro (G-1)."""
    assert textmetrics.render_width("电容") >= 2 * RENDER_TEXT_PX


def test_twenty_character_fullwidth_name_is_not_short():
    """567-G's measured defect: a 20-char fullwidth name 14.297 units short."""
    name = "输出电容滤波电路" * 2 + "输入滤波"
    assert len(name) == 20
    assert textmetrics.render_width(name) >= 20 * RENDER_TEXT_PX


def test_untabled_code_point_charges_the_conservative_fallback():
    """The fallback itself is the conservative 1.1 em, not the old 0.9."""
    assert textmetrics.TEXT_ADVANCE_EM_FALLBACK == pytest.approx(1.1)


# ------------------------------------------------------- G-1: ASCII is untouched

#: Advance values measured from the table as it stood before 575; the geometry
#: of an ASCII-only box must not move because a *non-ASCII* fallback changed.
ASCII_CASES = {
    "ABCD": 2.778,
    "VCC": 2.111,
    "RXD": 2.111,
    "12": 1.112,
    "100nF": 2.835,
    "GND": 2.222,
    "3V3": 1.779,
    "HVDC": 2.833,
    "N1": 1.278,
    "net-12": 2.835,
}


@pytest.mark.parametrize("text,em", sorted(ASCII_CASES.items()))
def test_ascii_advances_are_the_pinned_old_table_values(text, em):
    """ASCII reads exactly the table it read before 575 (the control case)."""
    assert textmetrics.render_width(text) == pytest.approx(em * RENDER_TEXT_PX)


def test_every_tabled_ascii_character_keeps_its_advance():
    """The seven punctuation marks the table lacks are the *only* ASCII the
    fallback can reach; the 88 it covers must still read the table."""
    tabled = [chr(code) for code in range(32, 127) if chr(code) in textmetrics.TEXT_ADVANCE_EM]
    untabled = [chr(code) for code in range(32, 127) if chr(code) not in textmetrics.TEXT_ADVANCE_EM]
    assert untabled == ["[", "\\", "]", "^", "`", "{", "}"]
    for char in tabled:
        assert textmetrics.render_width(char) == pytest.approx(
            textmetrics.TEXT_ADVANCE_EM[char] * RENDER_TEXT_PX
        )


def test_untabled_ascii_punctuation_keeps_the_old_charge():
    """575 must not move an ASCII-only box: the marks outside the table keep
    the 0.9 em every ASCII render was measured under."""
    for char in "[\\]^`{}":
        assert textmetrics.render_width(char) == pytest.approx(0.9 * RENDER_TEXT_PX), repr(char)
    assert textmetrics.render_width("()[]{}^\\`") == pytest.approx(6.966 * RENDER_TEXT_PX)


# -------------------------------------- 579: the builtin sum *is* the geometry

#: The flyback page's net name whose row 530e/530g/530d fingerprint. 579: 575
#: hand-rolled the accumulator (``em = 0.0`` then ``em += advance``) where this
#: module had always used the builtin ``sum`` over a generator, and the two are
#: **different floats** — the builtin one is compensated, so ``VFB_NF`` totals
#: ``3.834`` em where hand-rolled addition totals ``3.8340000000000005`` (1 ulp
#: high: 27.406743455497388 vs …384 canvas units of row, which the fingerprint
#: stores as a 1.42e-14 move of a bbox corner). That was enough to move the
#: shared flyback geometry and fail the three downstream equality tests.
FLYBACK_NET_NAME = "VFB_NF"


def _builtin_em(text: str) -> float:
    """``text``'s em total as :func:`render_width` must compute it.

    Spelled out in the test rather than imported, so the regression measures the
    arithmetic instead of calling back into the module under test: the **builtin**
    ``sum`` over a generator, table hit first, the ASCII/wide fallback split only
    for a miss.
    """
    return sum(
        textmetrics.TEXT_ADVANCE_EM[ch]
        if ch in textmetrics.TEXT_ADVANCE_EM
        else (
            textmetrics.TEXT_ADVANCE_EM_FALLBACK
            if ord(ch) > 0x7F
            else textmetrics.TEXT_ADVANCE_EM_FALLBACK_ASCII
        )
        for ch in text
    )


@pytest.mark.parametrize(
    "text",
    [
        FLYBACK_NET_NAME,  # the shared flyback fingerprint (530e/530g/530d)
        "17.8k 1% TH",  # a tabled ASCII value row, also 1 ulp apart by hand
        "HVDC",  # a flag name: tabled, 1 ulp the *other* way
        "EE16_3+3_V02",  # the transformer's value row (equal either way)
        "电容",  # wide fallback 1.1 through the same builtin sum
        "()[]{}^\\`",  # ASCII fallback 0.9 through the same builtin sum
        "输出滤波 100nF",  # mixed table/wide/ASCII-space
    ],
)
def test_width_is_the_builtin_sum_exactly(text):
    """``render_width`` is the **builtin** sum times the em — exactly, no
    ``approx``. The rounding is part of the geometry the rest of the suite
    fingerprints, so a hand-rolled accumulator must fail here."""
    assert textmetrics.render_width(text) == _builtin_em(text) * RENDER_TEXT_PX


def test_flyback_net_name_width_is_not_the_hand_rolled_total():
    """The 1 ulp is the whole defect: pin it to the literal so a future
    re-write of the accumulator cannot pass by matching itself."""
    assert textmetrics.render_width(FLYBACK_NET_NAME) == 27.406743455497384
    assert textmetrics.render_width(FLYBACK_NET_NAME) != 27.406743455497388


# ------------------------------------------------- G-2: the declared font size

def _text_node(
    text: str,
    *,
    x: float = 100.0,
    y: float = -300.0,
    size: float | None = None,
    anchor: str = "start",
    fill: str = "#0000FF",
) -> str:
    size_rule = f"font-size:{size!r}px;" if size is not None else ""
    return (
        f'<text style="font-family:\'Arial\';{size_rule}'
        f'font-style:normal;font-weight:normal;fill:{fill};stroke:none;"'
        f' x="{x}" y="{y}" text-anchor="{anchor}"'
        f' transform="rotate(0, {x}, {y})" dominant-baseline="ideographic">'
        f'<tspan xml:space="preserve" x="{x}" dx="0" dy="0">{text}</tspan></text>'
    )


def _svg(*nodes: str) -> str:
    return '<svg xmlns="http://www.w3.org/2000/svg">' + "".join(nodes) + "</svg>"


def _box(node: str) -> tuple[float, float, float, float]:
    boxes = drawlint.text_boxes_from_render(_svg(node))
    assert len(boxes) == 1
    return boxes[0].box


def test_records_keep_the_declared_size():
    """The reader hands the size on — the box builder consumes it, not a copy."""
    sizes = [RENDER_TEXT_PX, 2 * RENDER_TEXT_PX, 7.006200555911909]
    svg = _svg(*[_text_node("ABCD", y=-300.0 - index * 20, size=s) for index, s in enumerate(sizes)])
    records = drawlint._svg_text_records(svg)
    assert [record.size for record in records] == sizes


def test_declared_size_scales_the_box_width():
    """2x declared width → 2x box; 7.0062 → 7.0062/RENDER_TEXT_PX (0.9801)."""
    base = _box(_text_node("ABCD", size=RENDER_TEXT_PX))
    double = _box(_text_node("ABCD", size=2 * RENDER_TEXT_PX))
    native = _box(_text_node("ABCD", size=7.006200555911909))

    base_width = base[2] - base[0]
    assert base_width == pytest.approx(textmetrics.render_width("ABCD"))
    assert (double[2] - double[0]) == pytest.approx(2 * base_width)
    assert (native[2] - native[0]) == pytest.approx(
        base_width * 7.006200555911909 / RENDER_TEXT_PX
    )
    assert (native[2] - native[0]) == pytest.approx(0.9801154586273252 * base_width)


def test_declared_size_scales_the_box_height():
    """The glyphs are drawn bigger, so the row the box models grows with them."""
    base = _box(_text_node("ABCD", size=RENDER_TEXT_PX))
    double = _box(_text_node("ABCD", size=2 * RENDER_TEXT_PX))
    assert (base[3] - base[1]) == pytest.approx(CANVAS_TEXT_UNITS)
    assert (double[3] - double[1]) == pytest.approx(2 * CANVAS_TEXT_UNITS)


@pytest.mark.parametrize("anchor", ["start", "middle", "end"])
def test_scaled_box_anchors_on_the_scaled_width(anchor):
    """start grows right, middle centres, end grows left — at the drawn size."""
    width = textmetrics.render_width("ABCD") * 2
    x, y = 100.0, -300.0
    x0 = {"start": x, "middle": x - width / 2, "end": x - width}[anchor]
    box = _box(_text_node("ABCD", x=x, y=y, size=2 * RENDER_TEXT_PX, anchor=anchor))
    assert box[0] == pytest.approx(x0)
    assert box[2] == pytest.approx(x0 + width)
    assert box[1] == pytest.approx(-y)
    assert box[3] == pytest.approx(-y + 2 * CANVAS_TEXT_UNITS)


def test_undeclared_size_keeps_the_old_box_exactly():
    """No ``font-size`` on the node → the constants, byte for byte (control)."""
    text = "电容 12"
    old = drawlint.render_box(100.0, -300.0, text)
    box = _box(_text_node(text, x=100.0, y=-300.0))
    assert box == old
    assert (box[3] - box[1]) == pytest.approx(CANVAS_TEXT_UNITS)
    assert drawlint._svg_text_records(_svg(_text_node(text)))[0].size == 0.0


def test_zero_declared_size_keeps_the_old_box():
    """``font-size:0px`` reads as "none declared", not as a collapsed box."""
    old = drawlint.render_box(100.0, -300.0, "ABCD")
    assert _box(_text_node("ABCD", size=0.0)) == old


def test_five_field_view_is_still_handed_out():
    """163b's ``render_text_nodes`` and test_111 unpack five fields; the sized
    reader is the box builder's, and the projection stays available."""
    node = _text_node("VCC", size=2 * RENDER_TEXT_PX)
    assert drawlint._svg_text_nodes(_svg(node)) == [(100.0, -300.0, "VCC", "annotation", "start")]
