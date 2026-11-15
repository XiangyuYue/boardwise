"""038Q16A: the `'project'` scope of `lib.cbb.search` in the action catalogue.

The real defect this batch fixes: `lib_Cbb.search('', 'project')` returns the
project's own block (`ca89…`), but the old verification ran `lib_Cbb.get(ca89…,
'project')`, which the host refuses — so a legitimate project result was reported
as `CONNECTOR_ERROR`. The fix is a **reader swap by scope**, not a relaxation:
`lib.cbb.search` keeps `lib_Cbb.get` for every other library and uses
`lib_Symbol.get(uuid, 'project')` for the project scope, requiring the same uuid,
a `name` string, `type === 17` and `libraryType === '2'`.

The behaviour itself is pinned in `connector/tests/library-cbb.test.mjs`
(against the real `buildHandlers()` registry). What is checked here is the
**daemon-facing contract**:

* the entry is still `risk="read"`, connector-owned, with the same four
  parameters — the fix adds no parameter and no new action, so the CLI surface
  and `--read-only` gate are untouched;
* the catalogue says the scope keyword out loud, including that the source
  library uuid is provenance and never replaces the scope, and that other
  libraries keep their checks;
* `bridge call --read-only` still permits it and forwards `libraryUuid:
  'project'` untouched.

The general rules about names, duplicates and gate checks live in
`tests/test_action_catalogue.py` and `tests/test_537a_bridge_readonly.py`.
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

ACTION = "lib.cbb.search"


def _args(*argv: str):
    return build_parser().parse_args(["bridge", "call", *argv])


@pytest.fixture
def door(monkeypatch):
    """Record what would go over the wire; no socket, no daemon, no editor."""
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

    monkeypatch.setattr(
        "boardwise.cli._open_cli",
        lambda args: (FakeClient, BridgeError, 1, "token"),
    )
    return clients


def test_the_action_is_still_a_connector_owned_read():
    spec = action_spec(ACTION)
    assert spec is not None
    assert spec.owner == "connector"
    assert spec.risk == "read", "a scope fix must not re-tier the action"


def test_the_parameter_set_did_not_grow():
    """The project scope is a *value* of libraryUuid, not a new parameter."""
    assert action_spec(ACTION).params == ("query", "libraryUuid", "limit", "page")


def test_schema_names_the_project_scope():
    spec = action_spec(ACTION)
    schema = spec.params_schema
    assert "project" in schema, "the scope keyword is part of the contract"
    assert "lib_Symbol.get" in schema, "…and so is the reader it selects"


def test_summary_states_the_reader_swap_and_the_provenance_rule():
    summary = action_spec(ACTION).summary
    assert "SCOPE keyword, not a uuid" in summary
    assert "lib_Symbol.get(uuid, 'project')" in summary
    assert "lib_Cbb.get is not called at all" in summary, "the old reader is not merely tolerated"
    assert "type===17" in summary, "the symbol type check is contract"
    assert "libraryType==='2'" in summary, "the project-library check is contract"
    assert "sourceLibraryUuid" in summary
    assert "provenance" in summary, "the source uuid must not be read as the scope"
    assert "lib_Symbol.get(project)" in summary, "libraryIdentitySource is named"
    assert "lib_Cbb.get" in summary and "unchanged" in summary, "other libraries keep the old path"


def test_docs_row_states_the_scope_and_the_source_uuid_rule():
    from pathlib import Path

    doc = Path(__file__).resolve().parents[1] / "docs" / "bridge.md"
    rows = [
        line for line in doc.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `lib.cbb.search`")
    ]
    assert len(rows) == 1, "docs/bridge.md §4 must carry exactly one lib.cbb.search row"
    row = rows[0]
    assert "scope keyword, not a uuid" in row
    assert "lib_Symbol.get(entry.uuid, 'project')" in row
    assert "sourceLibraryUuid" in row
    assert "provenance" in row, "the row must not present the source uuid as the scope"
    assert "type === 17" in row and "libraryType === '2'" in row


def test_read_only_gate_still_permits_the_project_scope():
    assert _read_only_refusal(ACTION) is None


def test_read_only_call_forwards_the_project_scope_untouched(door, capsys):
    params = {"query": "", "libraryUuid": "project", "limit": 5, "page": 1}

    code = _cmd_bridge_call(
        _args("--action", ACTION, "--params", json.dumps(params), "--read-only")
    )

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert READ_ONLY_VIOLATION not in captured.err
    assert door[0].sent == [{"action": ACTION, "params": params}]


def test_the_gate_still_refuses_a_write(door, capsys):
    """Negative control: nothing about this batch widens `--read-only`."""
    code = _cmd_bridge_call(_args("--action", "doc.focus", "--read-only"))
    captured = capsys.readouterr()
    assert code != 0
    assert READ_ONLY_VIOLATION in captured.err


# --------------------------------------------------------------------------
# 038Q16B: `sch.place_project_cbb` — the project-local block placement.
#
# The behaviour is pinned in `connector/tests/project-cbb-placement.test.mjs`
# (real `buildHandlers()` registry). Here: the daemon-facing entry, the docs
# row, the generated CLI contract and the two structural promises of the
# source — one shared search, and no library reader/writer anywhere near it.
# --------------------------------------------------------------------------

PLACE = "sch.place_project_cbb"
PLACE_PARAMS = (
    "schematicUuid", "expectedName", "symbolUuid", "projectUuid", "pageUuid",
    "x", "y", "rotation", "mirror",
)


def test_project_placement_is_a_connector_owned_design_write():
    spec = action_spec(PLACE)
    assert spec is not None, f"{PLACE} is not in the catalogue"
    assert spec.owner == "connector"
    assert spec.risk == "write", "a placement is never anything but a write"
    assert spec.design_write is True, "it puts a block into the user's document"
    assert spec.params == PLACE_PARAMS, (
        f"the catalogue's parameter set is the handler's closed set; got {spec.params}"
    )


def test_project_placement_uses_the_placement_timeout():
    from boardwise.bridge.protocol import PLACEMENT_TIMEOUT, timeout_for

    assert timeout_for(PLACE) == PLACEMENT_TIMEOUT, (
        "a placement resolves a library and reads back; the daemon budget must "
        "outlast the connector's own readback"
    )


def test_the_catalogue_states_the_graph_search_and_partial_contract():
    spec = action_spec(PLACE)
    summary = spec.summary
    for token in (
        "dmt_Schematic.getSchematicInfo",
        "parentProjectUuid",
        "CBB Schematic",
        "cbbSymbol",
        "type === 17",
        "lib_Symbol.get(uuid, 'project')",
        "lib.cbb.search",
        "symbolUuid",
        "documentType === 1",
        "sch_PrimitiveComponent.create",
        "libraryType: '2'",
        "block_symbol",
        "getState_Symbol()",
        "getAllPinsByPrimitiveId",
        "partial: true",
        "verified: false",
        "lib_Cbb.get",
        "createCbbSymbol",
    ):
        assert token in summary, f"the summary lost {token!r}"

    schema = spec.params_schema
    for token in ("rotation: fixed 0", "mirror: fixed false", "PAGE_MISMATCH", "detail.guard"):
        assert token in schema, f"the params_schema lost {token!r}"


def test_the_docs_row_carries_the_same_contract():
    from pathlib import Path

    doc = Path(__file__).resolve().parents[1] / "docs" / "bridge.md"
    rows = [
        line for line in doc.read_text(encoding="utf-8").splitlines()
        if line.startswith(f"| `{PLACE}`")
    ]
    assert len(rows) == 1, f"docs/bridge.md §4 must carry exactly one {PLACE} row"
    row = rows[0]
    for token in (
        "CBB Schematic",
        "lib_Symbol.get(uuid, 'project')",
        "exactly one local symbol",
        "createCbbSymbol",
        "block_symbol",
        "getState_Symbol().uuid === symbolUuid",
        "partial: true, verified: false",
        "empty is a real reading",
    ):
        assert token in row, f"the docs row lost {token!r}"
    for param in PLACE_PARAMS:
        assert param in row, f"the docs row does not name {param}"


def test_the_cli_contract_was_regenerated_for_the_project_placement():
    from pathlib import Path

    contract = Path(__file__).resolve().parents[1] / "contracts" / "cli" / "v1.json"
    text = contract.read_text(encoding="utf-8")
    assert PLACE in text, (
        f"contracts/cli/v1.json does not mention {PLACE} — regenerate it with "
        "`PYTHONPATH=. python tools/cli_contract.py --write`"
    )


def test_the_placement_source_reuses_the_search_and_never_writes_a_library():
    import re
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "connector" / "src" / "project-cbb-placement.ts"
    raw = source.read_text(encoding="utf-8")
    # Comments are prose (they *name* the reader that is refused on purpose), so
    # the forbidden-token check runs on the code alone.
    code = re.sub(r"/\*.*?\*/", " ", raw, flags=re.S)
    code = "\n".join(line.split("//")[0] for line in code.splitlines())
    flat = re.sub(r"\s+", " ", code)
    assert "from './library-cbb'" in raw and "libCbbSearch" in flat, (
        "the project scope of lib.cbb.search must be reused, not re-implemented"
    )
    for forbidden in (
        "lib_Cbb.get",
        "lib_Cbb.create",
        "lib_Cbb.modify",
        "lib_Cbb.delete",
        "createCbbSymbol",
        "openProjectInEditor",
        "openSymbolInEditor",
    ):
        assert forbidden not in flat, f"{PLACE} must never reach {forbidden}"
    assert "libraryType: PROJECT_LIBRARY_TYPE" in flat
    assert "const PROJECT_LIBRARY_TYPE = '2'" in flat
    assert "'block_symbol'" in flat
    assert "getAllPinsByPrimitiveId" in flat
