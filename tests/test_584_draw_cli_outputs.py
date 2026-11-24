"""584 / W-P(CLI): `draw` refuses unreadable input and impossible output targets.

569-G measured four shapes on the real CLI (`.tmp_hole569/g/`, matrix in
`outputs/hole569/g/`): a non-UTF-8 spec escaped `_draw_inputs` as a bare
`UnicodeDecodeError` (G-01); `draw compile --out` naming an existing **file**
crashed in `Path.mkdir` with `FileExistsError` (G-02); `--json` at a missing
directory, `--json` at a directory and `draw plan --out` under a missing
directory each ended in `FileNotFoundError`/`PermissionError` **after** the
candidates had landed (G-05); and `draw plan --out` was the opposite of
`draw compile --out` — a file path vs a directory path with no statement made
about it (G-06).

Every case here runs the CLI as a process (`python -c ... main(...)`) so the
assertion is about the exit code and stderr a caller actually gets: a traceback
means an exception escaped `main`. The `cand*` assertions are the second half
of G-05 — the refusal has to happen before the first candidate is written, so
the output directory must not hold one.

The two legal shapes are pinned too (a fresh/既有 directory for compile, an
existing or new file for plan, a `--json` file beside it): a preflight that also
refused those would pass every negative case while breaking the command.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "drawapply"
CIRCUIT = FIXTURES / "divider.circuit.json"
PRESENTATION = FIXTURES / "divider.presentation.json"
LIBRARY = FIXTURES / "library.json"
PAGE_BOX = "0,-1000,1200,0"
PAGE = "0,0,1169,826"
PROV = "verified_recipe"

_ENTRY = "import sys; from boardwise.cli import main; sys.exit(main(sys.argv[1:]))"


def run_cli(cwd: Path, *argv: str) -> subprocess.CompletedProcess:
    """The CLI as a caller sees it: exit code, stdout, stderr."""
    return subprocess.run(
        [str(Path(sys.executable)), "-c", _ENTRY, *argv],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd), timeout=180,
    )


def assert_no_candidates(directory: Path) -> None:
    """G-05's second half: the run stopped before writing one candidate."""
    leftovers = sorted(path.name for path in directory.glob("cand*")) if directory.is_dir() else []
    assert leftovers == [], f"candidates were written before the refusal: {leftovers}"


def assert_named_refusal(proc: subprocess.CompletedProcess, flag: str) -> str:
    assert "Traceback" not in proc.stderr, proc.stderr
    assert proc.returncode == 5, (proc.returncode, proc.stderr)
    assert flag in proc.stderr, proc.stderr
    return proc.stderr


# ------------------------------------------------------------------ page specs


def _part(part_id: str, symbol: str, value: str, lcsc: str) -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value, "lcsc": lcsc,
            "provenance": PROV}


def _net(net_id: str, cls: str, members: list[str]) -> dict:
    return {"id": net_id, "class": cls, "members": members, "provenance": PROV}


def _page_circuit() -> dict:
    return {
        "parts": [
            _part("U1", "AMS1117-3.3", "AMS1117-3.3", "C6186"),
            _part("C1", "C0402", "10uF", "C15525"),
            _part("C2", "C0402", "22uF", "C45783"),
            _part("R1", "R0402", "10k", "C25744"),
            _part("R2", "R0402", "10k", "C25744"),
        ],
        "nets": [
            _net("VIN", "power", ["U1.3", "C1.1", "R1.1"]),
            _net("3V3", "power", ["U1.2", "C2.1"]),
            _net("TAP", "signal", ["R1.2", "R2.1"]),
            _net("GND", "gnd", ["U1.1", "C1.2", "C2.2", "R2.2"]),
        ],
    }


def _page_presentation() -> dict:
    return {
        "modules": [
            {"id": "pwr", "parts": ["U1", "C1", "C2"], "role": "regulator",
             "grammarRef": "ldo"},
            {"id": "sense", "parts": ["R1", "R2"], "role": "divider",
             "grammarRef": "voltage-divider"},
        ],
        "flow": [["pwr", "sense"]],
        "portRoles": {"VIN": "input", "3V3": "output"},
        "directWiringObligations": [
            {"nets": ["VIN", "3V3"], "note": "the regulator's own rails are wired"},
        ],
    }


def write_page_specs(tmp_path: Path) -> tuple[Path, Path]:
    circuit = tmp_path / "page.circuit.json"
    presentation = tmp_path / "page.presentation.json"
    circuit.write_text(json.dumps(_page_circuit()), encoding="utf-8")
    presentation.write_text(json.dumps(_page_presentation()), encoding="utf-8")
    return circuit, presentation


def _compile_args(circuit: Path = CIRCUIT, presentation: Path = PRESENTATION) -> list[str]:
    return [
        "draw", "compile",
        "--circuit", str(circuit),
        "--presentation", str(presentation),
        "--profiles", str(LIBRARY),
    ]


def _plan_args(circuit: Path = CIRCUIT, presentation: Path = PRESENTATION) -> list[str]:
    return [
        "draw", "plan",
        "--circuit", str(circuit),
        "--presentation", str(presentation),
        "--profiles", str(LIBRARY),
        "--lcsc", "R1=C25744",
        "--lcsc", "R2=C25744",
    ]


# ------------------------------------------------------- 569G-01: the decoders


def test_584_g01_non_utf8_circuit_is_a_named_refusal(tmp_path):
    bad = tmp_path / "badutf8.circuit.json"
    bad.write_bytes(b'{"parts": [\xff\xfe]}')
    proc = run_cli(tmp_path, *_compile_args(circuit=bad), "--page-box", PAGE_BOX)
    err = assert_named_refusal(proc, "--circuit")
    assert "UTF-8" in err or "codec" in err, err


def test_584_g01_non_utf8_presentation_is_a_named_refusal(tmp_path):
    bad = tmp_path / "badutf8.presentation.json"
    bad.write_bytes(b'\xff\xfe{"modules": []}')
    proc = run_cli(tmp_path, *_compile_args(presentation=bad), "--page-box", PAGE_BOX)
    err = assert_named_refusal(proc, "--presentation")
    assert "UTF-8" in err or "codec" in err, err


def test_584_g01_non_utf8_profiles_is_a_named_refusal(tmp_path):
    bad = tmp_path / "badutf8.library.json"
    bad.write_bytes(b'\xff\xfe{"profiles": []}')
    proc = run_cli(
        tmp_path,
        "draw", "compile", "--circuit", str(CIRCUIT),
        "--presentation", str(PRESENTATION), "--profiles", str(bad),
        "--page-box", PAGE_BOX,
    )
    err = assert_named_refusal(proc, "--profiles")
    assert "UTF-8" in err or "codec" in err, err


def test_584_g01_missing_and_bad_json_still_say_cannot_be_read(tmp_path):
    """The existing words for the shapes G-01 shares a try-block with."""
    missing = run_cli(
        tmp_path, *_compile_args(circuit=tmp_path / "missing.json"), "--page-box", PAGE_BOX
    )
    assert missing.returncode == 5
    assert "cannot be read" in missing.stderr
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    proc = run_cli(tmp_path, *_compile_args(circuit=broken), "--page-box", PAGE_BOX)
    assert proc.returncode == 5
    assert "is not JSON" in proc.stderr
    assert "Traceback" not in proc.stderr


# ------------------------------------------- 569G-02 / G-05: compile --out/--json


def test_584_g02_compile_out_existing_file_is_refused_before_the_compile(tmp_path):
    out = tmp_path / "afile"
    out.write_text("a file, not a directory", encoding="utf-8")
    proc = run_cli(tmp_path, *_compile_args(), "--page-box", PAGE_BOX, "--out", str(out))
    err = assert_named_refusal(proc, "--out")
    assert "directory" in err, err
    assert out.read_text(encoding="utf-8") == "a file, not a directory"
    assert_no_candidates(tmp_path)


def test_584_g05_compile_json_missing_parent_is_refused_before_the_candidates(tmp_path):
    out = tmp_path / "previews"
    report = tmp_path / "nope" / "compile.json"
    proc = run_cli(
        tmp_path, *_compile_args(), "--page-box", PAGE_BOX,
        "--out", str(out), "--json", str(report),
    )
    err = assert_named_refusal(proc, "--json")
    assert "does not exist" in err, err
    assert not report.exists()
    assert_no_candidates(out)


def test_584_g05_compile_json_is_a_directory_is_refused_before_the_candidates(tmp_path):
    out = tmp_path / "previews"
    report_as_dir = tmp_path / "jsondir"
    report_as_dir.mkdir()
    proc = run_cli(
        tmp_path, *_compile_args(), "--page-box", PAGE_BOX,
        "--out", str(out), "--json", str(report_as_dir),
    )
    err = assert_named_refusal(proc, "--json")
    assert "directory" in err, err
    assert_no_candidates(out)


def test_584_g05_compile_json_parent_is_a_file_is_refused(tmp_path):
    out = tmp_path / "previews"
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    proc = run_cli(
        tmp_path, *_compile_args(), "--page-box", PAGE_BOX,
        "--out", str(out), "--json", str(blocker / "report.json"),
    )
    err = assert_named_refusal(proc, "--json")
    assert "not a directory" in err, err
    assert_no_candidates(out)


def test_584_g05_page_compile_json_missing_parent_is_refused_before_the_candidates(
    tmp_path,
):
    circuit, presentation = write_page_specs(tmp_path)
    out = tmp_path / "previews"
    report = tmp_path / "nope" / "page.json"
    proc = run_cli(
        tmp_path, *_compile_args(circuit=circuit, presentation=presentation),
        "--page-box", PAGE, "--out", str(out), "--json", str(report),
    )
    err = assert_named_refusal(proc, "--json")
    assert "does not exist" in err, err
    assert not report.exists()
    assert_no_candidates(out)


def test_584_g05_page_compile_out_existing_file_is_refused_before_the_compile(tmp_path):
    circuit, presentation = write_page_specs(tmp_path)
    out = tmp_path / "afile"
    out.write_text("x", encoding="utf-8")
    proc = run_cli(
        tmp_path, *_compile_args(circuit=circuit, presentation=presentation),
        "--page-box", PAGE, "--out", str(out),
    )
    err = assert_named_refusal(proc, "--out")
    assert "directory" in err, err
    assert_no_candidates(tmp_path)


# ------------------------------------------------- 569G-05 / G-06: plan outputs


def test_584_g06_plan_out_existing_directory_is_refused_by_name(tmp_path):
    out = tmp_path / "outdir"
    out.mkdir()
    proc = run_cli(tmp_path, *_plan_args(), "--page-box", PAGE_BOX, "--out", str(out))
    err = assert_named_refusal(proc, "--out")
    assert "file" in err and "directory" in err, err
    assert list(out.iterdir()) == []


def test_584_g05_plan_out_missing_parent_is_refused_before_the_plan(tmp_path):
    out = tmp_path / "nope" / "plan.json"
    proc = run_cli(tmp_path, *_plan_args(), "--page-box", PAGE_BOX, "--out", str(out))
    err = assert_named_refusal(proc, "--out")
    assert "does not exist" in err, err
    assert not out.exists()


def test_584_g05_plan_out_parent_is_a_file_is_refused(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    proc = run_cli(
        tmp_path, *_plan_args(), "--page-box", PAGE_BOX,
        "--out", str(blocker / "plan.json"),
    )
    err = assert_named_refusal(proc, "--out")
    assert "not a directory" in err, err
    assert blocker.read_text(encoding="utf-8") == "x"


def test_584_g05_page_plan_json_missing_parent_writes_no_plan(tmp_path):
    circuit, presentation = write_page_specs(tmp_path)
    out = tmp_path / "plan.json"
    report = tmp_path / "nope" / "report.json"
    proc = run_cli(
        tmp_path,
        "draw", "plan", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE,
        "--out", str(out), "--json", str(report),
    )
    err = assert_named_refusal(proc, "--json")
    assert "does not exist" in err, err
    assert not out.exists(), "the plan was written before the --json target was refused"
    assert not (tmp_path / "plan.page.json").exists()
    assert not report.exists()


def test_584_g05_page_plan_out_existing_directory_is_refused(tmp_path):
    circuit, presentation = write_page_specs(tmp_path)
    out = tmp_path / "outdir"
    out.mkdir()
    proc = run_cli(
        tmp_path,
        "draw", "plan", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE, "--out", str(out),
    )
    err = assert_named_refusal(proc, "--out")
    assert "file" in err and "directory" in err, err
    assert list(out.iterdir()) == []


# ------------------------------------------------ the legal shapes are untouched


def test_584_legal_compile_writes_candidates_into_a_fresh_and_an_existing_directory(
    tmp_path,
):
    fresh = tmp_path / "fresh"
    proc = run_cli(
        tmp_path, *_compile_args(), "--page-box", PAGE_BOX,
        "--out", str(fresh), "--json", str(tmp_path / "compile.json"),
    )
    assert proc.returncode == 0, proc.stderr
    assert "Traceback" not in proc.stderr
    assert sorted(path.name for path in fresh.glob("cand*"))
    payload = json.loads((tmp_path / "compile.json").read_text(encoding="utf-8"))
    assert payload["ok"] is True and payload["candidates"]

    existing = tmp_path / "existing"
    existing.mkdir()
    proc = run_cli(
        tmp_path, *_compile_args(), "--page-box", PAGE_BOX, "--out", str(existing)
    )
    assert proc.returncode == 0, proc.stderr
    assert sorted(path.name for path in existing.glob("cand*"))


def test_584_legal_plan_still_writes_the_file_it_is_given(tmp_path):
    out = tmp_path / "plan.json"
    report = tmp_path / "report.json"
    proc = run_cli(
        tmp_path, *_plan_args(), "--page-box", PAGE_BOX,
        "--out", str(out), "--json", str(report),
    )
    printed = proc.stdout
    assert proc.returncode == 0, proc.stderr + printed
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["change"]["kind"] == "draw-module"
    assert json.loads(report.read_text(encoding="utf-8"))["command"] == "plan"


def test_584_legal_page_plan_still_writes_the_plan_and_its_page_document(tmp_path):
    circuit, presentation = write_page_specs(tmp_path)
    out = tmp_path / "plan.json"
    proc = run_cli(
        tmp_path,
        "draw", "plan", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE, "--out", str(out),
    )
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    assert (tmp_path / "plan.page.json").is_file(), "the page document sits beside the plan"
