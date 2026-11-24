"""594 (W-C2): `edit plan` with no way in, and the `doc.open` risk the doc forgot.

hole568-B-01 measured `boardwise edit plan` with no arguments dying in
`Path(None)`: a bare `TypeError` traceback and exit 1, while the `edit` family's
documented codes are 0/2/3/4/5. The `--file` / `--report` / `--insert` /
`--move` flags are all optional at the parser, so "nothing to plan from" is a
usage refusal that has to be stated before the value path dereferences
`args.file` — exit 2, no traceback, and no bridge opened for a plan that cannot
be built.

hole568-B-02 measured the other half: `docs/bridge.md` §4 filed `doc.open` as
`read` while `bridge/protocol.py` declares it `write` (it decides which page the
next call lands on, exactly like `doc.focus`, which the table already calls
`write`). The table is what a caller reads, so one row disagreeing with the
catalogue is a contract that lies. The check here is the whole §4 table, not
just the one row: a doc/catalogue drift anywhere is the same defect.
"""

from __future__ import annotations

import re
from pathlib import Path

from boardwise import cli
from boardwise.bridge.protocol import ACTIONS

REPO = Path(__file__).resolve().parents[1]
BRIDGE_DOC = REPO / "docs" / "bridge.md"


def _no_bridge(_args):
    raise AssertionError("a plan with no way in opened the bridge")


# ---------------------------------------------------------------------------
# 1. no input at all: a usage refusal (exit 2), not a traceback
# ---------------------------------------------------------------------------


def test_a_bare_edit_plan_is_a_usage_refusal_not_a_traceback(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_open_cli", _no_bridge)
    code = cli.main(["edit", "plan"])
    printed = capsys.readouterr()
    assert code == 2, f"expected a usage refusal, got {code}: {printed.err}"
    assert "Traceback" not in printed.err
    assert "TypeError" not in printed.err
    assert printed.out == "", "a refusal writes nothing to stdout"


def test_the_refusal_names_the_ways_in(capsys):
    code = cli.main(["edit", "plan"])
    err = capsys.readouterr().err
    assert code == 2
    assert err.startswith("boardwise edit plan:"), err
    for flag in ("--file", "--report", "--insert", "--move"):
        assert flag in err, f"the refusal must name {flag}: {err}"


# ---------------------------------------------------------------------------
# 2. the neighbouring refusals keep their own code and their own ordering
# ---------------------------------------------------------------------------


def test_work_order_without_move_is_still_exit_5(tmp_path, capsys):
    """591: `--work-order` is the move path's input; naming it elsewhere is 5."""
    code = cli.main([
        "edit", "plan", "--work-order", str(tmp_path / "work.json"),
    ])
    err = capsys.readouterr().err
    assert code == 5, f"--work-order without --move is a plan refusal: {err}"
    assert "--work-order names the agent-adjusted order a `--move` plan" in err


def test_a_pin_without_another_way_in_is_still_exit_5(capsys):
    """035: `--pin` alone answers about the report it needs, not about missing input."""
    code = cli.main(["edit", "plan", "--pin", "1"])
    err = capsys.readouterr().err
    assert code == 5, f"--pin's own refusal precedes the no-input gate: {err}"
    assert "--pin selects one of a **report's** findings" in err


# ---------------------------------------------------------------------------
# 3. the §4 table and the catalogue say the same risk, row by row
# ---------------------------------------------------------------------------


def _table_rows() -> dict[str, list[tuple[str, str]]]:
    """§4's action rows -> [(owner, risk)], with the table's bold markup removed."""
    lines = BRIDGE_DOC.read_text(encoding="utf-8").splitlines()
    start = next(
        index for index, line in enumerate(lines)
        if line.startswith("| action | owner | risk |")
    )
    rows: dict[str, list[tuple[str, str]]] = {}
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        match = re.match(r"^\| `([a-z][a-z0-9_.]*)` \| ([^|]+) \| ([^|]+) \|", line)
        if match is None:
            continue
        owner = match.group(2).strip()
        risk = match.group(3).strip().strip("*").strip()
        rows.setdefault(match.group(1), []).append((owner, risk))
    return rows


def test_the_doc_open_row_says_write_like_doc_focus():
    """568-B-02 / #44: `doc.open` moves the focus; `doc.focus` is the same kind."""
    rows = _table_rows()
    assert len(rows["doc.open"]) == 1, "docs/bridge.md §4 must carry exactly one doc.open row"
    assert rows["doc.open"][0][1] == "write", "doc.open changes which page the next call lands on"
    assert rows["doc.open"][0][1] == rows["doc.focus"][0][1]
    assert rows["doc.open"][0][1] == next(
        action.risk for action in ACTIONS if action.name == "doc.open"
    )


def test_every_action_row_in_the_bridge_table_matches_the_catalogue_risk():
    """The table is the caller's copy of `ACTIONS`; one drifted row is the defect."""
    rows = _table_rows()
    by_name = {action.name: action for action in ACTIONS}
    assert set(rows) == set(by_name), (
        f"the §4 table and the catalogue disagree on which actions exist: "
        f"doc-only {sorted(set(rows) - set(by_name))}, "
        f"catalogue-only {sorted(set(by_name) - set(rows))}"
    )
    mismatched = {
        name: (rows[name][0][1], by_name[name].risk)
        for name in rows
        if rows[name][0][1] != by_name[name].risk
    }
    assert not mismatched, f"docs/bridge.md §4 risk column vs protocol.ACTIONS: {mismatched}"
