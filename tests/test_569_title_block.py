"""569 / W-T: the sheet's title block is kept out at compile, recorded by the plan,
and read back at landing.

Three holes, one chain (``outputs/hole567/f/REPRO.md`` H-567F-1/H-567F-2 and
``outputs/hole565/s3/REPRO.md`` S3-1):

* a **page** compile never handed the page compiler the sheet's own title block,
  so an ``ok=True`` page put parts, wires, flags, labels and texts inside it;
* a **fresh** page plan (``draw plan`` without ``--layout``) wrote neither the
  island marker nor the reservation note, so ``draw apply``'s S-01 leg skipped it
  whole;
* the reservation note spelled the boxes with ``%g``, which does not survive a
  round trip for a sheet like 1234.567 while the landing compares at 1e-6.

The geometry here is a **second opinion**: every box is rebuilt from the produced
``LayoutPlan`` (body via ``pose_box``, pin tips, wire polylines, junctions,
labels, flag glyphs, texts) and tested with one intersection predicate — the
packer's own ``keepout_conflicts`` and ``ok`` are never trusted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.core import geometry, pageframe
from boardwise.core import symbolprofile as sp
from boardwise.core.changeplan import ChangePlan
from boardwise.core.layoutplan import LayoutPlan
from boardwise.core.pagelayoutplan import PageLayoutPlan
from boardwise.engines import drawapply, islandlayout, pagecompiler, svgpreview

from test_057_draw_page_cli import (  # noqa: F401  (the page fixtures the batch reuses)
    LIBRARY,
    PAGE_BOX,
    _PageEditor,
    _apply,
    _netlist_for,
    _plan_page,
    _report,
    _seed,
    _stub_export,
    _stub_editor,
    write_specs,
)
from test_533_island_guard import _source

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
FIXTURES = ROOT / "tests" / "fixtures"

#: H-567F-1's sheet: the CH343 page at a height that puts its bottom row inside
#: the 700x180 table ``(460, 10)-(1160, 190)``.
CH343_SHEET = (0.0, 0.0, 1170.0, 600.0)


def _book(stem: str) -> dict[str, sp.SymbolProfile]:
    payload = json.loads((SPECS / f"{stem}.library.json").read_text(encoding="utf-8"))
    return {
        profile.symbol_ref: profile
        for profile in (sp.SymbolProfile.from_dict(entry) for entry in payload["profiles"])
    }


def _overlaps(first, second) -> bool:
    """Positive-area intersection; a point or a touching edge is not one."""
    return (
        first[0] < second[2] and second[0] < first[2]
        and first[1] < second[3] and second[1] < first[3]
    )


def _outside(box, page) -> bool:
    return box[0] < page[0] or box[1] < page[1] or box[2] > page[2] or box[3] > page[3]


def _drawn_boxes(plan: LayoutPlan, book) -> list[tuple[str, tuple]]:
    """Every box the plan draws, rebuilt here from the plan and the symbol library.

    Not the packer's accounting: a part's drawn body and its pin tips, each wire's
    polyline, junctions, label boxes, flag glyphs and every text box (references,
    values, the module's own annotations).
    """
    out: list[tuple[str, tuple]] = []
    for part in plan.parts:
        profile = book.get(part.symbol_ref)
        assert profile is not None, f"no profile for {part.symbol_ref} in the fixture library"
        body = sp.pose_box(
            profile.body, rotation=part.rotation, mirror=part.mirror, ox=part.x, oy=part.y,
        )
        if body is not None:
            out.append((f"part {part.part_id} body", body))
        for pin in profile.pins:
            x, y = geometry.transform_point(
                pin.tip[0], pin.tip[1], rotation=part.rotation, mirror=part.mirror,
                ox=part.x, oy=part.y,
            )
            out.append((f"part {part.part_id} pin {pin.number} tip", (x, y, x, y)))
    for index, segment in enumerate(plan.segments):
        xs = [point[0] for point in segment.points]
        ys = [point[1] for point in segment.points]
        out.append(
            (f"wire[{index}] {segment.net or '-'}", (min(xs), min(ys), max(xs), max(ys)))
        )
    for index, junction in enumerate(plan.junctions):
        out.append((f"junction[{index}] {junction.net}", (junction.x, junction.y,
                                                          junction.x, junction.y)))
    for index, label in enumerate(plan.labels):
        out.append((f"label[{index}] {label.net}:{label.text}", label.bbox))
    for index, symbol in enumerate(plan.power_symbols):
        glyph = sp.flag_glyph_box(
            book.get(symbol.symbol_ref), rotation=symbol.rotation,
            anchor=(symbol.x, symbol.y),
        )
        if glyph is not None:
            out.append((f"flag[{index}] {symbol.net} glyph", glyph))
    for index, text in enumerate(plan.texts):
        out.append((f"text[{index}] {text.kind}:{text.text}", text.bbox))
    return out


# ------------------------------------------------- A. the page compile's wiring


def test_a_page_compile_keeps_every_drawn_box_out_of_the_title_block(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H-567F-1, measured on the product: the real CLI page compile at 1170x600.

    Before the batch the first two candidates had 5 and 16 drawn boxes inside
    ``(460, 10)-(1160, 190)`` and the run still said ``ok=True``; the same run now
    has to be clean for **every** candidate, and the preview has to be drawn with
    the same keep-out (a reviewer reads the SVG, not the JSON).
    """
    captured: list[tuple[tuple, ...]] = []
    real_preview = svgpreview.write_preview

    def _capture(path, plan, profiles, **options):
        captured.append(tuple(tuple(float(value) for value in box)
                              for box in options.get("keepouts") or ()))
        return real_preview(path, plan, profiles, **options)

    monkeypatch.setattr(svgpreview, "write_preview", _capture)
    out = tmp_path / "compiled"
    report = tmp_path / "compile.json"
    code = cli.main([
        "draw", "compile",
        "--circuit", str(SPECS / "ch343_uart.circuit.json"),
        "--presentation", str(SPECS / "ch343_uart.presentation.json"),
        "--profiles", str(SPECS / "ch343_uart.library.json"),
        "--page-box", "0,0,1170,600",
        "--out", str(out), "--json", str(report),
    ])
    printed = capsys.readouterr().out
    assert code == 0, printed
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert len(payload["pages"]) >= 2, "the original report's first two candidates"

    keep = pageframe.title_block_keepouts(CH343_SHEET)
    assert keep == ((460.0, 10.0, 1160.0, 190.0),)
    book = _book("ch343_uart")
    documents = sorted(out.glob("cand*.page.json"))
    assert len(documents) == len(payload["pages"])
    for path in documents:
        page = PageLayoutPlan.load(path)
        assert page.page_box == CH343_SHEET
        boxes = _drawn_boxes(page.plan, book)
        assert len(boxes) > 100, "the body, tips, wires, labels, flags and texts were walked"
        for name, box in boxes:
            assert not _outside(box, page.page_box), f"{path.name}: {name} escapes the page"
            assert not any(_overlaps(box, box_keep) for box_keep in keep), (
                f"{path.name}: {name} {tuple(round(value, 1) for value in box)} "
                f"enters the title block {keep[0]}"
            )
    assert captured, "the previews were written through svgpreview"
    assert all(boxes == keep for boxes in captured), captured


# -------------------------------------- B. the fresh page plan's own record


def test_a_fresh_page_plan_is_marked_and_carries_the_exact_title_keepout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """565-S3-1: the offline/live page plan must carry what the landing leg reads.

    ``draw apply`` reads the marker and the reservation off the plan's own notes;
    a fresh page plan carried neither, so the S-01 leg (the sheet read, the box
    comparison, the note) was skipped without a word.
    """
    editor = _PageEditor()
    _seed(editor)
    code, plan_path, _circuit, _presentation = _plan_page(monkeypatch, tmp_path, editor)
    assert code == 0, capsys.readouterr().out
    plan = ChangePlan.load(plan_path)
    notes = list(plan.change.draw_notes)
    assert any(str(note).startswith(islandlayout.ISLAND_PAGE_KIND) for note in notes), (
        f"the island marker is missing from {notes}"
    )
    title = pageframe.title_block_keepouts((0.0, 0.0, 1169.0, 826.0))[0]
    assert pageframe.page_keep_out_from_notes(notes) == ((0.0, 0.0, 1169.0, 826.0), title)
    assert cli._draw_plan_is_island_page(plan) is True


def test_a_single_module_plan_still_carries_no_page_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """The other side of B: a module is not a page, and its plan says nothing about a
    sheet's title block (530G's split, unchanged by this batch)."""
    out = tmp_path / "module-plan.json"
    fixtures = FIXTURES / "drawapply"
    code = cli.main([
        "draw", "plan",
        "--circuit", str(fixtures / "divider.circuit.json"),
        "--presentation", str(fixtures / "divider.presentation.json"),
        "--profiles", str(fixtures / "library.json"),
        "--out", str(out),
    ])
    assert code == 0, capsys.readouterr().out
    plan = ChangePlan.load(out)
    assert cli._draw_plan_is_island_page(plan) is False
    assert pageframe.page_keep_out_from_notes(plan.change.draw_notes) is None


# --------------------- C. the fresh compile keeps both kinds of keep-out


def _captured_budgets(monkeypatch: pytest.MonkeyPatch) -> list:
    budgets: list = []
    real = pagecompiler.compile_page

    def _capture(circuit, presentation, profiles, budget):
        budgets.append(budget)
        return real(circuit, presentation, profiles, budget)

    monkeypatch.setattr(pagecompiler, "compile_page", _capture)
    return budgets


def test_a_fresh_page_compile_is_handed_the_census_and_the_title_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """565-S3-1's compile side: the title block is **added**, never substituted."""
    budgets = _captured_budgets(monkeypatch)
    editor = _PageEditor()
    _seed(editor)
    code, _plan_path, _circuit, _presentation = _plan_page(monkeypatch, tmp_path, editor)
    assert code == 0, capsys.readouterr().out
    assert len(budgets) == 1
    budget = budgets[0]
    census = [tuple(row["box"]) for row in _report(tmp_path / "plan.report.json")["keepouts"]]
    assert len(census) >= 3, "the seeded page states a part, a wire segment and a flag"
    title = tuple(pageframe.title_block_keepouts((0.0, 0.0, 1169.0, 826.0))[0])
    boxes = [tuple(float(value) for value in box) for box in budget.keepouts]
    assert all(box in boxes for box in census), (census, boxes)
    assert title in boxes, boxes
    assert budget.relocate_around_keepouts is True


def test_a_census_that_already_states_the_title_block_is_not_doubled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Dedupe goes through the one comparison the saved page already uses."""
    title = tuple(pageframe.title_block_keepouts((0.0, 0.0, 1169.0, 826.0))[0])
    monkeypatch.setattr(
        drawapply, "census_keepouts",
        lambda measured: ([title], ["an existing sheet symbol (S-01)"], []),
    )
    budgets = _captured_budgets(monkeypatch)
    editor = _PageEditor()
    _seed(editor)
    code, _plan_path, _circuit, _presentation = _plan_page(monkeypatch, tmp_path, editor)
    assert code == 0, capsys.readouterr().out
    assert len(budgets) == 1
    boxes = [tuple(float(value) for value in box) for box in budgets[0].keepouts]
    assert boxes.count(title) == 1, boxes
    assert budgets[0].relocate_around_keepouts is True


# ------------------------------------------------ D. the note's precision


@pytest.mark.parametrize(
    "page_box",
    [
        (0.0, 0.0, 1234.567, 825.0),
        (0.0, 0.0, 1169.0049999, 826.0),
        (-12.5, 0.0, 1157.5, 825.0),
        (0.0, 100.0, 1170.0, 925.0),
    ],
    ids=["seven-significant-digits", "s3-2-tail", "negative-origin", "shifted-origin"],
)
def test_the_keep_out_note_round_trips_the_sheet_exactly(page_box) -> None:
    """H-567F-2 / 565-S3-2: the note is the only carrier of the sheet between runs.

    ``%g`` wrote 1234.567 as ``1234.57`` and 1169.0049999 as ``1169``, which the
    landing's 1e-6 comparison then called a different sheet.
    """
    keep = pageframe.title_block_keepouts(page_box)
    note = pageframe.keep_out_note(page_box, keep)
    parsed = pageframe.page_keep_out_from_notes([note])
    assert parsed is not None, note
    recorded_box, recorded_rect = parsed
    assert recorded_box == page_box, note
    assert recorded_rect == keep[0], note
    assert cli._draw_same_box(recorded_box, page_box)
    assert cli._draw_same_box(recorded_rect, keep[0])


@pytest.mark.parametrize(
    "page_box",
    [(0.0, 0.0, 1170.0, 825.0), (0.0, 0.0, 1170.5, 825.25)],
    ids=["integer-control", "half-control"],
)
def test_the_integer_and_half_round_trips_do_not_degrade(page_box) -> None:
    keep = pageframe.title_block_keepouts(page_box)
    parsed = pageframe.page_keep_out_from_notes(
        [pageframe.keep_out_note(page_box, keep)]
    )
    assert parsed == (page_box, keep[0])


# ------------------------------- E. the landing consumes the fresh plan's record


#: The fake page's own sheet, as its document source would state it (the fake's
#: ``SHEET`` bbox is 0,0,1169,826).
_FAKE_SHEET_ATTRS = {
    "Width": "1169", "Height": "826", "Blade Width": "10",
    "Title Block Position": "3", "Title Block": "1",
}


class _SheetPageEditor(_PageEditor):
    """A fake page that answers the one read the S-01 landing leg makes."""

    def __init__(self, attrs=None, **kwargs):
        super().__init__(**kwargs)
        self.sheet_attrs = dict(_FAKE_SHEET_ATTRS if attrs is None else attrs)

    async def call(self, action, params=None, **_route):
        if action == "sys.get_document_source":
            self.calls.append(action)
            return {"data": _source(self.sheet_attrs, attached=True)}
        return await super().call(action, params, **_route)


def test_a_fresh_page_plan_lands_through_the_s01_guard(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """The end of the chain: a fresh page plan's own record is what the landing reads.

    Without the marker and the note (565-S3-1) this leg did not run at all; with
    them, ``draw apply`` reads the live page's sheet, compares it to the sheet the
    plan recorded, and says so.  The refusal below is the other half of the same
    fact: a record for 1169x826 does not license a landing on a 1170x825 sheet.
    """
    editor = _SheetPageEditor()
    _seed(editor)
    code, plan_path, circuit, presentation = _plan_page(monkeypatch, tmp_path, editor)
    assert code == 0, capsys.readouterr().out
    plan = ChangePlan.load(plan_path)
    editor.netlists = [{"components": {}}, _netlist_for(plan)]
    code, report = _apply(editor, plan_path, circuit, presentation, tmp_path)
    assert code == 0, report["notes"]
    assert "sys.get_document_source" in editor.calls
    assert report["titleBlock"]["planRecordedPageBox"] == [0.0, 0.0, 1169.0, 826.0]
    assert report["titleBlock"]["planRecordedTitleBlock"] == [459.0, 10.0, 1159.0, 190.0]
    assert report["titleBlock"]["livePageBox"] == [0.0, 0.0, 1169.0, 826.0]
    assert any(
        "S-01: the plan's own title-block reservation" in line for line in report["notes"]
    ), report["notes"]

    wrong = _SheetPageEditor(attrs={"Width": "1170", "Height": "825", "Blade Width": "10",
                                    "Title Block Position": "3", "Title Block": "1"})
    wrong.netlists = [{"components": {}}, _netlist_for(plan)]
    _stub_editor(monkeypatch, wrong)
    code, refused = _apply(wrong, plan_path, circuit, presentation, tmp_path)
    assert code == 5
    assert refused["reason"] == "landing_sheet_mismatch"
    assert wrong.writes == [], "a refused landing writes nothing"
