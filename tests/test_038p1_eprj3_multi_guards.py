"""038P1 — merging several board files: the board names, and the two refusals.

038P let a folder project's boards be read into **one** multi-document stream.
That seam has three ways to lie, and this batch closes all three:

1. **a board head with no uuid.** The names travelled as a ``pcbTitles`` table
   keyed by the PCB document's ``DOCHEAD.uuid``, so a head without one had no
   key: the board's title came out empty even though :func:`_pcb_title` had
   already resolved a name from the file stem, and `_load_model`'s refusal
   listed a uuid-less board as "(无标题板)". ``pcbTitles`` is now a **list in PCB
   document order**, resolved once in the adapter, consumed positionally by
   ``_pcb_documents`` and by `cli._load_model`.
2. **the same PCB document uuid in two files** — one physical board exported
   twice (a copy). Merging reviews it twice and the report claims two boards
   where the design has one, so it is refused **by name** rather than aggregated
   by title or silently deduplicated. Even identical content is refused: the
   *board* is the duplicate, not a library copy of it.
3. **a library document uuid whose body disagrees between files.** Both builders
   key a library by its uuid, so a merged stream keeps the last copy read and the
   first board is then laid out with the *other* board's footprint — wrong pads,
   no error (the 90 mil pad in the test below). Same-content copies are normal
   and allowed; a real disagreement cannot be merged safely, so it is refused
   with the type, the uuid and both files named.

The signature that decides "the same" is :func:`document_signature`: the record
sequence as ``(type, id, body)``, canonically serialised, with only the
``DOCHEAD`` bookkeeping fields dropped. Renumbering, reordering or a body edit
all change it — this reader declines to call two such documents equivalent
rather than guessing, and neither guard runs on a single-file project, whose
reading is unchanged.

Every stream here is synthetic and anonymous; the real V4 sample is read-only
evidence and is not copied into the repo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.core.geometry import ParseStats
from boardwise.engines.pcbreview import _pcb_documents, run_pcb_review
from boardwise.parsers.eprj3 import (
    Eprj3Error,
    document_signature,
    load_eprj3_pcb_source,
)
from boardwise.parsers.epru_stream import split_documents


# --------------------------------------------------------------------------
# the record frame, and the two shapes a board file carries
# --------------------------------------------------------------------------


def _record(envelope: dict, body: dict | None = None) -> str:
    head = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    if body is None:
        return head + "|||"
    return head + "||" + json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "|"


def _head(
    doc_type: str, uuid: str | None = None, version: str = "4.1.60", ticket: int = 1
) -> str:
    """A ``DOCHEAD``. ``uuid=None`` writes the uuid-less head 038P1 has to name."""
    body: dict = {"docType": doc_type}
    if uuid is not None:
        body["uuid"] = uuid
    body["editVersion"] = version
    return _record({"type": "DOCHEAD", "ticket": ticket}, body)


def _library_head(
    doc_type: str, uuid: str, *, version: str = "1.0.0", ticket: int = 1
) -> str:
    """A library document's head — nothing of it is content except the uuid."""
    return _head(doc_type, uuid, version, ticket)


def _footprint(uuid: str, *, width: float, ticket: int = 1) -> str:
    """One ``FOOTPRINT`` document holding a single rectangular SMD pad."""
    return "\n".join([
        _library_head("FOOTPRINT", uuid, ticket=ticket),
        _record({"type": "META", "ticket": ticket, "id": "META"},
                {"title": uuid, "docType": 4}),
        _record({"type": "PAD", "ticket": ticket, "id": "e1"}, {
            "num": "1", "layerId": 1, "centerX": -100, "centerY": 0,
            "defaultPad": {"padType": "RECT", "width": width, "height": 30},
            "hole": None, "plated": True, "padAngle": 0,
        }),
    ]) + "\n"


def _device(uuid: str, *, value: str, ticket: int = 1) -> str:
    """One ``DEVICE`` document — library payload neither board lays out."""
    return "\n".join([
        _library_head("DEVICE", uuid, ticket=ticket),
        _record({"type": "META", "ticket": ticket, "id": "META"},
                {"title": uuid, "docType": 5}),
        _record({"type": "ATTR", "ticket": ticket, "id": "v1"},
                {"key": "Value", "value": value}),
    ]) + "\n"


def _pcb_stream(
    *,
    uuid: str | None,
    title: str = "",
    board: str = "",
    footprint: str = "",
    designator: str | None = None,
    x: float = 10.0,
    y: float = 20.0,
) -> str:
    """One board document: its head, its META, and an optional placed part.

    ``uuid=None`` is the uuid-less board head; ``title=""`` leaves the META
    without a name so `_pcb_title` has only the file stem left to use.
    """
    lines = [
        _head("PCB", uuid),
        _record({"type": "META", "id": "META"},
                {"title": title, "board": board, "docType": 3}),
        _record({"type": "LAYER", "id": '["LAYER",1]'},
                {"layerName": "Top Layer", "layerType": "TOP"}),
    ]
    if designator is not None:
        lines += [
            _record({"type": "COMPONENT", "id": "c1"},
                    {"partId": "c1", "x": x, "y": y, "angle": 0, "layerId": 1,
                     "zIndex": 1}),
            _record({"type": "ATTR", "id": "a1"},
                    {"parentId": "c1", "key": "Designator", "value": designator}),
        ]
        if footprint:
            lines.append(_record(
                {"type": "ATTR", "id": "a2"},
                {"parentId": "c1", "key": "Footprint", "value": footprint}))
    return "\n".join(lines) + "\n"


def _write_project(root: Path, *, boards: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    index = {
        "name": root.name,
        "owner_uuid": "0123456789abcdef0123456789abcdef",
        "format": "folder",
        "profile": {"schematics": {}, "sheets": {}, "pcbs": {}},
    }
    (root / f"{root.name}.eprj3").write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8")
    for relative, text in boards.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


# --------------------------------------------------------------------------
# 1. a board head with no uuid is named by its file stem, in both readers
# --------------------------------------------------------------------------


def test_a_uuid_less_board_is_named_by_its_file_stem(tmp_path):
    root = _write_project(tmp_path / "proj", boards={
        "pcb/PCB1.epcb2": _pcb_stream(uuid=None, designator="U1"),
        "pcb/PCB2.epcb2": _pcb_stream(uuid=None, designator="U2"),
    })

    source = load_eprj3_pcb_source(root)

    assert source.project_meta["pcbTitles"] == ["PCB1", "PCB2"], (
        "the names travel as a list in PCB-document order, so a head without a "
        "uuid still has a slot to be named in"
    )
    assert [document.uuid for document in source.documents_of_type("PCB")] == [
        None, None
    ], "the stream really does carry two uuid-less board heads"
    assert [title for title, _board, _doc in _pcb_documents(source)] == [
        "PCB1", "PCB2"
    ], "and the reviewer names them by file stem instead of by an empty string"


def test_load_model_names_uuid_less_boards_instead_of_dropping_them(tmp_path):
    root = _write_project(tmp_path / "proj", boards={
        "pcb/PCB1.epcb2": _pcb_stream(uuid=None, designator="U1"),
        "pcb/PCB2.epcb2": _pcb_stream(uuid=None, designator="U2"),
    })

    with pytest.raises(ValueError) as caught:
        cli._load_model(root, view="pcb")
    message = str(caught.value)

    assert "2 块板" in message
    assert "PCB1" in message and "PCB2" in message, (
        "a uuid-less board is listed by name, not as an empty slot"
    )
    assert "(无标题板)" not in message


# --------------------------------------------------------------------------
# 2. the same PCB document uuid twice: one board, two files — refused
# --------------------------------------------------------------------------


def test_a_repeated_board_uuid_is_refused_and_both_files_are_named(tmp_path):
    root = _write_project(tmp_path / "proj", boards={
        "pcb/PCB1.epcb2": _pcb_stream(
            uuid="doc-a", title="PCB1", board="board-a", designator="U1"),
        "pcb/PCB2.epcb2": _pcb_stream(
            uuid="doc-a", title="PCB1", board="board-a", designator="U1"),
    })

    with pytest.raises(Eprj3Error) as caught:
        load_eprj3_pcb_source(root)
    message = str(caught.value)

    assert "doc-a" in message, "the uuid is named"
    assert "PCB1.epcb2" in message and "PCB2.epcb2" in message, (
        "and so are both files that declared it"
    )
    assert "不重复审" in message, (
        "the refusal says what to do (delete the copy) instead of reviewing twice"
    )


# --------------------------------------------------------------------------
# 3. the same library copy in both files: normal, and each board keeps its
#    own geometry
# --------------------------------------------------------------------------


def test_identical_library_copies_are_allowed_and_each_board_keeps_its_own_pads(
    tmp_path,
):
    shared = _device("dev-1", value="100nF")
    root = _write_project(tmp_path / "proj", boards={
        "pcb/PCB1.epcb2": "\n".join([
            _footprint("fp-a", width=20),
            shared.rstrip("\n"),
            _pcb_stream(uuid="doc-a", title="PCB1", board="board-a",
                        footprint="fp-a", designator="U1", x=10.0, y=20.0),
        ]) + "\n",
        "pcb/PCB2.epcb2": "\n".join([
            _footprint("fp-b", width=90),
            shared.rstrip("\n"),
            _pcb_stream(uuid="doc-b", title="PCB2", board="board-b",
                        footprint="fp-b", designator="U2", x=2000.0, y=20.0),
        ]) + "\n",
    })

    source = load_eprj3_pcb_source(root)
    assert [document.uuid for document in source.documents_of_type("DEVICE")] == [
        "dev-1", "dev-1"
    ], "the identical DEVICE copy is still there twice — it was allowed, not merged"

    boards: list = []
    run_pcb_review(root, boards_out=boards)
    assert len(boards) == 2, "one geometry per board, in file order"

    first, second = boards
    assert len(first.pads) == 1 and len(second.pads) == 1
    assert (first.pads[0].width, first.pads[0].x) == (20.0, -90.0), (
        "board A lays out its own 20 mil pad, at its own placement"
    )
    assert (second.pads[0].width, second.pads[0].x) == (90.0, 1900.0), (
        "board B lays out its own 90 mil pad — the shared copy changed nothing"
    )


# --------------------------------------------------------------------------
# 4. a library copy whose body disagrees: refused, never silently merged
# --------------------------------------------------------------------------


def test_a_divergent_footprint_copy_is_refused_before_it_can_wrong_a_board(
    tmp_path,
):
    root = _write_project(tmp_path / "proj", boards={
        "pcb/PCB1.epcb2": "\n".join([
            _footprint("fp-shared", width=20),
            _pcb_stream(uuid="doc-a", title="PCB1", board="board-a",
                        footprint="fp-shared", designator="U1"),
        ]) + "\n",
        "pcb/PCB2.epcb2": "\n".join([
            _footprint("fp-shared", width=90),
            _pcb_stream(uuid="doc-b", title="PCB2", board="board-b",
                        footprint="fp-shared", designator="U2"),
        ]) + "\n",
    })

    with pytest.raises(Eprj3Error) as caught:
        load_eprj3_pcb_source(root)
    message = str(caught.value)

    assert "FOOTPRINT" in message and "fp-shared" in message, (
        "the refusal names the document type and its uuid"
    )
    assert "PCB1.epcb2" in message and "PCB2.epcb2" in message, (
        "and both files that disagree, so a reader knows where to look"
    )
    assert "不能安全合并" in message and "几何" in message, (
        "it says the merge is unsafe and that no geometry is produced — instead "
        "of the old behaviour, where board A was laid out with board B's 90 mil pad"
    )


# --------------------------------------------------------------------------
# 5. only the DOCHEAD bookkeeping differs: still the same library copy
# --------------------------------------------------------------------------


def test_copies_differing_only_in_head_bookkeeping_are_allowed(tmp_path):
    root = _write_project(tmp_path / "proj", boards={
        "pcb/PCB1.epcb2": "\n".join([
            _footprint("fp-shared", width=20, ticket=1),
            _pcb_stream(uuid="doc-a", title="PCB1", board="board-a",
                        footprint="fp-shared", designator="U1"),
        ]) + "\n",
        "pcb/PCB2.epcb2": "\n".join([
            # Same part, saved by a different editor build, re-ticketed: the
            # edit version and the ticket are not content.
            _library_head("FOOTPRINT", "fp-shared", version="2.3.1", ticket=7),
            _record({"type": "META", "ticket": 7, "id": "META"},
                    {"title": "fp-shared", "docType": 4}),
            _record({"type": "PAD", "ticket": 7, "id": "e1"}, {
                "num": "1", "layerId": 1, "centerX": -100, "centerY": 0,
                "defaultPad": {"padType": "RECT", "width": 20, "height": 30},
                "hole": None, "plated": True, "padAngle": 0,
            }),
            _pcb_stream(uuid="doc-b", title="PCB2", board="board-b",
                        footprint="fp-shared", designator="U2", x=2000.0),
        ]) + "\n",
    })

    source = load_eprj3_pcb_source(root)

    footprints = source.documents_of_type("FOOTPRINT")
    assert [document.uuid for document in footprints] == ["fp-shared", "fp-shared"]
    assert [document.edit_version for document in footprints] == ["1.0.0", "2.3.1"], (
        "the two copies really do differ in the head — and only there"
    )
    assert document_signature(footprints[0]) == document_signature(footprints[1]), (
        "the signature drops editVersion (and the envelope's ticket) and keeps "
        "everything else, which is what makes these two copies the same part"
    )
    assert source.footprints()["fp-shared"], "the merged library still has the pads"


def test_the_signature_keeps_element_ids_and_bodies(tmp_path):
    """Negative control for the signature itself: a body edit is a difference."""
    root = _write_project(tmp_path / "proj", boards={
        "pcb/PCB1.epcb2": "\n".join([
            _footprint("fp-shared", width=20),
            _pcb_stream(uuid="doc-a", title="PCB1", designator="U1"),
        ]) + "\n",
        "pcb/PCB2.epcb2": "\n".join([
            _footprint("fp-shared", width=21),
            _pcb_stream(uuid="doc-b", title="PCB2", designator="U2"),
        ]) + "\n",
    })

    source_documents = []
    for relative in ("pcb/PCB1.epcb2", "pcb/PCB2.epcb2"):
        text = (root / relative).read_text(encoding="utf-8")
        source_documents.append(split_documents(text, ParseStats())[0])
    assert document_signature(source_documents[0]) != document_signature(
        source_documents[1]
    ), "one pad width apart is not the same document"

    with pytest.raises(Eprj3Error):
        load_eprj3_pcb_source(root)
