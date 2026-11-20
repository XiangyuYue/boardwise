"""559 B2: `boardwise pcb connection` — the CLI adapter and its protocol entry.

The judgement is B1's (`tests/test_559_pcb_connection.py`); this file is about the
**wiring**: which flags exist, which actions are called and in what order, what
the route carries, how the version pair is disclosed, and the three exit codes
plus the one refusal that must never print a verdict.

`FakeBridge` stands in for ``cli._open_cli`` + ``BridgeClient`` exactly the way
``test_038y5_pcb_gate``'s does — the adapter opens its own short connection per
action, so the fake counts connections as well as actions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import test_559_pcb_connection as b1

from boardwise import cli, pcb_connection
from boardwise.bridge import protocol
from boardwise.commands import assembly as assembly_commands

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "boardwise" / "pcb_connection.py"

FROM_REF = "R1.1"
TO_REF = "J1.1"


def _connected() -> dict:
    """A probe response whose two direct answers share one Line — exit 0."""
    return b1._probe(
        from_end=b1._end("R1", "1", b1.PAD_FROM, "GND", items=[b1._item("line-1")]),
        to_end=b1._end("J1", "1", b1.PAD_TO, "GND", items=[b1._item("line-1")]),
    )


# --------------------------------------------------------------------------
# A bridge stand-in: one connection per action, every call recorded
# --------------------------------------------------------------------------
class FakeConnection:
    def __init__(self, owner: "FakeBridge", uri: str, token: str, role: str, client: str):
        self.owner = owner

    async def call(self, action, params=None, *, id=None, target_project=None,
                   target_instance=None):
        self.owner.actions.append(action)
        self.owner.calls.append(
            {
                "action": action,
                "params": dict(params or {}),
                "target_project": target_project,
                "target_instance": target_instance,
            }
        )
        if action == pcb_connection.PROBE_ACTION:
            if self.owner.probe_error is not None:
                raise self.owner.probe_error
            return self.owner.probe_answer
        if action == pcb_connection.CONNECTION_ACTION:
            if self.owner.connection_error is not None:
                raise self.owner.connection_error
            return self.owner.payload
        raise AssertionError(f"the adapter used an action 559 must not use: {action}")

    async def close(self) -> None:
        self.closed = True


class FakeBridge:
    """``cli._open_cli`` + ``BridgeClient`` with the two answers 559 may read."""

    def __init__(
        self,
        payload: dict | None = None,
        *,
        probe_answer: dict | None = None,
        probe_error: Exception | None = None,
        connection_error: Exception | None = None,
    ) -> None:
        self.payload = b1._probe() if payload is None else payload
        self.probe_answer = (
            {"version": "4.1.100", "connector": "0.6.3", "topLevel": [], "namespaces": {}}
            if probe_answer is None
            else probe_answer
        )
        self.probe_error = probe_error
        self.connection_error = connection_error
        self.actions: list[str] = []
        self.calls: list[dict] = []
        self.opened: list[FakeConnection] = []
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


def _args(argv: list[str]):
    return cli.build_parser().parse_args(["pcb", "connection", *argv])


def _run(args, bridge: FakeBridge, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = pcb_connection.run_cli_connection(args, bridge=bridge.opener)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --------------------------------------------------------------------------
# The flags: exactly the online contract, and nothing that could widen it
# --------------------------------------------------------------------------
def test_the_parser_names_every_contract_flag() -> None:
    args = _args(
        ["--from", "U9.2", "--to", "CN3.1", "--project", "test",
         "--instance", "win-1", "--port", "61200"]
    )
    assert args.command == "pcb"
    assert args.pcb_command == "connection"
    assert (args.from_ref, args.to_ref) == ("U9.2", "CN3.1")
    assert (args.project, args.instance, args.port) == ("test", "win-1", 61200)


@pytest.mark.parametrize(
    "extra",
    [
        ["--live"],
        ["--board", "board-1"],
        ["--json"],
        ["--through", "1"],
        ["--layer", "F.Cu"],
    ],
)
def test_no_file_live_or_board_option_exists(extra: list[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        _args(["--from", FROM_REF, "--to", TO_REF, *extra])
    assert excinfo.value.code == 2


def test_a_positional_file_is_a_usage_error_and_both_ends_are_required() -> None:
    with pytest.raises(SystemExit) as excinfo:
        _args(["board.epro2", "--from", FROM_REF, "--to", TO_REF])
    assert excinfo.value.code == 2, "the online command takes no FILE"
    with pytest.raises(SystemExit) as excinfo:
        _args(["--to", TO_REF])
    assert excinfo.value.code == 2, "--from is not optional"
    with pytest.raises(SystemExit) as excinfo:
        _args(["--from", FROM_REF])
    assert excinfo.value.code == 2, "--to is not optional"


# --------------------------------------------------------------------------
# The action order, the closed params, and the route
# --------------------------------------------------------------------------
def test_the_probe_runs_first_and_the_connection_second(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bridge = FakeBridge(_connected())
    code, _out, _err = _run(_args(["--from", FROM_REF, "--to", TO_REF]), bridge, capsys)
    assert code == 0
    assert bridge.actions == [pcb_connection.PROBE_ACTION, pcb_connection.CONNECTION_ACTION]
    assert len(bridge.opened) == 2, "one short connection per action"
    assert bridge.calls[0]["params"] == {"namespaces": []}, (
        "the version read must not enumerate or execute anything else"
    )
    assert bridge.calls[1]["params"] == {"from": FROM_REF, "to": TO_REF}, (
        "the probe action's params are closed to the two ends"
    )


def test_the_project_and_instance_travel_as_the_daemons_route(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bridge = FakeBridge(_connected())
    args = _args(["--from", FROM_REF, "--to", TO_REF, "--project", "test",
                  "--instance", "win-1", "--port", "61200"])
    code, _out, _err = _run(args, bridge, capsys)
    assert code == 0
    for call in bridge.calls:
        assert call["target_project"] == "test"
        assert call["target_instance"] == "win-1"
    assert bridge.ports == [61200, 61200]


def test_without_hints_no_route_is_sent(capsys: pytest.CaptureFixture[str]) -> None:
    bridge = FakeBridge()
    _run(_args(["--from", FROM_REF, "--to", TO_REF]), bridge, capsys)
    for call in bridge.calls:
        assert call["target_project"] is None
        assert call["target_instance"] is None


# --------------------------------------------------------------------------
# The version pair: read first, disclosed, never fabricated
# --------------------------------------------------------------------------
def test_the_version_pair_lands_in_source_and_does_not_carry_the_verdict(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bridge = FakeBridge(_connected())
    _code, out, _err = _run(_args(["--from", FROM_REF, "--to", TO_REF]), bridge, capsys)
    payload = json.loads(out)
    assert payload["verdict"] == "CONNECTED"
    assert payload["source"]["versions"] == {
        "host": "4.1.100",
        "connector": "0.6.3",
        "readBy": "sys.probe",
    }
    assert payload["source"]["connector"] == pcb_connection.CONNECTION_ACTION
    assert "error" not in payload["source"]["versions"]


def test_a_failed_version_read_is_disclosed_as_null_not_invented(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bridge = FakeBridge(_connected(), probe_error=RuntimeError("sys.probe is not in this build"))
    code, out, _err = _run(_args(["--from", FROM_REF, "--to", TO_REF]), bridge, capsys)
    payload = json.loads(out)
    assert code == 0, "a missing build number does not overturn measured evidence"
    assert payload["verdict"] == "CONNECTED"
    versions = payload["source"]["versions"]
    assert versions["host"] is None and versions["connector"] is None
    assert "sys.probe is not in this build" in versions["error"]
    assert versions["missing"] == ["host", "connector"]


def test_an_unreadable_probe_answer_is_not_a_version(capsys: pytest.CaptureFixture[str]) -> None:
    bridge = FakeBridge(probe_answer={"topLevel": []})
    _code, out, _err = _run(_args(["--from", FROM_REF, "--to", TO_REF]), bridge, capsys)
    versions = json.loads(out)["source"]["versions"]
    assert versions["host"] is None and versions["connector"] is None
    assert versions["missing"] == ["host", "connector"]
    assert versions["readBy"] == pcb_connection.PROBE_ACTION
    assert "connector" in versions["error"] and "host" in versions["error"], (
        "a null build number must name itself and say why, not look like a field that never existed"
    )


def test_one_missing_version_names_only_that_half(capsys: pytest.CaptureFixture[str]) -> None:
    bridge = FakeBridge(_connected(), probe_answer={"version": "4.1.100", "topLevel": []})
    code, out, _err = _run(_args(["--from", FROM_REF, "--to", TO_REF]), bridge, capsys)
    payload = json.loads(out)
    versions = payload["source"]["versions"]
    assert code == 0 and payload["verdict"] == "CONNECTED"
    assert versions["host"] == "4.1.100"
    assert versions["connector"] is None
    assert versions["missing"] == ["connector"]
    assert "host" not in versions["error"]


# --------------------------------------------------------------------------
# Three verdicts, three exits
# --------------------------------------------------------------------------
def test_connected_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _err = _run(
        _args(["--from", FROM_REF, "--to", TO_REF]), FakeBridge(_connected()), capsys
    )
    payload = json.loads(out)
    assert code == 0
    assert payload["verdict"] == "CONNECTED"
    assert payload["sharedIds"], "a CONNECTED answer carries the intersection it was built on"


def test_not_proven_exits_two(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _err = _run(
        _args(["--from", FROM_REF, "--to", TO_REF]), FakeBridge(b1._probe()), capsys
    )
    payload = json.loads(out)
    assert code == 2
    assert payload["verdict"] == "NOT_PROVEN"
    assert payload["proofs"] == [] and payload["sharedIds"] == []
    assert "path" not in payload, "NOT_PROVEN is not a path claim"


def test_indeterminate_exits_three(capsys: pytest.CaptureFixture[str]) -> None:
    # A **measured** INDETERMINATE: the probe answered, one end did not resolve to
    # exactly one pad, so the JSON is printed and the exit code is 3. (A non-PCB
    # focus never reaches this path — the connector refuses before it reads, and
    # that refusal is pinned below as an empty stdout.)
    bridge = FakeBridge(b1._probe(from_end=b1._end("R1", "1", b1.PAD_FROM, "GND", matches=2)))
    code, out, _err = _run(_args(["--from", FROM_REF, "--to", TO_REF]), bridge, capsys)
    payload = json.loads(out)
    assert code == 3
    assert payload["verdict"] == "INDETERMINATE"
    assert {row["code"] for row in payload["errors"]} == {"pad-not-unique"}


# --------------------------------------------------------------------------
# A refusal is not an answer
# --------------------------------------------------------------------------
def test_a_bridge_refusal_prints_no_json_and_exits_three(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bridge = FakeBridge(connection_error=RuntimeError("UNKNOWN_ACTION: pcb.connection_probe"))
    code, out, err = _run(_args(["--from", FROM_REF, "--to", TO_REF]), bridge, capsys)
    assert code == 3
    assert out == "", "an unasked question must never leave a verdict on stdout"
    assert "pcb.connection_probe" in err and "UNKNOWN_ACTION" in err


def test_a_malformed_reference_refused_by_the_connector_is_the_same_refusal(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bridge = FakeBridge(connection_error=RuntimeError("BAD_REQUEST: params.from must be REF.PAD"))
    code, out, err = _run(_args(["--from", "U9", "--to", TO_REF]), bridge, capsys)
    assert code == 3
    assert out == ""
    assert "BAD_REQUEST" in err


# --------------------------------------------------------------------------
# What leaves the process: the canonical payload, and no invented geometry
# --------------------------------------------------------------------------
def test_stdout_is_the_canonical_projection_of_the_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    probe_payload = b1._probe()
    bridge = FakeBridge(probe_payload)
    code, out, _err = _run(_args(["--from", FROM_REF, "--to", TO_REF]), bridge, capsys)
    payload = json.loads(out)
    assert payload["schema"] == "boardwise.pcbConnection/1"
    for key in ("unknown", "ignored", "errors", "coverage", "scope", "sharedIds", "proofs"):
        assert key in payload, f"{key} must always exist"
    for absent in ("path", "hops", "hopCount", "viaCount", "distance"):
        assert absent not in payload, f"{absent} would be a fabricated geometry claim"

    answers = {
        pcb_connection.PROBE_ACTION: bridge.probe_answer,
        pcb_connection.CONNECTION_ACTION: probe_payload,
    }
    expected, refusal = pcb_connection.probe_and_project(
        lambda action, params: answers[action], FROM_REF, TO_REF
    )
    assert refusal == ""
    assert out.strip() == expected.to_json(indent=None)
    assert code == 2


# --------------------------------------------------------------------------
# What the adapter may reach, and what the catalogue says about it
# --------------------------------------------------------------------------
def test_the_adapter_names_only_the_two_read_actions() -> None:
    source = MODULE.read_text(encoding="utf-8")
    named = set(re.findall(r'"([a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*)"', source))
    assert named == {pcb_connection.PROBE_ACTION, pcb_connection.CONNECTION_ACTION}
    for verb in ("doc.open", "doc.save", "doc.focus", "sys.self_update", "sch.set_",
                 "pcb.place_", "sch.delete_"):
        assert verb not in source, f"the online adapter must not reach {verb}"


def test_the_catalogue_entry_is_a_closed_read_only_action() -> None:
    action = next(a for a in protocol.ACTIONS if a.name == "pcb.connection_probe")
    assert action.owner == "connector"
    assert action.risk == "read"
    assert action.design_write is False
    assert action.params == ("from", "to")
    assert "pcb.connection_probe" in protocol.ACTION_NAMES
    assert "path" not in action.returns, "the catalogue promises no ordered path"


def test_main_routes_pcb_connection_to_the_assembly_owned_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list = []

    def dispatch(args, *, bridge):
        seen.append(args)
        return 0

    monkeypatch.setattr(pcb_connection, "run_cli_connection", dispatch)
    assert cli.main(["pcb", "connection", "--from", FROM_REF, "--to", TO_REF]) == 0
    assert [args.pcb_command for args in seen] == ["connection"]
    assert (seen[0].from_ref, seen[0].to_ref) == (FROM_REF, TO_REF)


def test_the_assembly_router_keeps_net_path_and_gate_on_their_own_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from boardwise import pcb_netpath

    seen: list = []
    monkeypatch.setattr(
        pcb_netpath, "run_cli_net_path", lambda args: seen.append(("net-path", args)) or 0
    )
    monkeypatch.setattr(
        assembly_commands, "dispatch_pcb_gate",
        lambda args, checkup, bridge: seen.append(("gate", args)) or 0,
    )
    monkeypatch.setattr(
        pcb_connection, "run_cli_connection", lambda args, *, bridge: seen.append(("connection", args)) or 0
    )
    parser = cli.build_parser()
    net = parser.parse_args(
        ["pcb", "net-path", "board.epro2", "--from", FROM_REF, "--to", TO_REF]
    )
    assert net.board == "", "550's --board default is untouched"
    assembly_commands.dispatch_pcb(net, checkup=None, bridge=None)
    gate = parser.parse_args(["pcb", "gate", "--out", "out-dir"])
    assembly_commands.dispatch_pcb(gate, checkup=None, bridge=None)
    conn = _args(["--from", FROM_REF, "--to", TO_REF])
    assembly_commands.dispatch_pcb(conn, checkup=None, bridge=None)
    assert [name for name, _args in seen] == ["net-path", "gate", "connection"]


def test_the_offline_net_path_flags_are_unchanged() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        ["pcb", "net-path", "board.epro2", "--from", FROM_REF, "--to", TO_REF,
         "--board", "main"]
    )
    assert (args.file, args.from_ref, args.to_ref, args.board) == (
        "board.epro2", FROM_REF, TO_REF, "main"
    )
    for flag in (["--live"], ["--json"], ["--project", "test"], ["--layer", "F.Cu"]):
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(
                ["pcb", "net-path", "board.epro2", "--from", FROM_REF, "--to", TO_REF, *flag]
            )
        assert excinfo.value.code == 2
