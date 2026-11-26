"""622-B: the three closings of the draw line's 622 batch, each pinned by its own case.

The batch's premise is that three small holes survive in code that is otherwise
gated, and each one is worth exactly one case here — a case that is **red before
the change** and green after, not a restatement of a value that was already true.

1. **A stated page box on the ordinary (non-island) build is a sheet.**
   `drawcompiler._build_one_variant` / `_build_path_first_variant` /
   `_build_service_group_variant` handed the readability gate
   `keepouts=ctx.budget.keepouts` and nothing else, while the island path derives
   the sheet's own block itself (`_island_keepouts`).  The CLI derives that block
   for a multi-island page only (`cli._draw_compile`), so a **single-island** page
   compiled with `--page-box` reached the gate with no block at all and a drawing
   could be shipped inside the title block S-01 calls 禁地.  The case below states
   a sheet whose block covers the drawing's own room and requires the refusal to
   name the keep-out — measured: `power_entry_xt30` on `(0, 0, 800, 240)` used to
   deliver 4 candidates with 18 of its objects inside `(-10, 10)-(790, 190)`.
   The control beside it states a sheet the drawing clears, so the fix cannot be
   mistaken for "a stated page is refused".

2. **`patchpin`'s call-site count is a fact, not a sentence.**  The docstring of
   `live_pin_refs` said `live_pin_nets` keeps its pair shape "for the twelve call
   sites already written against it" (571-D-1).  The count is measured here off
   the tree, so the sentence cannot drift away from it again in silence.

3. **`cli._draw_same_box` is not a prefix test.**  It compared with `zip`, which
   stops at the shorter sequence: `(0, 0)` against `(0, 0, 1169, 826)` was
   "the same sheet".  Two boxes are the same sheet only when they are the same
   box, and an equal-length comparison keeps its behaviour to the float.
"""

from __future__ import annotations

import json
from pathlib import Path

from boardwise import cli
from boardwise.core import pageframe
from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"

#: The sheet whose block covers the drawing's room: `power_entry_xt30` packs into
#: the bottom strip, and the block on this page is `(-10, 10)-(790, 190)`.
CROWDED_SHEET = (0.0, 0.0, 800.0, 240.0)
#: The same drawing on a sheet it clears — the control for the case above.
CLEAR_SHEET = (0.0, 0.0, 560.0, 450.0)


def _library(stem: str) -> dict[str, SymbolProfile]:
    payload = json.loads(
        (SPECS / f"{stem}.library.json").read_text(encoding="utf-8")
    )
    return {
        profile.symbol_ref: profile
        for profile in (
            SymbolProfile.from_dict(entry) for entry in payload["profiles"]
        )
    }


def _triplet(stem: str):
    return (
        CircuitSpec.load(SPECS / f"{stem}.circuit.json"),
        PresentationSpec.load(SPECS / f"{stem}.presentation.json"),
        _library(stem),
    )


# ==================================== 1. the ordinary build reads its sheet's block


def test_a_stated_page_box_keeps_the_ordinary_build_out_of_the_title_block() -> None:
    """A single-island page that states a sheet must clear that sheet's block.

    Measured before the change: `ok=True`, 4 candidates, and the first candidate
    drew 18 objects (part bodies, wires, texts) inside the derived block.  The
    block is the sheet's own table, not an extra the caller may forget, so the
    ordinary path has to derive it exactly as the island path does.
    """
    circuit, presentation, book = _triplet("power_entry_xt30")
    assert len(presentation.effective_islands()) == 1, (
        "this case is about the **ordinary** build — a multi-island page takes "
        "the island path, which derives the block already"
    )
    block = pageframe.title_block_keepouts(CROWDED_SHEET)
    assert block, "the crowded sheet must derive a block, or the case proves nothing"

    result = dc.compile(
        circuit, presentation, book, dc.CompileBudget(page_box=CROWDED_SHEET),
    )

    assert not result.ok, (
        "a sheet was stated and the block it derives covers the drawing's own "
        f"room {block[0]!r}; the ordinary build still shipped "
        f"{len(result.candidates)} candidate(s)"
    )
    details = " | ".join(failure.detail for failure in result.failures)
    assert "keep-out" in details, (
        "the refusal must name the keep-out — any other refusal is a different "
        f"answer, not this guard: {details}"
    )


def test_a_stated_page_box_the_drawing_clears_still_compiles() -> None:
    """The control: deriving the block is not a licence to refuse a stated page.

    Measured on this sheet: the drawing packs clear of the block, so a compile
    that states it has to keep its candidates.
    """
    circuit, presentation, book = _triplet("power_entry_xt30")
    result = dc.compile(
        circuit, presentation, book, dc.CompileBudget(page_box=CLEAR_SHEET),
    )
    assert result.ok, [failure.detail for failure in result.failures]
    assert result.candidates


# ============================================ 2. patchpin's count is measured


def _live_pin_nets_call_sites() -> int:
    """Every production call of `patchpin.live_pin_nets`, counted off the tree.

    The definition itself is not a call site; a docstring that names the function
    without a call (``:func:`live_pin_nets```) is not one either.
    """
    total = 0
    for path in sorted((ROOT / "src" / "boardwise").rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if "live_pin_nets(" not in line:
                continue
            if line.lstrip().startswith("def live_pin_nets("):
                continue
            total += 1
    return total


def test_patchpin_states_the_measured_number_of_call_sites() -> None:
    from boardwise.engines import patchpin

    count = _live_pin_nets_call_sites()
    assert count == 11, (
        f"the tree now calls live_pin_nets {count} times; the docstring's number "
        "has to be re-measured with it (622-B counted 11)"
    )
    text = patchpin.live_pin_refs.__doc__ or ""
    assert "twelve" not in text, (
        "the docstring still says twelve call sites; the measured count is "
        f"{count} (571-D-1)"
    )
    assert "eleven" in text, (
        f"the docstring must state the measured count ({count}), not a vague one"
    )


# ============================================= 3. two boxes, or not the same box


def test_draw_same_box_refuses_a_length_mismatch() -> None:
    """`(0, 0)` is not the sheet `(0, 0, 1169, 826)`, whatever `zip` says."""
    assert cli._draw_same_box((0.0, 0.0), (0.0, 0.0, 1169.0, 826.0)) is False
    assert cli._draw_same_box((0.0, 0.0, 1169.0, 826.0), (0.0, 0.0)) is False
    # A longer box that merely starts with the shorter one is the same hole in
    # the other direction: the prefix agrees and the sheets are not the same.
    assert cli._draw_same_box((0.0, 0.0), (0.0, 0.0, 1.0)) is False


def test_draw_same_box_still_compares_equal_length_boxes_to_the_float() -> None:
    """The equal-length answer is untouched: same box true, noise tolerated."""
    sheet = (0.0, 0.0, 1169.0, 826.0)
    assert cli._draw_same_box(sheet, sheet) is True
    assert cli._draw_same_box(sheet, (0.0, 0.0, 1169.0, 826.0 + 1e-9)) is True
    assert cli._draw_same_box(sheet, (0.0, 0.0, 1169.0, 826.1)) is False
