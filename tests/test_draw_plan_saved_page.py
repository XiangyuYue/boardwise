"""Saved page candidates are preflighted without compiling or writing an editor."""
from __future__ import annotations

import json
import dataclasses

import pytest

from boardwise import cli
from boardwise.core.changeplan import ChangePlan
from boardwise.core.pagelayoutplan import PageLayoutPlan
from boardwise.engines import pagecompiler
from test_057_draw_page_cli import (
    LIBRARY, PAGE_BOX, _PageEditor, _stub_editor, _stub_export,
    page_presentation, write_specs,
)


@pytest.fixture
def saved(tmp_path):
    circuit, presentation = write_specs(tmp_path)
    out = tmp_path / "compiled"
    assert cli.main([
        "draw", "compile", "--circuit", str(circuit),
        "--presentation", str(presentation), "--profiles", str(LIBRARY),
        "--page-box", PAGE_BOX, "--out", str(out),
    ]) == 0
    candidates = sorted(out.glob("cand*.page.json"))
    assert candidates
    return circuit, presentation, candidates


def args_for(saved, tmp_path, path=None, *extra):
    circuit, presentation, candidates = saved
    return [
        "draw", "plan", "--circuit", str(circuit),
        "--presentation", str(presentation), "--profiles", str(LIBRARY),
        "--layout", str(path or candidates[0]),
        "--out", str(tmp_path / "plan.json"),
        "--json", str(tmp_path / "report.json"), *extra,
    ]


def test_all_saved_candidates_are_consumed_without_compile(saved, tmp_path, monkeypatch):
    calls = []
    original = pagecompiler.compile_page

    def count(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(pagecompiler, "compile_page", count)
    candidates = saved[2]
    for index in range(max(4, len(candidates))):
        candidate = candidates[index % len(candidates)]
        assert cli.main(args_for(saved, tmp_path, candidate)) == 0
        page = PageLayoutPlan.load(candidate)
        report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert report["page"]["geometrySha256"] == page.page_geometry_sha256()
        assert report["layoutSource"] == str(candidate)
        assert "key" not in report["page"] and "candidates" not in report["page"]
        assert report["checks"]["page"]["ok"] and report["checks"]["drawing"]["ok"]
        inputs = cli._draw_inputs(cli.build_parser().parse_args(args_for(saved, tmp_path)))
        expected = cli._draw_plan_from_page(page, *inputs).to_jsonable()
        actual = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
        expected.pop("notes", None)
        actual.pop("notes", None)
        # The CLI adds provenance notes; every executable field stays identical.
        expected_notes = expected["change"].pop("notes")
        actual_notes = actual["change"].pop("notes")
        assert actual_notes[-len(expected_notes):] == expected_notes
        assert actual == expected, "the saved page must use the existing full ChangePlan builder"
    assert calls == [], "consuming a selected saved page must never run compile_page"


def test_legacy_plan_still_compiles(saved, tmp_path, monkeypatch):
    calls = []
    original = pagecompiler.compile_page

    def count(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(pagecompiler, "compile_page", count)
    circuit, presentation, _ = saved
    assert cli.main([
        "draw", "plan", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE_BOX,
        "--out", str(tmp_path / "legacy.json"),
    ]) == 0
    assert calls == [1]


@pytest.mark.parametrize("which", ["circuit", "presentation"])
def test_stale_sources_refuse_before_live_connection(saved, tmp_path, monkeypatch, which):
    path = saved[0 if which == "circuit" else 1]
    body = json.loads(path.read_text(encoding="utf-8"))
    if which == "circuit":
        body["parts"][0]["mpn"] = "changed-current-part-metadata"
    else:
        body["modules"][0]["role"] = "changed-current-functional-role"
    path.write_text(json.dumps(body), encoding="utf-8")

    def no_bridge(*args):
        raise AssertionError("stale saved inputs must refuse before opening a live connection")

    monkeypatch.setattr(cli, "_open_cli", no_bridge)
    assert cli.main(args_for(saved, tmp_path, None, "--page", "page-1")) == 5
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["reason"] == "stale_layout"
    assert any(which + "Sha256" in line for line in report["notes"])
    assert not (tmp_path / "plan.json").exists()


@pytest.mark.parametrize("extra", [("--candidate", "1"), ("--page-box", "0,0,1200,900")])
def test_saved_selection_and_sheet_are_not_silently_changed(saved, tmp_path, extra, capsys):
    assert cli.main(args_for(saved, tmp_path, None, *extra)) == 5
    assert extra[0] in capsys.readouterr().err
    assert not (tmp_path / "plan.json").exists()


def test_matching_explicit_sheet_is_accepted(saved, tmp_path):
    assert cli.main(args_for(saved, tmp_path, None, "--page-box", PAGE_BOX)) == 0


@pytest.mark.parametrize("mode", ["kind", "missing", "digest", "symbol-hash", "profile"])
def test_saved_document_and_profile_integrity_are_checked(saved, tmp_path, mode, capsys):
    page_path = saved[2][0]
    args = args_for(saved, tmp_path)
    if mode == "missing":
        args = args_for(saved, tmp_path, tmp_path / "not-present.page.json")
    elif mode == "profile":
        book = json.loads(LIBRARY.read_text(encoding="utf-8"))
        profile = next(item for item in book["profiles"] if item["symbolRef"] == "R0402")
        profile["body"][0] -= 1
        library = tmp_path / "changed.library.json"
        library.write_text(json.dumps(book), encoding="utf-8")
        args += ["--profiles", str(library)]
    else:
        body = json.loads(page_path.read_text(encoding="utf-8"))
        if mode == "kind":
            body["kind"] = "boardwise-layout-plan"
        elif mode == "digest":
            body["plan"]["parts"][0]["x"] += 5
        else:
            page = PageLayoutPlan.load(page_path)
            page.plan.parts[0] = dataclasses.replace(page.plan.parts[0], symbol_hash="0" * 64)
            page.dump(page_path)
            body = None
        if body is not None:
            page_path.write_text(json.dumps(body), encoding="utf-8")
    assert cli.main(args) == 5
    err = capsys.readouterr().err
    if mode in ("digest", "profile", "symbol-hash"):
        assert "geometry" in err
    else:
        assert err
    assert not (tmp_path / "plan.json").exists()


@pytest.mark.parametrize("mode", ["disconnect", "text-collision", "partition"])
def test_rehashed_bad_geometry_still_fails_current_checks(saved, tmp_path, mode):
    page_path = saved[2][0]
    page = PageLayoutPlan.load(page_path)
    if mode == "disconnect":
        page.plan.segments = [item for item in page.plan.segments if item.net != "TAP"]
    elif mode == "text-collision":
        first, second = page.plan.texts[:2]
        page.plan.texts[1] = dataclasses.replace(second, x=first.x, y=first.y, bbox=first.bbox)
    else:
        page.modules[0].parts.remove("C1")
        page.modules[1].parts.append("C1")
    page.dump(page_path)
    assert cli.main(args_for(saved, tmp_path)) == 5
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["reason"] in ("readability_refused", "cannot_build_plan")
    assert not (tmp_path / "plan.json").exists()


def test_fake_live_occupied_page_refuses_without_rearranging_or_writing(saved, tmp_path, monkeypatch):
    editor = _PageEditor()
    page = PageLayoutPlan.load(saved[2][0])
    first = page.plan.parts[0]
    editor.add_part("R9", first.x, first.y)
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch)
    before = editor.snapshot()

    def no_compile(*args, **kwargs):
        raise AssertionError("an occupied saved page must refuse without recompiling")

    monkeypatch.setattr(pagecompiler, "compile_page", no_compile)
    assert cli.main(args_for(saved, tmp_path, None, "--page", editor.page)) == 5
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["reason"] == "readability_refused"
    assert any("R9" in line for line in report["notes"])
    assert editor.snapshot() == before and editor.writes == []
    assert "sch.geometry" in editor.calls


def test_saved_module_local_lock_is_translated_by_the_existing_view(tmp_path):
    circuit, presentation = write_specs(tmp_path, presentation=page_presentation(
        userLocks=[{"partId": "R1", "x": 0, "y": 0, "rotation": 0}],
    ))
    out = tmp_path / "locked"
    assert cli.main([
        "draw", "compile", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE_BOX, "--out", str(out),
    ]) == 0
    paths = sorted(out.glob("cand*.page.json"))
    assert paths
    saved = (circuit, presentation, paths)
    assert PageLayoutPlan.load(paths[0]).plan.part("R1").x != 0
    assert cli.main(args_for(saved, tmp_path)) == 0


def test_fake_live_unreadable_geometry_is_unknown_and_zero_write(saved, tmp_path, monkeypatch):
    editor = _PageEditor(timeouts=["sch.geometry"])
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch)
    assert cli.main(args_for(saved, tmp_path, None, "--page", editor.page)) == 3
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["outcome"] == "unknown" and report["reason"] == "guard_unreadable"
    assert editor.writes == [] and not (tmp_path / "plan.json").exists()


def test_fake_live_clear_page_preserves_census_and_pool_without_writes(saved, tmp_path, monkeypatch):
    editor = _PageEditor()
    editor.add_part("R9", 950, 200)
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch, findings=["existing-finding"])
    assert cli.main(args_for(saved, tmp_path, None, "--page", editor.page)) == 0
    plan = ChangePlan.load(tmp_path / "plan.json")
    assert plan.change.draw_baseline.page_uuid == editor.page
    assert plan.change.baseline_findings == ["existing-finding"]
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["live"]["poolSize"] == 1
    assert "1 designator(s)" in report["poolSource"]
    assert editor.writes == []
