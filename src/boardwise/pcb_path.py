"""Assembly-owned adapter for ``boardwise pcb path`` (task 562, batch B2).

The judgement lives in :mod:`boardwise.core.livepath` (batch B1), which is a pure
function over one ``pcb.path_probe`` response. This module owns only what that
function cannot answer by itself — **which window** was asked, **which build**
answered, and **how the answer leaves the process**:

* it reads the version pair first (``sys.probe``) so the payload can say which
  host and which connector build produced this evidence. The disclosure is 559's,
  not a second copy of it: :func:`boardwise.pcb_connection._versions` names what
  could not be read in ``versions.missing`` and explains why in ``versions.error``,
  never fabricates a string, and never lets a missing build number change the
  verdict — a host version is not part of the copper-path question;
* it calls ``pcb.path_probe`` with exactly the two ``REF.PAD`` ends and nothing
  else. The action is closed and refuses unknown keys, so this adapter has no
  second entry point to widen it with. 562A's collector answers typed ``nodes[]``,
  **directed** ``edges[]``, ``seeds[]``, ``frontier[]``, ``coverage``,
  ``unknown``/``ignored``/``errors`` — graph evidence with **no verdict**, and no
  ``getEntireTrack`` id set anywhere in it;
* it projects the response through :func:`boardwise.core.livepath.project_live_path`
  and maps the verdict to the contract's exit code: ``0`` CONNECTED, ``2``
  NOT_PROVEN, ``3`` INDETERMINATE.

**Online only, and read-only.** There is no ``FILE``, no ``--live`` and no
``--board``: the focused PCB *is* the board identity, so this command can never
answer about a board the editor is not on, and it never switches pages or opens a
document on the caller's behalf. Nothing here writes a design, and the whole
surface of the run is two ``risk: read`` actions.

**Where the JSON goes is the caller's choice, and a failed write is not a
verdict.** Without ``--json`` the canonical payload is one line on stdout. With
``--json PATH`` the same payload is written beside ``PATH`` through a temporary
file in the same directory and ``os.replace`` — an interrupted run leaves either
the old file or the new one, never half of either — and stdout stays **empty**, so
a shell pipeline cannot mistake a file write for a printed answer. A write that
fails names the reason on stderr, prints **no verdict**, exits ``3`` and discloses
the temporary file it left behind: this module deletes nothing, so a caller can
read what the failure was and clean up after itself if it wants to.

**A refusal is not an answer.** A bridge failure — no connector, an unknown action
on an older build, an unparseable ``REF.PAD`` refused by the connector, a focus
that is not a read-only PCB page (the connector's ``requirePcbFocus`` throws
``PAGE_MISMATCH`` before it reads anything) — writes one line to stderr and leaves
stdout **empty**, at exit ``3``. Printing a ``verdict`` JSON there would let a
caller read "INDETERMINATE" as a measured answer instead of "the question was
never asked". Argparse's own usage errors stay exit ``2``, the same as every other
command.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .pcb_connection import (
    EXIT_CONNECTED,
    EXIT_INDETERMINATE,
    EXIT_NOT_PROVEN,
    PROBE_ACTION,
    PROBE_PARAMS,
    _short_connection_call,
    _versions,
)

__all__ = [
    "EXIT_CONNECTED",
    "EXIT_INDETERMINATE",
    "EXIT_NOT_PROVEN",
    "PATH_ACTION",
    "path_and_project",
    "run_cli_path",
    "write_json_atomically",
]

#: The one action this command is allowed to reach beyond the version read.
PATH_ACTION = "pcb.path_probe"

_VERDICT_EXIT = {
    "CONNECTED": EXIT_CONNECTED,
    "NOT_PROVEN": EXIT_NOT_PROVEN,
    "INDETERMINATE": EXIT_INDETERMINATE,
}


def path_and_project(
    call: Callable[[str, dict[str, Any]], Any], from_ref: str, to_ref: str
) -> tuple[Any | None, str]:
    """``(result, refusal)`` — the projected answer, or why there is none.

    ``call`` is ``(action, params) -> payload``; the caller owns the connection
    (the CLI adapter opens one short bridge connection per action). A failure of
    either action is a refusal: **no** ``LivePathResult`` is built, because a
    verdict needs a response and there is none.
    """
    from .core.livepath import project_live_path

    try:
        answer = call(PROBE_ACTION, dict(PROBE_PARAMS))
    except Exception as exc:  # noqa: BLE001 — a failed version read is disclosed, not fatal
        answer, failure = None, f"{type(exc).__name__}: {exc}"
    else:
        failure = ""
    try:
        payload = call(PATH_ACTION, {"from": from_ref, "to": to_ref})
    except Exception as exc:  # noqa: BLE001 — a refused read produced no evidence
        return None, (
            f"{PATH_ACTION} refused the read ({type(exc).__name__}: {exc}) — "
            "nothing was measured, so there is no verdict to print"
        )
    result = project_live_path(payload)
    result.source["versions"] = _versions(answer, failure)
    return result, ""


def write_json_atomically(path: str, payload: str) -> tuple[str | None, str]:
    """Write ``payload`` to ``path`` via a sibling temp file + ``os.replace``.

    ``(leftover, error)``: on success both are empty/``None``; on failure the
    error names the exception and ``leftover`` is the temporary file this call
    created and **deliberately did not delete**, so the caller can say exactly
    where the residue is. A failure is ``OSError`` (the filesystem said no) or
    ``ValueError`` (the payload itself cannot be encoded — a lone surrogate raises
    ``UnicodeEncodeError``, which is a ``ValueError``, not an ``OSError``); both
    leave the residue disclosed rather than escaping as a traceback. The parent
    directory may be created (a caller naming a new ``--out`` directory gets it),
    and the replacement is atomic on the same volume, so a reader never sees a
    half-written document.
    """
    target = Path(path)
    handle_path: str | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, handle_path = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
        )
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle_path, target)
    except (OSError, ValueError) as exc:
        return handle_path, f"{type(exc).__name__}: {exc}"
    return None, ""


def run_cli_path(
    args: argparse.Namespace, *, bridge: Callable[[argparse.Namespace], Any]
) -> int:
    """``boardwise pcb path`` — ask, project, print or write, exit."""
    import sys

    result, refusal = path_and_project(
        _short_connection_call(args, bridge),
        str(args.from_ref),
        str(args.to_ref),
    )
    if result is None:
        print(f"boardwise pcb path: {refusal}", file=sys.stderr)
        return EXIT_INDETERMINATE
    payload = result.to_json(indent=None)
    target = str(getattr(args, "json_path", "") or "").strip()
    if not target:
        print(payload)
        return _VERDICT_EXIT.get(result.verdict, EXIT_INDETERMINATE)
    leftover, failure = write_json_atomically(target, payload + "\n")
    if failure:
        residue = f"; the temporary file {leftover} was left behind" if leftover else ""
        print(
            f"boardwise pcb path: could not write --json {target} ({failure}) — "
            f"no verdict was printed{residue}",
            file=sys.stderr,
        )
        return EXIT_INDETERMINATE
    return _VERDICT_EXIT.get(result.verdict, EXIT_INDETERMINATE)
