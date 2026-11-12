"""038Q6: `lib.footprint_file.get` in the action catalogue and through the CLI.

The batch adds one read-only action: "read the file of ONE library footprint, by
explicit uuid". The connector side — the call shape, the closed parameter set,
the byte-complete-or-fail rule, and the shared reader that keeps the 038Q3 symbol
read from drifting — is pinned against a fake host in
`connector/tests/library-footprint-file.test.mjs`. What is checked here is the
**daemon-facing contract**:

* it is `risk="read"` and connector-owned, because the catalogue is the only
  authority the CLI's `--read-only` gate consults — a mis-tiered entry either
  opens a write to a delegated caller or locks a read out;
* the declared parameters are the closed set the handler accepts, and the schema
  says out loud what a reader of the catalogue alone must know: one uuid (no
  arrays), an omitted `libraryUuid` meaning the host's system library, and a
  **required** `fileType` limited to `elibz2`/`elibz`;
* the summary makes no claim the batch is not entitled to: the host method is
  measured **present**, not working; nothing is unpacked; no pad geometry, no
  PAD 4 and no electrical inference is reported;
* `bridge call --read-only` permits it and forwards the params untouched — the
  property the gate is for, checked through the CLI's own function rather than
  by re-implementing the relation here;
* the read-only probe allowlist (`PROBE_CALL_ACTIONS` in `actions.ts`) does not
  grow;
* the implementation is **one** internal reader configured per action, not a
  second copy of the symbol read's failure ladder;
* the old neighbours do not move — `lib.symbol_file.get`, `lib.footprint.get`
  and the 025 archive refusal keep exactly what they had.

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

ACTION = "lib.footprint_file.get"
SYMBOL_ACTION = "lib.symbol_file.get"
ROOT = Path(__file__).resolve().parents[1]
ACTIONS_TS = ROOT / "connector" / "src" / "actions.ts"
BRIDGE_DOC = ROOT / "docs" / "bridge.md"


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


def _actions_source() -> str:
    return ACTIONS_TS.read_text(encoding="utf-8").replace("\r\n", "\n")


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

    assert "uuid" in schema and "ONE" in schema, "one footprint per call"
    assert "array" in schema and "refused" in schema, "an array is refused, not fanned out"
    assert "libraryUuid" in schema and "undefined" in schema, "omitted travels as undefined"
    assert "system library" in schema, "the host's default is the reason"
    assert "empty string is refused" in schema, "'' is not 'omitted'"
    assert "REQUIRED" in schema and "elibz2" in schema and "elibz" in schema

    returns = spec.returns
    assert "source" in returns and "apiStatus" in returns and "isZip" in returns
    assert "data" in returns and "bytes" in returns


def test_the_summary_claims_neither_a_read_nor_a_pad():
    """The two statements this batch must not make, checked in the catalogue itself."""
    summary = action_spec(ACTION).summary

    assert "sys_FileManager.getFootprintFileByFootprintUuid" in summary
    assert "present" in summary and "unmeasured" in summary, (
        "a present method is not a working export, and the catalogue has to say so"
    )
    assert "not unpacked" in summary.lower(), "the container is not opened"
    assert "PAD 4" in summary, "the missing-pad question is named as out of scope"
    assert "isZip" in summary, "the two-byte observation is stated where it is returned"
    assert "下载库" in summary, "the documented gate travels with the action"


def test_read_only_gate_permits_the_action():
    """`None` is the gate's "may go" answer — no new bypass, just a read."""
    assert _read_only_refusal(ACTION) is None


def test_read_only_call_forwards_the_params_untouched(door, capsys):
    opened, clients = door
    params = {
        "uuid": "20c29e37a9b84b4197418483096f9c05",
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
    source = _actions_source()
    start = source.index("const PROBE_CALL_ACTIONS")
    end = source.index("\n};", start)
    block = source[start:end]

    assert "sys.get_document_file" in block, "the allowlist parse found the real block"
    assert ACTION not in block, f"{ACTION} must ride the catalogue, not the probe bypass"
    assert SYMBOL_ACTION not in block, "the 038Q3 action is unchanged too"


def test_the_two_file_reads_share_one_reader():
    """038Q6's architecture: configuration per action, behaviour once.

    A copied failure ladder is how two actions start answering differently about
    the same host behaviour, so the check is that there is exactly **one** reader
    definition and that both registrations delegate to it with their own spec.
    """
    source = _actions_source()

    assert source.count("async function readLibraryFile(") == 1, (
        "one internal reader, not one per action"
    )
    assert source.count("readLibraryFile(") == 3, (
        "the definition plus exactly two delegating actions"
    )
    for action, config in ((SYMBOL_ACTION, "SYMBOL_FILE_READ"), (ACTION, "FOOTPRINT_FILE_READ")):
        assert f"readLibraryFile('{action}', {config}, params, eda)" in source, (
            f"{action} must delegate to the shared reader with its own fixed configuration"
        )

    # The per-action configuration is the *only* difference, and it is fixed:
    # path, gate and noun, nothing else.
    for config, path in (
        ("SYMBOL_FILE_READ", "sys_FileManager.getSymbolFileBySymbolUuid"),
        ("FOOTPRINT_FILE_READ", "sys_FileManager.getFootprintFileByFootprintUuid"),
    ):
        start = source.index(f"const {config}: LibraryFileRead = {{")
        block = source[start:source.index("};", start)]
        assert f"path: '{path}'" in block
        assert "gate: '团队库 > 下载库" in block
        assert "noun: '" in block


def test_the_documentation_registers_the_action_with_its_unmeasured_edge():
    doc = BRIDGE_DOC.read_text(encoding="utf-8")
    row = next(
        (line for line in doc.splitlines() if line.startswith(f"| `{ACTION}` |")),
        None,
    )
    assert row is not None, f"{ACTION} is missing from the docs/bridge.md §4 table"
    assert "getFootprintFileByFootprintUuid" in row
    assert "unmeasured" in row, "the doc must not promise an exported file"
    assert "PAD 4" in row and "no electrical inference" in row.lower()


def test_the_old_symbol_file_contract_is_unchanged():
    """Negative control: adding an action did not re-tier or re-shape the 038Q3 one."""
    old = action_spec(SYMBOL_ACTION)
    assert old is not None
    assert old.risk == "read"
    assert old.params == ("uuid", "libraryUuid", "fileType")
    assert "getSymbolFileBySymbolUuid" in old.summary
    assert "getFootprintFileByFootprintUuid" not in old.summary


def test_the_old_footprint_metadata_contract_is_unchanged():
    """The action this batch exists because of keeps exactly what it answered."""
    old = action_spec("lib.footprint.get")
    assert old is not None
    assert old.risk == "read"
    assert old.params == ("uuid", "libraryUuid")
    assert old.returns == "{uuid, libraryUuid, found, name, item}"

    # And the archive reads' gate list this action must not imitate: still two.
    archive = action_spec("sys.get_document_file")
    assert archive.params == ("fileType", "fileName", "password", "timeoutMs")
    assert "文件导出" in archive.summary
