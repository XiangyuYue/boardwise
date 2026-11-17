"""Assembly-owned adapter for ``boardwise pcb net-path`` (task 550).

The judgement lives in :mod:`boardwise.core.netpath`; this module owns only the
things a :class:`~boardwise.core.geometry.BoardGeometry` cannot answer by
itself — **which container** was read, **how many boards** it holds, and **which
one** the caller asked for. That is the same split ``pcb gate`` uses, and the
same reader chain: boards come from ``engines.pcbreview.review_units``, one at a
time, lazily, so a single query never parses every board of a multi-board
archive.

Three refusals are deliberate and loud (never a fallback to the first board):

* a container this batch does not read — KiCad, a lone ``.epcb2``, anything
  else — is refused **by name before** ``review_units`` sees it, so the review
  runner's wider container support never quietly widens this command's promise;
* a multi-board container without ``--board`` is refused, because 「the first
  board」 is a guess and a wrong-board path is worse than no answer;
* ``--board`` that matches nothing, or matches several boards (duplicate title),
  is refused rather than resolved by position.

Exit codes are the contract's: ``0`` CONNECTED, ``2`` NOT_PROVEN, ``3``
INDETERMINATE and every input/container/selection refusal. argparse still exits
``2`` on a usage error, so ``--through``/``--layer``/``--json``/``--project``
are rejected as unknown options instead of being silently ignored.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

CONTAINER_SUFFIXES = (".epro2", ".eprj3")

# Named refusals. Each one is a container this batch could otherwise reach
# through the review runner, so the reason is written down where it is refused.
_REFUSED_BY_NAME = {
    ".kicad_pcb": "a KiCad board is not a supported net-path container in this batch",
    ".kicad_pro": "a KiCad project is not a supported net-path container in this batch",
    ".kicad_sch": "a KiCad schematic is not a supported net-path container in this batch",
    ".epcb2": (
        "a lone .epcb2 board file carries no container identity (no board uuid, no "
        "sibling documents); export the project as .epro2 or point at the .eprj3 folder"
    ),
    ".epru": (
        "a raw .epru stream is not a container; use the .epro2 export that wraps it"
    ),
}

EXIT_CONNECTED = 0
EXIT_NOT_PROVEN = 2
EXIT_INDETERMINATE = 3

_VERDICT_EXIT = {
    "CONNECTED": EXIT_CONNECTED,
    "NOT_PROVEN": EXIT_NOT_PROVEN,
    "INDETERMINATE": EXIT_INDETERMINATE,
}


class ContainerRefused(Exception):
    """The input is not a container (or board) this batch reads."""


def _fail(message: str) -> int:
    """One refusal line on stderr, exit 3 — never a partial JSON answer."""
    import sys

    print(f"boardwise pcb net-path: {message}", file=sys.stderr)
    return EXIT_INDETERMINATE


def _check_container(path: Path) -> str:
    """The container suffix (``".epro2"``/``".eprj3"``) this batch reads, else refuse.

    The suffix check runs **before** any parser, so a wider reader downstream
    cannot turn an unsupported format into a quiet success. A folder is only a
    container when ``parsers.eprj3.looks_like_eprj3`` says so (a directory
    holding an ``*.eprj3`` index), rather than any directory the caller
    happened to point at.

    A ``.eprj3`` **file** is that same index read by its own path — the reader
    accepts it, so the label has to say ``".eprj3"``. Calling it ``".epro2"``
    would put a container this run never read into ``source``, which is
    evidence and may not be a guess.
    """
    if not path.exists():
        raise ContainerRefused(f"{path} does not exist")
    if path.is_dir():
        from .parsers.eprj3 import looks_like_eprj3

        if not looks_like_eprj3(path):
            raise ContainerRefused(
                f"{path} is a folder without a {path.name}.eprj3 project index; "
                "this command reads .epro2 archives and .eprj3 folder projects only"
            )
        return ".eprj3"
    refused = _REFUSED_BY_NAME.get(path.suffix.lower())
    if refused:
        raise ContainerRefused(f"{path.name}: {refused}")
    if path.suffix.lower() not in CONTAINER_SUFFIXES:
        raise ContainerRefused(
            f"{path.name} is not a .epro2 archive or .eprj3 folder project; "
            "this batch reads those two containers only "
            "(KiCad, .epcb2 and the online editor are refused by name)"
        )
    if path.suffix.lower() == ".eprj3":
        from .parsers.eprj3 import looks_like_eprj3

        if looks_like_eprj3(path):
            return ".eprj3"
        raise ContainerRefused(
            f"{path.name} is not an .eprj3 project index this batch can read; "
            "this command reads .epro2 archives and .eprj3 folder projects only"
        )
    return ".epro2"


def _select_unit(units: list[tuple[str, str, Any, Any]], wanted: str) -> int:
    """Index of the board ``wanted`` names, or a refusal that lists the choices.

    A title and a board uuid are both identity spellings the review runner
    already reports, so both are accepted — but **exact**, and never by
    position: several matches mean duplicate titles, which is a refusal because
    picking one of them would be picking arbitrarily.
    """
    if not wanted:
        if len(units) > 1:
            choices = ", ".join(
                _describe(title, uuid) for title, uuid, _read, _model in units
            )
            raise ContainerRefused(
                f"this container holds {len(units)} boards; pass --board with one of: "
                f"{choices} (the first board is never assumed)"
            )
        return 0
    matches = [
        index
        for index, (title, uuid, _read, _model) in enumerate(units)
        if wanted == title or (uuid and wanted == uuid)
    ]
    if not matches:
        choices = ", ".join(
            _describe(title, uuid) for title, uuid, _read, _model in units
        )
        raise ContainerRefused(
            f"--board {wanted!r} matches no board of this container; available: {choices}"
        )
    if len(matches) > 1:
        choices = ", ".join(_describe(*units[index][:2]) for index in matches)
        raise ContainerRefused(
            f"--board {wanted!r} matches {len(matches)} boards ({choices}); "
            "the container has duplicate titles, so pass the board uuid instead"
        )
    return matches[0]


def _describe(title: str, uuid: str) -> str:
    return f"{title} ({uuid})" if uuid else (title or "<untitled>")


def run_cli_net_path(args: argparse.Namespace) -> int:
    """Run one query and print its JSON payload; return the verdict's exit code."""
    from .core.netpath import find_net_path
    from .engines.pcbreview import review_units

    path = Path(str(args.file)).expanduser()
    try:
        kind = _check_container(path)
        units = review_units(path)
        if not units:
            raise ContainerRefused(
                f"{path.name} holds no PCB document; there is no board to ask about"
            )
        index = _select_unit(units, str(getattr(args, "board", "") or "").strip())
    except ContainerRefused as refusal:
        return _fail(str(refusal))
    except Exception as error:  # a parser refusal is still an input refusal
        return _fail(f"{path.name}: {error}")

    title, uuid, read_board, _read_model = units[index]
    try:
        board = read_board()
    except Exception as error:
        return _fail(f"{path.name}: board {_describe(title, uuid)} could not be read: {error}")

    result = find_net_path(
        board,
        str(args.from_ref),
        str(args.to_ref),
        source={
            "container": kind,
            "boardCount": len(units),
            "title": title,
            "uuid": uuid or None,
            "path": str(path),
        },
    )
    print(result.to_json(indent=None))
    return _VERDICT_EXIT.get(result.verdict, EXIT_INDETERMINATE)
