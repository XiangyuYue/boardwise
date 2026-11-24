"""Offline SVG preview of a compiled plan (053 stage B: "岳不开编辑器即可看布局质量").

One function for the whole job — :func:`render_svg` — plus a writer that puts it
where a reviewer can open it. Pure standard library (string building, XML and
``html.escape``): the point of the preview is that a compiled drawing can be
*looked at* without a browser engine, a plotting library or the editor, and a new
dependency would be the one thing this path cannot carry.

What the picture shows, and why each element is there:

* the **page and the keep-outs**, the same boxes the readability checker tests
  against, so "it fits" is visible rather than asserted. When no page is stated
  the frame is the drawing's own extent — parts, texts, labels, wires,
  junctions, keep-outs and module frames together — because a keep-out that fell
  outside the picture would hide exactly the collision it exists to show. A plan
  with no geometry at all still gets a margin square: a zero-width document is a
  blank one;
* every **part** as its symbol's body box, with its pins and the reference/value
  text at the boxes the *compiler* computed — the font-metric boxes, drawn dashed,
  because a reviewer who sees only glyphs cannot tell whether a text was measured
  or estimated;
* every **wire**, **junction**, **label** and **flag**, with a label's anchor dot
  separate from its text (they are different facts in `LayoutPlan`). A label's
  text is drawn in the row its carrier's longest run prints it in
  (`_label_carrier_row`), and in its static box only when no row exists — which
  is a diagnostic, not a claim that a name is printed there. A flag's box
  is the one `drawcompiler` reserves — the glyph hanging away from the pin
  (`core.symbolprofile.flag_glyph_box`, 060) — so the two cannot disagree about
  which side of the anchor the flag occupies, which is how 054-059's upside-down
  flags stayed invisible;
* a caption with the plan's geometry digest, the compiler's notes and the raw soft
  metrics — never a score (052 sec.6), just the numbers the ranking used.

The transform is a pure map from canvas to SVG pixels: SVG's y grows down and the
canvas' grows up (010c measured), so ``Y = top - y``. Diagnostic text uses that
map directly. Optional native symbol art is already captured in SVG coordinates
at its stated pose; only its outer origin and positive scale are transformed.

``scale`` magnifies the **drawing**: geometry, and with it every visual attribute
a reader measures the drawing by — font sizes, stroke widths, dash pitch and dot
radii. Shrinking only the coordinates left the glyphs at their 1:1 size inside
boxes twice as tall, which is precisely the font-to-box relationship the preview
exists to show. The caption strip stays in output pixels, so it reads at any
magnification, and captured native art keeps its own captured size (only its
origin and the one outer ``scale`` move it).
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import math
from pathlib import Path
import re
from typing import Mapping, Sequence
from xml.etree import ElementTree as ET

from boardwise.core.layoutplan import TEXT_MODE_NATIVE, LayoutLabel, LayoutPlan
from boardwise.core.symbolprofile import (
    Box,
    SymbolPose,
    SymbolProfile,
    flag_glyph_box,
)
from boardwise.core.textmetrics import WireNameRow, wire_name_row

__all__ = [
    "NATIVE_TEXT_FONT_SIZE",
    "PREVIEW_FONT_SIZE",
    "PREVIEW_KIND",
    "PREVIEW_MARGIN",
    "NativeSymbolArt",
    "render_svg",
    "write_preview",
]

#: Identifies the artefact, so a file on disk says what it is.
PREVIEW_KIND = "boardwise-plan-preview/1"

#: Canvas units of blank space around the drawing when no page is stated.
PREVIEW_MARGIN = 40.0

#: The caption's font size in SVG units (the drawing itself is 1:1).
PREVIEW_FONT_SIZE = 11.0

#: The host font size of a placed text, a net label and a power symbol's net
#: name. It is the size a real V4 native SVG uses: in the y173 export
#: ``KEY_C1``, ``RFID_MISO``, ``HALL_LOCK``, ``+3V3``, ``GND`` and
#: ``STM32F103C8T6`` all carry ``font-size:7.006200555911909px`` (the label box
#: height the host claims for them is 9). Those three text kinds used to inherit
#: the 11-unit diagnostic default, which made them look larger — and therefore
#: more overlapping — than the native drawing they stand in for. The 11 stays the
#: canvas default for caption and other diagnostic text; a pin number stays 9
#: and a frame name 12, each stated where it is drawn.
NATIVE_TEXT_FONT_SIZE = 7.006

#: The caption strip's own metrics, in canvas units: the first line's baseline
#: below the drawing, the line pitch, and the room a line needs under its own
#: baseline (descenders plus a little air).
CAPTION_TOP = 16.0
CAPTION_LINE_HEIGHT = 15.0
CAPTION_DESCENT = 14.0

#: What the strip reserved before it was derived from the line count: exactly the
#: five lines a plan with **at most one note** produces (four fixed lines plus up
#: to four notes). Those previews keep the height they had, byte for byte; from
#: the sixth line on the canvas grows, because a hardcoded strip clipped the tail
#: of the plan's own provenance footer (100 #16).
CAPTION_MIN_HEIGHT = CAPTION_TOP + 4 * CAPTION_LINE_HEIGHT + CAPTION_DESCENT

_COLOURS = {
    "background": "#ffffff",
    "page": "#f7f7f4",
    "grid": "#eeeeea",
    "border": "#cccccc",
    "body": "#e8e8e8",
    "bodyEdge": "#333333",
    "pin": "#888888",
    "wire": "#0b6b3a",
    "junction": "#0b6b3a",
    "label": "#1d4ed8",
    "flag": "#b45309",
    "text": "#444444",
    "textBox": "#e0a800",
    "keepout": "#cc3333",
    "frame": "#7c3aed",
    "caption": "#222222",
}


@dataclass(frozen=True)
class NativeSymbolArt:
    """Self-contained symbol SVG, already captured at this exact pose.

    ``svg`` uses local SVG coordinates (x right, y down). It contains body,
    pin lines and pin text only; reference/value rows remain in the plan.
    ``source`` identifies the measured extraction or an explicitly proved pose
    equivalence. The renderer does not load paths or infer other poses.
    """

    symbol_ref: str
    rotation: float
    mirror: bool
    svg: str
    source: str


#: The tolerance :func:`boardwise.core.layoutplan.label_wire_indices` uses to say
#: "this label's anchor lies on this run". The preview reads that fact the same
#: way, so the wire it prints a name on is the wire the readability gate measures.
_CARRIER_TOL = 1e-6


def _anchor_on_run(
    start: tuple[float, float],
    stop: tuple[float, float],
    point: tuple[float, float],
) -> bool:
    """Is ``point`` on the orthogonal run ``start``-``stop`` (ends included)?

    ``label_wire_indices``' own test, in behaviour: a carrier is a horizontal or a
    vertical wire and the anchor lies on the closed span. A diagonal run carries no
    name on this host and is not a carrier here either.
    """
    if abs(start[0] - stop[0]) < 1e-9:  # vertical
        return abs(point[0] - start[0]) < _CARRIER_TOL and (
            min(start[1], stop[1]) - _CARRIER_TOL
            <= point[1]
            <= max(start[1], stop[1]) + _CARRIER_TOL
        )
    if abs(start[1] - stop[1]) < 1e-9:  # horizontal
        return abs(point[1] - start[1]) < _CARRIER_TOL and (
            min(start[0], stop[0]) - _CARRIER_TOL
            <= point[0]
            <= max(start[0], stop[0]) + _CARRIER_TOL
        )
    return False


def _label_carrier_row(layout_plan: LayoutPlan, label: LayoutLabel) -> WireNameRow | None:
    """The row the host prints this label's **name** in, or ``None``.

    A label on this host has no primitive of its own (029): the net's name is
    printed by a *wire*, at the midpoint of that wire's longest straight run and
    **start-anchored** from there (:func:`boardwise.core.textmetrics.wire_name_row`,
    measured on the 145e/147 renders). The carrier is the wire whose same-net
    orthogonal run the label's own anchor lies on — the one statement
    ``core.layoutplan.label_wire_indices`` makes for the landing, the readability
    gate and the connectivity re-verification, so the preview must not invent a
    second reading.

    Nowhere does the name sit at the label's static ``bbox`` centre: on the y173
    page the four J7 RFID labels all anchor at ``x=827.75`` while their static boxes
    reach ``x=780``/``x=782.5``, and the native drawing prints ``RFID_MOSI``,
    ``RFID_SCK`` and ``RFID_NSS`` at ``x=822.75`` — the midpoint of each 10-unit
    name stub ``827.75 -> 817.75`` — and ``RFID_MISO`` at ``x=752.75``, the midpoint
    of *its* long detour run (``832.75 -> 672.75``). Centring every label in its
    static box is what made an independent visual review reject the preview as
    "the RFID names hang off their stubs".

    ``None`` means **no row may be drawn**, and the caller keeps the old
    ``bbox``-centred text as a diagnostic:

    * ``text_mode="native"`` (:data:`TEXT_MODE_NATIVE`): the host prints the name
      with its attribute API at the label's own box, so the box *is* the row;
    * a label with no carrier on its net: nothing prints a name there, and no row
      is invented;
    * a carrier whose longest run is **vertical**. Only the horizontal row is this
      preview's contract (the measured rule above); a vertical row is a real host
      case (534 r18, the CH343 sheet) the preview does not model yet, so it is
      disclosed by falling back to the diagnostic box rather than guessed.
    """
    if not label.net or getattr(label, "text_mode", "") == TEXT_MODE_NATIVE:
        return None
    anchor = (float(label.x), float(label.y))
    for segment in layout_plan.segments:
        points = [(float(point[0]), float(point[1])) for point in segment.points]
        if segment.net != label.net or len(points) < 2:
            continue
        if not any(
            _anchor_on_run(start, stop, anchor)
            for start, stop in zip(points, points[1:])
        ):
            continue
        row = wire_name_row(points, label.text)
        # The first carrier in plan order is the one the landing named; a
        # vertical row is unmodelled, not silently replaced by a second carrier.
        return row if row is not None and row.horizontal else None
    return None


def render_svg(
    layout_plan: LayoutPlan,
    profiles: Mapping[str, SymbolProfile] | Sequence[SymbolProfile],
    *,
    page_box: Box | None = None,
    keepouts: Sequence[Box] = (),
    frames: Sequence[tuple[str, Box]] = (),
    title: str = "",
    scale: float = 1.0,
    native_art: Sequence[NativeSymbolArt] = (),
) -> str:
    """One compiled plan as an SVG document.

    ``profiles`` are the library entries the plan was drawn with — they are what
    turns a placed origin into a visible body, a pin and a glyph. ``page_box``
    states the sheet the drawing is meant for; when it is ``None`` the drawing's
    own bounding box (plus :data:`PREVIEW_MARGIN`) becomes the frame, which is
    the same convention the compiler uses for "no page was stated". ``frames`` are
    the named module frames of a *page* (056), drawn as outlines so a reviewer can
    see which group owns which part of the sheet; the parameter defaults to empty,
    and a single drawing's preview is byte-identical whether or not it is used.
    ``native_art`` optionally replaces a part's diagnostic box/pin dots with
    captured symbol art at the exact stated pose. Other drawing layers remain
    diagnostic; this is not a native editor export.
    """
    if scale <= 0:
        raise ValueError(f"scale must be positive, got {scale!r}")
    book = _book(profiles)
    art_by_pose: dict[tuple[str, float, bool], NativeSymbolArt] = {}
    for art in native_art:
        if not art.symbol_ref or not isinstance(art.source, str) or not art.source.strip():
            raise ValueError(f"native art {art.symbol_ref!r}: a measured source is required")
        if not math.isfinite(art.rotation) or not isinstance(art.mirror, bool):
            raise ValueError(f"native art {art.symbol_ref!r}: invalid captured pose")
        key = (art.symbol_ref, art.rotation, art.mirror)
        if key in art_by_pose:
            raise ValueError(f"native art {art.symbol_ref!r}: duplicate captured pose {key[1:]}")
        art_by_pose[key] = art
    box = _normalised_box(page_box) if page_box is not None else _content_box(
        layout_plan, book, keepouts=keepouts, frames=frames
    )
    width = (box[2] - box[0]) * scale
    height = (box[3] - box[1]) * scale
    canvas_width = float(f"{width:.0f}")
    canvas_height = float(f"{height:.0f}")
    if canvas_width <= 0 or canvas_height <= 0:
        raise ValueError(
            f"preview canvas would be {canvas_width:.0f} x {canvas_height:.0f} pixels "
            f"at scale {scale:g}: the drawing's extent is {width:g} x {height:g} units"
        )

    def x(value: float) -> float:
        return (value - box[0]) * scale

    def y(value: float) -> float:
        return (box[3] - value) * scale

    #: A drawing attribute in output pixels. ``scale`` is a magnification of the
    #: whole drawing, so glyphs, strokes, dash pitch and dots grow with it.
    def px(value: float) -> float:
        return value * scale

    def rect(item: Box, **attributes: str) -> str:
        left, bottom, right, top = _normalised_box(item)
        return (
            f'<rect x="{x(left):.3f}" y="{y(top):.3f}" '
            f'width="{(right - left) * scale:.3f}" '
            f'height="{(top - bottom) * scale:.3f}" '
            + " ".join(f'{key}="{value}"' for key, value in attributes.items())
            + "/>"
        )

    #: The strip is derived from the caption it holds — the caption is four fixed
    #: lines plus up to four notes, and the hardcoded 90 it used to reserve clipped
    #: everything from the sixth line down: the plan's own provenance footer, the
    #: geometry digest and the verdict included (100 #16).
    caption = _caption_lines(layout_plan, title, box, scale)
    if native_art:
        caption.append("Native symbol art only; wires, flags and planned text remain diagnostic.")
    strip = _caption_height(len(caption))

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
        f'height="{height + strip:.0f}" viewBox="0 0 {width:.0f} {height + strip:.0f}" '
        f'font-family="DejaVu Sans, Consolas, monospace" '
        f'font-size="{PREVIEW_FONT_SIZE:g}">',
        f'<rect x="0" y="0" width="{width:.0f}" height="{height + strip:.0f}" '
        f'fill="{_COLOURS["background"]}"/>',
        rect(box, fill=_COLOURS["page"], stroke=_COLOURS["border"]),
    ]
    parts.extend(_grid(box, scale, x, y))
    for keep in keepouts:
        parts.append(rect(keep, fill="none", stroke=_COLOURS["keepout"],
                          **{"stroke-dasharray": f"{px(4):g} {px(3):g}"}))
    for name, frame in frames:
        left, _, _, top = _normalised_box(frame)
        parts.append(rect(frame, fill="none", stroke=_COLOURS["frame"],
                          **{"stroke-dasharray": f"{px(6):g} {px(4):g}",
                             "stroke-width": f"{px(1.4):g}"}))
        parts.append(
            f'<text x="{x(left) + px(5):.3f}" y="{y(top) + px(13):.3f}" '
            f'fill="{_COLOURS["frame"]}" font-size="{px(12):g}">{escape(str(name))}</text>'
        )

    for symbol in layout_plan.power_symbols:
        profile = book.get(symbol.symbol_ref)
        glyph = flag_glyph_box(
            profile, rotation=symbol.rotation, anchor=(symbol.x, symbol.y),
        ) if profile is not None else None
        if glyph is not None:
            parts.append(rect(glyph, fill="none", stroke=_COLOURS["flag"],
                              **{"stroke-width": f"{px(1.2):g}"}))
        parts.append(
            f'<circle cx="{x(symbol.x):.3f}" cy="{y(symbol.y):.3f}" r="{px(2.5):g}" '
            f'fill="{_COLOURS["flag"]}"/>'
        )
        parts.append(
            f'<text x="{x(symbol.x) + px(6):.3f}" y="{y(symbol.y) - px(4):.3f}" '
            f'fill="{_COLOURS["flag"]}" font-size="{px(NATIVE_TEXT_FONT_SIZE):g}">'
            f"{escape(symbol.net)}</text>"
        )

    for part in layout_plan.parts:
        art = art_by_pose.get((part.symbol_ref, part.rotation, part.mirror))
        if art is not None:
            fragment = _native_fragment(art, part.part_id)
            fragment.set("transform", (
                f"translate({x(part.x):.3f},{y(part.y):.3f}) scale({scale:g})"
            ))
            parts.append(ET.tostring(fragment, encoding="unicode"))
            continue
        if any(key[0] == part.symbol_ref for key in art_by_pose):
            raise ValueError(
                f"native art for {part.part_id} ({part.symbol_ref}): no captured pose "
                f"rotation={part.rotation:g}, mirror={part.mirror}"
            )
        profile = book.get(part.symbol_ref)
        pose = SymbolPose(rotation=int(part.rotation), mirror=part.mirror)
        origin = (part.x, part.y)
        body = _body_box(profile, pose, origin)
        if body is not None:
            parts.append(rect(body, fill=_COLOURS["body"], stroke=_COLOURS["bodyEdge"],
                              **{"stroke-width": f"{px(1.2):g}"}))
        if profile is not None:
            for pin in profile.pins:
                tip = _transform(pin.tip, pose, origin)
                parts.append(
                    f'<circle cx="{x(tip[0]):.3f}" cy="{y(tip[1]):.3f}" r="{px(2.2):g}" '
                    f'fill="{_COLOURS["pin"]}"/>'
                )
                parts.append(
                    f'<text x="{x(tip[0]) + px(4):.3f}" y="{y(tip[1]) - px(3):.3f}" '
                    f'fill="{_COLOURS["pin"]}" font-size="{px(9):g}">'
                    f'{escape(str(pin.number))}</text>'
                )
        parts.append(
            f'<circle cx="{x(part.x):.3f}" cy="{y(part.y):.3f}" r="{px(1.6):g}" '
            f'fill="{_COLOURS["bodyEdge"]}"/>'
        )

    # Wires and junctions after the bodies: a conductor crossing a symbol is a
    # readability finding, so the preview must show it rather than let the
    # opaque body box paint over it.
    for segment in layout_plan.segments:
        points = " ".join(
            f"{x(point[0]):.3f},{y(point[1]):.3f}" for point in segment.points
        )
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{_COLOURS["wire"]}" '
            f'stroke-width="{px(1.8):g}"/>'
        )
    for junction in layout_plan.junctions:
        parts.append(
            f'<circle cx="{x(junction.x):.3f}" cy="{y(junction.y):.3f}" r="{px(3.2):g}" '
            f'fill="{_COLOURS["junction"]}"/>'
        )

    for text in layout_plan.texts:
        parts.append(rect(text.bbox, fill="none", stroke=_COLOURS["textBox"],
                          **{"stroke-dasharray": f"{px(2):g} {px(2):g}",
                             "stroke-width": f"{px(0.8):g}"}))
        centre_x = (text.bbox[0] + text.bbox[2]) / 2.0
        centre_y = (text.bbox[1] + text.bbox[3]) / 2.0
        parts.append(
            f'<text x="{x(centre_x):.3f}" y="{y(centre_y) + px(3):.3f}" '
            f'fill="{_COLOURS["text"]}" text-anchor="middle" '
            f'font-size="{px(NATIVE_TEXT_FONT_SIZE):g}">'
            f"{escape(text.text)}</text>"
        )
    for label in layout_plan.labels:
        row = _label_carrier_row(layout_plan, label)
        if row is None:
            # No row the host prints (native label, no carrier, unmodelled
            # vertical run): the static box stays as the diagnostic it always was.
            parts.append(rect(label.bbox, fill="none", stroke=_COLOURS["label"],
                              **{"stroke-dasharray": f"{px(2):g} {px(2):g}",
                                 "stroke-width": f"{px(0.8):g}"}))
            centre_x = (label.bbox[0] + label.bbox[2]) / 2.0
            centre_y = (label.bbox[1] + label.bbox[3]) / 2.0
            parts.append(
                f'<text x="{x(centre_x):.3f}" y="{y(centre_y) + px(3):.3f}" '
                f'fill="{_COLOURS["label"]}" text-anchor="middle" '
                f'font-size="{px(NATIVE_TEXT_FONT_SIZE):g}">'
                f"{escape(label.text)}</text>"
            )
        else:
            # The name is printed on its carrier's longest run: the dashed box is
            # that measured row, the glyphs start at the run's midpoint.
            parts.append(rect(row.box, fill="none", stroke=_COLOURS["label"],
                              **{"stroke-dasharray": f"{px(2):g} {px(2):g}",
                                 "stroke-width": f"{px(0.8):g}"}))
            parts.append(
                f'<text x="{x(row.box[0]):.3f}" y="{y(row.box[1]) - px(3):.3f}" '
                f'fill="{_COLOURS["label"]}" text-anchor="start" '
                f'font-size="{px(NATIVE_TEXT_FONT_SIZE):g}">'
                f"{escape(label.text)}</text>"
            )
        # The anchor is the label's own fact and does not move with its name's row.
        parts.append(
            f'<circle cx="{x(label.x):.3f}" cy="{y(label.y):.3f}" r="{px(2.0):g}" '
            f'fill="{_COLOURS["label"]}"/>'
        )

    parts.extend(_caption(caption, height))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def write_preview(
    path: str | Path,
    layout_plan: LayoutPlan,
    profiles: Mapping[str, SymbolProfile] | Sequence[SymbolProfile],
    **options: object,
) -> Path:
    """Render and write one preview; returns where it went."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_svg(layout_plan, profiles, **options),  # type: ignore[arg-type]
        encoding="utf-8",
    )
    return target


# ------------------------------------------------------------------- drawing


def _native_fragment(art: NativeSymbolArt, part_id: str) -> ET.Element:
    """Inline extracted geometry only, with per-instance IDs and scoped CSS."""
    context = f"native art for {part_id} ({art.symbol_ref}, source {art.source!r})"
    if "<!DOCTYPE" in art.svg.upper() or "<!ENTITY" in art.svg.upper():
        raise ValueError(f"{context}: document declarations are not extracted art")
    try:
        root = ET.fromstring(art.svg)
    except ET.ParseError as exc:
        raise ValueError(f"{context}: invalid SVG ({exc})") from exc
    allowed = {"svg", "g", "path", "line", "polyline", "polygon", "rect",
               "circle", "ellipse", "text", "tspan", "style"}
    prefix = "native-" + part_id.encode("utf-8").hex()
    identifiers: dict[str, str] = {}

    def validate(node: ET.Element, inside_pin: bool = False) -> None:
        tag = node.tag.removeprefix("{http://www.w3.org/2000/svg}")
        if tag not in allowed:
            raise ValueError(f"{context}: unsupported SVG element {tag!r}")
        node.tag = tag
        if tag == "svg" and node is not root:
            raise ValueError(f"{context}: nested SVG viewports are not extracted groups")
        is_pin = inside_pin or node.get("c_partid") == "part_pin"
        if (tag in {"text", "tspan"} or node.get("c_partid") == "part_attr") and not is_pin:
            raise ValueError(f"{context}: non-pin ATTR/text must come from the plan")
        for name, value in node.attrib.items():
            local_name = name.rsplit("}", 1)[-1].lower()
            if local_name.startswith("on") or local_name in {"href", "src"}:
                raise ValueError(f"{context}: external or active attribute {name!r}")
            if re.search(r"url\s*\(|javascript:|expression\s*\(", value, re.I):
                raise ValueError(f"{context}: external or active SVG dependency")
        identifier = node.get("id")
        if identifier is not None:
            if not identifier or identifier in identifiers:
                raise ValueError(f"{context}: duplicate or empty SVG id {identifier!r}")
            identifiers[identifier] = prefix + "-" + identifier.encode("utf-8").hex()
        for child in node:
            validate(child, is_pin)

    validate(root)
    if root.tag != "svg":
        raise ValueError(f"{context}: expected a self-contained svg root")
    for node in root.iter():
        if node.get("id") is not None:
            node.set("id", identifiers[node.get("id")])
        if node.tag == "style":
            css = node.text or ""
            if re.search(r"@|url\s*\(|expression\s*\(|/\*|\\", css, re.I):
                raise ValueError(f"{context}: external or unsupported CSS dependency")
            blocks = list(re.finditer(r"([^{}]+)\{([^{}]*)\}", css))
            if re.sub(r"([^{}]+)\{([^{}]*)\}", "", css).strip():
                raise ValueError(f"{context}: unsupported CSS structure")

            def rename_id(match: re.Match[str]) -> str:
                identifier = match.group(1)
                if identifier not in identifiers:
                    raise ValueError(f"{context}: CSS refers to unknown id {identifier!r}")
                return "#" + identifiers[identifier]

            node.text = "".join(
                ",".join(
                    f"#{prefix} " + re.sub(r"#([\w-]+)", rename_id, selector.strip())
                    for selector in block.group(1).split(",")
                ) + "{" + block.group(2) + "}"
                for block in blocks
            )
    group = ET.Element("g", {
        "id": prefix, "data-native-part": part_id,
        "data-native-symbol": art.symbol_ref, "data-native-source": art.source,
    })
    # Root viewport dimensions describe the extraction, not a new clipping box.
    root.tag = "g"
    for name in ("viewBox", "width", "height"):
        root.attrib.pop(name, None)
    group.append(root)
    return group


def _grid(box: Box, scale: float, x, y) -> list[str]:
    """A faint every-50-units grid, so a reader can measure by eye."""
    out: list[str] = []
    step = 50.0
    stroke_width = f"{0.6 * scale:g}"
    start = step * int(box[0] // step)
    while start <= box[2]:
        if start >= box[0]:
            out.append(
                f'<line x1="{x(start):.3f}" y1="{y(box[3]):.3f}" '
                f'x2="{x(start):.3f}" y2="{y(box[1]):.3f}" '
                f'stroke="{_COLOURS["grid"]}" stroke-width="{stroke_width}"/>'
            )
        start += step
    start = step * int(box[1] // step)
    while start <= box[3]:
        if start >= box[1]:
            out.append(
                f'<line x1="{x(box[0]):.3f}" y1="{y(start):.3f}" '
                f'x2="{x(box[2]):.3f}" y2="{y(start):.3f}" '
                f'stroke="{_COLOURS["grid"]}" stroke-width="{stroke_width}"/>'
            )
        start += step
    return out


def _caption_lines(
    plan: LayoutPlan, title: str, box: Box, scale: float
) -> list[str]:
    """The strip's text: what this is, and the raw numbers.

    Four fixed lines plus at most four notes — the count :func:`_caption_height`
    is fed, so the canvas and the text can never disagree about how tall the
    strip has to be.
    """
    metrics = ", ".join(
        f"{key}={value:g}" for key, value in sorted(plan.evidence.soft_metrics.items())
    ) or "soft metrics: not measured"
    return [
        title or "boardwise compiled plan (offline preview)",
        f"{PREVIEW_KIND}  geometry {plan.geometry_sha256()[:12]}  "
        f"size {box[2] - box[0]:g} x {box[3] - box[1]:g} units  scale {scale:g}",
        f"verdict {plan.evidence.verdict}  checker {plan.evidence.checker or 'not run'}",
        f"soft metrics: {metrics}",
        *[note[:150] for note in plan.notes[:4]],
    ]


def _caption_height(count: int) -> float:
    """Canvas units the caption strip reserves for ``count`` text lines.

    Never less than :data:`CAPTION_MIN_HEIGHT`, which is what the strip reserved
    when it was the constant 90 — five lines, the most a plan with one note
    produces. Only a caption that did not fit grows the canvas.
    """
    needed = CAPTION_TOP + (count - 1) * CAPTION_LINE_HEIGHT + CAPTION_DESCENT
    return max(CAPTION_MIN_HEIGHT, needed)


def _caption(lines: list[str], height: float) -> list[str]:
    """The caption's ``<text>`` elements, laid out on the strip below the drawing."""
    out: list[str] = []
    for index, line in enumerate(lines):
        out.append(
            f'<text x="8" y="{height + CAPTION_TOP + index * CAPTION_LINE_HEIGHT:.3f}" '
            f'fill="{_COLOURS["caption"]}">{escape(line)}</text>'
        )
    return out


# ------------------------------------------------------------------ geometry


def _book(
    profiles: Mapping[str, SymbolProfile] | Sequence[SymbolProfile],
) -> dict[str, SymbolProfile]:
    if isinstance(profiles, Mapping):
        return {str(key): value for key, value in profiles.items()}
    return {profile.symbol_ref: profile for profile in profiles}


def _transform(
    local: tuple[float, float], pose: SymbolPose, origin: tuple[float, float]
) -> tuple[float, float]:
    """The same rigid transform the compiler and the checker use.

    Imported from `core.geometry` rather than re-derived: a preview drawn with its
    own convention would show a *different* drawing from the one the checker
    measured, which is the one thing a preview must not do.
    """
    from boardwise.core.geometry import transform_point

    return transform_point(
        local[0], local[1], rotation=pose.rotation, mirror=pose.mirror,
        ox=origin[0], oy=origin[1],
    )


def _body_box(
    profile: SymbolProfile | None, pose: SymbolPose, origin: tuple[float, float]
) -> Box | None:
    if profile is None or profile.body is None:
        return None
    x0, y0, x1, y1 = profile.body
    corners = [
        _transform(corner, pose, origin)
        for corner in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    ]
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    return (min(xs), min(ys), max(xs), max(ys))


def _normalised_box(item: Box) -> Box:
    """``item`` with its lower corner first — the one convention `_body_box` uses.

    A box read from a document may state either corner first; a ``rect`` written
    from a reversed box carries a negative ``width`` and SVG drops it entirely,
    which is how a text box used to vanish from the preview without a word.
    """
    left, right = sorted((float(item[0]), float(item[2])))
    bottom, top = sorted((float(item[1]), float(item[3])))
    return (left, bottom, right, top)


def _content_box(
    plan: LayoutPlan,
    book: Mapping[str, SymbolProfile],
    keepouts: Sequence[Box] = (),
    frames: Sequence[tuple[str, Box]] = (),
) -> Box:
    """The drawing's own extent, used as the frame when no page is stated.

    Everything the picture draws is in it — including the keep-outs and module
    frames, which are exactly the boxes "does it fit" is answered with, and a
    lone junction, which can be the only thing outside a symbol's own extent.
    """
    boxes: list[Box] = []
    for part in plan.parts:
        profile = book.get(part.symbol_ref)
        body = _body_box(
            profile, SymbolPose(int(part.rotation), part.mirror), (part.x, part.y)
        )
        if body is not None:
            boxes.append(body)
        if profile is not None:
            for pin in profile.pins:
                tip = _transform(
                    pin.tip, SymbolPose(int(part.rotation), part.mirror),
                    (part.x, part.y),
                )
                boxes.append((tip[0], tip[1], tip[0], tip[1]))
    for symbol in plan.power_symbols:
        boxes.append((symbol.x, symbol.y, symbol.x, symbol.y))
    for text in plan.texts:
        boxes.append(_normalised_box(text.bbox))
    for label in plan.labels:
        boxes.append(_normalised_box(label.bbox))
    for segment in plan.segments:
        for point in segment.points:
            boxes.append((point[0], point[1], point[0], point[1]))
    for junction in plan.junctions:
        boxes.append((junction.x, junction.y, junction.x, junction.y))
    for keep in keepouts:
        boxes.append(_normalised_box(keep))
    for _, frame in frames:
        boxes.append(_normalised_box(frame))
    if not boxes:
        return (-PREVIEW_MARGIN, -PREVIEW_MARGIN, PREVIEW_MARGIN, PREVIEW_MARGIN)
    return (
        min(box[0] for box in boxes) - PREVIEW_MARGIN,
        min(box[1] for box in boxes) - PREVIEW_MARGIN,
        max(box[2] for box in boxes) + PREVIEW_MARGIN,
        max(box[3] for box in boxes) + PREVIEW_MARGIN,
    )


@dataclass(frozen=True)
class PreviewNote:
    """What one preview file says, for a caller that lists them."""

    path: str
    geometry: str
    verdict: str
