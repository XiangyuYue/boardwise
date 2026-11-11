"""038Q3: `lib.symbol_file.get` in the action catalogue and through the CLI.

The batch adds one read-only action: "read the file of ONE library symbol, by
explicit uuid". The connector side — the call shape, the closed parameter set,
the Byte-complete-or-fail rule, the unchanged old contracts — is pinned against
a fake host in `connector/tests/library-symbol-file.test.mjs`. What is checked
here is the **daemon-facing contract**:

* it is `risk="read"` and connector-owned, because the catalogue is the only
  authority the CLI's `--read-only` gate consults — a mis-tiered entry either
  opens a write to a delegated caller or locks a read out;
* the declared parameters are the closed set the handler accepts, and the
  schema says out loud what a reader of the catalogue alone must know: one uuid
  (no arrays), an omitted `libraryUuid` meaning the host's system library, and a
  **required** `fileType` limited to `elibz2`/`elibz`;
* `bridge call --read-only` permits it and forwards the params untouched — the
  property the gate is for, checked through the CLI's own function rather than
  by re-implementing the relation here;
* the read-only probe allowlist (`PROBE_CALL_ACTIONS` in `actions.ts`) does not
  grow: that list exists so a not-yet-restarted daemon can reach a freshly
  registered action, and this one rides the catalogue like any other;
* the old neighbours do not move — `lib.symbol.get`'s parameters and result
  shape stay what they were, which is the compatibility anchor this batch was
  told to keep.

The general rules about names, duplicates and gate checks live in
`tests/test_action_catalogue.py` and `tests/test_537a_bridge_readonly.py`; this
file is the focused pair, not a second catalogue framework.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.bridge.protocol import BridgeError, action_spec
from boardwise.cli import (
    READ_ONLY_VIOLATION,
    _cmd_bridge_call,
    _read_only_refusal,
    build_parser,
)

ACTION = "lib.symbol_file.get"
ROOT = Path(__file__).resolve().parents[1]
ACTIONS_TS = ROOT / "connector" / "src" / "actions.ts"


def _args(*argv: str):
    return build_parser().parse_args(["bridge", "call", *argv])


@pytest.fixture
def door(monkeypatch):
    """Record what would go over the wire; no socket, no daemon, no editor."""
    opened: list = []
    clients: list = []

    class FakeClient:
        def __init__(self) -> None:
            self.sent: list[dict] = []

        @classmethod
        async def open(cls, *args, **kwargs):
            client = cls()
            clients.append(client)
            return client

        async def call(self, action: str, params: dict, **kwargs) -> dict:
            self.sent.append({"action": action, "params": dict(params), **kwargs})
            return {"ok": True, "action": action}

        async def close(self) -> None:
            return None

    def fake_open(args):
        opened.append(args)
        return FakeClient, BridgeError, 1, "token"

    monkeypatch.setattr("boardwise.cli._open_cli", fake_open)
    return opened, clients


def test_the_action_is_a_connector_owned_read():
    """`risk` is what `--read-only` reads, so the tier is the contract."""
    spec = action_spec(ACTION)
    assert spec is not None, f"{ACTION} is not in the catalogue"
    assert spec.owner == "connector", "the connector answers it"
    assert spec.risk == "read", "reading a file is never a write"


def test_it_declares_only_the_parameters_it_accepts():
    assert action_spec(ACTION).params == ("uuid", "libraryUuid", "fileType")


def test_the_schema_states_the_whole_narrow_contract():
    """A reader who has only the catalogue has to learn every trap from it."""
    spec = action_spec(ACTION)
    schema = spec.params_schema

    assert "uuid" in schema and "ONE" in schema, "one symbol per call"
    assert "array" in schema and "refused" in schema, "an array is refused, not fanned out"
    assert "libraryUuid" in schema and "undefined" in schema, "omitted travels as undefined"
    assert "system library" in schema, "the host's default is the reason"
    assert "empty string is refused" in schema, "'' is not 'omitted'"
    assert "REQUIRED" in schema and "elibz2" in schema and "elibz" in schema

    returns = spec.returns
    assert "source" in returns and "apiStatus" in returns and "isZip" in returns
    assert "data" in returns and "bytes" in returns

    # The two claims this batch refuses to make, stated in the catalogue itself.
    assert "sys_FileManager.getSymbolFileBySymbolUuid" in spec.summary
    assert "isZip" in spec.summary
    assert "NOT unpacked" in spec.summary or "not unpacked" in spec.summary
    assert "unmeasured" in spec.summary, "existence of the API is not a successful export"


def test_read_only_gate_permits_the_action():
    """`None` is the gate's "may go" answer — no new bypass, just a read."""
    assert _read_only_refusal(ACTION) is None


def test_read_only_call_forwards_the_params_untouched(door, capsys):
    opened, clients = door
    params = {
        "uuid": "06f50e10ab7d460599b3fe3ee8717a78",
        "libraryUuid": "0819f05c4eef4c71ace90d822a990e87",
        "fileType": "elibz2",
    }

    code = _cmd_bridge_call(
        _args("--action", ACTION, "--params", json.dumps(params), "--read-only")
    )

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert READ_ONLY_VIOLATION not in captured.err
    assert len(opened) == 1, "the call has to reach the bridge"
    assert clients[0].sent == [{"action": ACTION, "params": params}]


def test_the_probe_allowlist_did_not_grow():
    """`PROBE_CALL_ACTIONS` is for actions a not-yet-restarted daemon cannot reach."""
    source = ACTIONS_TS.read_text(encoding="utf-8")
    start = source.index("const PROBE_CALL_ACTIONS")
    end = source.index("\n};", start)
    block = source[start:end]

    assert "sys.get_document_file" in block, "the allowlist parse found the real block"
    assert ACTION not in block, f"{ACTION} must ride the catalogue, not the probe bypass"


def test_the_old_symbol_metadata_contract_is_unchanged():
    """Negative control: this batch added an action, it did not re-tier an old one."""
    old = action_spec("lib.symbol.get")
    assert old is not None
    assert old.params == ("uuid", "libraryUuid")
    assert old.risk == "read"
    assert old.returns == "{uuid, libraryUuid, found, item, readErrors?}"

    # And the archive reads this action's failure text is *not* allowed to
    # imitate: their gate list stays exactly the two 025 gates.
    archive = action_spec("sys.get_document_file")
    assert archive.params == ("fileType", "fileName", "password", "timeoutMs")
    assert "文件导出" in archive.summary
