"""572F: the five ``svgpreview`` defects 572-F reproduced, re-read on 961b3b7.

572-F measured them on ``f5083286`` (677-line module). 565d (``961b3b7``) rewrote
the drawing path, so each case is re-read before anything is changed:

* **F-1** an empty plan rendered ``width="0"`` and the whole caption fell outside
  the viewport. 565d gave it the 80-unit margin square — still narrower than every
  caption line, which *also* clips. Fixed here: with nothing to frame, the
  document is widened to hold its own caption.
* **F-2** with no page the frame came from the parts alone, so a keep-out, a
  module frame or a lone junction was drawn outside the canvas — already fixed by
  565d's ``_content_box``; pinned here so it cannot come back.
* **F-3** ``scale`` multiplied geometry but not font size or dot radius, so at
  ``scale=2`` the glyph was half the height of its own measured box — already
  fixed by 565d's ``px()``; pinned here. The base em stays
  ``NATIVE_TEXT_FONT_SIZE`` (7.006, the host's native-text class), not the
  render's 7.148: that split is deliberate and pinned by
  ``test_svgpreview_native_text`` / ``test_svgpreview_label_carrier``.
* **F-4** the opaque body box was drawn after the wires and junctions, so a wire
  crossing a symbol disappeared — already fixed by 565d's draw order; pinned here.
* **F-5** ``rect()`` emitted a negative ``width`` for a reversed box, and SVG does
  not render such a rect at all — already fixed by 565d's ``_normalised_box``;
  pinned here.

Every assertion reads the *emitted document*, not a helper's return value, and the
caption width is measured with the host's own metric table
(:func:`boardwise.core.textmetrics.advance`) rather than with the renderer's.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest

from boardwise.core.layoutplan import (
    LayoutJunction,
    LayoutLabel,
    LayoutPart,
    LayoutPlan,
    LayoutSegment,
    LayoutText,
)
from boardwise.core.symbolprofile import SymbolPin, SymbolProfile
from boardwise.core.textmetrics import RENDER_TEXT_FAMILY, RENDER_TEXT_PX, advance
from boardwise.engines import svgpreview

SVG = "{http://www.w3.org/2000/svg}"


def _book() -> dict[str, SymbolProfile]:
    return {
        "R-1k": SymbolProfile(
            symbol_ref="R-1k",
            body=(-10.0, -20.0, 10.0, 20.0),
            pins=[SymbolPin(number="1", tip=(0.0, 20.0))],
        ),
    }


def _root(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def _view(root: ET.Element) -> tuple[float, float]:
    _, _, width, height = (float(value) for value in (root.get("viewBox") or "").split())
    return width, height


def _caption(root: ET.Element) -> list[ET.Element]:
    return [
        node
        for node in root.iter(f"{SVG}text")
        if float(node.get("x") or 0) == svgpreview.CAPTION_LEFT
    ]


# ------------------------------------------------- F-1: a canvas that holds it


def test_an_empty_plan_gets_a_canvas_wide_enough_for_its_own_caption() -> None:
    """Nothing is drawn, so the caption is the content and must not be clipped.

    Read on 961b3b7: ``width="80" height="170" viewBox="0 0 80 170"`` with the
    caption at ``x=8``, its widest line 384.6px wide — every line ran past the
    viewport, so the picture still said nothing (572-F-1 read ``width="0"``
    before 565d gave it the margin square).
    """
    svg = svgpreview.render_svg(LayoutPlan(), {})
    assert 'width="0"' not in svg and 'height="0"' not in svg

    root = _root(svg)
    width, height = _view(root)
    assert float(root.get("width")) == width, "the attribute and the viewBox must agree"
    assert width > 2 * svgpreview.PREVIEW_MARGIN, (
        "the margin square alone is narrower than the caption it carries"
    )

    caption = _caption(root)
    assert len(caption) == 4
    assert any("compiled plan" in (node.text or "") for node in caption)
    for node in caption:
        text = node.text or ""
        end = float(node.get("x")) + advance(
            text, RENDER_TEXT_FAMILY, svgpreview.PREVIEW_FONT_SIZE
        )
        assert end <= width, f"caption {text!r} ends at {end:.1f}, canvas is {width:.0f}"
        assert float(node.get("y")) + svgpreview.PREVIEW_FONT_SIZE <= height, "baseline below the strip"


def test_a_self_framed_drawing_is_as_wide_as_its_caption() -> None:
    """U-06: for a self-framed preview the caption decides the width when it is wider.

    572-F pinned a *drawing's* canvas at its own frame and the caption past that
    edge was clipped; its docstring named ``test_580``'s
    ``width == 20 + 2 * PREVIEW_MARGIN`` as the thing to keep. U-06 grows the
    document to ``max(drawing, caption)`` when no sheet is stated, and the
    coordinate compatibility 572-F was protecting is pinned where it belongs —
    `test_580`'s box/pin-dot assertions, which are unchanged. Measured on this
    tree (2026-11-26): a 100-unit drawing gets a 404.0-unit document, and every
    caption line ends inside it.
    """
    plan = LayoutPlan(parts=[LayoutPart(part_id="R1", symbol_ref="R-1k", x=0.0, y=0.0)])
    root = _root(svgpreview.render_svg(plan, _book()))
    width, height = _view(root)
    assert width == 404.0
    caption = _caption(root)
    assert caption, "the strip carries the caption this width is for"
    for node in caption:
        text = node.text or ""
        end = float(node.get("x")) + advance(
            text, RENDER_TEXT_FAMILY, svgpreview.PREVIEW_FONT_SIZE
        )
        assert end <= width, f"caption {text!r} ends at {end:.1f}, canvas is {width:.0f}"
        assert float(node.get("y")) + svgpreview.PREVIEW_FONT_SIZE <= height, (
            "baseline below the strip")


# ------------------------------- F-2: the frame holds every box, page or not


def test_without_a_page_every_drawn_box_lands_inside_the_canvas() -> None:
    """A keep-out, a module frame and a lone junction are all part of the extent.

    Read on f5083286 (572-F-2): the keep-out was drawn at ``x="-150"`` in a
    100-unit canvas because ``_content_box`` only looked at the parts.
    """
    plan = LayoutPlan(
        parts=[LayoutPart(part_id="R1", symbol_ref="R-1k", x=0.0, y=0.0)],
        junctions=[LayoutJunction(net="N1", x=400.0, y=-300.0)],
    )
    root = _root(
        svgpreview.render_svg(
            plan,
            _book(),
            keepouts=[(-200.0, -200.0, -150.0, -150.0)],
            frames=[("FAR", (-300.0, -300.0, -250.0, -250.0))],
        )
    )
    view_width, view_height = _view(root)
    skip = {svgpreview._COLOURS["background"], svgpreview._COLOURS["page"]}
    for node in root.iter(f"{SVG}rect"):
        if node.get("fill") in skip:
            continue
        left, top = float(node.get("x")), float(node.get("y"))
        box_width, box_height = float(node.get("width")), float(node.get("height"))
        assert left >= 0 and top >= 0, ET.tostring(node)
        assert left + box_width <= view_width and top + box_height <= view_height, ET.tostring(node)
    for node in root.iter(f"{SVG}circle"):
        assert 0 <= float(node.get("cx")) <= view_width, ET.tostring(node)
        assert 0 <= float(node.get("cy")) <= view_height, ET.tostring(node)


# --------------------------------- F-3: scale magnifies the whole drawing


def _scale_measures(scale: float) -> dict[str, float]:
    plan = LayoutPlan(
        parts=[LayoutPart(part_id="R1", symbol_ref="R-1k", x=50.0, y=50.0)],
        junctions=[LayoutJunction(net="N1", x=50.0, y=50.0)],
        texts=[LayoutText(kind="value", text="10k", bbox=(20.0, 10.0, 60.0, 20.0))],
    )
    root = _root(svgpreview.render_svg(plan, _book(), page_box=(0.0, 0.0, 140.0, 80.0), scale=scale))
    glyph = [node for node in root.iter(f"{SVG}text") if (node.text or "") == "10k"][0]
    box = [
        node for node in root.iter(f"{SVG}rect")
        if node.get("stroke") == svgpreview._COLOURS["textBox"]
    ][0]
    junction = [
        node for node in root.iter(f"{SVG}circle")
        if node.get("fill") == svgpreview._COLOURS["junction"]
    ][0]
    return {
        "font": float(glyph.get("font-size")),
        "box_height": float(box.get("height")),
        "box_stroke": float(box.get("stroke-width")),
        "dot_radius": float(junction.get("r")),
    }


def test_scale_magnifies_glyphs_and_dots_not_only_coordinates() -> None:
    """At ``scale=2`` the glyph used to stay 7.006 while its box doubled.

    Read on f5083286 (572-F-3): ``font-size`` 7.006 at both scales, ``r`` 2.2 at
    both. The base em is the host's own native-text class, and the printed label
    row's em is the render's — both from ``core.textmetrics``, neither invented
    here.
    """
    one = _scale_measures(1.0)
    two = _scale_measures(2.0)

    assert one["font"] == pytest.approx(svgpreview.NATIVE_TEXT_FONT_SIZE)
    assert svgpreview.LABEL_ROW_FONT_SIZE == RENDER_TEXT_PX
    for key in ("font", "box_height", "box_stroke", "dot_radius"):
        assert two[key] == pytest.approx(2 * one[key]), key
    # The ratio a reviewer reads the drawing with: glyph height over its box.
    assert two["box_height"] / two["font"] == pytest.approx(one["box_height"] / one["font"])


# ----------------------------------------- F-4: conductors over opaque bodies


def test_a_wire_and_a_junction_crossing_a_body_are_drawn_after_the_body() -> None:
    """An opaque body drawn last erased the 20 units of wire crossing it.

    Read on f5083286 (572-F-4): ``polyline`` index 11, junction 12, body rect 13.
    """
    plan = LayoutPlan(
        parts=[LayoutPart(part_id="R1", symbol_ref="R-1k", x=0.0, y=0.0)],
        segments=[LayoutSegment(net="N1", points=[(-60.0, 0.0), (60.0, 0.0)])],
        junctions=[LayoutJunction(net="N1", x=0.0, y=0.0)],
    )
    root = _root(svgpreview.render_svg(plan, _book(), page_box=(-70.0, -40.0, 70.0, 40.0)))
    order = list(root)

    def position(predicate) -> int:
        hits = [index for index, node in enumerate(order) if predicate(node)]
        assert len(hits) == 1, f"expected exactly one element, got {hits}"
        return hits[0]

    body = position(lambda node: node.get("fill") == svgpreview._COLOURS["body"])
    wire = position(lambda node: node.tag == f"{SVG}polyline")
    junction = position(
        lambda node: node.tag == f"{SVG}circle"
        and node.get("fill") == svgpreview._COLOURS["junction"]
    )
    assert body < wire < junction
    # Nothing was dropped instead: the wire still spans the body it crosses.
    assert order[wire].get("points") == "10.000,40.000 130.000,40.000"


# ------------------------------------------- F-5: a reversed box is normalised


def test_a_reversed_box_is_normalised_and_never_emits_a_negative_dimension() -> None:
    """A reversed bbox used to emit ``width="-50"``, which SVG does not render.

    Read on f5083286 (572-F-5): ``<rect x="150.000" y="40.000" width="-50.000"/>``
    — the text box vanished while its glyphs stayed, so the reader could not see
    that the box was gone.
    """
    plan = LayoutPlan(
        texts=[LayoutText(kind="value", text="BAD", bbox=(100.0, 60.0, 50.0, 80.0))],
        labels=[LayoutLabel(net="", text="L", bbox=(80.0, 20.0, 60.0, 30.0))],
    )
    root = _root(
        svgpreview.render_svg(
            plan,
            {},
            page_box=(0.0, 0.0, 120.0, 120.0),
            keepouts=[(-150.0, -150.0, -200.0, -200.0)],
            frames=[("F", (30.0, 30.0, 10.0, 10.0))],
        )
    )
    for rect in root.iter(f"{SVG}rect"):
        assert float(rect.get("width")) >= 0, ET.tostring(rect)
        assert float(rect.get("height")) >= 0, ET.tostring(rect)

    box = [
        node for node in root.iter(f"{SVG}rect")
        if node.get("stroke") == svgpreview._COLOURS["textBox"]
    ][0]
    assert (float(box.get("x")), float(box.get("y"))) == (50.0, 40.0)
    assert (float(box.get("width")), float(box.get("height"))) == (50.0, 20.0)
    assert "BAD" in "".join(root.itertext())
