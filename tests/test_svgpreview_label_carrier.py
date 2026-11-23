"""A label's name is previewed in the row its **carrier** prints it in.

Source: an independent visual review of the native-font preview (y173 page) rejected
``RFID_MISO``/``MOSI``/``SCK``/``NSS`` as "the names hang off their stubs". The four
J7 labels all anchor at ``x=827.75`` while their static boxes reach ``x=780`` /
``x=782.5``, and the preview centred every label's text in that static box — 36-48
units away from the name stub. The real V4 drawing prints those names on the wire:

* ``RFID_MOSI`` / ``RFID_SCK`` / ``RFID_NSS`` at ``x=822.75`` — the midpoint of each
  10-unit name stub ``827.75 -> 817.75``, start-anchored;
* ``RFID_MISO`` at ``x=752.75`` — the midpoint of *its* longest run
  (``832.75 -> 672.75``, the detour), not of the short run at the anchor.

That is the measured host rule ``core.textmetrics.wire_name_row`` on the carrier the
landing names (``core.layoutplan.label_wire_indices``), and ``readability
._named_wire_rows`` already models it. The preview now reads the same fact: the
numbers below are the y173 canvas units, so a regression to "centre it in the static
box" fails on the first assertion.
"""

from __future__ import annotations

from xml.etree import ElementTree

from boardwise.core.layoutplan import (
    LayoutLabel,
    LayoutPlan,
    LayoutSegment,
    TEXT_MODE_NATIVE,
)
from boardwise.core.textmetrics import WIRE_NAME_ROW, render_width
from boardwise.engines import svgpreview

SVG = "{http://www.w3.org/2000/svg}"

#: A window on the y173 page around the DUT header, so the real coordinates are
#: used unshifted and ``x(value)``/``y(value)`` are simple subtractions.
PAGE_BOX = (700.0, 980.0, 900.0, 1100.0)

#: The four J7 RFID labels, exactly as the page states them: one anchor, one static
#: box that ends 40+ units to the left of it.
RFID = {
    "RFID_MOSI": (1023.0, (716.5, 1018.5, 780.0, 1027.5)),
    "RFID_SCK": (1013.0, (724.0, 1008.5, 782.5, 1017.5)),
    "RFID_NSS": (1003.0, (724.0, 998.5, 782.5, 1007.5)),
    "RFID_MISO": (1033.0, (716.5, 1028.5, 780.0, 1037.5)),
}

#: Each label's own carrier, as ``page.plan.json`` states it (the four 10-unit name
#: stubs, and MISO's detour that the host anchors on its longest run).
CARRIERS = {
    "RFID_MOSI": [(827.75, 1023.0), (817.75, 1023.0)],
    "RFID_SCK": [(827.75, 1013.0), (817.75, 1013.0)],
    "RFID_NSS": [(827.75, 1003.0), (817.75, 1003.0)],
    "RFID_MISO": [
        (827.75, 1033.0),
        (832.75, 1033.0),
        (832.75, 1068.0),
        (672.75, 1068.0),
    ],
}


def _plan(
    nets: tuple[str, ...] = ("RFID_MOSI",),
    *,
    text_mode: str = "",
    segments: list[LayoutSegment] | None = None,
) -> LayoutPlan:
    labels = [
        LayoutLabel(
            net=net,
            text=net,
            bbox=RFID[net][1],
            x=827.75,
            y=RFID[net][0],
            text_mode=text_mode,
        )
        for net in nets
    ]
    if segments is None:
        segments = [LayoutSegment(net=net, points=list(CARRIERS[net])) for net in nets]
    return LayoutPlan(labels=labels, segments=segments)


def _render(plan: LayoutPlan) -> ElementTree.Element:
    return ElementTree.fromstring(
        svgpreview.render_svg(plan, {}, page_box=PAGE_BOX, title="label carrier")
    )


def _texts(root: ElementTree.Element) -> list[ElementTree.Element]:
    return list(root.iter(f"{SVG}text"))


def _text(root: ElementTree.Element, content: str) -> ElementTree.Element:
    matches = [node for node in _texts(root) if (node.text or "") == content]
    assert len(matches) == 1, f"expected one <text>{content}</text>, got {len(matches)}"
    return matches[0]


def _dashed_boxes(root: ElementTree.Element) -> list[tuple[str, str, str, str]]:
    return [
        (node.get("x"), node.get("y"), node.get("width"), node.get("height"))
        for node in root.iter(f"{SVG}rect")
        if node.get("stroke-dasharray") == "2 2"
    ]


def _anchor_dots(root: ElementTree.Element) -> list[tuple[str, str]]:
    return [(node.get("cx"), node.get("cy")) for node in root.iter(f"{SVG}circle")]


def test_a_ten_unit_name_stub_prints_its_name_at_the_run_midpoint() -> None:
    """``RFID_MOSI``: stub ``827.75 -> 817.75``, name start-anchored at ``822.75``.

    The static box centre is ``x=748.25`` (SVG ``48.250``) and its right edge is
    ``x=780`` (SVG ``80.000``); neither is where the host prints the name.
    """
    root = _render(_plan(("RFID_MOSI",)))
    text = _text(root, "RFID_MOSI")
    assert text.get("x") == "122.750"  # 822.75 - 700, the stub's midpoint
    assert text.get("text-anchor") == "start"
    assert text.get("x") not in ("48.250", "80.000")  # box centre / box right edge

    width = render_width("RFID_MOSI")
    assert _dashed_boxes(root) == [
        (
            "122.750",
            f"{PAGE_BOX[3] - (1023.0 + WIRE_NAME_ROW):.3f}",  # 67.000
            f"{width:.3f}",
            f"{WIRE_NAME_ROW:.3f}",
        )
    ]
    assert text.get("y") == f"{PAGE_BOX[3] - 1023.0 - 3:.3f}"  # 74.000
    # The anchor dot is the label's own fact and does not move with the row.
    assert _anchor_dots(root) == [("127.750", "77.000")]


def test_the_row_is_the_longest_run_not_the_run_at_the_anchor() -> None:
    """``RFID_MISO``: the host anchors on ``832.75 -> 672.75``, so ``x=752.75``.

    This is what separates "read the carrier's row" from "put the name near its
    own anchor": the run the anchor sits on is 5 units long and the name is not
    printed there.
    """
    root = _render(_plan(("RFID_MISO",)))
    text = _text(root, "RFID_MISO")
    assert text.get("x") == "52.750"  # 752.75 - 700
    assert text.get("text-anchor") == "start"
    width = render_width("RFID_MISO")
    assert _dashed_boxes(root) == [
        ("52.750", f"{PAGE_BOX[3] - (1068.0 + WIRE_NAME_ROW):.3f}", f"{width:.3f}", "10.000")
    ]


def test_native_text_mode_keeps_its_static_box_centre() -> None:
    """``text_mode="native"`` is the host's attribute row: the box is the row.

    The same label and the same carrier, so only the mode moves the text.
    """
    root = _render(_plan(("RFID_MOSI",), text_mode=TEXT_MODE_NATIVE))
    text = _text(root, "RFID_MOSI")
    assert text.get("x") == "48.250"  # (716.5 + 780) / 2 - 700
    assert text.get("text-anchor") == "middle"
    assert text.get("y") == f"{PAGE_BOX[3] - (1018.5 + 1027.5) / 2 + 3:.3f}"
    bbox = RFID["RFID_MOSI"][1]
    assert _dashed_boxes(root) == [
        (
            f"{bbox[0] - 700:.3f}",
            f"{PAGE_BOX[3] - bbox[3]:.3f}",
            f"{bbox[2] - bbox[0]:.3f}",
            f"{bbox[3] - bbox[1]:.3f}",
        )
    ]


def test_a_label_with_no_carrier_keeps_the_bbox_diagnostic() -> None:
    """No carrier (no segment at all, or one that misses the anchor): no row.

    The old bbox-centred text stays, and nothing pretends a name is printed on a
    wire — the fallback is disclosed, not a carrier.
    """
    for segments in (
        [],
        # Same net, but the anchor is nowhere on it: the orthogonal on-run test is
        # what makes it a non-carrier, not merely the net name.
        [LayoutSegment(net="RFID_MOSI", points=[(400.0, 1023.0), (500.0, 1023.0)])],
        # A diagonal run carries no name on this host, so it is not a carrier.
        [LayoutSegment(net="RFID_MOSI", points=[(817.75, 1013.0), (837.75, 1033.0)])],
    ):
        root = _render(_plan(("RFID_MOSI",), segments=segments))
        text = _text(root, "RFID_MOSI")
        assert text.get("x") == "48.250", segments
        assert text.get("text-anchor") == "middle"
        assert text.get("y") == f"{PAGE_BOX[3] - (1018.5 + 1027.5) / 2 + 3:.3f}"
        assert _dashed_boxes(root) == [("16.500", "72.500", "63.500", "9.000")]
        assert _anchor_dots(root) == [("127.750", "77.000")]


def test_the_carried_name_keeps_the_measured_host_font_size() -> None:
    """The row is a host text like any other: 7.006, and no other text moves."""
    assert svgpreview.NATIVE_TEXT_FONT_SIZE == 7.006
    root = _render(_plan(("RFID_MOSI",)))
    assert _text(root, "RFID_MOSI").get("font-size") == "7.006"
    assert [node for node in _texts(root) if node.get("font-size") == "7.006"] == [
        _text(root, "RFID_MOSI")
    ]
