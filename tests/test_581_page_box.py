"""581 W-N: a page and a box have to be *finite*, and a page has to fit a cap.

`outputs/hole569/g/REPRO.md` rows 569G-03 and 569G-04 are the two reproduced
holes this file pins:

* ``--page-box 0,0,nan,826`` used to be accepted, because ``0 >= nan`` is false
  and ``nan - 0 < 100`` is false, so neither the ordering check nor the size
  check ever fired.  The command exited 0 and wrote candidates whose SVG said
  ``width="nan"`` and whose page JSON carried a bare ``NaN`` literal.
* ``inf``/``1e9``/``1e308`` pages were accepted the same way and then hung the
  compiler for 20-45 s: nothing bounds how large a page may be, and the compile
  work grows with it.

Both validators are pinned here — ``cli._draw_page_box`` (finiteness **and** a
per-side size cap of 100000 canvas units) and ``symbolprofile.check_box``
(finiteness only; it also validates text boxes and keep-outs, where a page-size
cap would be a new, unasked-for rule).  The negative controls are the boxes that
are already legal: 1170x825, 1655x1170, 240x300 and pages at negative
coordinates must keep coming back unchanged, and the existing ordering / type /
``None`` semantics of ``check_box`` must not move.
"""

from __future__ import annotations

import time

import pytest

from boardwise import cli
from boardwise.core.layoutplan import LayoutPlanError
from boardwise.core.pagelayoutplan import PageLayoutPlanError
from boardwise.core.symbolprofile import SymbolProfileError, check_box


# ---------------------------------------------------------------------------
# cli._draw_page_box — finiteness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "0,0,nan,826",
        "0,0,NaN,826",
        "0,0,inf,826",
        "0,0,-inf,826",
        "nan,0,1170,825",
        "0,-inf,1170,825",
        "0,0,1170,inf",
        "-inf,0,1170,825",
    ],
)
def test_a_non_finite_page_box_is_refused_by_name(text):
    with pytest.raises(cli._DrawInputError) as excinfo:
        cli._draw_page_box(text)
    message = str(excinfo.value)
    assert text in message, "the refusal quotes the value it refused"
    assert "finite" in message, "the refusal says *why*: the coordinates are not finite"


def test_a_nan_page_box_cannot_reach_the_compiler_offline(tmp_path, capsys):
    """569G-03 at the entry point: exit 5, by name, and no candidate is written."""
    out = tmp_path / "out"
    code = cli.main([
        "draw", "compile",
        "--circuit", str(tmp_path / "missing.circuit.json"),
        "--presentation", str(tmp_path / "missing.presentation.json"),
        "--profiles", str(tmp_path / "missing.profiles.json"),
        "--page-box", "0,0,nan,826",
        "--out", str(out),
    ])
    captured = capsys.readouterr()
    assert code == 5, captured.err
    assert "nan" in captured.err.lower()
    assert "finite" in captured.err
    assert not out.exists(), "a refused page-box writes nothing"


# ---------------------------------------------------------------------------
# cli._draw_page_box — the per-side cap
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "0,0,100000.1,826",
        "0,0,1e9,826",
        "0,0,1e308,826",
        "0,0,1170,100000.1",
        "-1e9,0,1170,826",
        "-1e308,0,1170,826",
        "0,-1e9,1170,826",
    ],
)
def test_a_page_box_past_the_size_cap_is_refused_fast(text):
    started = time.monotonic()
    with pytest.raises(cli._DrawInputError) as excinfo:
        cli._draw_page_box(text)
    elapsed = time.monotonic() - started
    message = str(excinfo.value)
    assert "100000" in message, "the refusal names the cap it enforced"
    assert "canvas units" in message
    assert elapsed < 1.0, f"the cap is refused at parse time, not after {elapsed:.2f}s"


@pytest.mark.parametrize(
    "text,expected",
    [
        # the cap includes its own boundary
        ("0,0,100000,826", (0.0, 0.0, 100000.0, 826.0)),
        ("0,0,1170,100000", (0.0, 0.0, 1170.0, 100000.0)),
        ("0,0,100000,100000", (0.0, 0.0, 100000.0, 100000.0)),
        # the pages the existing tests and the real sheets use
        ("0,0,1170,825", (0.0, 0.0, 1170.0, 825.0)),
        ("0,0,1655,1170", (0.0, 0.0, 1655.0, 1170.0)),
        ("0,0,240,300", (0.0, 0.0, 240.0, 300.0)),
        # a page whose top-left is not the origin
        ("-500,-200,700,625", (-500.0, -200.0, 700.0, 625.0)),
    ],
)
def test_a_legal_page_box_is_returned_unchanged(text, expected):
    assert cli._draw_page_box(text) == expected


def test_the_existing_refusals_are_kept():
    assert cli._draw_page_box(None) is None
    assert cli._draw_page_box("") is None
    with pytest.raises(cli._DrawInputError) as reversed_box:
        cli._draw_page_box("0,0,-1170,825")
    assert "not a box" in str(reversed_box.value)
    with pytest.raises(cli._DrawInputError) as too_small:
        cli._draw_page_box("0,0,99,825")
    assert "too small" in str(too_small.value)
    with pytest.raises(cli._DrawInputError) as too_short:
        cli._draw_page_box("0,0,1170,50")
    assert "too small" in str(too_short.value)


# ---------------------------------------------------------------------------
# symbolprofile.check_box — finiteness, and only finiteness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("error", [SymbolProfileError, LayoutPlanError, PageLayoutPlanError])
@pytest.mark.parametrize(
    "value",
    [
        [0, 0, float("nan"), 826],
        [float("nan"), 0, 1170, 825],
        [0, 0, float("inf"), 826],
        [0, 0, 1170, float("inf")],
        [float("-inf"), 0, 1170, 825],
    ],
)
def test_check_box_refuses_non_finite_coordinates(value, error):
    with pytest.raises(error) as excinfo:
        check_box(value, "box", error)
    assert "finite" in str(excinfo.value)


def test_check_box_keeps_its_other_semantics():
    assert check_box(None, "box") is None
    assert check_box([0, 0, 100, 80], "box") == (0.0, 0.0, 100.0, 80.0)
    assert check_box((0, 0, 100, 80), "box") == (0.0, 0.0, 100.0, 80.0)
    with pytest.raises(SymbolProfileError) as reversed_box:
        check_box([0, 0, -100, 80], "box")
    assert "below" in str(reversed_box.value)
    with pytest.raises(SymbolProfileError) as wrong_length:
        check_box([0, 0, 100], "box")
    assert "minX" in str(wrong_length.value)
    with pytest.raises(SymbolProfileError) as boolean:
        check_box([0, 0, True, 80], "box")
    assert "minX" in str(boolean.value)


def test_check_box_has_no_page_size_cap():
    """A keep-out or text box is not a page: the page cap stays in `_draw_page_box`."""
    assert check_box([0, 0, 1e6, 1e6], "box") == (0.0, 0.0, 1e6, 1e6)
