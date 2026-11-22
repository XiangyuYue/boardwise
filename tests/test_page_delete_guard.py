"""The page-deletion guard (2026-11-19).

xianyuyijinban's rule, verbatim: 「非必要不删图，即便画错了也只允许清理掉图里的器件和
导线，而不是把整张图页删掉。除非用户下达了指令或者是有多余的图页不然不允许删掉。」

The repair is not prose in a recovery note but the daemon's **existing** confirmation
gate: `doc.delete_page` is filed in the `create` tier, so it is refused with
``CONFIRMATION_REQUIRED`` and nothing is forwarded unless ``params.confirm is True``.
A spare page is a *reason to ask the user*, never a decision an agent makes for
itself — which is what a gate can enforce and a sentence cannot.

What is pinned here, each against a real mechanism rather than a constant:

1. no ``confirm`` → refused by the real gate, and **zero frames** reach the connector
   (over a real socket, with a stand-in connector);
2. only the boolean ``True`` lifts it, and ``confirm`` is consumed on the way through,
   so the connector receives ``{"pageUuid": …}`` and nothing else;
3. the CLI is the party that supplies it — ``--yes`` non-interactively, or the
   interactive question, and neither answers on the user's behalf when there is no
   terminal;
4. ``draw discard`` — the "the drawing came out wrong, keep the page" path — never
   reaches ``doc.delete_page`` and never creates a page: it deletes the primitives
   the plan drew, and leaves everything else exactly as it was.
"""

from __future__ import annotations

import io
import json

import pytest

import test_bridge as tb
from boardwise import cli
from boardwise.bridge.daemon import BridgeDaemon
from boardwise.bridge.protocol import BridgeError, ErrorCodes, action_spec

run = tb.run
TOKEN = tb.TOKEN

#: What the flow under test actually asks for. Kept in one place so a rename of
#: the parameter shows up as a failing guard, not as a passing test.
PAGE = "page-1"


# --------------------------------------------------------------------------
# 1. the gate itself — no socket needed: it runs before anything is forwarded
# --------------------------------------------------------------------------


def test_a_delete_without_confirm_is_refused_by_the_gate(tmp_path):
    """The classification IS the enforcement: `risk` drives this gate.

    A deletion filed as `write` passes the gate with no consent at all — which is
    exactly the state this test was written against (risk was `write` until
    2026-11-19). The refusal must also be liftable, so it has to name the flag.
    """
    daemon = BridgeDaemon(token=TOKEN, home=tmp_path)
    with pytest.raises(BridgeError) as caught:
        run(daemon.handle_request("doc.delete_page", {"pageUuid": PAGE}, "cli"))
    error = caught.value
    assert error.code == ErrorCodes.CONFIRMATION_REQUIRED
    assert error.detail["action"] == "doc.delete_page"
    assert error.detail["risk"] == "create"
    assert error.detail["confirm"] is None
    assert "confirm" in error.message
    assert "deletes a schematic page and everything on it" in error.message
    assert "creates a new document" not in error.message


@pytest.mark.parametrize(
    "confirm", ["true", "yes", 1, 0, [], {}, "True", None, False]
)
def test_only_the_boolean_true_lifts_the_delete_guard(tmp_path, confirm):
    """Identity, not truthiness — the same rule every gated action lives under.

    ``"yes"`` and ``1`` are what a script reaches for; a guard that accepts them
    is a guard whose meaning depends on the caller's language.
    """
    daemon = BridgeDaemon(token=TOKEN, home=tmp_path)
    with pytest.raises(BridgeError) as caught:
        run(
            daemon.handle_request(
                "doc.delete_page", {"pageUuid": PAGE, "confirm": confirm}, "cli"
            )
        )
    assert caught.value.code == ErrorCodes.CONFIRMATION_REQUIRED
    assert caught.value.detail["confirm"] == confirm


def test_confirm_is_consumed_so_the_connector_never_sees_it(tmp_path):
    """The connector stays a plain executor: it cannot be talked into deleting.

    The flag is stripped by the daemon *before* the forward, so what the editor's
    extension receives is the address of the page and nothing else — a
    connector-side action has no confirmation concept to consult or to fake.
    """
    daemon = BridgeDaemon(token=TOKEN, home=tmp_path)
    spec = action_spec("doc.delete_page")
    forwarded = daemon._gate_confirmation(spec, {"pageUuid": PAGE, "confirm": True})
    assert forwarded == {"pageUuid": PAGE}


# --------------------------------------------------------------------------
# 2. end to end over a real socket — the "nothing was forwarded" half
# --------------------------------------------------------------------------


def test_a_refused_page_delete_forwards_nothing_and_a_confirmed_one_forwards_only_the_uuid(
    tmp_path,
):
    """Both directions in one scenario, so the same socket proves both halves."""

    async def scenario():
        daemon = tb._daemon(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            connector_ws, _ = await tb._hello(port, "connector", token=TOKEN)
            fake = tb.FakeConnector(
                connector_ws,
                responses={"doc.delete_page": {"deleted": True, "pageUuid": PAGE,
                                               "name": "P1"}},
            )
            import asyncio

            serving = asyncio.create_task(fake.serve())

            cli_ws, _ = await tb._hello(port, "cli", token=TOKEN)
            await cli_ws.send(
                tb.request_frame("doc.delete_page", {"pageUuid": PAGE}, id="r1")
            )
            reply = await tb._recv_frame(cli_ws)
            assert reply["ok"] is False
            assert reply["error"]["code"] == ErrorCodes.CONFIRMATION_REQUIRED

            # Give any (wrong) forward a chance to arrive before asserting.
            await asyncio.sleep(0.05)
            assert fake.received == [], (
                "the refused deletion was forwarded to the editor anyway: "
                f"{fake.received}"
            )

            # …and with the confirmation it does go through, without the flag.
            await cli_ws.send(
                tb.request_frame(
                    "doc.delete_page", {"pageUuid": PAGE, "confirm": True}, id="r2"
                )
            )
            reply2 = await tb._recv_frame(cli_ws)
            assert reply2["ok"] is True
            assert reply2["data"] == {"deleted": True, "pageUuid": PAGE, "name": "P1"}
            assert len(fake.received) == 1
            forwarded = fake.received[0]
            assert forwarded["action"] == "doc.delete_page"
            assert forwarded["params"] == {"pageUuid": PAGE}, (
                "confirm reached the connector: "
                f"{forwarded['params']}"
            )

            serving.cancel()
            await connector_ws.close()
            await cli_ws.close()

    run(scenario())


# --------------------------------------------------------------------------
# 3. the CLI is the party that supplies the confirmation
# --------------------------------------------------------------------------


class _RecordingClient:
    """Answers like the gated daemon does; records what the CLI asked for."""

    instance = None

    def __init__(self):
        self.calls: list[dict] = []

    @classmethod
    async def open(cls, *_args, **_kwargs):
        return cls.instance

    async def call(self, action, params):
        self.calls.append({"action": action, "params": dict(params)})
        if params.get("confirm") is not True:
            raise BridgeError(
                ErrorCodes.CONFIRMATION_REQUIRED,
                f"{action} deletes a page; re-send with confirm: true",
                {"action": action, "risk": "create", "confirm": params.get("confirm")},
            )
        return {"deleted": True, "pageUuid": PAGE, "name": "P1"}

    async def close(self):
        return None


def _patch(monkeypatch) -> _RecordingClient:
    _RecordingClient.instance = _RecordingClient()
    monkeypatch.setattr(
        cli, "_open_cli", lambda _args: (_RecordingClient, BridgeError, 61190, "t")
    )
    return _RecordingClient.instance


def _args(*extra: str):
    parser = cli.build_parser()
    return parser.parse_args(
        ["bridge", "call", "--action", "doc.delete_page",
         "--params", json.dumps({"pageUuid": PAGE}), *extra]
    )


def _no_tty(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))


def _tty(monkeypatch, answer: str):
    class TTY(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr("sys.stdin", TTY(""))
    monkeypatch.setattr("builtins.input", lambda _prompt="": answer)


def test_yes_confirms_the_delete_without_asking(monkeypatch):
    client = _patch(monkeypatch)
    _no_tty(monkeypatch)

    assert cli._cmd_bridge_call(_args("--yes")) == 0
    assert len(client.calls) == 1, "one call, carrying the confirmation"
    assert client.calls[0]["action"] == "doc.delete_page"
    assert client.calls[0]["params"] == {"pageUuid": PAGE, "confirm": True}


def test_without_yes_and_without_a_terminal_the_delete_does_not_happen(
    monkeypatch, capsys
):
    """A prompt nobody can see must not become a yes — for a deletion least of all."""
    client = _patch(monkeypatch)
    _no_tty(monkeypatch)

    assert cli._cmd_bridge_call(_args()) == 1
    assert len(client.calls) == 1
    assert "confirm" not in client.calls[0]["params"]
    err = capsys.readouterr().err
    assert "--yes" in err and "not a terminal" in err


def test_answering_yes_retries_the_delete_once_with_the_confirmation(monkeypatch):
    client = _patch(monkeypatch)
    _tty(monkeypatch, "y")

    assert cli._cmd_bridge_call(_args()) == 0
    assert len(client.calls) == 2, "one refusal, one retry"
    assert "confirm" not in client.calls[0]["params"]
    assert client.calls[1]["params"]["confirm"] is True


@pytest.mark.parametrize("answer", ["", "n", "no", "maybe"])
def test_anything_but_yes_declines_the_delete(monkeypatch, answer):
    client = _patch(monkeypatch)
    _tty(monkeypatch, answer)

    assert cli._cmd_bridge_call(_args()) == 1
    assert len(client.calls) == 1, f"answer {answer!r} must not delete a page"


# --------------------------------------------------------------------------
# 4. the catalogue says the same thing the gate enforces
# --------------------------------------------------------------------------


def test_the_entry_is_filed_in_the_gated_tier_and_says_what_to_do_instead():
    """A reader of the catalogue must be able to see the rule and the alternative."""
    spec = action_spec("doc.delete_page")
    assert spec is not None
    assert spec.risk == "create", (
        "a `write` filing means the confirmation gate never runs — the rule "
        "would be prose again"
    )
    assert "pageUuid" in spec.params, "the page guard must not be dropped"
    assert "confirm" in spec.params, (
        "a gated action that does not declare confirm can never be lifted"
    )
    assert "confirm" in spec.params_schema
    # "画错了也只允许清理掉图里的器件和导线" — the catalogue names the alternative.
    assert "sch.delete_primitives" in spec.summary, (
        "the entry must point at the primitive cleanup, or a caller reading it "
        "has no way to know the page is meant to survive"
    )


# --------------------------------------------------------------------------
# 5. `draw discard` is that alternative, and it stays that alternative
# --------------------------------------------------------------------------


def test_draw_discard_deletes_planned_primitives_and_never_touches_the_page(
    monkeypatch, tmp_path, capsys
):
    """The cleanup path an agent is *supposed* to reach for, driven for real.

    057's page fake records every action and answers only the ones the flow is
    allowed to call, so this is the whole `discard` run end to end: what must
    hold is that no frame for `doc.delete_page` (nor `sch.doc.new`) was ever
    emitted, that the ids deleted are exactly the ones apply drew, and that the
    page's pre-existing primitives come out byte-identical.
    """
    import test_057_draw_page_cli as t57

    editor, plan_path, _plan, _circuit, _presentation = t57._landed(
        monkeypatch, tmp_path, capsys
    )
    seeded = {ident: item for ident, item in editor.snapshot().items() if "old" in ident}
    drawn = set(editor.snapshot()) - set(seeded)
    assert drawn, "the apply should have drawn something for discard to clean up"
    calls_before = list(editor.calls)

    code, report = t57._discard(plan_path, "--save", tmp_path=tmp_path)
    assert code == 0, report["notes"]
    assert report["outcome"] == "discarded"

    emitted = editor.calls[len(calls_before):]
    assert "doc.delete_page" not in emitted, (
        f"discard deleted the page instead of its drawing: {emitted}"
    )
    assert "sch.doc.new" not in emitted, (
        f"discard created a page instead of reusing the one it drew on: {emitted}"
    )
    deleted = [ident for batch in editor.deletes for ident in batch]
    assert set(deleted) == drawn, (
        "discard touched primitives outside the plan's drawing: "
        f"unexpected {sorted(set(deleted) - drawn)}, missing {sorted(drawn - set(deleted))}"
    )
    assert editor.snapshot() == seeded, (
        "the page's own primitives did not survive the cleanup"
    )
    assert report["verify"]["remaining"] == []
    assert report["verify"]["outOfScope"] == []
