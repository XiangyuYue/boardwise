"""038Q14a: the native-CBB *archive* reads in the action catalogue.

`lib.cbb.personal`, `lib.cbb.libraries` and `lib.cbb.export` are the read-only
trio an archive of the host's own reuse modules needs: which library is this
workspace's personal one, which *other* libraries exist (the declaration excludes
the four special ones, so the list is a map, not a substitute), and one module's
own `.epro2` container. The connector side is pinned in
`connector/tests/library-cbb.test.mjs` (against the real `buildHandlers()`
registry); what is checked here is the **daemon-facing contract** these three
entries have to carry:

* all three are `risk="read"` and connector-owned — the catalogue is the only
  authority the CLI's `--read-only` gate consults, so a mis-tiered entry would
  either open a write to a delegated caller or lock a read out;
* the declared parameters are the closed set the handlers accept, and the
  schema/summary state the traps out loud: `lib.cbb.personal` and
  `lib.cbb.libraries` take **no** arguments; `lib.cbb.personal`'s unresolved
  uuid (`undefined`/`null`) is `personal-library-unresolved`, never "the
  workspace has no personal library"; `lib.cbb.export` requires **both** the uuid
  and the library (no system-library default, because the identity check is made
  against the library the caller names), re-reads the module through
  `lib_Cbb.get` first, sends that module's **own name** as `fileName` (the
  declaration's 复用模块名), and refuses an empty or over-16-MiB container;
* `bridge call --read-only` **permits** all three and forwards them untouched —
  the property the gate is for, checked through the CLI's own function rather
  than by re-implementing the relation here;
* nothing in the trio unpacks the container or claims its internal format: the
  catalogue says the bytes are opaque, and the only `.epro2` claim is the
  container the host was asked for.

This is a focused trio, not a second catalogue framework: the general rules
about names, duplicates and gate checks are `tests/test_action_catalogue.py`
and `tests/test_537a_bridge_readonly.py`.
"""

from __future__ import annotations

import json

import pytest

from boardwise.bridge.protocol import BridgeError, action_spec
from boardwise.cli import (
    READ_ONLY_VIOLATION,
    _cmd_bridge_call,
    _read_only_refusal,
    build_parser,
)

CBB_NATIVE_ACTIONS = ("lib.cbb.personal", "lib.cbb.export", "lib.cbb.libraries")


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


@pytest.mark.parametrize("name", CBB_NATIVE_ACTIONS)
def test_each_action_is_a_connector_owned_read(name):
    """`risk` is what `--read-only` reads, so the tier is the contract."""
    spec = action_spec(name)
    assert spec is not None, f"{name} is not in the catalogue"
    assert spec.owner == "connector", f"{name} is answered by the connector"
    assert spec.risk == "read", f"{name} must never be anything but read"


def test_the_personal_read_takes_no_parameters():
    assert action_spec("lib.cbb.personal").params == ()


def test_the_export_requires_a_uuid_and_a_library():
    """No system-library default: the identity is checked against the named one."""
    assert action_spec("lib.cbb.export").params == ("uuid", "libraryUuid")


def test_the_library_list_read_takes_no_parameters():
    """`lib.cbb.libraries` is a list of the *other* libraries; it takes nothing."""
    assert action_spec("lib.cbb.libraries").params == ()


def test_library_list_schema_states_the_list_contract():
    spec = action_spec("lib.cbb.libraries")
    assert "no arguments" in spec.params_schema
    summary = spec.summary
    assert "lib_LibrariesList.getAllLibrariesList" in summary
    assert "EXCLUDES" in summary, "the four special libraries are not in this list"
    assert "lib.cbb.personal" in summary, "it must not read as a personal-library substitute"
    assert "count 0" in summary, "an empty list is a real reading"
    assert "CONNECTOR_ERROR" in summary
    assert "duplicated" in summary.lower()
    returns = spec.returns
    assert "lib_LibrariesList.getAllLibrariesList" in returns
    assert "items" in returns and "uuid" in returns and "name" in returns


def test_library_list_docs_row_states_the_exclusion():
    """The §4 row carries the same caveat as the catalogue, not a shorter one."""
    from pathlib import Path

    doc = Path(__file__).resolve().parents[1] / "docs" / "bridge.md"
    rows = [
        line for line in doc.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `lib.cbb.libraries`")
    ]
    assert len(rows) == 1, "docs/bridge.md §4 must carry exactly one lib.cbb.libraries row"
    assert "excludes" in rows[0], "the special libraries are excluded — say so"
    assert "not** a substitute" in rows[0] or "not** a substitute for" in rows[0]



def test_personal_schema_states_the_unresolved_contract():
    """`undefined` is an unresolved uuid, not a diagnosed deployment fact."""
    spec = action_spec("lib.cbb.personal")
    schema = spec.params_schema
    assert "no arguments" in schema, "an argument is refused, not ignored"
    summary = spec.summary
    assert "lib_LibrariesList.getPersonalLibraryUuid" in summary
    assert "personal-library-unresolved" in summary, "the machine-readable reason is contract"
    assert "does not diagnose" in summary or "not a diagnosis" in summary.lower()
    assert "not evidence" in summary, "an unresolved uuid is not an empty library"
    assert "CONNECTOR_ERROR" in summary
    assert "NOT_IMPLEMENTED" in summary, "a missing API names its path"
    assert "lib_LibrariesList.getPersonalLibraryUuid" in spec.returns
    assert "libraryUuid" in spec.returns


def test_personal_docs_row_states_the_unresolved_contract():
    from pathlib import Path

    doc = Path(__file__).resolve().parents[1] / "docs" / "bridge.md"
    rows = [
        line for line in doc.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `lib.cbb.personal`")
    ]
    assert len(rows) == 1, "docs/bridge.md §4 must carry exactly one lib.cbb.personal row"
    row = rows[0]
    assert "personal-library-unresolved" in row
    assert "not" in row and "diagnosis" in row
    assert "no personal library" not in row, "the old over-claim must not survive in the doc"


def test_export_schema_states_the_identity_and_container_contract():
    spec = action_spec("lib.cbb.export")
    schema = spec.params_schema
    assert "uuid" in schema and "required" in schema
    assert "libraryUuid" in schema and "required" in schema
    assert "system-library default" in schema, "an omitted library is refused here"
    returns = spec.returns
    assert "format: 'epro2'" in returns
    assert "sys_FileManager.getCbbFileByCbbUuid" in returns
    assert "base64" in returns and "size" in returns
    summary = spec.summary
    assert "lib_Cbb.get" in summary, "the identity read is part of the contract"
    assert "复用模块名" in summary, "the fileName argument is the module's own name"
    assert "verbatim" in summary, "the name is forwarded, not rewritten"
    assert "before the file call" in summary or "before" in summary
    assert "16 MiB" in summary, "the size ceiling is part of the contract"
    assert "Nothing is unpacked" in summary, "the bytes are opaque by contract"


def test_export_docs_row_forwards_the_module_name():
    from pathlib import Path

    doc = Path(__file__).resolve().parents[1] / "docs" / "bridge.md"
    rows = [
        line for line in doc.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `lib.cbb.export`")
    ]
    assert len(rows) == 1
    row = rows[0]
    assert "复用模块名" in row
    assert "17087" in row, "the declaration line is the citation"
    assert "cbb-source.epro2" not in row, "the fixed file name is gone from the contract"


@pytest.mark.parametrize("action", CBB_NATIVE_ACTIONS)
def test_read_only_gate_permits_all_three_actions(action):
    """`None` is the gate's "may go" answer — no new bypass, just a read."""
    assert _read_only_refusal(action) is None


def test_read_only_call_forwards_the_personal_read_with_no_params(door, capsys):
    opened, clients = door

    code = _cmd_bridge_call(_args("--action", "lib.cbb.personal", "--read-only"))

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert READ_ONLY_VIOLATION not in captured.err
    assert len(opened) == 1, "the call has to reach the bridge"
    assert clients[0].sent == [{"action": "lib.cbb.personal", "params": {}}]


def test_read_only_call_forwards_the_library_list_read_with_no_params(door, capsys):
    opened, clients = door

    code = _cmd_bridge_call(_args("--action", "lib.cbb.libraries", "--read-only"))

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert READ_ONLY_VIOLATION not in captured.err
    assert len(opened) == 1
    assert clients[0].sent == [{"action": "lib.cbb.libraries", "params": {}}]


def test_read_only_call_forwards_the_export_pair_untouched(door, capsys):
    opened, clients = door
    params = {"uuid": "cbb-1", "libraryUuid": "lib-user"}

    code = _cmd_bridge_call(
        _args(
            "--action",
            "lib.cbb.export",
            "--params",
            json.dumps(params),
            "--read-only",
        )
    )

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert len(opened) == 1
    assert clients[0].sent == [{"action": "lib.cbb.export", "params": params}]


def test_the_gate_still_refuses_a_write(door, capsys):
    """Negative control: the permission above is the catalogue's, not a blanket pass."""
    opened, _clients = door

    code = _cmd_bridge_call(_args("--action", "doc.focus", "--read-only"))

    captured = capsys.readouterr()
    assert code != 0
    assert opened == []
    assert READ_ONLY_VIOLATION in captured.err
