"""544: the two commands' **output boundary** — a write that cannot happen.

Three failures from the 2026-11-04 problem list, all of them "the paths the caller
named cannot receive what this command produces", and all of them used to end in a
Python traceback instead of a sentence:

* ``checkup --out`` a directory that is not writable (T-E02);
* ``checkup --out`` a **regular file** (T-E03) — the runs before this batch died on
  ``mkdir`` *after* reading sidecars out of a path that is not a directory, so the
  refusal has to come before anything is read or written;
* ``arch --out`` a directory (T-A06) — the sibling of E03 at the other command's
  ``--out``.

What the assertions are allowed to say: the exit code (2, this CLI's "the input
cannot be used"), one actionable line on stderr, no traceback, and — for E03 — the
named file's bytes exactly as they were. The successful paths are asserted in the
same file so a fix cannot buy the three exits by refusing legal runs.

Deterministic and offline throughout: the unwritable directory is a patched
``Path.write_text`` raising ``PermissionError`` (``icacls`` is a machine setting,
not a test fixture), the archives are the real ``.epro2`` fixtures, and no bridge,
daemon or editor is touched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.cli import _cmd_arch, _cmd_checkup
from boardwise.engines.checkup import BOARD_REPORT_FILE

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = FIXTURES / "ch340_golden.epro2"


def _checkup_args(**overrides) -> argparse.Namespace:
    base = {"file": str(GOLDEN), "project": "", "instance": "", "out": "checkup", "port": None}
    base.update(overrides)
    return argparse.Namespace(**base)


def _no_traceback(captured: "pytest.CaptureResult") -> bool:
    return "Traceback" not in captured.out and "Traceback" not in captured.err


# --- T-E02: the output directory refuses the write --------------------------


def test_checkup_out_that_cannot_be_written_is_exit_two(tmp_path, monkeypatch, capsys):
    """A directory that refuses `report.json` is "unusable input", not a crash.

    Patched at `Path.write_text` rather than with ACLs: the branch under test is
    "the write raised `PermissionError`", and a machine's directory permissions
    would make the test pass or fail depending on who runs it.
    """
    out_dir = tmp_path / "readonly"
    out_dir.mkdir()
    real_write_text = Path.write_text

    def refuse(self, *args, **kwargs):
        if self.parent == out_dir:
            raise PermissionError(13, "Permission denied", str(self))
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", refuse)

    assert _cmd_checkup(_checkup_args(out=str(out_dir))) == 2
    captured = capsys.readouterr()

    assert _no_traceback(captured), "写盘失败必须是一句话，不是 traceback"
    assert captured.err.startswith("boardwise checkup:"), "错误行要能被 grep 到命令名"
    assert str(out_dir) in captured.err, "要说出哪个目录写不进"
    assert "未完整写出" in captured.err, "要如实说这次交付不完整"
    assert "不能当作完整交付" in captured.err
    assert "没有产出" not in captured.err, "不许声称「没有产出」，那是猜哪个文件落地了"
    assert "--out" in captured.err, "要给出可操作的下一步（换目录 / 修权限）"
    assert not (out_dir / "report.json").exists(), "失败的写不许留下半个 report.json"


# --- T-E03: `--out` names a file, not a directory ---------------------------


def test_checkup_out_that_is_a_regular_file_is_exit_two_and_untouched(tmp_path, capsys):
    """The file the caller named keeps every byte, and nothing is written beside it."""
    target = tmp_path / "boardwise-out"
    payload = "这不是目录，是一个普通文件：一个字节都不许动。\n".encode("utf-8")
    target.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()

    assert _cmd_checkup(_checkup_args(out=str(target))) == 2
    captured = capsys.readouterr()

    assert _no_traceback(captured)
    assert captured.err.startswith("boardwise checkup:")
    assert str(target) in captured.err
    assert "不是目录" in captured.err, "要说清这里要的是目录（report.json 写进去）"
    assert captured.out == "", (
        "这条要在跑审查之前就拒掉：stdout 一个字符都不该有（连头部那行都不该印出来）"
    )
    assert target.is_file(), "原路径仍是那个普通文件，没被换成目录"
    assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, "原文件必须逐字节不变"
    assert [entry.name for entry in tmp_path.iterdir()] == ["boardwise-out"], (
        "这个 --out 旁边也不许冒出 report.json"
    )


# --- T-A06: `arch --out` names a directory ----------------------------------


def test_arch_out_that_is_a_directory_is_exit_two_and_untouched(tmp_path, capsys):
    """`arch --out` writes a *file*; a directory there is a usage error, not a crash."""
    out_dir = tmp_path / "arch-target"
    out_dir.mkdir()

    assert cli.main(["arch", str(GOLDEN), "--out", str(out_dir)]) == 2
    captured = capsys.readouterr()

    assert _no_traceback(captured)
    assert captured.err.startswith("boardwise arch:")
    assert str(out_dir) in captured.err
    assert "文件" in captured.err, "要说清这里要的是文件路径"
    assert out_dir.is_dir(), "目录本身不变"
    assert list(out_dir.iterdir()) == [], "目录里不许出现 architecture.md 之类"


# --- negative control: the legal paths keep their contracts -----------------


def test_a_writable_out_dir_still_produces_the_report(tmp_path, capsys):
    """The fix must not buy the three exits by refusing a run that works."""
    out_dir = tmp_path / "checkup"

    code = _cmd_checkup(_checkup_args(out=str(out_dir)))
    captured = capsys.readouterr()

    assert code != 2, "合法 --out 不许被当成不可用输入"
    assert _no_traceback(captured)
    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    assert report["source"]["tier"] == "file"
    assert report["model"]["components"] == 17
    assert (out_dir / "report.md").is_file()


def test_arch_writes_the_skeleton_when_out_is_a_file_path(tmp_path, capsys):
    skeleton = tmp_path / "arch" / "architecture.md"

    assert cli.main(["arch", str(GOLDEN), "--out", str(skeleton)]) == 0
    captured = capsys.readouterr()

    assert _no_traceback(captured)
    assert skeleton.is_file()
    assert skeleton.read_text(encoding="utf-8").strip(), "合法 --out 要真的写出骨架"


# --- the refusal must not lie about what did land ---------------------------


def test_a_later_artifact_failing_does_not_claim_report_json_is_missing(
    tmp_path, monkeypatch, capsys
):
    """`report.json` lands, then `board-report.md` refuses — say *that*, not "no report".

    The first version of the message said "本次没有产出可用的 report.json", which is
    false in exactly this ordering: the report is on disk and one later delivery
    artifact is not. The assertion therefore pins the honest half — the run is not a
    complete delivery — and forbids the sentence that would make a reader redo a run
    whose `report.json` is already there.
    """
    out_dir = tmp_path / "checkup"
    real_write_text = Path.write_text

    def refuse_board_report(self, *args, **kwargs):
        if self.name == BOARD_REPORT_FILE:
            raise PermissionError(13, "Permission denied", str(self))
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", refuse_board_report)

    assert _cmd_checkup(_checkup_args(out=str(out_dir))) == 2
    captured = capsys.readouterr()

    assert _no_traceback(captured)
    assert (out_dir / "report.json").is_file(), "首个写动作必须真的成功（否则测的不是这个分支）"
    assert captured.err.startswith("boardwise checkup:")
    assert str(out_dir) in captured.err
    assert "未完整写出" in captured.err, "要如实说这次交付不完整"
    assert "不能当作完整交付" in captured.err
    assert BOARD_REPORT_FILE in captured.err, "要指名真正失败的那次写"
    assert "没有产出" not in captured.err, "report.json 已在盘上，不许说没有产出"
    assert "report.json 不存在" not in captured.err


def test_arch_skeleton_write_that_cannot_happen_is_exit_two(tmp_path, monkeypatch, capsys):
    """The skeleton file itself refusing the write is the same usage error, not a crash."""
    skeleton = tmp_path / "arch" / "architecture.md"
    real_write_text = Path.write_text

    def refuse_skeleton(self, *args, **kwargs):
        if self == skeleton:
            raise PermissionError(13, "Permission denied", str(self))
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", refuse_skeleton)

    assert cli.main(["arch", str(GOLDEN), "--out", str(skeleton)]) == 2
    captured = capsys.readouterr()

    assert _no_traceback(captured)
    assert captured.err.startswith("boardwise arch:")
    assert str(skeleton) in captured.err
    assert "一个字节都没写" not in captured.err, "写失败时不许谎称「一个字节都没写」"
    assert not skeleton.exists()


def test_arch_out_whose_parent_cannot_be_created_is_exit_two(tmp_path, capsys):
    """A parent that is a regular file is a real `OSError` — no monkeypatch needed."""
    blocker = tmp_path / "blocker"
    payload = b"parent is a plain file\n"
    blocker.write_bytes(payload)

    assert cli.main(["arch", str(GOLDEN), "--out", str(blocker / "architecture.md")]) == 2
    captured = capsys.readouterr()

    assert _no_traceback(captured)
    assert captured.err.startswith("boardwise arch:")
    assert blocker.read_bytes() == payload
