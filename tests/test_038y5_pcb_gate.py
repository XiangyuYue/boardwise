"""038Y5: `boardwise pcb gate` — read-only orchestration, three exits, no writes.

Two consumption faces, both from fakes and neither from a daemon:

* :func:`boardwise.pcb_gate.run_gate` — the synchronous judge, driven with a fake
  ``call``/``checkup_runner``; every negative control in the task book is pinned
  here (DRC not run / truncated / boolean / red, ``incomplete`` checkup, ERROR,
  ``complete-with-open-items``, each coverage gap, a missing report, a
  contradictory exit code, a stale ``--out``, a non-PCB focus, a hint mismatch);
* :func:`boardwise.pcb_gate.run_cli_gate` — the CLI adapter: the real `pcb gate`
  parser, the real `checkup` argument namespace, one short bridge connection per
  action, and the same project/instance/port handed to the checkup step.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import boardwise.cli as cli
from boardwise import pcb_gate
from boardwise.commands import assembly as assembly_commands

ROOT = Path(__file__).resolve().parents[1]
GATE_SOURCE = ROOT / "src" / "boardwise" / "pcb_gate.py"

GREEN = pcb_gate.GREEN
RED = pcb_gate.RED
INCOMPLETE = pcb_gate.INCOMPLETE


# ---------------------------------------------------------------------------
# Fakes: the two readings the gate is allowed to touch
# ---------------------------------------------------------------------------
def _listing(
    *,
    active_type: str = "pcb",
    active_uuid: str = "pcb-1",
    active_name: str = "main",
    project: tuple[str, str, str] | None = ("proj-1", "test", "/test"),
    instance: str = "",
    documents: list[dict] | None = None,
) -> dict:
    """A `doc.list` answer: `active` plus (optionally) the focused project row."""
    active: dict = {"uuid": active_uuid, "type": active_type, "name": active_name}
    if instance:
        active["instance"] = instance
    out: dict = {
        "documents": documents
        if documents is not None
        else [{"uuid": "page-1", "type": "page", "name": "main"},
              {"uuid": "pcb-1", "type": "pcb", "name": "main"}],
        "active": active,
        "schematicPages": 1,
        "pcbs": 1,
        "count": 2,
    }
    if project is not None:
        uuid, name, friendly = project
        out["projects"] = [{
            "projectUuid": uuid, "uuid": uuid, "name": name,
            "friendlyName": friendly, "focused": True, "opened": "yes",
        }]
    return out


def _drc(
    errors: int = 0,
    *,
    checked: bool = True,
    available: bool = True,
    truncated: bool = False,
    mode: str = "groups",
    counts: bool = True,
    items: int = 2,
) -> dict:
    """A `pcb.drc_check` answer (025's shape, trimmed to what the gate reads)."""
    payload: dict = {
        "source": "pcb_Drc.check",
        "checked": checked,
        "available": available,
        "mode": mode,
        "truncated": truncated,
        "elapsedMs": 12,
    }
    if counts:
        payload["counts"] = {
            "groups": 1, "returnedGroups": 1, "errors": errors,
            "errorsSource": "host", "items": items, "byLabel": {}, "jsonChars": 40,
        }
    else:
        payload["counts"] = None
    return payload


def _coverage(**over: object) -> dict:
    base: dict = {
        "modelEmpty": False, "parseIncomplete": False, "boardsEmpty": 0,
        "boardsEmptyNames": [], "pagesDropped": 0, "rulesRefused": 0,
        "recordsDropped": 0, "rulesErrored": [], "pcbReviewMissing": False,
    }
    base.update(over)
    return base


def _report(
    verdict: str = "complete",
    exit_code: int = 0,
    *,
    coverage: dict | None = None,
    error_count: int = 0,
    conclusion: str = "无 ERROR",
) -> dict:
    """A checkup `report.json` — the five verdict fields the gate reads."""
    cov = _coverage() if coverage is None else coverage
    return {
        "schema": "boardwise.checkup-report/1",
        "summary": {
            "exitCode": exit_code,
            "errorCount": error_count,
            "infoCount": 0,
            "warnCount": 0,
            "errors": [],
            "conclusion": conclusion,
            "countsIncomplete": False,
        },
        "conclusion": {
            "verdict": verdict,
            "exitCode": exit_code,
            "mayClaimPassed": verdict == "complete",
            "mayQuotePassed": verdict == "complete",
            "oneLiner": conclusion,
            "blockers": [],
        },
        "completion": {"verdict": verdict, "verdictWhy": [], "coverage": cov, "errors": 0},
        "drc": {"pcb": {"checked": True, "totals": {"leafs": 0}}},
        # A real report always carries this section; the gate refuses to read a
        # report that cannot state it (see the findings negative controls).
        "findings": [],
    }


def _finding(severity: str = "ERROR", rule_id: str = "pcb-silk-under-body") -> dict:
    return {"rule_id": rule_id, "severity": severity, "level": "error", "message": "x"}


class FakeCall:
    """``call(action, params)`` — records every action the gate asks for."""

    def __init__(self, listing: object = None, drc: object = None, *, boom: str = "") -> None:
        self.listing = _listing() if listing is None else listing
        self.drc = _drc() if drc is None else drc
        self.boom = boom
        self.log: list[tuple[str, dict]] = []

    def __call__(self, action: str, params: dict) -> object:
        self.log.append((action, dict(params)))
        if self.boom:
            raise RuntimeError(self.boom)
        if action == pcb_gate.DOC_LIST_ACTION:
            return self.listing
        if action == pcb_gate.DRC_ACTION:
            return self.drc
        raise AssertionError(f"the gate asked for an action it must not use: {action}")

    @property
    def actions(self) -> list[str]:
        return [action for action, _ in self.log]


_DEFAULT_REPORT = object()


class FakeRunner:
    """``checkup_runner(out_dir) -> (report, exit_code)``, and nothing else.

    ``report=None`` is a real value here — "checkup wrote no report.json" — so the
    "use the default clean report" case is spelled with a sentinel instead.
    """

    def __init__(self, report: object = _DEFAULT_REPORT, exit_code: int = 0,
                 *, boom: str = "") -> None:
        self.report = _report() if report is _DEFAULT_REPORT else report
        self.exit_code = exit_code
        self.boom = boom
        self.dirs: list[Path] = []
        self.existed: list[bool] = []

    def __call__(self, out_dir: Path) -> tuple[object, int]:
        self.existed.append(Path(out_dir).exists())
        self.dirs.append(Path(out_dir))
        if self.boom:
            raise RuntimeError(self.boom)
        return self.report, self.exit_code


def _gate(tmp_path: Path, call: FakeCall, runner: FakeRunner, name: str = "gate", **kwargs):
    out = tmp_path / name
    report = pcb_gate.run_gate(call, runner, out, **kwargs)
    return report, out


def _written(out: Path) -> dict:
    return json.loads((out / pcb_gate.GATE_REPORT).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The GREEN path, and what it is allowed to say
# ---------------------------------------------------------------------------
def test_green_asks_the_declared_drc_and_a_fresh_checkup(tmp_path: Path) -> None:
    call, runner = FakeCall(), FakeRunner()
    report, out = _gate(tmp_path, call, runner)

    assert report.verdict == GREEN, report.reason
    assert report.exit_code == 0
    # The two reads, in order, and the DRC asked the way the review asks it.
    assert call.actions == [pcb_gate.DOC_LIST_ACTION, pcb_gate.DRC_ACTION]
    assert call.log[1][1] == {
        "strict": True, "userInterface": False, "includeVerboseError": True,
    }
    # The checkup gets its own directory **inside** the new `--out`, and it did
    # not exist when it was handed over, so there is nothing in there to reuse.
    assert runner.dirs == [out / pcb_gate.CHECKUP_DIR]
    assert runner.existed == [False]
    written = _written(out)
    assert written["schema"] == "boardwise.pcb-gate/1"
    assert (written["verdict"], written["exitCode"]) == (GREEN, 0)
    assert written["drc"]["errors"] == 0
    assert written["checkup"]["verdict"] == "complete"
    assert written["identity"]["board"]["uuid"] == "pcb-1"
    assert written["identity"]["project"]["uuid"] == "proj-1"


def test_the_written_report_is_a_summary_not_a_copy(tmp_path: Path) -> None:
    call = FakeCall(drc=_drc(errors=0, items=7))
    report, out = _gate(tmp_path, call, FakeRunner())
    written = _written(out)
    assert written["drc"]["items"] == 7
    # No group tree, no findings list, no raw payload: the detail lives in the
    # checkup report beside it.
    text = json.dumps(written)
    for forbidden in ("groups", "findings", "byLabel", "unreviewed_parts", "raw"):
        assert f'"{forbidden}"' not in text, forbidden


def test_complete_with_open_items_is_green_and_disclosed(tmp_path: Path) -> None:
    runner = FakeRunner(_report("complete-with-open-items", 0,
                                conclusion="无 ERROR；2 条 warning 待分诊"), 0)
    report, out = _gate(tmp_path, FakeCall(), runner)
    assert (report.verdict, report.exit_code) == (GREEN, 0), report.reason
    written = _written(out)
    assert written["checkup"]["verdict"] == "complete-with-open-items"
    assert "待分诊" in written["checkup"]["conclusion"]


# ---------------------------------------------------------------------------
# The host DRC: unstated is not zero, and red is a conclusion
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("drc", "needle"),
    [
        pytest.param(_drc(checked=False, available=False, counts=False),
                     "did not run", id="drc-not-run"),
        pytest.param(_drc(truncated=True), "truncated", id="drc-truncated"),
        pytest.param(_drc(mode="boolean", counts=False), "no counts", id="drc-boolean"),
        pytest.param(_drc(available=False), "not available", id="drc-unavailable"),
        pytest.param({**_drc(), "counts": {"items": 2}}, "no error count",
                     id="drc-count-missing"),
        pytest.param("passed", "not the declared object", id="drc-not-an-object"),
    ],
)
def test_a_drc_that_cannot_be_stated_is_incomplete(
    tmp_path: Path, drc: object, needle: str
) -> None:
    call, runner = FakeCall(drc=drc), FakeRunner()
    report, out = _gate(tmp_path, call, runner)
    assert report.verdict == INCOMPLETE, report.reason
    assert report.exit_code == 3
    assert needle in report.reason
    # No conclusion from the DRC step means no checkup is spent on it.
    assert runner.dirs == []
    assert call.actions == [pcb_gate.DOC_LIST_ACTION, pcb_gate.DRC_ACTION]
    assert _written(out)["checkup"]["ran"] is False


def test_a_red_host_drc_is_red_at_exit_2_and_skips_the_checkup(tmp_path: Path) -> None:
    call, runner = FakeCall(drc=_drc(errors=2)), FakeRunner()
    report, out = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (RED, 2), report.reason
    assert report.drc["errors"] == 2
    assert runner.dirs == []
    assert _written(out)["checkup"]["ran"] is False


def test_a_drc_that_raises_is_incomplete_not_red(tmp_path: Path) -> None:
    call, runner = FakeCall(boom="daemon went away"), FakeRunner()
    report, _ = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3)
    assert runner.dirs == []


# ---------------------------------------------------------------------------
# The checkup verdict: incomplete outranks ERROR
# ---------------------------------------------------------------------------
def test_an_incomplete_checkup_is_never_green_even_with_no_error(tmp_path: Path) -> None:
    report_in = _report("incomplete", 3, error_count=0, conclusion="7 颗器件缺手册未审")
    report_in["completion"]["verdictWhy"] = ["7 颗器件缺手册未审"]
    call, runner = FakeCall(), FakeRunner(report_in, 3)
    report, out = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason
    assert report.reason
    assert report.checkup["verdict"] == "incomplete"
    assert report.checkup["exitCode"] == 3
    written = _written(out)
    assert written["checkup"]["ran"] is True
    assert written["checkup"]["verdict"] == "incomplete"


def test_an_incomplete_verdict_outranks_a_zero_exit(tmp_path: Path) -> None:
    """The pre-research defect: `incomplete` beside exit 0 used to read as GREEN."""
    report_in = _report("incomplete", 0, error_count=0)
    report_in["completion"]["verdictWhy"] = ["3 颗器件缺手册未审"]
    call, runner = FakeCall(), FakeRunner(report_in, 0)
    report, _ = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason
    assert "`incomplete`" in report.reason
    assert "缺手册" in report.reason


def test_an_error_is_red_at_exit_2(tmp_path: Path) -> None:
    call, runner = FakeCall(), FakeRunner(_report("complete", 1, error_count=3), 1)
    report, _ = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (RED, 2), report.reason
    assert "ERROR" in report.reason


def test_error_count_alone_is_red_even_if_the_exit_says_zero(tmp_path: Path) -> None:
    call, runner = FakeCall(), FakeRunner(_report("complete", 0, error_count=2), 0)
    report, _ = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (RED, 2), report.reason


@pytest.mark.parametrize(
    "coverage",
    [
        pytest.param({"modelEmpty": True}, id="model-empty"),
        pytest.param({"parseIncomplete": True}, id="parse-incomplete"),
        pytest.param({"rulesErrored": ["pcb-silk-under-body"]}, id="rules-errored"),
        pytest.param({"recordsDropped": 4}, id="records-dropped"),
        pytest.param({"pcbReviewMissing": True}, id="pcb-review-missing"),
        # 038Y5 main-review: these three are gaps too — a `complete` verdict beside
        # them used to read as GREEN.
        pytest.param({"rulesRefused": 2}, id="rules-refused"),
        pytest.param({"pagesDropped": 1}, id="pages-dropped"),
        pytest.param({"boardsEmpty": 1, "boardsEmptyNames": ["main"]}, id="boards-empty"),
    ],
)
def test_a_declared_coverage_gap_is_incomplete(
    tmp_path: Path, coverage: dict
) -> None:
    call, runner = FakeCall(), FakeRunner(_report("complete", 0, coverage=_coverage(**coverage)), 0)
    report, _ = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason
    assert report.checkup["coverageGaps"] == [
        name for name in pcb_gate.COVERAGE_GAPS if coverage.get(name)
    ]
    assert next(iter(coverage)) in report.reason


@pytest.mark.parametrize(
    ("report_in", "exit_code", "needle"),
    [
        pytest.param(None, 0, "no report.json", id="report-missing"),
        pytest.param(_report("complete", 1), 0, "declares exitCode 1", id="exit-contradiction"),
        pytest.param(_report("complete", 0), 3, "exited 3", id="exit-3"),
        pytest.param(_report("complete", 2), 2, "exited 2", id="exit-2"),
        pytest.param(_report("we-are-fine", 0), 0, "does not know", id="unknown-verdict"),
        pytest.param({"summary": {"exitCode": 0}}, 0, "does not know", id="no-verdict"),
        pytest.param({"completion": {"verdict": "complete"}}, 0, "no exit code",
                     id="no-declared-exit"),
        pytest.param({"summary": {"exitCode": 0, "errorCount": 0},
                      "completion": {"verdict": "complete"}}, 0,
                     "missing coverage", id="no-coverage-section"),
    ],
)
def test_a_report_that_contradicts_itself_is_incomplete(
    tmp_path: Path, report_in: object, exit_code: int, needle: str
) -> None:
    call, runner = FakeCall(), FakeRunner(report_in, exit_code)
    report, _ = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason
    assert needle in report.reason, report.reason


def test_a_conflicting_verdict_pair_is_incomplete(tmp_path: Path) -> None:
    """`completion: complete` beside `conclusion: incomplete` used to be GREEN."""
    report_in = _report("complete", 0, error_count=0)
    report_in["conclusion"]["verdict"] = "incomplete"
    call, runner = FakeCall(), FakeRunner(report_in, 0)
    report, _ = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason
    assert "two verdicts" in report.reason


def test_an_incomplete_conclusion_beside_a_complete_completion_is_incomplete(
    tmp_path: Path,
) -> None:
    report_in = _report("incomplete", 0, error_count=0)
    report_in["conclusion"]["verdict"] = "complete"
    call, runner = FakeCall(), FakeRunner(report_in, 0)
    report, _ = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason


@pytest.mark.parametrize(
    "section",
    [
        pytest.param("completion", id="completion-only"),
        pytest.param("conclusion", id="conclusion-only"),
    ],
)
def test_one_verdict_section_alone_is_still_read(tmp_path: Path, section: str) -> None:
    report_in = _report("complete", 0)
    other = "conclusion" if section == "completion" else "completion"
    report_in[other].pop("verdict")
    call, runner = FakeCall(), FakeRunner(report_in, 0)
    report, out = _gate(tmp_path, call, runner, name=f"gate-{section}")
    assert (report.verdict, report.exit_code) == (GREEN, 0), report.reason
    assert _written(out)["checkup"]["verdict"] == "complete"


@pytest.mark.parametrize(
    "findings",
    [
        pytest.param(None, id="absent"),
        pytest.param({"ERROR": 3}, id="object"),
        pytest.param("none", id="string"),
    ],
)
def test_unreadable_findings_are_incomplete_not_zero(
    tmp_path: Path, findings: object
) -> None:
    report_in = _report("complete", 0, error_count=0)
    if findings is None:
        report_in.pop("findings")
    else:
        report_in["findings"] = findings
    call, runner = FakeCall(), FakeRunner(report_in, 0)
    report, _ = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason
    assert "findings section" in report.reason


def test_an_error_finding_is_red_even_at_exit_0_with_no_counts(tmp_path: Path) -> None:
    """The count-based reading used to miss this: exit 0, no counts, one ERROR row."""
    report_in = _report("complete", 0, error_count=0)
    report_in["findings"] = [_finding("INFO"), _finding("ERROR")]
    report_in["summary"].pop("errorCount")
    call, runner = FakeCall(), FakeRunner(report_in, 0)
    report, out = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (RED, 2), report.reason
    assert "1 ERROR finding" in report.reason
    assert _written(out)["checkup"]["errorFindings"] == 1


def test_completion_errors_alone_is_red(tmp_path: Path) -> None:
    """`completion.errors` is a count too — 3 there with exit 0 is still RED."""
    report_in = _report("complete", 0, error_count=0)
    report_in["completion"]["errors"] = 3
    call, runner = FakeCall(), FakeRunner(report_in, 0)
    report, _ = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (RED, 2), report.reason
    assert "completion.errors=3" in report.reason


def test_a_missing_error_count_no_longer_hides_error_findings(tmp_path: Path) -> None:
    report_in = _report("complete", 0)
    report_in["summary"].pop("errorCount")
    report_in["findings"] = [_finding("ERROR")]
    call, runner = FakeCall(), FakeRunner(report_in, 0)
    report, _ = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (RED, 2), report.reason


def test_a_checkup_that_raises_is_incomplete(tmp_path: Path) -> None:
    call, runner = FakeCall(), FakeRunner(boom="checkup crashed")
    report, out = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3)
    assert "checkup" in report.reason
    assert _written(out)["checkup"]["ran"] is False


# ---------------------------------------------------------------------------
# Identity and focus: the gate never switches documents
# ---------------------------------------------------------------------------
def test_a_non_pcb_focus_is_refused_and_no_board_is_borrowed(tmp_path: Path) -> None:
    listing = _listing(
        active_type="page", active_uuid="page-1",
        documents=[{"uuid": "page-1", "type": "page", "name": "main"},
                   {"uuid": "pcb-1", "type": "pcb", "name": "main"},
                   {"uuid": "pcb-2", "type": "pcb", "name": "second"}],
    )
    call, runner = FakeCall(listing=listing), FakeRunner()
    report, out = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason
    assert "not a PCB" in report.reason
    # Zero DRC: no boards[0] / documents[0] fallback, and no doc.open to reach one.
    assert call.actions == [pcb_gate.DOC_LIST_ACTION]
    assert runner.dirs == []
    assert "board" not in json.loads((out / pcb_gate.GATE_REPORT).read_text("utf-8"))["identity"]


def test_an_empty_focus_is_refused(tmp_path: Path) -> None:
    listing = _listing(active_type="", active_uuid="")
    call, runner = FakeCall(listing=listing), FakeRunner()
    report, _ = _gate(tmp_path, call, runner)
    assert report.verdict == INCOMPLETE
    assert call.actions == [pcb_gate.DOC_LIST_ACTION]


def test_a_project_hint_mismatch_is_refused_before_any_drc(tmp_path: Path) -> None:
    call, runner = FakeCall(), FakeRunner()
    report, _ = _gate(tmp_path, call, runner, project="another-project")
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason
    assert "does not match the project" in report.reason
    assert call.actions == [pcb_gate.DOC_LIST_ACTION]
    assert runner.dirs == []


@pytest.mark.parametrize("hint", ["proj-1", "test", "/test"])
def test_a_matching_project_hint_keeps_the_gate_going(tmp_path: Path, hint: str) -> None:
    call, runner = FakeCall(), FakeRunner()
    report, _ = _gate(tmp_path, call, runner, name=f"gate-{hint.strip('/')}", project=hint)
    assert report.verdict == GREEN, report.reason
    assert report.identity["project"]["uuid"] == "proj-1"


def test_an_instance_hint_mismatch_is_refused_before_any_drc(tmp_path: Path) -> None:
    call, runner = FakeCall(listing=_listing(instance="win-7")), FakeRunner()
    report, _ = _gate(tmp_path, call, runner, instance="win-9")
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason
    assert "window" in report.reason
    assert call.actions == [pcb_gate.DOC_LIST_ACTION]


def test_an_unprovable_project_needs_an_explicit_instance(tmp_path: Path) -> None:
    listing = _listing(project=None)
    call, runner = FakeCall(listing=listing), FakeRunner()
    report, _ = _gate(tmp_path, call, runner, name="no-identity")
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason
    assert "no --instance" in report.reason
    assert call.actions == [pcb_gate.DOC_LIST_ACTION]

    call2, runner2 = FakeCall(listing=listing), FakeRunner()
    report2, _ = _gate(tmp_path, call2, runner2, name="with-instance", instance="win-3")
    assert report2.verdict == GREEN, report2.reason
    assert report2.identity["instance"] == "win-3"
    assert report2.identity["project"] == {}


def test_doc_list_failure_is_incomplete(tmp_path: Path) -> None:
    call, runner = FakeCall(boom="daemon not reachable"), FakeRunner()
    report, _ = _gate(tmp_path, call, runner)
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason
    assert "doc.list" in report.reason
    assert runner.dirs == []


# ---------------------------------------------------------------------------
# The output directory: new, or nothing
# ---------------------------------------------------------------------------
def test_an_existing_out_is_refused_before_anything_is_read(tmp_path: Path) -> None:
    out = tmp_path / "used"
    out.mkdir()
    (out / "report.json").write_text(json.dumps({"stale": True}), encoding="utf-8")
    call, runner = FakeCall(), FakeRunner()
    report = pcb_gate.run_gate(call, runner, out)
    assert (report.verdict, report.exit_code) == (INCOMPLETE, 3), report.reason
    assert "already exists" in report.reason
    # No bridge action, no checkup, and not one byte written into that directory.
    assert call.log == []
    assert runner.dirs == []
    assert sorted(path.name for path in out.iterdir()) == ["report.json"]
    assert json.loads((out / "report.json").read_text("utf-8")) == {"stale": True}


def test_a_second_run_on_the_same_out_is_refused_and_reuses_nothing(tmp_path: Path) -> None:
    call, runner = FakeCall(), FakeRunner()
    first, out = _gate(tmp_path, call, runner)
    assert first.verdict == GREEN
    before = (out / pcb_gate.GATE_REPORT).read_bytes()

    second = pcb_gate.run_gate(FakeCall(), runner, out)
    assert (second.verdict, second.exit_code) == (INCOMPLETE, 3), second.reason
    assert "already exists" in second.reason
    assert len(runner.dirs) == 1  # the second run never reached the checkup
    assert (out / pcb_gate.GATE_REPORT).read_bytes() == before


# ---------------------------------------------------------------------------
# The CLI adapter: one short connection per action, the real checkup namespace
# ---------------------------------------------------------------------------
class FakeConnection:
    def __init__(self, owner: "FakeBridge", uri: str, token: str, role: str, client: str) -> None:
        self.owner, self.uri, self.token, self.role, self.client = owner, uri, token, role, client
        self.calls: list[dict] = []
        self.closed = False

    async def call(self, action, params=None, *, id=None, target_project=None,
                   target_instance=None):
        self.calls.append({
            "action": action, "params": dict(params or {}),
            "target_project": target_project, "target_instance": target_instance,
        })
        self.owner.actions.append(action)
        if action == pcb_gate.DOC_LIST_ACTION:
            return self.owner.listing
        if action == pcb_gate.DRC_ACTION:
            return self.owner.drc
        raise AssertionError(f"the adapter used an action the gate must not use: {action}")

    async def close(self) -> None:
        self.closed = True


class FakeBridge:
    """Stands in for ``cli._open_cli`` + ``BridgeClient``: one connection per action."""

    def __init__(self, listing: dict | None = None, drc: dict | None = None) -> None:
        self.listing = _listing() if listing is None else listing
        self.drc = _drc() if drc is None else drc
        self.opened: list[FakeConnection] = []
        self.actions: list[str] = []
        self.ports: list[int | None] = []

    def opener(self, args):
        self.ports.append(getattr(args, "port", None))
        return (self._client_class(), None, getattr(args, "port", None) or 61190, "tok-1")

    def _client_class(self):
        owner = self

        class Client:
            @classmethod
            async def open(cls, uri, token, role, client=""):
                connection = FakeConnection(owner, uri, token, role, client)
                owner.opened.append(connection)
                return connection

        return Client


def _fake_checkup(report: dict | None, exit_code: int, *, write: bool = True):
    """``cli._cmd_checkup`` stand-in: writes this run's report into ``--out``."""
    seen: list = []

    def run(namespace) -> int:
        seen.append(namespace)
        if write and report is not None:
            out = Path(namespace.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / "report.json").write_text(
                json.dumps(report, ensure_ascii=False), encoding="utf-8"
            )
        return exit_code

    run.seen = seen  # type: ignore[attr-defined]
    return run


def test_the_cli_parser_names_every_flag_and_offers_no_way_past_the_checkup() -> None:
    args = cli.build_parser().parse_args(
        ["pcb", "gate", "--out", "gate-out", "--project", "test",
         "--instance", "win-1", "--port", "61200"]
    )
    assert (args.command, args.pcb_command, args.out) == ("pcb", "gate", "gate-out")
    assert (args.project, args.instance, args.port) == ("test", "win-1", 61200)
    # The pre-research gate's three escape hatches are gone on purpose: there is
    # no way to skip the checkup, no autofix and no save.
    assert not hasattr(args, "skip_checkup")
    assert not hasattr(args, "autofix")
    assert not hasattr(args, "save")
    with pytest.raises(SystemExit) as excinfo:
        cli.build_parser().parse_args(["pcb", "gate", "--skip-checkup", "--out", "x"])
    assert excinfo.value.code == 2


def test_the_cli_adapter_passes_the_same_project_instance_and_port_to_checkup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "gate"
    bridge = FakeBridge()
    checkup = _fake_checkup(_report(), 0)
    args = cli.build_parser().parse_args(
        ["pcb", "gate", "--out", str(out), "--project", "test",
         "--instance", "win-1", "--port", "61200"]
    )
    code = pcb_gate.run_cli_gate(
        args,
        checkup=checkup,
        bridge=bridge.opener,
    )
    assert code == 0
    assert bridge.actions == [pcb_gate.DOC_LIST_ACTION, pcb_gate.DRC_ACTION]
    # One short connection per action, each its own handshake and each closed.
    assert len(bridge.opened) == 2
    assert all(connection.closed for connection in bridge.opened)
    assert {connection.uri for connection in bridge.opened} == {"ws://127.0.0.1:61200/eda"}
    assert all(
        (call["target_project"], call["target_instance"]) == ("test", "win-1")
        for connection in bridge.opened for call in connection.calls
    )
    # The checkup is the real command's namespace, on <out>/checkup, same routing.
    assert len(checkup.seen) == 1  # type: ignore[attr-defined]
    namespace = checkup.seen[0]  # type: ignore[attr-defined]
    assert namespace.command == "checkup"
    assert Path(namespace.out) == out / pcb_gate.CHECKUP_DIR
    assert (namespace.project, namespace.instance, namespace.port) == ("test", "win-1", 61200)
    assert (namespace.file, namespace.strict, namespace.interconnect) == ("", False, None)
    printed = capsys.readouterr().out
    assert "verdict: GREEN (exit 0)" in printed
    assert "checkup: exit 0 / verdict complete" in printed
    assert _written(out)["checkup"]["out"] == str(out / pcb_gate.CHECKUP_DIR)


def test_the_cli_adapter_reads_only_the_report_this_run_wrote(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "gate"
    bridge = FakeBridge()
    checkup = _fake_checkup(_report(), 0, write=False)
    args = cli.build_parser().parse_args(["pcb", "gate", "--out", str(out)])
    code = pcb_gate.run_cli_gate(
        args, checkup=checkup, bridge=bridge.opener
    )
    assert code == 3
    printed = capsys.readouterr()
    assert "no report.json" in printed.err
    assert _written(out)["checkup"]["ran"] is True


def test_the_cli_adapter_refuses_a_used_out_before_the_daemon_or_the_checkup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "gate"
    out.mkdir()
    bridge = FakeBridge()
    checkup = _fake_checkup(_report(), 0)
    args = cli.build_parser().parse_args(["pcb", "gate", "--out", str(out)])
    code = pcb_gate.run_cli_gate(
        args, checkup=checkup, bridge=bridge.opener
    )
    assert code == 3
    assert bridge.opened == []
    assert bridge.ports == []
    assert checkup.seen == []  # type: ignore[attr-defined]
    assert "already exists" in capsys.readouterr().err


def test_main_routes_pcb_to_the_assembly_owned_adapter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list = []

    def dispatch(args, checkup, bridge):
        seen.append((args.command, args.pcb_command, args.out, callable(checkup), callable(bridge)))
        return 7

    monkeypatch.setattr(assembly_commands, "dispatch_pcb_gate", dispatch)
    assert cli.main(["pcb", "gate", "--out", str(tmp_path / "route")]) == 7
    assert seen == [("pcb", "gate", str(tmp_path / "route"), True, True)]


# ---------------------------------------------------------------------------
# Contract and ownership anchors
# ---------------------------------------------------------------------------
def test_the_contract_pins_the_three_exit_codes() -> None:
    contract = json.loads(
        (ROOT / "contracts" / "cli" / "v1.json").read_text(encoding="utf-8")
    )
    assert contract["exitCodes"]["commands"]["pcb"] == [0, 2, 3]
    assert contract["exitCodes"]["subcommands"]["pcb.gate"] == [0, 2, 3]
    choices = next(
        action["choices"] for action in contract["parser"]["actions"]
        if isinstance(action["choices"], dict)
    )
    gate = choices["pcb"]["actions"][-1]["choices"]["gate"]
    flags = [option for action in gate["actions"] for option in action["optionStrings"]]
    assert flags == ["-h", "--help", "--out", "--project", "--instance", "--port"]


def test_the_gate_module_is_assembly_owned_and_imports_no_cli() -> None:
    owners = json.loads(
        (ROOT / "contracts" / "module-owners.json").read_text(encoding="utf-8")
    )
    assert owners["modules"]["pcb_gate.py"] == "assembly"

    tree = ast.parse(GATE_SOURCE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add("." * (node.level or 0) + (node.module or ""))
    # `checkup` and the bridge opener are handed in by assembly; importing cli.py
    # back into the module would be the reverse edge commands/*.py must not grow.
    assert not [name for name in imported if name.rstrip(".").endswith("cli")], imported
    assert imported <= {
        "__future__", "argparse", "asyncio", "json", "collections.abc", "dataclasses",
        "pathlib", "sys", "typing", ".commands", ".bridge", ".bridge.client",
    }, sorted(imported - {
        "__future__", "argparse", "asyncio", "json", "collections.abc", "dataclasses",
        "pathlib", "sys", "typing", ".commands", ".bridge", ".bridge.client",
    })


def test_the_gate_can_only_reach_the_two_read_actions(tmp_path: Path) -> None:
    """A whole run logs exactly `doc.list` + `pcb.drc_check` — no write action."""
    call = FakeCall()
    report, _ = _gate(tmp_path, call, FakeRunner())
    assert report.verdict == GREEN
    assert call.actions == [pcb_gate.DOC_LIST_ACTION, pcb_gate.DRC_ACTION]
    assert set(call.actions) == {pcb_gate.DOC_LIST_ACTION, pcb_gate.DRC_ACTION}
    for write_action in ("doc.open", "doc.save", "pcb.move_attribute", "pcb.save"):
        assert write_action not in call.actions
