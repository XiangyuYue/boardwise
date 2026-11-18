"""Agent-adjusted move work orders: semantic intent, existing move-block guards."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.engines.agentadjusted import propose_agent_adjusted_move
from boardwise.engines.v4facts import presentation_evidence, read_v4_facts

FIXTURE = Path(__file__).parent / "fixtures" / "eprj3_synth"


def _evidence():
    return presentation_evidence(read_v4_facts(FIXTURE))


def test_move_work_order_keeps_semantics_and_marks_live_guards_unproven():
    work = propose_agent_adjusted_move(
        _evidence(), ["U1"], 10.0, 0.0,
        "Keep U1 with its local decoupling branch and free the left signal lane.",
    )
    assert work["schema"] == "boardwise.agent-adjusted-move/1"
    assert work["mode"] == "agent-adjusted"
    assert work["status"] == "proposed"
    assert work["delta"] == {"dx": 10.0, "dy": 0.0}
    assert work["instances"][0]["designator"] == "U1"
    assert work["instances"][0]["page"] == "P1"
    assert work["targetFreeProven"] is False
    assert work["netlistIdentityProven"] is False
    assert work["nextCommand"][:4] == ["boardwise", "edit", "plan", "--move"]
    assert work["openQuestions"]


def test_move_work_order_rejects_unknown_designators_off_grid_and_empty_reason():
    with pytest.raises(ValueError, match="U9"):
        propose_agent_adjusted_move(_evidence(), ["U9"], 10.0, 0.0, "reason")
    with pytest.raises(ValueError, match="grid"):
        propose_agent_adjusted_move(_evidence(), ["U1"], 2.5, 0.0, "reason")
    with pytest.raises(ValueError, match="reason"):
        propose_agent_adjusted_move(_evidence(), ["U1"], 10.0, 0.0, " ")


def test_move_propose_cli_writes_the_work_order(tmp_path, capsys):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence()), encoding="utf-8")
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "U1", "--dx", "10", "--dy", "0",
        "--reason", "Free the left signal lane.", "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    work = json.loads(out.read_text(encoding="utf-8"))
    assert work["mode"] == "agent-adjusted"
    assert work["targetFreeProven"] is False


def test_move_propose_cli_returns_five_for_an_unknown_designator(tmp_path, capsys):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence()), encoding="utf-8")
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "U9", "--dx", "10", "--dy", "0", "--reason", "reason",
    ])
    printed = capsys.readouterr()
    assert code == 5
    assert "U9" in printed.err


def _repeated_evidence():
    return {
        "schema": "boardwise.v4-presentation-evidence/1",
        "pageGroups": [
            {"instances": [{"designator": "U1", "partId": "a-u1", "pageUuid": "page-A"},
                           {"designator": "R1", "partId": "a-r1", "pageUuid": "page-A"}]},
            {"instances": [{"designator": "u1", "partId": "b-u1", "pageUuid": "page-B"}]},
        ],
    }


def test_move_work_order_refuses_ambiguous_selected_designator():
    with pytest.raises(ValueError, match=r"ambiguous.*U1"):
        propose_agent_adjusted_move(_repeated_evidence(), ["U1"], 10., 0., "reason")


def test_move_work_order_keeps_unique_selection_when_other_designators_repeat():
    work = propose_agent_adjusted_move(_repeated_evidence(), ["R1"], 10., 0., "reason")
    assert [item["partId"] for item in work["instances"]] == ["a-r1"]
    assert work["status"] == "proposed"
    assert work["targetFreeProven"] is False
    assert work["netlistIdentityProven"] is False


def test_move_propose_cli_refuses_ambiguity_without_writing(tmp_path, capsys):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_repeated_evidence()), encoding="utf-8")
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "U1", "--dx", "10", "--dy", "0",
        "--reason", "reason", "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 5
    assert "ambiguous" in printed.err and "U1" in printed.err
    assert not out.exists()
