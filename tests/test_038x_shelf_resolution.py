"""038X: the default shelf is a **file**, not a working-directory accident.

The hole this pins. A checkout's default shelf used to be the *relative*
spelling ``blocklib/parts.json``, resolved against the process working
directory, and `core.parts.load_parts` deliberately reads a missing file as an
empty shelf (the write side has to be able to create one). So any run started
outside the repository root — a DSH spawn, a CI step in a build directory, a
terminal left in ``~`` — reviewed every board against *nothing* and reported it
as "the shelf has nothing", which is a claim about the shelf rather than about
where the process stood.

Three answers must not collapse, and this file separates all three:

* **read** — the checkout default is the absolute file in this checkout
  (``resources.parts_library()``), whatever the CWD; frozen keeps 186-H2's
  user-then-bundled order and the broken-bootstrap fallback;
* **missing** — a path that is not a file is ``(None, why)`` from the one
  read-only entry point, and `checkup` says so at the top level
  (``shelfMissing: true``) instead of printing an empty shelf's verdict;
* **empty** — a real 0-entry JSON file is a shelf, read and reported as empty
  ("这是空货架，不是读取失败"), and `parts show`'s miss stays exit 2.

The write side is deliberately unchanged in the one respect that matters:
`parts add` on a path that does not exist still creates it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pytest

from boardwise import cli, resources
from boardwise.core.parts import PartLibrary, load_parts, save_parts
from boardwise.rules import facts as facts_rules

REPO = Path(__file__).resolve().parents[1]
BOARD = Path(__file__).resolve().parent / "fixtures" / "ch340_golden.epro2"
SHELF = REPO / "blocklib" / "parts.json"


def _args(library: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(library=library)


def _empty_shelf(tmp_path: Path) -> Path:
    return save_parts(PartLibrary(), tmp_path / "empty.json")


def _checkup(tmp_path: Path, monkeypatch, *extra: str) -> tuple[int, dict, Path]:
    monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path / "home"))
    out = tmp_path / "out"
    code = cli.main(["checkup", "--file", str(BOARD), "--out", str(out), *extra])
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    return code, report, out


# ---------------------------------------------------------------------------
# 1. the default path: absolute, and the same file from any CWD
# ---------------------------------------------------------------------------


def test_the_checkout_default_is_the_absolute_file_in_this_checkout(monkeypatch, tmp_path):
    """Not the relative constant: the answer is a location, not a spelling."""
    default = facts_rules.default_library_path()
    assert default == str(resources.parts_library())
    assert Path(default).is_absolute()
    assert Path(default).is_file()
    assert default != facts_rules.DEFAULT_LIBRARY_PATH

    monkeypatch.chdir(tmp_path)
    assert facts_rules.default_library_path() == default
    assert facts_rules.default_library_paths() == (default,)


def test_parts_show_finds_an_entry_from_a_working_directory_with_no_blocklib(
    monkeypatch, tmp_path, capsys
):
    """The measured failure: the same lookup answered "no entry" from anywhere else."""
    key = load_parts(SHELF).parts[0].key
    monkeypatch.chdir(tmp_path)
    assert not (tmp_path / "blocklib").exists()

    code = cli.main(["parts", "show", key])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert key in captured.out


def test_the_write_target_is_the_same_absolute_file(monkeypatch, tmp_path):
    """`parts add` without `--library` edits the shelf the rules read, not a CWD twin."""
    monkeypatch.chdir(tmp_path)
    args = _args()
    assert cli._parts_library_path(args, writable=True) == str(resources.parts_library())
    assert cli._parts_library_path(args) == str(resources.parts_library())


# ---------------------------------------------------------------------------
# 2. frozen: the 186-H2 order, unchanged
# ---------------------------------------------------------------------------


def _frozen_bundle(tmp_path: Path, monkeypatch) -> Path:
    bundle = tmp_path / "frozen" / resources.FROZEN_SUBDIR / "blocklib"
    bundle.mkdir(parents=True)
    shutil.copyfile(SHELF, bundle / "parts.json")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "frozen"), raising=False)
    monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    return bundle / "parts.json"


def test_frozen_still_reads_user_over_bundled(tmp_path, monkeypatch):
    bundled = _frozen_bundle(tmp_path, monkeypatch)
    assert facts_rules.default_library_path() == str(bundled)
    assert facts_rules.default_library_paths() == (str(bundled),)

    home = tmp_path / "home"
    home.mkdir()
    user = home / "parts.json"
    user.write_text('{"parts": []}\n', encoding="utf-8")
    assert facts_rules.default_library_path() == str(user)
    assert facts_rules.default_library_paths() == (str(user), str(bundled))


def test_a_broken_bootstrap_keeps_the_constant_and_now_says_it_is_missing(
    tmp_path, monkeypatch
):
    """A frozen process with no extraction root: same answer, honest disclosure."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path / "home"))
    # Away from the repository root: the constant is a relative spelling, so the
    # repository's own file must not decide this test.
    monkeypatch.chdir(tmp_path)
    assert facts_rules.default_library_path() == facts_rules.DEFAULT_LIBRARY_PATH
    assert facts_rules.default_library_paths() == (facts_rules.DEFAULT_LIBRARY_PATH,)

    library, note = cli._read_default_shelf(_args())
    assert library is None
    assert facts_rules.DEFAULT_LIBRARY_PATH in note and "不存在" in note, note


# ---------------------------------------------------------------------------
# 3. the read-only entry point: missing ≠ empty
# ---------------------------------------------------------------------------


def test_a_missing_explicit_shelf_is_reported_with_its_path(tmp_path):
    library, note = cli._read_default_shelf(_args(str(tmp_path / "nope.json")))
    assert library is None
    assert str(tmp_path / "nope.json") in note and "不存在" in note, note


def test_a_missing_default_shelf_is_reported_not_read_as_empty(tmp_path, monkeypatch):
    gone = tmp_path / "gone.json"
    monkeypatch.setattr(facts_rules, "default_library_path", lambda: str(gone))
    library, note = cli._read_default_shelf(_args())
    assert library is None
    assert str(gone) in note and "不存在" in note, note


def test_a_directory_at_the_shelf_path_is_not_a_file(tmp_path):
    library, note = cli._read_default_shelf(_args(str(tmp_path)))
    assert library is None
    assert "目录" in note and str(tmp_path) in note, note


def test_a_multi_shelf_default_with_one_missing_is_not_passed_off_as_complete(
    tmp_path, monkeypatch
):
    """A half-read merge is a different shelf; the caller must learn that."""
    present = _empty_shelf(tmp_path)
    gone = tmp_path / "missing" / "parts.json"
    monkeypatch.setattr(
        facts_rules, "default_library_paths", lambda: (str(gone), str(present))
    )
    library, note = cli._read_default_shelf(_args())
    assert library is None
    assert str(gone) in note and "合并" in note, note


def test_a_real_empty_shelf_is_a_shelf_and_says_so(tmp_path):
    empty = _empty_shelf(tmp_path)
    library, note = cli._read_default_shelf(_args(str(empty)))
    assert library is not None and library.parts == []
    assert "空货架" in note and "不是读取失败" in note, note


def test_checkup_shelf_appends_its_own_verdict_sentence_to_the_reason(tmp_path):
    shelf, note = cli._checkup_shelf(_args(str(tmp_path / "nope.json")))
    assert shelf is None
    assert str(tmp_path / "nope.json") in note
    assert "不是「货架为空」" in note, note


def test_arch_treats_an_unreadable_shelf_as_absent_evidence(tmp_path):
    library, note = cli._architecture_shelf_evidence(_args(str(tmp_path / "nope.json")))
    assert library is None
    assert str(tmp_path / "nope.json") in note and "没有货架证据" in note, note


# ---------------------------------------------------------------------------
# 4. `parts show`: the miss and the unreadable shelf are different answers
# ---------------------------------------------------------------------------


def test_parts_show_separates_a_miss_in_an_empty_shelf_from_an_unreadable_one(
    tmp_path, capsys
):
    empty = _empty_shelf(tmp_path)
    code = cli.main(["parts", "show", "nothing.here", "--library", str(empty)])
    captured = capsys.readouterr()
    assert code == 2
    assert "no entry for 'nothing.here'" in captured.err
    assert "空货架" in captured.err, "真实 0 条要说是空架，不是读取失败"

    gone = tmp_path / "nope.json"
    code = cli.main(["parts", "show", "nothing.here", "--library", str(gone)])
    captured = capsys.readouterr()
    assert code == 3, "货架读不了必须是自己的退出码，不能与未命中同码"
    assert str(gone) in captured.err and "读不了" in captured.err, captured.err
    assert "no entry for" not in captured.err, "没能查不等于查过没有"


def test_parts_list_reports_the_unreadable_shelf_and_still_exits_2(tmp_path, capsys):
    library, _note = cli._read_default_shelf(_args(str(tmp_path / "nope.json")))
    assert library is None  # the entry point every read-only command shares
    capsys.readouterr()
    code = cli.main(["parts", "list", "--library", str(tmp_path / "nope.json")])
    err = capsys.readouterr().err
    assert code == 2
    assert str(tmp_path / "nope.json") in err, err
    assert "不存在" in err, err


# ---------------------------------------------------------------------------
# 5. `checkup`: reviewedByShelf is the same story from any CWD, and a missing
#    shelf is disclosed at the top level
# ---------------------------------------------------------------------------


def test_checkup_judges_the_same_parts_with_the_default_and_an_explicit_shelf(
    tmp_path, monkeypatch
):
    """The negative control: the CWD no longer changes what the review read."""
    monkeypatch.chdir(tmp_path)  # no blocklib/ here
    code, default_report, _out = _checkup(tmp_path / "a", monkeypatch)
    assert code in (0, 3), "夹具板的 verdict 不是命令失败"
    assert default_report["shelfPath"] == str(resources.parts_library())
    assert "shelfMissing" not in default_report

    code2, explicit_report, _out2 = _checkup(
        tmp_path / "b", monkeypatch, "--library", str(resources.parts_library())
    )
    assert code2 == code
    assert explicit_report["reviewedByShelf"] == default_report["reviewedByShelf"]
    assert explicit_report["reviewedByShelf"], "货架该判过一些器件，否则这条断言没有意义"


def test_checkup_discloses_a_missing_shelf_at_the_top_level(tmp_path, monkeypatch):
    gone = tmp_path / "nope.json"
    code, report, out = _checkup(tmp_path, monkeypatch, "--library", str(gone))
    assert report["shelfMissing"] is True
    assert report["shelfPath"] == str(gone)
    notes = "\n".join(report["source"]["notes"])
    assert str(gone) in notes and "不存在" in notes, notes
    assert "空货架" not in notes or "不是读取失败" in notes
    # …and the gate is not allowed to call this a complete review.
    assert report["completion"]["coverage"]["shelfUnreadable"] is True
    assert report["completion"]["verdict"] == "incomplete"
    assert code == 3
    markdown = (out / "report.md").read_text(encoding="utf-8")
    assert str(gone) in markdown, "Markdown 也要带原因"


def test_checkup_does_not_mark_a_real_empty_shelf_as_missing(tmp_path, monkeypatch):
    empty = _empty_shelf(tmp_path)
    code, report, _out = _checkup(tmp_path, monkeypatch, "--library", str(empty))
    assert "shelfMissing" not in report
    assert report["shelfPath"] == str(empty)
    notes = "\n".join(report["source"]["notes"])
    assert "空货架" in notes and "不是读取失败" in notes, notes
    assert "shelfUnreadable" not in report["completion"]["coverage"]


def test_checkup_report_keeps_its_shape_for_a_plain_offline_run(tmp_path, monkeypatch):
    """The additive key: only a missing shelf adds `shelfMissing`, nothing else moves."""
    _code, report, _out = _checkup(tmp_path, monkeypatch)
    assert report["schema"] == "boardwise.checkup/7"
    assert "shelfMissing" not in report
    assert "shelfUnreadable" not in report["completion"]["coverage"]


# ---------------------------------------------------------------------------
# 6. the write side still creates a shelf that is not there
# ---------------------------------------------------------------------------


def test_parts_add_still_creates_a_missing_explicit_shelf(tmp_path, capsys):
    target = tmp_path / "new" / "parts.json"
    code = cli.main(["parts", "add", "SHELF-038X-1", "--lcsc", "C99000381",
                     "--library", str(target)])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert target.is_file()
    assert [part.mpn for part in load_parts(target).parts] == ["SHELF-038X-1"]


@pytest.mark.parametrize("name", ["blocklib/parts.json"])
def test_the_relative_constant_is_still_a_name_not_a_resolution(name):
    """The constant's meaning is unchanged: a name, and only a name."""
    assert facts_rules.DEFAULT_LIBRARY_PATH == name
