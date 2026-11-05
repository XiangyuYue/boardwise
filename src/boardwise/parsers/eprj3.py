"""The ``.eprj3`` **folder** project — the V4 offline format, read-only (038, tier A).

`.epro2` is one ZIP with one record stream inside it; `.eprj3` is a **folder** whose
each document is a file of the same record format — `sch/<schematic>/<page>.esch2`
per schematic page, `pcb/<pcb>.epcb2`, and a `<name>.eprj3` JSON index that names
them. The framing layer (``{envelope}||{body}|`` + LF, DOCHEAD-delimited documents)
is byte-for-byte the same, so :func:`~boardwise.parsers.epru_stream.iter_epru_records`
and ``split_documents`` are reused untouched: this module only has to find the
files, glue them into the one stream every consumer already reads, and do the one
transform eprj3 adds.

**The one transform is `yAxisDirection`** (spec: `easyeda-pro-format-skill`,
`primitives/REFERENCE/ty-axis-direction.md`, MIT — fetched 2026-09-25). eprj3 local
files are written in the **cartesian** frame (y up) and marked `up`; the cloud
frame V3 uses is y **down**, which is what every consumer here assumes, so reading
has to flip y back and strip the marker:

* only the **schematic family** is flipped (`SCH` / `SCH_PAGE` / `SIM_SCH` /
  `SIMULATION` / `SYMBOL`); `FOOTPRINT` / `DEVICE` / `PCB` pass through untouched;
* the flipped fields are per primitive (the spec's table): ``y`` for
  ATTR/TEXT/PIN/COMPONENT, ``originY`` for CANVAS, ``startY``/``endY`` for LINE,
  ``dotY1``/``dotY2`` for RECT (plus an embedded ``text.y``), ``centerY`` for
  CIRCLE/ELLIPSE (plus ``text.y``), every element's ``y`` for POLY, the odd
  ``controls`` indices for BEZIER, ``pointY`` for BUSENTRY and every entry of a
  BUS's ``busEntry``, ``startY``/``referY``/``endY`` for ARC, ``startY`` for
  OBJ/TABLE;
* **amplitude fields are never touched** (``height`` / ``radius`` / ``length`` /
  ``expandHeight`` / …) and neither are ``rotation`` / ``isMirror`` / ``zIndex``:
  flipping them would break "flip twice and you are back";
* a missing field means `down` (the cloud frame), and any other value is treated
  as the cloud frame too — only the literal ``up`` flips, which is the spec's own
  rule ("实现只认字面量 'up'").

Where the marker sits in a line is **not** stated by the spec and the official
example project happens to contain none, so this reader accepts it in the
**envelope or the body** and strips it from whichever object held it. Both
placements are covered by the tests, and the day a real V4 export shows a third
one, the fixture is what will say so.

Tier A is **read-only SCH_PAGE**. The **source** half of the pcb view is 038F4's:
:func:`load_eprj3_pcb_source` reads ``pcb/**/*.epcb2`` and hands it to the very same
``split_documents`` / :class:`~boardwise.parsers.epru.Epro2Source` the ``.epro2``
container uses, so both builders work unchanged. 038F5 wired it into the CLI:
``_load_model(view="pcb")`` returns that adapter's source through
``build_design_model`` / ``build_board_geometry``, and
:func:`boardwise.engines.pcbreview._review_units` selects it for a folder project
before running the one shared PCB review path. A project with no board file, or
whose board file holds no PCB document, is refused by the adapter by name — never
answered with an empty model (a model with 0 components and 0 nets reads as "a
clean board" — SKILL pit 14).

**Several boards are normal here** (038P): a V4 folder keeps one ``.epcb2`` per
board, and the real sample ships two. The adapter reads them all, in
:func:`pcb_files` order, into one multi-document stream — the same shape an
``.epro2`` backup of a multi-board project already has, so the review runner
returns one ``boards[]`` entry per board with no new parser and no new list API.
The single-model caller (``--view pcb``) is the one that cannot take several, and
it says so by name instead of letting ``pcb_context()`` answer with the first.

**Merging several files is not always honest** (038P1), and the merged stream is
where an `.epro2` never had to answer the question. Two things are refused here,
**by name**, and only when the project really has more than one board file:

* the **same PCB document uuid** in two files — one physical board exported
  twice (a copy/duplicate) would be reviewed twice, and the report would claim
  two boards where the design has one. Nothing is aggregated by title and
  nothing is deduplicated silently: delete the copy. (Even identical content is
  refused: the *board* is the duplicate, not a library copy of it.)
* a **library document** (``FOOTPRINT`` / ``DEVICE`` / ``SYMBOL``) with the same
  uuid but a **different body** in two files. Both builders key a library by its
  uuid, so a merged stream keeps the last one read and the first board is then
  laid out with the other board's footprint — the wrong pads, silently. Two
  boards carrying the *same* library copy is normal and allowed
  (:func:`document_signature` decides what "the same" means); a real disagreement
  cannot be merged safely, so it is refused instead of resolved.

A PCB document carries **no** ``yAxisDirection`` the way a page does: PCB
coordinates are the cloud frame already, and the board's libraries (``SYMBOL`` /
``FOOTPRINT`` copied into the same file) are library payload that must never be
flipped either. So the PCB read passes the whole file through **untransformed** —
the schematic branch is the only place the y-flip runs.

**The editor version** (038F2) is the other thing a folder project does not hand
over the way an `.epro2` does: there is no `project2.json`, so an index without
`editorVersion` left `ParseStats.editor_version` empty and every consumer that
grades "which editor wrote this" saw unknown. Each content document's `DOCHEAD`
carries `editVersion`, and that is the project's editor version — but only for
the documents that *are* the design (`SCH` / `SCH_PAGE` / `PCB` / `PANEL`).
`SYMBOL` / `DEVICE` / `FOOTPRINT` documents are library payload copied into the
project, so their `editVersion` is whatever editor last saved *that part*; taking
it would be reporting a library's age as the project's. Only a single non-empty
content version becomes `editorVersion`; a conflict is disclosed under
`editorVersionConflict` rather than silently resolved, and no version stays
unknown. An index that does name `editorVersion` keeps its say.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime import cycle
    from .epru import Epro2Source

#: The index file's extension. A folder project is `<folder>/<name>.eprj3`.
EPRJ3_SUFFIX = ".eprj3"
#: Schematic page documents.
ESCH2_SUFFIX = ".esch2"
#: PCB documents: one file per board, ``pcb/<board>.epcb2``.
EPCB2_SUFFIX = ".epcb2"

#: Document types whose coordinates are written y-up in an eprj3 file. Everything
#: else in the same stream passes through byte-for-byte.
SCHEMATIC_DOC_TYPES = frozenset({"SCH", "SCH_PAGE", "SIM_SCH", "SIMULATION", "SYMBOL"})

#: Documents whose ``DOCHEAD.editVersion`` is the **project's** editor version.
#: Library documents (``SYMBOL`` / ``DEVICE`` / ``FOOTPRINT``) also sit in the
#: stream with an ``editVersion``, but theirs is the version of whichever editor
#: last saved that part — it says nothing about this project.
CONTENT_DOC_TYPES = frozenset({"SCH", "SCH_PAGE", "PCB", "PANEL"})

#: Files that declare a content ``DOCHEAD`` but are not part of the tier-A stream
#: (the root schematic config, the PCB, the panel). Read for the version only.
CONTENT_DOC_GLOBS = ("sch/**/*.ecfg", f"pcb/**/*{EPCB2_SUFFIX}", "panel/**/*.epan2")

#: Library documents a board file copies along with the board itself. Two board
#: files of one project routinely copy the same part, so a merged stream holds
#: both copies and the guards below have to say when that is harmless.
LIBRARY_DOC_TYPES = frozenset({"FOOTPRINT", "DEVICE", "SYMBOL"})

#: ``DOCHEAD`` body fields that are per-save bookkeeping rather than content: two
#: saves of the same part differ in these and in nothing else. Everything else on
#: the head (``docType`` / ``uuid`` / …) is content and stays in the signature.
DOCHEAD_BOOKKEEPING_FIELDS = frozenset(
    {"editVersion", "updateTime", "version", "client", "user"}
)

#: Which body field of which primitive carries y (the spec's table, verbatim).
FLIPPED_FIELDS: dict[str, tuple[str, ...]] = {
    "ATTR": ("y",),
    "TEXT": ("y",),
    "PIN": ("y",),
    "COMPONENT": ("y",),
    "CANVAS": ("originY",),
    "LINE": ("startY", "endY"),
    "ARC": ("startY", "referY", "endY"),
    "OBJ": ("startY",),
    "TABLE": ("startY",),
    "CIRCLE": ("centerY",),
    "ELLIPSE": ("centerY",),
    "RECT": ("dotY1", "dotY2"),
    "MASK_REGION": ("dotY1", "dotY2"),
    "BUSENTRY": ("pointY",),
}
#: Types whose embedded ``text`` object also carries a ``y``.
EMBEDDED_TEXT_TYPES = frozenset({"CIRCLE", "ELLIPSE", "RECT"})
#: Types whose ``points`` array is a list of ``{x, y}``.
POINTS_ARRAY_TYPES = frozenset({"POLY"})
#: Types whose ``controls`` array interleaves x and y (the odd indices are y).
CONTROLS_ARRAY_TYPES = frozenset({"BEZIER"})
#: Types whose ``busEntry`` array is a list of ``{pointY}``.
BUS_TYPES = frozenset({"BUS"})


class Eprj3Error(ValueError):
    """The folder is not a readable eprj3 project (message says which part)."""


def looks_like_eprj3(path: str | Path) -> bool:
    """Is this a folder project? (a directory holding a ``*.eprj3`` index)"""
    candidate = Path(path)
    if candidate.is_dir():
        return any(candidate.glob(f"*{EPRJ3_SUFFIX}"))
    if candidate.is_file() and candidate.suffix.lower() == EPRJ3_SUFFIX:
        return True
    return False


def index_path(path: str | Path) -> Path:
    """The ``<name>.eprj3`` index of a folder project, or a refusal."""
    candidate = Path(path)
    if candidate.is_file() and candidate.suffix.lower() == EPRJ3_SUFFIX:
        return candidate
    if not candidate.is_dir():
        raise Eprj3Error(f"{candidate}: not a folder and not a {EPRJ3_SUFFIX} file")
    found = sorted(candidate.glob(f"*{EPRJ3_SUFFIX}"))
    if not found:
        raise Eprj3Error(
            f"{candidate}: no {EPRJ3_SUFFIX} index inside the folder — an eprj3 project "
            "is a folder whose <name>.eprj3 names its documents"
        )
    return found[0]


def read_index(path: str | Path) -> dict[str, Any]:
    """The project metadata (``name`` / ``owner_uuid`` / ``profile`` …).

    Read instead of ``project2.json``: the index is where eprj3 keeps the project
    identity, which is also why the "only a `.epro2` carries a project uuid" gap
    in `cli.py` can be fixed for folder projects (038 §2).
    """
    index = index_path(path)
    try:
        payload = json.loads(index.read_text(encoding="utf-8"))
    except OSError as exc:
        raise Eprj3Error(f"{index}: cannot be read ({exc})") from exc
    except ValueError as exc:
        raise Eprj3Error(f"{index}: is not JSON ({exc})") from exc
    if not isinstance(payload, dict):
        raise Eprj3Error(f"{index}: the index is not a JSON object")
    return payload


def page_files(path: str | Path) -> list[Path]:
    """Every schematic page file, deterministically ordered.

    ``sch/**/*.esch2`` — the schematic tree, one file per page (the spec's own
    layout: ``sch/<schematic>/<page>.esch2``). Sorted by path so two runs of the
    same read produce the same stream, and deduplicated case-insensitively the way
    the rest of the harness treats Windows paths.
    """
    root = Path(path)
    if root.is_file():
        root = root.parent
    found: dict[str, Path] = {}
    for candidate in sorted(root.glob(f"sch/**/*{ESCH2_SUFFIX}")):
        if candidate.is_file():
            found.setdefault(str(candidate).lower(), candidate)
    return [found[key] for key in sorted(found)]


def pcb_files(path: str | Path) -> list[Path]:
    """Every PCB file under ``pcb/``, deterministically ordered (038F4).

    ``pcb/**/*.epcb2`` — the spec's layout is ``pcb/<board>.epcb2``, one file per
    board. Same discipline as :func:`page_files`: a folder and its ``.eprj3``
    index name the same project and give the same list, the order is by path, and
    duplicates are collapsed case-insensitively the way Windows paths compare.
    """
    root = Path(path)
    if root.is_file():
        root = root.parent
    found: dict[str, Path] = {}
    for candidate in sorted(root.glob(f"pcb/**/*{EPCB2_SUFFIX}")):
        if candidate.is_file():
            found.setdefault(str(candidate).lower(), candidate)
    return [found[key] for key in sorted(found)]


def _flip(value: Any) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    return -value


def flip_line(line: str) -> str:
    """One record line, y-flipped per the spec's table, marker stripped.

    A line whose record type has no coordinates (``WIRE`` / ``META`` / ``GROUP`` /
    ``PART`` / …) is returned **untouched**, exactly as the spec says — the flip is
    keyed on (document type, primitive type), and amplitude fields are never in
    the table, so "flip twice" is a fixed point.
    """
    core = line[:-1] if line.endswith("|") else line
    if "yAxisDirection" not in core:
        return line
    if core.count("||") < 1:
        return line
    envelope_text, _, body_text = core.partition("||")
    try:
        envelope = json.loads(envelope_text)
    except ValueError:
        return line
    if not isinstance(envelope, dict):
        return line
    body: dict[str, Any] | None = None
    if body_text.strip():
        try:
            decoded = json.loads(body_text)
        except ValueError:
            decoded = None
        body = decoded if isinstance(decoded, dict) else None
    marker = envelope.pop("yAxisDirection", None)
    if body is not None:
        marker = body.pop("yAxisDirection", marker)
    if marker != "up":
        # Only the literal `up` flips (the spec's rule); anything else is the cloud
        # frame — and the marker still goes away, because a read strips it.
        return _join(envelope, body) if marker is not None else line
    if body is not None:
        _flip_body(str(envelope.get("type") or ""), body)
    return _join(envelope, body)


def _join(envelope: dict[str, Any], body: dict[str, Any] | None) -> str:
    text = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    if body is None:
        return text + "|||"
    return text + "||" + json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "|"


def _flip_body(record_type: str, body: dict[str, Any]) -> None:
    for field in FLIPPED_FIELDS.get(record_type, ()):
        if field in body:
            body[field] = _flip(body[field])
    if record_type in EMBEDDED_TEXT_TYPES:
        embedded = body.get("text")
        if isinstance(embedded, dict) and "y" in embedded:
            embedded["y"] = _flip(embedded["y"])
    if record_type in POINTS_ARRAY_TYPES:
        for item in body.get("points") or []:
            if isinstance(item, dict) and "y" in item:
                item["y"] = _flip(item["y"])
    if record_type in CONTROLS_ARRAY_TYPES:
        controls = body.get("controls")
        if isinstance(controls, list):
            for index in range(1, len(controls), 2):
                controls[index] = _flip(controls[index])
    if record_type in BUS_TYPES:
        for entry in body.get("busEntry") or []:
            if isinstance(entry, dict) and "pointY" in entry:
                entry["pointY"] = _flip(entry["pointY"])


def _doc_head(line: str) -> tuple[str, str] | None:
    """``(docType, editVersion)`` of a ``DOCHEAD`` line, or ``None``.

    Both fields are returned as strings (``""`` when the head does not carry
    one), because the head is the only place a document names itself. A line
    that is not a decodable ``DOCHEAD`` is ``None`` — the caller's job, not this
    one's, to decide whether that matters.
    """
    core = line.rstrip("\r\n")
    core = core[:-1] if core.endswith("|") else core
    envelope_text, _, body_text = core.partition("||")
    try:
        envelope = json.loads(envelope_text)
    except ValueError:
        return None
    if not isinstance(envelope, dict) or envelope.get("type") != "DOCHEAD":
        return None
    try:
        head = json.loads(body_text) if body_text.strip() else {}
    except ValueError:
        return None
    if not isinstance(head, dict):
        return None
    return (str(head.get("docType") or ""), str(head.get("editVersion") or "").strip())


def _doc_type_of(line: str) -> str | None:
    head = _doc_head(line)
    return head[0] if head is not None else None


def _stream_versions(text: str) -> list[str]:
    """Content-document versions in one record stream, in the order they appear."""
    found: list[str] = []
    for line in text.split("\n"):
        head = _doc_head(line)
        if head is None or head[0] not in CONTENT_DOC_TYPES or not head[1]:
            continue
        if head[1] not in found:
            found.append(head[1])
    return found


def _file_versions(root: Path) -> list[str]:
    """Content-document versions from the documents the stream does **not** carry.

    Line-by-line rather than whole-file: a PCB file is the largest document in a
    project and only its ``DOCHEAD`` matters here. An unreadable file is skipped
    — this is metadata, and a version we cannot read is "unknown", not a reason
    to refuse a schematic read that would have worked.
    """
    found: list[str] = []
    for pattern in CONTENT_DOC_GLOBS:
        for candidate in sorted(root.glob(pattern)):
            if not candidate.is_file():
                continue
            try:
                with candidate.open(encoding="utf-8-sig", errors="replace") as handle:
                    for line in handle:
                        if '"DOCHEAD"' not in line:
                            continue
                        head = _doc_head(line)
                        if head is None or head[0] not in CONTENT_DOC_TYPES or not head[1]:
                            continue
                        if head[1] not in found:
                            found.append(head[1])
            except OSError:
                continue
    return found


def _apply_editor_version(meta: dict[str, Any], versions: list[str]) -> None:
    """Fill ``meta['editorVersion']`` from content documents — or say it is unclear.

    The index wins when it names a version (that is the precedence the `.epro2`
    path always had). With nothing in the index: one content version is the
    project's version; several are a conflict, and picking one would be inventing
    a fact, so they are disclosed as ``editorVersionConflict`` and the version
    stays unknown; none leaves it unknown with no extra field.
    """
    declared = meta.get("editorVersion")
    if str(declared or "").strip():
        return
    unique: list[str] = []
    for version in versions:
        if version and version not in unique:
            unique.append(version)
    if not unique:
        return
    if len(unique) == 1:
        meta["editorVersion"] = unique[0]
        return
    meta["editorVersionConflict"] = unique


def transform_text(text: str) -> str:
    """The whole page file: flip only inside the schematic family, keep the rest.

    The document type is tracked the way the stream itself declares it (the last
    ``DOCHEAD``), because the spec's rule is a **(document type, primitive type)**
    pair — a `POLY` means `points` in the schematic domain and `path` in the
    footprint domain, and dispatching on the primitive name alone would flip a
    footprint polygon without saying so.
    """
    out: list[str] = []
    doc_type: str | None = None
    for line in text.split("\n"):
        if not line:
            out.append(line)
            continue
        declared = _doc_type_of(line)
        if declared is not None:
            doc_type = declared
        if doc_type in SCHEMATIC_DOC_TYPES and "yAxisDirection" in line:
            out.append(flip_line(line))
        else:
            out.append(line)
    return "\n".join(out)


def load_eprj3_text(path: str | Path) -> tuple[str, dict[str, Any]]:
    """The project's record stream and metadata, in the same shape `.epro2` gives.

    Every page file is a complete record stream of its own (its own DOCHEAD), so
    gluing them with newlines yields exactly the multi-document stream the offline
    pipeline already reads. Files are read in path order, so the stream is
    reproducible; an unreadable page is reported with its path rather than skipped.

    The metadata is the index plus the fields the pipeline reads; ``editorVersion``
    comes from the index when it has one, otherwise from the content documents'
    ``DOCHEAD.editVersion`` (see :func:`_apply_editor_version`) — the one fact
    that otherwise only exists inside the stream and never reached ``ParseStats``.
    """
    root = Path(path)
    if root.is_file():
        root = root.parent
    index = read_index(path)
    pages = page_files(root)
    if not pages:
        raise Eprj3Error(
            f"{root}: no schematic page ({ESCH2_SUFFIX}) under sch/ — tier A reads the "
            "schematic tree only"
        )
    chunks: list[str] = []
    for page in pages:
        # ``utf-8-sig``: a BOM on the page file made its first line — the page's
        # own ``DOCHEAD``, which is what declares the document type the y-flip
        # below keys on — unparseable, so **no** record in the page was flipped
        # and a y-up board read in the wrong frame (100 #19). Both branches carry
        # the ``-sig``; a page that is BOM'd *and* undecodable kept the BOM.
        try:
            chunks.append(transform_text(page.read_text(encoding="utf-8-sig")))
        except OSError as exc:
            raise Eprj3Error(f"{page}: cannot be read ({exc})") from exc
        except UnicodeDecodeError:
            chunks.append(transform_text(
                page.read_text(encoding="utf-8-sig", errors="replace")))
    text = "\n".join(chunk.rstrip("\n") for chunk in chunks)
    meta = dict(index)
    meta.setdefault("name", root.name)
    meta["format"] = "eprj3"
    meta["pages"] = [page.stem for page in pages]
    meta["sourcePath"] = str(root)
    _apply_editor_version(meta, _stream_versions(text) + _file_versions(root))
    return text, meta


def document_signature(document: Any) -> str:
    """Canonical text of one document's record sequence (038P1's sameness test).

    Two copies of one library part are "the same" only if a merge cannot change
    what either board reads. What a reader can observe is the record sequence —
    order, element ids, bodies — so that is what this hashes, as
    ``(type, id, body)`` per record, canonically serialised by the stdlib's own
    ``json`` (sorted keys, no whitespace).

    ``DOCHEAD`` is included but with :data:`DOCHEAD_BOOKKEEPING_FIELDS` dropped:
    two saves of one part differ in exactly those, and refusing them would refuse
    the normal case. Nothing else is normalised — a renumbered element or a
    reordered record changes the signature, and that is deliberate: this reader
    does not claim two differently-ordered documents are semantically equal, it
    only lets the literal copies through.
    """
    records: list[list[Any]] = []
    for record in getattr(document, "records", ()) or ():
        body = record.body
        if record.type == "DOCHEAD" and isinstance(body, dict):
            body = {
                key: value
                for key, value in body.items()
                if key not in DOCHEAD_BOOKKEEPING_FIELDS
            }
        records.append([record.type, record.id, body])
    return json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _guard_multi_file_documents(
    documents: list[Any], origin: dict[int, Path]
) -> None:
    """Refuse a multi-file project whose documents cannot be merged honestly.

    Only called when the project has more than one board file: a single file is
    the `.epro2` shape, where a repeated uuid is not something this reader has
    ever had to interpret, and it must keep reading exactly as before.

    Two refusals, both naming the uuid and the files (see the module docstring):

    * a repeated **PCB** document uuid — the same physical board exported twice;
    * a ``FOOTPRINT`` / ``DEVICE`` / ``SYMBOL`` uuid whose body disagrees between
      files — a merge would keep one and lay out the other board with it.
    """
    boards_seen: dict[str, Path] = {}
    library_seen: dict[tuple[str, str], tuple[str, Path]] = {}
    for document in documents:
        path = origin[id(document)]
        uuid = str(getattr(document, "uuid", "") or "").strip()
        if not uuid:
            # A head without a uuid (038P1) cannot be matched to anything; the
            # boards are still named, from the file stem (see `_pcb_title`).
            continue
        if document.doc_type == "PCB":
            first = boards_seen.get(uuid)
            if first is None:
                boards_seen[uuid] = path
                continue
            raise Eprj3Error(
                f"{first} 和 {path} 声明了同一个 PCB 文档 uuid {uuid} —— 这是同一块物理"
                "板被重复导出（拷贝/副本），合流后会被审两遍，报告会凭空多出一块板。"
                "重复/副本板不重复审：删掉多余的那份再读。这里不按标题聚合，也不静默去重"
            )
        if document.doc_type not in LIBRARY_DOC_TYPES:
            continue
        signature = document_signature(document)
        key = (document.doc_type, uuid)
        previous = library_seen.get(key)
        if previous is None:
            library_seen[key] = (signature, path)
            continue
        if previous[0] == signature:
            continue  # 同内容的库副本：两块板各带一份，合并后读到的仍是同一份
        raise Eprj3Error(
            f"{previous[1]} 和 {path} 里的 {document.doc_type} 文档 uuid {uuid} 内容不一致 "
            "—— 多文件合流后库文档只能留一份（后读的覆盖先读的），先读的那块板就会按"
            "另一块板的库几何来审（错的焊盘、错的丝印，且不报错）。当前不能安全合并，"
            "这里拒绝读取，不产出错误几何。请核对两份库副本，或把不一致的板拆开单独审"
        )


def _pcb_title(index: dict[str, Any], document: Any, pcb_path: Path) -> str:
    """The board document's own title, in the index's words when it has them.

    ``profile.pcbs`` is the project's uuid→title map and the PCB document's own
    ``DOCHEAD.uuid`` is the key into it, so a board is named the way the project
    names it. Otherwise the document's ``META.title`` says the same thing from the
    board's side, and the file stem is the last resort — never an empty name.
    """
    uuid = str(getattr(document, "uuid", "") or "").strip()
    if uuid:
        profile = index.get("profile")
        pcbs = profile.get("pcbs") if isinstance(profile, dict) else None
        entry = pcbs.get(uuid) if isinstance(pcbs, dict) else None
        if isinstance(entry, dict):
            title = str(entry.get("title") or "").strip()
            if title:
                return title
    for record in getattr(document, "records", ()) or ():
        if record.type != "META":
            continue
        title = str((record.body or {}).get("title") or "").strip()
        if title:
            return title
        break
    return pcb_path.stem


def load_eprj3_pcb_source(path: str | Path) -> "Epro2Source":
    """The folder project's **PCB** document as an :class:`Epro2Source` (038F4).

    The container difference stops here: a folder project keeps its board in
    ``pcb/<board>.epcb2``, which is a complete record stream of its own (its own
    ``DOCHEAD``, its libraries, and the PCB document), so feeding it to the very
    :func:`~boardwise.parsers.epru_stream.split_documents` the ``.epro2`` reader
    uses yields documents both builders already consume —
    :func:`~boardwise.parsers.epru.build_board_geometry` and
    :func:`~boardwise.parsers.epro2_model.build_design_model`. No PCB parser is
    copied and no geometry rule changes.

    **No y-flip.** A page file is written y-up; a PCB file is not — its board
    coordinates are the frame the geometry walk already assumes, and the
    ``SYMBOL`` / ``FOOTPRINT`` documents the file carries are library payload that
    the schematic transform would flip. The file is therefore read verbatim.

    **Every** board of the project is read (038P). A folder project keeps **one
    file per board** (``pcb/PCB1.epcb2``, ``pcb/PCB2.epcb2`` in the real V4
    sample), and each file is a complete record stream of its own, so they are
    read in :func:`pcb_files` order and glued with newlines into **one**
    :class:`Epro2Source` — exactly the multi-document stream an ``.epro2``
    container yields. Nothing downstream learns a second shape: ``_pcb_documents``
    already walks every PCB document, and one shared runner reviews each board on
    its own (one ``boards[]`` entry apiece). A file that holds **no** PCB document
    is refused **by name** — a board file without a board is not an empty board
    (SKILL 坑 14), and the project's other boards do not excuse it.

    ``project_meta`` is the index (its identity fields included), with
    ``editorVersion`` from 038F2's rule — the index when it names one, else the
    content documents' ``editVersion``. The board **names** follow the same
    either/or as the stream: ``title`` is set only when the project holds exactly
    one board (the historic shape), and with several the names travel as
    ``pcbTitles`` — a **list in the same order as the PCB documents** of
    ``source.documents_of_type("PCB")``, one name per board, each resolved the way
    :func:`_pcb_title` resolves one board: the index's ``profile.pcbs`` title
    first, then the document's own ``META.title``, then the file stem. A list and
    not a uuid→name table (038P1): a board file whose ``DOCHEAD`` carries no
    ``uuid`` still has a name (the stem), and a table keyed by uuid used to drop
    it, leaving that board's ``boards[].title`` empty. ``_pcb_documents`` and
    the caller in ``cli._load_model`` consume the list by position and keep their
    META/uuid fallback. ``boardUuid`` is **not** in this list and never comes from
    a title: it stays the document's own ``META.board`` link (151).

    ``--view pcb`` (which builds one model, not a list) is the one caller that
    cannot take several boards; ``cli._load_model`` refuses that case **by name**
    rather than letting ``pcb_context()`` answer with the first board. Every
    per-board consumer (``checkup --file``) goes through the review runner and is
    unaffected.

    **Multi-file refusals** (038P1): with more than one board file, a PCB document
    uuid repeated across files and a library document uuid whose body disagrees
    across files are both refused by :func:`_guard_multi_file_documents`. A
    single-file project takes neither check, so its reading is unchanged.
    """
    from ..core.geometry import ParseStats
    from .epru import Epro2Source
    from .epru_stream import split_documents

    root = Path(path)
    if root.is_file():
        root = root.parent
    index = read_index(path)
    boards = pcb_files(root)
    if not boards:
        raise Eprj3Error(
            f"{root}: no PCB file ({EPCB2_SUFFIX}) under pcb/ — this folder project has "
            "no board document, and an empty board model would read as \"0 器件 0 网\" "
            "(SKILL 坑 14)"
        )

    chunks: list[str] = []
    for pcb_path in boards:
        try:
            chunks.append(pcb_path.read_text(encoding="utf-8-sig"))
        except UnicodeDecodeError:
            chunks.append(pcb_path.read_text(encoding="utf-8-sig", errors="replace"))
        except OSError as exc:
            raise Eprj3Error(f"{pcb_path}: cannot be read ({exc})") from exc
    text = "\n".join(chunk.rstrip("\n") for chunk in chunks)

    meta = dict(index)
    meta.setdefault("name", root.name)
    meta["format"] = "eprj3"
    meta["sourcePath"] = str(root)
    meta["pcbPaths"] = [str(board) for board in boards]
    if len(boards) == 1:
        meta["pcbPath"] = str(boards[0])
    _apply_editor_version(meta, _stream_versions(text) + _file_versions(root))

    stats = ParseStats(source=str(root), editor_version=meta.get("editorVersion"))
    documents: list[Any] = []
    found: list[tuple[Any, Path]] = []
    origin: dict[int, Path] = {}
    for pcb_path, chunk in zip(boards, chunks):
        file_documents = split_documents(chunk, stats, consistent=True)
        file_boards = [
            document for document in file_documents if document.doc_type == "PCB"
        ]
        if not file_boards:
            raise Eprj3Error(
                f"{pcb_path}: no PCB document (DOCHEAD docType \"PCB\") inside the file — "
                "a board file without a board is not an empty board"
            )
        documents.extend(file_documents)
        found.extend((document, pcb_path) for document in file_boards)
        for document in file_documents:
            origin[id(document)] = pcb_path

    if len(boards) > 1:
        _guard_multi_file_documents(documents, origin)

    titles = [_pcb_title(index, document, pcb_path) for document, pcb_path in found]
    if len(found) == 1:
        meta["title"] = titles[0]
    else:
        meta["pcbTitles"] = titles
    return Epro2Source(
        source=str(root), stats=stats, documents=documents, project_meta=meta,
    )


def describe(path: str | Path) -> dict[str, Any]:
    """A sanity line for the evidence files: pages, components, nets (038 §3).

    Read-only and cheap: it counts what the stream declares without building a
    model, so a development-time comparison against the official example can be
    printed even when the model builder is not involved.
    """
    from .epru_stream import iter_epru_records

    text, meta = load_eprj3_text(path)
    counts: dict[str, int] = {}
    designs: list[str] = []
    for record in iter_epru_records(text):
        counts[record.type] = counts.get(record.type, 0) + 1
        if record.type == "ATTR" and (record.body or {}).get("key") == "Designator":
            value = str((record.body or {}).get("value") or "").strip()
            if value:
                designs.append(value)
    designators = sorted(set(designs))
    return {
        "source": str(path),
        "name": meta.get("name"),
        "ownerUuid": meta.get("owner_uuid"),
        "pages": meta.get("pages"),
        "componentInstances": counts.get("COMPONENT", 0),
        "wires": counts.get("WIRE", 0),
        "pins": counts.get("PIN", 0),
        "netlabels": sum(
            1 for record in iter_epru_records(text)
            if record.type == "ATTR" and (record.body or {}).get("key") == "NET"
        ),
        "designators": designators,
        "recordTypes": dict(sorted(counts.items())),
    }


def iter_pages(path: str | Path) -> Iterable[tuple[str, str]]:
    """``(page name, transformed text)`` per page — for callers that want one page."""
    root = Path(path)
    if root.is_file():
        root = root.parent
    for page in page_files(root):
        yield page.stem, transform_text(page.read_text(encoding="utf-8"))
