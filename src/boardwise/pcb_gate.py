"""038Y5: the read-only ``boardwise pcb gate`` — host DRC, then a fresh checkup.

The last step after a board change, and **only** an orchestration of two readings
that already exist: the editor's own PCB DRC (:data:`DRC_ACTION`, 025) and
``boardwise checkup`` (whose report carries the three 038Y rules and the silk
review). Nothing here judges a board, copies a silk geometry model, or writes a
document — :func:`run_gate` never calls ``doc.open`` / ``doc.save`` /
``pcb.*`` writes, and has no autofix path.

Three behaviours of the pre-research gate (``.tmp_pcb_review_20261115/code/``)
are **not** carried over, and each is a rule below rather than a comment:

1. a checkup that says ``incomplete`` may not be GREEN — the gate cannot claim a
   board was seen whole when the review said it was not (:func:`_checkup_state`);
2. RED (the board has errors) is exit **2**, "cannot be stated" is exit **3** —
   the pre-research gate had those two the other way round, so a red board
   looked like a broken tool;
3. the report directory must be **new**. A fixed ``--out`` let a second run read
   the first run's ``report.json`` and answer for a board it never looked at, so
   an existing ``DIR`` is refused *before* any bridge action and no report is
   ever read from it.

Exit codes: ``0`` GREEN / ``2`` RED / ``3`` INCOMPLETE or an input, identity or
output that cannot be used. Argparse's own usage errors stay 2 (the same as every
other command's), and there is no RED-DRC special case.

Two consumption faces, one implementation:

* :func:`run_gate` — synchronous, takes ``call(action, params) -> payload`` and
  ``checkup_runner(out_dir) -> (report_dict | None, exit_code)``. Every test
  drives this with fakes; it never imports the bridge.
* :func:`run_cli_gate` — the CLI adapter: each bridge action gets **its own
  short connection** (so the synchronous checkup below can be called outside an
  event loop), and the checkup is the real :func:`boardwise.cli._cmd_checkup`
  handed in by assembly, with a namespace built from the real ``checkup`` parser
  so its defaults cannot drift from the command's.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "CHECKUP_DIR",
    "COVERAGE_GAPS",
    "DRC_PARAMS",
    "GATE_REPORT",
    "GateReport",
    "GREEN",
    "INCOMPLETE",
    "RED",
    "checkup_namespace",
    "run_cli_gate",
    "run_gate",
]

GREEN = "GREEN"
RED = "RED"
INCOMPLETE = "INCOMPLETE"

#: The gate's own machine-readable summary, written into the **new** ``--out``.
GATE_REPORT = "gate-report.json"
#: The checkup's directory *inside* that new ``--out``.
CHECKUP_DIR = "checkup"
#: The checkup report this gate reads back (its own run's; see ``_checkup_runner``).
CHECKUP_REPORT = "report.json"

DOC_LIST_ACTION = "doc.list"
#: 025's item-level PCB DRC, asked the way the review already asks it: verbose
#: leaves, not the editor's bottom panel.
DRC_ACTION = "pcb.drc_check"
DRC_PARAMS: dict[str, Any] = {
    "strict": True,
    "userInterface": False,
    "includeVerboseError": True,
}

#: The coverage keys that mean the review did not see the whole board. Any one of
#: them being truthy keeps the gate out of GREEN regardless of what the verdict
#: says ``complete`` — the keys the report's own ``incomplete`` gate reads
#: (``_completion_body``: modelEmpty / pcbReviewMissing / shelfUnreadable), the
#: ones it counts as coverage gaps (``_completion_coverage_gates``: pagesDropped /
#: rulesRefused / recordsDropped / rulesErrored / hostPcbDrcUnchecked) and
#: parseIncomplete, named here so the gate cannot silently narrow. Two deliberate
#: omissions: ``boardsEmptyNames`` is the *names* beside ``boardsEmpty`` (counting
#: it would double-count one fact), and ``hostPcbDrcUnchecked`` — this gate has
#: just run the host DRC itself, so its absence from a checkup is not a hole it
#: may inherit.
COVERAGE_GAPS = (
    "modelEmpty",
    "parseIncomplete",
    "rulesErrored",
    "recordsDropped",
    "rulesRefused",
    "pagesDropped",
    "boardsEmpty",
    "pcbReviewMissing",
)

#: The two verdicts that may stand behind a GREEN gate: ``complete`` and
#: ``complete-with-open-items`` (an open item is a disclosed hole, not a silent
#: one — the gate discloses the verdict it read in its own report).
GREEN_VERDICTS = ("complete", "complete-with-open-items")
#: The one verdict that is a *refusal to state*, and the only other known value.
INCOMPLETE_VERDICT = "incomplete"
KNOWN_VERDICTS = (*GREEN_VERDICTS, INCOMPLETE_VERDICT)


# ---------------------------------------------------------------------------
# The conclusion — one object, three exits
# ---------------------------------------------------------------------------
@dataclass
class GateReport:
    """One gate run's conclusion and the two readings it was built from.

    Fields are the stable contract of ``gate-report.json``. It carries **sums
    only** — counts, flags and the checkup's own verdict/conclusion line — never
    the DRC group tree or a findings list: the checkup report beside it is where
    the detail lives, and a second copy here would be a second thing to trust.
    """

    verdict: str
    reason: str = ""
    out: str = ""
    #: ``{"project": {uuid, name, friendlyName}, "instance": str}`` — whatever
    #: ``doc.list`` proved, or the explicit ``--instance`` when it proved nothing.
    identity: dict[str, Any] = field(default_factory=dict)
    #: ``{ran, checked, errors, items, truncated, reason}`` — the host DRC reading.
    drc: dict[str, Any] = field(default_factory=dict)
    #: ``{ran, out, exitCode, verdict, conclusion, coverageGaps, reason}``.
    checkup: dict[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        """``0`` GREEN / ``2`` RED / ``3`` everything else (never stated)."""
        if self.verdict == GREEN:
            return 0
        if self.verdict == RED:
            return 2
        return 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "boardwise.pcb-gate/1",
            "verdict": self.verdict,
            "exitCode": self.exit_code,
            "reason": self.reason,
            "out": self.out,
            "identity": self.identity,
            "drc": self.drc,
            "checkup": self.checkup,
        }


# ---------------------------------------------------------------------------
# Identity: which project, which window, and is that document a PCB
# ---------------------------------------------------------------------------
def _project_of(listing: Mapping[str, Any]) -> dict[str, str]:
    """The project ``doc.list`` says it read, or ``{}`` when it says nothing.

    The focused row of ``projects[]`` is the measured shape (012 §五); a
    hand-built or older answer may carry ``project`` or ``active.project``
    instead, and both are read rather than one being called "the" shape. An
    entry with no uuid **and** no name is not identity — it is an empty box, and
    :func:`_identity` treats it as unreadable instead of matching everything.
    """
    rows: list[Any] = []
    for project in listing.get("projects") or []:
        if isinstance(project, Mapping) and project.get("focused") is True:
            rows.append(project)
    if isinstance(listing.get("project"), Mapping):
        rows.append(listing["project"])
    active = listing.get("active")
    if isinstance(active, Mapping) and isinstance(active.get("project"), Mapping):
        rows.append(active["project"])
    for row in rows:
        out = {
            "uuid": str(row.get("uuid") or row.get("projectUuid") or ""),
            "name": str(row.get("name") or ""),
            "friendlyName": str(row.get("friendlyName") or ""),
        }
        if out["uuid"] or out["name"] or out["friendlyName"]:
            return out
    return {}


def _declared_instance(listing: Mapping[str, Any]) -> str:
    """The window key ``doc.list`` declares, if this build's answer declares one.

    Only an explicit ``instance`` / ``instanceKey`` field counts. ``tabId`` is
    *not* one: it is a tab, the ``--instance`` hint is a window key, and
    comparing the two would refuse correct runs on a real machine.
    """
    for container in (listing, listing.get("active")):
        if not isinstance(container, Mapping):
            continue
        for key in ("instance", "instanceKey"):
            value = container.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def _matches(hint: str, project: Mapping[str, str]) -> bool:
    """Verbatim match (R1) against any name the listing carries."""
    return hint in {
        str(project.get("uuid") or ""),
        str(project.get("name") or ""),
        str(project.get("friendlyName") or ""),
    }


def _identity(
    listing: Mapping[str, Any], *, project: str, instance: str
) -> tuple[dict[str, Any], str]:
    """``(identity, why)`` — ``why`` non-empty means the gate must not go on.

    * A readable project is the identity, and an explicit ``--project`` has to
      match it verbatim (name, friendly name or uuid).
    * With **no** readable project, only an explicit ``--instance`` can stand in
      — it is the one thing the caller asserted and the daemon resolved. Nothing
      readable and no instance is "cannot prove which project this is", which is
      an exit 3, not a guess.
    * An instance the listing *declares* must agree with the hint; a listing
      that declares none proves nothing either way, so it is not held against
      the caller.
    """
    project = (project or "").strip()
    instance = (instance or "").strip()
    found = _project_of(listing)
    declared = _declared_instance(listing)
    if instance and declared and declared != instance:
        return {}, (
            f"instance hint {instance!r} does not match the window doc.list reports "
            f"({declared!r}) — refusing to check another window's board"
        )
    if found:
        if project and not _matches(project, found):
            name = found.get("friendlyName") or found.get("name") or found.get("uuid")
            return {}, (
                f"project hint {project!r} does not match the project doc.list reports "
                f"({name!r}, uuid={found.get('uuid')!r}) — refusing to review another project"
            )
        return {"project": found, "instance": instance or declared}, ""
    if instance:
        return {"project": {}, "instance": instance}, ""
    return {}, (
        "doc.list proved no project identity (no projects[]/project name or uuid) and "
        "no --instance was given — nothing says which project this board belongs to"
    )


def _active_pcb(listing: Mapping[str, Any]) -> tuple[dict[str, str], str]:
    """``(active pcb, why)`` — the focused document, or the reason there is none.

    **No fallback, ever**: the board under review is the one the editor is on.
    Picking ``documents[0]`` / ``pcbs[0]`` would check a board the caller is not
    looking at (and, on a multi-board project, answer for whichever one the host
    happened to list first). One active PCB is reviewed; the others are not
    merged into it and never silently replace it.
    """
    active = listing.get("active")
    if not isinstance(active, Mapping):
        return {}, "doc.list reports no active document — there is no board to check"
    uuid = str(active.get("uuid") or "")
    kind = str(active.get("type") or "").lower()
    if not uuid:
        return {}, "doc.list's active document carries no uuid — no board to check"
    if kind != "pcb":
        return {}, (
            f"the active document is a {kind or '(untyped)'}, not a PCB — the gate does "
            "not switch documents, so there is nothing to check"
        )
    return {"uuid": uuid, "name": str(active.get("name") or "")}, ""


# ---------------------------------------------------------------------------
# The host DRC reading
# ---------------------------------------------------------------------------
def _drc_state(payload: Any) -> tuple[str, dict[str, Any], str]:
    """``(state, summary, why)`` for one ``pcb.drc_check`` answer.

    ``state`` is ``"clean"`` / ``"red"`` / ``"unverifiable"``. Everything the
    reading did not actually state lands in the third bucket instead of a zero:
    a DRC that did not run, answered only a boolean, dropped whole groups to stay
    inside ``maxChars``, or reports no error count has **no** number to gate on.
    """
    summary: dict[str, Any] = {"ran": True, "checked": False, "errors": None,
                              "items": None, "truncated": None}
    if not isinstance(payload, Mapping):
        return "unverifiable", summary, (
            f"pcb.drc_check answered a {type(payload).__name__}, not the declared object"
        )
    summary["checked"] = payload.get("checked") is True
    summary["truncated"] = bool(payload.get("truncated"))
    if payload.get("checked") is not True:
        return "unverifiable", summary, (
            "the host DRC did not run: " + str(payload.get("reason") or "checked is not true")
        )
    if payload.get("available") is not True:
        return "unverifiable", summary, (
            "the host DRC is not available: " + str(payload.get("reason") or "available is not true")
        )
    if summary["truncated"]:
        return "unverifiable", summary, (
            "the host DRC tree was truncated to stay inside maxChars — the returned "
            "groups are not the whole answer, and `counts` below it cannot be quoted"
        )
    counts = payload.get("counts")
    if not isinstance(counts, Mapping):
        return "unverifiable", summary, (
            f"the host DRC answered mode={payload.get('mode')!r} with no counts — "
            "whether it found errors, and how many, is not stated"
        )
    errors = counts.get("errors")
    if isinstance(errors, bool) or not isinstance(errors, int):
        return "unverifiable", summary, (
            f"the host DRC states no error count (counts.errors={errors!r})"
        )
    items = counts.get("items")
    summary["errors"] = errors
    summary["items"] = items if isinstance(items, int) and not isinstance(items, bool) else None
    if errors > 0:
        return "red", summary, (
            f"the host PCB DRC reports {errors} error(s) — the board is red before any "
            "review of it"
        )
    return "clean", summary, ""


# ---------------------------------------------------------------------------
# The checkup report reading
# ---------------------------------------------------------------------------
def _coverage_gaps(report: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """``(coverage, gaps)`` — the declared coverage, and the names that are red."""
    completion = report.get("completion")
    coverage = (completion or {}).get("coverage") if isinstance(completion, Mapping) else None
    if not isinstance(coverage, Mapping):
        return {}, ["coverage"]
    gaps = [name for name in COVERAGE_GAPS if coverage.get(name)]
    return dict(coverage), gaps


def _summary_exit_code(report: Mapping[str, Any]) -> Any:
    """Every exit code the report itself declares, as one comparable list."""
    declared: list[Any] = []
    summary = report.get("summary")
    if isinstance(summary, Mapping) and summary.get("exitCode") is not None:
        declared.append(summary.get("exitCode"))
    conclusion = report.get("conclusion")
    if isinstance(conclusion, Mapping) and conclusion.get("exitCode") is not None:
        declared.append(conclusion.get("exitCode"))
    return declared


def _checkup_state(
    report: Any, exit_code: int
) -> tuple[str, dict[str, Any], str]:
    """``(state, summary, why)`` for the checkup this gate just ran.

    ``state`` is ``"green"`` / ``"red"`` / ``"incomplete"``. The order of the
    checks is the ruling: **incomplete outranks ERROR**, because a review that
    says it did not see the whole board cannot be quoted as having found *all*
    the errors either. So the refusal-to-state conditions are read first, and
    only a run that may be stated is allowed to be RED or GREEN.
    """
    summary: dict[str, Any] = {
        "ran": True,
        "exitCode": exit_code,
        "verdict": "",
        "conclusion": "",
        "coverageGaps": [],
    }
    if report is None:
        return "incomplete", summary, (
            "checkup wrote no report.json into this run's fresh directory — nothing "
            "can be quoted as this run's result"
        )
    if not isinstance(report, Mapping):
        return "incomplete", summary, f"checkup's report.json is a {type(report).__name__}"
    completion = report.get("completion") if isinstance(report.get("completion"), Mapping) else {}
    conclusion_section = report.get("conclusion") if isinstance(report.get("conclusion"), Mapping) else {}
    # Two sections, one verdict. Either may be the only one present (an older or
    # hand-built report), so one value is read as is; two **different** values are
    # not a precedence question — the report disagrees with itself and neither can
    # be quoted, which is exactly how a `conclusion: incomplete` used to be
    # masked by a `completion: complete` beside it.
    completion_verdict = str(completion.get("verdict") or "").strip()
    conclusion_verdict = str(conclusion_section.get("verdict") or "").strip()
    stated = [value for value in (completion_verdict, conclusion_verdict) if value]
    summary["verdict"] = completion_verdict or conclusion_verdict
    summary["verdicts"] = {"completion": completion_verdict, "conclusion": conclusion_verdict}
    one_liner = conclusion_section.get("oneLiner")
    summary_section = report.get("summary")
    summary["conclusion"] = str(
        (summary_section.get("conclusion") if isinstance(summary_section, Mapping) else "")
        or one_liner
        or ""
    )
    coverage, gaps = _coverage_gaps(report)
    summary["coverageGaps"] = gaps
    if len(set(stated)) > 1:
        return "incomplete", summary, (
            f"the report states two verdicts: completion.verdict="
            f"{completion_verdict or '(absent)'!r} vs conclusion.verdict="
            f"{conclusion_verdict or '(absent)'!r} — a review that disagrees with its own "
            "conclusion is not a pass"
        )
    if exit_code not in (0, 1):
        return "incomplete", summary, (
            f"checkup exited {exit_code} — 2 is an unusable input and 3 is 「nothing may "
            "be stated」; neither is a review of this board"
        )
    verdict = stated[0] if stated else ""
    if verdict not in KNOWN_VERDICTS:
        return "incomplete", summary, (
            f"checkup's verdict is {verdict or '(absent)'!r}, which this gate does not "
            "know — an unreadable verdict is not a pass"
        )
    if verdict == INCOMPLETE_VERDICT:
        why = "; ".join(str(item) for item in (completion.get("verdictWhy") or []))
        return "incomplete", summary, (
            "checkup's own completion.verdict is `incomplete`" + (f"（{why}）" if why else "")
            + " — the review did not see the whole board, so its lack of ERRORs is not a pass"
        )
    declared = _summary_exit_code(report)
    if not declared:
        return "incomplete", summary, (
            "the checkup report declares no exit code (summary.exitCode) — the report and "
            "the process cannot be reconciled"
        )
    mismatched = [value for value in declared if value != exit_code]
    if mismatched:
        return "incomplete", summary, (
            f"the checkup report declares exitCode {mismatched[0]!r} but the run exited "
            f"{exit_code} — one of the two is not this run's result"
        )
    if gaps:
        return "incomplete", summary, (
            "checkup declares missing coverage ("
            + ", ".join(gaps)
            + ") — the review did not read that much of the board"
        )
    # The ERROR question is asked of the report's **findings**, not of one count
    # that may be absent: a count nobody wrote is not a count of zero, and a
    # `findings` that is not a list is a section that cannot be read at all.
    findings = report.get("findings")
    if not isinstance(findings, list):
        return "incomplete", summary, (
            "the report's findings section is "
            + ("(absent)" if findings is None else f"a {type(findings).__name__}")
            + ", not a list — it states no ERROR and no absence of one, so neither "
            "answer can be given"
        )
    error_findings = [
        entry for entry in findings
        if isinstance(entry, Mapping)
        and str(entry.get("severity") or "").strip().upper() == "ERROR"
    ]
    summary["errorFindings"] = len(error_findings)
    error_count = (report.get("summary") or {}).get("errorCount")
    if isinstance(error_count, bool) or not isinstance(error_count, int):
        error_count = None
    completion_errors = completion.get("errors")
    if isinstance(completion_errors, bool):
        completion_errors = None
    if isinstance(completion_errors, (list, tuple)):
        completion_errors = len(completion_errors)
    if not isinstance(completion_errors, int):
        completion_errors = None
    if (
        exit_code == 1 or error_findings or error_count
        or (completion_errors or 0) > 0
    ):
        evidence = [
            f"exit {exit_code}",
            f"{len(error_findings)} ERROR finding(s)" if error_findings else "",
            f"summary.errorCount={error_count}" if error_count else "",
            f"completion.errors={completion_errors}" if (completion_errors or 0) > 0 else "",
        ]
        return "red", summary, "checkup found ERROR-severity findings (" + ", ".join(
            item for item in evidence if item
        ) + ")"
    return "green", summary, ""


# ---------------------------------------------------------------------------
# The gate itself
# ---------------------------------------------------------------------------
def _write_report(out_dir: Path, report: GateReport) -> None:
    path = out_dir / GATE_REPORT
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_gate(
    call: Callable[[str, dict[str, Any]], Any],
    checkup_runner: Callable[[Path], tuple[Any, int]],
    out: str | Path,
    *,
    project: str = "",
    instance: str = "",
) -> GateReport:
    """Run the gate once and return its conclusion (the caller owns the exit code).

    ``call`` is ``(action, params) -> payload`` — synchronous, and the caller's
    business (the CLI adapter opens one short bridge connection per action).
    ``checkup_runner`` is ``(checkup_out_dir) -> (report_dict | None, exit_code)``
    and is only ever called with ``<out>/checkup`` on a directory this run just
    created; it is **not** called at all when the gate already has a conclusion
    (no PCB in focus, wrong project, a red or unreadable host DRC).

    The output directory is created here and must not exist beforehand: the
    pre-research gate let a rerun read the previous ``report.json`` and answer for
    a board it never looked at, so this refuses an existing ``DIR`` before the
    first bridge action and writes nothing into it. Everything after that is
    inside the new directory — including the refusal, so a failed run leaves one
    machine-readable sentence instead of a bare exit code.
    """
    out_dir = Path(out)
    if out_dir.exists():
        return GateReport(
            verdict=INCOMPLETE,
            reason=(
                f"{out_dir} already exists — the gate writes only into a new directory, so "
                "a report in there would be someone else's run; name a fresh --out"
            ),
            out=str(out_dir),
        )
    try:
        out_dir.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        return GateReport(
            verdict=INCOMPLETE,
            reason=f"cannot create the report directory {out_dir}: {exc}",
            out=str(out_dir),
        )
    report = _run(call, checkup_runner, out_dir, project=project, instance=instance)
    _write_report(out_dir, report)
    return report


def _incomplete(report: GateReport, reason: str, **sections: Any) -> GateReport:
    report.verdict = INCOMPLETE
    report.reason = reason
    for name, value in sections.items():
        setattr(report, name, value)
    return report


def _run(
    call: Callable[[str, dict[str, Any]], Any],
    checkup_runner: Callable[[Path], tuple[Any, int]],
    out_dir: Path,
    *,
    project: str,
    instance: str,
) -> GateReport:
    # The two sections always exist, even when the run stops before reaching
    # them: `checkup.ran: false` is the difference between "did not run" and
    # "ran and found nothing", and the report must never have to be guessed at.
    report = GateReport(
        verdict=INCOMPLETE,
        out=str(out_dir),
        drc={"ran": False, "checked": False, "errors": None, "items": None, "truncated": None},
        checkup={"ran": False, "out": "", "exitCode": None, "verdict": "",
                 "conclusion": "", "coverageGaps": []},
    )
    try:
        listing = call(DOC_LIST_ACTION, {})
    except Exception as exc:  # noqa: BLE001 — a bridge failure is "cannot state"
        return _incomplete(
            report, f"doc.list is unavailable ({type(exc).__name__}: {exc}) — no board was named"
        )
    if not isinstance(listing, Mapping):
        return _incomplete(
            report, f"doc.list answered a {type(listing).__name__}, not the declared object"
        )
    identity, why = _identity(listing, project=project, instance=instance)
    if why:
        return _incomplete(report, why, identity=identity)
    report.identity = identity
    active, why = _active_pcb(listing)
    if why:
        return _incomplete(report, why)
    report.identity = {**identity, "board": active}

    try:
        payload = call(DRC_ACTION, dict(DRC_PARAMS))
    except Exception as exc:  # noqa: BLE001 — the same "cannot state" as above
        return _incomplete(
            report,
            f"pcb.drc_check is unavailable ({type(exc).__name__}: {exc})",
            drc={"ran": False, "checked": False, "errors": None, "items": None,
                 "truncated": None},
        )
    state, drc, why = _drc_state(payload)
    report.drc = drc
    if state == "unverifiable":
        return _incomplete(report, why)
    if state == "red":
        # The one "stated" result on this path: a red board is a conclusion, not
        # a missing one, and the checkup is not spent on it.
        report.verdict, report.reason = RED, why
        return report

    checkup_out = out_dir / CHECKUP_DIR
    report.checkup = {**report.checkup, "out": str(checkup_out)}
    try:
        checkup_report, exit_code = checkup_runner(checkup_out)
    except Exception as exc:  # noqa: BLE001 — a crashed checkup is not a pass
        return _incomplete(report, f"checkup could not be run ({type(exc).__name__}: {exc})")
    try:
        code = int(exit_code)
    except (TypeError, ValueError):
        # Not a number is not a pass either: -1 lands in "unknown exit" below.
        code = -1
    state, checkup, why = _checkup_state(checkup_report, code)
    checkup["ran"] = True
    checkup["out"] = str(checkup_out)
    report.checkup = checkup
    report.verdict = {"green": GREEN, "red": RED, "incomplete": INCOMPLETE}[state]
    report.reason = "" if state == "green" else why
    return report


# ---------------------------------------------------------------------------
# The CLI adapter
# ---------------------------------------------------------------------------
def checkup_namespace(
    out_dir: str | Path, *, project: str = "", instance: str = "", port: int | None = None
) -> argparse.Namespace:
    """The argument namespace ``boardwise checkup`` would get for this gate run.

    Built from the **real** ``checkup`` parser (:func:`register_checkup_parser`)
    rather than a hand-copied ``argparse.Namespace``: every default the command
    has — ``--library``, ``--intent``, ``--strict``, … — is therefore exactly the
    command's own, and a new one cannot silently reach this call as ``None``.
    """
    from .commands import review as review_commands

    parser = argparse.ArgumentParser(add_help=False, prog="boardwise")
    sub = parser.add_subparsers(dest="command", required=True)
    review_commands.register_checkup_parser(sub)
    argv = ["checkup", "--out", str(out_dir)]
    if (project or "").strip():
        argv += ["--project", project.strip()]
    if (instance or "").strip():
        argv += ["--instance", instance.strip()]
    if port is not None:
        argv += ["--port", str(port)]
    return parser.parse_args(argv)


def _short_connection_call(
    args: argparse.Namespace, bridge: Callable[[argparse.Namespace], Any]
) -> Callable[[str, dict[str, Any]], Any]:
    """``call(action, params)`` — one short bridge connection **per action**.

    The synchronous checkup runs between the two actions, so a single connection
    held open across it would need an event loop that is not running; opening,
    calling and closing per action costs one handshake and keeps every bridge
    action inside its own ``asyncio.run``. ``bridge`` is assembly's own opener
    (``cli._open_cli``): the daemon-on-demand start and the token stay one
    implementation.
    """
    route: dict[str, str] = {}
    project = str(getattr(args, "project", "") or "").strip()
    instance = str(getattr(args, "instance", "") or "").strip()
    if project:
        route["target_project"] = project
    if instance:
        route["target_instance"] = instance

    def call(action: str, params: dict[str, Any]) -> Any:
        from .bridge import client as bridge_client

        BridgeClient, _, port, token = bridge(args)

        async def one() -> Any:
            client = await BridgeClient.open(
                bridge_client.uri_for(port=port), token, "cli", client="boardwise-cli"
            )
            try:
                return await client.call(action, dict(params), **route)
            finally:
                await client.close()

        return asyncio.run(one())

    return call


def _checkup_runner(
    args: argparse.Namespace, checkup: Callable[[argparse.Namespace], int]
) -> Callable[[Path], tuple[Any, int]]:
    """``(report, exit_code)`` from the real checkup, on this run's own directory.

    The report is read **only** when the file did not exist before the call. The
    gate's directory is fresh, so that is a belt beside the braces of
    :func:`run_gate`'s refusal — the point is that no code path here can read a
    report the run did not just write.
    """
    project = str(getattr(args, "project", "") or "")
    instance = str(getattr(args, "instance", "") or "")
    port = getattr(args, "port", None)

    def run(out_dir: Path) -> tuple[Any, int]:
        path = Path(out_dir) / CHECKUP_REPORT
        existed = path.exists()
        namespace = checkup_namespace(out_dir, project=project, instance=instance, port=port)
        exit_code = int(checkup(namespace))
        if existed:
            return None, exit_code
        try:
            return json.loads(path.read_text(encoding="utf-8")), exit_code
        except (OSError, ValueError):
            return None, exit_code

    return run


def run_cli_gate(
    args: argparse.Namespace,
    *,
    checkup: Callable[[argparse.Namespace], int],
    bridge: Callable[[argparse.Namespace], Any],
) -> int:
    """``boardwise pcb gate`` — parse, connect, conclude, print, exit.

    ``checkup`` is assembly's ``cli._cmd_checkup`` (handed in, not imported: the
    command modules never import ``cli.py``), and ``bridge`` is ``cli._open_cli``
    for the same reason. Nothing here writes a design: the only bridge actions
    are :data:`DOC_LIST_ACTION` and :data:`DRC_ACTION`, both ``risk: read``.
    """
    import sys

    report = run_gate(
        _short_connection_call(args, bridge),
        _checkup_runner(args, checkup),
        args.out,
        project=getattr(args, "project", ""),
        instance=getattr(args, "instance", ""),
    )
    project_name = ((report.identity or {}).get("project") or {})
    board = ((report.identity or {}).get("board") or {})
    print("boardwise pcb gate: 只读 —— 宿主 PCB DRC + 全新 checkup，不写设计")
    if project_name or board:
        label = (
            project_name.get("friendlyName")
            or project_name.get("name")
            or project_name.get("uuid")
            or (report.identity or {}).get("instance")
            or "(identity unknown)"
        )
        print(f"  project: {label}")
        if board:
            print(f"  board: {board.get('name') or '(unnamed)'} [{board.get('uuid')}]")
    drc = report.drc or {}
    if drc:
        print(
            "  drc: "
            + (
                f"errors {drc.get('errors')} / items {drc.get('items')}"
                if drc.get("errors") is not None
                else "not stated"
            )
        )
    checkup_section = report.checkup or {}
    if checkup_section.get("ran"):
        print(
            f"  checkup: exit {checkup_section.get('exitCode')} / "
            f"verdict {checkup_section.get('verdict') or '(absent)'}"
        )
        if checkup_section.get("conclusion"):
            print(f"    conclusion: {checkup_section['conclusion']}")
        if checkup_section.get("coverageGaps"):
            print(f"    coverage gaps: {', '.join(checkup_section['coverageGaps'])}")
    else:
        print("  checkup: not run (the gate already has a conclusion)")
    if report.reason:
        print(f"  reason: {report.reason}", file=sys.stderr)
    print(f"  report: {Path(report.out) / GATE_REPORT}")
    print(f"  verdict: {report.verdict} (exit {report.exit_code})")
    return report.exit_code
