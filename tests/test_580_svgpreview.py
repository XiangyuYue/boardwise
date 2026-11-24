"""580: the five svgpreview defects the 572-F triage reproduced.

Each group pins *behaviour* the preview was measured to get wrong, so a
regression fails on the defect itself rather than on a byte snapshot:

* F-1 an empty plan rendered ``width="0"`` and its whole caption fell outside
  the viewport;
* F-2 with no page the frame came from the parts alone, so a keep-out, a module
  frame or a lone junction was drawn outside the canvas;
* F-3 ``scale`` multiplied geometry but not font size, stroke width, dash pitch
  or dot radius, so at ``scale=2`` the glyph was half the height of its own
  measured box;
* F-4 the opaque body box was drawn after the wires and junctions, so a wire
  crossing a symbol disappeared;
* F-5 ``rect()`` emitted a negative ``width`` for a reversed box, and SVG does
  not render such a rect at all.

The compatibility controls next to them are the ones the fix must not move: a
stated page is not enlarged by far keep-outs, native art keeps its captured
size (only its origin is scaled), and a normal (non-reversed) drawing keeps its
coordinates.
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
from boardwise.engines import svgpreview

SVG = "{http://www.w3.org/2000/svg}"
PAGE = (0.0, 0.0, 100.0, 100.0)


def _book() -> dict[str, SymbolProfile]:
    return {
        "R-1k": SymbolProfile(
            symbol_ref="R-1k",
            body=(-10.0, -20.0, 10.0, 20.0),
            pins=[SymbolPin(number="1", tip=(0.0, 20.0))],
        ),
    }


def _r1() -> LayoutPlan:
    return LayoutPlan(parts=[LayoutPart(part_id="R1", symbol_ref="R-1k", x=0.0, y=0.0)])


def _root(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def _view(root: ET.Element) -> tuple[float, float]:
    _, _, width, height = (float(value) for value in (root.get("viewBox") or "").split())
    return width, height


def _box(root: ET.Element, stroke: str) -> tuple[float, float, float, float]:
    matches = [node for node in root.iter(f"{SVG}rect") if node.get("stroke") == stroke]
    assert len(matches) == 1, f"expected one rect stroked {stroke}, got {len(matches)}"
    left, top = float(matches[0].get("x")), float(matches[0].get("y"))
    return left, top, float(matches[0].get("width")), float(matches[0].get("height"))


# ---------------------------------------------------------------- F-1 canvas


def test_an_empty_plan_still_gets_a_visible_canvas_with_a_readable_caption() -> None:
    """No geometry: the canvas is at least the margin square, and the caption fits.

    Before the fix the document said ``width="0" height="90" viewBox="0 0 0 90"``
    and all four caption lines were written at ``x=8`` — outside the viewport, so
    the picture was entirely blank.
    """
    svg = svgpreview.render_svg(LayoutPlan(), {})
    assert 'width="0"' not in svg and 'height="0"' not in svg
    root = _root(svg)
    width, height = _view(root)
    assert width >= 2 * svgpreview.PREVIEW_MARGIN
    assert height > 2 * svgpreview.PREVIEW_MARGIN
    assert float(root.get("width")) == width and float(root.get("height")) == height

    caption = [node for node in root.iter(f"{SVG}text") if node.get("x") == "8"]
    assert len(caption) == 4
    assert all(float(node.get("x")) < width for node in caption)
    assert any("compiled plan" in (node.text or "") for node in caption)


def test_a_canvas_that_would_round_to_zero_pixels_is_refused_not_written() -> None:
    """``:.0f`` on a sub-pixel extent used to write another ``width="0"`` silently."""
    with pytest.raises(ValueError, match="(?i)pixel"):
        svgpreview.render_svg(LayoutPlan(), {}, page_box=(0.0, 0.0, 0.4, 100.0))


# ------------------------------------------------------- F-2 content extent


def test_without_a_page_keepouts_and_frames_land_inside_the_viewport() -> None:
    """Both boxes are at the far corner; the frame must be grown to hold them."""
    svg = svgpreview.render_svg(
        _r1(),
        _book(),
        keepouts=[(-200.0, -200.0, -150.0, -150.0)],
        frames=[("FAR", (-300.0, -300.0, -250.0, -250.0))],
    )
    root = _root(svg)
    view_width, view_height = _view(root)
    for stroke in (svgpreview._COLOURS["keepout"], svgpreview._COLOURS["frame"]):
        left, top, width, height = _box(root, stroke)
        assert left >= 0 and top >= 0, stroke
        assert left + width <= view_width and top + height <= view_height, stroke


def test_without_a_page_a_junction_far_from_the_geometry_is_inside_the_viewport() -> None:
    plan = _r1()
    plan.junctions.append(LayoutJunction(net="N1", x=500.0, y=400.0))
    root = _root(svgpreview.render_svg(plan, _book()))
    view_width, view_height = _view(root)
    dots = [node for node in root.iter(f"{SVG}circle")
            if node.get("fill") == svgpreview._COLOURS["junction"]]
    assert len(dots) == 1
    assert float(dots[0].get("cx")) < view_width
    assert float(dots[0].get("cy")) < view_height


def test_a_stated_page_is_not_enlarged_by_far_keepouts_or_frames() -> None:
    """The compat control: only the *no page* path reads the content extent."""
    svg = svgpreview.render_svg(
        _r1(),
        _book(),
        page_box=PAGE,
        keepouts=[(-2000.0, -2000.0, -1900.0, -1900.0)],
        frames=[("FAR", (5000.0, 5000.0, 5100.0, 5100.0))],
    )
    view_width, view_height = _view(_root(svg))
    assert view_width == PAGE[2] - PAGE[0]
    assert view_height > PAGE[3] - PAGE[1]  # the drawing plus its caption strip


def test_a_normal_drawing_keeps_its_coordinates() -> None:
    """The compat control: an unremarkable R1 plan is framed and placed as before."""
    root = _root(svgpreview.render_svg(_r1(), _book(), page_box=None))
    width, _ = _view(root)
    left, top, box_width, box_height = _box(root, svgpreview._COLOURS["bodyEdge"])
    assert (box_width, box_height) == (20.0, 40.0)
    assert (left, top) == (40.0, 40.0)  # body (-10..10, -20..20) in a -50..50 frame
    dots = [(node.get("cx"), node.get("cy")) for node in root.iter(f"{SVG}circle")]
    assert dots == [("50.000", "40.000"), ("50.000", "60.000")]
    assert width == 20 + 2 * svgpreview.PREVIEW_MARGIN


# --------------------------------------------------------- F-3 visual scale


def _drawing() -> LayoutPlan:
    return LayoutPlan(
        parts=[LayoutPart(part_id="R1", symbol_ref="R-1k", x=50.0, y=50.0)],
        segments=[LayoutSegment(net="N1", points=[(0.0, 50.0), (100.0, 50.0)])],
        junctions=[LayoutJunction(net="N1", x=50.0, y=50.0)],
        texts=[LayoutText(kind="value", text="10k", bbox=(20.0, 10.0, 60.0, 20.0))],
    )


def _measures(svg: str) -> dict[str, object]:
    root = _root(svg)
    texts = [node for node in root.iter(f"{SVG}text") if node.get("x") != "8"]
    value = [node for node in texts if (node.text or "") == "10k"][0]
    pin_number = [node for node in texts if (node.text or "") == "1"][0]
    box = [node for node in root.iter(f"{SVG}rect")
           if node.get("stroke") == svgpreview._COLOURS["textBox"]][0]
    circles = list(root.iter(f"{SVG}circle"))
    return {
        "font": float(value.get("font-size")),
        "text_box_stroke": float(box.get("stroke-width")),
        "text_box_dash": [float(item) for item in box.get("stroke-dasharray").split()],
        "text_box_height": float(box.get("height")),
        "pin_number_font": float(pin_number.get("font-size")),
        "wire_stroke": float([node for node in root.iter(f"{SVG}polyline")
                              if node.get("stroke") == svgpreview._COLOURS["wire"]][0]
                             .get("stroke-width")),
        "pin_radius": float([node for node in circles
                             if node.get("fill") == svgpreview._COLOURS["pin"]][0].get("r")),
        "junction_radius": float([node for node in circles
                                  if node.get("fill") == svgpreview._COLOURS["junction"]][0].get("r")),
        "body_stroke": float([node for node in root.iter(f"{SVG}rect")
                              if node.get("fill") == svgpreview._COLOURS["body"]][0]
                             .get("stroke-width")),
    }


def test_scale_magnifies_every_visual_attribute_together_with_the_geometry() -> None:
    """``scale`` is a magnification of the *drawing*, not of its coordinates only."""
    one = _measures(svgpreview.render_svg(_drawing(), _book(), page_box=(0.0, 0.0, 220.0, 160.0)))
    two = _measures(
        svgpreview.render_svg(_drawing(), _book(), page_box=(0.0, 0.0, 220.0, 160.0), scale=2.0)
    )
    assert two["text_box_dash"] == [2 * value for value in one["text_box_dash"]]
    for key in ("font", "text_box_stroke", "text_box_height", "pin_number_font",
                "wire_stroke", "pin_radius", "junction_radius", "body_stroke"):
        assert two[key] == pytest.approx(2 * one[key]), key
    # The glyph-to-box ratio is the one a reviewer reads the drawing with.
    assert two["text_box_height"] / two["font"] == pytest.approx(
        one["text_box_height"] / one["font"]
    )


_ART = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="-15 -10 30 20">
<g c_partid="part"><path d="M -10 0 h 5" style="stroke:#880000;fill:none"/></g></svg>"""


def test_native_art_is_scaled_by_its_own_transform_once() -> None:
    """The compat control: captured art is already at scale, so it is not re-scaled."""
    plan = LayoutPlan(parts=[LayoutPart(part_id="U1", symbol_ref="SYN", x=50.0, y=50.0)])
    book = {"SYN": SymbolProfile(symbol_ref="SYN", body=(-5.0, -5.0, 5.0, 5.0), pins=[])}
    art = svgpreview.NativeSymbolArt(
        symbol_ref="SYN", rotation=0.0, mirror=False, svg=_ART, source="580 synthetic art",
    )

    def rendered(scale: float) -> ET.Element:
        return _root(svgpreview.render_svg(plan, book, page_box=PAGE, scale=scale,
                                           native_art=[art]))

    def scopes(root: ET.Element) -> list[str]:
        return [node.get("transform") for node in root.iter()
                if node.get("data-native-part") == "U1"]

    assert scopes(rendered(1.0)) == ["translate(50.000,50.000) scale(1)"]
    assert scopes(rendered(2.0)) == ["translate(100.000,100.000) scale(2)"]
    for scale in (1.0, 2.0):
        root = rendered(scale)
        paths = list(root.iter(f"{SVG}path"))
        assert len(paths) == 1
        assert paths[0].get("d") == "M -10 0 h 5"
        assert paths[0].get("transform") is None
        assert paths[0].get("style") == "stroke:#880000;fill:none"


# ------------------------------------------------------------ F-4 draw order


def _drawing_order(root: ET.Element) -> list[ET.Element]:
    return list(root)


def test_a_wire_and_a_junction_through_a_body_are_drawn_after_the_body() -> None:
    """An opaque body box drawn last erased the 20 units of wire crossing it."""
    plan = LayoutPlan(
        parts=[LayoutPart(part_id="R1", symbol_ref="R-1k", x=0.0, y=0.0)],
        segments=[LayoutSegment(net="N1", points=[(-60.0, 0.0), (60.0, 0.0)])],
        junctions=[LayoutJunction(net="N1", x=0.0, y=0.0)],
        texts=[LayoutText(kind="value", text="10k", bbox=(30.0, 0.0, 60.0, 10.0))],
    )
    order = _drawing_order(
        _root(svgpreview.render_svg(plan, _book(), page_box=(-70.0, -30.0, 70.0, 50.0)))
    )

    def positions(predicate) -> list[int]:
        return [index for index, node in enumerate(order) if predicate(node)]

    body = positions(lambda node: node.get("fill") == svgpreview._COLOURS["body"])
    wire = positions(lambda node: node.tag == f"{SVG}polyline"
                     and node.get("stroke") == svgpreview._COLOURS["wire"])
    junction = positions(lambda node: node.tag == f"{SVG}circle"
                         and node.get("fill") == svgpreview._COLOURS["junction"])
    value = positions(lambda node: node.tag == f"{SVG}text" and (node.text or "") == "10k")
    assert len(body) == len(wire) == len(junction) == len(value) == 1
    assert body[0] < wire[0] < junction[0] < value[0]
    # The wire still spans the body box it crosses: nothing was dropped instead.
    assert order[wire[0]].get("points") == "10.000,50.000 130.000,50.000"


# -------------------------------------------------------- F-5 reversed boxes


def test_a_reversed_text_box_is_normalised_instead_of_dropped() -> None:
    plan = LayoutPlan(texts=[LayoutText(kind="value", text="BAD",
                                        bbox=(100.0, 60.0, 50.0, 80.0))])
    root = _root(svgpreview.render_svg(plan, {}, page_box=PAGE))
    left, top, width, height = _box(root, svgpreview._COLOURS["textBox"])
    assert (width, height) == (50.0, 20.0)
    assert (left, top) == (50.0, 20.0)
    assert "BAD" in "".join(root.itertext())


def test_reversed_keepout_frame_and_label_boxes_never_emit_a_negative_dimension() -> None:
    plan = LayoutPlan(labels=[LayoutLabel(net="", text="L", bbox=(80.0, 20.0, 60.0, 30.0))])
    root = _root(svgpreview.render_svg(
        plan,
        {},
        keepouts=[(-150.0, -150.0, -200.0, -200.0)],
        frames=[("F", (30.0, 30.0, 10.0, 10.0))],
    ))
    for rect in root.iter(f"{SVG}rect"):
        assert not rect.get("width").startswith("-"), ET.tostring(rect)
        assert not rect.get("height").startswith("-"), ET.tostring(rect)
    left, top, width, height = _box(root, svgpreview._COLOURS["keepout"])
    assert (width, height) == (50.0, 50.0)
    view_width, view_height = _view(root)
    # The content extent is normalised too, or the box would be framed outside.
    assert left >= 0 and top >= 0
    assert left + width <= view_width and top + height <= view_height
