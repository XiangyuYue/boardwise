"""One library symbol out of an ``.elibz2`` archive (038Q4).

``lib.symbol_file.get`` hands back the Byte-complete file of one library
symbol; on EasyEDA Pro 4.1.93 a public LCSC **symbol** arrives as an
``.elibz2`` ZIP holding exactly two members — one ``.elibu`` record stream and
one ``symbol2.json`` manifest (measured 2026-11-11 on the AMS1117-3.3 symbol,
``outputs/review/038q3/container-identity.json``).

This module reads that container for **one** symbol and refuses everything it
was not measured to handle. Two facts about the measured stream drive the whole
design:

* the stream carries **two identical ``SYMBOL`` ``DOCHEAD``s** for the same
  uuid: the first segment holds ``META``, the second the ``CANVAS``/``PART``/
  ``RECT``/``PIN``/``ATTR`` body. Feeding that stream to the project reader is
  what produced a correct body box with **0 pins** — the symbol merge in
  :func:`boardwise.parsers.schematic._collect_symbols` is first-wins per uuid,
  so the ``META``-only first copy won and the second copy's pins were dropped
  as a conflicting library document. The fix belongs **here**, not in the
  project path: the same uuid appearing twice in a project archive is a real
  disagreement and must keep its first-wins reading.
* the ``Pin Name``/``Pin Number``/``Pin Type`` attributes name their pin
  through ``parentId == <PIN row's own id>``, so this container is read with
  ``pin_key="pin_id"``. That is a statement about *this* stream, not a
  re-classification of ``.epro2`` (V3 keys by the synthesised ``e<zIndex>``).

What is **not** claimed here: ``.elibz`` (folder form) is unread, one symbol
per archive only, and the profile carries the same gaps the shared collector
always had (no text records, no pin length — see
:func:`boardwise.core.symbolprofile.from_parsed_symbol`'s notes).
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ..core.symbolprofile import SymbolProfile, from_parsed_symbol
from .epru_stream import EpruRecord, ParseStats, iter_epru_records
from .schematic import SymbolDetail, _iter_schematic_records, _symbol_details_from_records

#: The one stream member, by lower-cased suffix: the host names it after the
#: editor that wrote it (``ProLib_pc_2026-11-11.elibu``), so the name is not a
#: constant — only the suffix is.
_STREAM_SUFFIX = ".elibu"

#: The manifest member, by exact name.
_MANIFEST_NAME = "symbol2.json"

#: ``symbol2.json``'s ``docType`` for a symbol (measured: 2).
_SYMBOL_DOC_TYPE = 2

#: Attribute keys that name a pin. Same three the shared collector files by
#: ``parentId``; this reader needs them to prove every ``PIN`` row has exactly
#: one number before it hands the records over.
_PIN_ATTR_KEYS = ("Pin Number", "Pin Name", "Pin Type")

#: Declared sizes are checked **before** anything is decompressed, which is the
#: only place a ZIP bomb can be stopped: ``testzip()`` and ``read()`` both expand
#: the member. A single LCSC symbol stream measured 8.9 kB, so these caps are
#: three orders of magnitude above the measured shape.
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_MEMBER_BYTES = 4 * 1024 * 1024
MAX_TOTAL_MEMBER_BYTES = 8 * 1024 * 1024
MAX_COMPRESSION_RATIO = 512


class Elibz2Error(ValueError):
    """The container, the manifest or the stream is not the shape this reads.

    One refusal type for the whole read, because every caller answer is the same
    — "this file is not the one symbol you asked for, here is why" — and the
    message always names the concrete reason rather than "invalid file".
    """


@dataclass(frozen=True)
class Elibz2Symbol:
    """One symbol read out of an ``.elibz2`` container, with its provenance."""

    #: The parsed symbol, in the shape the shared collector produces.
    detail: SymbolDetail
    #: SHA-256 of the container file itself — the identity a caller can quote
    #: without shipping a host path.
    archive_sha256: str
    #: SHA-256 of the decoded ``.elibu`` stream inside it.
    stream_sha256: str
    #: The stream member's name, kept because the host derives it from the
    #: writing editor and it is the only per-file fact the manifest omits.
    stream_member: str
    symbol_uuid: str
    library_uuid: str
    #: ``display_title`` from ``symbol2.json``, already proven equal to the
    #: stream's own ``META.title``.
    title: str
    #: ``editVersion`` of the ``SYMBOL`` ``DOCHEAD`` (measured: ``4.1.93``).
    editor_version: str
    #: How many ``SYMBOL`` ``DOCHEAD``s the stream carried. Measured shape: 2.
    symbol_head_count: int

    @property
    def source(self) -> str:
        """The ``SymbolProfile.source`` string: container identity, no host path."""
        return f"elibz2:{self.symbol_uuid}:sha256:{self.archive_sha256}"

    def symbol_profile(self) -> SymbolProfile:
        """The auditable :class:`SymbolProfile` for this symbol.

        Goes through the one shared mapper, so the pin directions (derived from
        the body box), the electrical roles (from the pin-name table) and the
        three standing "the parser does not expose this" notes are exactly what
        every other profile in the tree carries. Three notes are appended for
        what is specific to this container — and none of them upgrades a
        *derived* value into something the file stated.
        """
        profile = from_parsed_symbol(self.detail, source=self.source)
        profile.notes = [
            *profile.notes,
            f"container: .elibz2 archive sha256:{self.archive_sha256}, stream "
            f"sha256:{self.stream_sha256}, {self.symbol_head_count} SYMBOL "
            "DOCHEAD(s) merged as continuation segments because their head "
            "bodies are identical; a differing repeat is refused, never merged",
            "pin numbers: read from the Pin Number attribute filed by the PIN "
            "row's own id (pin_id) — this container's own key, not a claim that "
            "the stream is an eprj3 project",
            "pin rotation/length: a PIN row may carry its own rotation and "
            "length, and neither reaches SymbolDetail (it exposes tips only), so "
            "a pin's direction below is a body-box reading and not that row's "
            "rotation — the values themselves stay in the container",
        ]
        return profile


def _member_path_problem(name: str) -> str:
    """Why ``name`` is not an acceptable member name, or ``""``.

    A flat member list is what the measured archive has, and it is also the
    only shape whose extraction target is unambiguous: an absolute path, a
    drive letter or a ``..`` component decides where the member *would* land,
    and this reader never wants to know that.
    """
    if not name:
        return "empty member name"
    if name.startswith(("/", "\\")):
        return f"absolute member path {name!r}"
    if "\\" in name:
        return f"backslash in member path {name!r}"
    if len(name) > 1 and name[1] == ":":
        return f"drive-letter member path {name!r}"
    if any(part == ".." for part in name.split("/")):
        return f"parent traversal in member path {name!r}"
    if "/" in name:
        return f"member path {name!r} is not flat"
    return ""


def _read_members(archive: zipfile.ZipFile) -> dict[str, tuple[str, bytes]]:
    """Validate the container and return ``{lower-cased name: (name, bytes)}``.

    The lower-cased key is the *lookup* (the host's own casing is not a
    contract), while the stored real name is what a caller gets to quote.
    """
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(set(names)) != len(names):
        raise Elibz2Error(
            "the archive repeats a member name, so which copy is the file is "
            f"undecidable: {sorted(names)}"
        )
    for info in infos:
        problem = _member_path_problem(info.filename)
        if problem:
            raise Elibz2Error(problem)
    if any(info.flag_bits & 0x1 for info in infos):
        raise Elibz2Error(
            "the archive has encrypted members; an .elibz2 symbol file is never "
            "encrypted, and this reader has no key"
        )
    streams = [i for i in infos if i.filename.lower().endswith(_STREAM_SUFFIX)]
    manifests = [i for i in infos if i.filename.lower() == _MANIFEST_NAME]
    if len(streams) != 1:
        raise Elibz2Error(
            f"expected exactly one *{_STREAM_SUFFIX} member, found {len(streams)}; "
            f"members are {sorted(names)}"
        )
    if len(manifests) != 1:
        raise Elibz2Error(
            f"expected exactly one {_MANIFEST_NAME}, found {len(manifests)}; "
            f"members are {sorted(names)}"
        )
    extras = sorted(
        name for name in names if name not in (streams[0].filename, manifests[0].filename)
    )
    if extras:
        raise Elibz2Error(
            f"the archive carries members this single-symbol contract does not "
            f"read: {extras}"
        )
    # Declared sizes first, decompression second: `testzip()` and `read()` are
    # both the amplification a bomb wants.
    total = 0
    for info in (streams[0], manifests[0]):
        if info.file_size > MAX_MEMBER_BYTES:
            raise Elibz2Error(
                f"member {info.filename!r} declares {info.file_size} bytes, over "
                f"the {MAX_MEMBER_BYTES}-byte cap for one symbol file"
            )
        total += info.file_size
        if info.compress_size and info.file_size > 1024 * 1024:
            ratio = info.file_size / info.compress_size
            if ratio > MAX_COMPRESSION_RATIO:
                raise Elibz2Error(
                    f"member {info.filename!r} declares a {ratio:.0f}:1 expansion, "
                    "which is a decompression bomb, not a symbol stream"
                )
    if total > MAX_TOTAL_MEMBER_BYTES:
        raise Elibz2Error(
            f"the archive declares {total} bytes across its members, over the "
            f"{MAX_TOTAL_MEMBER_BYTES}-byte cap"
        )
    damaged = archive.testzip()
    if damaged is not None:
        raise Elibz2Error(f"member {damaged!r} fails its CRC check")

    out: dict[str, tuple[str, bytes]] = {}
    for info in (streams[0], manifests[0]):
        try:
            out[info.filename.lower()] = (info.filename, archive.read(info))
        except (RuntimeError, zipfile.BadZipFile) as exc:
            raise Elibz2Error(f"member {info.filename!r} cannot be read ({exc})") from exc
    return out


def _decode(raw: bytes, what: str) -> str:
    """Strict UTF-8 (BOM tolerated) for both members.

    ``errors="replace"`` would let a damaged byte become U+FFFD inside a title
    or a pin name and then be reported as a symbol that says that, so the read
    fails instead.
    """
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Elibz2Error(f"{what} is not valid UTF-8 ({exc})") from exc


def _manifest_identity(
    raw: bytes, symbol_uuid: str, library_uuid: str
) -> str:
    """Validate ``symbol2.json`` against the request. Returns the display title."""
    text = _decode(raw, _MANIFEST_NAME)
    try:
        manifest = json.loads(text)
    except ValueError as exc:
        raise Elibz2Error(f"{_MANIFEST_NAME} is not JSON ({exc})") from exc
    if not isinstance(manifest, dict):
        raise Elibz2Error(f"{_MANIFEST_NAME} is not a JSON object")
    for key in ("devices", "footprints", "panelLibs"):
        value = manifest.get(key)
        if value not in (None, {}):
            raise Elibz2Error(
                f"{_MANIFEST_NAME} carries {key} content; a single-symbol file "
                "does not, and this reader will not pick one of them"
            )
    symbols = manifest.get("symbols")
    if not isinstance(symbols, dict) or not symbols:
        raise Elibz2Error(f"{_MANIFEST_NAME} lists no symbols")
    if symbol_uuid not in symbols:
        raise Elibz2Error(
            f"{_MANIFEST_NAME} does not list symbol {symbol_uuid!r}; it lists "
            f"{sorted(symbols)}"
        )
    extra = sorted(set(symbols) - {symbol_uuid})
    if extra:
        raise Elibz2Error(
            f"{_MANIFEST_NAME} lists more than the requested symbol: {extra}"
        )
    entry = symbols[symbol_uuid]
    if not isinstance(entry, dict):
        raise Elibz2Error(f"{_MANIFEST_NAME} entry for {symbol_uuid!r} is not an object")
    declared = str(entry.get("uuid") or "")
    if declared != symbol_uuid:
        raise Elibz2Error(
            f"symbol identity mismatch: requested {symbol_uuid!r}, manifest entry "
            f"says {declared!r}"
        )
    path = str(entry.get("path") or "")
    if path != library_uuid:
        raise Elibz2Error(
            f"library identity mismatch: requested {library_uuid!r}, manifest "
            f"entry's path says {path!r}"
        )
    if entry.get("docType") != _SYMBOL_DOC_TYPE:
        raise Elibz2Error(
            f"manifest entry docType is {entry.get('docType')!r}, not a symbol "
            f"({_SYMBOL_DOC_TYPE})"
        )
    title = str(entry.get("display_title") or "")
    if not title:
        raise Elibz2Error("manifest entry declares no display_title")
    return title


@dataclass(frozen=True)
class _Segment:
    """One ``DOCHEAD``-delimited run of records, head included."""

    head: EpruRecord
    records: tuple[EpruRecord, ...]


def _segments(records: list[EpruRecord]) -> list[_Segment]:
    """Cut the raw stream at every ``DOCHEAD`` and validate the document set."""
    segments: list[_Segment] = []
    current: list[EpruRecord] = []
    head: EpruRecord | None = None
    for record in records:
        if record.type == "DOCHEAD":
            if head is not None:
                segments.append(_Segment(head=head, records=tuple(current)))
            elif current:
                raise Elibz2Error(
                    f"{len(current)} record(s) arrive before the first DOCHEAD, so "
                    "no document owns them"
                )
            head, current = record, []
            continue
        if head is None:
            current.append(record)
            continue
        current.append(record)
    if head is None:
        raise Elibz2Error("the stream has no DOCHEAD at all")
    segments.append(_Segment(head=head, records=tuple(current)))
    return segments


def load_elibz2_symbol(
    path: str | Path,
    *,
    symbol_uuid: str,
    library_uuid: str,
) -> Elibz2Symbol:
    """Read **one** symbol from an ``.elibz2`` archive.

    The identity is the caller's: both uuids are required, and the manifest and
    every ``SYMBOL`` ``DOCHEAD`` in the stream have to answer to them. Nothing
    about a symbol's pins is inferred from the manifest, the file name or a
    display title — the stream is the only source of numbers, names and
    geometry, and any disagreement between the two members is refused.

    Raises :class:`Elibz2Error` for every refusal (container, manifest,
    identity, stream shape, pin ambiguity).
    """
    symbol_uuid = str(symbol_uuid or "").strip()
    library_uuid = str(library_uuid or "").strip()
    if not symbol_uuid or not library_uuid:
        raise Elibz2Error(
            "both the symbol uuid and its library uuid are required; neither is "
            "inferred from the file name or the manifest"
        )
    source_path = Path(path)
    try:
        data = source_path.read_bytes()
    except OSError as exc:
        raise Elibz2Error(f"{source_path}: cannot be read ({exc})") from exc
    if not data:
        raise Elibz2Error(f"{source_path}: the file is empty")
    if len(data) > MAX_ARCHIVE_BYTES:
        raise Elibz2Error(
            f"{source_path}: {len(data)} bytes, over the {MAX_ARCHIVE_BYTES}-byte "
            "cap for one symbol file"
        )
    archive_sha256 = hashlib.sha256(data).hexdigest()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = _read_members(archive)
    except zipfile.BadZipFile as exc:
        raise Elibz2Error(
            f"{source_path}: not a readable ZIP, so not an .elibz2 symbol "
            f"container ({exc})"
        ) from exc

    _, manifest_raw = members[_MANIFEST_NAME]
    stream_member, stream_bytes = next(
        value for name, value in members.items() if name.endswith(_STREAM_SUFFIX)
    )
    title = _manifest_identity(manifest_raw, symbol_uuid, library_uuid)
    stream_text = _decode(stream_bytes, "the .elibu stream")

    stats = ParseStats(source=str(source_path))
    raw_records = list(iter_epru_records(stream_text, stats))
    if stats.malformed_records:
        raise Elibz2Error(
            f"the stream has {stats.malformed_records} unparseable record(s); a "
            "symbol read that skipped them would report a part the file does not "
            "describe"
        )
    segments = _segments(raw_records)

    heads: list[dict] = []
    for segment in segments:
        body = segment.head.body
        if not isinstance(body, dict):
            raise Elibz2Error("a DOCHEAD in the stream has no readable body")
        heads.append(body)
    canonical = heads[0]
    for index, body in enumerate(heads):
        if body.get("docType") != "SYMBOL":
            raise Elibz2Error(
                f"DOCHEAD #{index} is docType {body.get('docType')!r}, not a "
                "SYMBOL document"
            )
        if str(body.get("uuid") or "") != symbol_uuid:
            raise Elibz2Error(
                f"DOCHEAD #{index} describes symbol {body.get('uuid')!r}, not the "
                f"requested {symbol_uuid!r}"
            )
        if body != canonical:
            raise Elibz2Error(
                f"DOCHEAD #{index} repeats the symbol uuid with a different body "
                f"({sorted(set(body) ^ set(canonical)) or 'field values differ'}); "
                "only an identical repeat is this container's continuation segment"
            )
    editor_version = str(canonical.get("editVersion") or "")

    # The repeated heads are this container's continuation segments, and merging
    # them is only safe under two rules, both refusing rather than guessing: an
    # element id may not appear in an earlier segment with a *different* body
    # (that is a later write, and it is neither overwritten nor used), and an
    # identical body under one id is dropped as the same record written twice.
    # Dropping the repeat heads is what lets the shared collector see one
    # document instead of two copies of one uuid — the shape whose first-wins
    # merge returned the META-only copy and 0 pins.
    by_id: dict[str, dict] = {
        str(record.id): record.body or {}
        for record in segments[0].records
        if record.id
    }
    dropped_lines = {segment.head.line_no for segment in segments[1:]}
    for segment in segments[1:]:
        for record in segment.records:
            label = str(record.id or "")
            if record.body is None:
                raise Elibz2Error(
                    "a continuation segment carries a record with an empty body, "
                    "which the collector would skip silently"
                )
            if not label:
                if record.type == "PIN" or (
                    record.type == "ATTR"
                    and record.body.get("key") in _PIN_ATTR_KEYS
                ):
                    raise Elibz2Error(
                        f"a {record.type} record in a continuation segment has no "
                        "element id, so its owner is ambiguous"
                    )
                continue
            previous = by_id.get(label)
            if previous is None:
                by_id[label] = record.body
                continue
            if previous != record.body:
                raise Elibz2Error(
                    f"element {label!r} appears twice with different bodies; the "
                    "later copy is not overwritten and not used"
                )
            dropped_lines.add(record.line_no)

    _check_pins(segments)

    lines = stream_text.split("\n")
    merged_text = "\n".join(
        line for index, line in enumerate(lines) if index not in dropped_lines
    )
    merged_stats = ParseStats(source=str(source_path), editor_version=editor_version)
    detail_records = _iter_schematic_records(merged_text, merged_stats)
    details = _symbol_details_from_records(detail_records, merged_stats, pin_key="pin_id")
    detail = details.get(symbol_uuid)
    if detail is None:
        raise Elibz2Error(
            f"the merged stream yielded no SYMBOL detail for {symbol_uuid!r}; "
            f"it yielded {sorted(details)}"
        )
    if detail.title != title:
        raise Elibz2Error(
            f"title mismatch: manifest display_title {title!r}, stream META.title "
            f"{detail.title!r}"
        )
    if len(detail.offsets) != _pin_number_count(segments):
        raise Elibz2Error(
            f"the stream has {_pin_number_count(segments)} numbered PIN record(s) "
            f"but the merged symbol reads {len(detail.offsets)} pin(s)"
        )

    return Elibz2Symbol(
        detail=detail,
        archive_sha256=archive_sha256,
        stream_sha256=hashlib.sha256(stream_bytes).hexdigest(),
        stream_member=stream_member,
        symbol_uuid=symbol_uuid,
        library_uuid=library_uuid,
        title=title,
        editor_version=editor_version,
        symbol_head_count=len(segments),
    )


def _check_pins(segments: list[_Segment]) -> None:
    """Prove every pin attribute names a real pin, once, or refuse.

    The collector filenames attributes in two passes: by ``parentId``, and — for
    a ``parentId`` it does not recognise — against the **open run**, the last
    ``PIN`` seen. That fallback is the trap here: an attribute whose parent
    dangles would be handed to the neighbouring pin, and the symbol would then
    read a name or a type the file never gave it. So all three keys in
    :data:`_PIN_ATTR_KEYS` must name an existing ``PIN`` record, and a
    ``(pin, key)`` pair may appear at most once.

    On top of that, a symbol is a set of numbered pins: two ``PIN`` rows under
    one element id, two rows claiming one number, a row with no
    ``Pin Number`` at all, or an empty number are all refused. ``Pin Name`` and
    ``Pin Type`` stay optional per pin — a symbol may name none of them.
    """
    pins: dict[str, dict] = {}
    for segment in segments:
        for record in segment.records:
            if record.type != "PIN":
                continue
            if record.body is None:
                raise Elibz2Error("a PIN record has an empty body")
            label = str(record.id or "")
            if not label:
                raise Elibz2Error("a PIN record has no element id to file it by")
            if label in pins:
                raise Elibz2Error(f"PIN record id {label!r} appears twice")
            pins[label] = record.body
    if not pins:
        raise Elibz2Error("the stream has no PIN record, so it is not a pin symbol")

    seen: set[tuple[str, str]] = set()
    numbers: dict[str, str] = {}
    for segment in segments:
        for record in segment.records:
            if record.type != "ATTR" or record.body is None:
                continue
            key = str(record.body.get("key") or "")
            if key not in _PIN_ATTR_KEYS:
                continue
            parent = str(record.body.get("parentId") or "")
            if parent not in pins:
                raise Elibz2Error(
                    f"a {key} attribute names {parent!r}, which is no PIN record "
                    "of this symbol; the collector would file it against another pin"
                )
            if (parent, key) in seen:
                raise Elibz2Error(f"pin {parent!r} carries two {key} attributes")
            seen.add((parent, key))
            if key != "Pin Number":
                continue
            number = str(record.body.get("value") or "").strip()
            if not number:
                raise Elibz2Error(f"pin {parent!r} has an empty number")
            if number in numbers.values():
                raise Elibz2Error(f"pin number {number!r} is used by two PIN records")
            numbers[parent] = number
    missing = sorted(set(pins) - set(numbers))
    if missing:
        raise Elibz2Error(f"PIN record(s) {missing} carry no Pin Number attribute")


def _pin_number_count(segments: list[_Segment]) -> int:
    """How many ``PIN`` rows the raw stream holds (the count the read must match)."""
    return sum(
        1 for segment in segments for record in segment.records if record.type == "PIN"
    )
