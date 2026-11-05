"""041 S2: an engineer's explicit cross-board declaration, read and checked.

041 S1 gave the model a way to say what it **cannot** prove: two boards' ``GND``
are two :class:`~boardwise.core.model.NetInstance` objects, and the same spelling
is a question (``ProjectModel.unproven_edges``), never a connection. This module
is the other half of that ruling — somebody who *knows* the harness ties
``5V_IN`` on board A to ``VSYS`` on board B writes it down in a JSON file, and
that file is read here, checked against the real model, and handed back as data.

Three boundaries are deliberate and each is enforced by refusing rather than by
guessing:

* **No discovery.** Only a path the caller names is read; there is no default
  name, no search of the project directory, no environment variable. A file
  lying next to the project is not evidence — an engineer naming it is.
* **No welding.** Nothing here touches :class:`ProjectModel`. The declaration is
  report input; ``net_instances()``, ``cross_board_net_instances()`` and
  ``unproven_edges`` keep answering exactly what they answered before, so a
  same-named group stays "unproven by name" even when a declaration mentions
  one of its members. No union-find, no merged netlist, no dropped E0 group.
* **No verdict.** A :class:`ProvenNetEdge` says a human declared this tie. It is
  ``engineer-declared`` evidence, not a host cross-check (that is S3), and its
  absence never means "disconnected".

Every rejection is one :class:`InterconnectError` carrying a readable reason and
the source, because the CLI turns it into exit 2 and must not print a traceback —
and because a half-read declaration is worse than none: a bad file never
degrades into "0 declared connections".
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .model import BoardModel, NetInstance, ProjectModel

#: The only version this reader understands. Integer 1, and ``True`` is not 1:
#: a boolean where a version belongs means the writer guessed, not that the
#: schema was met.
INTERCONNECT_VERSION = 1

#: The only accepted ``declaredBy``. A declaration is a human's statement; a
#: free-form string here would let a tool mint one.
DECLARED_BY_ENGINEER = "engineer"

_ROOT_KEYS = frozenset({"interconnectVersion", "projectUuid", "edges"})
_REQUIRED_ROOT_KEYS = ("interconnectVersion", "edges")
_EDGE_KEYS = frozenset({"from", "to", "declaredBy", "note"})
_REQUIRED_EDGE_KEYS = ("from", "to", "declaredBy")
_ENDPOINT_KEYS = frozenset({"boardUuid", "net"})


class InterconnectError(ValueError):
    """A declaration this reader refuses, with the reason in the message.

    Covers the whole path: an unreadable file, a broken JSON document, an
    unknown/duplicate key, a version it does not know, and an endpoint that does
    not exist in the project it was declared against. One class because the
    caller's reaction is always the same — refuse to run, say why, write nothing
    — and a ``ValueError`` subclass so an existing handler degrades to a message
    instead of a traceback.
    """


def _kind(value: Any) -> str:
    """The type name to quote in a rejection (``bool`` stays distinct from ``int``)."""
    return type(value).__name__


@dataclass(frozen=True)
class ProvenNetEdge:
    """Two boards' nets an engineer **declared** to be one node (041 §4.1).

    Both ends are :class:`NetInstance`, so both boards are addressable by their
    container uuid and both nets exist verbatim in their board's netlist; the
    validator below is what established that, and the same checks run again here
    so an edge cannot be built around the reader.

    ``evidence_level`` is deliberately a constant, not caller-settable: this batch
    has exactly one kind of proof for a cross-board tie — a human said so, and a
    file cannot claim a stronger one. A host
    cross-check (S3) would be a different level with a different source, and
    inventing the vocabulary now would let a report print a level nothing
    established.

    The two ends must be on **different** boards. A same-board pair is a short
    inside one netlist, which this contract explicitly does not express (041
    S2 §1) — it would also make the "proven" count say something about one board
    twice.
    """

    first: NetInstance
    second: NetInstance
    declared_by: str = DECLARED_BY_ENGINEER
    note: str = ""

    evidence_level: str = field(
        default="engineer-declared", init=False, compare=False, repr=True
    )

    def __post_init__(self) -> None:
        for side, instance in (("first", self.first), ("second", self.second)):
            if not isinstance(instance, NetInstance):
                raise TypeError(
                    f"ProvenNetEdge.{side} must be a NetInstance, not "
                    f"{_kind(instance)}: a declared edge joins two boards' nets, "
                    "never a board, a title, a page or a bare name"
                )
            if not isinstance(instance.net_name, str) or not instance.net_name:
                raise InterconnectError(
                    f"ProvenNetEdge.{side} has no net name ({instance!r}): an "
                    "endpoint must name a net that exists verbatim on its board"
                )
        if self.first.board_uuid == self.second.board_uuid:
            if self.first == self.second:
                raise InterconnectError(
                    f"ProvenNetEdge cannot join {self.first!r} to itself: a "
                    "declaration says two boards are tied, and a net is not tied "
                    "to its own instance"
                )
            raise InterconnectError(
                f"ProvenNetEdge cannot join two nets of one board "
                f"({self.first!r}, {self.second!r}): a board-internal short is "
                "not a cross-board declaration (041 S2 §1)"
            )
        if self.declared_by != DECLARED_BY_ENGINEER:
            raise InterconnectError(
                f"ProvenNetEdge.declared_by must be exactly "
                f"{DECLARED_BY_ENGINEER!r}, not {self.declared_by!r}: a "
                "declaration is a human's statement, and no tool may stand in "
                "for one"
            )
        if not isinstance(self.note, str):
            raise InterconnectError(
                f"ProvenNetEdge.note must be a string, not {_kind(self.note)}"
            )


@dataclass(frozen=True)
class InterconnectContract:
    """One successfully read declaration: the claimed project and its edges.

    ``edges`` is a **tuple** so the validated result cannot be appended to by a
    consumer and re-read as if it had been checked. ``project_uuid`` is the uuid
    the file itself pinned, ``""`` when the file omitted it — never the model's
    identity filled in for it, because "this file was written for that project"
    and "this file did not say" are different statements and a report quotes the
    file.

    An empty ``edges`` is a real, successful answer ("this project declares no
    cross-board tie"); it is only reachable from a file that validated, never
    from a failed read.
    """

    project_uuid: str = ""
    edges: tuple[ProvenNetEdge, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.project_uuid, str):
            raise InterconnectError(
                f"InterconnectContract.project_uuid must be a string, not "
                f"{_kind(self.project_uuid)}"
            )
        edges = tuple(self.edges)
        for position, edge in enumerate(edges):
            if not isinstance(edge, ProvenNetEdge):
                raise InterconnectError(
                    f"InterconnectContract.edges[{position}] must be a "
                    f"ProvenNetEdge, not {_kind(edge)}"
                )
        object.__setattr__(self, "edges", edges)


def _reject_unknown_keys(
    payload: Mapping[Any, Any], allowed: frozenset[str], *, where: str
) -> None:
    unknown = sorted(str(key) for key in payload if key not in allowed)
    if unknown:
        raise InterconnectError(
            f"{where}: unknown key(s) {', '.join(repr(key) for key in unknown)} — "
            f"only {', '.join(sorted(allowed))} are accepted, so a typo is "
            "refused instead of silently ignored"
        )


def _require_keys(payload: Mapping[Any, Any], required: tuple[str, ...], *, where: str) -> None:
    missing = [key for key in required if key not in payload]
    if missing:
        raise InterconnectError(
            f"{where}: missing required key(s) "
            f"{', '.join(repr(key) for key in missing)}"
        )


def _addressable_boards(model: ProjectModel, *, where: str) -> dict[str, BoardModel]:
    """uuid -> the board that answers to it, skipping non-addressable boards.

    A board with an empty uuid (the implicit board of a project that declares no
    BOARD document, or an ``unattached`` page group) is not in here: it has no id
    a file could name, and no id is invented for it.

    Two boards answering to **one** uuid is refused, not resolved. A container
    that mints a duplicate BOARD id leaves the declaration ambiguous — which
    netlist the endpoint names is unknowable from the file — and every way of
    picking one is wrong: first-board-wins would let a declaration be validated
    against a board the engineer was not looking at (and a board with a different
    net list could make an edge pass or fail by accident), while grouping by title
    or by position would invent a tiebreak the file does not carry. The 038p1
    duplicate-PCB guard already refuses such a project elsewhere; this is the same
    ruling at the identity gate, so the guard is not softened for declarations.
    """
    boards: dict[str, BoardModel] = {}
    for board_model in model.boards:
        uuid = board_model.board.uuid
        # A uuid that is not a string, or is blank, is **not an addressable id**:
        # no file could name it, and looking it up in `BoardModel.nets` would
        # raise the model's own bare `ValueError` out through a caller that only
        # expects `InterconnectError`. The value is never trimmed or replaced — a
        # non-blank uuid is compared verbatim (`" aaaa "` is not `"aaaa"`).
        if not isinstance(uuid, str) or not uuid.strip():
            continue
        existing = boards.get(uuid)
        if existing is not None:
            raise InterconnectError(
                f"{where}: two boards answer to the same BOARD uuid {uuid!r} "
                f"({existing.board.title!r} and {board_model.board.title!r}) — a "
                "declaration names a board by uuid, and with a repeated uuid it is "
                "unknowable which netlist the endpoint means; no first board, "
                "title grouping or page position is accepted as a tiebreak "
                "(041 S2 §3)"
            )
        boards[uuid] = board_model
    if len(boards) < 2:
        raise InterconnectError(
            f"{where}: a cross-board declaration needs at least two addressable "
            f"boards, and this project has {len(model.boards)} board(s), "
            f"{len(boards)} of them addressable by BOARD uuid"
            + (f" ({', '.join(sorted(boards))})" if boards else "")
            + " — a single-board or implicit project has no cross-board endpoint "
            "to declare (041 S2 §3)"
        )
    return boards


def _endpoint(value: Any, *, side: str, where: str, boards: Mapping[str, BoardModel]) -> NetInstance:
    """One ``{boardUuid, net}`` endpoint, proven against the model it names."""
    if not isinstance(value, Mapping):
        raise InterconnectError(
            f"{where}.{side}: must be an object with boardUuid/net, not "
            f"{_kind(value)}"
        )
    _reject_unknown_keys(value, _ENDPOINT_KEYS, where=f"{where}.{side}")
    _require_keys(value, ("boardUuid", "net"), where=f"{where}.{side}")

    resolved: dict[str, str] = {}
    for key in ("boardUuid", "net"):
        raw = value[key]
        if not isinstance(raw, str):
            raise InterconnectError(
                f"{where}.{side}.{key}: must be a string, not {_kind(raw)}"
            )
        if raw == "":
            raise InterconnectError(
                f"{where}.{side}.{key}: must not be empty — an endpoint names one "
                "real board uuid and one net that exists verbatim on it"
            )
        resolved[key] = raw

    uuid = resolved["boardUuid"]
    board_model = boards.get(uuid)
    if board_model is None:
        raise InterconnectError(
            f"{where}.{side}.boardUuid: no addressable BOARD has uuid {uuid!r} "
            f"(addressable: {', '.join(sorted(boards)) or 'none'}) — a board "
            "title, a page uuid, an unattached page or a file digest is not an "
            "identity"
        )
    net_name = resolved["net"]
    if net_name not in board_model.nets:
        raise InterconnectError(
            f"{where}.{side}.net: board {uuid!r} has no net {net_name!r} "
            f"(its nets: {', '.join(sorted(board_model.nets)) or 'none'}) — net "
            "names are compared verbatim, with no trimming and no case folding"
        )
    return NetInstance(uuid, net_name)


def _edge(
    value: Any, *, index: int, where: str, boards: Mapping[str, BoardModel]
) -> ProvenNetEdge:
    """One edge object, with every structural and model check applied in order."""
    location = f"{where}: edges[{index}]"
    if not isinstance(value, Mapping):
        raise InterconnectError(
            f"{location}: must be an object with from/to/declaredBy/note, not "
            f"{_kind(value)}"
        )
    _reject_unknown_keys(value, _EDGE_KEYS, where=location)
    _require_keys(value, _REQUIRED_EDGE_KEYS, where=location)

    declared_by = value["declaredBy"]
    if not isinstance(declared_by, str):
        raise InterconnectError(
            f"{location}.declaredBy: must be a string, not {_kind(declared_by)}"
        )
    if declared_by != DECLARED_BY_ENGINEER:
        raise InterconnectError(
            f"{location}.declaredBy: must be exactly {DECLARED_BY_ENGINEER!r}, "
            f"not {declared_by!r} — this batch recognises no other declarer"
        )

    note: Any = value.get("note", "")
    if not isinstance(note, str):
        raise InterconnectError(
            f"{location}.note: must be a string when given, not {_kind(note)}"
        )

    return ProvenNetEdge(
        _endpoint(value["from"], side="from", where=location, boards=boards),
        _endpoint(value["to"], side="to", where=location, boards=boards),
        declared_by=declared_by,
        note=note,
    )


def parse_interconnect(
    payload: Any,
    model: ProjectModel,
    *,
    project_uuid: str = "",
    source: str = "<memory>",
) -> InterconnectContract:
    """Validate an already-decoded declaration against ``model``; never reads a file.

    ``project_uuid`` is the **real** identity of the project the model came from
    (``""`` when the container carries none, which is every ``.epro2``). It is
    used for one comparison only: a file that pins a ``projectUuid`` must match
    it verbatim, and a file that pins one while the project has no real identity
    is refused — a file name digest, a title or a path is not an identity.

    ``source`` names the origin in every rejection (a path for
    :func:`load_interconnect`, ``"<memory>"`` for a caller holding decoded JSON),
    so a message is actionable without a traceback.
    """
    where = str(source) or "<memory>"

    if not isinstance(model, ProjectModel):
        raise InterconnectError(
            f"{where}: a cross-board declaration is validated against a "
            f"ProjectModel, not {_kind(model)} — a plain DesignModel or one "
            "board's model has no cross-board endpoints to name (041 S2 §3)"
        )
    boards = _addressable_boards(model, where=where)

    if not isinstance(payload, Mapping):
        raise InterconnectError(
            f"{where}: the declaration must be a JSON object with "
            "interconnectVersion/edges, not " + _kind(payload)
        )
    _reject_unknown_keys(payload, _ROOT_KEYS, where=where)
    _require_keys(payload, _REQUIRED_ROOT_KEYS, where=where)

    version = payload["interconnectVersion"]
    if isinstance(version, bool) or not isinstance(version, int) or version != INTERCONNECT_VERSION:
        raise InterconnectError(
            f"{where}.interconnectVersion: must be the integer "
            f"{INTERCONNECT_VERSION}, not {version!r} ({_kind(version)}) — a "
            "boolean or a string where a version belongs is not a version"
        )

    declared_project = ""
    if "projectUuid" in payload:
        raw_project = payload["projectUuid"]
        if not isinstance(raw_project, str):
            raise InterconnectError(
                f"{where}.projectUuid: must be a string, not {_kind(raw_project)}"
            )
        if raw_project == "":
            raise InterconnectError(
                f"{where}.projectUuid: must not be empty when given — omit the "
                "key to say 'this file does not pin a project'"
            )
        current = project_uuid if isinstance(project_uuid, str) else ""
        if not current:
            raise InterconnectError(
                f"{where}.projectUuid: this project has no real projectUuid to "
                f"match (the file says {raw_project!r}), and no title, file name, "
                "digest or path is accepted in its place (041 S2 §1)"
            )
        if raw_project != current:
            raise InterconnectError(
                f"{where}.projectUuid: {raw_project!r} does not match this "
                f"project's uuid {current!r} — a declaration is not applied to a "
                "different project, and the comparison is verbatim"
            )
        declared_project = raw_project

    raw_edges = payload["edges"]
    if not isinstance(raw_edges, list):
        raise InterconnectError(
            f"{where}.edges: must be an array (an explicit [] means 'no "
            f"declared ties'), not {_kind(raw_edges)}"
        )

    edges: list[ProvenNetEdge] = []
    seen: dict[frozenset[NetInstance], int] = {}
    for index, raw_edge in enumerate(raw_edges):
        edge = _edge(raw_edge, index=index, where=where, boards=boards)
        pair = frozenset((edge.first, edge.second))
        previous = seen.get(pair)
        if previous is not None:
            raise InterconnectError(
                f"{where}: edges[{index}] repeats edges[{previous}]: "
                f"{edge.first!r} <-> {edge.second!r} is already declared — a pair "
                "is unordered, so swapping from/to (or changing note) does not "
                "make it a second tie"
            )
        seen[pair] = index
        edges.append(edge)

    return InterconnectContract(project_uuid=declared_project, edges=tuple(edges))


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """``json`` object hook: one key twice in one object is an error, not a last-wins.

    ``json.loads`` silently keeps the later value, which would let a file carry a
    corrected edge next to a stale one and be read as the correction. Refusing is
    the only reading that cannot be mistaken for validation.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise InterconnectError(
                f"duplicate key {key!r} in one JSON object — the later value "
                "would silently replace the earlier one, so the document is "
                "refused instead"
            )
        seen[key] = value
    return seen


def load_interconnect(
    path: str | Path,
    model: ProjectModel,
    *,
    project_uuid: str = "",
) -> InterconnectContract:
    """Read the UTF-8 JSON file at ``path`` and validate it against ``model``.

    ``path`` is the only file this reader ever opens: there is no default name
    and no discovery, so a declaration next to the project is not applied until
    somebody names it. Every failure — missing file, a directory, an unreadable
    file, bytes that are not UTF-8, broken JSON, a repeated key, a version or
    structure this reader does not know, an endpoint the model does not have —
    arrives as one :class:`InterconnectError` naming the path and the reason.
    It never returns an empty contract in place of a failure: "no declared ties"
    and "could not read the declaration" must not look the same to a report.
    """
    location = Path(path)
    try:
        if location.is_dir():
            raise InterconnectError(
                f"{location}: is a directory, not a declaration file — pass the "
                "JSON file itself"
            )
        text = location.read_text(encoding="utf-8")
    except InterconnectError:
        raise
    except FileNotFoundError:
        raise InterconnectError(
            f"{location}: declaration file not found — no default file is "
            "searched for, so the path given to --interconnect must exist"
        ) from None
    except UnicodeDecodeError as exc:
        raise InterconnectError(
            f"{location}: not UTF-8 text ({exc.reason} at byte {exc.start}) — the "
            "declaration is read as UTF-8 only"
        ) from None
    except OSError as exc:
        raise InterconnectError(
            f"{location}: cannot be read ({exc.strerror or exc})"
        ) from None

    try:
        payload = json.loads(text, object_pairs_hook=_pairs_without_duplicates)
    except InterconnectError as exc:
        raise InterconnectError(f"{location}: {exc}") from None
    except json.JSONDecodeError as exc:
        raise InterconnectError(
            f"{location}: not valid JSON ({exc.msg} at line {exc.lineno} column "
            f"{exc.colno})"
        ) from None

    return parse_interconnect(
        payload, model, project_uuid=project_uuid, source=str(location)
    )
