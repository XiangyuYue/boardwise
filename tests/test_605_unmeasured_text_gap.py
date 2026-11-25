"""605: a page whose only statement is one rail flag has no gap to measure.

570-A2-H1: `_min_text_gap` declares "fewer than two text boxes => UNMEASURED,
never an exception, never 0.0", but `_text_boxes` gives one rail flag **two**
boxes (its glyph and the name row the host prints beside it, 147). The 147b
exclusion skips exactly that pair, so on a page with nothing else `best` stayed
``None`` and the final ``assert`` ended the whole ``check()``.

The contract here is the same one the one-box page already has: the metric says
"cannot measure" in words, and the exclusion stays a *pair* rule — a flag still
has to keep its distance from every other statement on the page.
"""

from __future__ import annotations

import pytest

from boardwise.core.layoutplan import (
    LayoutPlan,
    LayoutPowerSymbol,
    LayoutSource,
)
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import readability
from boardwise.engines.readability import UNMEASURED

HASH = "a" * 64
FLAG = "PWR-HVDC"

# The two boxes 570-A2's probe used: a flag's drawn extent and its own name row,
# edge to edge (that adjacency is the host's typography, measured in 147).
GLYPH = (100.0, 100.0, 120.0, 110.0)
NAME = (120.0, 100.0, 140.0, 110.0)


def _rail_flag() -> SymbolProfile:
    """A pin-less rail flag: its origin is the connection, its body hangs away."""
    return SymbolProfile(
        symbol_ref=FLAG,
        title="Rail flag",
        body=(-5.0, 0.0, 5.0, 10.0),
        pins=[],
    )


def _one_statement() -> list[tuple[str, tuple[float, float, float, float], str, str]]:
    return [
        ("powerSymbols[0]", GLYPH, "powerSymbols[0]", "HVDC"),
        ("powerSymbols[0] name", NAME, "powerSymbols[0]", "HVDC"),
    ]


def _plan(*, power_symbols=()) -> LayoutPlan:
    return LayoutPlan(
        source=LayoutSource(circuit_sha256=HASH, presentation_sha256=HASH),
        parts=[],
        segments=[],
        junctions=[],
        labels=[],
        power_symbols=list(power_symbols),
        texts=[],
    )


# ------------------------------------------------- 1. the crash 570-A2 found


def test_a_page_whose_only_statement_is_one_flag_reports_unmeasured():
    """Two boxes that are **one statement** leave no pair to measure.

    Today this raises ``AssertionError`` from the ``assert best is not None``
    line; the one-box page right below already answers ``UNMEASURED`` in words,
    and that is the answer here too.
    """
    gap, reasons = readability._min_text_gap(_one_statement())
    assert gap == UNMEASURED
    assert reasons, "an unmeasured metric has to say why"
    joined = " ".join(reasons)
    assert "one statement" in joined, joined
    assert "cannot measure" in joined, joined


def test_the_real_single_flag_box_set_from_the_host_text_model_is_unmeasured():
    """Not a hand-written name list: the boxes come out of ``_text_boxes``.

    One rail flag on the page and no other text => its glyph box plus the name
    row the host prints = the two boxes of one statement, which is the page
    570-A2-H1 crashed on.
    """
    plan = _plan(power_symbols=[
        LayoutPowerSymbol(symbol_ref=FLAG, symbol_hash=HASH, net="HVDC",
                          x=500.0, y=400.0, rotation=0.0),
    ])
    boxes = readability._text_boxes(plan, {FLAG: _rail_flag()})
    assert [name for name, *_ in boxes] == [
        "powerSymbols[0]", "powerSymbols[0] name",
    ], "the fixture has to be the page with one statement on it"
    gap, reasons = readability._min_text_gap(boxes)
    assert gap == UNMEASURED
    assert reasons and "one statement" in " ".join(reasons)


# --------------------------------- 2. the existing guards and the narrow exclusion


def test_zero_and_one_box_still_report_unmeasured():
    assert readability._min_text_gap([])[0] == UNMEASURED
    assert readability._min_text_gap(_one_statement()[:1])[0] == UNMEASURED


def test_an_added_statement_is_measured_and_the_flag_pair_stays_exempt():
    """The exclusion is a **pair**, not the flag's boxes.

    A foreign row 60/90 units away leaves the flag measurable against it; if the
    integration had dropped the flag's boxes (or the exclusion), the closest pair
    would be the flag's own glyph/name at 0.0.
    """
    boxes = _one_statement() + [
        ("texts[0]", (200.0, 200.0, 210.0, 210.0), "U1", "10k"),
    ]
    gap, reasons = readability._min_text_gap(boxes)
    assert gap == pytest.approx(108.1665, abs=0.01)  # hypot(60, 90)
    assert reasons[0].startswith("closest pair ")
    assert "texts[0]" in reasons[0]


# ------------------------------------------- 3. unchanged ordinary measurements


def test_two_ordinary_statements_keep_their_gap_and_touching_count():
    boxes = [
        ("texts[0]", (0.0, 0.0, 10.0, 10.0), "U1", "U1"),
        ("texts[1]", (20.0, 0.0, 30.0, 10.0), "U2", "U2"),
    ]
    gap, reasons = readability._min_text_gap(boxes)
    assert gap == pytest.approx(10.0)
    assert len(reasons) == 1

    boxes[1] = ("texts[1]", (10.0, 0.0, 20.0, 10.0), "U2", "U2")
    gap, reasons = readability._min_text_gap(boxes)
    assert gap == 0.0
    assert any("touch edge to edge" in reason for reason in reasons)
    assert not any("genuinely intersect" in reason for reason in reasons)


def test_two_ordinary_statements_that_overlap_keep_the_overlap_count():
    boxes = [
        ("texts[0]", (0.0, 0.0, 10.0, 10.0), "U1", "U1"),
        ("texts[1]", (5.0, 5.0, 15.0, 15.0), "U2", "U2"),
    ]
    gap, reasons = readability._min_text_gap(boxes)
    assert gap == 0.0
    assert any("genuinely intersect" in reason for reason in reasons)
    assert not any("touch edge to edge" in reason for reason in reasons)
