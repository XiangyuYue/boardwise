"""Agent-adjusted move work orders: semantic intent, existing move-block guards."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.engines.agentadjusted import (
    LOCK_KEYS,
    STRATEGY_DIRECT,
    STRATEGY_RECOMPILE_WITH_LOCKS,
    propose_agent_adjusted_move,
)
from boardwise.engines.v4facts import presentation_evidence, read_v4_facts

FIXTURE = Path(__file__).parent / "fixtures" / "eprj3_synth"

#: The default order's fields, frozen: the opt-in strategy adds a key delimited
#: below and must never reshape or reorder these.
DEFAULT_KEYS = (
    "schema", "mode", "status", "source", "evidenceSchema", "designators",
    "delta", "semanticReason", "instances", "targetFreeProven",
    "netlistIdentityProven", "openQuestions", "guards", "nextCommand",
)


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


# --- the opt-in "recompile with locks" alternative (attachment refusals) -----
#
# The direct move is the order's own command and stays it. When the move-block
# planner refuses that move because a flag/label is attached, the order may
# carry one extra segment: the same group's module locks for the existing
# PresentationSpec compiler. It is opted into, never automatic, and it proves
# neither live guard.


def _posed_evidence(instances=None):
    """Evidence that states page poses — what a lock needs, and what the
    v4-facts sidecar (identity and rotation only) does not carry."""
    rows = instances or [
        {"designator": "U30", "partId": "part-u30", "pageUuid": "page-p5",
         "page": "P5", "rotation": 0, "x": 100.0, "y": 200.0},
        {"designator": "R31", "partId": "part-r31", "pageUuid": "page-p5",
         "page": "P5", "rotation": 90, "x": 140.0, "y": 200.0},
    ]
    return {
        "schema": "boardwise.v4-presentation-evidence/1",
        "source": "synth",
        "pageGroups": [{"pageUuid": "page-p5", "page": "P5", "instances": rows}],
        "openQuestions": [],
    }


def _unposed_evidence():
    """The same shape, but the records declare no x/y (evidence has no pose)."""
    return {
        "schema": "boardwise.v4-presentation-evidence/1",
        "source": "synth",
        "pageGroups": [{"pageUuid": "page-p5", "page": "P5", "instances": [
            {"designator": "U1", "partId": "part-u1", "pageUuid": "page-p5",
             "page": "P5", "rotation": 0},
        ]}],
        "openQuestions": [],
    }


def test_the_strategy_defaults_to_the_direct_move_and_adds_no_section():
    work = propose_agent_adjusted_move(
        _posed_evidence(), ["U30", "R31"], 10.0, 5.0, "Free the left lane.",
    )
    assert list(work) == list(DEFAULT_KEYS)
    assert "recompileWithLocks" not in work
    assert work["nextCommand"] == [
        "boardwise", "edit", "plan", "--move",
        "--designators", "U30,R31", "--dx", "10", "--dy", "5",
    ]
    assert work["targetFreeProven"] is False
    assert work["netlistIdentityProven"] is False
    assert work["status"] == "proposed"
    # Naming the direct move is the same document as saying nothing.
    assert propose_agent_adjusted_move(
        _posed_evidence(), ["U30", "R31"], 10.0, 5.0, "Free the left lane.",
        strategy=STRATEGY_DIRECT,
    ) == work


def test_recompile_strategy_locks_the_whole_group_at_pose_plus_delta():
    evidence = _posed_evidence()
    default = propose_agent_adjusted_move(
        evidence, ["U30", "R31"], 10.0, 5.0, "Free the left lane.",
    )
    work = propose_agent_adjusted_move(
        evidence, ["U30", "R31"], 10.0, 5.0, "Free the left lane.",
        strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
    )
    assert list(work) == [*DEFAULT_KEYS, "recompileWithLocks"]
    section = work["recompileWithLocks"]
    # The moved parts, all of them, at the measured pose plus the delta.
    assert [lock["partId"] for lock in section["locks"]] == ["U30", "R31"]
    assert [(lock["x"], lock["y"], lock["rotation"]) for lock in section["locks"]] == [
        (110.0, 205.0, 0.0), (150.0, 205.0, 90.0),
    ]
    assert section["designators"] == ["U30", "R31"]
    assert section["partIds"] == ["part-u30", "part-r31"]
    assert section["pageUuid"] == "page-p5"
    # Module locks only: the closed key set, and no `scope` key on a lock (a
    # page lock states scope and may not carry a rotation).
    for lock in section["locks"]:
        assert set(lock) == set(LOCK_KEYS)
        assert "scope" not in lock
    assert section["lockScope"] == "module"
    assert "scope=page" in section["lockContract"]
    # An alternative somebody chooses, never a step that runs itself.
    assert section["automatic"] is False
    assert "refused" in section["appliesOnlyWhen"]
    # The whole group is reviewed, not the MCU alone.
    review = " ".join(section["presentationSpecReview"])
    assert "group, not the MCU alone" in review
    assert "flag" in review and "label" in review
    # Apply lands on the original page and reuses it.
    apply_step = section["followUp"][-1]["command"]
    assert apply_step[:4] == ["boardwise", "draw", "apply", "<plan.json>"]
    assert apply_step[apply_step.index("--page") + 1] == "page-p5"
    assert section["doesNotProve"] == ["targetFreeProven", "netlistIdentityProven"]
    # None of the direct move's guarantees move: command, status and proofs.
    assert work["nextCommand"] == default["nextCommand"]
    assert work["status"] == default["status"] == "proposed"
    assert work["mode"] == default["mode"] == "agent-adjusted"
    assert work["designators"] == default["designators"]
    assert work["instances"] == default["instances"]
    assert work["targetFreeProven"] is False
    assert work["netlistIdentityProven"] is False


def test_recompile_locks_use_designators_when_device_part_ids_repeat():
    evidence = _posed_evidence([
        {"designator": "R30", "partId": "same-device", "pageUuid": "page-p5",
         "page": "P5", "rotation": 0, "x": 10.0, "y": 20.0},
        {"designator": "R31", "partId": "same-device", "pageUuid": "page-p5",
         "page": "P5", "rotation": 0, "x": 20.0, "y": 30.0},
        {"designator": "R32", "partId": "same-device", "pageUuid": "page-p5",
         "page": "P5", "rotation": 0, "x": 30.0, "y": 40.0},
    ])
    work = propose_agent_adjusted_move(
        evidence, ["R30", "R31", "R32"], 5.0, 0.0, "Make room for the rail flag.",
        strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
    )
    locks = work["recompileWithLocks"]["locks"]
    assert [lock["partId"] for lock in locks] == ["R30", "R31", "R32"]
    assert len({lock["partId"] for lock in locks}) == 3
    assert work["recompileWithLocks"]["partIds"] == ["same-device"] * 3


def test_recompile_strategy_uses_the_declared_v4_pose_plus_delta():
    """The real sidecar now carries the COMPONENT's own x/y: locks use them as-is.

    U1 is declared at (300, -500) in the fixture. The lock is x plus dx and
    the shared _page_y canvas conversion of that y plus dy — no second flip,
    no snap, no default, and the rotation stays the instance's own value.
    """
    evidence = _evidence()
    u1 = next(
        item for item in evidence["pageGroups"][0]["instances"]
        if item["designator"] == "U1"
    )
    assert (u1["x"], u1["y"]) == (300.0, 500.0)
    work = propose_agent_adjusted_move(
        evidence, ["U1"], 10.0, 5.0, "Free the left lane.",
        strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
    )
    section = work["recompileWithLocks"]
    assert [(lock["x"], lock["y"], lock["rotation"]) for lock in section["locks"]] == [
        (310.0, 505.0, 0.0),
    ]
    assert section["pageUuid"] == "page-1"
    assert set(section["locks"][0]) == set(LOCK_KEYS)
    assert "scope" not in section["locks"][0]
    assert work["targetFreeProven"] is False
    assert work["netlistIdentityProven"] is False


def test_recompile_strategy_refuses_a_part_the_evidence_gives_no_pose():
    # Evidence whose records state no x/y: a lock coordinate would be
    # fabricated, so the alternative refuses naming the part.
    with pytest.raises(ValueError, match=r"no x/y pose for U1"):
        propose_agent_adjusted_move(
            _unposed_evidence(), ["U1"], 10.0, 0.0, "reason",
            strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
        )


def test_recompile_strategy_refuses_a_group_that_spans_pages():
    evidence = _posed_evidence([
        {"designator": "U30", "partId": "part-u30", "pageUuid": "page-p5",
         "page": "P5", "rotation": 0, "x": 100.0, "y": 200.0},
        {"designator": "R31", "partId": "part-r31", "pageUuid": "page-p6",
         "page": "P6", "rotation": 0, "x": 10.0, "y": 20.0},
    ])
    with pytest.raises(ValueError, match=r"span pages.*page-p5, page-p6"):
        propose_agent_adjusted_move(
            evidence, ["U30", "R31"], 10.0, 0.0, "reason",
            strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
        )


def test_an_unknown_strategy_is_refused_by_name():
    with pytest.raises(ValueError, match=r"strategy is 'automatic'.*recompile-with-locks"):
        propose_agent_adjusted_move(
            _posed_evidence(), ["U30"], 10.0, 0.0, "reason", strategy="automatic",
        )


def test_move_propose_cli_output_still_has_no_recompile_section(tmp_path, capsys):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_posed_evidence()), encoding="utf-8")
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "U30,R31", "--dx", "10", "--dy", "5",
        "--reason", "Free the left lane.", "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    work = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(work) == sorted(DEFAULT_KEYS)
    assert work["nextCommand"] == [
        "boardwise", "edit", "plan", "--move",
        "--designators", "U30,R31", "--dx", "10", "--dy", "5",
    ]
    assert work["targetFreeProven"] is False
    assert work["netlistIdentityProven"] is False


# --- CLI: the optional strategy is forwarded, the default bytes are frozen ----

def test_cli_registers_the_engine_strategy_vocabulary_and_the_direct_default():
    from boardwise.commands import draw as draw_commands
    from boardwise.engines.agentadjusted import STRATEGIES

    assert draw_commands.MOVE_STRATEGIES == STRATEGIES
    assert draw_commands.DEFAULT_MOVE_STRATEGY == STRATEGY_DIRECT
    parsed = cli.build_parser().parse_args([
        "draw", "move-propose", "--evidence", "e.json",
        "--designators", "U1", "--dx", "10", "--dy", "0", "--reason", "r",
    ])
    assert parsed.strategy == STRATEGY_DIRECT


def test_move_propose_cli_forwards_an_explicit_recompile_strategy(tmp_path, capsys):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence()), encoding="utf-8")
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "U1", "--dx", "10", "--dy", "5",
        "--reason", "Free the left lane.", "--strategy", STRATEGY_RECOMPILE_WITH_LOCKS,
        "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    work = json.loads(out.read_text(encoding="utf-8"))
    # The CLI writes `sort_keys=True`, so compare the key set, not file order.
    assert sorted(work) == sorted([*DEFAULT_KEYS, "recompileWithLocks"])
    section = work["recompileWithLocks"]
    assert section["strategy"] == STRATEGY_RECOMPILE_WITH_LOCKS
    assert [(lock["x"], lock["y"], lock["rotation"]) for lock in section["locks"]] == [
        (310.0, 505.0, 0.0),
    ]
    assert section["pageUuid"] == "page-1"
    for lock in section["locks"]:
        assert set(lock) == set(LOCK_KEYS) and "scope" not in lock
    assert work["nextCommand"][:4] == ["boardwise", "edit", "plan", "--move"]
    assert work["targetFreeProven"] is False
    assert work["netlistIdentityProven"] is False


def test_move_propose_cli_default_strategy_is_byte_identical_to_naming_it(
    tmp_path, capsys,
):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_posed_evidence()), encoding="utf-8")
    first = tmp_path / "default.json"
    second = tmp_path / "named.json"
    base = [
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "U30,R31", "--dx", "10", "--dy", "5",
        "--reason", "Free the left lane.",
    ]
    assert cli.main([*base, "-o", str(first)]) == 0
    capsys.readouterr()
    assert cli.main([
        *base, "--strategy", STRATEGY_DIRECT, "-o", str(second),
    ]) == 0
    capsys.readouterr()
    assert first.read_bytes() == second.read_bytes()
    assert sorted(json.loads(first.read_text(encoding="utf-8"))) == sorted(DEFAULT_KEYS)


def test_move_propose_cli_refuses_an_unknown_strategy_before_any_output(
    tmp_path, capsys,
):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_posed_evidence()), encoding="utf-8")
    out = tmp_path / "move.json"
    with pytest.raises(SystemExit) as excinfo:
        cli.main([
            "draw", "move-propose", "--evidence", str(evidence_path),
            "--designators", "U30", "--dx", "10", "--dy", "0",
            "--reason", "reason", "--strategy", "automatic", "-o", str(out),
        ])
    assert excinfo.value.code == 2
    assert not out.exists()


def test_move_propose_cli_refuses_a_lock_for_an_unposed_part(tmp_path, capsys):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_unposed_evidence()), encoding="utf-8")
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "U1", "--dx", "10", "--dy", "0",
        "--reason", "reason", "--strategy", STRATEGY_RECOMPILE_WITH_LOCKS,
        "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 5
    assert "no x/y pose for U1" in printed.err
    assert not out.exists()
