"""The preview draws a placed text, a net label and a flag's net name at the
host's measured font size, not at the 11-unit diagnostic default.

Source: the y173 native SVG export. ``KEY_C1``, ``RFID_MISO``, ``HALL_LOCK``,
``+3V3``, ``GND`` and ``STM32F103C8T6`` all carry
``font-size:7.006200555911909px`` in the real V4 drawing. The preview rendered
those three kinds with no ``font-size`` of their own, so they inherited the
canvas default of 11: they looked bigger than the drawing they stand in for and
magnified overlaps that the native page does not have. The caption and the other
diagnostic text keep 11 (the canvas default), a pin number keeps its explicit 9
and a frame name its explicit 12.

The geometry checks below pin the exact x/y/width/height the renderer emitted
before this change: only the font size of those three text kinds may move.
"""

from __future__ import annotations

from xml.etree import ElementTree

from boardwise.core.layoutplan import (
    LayoutLabel,
    LayoutPart,
    LayoutPlan,
    LayoutPowerSymbol,
    LayoutText,
)
from boardwise.core.symbolprofile import SymbolPin, SymbolProfile
from boardwise.engines import svgpreview

SVG = "{http://www.w3.org/2000/svg}"

PAGE_BOX = (0.0, 0.0, 200.0, 160.0)


def _plan() -> LayoutPlan:
    return LayoutPlan(
        parts=[LayoutPart(part_id="R1", symbol_ref="R-1k", x=50.0, y=50.0)],
        power_symbols=[
            LayoutPowerSymbol(symbol_ref="PWR-GND", net="GND", x=30.0, y=100.0),
        ],
        texts=[
            LayoutText(kind="value", text="STM32F103C8T6", bbox=(20.0, 20.0, 80.0, 30.0)),
        ],
        labels=[
            LayoutLabel(net="RFID_MISO", text="RFID_MISO", bbox=(100.0, 40.0, 160.0, 50.0),
                        x=100.0, y=40.0),
        ],
    )


def _profiles() -> dict[str, SymbolProfile]:
    return {
        "R-1k": SymbolProfile(
            symbol_ref="R-1k",
            body=(0.0, -5.0, 10.0, 5.0),
            pins=[SymbolPin(number="7", tip=(10.0, 0.0))],
        ),
        # A flag has no pins: its origin is the connection point.
        "PWR-GND": SymbolProfile(symbol_ref="PWR-GND", body=(-10.0, 0.0, 10.0, 19.0)),
    }


def _render(**options: object) -> str:
    return svgpreview.render_svg(
        _plan(), _profiles(), page_box=PAGE_BOX, title="native text", **options
    )


def _texts(svg: str) -> list[ElementTree.Element]:
    return list(ElementTree.fromstring(svg).iter(f"{SVG}text"))


def _by_text(svg: str, content: str) -> ElementTree.Element:
    matches = [node for node in _texts(svg) if (node.text or "") == content]
    assert len(matches) == 1, f"expected exactly one <text>{content}</text>, got {len(matches)}"
    return matches[0]


def test_three_native_text_kinds_use_the_measured_host_font_size() -> None:
    """A placed text, a label and a flag's net name are all 7.006.

    The exact value is the one the real V4 export measured
    (7.006200555911909px); the preview rounds it to three decimals, which is
    what :data:`svgpreview.NATIVE_TEXT_FONT_SIZE` states.
    """
    assert svgpreview.NATIVE_TEXT_FONT_SIZE == 7.006
    svg = _render()
    for content in ("STM32F103C8T6", "RFID_MISO", "GND"):
        assert _by_text(svg, content).get("font-size") == "7.006", content
    seven = [node for node in _texts(svg) if node.get("font-size") == "7.006"]
    assert len(seven) == 3, "only the three host text kinds may be 7.006"


def test_diagnostic_font_sizes_stay_what_they_were() -> None:
    """The 11-unit canvas default, the 12-unit frame name and the 9-unit pin
    number are untouched by the native-text change."""
    assert svgpreview.PREVIEW_FONT_SIZE == 11.0
    assert svgpreview.NATIVE_TEXT_FONT_SIZE != svgpreview.PREVIEW_FONT_SIZE
    svg = _render(frames=[("mcu", (0.0, 120.0, 60.0, 160.0))])
    root = ElementTree.fromstring(svg)
    assert root.get("font-size") == "11"
    # Caption lines start at x=8 and carry no font-size of their own: they
    # inherit the canvas's 11.
    caption = [node for node in _texts(svg) if node.get("x") == "8"]
    assert len(caption) == 4
    assert all(node.get("font-size") is None for node in caption)
    assert _by_text(svg, "mcu").get("font-size") == "12"
    assert _by_text(svg, "7").get("font-size") == "9"


def test_only_the_font_size_of_the_three_text_nodes_moves() -> None:
    """Everything else stays at the exact coordinates the renderer emitted.

    With the same plan and an explicit page box the drawing is deterministic, so
    the text baselines, the dashed font-metric boxes and the label anchor dot are
    asserted numerically: a change to any of them is a geometry change, not this
    batch's font-size change.
    """
    svg = _render()
    text = _by_text(svg, "STM32F103C8T6")
    # centre (50, 25) -> SVG y = 160 - 25 + 3
    assert (text.get("x"), text.get("y")) == ("50.000", "138.000")
    label = _by_text(svg, "RFID_MISO")
    # centre (130, 45) -> SVG y = 160 - 45 + 3
    assert (label.get("x"), label.get("y")) == ("130.000", "118.000")
    flag = _by_text(svg, "GND")
    # 6 units right of the anchor, 4 above it
    assert (flag.get("x"), flag.get("y")) == ("36.000", "56.000")

    rects = list(ElementTree.fromstring(svg).iter(f"{SVG}rect"))
    text_box = [node for node in rects if node.get("stroke-dasharray") == "2 2"]
    # text bbox (20,20,80,30) then label bbox (100,40,160,50)
    assert [(n.get("x"), n.get("y"), n.get("width"), n.get("height")) for n in text_box] == [
        ("20.000", "130.000", "60.000", "10.000"),
        ("100.000", "110.000", "60.000", "10.000"),
    ]
    circles = list(ElementTree.fromstring(svg).iter(f"{SVG}circle"))
    # flag anchor, pin tip, part origin, label anchor (the part loop draws the
    # pin tip before the placed origin)
    assert [(n.get("cx"), n.get("cy")) for n in circles] == [
        ("30.000", "60.000"),
        ("60.000", "110.000"),
        ("50.000", "110.000"),
        ("100.000", "120.000"),
    ]
