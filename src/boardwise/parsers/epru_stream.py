"""The ``.epru`` record *stream* — framing, decoding and document splitting.

Split out of :mod:`boardwise.parsers.epru` (006c, work item 4). The framing
layer used to live inside the PCB-geometry module, which meant the schematic
parser had to import a **private** name (``load_epru_text``) from the copper
builder in order to read a text file: two unrelated concerns sharing a module,
with the schematic side paying the coupling cost.

Format facts this module owns (reverse-engineered, see ``docs/epru-format.md``;
"confirmed" there means checked on the LLC fixture):

- ``.epro2`` is a ZIP holding ``project2.json`` plus one ``*.epru`` per document
  stream. **Zip entry names may be mojibake'd Chinese**, so the ``.epru`` member
  is matched by extension, never by name.
- ``.epru`` is a line record format: ``{envelope-json}||{body-json}|``
  terminated by ``\n``. Two real-world deviations are tolerated: the final line
  may lack the terminator (``{envelope}||{body-json}``), and a record may carry
  an **empty body** (``{envelope}|||``) — counted as ``empty_body_records`` and
  skipped here, since there is no payload to read. At this framing layer it is
  only a record with no body; the 038U1 consistency view is where it becomes
  what the format calls it — the **atomic delete** of that record's id, which
  is why the raw count is not a drop and the view keeps it as a boundary. The
  two deviations compose: a real V4 export
  ends its document streams with ``{envelope}||``, an empty body whose terminator
  is missing (038F1). That line is **not** ``{envelope}|`` — there the field
  separator itself is gone, which is what a genuinely truncated record looks
  like.
- The stream is a concatenation of **documents**, each introduced by a
  ``DOCHEAD`` record carrying a ``docType``. On the fixture: 252 documents —
  83 SYMBOL, 81 FOOTPRINT, 81 DEVICE, 1 SCH, 1 SCH_PAGE, **1 PCB**, ...

Everything is read in a single streaming pass. Unknown record types are counted
and skipped; malformed lines are counted and skipped. Neither ever raises.

What does **not** belong here: anything that knows what a pad, a track or a
netlist is. Those are views *over* this stream and live in
:mod:`boardwise.parsers.epru` (copper) and
:mod:`boardwise.parsers.epro2_model` (connectivity).
"""

from __future__ import annotations

import json
import math
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

#: Re-exported from :mod:`boardwise.core.geometry`, where it actually lives: a
#: :class:`~boardwise.core.geometry.BoardGeometry` carries one, so the type
#: belongs to the geometry model — moving it down here would invert the
#: layering (``core`` must not import ``parsers``). Importers of the stream get
#: it from this module so that reading the framing code does not require
#: knowing that.
from ..core.geometry import ParseStats

__all__ = [
    "DEVICE_DOC_TYPE",
    "Document",
    "EncryptedProjectError",
    "EpruRecord",
    "FIELD_SEP",
    "FOOTPRINT_DOC_TYPE",
    "KEPT_DOC_TYPES",
    "KNOWN_RECORD_TYPES",
    "PCB_DOC_TYPE",
    "ParseStats",
    "SYMBOL_DOC_TYPE",
    "iter_epru_records",
    "load_epru_text",
    "read_project_meta",
    "resolve_document",
    "resolve_documents",
    "resolve_records",
    "split_documents",
]


class EncryptedProjectError(ValueError):
    """Raised when an ``.epro2`` file cannot be read at all.

    EasyEDA Pro's "save project as (local)" dialog offers an optional
    encryption checkbox. An encrypted export is not a ZIP archive, and an
    archive whose entries carry the encryption flag cannot be read either.
    Both cases land here with an actionable message instead of a confusing
    ``zipfile.BadZipFile`` / ``JSONDecodeError`` stack.
    """

#: Document types that hold data we need.
PCB_DOC_TYPE = "PCB"
FOOTPRINT_DOC_TYPE = "FOOTPRINT"
DEVICE_DOC_TYPE = "DEVICE"
SYMBOL_DOC_TYPE = "SYMBOL"

#: Document types kept by :func:`split_documents`. Everything else is
#: dropped after counting, so memory stays proportional to useful data.
#: ``SYMBOL`` joined the set in 131a: it is the only place a ``.epro2`` backup
#: writes pin *names* (``Pin Name``), and :func:`symbol_pin_names` below reads
#: nothing else for them. It costs 2.5–5k records on the board fixtures (~20% of
#: what was already kept) — paid for, not dropped, and every record is still
#: counted in ``ParseStats`` exactly as before.
KEPT_DOC_TYPES: frozenset[str] = frozenset(
    {PCB_DOC_TYPE, FOOTPRINT_DOC_TYPE, DEVICE_DOC_TYPE, SYMBOL_DOC_TYPE}
)

#: Record types observed on the fixture. Anything outside this set is
#: reported in ``ParseStats.unknown_types`` — i.e. the format drifted.
#:
#: ``POUR`` and ``REGION`` joined in 162b. Both are real record types the walk
#: already reads (``POUR`` became a ``kind="pour"`` polygon in 131f; ``REGION``
#: a prohibition region in 162b) yet neither was listed here, so every board
#: carrying one reported a **format drift** on ``ParseStats.unknown_types``
#: while the parser was in fact decoding that very record. Measured over the
#: 14 ``.epro2`` fixtures: ``POUR`` occurs on 9 of them, 145 records in total
#: (2..46 each); ``REGION`` on 2 of them, 7 records. A drift signal that fires
#: on a type the parser consumes is worse than no signal — it hides the real
#: ones (``TABLE``, ``UNIVERSAL``, ``LAYER_FILL``, ``IMAGE``, ...).
KNOWN_RECORD_TYPES: frozenset[str] = frozenset(
    {
        "ACTIVE_LAYER", "ARC", "ATTR", "BEZIER", "BLOB", "CANVAS", "CIRCLE",
        "COMPONENT", "DELETE_DOC", "DIMENSION", "DOCHEAD", "ELE_PLACEHOLDER", "ELLIPSE",
        "FILL", "FONT", "GROUP", "LAYER", "LAYER_PHYS", "LINE", "META",
        "NET", "OBJ", "PAD", "PAD_NET", "PANELIZE", "PART", "PIN",
        "POLY", "POUR", "POURED", "PREFERENCE", "PRIMITIVE", "RECT", "REGION",
        "RULE", "RULE_SELECTOR", "RULE_TEMPLATE", "SILK_OPTS", "STRING",
        "TEXT", "VIA", "WIRE",
    }
)

#: Separator between envelope JSON and body JSON.
FIELD_SEP = "||"

@dataclass
class EpruRecord:
    """One decoded ``.epru`` line.

    ``client`` is the source flag the envelope may carry (the writing client's
    identity). It is ``None`` when the envelope has none — ``.epro2`` writes it
    on the ``DOCHEAD`` body instead, which is why :class:`Document` carries one
    too. The 038U1 consistency view is its only reader; raw framing is
    unchanged by its presence.
    """

    line_no: int
    type: str
    ticket: int | None = None
    id: str | None = None
    first_ticket: int | None = None
    body: dict[str, Any] | None = None
    client: str | None = None

    @property
    def has_body(self) -> bool:
        return self.body is not None

@dataclass
class Document:
    """A ``DOCHEAD``-delimited document and the records that follow it.

    ``client`` is the ``DOCHEAD`` body's ``client`` (absent on older exports),
    the tie-breaker the consistency view uses when two versions of one id share
    a ticket. It sits **after** ``records`` so every existing positional
    construction keeps its meaning.

    ``deleted`` (038U2) is what the consistency view decided about the document
    **itself**: a winning ``DELETE_DOC`` carrying ``isDelete: true`` retires the
    whole document, and then this carries the document's own metadata with an
    empty ``records`` list. It sits last for the same reason ``client`` does —
    every positional construction written before 038U2 keeps its meaning, and
    the raw view never sets it.
    """

    doc_type: str | None
    uuid: str | None
    edit_version: str | None
    records: list[EpruRecord] = field(default_factory=list)
    client: str | None = None
    deleted: bool = False

def iter_epru_records(text: str, stats: ParseStats | None = None) -> Iterator[EpruRecord]:
    """Decode ``.epru`` text record by record.

    Yields only well-formed records; malformed lines and empty-body records
    are counted on ``stats`` when one is passed. Never raises on bad input.
    """
    for line_no, line in enumerate(text.split("\n")):
        if not line:
            continue
        if stats is not None:
            stats.total_records += 1

        # A record ends with "|"; the final line of a file may not have one.
        # Four shapes reach this point, and they must not be conflated (038F1):
        #   ``{env}||{body}|`` terminated, body present
        #   ``{env}||``        empty body, missing terminator (the V4 EOF shape)
        #   ``{env}|||``       empty body, terminated
        #   ``{env}``          no separator at all — truncated, stays malformed
        # Stripping the last "|" unconditionally is what turned the second shape
        # into ``{env}|``: the separator's second "|" was eaten, so the record
        # "had no separator" and every V4 document stream reported one damaged
        # line at EOF.
        if line.endswith(FIELD_SEP + "|"):
            core = line[:-1]
        elif line.endswith(FIELD_SEP):
            core = line
        elif line.endswith("|"):
            core = line[:-1]
        else:
            core = line
        if FIELD_SEP not in core:
            if stats is not None:
                stats.malformed_records += 1
            continue

        envelope_text, body_text = core.split(FIELD_SEP, 1)
        try:
            envelope = json.loads(envelope_text)
        except ValueError:
            if stats is not None:
                stats.malformed_records += 1
            continue

        if not isinstance(envelope, dict):
            if stats is not None:
                stats.malformed_records += 1
            continue

        body: dict[str, Any] | None = None
        if body_text.strip():
            try:
                decoded = json.loads(body_text)
            except ValueError:
                if stats is not None:
                    stats.malformed_records += 1
                continue
            body = decoded if isinstance(decoded, dict) else None
        else:
            if stats is not None:
                stats.empty_body_records += 1

        record_type = str(envelope.get("type", ""))
        if stats is not None:
            stats.records_by_type[record_type] = stats.records_by_type.get(record_type, 0) + 1
            if record_type not in KNOWN_RECORD_TYPES:
                stats.unknown_types[record_type] = stats.unknown_types.get(record_type, 0) + 1

        yield EpruRecord(
            line_no=line_no,
            type=record_type,
            ticket=envelope.get("ticket"),
            id=envelope.get("id"),
            first_ticket=envelope.get("firstTicket"),
            body=body,
            client=_source_client(envelope.get("client")),
        )

def split_documents(
    text: str, stats: ParseStats, *, consistent: bool = False
) -> list[Document]:
    """Split the record stream into documents, keeping only the ones we need.

    A new document starts at every ``DOCHEAD`` record. Only PCB, FOOTPRINT,
    DEVICE and SYMBOL documents are retained (records of all others are
    dropped after counting) so memory stays proportional to the useful data:

    * PCB       — the board: placements, copper, nets.
    * FOOTPRINT — pad shapes, instantiated per placement.
    * DEVICE    — library metadata (Value / LCSC / Manufacturer) joined to
      a placement through its ``Device`` attribute.
    * SYMBOL    — pin *names*. 131a: a placement's own PCB attributes carry no
      ``Symbol`` pointer, so the DEVICE ``Symbol`` attribute is the only route
      from a pad number to the ``Pin Name`` the library wrote for it (see
      :func:`boardwise.parsers.epro2_model.symbol_pin_names`).

    ``consistent=True`` runs every kept document through
    :func:`resolve_document` and returns that view instead — the raw frame log
    is never touched, this only decides what a model reader gets. The default
    is ``False``, which is the byte-for-byte behaviour of every earlier caller.
    With ``consistent=True`` the per-group consistency counters land on
    ``stats``; the raw count is never inflated either way.

    038U2: a document the view confirmed **deleted** is not part of the returned
    list at all — a tombstoned document is not something a model reader may see,
    and an empty stand-in would read as a document whose every record vanished.
    The raw view is unaffected: ``consistent=False`` keeps it, ``deleted=False``
    and ``stats.deleted_documents`` at 0.
    """
    documents: list[Document] = []
    current: Document | None = None
    for record in iter_epru_records(text, stats):
        if record.type == "DOCHEAD":
            body = record.body or {}
            doc_type = body.get("docType")
            if doc_type is not None:
                stats.document_types[str(doc_type)] = stats.document_types.get(str(doc_type), 0) + 1
            current = Document(
                doc_type=doc_type,
                uuid=body.get("uuid"),
                edit_version=body.get("editVersion"),
                client=_source_client(body.get("client")),
            )
            if doc_type in KEPT_DOC_TYPES:
                documents.append(current)
                current.records.append(record)
            else:
                current = None
            continue
        if current is not None:
            current.records.append(record)
    if consistent:
        documents = [
            resolved
            for resolved in (resolve_document(document, stats) for document in documents)
            if not resolved.deleted
        ]
    return documents

# --------------------------------------------------------------------------
# the consistency view (038U1)
# --------------------------------------------------------------------------

#: Document markers, not elements. A ``DOCHEAD`` introduces a document and a
#: ``DELETE_DOC`` retires one; neither competes as an atomic id, so the element
#: resolver never groups them on an id. ``DELETE_DOC`` is still **read** — by
#: :func:`_document_delete_state`, which asks the same
#: :func:`_resolve_group` the elements use (038U2) and then answers the one
#: question the marker asks: did this document get retired or not.
_DOCUMENT_LEVEL_TYPES: frozenset[str] = frozenset({"DOCHEAD", "DELETE_DOC"})

def _source_client(value: Any) -> str | None:
    """The envelope/DOCHEAD ``client`` string, or ``None`` when absent."""
    return value if isinstance(value, str) else None

def _canonical_json(value: Any) -> str:
    """Key-order-insensitive JSON text for comparing two decoded values."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

def _normalised_id(value: Any) -> tuple[str, str] | None:
    """The comparison key of a record id, or ``None`` when it has no id.

    A plain string compares exactly — no trimming, no alias guessing. A string
    that starts with ``[`` and parses as a JSON **array** is the format's
    composite key (``"[\"LAYER\",1]"``), so it compares as canonical JSON with
    the array's element types intact. A non-string JSON value (synthesised
    input, never seen on a real export) compares the same way.

    An **empty** id is no id: ``""`` is what a record writes when it declares
    none, and grouping on it would merge unrelated elements — two different
    graphic records that both omit their id are not two versions of one of
    them. They pass through verbatim and count nothing.
    """
    if value is None or value == "":
        return None
    if isinstance(value, str):
        if value.startswith("["):
            try:
                parsed = json.loads(value)
            except ValueError:
                parsed = None
            if isinstance(parsed, list):
                return ("json", _canonical_json(parsed))
        return ("raw", value)
    return ("json", _canonical_json(value))

def _ticket_value(value: Any) -> int | None:
    """A finite integer ticket, or ``None`` when the value cannot order anything.

    ``bool`` is not a ticket (``True`` is an ``int`` in Python, which would
    silently rank a flag as ticket 1); a non-finite or fractional float is not
    one either, and neither is a numeric *string* — coercing it would be a guess.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return None

def _body_signature(body: dict[str, Any] | None) -> str | None:
    return None if body is None else _canonical_json(body)

def _resolve_group(
    indexes: list[int], records: list[EpruRecord], document: Document
) -> tuple[int | None, bool]:
    """Pick one winner among the versions of a single id.

    Returns ``(index_of_winner, resolved)``. ``(None, False)`` means the group
    could not be ordered without guessing, and every version must be kept as
    it stands — the caller turns that into ``consistency_unresolved``. Stream
    order is **never** used as a silent fallback, and a later version never
    wins because it came later.
    """
    tickets: list[int] = []
    for index in indexes:
        ticket = _ticket_value(records[index].ticket)
        if ticket is None:
            return None, False
        tickets.append(ticket)
    best_ticket = max(tickets)
    top = [index for index, ticket in zip(indexes, tickets) if ticket == best_ticket]
    if len(top) == 1:
        return top[0], True

    clients: list[str] = []
    for index in top:
        record = records[index]
        client = record.client if record.client is not None else document.client
        if client is None:
            return None, False
        clients.append(client)
    best_client = max(clients)
    top_client = [index for index, client in zip(top, clients) if client == best_client]
    if len(top_client) == 1:
        return top_client[0], True

    # Same id, same ticket, same source: only a genuinely identical copy is
    # safe to drop. Anything else is a conflict no rule in the format settles.
    signatures = {
        (records[index].type, _body_signature(records[index].body), records[index].first_ticket)
        for index in top_client
    }
    if len(signatures) == 1:
        return top_client[0], True
    return None, False

#: The three answers :func:`_document_delete_state` can give about one document.
#: Strings rather than an ``Enum``: they only ever travel one branch deep, and a
#: typo is caught by every test that asks about a deleted page.
_DOC_KEPT = "kept"
_DOC_DELETED = "deleted"
_DOC_UNRESOLVED = "unresolved"

def _document_delete_state(document: Document, stats: ParseStats | None) -> str:
    """Did this document get deleted, kept, or is the question unsettled?

    The official rule (038U2): whole-document deletion is
    ``{"type":"DELETE_DOC","ticket":N}||{"isDelete":true}``, ``isDelete:false``
    revokes it, and a ``DELETE_DOC`` whose body is empty counts as **not
    deleted** — the empty body is the *element* tombstone's shape, not the
    document's, so the two may never be conflated.

    Several markers about one document are adjudicated by the **same**
    :func:`_resolve_group` the element ids use — highest ticket, then largest
    source client, and identical copies collapse — never by a second,
    document-shaped copy of that rule. Returns ``"deleted"``, ``"kept"`` or
    ``"unresolved"``; the last one means the document must be kept **whole** and
    counted on ``consistency_unresolved``, because every shape below is a
    question the format does not settle:

    * a missing/non-integer ticket, a top-ticket tie with no client, or a
      same-client tie whose markers disagree (all three from
      :func:`_resolve_group`);
    * a winning marker whose body has no ``isDelete`` key, or one that is not a
      strict boolean — ``"true"``, ``1`` and ``null`` are not the format's flag,
      and coercing them would be the guess this whole view refuses to make.

    Only the **unsettled** answer is counted, on ``consistency_unresolved`` —
    one per document, including a lone marker whose ticket is unusable.
    ``consistency_duplicate_groups`` is deliberately **not** touched: 038U1's
    contract scopes it to *element id* groups, and a ``DELETE_DOC`` marker has no
    element id, so several markers about one document are one document-level
    question rather than a duplicate element. ``deleted_documents`` is not
    touched here either — only :func:`resolve_document` knows the document is
    leaving the view.
    """
    indexes = [
        index for index, record in enumerate(document.records)
        if record.type == "DELETE_DOC"
    ]
    if not indexes:
        return _DOC_KEPT
    winner, resolved = _resolve_group(indexes, document.records, document)
    if not resolved or winner is None:
        if stats is not None:
            stats.consistency_unresolved += 1
        return _DOC_UNRESOLVED
    body = document.records[winner].body
    if not body:
        return _DOC_KEPT
    flag = body.get("isDelete")
    if not isinstance(flag, bool):
        if stats is not None:
            stats.consistency_unresolved += 1
        return _DOC_UNRESOLVED
    return _DOC_DELETED if flag else _DOC_KEPT

def resolve_document(document: Document, stats: ParseStats | None = None) -> Document:
    """The consistency view of one document: one surviving version per element id.

    The document's **own** fate is decided first (:func:`_document_delete_state`)
    and an element never competes across that answer: a confirmed deletion
    returns the document's own ``doc_type``/``uuid``/``edit_version``/``client``
    with ``records=[]`` and ``deleted=True`` — a tombstone, not a document with
    nothing in it, which is why :func:`resolve_documents`,
    :func:`split_documents` and :func:`resolve_records` drop it instead of
    handing it on. An unsettled document comes back **verbatim** (same object,
    ``deleted=False``) and its elements are not adjudicated at all: a partial
    repair presented as a complete conclusion is worse than the disagreement.

    For a document that survives, groups the records by normalised id (type is
    **not** part of the key, so a ``TEXT`` and an ``ATTR`` under one id
    compete), picks the winner per the format's rule — highest ticket, then
    highest source ``client`` (``record.client``, else ``document.client``) —
    and returns a document where the winner sits at the id's **first**
    appearance (its own ``line_no``/``client``/``body`` intact, for provenance)
    and every other version of that id is gone.

    Three cases stay verbatim:

    * an id that appears once (including a lone tombstone) — same ``EpruRecord``
      objects, same order, so the 14 archived fixtures cannot drift;
    * a record with no id at all (``DOCHEAD``, ``DELETE_DOC``, page metadata) —
      never grouped, never moved;
    * an **unresolved** group — a missing/non-integer ticket, a top-ticket tie
      with no client, or a same-client tie whose payloads disagree. Every
      version is kept as it stands and ``stats.consistency_unresolved`` counts
      the group; the model layer must disclose it rather than pretend the
      question is settled.

    A **winning** empty body is a tombstone: it keeps its ``body=None`` at the
    id's first slot as an ordering boundary (dropping it would let an ATTR that
    an empty line had ended attach to the component before it) while deleting
    every live version of that id. A *losing* tombstone deletes nothing.

    ``stats`` receives one increment per duplicate **element-id** group with more
    than one version: ``consistency_duplicate_groups`` when it was resolved,
    ``consistency_unresolved`` when it was not; and one per document that leaves
    the view entirely, on ``deleted_documents``. A deleted document's elements
    are not adjudicated, so its duplicate ids are not counted — there is no
    model view for them to be duplicated *in*. The same boundary runs the other
    way for the document markers themselves: ``DELETE_DOC`` has no element id,
    so several markers about one document never land on
    ``consistency_duplicate_groups`` (only an unsettled document state is
    counted, on ``consistency_unresolved``).
    """
    state = _document_delete_state(document, stats)
    if state == _DOC_UNRESOLVED:
        return document
    if state == _DOC_DELETED:
        if stats is not None:
            stats.deleted_documents += 1
        return Document(
            doc_type=document.doc_type,
            uuid=document.uuid,
            edit_version=document.edit_version,
            records=[],
            client=document.client,
            deleted=True,
        )

    records = document.records
    keys: dict[int, tuple[str, str]] = {}
    groups: dict[tuple[str, str], list[int]] = {}
    for index, record in enumerate(records):
        if record.type in _DOCUMENT_LEVEL_TYPES:
            continue
        key = _normalised_id(record.id)
        if key is None:
            continue
        keys[index] = key
        groups.setdefault(key, []).append(index)
    if not any(len(indexes) > 1 for indexes in groups.values()):
        return document

    winners: dict[tuple[str, str], int | None] = {}
    for key, indexes in groups.items():
        if len(indexes) < 2:
            continue
        winner, resolved = _resolve_group(indexes, records, document)
        winners[key] = winner
        if stats is not None:
            if resolved:
                stats.consistency_duplicate_groups += 1
            else:
                stats.consistency_unresolved += 1

    resolved_records: list[EpruRecord] = []
    for index, record in enumerate(records):
        key = keys.get(index)
        if key is None or key not in winners:
            resolved_records.append(record)
            continue
        winner = winners[key]
        if winner is None:
            resolved_records.append(record)
        elif index == groups[key][0]:
            resolved_records.append(records[winner])

    return Document(
        doc_type=document.doc_type,
        uuid=document.uuid,
        edit_version=document.edit_version,
        records=resolved_records,
        client=document.client,
    )

def resolve_documents(
    documents: list[Document], stats: ParseStats | None = None
) -> list[Document]:
    """Apply :func:`resolve_document` to every document, minus the deleted ones.

    A document the view confirmed **deleted** is not in the returned list (038U2):
    its tombstone form exists so a caller can *see* the answer, not so a model
    reader can consume a document with no records in it.
    """
    return [
        resolved
        for resolved in (resolve_document(document, stats) for document in documents)
        if not resolved.deleted
    ]

def resolve_records(
    records: Iterable[EpruRecord], stats: ParseStats | None = None
) -> list[EpruRecord]:
    """The consistency view of a **flat** record list, cut back into documents.

    :func:`iter_epru_records` yields one flat stream, but the competition key is
    "document + normalised id": two records only compete when they arrived under
    the same ``DOCHEAD``. So the stream is cut at every ``DOCHEAD`` — one
    :class:`Document` per segment, with that head's own
    ``docType``/``uuid``/``editVersion``/``client`` — each segment is passed to
    the **same** :func:`resolve_document` the archive reader uses, and the
    surviving records come back concatenated in stream order.

    Three properties the callers rely on:

    * records **before the first** ``DOCHEAD`` belong to no document and are
      passed through verbatim — there is no document identity to compete inside,
      and inventing one would put records into a document the file never
      declared;
    * segments are never merged, and a tombstone that wins keeps its
      ``body=None`` slot as the ordering boundary it is;
    * a stream with no duplicate id comes back as the same ``EpruRecord``
      objects in the same order — the structural reason the archived fixtures
      cannot drift through this entry point either.

    038U2 adds one subtraction: a document the view confirmed **deleted**
    contributes nothing at all — not its head, not its ``META``, not its
    ``DELETE_DOC``. That is the half this entry point owns for the pages
    ``split_documents`` never keeps (``SCH_PAGE`` among them): the flat view is
    what the schematic reader walks, so retiring a whole page has to happen
    here or not at all.

    ``stats`` receives the view's per-group counters (see
    :func:`resolve_document`); pass the same object the raw pass used, or
    ``None`` for a read that must not report.
    """
    documents: list[Document] = []
    loose: list[EpruRecord] = []
    current: Document | None = None
    for record in records:
        if record.type == "DOCHEAD":
            body = record.body or {}
            current = Document(
                doc_type=body.get("docType"),
                uuid=body.get("uuid"),
                edit_version=body.get("editVersion"),
                records=[record],
                client=_source_client(body.get("client")),
            )
            documents.append(current)
            continue
        if current is None:
            loose.append(record)
            continue
        current.records.append(record)
    out: list[EpruRecord] = list(loose)
    for document in documents:
        resolved = resolve_document(document, stats)
        if resolved.deleted:
            continue
        out.extend(resolved.records)
    return out

# --------------------------------------------------------------------------
# archive reading
# --------------------------------------------------------------------------

#: The advice every unreadable-archive refusal carries. One string rather than
#: one per reader, because ``.epru`` and ``project2.json`` are two members of
#: **one** container: a partially-copied download damages either, and both reads
#: have to say the same thing about it (101 #4).
_UNREADABLE_HINT = (
    "This project backup cannot be read. EasyEDA Pro's \"save as (local)\" "
    "dialog has an optional encryption checkbox — if the export was "
    "encrypted, re-export it with that option disabled and try again."
)

def read_project_meta(path: str | Path) -> dict[str, Any]:
    """Read ``project2.json`` from an ``.epro2`` archive.

    Returns an empty dict when the archive has no project metadata, which
    keeps callers from having to special-case older backups.

    An archive that cannot be read raises :class:`EncryptedProjectError` — the
    same refusal, with the same advice, that :func:`load_epru_text` gives for the
    ``.epru`` member of that **same** container. This is the reader that re-opens
    the archive, so its ``BadZipFile``/``RuntimeError`` describes exactly the
    damage the other read already converts; letting it out raw (101 #4) gave a
    stack trace and exit 1 to call sites that catch
    ``EncryptedProjectError``/``ValueError``/``OSError``.
    """
    source_path = Path(path)
    try:
        with zipfile.ZipFile(source_path) as archive:
            for info in archive.infolist():
                if info.filename.lower().endswith("project2.json"):
                    try:
                        decoded = json.loads(archive.read(info).decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        return {}
                    return decoded if isinstance(decoded, dict) else {}
    except (zipfile.BadZipFile, RuntimeError) as exc:
        # BadZipFile: not a ZIP at all, or an entry whose CRC does not match.
        # RuntimeError is what zipfile raises for encrypted/CRC-broken data.
        raise EncryptedProjectError(f"{source_path}: {exc}. {_UNREADABLE_HINT}") from exc
    return {}

def load_epru_text(path: str | Path) -> tuple[str, dict[str, Any]]:
    """The project's record stream and metadata — **whatever container it is in**.

    One seam, three containers: a ``.epro2`` ZIP (one ``.epru`` stream inside it),
    and — since 038 — an **eprj3 folder** (one file per document, glued back into a
    single stream by :mod:`boardwise.parsers.eprj3`). Every caller above this line
    keeps taking ``(text, meta)`` and never learns which one it got, which is what
    made the V4 read-only tier a pure increment instead of eight call-site edits.

    Raises :class:`EncryptedProjectError` — with advice to re-export without
    the encryption option — when the file is not a readable ZIP, when its
    entries are flagged encrypted, or when nothing decodes. An eprj3 folder that
    cannot be read raises the same class from the reader (one refusal type for
    "this input is not readable", whatever the reason).
    """
    source_path = Path(path)
    from .eprj3 import Eprj3Error, load_eprj3_text, looks_like_eprj3

    if looks_like_eprj3(source_path):
        try:
            return load_eprj3_text(source_path)
        except Eprj3Error as exc:
            raise EncryptedProjectError(str(exc)) from exc
    hint = _UNREADABLE_HINT
    if not zipfile.is_zipfile(source_path):
        raise EncryptedProjectError(
            f"{source_path}: not an EasyEDA .epro2 archive (not a ZIP file). {hint}"
        )
    try:
        with zipfile.ZipFile(source_path) as archive:
            members = [i for i in archive.infolist() if i.filename.lower().endswith(".epru")]
            if not members:
                raise EncryptedProjectError(
                    f"{source_path}: no .epru document stream inside the archive. {hint}"
                )
            if any(i.flag_bits & 0x1 for i in members):
                raise EncryptedProjectError(
                    f"{source_path}: archive entries are password-protected. {hint}"
                )
            member = max(members, key=lambda i: i.file_size)
            try:
                raw = archive.read(member)
            except (RuntimeError, zipfile.BadZipFile) as exc:
                # RuntimeError is what zipfile raises for encrypted/CRC-broken data.
                raise EncryptedProjectError(f"{source_path}: {exc}. {hint}") from exc
    except zipfile.BadZipFile as exc:
        raise EncryptedProjectError(f"{source_path}: corrupt archive ({exc}). {hint}") from exc

    meta = read_project_meta(source_path)
    # ``utf-8-sig`` and not ``utf-8``: a BOM is part of the container, and a
    # leading U+FEFF made ``json.loads`` refuse the stream's **first** record —
    # counted malformed, dropped, and never reported (100 #19). Both decodes
    # carry the ``-sig``: a stream that is BOM'd *and* damaged must not lose the
    # same record a second time through the fallback branch.
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("utf-8-sig", errors="replace")
    return text, meta
