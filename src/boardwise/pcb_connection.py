"""Assembly-owned adapter for ``boardwise pcb connection`` (task 559, batch B2).

The judgement lives in :mod:`boardwise.core.connection` (batch B1), which is a
pure function over one ``pcb.connection_probe`` response. This module owns only
what that function cannot answer by itself — **which window** was asked, **which
build** answered, and **how the answer leaves the process**:

* it reads the version pair first (``sys.probe``) so the payload can say which
  host and which connector build produced this evidence. A version that could not
  be read is ``None``, named in ``versions.missing`` and explained in
  ``versions.error``; it is **never** a fabricated string, never a silent ``null``
  a reader could mistake for "no such field", and it never changes the verdict,
  because the editor's build number is not part of the connectivity question;
* it calls ``pcb.connection_probe`` with exactly the two ``REF.PAD`` ends and
  nothing else. The probe action is closed and refuses unknown keys, so this
  adapter has no second entry point to widen it with. The probe is **direct
  only**: it reports each end's ``getConnectedPrimitives(false)`` answer, never a
  ``getEntireTrack`` id set (559B measured those sets to span other,
  offline-disconnected copper components);
* it projects the response through :func:`boardwise.core.connection.project_connection`,
  writes the canonical JSON on stdout and maps the verdict to the contract's exit
  code: ``0`` CONNECTED, ``2`` NOT_PROVEN, ``3`` INDETERMINATE.

**Online only, and read-only.** There is no ``FILE``, no ``--live`` and no
``--board``: the focused PCB *is* the board identity, so this command can never
answer about a board the editor is not on, and it never switches pages or opens
a document on the caller's behalf (the connector's own guard refuses a non-PCB
focus before it reads anything). Nothing here writes a design, and the whole
surface of the run is two ``risk: read`` actions.

**A refusal is not an answer.** A bridge failure — no connector, an unknown
action on an older build, an unparseable ``REF.PAD`` refused by the connector, a
focus that is not a read-only PCB page (the connector's ``requirePcbFocus`` throws
``PAGE_MISMATCH`` before it reads anything) — writes one line to stderr and leaves
stdout **empty**, at exit ``3``. Printing a ``verdict`` JSON there would let a
caller read "INDETERMINATE" as a measured
answer instead of "the question was never asked". Argparse's own usage errors
stay exit ``2``, the same as every other command.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Mapping
from typing import Any

__all__ = [
    "CONNECTION_ACTION",
    "EXIT_CONNECTED",
    "EXIT_INDETERMINATE",
    "EXIT_NOT_PROVEN",
    "PROBE_ACTION",
    "PROBE_PARAMS",
    "probe_and_project",
    "run_cli_connection",
]

#: The version read that comes **first**: whose editor, whose connector build.
PROBE_ACTION = "sys.probe"
#: An empty namespaces list is the cheapest answer that still carries both
#: versions: the probe enumerates the top level and nothing else. Asking for
#: `realm` would execute constant code for a version string, and `checks` would
#: enumerate method tables nobody here reads.
PROBE_PARAMS: dict[str, Any] = {"namespaces": []}

#: The one action this command is allowed to reach beyond the version read.
CONNECTION_ACTION = "pcb.connection_probe"

EXIT_CONNECTED = 0
EXIT_NOT_PROVEN = 2
EXIT_INDETERMINATE = 3

_VERDICT_EXIT = {
    "CONNECTED": EXIT_CONNECTED,
    "NOT_PROVEN": EXIT_NOT_PROVEN,
    "INDETERMINATE": EXIT_INDETERMINATE,
}


def _text(value: Any) -> str | None:
    """A non-empty string, or ``None`` — never a coerced ``""``."""
    return value if isinstance(value, str) and value else None


def _versions(answer: Any, failure: str = "") -> dict[str, Any]:
    """The host/connector build pair, and where it came from.

    Both spellings live in one object on purpose: a reader that quotes
    「connector 0.6.x answered this」 has to be able to see that the number came
    from a *different* call than the evidence did. ``null`` is never left to
    speak for itself: a member that could not be read is named in ``missing``
    and the reason is in ``error``, because 「the probe answered without a build
    number」 and 「this payload has no such field」 are different facts and this
    object is the only place that can tell them apart. Neither ever becomes a
    wrong version, and neither ever changes the verdict.
    """
    box = answer if isinstance(answer, Mapping) else {}
    row: dict[str, Any] = {
        "host": _text(box.get("version")),
        "connector": _text(box.get("connector")),
        "readBy": PROBE_ACTION,
    }
    missing = [name for name in ("host", "connector") if row[name] is None]
    if missing:
        row["missing"] = missing
    if failure:
        row["error"] = failure
    elif missing:
        row["error"] = (
            f"{PROBE_ACTION} answered without {', '.join(missing)} — the build number was not read, "
            "which is not the same as the field not existing"
        )
    return row


def probe_and_project(
    call: Callable[[str, dict[str, Any]], Any], from_ref: str, to_ref: str
) -> tuple[Any | None, str]:
    """``(result, refusal)`` — the projected answer, or why there is none.

    ``call`` is ``(action, params) -> payload``; the caller owns the connection
    (the CLI adapter opens one short bridge connection per action). A failure of
    either action is a refusal: **no** ``ConnectionResult`` is built, because a
    verdict needs a response and there is none.
    """
    from .core.connection import project_connection

    try:
        answer = call(PROBE_ACTION, dict(PROBE_PARAMS))
    except Exception as exc:  # noqa: BLE001 — a failed version read is disclosed, not fatal
        answer, failure = None, f"{type(exc).__name__}: {exc}"
    else:
        failure = ""
    try:
        payload = call(CONNECTION_ACTION, {"from": from_ref, "to": to_ref})
    except Exception as exc:  # noqa: BLE001 — a refused read produced no evidence
        return None, (
            f"{CONNECTION_ACTION} refused the read ({type(exc).__name__}: {exc}) — "
            "nothing was measured, so there is no verdict to print"
        )
    result = project_connection(payload)
    result.source["versions"] = _versions(answer, failure)
    return result, ""


def _short_connection_call(
    args: argparse.Namespace, bridge: Callable[[argparse.Namespace], Any]
) -> Callable[[str, dict[str, Any]], Any]:
    """``call(action, params)`` — one short bridge connection **per action**.

    Same shape as ``pcb gate``'s adapter: ``bridge`` is assembly's own opener
    (``cli._open_cli``), so the daemon-on-demand start and the token stay one
    implementation, and the ``--project``/``--instance`` hints travel as the
    route the daemon already understands rather than being resolved here.
    """
    route: dict[str, str] = {}
    project = str(getattr(args, "project", "") or "").strip()
    instance = str(getattr(args, "instance", "") or "").strip()
    if project:
        route["target_project"] = project
    if instance:
        route["target_instance"] = instance

    def call(action: str, params: dict[str, Any]) -> Any:
        from .bridge import client as bridge_client

        BridgeClient, _, port, token = bridge(args)

        async def one() -> Any:
            client = await BridgeClient.open(
                bridge_client.uri_for(port=port), token, "cli", client="boardwise-cli"
            )
            try:
                return await client.call(action, dict(params), **route)
            finally:
                await client.close()

        return asyncio.run(one())

    return call


def run_cli_connection(
    args: argparse.Namespace, *, bridge: Callable[[argparse.Namespace], Any]
) -> int:
    """``boardwise pcb connection`` — ask, project, print, exit."""
    import sys

    result, refusal = probe_and_project(
        _short_connection_call(args, bridge),
        str(args.from_ref),
        str(args.to_ref),
    )
    if result is None:
        print(f"boardwise pcb connection: {refusal}", file=sys.stderr)
        return EXIT_INDETERMINATE
    print(result.to_json(indent=None))
    return _VERDICT_EXIT.get(result.verdict, EXIT_INDETERMINATE)
