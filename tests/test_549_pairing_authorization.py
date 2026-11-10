"""549: a connector pairs only after the user authorises it, from the CLI.

The security property this suite exists for is one sentence long: **nothing a
connector can do on its own gets it paired.** Before 549 a newcomer could write
`~/.boardwise/connector-token` by arriving while no record existed (and, with a
record but no window attached, replace the record it found). The mitigation at
the time was an `Origin` gate that exempted the one measured editor Origin — and
that is what refused a real editor: EDA 4.1.71 reports
`https://pro.lceda.cn`, not `https://client`.

So the gate moved to something a page cannot produce and a user can: an
in-memory grant minted by `pair.authorize` (CLI role only) and presented by the
connector as `hello.pairCode`. These tests drive the *real* socket and the real
action path — no test here writes `daemon.pair_grant` directly except to age a
grant out, which is the one thing a test cannot do in real time.

What is deliberately *not* covered here: the Connector's own CSPRNG and its
display of the code (TypeScript, `connector/tests/`), the CLI's `bridge pair`
wiring, and any real editor. Local, offline only — no daemon on 61190, no EDA.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time

import pytest
import websockets

import test_bridge as tb
from boardwise.bridge.daemon import (
    AUDIT_PAIRING,
    AUDIT_PAIR_AUTHORIZE,
    AUDIT_REPAIRING,
    PAIR_GRANT_TTL,
    BridgeDaemon,
    connector_fingerprint,
    connector_token_path,
    load_connector_token,
    mask_pair_code,
    normalise_pair_code,
    revoke_connector_token,
)
from boardwise.bridge.protocol import (
    PROTOCOL_VERSION,
    BridgeError,
    ErrorCodes,
    action_spec,
    decode_frame,
    request_frame,
)

#: The value EDA 4.1.71 sends, and the Origin this whole task started from.
PROLCEDA = "https://pro.lceda.cn"
CODE = "ABCD-EFGH"
OTHER_CODE = "JKMN-PQRS"
TOKEN = tb.TOKEN


def _daemon(home) -> BridgeDaemon:
    """A daemon with **no** authorisation — the interesting starting state.

    ``home`` is always the caller's own `tmp_path` (or a subdirectory of it):
    the daemon appends its audit log under `<home>/audit/`, and a bare relative
    path here used to leave that directory in the repository root.
    """
    return BridgeDaemon(token=TOKEN, home=home, write_projects={"*"})


async def _pair(port, token, code=CODE, origin=PROLCEDA, client="fake"):
    return await tb._hello(
        port, "connector", token=token, client=client,
        headers=None if origin is None else {"Origin": origin},
        pairCode=code,
    )


def _authorised(home) -> BridgeDaemon:
    daemon = _daemon(home)
    tb.authorize_pairing(daemon, CODE)
    return daemon


# --------------------------------------------------------------------------
# the evidence: pro.lceda.cn, unauthorised, then authorised
# --------------------------------------------------------------------------


def test_pro_lceda_cn_cannot_pair_without_an_authorisation(tmp_path):
    """The 549 reproduction: the real Origin, a fresh daemon, zero records."""

    async def scenario():
        daemon = _daemon(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "generated-by-eda-4-1-71")
            assert reply["ok"] is False
            assert reply["error"]["code"] == ErrorCodes.UNAUTHENTICATED
            assert reply["error"]["detail"]["pairCodeRequired"] is True
            assert reply["error"]["detail"]["reason"] == "no-grant"
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) is None
    assert not connector_token_path(tmp_path).exists()
    assert not [r for r in tb._audit_records(tmp_path) if r["action"] == AUDIT_PAIRING]


def test_pro_lceda_cn_pairs_once_authorised(tmp_path):
    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "generated-by-eda-4-1-71")
            assert reply["ok"] is True, reply
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "generated-by-eda-4-1-71"


def test_the_authorisation_records_the_fingerprint_it_was_issued_against(tmp_path):
    """`pair.authorize` pins the record it saw, and the answer is a receipt.

    Both halves matter: the pin is what makes a grant single-use against one
    state (next test), and the receipt is what a CLI can print without ever
    putting the code — let alone a token — on a terminal or in a log.
    """
    daemon = _daemon(tmp_path)
    receipt = daemon._local_action("pair.authorize", role="cli", params={"code": CODE})

    assert receipt["authorized"] is True
    assert receipt["fingerprint"] is None, "nothing was paired yet"
    assert receipt["expiresIn"] == int(PAIR_GRANT_TTL)
    assert receipt["pairCode"] == mask_pair_code(normalise_pair_code(CODE))
    assert CODE.replace("-", "") not in json.dumps(receipt)
    grant = daemon.pair_grant
    assert grant is not None
    assert grant.code == "ABCDEFGH", "normalised: case and separators folded"
    assert grant.fingerprint is None
    assert grant.failures == 0
    assert 0 < grant.remaining(time.monotonic()) <= PAIR_GRANT_TTL

    records = [r for r in tb._audit_records(tmp_path)
               if r["action"] == AUDIT_PAIR_AUTHORIZE]
    assert len(records) == 1
    assert records[0]["ok"] is True
    assert records[0]["pairCode"] == mask_pair_code("ABCDEFGH")


def test_a_code_typed_any_way_the_user_likes_is_the_same_code(tmp_path):
    """`abcd efgh` is the code on the screen; a comparison must not care."""
    daemon = _daemon(tmp_path)
    daemon._local_action("pair.authorize", role="cli", params={"code": " abcd efgh "})

    async def scenario():
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "token-a", code="ABCD-EFGH")
            assert reply["ok"] is True, reply
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "token-a"


def test_whitespace_inside_a_code_means_the_same_thing_on_both_sides(tmp_path):
    """The Connector folds `[-_\\s]`; the daemon must not fold a narrower set (549 review).

    A code is read off the editor screen and typed — often pasted out of a chat
    window or a web page, where the gap between the groups can be U+00A0 rather
    than U+0020. JS `\\s` is *Unicode* whitespace, so the Connector's own copy of
    the code normalises to eight symbols; a daemon that only stripped
    `" \\t\\n\\r"` counted nine and answered `BAD_REQUEST` to a code the editor
    had just shown the user. Both halves are pinned here: the fold itself, and a
    real authorisation whose code arrives with an NBSP in it.
    """
    for gap in ("\u00a0", "\u3000", "\u202f", "\u2009", "\u2028"):
        assert normalise_pair_code(f"ABCD{gap}EFGH") == "ABCDEFGH", repr(gap)
        assert normalise_pair_code(f"abcd{gap}efgh") == "ABCDEFGH", repr(gap)

    # Whitespace *around* the whole code is folded too, and a string that is
    # nothing but whitespace still normalises to nothing — never to a wildcard.
    assert normalise_pair_code("\u00a0ABCD-EFGH\u00a0") == "ABCDEFGH"
    assert normalise_pair_code("\u00a0\u3000\t") == ""

    # U+200B is not whitespace in either language (`\s` does not match it), so it
    # stays a real character: folding it would be the daemon inventing a symbol.
    assert normalise_pair_code("ABCD\u200bEFGH") == "ABCD\u200bEFGH"

    daemon = _daemon(tmp_path)
    daemon._local_action("pair.authorize", role="cli", params={"code": "ABCD\u00a0EFGH"})

    async def scenario():
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "token-a", code="ABCD-EFGH")
            assert reply["ok"] is True, reply
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "token-a"


# --------------------------------------------------------------------------
# the refusals, one reason at a time
# --------------------------------------------------------------------------


def test_a_wrong_code_is_refused_and_counted(tmp_path):
    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "token-a", code=OTHER_CODE)
            assert reply["ok"] is False
            assert reply["error"]["code"] == ErrorCodes.UNAUTHENTICATED
            assert reply["error"]["detail"]["reason"] == "code-mismatch"
            # The refusal says *why* and nothing else: the socket has
            # authenticated nothing, so the count and the fingerprints stay on
            # this side of the wire (they go to the audit — see the DoS test).
            assert set(reply["error"]["detail"]) == {"pairCodeRequired", "reason"}
            await ws.close()
            # The grant survives a wrong code: the user mistyping once must not
            # cost them the whole authorisation.
            assert daemon.pair_grant is not None
            assert daemon.pair_grant.failures == 1

            ws, reply = await _pair(port, "token-a")
            assert reply["ok"] is True, "the right code still works afterwards"
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "token-a"
    hello_refusals = [r for r in tb._audit_records(tmp_path)
                      if r["action"] == "hello" and not r["ok"]]
    assert hello_refusals[-1]["reason"] == "code-mismatch", hello_refusals[-1]
    assert hello_refusals[-1]["pairCodeFailures"] == 1, hello_refusals[-1]


def test_a_wrong_code_never_voids_the_grant(tmp_path):
    """The denial-of-service the red team found, closed at the root (549).

    A failure *budget* was the original design: ten wrong codes voided the grant.
    The count cannot tell one peer from another — a socket's port is free, and a
    page in the user's browser can open as many as it likes — so any
    unauthenticated peer could deliberately spend the user's authorisation and
    leave them with a "pair code is void" they never caused. The guard was the
    attack. Now a wrong code is bookkeeping (counted, audited, refused) and the
    grant survives any number of them, from the same peer or from new ones.

    Refusing to pair *is* what a wrong code achieves, and the grant is still
    bounded by what it always was: one code, one five-minute window, one pairing.
    """

    async def scenario():
        daemon = _authorised(tmp_path)
        assert daemon.pair_grant is not None

        # The same peer, past the old budget. Called at the level the handshake
        # calls: `_authenticate_connector` takes the peer string, and nothing in
        # the check uses it — which is exactly why a per-peer count could not have
        # fixed this.
        for _ in range(12):
            with pytest.raises(BridgeError) as caught:
                daemon._authenticate_connector(
                    "token-a", "fake", "127.0.0.1:40000", None, OTHER_CODE,
                )
            assert caught.value.detail == {
                "pairCodeRequired": True, "reason": "code-mismatch",
            }
        assert daemon.pair_grant is not None, "the grant must outlive wrong codes"
        assert daemon.pair_grant.failures == 12
        assert load_connector_token(tmp_path) is None, "nothing was written"

        server, port = await tb._start(daemon)
        async with server:
            # …and the same again over the wire, each from a fresh peer.
            for _ in range(3):
                ws, reply = await _pair(port, "token-a", code=OTHER_CODE)
                assert reply["ok"] is False
                assert reply["error"]["detail"]["reason"] == "code-mismatch"
                await ws.close()
                await tb._until(lambda: not daemon.has_connector())

            ws, reply = await _pair(port, "token-a")
            assert reply["ok"] is True, "the right code still pairs: " + str(reply)
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "token-a"
    audit = json.dumps(tb._audit_records(tmp_path))
    assert "code-attempts-exhausted" not in audit, (
        "there is no exhausting a grant any more"
    )


def test_an_expired_grant_is_refused_and_dropped(tmp_path):
    """Five minutes, `time.monotonic` — aged here rather than slept through."""

    async def scenario():
        daemon = _authorised(tmp_path)
        assert daemon.pair_grant is not None
        # The one thing a test cannot do in real time: move the deadline.
        daemon.pair_grant.expires_at = time.monotonic() - 0.001
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "token-a")
            assert reply["ok"] is False
            assert reply["error"]["detail"]["reason"] == "grant-expired"
            assert daemon.pair_grant is None, "an expired grant is never reusable"
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) is None


def test_a_reused_grant_is_refused(tmp_path):
    """One authorisation, one pairing: the second connector is a stranger."""

    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "token-a")
            assert reply["ok"] is True
            await ws.close()
            await tb._until(lambda: not daemon.has_connector())

            ws, reply = await _pair(port, "token-b")
            assert reply["ok"] is False
            assert reply["error"]["detail"]["reason"] == "no-grant"
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "token-a"


def test_a_revoked_record_voids_the_grant(tmp_path):
    """The fingerprint the grant pinned is gone, so the grant no longer applies.

    `bridge revoke` deletes the record; an authorisation issued against the old
    one must not become a licence to write a *different* record.
    """

    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "token-a")
            assert reply["ok"] is True
            await ws.close()
            await tb._until(lambda: not daemon.has_connector())

            # Authorise again — against token-a's record — then revoke.
            tb.authorize_pairing(daemon, CODE)
            assert daemon.pair_grant is not None
            assert daemon.pair_grant.fingerprint == connector_fingerprint("token-a")
            revoke_connector_token(tmp_path)

            ws, reply = await _pair(port, "token-b")
            assert reply["ok"] is False
            assert reply["error"]["detail"]["reason"] == "record-changed"
            assert daemon.pair_grant is None
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) is None


def test_a_daemon_restart_drops_the_grant(tmp_path):
    """Memory only, by design: nothing to inherit, nothing to leave behind."""

    async def scenario():
        daemon = _authorised(tmp_path)
        # A restart is a new object in real life and a new process: same home,
        # nothing inherited.
        restarted = _daemon(tmp_path)
        assert restarted.pair_grant is None
        server, port = await tb._start(restarted)
        async with server:
            ws, reply = await _pair(port, "token-a")
            assert reply["ok"] is False
            assert reply["error"]["detail"]["reason"] == "no-grant"
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) is None


def test_a_connector_without_a_code_cannot_pair_and_is_told_to_upgrade(tmp_path):
    """A pre-549 connector sends no `pairCode`. It must not fall back to TOFU."""

    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "old-connector", code=None)
            assert reply["ok"] is False
            assert reply["error"]["detail"]["reason"] == "code-missing"
            assert "update the connector" in reply["error"]["message"], reply["error"]
            # …and the missing code does not spend the grant, so a rebuilt
            # connector with the same authorisation can still pair.
            assert daemon.pair_grant is not None
            assert daemon.pair_grant.failures == 0
            await ws.close()

            ws, reply = await _pair(port, "new-connector")
            assert reply["ok"] is True, reply
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "new-connector"


def test_an_old_connector_cannot_silently_replace_an_unattended_pairing(tmp_path):
    """The other branch TOFU had: a record exists, its window is gone.

    Before 549 this is where a newcomer took the record over (004f's sideload
    self-heal). Now the record stays, and the newcomer is refused whatever it
    presents — with a code, without one, or with the right one after the grant
    was spent by the first pairing.
    """

    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "paired-one")
            assert reply["ok"] is True
            await ws.close()
            await tb._until(lambda: not daemon.has_connector())

            for code, expected in (
                (None, "no-grant"),
                (CODE, "no-grant"),
                (OTHER_CODE, "no-grant"),
            ):
                ws, reply = await _pair(port, "sideloaded-build", code=code)
                assert reply["ok"] is False, code
                assert reply["error"]["detail"]["reason"] == expected, (code, reply)
                await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "paired-one"
    assert not [r for r in tb._audit_records(tmp_path) if r["action"] == AUDIT_REPAIRING]


# --------------------------------------------------------------------------
# single slot, and the connector that stays paired
# --------------------------------------------------------------------------


def test_only_the_latest_authorised_code_works(tmp_path):
    """Two connectors, two codes, one authorisation: only the last one is live."""

    async def scenario():
        daemon = _daemon(tmp_path)
        tb.authorize_pairing(daemon, CODE)
        tb.authorize_pairing(daemon, OTHER_CODE)   # replaces, and is audited
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "token-a", code=CODE)
            assert reply["ok"] is False
            assert reply["error"]["detail"]["reason"] == "code-mismatch"
            await ws.close()

            ws, reply = await _pair(port, "token-a", code=OTHER_CODE)
            assert reply["ok"] is True, reply
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "token-a"
    authorisations = [r for r in tb._audit_records(tmp_path)
                      if r["action"] == AUDIT_PAIR_AUTHORIZE]
    assert len(authorisations) == 2, "each explicit authorisation is audited"
    assert authorisations[1]["replacedPairCode"] == mask_pair_code("ABCDEFGH")


def test_a_valid_old_pairing_reconnects_at_any_origin_without_a_grant(tmp_path):
    """The half of the rule that must not regress: the record is the credential."""

    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "paired-one")
            assert reply["ok"] is True
            await ws.close()
            await tb._until(lambda: not daemon.has_connector())
            assert daemon.pair_grant is None, "spent by the pairing above"

            for origin in (PROLCEDA, "https://client", "http://evil.example", None):
                ws, reply = await _pair(
                    port, "paired-one", code=None, origin=origin,
                )
                assert reply["ok"] is True, (origin, reply)
                await ws.close()
                await tb._until(lambda: not daemon.has_connector())

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "paired-one"
    assert len([r for r in tb._audit_records(tmp_path)
                if r["action"] == AUDIT_PAIRING]) == 1


def test_the_hello_receipt_says_whether_this_handshake_wrote_the_record(tmp_path):
    """`pairCodeUsed` is per handshake, not "the last pairing this daemon saw".

    It is what lets the connector retire a code the moment that code has done its
    one job, and it must be *this* handshake's answer: a reconnect with the token
    already on file never consults a grant, so its code was not spent and must not
    be reported as spent. A process-global "the last pairing was authorised"
    would make the second window's greeting depend on the first window's past —
    the shape of bug this field exists to avoid.
    """

    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            # First pairing: a grant was presented and a record written.
            ws, reply = await _pair(port, "paired-one")
            assert reply["ok"] is True, reply
            assert reply["data"]["pairCodeUsed"] is True, reply
            await ws.close()
            await tb._until(lambda: not daemon.has_connector())
            assert daemon.pair_grant is None, "spent by the pairing above"

            # The same connector coming back: the token is the credential, the
            # code is not even looked at, and nothing was written.
            for code in (CODE, None):
                ws, reply = await _pair(port, "paired-one", code=code)
                assert reply["ok"] is True, (code, reply)
                assert reply["data"]["pairCodeUsed"] is False, (code, reply)
                await ws.close()
                await tb._until(lambda: not daemon.has_connector())

            # An explicit re-pair: another authorisation, another write, and the
            # receipt says so again — the code the connector was showing before
            # this point is the one that was spent.
            tb.authorize_pairing(daemon, OTHER_CODE)
            ws, reply = await _pair(port, "token-b", code=OTHER_CODE)
            assert reply["ok"] is True, reply
            assert reply["data"]["pairCodeUsed"] is True, reply
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "token-b"
    pairings = [r for r in tb._audit_records(tmp_path)
                if r["action"] in (AUDIT_PAIRING, AUDIT_REPAIRING)]
    assert [r["ok"] for r in pairings] == [True, True], (
        "two writes: the first pairing and the re-pair"
    )


def test_a_cli_connection_never_reports_a_pairing_write(tmp_path):
    """The field is about pairing, and a CLI connection never pairs."""

    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            ws = await websockets.connect(
                f"ws://127.0.0.1:{port}", max_size=None)
            await tb._recv_event(ws)
            await ws.send(request_frame("hello", {
                "token": TOKEN, "role": "cli", "protocol": PROTOCOL_VERSION,
            }, id="hello"))
            reply = await tb._recv_frame(ws)
            assert reply["ok"] is True, reply
            assert reply["data"]["pairCodeUsed"] is False, reply
            await ws.close()

    tb.run(scenario())


def test_a_live_window_is_not_displaced_by_an_authorised_re_pair(tmp_path):
    """An authorisation is not a licence to take a pairing off a live window.

    It also must not be *spent* by the refusal: closing that window and retrying
    inside the five minutes is the user's next move, and it works.
    """

    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            live, reply = await _pair(port, "paired-one")
            assert reply["ok"] is True

            tb.authorize_pairing(daemon, OTHER_CODE)
            ws, reply = await _pair(port, "token-b", code=OTHER_CODE)
            assert reply["ok"] is False
            assert reply["error"]["detail"]["reason"] == "connector-attached"
            assert daemon.pair_grant is not None, "the refusal does not spend it"
            await ws.close()
            await live.close()
            await tb._until(lambda: not daemon.has_connector())

            ws, reply = await _pair(port, "token-b", code=OTHER_CODE)
            assert reply["ok"] is True, reply
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "token-b"


def test_two_simultaneous_handshakes_cannot_both_spend_one_grant(tmp_path):
    """Check-and-write has no `await` in it, so exactly one of them wins.

    That is the whole reason the daemon has no cross-process lock: the grant is
    checked and spent inside one event loop turn per handshake, so two sockets
    arriving together are ordered, not interleaved.
    """

    async def scenario():
        daemon = _authorised(tmp_path)
        assert not inspect.iscoroutinefunction(daemon._authenticate_connector)
        assert not inspect.iscoroutinefunction(daemon._pair)
        server, port = await tb._start(daemon)
        async with server:
            results = await asyncio.gather(
                _pair(port, "racer-one"), _pair(port, "racer-two"),
                return_exceptions=True,
            )
            oks = [reply["ok"] for _, reply in results if isinstance(reply, dict)]
            assert oks.count(True) == 1, results
            for ws, _ in results:
                await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) in ("racer-one", "racer-two")
    assert daemon_grant_is_spent(tmp_path)


def daemon_grant_is_spent(home) -> bool:
    """A fresh daemon on the same home has no grant — i.e. nothing persisted."""
    return _daemon(home).pair_grant is None


def test_a_failed_write_keeps_the_grant(tmp_path):
    """The record could not be written: the authorisation is untouched.

    Simulated by putting a *directory* where the record file goes — the real
    failure mode is a permissions problem on `~/.boardwise`, and the property
    under test is the same one: a failed write must not cost the user their
    five-minute window, because the code was never wrong. The write is atomic
    now (temp file + `os.replace`), so the failure must also leave no temp file
    behind.
    """

    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            blocked = connector_token_path(tmp_path)
            blocked.mkdir()
            try:
                ws, reply = await _pair(port, "token-a")
                assert reply["ok"] is False
                assert reply["error"]["code"] == ErrorCodes.INTERNAL, reply
                assert daemon.pair_grant is not None, "a failed write keeps the grant"
                await ws.close()
            finally:
                blocked.rmdir()
            assert not [p for p in tmp_path.iterdir()
                        if p.name.startswith(".connector-token.")], (
                "a failed write must clean up its temporary file"
            )

            ws, reply = await _pair(port, "token-a")
            assert reply["ok"] is True, reply
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "token-a"
    pairing_records = [r for r in tb._audit_records(tmp_path)
                       if r["action"] in (AUDIT_PAIRING, AUDIT_REPAIRING)]
    assert [r["ok"] for r in pairing_records] == [False, True], (
        "the failed write is recorded as a failure and then retried"
    )


def test_a_write_that_fails_halfway_leaves_the_old_record_intact(tmp_path, monkeypatch):
    """`Path.write_text` truncates first; a secret must not be written that way.

    The old code wrote the record in place, so a failure *after* the truncation —
    a full disk, a scanner holding the file, an interrupted process — left a
    short or empty `connector-token` behind. That is the paired connector's only
    credential: losing it mid-write locks a working editor out, and does it at the
    exact moment the user was *trying* to pair, with no way to tell what happened.

    The failure is injected at the last step (`os.replace`, after every byte of
    the new value is on disk), which is the step the old design did not have.
    Three things have to hold: the old record is byte-for-byte unchanged, the
    authorisation is still there to retry with, and the retry then succeeds.
    """

    async def scenario():
        daemon = _authorised(tmp_path)
        assert daemon.pair_grant is not None
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "paired-one", code=CODE)
            assert reply["ok"] is True, reply
            await ws.close()
            await tb._until(lambda: not daemon.has_connector())

            # Authorise a re-pair, then break the last step of the write.
            tb.authorize_pairing(daemon, OTHER_CODE)
            before = connector_token_path(tmp_path).read_bytes()

            def half_way(source, destination):
                raise OSError("simulated failure while replacing the record")

            monkeypatch.setattr("os.replace", half_way)
            try:
                ws, reply = await _pair(port, "token-b", code=OTHER_CODE)
                assert reply["ok"] is False, reply
                assert reply["error"]["code"] == ErrorCodes.INTERNAL, reply
                assert daemon.pair_grant is not None, (
                    "a write that never landed keeps the grant"
                )
                assert connector_token_path(tmp_path).read_bytes() == before, (
                    "the old pairing record must survive a failed write untouched"
                )
                assert not [p for p in tmp_path.iterdir()
                            if p.name.startswith(".connector-token.")], (
                    "the temporary file must not be left behind"
                )
                await ws.close()
            finally:
                monkeypatch.undo()

            ws, reply = await _pair(port, "token-b", code=OTHER_CODE)
            assert reply["ok"] is True, reply
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "token-b"
    pairing_records = [r for r in tb._audit_records(tmp_path)
                       if r["action"] in (AUDIT_PAIRING, AUDIT_REPAIRING)]
    assert [r["ok"] for r in pairing_records] == [True, False, True], (
        "first pairing, the failed re-pair, then the successful retry"
    )


# --------------------------------------------------------------------------
# who may authorise, and what the catalogue says about it
# --------------------------------------------------------------------------


def test_only_the_cli_role_may_authorise_a_pairing(tmp_path):
    """A connector that authorises its own pairing is TOFU with extra steps."""
    daemon = _daemon(tmp_path / "home")
    for role in ("connector", "-", ""):
        with pytest.raises(BridgeError) as caught:
            daemon._local_action("pair.authorize", role=role, params={"code": CODE})
        assert caught.value.code == ErrorCodes.BAD_REQUEST, role
        assert caught.value.detail["pairCodeRequired"] is True
        assert caught.value.detail["reason"] == "role-not-allowed"
    assert daemon.pair_grant is None, "a refused role must not authorise anything"


def test_a_connector_cannot_authorise_itself_over_the_wire(tmp_path):
    """The same refusal through the real dispatch, from a connector socket."""

    async def scenario():
        daemon = _daemon(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            ws, hello = await tb._hello(port, "connector", token="some-token")
            assert hello["ok"] is False, "a connector cannot pair on its own"
            await ws.close()

            cli_ws, hello = await tb._hello(port, "cli")
            assert hello["ok"] is True
            await cli_ws.send(request_frame(
                "pair.authorize", {"code": CODE}, id="a1"))
            reply = decode_frame(await cli_ws.recv())
            assert reply["ok"] is True, reply
            assert reply["data"]["authorized"] is True
            await cli_ws.close()

            ws, reply = await _pair(port, "some-token")
            assert reply["ok"] is True, reply
            await ws.close()

    tb.run(scenario())

    assert load_connector_token(tmp_path) == "some-token"


def test_a_connector_socket_cannot_call_pair_authorize(tmp_path):
    """Even a *paired* connector may not mint the next grant."""

    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            ws, hello = await _pair(port, "paired-one")
            assert hello["ok"] is True
            await ws.send(request_frame(
                "pair.authorize", {"code": OTHER_CODE}, id="a1"))
            reply = await tb._recv_frame(ws)
            assert reply["ok"] is False
            assert reply["error"]["code"] == ErrorCodes.BAD_REQUEST
            assert reply["error"]["detail"]["reason"] == "role-not-allowed"
            assert daemon.pair_grant is None
            await ws.close()

    tb.run(scenario())


def test_pair_authorize_needs_a_code(tmp_path):
    daemon = _daemon(tmp_path / "home")
    for params in ({}, {"code": ""}, {"code": "   -  "}):
        with pytest.raises(BridgeError) as caught:
            daemon._local_action("pair.authorize", role="cli", params=params)
        assert caught.value.code == ErrorCodes.BAD_REQUEST, params
    assert daemon.pair_grant is None


#: Every shape of "that is not a pair code". Empty and blank are a missing field;
#: wrong length is a typo or a paste; the last two are *length 8* — the old check
#: let both of them through and minted a grant no connector could ever match.
NOT_A_PAIR_CODE = (
    {},
    {"code": None},
    {"code": 12345678},
    {"code": ""},
    {"code": "   -  "},
    {"code": "ABCD"},
    {"code": "ABCD-EFG"},
    {"code": "ABCD-EFGHI"},
    {"code": "ABCDEFGHJ"},
    # 8 symbols, but two of them are not in the alphabet the connector draws
    # from: `I` and `L`, the two a human reads back wrong.
    {"code": "ABCD-EFGI"},
    {"code": "ABCD-EFGL"},
    {"code": "ABCD-EFG!"},
)


def test_pair_authorize_refuses_anything_that_is_not_an_eight_symbol_code(tmp_path):
    """549 red team: `> 64` was the whole validation, so junk minted grants.

    The code is the only thing the user types, and the alphabet exists precisely
    because it is typed back from a screen. A length or alphabet check here means
    the typo is refused at the CLI — where the user can still see and fix it —
    instead of becoming a five-minute grant that is impossible to match and is
    indistinguishable from "the connector is broken".
    """
    daemon = _daemon(tmp_path / "home")
    for params in NOT_A_PAIR_CODE:
        with pytest.raises(BridgeError) as caught:
            daemon._local_action("pair.authorize", role="cli", params=params)
        assert caught.value.code == ErrorCodes.BAD_REQUEST, params
        assert caught.value.detail["field"] == "code", params
        assert daemon.pair_grant is None, params


def test_a_malformed_code_does_not_replace_a_valid_grant(tmp_path):
    """The failure the red team was really pointing at: a typo killing a grant.

    Before the strict check, `bridge pair` with a malformed code *replaced* the
    good authorisation (single slot, validate-nothing), so the user's correct
    first attempt became unrecoverable without re-reading the code. A refused
    authorisation must leave the previous one exactly as it was.
    """
    daemon = _daemon(tmp_path)
    daemon._local_action("pair.authorize", role="cli", params={"code": CODE})
    before = daemon.pair_grant
    assert before is not None

    for params in NOT_A_PAIR_CODE:
        with pytest.raises(BridgeError) as caught:
            daemon._local_action("pair.authorize", role="cli", params=params)
        assert caught.value.code == ErrorCodes.BAD_REQUEST, params
        assert daemon.pair_grant is before, params
        assert daemon.pair_grant.code == "ABCDEFGH", params

    async def scenario():
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "token-a")
            assert reply["ok"] is True, reply
            await ws.close()

    tb.run(scenario())
    assert load_connector_token(tmp_path) == "token-a"
    authorisations = [r for r in tb._audit_records(tmp_path)
                      if r["action"] == AUDIT_PAIR_AUTHORIZE]
    assert len(authorisations) == 1, "a refused authorisation is not an authorisation"


class _Recorder:
    """A socket stand-in that keeps the frames ``_close`` sends."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed = False

    async def send(self, raw) -> None:
        self.sent.append(decode_frame(raw))

    async def close(self) -> None:
        self.closed = True


def test_a_refused_handshake_cannot_carry_internal_state(tmp_path):
    """One allowlist, at the single place a refused handshake is written out.

    The detail goes to a socket that has authenticated *nothing*, so it is an
    allowlist and not a per-call-site courtesy: `pairCodeRequired` and `reason`
    are what the connector acts on, and everything else — the pairing record's
    fingerprint before and after an authorisation, the failure count — is state
    the caller has not earned. Filtering here, rather than at the call sites, is
    what stops the next refusal from growing a new field.
    """
    daemon = _daemon(tmp_path / "home")

    for code, expected in (
        (
            ErrorCodes.UNAUTHENTICATED,
            {"pairCodeRequired": True, "reason": "code-mismatch"},
        ),
        (ErrorCodes.PROTOCOL_VIOLATION, {"action": "ping"}),
        (ErrorCodes.BAD_REQUEST, None),
        (ErrorCodes.VERSION_MISMATCH, None),
    ):
        recorder = _Recorder()
        detail = {
            "pairCodeRequired": True,
            "reason": "code-mismatch",
            "action": "ping",
            # …everything a refusal might be tempted to add:
            "pairedFingerprint": "deadbeef",
            "authorizedFingerprint": "cafe0000",
            "attempts": 7,
            "failures": 7,
            "record": "deadbeef",
            "nested": {"fingerprint": "deadbeef"},
        }
        tb.run(daemon._close(recorder, code, "refused", detail))
        assert recorder.closed is True
        error = recorder.sent[0]["error"]
        assert error.get("detail") == expected, (code, error)

    # A non-dict detail cannot smuggle anything either.
    recorder = _Recorder()
    tb.run(daemon._close(recorder, ErrorCodes.UNAUTHENTICATED, "refused", ["x"]))
    assert "detail" not in recorder.sent[0]["error"]


def test_no_unauthenticated_refusal_on_the_wire_names_internal_state(tmp_path):
    """The same rule, measured on real frames from a real socket."""

    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            # Wrong code, and a live window in the way: two different refusals,
            # both of which used to carry the pairing fingerprints.
            ws, reply = await _pair(port, "token-a", code=OTHER_CODE)
            assert reply["ok"] is False
            assert set(reply["error"]["detail"]) == {"pairCodeRequired", "reason"}
            await ws.close()

            live, reply = await _pair(port, "paired-one")
            assert reply["ok"] is True
            tb.authorize_pairing(daemon, OTHER_CODE)
            ws, reply = await _pair(port, "token-b", code=OTHER_CODE)
            assert reply["ok"] is False
            assert reply["error"]["detail"]["reason"] == "connector-attached"
            assert set(reply["error"]["detail"]) == {"pairCodeRequired", "reason"}
            blob = json.dumps(reply)
            for leak in ("pairedFingerprint", "authorizedFingerprint", "attempts",
                         connector_fingerprint("paired-one")):
                assert leak not in blob, (leak, reply)
            await ws.close()
            await live.close()

    tb.run(scenario())


def test_no_response_or_audit_ever_carries_a_token(tmp_path):
    """The one thing that must never leak, checked on the frames and the log."""

    async def scenario():
        daemon = _authorised(tmp_path)
        server, port = await tb._start(daemon)
        async with server:
            ws, reply = await _pair(port, "the-pairing-secret")
            assert reply["ok"] is True
            frames = [json.dumps(reply)]
            await ws.send(request_frame("ping", {}, id="p1"))
            frames.append(json.dumps(await tb._recv_frame(ws)))
            await ws.close()
        return frames

    frames = tb.run(scenario())
    blob = "\n".join(frames)
    assert "the-pairing-secret" not in blob
    assert connector_token_path(tmp_path).read_text(encoding="utf-8").strip() == (
        "the-pairing-secret"
    )
    log = json.dumps(tb._audit_records(tmp_path))
    assert "the-pairing-secret" not in log
    # The pairing code is public, and only its masked form is written down.
    assert "ABCDEFGH" not in log
    assert mask_pair_code("ABCDEFGH") in log
