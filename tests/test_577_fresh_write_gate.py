"""577 / W-D1: a design write is judged by the editor's **live** identity.

566-D-1 (``outputs/hole566/d/REPRO.md``) measured the hole: 537A3's gate read
``window.project_name``, which is the ``hello`` snapshot plus whatever the *last*
connector response happened to say. A user who switched that window from ``test``
to a real project and then made no bridge call left the daemon believing
``test`` — the first design write went through. The fix is not a better
snapshot: it is one read of the editor's own two identity layers, made **inside
the window's write lock, immediately before the write**, and the gate runs on
that answer.

What is pinned here, each against the real dispatch:

1. **the hole** — a stale ``test`` window whose live ``sys.identity`` says
   ``REAL_TARGET`` refuses the first design write, forwards only the read-only
   probe, and does not mark ``routed``;
2. **the order** — lock, then ``sys.identity``, then the gate, then the write;
   the check is inside the lock, so a switch that happens while a call is parked
   on the lock is judged by the value read *after* acquiring it;
3. **the allowed path** — ``test`` / ``test2`` still write, with one extra read
   in front, for every kind of design write (page, placement, NC flag);
4. **fail closed** — disagreeing layers, an undecidable ``consistent``, no
   project, no uuid, an old connector (``UNKNOWN_ACTION``) all refuse with no
   design write; a genuine technical error keeps its own code;
5. **what must not change** — reads, navigation, ``sys.self_update`` and the
   ``*`` legacy switch gain no probe, and only the routed window is asked.

The fake connector is a spy on ``_forward`` (the same seam 537A uses), so
"what reached the editor" is a list, not a claim in a sentence.
"""

from __future__ import annotations

import asyncio

import pytest
from websockets.protocol import State

from boardwise.bridge.daemon import BridgeDaemon, WindowConnection
from boardwise.bridge.protocol import BridgeError, ErrorCodes

TOKEN = "test-token-not-a-real-secret"

#: The project a stale window is told to believe it still has, and the one the
#: editor reports when asked. Synthetic: no real board's name is used anywhere.
STALE_NAME = "test"
STALE_UUID = "uuid-test"
REAL_NAME = "REAL_TARGET"
REAL_UUID = "uuid-real-0001"

#: The wording the refusal must carry (and must not lose): the identity probe is
#: a read, so "nothing was forwarded" was the wrong sentence — it read as
#: "nothing was read either", which hid the one frame that *did* go out.
NO_DESIGN_WRITE = "No design write was forwarded"

DELETE = {"pageUuid": "page-abc", "confirm": True}
PLACE = {"designator": "R1"}
NC = {
    "pageUuid": "page-abc",
    "parentPrimitiveId": "c1",
    "primitiveId": "p1",
    "expectedPinNumber": "1",
    "noConnected": True,
}


class FakeSocket:
    """A connector socket that only records; nothing is ever written to a peer."""

    def __init__(self, state: State = State.OPEN) -> None:
        self.state = state
        self.sent: list = []

    async def send(self, raw) -> None:
        self.sent.append(raw)

    async def close(self) -> None:
        self.state = State.CLOSED


def _window(key: str = "w1", *, name: str = "", uuid: str = "") -> WindowConnection:
    return WindowConnection(
        websocket=FakeSocket(),
        key=key,
        instance_id=key,
        project_name=name,
        project_uuid=uuid,
    )


def identity(
    name: str = STALE_NAME,
    uuid: str = STALE_UUID,
    *,
    active: bool = True,
    consistent: bool = True,
    basis: str | None = None,
):
    """One ``sys.identity`` answer in the connector's own wire shape."""
    project = {"projectUuid": uuid, "name": name, "friendlyName": name}
    if not active:
        return {
            "focusedProject": project,
            "activeDocument": None,
            "consistent": None,
            "consistentBasis": "no-active-document",
            "pageUuid": None,
            "readOnly": True,
        }
    return {
        "focusedProject": project,
        "activeDocument": {
            "uuid": "doc-1",
            "type": "schematic",
            "tabId": "tab-1",
            "projectUuid": uuid,
            "project": project,
        },
        "consistent": consistent,
        "consistentBasis": basis or "project-uuid",
        "pageUuid": "page-abc",
        "readOnly": True,
    }


class Editor:
    """The fake connector: records every frame and answers ``sys.identity``.

    ``identity`` is staged per window key. An answer the test did not stage is an
    **assertion failure**, not an empty payload: a test that says "this call must
    not read the editor" has to be able to prove it, and a silent default would
    let a stray probe look like a pass.
    """

    def __init__(self) -> None:
        self.forwarded: list[tuple[str, dict, str]] = []
        self.events: list[tuple[str, str]] = []
        self.identity: dict[str, object] = {}
        self.hooks: dict[str, object] = {}

    def stage(self, key: str, answer) -> None:
        self.identity[key] = answer

    def actions(self) -> list[str]:
        return [entry[0] for entry in self.forwarded]

    def writes(self) -> list[tuple[str, dict, str]]:
        return [entry for entry in self.forwarded if entry[0] != "sys.identity"]

    async def __call__(self, action, params, role, window):
        self.forwarded.append((action, dict(params), window.key))
        self.events.append(("forward", action))
        hook = self.hooks.get(action)
        if hook is not None:
            await hook()
        if action == "sys.identity":
            assert window.key in self.identity, (
                f"unexpected sys.identity probe on {window.key!r}: this test "
                "staged no identity for that window"
            )
            answer = self.identity[window.key]
            if isinstance(answer, Exception):
                raise answer
            return answer
        return {"spy": action}


def _daemon(tmp_path, monkeypatch, *, env: str | None = None):
    if env is None:
        monkeypatch.delenv("BOARDWISE_WRITE_PROJECTS", raising=False)
    else:
        monkeypatch.setenv("BOARDWISE_WRITE_PROJECTS", env)
    daemon = BridgeDaemon(token=TOKEN, home=tmp_path)
    editor = Editor()
    monkeypatch.setattr(daemon, "_forward", editor)
    return daemon, editor


def _call(daemon, action, *, params=None, routed=None, target_project="", target_instance=""):
    return asyncio.run(daemon.handle_request(
        action, params or {}, "cli", target_project, routed, target_instance,
    ))


def _refusal(daemon, action, **kwargs) -> BridgeError:
    with pytest.raises(BridgeError) as raised:
        _call(daemon, action, **kwargs)
    return raised.value


class RecordingLock:
    """The window's real lock, plus one line in an event log per acquisition."""

    def __init__(self, inner: asyncio.Lock, log: list) -> None:
        self.inner = inner
        self.log = log

    async def __aenter__(self):
        await self.inner.acquire()
        self.log.append(("lock", "enter"))
        return self

    async def __aexit__(self, *exc_info):
        self.log.append(("lock", "exit"))
        self.inner.release()
        return False


# --------------------------------------------------------------------------
# 1. the hole 566-D-1 measured
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "params"), [("doc.delete_page", DELETE),
                            ("sch.place_component", PLACE),
                            ("sch.set_pin_no_connected", NC)]
)
def test_the_first_design_write_after_a_switch_is_refused(
    tmp_path, monkeypatch, action, params
):
    """A window that says ``test`` and *is* something else must not write.

    The stale claim is the one the last response left behind; the editor is asked
    afresh, and its answer — not the bookkeeping — decides. The refusal has to be
    the first design write, not the second one after an accidental refresh.
    """
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name=STALE_NAME, uuid=STALE_UUID)
    daemon.windows[window.key] = window
    editor.stage(window.key, identity(REAL_NAME, REAL_UUID))
    routed: dict = {}

    error = _refusal(daemon, action, params=dict(params), routed=routed)

    assert error.code == ErrorCodes.WRITE_PROJECT_FORBIDDEN
    assert action in error.message
    assert REAL_NAME in error.message or REAL_UUID in error.message
    # Only the read-only probe was forwarded; the design write never left.
    assert editor.forwarded == [("sys.identity", {}, window.key)]
    assert editor.writes() == []
    assert routed == {}, "a refused call must not be marked as routed"
    assert NO_DESIGN_WRITE in error.message
    # The identity the editor gave is the identity the window now reports.
    assert (window.project_name, window.project_uuid) == (REAL_NAME, REAL_UUID)


def test_a_successful_write_refreshes_the_window_it_wrote_through(tmp_path, monkeypatch):
    """A read that confirms the project also keeps the router honest."""
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name="", uuid="")
    daemon.windows[window.key] = window
    editor.stage(window.key, identity(STALE_NAME, STALE_UUID))

    assert _call(daemon, "sch.place_component", params=dict(PLACE)) == {
        "spy": "sch.place_component"
    }
    assert (window.project_name, window.project_uuid) == (STALE_NAME, STALE_UUID)
    assert editor.actions() == ["sys.identity", "sch.place_component"]


# --------------------------------------------------------------------------
# 2. the order: lock → identity → gate → write
# --------------------------------------------------------------------------


def test_the_identity_read_and_the_gate_run_inside_the_lock_before_the_write(
    tmp_path, monkeypatch
):
    """The gate moved into the lock; the probe moved with it.

    Reading the identity *before* taking the lock leaves the hole 566-D-1 also
    names: a call parked on the lock would judge yesterday's project. The log is
    the whole claim — order and lock bracket, not a comment.
    """
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name=STALE_NAME, uuid=STALE_UUID)
    daemon.windows[window.key] = window
    editor.stage(window.key, identity())

    log: list = []
    window.write_lock = RecordingLock(asyncio.Lock(), log)
    editor.events = log

    real_check = daemon._check_design_write

    def recorded_check(spec, window):
        log.append(("check", spec.name))
        return real_check(spec, window)

    monkeypatch.setattr(daemon, "_check_design_write", recorded_check)

    assert _call(daemon, "sch.place_component", params=dict(PLACE)) == {
        "spy": "sch.place_component"
    }

    assert log == [
        ("lock", "enter"),
        ("forward", "sys.identity"),
        ("check", "sch.place_component"),
        ("forward", "sch.place_component"),
        ("lock", "exit"),
    ]


def test_a_switch_while_the_lock_is_held_is_judged_by_the_value_read_inside_it(
    tmp_path, monkeypatch
):
    """The race the lock exists for, made to happen.

    Call A holds the window's lock with its frame in flight; the operator
    switches the project; call B parks on the lock. B must be judged by the
    identity read *after* it acquires the lock — never by the one A ran under, and
    never by what the window claimed before either of them.
    """

    async def scenario():
        daemon, editor = _daemon(tmp_path, monkeypatch)
        window = _window(name=STALE_NAME, uuid=STALE_UUID)
        daemon.windows[window.key] = window
        editor.stage(window.key, identity())

        started = asyncio.Event()
        release = asyncio.Event()

        async def hold_the_frame():
            started.set()
            await release.wait()

        editor.hooks["sch.place_component"] = hold_the_frame

        first = asyncio.create_task(
            daemon.handle_request("sch.place_component", dict(PLACE), "cli")
        )
        await asyncio.wait_for(started.wait(), timeout=5)

        # The operator switches projects while A's frame is in flight.
        editor.stage(window.key, identity(REAL_NAME, REAL_UUID))

        second_routed: dict = {}
        second = asyncio.create_task(daemon.handle_request(
            "sch.place_component", dict(PLACE), "cli", "", second_routed,
        ))
        await asyncio.sleep(0.05)  # B is parked on the lock by now
        assert not second.done(), "B must wait for the window's write lock"

        editor.hooks.pop("sch.place_component")
        release.set()
        assert await first == {"spy": "sch.place_component"}

        with pytest.raises(BridgeError) as caught:
            await second

        assert caught.value.code == ErrorCodes.WRITE_PROJECT_FORBIDDEN
        assert NO_DESIGN_WRITE in caught.value.message
        assert second_routed == {}
        # One design write left for the window, and it is A's: B's probe ran
        # after A's frame, i.e. after B acquired the lock.
        assert [entry[0] for entry in editor.writes()] == ["sch.place_component"]
        probes = [i for i, e in enumerate(editor.events)
                  if e == ("forward", "sys.identity")]
        writes = [i for i, e in enumerate(editor.events)
                  if e == ("forward", "sch.place_component")]
        assert len(probes) == 2 and len(writes) == 1
        assert writes[0] < probes[1], "B probed before A's write finished"

    asyncio.run(scenario())


# --------------------------------------------------------------------------
# 3. the allowed path: identity first, then the write
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "params", "forwarded_params"),
    [
        ("doc.delete_page", DELETE, {"pageUuid": "page-abc"}),
        ("sch.place_component", PLACE, PLACE),
        ("sch.set_pin_no_connected", NC, NC),
    ],
)
def test_an_allowed_project_writes_after_one_identity_read(
    tmp_path, monkeypatch, action, params, forwarded_params
):
    """``test`` / ``test2`` still write — the gate only asks who it is first."""
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name=STALE_NAME, uuid=STALE_UUID)
    daemon.windows[window.key] = window
    editor.stage(window.key, identity(STALE_NAME, STALE_UUID))
    routed: dict = {}

    assert _call(daemon, action, params=dict(params), routed=routed) == {"spy": action}
    assert editor.forwarded == [
        ("sys.identity", {}, window.key),
        (action, forwarded_params, window.key),
    ]
    assert routed == {"windowKey": window.key}


def test_the_uuid_half_of_the_identity_is_enough_to_be_allowed(tmp_path, monkeypatch):
    """The allowlist matches name *or* uuid; the probe supplies both."""
    daemon, editor = _daemon(tmp_path, monkeypatch, env="uuid-my-board")
    window = _window(name="", uuid="")
    daemon.windows[window.key] = window
    editor.stage(window.key, identity("whatever-the-editor-calls-it", "uuid-my-board"))

    assert _call(daemon, "sch.doc.save") == {"spy": "sch.doc.save"}
    assert editor.actions() == ["sys.identity", "sch.doc.save"]


def test_a_name_only_identity_is_enough(tmp_path, monkeypatch):
    """An editor that filled a name and no uuid still proves which project it is.

    537A3 has always matched a project by name **or** uuid; the fresh read must
    not be stricter than the gate it feeds, or a project the operator allowed by
    name would be refused for filling only half of the identity object.
    """
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name="", uuid="")
    daemon.windows[window.key] = window
    editor.stage(window.key, identity(STALE_NAME, ""))

    assert _call(daemon, "sch.doc.save") == {"spy": "sch.doc.save"}
    assert editor.actions() == ["sys.identity", "sch.doc.save"]
    # Written as it came: the half the editor did not name is empty, not the
    # window's old value dressed up as news.
    assert (window.project_name, window.project_uuid) == (STALE_NAME, "")


def test_a_uuid_only_identity_is_enough(tmp_path, monkeypatch):
    """The other half: an operator who allowed a uuid must not need the name."""
    daemon, editor = _daemon(tmp_path, monkeypatch, env="uuid-my-board")
    window = _window(name="", uuid="")
    daemon.windows[window.key] = window
    editor.stage(window.key, identity("", "uuid-my-board"))

    assert _call(daemon, "sch.doc.save") == {"spy": "sch.doc.save"}
    assert editor.actions() == ["sys.identity", "sch.doc.save"]
    assert (window.project_name, window.project_uuid) == ("", "uuid-my-board")


# --------------------------------------------------------------------------
# 4. fail closed: an identity the daemon cannot trust is a refusal
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        identity(STALE_NAME, STALE_UUID, active=True, consistent=False),
        identity(STALE_NAME, STALE_UUID, active=True, consistent=None,
                 basis="unavailable"),
        identity(STALE_NAME, STALE_UUID, active=True, consistent="true"),
        # `consistent` missing altogether is the same fact as null.
        {k: v for k, v in identity().items() if k != "consistent"},
    ],
    ids=["consistent-false", "consistent-null", "consistent-not-a-bool",
         "consistent-absent"],
)
def test_a_disagreeing_or_undecidable_editor_is_refused(tmp_path, monkeypatch, answer):
    """Two layers that disagree are the measured 2026-09-21 condition.

    ``consistent`` is only ``true`` when both project uuids were read and match;
    anything else means the write's landing place is unproven, which is exactly
    when a design write must not go out.
    """
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name=STALE_NAME, uuid=STALE_UUID)
    daemon.windows[window.key] = window
    editor.stage(window.key, answer)
    routed: dict = {}

    error = _refusal(daemon, "sch.place_component", params=dict(PLACE), routed=routed)

    assert error.code == ErrorCodes.WRITE_PROJECT_FORBIDDEN
    assert editor.writes() == []
    assert routed == {}
    assert NO_DESIGN_WRITE in error.message
    assert "consistent" in error.message.lower() or "identity" in error.message.lower()


@pytest.mark.parametrize(
    "answer",
    [
        {"focusedProject": None, "activeDocument": None, "consistent": None,
         "consistentBasis": "unavailable"},
        {"focusedProject": {"name": "", "projectUuid": ""},
         "activeDocument": None, "consistent": None},
        {"focusedProject": {},
         "activeDocument": {"uuid": "doc-1", "project": None},
         "consistent": True},
        {"focusedProject": None,
         "activeDocument": {"uuid": "doc-1",
                            "project": {"name": "", "projectUuid": ""}},
         "consistent": True},
        {"readOnly": True},
        ["not", "an", "object"],
        None,
    ],
    ids=["no-projects", "empty-project-fields", "active-without-any-project",
         "active-and-focused-both-unnamed", "only-readonly", "not-an-object",
         "null-payload"],
)
def test_an_identity_that_names_no_project_is_refused(tmp_path, monkeypatch, answer):
    """Naming the project neither way is not an identity.

    537A3 matches a project by name **or** uuid, and the fresh read is held to
    the same bar: one half is enough to identify (see the name-only and
    uuid-only positives), neither half is "unknown project", which is refused
    rather than assumed safe.
    """
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name=STALE_NAME, uuid=STALE_UUID)
    daemon.windows[window.key] = window
    editor.stage(window.key, answer)

    error = _refusal(daemon, "doc.delete_page", params=dict(DELETE))

    assert error.code == ErrorCodes.WRITE_PROJECT_FORBIDDEN
    assert editor.writes() == []
    assert NO_DESIGN_WRITE in error.message
    # A window that cannot say which project it is is not "safely unnamed".
    assert "unknown" in error.message.lower()


def test_an_old_connector_without_sys_identity_is_refused(tmp_path, monkeypatch):
    """``UNKNOWN_ACTION`` means "no identity capability", not "identity unknown
    but writable" — the catalogued action exists here, so the answer can only be
    that this editor cannot prove which project a write lands in.
    """
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name=STALE_NAME, uuid=STALE_UUID)
    daemon.windows[window.key] = window
    editor.stage(
        window.key,
        BridgeError(ErrorCodes.UNKNOWN_ACTION, "unknown action 'sys.identity'"),
    )

    error = _refusal(daemon, "sch.place_component", params=dict(PLACE))

    assert error.code == ErrorCodes.WRITE_PROJECT_FORBIDDEN
    assert error.code != ErrorCodes.UNKNOWN_ACTION
    assert editor.writes() == []
    assert NO_DESIGN_WRITE in error.message


@pytest.mark.parametrize(
    "code", [ErrorCodes.TIMEOUT, ErrorCodes.DISCONNECTED, ErrorCodes.CONNECTOR_ERROR]
)
def test_a_technical_error_keeps_its_own_code(tmp_path, monkeypatch, code):
    """A probe that could not run is not the same fact as a refusal.

    ``TIMEOUT``/``DISCONNECTED`` say "nobody knows whether the editor acted";
    turning them into ``WRITE_PROJECT_FORBIDDEN`` would tell the caller a safe
    thing that is not known. The code passes through untouched and no design
    write is sent.
    """
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name=STALE_NAME, uuid=STALE_UUID)
    daemon.windows[window.key] = window
    editor.stage(window.key, BridgeError(code, "the connector did not answer"))

    error = _refusal(daemon, "sch.place_component", params=dict(PLACE))

    assert error.code == code
    assert editor.writes() == []


def test_no_active_document_still_allows_a_first_page(tmp_path, monkeypatch):
    """Creating the first page of ``test`` is legitimate: no document to compare.

    The connector reports ``consistent: null`` with ``no-active-document`` here,
    and requiring ``true`` would make an empty project unwritable.
    """
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name="", uuid="")
    daemon.windows[window.key] = window
    editor.stage(window.key, identity(STALE_NAME, STALE_UUID, active=False))

    assert _call(daemon, "sch.doc.new", params={"name": "scratch", "confirm": True}) == {
        "spy": "sch.doc.new"
    }
    assert editor.actions() == ["sys.identity", "sch.doc.new"]

    editor.stage(window.key, identity(REAL_NAME, REAL_UUID, active=False))
    assert _refusal(
        daemon, "sch.doc.new", params={"name": "scratch", "confirm": True}
    ).code == ErrorCodes.WRITE_PROJECT_FORBIDDEN


def test_the_active_documents_project_wins_when_the_two_layers_agree(tmp_path, monkeypatch):
    """``consistent`` is a comparison — when it holds, the document's project is
    the one the write lands on, so that is the one the gate must judge.
    """
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name=STALE_NAME, uuid=STALE_UUID)
    daemon.windows[window.key] = window
    answer = identity(STALE_NAME, STALE_UUID)
    answer["focusedProject"] = {"projectUuid": STALE_UUID, "name": STALE_NAME}
    answer["activeDocument"]["project"] = {"projectUuid": REAL_UUID, "name": REAL_NAME}
    editor.stage(window.key, answer)

    error = _refusal(daemon, "sch.place_component", params=dict(PLACE))

    assert error.code == ErrorCodes.WRITE_PROJECT_FORBIDDEN
    assert REAL_NAME in error.message or REAL_UUID in error.message
    assert editor.writes() == []


def test_the_focused_project_is_the_fallback_when_the_document_names_none(
    tmp_path, monkeypatch
):
    """`focused-project-listing`: the document did not name its project, the
    listing proved it is in the focused one. That is `consistent: true` with an
    empty `activeDocument.project`, and the focused project is the answer.
    """
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name="", uuid="")
    daemon.windows[window.key] = window
    answer = identity(STALE_NAME, STALE_UUID)
    answer["activeDocument"]["project"] = None
    answer["consistentBasis"] = "focused-project-listing"
    editor.stage(window.key, answer)

    assert _call(daemon, "sch.place_component", params=dict(PLACE)) == {
        "spy": "sch.place_component"
    }
    assert editor.actions() == ["sys.identity", "sch.place_component"]
    assert (window.project_name, window.project_uuid) == (STALE_NAME, STALE_UUID)


# --------------------------------------------------------------------------
# 5. what must not change
# --------------------------------------------------------------------------


def test_a_read_is_not_probed(tmp_path, monkeypatch):
    """Reads cannot change anything, and `doc.list` on a real project must work."""
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name=REAL_NAME, uuid=REAL_UUID)
    daemon.windows[window.key] = window

    assert _call(daemon, "doc.list") == {"spy": "doc.list"}
    assert editor.forwarded == [("doc.list", {}, window.key)]


@pytest.mark.parametrize(
    ("action", "params", "forwarded_params"),
    [
        ("doc.focus", {"uuid": "page-1"}, {"uuid": "page-1"}),
        ("doc.open", {"uuid": "page-1"}, {"uuid": "page-1"}),
        # `confirm` is consumed by the daemon's own gate, as for every tier.
        ("sys.self_update", {"bundleB64": "AA==", "confirm": True},
         {"bundleB64": "AA=="}),
    ],
)
def test_navigation_and_self_update_are_not_probed(
    tmp_path, monkeypatch, action, params, forwarded_params
):
    """They move the focus or replace the connector; no project byte moves."""
    daemon, editor = _daemon(tmp_path, monkeypatch)
    window = _window(name=REAL_NAME, uuid=REAL_UUID)
    daemon.windows[window.key] = window
    routed: dict = {}

    assert _call(daemon, action, params=dict(params), routed=routed) == {"spy": action}
    assert editor.forwarded == [(action, forwarded_params, window.key)]
    assert routed == {"windowKey": window.key}


def test_the_star_allowlist_keeps_the_legacy_single_frame(tmp_path, monkeypatch):
    """``*`` is for old callers: every project, and no new round trip."""
    daemon, editor = _daemon(tmp_path, monkeypatch, env="*")
    window = _window(name=REAL_NAME, uuid=REAL_UUID)
    daemon.windows[window.key] = window
    routed: dict = {}

    assert _call(daemon, "sch.place_component", params=dict(PLACE), routed=routed) == {
        "spy": "sch.place_component"
    }
    assert editor.forwarded == [("sch.place_component", PLACE, window.key)]
    assert routed == {"windowKey": window.key}


def test_only_the_routed_window_is_probed_and_updated(tmp_path, monkeypatch):
    """With two windows open, the one that is not routed is not read or renamed."""
    daemon, editor = _daemon(tmp_path, monkeypatch)
    first = _window(key="w1", name=STALE_NAME, uuid=STALE_UUID)
    second = _window(key="w2", name="test2", uuid="uuid-test2")
    daemon.windows[first.key] = first
    daemon.windows[second.key] = second
    editor.stage("w2", identity("test2", "uuid-test2"))
    routed: dict = {}

    assert _call(
        daemon, "sch.place_component", params=dict(PLACE), routed=routed,
        target_project="test2",
    ) == {"spy": "sch.place_component"}

    assert [entry[2] for entry in editor.forwarded] == ["w2", "w2"]
    assert routed == {"windowKey": "w2"}
    assert (first.project_name, first.project_uuid) == (STALE_NAME, STALE_UUID)


def test_an_empty_allowlist_refuses_but_still_reads_before_it_does(tmp_path, monkeypatch):
    """``""`` is a policy ("write nowhere"), and the refusal names the live project.

    The probe still runs: the message has to say which project the write would
    have landed in, and that fact is only true if it was read now.
    """
    daemon, editor = _daemon(tmp_path, monkeypatch, env="")
    window = _window(name=STALE_NAME, uuid=STALE_UUID)
    daemon.windows[window.key] = window
    editor.stage(window.key, identity(REAL_NAME, REAL_UUID))

    error = _refusal(daemon, "sch.place_component", params=dict(PLACE))

    assert error.code == ErrorCodes.WRITE_PROJECT_FORBIDDEN
    assert REAL_NAME in error.message
    assert editor.writes() == []
    assert NO_DESIGN_WRITE in error.message
