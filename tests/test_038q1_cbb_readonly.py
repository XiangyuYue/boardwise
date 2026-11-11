"""038Q1: the two native-CBB reads in the action catalogue.

`lib.cbb.search` and `lib.cbb.get` are the read-only half of 038Q: a caller can
page through the host's own reuse modules (an empty keyword is the inventory
entry point) and read one module's identity, and can do neither with any write.
The connector side is pinned in `connector/tests/library-cbb.test.mjs`; what is
checked here is the **daemon-facing contract** these two entries have to carry:

* both are `risk="read"` and connector-owned — the catalogue is the only
  authority the CLI's `--read-only` gate consults, so a mis-tiered entry would
  either open a write to a delegated caller or lock a read out;
* the declared parameters are the closed set the handlers accept, and the
  schema says out loud what the contract needs a reader to know: the empty
  keyword, the 1..100 limit and page floor, and the system-library default;
* `bridge call --read-only` **permits** both and forwards them untouched — the
  property the gate is for, checked through the CLI's own function rather than
  by re-implementing the relation here.

This is a focused pair, not a second catalogue framework: the general rules
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

CBB_ACTIONS = ("lib.cbb.search", "lib.cbb.get")


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


def test_both_actions_are_connector_owned_reads():
    """`risk` is what `--read-only` reads, so the tier is the contract."""
    for name in CBB_ACTIONS:
        spec = action_spec(name)
        assert spec is not None, f"{name} is not in the catalogue"
        assert spec.owner == "connector", f"{name} is answered by the connector"
        assert spec.risk == "read", f"{name} must never be anything but read"


def test_the_two_actions_declare_only_the_parameters_they_accept():
    assert action_spec("lib.cbb.search").params == ("query", "libraryUuid", "limit", "page")
    assert action_spec("lib.cbb.get").params == ("uuid", "libraryUuid")


def test_search_schema_states_the_inventory_contract():
    """A reader of the catalogue alone has to learn the three traps."""
    spec = action_spec("lib.cbb.search")
    schema = spec.params_schema
    assert "query" in schema and "empty" in schema
    assert "1..100" in schema, "the limit range is part of the contract"
    assert "20" in schema, "the limit default is part of the contract"
    assert "page" in schema and ">=1" in schema
    assert "system library" in schema, "an omitted library means the host's own"
    assert "lib_Cbb.search" in spec.returns
    assert "count" in spec.returns, "the page count is the honest number, not a total"


def test_get_schema_states_the_identity_contract():
    spec = action_spec("lib.cbb.get")
    assert "uuid" in spec.params_schema
    assert "libraryUuid" in spec.params_schema
    assert "system library" in spec.params_schema
    assert "lib_Cbb.get" in spec.returns
    assert "found" in spec.returns and "boards" in spec.summary


@pytest.mark.parametrize("action", CBB_ACTIONS)
def test_read_only_gate_permits_both_actions(action):
    """`None` is the gate's "may go" answer — no new bypass, just a read."""
    assert _read_only_refusal(action) is None


def test_read_only_call_forwards_the_search_page_untouched(door, capsys):
    """The empty keyword and the page numbers reach the wire exactly as typed."""
    opened, clients = door
    params = {"query": "", "limit": 3, "page": 2}

    code = _cmd_bridge_call(
        _args(
            "--action",
            "lib.cbb.search",
            "--params",
            json.dumps(params),
            "--read-only",
        )
    )

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert READ_ONLY_VIOLATION not in captured.err
    assert len(opened) == 1, "the call has to reach the bridge"
    assert clients[0].sent == [{"action": "lib.cbb.search", "params": params}]


def test_read_only_call_forwards_get_with_its_uuid(door, capsys):
    opened, clients = door
    params = {"uuid": "cbb-1", "libraryUuid": "lib-user"}

    code = _cmd_bridge_call(
        _args(
            "--action",
            "lib.cbb.get",
            "--params",
            json.dumps(params),
            "--read-only",
        )
    )

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert len(opened) == 1
    assert clients[0].sent == [{"action": "lib.cbb.get", "params": params}]


def test_the_gate_still_refuses_a_write(door, capsys):
    """Negative control: the permission above is the catalogue's, not a blanket pass."""
    opened, _clients = door

    code = _cmd_bridge_call(_args("--action", "doc.focus", "--read-only"))

    captured = capsys.readouterr()
    assert code != 0
    assert opened == []
    assert READ_ONLY_VIOLATION in captured.err
