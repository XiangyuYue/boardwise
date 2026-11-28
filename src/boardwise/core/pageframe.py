"""Where the sheet's title block is — the keep-out S-01 is about.

`docs/schematic-style-spec.md` S-01 is a hard rule: 「标题栏是禁地，整图下方留白」
— content does not enter the title-block rectangle, and the drawing keeps ~15% of
the sheet height blank below it.  This module is the **first half of that
sentence**: it says, for a page and its declared sheet attributes, which
rectangle the title block occupies.  The second half (the blank band) is a
packing rule and lives in `islandlayout.PageBudget`.

**The block is the sheet symbol's own table, not a ratio.**  A page's frame is a
library *symbol* (嘉立创EDA专业版: 图纸符号) attached to the page; the title block
is a ``TABLE`` primitive inside that symbol, and the page's declared attributes
(``Width`` / ``Height`` / ``Border`` / ``Blade Width`` / ``Title Block`` /
``Title Block Position`` / the region counts) are attributes of the symbol.  Read
out of the golden fixtures — the same ``Drawing-Symbol_A4`` in
``ProPrj_ROBOT ctrl FOC`` (1655x1170) and ``ch340_golden`` (1170x825):

* ``TABLE.startX = 460, startY = -190``, ``colSizes`` summing to **700.0**,
  ``rowSizes`` summing to **180.0** — the block is 700 x 180, in canvas units;
* and the page's own copies of the symbol's attributes are *translated* with the
  page width and **not** with the page height: every field's x on the 1655-wide
  page is its x on the 1170-wide page **plus 485** (= 1655 - 1170), while every y
  is identical on the 825-tall and the 1170-tall page.  So the block is anchored
  to the **corner** and does not scale with the sheet: the two pages put it at
  ``(460, 10)-(1160, 190)`` and ``(945, 10)-(1645, 190)``.

That x-shift is the whole reason this is a model rather than a constant: a page
whose ``Width`` is not 1170 moves the block, and a keep-out that did not move
with it would leave the sheet's own title block outside the reserved area.

**The render agrees.**  ``evidence/521/521_page.svg`` (the editor's own
``export.render`` of the golden flyback page, 1170x825) draws that table at
``x 460..1160, y -190..-10`` screen = ``(460, 10)-(1160, 190)`` canvas — the same
numbers the file states, measured from the picture.  Both were checked in this
batch (``evidence/530g/probes/25_sheet_symbol.py`` and the SVG walk that reads
the ``table-*`` fill rects).

**The block is bigger than the legacy constant.**  `engines.layout.TITLE_BLOCK`
carves 320 x 100 at the bottom-right (``(W - 330, 10, W - 10, 110)``, task 006's
"标题栏禁区（右下 330×110）"); the real block is 700 x 180.  The legacy rectangle
is therefore a **subset** of the real one, which is why S-01 could not be kept by
the constant: on the flyback's own sheet the island page as packed before this
batch had 41 objects inside the *real* block (``evidence/530g/report.md``).  This
module states the real one; the legacy constant is left where it is, because
`engines.layout` is the shelf packer's own calibration and not this module's
caller.

**Positions.**  ``Title Block Position`` selects a corner.  Only **3 =
bottom-right** is measured (every page we have that is not ``Title Block = 0``
declares 3, and the render above shows a bottom-right block), and it is the only
value `TITLE_BLOCK_POSITION_MEASURED` holds; the other three corners are the
declared reading of the selector and are marked unmeasured.  An unknown or absent
value falls back to the measured corner — a keep-out that is stated and slightly
wrong costs layout space, and one that is skipped costs the rule.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from .symbolprofile import Box

#: The block's own drawn size, in canvas units.  Sum of ``colSizes`` and of
#: ``rowSizes`` in the ``Drawing-Symbol_A4`` table — see the module docstring for
#: which two fixtures state it and which render draws it.
TITLE_BLOCK_SIZE: tuple[float, float] = (700.0, 180.0)

#: The smallest page that can hold the block plus the frame inset on both sides.
#: Stated so a caller can refuse a page **before** the packing starts: a block
#: wider than its sheet is not a keep-out, it is a rectangle that reaches outside
#: the drawing (634A-02/03).
MINIMUM_TITLE_BLOCK_PAGE: tuple[float, float] = (
    TITLE_BLOCK_SIZE[0] + 2 * 10.0,
    TITLE_BLOCK_SIZE[1] + 2 * 10.0,
)

#: ``Blade Width`` as every fixture we have declares it — the frame inset, and so
#: the gap between the block and the sheet edge.  Used when a page does not state
#: one; a stated non-positive value is treated as "not stated" rather than as
#: "the block hangs off the sheet".
BLADE_WIDTH_DEFAULT: float = 10.0

#: ``Title Block Position`` -> ``(horizontal, vertical)`` corner, **as declared**.
#:
#: Only ``3`` has ever been measured (the rendered block on every page we have).
#: The other three are the reading this repo has written down, not a reading
#: anyone checked: no 2x2 grid order is claimed, because the two orderings
#: disagree about 3 and 4 and only 3 is pinned by evidence (634A-08).
TITLE_BLOCK_POSITIONS: Mapping[str, tuple[str, str]] = {
    "1": ("left", "top"),
    "2": ("left", "bottom"),
    "3": ("right", "bottom"),
    "4": ("right", "top"),
}

#: The positions this repo has actually seen on a page.  A page's own render is
#: the evidence for 3 (module docstring); 1, 2 and 4 are declared, not measured,
#: and a future batch that can drive the editor should move them here one at a
#: time.
TITLE_BLOCK_POSITION_MEASURED: frozenset[str] = frozenset({"3"})

#: What ``Title Block Position`` falls back to when the page does not state a
#: usable value: the corner that was measured.
DEFAULT_TITLE_BLOCK_POSITION = "3"

#: ``Title Block`` -> the symbol's template selector, as far as this repo can
#: read it: every page that has a title block declares ``1``, and the one page
#: that declares ``0`` (级联多电平-主拓扑, 900x825) declares no block size at all.
#: That reading is **unverified** — nothing here has seen a page with ``0``
#: rendered — so it is only honoured by
#: :func:`title_block_from_sheet_attrs`, which is the reader that has the
#: attribute in front of it; a caller with no attributes (the compiler path)
#: always reserves the block, which is the safe direction to be wrong in.
NO_TITLE_BLOCK = "0"


class PageFrameError(ValueError):
    """A page that cannot hold its own title block (634A-02/03)."""


def _as_float(value: Any) -> float | None:
    """``value`` as a float, or ``None`` when it is not a usable number."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _corner(position: Any) -> tuple[tuple[str, str], bool]:
    """``((horizontal, vertical), assumed)`` for a declared position.

    ``assumed`` is true when the value is not one this build reads — an absent
    selector, ``0``, ``9``, ``right-bottom``.  The *rectangle* is the same as a
    declared ``3`` would give (the measured corner, and 634A-01's safe direction),
    but the caller can now tell the two apart and say so (634A-07).
    """
    text = str(position).strip() if position is not None else ""
    corner = TITLE_BLOCK_POSITIONS.get(text)
    if corner is None:
        return TITLE_BLOCK_POSITIONS[DEFAULT_TITLE_BLOCK_POSITION], True
    return corner, False


def _inset(attrs: Mapping[str, Any]) -> tuple[float, str]:
    """``(margin, note)`` — the frame inset a page declares.

    ``Blade Width`` first, then ``Border``, then :data:`BLADE_WIDTH_DEFAULT`.  A
    non-positive number is "not stated", the reading this module has always had:
    a stated ``0`` must not hang the block off the sheet.  ``note`` is empty
    unless the inset came from ``Border`` — which is the *frame's* inset, not the
    block's, so a page that states only that one is worth saying out loud
    (634A-04).  The two are not compared when both are stated: on every measured
    page ``Border`` is the frame line width (1) and ``Blade Width`` the gap (10),
    so "they disagree" is the normal case, not a defect.
    """
    blade = _as_float(attrs.get("Blade Width"))
    if blade is not None and blade > 0:
        return blade, ""
    border = _as_float(attrs.get("Border"))
    if border is not None and border > 0:
        return border, (
            f"`Blade Width` is not stated, so the block is inset by the frame's own "
            f"`Border` ({border:g})"
        )
    return BLADE_WIDTH_DEFAULT, ""


def title_block_fits(
    page_box: Box, *, border: float = BLADE_WIDTH_DEFAULT
) -> bool:
    """Can this page hold the block and its inset on both touched edges (634A-02)?

    A rectangle wider or taller than the sheet is not a keep-out: nothing can be
    packed clear of it, and a plan that carries it across a run carries a
    rectangle that reaches outside the drawing.  The caller decides whether to
    refuse the page — this is the measurement, not the policy.
    """
    margin = _as_float(border)
    if margin is None or margin < 0:
        margin = BLADE_WIDTH_DEFAULT
    width, height = TITLE_BLOCK_SIZE
    return (page_box[2] - page_box[0]) >= width + margin and (
        page_box[3] - page_box[1]
    ) >= height + margin


def title_block_box(
    page_box: Box,
    *,
    border: float = BLADE_WIDTH_DEFAULT,
    position: Any = DEFAULT_TITLE_BLOCK_POSITION,
    notes: list[str] | None = None,
) -> Box:
    """The title block's rectangle on ``page_box``, in the page's own coordinates.

    ``page_box`` is ``(x0, y0, x1, y1)`` in canvas units, y **up** (010c), exactly
    the box `drawcompiler.CompileBudget.page_box` and
    `islandlayout.PageBudget.page_box` take.  ``border`` is the frame inset
    (``Blade Width``); it is floored at 0 so a stated 0 puts the block flush with
    the corner instead of outside the sheet.

    The block keeps its own size (``TITLE_BLOCK_SIZE``) — it does not scale with
    the sheet — and is anchored to the corner ``position`` names, inset by
    ``border`` from both edges it touches.
    """
    width, height = TITLE_BLOCK_SIZE
    margin = _as_float(border)
    if margin is None or margin < 0:
        margin = BLADE_WIDTH_DEFAULT
    (horizontal, vertical), assumed = _corner(position)
    if assumed and notes is not None:
        # 634A-07: the rectangle looks like a declared `3`; only this says it is not.
        notes.append(
            f"title block: {position!r} is not a position this build reads, so the "
            f"measured corner {DEFAULT_TITLE_BLOCK_POSITION!r} was assumed"
        )
    if horizontal == "left":
        x0, x1 = page_box[0] + margin, page_box[0] + margin + width
    else:
        x0, x1 = page_box[2] - margin - width, page_box[2] - margin
    if vertical == "bottom":
        y0, y1 = page_box[1] + margin, page_box[1] + margin + height
    else:
        y0, y1 = page_box[3] - margin - height, page_box[3] - margin
    return (x0, y0, x1, y1)


def page_box_from_sheet_attrs(attrs: Mapping[str, Any]) -> Box | None:
    """The page's own box ``(0, 0, Width, Height)``, or ``None`` when unstated.

    A page's origin is its bottom-left corner in canvas units — the frame the
    island page packs in and the one `--page-box 0,0,W,H` states by hand — so a
    page reader that has the declared attributes has the box too. ``None`` means
    the page stated no usable ``Width``/``Height``; it never means A4.
    """
    width = _as_float(attrs.get("Width"))
    height = _as_float(attrs.get("Height"))
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    return (0.0, 0.0, width, height)


def title_block_from_sheet_attrs(
    attrs: Mapping[str, Any],
    *,
    default_position: Any = DEFAULT_TITLE_BLOCK_POSITION,
    notes: list[str] | None = None,
) -> Box | None:
    """The title block's rectangle for a page's declared sheet attributes.

    ``attrs`` is what a page reader hands over — `parsers.schematic.PageLayout`'s
    ``sheet_attrs``, i.e. the ``Width``/``Height``/``Border``/``Blade Width``/
    ``Title Block``/``Title Block Position``/region-count strings straight out of
    the file.  The page box is then ``(0, 0, Width, Height)``: a page's own origin
    is its bottom-left corner in canvas units (the same frame the island page packs
    in), which is why the width is what moves the block and the height is not read
    by it at all.

    ``None`` means **"this page states no title block"**, and there is exactly one
    such case here: ``Title Block`` is :data:`NO_TITLE_BLOCK`, or the page states
    no usable ``Width``/``Height``.  The region counts (``X``/``Y Region Count``)
    are deliberately **not** read: they divide the frame into the zone ticks the
    editor draws, and the block's size and place are independent of them — the
    two measured pages declare 6x4 and put the same 700x180 block in the corner.
    """
    template = str(attrs.get("Title Block", "") or "").strip()
    if template == NO_TITLE_BLOCK:
        return None
    box = page_box_from_sheet_attrs(attrs)
    if box is None:
        return None
    border, inset_note = _inset(attrs)
    if notes is not None and inset_note:
        notes.append(f"title block: {inset_note}")
    position = attrs.get("Title Block Position")
    if position is None or not str(position).strip():
        position = default_position
    return title_block_box(box, border=border, position=position, notes=notes)


def title_block_keepouts(
    page_box: Box | None,
    *,
    position: Any = None,
    border: float | None = None,
    has_title_block: bool | None = None,
    notes: list[str] | None = None,
) -> tuple[Box, ...]:
    """The keep-out a compile states for a page it was handed, or ``()`` for none.

    ``page_box is None`` (no page stated) means the drawing defines its own frame,
    and a drawing with no sheet has no sheet's title block to keep out of.

    The three optional inputs are what 634A-01/-05 added: a caller that has the
    page's **attributes** hands them over (`position=`, `border=`,
    `has_title_block=`), and a caller that does not says so by leaving them
    ``None``.  ``None`` still reserves the block — the safe direction, since a
    skipped keep-out costs the rule — but every step that was an assumption is
    written into ``notes`` instead of being indistinguishable from a reading
    (634A-05: `Title Block=0` used to give one answer here and another from
    `title_block_from_sheet_attrs`).
    """
    if page_box is None:
        return ()
    if has_title_block is False:
        if notes is not None:
            notes.append(
                "title block: the page declares `Title Block = 0`, so no title-block "
                "keep-out was reserved"
            )
        return ()
    if has_title_block is None and notes is not None:
        notes.append(
            "title block: this call was handed a page box and no sheet attributes, "
            f"so the corner is assumed to be {DEFAULT_TITLE_BLOCK_POSITION!r} and the "
            "inset the measured default"
        )
    margin = _as_float(border)
    if margin is None or margin < 0:
        margin = BLADE_WIDTH_DEFAULT
    if not title_block_fits(page_box, border=margin):
        # 634A-02/03. The measurement is here; the **refusal** is a policy and
        # belongs at the compile entrance, which is where a page box is chosen
        # (岳 J3: 松一点 — do not hard-refuse inside a geometry helper, but say the
        # fact out loud so the caller can judge). `title_block_fits` and
        # `PageFrameError` are the two symbols that entrance needs; until it is
        # wired, the note below is what a reader gets.
        minimum = MINIMUM_TITLE_BLOCK_PAGE
        if notes is not None:
            notes.append(
                f"title block: the sheet is {page_box[2] - page_box[0]:g}x"
                f"{page_box[3] - page_box[1]:g}, smaller than the block it has to "
                f"hold ({TITLE_BLOCK_SIZE[0]:g}x{TITLE_BLOCK_SIZE[1]:g} plus the "
                f"frame inset {margin:g}) — the keep-out reaches outside the drawing; "
                f"the smallest page is {minimum[0]:g}x{minimum[1]:g}"
            )
    return (
        title_block_box(page_box, border=margin, position=position, notes=notes),
    )


#: The prefix of the note a compile writes into the **plan** when it reserved a
#: sheet's title block.  A plan is a file that travels (054 §四.1) and the
#: landing stage is a different run, so the fact "this drawing was packed for
#: this sheet, with the block kept out" has to be written down — a landing that
#: could not read it could not tell a protected drawing from the 530F/532 one
#: that landed 32 primitives in the title block.
KEEP_OUT_NOTE_PREFIX = "S-01 plan keep-out:"

#: ``page box (x0, y0, x1, y1)`` and ``title block (...)`` as
#: :func:`keep_out_note` writes them.  Parsed back by
#: :func:`page_keep_out_from_notes`; every value is spelled ``%.17g``, the
#: shortest form that parses back to the same Python float, because the landing
#: compares these boxes at 1e-6 (``cli._draw_same_box``) and the note is the only
#: carrier of the sheet between the two runs.  ``%g``'s 6 significant digits wrote
#: 1234.567 as ``1234.57`` and 1169.0049999 as ``1169``, which the landing then
#: called a different sheet.
_KEEP_OUT_PATTERN = re.compile(
    r"page box \(\s*([-0-9.eE+]+)\s*,\s*([-0-9.eE+]+)\s*,\s*([-0-9.eE+]+)\s*,\s*([-0-9.eE+]+)\s*\)"
    r"\s*,?\s*(?:title block|keep-out)\s*\(\s*"
    r"([-0-9.eE+]+)\s*,\s*([-0-9.eE+]+)\s*,\s*([-0-9.eE+]+)\s*,\s*([-0-9.eE+]+)\s*\)"
)


def keep_out_note(page_box: Box, keepouts: Iterable[Box]) -> str:
    """The note a compile writes so a later landing can read what it reserved.

    One line, machine-readable on the way back in
    (:func:`page_keep_out_from_notes`), and it says **which page** as well as
    which rectangle: a plan packed for a 1170-wide sheet landed on a 1655-wide
    one must be refused, and the block on the two is not the same rectangle.
    """
    boxes = tuple(keepouts)
    if not boxes:
        return f"{KEEP_OUT_NOTE_PREFIX} nothing was reserved"
    rect = boxes[0]
    return (
        f"{KEEP_OUT_NOTE_PREFIX} page box ({page_box[0]:.17g}, {page_box[1]:.17g}, "
        f"{page_box[2]:.17g}, {page_box[3]:.17g}), title block ({rect[0]:.17g}, "
        f"{rect[1]:.17g}, {rect[2]:.17g}, {rect[3]:.17g}); "
        f"corner {DEFAULT_TITLE_BLOCK_POSITION} (position not read at compile time), "
        f"fits {'yes' if title_block_fits(page_box) else 'no'} — the sheet's own "
        "table is a keep-out, so the packing was told to clear it"
    )


def page_keep_out_from_notes(notes: Iterable[Any]) -> tuple[Box, Box] | None:
    """``(page_box, title_block)`` out of a plan's own notes, or ``None``.

    ``None`` is the answer for a plan that never reserved anything — the two
    drawings that landed in a title block (530F deviation 4, 532's page A) carry
    exactly this shape, and the landing stage reads it as a refusal rather than
    as an absence of news.
    """
    for note in notes:
        text = str(note)
        if not text.startswith(KEEP_OUT_NOTE_PREFIX):
            continue
        found = _KEEP_OUT_PATTERN.search(text)
        if found is None:
            continue
        values = tuple(float(item) for item in found.groups())
        return (
            (values[0], values[1], values[2], values[3]),
            (values[4], values[5], values[6], values[7]),
        )
    return None
