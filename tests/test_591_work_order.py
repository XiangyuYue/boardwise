"""591 (W-R2): an agent-adjusted work order becomes an input, not a comment.

hole568 D-4 measured the gap this file closes: `draw move-propose` wrote
`mode: agent-adjusted` / `status: proposed`, but nothing downstream read them —
`nextCommand` was an argv line and `edit plan --move` never looked at the file, so
those fields could be changed to anything without a single red test.

The link is deliberately narrow:

* the saved order's `nextCommand` names the file it was saved to, so the command
  it prints can be run as it stands (an order printed to stdout names nothing);
* `edit plan --move --work-order work.json` reads the order and judges it
  **before the bridge is opened**: schema, mode, status, the group (same
  uppercase rule, item by item) and the delta must agree with the command;
* a plan that consumed one records `route: "agent-adjusted"` at the top level,
  and a plan that did not is the exact document it was.

`route` is where the proposal came from, not that it is right: the live
move-block guards (target free, wire redraw, netlist identity) are still the only
judge, and every refusal here is a named exit 5 with no traceback.
"""

from __future__ import annotations

import argparse
import json

import pytest

from boardwise import cli
from boardwise.core.changeplan import (
    MOVE_BLOCK_KIND,
    ChangePlan,
    ChangePlanError,
    PlanIsland,
    PlanMove,
    PlanSource,
    move_block_plan,
)
from boardwise.engines.agentadjusted import (
    SCHEMA as WORK_ORDER_SCHEMA,
    propose_agent_adjusted_move,
)
from test_037_moveblock import (  # the 037 fake page, reused (tests import each other)
    _model,
    _move_bridge,
    _stub_bridge,
    _stub_export,
)

NAMES = ("U1", "U2")


# --------------------------------------------------------------------------
# a real work order (the engine writes it) and the file the CLI reads
# --------------------------------------------------------------------------


def _evidence(names=NAMES):
    return {
        "schema": "boardwise.v4-presentation-evidence/1",
        "source": "page:P1",
        "pageGroups": [{"instances": [
            {"designator": name, "partId": f"p-{name}", "pageUuid": "page-1",
             "page": "P1"}
            for name in names
        ]}],
    }


def _order(*, names=NAMES, dx=100.0, dy=0.0, **overrides):
    work = propose_agent_adjusted_move(
        _evidence(names), list(names), dx, dy,
        "Free the left signal lane.",
    )
    work.update(overrides)
    return work


def _write(tmp_path, payload, name="work.json"):
    path = tmp_path / name
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    elif isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _argv(*, out, json_out, work_order=None, designators="U1,U2", dx="100", dy="0"):
    argv = ["edit", "plan", "--move", "--designators", designators,
            "--dx", dx, "--dy", dy, "-o", str(out), "--json", str(json_out)]
    if work_order is not None:
        argv.extend(["--work-order", str(work_order)])
    return argv


# --------------------------------------------------------------------------
# 1. the producer: the saved order names its own file
# --------------------------------------------------------------------------


def test_a_saved_order_names_the_file_it_was_saved_to(tmp_path, capsys):
    evidence = _write(tmp_path, _evidence(), "evidence.json")
    out = tmp_path / "work.json"
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence),
        "--designators", "U1,U2", "--dx", "100", "--dy", "0",
        "--reason", "Free the left signal lane.", "-o", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    work = json.loads(out.read_text(encoding="utf-8"))
    assert work["nextCommand"][:4] == ["boardwise", "edit", "plan", "--move"]
    assert work["nextCommand"][-2:] == ["--work-order", str(out)]
    # The four flags the engine itself spells are untouched and in order.
    assert work["nextCommand"][4:8] == ["--designators", "U1,U2", "--dx", "100"]


def test_an_order_printed_to_stdout_names_no_file_and_the_engine_is_unchanged(
        tmp_path, capsys):
    evidence = _write(tmp_path, _evidence(), "evidence.json")
    code = cli.main([
        "draw", "move-propose", "--evidence", str(evidence),
        "--designators", "U1,U2", "--dx", "100", "--dy", "0",
        "--reason", "Free the left signal lane.",
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    work = json.loads(printed.out)
    assert "--work-order" not in work["nextCommand"]
    # The engine's own document is the one 570/571 froze, field for field.
    assert work["nextCommand"] == [
        "boardwise", "edit", "plan", "--move",
        "--designators", "U1,U2", "--dx", "100", "--dy", "0",
    ]
    assert work == _order()


# --------------------------------------------------------------------------
# 2. the flag exists on `edit plan` (and only there)
# --------------------------------------------------------------------------


def _subparser(parser, *path):
    for name in path:
        actions = [item for item in parser._actions
                   if isinstance(item, argparse._SubParsersAction)]
        assert actions, f"{name} has no subcommands"
        parser = actions[0].choices[name]
    return parser


def test_edit_plan_registers_work_order():
    plan = _subparser(cli.build_parser(), "edit", "plan")
    flags = {option for action in plan._actions for option in action.option_strings}
    assert "--work-order" in flags
    # `draw move-propose` does not grow the flag: it writes the file the flag names.
    propose = _subparser(cli.build_parser(), "draw")
    propose_flags = {option for action in propose._actions
                     for option in action.option_strings}
    assert "--work-order" not in propose_flags


# --------------------------------------------------------------------------
# 3. every early refusal happens before any bridge call
# --------------------------------------------------------------------------


def _no_bridge(_args):
    raise AssertionError("the plan opened the bridge before judging the work order")


@pytest.mark.parametrize(
    "label, payload, keyword",
    [
        ("missing file", None, "cannot be read"),
        ("not JSON", "{not json", "is not JSON"),
        ("not UTF-8", b'\xff\xfe{"schema": 1}', "is not UTF-8"),
        ("not an object", ["schema"], "not an object"),
        ("wrong schema", {"schema": "boardwise.agent-adjusted-move/2"}, "schema is"),
        ("wrong mode", {"mode": "automatic"}, "mode is"),
        ("wrong status", {"status": "accepted"}, "status is"),
        ("a smaller group", {"designators": ["U1"]}, "names U1; the command names"),
        ("the same group reordered", {"designators": ["U2", "U1"]}, "names U2, U1"),
        ("a different dx", {"delta": {"dx": 5.0, "dy": 0.0}}, "the two disagree"),
        ("a different dy", {"delta": {"dx": 100.0, "dy": 5.0}}, "the two disagree"),
        ("a non-numeric dx", {"delta": {"dx": "100", "dy": 0.0}}, "delta.dx must be a number"),
        # 591B: the order's alternative route must say `automatic: false` itself
        # (hole568 D-4's last unread field).
        ("recompileWithLocks says automatic",
         {"recompileWithLocks": {"automatic": True}},
         "recompileWithLocks.automatic is True"),
        ("recompileWithLocks does not say",
         {"recompileWithLocks": {"locks": []}},
         "recompileWithLocks.automatic is None"),
        ("recompileWithLocks.automatic is 1",
         {"recompileWithLocks": {"automatic": 1}},
         "recompileWithLocks.automatic is 1"),
        ("recompileWithLocks.automatic is 0",
         {"recompileWithLocks": {"automatic": 0}},
         "recompileWithLocks.automatic is 0"),
        ("recompileWithLocks.automatic is a string",
         {"recompileWithLocks": {"automatic": "false"}},
         "recompileWithLocks.automatic is 'false'"),
        ("recompileWithLocks.automatic is null",
         {"recompileWithLocks": {"automatic": None}},
         "recompileWithLocks.automatic is None"),
        ("recompileWithLocks.automatic is a list",
         {"recompileWithLocks": {"automatic": [False]}},
         "recompileWithLocks.automatic is [False]"),
        ("recompileWithLocks is not an object",
         {"recompileWithLocks": ["automatic"]},
         "recompileWithLocks is a JSON list, not an object"),
    ],
)
def test_a_bad_work_order_is_refused_before_the_bridge(
        monkeypatch, tmp_path, capsys, label, payload, keyword):
    monkeypatch.setattr(cli, "_open_cli", _no_bridge)
    path = None
    if payload is not None:
        document = _order()
        if isinstance(payload, dict):
            document.update(payload)
        else:
            document = payload
        path = _write(tmp_path, document)
    work_order = path if path is not None else tmp_path / "absent.json"
    code = cli.main(_argv(out=tmp_path / "plan.json", json_out=tmp_path / "r.json",
                          work_order=work_order))
    printed = capsys.readouterr()
    assert code == 5, f"{label}: {printed.err}"
    assert keyword in printed.err, f"{label}: {printed.err}"
    assert "Traceback" not in printed.err
    assert not (tmp_path / "plan.json").exists()


def test_work_order_without_move_is_a_named_refusal(tmp_path, capsys):
    path = _write(tmp_path, _order())
    code = cli.main([
        "edit", "plan", "--file", str(tmp_path / "x.epro2"), "--rule", "x",
        "--designator", "U1", "--after", "2k", "--work-order", str(path),
    ])
    printed = capsys.readouterr()
    assert code == 5
    assert "--work-order names the agent-adjusted order a `--move` plan" in printed.err


# --------------------------------------------------------------------------
# 4. a consumed order: the plan says where it came from, the guards still judge
# --------------------------------------------------------------------------


def test_the_plan_records_the_route_and_the_live_guards_still_build_it(
        monkeypatch, tmp_path, capsys):
    _stub_bridge(monkeypatch, _move_bridge())
    _stub_export(monkeypatch, [_model(components=[("U1", ("", "")), ("U2", ("", ""))])])
    work_order = _write(tmp_path, _order())
    out = tmp_path / "plan.json"
    json_out = tmp_path / "result.json"
    code = cli.main(_argv(out=out, json_out=json_out, work_order=work_order))
    printed = capsys.readouterr()
    assert code == 0, printed.err
    assert f"route: agent-adjusted (work order {work_order})" in printed.out
    plan = ChangePlan.load(out)
    assert plan.route == "agent-adjusted"
    assert plan.change.kind == MOVE_BLOCK_KIND
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["route"] == "agent-adjusted"
    assert payload["change"]["kind"] == MOVE_BLOCK_KIND
    result = json.loads(json_out.read_text(encoding="utf-8"))
    assert result["route"] == "agent-adjusted"
    assert result["workOrder"] == str(work_order)


def test_the_group_is_compared_by_the_same_uppercase_rule(monkeypatch, tmp_path, capsys):
    _stub_bridge(monkeypatch, _move_bridge())
    _stub_export(monkeypatch, [_model(components=[("U1", ("", "")), ("U2", ("", ""))])])
    work = _order()
    work["designators"] = ["u1", "u2"]
    work_order = _write(tmp_path, work)
    out = tmp_path / "plan.json"
    code = cli.main(_argv(out=out, json_out=tmp_path / "r.json",
                          work_order=work_order, designators="u1,u2"))
    assert code == 0, capsys.readouterr().err
    assert ChangePlan.load(out).route == "agent-adjusted"


def test_a_locked_order_that_says_automatic_false_still_plans(monkeypatch, tmp_path, capsys):
    """591B: the alternative route's own `automatic: false` is what is required —
    the order stays consumable, and the plan is still the agent-adjusted one."""
    _stub_bridge(monkeypatch, _move_bridge())
    _stub_export(monkeypatch, [_model(components=[("U1", ("", "")), ("U2", ("", ""))])])
    work = _order()
    work["recompileWithLocks"] = {
        "automatic": False,
        "strategy": "recompile-with-locks",
        "locks": [{"partId": "p-U1", "x": 400.0, "y": 300.0, "scope": "page"}],
    }
    work_order = _write(tmp_path, work)
    out = tmp_path / "plan.json"
    json_out = tmp_path / "result.json"
    code = cli.main(_argv(out=out, json_out=json_out, work_order=work_order))
    printed = capsys.readouterr()
    assert code == 0, printed.err
    assert f"route: agent-adjusted (work order {work_order})" in printed.out
    assert ChangePlan.load(out).route == "agent-adjusted"
    result = json.loads(json_out.read_text(encoding="utf-8"))
    assert result["route"] == "agent-adjusted"
    assert result["workOrder"] == str(work_order)


def test_without_a_work_order_the_plan_is_the_document_it_was(monkeypatch, tmp_path, capsys):
    _stub_bridge(monkeypatch, _move_bridge())
    _stub_export(monkeypatch, [_model(components=[("U1", ("", "")), ("U2", ("", ""))])])
    out = tmp_path / "plan.json"
    json_out = tmp_path / "result.json"
    code = cli.main(_argv(out=out, json_out=json_out))
    printed = capsys.readouterr()
    assert code == 0, printed.err
    assert "route:" not in printed.out
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "route" not in payload
    assert list(payload) == [
        "planVersion", "source", "target", "change",
        "preconditions", "expectedPostcondition",
    ]
    result = json.loads(json_out.read_text(encoding="utf-8"))
    assert "route" not in result and "workOrder" not in result
    assert ChangePlan.load(out).route == ""


# --------------------------------------------------------------------------
# 5. the ChangePlan field: optional on read, closed on values, absent on write
# --------------------------------------------------------------------------


def _move_plan(**kwargs):
    return move_block_plan(
        PlanSource(input_sha256="a" * 64, page_uuid="page-1"),
        moves=[PlanMove(designator="U1", primitive_id="p-U1",
                        from_at=(300.0, 300.0), from_rotation=0.0,
                        to_at=(400.0, 300.0))],
        wire_ops=[],
        islands=[PlanIsland(pin="U1.1", mates=["U2.1"])],
        designators=["U1"],
        dx=100.0, dy=0.0,
        **kwargs,
    )


def test_a_move_plan_writes_a_route_only_when_it_has_one(tmp_path):
    plain = _move_plan().to_jsonable()
    assert "route" not in plain
    stated = _move_plan(route="agent-adjusted")
    payload = stated.to_jsonable()
    assert payload["route"] == "agent-adjusted"
    # The rest of the document is untouched: adding the route adds one key.
    assert {key: value for key, value in payload.items() if key != "route"} == plain
    path = tmp_path / "plan.json"
    stated.dump(path)
    loaded = ChangePlan.load(path)
    assert loaded.route == "agent-adjusted"
    assert loaded.to_jsonable() == payload


def test_a_plan_without_a_route_round_trips_byte_for_byte(tmp_path):
    path = tmp_path / "plan.json"
    _move_plan().dump(path)
    before = path.read_bytes()
    ChangePlan.load(path).dump(path)
    assert path.read_bytes() == before


def test_an_unknown_route_is_refused_by_name():
    with pytest.raises(ValueError, match="route must be one of"):
        _move_plan(route="automatic-ish")
    payload = _move_plan().to_jsonable()
    for bad in ("Automatic", " automatic", "", None, 1, ["automatic"]):
        broken = dict(payload, route=bad)
        with pytest.raises(ChangePlanError, match="route is"):
            ChangePlan.from_jsonable(broken)


def test_every_recorded_route_is_legal_and_the_old_document_reads_as_no_route():
    payload = _move_plan().to_jsonable()
    for route in ("automatic", "reference-replay", "agent-adjusted"):
        plan = ChangePlan.from_jsonable(dict(payload, route=route))
        assert plan.route == route
        assert plan.to_jsonable()["route"] == route
    old = ChangePlan.from_jsonable(payload)
    assert old.route == ""
    assert "route" not in old.to_jsonable()


def test_the_two_route_vocabularies_cannot_drift():
    """ChangePlan states its own list (a shared module may not import the drawing
    line's `layoutplan`), so the two must be pinned equal here."""
    from boardwise.core.changeplan import PLAN_ROUTES as PLAN_ROUTES_HERE
    from boardwise.core.layoutplan import PLAN_ROUTES as PLAN_ROUTES_DRAWING

    assert PLAN_ROUTES_HERE == PLAN_ROUTES_DRAWING
