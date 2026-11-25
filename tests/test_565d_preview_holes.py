"""565d — the three svgpreview self-consistency holes (S6-H1 / S6-H2 / S6-H4).

Every case here states a fact the preview has to agree with itself about, so a
failure names a real disagreement rather than a moved number:

* **H1** — the dashed box a reviewer measures and the glyphs drawn inside it are
  one text in one font at one size. The box width is `textmetrics.render_width`
  (Arial advances x `RENDER_TEXT_PX`); the document declared
  ``font-family="DejaVu Sans, Consolas, monospace"`` and drew at 7.006, so on a
  machine without DejaVu the painted string was a monospace one — ``WWWWWWWW``
  painted 43% narrower than its own box, ``IIIIIIII`` 94% wider.
* **H2** — every file the preview writes is well-formed XML. C0 control
  characters are not representable in XML 1.0 at all, so they are removed before
  escaping (``\\t``, ``\\n``, ``\\r`` survive), and ``write_preview`` parses its
  own output before touching the disk.
* **H4** — the picture prints the name once per carrier the landing names
  (``layoutplan.label_wire_indices``), and a carrier whose row runs vertically is
  **disclosed** in the caption instead of quietly being replaced by text at the
  label's static box, where the host prints no name.

Pure in-memory ``LayoutPlan`` fixtures. No ``tmp_path``: on this Windows host a
Python 3.14 ``tmp_path`` directory carries a restricted DACL and the tests fail
for a reason that has nothing to do with the preview. Files go to
``.tmp_565d/tests-out/`` instead.
"""

from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from boardwise.core import textmetrics
from boardwise.core.layoutplan import (
    LayoutLabel,
    LayoutPlan,
    LayoutSegment,
    LayoutText,
    label_wire_indices,
)
from boardwise.engines import svgpreview
from boardwise.engines.svgpreview import render_svg, write_preview

SVG_NS = "{http://www.w3.org/2000/svg}"
LABEL_COLOUR = "#1d4ed8"
OUT = Path(__file__).resolve().parents[1] / ".tmp_565d" / "tests-out"


# --------------------------------------------------------------- fixtures


def _labeled(
    text: str = "SENSE",
    segments: list[LayoutSegment] | None = None,
    bbox: tuple[float, float, float, float] = (30.0, -5.0, 60.0, 5.0),
) -> LayoutPlan:
    """One label anchored at (40, 0) on the named segments."""
    plan = LayoutPlan()
    plan.segments.extend(
        segments
        if segments is not None
        else [LayoutSegment(net="SENSE", points=[(0.0, 0.0), (80.0, 0.0)])]
    )
    plan.labels.append(
        LayoutLabel(net="SENSE", text=text, bbox=bbox, x=40.0, y=0.0)
    )
    return plan


def _two_horizontal_carriers() -> LayoutPlan:
    """Two same-net horizontal runs whose shared end is the anchor.

    ``label_wire_indices`` names both (565-S6 measured ``frozenset({0, 1})`` on the
    probe's T junction); the preview used to draw the first one only.
    """
    return _labeled(
        segments=[
            LayoutSegment(net="SENSE", points=[(0.0, 0.0), (40.0, 0.0)]),
            LayoutSegment(net="SENSE", points=[(40.0, 0.0), (120.0, 0.0)]),
        ]
    )


def _vertical_first() -> LayoutPlan:
    """The T of the S6 probe: the vertical stub comes first in plan order."""
    return _labeled(
        segments=[
            LayoutSegment(net="SENSE", points=[(40.0, 0.0), (40.0, 30.0)]),
            LayoutSegment(net="SENSE", points=[(0.0, 0.0), (80.0, 0.0)]),
        ]
    )


def _vertical_only() -> LayoutPlan:
    return _labeled(
        segments=[LayoutSegment(net="SENSE", points=[(40.0, 0.0), (40.0, 40.0)])]
    )


def _texts(root: ET.Element) -> list[ET.Element]:
    return list(root.iter(f"{SVG_NS}text"))


def _by_text(root: ET.Element, text: str) -> list[ET.Element]:
    hits = [node for node in _texts(root) if (node.text or "") == text]
    assert hits, f"no <text> {text!r}; painted: {[n.text for n in _texts(root)]}"
    return hits


def _label_rects(root: ET.Element) -> list[ET.Element]:
    """The dashed boxes the preview draws for labels (one per printed row)."""
    return [
        node
        for node in root.iter(f"{SVG_NS}rect")
        if node.get("stroke") == LABEL_COLOUR and node.get("stroke-dasharray")
    ]


def _caption_text(root: ET.Element) -> str:
    """The caption strip: the text nodes that carry no font-size of their own."""
    return "\n".join(
        node.text or "" for node in _texts(root) if node.get("font-size") is None
    )


# ------------------------------------------------------- H1: box == glyphs


def test_h1_the_document_declares_the_one_font_the_metric_table_measures() -> None:
    """One family constant, shared by the advance table and the SVG root.

    A preview may name fallbacks (a machine without Arial needs one), but the
    first family must be the one :data:`textmetrics.TEXT_ADVANCE_EM` measured —
    otherwise the box and the glyphs are two different texts.
    """
    family = getattr(textmetrics, "RENDER_TEXT_FAMILY", None)
    assert family, (
        "textmetrics must name the font family its advance table models, so the "
        "drawing can declare the family its boxes are measured in"
    )
    root = ET.fromstring(render_svg(_two_horizontal_carriers(), {}))
    assert root.get("font-family") == family, (
        f"the preview declares font-family={root.get('font-family')!r} while its "
        f"boxes are measured in {family!r}: the same document is a different "
        f"picture on every machine that resolves that family differently"
    )


def test_h1_the_painted_size_is_the_em_the_boxes_are_measured_with() -> None:
    """The label's drawn ``font-size`` is `RENDER_TEXT_PX`, not another number."""
    root = ET.fromstring(render_svg(_two_horizontal_carriers(), {}))
    painted = {float(node.get("font-size")) for node in _by_text(root, "SENSE")}
    assert len(painted) == 1, f"one row, {len(painted)} painted sizes: {sorted(painted)}"
    assert painted.pop() == pytest.approx(textmetrics.RENDER_TEXT_PX, abs=1e-3), (
        f"the row is painted at another size than the box model's em "
        f"{textmetrics.RENDER_TEXT_PX}: a 2% box/glyph disagreement is exactly how "
        f"H1 hid wide-glyph overlaps"
    )


@pytest.mark.parametrize("text", ["IIIIIIII", "WWWWWWWW", "RFID_MOSI"])
def test_h1_the_dashed_box_is_the_width_that_string_paints(text: str) -> None:
    """box width == advance(text, declared family, drawn px), for every string.

    This is the causal assertion: it re-measures the painted size taken *out of
    the SVG* with the metric table, so changing the family or the font-size in
    the renderer without changing the other one fails here — ``IIIIIIII`` and
    ``WWWWWWWW`` are the two shapes the monospace fallback got wrong in opposite
    directions (94% too wide and 43% too narrow).
    """
    advance = getattr(textmetrics, "advance", None)
    assert advance is not None, (
        "textmetrics must expose advance(text, family, font_px): the box is the "
        "width the declared family has at the size the preview paints"
    )
    family = getattr(textmetrics, "RENDER_TEXT_FAMILY", None)
    assert family, "textmetrics.RENDER_TEXT_FAMILY is the family the SVG must declare"
    root = ET.fromstring(render_svg(_labeled(text=text, bbox=(-60.0, -5.0, 90.0, 5.0)), {}))
    painted = {float(node.get("font-size")) for node in _by_text(root, text)}
    assert len(painted) == 1, f"one label, {len(painted)} font sizes: {sorted(painted)}"
    drawn_px = painted.pop()
    boxes = _label_rects(root)
    assert len(boxes) == 1, f"one printed row, {len(boxes)} dashed boxes"
    box_width = float(boxes[0].get("width"))
    assert box_width == pytest.approx(advance(text, family, drawn_px), abs=1e-3), (
        f"{text!r}: box {box_width:.3f} units vs {advance(text, family, drawn_px):.3f} "
        f"at the size the SVG paints ({drawn_px}) in {family!r}"
    )


def test_h1_a_printed_row_and_a_native_text_keep_their_own_measured_sizes() -> None:
    """Two host text classes, two measurements — the row is not a native text.

    ``NATIVE_TEXT_FONT_SIZE`` (7.006) is the V4 native-text measurement used for
    ``LayoutText``, a flag's net name and a label with no printed row;
    ``LABEL_ROW_FONT_SIZE`` is the em the row's own box was laid out with. Folding
    one into the other would either shrink the row inside its box or rewrite the
    native text's measurement, so both numbers stay and both are drawn.
    """
    plan = _two_horizontal_carriers()
    plan.texts.append(LayoutText(kind="value", text="NATIVE", bbox=(-40.0, 30.0, -10.0, 40.0)))
    root = ET.fromstring(render_svg(plan, {}))
    row_sizes = {float(node.get("font-size")) for node in _by_text(root, "SENSE")}
    native_sizes = {float(node.get("font-size")) for node in _by_text(root, "NATIVE")}
    assert len(row_sizes) == 1 and abs(row_sizes.pop() - textmetrics.RENDER_TEXT_PX) < 1e-3, row_sizes
    assert len(native_sizes) == 1 and abs(native_sizes.pop() - svgpreview.NATIVE_TEXT_FONT_SIZE) < 1e-9, (
        f"native text painted at {sorted(native_sizes)}, not at "
        f"{svgpreview.NATIVE_TEXT_FONT_SIZE}: the V4 native-text measurement was "
        f"overwritten by the row's em"
    )
    assert svgpreview.LABEL_ROW_FONT_SIZE == pytest.approx(textmetrics.RENDER_TEXT_PX)
    assert svgpreview.LABEL_ROW_FONT_SIZE != svgpreview.NATIVE_TEXT_FONT_SIZE


# -------------------------------------------- H2: every written file is XML


def test_h2_control_characters_never_reach_the_document() -> None:
    """A label carrying C0 characters still yields a parseable SVG."""
    plan = _labeled(text="A\x01B")
    svg = render_svg(plan, {})
    root = ET.fromstring(svg)  # must not raise: XML 1.0 forbids C0 outright
    painted = [node.text or "" for node in _texts(root)]
    assert any("A" in text and "B" in text for text in painted), painted
    for char in "\x00\x01\x08\x0b\x0c\x0e\x1f":
        assert char not in svg, f"XML 1.0 forbids {char!r}; it reached the document"


def test_h2_printable_whitespace_survives_the_filter() -> None:
    """``\\t``, ``\\n`` and ``\\r`` are XML-legal and must not be stripped."""
    plan = _labeled(text="A\tB\nC\rD")
    svg = render_svg(plan, {})
    assert "A\tB\nC\rD" in svg, "tab/newline/carriage-return were stripped with the C0 range"
    ET.fromstring(svg)


def test_h2_write_preview_writes_a_document_a_reviewer_can_open() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "h2_control_chars.svg"
    written = write_preview(path, _labeled(text="A\x01B"), {})
    assert Path(written) == path
    ET.parse(path)  # parses, i.e. the artefact on disk really is an SVG


def test_h2_write_preview_refuses_what_it_cannot_parse(monkeypatch) -> None:
    """The writer checks its own output before the disk sees it.

    ``render_svg`` is replaced by a truncated document because after the H2 fix
    no plan can make it emit one — the self-check is the last line of defence and
    this is the only way to prove it is wired.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"h2_refused_{os.getpid()}.svg"
    monkeypatch.setattr(svgpreview, "render_svg", lambda *a, **k: "<svg><unclosed>")
    with pytest.raises(ValueError) as caught:
        write_preview(path, _labeled(), {})
    message = str(caught.value).lower()
    assert "xml" in message or "parse" in message, message
    assert not path.exists(), "the refused document was written to disk anyway"


# ------------------------------------------- H4: one row per named carrier


def test_h4_every_named_carrier_gets_its_own_row() -> None:
    """The picture prints the name as many times as the landing names a carrier."""
    plan = _two_horizontal_carriers()
    indices = label_wire_indices(plan)
    assert len(indices) == 2, f"fixture must name two carriers, names {sorted(indices)}"
    root = ET.fromstring(render_svg(plan, {}))
    rows = _by_text(root, "SENSE")
    assert len(rows) == len(indices), (
        f"landing names {len(indices)} carriers, preview paints {len(rows)} row(s): "
        f"the second carrier's name is invisible in the picture"
    )
    assert len({node.get("x") for node in rows}) == 2, (
        f"two rows, but all at x={{{rows[0].get('x')}}}: one carrier was drawn twice"
    )
    assert len(_label_rects(root)) == len(indices), (
        f"{len(_label_rects(root))} dashed boxes for {len(indices)} printed rows"
    )
    assert all(node.get("text-anchor") == "start" for node in rows)


def test_h4_a_vertical_carrier_is_disclosed_in_the_caption() -> None:
    """A vertical carrier is named in the caption, not silently replaced."""
    plan = _vertical_first()
    assert len(label_wire_indices(plan)) == 2
    root = ET.fromstring(render_svg(plan, {}))
    rows = _by_text(root, "SENSE")
    assert len(rows) == 1, (
        f"only the horizontal carrier has a modelled row; painted {len(rows)} "
        f"SENSE row(s)"
    )
    caption = _caption_text(root)
    assert "vertical" in caption.lower(), (
        "the vertical carrier is unmodelled and the caption says nothing about it: "
        f"caption was {caption!r}"
    )
    assert "SENSE" in caption


def test_h4_a_vertical_only_carrier_is_not_claimed_as_a_row() -> None:
    """No horizontal carrier: the box stays a diagnostic, the caption says why."""
    root = ET.fromstring(render_svg(_vertical_only(), {}))
    painted = _by_text(root, "SENSE")
    assert len(painted) == 1 and painted[0].get("text-anchor") == "middle", (
        "with no horizontal carrier the only text is the static-box diagnostic "
        "(middle-anchored), never a row claim"
    )
    caption = _caption_text(root)
    assert "vertical" in caption.lower() and "SENSE" in caption, (
        f"silent fallback: the caption does not disclose the vertical carrier: {caption!r}"
    )


def test_h4_the_helper_returns_one_row_per_carrier() -> None:
    """`_label_carrier_row` states every named carrier, not only the first."""
    plan = _two_horizontal_carriers()
    rows = svgpreview._label_carrier_row(plan, plan.labels[0])
    assert isinstance(rows, list), (
        f"expected a list of rows, got {type(rows).__name__}: a single row is what "
        f"drew one name where the landing named two"
    )
    assert len(rows) == len(label_wire_indices(plan))
    assert [row.horizontal for row in rows] == [True, True]
    assert {(tuple(row.run[0]), tuple(row.run[1])) for row in rows} == {
        ((0.0, 0.0), (40.0, 0.0)),
        ((40.0, 0.0), (120.0, 0.0)),
    }
