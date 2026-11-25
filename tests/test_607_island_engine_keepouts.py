"""607（570-B2-1）：声明了页框，就等于声明了页框自己的标题栏（多岛引擎 API）。

`outputs/hole570/b2/REPRO.md` 的 570-B2-1：直接调 `drawcompiler.compile(flyback,
CompileBudget(page_box=(0, 0, 1170, 825)))`（**不给** keepouts）得到 `ok=True`，
174 个呈现盒里有 25 个落在 `(460, 10)-(1160, 190)`；1170×600 时 36 个。CLI 早就在
`cli._draw_compile` 里派生标题栏，缺口是公开引擎 API 这个入口：`page_box` 和
`keepouts` 是两个字段，"声明了纸"没有被读成"声明了纸的表"。

本文件钉三件事：

1. **真实 compile 的暴力 oracle**：不用 `keepout_conflicts`、不看 `ok=True`，
   从产物逐对象重算盒（器件体、pin tip、导线段、文字、label、旗标字形+名称行、
   junction），对 `pageframe.title_block_keepouts` 与页框各判一次。修前 25 个相交，
   修后必须 0。
2. **同源与去重**：引擎内部派生一次，`PageBudget`（打包地板/冲突）与
   `readability.check`（闸）拿到的是**同一个**元组；CLI 已经传进来的标题栏不得
   变成第二条，调用者显式给的额外 keepout 不得被覆盖或丢弃。
3. **负控**：没有 `page_box` 就不派生（不造 S-01）；单岛文档不走岛路，
   `island_page` 都不该被调用。

边界：本批只改引擎 API 的多岛路径，`islandlayout.IslandBlock.bbox()` 的器件体
（570-B2-2）是 608，不在这里。
"""

from __future__ import annotations

import json
from pathlib import Path

from boardwise.core import pageframe, symbolprofile, textmetrics
from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import islandlayout as il
from boardwise.engines import readability as rb

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"

#: The flyback's own sheet — the page S-01 was read off, and where the block is
#: `(460, 10)-(1160, 190)`.
SHEET = (0.0, 0.0, 1170.0, 825.0)
#: An explicit region a caller might reserve on top of the sheet's own block.
EXTRA = (20.0, 20.0, 220.0, 120.0)


def _library(stem: str) -> dict[str, SymbolProfile]:
    payload = json.loads(
        (SPECS / f"{stem}.library.json").read_text(encoding="utf-8")
    )
    book: dict[str, SymbolProfile] = {}
    for entry in payload["profiles"]:
        profile = SymbolProfile.from_dict(entry)
        book[profile.symbol_ref] = profile
    return book


def _triplet(stem: str):
    return (
        CircuitSpec.load(SPECS / f"{stem}.circuit.json"),
        PresentationSpec.load(SPECS / f"{stem}.presentation.json"),
        _library(stem),
    )


def _overlaps(first, second, tol: float = 1e-9) -> bool:
    """Positive-area intersection (a box merely touching an edge is not inside)."""
    return (
        min(first[2], second[2]) - max(first[0], second[0]) > tol
        and min(first[3], second[3]) - max(first[1], second[1]) > tol
    )


def _in_box(inner, outer, tol: float = 1e-9) -> bool:
    return (
        outer[0] - tol <= inner[0] and outer[1] - tol <= inner[1]
        and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol
    )


def _seg_hits(points, box, tol: float = 1e-9) -> bool:
    """Liang–Barsky clip of one polyline against a box, positive length only.

    Written out rather than reusing the readability checker: this walk is the
    independent opinion, so it must not share the checker's wire test.
    """
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        dx, dy = x1 - x0, y1 - y0
        u0, u1 = 0.0, 1.0
        ok = True
        for p, q in (
            (-dx, x0 - box[0]), (dx, box[2] - x0),
            (-dy, y0 - box[1]), (dy, box[3] - y0),
        ):
            if p == 0:
                if q < -tol:
                    ok = False
                    break
            else:
                t = q / p
                if p < 0:
                    u0 = max(u0, t)
                else:
                    u1 = min(u1, t)
                if u0 > u1:
                    ok = False
                    break
        if ok and u1 - u0 > 1e-9:
            return True
    return False


def _presentation_boxes(plan, book) -> list[tuple[str, str, tuple, object]]:
    """Every box the page draws, recomputed from the plan and the profiles.

    Deliberately does not consult `IslandBlock.bbox()` or `keepout_conflicts`:
    the packer's own account of what it kept out of is not a measurement.
    """
    rows: list[tuple[str, str, tuple, object]] = []
    for part in plan.parts:
        profile = book[part.symbol_ref]
        if profile.body is not None:
            body = symbolprofile.pose_box(
                profile.body, rotation=part.rotation, mirror=part.mirror,
                ox=part.x, oy=part.y,
            )
            rows.append((f"parts[{part.part_id}] body", "body", body, None))
        for pin in profile.pins:
            x, y = transform_point(
                pin.tip[0], pin.tip[1], rotation=part.rotation,
                mirror=part.mirror, ox=part.x, oy=part.y,
            )
            rows.append(
                (f"parts[{part.part_id}].{pin.number} tip", "pin-tip", (x, y, x, y), None)
            )
    for index, segment in enumerate(plan.segments):
        points = [(float(x), float(y)) for x, y in segment.points]
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        rows.append(
            (f"segments[{index}] net {segment.net}", "wire",
             (min(xs), min(ys), max(xs), max(ys)), points)
        )
    for index, label in enumerate(plan.labels):
        rows.append((f"labels[{index}] {label.text!r}", "label", tuple(label.bbox), None))
    for index, text in enumerate(plan.texts):
        rows.append(
            (f"texts[{index}] {text.kind} {text.text!r}", "text", tuple(text.bbox), None)
        )
    for index, symbol in enumerate(plan.power_symbols):
        profile = book[symbol.symbol_ref]
        anchor = (symbol.x, symbol.y)
        glyph = symbolprofile.flag_glyph_box(
            profile, rotation=symbol.rotation, anchor=anchor,
        ) or (anchor[0], anchor[1], anchor[0], anchor[1])
        rows.append(
            (f"powerSymbols[{index}] glyph {symbol.net!r}", "flag-glyph", tuple(glyph), None)
        )
        row = textmetrics.flag_name_box(
            glyph, anchor, symbol.net, axis_up=glyph[3] > anchor[1],
        )
        joined = (
            min(glyph[0], row[0]), min(glyph[1], row[1]),
            max(glyph[2], row[2]), max(glyph[3], row[3]),
        )
        rows.append(
            (f"powerSymbols[{index}] glyph+row {symbol.net!r}", "flag-row", joined, None)
        )
    for index, junction in enumerate(plan.junctions):
        rows.append(
            (f"junctions[{index}] {junction.net!r}", "junction",
             (junction.x, junction.y, junction.x, junction.y), None)
        )
    return rows


def _hits(rows, keep) -> list[str]:
    out: list[str] = []
    for name, _kind, box, points in rows:
        hit = _seg_hits(points, keep) if points is not None else _overlaps(box, keep)
        if hit:
            out.append(name)
    return out


def _compile(circuit, presentation, book, budget):
    return dc.compile(circuit, presentation, book, budget)


# ============================================ 1. the real page, brute oracle


def test_engine_api_with_a_stated_sheet_keeps_the_title_block_out() -> None:
    """570-B2-1's own reproduction, driven through the public `compile`.

    Before this batch the same call (no `keepouts`, sheet only) delivered a
    candidate with 25 of its 174 boxes inside `(460, 10)-(1160, 190)`; the sheet
    is the page S-01 was read off, so the sheet's block is not an extra the caller
    may forget. A candidate is still required — refusing the page would be a
    different (and wrong) answer.
    """
    circuit, presentation, book = _triplet("flyback_uc3845")
    assert len(presentation.effective_islands()) > 1
    result = _compile(circuit, presentation, book, dc.CompileBudget(page_box=SHEET))
    assert result.candidates, [failure.detail for failure in result.failures]

    plan = result.candidates[0]
    rows = _presentation_boxes(plan, book)
    kinds = {kind for _name, kind, _box, _pts in rows}
    assert kinds == {
        "body", "pin-tip", "wire", "label", "text", "flag-glyph", "flag-row",
        "junction",
    }, "the oracle must cover every object class the page draws"
    assert len(rows) == 174
    assert _hits(rows, pageframe.title_block_box(SHEET)) == []
    assert [name for name, _k, box, _p in rows if not _in_box(box, SHEET)] == []


# ==================================== 2. one derivation, both consumers, dedupe


def _spy(monkeypatch):
    """Record the keep-out tuple each consumer is handed; still run the real ones."""
    seen: dict[str, tuple] = {}
    real_island_page = il.island_page
    real_check = rb.check

    def island_page(*args, **kwargs):
        page_budget = kwargs.get("page_budget")
        seen["packer"] = tuple(
            tuple(box) for box in (page_budget.keepouts if page_budget else ())
        )
        return real_island_page(*args, **kwargs)

    def check(*args, **kwargs):
        seen["readability"] = tuple(tuple(box) for box in kwargs.get("keepouts", ()))
        return real_check(*args, **kwargs)

    monkeypatch.setattr(il, "island_page", island_page)
    monkeypatch.setattr(rb, "check", check)
    return seen


def test_the_packer_and_the_gate_get_one_derived_set(monkeypatch) -> None:
    """The CLI's own copy of the block must not become a second entry."""
    seen = _spy(monkeypatch)
    circuit, presentation, book = _triplet("flyback_uc3845")
    block = pageframe.title_block_keepouts(SHEET)
    result = _compile(
        circuit, presentation, book,
        dc.CompileBudget(page_box=SHEET, keepouts=block),
    )
    assert result.candidates, [failure.detail for failure in result.failures]
    assert seen["packer"] == tuple(tuple(box) for box in block)
    assert seen["readability"] == seen["packer"]


def test_an_explicit_keepout_survives_the_merge(monkeypatch) -> None:
    """A caller's own region is kept, and the sheet's block is added beside it."""
    seen = _spy(monkeypatch)
    circuit, presentation, book = _triplet("flyback_uc3845")
    block = pageframe.title_block_keepouts(SHEET)
    result = _compile(
        circuit, presentation, book,
        dc.CompileBudget(page_box=SHEET, keepouts=(EXTRA,)),
    )
    assert result.candidates, [failure.detail for failure in result.failures]
    assert seen["packer"] == (EXTRA, block[0])
    assert seen["readability"] == seen["packer"]

    rows = _presentation_boxes(result.candidates[0], book)
    assert _hits(rows, EXTRA) == []
    assert _hits(rows, block[0]) == []
    assert [name for name, _k, box, _p in rows if not _in_box(box, SHEET)] == []


# ==================================================== 3. negative controls


def test_no_sheet_derives_no_title_block(monkeypatch) -> None:
    """A drawing with no stated page has no page's block to keep out of."""
    seen = _spy(monkeypatch)
    circuit, presentation, book = _triplet("flyback_uc3845")
    result = _compile(circuit, presentation, book, dc.CompileBudget())
    assert result.candidates, [failure.detail for failure in result.failures]
    assert seen["packer"] == ()
    assert seen["readability"] == ()


def test_a_single_island_document_never_reaches_the_island_page(monkeypatch) -> None:
    """The single-island path is untouched here, and stays untouched by the new merge."""
    seen = _spy(monkeypatch)
    circuit, presentation, book = _triplet("power_entry_xt30")
    assert len(presentation.effective_islands()) == 1
    result = _compile(
        circuit, presentation, book,
        dc.CompileBudget(page_box=(0.0, 0.0, 560.0, 450.0)),
    )
    assert result.candidates, [failure.detail for failure in result.failures]
    assert "packer" not in seen
