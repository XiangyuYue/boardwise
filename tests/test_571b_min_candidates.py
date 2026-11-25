"""571-B-H1: ``PageCompileBudget.min_candidates`` must actually be consumed.

Before the fix the field was declared (``pagecompiler.py:318``), copied into the
cheaper module budget and then never read again: ``min_candidates=99`` produced
the same eight pages as the default and said nothing, and ``min_candidates=0``
or ``min_candidates > max_candidates`` were accepted without a word. These tests
pin the two halves of the repair — the *refusal* of a floor that cannot be
honoured, and the *report* of a floor the finite search did not reach — and the
negative controls that keep the default budget byte-identical.

The fixtures are 056's own scene 8 (three modules, 12 variants built, 8 legal
pages), so this file does not carry a second copy of a circuit.
"""

from __future__ import annotations

import dataclasses
import hashlib

import pytest

import test_056_pagecompiler as t056

from boardwise.engines import pagecompiler as pc

#: 056's page budget: the 1169x826 sheet, the default floor of 3 and ceiling of 8.
PAGE = t056.PAGE

#: The sentence the compiler uses when the search built fewer pages than the
#: caller's floor asks for. Deliberately a phrase, not a whole string: the test
#: pins that the shortfall is *named*, and the note's numbers are checked below.
SHORTFALL = "fewer than budget.min_candidates"

#: The pre-fix baseline of the default budget, captured before the change
#: (`.tmp_571b1/golden_prefix.json`). Byte-equivalence means these three numbers
#: do not move: eight pages, the same geometry, the same ranking.
GOLDEN_PAGES = 8
GOLDEN_DIGEST = (
    "39711a22397247dff7566deb9de6daf7e158f9598da29f5a3bfd3cf4fe38772c"
)
GOLDEN_KEYS = (
    ("0", "0", "0.0", "0.0", "0.0", "0.0", "306440.0"),
    ("0", "0", "0.0", "0.0", "0.0", "0.0", "325240.0"),
    ("0", "0", "0.0", "0.0", "0.0", "0.0", "358380.0"),
    ("0", "0", "0.0", "0.0", "0.0", "0.0", "378180.0"),
    ("0", "0", "463.5", "0.0", "0.0", "0.0", "429660.0"),
    ("0", "0", "488.5", "0.0", "0.0", "0.0", "463060.0"),
    ("0", "0", "538.5", "0.0", "0.0", "0.0", "503250.0"),
    ("0", "0", "563.5", "0.0", "0.0", "0.0", "539400.0"),
)


def compile_with(budget: pc.PageCompileBudget) -> pc.PageCompileResult:
    scene = t056.scenes()[8]
    return pc.compile_page(
        scene.circuit, scene.presentation, t056.library(), budget
    )


def page_digest(result: pc.PageCompileResult) -> str:
    """One digest over the pages, in order — the whole of what a caller draws."""
    rolling = hashlib.sha256()
    for page in result.pages:
        rolling.update(page.page_geometry_sha256().encode())
    return rolling.hexdigest()


def ranked_keys(result: pc.PageCompileResult) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(str(value) for value in item.key)
        for item in result.ranked[: len(result.pages)]
    )


def shortfall_notes(result: pc.PageCompileResult) -> list[str]:
    return [note for note in result.notes if SHORTFALL in note]


# --------------------------------------------------------------- 会漏（先红）


def test_a_floor_the_search_cannot_reach_is_named_in_the_notes():
    """min=99 with a legal ceiling: the answer must say it is short, not pretend."""
    budget = dataclasses.replace(PAGE, min_candidates=99, max_candidates=99)
    result = compile_with(budget)

    assert result.ok, result.render_failures()
    assert len(result.pages) < 99, "the fixture is supposed to fall short here"
    notes = shortfall_notes(result)
    assert len(notes) == 1, f"expected exactly one shortfall note, got {result.notes!r}"
    note = notes[0]
    assert "min_candidates" in note
    assert "99" in note, f"the note must carry the requirement, got {note!r}"
    assert str(len(result.pages)) in note, (
        f"the note must carry the actual page count {len(result.pages)}, got {note!r}"
    )


def test_a_floor_below_one_is_refused_by_name():
    """min=0 asks for a page count every answer violates: refused, not ignored."""
    budget = dataclasses.replace(PAGE, min_candidates=0)
    with pytest.raises(pc.PageCompileError) as caught:
        compile_with(budget)
    message = str(caught.value)
    assert "budget.min_candidates" in message, message
    assert "0" in message, message


def test_a_floor_above_the_ceiling_is_refused_by_name():
    """min=99, max=8: no budget can satisfy both, so the budget itself is invalid."""
    budget = dataclasses.replace(PAGE, min_candidates=99, max_candidates=8)
    with pytest.raises(pc.PageCompileError) as caught:
        compile_with(budget)
    message = str(caught.value)
    assert "budget.min_candidates" in message, message
    assert "budget.max_candidates" in message, message
    assert "99" in message, message
    assert "8" in message, message


# ------------------------------------------------------- 负控（前后都绿）


def test_the_default_budget_stays_byte_identical_and_silent():
    """min=3 of 8 pages: no note, and the old bytes, key for key."""
    result = compile_with(PAGE)

    assert len(result.pages) == GOLDEN_PAGES
    assert page_digest(result) == GOLDEN_DIGEST
    assert ranked_keys(result) == GOLDEN_KEYS
    assert not shortfall_notes(result), result.notes


def test_a_floor_of_one_is_reached_and_not_reported():
    """The floor is satisfied (1 <= 8): the note must not appear."""
    budget = dataclasses.replace(PAGE, min_candidates=1)
    result = compile_with(budget)

    assert len(result.pages) == GOLDEN_PAGES
    assert page_digest(result) == GOLDEN_DIGEST
    assert not shortfall_notes(result), result.notes
