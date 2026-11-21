"""562 B2: `boardwise pcb path` — the CLI adapter, its protocol entry and `--json`.

The judgement is B1's (`tests/test_562_live_path.py`); this file is about the
**wiring**: which flags exist, which actions are called and in what order, what the
route carries, how the version pair is disclosed, the three exit codes, the one
refusal that must never print a state, and the one place this command may put its
bytes — a file, written atomically, that a failed write does not turn into a
verdict.

`FakeBridge` stands in for ``cli._open_cli`` + ``BridgeClient`` exactly the way
``test_559_pcb_connection_cli``'s does — the adapter opens its own short
connection per action, so the fake counts connections as well as actions — and the
payloads are B1's own builders, so the shape the CLI projects is the shape the
collector reports.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import test_562_live_path as b1
from test_540_cli_draw import _subparsers

from boardwise import cli, pcb_connection, pcb_path
from boardwise.bridge import protocol
from boardwise.commands import assembly as assembly_commands

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "boardwise" / "pcb_path.py"

FROM_REF = "R1.1"
TO_REF = "J1.1"


# --------------------------------------------------------------------------
# The three states, built by B1's own builders
# --------------------------------------------------------------------------
def _connected() -> dict:
    """Both ends' own direct answer names the same Line: exit 0."""
    return b1._pad_direct_shared_line()


def _not_proven() -> dict:
    """An exhausted legal graph with nothing withheld: exit 2."""
    return b1._probe()


def _indeterminate() -> dict:
    """A **measured** refusal to answer: one end resolved to two pads, exit 3."""
    return b1._probe(from_end=b1._end("R1", "1", b1.PAD_FROM, matches=2))


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
        if action == pcb_path.PROBE_ACTION:
            if self.owner.probe_error is not None:
                raise self.owner.probe_error
            return self.owner.probe_answer
        # The literal, not the module constant: an adapter that renamed its own
        # action would otherwise take this stand-in with it and stay green.
        if action == "pcb.path_probe":
            if self.owner.path_error is not None:
                raise self.owner.path_error
            return self.owner.payload
        raise AssertionError(f"the adapter used an action 562 must not use: {action}")

    async def close(self) -> None:
        self.closed = True


class FakeBridge:
    """``cli._open_cli`` + ``BridgeClient`` with the two answers 562 may read."""

    def __init__(
        self,
        payload: dict | None = None,
        *,
        probe_answer: dict | None = None,
        probe_error: Exception | None = None,
        path_error: Exception | None = None,
    ) -> None:
        self.payload = _not_proven() if payload is None else payload
        self.probe_answer = (
            {"version": "4.1.100", "connector": "0.6.3", "topLevel": [], "namespaces": {}}
            if probe_answer is None
            else probe_answer
        )
        self.probe_error = probe_error
        self.path_error = path_error
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
    return cli.build_parser().parse_args(["pcb", "path", *argv])


def _surrogate_payload() -> dict:
    """A CONNECTED payload whose every net carries a lone surrogate (562D MEDIUM-4).

    `to_json` writes it (``json`` does not encode), but a UTF-8 file write cannot:
    the failure is a ``UnicodeEncodeError``, i.e. a ``ValueError``.
    """
    def wash(value):
        if isinstance(value, str):
            return "\ud800" if value == b1.NET else value
        if isinstance(value, dict):
            return {key: wash(item) for key, item in value.items()}
        if isinstance(value, list):
            return [wash(item) for item in value]
        return value

    return wash(_connected())


def _run(args, bridge: FakeBridge, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = pcb_path.run_cli_path(args, bridge=bridge.opener)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --------------------------------------------------------------------------
# The flags: exactly the online contract, and nothing that could widen it
# --------------------------------------------------------------------------
def test_the_parser_names_every_contract_flag(tmp_path: Path) -> None:
    target = tmp_path / "path.json"
    args = _args(
        ["--from", "U9.2", "--to", "CN3.1", "--project", "test",
         "--instance", "win-1", "--port", "61200", "--json", str(target)]
    )
    assert args.command == "pcb"
    assert args.pcb_command == "path"
    assert (args.from_ref, args.to_ref) == ("U9.2", "CN3.1")
    assert (args.project, args.instance, args.port) == ("test", "win-1", 61200)
    assert args.json_path == str(target)


def test_the_optional_flags_default_to_nothing() -> None:
    args = _args(["--from", FROM_REF, "--to", TO_REF])
    assert (args.project, args.instance, args.port, args.json_path) == ("", "", None, "")


@pytest.mark.parametrize(
    "extra",
    [
        ["--live"],
        ["--board", "board-1"],
        ["--through", "1"],
        ["--layer", "F.Cu"],
        ["--file", "board.epro2"],
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


def test_json_takes_a_path_and_never_a_bare_switch() -> None:
    with pytest.raises(SystemExit) as excinfo:
        _args(["--from", FROM_REF, "--to", TO_REF, "--json"])
    assert excinfo.value.code == 2, "--json names a destination; it is not a mode switch"


# --------------------------------------------------------------------------
# The action order, the closed params, and the route
# --------------------------------------------------------------------------
def test_the_probe_runs_first_and_the_path_probe_second(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bridge = FakeBridge(_connected())
    code, _out, _err = _run(_args(["--from", FROM_REF, "--to", TO_REF]), bridge, capsys)
    assert code == 0
    assert bridge.actions == [pcb_path.PROBE_ACTION, "pcb.path_probe"]
    assert bridge.actions[1] == pcb_path.PATH_ACTION, (
        "the action this command reaches is pcb.path_probe, not another read"
    )
    assert len(bridge.opened) == 2, "one short connection per action"
    assert bridge.calls[0]["params"] == {"namespaces": []}, (
        "the version read must not enumerate or execute anything else"
    )
    assert bridge.calls[1]["params"] == {"from": FROM_REF, "to": TO_REF}, (
        "the action's params are closed to the two ends"
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
# The version pair: 559's disclosure, reused rather than reinvented
# --------------------------------------------------------------------------
def test_the_adapter_reuses_559s_version_disclosure_and_short_route() -> None:
    assert pcb_path.PROBE_ACTION == pcb_connection.PROBE_ACTION
    assert pcb_path.PROBE_PARAMS == pcb_connection.PROBE_PARAMS
    assert pcb_path._versions is pcb_connection._versions, (
        "one copy of the version disclosure, not a second spelling of it"
    )
    assert pcb_path._short_connection_call is pcb_connection._short_connection_call, (
        "one copy of the daemon route, not a second one"
    )


def test_the_version_pair_lands_in_source_and_does_not_carry_the_state(
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
    assert payload["source"]["connector"] == pcb_path.PATH_ACTION
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
    assert versions["readBy"] == pcb_path.PROBE_ACTION
    assert "connector" in versions["error"] and "host" in versions["error"]


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
# Three states, three exits
# --------------------------------------------------------------------------
def test_connected_exits_zero_with_the_walked_path(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _err = _run(
        _args(["--from", FROM_REF, "--to", TO_REF]), FakeBridge(_connected()), capsys
    )
    payload = json.loads(out)
    assert code == 0
    assert payload["verdict"] == "CONNECTED"
    assert [row["primitiveId"] for row in payload["path"]] == [b1.PAD_FROM, b1.LN1, b1.PAD_TO]
    assert payload["hopCount"] == 2


def test_not_proven_exits_two_and_carries_no_path(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _err = _run(
        _args(["--from", FROM_REF, "--to", TO_REF]), FakeBridge(_not_proven()), capsys
    )
    payload = json.loads(out)
    assert code == 2
    assert payload["verdict"] == "NOT_PROVEN"
    assert payload["path"] == [] and payload["hops"] == []
    assert payload["coverage"]["partial"] is False, "NOT_PROVEN is only claimed with no gap"


def test_indeterminate_exits_three(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _err = _run(
        _args(["--from", FROM_REF, "--to", TO_REF]), FakeBridge(_indeterminate()), capsys
    )
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
    bridge = FakeBridge(path_error=RuntimeError("UNKNOWN_ACTION: pcb.path_probe"))
    code, out, err = _run(_args(["--from", FROM_REF, "--to", TO_REF]), bridge, capsys)
    assert code == 3
    assert out == "", "an unasked question must never leave a state on stdout"
    assert "pcb.path_probe" in err and "UNKNOWN_ACTION" in err


def test_a_malformed_reference_refused_by_the_connector_is_the_same_refusal(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bridge = FakeBridge(path_error=RuntimeError("BAD_REQUEST: params.from must be REF.PAD"))
    code, out, err = _run(_args(["--from", "U9", "--to", TO_REF]), bridge, capsys)
    assert code == 3
    assert out == ""
    assert "BAD_REQUEST" in err


# --------------------------------------------------------------------------
# Where the bytes go: stdout, or one atomic file — never both
# --------------------------------------------------------------------------
def test_stdout_is_the_canonical_projection_of_the_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    probe_payload = _connected()
    bridge = FakeBridge(probe_payload)
    code, out, _err = _run(_args(["--from", FROM_REF, "--to", TO_REF]), bridge, capsys)
    payload = json.loads(out)
    assert payload["schema"] == "boardwise.pcbLivePath/1"
    for key in ("verdict", "source", "query", "path", "hops", "hopCount", "viaCount",
                "unknown", "ignored", "errors", "coverage", "scope"):
        assert key in payload, f"{key} must always exist"

    answers = {
        pcb_path.PROBE_ACTION: bridge.probe_answer,
        pcb_path.PATH_ACTION: probe_payload,
    }
    expected, refusal = pcb_path.path_and_project(
        lambda action, params: answers[action], FROM_REF, TO_REF
    )
    assert refusal == ""
    assert out.strip() == expected.to_json(indent=None)
    assert code == 0


def test_json_writes_the_same_payload_and_leaves_stdout_empty(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    target = tmp_path / "path.json"
    bridge = FakeBridge(_connected())
    code, out, err = _run(
        _args(["--from", FROM_REF, "--to", TO_REF, "--json", str(target)]), bridge, capsys
    )
    assert code == 0, "the exit code still follows the state"
    assert out == "" and err == ""
    assert json.loads(target.read_text(encoding="utf-8"))["verdict"] == "CONNECTED"
    assert list(tmp_path.iterdir()) == [target], (
        "the sibling temporary file is consumed by the replace, not left behind"
    )


def test_json_honours_the_state_it_did_not_print(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    target = tmp_path / "path.json"
    code, out, _err = _run(
        _args(["--from", FROM_REF, "--to", TO_REF, "--json", str(target)]),
        FakeBridge(_not_proven()),
        capsys,
    )
    assert (code, out) == (2, "")
    assert json.loads(target.read_text(encoding="utf-8"))["verdict"] == "NOT_PROVEN"


def test_json_creates_the_parent_directory_it_was_given(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    target = tmp_path / "nested" / "deeper" / "path.json"
    code, out, _err = _run(
        _args(["--from", FROM_REF, "--to", TO_REF, "--json", str(target)]),
        FakeBridge(_connected()),
        capsys,
    )
    assert (code, out) == (0, "")
    assert target.is_file()


def test_a_failed_json_write_exits_three_with_no_state_and_names_its_residue(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    # The verdict that would have been printed is CONNECTED (exit 0); the target
    # is an existing directory, so the atomic replace cannot land. A caller must
    # not read the exit code or stdout as a state.
    target = tmp_path / "path.json"
    target.mkdir()
    bridge = FakeBridge(_connected())
    code, out, err = _run(
        _args(["--from", FROM_REF, "--to", TO_REF, "--json", str(target)]), bridge, capsys
    )
    assert code == 3, "a write that did not happen cannot report the measured state"
    assert out == "", "no state is printed when --json was asked for and the write failed"
    assert "CONNECTED" not in out and "CONNECTED" not in err
    assert "could not write" in err and "--json" in err
    residue = re.search(r"the temporary file (.+?) was left behind", err)
    assert residue, f"the residue must be disclosed by name, got: {err!r}"
    leftover = Path(residue.group(1))
    assert leftover.is_file(), "the leftover temporary file is disclosed, never deleted"
    assert leftover.parent == tmp_path


def test_the_adapter_deletes_nothing() -> None:
    source = MODULE.read_text(encoding="utf-8")
    for verb in ("unlink", "os.remove", "rmtree", "shutil.move", "os.rmdir"):
        assert verb not in source, f"the adapter must not clean up after itself: {verb}"


def test_an_unencodable_payload_is_a_named_failure_with_its_residue(tmp_path: Path) -> None:
    # 562D MEDIUM-4: a lone surrogate raises UnicodeEncodeError, which is a
    # ValueError and not an OSError — it must come back as (leftover, error),
    # never as a traceback out of the writer.
    target = tmp_path / "path.json"
    leftover, failure = pcb_path.write_json_atomically(str(target), '{"net": "\ud800"}\n')

    assert failure.startswith("UnicodeEncodeError"), failure
    assert leftover is not None, "the writer names the residue it left behind"
    assert Path(leftover).is_file(), "the residue is disclosed, never deleted"
    assert Path(leftover).parent == tmp_path
    assert not target.exists(), "a document that could not be encoded is never left as a result"


def test_a_json_write_that_cannot_encode_exits_three_with_its_residue(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    # The verdict that would have been printed is CONNECTED (exit 0); the payload
    # cannot be encoded, so no state may be reported and the residue must be named.
    target = tmp_path / "path.json"
    code, out, err = _run(
        _args(["--from", FROM_REF, "--to", TO_REF, "--json", str(target)]),
        FakeBridge(_surrogate_payload()),
        capsys,
    )
    assert code == 3, "a write that did not happen cannot report the measured state"
    assert out == "", "no state is printed when --json was asked for and the write failed"
    assert "CONNECTED" not in out and "CONNECTED" not in err
    assert "could not write" in err and "--json" in err
    assert "UnicodeEncodeError" in err, err
    residue = re.search(r"the temporary file (.+?) was left behind", err)
    assert residue, f"the residue must be disclosed by name, got: {err!r}"
    leftover = Path(residue.group(1))
    assert leftover.is_file(), "the leftover temporary file is disclosed, never deleted"
    assert leftover.parent == tmp_path
    assert not target.exists()


# --------------------------------------------------------------------------
# What the adapter may reach, and what the catalogue says about it
# --------------------------------------------------------------------------
def test_the_adapter_names_only_the_path_action() -> None:
    source = MODULE.read_text(encoding="utf-8")
    named = set(re.findall(r'"([a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*)"', source))
    assert named == {pcb_path.PATH_ACTION}, sorted(named)
    for verb in ("doc.open", "doc.save", "doc.focus", "sys.self_update", "sch.set_",
                 "pcb.place_", "sch.delete_", "pcb.doc.new"):
        assert verb not in source, f"the online adapter must not reach {verb}"


def test_the_catalogue_entry_is_a_closed_read_only_action() -> None:
    action = next(a for a in protocol.ACTIONS if a.name == "pcb.path_probe")
    assert action.owner == "connector"
    assert action.risk == "read"
    assert action.design_write is False
    assert action.params == ("from", "to")
    assert "pcb.path_probe" in protocol.ACTION_NAMES
    for promised in ("nodes", "edges", "seeds", "frontier", "coverage"):
        assert promised in action.returns, f"the catalogue must describe {promised}"
    assert "verdict" not in action.returns, "the catalogue promises no verdict here"
    assert "entireTrack" not in action.returns, "the catalogue promises no entireTrack set"
    assert "No verdict" in action.summary
    assert "getEntireTrack` is never called" in action.summary


def test_main_routes_pcb_path_to_the_assembly_owned_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list = []

    def dispatch(args, *, bridge):
        seen.append(args)
        return 0

    monkeypatch.setattr(pcb_path, "run_cli_path", dispatch)
    assert cli.main(["pcb", "path", "--from", FROM_REF, "--to", TO_REF]) == 0
    assert [args.pcb_command for args in seen] == ["path"]
    assert (seen[0].from_ref, seen[0].to_ref) == (FROM_REF, TO_REF)


def test_the_assembly_router_keeps_the_other_three_on_their_own_paths(
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
        pcb_connection, "run_cli_connection",
        lambda args, *, bridge: seen.append(("connection", args)) or 0,
    )
    monkeypatch.setattr(
        pcb_path, "run_cli_path", lambda args, *, bridge: seen.append(("path", args)) or 0
    )
    parser = cli.build_parser()
    net = parser.parse_args(
        ["pcb", "net-path", "board.epro2", "--from", FROM_REF, "--to", TO_REF]
    )
    assert net.board == "", "550's --board default is untouched"
    assembly_commands.dispatch_pcb(net, checkup=None, bridge=None)
    gate = parser.parse_args(["pcb", "gate", "--out", "out-dir"])
    assembly_commands.dispatch_pcb(gate, checkup=None, bridge=None)
    conn = parser.parse_args(["pcb", "connection", "--from", FROM_REF, "--to", TO_REF])
    assembly_commands.dispatch_pcb(conn, checkup=None, bridge=None)
    path = _args(["--from", FROM_REF, "--to", TO_REF])
    assembly_commands.dispatch_pcb(path, checkup=None, bridge=None)
    assert [name for name, _seen in seen] == ["net-path", "gate", "connection", "path"]


def test_path_registers_after_connection_and_the_old_three_keep_their_order() -> None:
    top = _subparsers(cli.build_parser())
    assert list(_subparsers(top.choices["pcb"]).choices) == [
        "gate", "net-path", "connection", "path",
    ], "the new subcommand appends; the historical three do not move"


def test_the_offline_and_direct_only_neighbours_are_unchanged() -> None:
    parser = cli.build_parser()
    net = parser.parse_args(
        ["pcb", "net-path", "board.epro2", "--from", FROM_REF, "--to", TO_REF,
         "--board", "main"]
    )
    assert (net.file, net.from_ref, net.to_ref, net.board) == (
        "board.epro2", FROM_REF, TO_REF, "main"
    )
    for flag in (["--live"], ["--json", "out.json"], ["--project", "test"]):
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(
                ["pcb", "net-path", "board.epro2", "--from", FROM_REF, "--to", TO_REF, *flag]
            )
        assert excinfo.value.code == 2, f"550's offline surface must not gain {flag}"
    conn = parser.parse_args(["pcb", "connection", "--from", FROM_REF, "--to", TO_REF])
    assert not hasattr(conn, "json_path"), "559's direct-only surface gains no --json"
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(
            ["pcb", "connection", "--from", FROM_REF, "--to", TO_REF, "--json", "out.json"]
        )
    assert excinfo.value.code == 2
