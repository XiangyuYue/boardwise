"""Wire protocol for the boardwise bridge (daemon <-> connector / CLI).

One WebSocket server speaks to two kinds of client, distinguished at
handshake by ``params.role``:

- ``connector`` — the TypeScript extension running inside EasyEDA Pro. It owns
  the ``eda.*`` API, so every *editor* action is forwarded to it. At most one
  connector is tracked at a time.
- ``cli``       — short-lived command line calls. They ask the daemon to
  forward an action and wait for the answer.

Framing is one JSON object per WebSocket text message. Nothing here touches
the network — this module only defines, builds and validates frames, which
keeps the contract testable without a socket.

There are three kinds of frame, told apart by which key is present:

======================  ==========================  =========================
kind                    key                         meaning
======================  ==========================  =========================
request                 ``action``                  asks for something
response                ``ok``                      answers a request
event                   ``event``                   unsolicited notification
======================  ==========================  =========================

``ok`` wins over ``event`` wins over ``action`` when reading, so a frame is
classified by the strongest key it carries.

Envelope (request)::

    {"id": "…", "action": "pcb.readback", "params": {…}}

Envelope (response)::

    {"id": "…", "ok": true,  "data": {…}}
    {"id": "…", "ok": false, "error": {"code": "…", "message": "…"}}

Envelope (event) — no ``id``, because nothing correlates with it::

    {"event": "banner", "data": {…}}

The shape is deliberately close to the ``easyeda-agent`` frames reconnoitred
in 2026-08 (see ``docs/bridge.md``), so behaviour learned on that connector
transfers: ``id`` correlates, ``ok`` decides, ``error.code`` is machine
readable. Three differences: we put results in ``data`` instead of
``result``/``artifacts``, every action is explicitly declared in
:data:`ACTIONS` rather than discovered at runtime, and the liveness signal
travels *daemon to connector* as an event (:func:`banner_frame`) instead of
being inferred from a connect callback the editor does not reliably call.

Since 023 the daemon is a **hub of editor windows** (one registration per
connector socket, keyed by the instance id it claims) rather than a
single-active slot, which puts two optional top-level fields on this wire:

- ``targetProject`` on a **request** — the project (name or uuid) the CLI wants
  to be answered by. The daemon resolves it to one registered window or refuses
  with ``PROJECT_NOT_CONNECTED`` / ``PROJECT_AMBIGUOUS``; with no hint and more
  than one window it refuses with ``WINDOW_UNSPECIFIED`` rather than guessing.
- ``targetInstance`` on a **request** — the same instruction spelled with the
  *instance id* the window itself claimed, which needs no project to be readable
  at all. Measured 2026-09-22: three windows restart and greet the daemon before
  the editor API is ready, so every ``context`` comes back null and **no** project
  hint can match anything — ``--project`` has nothing to match against, while the
  instance id is in the ``hello`` params and always there. When both hints are
  present the instance wins: it names one connection, a project name may be
  claimed by several.
- ``context`` on a **response** — ``{projectName, projectUuid, pageUuid,
  pageType}``, the window's live identity at the moment it ran the action. The
  connector reads it fresh per response and omits what it cannot read; the
  daemon merges the non-empty keys into its own bookkeeping (:func:`merge_context`),
  so routing follows the user switching projects instead of a picture frozen at
  the handshake. The daemon passes the merged context on to the CLI in the relayed
  frame, so "which window answered this?" is answerable by the caller.

Both fields are optional, and a frame without them is byte-for-byte the
pre-023 frame: an old connector never sends ``context``, and an old caller never
sends ``targetProject`` (nor, since the instance hint, ``targetInstance``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

__all__ = [
    "PROTOCOL_VERSION",
    "ROLE_CONNECTOR",
    "ROLE_CLI",
    "ROLES",
    "EVENT_BANNER",
    "Action",
    "ACTIONS",
    "ACTION_NAMES",
    "HELLO_TIMEOUT",
    "CONTEXT_KEYS",
    "BridgeError",
    "ErrorCodes",
    "Connection",
    "new_id",
    "banner_frame",
    "request_frame",
    "response_frame",
    "error_frame",
    "decode_frame",
    "frame_kind",
    "merge_context",
    "context_of",
    "describe_actions",
]

#: Bumped whenever the envelope or an action's params/result contract changes.
#: A connector whose ``hello`` reports a different major version is rejected
#: with ``ErrorCodes.VERSION_MISMATCH`` rather than silently mis-speaking.
PROTOCOL_VERSION = "1.0"

ROLE_CONNECTOR = "connector"
ROLE_CLI = "cli"
ROLES: tuple[str, ...] = (ROLE_CONNECTOR, ROLE_CLI)

#: Seconds a fresh connection has to present a valid ``hello`` before the
#: daemon hangs up.
#:
#: Five seconds, not ten: the daemon speaks first (:func:`banner_frame`), so
#: silence is unambiguous — either the client never opened a socket, or it got
#: the banner and failed to answer. Nothing is gained by waiting longer, and a
#: short hang-up keeps the audit log honest instead of full of dead sockets.
#:
#: Reference point: the ``easyeda-agent`` daemon allows 1.5 s. We are more
#: generous only because a freshly started editor can be busy loading a board.
HELLO_TIMEOUT = 5.0

#: Seconds the daemon waits for the connector to answer a forwarded action.
ACTION_TIMEOUT = 30.0

#: Seconds the daemon waits for a screenshot: the editor renders the canvas
#: before replying, which is slower than a plain readback.
SCREENSHOT_TIMEOUT = 60.0

#: Seconds the daemon waits for a component placement. The editor resolves the
#: library on the *first* placement of a session, which on the measured host
#: outran the old 30 s default — and the placement landed anyway. The daemon
#: budget has to sit above the connector's own 30 s deadline so the connector's
#: readback ("did it land?") is what answers, not a daemon-side hang-up.
PLACEMENT_TIMEOUT = 60.0

#: Seconds the daemon waits for a primitive delete batch. Measured 2026-09-21
#: (012): the editor re-solves the page per primitive at ~3.7 s each, so a
#: 17-part cleanup needs ~63 s and blew through the 30 s default mid-batch.
#: 150 s covers ~40 primitives — the largest single cleanup worth doing in
#: one call; beyond that the caller should split on purpose, not by accident.
DELETE_TIMEOUT = 150.0

#: Seconds the daemon waits for a fab bundle. Three manufacture exports run in
#: one call (Gerber / pick-and-place / BOM) and each can take tens of seconds on
#: a real board, so the connector bounds **each file** at 60 s and this budget
#: sits above 3 of those deadlines: a connector that hangs on one file still
#: answers, per-file, inside the daemon's patience.
FAB_TIMEOUT = 240.0

#: Seconds the daemon waits for a part recommendation. Up to 3 rungs × 3 pages
#: of library search, each of which is a round trip to the editor's own library
#: backend — 30 s is the default for *one* read and this is up to nine.
RECOMMEND_TIMEOUT = 90.0

#: Name of the event the daemon sends the instant a socket opens.
EVENT_BANNER = "banner"

#: The keys a response frame's ``context`` may carry (023 §协议字段约定), in the
#: order they are merged. Wire spelling is camelCase like every other optional
#: field (``instanceId``, ``projectName``); :data:`_CONTEXT_ATTRS` maps each one
#: onto the bookkeeping attribute that holds it.
#:
#: ``pageType`` is the *document* domain — ``sch`` or ``pcb`` — and the
#: vocabulary is the connector's to spell because only the editor knows; the
#: daemon records what it is told rather than translating, and a value nobody
#: recognises is still recorded as itself. A wrong page type is a claim about
#: the editor, and quietly rewriting a claim is how a routing decision ends up
#: justified by something the daemon made up.
CONTEXT_KEYS: tuple[str, ...] = ("projectName", "projectUuid", "pageUuid", "pageType")

#: wire key -> the attribute it is merged into. One table, so the merge and the
#: read-back (:func:`context_of`) can never disagree about where a value lives.
_CONTEXT_ATTRS: dict[str, str] = {
    "projectName": "project_name",
    "projectUuid": "project_uuid",
    "pageUuid": "page_uuid",
    "pageType": "page_type",
}


@dataclass(frozen=True)
class Action:
    """One entry of the typed action catalogue."""

    name: str
    summary: str
    #: What the call can do to the project — the field a reviewer reads before
    #: letting anything run unattended. No default: every entry must state it,
    #: because a forgotten risk is a silently ungated action.
    #:
    #: * ``read`` — cannot change project content. Reads, probes, exports, and
    #:   view-only annotations (``canvas.highlight``) live here.
    #: * ``write`` — changes existing content in place (place, wire, attribute
    #:   writes, rename, save), or moves the editor's focus. ``doc.open`` and
    #:   ``doc.focus`` change no byte of the project, but they decide which page
    #:   the placement actions land on, so they are write.
    #: * ``create`` — produces a **new document**. The daemon refuses these
    #:   unless ``params.confirm is True`` (``CONFIRMATION_REQUIRED``).
    #: * ``dangerous`` — outranks every document write: replaces running code or
    #:   otherwise acts beyond any single document (``sys.self_update`` swaps the
    #:   connector's own bundle and reloads the editor page). Same choke point as
    #:   ``create``: refused unless ``params.confirm is True``. Filed as its own
    #:   tier (2026-10-06, issue「self_update 绕开唯一的创建闸」) because the
    #:   ``create`` wording ("produces a new document") cannot honestly cover it —
    #:   and because PROGRESS 坑 36 had already called the flow 破坏性 while the
    #:   enum still said ``write``; the taxonomy not matching the fact is exactly
    #:   the disease that let it sit.
    risk: str
    #: Who may originate this action. ``connector`` actions are executed by
    #: the extension; ``daemon`` actions are answered by the daemon itself.
    owner: str = "connector"
    params: tuple[str, ...] = ()
    #: Docs only — what a successful ``data`` payload looks like.
    returns: str = ""
    params_schema: str = ""
    #: Whether the action **changes the project's own bytes** (537A3), as opposed
    #: to the two things ``risk`` groups with it but should not send through the
    #: daemon's project whitelist: moving the editor's focus (``doc.open`` /
    #: ``doc.focus`` decide what the next call lands on, but change no project
    #: content) and replacing the connector itself (``sys.self_update`` swaps
    #: running code, not the design).
    #:
    #: **Defaults to ``True`` on purpose.** A new non-read action is a design
    #: write unless somebody deliberately says otherwise, so forgetting to
    #: register it cannot reopen the hole the whitelist exists to close — the
    #: safe answer is the one you get by not thinking about it. ``read`` actions
    #: are unaffected either way (the daemon checks ``risk`` first). Declared
    #: last so every pre-existing positional construction keeps its order.
    design_write: bool = True


#: Every action the bridge knows about. ``--help`` renders this table, and the
#: daemon refuses anything not listed (``ErrorCodes.UNKNOWN_ACTION``) instead
#: of forwarding an open-ended string into the editor.
ACTIONS: tuple[Action, ...] = (
    Action(
        name="hello",
        summary="Handshake. Must be the first frame on every connection.",
        owner="daemon",
        params=("token", "role", "protocol", "client", "pairCode"),
        returns="{ok: true, data: {role, protocol, serverTime}}",
        params_schema=(
            "pairCode: optional, and only a connector sends it — the public "
            "8-character code the connector shows, which an active "
            "`pair.authorize` grant must match before this handshake may write the "
            "pairing record (549). A connector that already presents the paired "
            "token does not need it."
        ),
        risk="read",
    ),
    Action(
        name="ping",
        summary="Liveness check; answered by the daemon, not forwarded.",
        owner="daemon",
        returns="{ok: true, data: {pong: true, connector: bool}}",
        risk="read",
    ),
    Action(
        name="pair.authorize",
        summary=(
            "CLI ONLY: authorise the next connector pairing for five minutes. "
            "The daemon keeps one in-memory grant — the normalised code, a "
            "monotonic deadline, the pairing fingerprint it was issued against and "
            "a failure count — and a connector may write `~/.boardwise/"
            "connector-token` only by presenting that code in `hello.pairCode`. A "
            "second authorisation replaces the first; a wrong code is counted for "
            "the audit and does not void the grant; a successful pairing spends it; "
            "`bridge revoke`, or any pairing in between, changes the record and so "
            "voids it; a daemon restart drops it. Refusals use "
            "UNAUTHENTICATED with `detail.pairCodeRequired` and a `reason`. The "
            "answer never carries a token and never the code in full."
        ),
        owner="daemon",
        params=("code",),
        returns="{authorized: true, pairCode, expiresIn, fingerprint, replaced}",
        params_schema=(
            "code: the pair code shown in the connector (case, spaces and hyphens "
            "are ignored)"
        ),
        # `write`, not `read` (549). Nothing on disk moves here, but the thing it
        # changes is *authority*: after this call a connector that arrives holding
        # the code may write the pairing record. Filing that as a read would let a
        # caller promised read-only (`bridge call --read-only`, the DSH tool's
        # default) mint the one grant the whole pairing gate rests on — a risk
        # label that says "harmless" about the decision that admits a peer.
        # `design_write` stays False: no project byte, no page, no focus.
        risk="write",
        design_write=False,
    ),
    Action(
        name="document.current",
        summary="Which project / document / document type is open in the editor.",
        params=(),
        returns="{project: {…}, document: {…}, type: 'sch'|'pcb'|…}",
        risk="read",
    ),
    Action(
        name="sys.probe",
        summary=(
            "READ-ONLY introspection of the editor's live API surface: the "
            "editor version, the namespaces bound on `eda`, and what each "
            "requested namespace actually exposes. Exists because the type "
            "package declaring a method and the running editor exposing it "
            "are different statements. `checks` verifies named members with "
            "a plain `typeof ns[name]` read (immune to the exotic host objects "
            "that abort enumeration), enumeration finds members nobody "
            "predicted, `call` dispatches an allowlisted read-only action, and "
            "`realm` measures constant-code execution. `instances` (550B) "
            "resolves named PCB primitives by id and reports whether the "
            "single method the type package declares on such an instance is "
            "there: `getConnectedPrimitives` on a pad, `getEntireTrack` on a "
            "line or an arc, `getAdjacentPrimitives` on a line, an arc or a "
            "via. It is a measurement of the method, not a net-path, and it "
            "reads nothing but the returned primitives' ids. Measured on EDA "
            "4.1.100 (550B): line/arc/via answer all three, while a base pad has "
            "no `getConnectedPrimitives` — that method lives on "
            "`IPCB_PrimitiveComponentPad`, so a pad row falls back to a bounded "
            "component-pad lookup (see params_schema) instead of reporting the "
            "base instance's absence as the component pad's."
        ),
        params=(
            "checks", "namespace", "namespaces", "functionsOnly", "call", "realm",
            "instances", "limit",
        ),
        returns=(
            "realm mode (R4): {version, connector, topLevel, realm: {kinds, execution: "
            "{indirectEval, newFunction, dynamicImportDataUrl: {ok, value|error}}, note}} "
            "— constant code only, nothing from params is executed; "
            "checks mode: {version, topLevel, checks: {NAME: {present, kind, "
            "checked, missing, status: {member: 'function'|'object'|"
            "'undefined'|'threw: …'|'namespace-absent'}, arity: {member: "
            "fn.length for the members that are functions}, notes?}}}; "
            "enumerate mode: {version, topLevel, namespaces: {NAME: {present, "
            "functions, data, errors?}}}; call mode (025): {version, topLevel, "
            "call: {action, params, result}} — result is the named action's own "
            "answer; instances mode (550B): {version, connector, topLevel, page: "
            "{uuid, type}, readOnly: true, instances: [{kind, primitiveId, method, "
            "status: 'function'|'absent'|'not-found'|'unavailable'|'error', arity?, "
            "call?: {ok: true, count, ids, truncated, unreadable?} | {ok: false, "
            "error}, error?, resolution?: 'direct'|'component', componentFallback?: "
            "{components, matches, readErrors, truncated}}]} — `call` is present iff "
            "the method was actually invoked, `count` is the host's own array length "
            "while `ids` stops at limit, and a non-array answer is an error, never an "
            "empty list. On a pad row, `resolution` says which instance answered: "
            "'direct' (the base pad from pcb_PrimitivePad.get, and then no component "
            "is enumerated at all) or 'component' (the bounded ComponentPad fallback "
            "below), and `componentFallback` is its evidence — components inspected, "
            "how many carried the requested primitive id, per-component read errors, "
            "and whether the 512-component cap truncated the scan"
        ),
        params_schema=(
            "instances (550B): optional array of 1..4 objects "
            "{kind: 'pad'|'line'|'via'|'arc', primitiveId: non-empty string, "
            "method: 'connected'|'entireTrack'|'adjacent', "
            "onlyCentreConnection?: bool only with `connected` (default true), "
            "includeVias?: bool only with `entireTrack` (default false)} — unknown "
            "keys are refused, and pad takes `connected`, line/arc take "
            "`entireTrack` or `adjacent`, via takes `adjacent`. It is a mode of "
            "its own: combined with realm/call/checks/namespace/namespaces/"
            "functionsOnly the call is refused BAD_REQUEST, and without `instances` "
            "every other mode behaves exactly as before; "
            "limit: integer 1..64, default 32, only with `instances` — how many "
            "primitive ids one item's answer may report; the answer's `count` is "
            "always the host's own length and `truncated` says ids were held back. "
            "The focused document must be exactly a PCB page (a wrong page, or a "
            "focus that cannot be proven to be a PCB, is PAGE_MISMATCH and nothing "
            "is read: the probe never switches the page itself). "
            "pad.connected and the ComponentPad fallback (550B, measured on EDA "
            "4.1.100): the instance pcb_PrimitivePad.get(id) answers has no "
            "getConnectedPrimitives — the type package declares it on "
            "IPCB_PrimitiveComponentPad — so when the base instance lacks the "
            "method the connector walks pcb_PrimitiveComponent.getAll() and each "
            "component's getAllPins(), matching only getState_PrimitiveId, capped "
            "at 512 components (a longer list is disclosed as "
            "componentFallback.truncated). A direct hit enumerates nothing. One "
            "match calls the method on that component pad (resolution 'component'); "
            "more than one is an error/ambiguous refusal, never the first match; a "
            "negative answer stays 'absent' only when the walk completed — any "
            "per-component read gap or truncation upgrades it to 'error'/"
            "'unavailable', because 'the ComponentPad has no such method either' "
            "cannot be claimed from an incomplete scan. line/arc/via answers are "
            "unchanged and carry neither key."
        ),
        risk="read",
    ),
    Action(
        name="sys.self_update",
        summary=(
            "Replace this connector's bundle in the editor's extension "
            "IndexedDB (User_<teamUuid>_v6, store names are EasyEDA-internal) "
            "and reload the page, so a new build takes effect WITHOUT "
            "uninstall/import/restart. The response is sent before the reload "
            "fires. Only `config.version` and `fileSize` are touched in the "
            "index record — the external-interaction grant is preserved. Every "
            "step validates; any failure is an explicit error (fall back to a "
            "manual reinstall), never a silent degrade. `reload: false` (528A) "
            "writes the same records and schedules no reload: the stored build "
            "stays dormant until the editor re-evaluates the extension."
        ),
        params=("bundleB64", "version", "confirm", "reload"),
        returns="{ok, oldVersion, newVersion, bytes, database, reloadInMs}",
        params_schema=(
            "bundleB64: the new dist/index.js, base64-encoded (required); "
            "version: the new version string to store (required); "
            "confirm: must be `true` — the daemon's dangerous-tier gate refuses "
            "anything else, because this replaces running code and reloads the "
            "editor (2026-10-06: it was risk=write and slipped the create gate "
            "wide open while a blank pcb.doc.new was refused); "
            "reload: optional, default `true` — only the exact value `false` "
            "writes without reloading, and the reply then carries "
            "`reloadInMs: 0` so a caller can tell the two apart (528A; "
            "`boardwise bridge update-connector --no-reload`)"
        ),
        risk="dangerous",
        # 537A3: replaces the connector's bundle and reloads the editor — not a
        # byte of the project changes, so a project whitelist must not stop it.
        design_write=False,
    ),
    Action(
        name="sys.identity",
        summary=(
            "READ-ONLY: the editor's two identity layers, and whether they agree "
            "(018 §B). Returns the project the editor reports as focused, the "
            "project the *active document* belongs to (from "
            "getCurrentDocumentInfo's parentProjectUuid, or the document's own "
            "per-kind info read), a `consistent` flag comparing the two, and the "
            "active page's uuid. Exists because the two layers disagreed on the "
            "machine (2026-09-21): `doc.open`, which addresses the pages of the "
            "project the editor has open, refused a uuid whose document was in "
            "front — so a caller about to write needs to be able to ask this "
            "first. `consistent` is **null** (with `consistentBasis`) when the "
            "comparison cannot be made, never a hopeful true."
        ),
        params=(),
        returns=(
            "{focusedProject: {projectUuid, name, friendlyName} | null, "
            "activeDocument: {uuid, type, tabId, projectUuid, project, source} | null, "
            "consistent: bool | null, consistentBasis: 'project-uuid'|"
            "'focused-project-listing'|'no-active-document'|'unavailable', "
            "pageUuid: str | null, readOnly: true, notes?}"
        ),
        risk="read",
    ),
    # --- 025: online review data (document file / source, the two DRC checks) --
    Action(
        name="sys.get_document_file",
        summary=(
            "READ-ONLY: the open document as an .epro/.epro2 archive, base64. The "
            "online half of the offline review pipeline — the bytes are the same "
            "kind of archive `boardwise review` reads, so they go through "
            "load_epru_text -> build_schematic_model with no rule changes. The "
            "declaration gates the call on 工程设计图 > 文件导出 and says a missing "
            "grant throws every time; the connector cannot read grants, so a "
            "refusal carries the host's own message plus the documented gates in "
            "`detail.permissions`. `isZip` is reported rather than assumed."
        ),
        params=("fileType", "fileName", "password", "timeoutMs"),
        returns=(
            "{fileType, source, scope: 'document', encoding: 'base64', name, mime, "
            "bytes, data, isZip, note?}"
        ),
        params_schema=(
            "fileType: epro2|epro (default epro2); fileName: optional; password: "
            "optional (an encrypted export reads as an unreadable archive "
            "downstream); timeoutMs: optional, default 30000"
        ),
        risk="read",
    ),
    Action(
        name="sys.get_project_file",
        summary=(
            "READ-ONLY: the open **project** as one .epro/.epro2 archive, base64 — "
            "every page, every library document and the PCB in a single payload, "
            "which is why 025 batch 2's data path tries it first (tier "
            "`project-file`). Gated on 工程管理 > 下载工程, a **different** gate "
            "from getDocumentFile's 工程设计图 > 文件导出, so \"the document export "
            "works\" does not imply this one does; a refusal carries the host's "
            "message plus the gate the declaration names for this call. `scope` "
            "says which archive the caller actually got."
        ),
        params=("fileType", "fileName", "password", "timeoutMs"),
        returns=(
            "{fileType, source, scope: 'project', encoding: 'base64', name, mime, "
            "bytes, data, isZip, note?}"
        ),
        params_schema=(
            "fileType: epro2|epro (default epro2); fileName: optional; password: "
            "optional; timeoutMs: optional, default 30000"
        ),
        risk="read",
    ),
    Action(
        name="sys.get_document_source",
        summary=(
            "READ-ONLY: one document's own source text, unjudged. The declaration "
            "is one line (`Promise<string | undefined>`, @beta) and says nothing "
            "about the format, so whether it equals the .epru record stream inside "
            "an .epro2 is a question for a probe, not for this action. Truncates "
            "to `maxChars` and echoes both ends of the text (the head, plus `tail` "
            "when truncated), because a stream is recognised by its first and last "
            "records. `uuid` is honoured or refused: the host's `getDocumentSource()` "
            "takes no arguments (measured arity 0 on EDA 3.2.186), so it reads the "
            "**active** document and nothing else — asking for any other uuid is "
            "`DOC_NOT_ACTIVE` (open it with `doc.open` first), never a silent return "
            "of the wrong document's source (179, the hole 178b's probe filed). Omitting `uuid` reads "
            "whatever is active. Every answer names the document it read (R1-2): "
            "`uuid` / `name` / `type` as the project's document listing spells "
            "them, or all three null with a `notes` line when the focus moved "
            "during the read."
        ),
        params=("maxChars", "uuid"),
        returns=(
            "{source, uuid, name, type, chars, maxChars, truncated, data, headLines, "
            "tail?, note?, notes?}"
        ),
        params_schema=(
            "maxChars: 256..4000000 (default 65536); `data` is the head, `tail` "
            "the last 1024 characters, present only when truncated; uuid: optional, "
            "must be the active document's uuid (from doc.list) or the call is "
            "refused with DOC_NOT_ACTIVE"
        ),
        risk="read",
    ),
    Action(
        name="sys.set_document_source",
        summary=(
            "**RECON ONLY, DANGEROUS**: rewrite the **active** document's source "
            "text. The write half of the source channel (R1-3): 178b/179 measured "
            "that the bridge could read a document's source but nothing could "
            "write one, so whether `doc.rename`'s NOT_SUPPORTED on 3.2.186 is "
            "repairable through the source was unmeasurable. Intended use is a "
            "scratch page of the test project (create → rewrite → read back → "
            "delete; outputs/R1/runbook.md §R1-3) — the discipline is the "
            "caller's, because `setDocumentSource` replaces a whole document's "
            "text in one call. `uuid` is required and must be the active "
            "document (179's DOC_NOT_ACTIVE shape): the host call takes the text "
            "and nothing else (declared arity 1), so it rewrites whatever is in "
            "front. `risk=dangerous` puts it behind the create gate's choke "
            "point — the daemon refuses it unless `params.confirm is True` and "
            "strips the flag. A `true` is read back "
            "(`readBack: identical|differs|unreadable`) rather than trusted; "
            "anything but `true` is a failure naming the host's own answer."
        ),
        params=("source", "uuid", "confirm"),
        returns=(
            "{source, uuid, type, chars, hostAnswer: true, readBack, "
            "readBackChars, notes?}"
        ),
        params_schema=(
            "source: the whole document text as `sys.get_document_source` "
            "returns it (required, non-empty — an empty string would be a "
            "blanket erase); uuid: required, must be the active document's uuid "
            "(from doc.list) or the call is refused with DOC_NOT_ACTIVE; "
            "confirm: must be `true` — the daemon's dangerous-tier gate refuses "
            "anything else and consumes the flag, so the connector never sees it"
        ),
        risk="dangerous",
    ),
    Action(
        name="sch.drc_check",
        summary=(
            "READ-ONLY: the schematic DRC, via sch_Drc.check(strict, "
            "userInterface, includeVerboseError). The answer's shape changed "
            "between editor generations, and both are read (038 O3a/O3b): the "
            "025 §0 measurement (V3) found **aggregate counts only** — "
            "`[{type: 'fatalError'|'error'|'warn', count}]`, the per-item detail "
            "going to the bottom panel, which has no read interface; the V4.1.93 "
            "measurement (2026-10-31, two pages of the test project) found **one "
            "object per finding** — `{type, rule, primitives}` with no `count`, "
            "519 of them. The connector normalises both: `entryShape` says which "
            "shape answered, `total`/`byType` sum the recognised entries, and "
            "`items` keeps the per-item objects verbatim. The host array is still "
            "returned **verbatim** under `counts`; an entry with a numeric "
            "`count` contributes that count and is never split, a legal-severity "
            "entry without one contributes 1, and anything else is counted in "
            "`unparsed` instead of folding in as zero. `passed` is `null` "
            "(unknown) as soon as any entry was unparsed. A boolean answer is "
            "reported as mode `boolean`, never as an empty result. Throws on a "
            "page that is not a schematic page, and the throw is reported with "
            "the focused document named."
        ),
        params=("strict", "userInterface", "includeVerboseError"),
        returns=(
            "{source, checked, mode: 'counts'|'boolean'|'unexpected', "
            "entryShape?: 'aggregate'|'per-item', counts, entries?, total?, "
            "byType?, unparsed?, items?, passed, elapsedMs, args, page, "
            "uiRequested, notes?, raw?, unrenderable?, note?}"
        ),
        params_schema=(
            "strict: default true; userInterface: default false (true pops the "
            "editor's bottom DRC panel); includeVerboseError: default true"
        ),
        risk="read",
    ),
    Action(
        name="pcb.drc_check",
        summary=(
            "READ-ONLY: the PCB DRC, per item, via pcb_Drc.check(strict, "
            "userInterface, includeVerboseError) — the one DRC that hands back "
            "item-level detail (025 §0, and measured 2026-09-23: the tree is "
            "group.list[].list[] with leaves carrying ruleName / errorType / "
            "explanation.str / obj1 / obj2 / globalIndex / parentId, and every "
            "node states its own `count`). Groups are returned **verbatim** so a "
            "Finding-mapping layer can read the shape the editor really produces; "
            "`counts` only describes what came back, and whole groups are dropped "
            "(never cut in half) to stay inside `maxChars`. A non-PCB page is "
            "kept distinct from a clean board: the declaration promises "
            "`undefined`, the host actually **throws** (a message-bus error — the "
            "check publishes to the PCB canvas topic and nothing subscribes on a "
            "schematic page), and both are reported as `checked: false` with the "
            "focused document named — never as an empty result. Note that an "
            "*empty* PCB is not a clean board with zero findings either: the test "
            "project's empty PCB answered one 'Netlist Error / Import Changes'."
        ),
        params=("strict", "userInterface", "includeVerboseError", "maxChars"),
        returns=(
            "{source, checked, available, mode: 'groups'|'boolean'|'unexpected', "
            "groups, counts: {groups, returnedGroups, errors, errorsSource, items, "
            "byLabel, jsonChars}, truncated, elapsedMs, args, page, uiRequested, "
            "reason?, notes?, raw?}"
        ),
        params_schema=(
            "strict: default true; userInterface: default false; "
            "includeVerboseError: default true; maxChars: 1000..4000000 (default "
            "200000)"
        ),
        risk="read",
    ),
    # --- 123: the DRC rule set, read-only -------------------------------------
    Action(
        name="pcb.drc_ruleset",
        summary=(
            "READ-ONLY: the DRC rule set in force on the focused PCB, via the "
            "read-side members of pcb_Drc — getCurrentRuleConfigurationName(), "
            "getCurrentRuleConfiguration(), getDefaultRuleConfigurationName(), "
            "getRealTimeDrcStatus() (`all: true` adds getAllRuleConfigurations()). "
            "A PCB DRC result is a statement about a rule set, so 025's leaves "
            "without these are half an answer. The values come back **verbatim**, "
            "sanitised conservatively: functions dropped (they are the "
            "back-references that make an editor object graph cyclic), `toJSON`-"
            "bearing objects rendered through the host's own serialiser (a Date "
            "stays the instant it is), cycles cut as '(cycle)' at the re-entry "
            "point; every cut is counted and named in `notes`. **Nothing is "
            "compared** — whether a rule set matches the board's process is a "
            "judgement the review layer makes, not the read. **No write is "
            "reachable from this action**: save/overwrite/create/delete/rename "
            "rules, setAsDefault, start/stopRealTimeDrc and the whole "
            "net-class / pad-pair / equal-length / differential-pair family are "
            "off the list. Focus discipline is `pcb.drc_check`'s: a non-PCB "
            "focus is refused with PAGE_MISMATCH and the focused document named "
            "(no auto doc.open — opening a board is the caller's job), and an "
            "absent member is reported as absent rather than as a value, so a "
            "board whose rule set could not be read never reads as a board with "
            "no rules."
        ),
        params=("maxChars", "all"),
        returns=(
            "{source: 'pcb_Drc', page, ruleset: {currentName, current, defaultName, "
            "realTimeDrcStatus, allConfigurations?}, reads: [{key, path, read}], "
            "missing, unreadable, jsonChars, elapsedMs, readOnly: true, notes?}"
        ),
        params_schema=(
            "maxChars: 1000..4000000 (default 400000); all: true adds "
            "getAllRuleConfigurations() (the whole catalogue, not this board's set)"
        ),
        risk="read",
    ),
    # --- 551: the persisted net classes + net rules, read-only ----------------
    Action(
        name="pcb.net_class.list",
        summary=(
            "READ-ONLY 551: the real, host-persisted EasyEDA PCB net classes plus "
            "the net-rule records, via pcb_Drc.getAllNetClasses() and "
            "pcb_Drc.getNetRules(). It answers a different question from "
            "`pcb.drc_ruleset` — which nets are grouped and what their rules say, "
            "rather than which rule set the board is checked against — which is "
            "why it is its own action instead of two more keys on that narrow "
            "read. Values come back **verbatim**, sanitised exactly as the "
            "rule-set action sanitises (functions dropped, `toJSON`-bearing "
            "objects rendered through the host's own serialiser, cycles cut as "
            "'(cycle)', every cut counted and named in `unreadable`/`notes`); no "
            "field is invented for what the host has not been measured to send. "
            "**「could not read」is never「there are none」**: an absent member "
            "lands in `missing`, a throwing or unserialisable one in "
            "`unreadable`, and either way the key is `null` (never `[]`) and "
            "`count` is `null` rather than a fabricated 0. `classes: []` beside a "
            "non-empty `netRules` is a real state and both are reported. **No "
            "write is reachable**: createNetClass/deleteNetClass/"
            "modifyNetClassName/addNetToNetClass/removeNetFromNetClass and the "
            "whole pad-pair / equal-length / differential-pair / rule-writer "
            "family are off the list. The router's heuristic width ladder "
            "(「signal/power/high-current」guessed from net names) is **not** this "
            "data and is never reported as a net class. Focus discipline is "
            "`pcb.drc_ruleset`'s: a non-PCB focus is refused with PAGE_MISMATCH "
            "and the focused document named, with no auto doc.open; `active: "
            "null` is not evidence that a PCB is in front."
        ),
        params=("maxChars",),
        returns=(
            "{source: 'pcb_Drc', page, classes: [{name, nets, color}] | null, "
            "netRules | null, count (classes.length or null), reads: [{key, path, "
            "read}], missing, unreadable, jsonChars, elapsedMs, readOnly: true, "
            "notes?}"
        ),
        params_schema=(
            "maxChars: 1000..4000000 (default 400000), the same bounds as "
            "pcb.drc_ruleset; the reading is never clipped — an oversized answer "
            "says so in notes and keeps every key"
        ),
        risk="read",
        design_write=False,
    ),
    # --- 559: the host half of `boardwise pcb connection` --------------------
    Action(
        name="pcb.connection_probe",
        summary=(
            "READ-ONLY 559: host evidence for 「are these two named pads on the "
            "same copper?」, as two REF.PAD ends — the direct "
            "`getConnectedPrimitives(false)` answer on each end's resolved "
            "ComponentPad. **Direct-only (559B)**: `getEntireTrack` is not called at "
            "all, because on a real net it answered 76 ids with `truncated: true` "
            "while four of them belonged to copper components the offline 550 model "
            "separates (evidence/559/entire-track-rejection.json) — membership in an "
            "id set is not a connected component. What remains is directly "
            "measurable: both ends naming the same typed Line/Arc, or one end naming "
            "the other end's pad id. **No verdict and no path**: the verdict is "
            "projected in Python (`boardwise.core.connection`) from the typed, "
            "sourced intersections this action reports. Each end carries its "
            "resolution (matches / candidates / readErrors / truncated / complete), "
            "the resolved pad's own public fields (primitiveId, padNumber, net, "
            "type) and `direct: {ok, count, ids, items, truncated, unreadable?, "
            "error?}`; there is no `tracks[]`, nothing is guessed and nothing absent "
            "is reported as an empty array. **Via / fill / pour / polyline adjacency "
            "is not proof** and is reported under `unknown` instead of being read as "
            "connectivity. "
            "Focus discipline is 550B's `requirePcbFocus`: the focused page must be "
            "exactly a PCB (PAGE_MISMATCH otherwise, with the focused document "
            "named and nothing read), and no `doc.open`/`doc.focus` is ever "
            "performed on the caller's behalf — the first board of a project is "
            "never assumed. **No write is reachable**: the action only reads pad "
            "identity and the one direct connection method; the caps it spends (512 "
            "components, 16 direct primitives per end) are all disclosed in "
            "`coverage` with a `truncated` bit rather than silently applied. "
            "`coverage.complete` is the connector's own summary — a caller deciding "
            "a **negative** must re-derive it from the individual readings."
        ),
        params=("from", "to"),
        returns=(
            "{page: {uuid, type}, readOnly: true, from, to, errors, unknown, "
            "ignored, coverage: {scan, direct, unknown, ignored, errors, "
            "complete}} — each end is {ref: {designator, pad}, status: "
            "'resolved'|…, error?, resolution: {matches, candidates, components?, "
            "readErrors, truncated, complete}, pad: {primitiveId, padNumber, net, "
            "type} | null, direct: {ok, count, ids, items, truncated, "
            "unreadable?, error?} | null}"
        ),
        params_schema=(
            "from / to: each one `REF.PAD` as a single string — a component "
            "designator, a separating dot, a pad number (e.g. `U9.2`), split at the "
            "**last** dot so a *designator that itself contains dots* still parses "
            "(the pad is always the trailing segment; a pad number that contains a "
            "dot cannot be expressed). The key set is closed: any other key is "
            "BAD_REQUEST, and a missing, non-string or dot-less end is refused "
            "before the host is touched"
        ),
        risk="read",
        # Reads two pads' identity and the two connection methods; no project
        # byte, no page, no focus.
        design_write=False,
    ),
    # --- 562: the host half of `boardwise pcb path` --------------------------
    Action(
        name="pcb.path_probe",
        summary=(
            "READ-ONLY 562: multi-hop copper **graph evidence** between two named "
            "pads — the host half of `boardwise pcb path`. Two `REF.PAD` ends in; "
            "out comes the adjacency the host itself answered, keyed by primitive "
            "identity: typed `nodes[]` (`type`, `primitiveId`, `net`), "
            "**directed** `edges[]` (`from`, `to`, `method`, `kind`, `callIndex`, "
            "`hostOrder` — one row per direction the host answered), `seeds[]`, "
            "`frontier[]` (vertices that were never expanded), `coverage`, and its "
            "own `unknown`/`ignored`/`errors`. **`getEntireTrack` is never "
            "called**: 559B measured an id set to span copper components the "
            "offline model separates "
            "(evidence/559/entire-track-rejection.json), so an id set is not a "
            "connected component and this action spends no id budget. What it "
            "reads instead is the two seams a walk can be sourced from — each "
            "resolved pad's `getConnectedPrimitives(false)` and each Line/Via's "
            "`getAdjacentPrimitives()` — capped and disclosed in `coverage` with "
            "its `truncated` bits. **No verdict and no path**: whether this graph "
            "proves a connection is projected in Python "
            "(`boardwise.core.livepath`), where a hop needs **reciprocal** "
            "adjacency, only Line/Via may be walked, Arc / pad↔via contact / "
            "poured copper are named `unknown`/`ignored`, and an unexpanded "
            "`frontier`, a truncation or an error keeps a negative answer from "
            "being claimed. Focus discipline is 550B's `requirePcbFocus`: the "
            "focused page must be exactly a PCB (`PAGE_MISMATCH` otherwise, with "
            "the focused document named and nothing read), and no "
            "`doc.open`/`doc.focus` is ever performed on the caller's behalf. "
            "**No write is reachable**: the action reads primitive identity, nets "
            "and the two adjacency methods; params are closed to `from`/`to`."
        ),
        params=("from", "to"),
        returns=(
            "{page: {uuid, type}, readOnly: true, from, to, nodes: [{type, "
            "primitiveId, net, layer?}], edges: [{from: {type, primitiveId}, "
            "to: {type, primitiveId}, method, kind, callIndex, hostOrder}], "
            "seeds: [{type, primitiveId, …}], frontier: [{type, primitiveId}], "
            "coverage: {scan, direct, adjacent, nodes, edges, perCallTruncated, "
            "budget, nets, seeds, frontier, complete}, unknown, ignored, errors} "
            "— each end is {ref: {designator, pad}, status: 'resolved'|…, "
            "resolution: {matches, candidates, readErrors, truncated, "
            "complete}, pad: {primitiveId, padNumber, net, type} | null, "
            "direct: {ok, count, ids, items, truncated, error?} | null}. Shape "
            "only — the walk, the three states and every refusal are decided in "
            "Python (`boardwise.core.livepath`) over these rows, never here."
        ),
        params_schema=(
            "from / to: each one `REF.PAD` as a single string — a component "
            "designator, a separating dot, a pad number (e.g. `U9.2`), split at "
            "the **last** dot so a designator that itself contains dots still "
            "parses. The key set is closed: any other key is BAD_REQUEST, and a "
            "missing, non-string or dot-less end is refused before the host is "
            "touched"
        ),
        risk="read",
        # Reads two pads' identity, nets and the two adjacency methods; no
        # project byte, no page, no focus.
        design_write=False,
    ),
    # --- 026b: the promoted diagnostics action ------------------------------
    Action(
        name="sys.connector_status",
        summary=(
            "The About box's own read-out, for a caller outside the editor: the "
            "connection state plus the lifecycle counters that tell an inert "
            "extension from a missing one — moduleBootstrapObserved (was the bundle "
            "evaluated at all?), activateObserved (was activate() dispatched?), "
            "evaluations (how many times), and the background watchdog's state "
            "(running | unavailable(reason) | not started), which is the difference "
            "between a window that recovers by itself in the background and one that "
            "waits for the user to bring it to the front. Read-only: it never starts, "
            "stops or reconnects anything. If no evaluation has published its runtime "
            "record, present=false says so rather than guessing. Since 087F2 it also "
            "answers `capabilities.pcbRenderViewport` (a fact about the connector build, "
            "present on every branch): `true` only where `export.render` really accepts a "
            "PCB target and answers `channel/evidenceGrade: 'viewport'` (#87②, 087F1). A "
            "connector that omits the key is older than that branch, so a caller must "
            "read a missing key as **no such capability** and never as a reason to spend "
            "a render timeout finding out — the flag exists to be read before the call."
        ),
        params=(),
        returns=(
            "{present: bool, readStatus: bool, capabilities?: "
            "{pcbRenderViewport?: bool}, status: {state, detail?, lastError?, "
            "paired?, fingerprint?, minConnectorVersion?, connectorOutdated?, "
            "moduleBootstrapObserved, activateObserved, evaluations, bootstrapAt?, "
            "activateAt?, watchdog?: {state, reason?, wakes, lastWakeAt?, "
            "activityPosts, checkIntervalMs, activityTimeoutMs, lastWake}}, "
            "moduleBootstrapObserved, activateObserved, evaluations} | "
            "{present: false, capabilities?, error?|observed|note}"
        ),
        risk="read",
    ),
    # --- 111b: the sys_Log panel, read as text -------------------------------
    Action(
        name="sys.log_read",
        summary=(
            "READ-ONLY: the host's own log panel, as text, via "
            "`sys_Log.sort(types?)`. It exists because the **V3** `sch_Drc.check` "
            "verbose answer held **aggregate counts only** (025 §0, measured: no "
            "detail), while 岳's log panel showed 22 warn lines of full text on "
            "2026-10-04. (V4 enumerates its findings in the array itself — see "
            "`sch.drc_check`'s `items` — so the panel is no longer the only "
            "per-item source there.) "
            "**Measured live 2026-10-04 (111b, test/P1, 22 warns): an API-driven "
            "`sch.drc_check` writes NOTHING to sys_Log — neither with "
            "userInterface:false nor :true — so this action does NOT recover the "
            "per-item ERC text of a harness-run check; that wording still comes "
            "only from a human running DRC from the editor menu (which is what "
            "fills the panel; inferred from the panel format, not yet re-confirmed "
            "by a manual run). What the action verifiably does: read the panel "
            "back — extension diagnostics, openProject events, and any menu-run "
            "ERC text that is there. `sort` only: `export` is never called "
            "(it opens the editor's save dialog) and `clear` is never called (it "
            "destroys the evidence); `find` is unused because sort plus a client-side "
            "substring filter covers it. Lines cross the wire verbatim — no "
            "re-casing, trimming or wrapping."
        ),
        params=("types", "since", "pattern", "limit", "maxChars"),
        returns=(
            "{source: 'sys_Log.sort', lines: [{timestamp, type, message}], count, "
            "total, truncated, types?, since?, pattern?, elapsedMs, notes?}"
        ),
        params_schema=(
            "types: one or more of ESYS_LogType (info | warn | error | "
            "fatalError | find | replace | openProject), omitted = every type; "
            "since: ms since the epoch, keeps `timestamp >= since`; pattern: "
            "case-insensitive substring; limit: 1..5000 (default 200); maxChars: "
            "1..4000000 (default 200000) — whole lines only, a line that does not "
            "fit is dropped, never sliced"
        ),
        risk="read",
    ),
    # --- 026 probe batch: TEMPORARY instrumentation --------------------------
    # (empty: `sys.worker_probe` was removed in 0.4.18 / 026c. Its four
    # measurement modes were retired with their answers in 026b; its one
    # remaining question — can a native WebSocket reach the daemon from the page
    # and from a Worker? — was measured on the machine in batch 2b, and the
    # answer is recorded in `outputs/026b_2b_p6_nativews.txt` and in the P6
    # section of `outputs/026_probe.md`. The section header stays as the marker
    # that the whole probe family is gone, not as a place to add another one.)
    Action(
        name="sch.readback",
        summary=(
            "Schematic components and a primitive subset, for a netlist view. "
            "Refused with PAGE_MISMATCH when the focused document is a PCB (527B): "
            "the read answers in whatever namespace it is named after, not in the "
            "focused page's, so a wrong-page call used to return a phantom row or "
            "die on `null`."
        ),
        params=("includePrimitives",),
        returns=(
            "{kind, components: [...], primitives: [...], componentCount, "
            "unreadable?: int (count of unreadable rows + failed reads + null "
            "holes the host left), reason?: str (the first of them), "
            "problems?: [str] (an unusable focus reading — an unnamed document "
            "type means the page guard did not run)}. Each component row carries "
            "the optional `value` / `mpn` / `valueSource` / `mpnSource` lift "
            "(#87⑤): `value` is `OtherProperty['Value']`, `mpn` prefers "
            "`ManufacturerId` and falls back to `OtherProperty['Manufacturer "
            "Part'|'ManufacturerPart'|'partNumber']`, blanks read as null and a "
            "failed getter keeps the row and is counted — an old connector "
            "without these keys still answers, so callers keep the archive "
            "fallback instead of inventing an empty value"
        ),
        risk="read",
    ),
    Action(
        name="pcb.readback",
        summary=(
            "PCB components and a primitive subset (pads / tracks / vias). Same "
            "PAGE_MISMATCH refusal as sch.readback, mirrored for a schematic page "
            "in front (527B)."
        ),
        params=("includePrimitives",),
        returns=(
            "same shape with kind 'pcb'; includePrimitives adds "
            "{__meta: {unavailable: [namespace], returned, nullEntries?}} as "
            "primitives[0]"
        ),
        risk="read",
    ),
    Action(
        name="export.screenshot",
        summary="Native editor image export of the current canvas, as base64 PNG.",
        params=("fit",),
        returns="{format: 'png', encoding: 'base64', data: '…'}",
        risk="read",
    ),
    Action(
        name="export.render",
        summary=(
            "Render the target document to an image file (base64). On a "
            "**schematic** page this is the *document* render via "
            "sch_ManufactureData.getExportDocumentFile — the acceptance image; a "
            "viewport capture (export.screenshot) can return cached frames on this "
            "host, so it is never evidence. On a **confirmed PCB** (#87②) the "
            "document-render API hangs on this host (EDA 4.1.93, measured 60 s), "
            "so the action takes the one channel the 087f probe proved — "
            "zoomToAllPrimitives + dmt_EditorControl.getCurrentRenderedAreaImage — "
            "and answers a *viewport* PNG marked channel/evidenceGrade='viewport'. "
            "Scope can be the current page, a selection of primitives, or the whole "
            "project on a schematic; a multi-page project may come back as a zip "
            "and the `format` field says which. A PCB accepts format=png + "
            "scope=page only: svg/pdf/selection/project are refused by name and "
            "never reach the schematic export."
        ),
        params=("format", "scope", "ids", "fileName", "pageUuid", "timeoutMs"),
        returns=(
            "schematic: {format: 'image/png'|'image/svg+xml'|'application/pdf'|'zip', "
            "encoding: 'base64', bytes, data, scope, channel: 'document', "
            "activatedPageUuid?, activated?, note}. PCB: the same fields with format "
            "'image/png', scope 'page', plus channel: 'viewport', evidenceGrade: "
            "'viewport' and a note saying it is not a document render and freshness "
            "must be checked before use; there are no bboxes (a capture is not "
            "geometry)"
        ),
        params_schema=(
            "format: png|svg|pdf (default png; a PCB accepts png only); scope: "
            "page|selection|project (default page; a PCB accepts page only); ids: "
            "primitive ids, required when scope=selection; fileName: optional, "
            "default render.<ext>; pageUuid (0.4.22): the page the render is about "
            "— and #87② the *only* doc.list-confirmed way to name a PCB target "
            "when it is not the active document; timeoutMs (0.4.20): clamped into "
            "1..60 s, default 30 s, and it bounds the PCB viewport capture too"
        ),
        risk="read",
    ),
    Action(
        name="canvas.highlight",
        summary="Mark primitives on the live canvas by uuid (review annotations).",
        params=("uuids", "color", "clear", "zoom"),
        returns="{highlighted: n, cleared: bool}",
        risk="read",
    ),
    # --- 006: schematic candidate-model reads -------------------------------
    Action(
        name="sch.component_pins",
        summary=(
            "Recon (read-only): the placed pins of one component, with geometry. "
            "The seventh path to a pin the six-path table had missed — "
            "sch_PrimitiveComponent.getAllPinsByPrimitiveId returns "
            "器件引脚图元 (x/y/pinNumber/pinName/rotation/pinLength) for a PLACED "
            "component, @beta with no ADD-since-v4 marker. Decides whether F3 "
            "(drifted-part endpoint snapping) is implementable."
        ),
        params=("primitiveId",),
        returns="{primitiveId, returned, pins, note?, readErrors?}",
        params_schema="primitiveId: the placed component's primitive id (required)",
        risk="read",
    ),
    Action(
        name="sch.set_pin_no_connected",
        summary=(
            "Write ONE placed pin's native NoConnected cross "
            "(sch_PrimitivePin.modify). Only noConnected changes: the pin's "
            "current x/y are read from the parent's own pin list and repeated in "
            "the same modify so the host does not re-derive the position "
            "(V4.1.100 measured an off-page NC cross otherwise; restoring the "
            "flag restored the coordinate). The parent list must contain "
            "primitiveId, the pin's PinNumber must equal expectedPinNumber and, "
            "when given, its current NoConnected must equal expectedNoConnected — "
            "otherwise nothing is written. Success is a fresh parent-pin read "
            "equal to the request — both NoConnected and the coordinates; a "
            "non-boolean/unequal read-back or an x/y that moved is "
            "CONNECTOR_ERROR with applied:false and mismatched, because an NC "
            "cross on a re-derived pin is not the requested edit. x/y/net and "
            "every other property are not caller parameters and are refused by "
            "name. Added for the F1/STM32G431 rebuild's real NC crosses."
        ),
        params=(
            "pageUuid", "parentPrimitiveId", "primitiveId",
            "expectedPinNumber", "noConnected", "expectedNoConnected",
        ),
        returns=(
            "{pageUuid, parentPrimitiveId, primitiveId, pinNumber, before, "
            "requested, after, coordinatesBefore, coordinatesAfter, applied, "
            "mismatched, returned?, modifyError?, note?}"
        ),
        params_schema=(
            "pageUuid, parentPrimitiveId, primitiveId, expectedPinNumber and "
            "noConnected are required; expectedPinNumber is a string, noConnected "
            "a strict boolean; expectedNoConnected is optional and, when present, "
            "must be a strict boolean equal to the pin's pre-write value. The "
            "pin's current x/y are not parameters: they are read internally (a "
            "coordinate that cannot be read refuses the write before it) and "
            "repeated unchanged so the host keeps the pin in place. Unknown "
            "parameters are refused."
        ),
        risk="write",
    ),
    Action(
        name="lib.device.get",
        summary=(
            "Recon (read-only): one library device, dumped whole. Its "
            "association.symbol is the *library* symbol uuid that lib.symbol.get "
            "needs — the netlist's Symbol property is project-local and answers "
            "found:false there."
        ),
        params=("uuid", "libraryUuid"),
        returns="{uuid, libraryUuid, found, item, readErrors?}",
        params_schema="uuid: library device uuid (required); libraryUuid: optional",
        risk="read",
    ),
    Action(
        name="lib.device.search",
        summary=(
            "Read-only: library device keyword candidates, each dumped. A search "
            "item carries association.footprint.uuid, so pairing it with "
            "lib.footprint.get answers 'which hit is really 0402?' by measurement."
        ),
        params=("keyword", "limit"),
        returns="{keyword, returned, shown, items}",
        params_schema="keyword: search text; limit: max items to dump (default 8)",
        risk="read",
    ),
    Action(
        name="lib.footprint.get",
        summary=(
            "Read-only: one library footprint, dumped whole. Turns the netlist's "
            "footprint uuid back into the package name both sides can compare, "
            "and verifies a replacement part really is the package it claims."
        ),
        params=("uuid", "libraryUuid"),
        returns="{uuid, libraryUuid, found, name, item}",
        params_schema="uuid: library footprint uuid (required); libraryUuid: optional",
        risk="read",
    ),
    # --- 038Q1: the host's own reuse modules (CBB), reads only --------------
    Action(
        name="lib.cbb.search",
        summary=(
            "Read-only: one page of the host's native reuse modules (复用模块) by "
            "keyword; an empty query is the legal inventory entry point. Every hit "
            "is re-read through lib_Cbb.get and must come back with the same uuid "
            "and a matching libraryUuid — a non-array answer, an over-sized page, "
            "a malformed item or a missing get answer is CONNECTOR_ERROR, never an "
            "empty library. count is this page's size, not a library total. "
            "`libraryUuid: 'project'` is a SCOPE keyword, not a uuid (038Q16): in "
            "that scope lib_Cbb.get is not called at all (it refuses project-local "
            "blocks) and each hit is verified through lib_Symbol.get(uuid, "
            "'project') — same uuid, a name string, type===17, libraryType==='2' — "
            "then reported as libraryUuid:'project' with the host symbol's own "
            "libraryUuid as sourceLibraryUuid and libraryIdentitySource:"
            "'lib_Symbol.get(project)'. That source uuid is provenance and never "
            "replaces the caller's scope; every other library keeps lib_Cbb.get and "
            "its hard checks unchanged."
        ),
        params=("query", "libraryUuid", "limit", "page"),
        returns=(
            "{query, libraryUuid, limit, page, count, items, "
            "source: 'lib_Cbb.search', apiStatus: 'beta'}"
        ),
        params_schema=(
            "query: search text, default '' (empty inventories the library); "
            "libraryUuid: optional, omitted = the host's system library, 'project' = "
            "the open project's own library (read through lib_Symbol.get); "
            "limit: 1..100, default 20; page: >=1, default 1"
        ),
        risk="read",
    ),
    Action(
        name="lib.cbb.get",
        summary=(
            "Read-only: one native reuse module's identity and boards metadata. "
            "Never opens the module project. A uuid the host does not know answers "
            "found:false; a uuid that comes back as a different module, without a "
            "libraryUuid or without a boards array is CONNECTOR_ERROR."
        ),
        params=("uuid", "libraryUuid"),
        returns=(
            "{uuid, libraryUuid, found, cbb, source: 'lib_Cbb.get', apiStatus: 'beta'}"
        ),
        params_schema=(
            "uuid: reuse-module uuid (required); libraryUuid: optional, omitted = "
            "the host's system library"
        ),
        risk="read",
    ),
    # --- 038Q14: the archive half of the same reads -------------------------
    Action(
        name="lib.cbb.personal",
        summary=(
            "Read-only: the uuid of this workspace's personal library "
            "(lib_LibrariesList.getPersonalLibraryUuid, @public). An absent "
            "namespace or method is NOT_IMPLEMENTED; undefined/null is "
            "CONNECTOR_ERROR with detail.reason='personal-library-unresolved' — no "
            "uuid was resolved in this workspace/session, and the declaration only "
            "says a private deployment always answers undefined, which does not "
            "diagnose this call. An unresolved uuid is not evidence of an empty "
            "library; a blank or non-string answer is refused the same way."
        ),
        params=(),
        returns=(
            "{libraryUuid, source: 'lib_LibrariesList.getPersonalLibraryUuid', "
            "apiStatus: 'public'}"
        ),
        params_schema="none — the call takes no arguments, and any parameter is refused",
        risk="read",
    ),
    Action(
        name="lib.cbb.export",
        summary=(
            "Read-only: one native reuse module's own .epro2 container, as base64 and "
            "opaque. lib_Cbb.get is re-read FIRST with the caller's uuid and library, "
            "so the bytes belong to a module whose identity is verified by a second "
            "host answer; then sys_FileManager.getCbbFileByCbbUuid(uuid, libraryUuid, "
            "{fileName: <the name get returned>, fileType:'epro2'}) — the declaration "
            "documents that fileName as 复用模块名, so it is the module's own name "
            "passed verbatim and a module without a usable name is refused before the "
            "file call. Nothing is unpacked, no internal record format is guessed, and "
            "neither the library nor the project is written. A file that is missing, "
            "zero-byte, over 16 MiB, of unreadable size, or whose bytes disagree with "
            "its declared size is CONNECTOR_ERROR."
        ),
        params=("uuid", "libraryUuid"),
        returns=(
            "{uuid, libraryUuid, format: 'epro2', size, base64, "
            "source: 'sys_FileManager.getCbbFileByCbbUuid', apiStatus: 'beta'}"
        ),
        params_schema=(
            "uuid: reuse-module uuid (required); libraryUuid: the library the module "
            "must be in (required — the identity check is made against the library "
            "the caller names, so no system-library default is applied here)"
        ),
        risk="read",
    ),
    Action(
        name="lib.cbb.libraries",
        summary=(
            "Read-only: the workspace's other libraries as a list "
            "(lib_LibrariesList.getAllLibrariesList, @public), each item just "
            "{uuid, name}. The declaration states this list EXCLUDES the system, "
            "personal, project and favourite libraries — it is not a substitute for "
            "lib.cbb.personal — and this action neither writes nor registers a "
            "library. An empty array is a real reading (count 0); a non-array "
            "answer, an item without a non-blank uuid or a string name, a duplicated "
            "uuid or a throw is CONNECTOR_ERROR, never an empty list."
        ),
        params=(),
        returns=(
            "{items: [{uuid, name}], count, "
            "source: 'lib_LibrariesList.getAllLibrariesList', apiStatus: 'public'}"
        ),
        params_schema="none — the call takes no arguments, and any parameter is refused",
        risk="read",
    ),
    Action(
        name="sch.set_component_attribute",
        summary=(
            "Write schematic attributes on a placed component in ONE call, then "
            "read them back. modify()'s otherProperty REPLACES the whole map "
            "(measured: writing Value then Supplier Footprint kept only the "
            "second), so callers send attributes{} and the action merges first. "
            "`applied` means the read-back equals the target, never 'modify "
            "returned an object'."
        ),
        params=("primitiveId", "attributes", "key", "value", "pageUuid"),
        returns=(
            "{primitiveId, attributes, mergedKeys, applied, wrote, "
            "otherPropertyBefore, otherPropertyAfter, mismatched?, "
            "clobberedOtherKeys?, readBackBefore?, readBackAfter?}"
        ),
        params_schema=(
            "primitiveId: placed component id; attributes: {name: value} written "
            "in one call (preferred); key/value: single-pair shorthand; pageUuid"
        ),
        risk="write",
    ),
    Action(
        name="lib.symbol.get",
        summary=(
            "Recon (read-only): one library symbol, dumped whole. Answers whether "
            "the *library* path exposes pin geometry — the canvas path is measured "
            "dead (sch_PrimitivePin.getAll() empty, Symbol state {}, netlist has no "
            "coordinates), but nobody had looked here."
        ),
        params=("uuid", "libraryUuid"),
        returns="{uuid, libraryUuid, found, item, readErrors?}",
        params_schema="uuid: library symbol uuid (required); libraryUuid: optional",
        risk="read",
    ),
    Action(
        name="lib.symbol_file.get",
        summary=(
            "Read-only (038Q3): ONE library symbol's own file, by explicit uuid "
            "(sys_FileManager.getSymbolFileBySymbolUuid, @beta, gated 团队库 > 下载库). "
            "lib.symbol.get is measured to answer metadata only — no pins, no body "
            "geometry — so the container file is the remaining honest source for it. "
            "The bytes come back whole as base64 and are NOT unpacked: isZip reports "
            "the file header alone, and neither the request uuid nor the file name is "
            "treated as proof of identity inside the container. Whether a host actually "
            "exports the file is unmeasured on EDA 4.1.93; a throw is reported with the "
            "host's own words plus the documented gate, never as a diagnosed grant."
        ),
        params=("uuid", "libraryUuid", "fileType"),
        returns=(
            "{uuid, libraryUuid, fileType, source, apiStatus, encoding, name, mime, "
            "bytes, data, isZip}"
        ),
        params_schema=(
            "uuid: ONE library symbol uuid, a single non-empty string (an array is "
            "refused, not fanned out); libraryUuid: optional non-empty uuid — omitted "
            "is forwarded as undefined so the host's system library applies, and an "
            "empty string is refused rather than defaulted; fileType: REQUIRED, "
            "'elibz2' or 'elibz' (the declaration's optional default is not measured, "
            "so the caller states the container)"
        ),
        risk="read",
    ),
    Action(
        name="lib.footprint_file.get",
        summary=(
            "Read-only (038Q6): ONE library footprint's own file, by explicit uuid "
            "(sys_FileManager.getFootprintFileByFootprintUuid, @beta, gated 团队库 > 下载库). "
            "lib.footprint.get is measured to answer the package name and nothing about "
            "PAD geometry, so the container file is the next honest place to look. Measured "
            "present as a function with arity 3 on EDA 4.1.93, which is not the same as "
            "working: whether the host exports the file is unmeasured. The bytes come back "
            "whole as base64 and are NOT unpacked — isZip reports the file header alone, "
            "no manifest name, docType, member suffix or PAD number is guessed, and neither "
            "the request uuid nor the file name is proof of what the container holds. A "
            "throw is reported with the host's own words plus the documented gate, never as "
            "a diagnosed grant; no pad geometry, PAD 4, or electrical inference is claimed."
        ),
        params=("uuid", "libraryUuid", "fileType"),
        returns=(
            "{uuid, libraryUuid, fileType, source, apiStatus, encoding, name, mime, "
            "bytes, data, isZip}"
        ),
        params_schema=(
            "uuid: ONE library footprint uuid, a single non-empty string (an array is "
            "refused, not fanned out); libraryUuid: optional non-empty uuid — omitted "
            "is forwarded as undefined so the host's system library applies, and an "
            "empty string is refused rather than defaulted; fileType: REQUIRED, "
            "'elibz2' or 'elibz' (the declaration's optional default is not measured, "
            "so the caller states the container)"
        ),
        risk="read",
    ),
    Action(
        name="sch.netlist",
        summary=(
            "The editor's own netlist export (sch_ManufactureData.getNetlistFile) "
            "— the ground-truth connectivity for draw verification."
        ),
        params=("type",),
        returns="{type, source, size, text}",
        params_schema="type: ESYS_NetlistType value ('EasyEDA' | 'Protel2' | 'JLCEDA' | 'PADS' | …), default 'EasyEDA'",
        risk="read",
    ),
    Action(
        name="sch.geometry",
        summary=(
            "Full geometry of the open schematic page (wires with polylines, "
            "pins, net labels, components) — the readback fallback when the "
            "netlist export is unusable."
        ),
        params=("bboxIds",),
        returns=(
            "{components: [...], wires: [...], pins: [...], netlabels: [...], "
            "bboxes: {primitiveId: {minX,minY,maxX,maxY}}, meta: {...}}"
        ),
        params_schema="bboxIds: optional array of primitive ids to measure as well",
        risk="read",
    ),
    Action(
        name="sch.list_attributes",
        summary=(
            "Read-only: every ISCH_PrimitiveAttribute of a page, or of one owner "
            "primitive, field by field (sch_PrimitiveAttribute.getAll). Built for "
            "053P — a createNetLabel that answered undefined while two name texts "
            "appeared in the render can only be told apart from canvas decoration "
            "by reading the attribute namespace itself."
        ),
        params=("pageUuid", "parentPrimitiveId"),
        returns=(
            "{pageUuid, parentPrimitiveId, count, attributes: [{primitiveId, "
            "parentPrimitiveId, key, value, x, y, rotation, alignMode, fillColor, "
            "keyVisible, valueVisible}], readErrors}"
        ),
        params_schema=(
            "pageUuid: required, the page the attributes belong to (the focused "
            "page must match — PAGE_MISMATCH otherwise); parentPrimitiveId: "
            "optional non-empty id, forwarded as the one argument of "
            "getAll(parentPrimitiveId) — omitted means the bare getAll()"
        ),
        risk="read",
    ),
    Action(
        name="sch.move_attribute",
        summary=(
            "Move ONE existing attribute's text position (x/y/rotation/alignMode) or "
            "its ValueVisible flag, after re-reading the page's own attribute list "
            "and proving the id, its parent and its current key/value. Built for "
            "053Q: the 053P reader could see an attribute and not place it. 053U "
            "adds valueVisible (strict boolean) so a duplicated net name — a "
            "reversible Type-C pin that keeps its own NET — can be hidden without "
            "clearing the wire's net, deleting the ATTR or drawing across pins. "
            "Any identity mismatch, a missing ValueVisible read port, or a "
            "read-back that cannot confirm the requested fields, is an error "
            "naming the mismatched fields — never a silent success."
        ),
        params=(
            "pageUuid", "primitiveId", "parentPrimitiveId", "expectedKey",
            "expectedValue", "x", "y", "rotation", "alignMode", "valueVisible",
        ),
        returns=(
            "{pageUuid, primitiveId, parentPrimitiveId, key, value, before, "
            "requested, returned, after, applied, mismatched, readErrors?, "
            "modifyError?, readbackError?}"
        ),
        params_schema=(
            "pageUuid/primitiveId/parentPrimitiveId/expectedKey/expectedValue: "
            "required (expectedValue may be an empty string, but must be a string); "
            "x/y/rotation: finite numbers; alignMode: ESCH_PrimitiveTextAlignMode "
            "(1..9); valueVisible: strict boolean; at least one of the five. "
            "key/value/keyVisible/font fields are refused, not forwarded. A "
            "valueVisible request is refused before the write unless the host can "
            "read getState_ValueVisible back. applied is decided by a fresh "
            "sch_PrimitiveAttribute.get(primitiveId) read-back"
        ),
        risk="write",
    ),
    Action(
        name="pcb.geometry",
        summary=(
            "Read-only: the **measured** rendered bounding box of PCB primitives "
            "(`eda.pcb_Primitive.getPrimitivesBBox`, one call per id — the host "
            "answers a union box for a list). The PCB twin of `sch.geometry`'s "
            "`bboxIds` half: a board primitive's real extent is not in the file, "
            "so this is the only way to answer 「这块丝印压上焊盘了吗」 by "
            "measurement rather than by a font-width model."
        ),
        params=("bboxIds",),
        returns=(
            "{bboxes: {primitiveId: {minX,minY,maxX,maxY}}, "
            "meta: {available: {bboxes}, requested, measured, reasons?, unreadable?}}"
        ),
        params_schema=(
            "bboxIds: array of PCB primitive ids to measure (each gets its own "
            "call); an id the host cannot measure is named in meta.unreadable "
            "rather than silently dropped"
        ),
        risk="read",
    ),
    # --- 006: schematic write actions ---------------------------------------
    Action(
        name="sch.doc.new",
        summary="Create a blank schematic page in the current project.",
        params=("name", "confirm"),
        returns="{schematicUuid, pageUuid, focused}",
        risk="create",
    ),
    Action(
        name="sch.doc.save",
        summary=(
            "Save the project — required before the netlist export, which "
            "returns nothing for a never-saved project (measured)."
        ),
        params=(),
        returns="{saved: true}",
        risk="write",
    ),
    Action(
        name="sch.place_component",
        summary=(
            "Place a library device (resolved by LCSC part number, library "
            "uuid pair, or keyword search) on the current schematic page. "
            "Timeout-bounded and self-reporting: the first placement of a "
            "session can outrun its deadline and land anyway, so a miss reads "
            "the page back and says whether a part appeared."
        ),
        params=(
            "lcsc", "deviceUuid", "libraryUuid", "keyword", "x", "y",
            "rotation", "mirror", "designator", "pageUuid", "timeoutMs",
        ),
        returns="{uuid, device: {uuid, libraryUuid, name}, resolvedBy, elapsedMs}",
        params_schema="timeoutMs: override the 30 s placement deadline (200..60000, clamped)",
        risk="write",
    ),
    Action(
        name="sch.place_cbb",
        summary=(
            "Place one native reuse module (CBB / 复用模块) as a block instance on "
            "the focused schematic page (038Q15). The module is re-read through "
            "`lib_Cbb.get` and its name must equal `expectedName`; the focused "
            "project and page (`dmt_Project.getCurrentProjectInfo` / "
            "`dmt_SelectControl.getCurrentDocumentInfo`, `documentType === 1`) must "
            "equal `projectUuid`/`pageUuid` before and after the write. The source "
            "symbol is checked through `lib_Symbol.get` when the host can read it; "
            "an unreadable symbol is refused unless the caller passes "
            "`allowUnverifiedSourceSymbol: true`, and the answer then reports "
            "`symbolVerification.mode: 'unverified-source-symbol'`. The page's "
            "components are read completely first (unique ids, finite geometry) and "
            "again afterwards: exactly one new id, every old component's geometry "
            "unchanged, `block_symbol` type, the requested pose, the CBB/CBB-symbol "
            "identity, and `getAllPinsByPrimitiveId` as an array (an empty one is a "
            "real reading). Any failure after the host call answers "
            "`{partial: true, verified: false, primitiveId, state, problems}` — the "
            "evidence is kept, nothing is retried or rolled back."
        ),
        params=(
            "uuid", "libraryUuid", "expectedName", "symbolUuid", "projectUuid",
            "pageUuid", "x", "y", "rotation", "mirror",
            "allowUnverifiedSourceSymbol",
        ),
        returns=(
            "{uuid, libraryUuid, expectedName, symbolUuid, projectUuid, pageUuid, "
            "requested, symbolVerification, beforeCount, primitiveId, state, cbb, "
            "cbbSymbol, pins, preserved, problems, verified, partial, error?}"
        ),
        params_schema=(
            "uuid/libraryUuid/expectedName: the module identity to re-read; "
            "symbolUuid: the source CBB symbol; projectUuid/pageUuid: the only "
            "project and page this may write to (PAGE_MISMATCH otherwise, "
            "detail.guard says which); x/y: finite numbers; rotation: 0|90|180|270; "
            "mirror: boolean; allowUnverifiedSourceSymbol: boolean, true only when "
            "the source identity is backed by another host reading — an unreadable "
            "source is reported as unverified, never as verified"
        ),
        risk="write",
    ),
    Action(
        name="sch.place_project_cbb",
        summary=(
            "Place one project-*local* native CBB block — a module imported into "
            "the open project — on the focused schematic page (038Q16B). The "
            "schematic is proved first: `dmt_Schematic.getSchematicInfo(schematicUuid)` "
            "must answer the same uuid, `parentProjectUuid === projectUuid`, "
            "`name === expectedName`, `itemType === 'CBB Schematic'` and a "
            "`cbbSymbol` of `type === 17`; those graph fields are kept in the answer "
            "as the source identity. `expectedName` is then resolved through the "
            "038Q16A project scope of `lib.cbb.search`, and every candidate is "
            "re-read with `lib_Symbol.get(uuid, 'project')` — the host symbol's own "
            "name is the authority, not the search row — so exactly one local symbol "
            "must match and `symbolUuid` must be that local uuid (zero, several or a "
            "different uuid are refusals before anything is written). The focused "
            "project and page (`documentType === 1`) are checked before and after. "
            "The write is the ordinary project-symbol call "
            "`sch_PrimitiveComponent.create({libraryType: '2', libraryUuid: "
            "projectUuid, uuid: symbolUuid}, x, y, '', 0, false, true, true)` — "
            "rotation/mirror are fixed at 0/false in this action. The page is "
            "inventoried completely before (unique ids, finite geometry) and again "
            "after: exactly one new component, every old one unchanged, "
            "`block_symbol`, `getState_Symbol().uuid === symbolUuid`, the fixed "
            "pose, and `getAllPinsByPrimitiveId` as an array (empty is a real "
            "reading). Any failure after the host call answers "
            "`{partial: true, verified: false, primitiveId, state, problems}`; "
            "`lib_Cbb.get` with the project scope, `createCbbSymbol` and every "
            "library write are never reached."
        ),
        params=(
            "schematicUuid", "expectedName", "symbolUuid", "projectUuid", "pageUuid",
            "x", "y", "rotation", "mirror",
        ),
        returns=(
            "{schematicUuid, expectedName, symbolUuid, projectUuid, pageUuid, graph, "
            "resolution, requested, beforeCount, primitiveId, state, symbol, pins, "
            "preserved, problems, verified, partial, error?}"
        ),
        params_schema=(
            "schematicUuid: the CBB schematic document whose graph must match; "
            "expectedName: the block's display name, matched only against "
            "`lib_Symbol.get(uuid, 'project').name`; symbolUuid: the project-local "
            "symbol uuid the name must resolve to; projectUuid/pageUuid: the only "
            "project and page this may write to (PAGE_MISMATCH otherwise, "
            "detail.guard says which); x/y: finite numbers; rotation: fixed 0 "
            "(any other value is refused); mirror: fixed false (any other value is "
            "refused)"
        ),
        risk="write",
    ),
    Action(
        name="sch.place_wire",
        summary="Place a wire polyline, optionally naming its net.",
        params=("points", "net", "pageUuid"),
        returns="{uuid}",
        params_schema=(
            "points: [[x, y], …] (2+ points); net: optional net name carried by the wire; "
            "pageUuid: refuse to write unless the focused page matches"
        ),
        risk="write",
    ),
    Action(
        name="sch.place_netlabel",
        summary=(
            "Place a net label. Timeout-bounded and self-reporting: the call "
            "races an 8 s deadline and, when the host hangs (measured on "
            "3.2.186, reference issue #191), reads back whether the label "
            "landed anyway before failing — never retry blind."
        ),
        params=("x", "y", "net", "pageUuid", "timeoutMs"),
        returns="{uuid, outcome: 'ok', elapsedMs, landedAnyway}",
        params_schema=(
            "pageUuid: refuse to write unless the focused page matches; "
            "timeoutMs: override the 8 s deadline (200..30000, clamped)"
        ),
        risk="write",
    ),
    Action(
        name="sch.place_text",
        summary=(
            "Place a free text primitive next to a wire — the *decorative* "
            "signal-name fallback. `createNetLabel` (the only real net-label "
            "API) is documented 'ADD since EDA v4' and can never settle on the "
            "v3.2 host, so a signal name is drawn as text: visible to a reader, "
            "but NOT an electrical object. The response says `decorative: true`."
        ),
        params=("x", "y", "content", "rotation", "color", "fontSize", "pageUuid"),
        returns="{uuid, content, decorative: true}",
        risk="write",
    ),
    Action(
        name="sch.place_power",
        summary=(
            "Place a power / ground net flag (a real library component placed "
            "by the editor, named with the given net)."
        ),
        params=("kind", "net", "x", "y", "rotation", "mirror", "pageUuid"),
        returns="{uuid}",
        params_schema=(
            "kind: 'Power' | 'Ground' | 'AnalogGround' | 'ProtectGround'; "
            "pageUuid: refuse to write unless the focused page matches"
        ),
        risk="write",
    ),
    Action(
        name="sch.place_netport",
        summary=(
            "Place a net port (IN / OUT / BI) carrying a net name. The solver's "
            "LAST resort only: xianyuyijinban's rule bans I/O ports for signal naming — "
            "the draw flow names signals with label actions and never emits one."
        ),
        params=("direction", "net", "x", "y", "rotation", "mirror", "pageUuid"),
        returns="{uuid}",
        params_schema=(
            "direction: 'IN' | 'OUT' | 'BI'; "
            "pageUuid: refuse to write unless the focused page matches"
        ),
        risk="write",
    ),
    # --- 012: delete / move / rotate by id (the AI's basic edit verbs) -------
    Action(
        name="sch.delete_primitives",
        summary=(
            "Delete schematic primitives by id. The page's id index is built "
            "first (component / wire / text / pin — the classes the type "
            "package lets address by id; attribute primitives cannot be), so "
            "an id the page never held is reported, not guessed at. Honest "
            "partial result: deleted / notFound / failed."
        ),
        params=("pageUuid", "primitiveIds"),
        returns="{deleted: [id], notFound: [id], failed: [{id, reason}]}",
        params_schema="pageUuid: the guarded page; primitiveIds: list of primitive ids",
        risk="write",
    ),
    Action(
        name="pcb.delete_primitives",
        summary=(
            "Delete PCB primitives by id — component / line / via / pad / "
            "pour, guarded against the focused PCB. Honest partial result, "
            "same shape as sch.delete_primitives."
        ),
        params=("pageUuid", "primitiveIds"),
        returns="{deleted: [id], notFound: [id], failed: [{id, reason}]}",
        params_schema="pageUuid: the guarded PCB uuid; primitiveIds: list of primitive ids",
        risk="write",
    ),
    Action(
        name="sch.modify_primitive",
        summary=(
            "Move / rotate / mirror one schematic primitive by id — pose only. "
            "The class comes from the page's id index; the pose keys are "
            "filtered through what that class's modify actually accepts "
            "(a wire has no pose in the type package and is refused). "
            "Returns the before/after pose for verification."
        ),
        params=("pageUuid", "primitiveId", "x", "y", "rotation", "mirror"),
        returns="{before: {x, y, rotation, mirror}, after: {…}}",
        params_schema="at least one of x / y / rotation / mirror",
        risk="write",
    ),
    Action(
        name="pcb.modify_primitive",
        summary=(
            "Move / rotate one PCB primitive by id — pose only, same contract "
            "as sch.modify_primitive against the focused PCB."
        ),
        params=("pageUuid", "primitiveId", "x", "y", "rotation", "mirror"),
        returns="{before: {x, y, rotation, mirror}, after: {…}}",
        params_schema="at least one of x / y / rotation / mirror",
        risk="write",
    ),
    # --- R1-1: put a footprint on a board ------------------------------------
    Action(
        name="pcb.place_component",
        summary=(
            "Place a library device's footprint on the focused PCB (R1-1) — the "
            "PCB twin of sch.place_component, same resolution ladder (uuid pair / "
            "LCSC / keyword). `pageUuid` is required and must be the focused PCB. "
            "Timeout-bounded; a miss diffs the board's component ids before and "
            "after the call, so 'did anything land' is read, not guessed."
        ),
        params=(
            "pageUuid", "lcsc", "deviceUuid", "libraryUuid", "keyword", "x", "y",
            "rotation", "layer", "timeoutMs",
        ),
        returns=(
            "{uuid, device: {uuid, libraryUuid, name}, resolvedBy, "
            "requested: {x, y, rotation, layer}, "
            "placed: {x, y, rotation, layer, designator}, appeared, elapsedMs}"
        ),
        params_schema=(
            "pageUuid: required, the focused PCB's uuid (doc.list); layer: 'top' "
            "(default) | 'bottom'; x/y in canvas units (mil); timeoutMs: override "
            "the 30 s placement deadline (200..60000, clamped)"
        ),
        risk="write",
    ),
    # --- 012 §五: multi-project awareness ------------------------------------
    Action(
        name="doc.focus",
        summary=(
            "Put an already-open document on top: resolve a tab id from a "
            "page uuid (or take a full tabId) in the split-screen tree and "
            "activate it. Refuses (NOT_FOUND) when nothing is open for that "
            "uuid — doc.open is the one that opens tabs."
        ),
        params=("pageUuid", "tabId"),
        returns="{activated, tabId, title, documentType}",
        params_schema="pageUuid or tabId, one required",
        risk="write",
        # 537A3: navigation only — it decides which page the next placement
        # lands on, but writes nothing into the project. ``risk`` stays
        # ``write`` so 537A2's read-only gate keeps refusing it.
        design_write=False,
    ),
    Action(
        name="doc.delete_page",
        summary=(
            "Delete a schematic page by uuid — the cleanup half of the "
            "scratch-page flow. The uuid must be one the project lists "
            "(NOT_FOUND otherwise); the host refuses to delete a schematic's "
            "last page."
        ),
        params=("pageUuid",),
        returns="{deleted, pageUuid, name}",
        params_schema="pageUuid: the page to delete",
        risk="write",
    ),
    # --- 012 §六/§七: the fab bundle and part recommendations ----------------
    Action(
        name="export.fab",
        summary=(
            "The focused PCB's fab bundle in one call (012 §六): Gerber (zip) + "
            "pick-and-place + BOM, plus a manifest carrying the file list, the "
            "parameters used, the project/pcb identity and the timestamp. The "
            "connector CANNOT write to a path — no declared API takes a directory "
            "(SYS_FileSystem.saveFile(fileData, fileName?) has none) — so the three "
            "files come back as base64 and the caller writes them into `outDir`; "
            "`boardwise bridge export-fab` is that caller. Vendor presets: `generic` "
            "only, until a 捷配 sample BOM arrives. A file the host refuses, returns "
            "empty or hangs on is reported per file in `failed` (`partial: true`) "
            "while the others still come back. Measured on 3.2.186 (2026-09-21): the "
            "15 BOM column names come back verbatim — the two counting columns reach "
            "the host as `statistics` and the other 13 as `property`, two disjoint "
            "lists whose union it checks per column, because naming a column in both "
            "is what doubled the header (17 columns for a 15-column preset) and "
            "dropping `statistics` makes it return no BOM file at all; the BOM's "
            "`filterOptions` are "
            "*exclusion* rules — `includeValue` is the value that leaves a row out, "
            "not the one it keeps — and the host names the BOM file itself "
            "(`fileName + '.' + fileType`) while gerber/P&P echo the name they are "
            "handed."
        ),
        params=("pcbUuid", "outDir", "vendor", "gerber", "bom", "bomTemplate", "timeoutMs"),
        returns=(
            "{vendor, project, pcb, outDir, generatedAt, encoding: 'base64', "
            "files: [{role, name, mime, bytes, data}], manifest, failed, partial, note}"
        ),
        params_schema=(
            "pcbUuid: the board to export — default is the focused PCB, and a pcbUuid "
            "that is not the focused one is PAGE_MISMATCH (the manufacture APIs export "
            "the board in front); outDir: the directory the CALLER writes into "
            "(required; recorded in the manifest); vendor: 'generic' (default); gerber: "
            "override object limited to fileName/colorSilkscreen/unit/digitalFormat/"
            "other/layers/objects; bom: override object limited to filterOptions — "
            "`[{property, includeValue}]` where the rule leaves a row **out** when the "
            "part's property matches `includeValue` (so the preset sends 'Add into "
            "BOM': 'no'), and `null` means 'send none — keep the host's own default "
            "rules'; bomTemplate: a saved BOM template name; timeoutMs: "
            "per-file deadline (200..600000, default 60000)"
        ),
        risk="read",
    ),
    Action(
        name="lib.recommend",
        summary=(
            "READ-ONLY part recommendations for a placed part or a bare query "
            "(012 §七). The search descends: the LCSC code as `supplierId` (the one "
            "properties key 3.2.186 indexes, measured 2026-09-21) → "
            "searchByProperties(value + footprintName) → search(keyword); "
            "each rung reports its own hit count (5 per page, 3 pages max) and the "
            "rungs a hit made unnecessary are reported as not called. JLCPCB Basic "
            "parts sort first. No stock and no price — the type package's search item "
            "carries neither — so the answer labels them `stock/price: 以商城实时为准`. "
            "`probes` (≤10) replaces the descent with raw `searchByProperties` calls — a "
            "read-only channel for measuring that method on a live host, see "
            "`params_schema`. Nothing is placed: placement stays the oracle's decision."
        ),
        params=("query", "pageUuid", "ref", "topN", "allLayers", "timeoutMs", "probes"),
        returns=(
            "{source, query, ref, component, target, layers: [{layer, api, called, args, "
            "hitCount, pagesFetched, reason?, error?}], returned, shown, candidates: "
            "[{name, lcsc, mpn, footprintName, partClass, datasheet, deviceUuid, "
            "libraryUuid, symbolUuid, footprintUuid, layer}], 'stock/price', readOnly, placed}; "
            "with probes: {source: 'probes', probes: [{args, called, hitCount, pageSize, "
            "firstKeys, error?}], probesOnly: true, layers: [], candidates: [], returned: 0, "
            "shown: 0, …}"
        ),
        params_schema=(
            "query: free text (an MPN, a value, or a C-number) — or pageUuid+ref for a "
            "part already on the page (the ref path is focus-guarded: the designator is "
            "resolved in the focused page's component list); a bare MPN reaches the "
            "keyword rung only: the exact rung is the LCSC code under `supplierId`, "
            "because that is the one properties key 3.2.186 indexes (measured "
            "2026-09-21); topN: how many candidates "
            "(1..20, default 5); allLayers: run every rung instead of stopping at the "
            "first that hits; timeoutMs: per-page deadline for one library search "
            "(200..120000, default 20000) — a hung page is reported as that rung's "
            "error and the descent continues; probes: at most 10 raw "
            "{properties, libraryUuid?, classification?, symbolType?, itemsOfPage?, page?} "
            "entries — each is one `lib_Device.searchByProperties` call sent with exactly "
            "the arguments given (an argument left out is not sent, so `arguments.length` "
            "is the caller's), the ladder is not walked at all, and each entry is reported "
            "as {args, called, hitCount, pageSize, firstKeys, error?} with "
            "`probesOnly: true` in the answer"
        ),
        risk="read",
    ),
    # --- 012 §八: a review pass drawn back onto the canvas -------------------
    Action(
        name="review.mark",
        summary=(
            "Draw a `boardwise review` pass on the focused schematic page as "
            "indicator markers, and jump to one finding (012 §八). The marker API "
            "takes SHAPES, not text, so each mark's ref is resolved to its "
            "component's coordinates first (the same component dump `sch.geometry` "
            "returns) and the rule id / severity / one-line summary travel in the "
            "result instead: `marked[k-1]` is marker k. View-only: markers are an "
            "overlay, no primitive is created, moved or modified."
        ),
        params=("pageUuid", "marks", "clear", "focus", "color", "zoom", "markers"),
        returns=(
            "{mode: 'markers'|'list', cleared, page: {components, designators, "
            "withoutPosition, active}, count, marked: [{position, marker, ref, "
            "designator, ruleId, severity, text, primitiveId, x, y}], unresolved: "
            "[{position, ref, ruleId, severity, text, reason}], markers: {attempted, "
            "accepted, reason?}, focused?: {position, ref, zoomed, reason?}, readOnly, "
            "note, notes?}"
        ),
        params_schema=(
            "pageUuid: optional — the schematic page the findings are about; a "
            "different focused page is PAGE_MISMATCH (without it, the page is not "
            "verified and the result says so); marks: [{ref, ruleId, severity, text}] "
            "in the caller's own finding order (position k is the k-th entry, which is "
            "what `focus` counts) — a ref that is not on the page is reported in "
            "`unresolved` while the rest are still marked; clear: true calls "
            "removeIndicatorMarkers instead (and ignores marks) — it has **no page "
            "guard** (it clears whatever canvas is in front, which may belong to "
            "another project), and with no active document it answers cleared: true "
            "with the note 'no active canvas — nothing to remove' instead of "
            "reporting the host's refusal of a call that had nothing to act on; "
            "focus: 1-based "
            "position to zoom to, via zoomToRegion; color: '#RRGGBB' or "
            "{r,g,b,alpha}; zoom: zoom the canvas to all markers (ignored when focus "
            "is given); markers: false returns the jump list (ref + coordinates) "
            "without drawing — the explicit form of the degradation that also "
            "happens when generateIndicatorMarkers is missing or refuses"
        ),
        risk="read",
    ),
    # --- 006c: document management (probe / open / create / rename) ----------
    Action(
        name="doc.list",
        summary=(
            "READ-ONLY: every document in the open project — schematic pages and "
            "PCBs — with uuid / name / type / which one is active. The harness has "
            "been acting on 'whatever page is focused'; this makes the project's "
            "document set something a caller can see instead of assume, and is "
            "how a uuid for doc.open / doc.rename is obtained."
        ),
        params=(),
        returns=(
            "{documents: [{uuid, name, type, active}], active: {uuid, type, tabId}, "
            "schematicPages, pcbs, count, notes?}"
        ),
        risk="read",
    ),
    Action(
        name="doc.open",
        summary=(
            "Open a document by uuid and put the input focus in it, so subsequent "
            "actions operate on the page the caller chose rather than on whichever "
            "tab happened to be in front. Changes the editor's active document, "
            "never the project's content."
        ),
        params=("uuid",),
        returns="{uuid, tabId, opened, activated, document: {uuid, name, type, active}}",
        params_schema="uuid: schematic page / schematic / PCB uuid (from doc.list)",
        risk="write",
        # 537A3: opening a document moves the editor's focus; it renames,
        # creates and deletes nothing. ``risk`` stays ``write`` for 537A2.
        design_write=False,
    ),
    Action(
        name="pcb.doc.new",
        summary=(
            "CREATE a PCB in the current project (mirrors sch.doc.new). Produces a "
            "new document, so the daemon refuses it without params.confirm: true "
            "(CONFIRMATION_REQUIRED)."
        ),
        params=("boardName", "confirm"),
        returns="{pcbUuid, focused}",
        params_schema="boardName: optional parent board name; confirm: must be true",
        risk="create",
    ),
    Action(
        name="doc.rename",
        summary=(
            "Rename a schematic page, a schematic, or a PCB by uuid. The editor "
            "exposes three separate calls (modifySchematicPageName / "
            "modifySchematicName / modifyPcbName) and the action dispatches on the "
            "requested type — a rename is a write to existing content, not a new "
            "document. A rename that did not happen is an error, not an answer: the "
            "success shape is returned only when the editor's own listing confirms "
            "the new name. `CONNECTOR_ERROR` when the host claimed success and "
            "stored nothing, `NOT_SUPPORTED` when the host's call answered falsy "
            "and nothing changed (measured on EDA 3.2.186 for schematic pages, 179)."
        ),
        params=("uuid", "name", "type"),
        returns="{uuid, name, type, renamed, confirmed, notes?}",
        params_schema=(
            "uuid: document uuid; name: the new name; type: 'page'|'schematic'|'pcb' "
            "(optional — resolved through doc.list when omitted)"
        ),
        risk="write",
    ),
)

ACTION_NAMES: frozenset[str] = frozenset(action.name for action in ACTIONS)
_ACTIONS_BY_NAME: dict[str, Action] = {action.name: action for action in ACTIONS}


class ErrorCodes:
    """Machine-readable error codes carried in ``error.code``."""

    #: No ``hello``, a bad or missing token.
    UNAUTHENTICATED = "UNAUTHENTICATED"
    #: First frame was not ``hello``, or ``hello`` arrived twice.
    PROTOCOL_VIOLATION = "PROTOCOL_VIOLATION"
    #: Connector and daemon disagree on the protocol major version.
    VERSION_MISMATCH = "VERSION_MISMATCH"
    #: Malformed JSON, or a frame missing a required field.
    BAD_REQUEST = "BAD_REQUEST"
    #: Action is not in :data:`ACTIONS`.
    UNKNOWN_ACTION = "UNKNOWN_ACTION"
    #: Action is known but this side does not implement it yet.
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    #: A ``create`` action arrived without ``params.confirm is True``. Raised by
    #: the daemon, before anything is forwarded, so the editor never sees it.
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    #: A **design write** was routed to a window whose project the daemon may not
    #: write into (537A3). Raised after routing and before the frame is
    #: forwarded, so the editor never sees the call — the whole point is that the
    #: refusal does not depend on a caller (or a model) remembering to stay out
    #: of real projects. The daemon allows ``test`` / ``test2`` by default; an
    #: operator can name other projects in ``BOARDWISE_WRITE_PROJECTS``, where
    #: ``*`` is the legacy full-allow switch and an explicitly empty value denies
    #: everything. Reads, navigation (``doc.open`` / ``doc.focus``) and
    #: ``sys.self_update`` are outside this gate: they are not design writes.
    WRITE_PROJECT_FORBIDDEN = "WRITE_PROJECT_FORBIDDEN"
    #: The action needs the editor but no connector is connected.
    NO_CONNECTOR = "NO_CONNECTOR"
    #: A ``targetProject`` hint that no connected window has open (023). Raised
    #: by the daemon, before anything is forwarded: the message lists the windows
    #: that *are* online, because the caller's next move is to name one of them.
    PROJECT_NOT_CONNECTED = "PROJECT_NOT_CONNECTED"
    #: A ``targetProject`` hint that more than one connected window matches —
    #: the same project open twice, or a name and a uuid that are not unique.
    #: Honest rather than clever: the daemon does not pick one, because a write
    #: sent to the wrong window is the failure mode this whole routing exists to
    #: prevent. The message lists the candidates (023).
    PROJECT_AMBIGUOUS = "PROJECT_AMBIGUOUS"
    #: A ``targetInstance`` hint that no connected window answers to — neither as
    #: the hub key it registered under nor as the instance id it claimed. Raised
    #: by the daemon, before anything is forwarded, and the message lists the
    #: windows that *are* online, exactly like ``PROJECT_NOT_CONNECTED``: the
    #: caller named a window and the useful thing to say next is which windows
    #: exist. Its own code rather than a reuse of ``PROJECT_NOT_CONNECTED``
    #: because the hint was a different kind of name, and a caller that mistyped
    #: an instance id should be told *that*, not that a project is not open.
    #:
    #: **Superseded by ``INSTANCE_STALE`` (185), and kept on purpose.** The
    #: daemon no longer raises it: an instance hint that resolves to nothing live
    #: is now reported under the name that says what the caller most likely did
    #: (kept a window id across a reconnect). It stays in the vocabulary for the
    #: same reason ``CONNECTOR_ALREADY_ACTIVE`` below does — a connector or CLI
    #: build in the field switches on the string, and a name that vanished from
    #: the shared vocabulary would leave its handling referencing nothing. A build
    #: that still switches on it has a branch that no longer fires, and the two
    #: codes carry the same listing and the same explanation.
    WINDOW_NOT_CONNECTED = "WINDOW_NOT_CONNECTED"
    #: A ``targetInstance`` hint that names no **live** window, where the useful
    #: thing to say is not "wrong id" but "**this id is stale**" (185 §C, 岳's
    #: 2026-10-15 feedback P5). An editor window's instance id is minted by the
    #: connector at ``hello`` time: restart the editor, or reload the page, and the
    #: window comes back under a *new* id — so an id copied out of an earlier
    #: ``bridge status`` (or out of a report) names nothing, and a caller that
    #: mistook that for "the call worked and returned nothing" loses the run.
    #:
    #: Raised by the daemon, before anything is forwarded, with the **same**
    #: listing ``WINDOW_NOT_CONNECTED`` uses and the same sentence about the id
    #: possibly being stale. The daemon cannot tell 「a window that was here and
    #: has gone」 from 「an id it has never seen」: a window is dropped from the hub
    #: when its socket ends (:meth:`WindowHub.unregister`), and nothing keeps a
    #: per-instance history across that — an id from a previous daemon run is
    #: indistinguishable from a typo. Both are therefore reported under this one
    #: code, whose message says the id may be stale, never that the caller made a
    #: mistake.
    INSTANCE_STALE = "INSTANCE_STALE"
    #: Several windows are connected and the request named none (023). Not an
    #: error in the "something is broken" sense — it is the daemon saying it will
    #: not guess which window the caller meant.
    WINDOW_UNSPECIFIED = "WINDOW_UNSPECIFIED"
    #: A connector arrived while another editor instance already held the
    #: bridge, so it was refused and its socket closed (018 §A).
    #:
    #: **Retired by 023, and kept on purpose.** The single-active guard is gone:
    #: every authenticated connector is now registered in the hub, so this daemon
    #: never sends this code. It stays in the vocabulary because the code is read
    #: by connector builds in the field, and a name that vanished from the shared
    #: vocabulary would leave their handling of it referencing nothing. Nothing
    #: in this package raises it; a connector that still switches on it simply
    #: has a branch that no longer fires.
    CONNECTOR_ALREADY_ACTIVE = "CONNECTOR_ALREADY_ACTIVE"
    #: The connector raised / returned an error.
    CONNECTOR_ERROR = "CONNECTOR_ERROR"
    #: The connector did not answer in time.
    TIMEOUT = "TIMEOUT"
    #: The answer never arrived, whoever was waiting for it. Raised by the
    #: **client** when the daemon connection dies, and by the **daemon** when the
    #: window it was waiting on goes away while the call is in flight (#43) — in
    #: both cases there is nobody left to answer. It exists as its own code
    #: because "the transport died" and "the action failed" are not the same fact
    #: — a write whose answer never came may still have landed in the editor, and
    #: a caller that cannot tell them apart will report a half-drawn page as
    #: untouched (M0-P0d follow-up, 2026-09-18).
    DISCONNECTED = "DISCONNECTED"
    #: Anything else; ``error.message`` carries the text.
    INTERNAL = "INTERNAL"
    #: The host's own call cannot do what was asked on this build, and said so by
    #: answering rather than throwing (179). Raised by the connector when
    #: ``doc.rename`` was accepted, answered falsy and changed nothing — the case
    #: that used to come back as a successful ``{renamed: false}``, where a caller
    #: reading only the exit status saw a rename that never happened.
    NOT_SUPPORTED = "NOT_SUPPORTED"
    #: The caller named a document that is not the editor's active one, and the
    #: requested read cannot address it (179). The host's
    #: ``sys_FileManager.getDocumentSource()`` takes no arguments (measured arity
    #: 0 on EDA 3.2.186), so it can only read the active document: a ``uuid``
    #: naming anything else is refused instead of answered with the wrong
    #: document's source. The message names the active document and the
    #: ``doc.open`` that would make the target readable.
    DOC_NOT_ACTIVE = "DOC_NOT_ACTIVE"


class BridgeError(Exception):
    """An error that carries a wire-level code."""

    def __init__(self, code: str, message: str, detail: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.detail is not None:
            error["detail"] = self.detail
        return error


# --------------------------------------------------------------------------
# frame building / parsing
# --------------------------------------------------------------------------

_id_counter = 0


def new_id(prefix: str = "req") -> str:
    """Return a short unique correlation id.

    Monotonic counter plus a random suffix: unique within a process and
    unguessable enough that a stray late response cannot be mistaken for the
    current one.
    """
    global _id_counter
    _id_counter += 1
    return f"{prefix}-{_id_counter:06d}-{_random_suffix()}"


def _random_suffix() -> str:
    import secrets

    return secrets.token_hex(3)


def request_frame(
    action: str,
    params: dict[str, Any] | None = None,
    *,
    id: str | None = None,
    target_project: str = "",
    target_instance: str = "",
) -> str:
    """Serialise a request frame.

    ``target_project`` (023) names the project the caller wants to be answered
    by and rides **top level**, not in ``params``: it is an instruction to the
    daemon about *which window*, not something the connector is being asked to
    do, and keeping it out of ``params`` means it can never be forwarded into an
    action that has no idea what a project hint is. Empty means "no hint" and
    the key is omitted entirely, so a frame without a hint is the pre-023 frame.

    ``target_instance`` is the same instruction by instance id — the window's own
    name for itself, which survives a daemon that knows no projects at all (the
    editor restarted and every context read came back null). Both keys may ride
    one frame and the daemon prefers the instance; this function does not choose,
    because sending everything the caller said is the only version of this that
    cannot lose a hint.
    """
    frame: dict[str, Any] = {"id": id or new_id(), "action": action}
    if params:
        frame["params"] = params
    hint = str(target_project or "").strip()
    if hint:
        frame["targetProject"] = hint
    instance = str(target_instance or "").strip()
    if instance:
        frame["targetInstance"] = instance
    return json.dumps(frame, ensure_ascii=False)


def response_frame(id: str, data: Any = None, *, context: dict[str, Any] | None = None) -> str:
    """Serialise a successful response frame.

    ``context`` (023) is the answering window's live identity, a **sibling of**
    ``data`` rather than part of it: an action's result shape is the connector's
    contract and must not grow a field that means "which window this was". Only
    non-empty keys are written, so a window that could read nothing sends a
    response that looks exactly like a pre-023 one.
    """
    frame: dict[str, Any] = {"id": id, "ok": True, "data": data}
    if context:
        frame["context"] = context
    return json.dumps(frame, ensure_ascii=False)


def error_frame(
    id: str | None,
    error: BridgeError | dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> str:
    """Serialise a failed response frame.

    ``context`` (023) is the same window context :func:`response_frame` carries,
    on the failure path: a write that came back refused is exactly when the
    caller most needs to know *which* window refused it, and it is the same
    top-level sibling of the payload as on a success.
    """
    payload = error.as_dict() if isinstance(error, BridgeError) else error
    frame: dict[str, Any] = {"id": id, "ok": False, "error": payload}
    if context:
        frame["context"] = context
    return json.dumps(frame, ensure_ascii=False)


def banner_frame() -> str:
    """Serialise the event the daemon sends the moment a socket opens.

    This is the fix for the handshake deadlock found on real hardware (task
    004b). The connector used to send ``hello`` from the editor's *connect
    callback*, and when that callback did not fire the connector stayed silent
    while the daemon waited — nothing was ever sent in either direction.
    Sending a frame from the daemon first makes the handshake **message
    driven**: any inbound frame proves the socket is up end to end, and the
    connector answers it with ``hello``.

    Carries no secret: it arrives before authentication, so it may only say
    what is already public about the daemon. ``expect`` states the next move
    explicitly rather than leaving the client to infer it.
    """
    return json.dumps(
        {
            "event": EVENT_BANNER,
            "data": {
                "server": "boardwise",
                "protocol": PROTOCOL_VERSION,
                "expect": "hello",
            },
        },
        ensure_ascii=False,
    )


def decode_frame(raw: str | bytes) -> dict[str, Any]:
    """Parse one frame, raising :class:`BridgeError` on anything unusable.

    Validated here: JSON parses, the top level is an object, ``action`` is a
    non-empty string on requests. ``id`` is *not* required — the caller may
    still need to answer "I could not even read your id".
    """
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BridgeError(ErrorCodes.BAD_REQUEST, "frame is not UTF-8") from exc
    try:
        frame = json.loads(raw)
    except ValueError as exc:
        raise BridgeError(ErrorCodes.BAD_REQUEST, f"frame is not JSON: {exc}") from exc
    if not isinstance(frame, dict):
        raise BridgeError(ErrorCodes.BAD_REQUEST, "frame must be a JSON object")
    if "action" in frame and not (isinstance(frame["action"], str) and frame["action"]):
        raise BridgeError(ErrorCodes.BAD_REQUEST, "frame.action must be a non-empty string")
    return frame


def frame_kind(frame: dict[str, Any]) -> str:
    """Classify a decoded frame: ``"response"`` | ``"event"`` | ``"request"``.

    A frame is classified by the strongest key it carries, so a frame that
    somehow holds two of them behaves predictably instead of ambiguously. Both
    clients use this to step over the banner while waiting for an answer, and
    the tests use it to say what they expect on the wire.
    """
    if "ok" in frame:
        return "response"
    if "event" in frame:
        return "event"
    return "request"


def describe_actions(actions: Iterable[Action] = ACTIONS) -> str:
    """Render the action catalogue for ``--help`` / docs."""
    lines = [f"{'action':22} {'owner':10} {'risk':7} {'params':28} summary"]
    for action in actions:
        params = ",".join(action.params) or "-"
        lines.append(
            f"{action.name:22} {action.owner:10} {action.risk:7} {params:28} {action.summary}"
        )
    return "\n".join(lines)


def action_spec(name: str) -> Action | None:
    return _ACTIONS_BY_NAME.get(name)


def timeout_for(action: str) -> float:
    """Per-action timeout: image work and placements render; the rest just reads."""
    # Image work is slow: a canvas capture and a document render both wait on
    # the editor's renderer, so they get the longer budget.
    if action in ("export.screenshot", "export.render"):
        return SCREENSHOT_TIMEOUT
    # A placement resolves the library on first use; the connector bounds the
    # call itself (30 s default) and reads back on a miss, so the daemon's
    # budget must outlast that readback for its answer to reach the caller.
    if action in (
        "sch.place_component",
        "pcb.place_component",
        "sch.place_cbb",
        "sch.place_project_cbb",
    ):
        return PLACEMENT_TIMEOUT
    # 012 measured 2026-09-21: a schematic delete costs ~3.7 s per primitive
    # (the editor re-solves the page each time), so the 17-part cleanup ran
    # past the 30 s default and the CLI hung up mid-batch. The action is
    # per-id honest and resumable, but a caller that has to split its own
    # batches to fit a timeout is a caller working around the daemon. 150 s
    # covers ~40 primitives, the largest sane single cleanup.
    if action in ("sch.delete_primitives", "pcb.delete_primitives"):
        return DELETE_TIMEOUT
    # Three manufacture exports in one call, each bounded at 60 s by the
    # connector — the daemon has to outlast all three so a per-file miss
    # ("gerber timed out, BOM still landed") reaches the caller as an answer.
    if action == "export.fab":
        return FAB_TIMEOUT
    # Up to nine library searches (3 rungs × 3 pages) behind one action.
    if action == "lib.recommend":
        return RECOMMEND_TIMEOUT
    return ACTION_TIMEOUT


@dataclass
class Connection:
    """Bookkeeping the daemon keeps for one socket. Not wire-visible."""

    role: str = ""
    client: str = ""
    protocol: str = ""
    #: The connector's own build version, announced in `hello`. Empty for a CLI
    #: connection and for a connector built before 0.4.1 — see
    #: :func:`boardwise.bridge.daemon.client_with_version`, which renders that
    #: absence as "(version unknown)" instead of hiding it.
    connector_version: str = ""
    #: The *instance* this socket claims to be (018 §A), read from the `hello`
    #: params — declared here rather than set on the object by the daemon, which
    #: is how it used to travel and made "which fields exist?" a question about
    #: the caller. ``instance_id_source`` says where the id came from: ``hello``
    #: when the connector named itself, ``connection`` when the daemon invented
    #: one for a build that predates the field.
    instance_id: str = ""
    instance_id_source: str = ""
    #: The hub key this socket registered under (023). Equal to
    #: ``instance_id`` except when two live sockets claim the same id, where the
    #: second gets a suffixed key. Set by the daemon at registration; empty on a
    #: CLI connection.
    window_key: str = ""
    #: The editor *window's* project, announced in `hello` (021 §2.3) and then
    #: **kept fresh** from every response frame's ``context`` (023). Empty for a
    #: CLI connection, for a connector build that predates the fields, and for a
    #: window that could not read its project — the three cases are deliberately
    #: not told apart here, because the honest reading of all three is "this
    #: window named no project", and a guessed name is worse than none.
    project_name: str = ""
    project_uuid: str = ""
    #: The document in front of that window, and its domain (`sch` / `pcb`), from
    #: the same response ``context`` (023). Reachable only from a response: the
    #: handshake happens before any action has run, so a fresh connection knows
    #: no page until the connector answers something.
    page_uuid: str = ""
    page_type: str = ""
    authenticated: bool = False
    #: Frames received after handshake, for the audit log.
    seen_actions: list[str] = field(default_factory=list)


def merge_context(target: Any, context: Any) -> tuple[str, ...]:
    """Fold a response frame's ``context`` into a connection's bookkeeping.

    Returns the attribute names that **changed**, in :data:`CONTEXT_KEYS` order —
    empty when nothing did, which is also what an old connector (no ``context``
    at all) and a context full of unreadable keys produce.

    Three rules, all of them about not inventing facts:

    - **Only non-empty strings are merged.** A key the connector could not read
      is omitted from its frame, and the merge treats ``None``, ``""`` and a
      non-string the same as absent: they leave the known value alone. A window
      that has just lost its active document must not have its project erased by
      a null — the project is still open.
    - **Unknown keys are ignored**, not stored: the frame is written by a
      connector we did not build, and letting it write arbitrary attributes onto
      daemon-side bookkeeping is a privilege nothing needs.
    - **Values are kept as sent** (whitespace-stripped), never translated or
      validated against a vocabulary. A ``pageType`` this daemon has never heard
      of is still the editor's own answer.

    Duck-typed rather than typed to :class:`Connection`: the daemon's live
    registry entry carries the same four attributes, and the routing decision has
    to read the *registry's* copy. One merge implementation for both, so the two
    cannot drift.
    """
    if not isinstance(context, dict):
        return ()
    changed: list[str] = []
    for key in CONTEXT_KEYS:
        value = context.get(key)
        if not isinstance(value, str):
            continue
        value = value.strip()
        if not value:
            continue
        attribute = _CONTEXT_ATTRS[key]
        if getattr(target, attribute, "") != value:
            setattr(target, attribute, value)
            changed.append(attribute)
    return tuple(changed)


def context_of(target: Any) -> dict[str, str]:
    """One connection's current context, wire-shaped; empty keys are omitted.

    The inverse of :func:`merge_context`, and the reason both live here: what the
    daemon hands back to the caller on a relayed response has to be spelled the
    same way the connector spells it, or a reader would have to know which side
    of the wire it is looking at.
    """
    payload: dict[str, str] = {}
    for key in CONTEXT_KEYS:
        value = str(getattr(target, _CONTEXT_ATTRS[key], "") or "")
        if value:
            payload[key] = value
    return payload
