"""038R2: 宿主 PCB DRC 没跑，PCB 工程不得读成 `complete`。

缺口（任务书 038r2）：离线 `--file` 的 `drc.pcb` 段是
``{checked:false, source:offline-not-available, reason}``——一段**没查**的记录，
`drc.summarise` 不伪造计数、不加 ERROR（这是必须保留的正确行为）。但
`completion.coverage` 里没有这一项，于是其余闸全清时报告可以给出
``verdict=complete`` + ``conclusion.mayQuotePassed=true`` +「可以投板」。
自有规则没有新增 clearance finding，并不等于宿主 DRC 通过。

裁定（038r2 主代理）：**complete-with-open-items，不是 incomplete**；
无其他 ERROR 时 `summary.exitCode` 仍为 0；`mayQuotePassed=false`；
整板结论不得写「可以投板」；`checked=false` 不得被改写成 ERROR 或 Finding。

本文件钉的六件事，全部用**纯 fake 的 coverage/completion 读数**或现有公开夹具，
不连编辑器、不碰 daemon：

* **杀手测试**：coverage 带 ``hostPcbDrcUnchecked: true``、无 ERROR、其余覆盖干净时，
  verdict 必须是 ``complete-with-open-items``、`mayQuotePassed=false`、理由点名宿主
  未跑 —— 旧实现把这一键当空气（coverage 里多一个没人读的键），verdict 仍是
  ``complete``，`mayQuotePassed=true`。这条在旧实现上必红；
* **对照**：coverage 不带该键（旧报告/旧读数）仍是 ``complete``/``mayQuotePassed=true``
  —— 新闸不追溯改写历史归档；
* ``_coverage_section`` 只在事实为真时写键（缺省不写，键集与 038R2 之前逐字相同）；
* 事实读数 `_host_pcb_drc_unchecked`：有 PCB 且 `checked` 非 true 才为真；无 PCB、
  `checked=true` 都为假；
* CLI 侧：一个**含 PCB 文档的现有归档夹具**上事实为真、键在、理由在，且**宿主段与
  findings/ERROR/退出码逐项不变**（对照组把事实按住，其它读数必须一模一样）；
  一个**纯原理图归档夹具**（没有 PCB 文档）不触发；
* `_completion_coverage_gates` 把这一类计入 open-item 的 `coverage_gaps`，并让
  `summary.conclusion` 那句「另有 N 类覆盖缺口」跟着动 —— verdict 与结论句不许分裂。

夹具一律只读。
"""

from __future__ import annotations

import json
from pathlib import Path

from boardwise import cli
from boardwise.cli import (
    _clean_coverage,
    _completion_body,
    _completion_coverage_gates,
    _completion_from_report,
    _coverage_reasons,
    _coverage_section,
    _regate_exit_code,
    _review_conclusion,
)
from boardwise.core.geometry import ParseStats
from boardwise.core.model import Component, DesignModel, Net, Pin
from boardwise.engines.checkup import conclusion_section

FIXTURES = Path(__file__).parent / "fixtures"
SHELF = Path(__file__).resolve().parents[1] / "blocklib" / "parts.json"

#: 一个含 PCB 文档的现有归档夹具（多块 PCB，PCB1/PCB2/…）：离线跑它时
#: `drc.pcb` 段是 `offline-not-available`，而 PCB runner **确实**产出 `pcb_review`。
#: 路径字符串是既有文件的寻址，不是夹具身份的描述。
PCB_WITH_DOCS = FIXTURES / "ProPrj_毕设FOC驱动板_2026-09-17.epro2"
#: 一个没有 PCB 文档的现有归档夹具（纯原理图）：本闸必须忽略的那种缺席。
SCHEMATIC_ONLY = FIXTURES / "ProPrj_CH340G_2026-09-13.epro2"

#: The `drc.pcb` segment an offline run writes — read verbatim off the PCB fixture
#: (038R2 实测), so the fake and the real path read the same shape.
OFFLINE_PCB_DRC = {
    "checked": False,
    "source": "offline-not-available",
    "reason": "离线路径（--file）不连编辑器，因此没有主机 PCB DRC；要它就给一个在线工程",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _clean(*extra: dict) -> dict:
    """A coverage section in which nothing was known to be missing."""
    coverage = _clean_coverage()
    for patch in extra:
        coverage.update(patch)
    return coverage


def _fake_body(coverage: dict, *, errors: int = 0) -> dict:
    """`completion` from a **fake** coverage reading: no parse, no model, no rules.

    Every other gate is clean on purpose (no ERROR, no unreviewed part, no
    pending triage, a filled architecture skeleton), so the verdict is decided by
    the coverage reading alone — which is the whole question 038R2 asks.
    """
    return _completion_body(
        scope={"rules": 74, "boards": 1, "pages": 1},
        summary={"errorCount": errors, "errors": [], "exitCode": 0, "countsIncomplete": False},
        unreviewed=[],
        triage=[],
        needs_datasheet=[],
        architecture={"totals": {"slots": 2, "filled": 2, "stale": 0}},
        coverage=coverage,
    )


def _fake_report(body: dict, *, exit_code: int = 0) -> dict:
    """The smallest report `conclusion_section` can read a verdict out of."""
    return {"summary": {"exitCode": exit_code}, "completion": body, "findings": []}


def _tiny_model() -> DesignModel:
    """One component on one net — a reading that read **something**."""
    model = DesignModel()
    model.components["U1"] = Component(
        uid="u1", designator="U1", pins=[Pin("1", "VIN", "VCC")]
    )
    model.nets = {"VCC": Net("VCC", [("U1", "1")])}
    return model


def _run_checkup(tmp_path: Path, monkeypatch, fixture: Path, name: str) -> dict:
    """One offline checkup over a real fixture, returning its ``report.json``."""
    monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path / f"home-{name}"))
    out = tmp_path / name
    cli.main([
        "checkup", "--file", str(fixture), "--out", str(out), "--library", str(SHELF),
    ])
    return json.loads((out / "report.json").read_text(encoding="utf-8"))


def _finding_digest(report: dict) -> list:
    """Every finding the report carries, reduced to what a reader acts on."""
    return [
        [f.get("rule_id"), f.get("severity"), f.get("refs"), f.get("message")]
        for f in report.get("findings") or []
    ]


# ---------------------------------------------------------------------------
# 1. the killer: a PCB project whose host DRC never ran is not `complete`
# ---------------------------------------------------------------------------


def test_a_pcb_project_whose_host_drc_never_ran_is_not_complete():
    """038R2 裁定：complete-with-open-items，不是 incomplete，也不是 complete。

    This is the test the old implementation fails: `hostPcbDrcUnchecked` reached
    `coverage` and nobody read it, so the reading — no ERROR, every other coverage
    fact clean, a PCB document in the project — came out ``complete`` with
    ``mayQuotePassed = true`` (「可以投板」). 自有规则零新增不等于宿主 DRC 通过。
    """
    body = _fake_body(_clean({"hostPcbDrcUnchecked": True}))

    assert body["verdict"] == "complete-with-open-items", (
        "a PCB project whose host PCB DRC did not run is an **open item**, not "
        "`complete` (nothing was found) and not `incomplete` (the review did run)"
    )
    clause = body["verdictWhy"][-1]
    assert "宿主" in clause and "DRC" in clause and "drc.pcb.checked=false" in clause, (
        f"the clause must name the host DRC and the segment that says so; got {clause!r}"
    )
    assert "投板" not in clause, "an open item is not a shipping verdict either way"

    # 无其他 ERROR 时退出码仍为 0：这一条不是 incomplete，就不许把 exitCode 抬到 3。
    assert body["errors"] == 0
    assert _regate_exit_code({"exitCode": 0}, body["verdict"]) == 0, (
        "the open-item verdict keeps exit 0 (073's mapping); widening it would "
        "move the exit code of most real boards"
    )

    # 结论句：mayQuotePassed 是脚本能判读的唯一开关，它必须跟着 verdict 走。
    conclusion = conclusion_section(_fake_report(body))
    assert conclusion["verdict"] == "complete-with-open-items"
    assert conclusion["mayQuotePassed"] is False, (
        "「宿主 PCB DRC 未运行」的板子不得被引用成通过"
    )
    assert "可以投板" not in conclusion["oneLiner"], conclusion["oneLiner"]
    assert clause in conclusion["blockers"], (
        "the blocker list quotes completion.verdictWhy verbatim, so the host DRC "
        "line has to be in it"
    )


def test_the_old_reading_stays_the_control():
    """coverage 里没有这一键（旧报告/旧读数）→ 仍是 `complete`。

    The negative control for the test above: the *same* fake reading minus the
    new key still reads ``complete``. That is the behaviour a report written
    before this batch keeps (see the re-gate test below), and it is what makes
    the killer assertion above about the new fact rather than about fake data.
    """
    body = _fake_body(_clean())

    assert body["verdict"] == "complete"
    assert body["verdictWhy"] == []
    assert conclusion_section(_fake_report(body))["mayQuotePassed"] is True


# ---------------------------------------------------------------------------
# 2. the fact: written only when it is true
# ---------------------------------------------------------------------------


def test_the_new_key_is_absent_unless_the_fact_is_true():
    """`_coverage_section` 缺省不写这一键 —— 普通旧输出的键集一字不动。"""
    base = _coverage_section(
        model=_tiny_model(), board=None, attempts=[],
        parse_stats=ParseStats(), rules_errored=[],
    )
    assert "hostPcbDrcUnchecked" not in base, (
        "a run that is not 「PCB 工程 + 宿主 DRC 没跑」 must keep exactly the keys "
        "it had before 038R2"
    )
    assert tuple(base) == (
        "parseIncomplete", "modelEmpty", "boardsEmpty", "boardsEmptyNames",
        "pagesDropped", "rulesRefused", "recordsDropped", "rulesErrored",
        "pcbReviewMissing",
    ), (
        "the default key set (and order) is the one the 038R2 之前 build wrote: no "
        "new key without the fact"
    )

    flagged = _coverage_section(
        model=_tiny_model(), board=None, attempts=[],
        parse_stats=ParseStats(), rules_errored=[],
        host_pcb_drc_unchecked=True,
    )
    assert flagged["hostPcbDrcUnchecked"] is True
    assert set(flagged) - set(base) == {"hostPcbDrcUnchecked"}, (
        "the fact is the **only** key it adds"
    )


def test_the_fact_reads_checked_and_pcb_documents_together():
    """`drc.pcb.checked` 非 true **且** 工程真有 PCB 文档，事实才为真。

    Both halves are read where both are in hand (the CLI's coverage call site);
    this pins the predicate itself so a later batch cannot quietly default it to
    either side: 「没有 PCB」不是缺口，`checked=true` 更不是。
    """
    read = cli._host_pcb_drc_unchecked
    offline = {"pcb": dict(OFFLINE_PCB_DRC)}

    assert read(offline, pcb_had_documents=True) is True
    assert read(offline, pcb_had_documents=False) is False, (
        "a schematic-only project is not downgraded for a DRC it never needed"
    )
    assert read(
        {"pcb": {"checked": True, "totals": {"leafs": 0, "groups": 0}}},
        pcb_had_documents=True,
    ) is False, "checked=true is the run that **did** ask the host — no new key"
    assert read({"pcb": {"checked": None}}, pcb_had_documents=True) is True, (
        "非 true 即未查：the wording is `not checked`, not `checked is False`"
    )
    assert read(
        {"pcb": {"checked": False, "reason": "bridge 拒绝"}}, pcb_had_documents=True
    ) is True, "an online refusal is the same open item as the offline absence"


# ---------------------------------------------------------------------------
# 3. the clause and the conclusion gate
# ---------------------------------------------------------------------------


def test_the_clause_names_the_host_segment_and_says_what_it_is_not():
    """一条理由，钉住「自有规则零新增 ≠ 宿主通过」这半句。"""
    reasons = _coverage_reasons(_clean({"hostPcbDrcUnchecked": True}))

    assert len(reasons) == 1, reasons
    clause = reasons[0]
    assert "drc.pcb.checked=false" in clause, (
        "the clause must point the reader at the segment that states the reason"
    )
    assert "不等于" in clause or "不表示" in clause, (
        "the clause has to say that no new finding is not the same as a host pass; "
        f"got {clause!r}"
    )
    assert _coverage_reasons(_clean()) == [], "no fact, no clause"


def test_the_conclusion_gate_counts_the_new_kind():
    """`_completion_coverage_gates` 同步计入这一类（open-item，不是 incomplete）。"""
    gates = _completion_coverage_gates(
        completion={"coverage": _clean({"hostPcbDrcUnchecked": True})}
    )

    assert gates["coverage_gaps"] == 1, gates
    assert gates["coverage_missing"] is False, (
        "this is not 「no input at all」: the review read the board"
    )
    assert gates["pcb_review_missing"] is False, (
        "126d's flag is a different statement (the PCB section is absent)"
    )
    assert set(gates) == {"coverage_missing", "coverage_gaps", "pcb_review_missing"}, (
        "the conclusion's gate dict is not extended, only its count moved"
    )

    both = _completion_coverage_gates(
        completion={
            "coverage": _clean(
                {"hostPcbDrcUnchecked": True, "rulesErrored": ["led"], "pagesDropped": 2}
            )
        }
    )
    assert both["coverage_gaps"] == 3, both

    clean = _completion_coverage_gates(completion={"coverage": _clean()})
    assert clean["coverage_gaps"] == 0, "a run that asked the host adds no gap"


def test_the_quotable_line_counts_the_gap_too():
    """verdict 与结论句不许分裂：闸计进了 gap，那句「另有 N 类覆盖缺口」跟着动。"""
    gates = _completion_coverage_gates(
        completion={"coverage": _clean({"hostPcbDrcUnchecked": True})}
    )
    line = _review_conclusion(
        {"errorCount": 0}, unreviewed_count=0, marked_count=0, **gates
    )

    assert "1 类覆盖缺口" in line, line
    assert "宿主" in line, (
        "the parenthetical names the kinds; a host DRC that never ran is one of them"
    )
    clean_line = _review_conclusion(
        {"errorCount": 0}, unreviewed_count=0, marked_count=0,
        **_completion_coverage_gates(completion={"coverage": _clean()}),
    )
    assert "覆盖缺口" not in clean_line, clean_line


# ---------------------------------------------------------------------------
# 4. the old report: re-gate keeps the old verdict, and keeps the new gate
# ---------------------------------------------------------------------------


def _old_report(coverage: dict) -> dict:
    return {
        "summary": {"errorCount": 0, "errors": [], "exitCode": 0},
        "completion": {
            "scope": {"rules": 74, "boards": 1, "pages": 1},
            "coverage": coverage,
        },
        "model": {"boards": [{"title": "B1", "pages": [{"title": "P1"}]}]},
        "unreviewed_parts": [],
        "warning_triage": [],
        "architecture": {"totals": {"slots": 2, "filled": 2, "stale": 0}},
        "accepted_unknown": [],
    }


def test_a_regate_of_an_old_report_keeps_its_old_verdict():
    """缺这一键的旧报告 re-gate 后仍是 `complete` —— 不用新闸追溯惩罚旧归档。"""
    section = _completion_from_report(_old_report(_clean()), needs_datasheet=[])

    assert section["verdict"] == "complete", (
        "a report written before 038R2 carries no such key; absence means False, "
        "which is the neutral reading — its verdict is not re-litigated"
    )
    assert "hostPcbDrcUnchecked" not in (section.get("coverage") or {})


def test_a_regate_of_a_new_report_keeps_the_gate():
    """在报告里的闸可以在 re-gate 里活下来（#30 的教训：闸不许只活在 CLI 内存里）。"""
    section = _completion_from_report(
        _old_report(_clean({"hostPcbDrcUnchecked": True})), needs_datasheet=[]
    )

    assert section["coverage"]["hostPcbDrcUnchecked"] is True
    assert section["verdict"] == "complete-with-open-items", (
        "a re-gate must not be a way to lose the gate"
    )


# ---------------------------------------------------------------------------
# 5. the real paths: offline with PCB / offline without PCB
# ---------------------------------------------------------------------------


def test_an_offline_backup_with_pcb_carries_the_fact_and_nothing_else(
    tmp_path, monkeypatch
):
    """含 PCB 的归档夹具：事实为真、键在、理由在；宿主段与 findings/ERROR/退出码一字不动。

    The control run (the fact held down at its source) is the report the same
    build would have written before this batch: every other reading must be
    **identical**, which is how 「不伪造宿主计数、不加 ERROR、不加 Finding、退出码
    不变」 is measured rather than asserted about the fake.
    """
    seen: list[bool] = []
    real = cli._host_pcb_drc_unchecked

    def spy(drc, *, pcb_had_documents):
        value = real(drc, pcb_had_documents=pcb_had_documents)
        seen.append(value)
        return value

    monkeypatch.setattr(cli, "_host_pcb_drc_unchecked", spy)
    flagged = _run_checkup(tmp_path, monkeypatch, PCB_WITH_DOCS, "flagged")

    assert seen == [True], "the fact is read once, from the CLI's own PCB block"

    coverage = flagged["completion"]["coverage"]
    assert coverage["hostPcbDrcUnchecked"] is True
    assert coverage["pcbReviewMissing"] is False, (
        "the PCB section is present: this is not 126d's case"
    )
    assert any("drc.pcb.checked=false" in reason
               for reason in flagged["completion"]["verdictWhy"]), (
        "the open item is spelled out in the reasons a reader sees"
    )
    # 宿主段保持原样：仍说「没查」，不伪造计数、不改写成错误。
    assert flagged["drc"]["pcb"] == {
        "checked": False,
        "source": "offline-not-available",
        "reason": OFFLINE_PCB_DRC["reason"],
        "note": flagged["drc"]["pcb"]["note"],
    }, flagged["drc"]["pcb"]
    assert "totals" not in flagged["drc"]["pcb"], (
        "no host counts may be invented for a host that never ran"
    )

    # The control: the same build, the same fixture, the fact held down at its
    # source — the report 038R2 之前 would have written.
    monkeypatch.setattr(
        cli, "_host_pcb_drc_unchecked", lambda drc, *, pcb_had_documents: False
    )
    control = _run_checkup(tmp_path, monkeypatch, PCB_WITH_DOCS, "control")

    assert "hostPcbDrcUnchecked" not in control["completion"]["coverage"]
    assert flagged["drc"] == control["drc"], (
        "the DRC reading is the same run's fact: the gate adds no host answer"
    )
    assert _finding_digest(flagged) == _finding_digest(control), (
        "checked=false must not be turned into a Finding"
    )
    assert flagged["summary"]["errorCount"] == control["summary"]["errorCount"]
    assert len(flagged["summary"].get("errors") or []) == len(
        control["summary"].get("errors") or []
    ), "checked=false must not be turned into an ERROR"
    assert flagged["summary"]["exitCode"] == control["summary"]["exitCode"], (
        "the exit code is decided by drc.summarise and keeps its priority"
    )
    assert flagged["conclusion"]["mayQuotePassed"] is False


def test_an_offline_backup_without_pcb_is_not_downgraded(tmp_path, monkeypatch):
    """纯原理图归档夹具（无 PCB 文档）：不触发、不写键、verdict 与之前一样。"""
    seen: list[bool] = []
    real = cli._host_pcb_drc_unchecked

    def spy(drc, *, pcb_had_documents):
        value = real(drc, pcb_had_documents=pcb_had_documents)
        seen.append(value)
        return value

    monkeypatch.setattr(cli, "_host_pcb_drc_unchecked", spy)
    report = _run_checkup(tmp_path, monkeypatch, SCHEMATIC_ONLY, "no-pcb")

    assert seen == [False], "no PCB document → nothing was obliged to run"
    assert "hostPcbDrcUnchecked" not in report["completion"]["coverage"]
    assert not any("宿主" in reason for reason in report["completion"]["verdictWhy"]), (
        "a schematic-only project owes no PCB DRC sentence"
    )
