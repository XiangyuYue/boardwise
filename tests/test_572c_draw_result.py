"""572C — the four findings of the 572-C hole batch, pinned as they now behave.

One test class per finding; each one fails against the code as it was at
`961b3b7` (the readings are quoted in the docstrings, taken by
`.tmp_572c/probe_before.py`).

572C-04 is **not** fixed here: its exit code is produced by
`cli.py:_render_draw_result`, which this batch may not touch. What is pinned
for it is the engine-side fact the CLI has to read — the persistence state of
each early return — with the measurements that show three of the four already
exit 3.
"""

from __future__ import annotations

import asyncio
import inspect
import io
import types

import pytest

from boardwise.core.compare import COMPONENT_LEVEL, ComparisonReport, Difference
from boardwise.engines import draw as draw_mod
from boardwise.engines.draw import (
    DrawResult,
    StepRecord,
    _save_project,
)
from boardwise.engines.generate import ActionPlan

ARGS = types.SimpleNamespace(spec=None, render=None, screenshot=None)


def _cli_exit(result: DrawResult) -> int:
    """The exit code `cli.py:_render_draw_result` returns for this result."""
    from boardwise.cli import _render_draw_result

    with io.StringIO() as buf, _redirect(buf):
        return _render_draw_result(result, ARGS)


class _redirect:
    def __init__(self, buf: io.StringIO) -> None:
        self._buf = buf

    def __enter__(self):
        import contextlib

        self._cm = contextlib.redirect_stdout(self._buf)
        return self._cm.__enter__()

    def __exit__(self, *exc):
        return self._cm.__exit__(*exc)


def _one_row(detail: str, golden: str, candidate: str) -> ComparisonReport:
    return ComparisonReport(
        component_differences=[
            Difference(COMPONENT_LEVEL, "U1", detail, golden, candidate)
        ]
    )


class _StubClient:
    def __init__(self, answer):
        self.answer = answer
        self.calls: list[tuple[str, dict]] = []

    async def call(self, action, params):
        self.calls.append((action, params))
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


def _save(answer) -> tuple[DrawResult, bool]:
    result = DrawResult(plan=ActionPlan())
    result.comparison = ComparisonReport()  # a compared, empty diff
    client = _StubClient(answer)
    ok = asyncio.run(_save_project(client, result, "save project"))
    return result, ok


def _save_rows(result: DrawResult) -> list[StepRecord]:
    return [r for r in result.records if r.action == "persistence.save"]


# --- 572C-02: the save is judged by the answer's `saved`, not by "it answered"


def test_save_answer_false_is_a_failure_not_a_success():
    """Before the fix: `{"saved": false}` → `save_ok=True`,
    `persistence=saved_unverified`, **zero** extra rows (probe_before P2)."""
    result, ok = _save({"saved": False})

    assert ok is False
    assert result.save_ok is False
    assert result.persistence != "saved_unverified", (
        "an editor that said saved:false is not a save the report may call ok"
    )
    rows = _save_rows(result)
    assert len(rows) == 1, "the refusal must be one named row, not silence"
    assert rows[0].ok is False
    assert "REFUSED" in rows[0].summary


def test_save_answer_false_keeps_the_editors_reason():
    result, ok = _save({"saved": False, "reason": "read-only project"})

    assert ok is False and result.save_ok is False
    assert "read-only project" in _save_rows(result)[0].detail


def test_save_answer_without_saved_is_unknown_not_success():
    """Before the fix: `{}` → `save_ok=True`, `saved_unverified`, zero rows."""
    for answer in ({}, {"ok": True}, {"saved": "true"}, {"saved": 1}):
        result, ok = _save(answer)
        assert ok is False, f"{answer!r} must not read as a successful save"
        assert result.save_ok is False
        assert result.persistence != "saved_unverified"
        rows = _save_rows(result)
        assert len(rows) == 1, f"{answer!r} must leave one named row"
        assert "did not give `saved`" in rows[0].summary, (
            f"{answer!r}: the row must name that the answer gave no saved — "
            f"got {rows[0].summary!r}"
        )
        assert "UNKNOWN" in rows[0].summary


def test_a_failed_save_call_stays_a_refusal():
    """No answer at all is a failed call, not a missing field: the connector
    refuses by throwing ("sch_Document.save() returned false"), so this row
    keeps saying the editor did NOT accept the save — the distinction the
    existing suite pins at `tests/test_candidate_draw.py:1076`."""
    from boardwise.bridge.protocol import BridgeError, ErrorCodes

    result, ok = _save(BridgeError(ErrorCodes.CONNECTOR_ERROR, "returned false"))

    assert ok is False and result.save_ok is False
    rows = _save_rows(result)
    assert len(rows) == 1
    assert rows[0].ok is False
    assert "did NOT accept a save" in rows[0].summary


def test_save_answer_true_is_still_a_success():
    result, ok = _save({"saved": True})

    assert ok is True
    assert result.save_ok is True
    assert result.persistence == "saved_unverified"
    assert _save_rows(result) == [], "a stated save needs no contradicting row"


# --- 572C-01: one verdict per report — `zero_diff` is derived from it


@pytest.mark.parametrize(
    "detail,golden,candidate",
    [
        ("value differs", "1kΩ", "2.2kΩ"),
        ("footprint differs", "0402", "0603"),
        ("lcsc differs", "C1", "C2"),
        ("component missing in candidate", "present", "absent"),
        ("component extra in candidate", "absent", "present"),
    ],
)
def test_zero_diff_agrees_with_the_report(detail, golden, candidate):
    """Before the fix: `value differs(1kΩ→2.2kΩ)` and `footprint differs
    (0402→0603)` gave `is_empty=False` **and** `zero_diff=True` — the exit code
    (1) and the "acceptance gate" (True) contradicted each other
    (probe_before P1)."""
    report = _one_row(detail, golden, candidate)
    result = DrawResult(plan=ActionPlan())
    result.comparison = report

    assert report.is_empty is False
    assert result.zero_diff is False, (
        f"{detail}: zero_diff must not call a real difference a pass"
    )
    assert result.zero_diff == report.is_empty
    assert _cli_exit(result) == 1, "the exit code is the report's verdict"


def test_zero_diff_agrees_on_an_empty_report():
    result = DrawResult(plan=ActionPlan())
    result.comparison = ComparisonReport()

    assert result.zero_diff is True
    assert result.zero_diff == result.comparison.is_empty
    assert _cli_exit(result) == 0


def test_zero_diff_is_false_when_no_comparison_ran():
    result = DrawResult(plan=ActionPlan())
    assert result.comparison is None
    assert result.zero_diff is False


def test_zero_diff_is_the_reports_verdict_everywhere():
    """The property is a derivation, not a second opinion: it must equal
    `report.is_empty` for every shape of the report, including a mixed one."""
    cases = [
        ComparisonReport(),
        _one_row("value differs", "1kΩ", "2.2kΩ"),
        _one_row("component extra in candidate", "absent", "present"),
        ComparisonReport(
            component_differences=[
                Difference(COMPONENT_LEVEL, "U1", "value differs", "1kΩ", "2.2kΩ")
            ],
            net_differences=[Difference("net", "GND", "net missing", "GND", "")],
        ),
    ]
    for report in cases:
        result = DrawResult(plan=ActionPlan())
        result.comparison = report
        assert result.zero_diff == report.is_empty


# --- 572C-03: the 2c junction block exists once


def test_junction_split_block_exists_once():
    """Before the fix: the whole block (comment, import and call) was pasted
    twice — probe_before P3 counted 2 imports and 2 calls."""
    source = inspect.getsource(draw_mod)

    assert source.count("from boardwise.engines.replay import split_at_junctions") == 1
    assert source.count("plan.wires, resplit = split_at_junctions(plan.wires)") == 1
    # The kept copy is an import: draw.py must not grow a second definition of
    # its own, which is how "keep one" could be satisfied while doubling the
    # geometry rule.
    assert source.count("def split_at_junctions") == 0
    from boardwise.engines import replay as replay_mod

    replay_source = inspect.getsource(replay_mod)
    assert replay_source.count("def split_at_junctions") == 1, (
        "the one definition lives in engines.replay"
    )


def test_junction_split_still_runs_on_the_snapped_plan():
    """Removing the duplicate must not remove the pass itself."""
    source = inspect.getsource(draw_mod)
    body = source[source.index("plan.wires, resplit = split_at_junctions(plan.wires)") :]
    assert '"plan.split_junctions"' in body[:800], (
        "the surviving call still records its own row"
    )


# --- 572C-04: what the engine hands the CLI at each early return


@pytest.mark.parametrize(
    "records,expected",
    [
        ([], "not_placed"),
        (
            [StepRecord("sch.pcblib.place_component", "place U1", True, wrote=True)],
            "unknown",
        ),
        (
            [StepRecord("sch.pcblib.place_component", "place U1", False, wrote=True)],
            "not_placed",
        ),
        (
            [StepRecord("sch.wire.create", "wire", True, wrote=True)],
            "unknown",
        ),
        (
            [
                StepRecord(
                    "sch.doc.save", "save", False, wrote=True, timed_out=True
                )
            ],
            "unknown",
        ),
    ],
)
def test_early_return_persistence_is_the_state_cli_reads(records, expected):
    """`comparison is None` at all four early returns; what varies is whether a
    write was acknowledged. Measured at `961b3b7` (probe_before P4): the three
    that placed parts already reach `unknown` → cli exit 3; the one that wrote
    nothing stays `not_placed` → cli exit 1, although `docs/draw.md:658-661`
    calls that case 2 ("nothing was executed"). The exit code is
    `cli.py`'s to change; this pins the engine-side input to it."""
    result = DrawResult(plan=ActionPlan())
    result.records = list(records)
    assert result.comparison is None
    assert result.zero_diff is False
    assert result.persistence == expected
