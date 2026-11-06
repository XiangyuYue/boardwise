"""`checkup --strict` — the re-computation guard (541 R2).

What this file pins, and why each piece is a separate test:

* the **first** strict run is allowed and freezes `run.json` from the report (not
  from a second walk of the board);
* the **second** run over the same evidence is refused *before* any work — the
  spies here are the contract, because "refused after loading the model and
  running the rules, then printed a warning" is the failure mode this batch
  exists to make impossible;
* the refusal **escalates** with the count: a baseline that already had two
  reviews demands new evidence, not merely a different command;
* a changed archive opens a new run and `run-diff.json` says what moved — with a
  single-variable attribution only when exactly one variable did;
* `--new-evidence archive-bytes-changed` is a claim the guard **checks**: the same
  bytes with the flag is still a refusal;
* a broken `run.json` is not a first run;
* `--strict` online is refused without a daemon;
* without the flag nothing is read and nothing is written (a *corrupt* manifest is
  the proof: a non-strict run must not even notice it);
* the default report's shape is untouched, and finding identities are stable,
  unique, and keyed for every severity rather than the `warning_triage` WARN subset;
* **B5 fix B**: the run's own output (`--out` inside the project tree, or at the
  project root) never enters the digest that judged it, the two human sidecars in
  `--out` always do, a copy of the same bytes at another path is the same
  baseline, and an unwritten manifest says `run-manifest-unwritten` without moving
  the exit code.

No test connects to the editor: every run here is the offline `--file` path, and
the online case asserts the refusal happens before `_load_model_online` is called.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pytest

import boardwise.cli as cli
from boardwise.core.runmanifest import SCHEMA, sha256_file

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = FIXTURES / "ch340_golden.epro2"
#: A second, genuinely different export (a different board), used only as "the
#: archive's bytes changed" — same path, other bytes.
OTHER = FIXTURES / "毕设滤波采样_2026-09-27.epro2"
LIBRARY = Path(__file__).resolve().parents[1] / "blocklib" / "parts.json"


def _args(out: Path, **overrides) -> argparse.Namespace:
    """A checkup invocation as `_checkup_args` in test_checkup_cli builds it.

    The two 541 attributes are spelled out on purpose: a hand-built Namespace is
    exactly what the default-path compatibility claim is about, and the guard has
    to read them with `getattr` so a caller that predates the flag still works.
    """
    base = {
        "file": str(GOLDEN),
        "project": "",
        "instance": "",
        "out": str(out),
        "port": None,
        "strict": True,
        "new_evidence": "",
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _manifest(out: Path) -> dict:
    return json.loads((out / "run.json").read_text(encoding="utf-8"))


def _report(out: Path) -> dict:
    return json.loads((out / "report.json").read_text(encoding="utf-8"))


def _spies(monkeypatch) -> list[str]:
    """Zero-call proof for everything a refusal must not reach (541 R2 §2)."""
    calls: list[str] = []
    for name in (
        "_load_model",
        "run_review",
        "_run_pcb_runner",
        "_write_checkup_report",
        "_checkup_lock_acquire",
    ):
        real = getattr(cli, name)

        def spy(*a, _name=name, _real=real, **k):
            calls.append(_name)
            return _real(*a, **k)

        monkeypatch.setattr(cli, name, spy)
    return calls


# ---------------------------------------------------------------------------
# The first run: allowed, and it freezes what it really read
# ---------------------------------------------------------------------------


def test_the_first_strict_run_freezes_the_manifest_from_the_report(tmp_path):
    out = tmp_path / "out"
    assert cli._cmd_checkup(_args(out)) == 3, "the golden fixture's verdict is incomplete → 3"

    manifest = _manifest(out)
    report = _report(out)

    assert manifest["schema"] == SCHEMA
    assert manifest["drcReviewCount"] == 1
    assert manifest["newEvidence"] is None
    assert not (out / "run-diff.json").exists(), "nothing to diff on a first run"

    # inputs: the project archive and the shelf the run actually read, by absolute
    # path and by digest — recomputed here, never trusted from the manifest.
    rows = {row["path"]: row for row in manifest["inputs"]}
    project = str(GOLDEN.resolve()).replace("\\", "/")
    library = str(LIBRARY.resolve()).replace("\\", "/")
    assert set(rows) == {project, library}
    assert rows[project]["sha256"] == sha256_file(GOLDEN)
    assert rows[project]["bytes"] == GOLDEN.stat().st_size
    assert rows[library]["sha256"] == sha256_file(LIBRARY)

    # engine: the three fingerprints, the same ones the report's completion
    # section names as this build's source versions.
    engine = manifest["engine"]
    assert set(engine) == {"boardwise", "ruleset", "rulebody"}
    assert engine["boardwise"] == report["toolVersion"]
    assert engine["ruleset"] == report["completion"]["sourceVersions"]["ruleset"]
    assert engine["rulebody"] == (
        report["completion"]["sourceVersions"]["rulebody"] or "unavailable"
    )
    assert manifest["intent"] is None, "no default contract exists in this environment"

    # pages / modelCounts / findings come out of the report, not re-derived
    assert manifest["pages"] == [page for b in report["model"]["boards"] for page in b["pages"]]
    assert manifest["modelCounts"] == {
        "components": report["model"]["components"],
        "nets": report["model"]["nets"],
        "datasheetsMissing": report["summary"]["unreviewedParts"],
    }
    findings = manifest["findings"]
    assert len(findings) == len(report["findings"])
    assert len(set(findings)) == len(findings), "identities are unique by construction"
    assert findings == sorted(findings)
    assert all(identity.startswith("boardwise-rule:") for identity in findings)
    # the identity is the rule + its structured target, never the message text
    assert all("找不到" not in identity for identity in findings)

    # channels are the report's own evidence statuses, as booleans
    closed = {"ok", "not-applicable"}
    expected = {
        name: str((row or {}).get("status") or "") in closed
        for name, row in report["evidence"]["channels"].items()
    }
    assert manifest["channels"] == expected
    assert any(manifest["channels"].values()), "at least the archive was read"


def test_a_second_run_over_the_same_evidence_is_refused_before_any_work(
    tmp_path, monkeypatch, capsys
):
    """The same baseline and no new evidence → exit 2 with the code, and no work.

    The manifest is copied into a **fresh** output directory, so "no lock carrier"
    is a real assertion: had the guard run after `_checkup_lock_acquire`, the
    carrier would exist in that directory.
    """
    first = tmp_path / "first"
    assert cli._cmd_checkup(_args(first)) == 3
    capsys.readouterr()

    second = tmp_path / "second"
    second.mkdir()
    shutil.copyfile(first / "run.json", second / "run.json")

    calls = _spies(monkeypatch)
    assert cli._cmd_checkup(_args(second)) == 2

    assert calls == [], f"a refusal reached {calls}"
    stderr = capsys.readouterr().err
    assert "reject-use-existing" in stderr
    assert not (second / ".checkup.lock").exists(), "no lock carrier for a refused run"
    assert not (second / "report.json").exists(), "no report byte for a refused run"


def test_a_baseline_with_two_reviews_demands_new_evidence(tmp_path, capsys):
    first = tmp_path / "first"
    assert cli._cmd_checkup(_args(first)) == 3
    capsys.readouterr()

    second = tmp_path / "second"
    second.mkdir()
    manifest = _manifest(first)
    manifest["drcReviewCount"] = 2
    (second / "run.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert cli._cmd_checkup(_args(second)) == 2
    stderr = capsys.readouterr().err
    assert "reject-needs-new-evidence" in stderr
    assert "reject-use-existing" not in stderr
    assert not (second / ".checkup.lock").exists()


def test_a_broken_manifest_is_refused_instead_of_read_as_a_first_run(tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    (out / "run.json").write_text('{"schema": "boardwise.run-manifest/1", "runI', encoding="utf-8")

    assert cli._cmd_checkup(_args(out)) == 2
    stderr = capsys.readouterr().err
    assert "reject-unreadable-manifest" in stderr
    assert not (out / ".checkup.lock").exists()
    assert not (out / "report.json").exists()
    # The bad manifest is left exactly as it was: a refusal does not rewrite state.
    assert (out / "run.json").read_text(encoding="utf-8").endswith('"runI')


# ---------------------------------------------------------------------------
# New evidence: opens a run, and the diff says which variable moved
# ---------------------------------------------------------------------------


def test_a_changed_archive_opens_a_new_run_and_diff_records_it(tmp_path, capsys):
    project = tmp_path / "proj.epro2"
    shutil.copyfile(GOLDEN, project)
    out = tmp_path / "out"

    assert cli._cmd_checkup(_args(out, file=str(project))) == 3
    first = _manifest(out)
    assert first["drcReviewCount"] == 1
    capsys.readouterr()

    # The user re-exports: same path, different bytes. That is new evidence, and
    # declaring it is optional once the digest moved.
    shutil.copyfile(OTHER, project)
    second_args = _args(
        out, file=str(project), new_evidence="archive-bytes-changed"
    )
    assert cli._cmd_checkup(second_args) == 1

    second = _manifest(out)
    assert second["drcReviewCount"] == 2, "a new run over a moved baseline counts +1"
    assert second["runId"] != first["runId"], "a run id names one run, not a board"
    assert second["newEvidence"] == "archive-bytes-changed"
    assert second["inputs"] != first["inputs"]

    diff = json.loads((out / "run-diff.json").read_text(encoding="utf-8"))
    assert set(diff) == {
        "sameBaseline",
        "inputsChanged",
        "coverageChanged",
        "addedFindings",
        "removedFindings",
        "multiVariableChange",
        "attribution",
    }
    assert diff["sameBaseline"] is False
    changed = diff["inputsChanged"]
    assert len(changed) == 1, f"exactly the archive moved, got {changed}"
    assert changed[0]["path"] == str(project.resolve()).replace("\\", "/")
    before = {row["path"]: row["sha256"] for row in first["inputs"]}
    assert changed[0]["before"] == before[changed[0]["path"]]
    assert changed[0]["after"] == sha256_file(project)
    assert diff["addedFindings"] and diff["removedFindings"]
    assert not set(diff["addedFindings"]) & set(diff["removedFindings"])
    # Two variables really did move here (the second export's coverage differs), so
    # the diff must refuse to hand the change to one of them.
    assert diff["multiVariableChange"] is (
        len(changed) + len(diff["coverageChanged"]) > 1
    )
    assert diff["attribution"] == (
        "multi-variable-change"
        if diff["multiVariableChange"]
        else f"input:{changed[0]['path']}"
    )

    # Same baseline twice already reviewed → the next identical run is refused
    # with the escalation, and the count that triggered it is the file's own.
    capsys.readouterr()
    assert cli._cmd_checkup(_args(out, file=str(project))) == 2
    assert "reject-needs-new-evidence" in capsys.readouterr().err


def test_the_same_archive_with_a_new_evidence_claim_is_refused(tmp_path, capsys):
    out = tmp_path / "out"
    assert cli._cmd_checkup(_args(out)) == 3
    capsys.readouterr()

    refusal = _args(out, new_evidence="archive-bytes-changed")
    assert cli._cmd_checkup(refusal) == 2
    stderr = capsys.readouterr().err
    assert "reject-evidence-not-new" in stderr
    # The declaration is checked, not believed: nothing was re-run or re-written.
    assert _manifest(out)["drcReviewCount"] == 1
    assert not (out / "run-diff.json").exists()


# ---------------------------------------------------------------------------
# What the baseline is made of
# ---------------------------------------------------------------------------


def test_the_current_baseline_carries_intent_library_and_interconnect(tmp_path):
    contract = tmp_path / "contract.json"
    contract.write_text(
        json.dumps(
            {
                "intentVersion": 1,
                "requirements": {"rails": [], "signals": [], "buses": []},
                "blocks": [],
                "decisions": [],
            }
        ),
        encoding="utf-8",
    )
    library = tmp_path / "shelf.json"
    shutil.copyfile(LIBRARY, library)
    interconnect = tmp_path / "interconnect.json"
    interconnect.write_text("{}", encoding="utf-8")

    plan = cli._checkup_strict_baseline(
        _args(
            tmp_path / "out",
            intent=str(contract),
            library=str(library),
            interconnect=str(interconnect),
        ),
        tmp_path / "out",
    )
    assert plan is not None
    paths = [row["path"] for row in plan["inputs"]]
    assert str(GOLDEN.resolve()).replace("\\", "/") in paths
    assert str(library.resolve()).replace("\\", "/") in paths
    assert str(interconnect.resolve()).replace("\\", "/") in paths
    assert plan["intent"] == {
        "path": str(contract.resolve()).replace("\\", "/"),
        "sha256": sha256_file(contract),
    }
    # The hashes are the files' own, so a re-export or an edited contract moves
    # the baseline instead of reusing an old conclusion.
    rows = {row["path"]: row["sha256"] for row in plan["inputs"]}
    assert rows[str(interconnect.resolve()).replace("\\", "/")] == sha256_file(interconnect)


def test_the_default_intent_path_reuses_the_architecture_fold(tmp_path, monkeypatch):
    """The guard's intent path is the run body's, not a second spelling (R2 §3)."""
    from types import SimpleNamespace

    from boardwise.core.architecture import _project_uuid

    expected = _project_uuid(SimpleNamespace(source=str(GOLDEN)))[0]
    home = tmp_path / "home"
    (home / "design-intent").mkdir(parents=True)
    contract = home / "design-intent" / f"{expected}.json"
    contract.write_text(
        json.dumps(
            {
                "intentVersion": 1,
                "requirements": {"rails": [], "signals": [], "buses": []},
                "blocks": [],
                "decisions": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BOARDWISE_HOME", str(home))

    plan = cli._checkup_strict_baseline(_args(tmp_path / "out"), tmp_path / "out")
    assert plan is not None
    assert plan["intent"] is not None
    assert plan["intent"]["path"] == str(contract.resolve()).replace("\\", "/")
    assert plan["intent"]["sha256"] == sha256_file(contract)


def test_a_changed_library_opens_a_new_run(tmp_path, capsys):
    """Same shelf path, different bytes: the shelf is evidence, so a new run.

    B5 fix B narrowed this test. A shelf **copied to another path** carries the
    same bytes and is now the same baseline — a path is not evidence; see
    `test_the_same_bytes_at_a_new_path_are_the_same_baseline`. Changing the file's
    content is what opens the run.
    """
    library = tmp_path / "shelf.json"
    shutil.copyfile(LIBRARY, library)
    out = tmp_path / "out"

    assert cli._cmd_checkup(_args(out, library=str(library))) == 3
    first = _manifest(out)
    shelf_path = str(library.resolve()).replace("\\", "/")
    assert any(row["path"] == shelf_path for row in first["inputs"])
    capsys.readouterr()

    # Same path, edited content (a trailing newline is enough: the baseline is the
    # file's SHA-256, not a parse of it) → a different baseline, a second run.
    library.write_bytes(library.read_bytes() + b"\n")
    assert cli._cmd_checkup(_args(out, library=str(library))) == 3
    second = _manifest(out)
    assert second["drcReviewCount"] == 2
    assert second["inputs"] != first["inputs"]
    diff = json.loads((out / "run-diff.json").read_text(encoding="utf-8"))
    assert diff["sameBaseline"] is False
    changed = {row["path"]: row for row in diff["inputsChanged"]}
    assert shelf_path in changed, "the shelf that moved is named in the diff"
    assert changed[shelf_path]["before"] == sha256_file(LIBRARY)
    assert changed[shelf_path]["after"] == sha256_file(library)


# ---------------------------------------------------------------------------
# Online refusal, and the untouched default path
# ---------------------------------------------------------------------------


def test_online_strict_is_refused_without_reaching_the_daemon(tmp_path, monkeypatch, capsys):
    def bomb(*_a, **_k):  # noqa: ANN002, ANN003 — a spy that must never run
        raise AssertionError("an online --strict run reached the daemon")

    monkeypatch.setattr(cli, "_load_model_online", bomb)
    out = tmp_path / "out"

    assert cli._cmd_checkup(_args(out, file="")) == 2
    stderr = capsys.readouterr().err
    assert "--strict" in stderr and "离线" in stderr
    assert not out.exists(), "a refused invocation creates no --out and no lock"


def test_without_strict_nothing_is_read_or_written(tmp_path, capsys):
    """A corrupt `run.json` is the sharpest proof of "never read without --strict".

    A run that peeked would have to refuse it (that is what `--strict` does with
    the same file); this one must not notice it at all, and must not touch it.
    """
    out = tmp_path / "out"
    out.mkdir()
    sentinel = '{"not": "a manifest"'
    (out / "run.json").write_text(sentinel, encoding="utf-8")

    args = _args(out, strict=False)
    assert cli._cmd_checkup(args) == 3
    assert (out / "report.json").is_file()
    assert (out / "run.json").read_text(encoding="utf-8") == sentinel
    assert not (out / "run-diff.json").exists()
    capsys.readouterr()

    # And a plain rerun stays legal even with a *valid* manifest from a strict run.
    strict_out = tmp_path / "strict"
    assert cli._cmd_checkup(_args(strict_out)) == 3
    frozen = (strict_out / "run.json").read_bytes()
    assert cli._cmd_checkup(_args(strict_out, strict=False)) == 3
    assert (strict_out / "run.json").read_bytes() == frozen


def test_the_default_report_shape_is_unchanged(tmp_path, capsys):
    """`--strict` adds files beside the report, not keys inside it."""
    plain = tmp_path / "plain"
    strict = tmp_path / "strict"
    assert cli._cmd_checkup(_args(plain, strict=False)) == 3
    capsys.readouterr()
    assert cli._cmd_checkup(_args(strict)) == 3
    capsys.readouterr()

    plain_report = _report(plain)
    strict_report = _report(strict)
    assert set(plain_report) == set(strict_report)
    assert plain_report["schema"] == strict_report["schema"] == "boardwise.checkup/7"
    assert not {"run", "runManifest", "runDiff", "drcReviewCount"} & set(plain_report)
    assert plain_report["findings"] == strict_report["findings"]
    assert plain_report["evidence"] == strict_report["evidence"]

    parser = cli.build_parser()
    defaults = parser.parse_args(["checkup", "--file", "x.epro2"])
    assert defaults.strict is False
    assert defaults.new_evidence == ""
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["checkup", "--file", "x.epro2", "--new-evidence", "because-i-say-so"]
        )


# ---------------------------------------------------------------------------
# Finding identities
# ---------------------------------------------------------------------------


def test_a_folder_project_baselines_the_tree_not_its_index(tmp_path, capsys):
    """A folder project's evidence is `sch/**` + `pcb/**`, not the 354-byte index.

    Hashing only the `.eprj3` index would let a re-drawn page reuse the previous
    conclusion — the reuse this guard exists to stop — so both spellings (the
    folder, and the index file inside it) fold to the folder's content digest.
    """
    source = FIXTURES / "eprj3_synth"
    project = tmp_path / "proj"
    shutil.copytree(source, project)
    index = project / "eprj3_synth.eprj3"
    out = tmp_path / "out"

    assert cli._cmd_checkup(_args(out, file=str(index))) == 3
    manifest = _manifest(out)
    rows = {row["path"]: row for row in manifest["inputs"]}
    root = str(project.resolve()).replace("\\", "/")
    assert root in rows, f"the folder is the project input, got {list(rows)}"
    size, digest = cli._checkup_tree_digest(project, out)
    assert rows[root]["bytes"] == size
    assert rows[root]["sha256"] == digest
    capsys.readouterr()

    # Editing one page inside the folder moves the baseline (same out dir, so this
    # is a real "new evidence" judgement, not a unit shortcut).
    page = sorted(path for path in (project / "sch").rglob("*") if path.is_file())[0]
    page.write_bytes(page.read_bytes() + b"\n")
    moved = cli._checkup_strict_baseline(_args(out, file=str(project)), out)
    assert moved is not None
    assert moved["projectPath"] == root
    assert moved["projectSha256"] != rows[root]["sha256"]


def test_finding_identities_are_stable_unique_and_cover_every_severity():
    """Every severity is keyed, not the `warning_triage` WARN subset (R2 §4)."""
    findings = [
        {
            "rule_id": "decap-required-caps",
            "severity": "WARN",
            "message": "U11 pin5: the grounded capacitor on 'NET10' is only 100nF",
            "target": {"component_ref": "U11", "pin_refs": ["5"], "net_refs": ["NET10"]},
            "refs": ["U11", "C20"],
        },
        {
            # Same rule and part, another pin: a *different* identity.
            "rule_id": "decap-required-caps",
            "severity": "WARN",
            "message": "U11 pin6: the grounded capacitor on 'NET11' is only 100nF",
            "target": {"component_ref": "U11", "pin_refs": ["6"], "net_refs": ["NET11"]},
            "refs": ["U11"],
        },
        {
            # Reworded, same structured target: the *same* identity.
            "rule_id": "decap-required-caps",
            "severity": "WARN",
            "message": "completely different prose about the same pin",
            "target": {"component_ref": "U11", "pin_refs": ["5"], "net_refs": ["NET10"]},
            "refs": ["U11"],
        },
        {
            "rule_id": "pcb-footprint-consistency",
            "severity": "ERROR",
            "message": "U1 footprint mismatch",
            "target": {"component_ref": "U1", "pin_refs": [], "net_refs": []},
            "refs": ["U1"],
        },
        {
            "rule_id": "some-info-rule",
            "severity": "INFO",
            "message": "just so you know",
            "target": {},
            "refs": ["R7"],
        },
    ]
    identities = cli._checkup_finding_identities(findings)

    assert len(identities) == len(findings), "each finding gets its own identity"
    assert len(set(identities)) == len(identities), "identities never repeat"
    string_11_5 = "boardwise-rule:decap-required-caps:U11,pin:5,net:NET10"
    assert identities.count(string_11_5) == 1, "the reworded duplicate collapsed… "
    # …and the collapse is a *deduplication of identity*, which leaves the second
    # row the `#2` suffix rather than silently dropping it.
    assert string_11_5 + "#2" in identities
    assert "boardwise-rule:decap-required-caps:U11,pin:6,net:NET11" in identities
    assert "boardwise-rule:pcb-footprint-consistency:U1" in identities
    assert "boardwise-rule:some-info-rule:R7" in identities

    # Same input, same identities — the key is a function of the finding alone.
    assert cli._checkup_finding_identities(findings) == identities
    # The order of the input does not invent new identities.
    reversed_ids = cli._checkup_finding_identities(list(reversed(findings)))
    assert reversed_ids == identities


# ---------------------------------------------------------------------------
# B5 fix B: the run's own output, and the evidence a human keeps beside it
# ---------------------------------------------------------------------------


def _write_needs_sidecar(out: Path, *, reason: str) -> Path:
    """A `needs-datasheet.json` in the shape `boardwise need-datasheet` writes.

    The mark names a designator this board does not carry, so the run counts it
    `unmatched` and only prints a note — the sidecar's *bytes* are what this test
    is about, not a fold-in that would move findings around.
    """
    path = out / "needs-datasheet.json"
    path.write_text(
        json.dumps(
            {
                "schema": "boardwise.needs-datasheet/1",
                "marks": [
                    {"part": "U-nope", "pin": "", "reason": reason, "source": "reviewer"}
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_an_out_dir_inside_the_project_tree_does_not_hash_itself(tmp_path, capsys):
    """`--out` under the `.eprj3` folder: the run's report is not evidence.

    Before B5 fix B the tree digest counted `<out>/report.json` and `<out>/run.json`,
    so a project-relative `--out` made the baseline depend on the run that judged
    it and no second `--strict` invocation could ever be refused — "it always
    hashes itself". The exclusion is exactly `--out` and everything under it.
    """
    project = tmp_path / "proj"
    shutil.copytree(FIXTURES / "eprj3_synth", project)
    out = project / "out"

    before = cli._checkup_tree_digest(project, out)
    assert cli._cmd_checkup(_args(out, file=str(project))) == 3
    capsys.readouterr()

    # The run really did write its report **inside** the baselined tree…
    assert (out / "report.json").is_file()
    assert (out / "run.json").is_file()
    # …and it is invisible to the digest, while a scan *without* the exclusion does
    # see the new bytes: that difference is what the exclusion buys.
    assert cli._checkup_tree_digest(project, out) == before
    assert cli._checkup_tree_digest(project) != before

    assert cli._cmd_checkup(_args(out, file=str(project))) == 2
    assert "reject-use-existing" in capsys.readouterr().err
    assert _manifest(out)["drcReviewCount"] == 1, "a refusal freezes nothing"


def test_out_at_the_project_root_is_stable_across_runs(tmp_path, capsys):
    """`--out` **is** the folder project: skip the run's artifacts, not the project.

    Skipping the out subtree would skip the whole tree and fold every project to
    the empty digest, so at the root the run's own files are named instead
    (`_CHECKUP_OUT_ARTIFACT_NAMES`): the pages still count, the report does not,
    and the second `--strict` run is refused as it is anywhere else.
    """
    project = tmp_path / "proj"
    shutil.copytree(FIXTURES / "eprj3_synth", project)

    before = cli._checkup_tree_digest(project, project)
    assert before[0] > 0, "the project's own pages are still hashed"

    assert cli._cmd_checkup(_args(project, file=str(project))) == 3
    capsys.readouterr()
    landed = {path.name for path in project.iterdir() if path.is_file()}
    assert {"report.json", "run.json"} <= landed, f"the run wrote {sorted(landed)}"
    assert cli._checkup_tree_digest(project, project) == before

    assert cli._cmd_checkup(_args(project, file=str(project))) == 2
    assert "reject-use-existing" in capsys.readouterr().err


def test_a_new_edited_or_vanished_sidecar_moves_the_baseline(tmp_path, capsys):
    """`needs-datasheet.json` is evidence a human wrote — so it is in the baseline.

    The sidecar lives in `--out`, which the tree digest skips, and the guard used
    to ignore it entirely: a reviewer's newly added mark was refused as "the same
    evidence" and silently dropped (`reject-use-existing`). Appearing, changing and
    disappearing each move the baseline and open a run.
    """
    out = tmp_path / "out"
    assert cli._cmd_checkup(_args(out)) == 3
    first = _manifest(out)
    assert not [
        row
        for row in first["inputs"]
        if row["path"].endswith(("needs-datasheet.json", "warning-triage.json"))
    ], "no sidecar existed, so no sidecar row was invented"
    capsys.readouterr()

    # Appears: new evidence → a new run, not a refusal.
    _write_needs_sidecar(out, reason="first")
    assert cli._cmd_checkup(_args(out)) == 3
    second = _manifest(out)
    assert second["drcReviewCount"] == 2
    sidecar = str((out / "needs-datasheet.json").resolve()).replace("\\", "/")
    rows = {row["path"]: row for row in second["inputs"]}
    assert rows[sidecar]["sha256"] == sha256_file(out / "needs-datasheet.json")
    assert rows[sidecar]["bytes"] == (out / "needs-datasheet.json").stat().st_size
    capsys.readouterr()

    # Changes: new evidence again.
    _write_needs_sidecar(out, reason="second")
    assert cli._cmd_checkup(_args(out)) == 3
    third = _manifest(out)
    assert third["drcReviewCount"] == 3
    assert {row["path"]: row["sha256"] for row in third["inputs"]}[sidecar] == sha256_file(
        out / "needs-datasheet.json"
    )
    capsys.readouterr()

    # Disappears: the row goes with it (`renamed aside` is how an absent file is
    # produced here — the row is keyed by that exact name, so the baseline moves).
    deleted = cli._checkup_strict_baseline(_args(out), out)
    (out / "needs-datasheet.json").rename(out / "needs-datasheet.json.old")
    gone = cli._checkup_strict_baseline(_args(out), out)
    assert sidecar in {row["path"] for row in deleted["inputs"]}
    assert sidecar not in {row["path"] for row in gone["inputs"]}
    assert gone["inputs"] != deleted["inputs"]
    assert cli._cmd_checkup(_args(out)) == 3
    assert _manifest(out)["drcReviewCount"] == 4
    capsys.readouterr()


def test_the_same_bytes_at_a_new_path_are_the_same_baseline(tmp_path, capsys):
    """A copy is not new evidence: content decides, path does not (B5 fix B).

    The guard compared `inputs` rows whole, so copying the archive — or the shelf —
    to a second path changed only a `path` and passed as a new run; the
    `--new-evidence` declaration bypassed it the same way. Now the same bytes are
    the same baseline, and a *different* hash is still what opens a run.
    """
    first_copy = tmp_path / "a" / "proj.epro2"
    second_copy = tmp_path / "b" / "proj.epro2"
    first_copy.parent.mkdir()
    second_copy.parent.mkdir()
    shutil.copyfile(GOLDEN, first_copy)
    shutil.copyfile(GOLDEN, second_copy)
    out = tmp_path / "out"

    assert cli._cmd_checkup(_args(out, file=str(first_copy))) == 3
    first = _manifest(out)
    assert first["drcReviewCount"] == 1
    capsys.readouterr()

    # Same bytes, other path, nothing declared → the same baseline.
    assert cli._cmd_checkup(_args(out, file=str(second_copy))) == 2
    assert "reject-use-existing" in capsys.readouterr().err

    # Same bytes, other path, and the flag that used to be the way through: the
    # declaration is not believed, and the refusal names the baseline coming back
    # under another name rather than a false "the bytes changed".
    declared = _args(out, file=str(second_copy), new_evidence="archive-bytes-changed")
    assert cli._cmd_checkup(declared) == 2
    stderr = capsys.readouterr().err
    assert "reject-use-existing" in stderr
    assert _manifest(out)["drcReviewCount"] == 1, "no refusal wrote a baseline"
    assert not (out / "run-diff.json").exists()

    # Genuinely different bytes at that path: a new run, and the diff says so.
    shutil.copyfile(OTHER, second_copy)
    assert cli._cmd_checkup(_args(out, file=str(second_copy))) == 1
    second = _manifest(out)
    assert second["drcReviewCount"] == 2
    diff = json.loads((out / "run-diff.json").read_text(encoding="utf-8"))
    assert diff["sameBaseline"] is False
    capsys.readouterr()


def test_an_unwritable_manifest_names_run_manifest_unwritten(
    tmp_path, monkeypatch, capsys
):
    """The note carries one fixed token, and the delivered report keeps its code.

    The exception's text is host- and locale-shaped; an agent deciding "was a
    baseline frozen?" greps for a token, the way it greps the refusal codes. The
    exit code stays the review's own (3 here), because the report *was* delivered.
    """

    def boom(*_a, **_k):  # noqa: ANN002, ANN003 — a writer that must fail
        raise OSError("the disk said no")

    monkeypatch.setattr("boardwise.core.runmanifest.write_manifest", boom)
    out = tmp_path / "out"

    assert cli._cmd_checkup(_args(out)) == 3, "a manifest failure is not an exit code"
    assert (out / "report.json").is_file(), "the report is still delivered"
    stderr = capsys.readouterr().err
    assert "run-manifest-unwritten" in stderr
    assert not (out / "run.json").exists()


def test_the_lock_and_atomic_temporaries_are_not_project_files(tmp_path):
    """A lock carrier and an in-flight temp are run state, never evidence."""
    project = tmp_path / "proj"
    (project / "sch").mkdir(parents=True)
    (project / "sch" / "page.json").write_text("{}", encoding="utf-8")
    before = cli._checkup_tree_digest(project)

    (project / ".checkup.lock").write_text("holder", encoding="utf-8")
    (project / "sch" / ".run.json.abc123.tmp").write_text("half", encoding="utf-8")
    assert cli._checkup_tree_digest(project) == before

    # …while a real page still moves it: the skip is those two names, not everything.
    (project / "sch" / "page2.json").write_text("{}", encoding="utf-8")
    assert cli._checkup_tree_digest(project) != before
