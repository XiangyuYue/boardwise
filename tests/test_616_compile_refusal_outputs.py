"""616 / F2-07: a compile that refuses must not swallow the output refusal.

570-F2-07 measured the old HEAD: `draw compile ... --json <missing parent>`
ended in `FileNotFoundError` after the candidates had landed, so the named
refusal and exit 5 never arrived. 584 closed it by asking both output flags
before the compile (`_draw_output_checks` at the top of `_cmd_draw_compile`);
this file is the permanent regression for the shape 584 did not name — an
output refusal **stacked on** a compile that also refuses. The F2 inputs are
the real blocklib ones (`sy8089_buck_3v3`) and `--page-box 0,0,420,300` is
below the smallest legal layout, so the compile's own answer is `layout-unsat`.

Two orders are pinned, and they are not the same claim:

* missing `--json` parent + a compile that would say `[layout-unsat]`: exit 5,
  `--json` and the missing directory named, no traceback, the parent is **not**
  created (the CLI does not invent directories), no `result.json`, and the new
  `--out` directory holds nothing — the preflight wins, so the refusal stays
  the output's own sentence.
* legal `--json` parent, the same page box: exit 5, `[layout-unsat]` in stderr,
  no traceback, and the report exists with `ok=false` and a non-empty
  `failures` — the compile refusal is still written where 584 put it.

The parent baseline for both runs is `evidence/616/PARENT-BASELINE.md`; these
tests are the same two commands, run as processes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT = ROOT / "blocklib" / "modules" / "circuits" / "sy8089_buck_3v3.circuit.json"
PRESENTATION = ROOT / "blocklib" / "specs" / "sy8089_buck_3v3.presentation.json"
PROFILES = ROOT / "blocklib" / "symbols" / "profiles.json"
PAGE_BOX = "0,0,420,300"

_ENTRY = "import sys; from boardwise.cli import main; sys.exit(main(sys.argv[1:]))"


def run_cli(cwd: Path, *argv: str) -> subprocess.CompletedProcess:
    """The CLI as a caller sees it: exit code, stdout, stderr."""
    return subprocess.run(
        [str(Path(sys.executable)), "-c", _ENTRY, *argv],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd), timeout=180,
    )


def compile_args() -> list[str]:
    return [
        "draw", "compile",
        "--circuit", str(CIRCUIT),
        "--presentation", str(PRESENTATION),
        "--profiles", str(PROFILES),
        "--page-box", PAGE_BOX,
    ]


def assert_no_candidates(directory: Path) -> None:
    leftovers = sorted(path.name for path in directory.glob("cand*")) \
        if directory.is_dir() else []
    assert leftovers == [], f"candidates were written before the refusal: {leftovers}"


def test_616_f2_07_missing_json_parent_wins_over_the_layout_refusal(tmp_path):
    out = tmp_path / "previews"
    missing = tmp_path / "nope"
    report = missing / "result.json"
    proc = run_cli(
        tmp_path, *compile_args(), "--out", str(out), "--json", str(report)
    )
    assert "Traceback" not in proc.stderr, proc.stderr
    assert proc.returncode == 5, (proc.returncode, proc.stderr)
    assert "--json" in proc.stderr, proc.stderr
    assert "does not exist" in proc.stderr, proc.stderr
    assert str(missing) in proc.stderr, proc.stderr
    assert not missing.exists(), "the CLI created the missing --json directory"
    assert not report.exists(), "a report was written to a refused target"
    assert not out.exists(), "the --out directory was created before the refusal"
    assert_no_candidates(out)


def test_616_f2_07_legal_json_parent_keeps_the_layout_refusal(tmp_path):
    out = tmp_path / "previews"
    report = tmp_path / "result.json"
    proc = run_cli(
        tmp_path, *compile_args(), "--out", str(out), "--json", str(report)
    )
    assert "Traceback" not in proc.stderr, proc.stderr
    assert proc.returncode == 5, (proc.returncode, proc.stderr)
    # The four categories are printed on stdout (the refusal summary is the one
    # line on stderr), so the named reason is asked of the caller's whole view.
    assert "layout-unsat" in proc.stdout + proc.stderr, (proc.stdout, proc.stderr)
    assert report.is_file(), "the compile refusal was not written to --json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is False, payload
    assert payload["failures"], payload
    assert_no_candidates(out)


def test_616_f2_07_preflight_runs_before_the_compile(monkeypatch, tmp_path, capsys):
    """The output refusal is decided without compiling at all (spy, not the proof)."""
    import boardwise.cli as cli

    def explode(*args, **kwargs):
        raise AssertionError("the compile ran although the --json target was refused")

    monkeypatch.setattr(cli, "_draw_compile", explode)
    monkeypatch.setattr(cli, "_cmd_draw_compile_page", explode)

    missing = tmp_path / "nope"
    code = cli.main([
        *compile_args(),
        "--out", str(tmp_path / "previews"),
        "--json", str(missing / "result.json"),
    ])
    err = capsys.readouterr().err
    assert code == 5, err
    assert "--json" in err and "does not exist" in err, err
    assert not missing.exists()
