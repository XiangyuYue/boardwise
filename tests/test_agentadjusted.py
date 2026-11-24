"""Agent-adjusted move work orders: semantic intent, existing move-block guards."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import pagecompiler
from boardwise.engines.agentadjusted import (
    PAGE_LOCK_KEYS,
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
# carry one extra segment: the same group's **page** locks for the existing
# PresentationSpec compiler. Page locks, because the measured pose is a page
# pose: `pagecompiler.page_presentation_view` translates a module lock by its
# module's offset and passes a page lock as it is, so a module-scope segment
# would land the part at pose + delta + offset on every page whose module is not
# at the origin. It is opted into, never automatic, and it proves neither live
# guard.


def _posed_evidence(instances=None):
    """Evidence that states page poses — what a lock needs, and what the
    v4-facts sidecar (identity and rotation only) does not carry.

    The default rows are in the natural pose a page lock can keep: rotation 0,
    not mirrored. A page lock pins a position, so any other pose is a refusal
    (566-B-2), tested separately below; keeping a rotated part here would make
    every success test depend on the silent re-pose the guard now refuses.
    """
    rows = instances or [
        {"designator": "U30", "partId": "part-u30", "pageUuid": "page-p5",
         "page": "P5", "rotation": 0, "isMirror": False, "x": 100.0, "y": 200.0},
        {"designator": "R31", "partId": "part-r31", "pageUuid": "page-p5",
         "page": "P5", "rotation": 0, "isMirror": False, "x": 140.0, "y": 200.0},
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


def _group_presentation(*modules):
    """The page's PresentationSpec, as far as member proof goes: module -> parts.

    A page lock moves the named part's **whole module** (the page derives the
    module origin from the lock point), so the spec's module membership is the
    only proof of which parts move together. These specs carry the modules and
    nothing else: no locks, no flow, no grammar.
    """
    return PresentationSpec.from_dict({
        "modules": [
            {"id": module_id, "parts": list(parts), "role": "core"}
            for module_id, parts in modules
        ],
    })


def _two_module_evidence():
    """The B-1 scene in miniature: a rigid sense pair and a pwr pair on one page."""
    return _posed_evidence([
        {"designator": "R1", "partId": "part-r1", "pageUuid": "page-p5",
         "page": "P5", "rotation": 0, "isMirror": False, "x": 410.0, "y": 565.0},
        {"designator": "R2", "partId": "part-r2", "pageUuid": "page-p5",
         "page": "P5", "rotation": 0, "isMirror": False, "x": 410.0, "y": 600.0},
        {"designator": "C1", "partId": "part-c1", "pageUuid": "page-p5",
         "page": "P5", "rotation": 0, "isMirror": False, "x": 500.0, "y": 600.0},
        {"designator": "C2", "partId": "part-c2", "pageUuid": "page-p5",
         "page": "P5", "rotation": 0, "isMirror": False, "x": 500.0, "y": 635.0},
    ])


def _two_module_presentation():
    return _group_presentation(("sense", ["R1", "R2"]), ("pwr", ["C1", "C2"]))


def _moved_group_evidence(rotation=0, is_mirror=False):
    """A complete two-part module whose first part carries the pose under test."""
    return _posed_evidence([
        {"designator": "R1", "partId": "part-r1", "pageUuid": "page-p5",
         "page": "P5", "rotation": rotation, "isMirror": is_mirror,
         "x": 410.0, "y": 565.0},
        {"designator": "R2", "partId": "part-r2", "pageUuid": "page-p5",
         "page": "P5", "rotation": 0, "isMirror": False, "x": 410.0, "y": 600.0},
    ])


def _moved_group_presentation():
    return _group_presentation(("sense", ["R1", "R2"]))


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
        presentation=_group_presentation(("mcu-1", ["U30", "R31"])),
    )
    assert list(work) == [*DEFAULT_KEYS, "recompileWithLocks"]
    section = work["recompileWithLocks"]
    # The moved parts, all of them, at the measured page pose plus the delta,
    # as page locks: no rotation (a page lock pins a position, not a pose).
    assert section["locks"] == [
        {"partId": "U30", "x": 110.0, "y": 205.0, "scope": "page"},
        {"partId": "R31", "x": 150.0, "y": 205.0, "scope": "page"},
    ]
    assert [lock["partId"] for lock in section["locks"]] == ["U30", "R31"]
    assert section["designators"] == ["U30", "R31"]
    assert section["partIds"] == ["part-u30", "part-r31"]
    assert section["pageUuid"] == "page-p5"
    # Page locks only: the closed key set, and no rotation on any of them.
    for lock in section["locks"]:
        assert set(lock) == set(PAGE_LOCK_KEYS)
        assert lock["scope"] == "page"
        assert "rotation" not in lock
    assert section["lockScope"] == "page"
    assert "scope=page" in section["lockContract"]
    assert "rotation" in section["lockContract"]
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
        presentation=_group_presentation(("rail", ["R30", "R31", "R32"])),
    )
    locks = work["recompileWithLocks"]["locks"]
    assert [lock["partId"] for lock in locks] == ["R30", "R31", "R32"]
    assert len({lock["partId"] for lock in locks}) == 3
    assert work["recompileWithLocks"]["partIds"] == ["same-device"] * 3


def test_recompile_strategy_uses_the_declared_v4_pose_plus_delta():
    """The real sidecar now carries the COMPONENT's own x/y: locks use them as-is.

    U1 is declared at (300, 500) and U2 at (400, 500) in the fixture. The lock is
    x plus dx and the shared _page_y canvas conversion of that y plus dy — no
    second flip, no snap, no default, and no rotation: the pose stays the module
    drawing's, which is what a page lock means. The fixture's page module names
    both parts, so both are named here: a page lock moves the whole module.
    """
    evidence = _evidence()
    u1 = next(
        item for item in evidence["pageGroups"][0]["instances"]
        if item["designator"] == "U1"
    )
    assert (u1["x"], u1["y"]) == (300.0, 500.0)
    work = propose_agent_adjusted_move(
        evidence, ["U1", "U2"], 10.0, 5.0, "Free the left lane.",
        strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
        presentation=_group_presentation(("mcu-1", ["U1", "U2"])),
    )
    section = work["recompileWithLocks"]
    assert section["locks"] == [
        {"partId": "U1", "x": 310.0, "y": 505.0, "scope": "page"},
        {"partId": "U2", "x": 410.0, "y": 505.0, "scope": "page"},
    ]
    assert section["pageUuid"] == "page-1"
    for lock in section["locks"]:
        assert set(lock) == set(PAGE_LOCK_KEYS)
        assert "rotation" not in lock
    assert section["lockScope"] == "page"
    assert work["targetFreeProven"] is False
    assert work["netlistIdentityProven"] is False


def test_the_page_view_never_translates_these_locks_a_second_time():
    """The release blocker: a module lock is pose + delta, and the page view adds
    its module's offset on top of that — silently, and only on pages whose module
    is not at the origin. A page lock is already a page coordinate and is passed
    through as it is, so the segment states each lock at ``scope: page``."""
    offset = {"mcu-1": (140.0, 200.0)}
    work = propose_agent_adjusted_move(
        _posed_evidence(), ["U30", "R31"], 10.0, 5.0, "Free the left lane.",
        strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
        presentation=_group_presentation(("mcu-1", ["U30", "R31"])),
    )
    locks = work["recompileWithLocks"]["locks"]
    presentation = PresentationSpec.from_dict({
        "modules": [{"id": "mcu-1", "parts": ["U30", "R31"], "role": "mcu"}],
        # The segment's own locks, read back through the schema: a page lock
        # states scope and no rotation, so this parse is the shape proof too.
        "userLocks": [*locks],
    })
    view = pagecompiler.page_presentation_view(
        presentation, presentation.modules, offset,
    )
    landed = {lock.part_id: (lock.x, lock.y, lock.scope, lock.rotation)
              for lock in view.user_locks}
    assert landed == {
        "U30": (110.0, 205.0, "page", 0.0),
        "R31": (150.0, 205.0, "page", 0.0),
    }, "a page lock is page coordinates: the module's offset is never added to it"
    # The control, in its own spec: the very same numbers as a *module* lock are
    # moved by that offset, which is the whole reason the segment may not state
    # one.
    control = PresentationSpec.from_dict({
        "modules": [{"id": "mcu-1", "parts": ["U30", "R31"], "role": "mcu"}],
        "userLocks": [{"partId": "R31", "x": 150.0, "y": 205.0, "rotation": 90}],
    })
    (module_lock,) = pagecompiler.page_presentation_view(
        control, control.modules, offset,
    ).user_locks
    assert (module_lock.x, module_lock.y, module_lock.scope) == (290.0, 405.0, "module")
    assert module_lock.rotation == 90.0


def test_recompile_strategy_refuses_a_part_the_evidence_gives_no_pose():
    # Evidence whose records state no x/y: a lock coordinate would be
    # fabricated, so the alternative refuses naming the part.
    with pytest.raises(ValueError, match=r"no x/y pose for U1"):
        propose_agent_adjusted_move(
            _unposed_evidence(), ["U1"], 10.0, 0.0, "reason",
            strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
            presentation=_group_presentation(("mcu-1", ["U1"])),
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
            presentation=_group_presentation(("mcu-1", ["U30", "R31"])),
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
    # 591: the saved order names its own file, so its nextCommand can be run as
    # it stands; the four flags the engine spells are unchanged.
    assert work["nextCommand"] == [
        "boardwise", "edit", "plan", "--move",
        "--designators", "U30,R31", "--dx", "10", "--dy", "5",
        "--work-order", str(out),
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
    # The member proof is optional on the command line: only the opt-in
    # strategy needs it, so a direct-move invocation parses without it.
    assert parsed.presentation == ""


def test_move_propose_cli_forwards_an_explicit_recompile_strategy(tmp_path, capsys):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence()), encoding="utf-8")
    presentation_path = tmp_path / "presentation.json"
    _group_presentation(("mcu-1", ["U1", "U2"])).dump(presentation_path)
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "U1,U2", "--dx", "10", "--dy", "5",
        "--reason", "Free the left lane.", "--strategy", STRATEGY_RECOMPILE_WITH_LOCKS,
        "--presentation", str(presentation_path), "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    work = json.loads(out.read_text(encoding="utf-8"))
    # The CLI writes `sort_keys=True`, so compare the key set, not file order.
    assert sorted(work) == sorted([*DEFAULT_KEYS, "recompileWithLocks"])
    section = work["recompileWithLocks"]
    assert section["strategy"] == STRATEGY_RECOMPILE_WITH_LOCKS
    assert section["locks"] == [
        {"partId": "U1", "x": 310.0, "y": 505.0, "scope": "page"},
        {"partId": "U2", "x": 410.0, "y": 505.0, "scope": "page"},
    ]
    assert section["pageUuid"] == "page-1"
    assert section["lockScope"] == "page"
    for lock in section["locks"]:
        assert set(lock) == set(PAGE_LOCK_KEYS) and "rotation" not in lock
    assert work["nextCommand"][:4] == ["boardwise", "edit", "plan", "--move"]
    assert work["targetFreeProven"] is False
    assert work["netlistIdentityProven"] is False


def test_move_propose_cli_default_strategy_is_byte_identical_to_naming_it(
    tmp_path, capsys,
):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_posed_evidence()), encoding="utf-8")
    # One output path for both runs: since 591 the saved order names the file it
    # was saved to, so two different paths would differ in `nextCommand` alone —
    # and the claim here is about the strategy, not about the output file name.
    order = tmp_path / "order.json"
    base = [
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "U30,R31", "--dx", "10", "--dy", "5",
        "--reason", "Free the left lane.",
    ]
    assert cli.main([*base, "-o", str(order)]) == 0
    capsys.readouterr()
    first = order.read_bytes()
    assert cli.main([
        *base, "--strategy", STRATEGY_DIRECT, "-o", str(order),
    ]) == 0
    capsys.readouterr()
    assert order.read_bytes() == first
    assert sorted(json.loads(order.read_text(encoding="utf-8"))) == sorted(DEFAULT_KEYS)


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
    presentation_path = tmp_path / "presentation.json"
    _group_presentation(("mcu-1", ["U1"])).dump(presentation_path)
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "U1", "--dx", "10", "--dy", "0",
        "--reason", "reason", "--strategy", STRATEGY_RECOMPILE_WITH_LOCKS,
        "--presentation", str(presentation_path), "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 5
    assert "no x/y pose for U1" in printed.err
    assert not out.exists()



# --- 566-B-1: a page lock moves a whole module, so the group must prove members
#
# The page compiler derives a module's origin from a page lock point
# (`pagecompiler._page_origins`), so locking one part is moving the module: every
# unnamed companion travels with it, and the page packer re-places the modules
# the group does not name. A work order that names one part of a rigid module is
# therefore a subset claim, and the only honest proof of membership is the page's
# own PresentationSpec — the evidence sidecar carries pages, not modules.


def test_recompile_strategy_refuses_without_the_presentation_spec():
    """No spec, no member proof: the order could name one part and move the rest."""
    with pytest.raises(ValueError) as excinfo:
        propose_agent_adjusted_move(
            _two_module_evidence(), ["R1", "R2"], 10.0, -15.0, "reason",
            strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
        )
    message = str(excinfo.value)
    assert "needs the page's PresentationSpec" in message
    assert "--presentation" in message
    assert "whole module" in message
    # The default strategy still needs nothing of the kind.
    work = propose_agent_adjusted_move(
        _two_module_evidence(), ["R1", "R2"], 10.0, -15.0, "reason",
    )
    assert list(work) == list(DEFAULT_KEYS)


def test_recompile_strategy_refuses_a_module_subset_and_names_the_companion():
    with pytest.raises(ValueError) as excinfo:
        propose_agent_adjusted_move(
            _two_module_evidence(), ["R1"], 10.0, -15.0, "reason",
            strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
            presentation=_two_module_presentation(),
        )
    message = str(excinfo.value)
    assert "sense" in message and "R1" in message
    assert "R2" in message, "the companion that would move silently must be named"
    assert "C1" not in message and "C2" not in message, "only the claimed module is judged"
    assert "direct move" in message
    assert "R2" in message and "R1" in message


def test_recompile_strategy_refuses_a_part_the_spec_gives_no_module():
    with pytest.raises(ValueError, match=r"no module for R1"):
        propose_agent_adjusted_move(
            _two_module_evidence(), ["R1", "R2"], 10.0, 0.0, "reason",
            strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
            presentation=_group_presentation(("sense", ["R2"]), ("pwr", ["C1", "C2"])),
        )


def test_recompile_strategy_accepts_two_complete_modules_and_says_what_is_unproven():
    """The positive control: a multi-module group, every member named."""
    work = propose_agent_adjusted_move(
        _two_module_evidence(), ["R1", "R2", "C1", "C2"], 10.0, -15.0, "reason",
        strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
        presentation=_two_module_presentation(),
    )
    section = work["recompileWithLocks"]
    assert section["locks"] == [
        {"partId": "R1", "x": 420.0, "y": 550.0, "scope": "page"},
        {"partId": "R2", "x": 420.0, "y": 585.0, "scope": "page"},
        {"partId": "C1", "x": 510.0, "y": 585.0, "scope": "page"},
        {"partId": "C2", "x": 510.0, "y": 620.0, "scope": "page"},
    ]
    for lock in section["locks"]:
        assert set(lock) == set(PAGE_LOCK_KEYS)
        assert "rotation" not in lock
    review = " ".join(section["presentationSpecReview"])
    # Where the member proof came from ...
    assert "member proof" in review and "PresentationSpec" in review
    # ... and what the order still cannot promise: the unselected modules move
    # with the page packer, so the whole plan is what a human reviews.
    assert "pwr" in review, "a module the group does not name must be disclosed"
    assert "whole recompiled plan" in review
    assert "does not claim" in review
    assert section["automatic"] is False
    assert work["targetFreeProven"] is False
    assert work["netlistIdentityProven"] is False


def test_recompile_strategy_accepts_one_complete_module_and_reports_the_rest():
    work = propose_agent_adjusted_move(
        _two_module_evidence(), ["R1", "R2"], 10.0, -15.0, "reason",
        strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
        presentation=_two_module_presentation(),
    )
    section = work["recompileWithLocks"]
    assert [lock["partId"] for lock in section["locks"]] == ["R1", "R2"]
    review = " ".join(section["presentationSpecReview"])
    assert "pwr" in review


# --- 566-B-2: a page lock pins a position, never a pose ----------------------


@pytest.mark.parametrize("rotation", [90, 270, -90, 180])
def test_recompile_strategy_refuses_a_rotation_a_page_lock_cannot_keep(rotation):
    with pytest.raises(ValueError) as excinfo:
        propose_agent_adjusted_move(
            _moved_group_evidence(rotation=rotation), ["R1", "R2"], 10.0, 0.0,
            "reason", strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
            presentation=_moved_group_presentation(),
        )
    message = str(excinfo.value)
    assert f"rotation {rotation}" in message
    assert "page lock pins a position, not a pose" in message
    assert "direct move" in message


def test_recompile_strategy_refuses_a_mirrored_part():
    with pytest.raises(ValueError) as excinfo:
        propose_agent_adjusted_move(
            _moved_group_evidence(is_mirror=True), ["R1", "R2"], 10.0, 0.0,
            "reason", strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
            presentation=_moved_group_presentation(),
        )
    message = str(excinfo.value)
    assert "mirrored" in message
    assert "page lock pins a position, not a pose" in message
    assert "direct move" in message


@pytest.mark.parametrize("rotation", [float("nan"), float("inf"), "90", None, True])
def test_recompile_strategy_refuses_a_rotation_it_cannot_read(rotation):
    """NaN, inf, a string and a bool are not rotations; none may pass through."""
    with pytest.raises(ValueError) as excinfo:
        propose_agent_adjusted_move(
            _moved_group_evidence(rotation=rotation), ["R1", "R2"], 10.0, 0.0,
            "reason", strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
            presentation=_moved_group_presentation(),
        )
    message = str(excinfo.value)
    assert "finite" in message
    assert "page lock pins a position, not a pose" in message
    assert "direct move" in message


@pytest.mark.parametrize("rotation", [0, 360, -360, 720])
def test_recompile_strategy_accepts_rotations_that_are_the_same_pose(rotation):
    work = propose_agent_adjusted_move(
        _moved_group_evidence(rotation=rotation), ["R1", "R2"], 10.0, 0.0,
        "reason", strategy=STRATEGY_RECOMPILE_WITH_LOCKS,
        presentation=_moved_group_presentation(),
    )
    assert work["recompileWithLocks"]["locks"] == [
        {"partId": "R1", "x": 420.0, "y": 565.0, "scope": "page"},
        {"partId": "R2", "x": 420.0, "y": 600.0, "scope": "page"},
    ]


def test_the_direct_move_still_takes_a_rotated_mirrored_part():
    """The pose refusal belongs to the lock segment only: the direct move moves
    the part as it stands, so nothing about it changes."""
    work = propose_agent_adjusted_move(
        _moved_group_evidence(rotation=90, is_mirror=True), ["R1", "R2"],
        10.0, 0.0, "reason",
    )
    assert list(work) == list(DEFAULT_KEYS)
    assert "recompileWithLocks" not in work
    assert work["instances"][0]["rotation"] == 90
    assert work["instances"][0]["isMirror"] is True


# --- CLI: `--presentation` is the recompile proof, never a direct-move input --


def test_move_propose_cli_refuses_recompile_without_the_presentation(tmp_path, capsys):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_two_module_evidence()), encoding="utf-8")
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "R1,R2", "--dx", "10", "--dy", "0",
        "--reason", "reason", "--strategy", STRATEGY_RECOMPILE_WITH_LOCKS,
        "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 5
    assert "PresentationSpec" in printed.err
    assert "--presentation" in printed.err
    assert not out.exists()


def test_move_propose_cli_refuses_a_module_subset_naming_the_companion(
    tmp_path, capsys,
):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_two_module_evidence()), encoding="utf-8")
    presentation_path = tmp_path / "presentation.json"
    _two_module_presentation().dump(presentation_path)
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "R1", "--dx", "10", "--dy", "0",
        "--reason", "reason", "--strategy", STRATEGY_RECOMPILE_WITH_LOCKS,
        "--presentation", str(presentation_path), "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 5
    assert "R2" in printed.err
    assert "sense" in printed.err
    assert not out.exists()


def test_move_propose_cli_accepts_two_complete_modules(tmp_path, capsys):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_two_module_evidence()), encoding="utf-8")
    presentation_path = tmp_path / "presentation.json"
    _two_module_presentation().dump(presentation_path)
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "R1,R2,C1,C2", "--dx", "10", "--dy", "-15",
        "--reason", "reason", "--strategy", STRATEGY_RECOMPILE_WITH_LOCKS,
        "--presentation", str(presentation_path), "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    section = json.loads(out.read_text(encoding="utf-8"))["recompileWithLocks"]
    assert [lock["partId"] for lock in section["locks"]] == ["R1", "R2", "C1", "C2"]
    assert "pwr" in " ".join(section["presentationSpecReview"])


def test_move_propose_cli_refuses_a_pose_a_page_lock_cannot_keep(tmp_path, capsys):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(_moved_group_evidence(rotation=270, is_mirror=True)),
        encoding="utf-8",
    )
    presentation_path = tmp_path / "presentation.json"
    _moved_group_presentation().dump(presentation_path)
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "R1,R2", "--dx", "10", "--dy", "0",
        "--reason", "reason", "--strategy", STRATEGY_RECOMPILE_WITH_LOCKS,
        "--presentation", str(presentation_path), "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 5
    assert "page lock pins a position, not a pose" in printed.err
    assert "direct move" in printed.err
    assert not out.exists()


def test_move_propose_cli_direct_move_bytes_ignore_the_presentation(
    tmp_path, capsys,
):
    """`--presentation` is read, but a direct move's document is the old one."""
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_two_module_evidence()), encoding="utf-8")
    presentation_path = tmp_path / "presentation.json"
    _two_module_presentation().dump(presentation_path)
    # One output path for both runs (591: the saved order names its own file).
    order = tmp_path / "order.json"
    base = [
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "R1,R2", "--dx", "10", "--dy", "0", "--reason", "reason",
    ]
    assert cli.main([*base, "-o", str(order)]) == 0
    capsys.readouterr()
    first = order.read_bytes()
    assert cli.main([
        *base, "--presentation", str(presentation_path), "-o", str(order),
    ]) == 0
    capsys.readouterr()
    assert order.read_bytes() == first
    assert sorted(json.loads(order.read_text(encoding="utf-8"))) == sorted(DEFAULT_KEYS)


def test_move_propose_cli_refuses_an_unreadable_presentation_before_any_output(
    tmp_path, capsys,
):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_two_module_evidence()), encoding="utf-8")
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "R1,R2", "--dx", "10", "--dy", "0",
        "--reason", "reason", "--strategy", STRATEGY_RECOMPILE_WITH_LOCKS,
        "--presentation", str(tmp_path / "missing.json"), "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 2
    assert "cannot read the presentation" in printed.err
    assert not out.exists()


def test_move_propose_cli_refuses_a_presentation_that_is_not_a_spec(
    tmp_path, capsys,
):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_two_module_evidence()), encoding="utf-8")
    presentation_path = tmp_path / "presentation.json"
    presentation_path.write_text(json.dumps({
        "modules": [{"id": "sense", "parts": [], "role": "core"}],
    }), encoding="utf-8")
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "R1,R2", "--dx", "10", "--dy", "0",
        "--reason", "reason", "--strategy", STRATEGY_RECOMPILE_WITH_LOCKS,
        "--presentation", str(presentation_path), "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 5
    assert "parts" in printed.err
    assert not out.exists()


def test_move_propose_cli_refuses_presentation_json_that_is_not_json(
    tmp_path, capsys,
):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_two_module_evidence()), encoding="utf-8")
    presentation_path = tmp_path / "presentation.json"
    presentation_path.write_text("{not json", encoding="utf-8")
    out = tmp_path / "move.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence_path),
        "--designators", "R1,R2", "--dx", "10", "--dy", "0",
        "--reason", "reason", "--strategy", STRATEGY_RECOMPILE_WITH_LOCKS,
        "--presentation", str(presentation_path), "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 2
    assert "invalid presentation JSON" in printed.err
    assert not out.exists()


def test_the_cli_contract_records_presentation_as_an_optional_move_propose_input():
    from tools.cli_contract import CONTRACT_PATH

    parser = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["parser"]
    draw = next(
        action["choices"]["draw"] for action in parser["actions"]
        if isinstance(action["choices"], dict) and "draw" in action["choices"]
    )
    subcommands = next(
        item for item in draw["actions"]
        if isinstance(item.get("choices"), dict) and "move-propose" in item["choices"]
    )
    move = subcommands["choices"]["move-propose"]
    option = next(
        item for item in move["actions"]
        if "--presentation" in item["optionStrings"]
    )
    assert option["dest"] == "presentation"
    assert option["required"] is False
    assert option["default"] == "''"
    assert "--presentation" in move["help"]
    assert "recompile-with-locks" in move["help"]
