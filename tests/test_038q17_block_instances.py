"""038Q17: a placed native CBB block is read as a block, not as a nameless part.

The bug this batch fixes is again a **silent drop plus a false signal**. Measured
2026-11-15 on a V4 container with one real placed block: the placement
(``COMPONENT bf1c81ee9e14827d``, ``partId=32c6fc8b0adcd464``) reached the parts
pass with no designator, matched ``_looks_like_a_nameless_part`` (no ``Device``
document, no ``Name``), so ``instances_without_designator`` went 0 -> 1 and the
instance was dropped — a block reported as "a part we could not name".

What identifies a block is **three anchors, all required**:

1. ``COMPONENT.partId`` is a ``PART`` record id inside a SYMBOL document;
2. the instance's ``ATTR Symbol`` is that very document's uuid;
3. that document's ``META.docType`` is the number ``17``.

Anchor 1 alone matches ordinary parts (their ``partId`` is ``<device>.1`` and
their symbol document declares exactly that ``PART`` id), so anchor 3 is what
separates a block from a part and anchor 2 is what binds *this* instance to the
symbol. Everything else the container offers is **not** identity: ``Reuse Block``
is ``null`` on the real block, an instance ``Designator``/``Name`` is a label a
user can type, and a shared template id (the page frame's) is declared by many
symbol documents at once.

These tests build **anonymous synthetic** containers in ``tmp_path``. No real
project container, and no copy of one, enters ``tests/``: the fake ids here are
repetitions (``0b0b…``), and the numbers are invented. The real containers are
read only on this machine, in ``.tmp_038q_native/``.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from boardwise.core.geometry import ParseStats
from boardwise.parsers.epru_stream import KNOWN_RECORD_TYPES
from boardwise.parsers.schematic import (
    BLOCK_SOURCE_EMPTY,
    BLOCK_SOURCE_MALFORMED,
    BLOCK_SOURCE_UNRESOLVED,
    BLOCK_SYMBOL_MISMATCH,
    BLOCK_SYMBOL_MISSING,
    BLOCK_UNRESOLVED,
    BLOCK_VERIFIED,
    collect_block_instances,
    collect_part_devices,
    build_project_model,
)

# --------------------------------------------------------------------------
# anonymous ids: 16 hex digits, invented
# --------------------------------------------------------------------------

PAGE = "0a0a0a0a0a0a0a0a"

#: The block's local SYMBOL document and the ``PART`` record inside it.
BLOCK_SYM = "0b0b0b0b0b0b0b0b"
BLOCK_PART = "0c0c0c0c0c0c0c0c"
#: ``META.source`` of a sourced block: ``<source symbol>|<source CBB project>``.
SRC_SYM = "0d0d0d0d0d0d0d0d"
SRC_CBB = "0e" * 32

#: An ordinary part: ``<device>.1`` part id, docType-2 symbol, real designator.
ORD_SYM = "1a1a1a1a1a1a1a1a"
ORD_DEV = "1b1b1b1b1b1b1b1b"
ORD_PART = "CAP0402.1"

#: The page frame: one shared template part id across symbol documents.
FRAME_SYM = "2b2b2b2b2b2b2b2b"
FRAME_PART = "2c2c2c2c2c2c2c2c"

#: A power flag: docType-18 symbol and a ``Global Net Name``.
FLAG_SYM = "3d3d3d3d3d3d3d3d"
FLAG_PART = "3e3e3e3e3e3e3e3e"

#: A docType-17 symbol document that **no** instance uses.
UNPLACED_SYM = "4f4f4f4f4f4f4f4f"
UNPLACED_PART = "4040404040404040"


# --------------------------------------------------------------------------
# record builders (the ``.epru`` line shape: <envelope JSON>||<body JSON>)
# --------------------------------------------------------------------------


def _record(record_type: str, uid: str | None = None, body: dict | None = None,
            ticket: int | None = None) -> str:
    envelope: dict = {"type": record_type}
    if uid is not None:
        envelope["id"] = uid
    if ticket is not None:
        envelope["ticket"] = ticket
    return json.dumps(envelope) + "||" + (json.dumps(body) if body is not None else "")


def _attr(uid: str, parent: str, key: str, value) -> str:
    return _record("ATTR", uid, {"parentId": parent, "key": key, "value": value})


def _component(uid: str, part_id: str, ticket: int, x: float, y: float,
               z_index: int | None, *, rotation: float = 0.0,
               is_mirror: bool = False) -> str:
    return _record("COMPONENT", uid, {
        "partId": part_id, "ticket": ticket, "x": x, "y": y,
        "rotation": rotation, "isMirror": is_mirror, "zIndex": z_index,
    })


def _symbol_doc(uuid: str, parts: list[str], *, doc_type, title: str = "",
                source: str | None = None, pins: tuple = (),
                tag: str = "") -> list[str]:
    """One SYMBOL document: a ``PART`` per part id, optional pins, one ``META``.

    ``pins`` entries are ``(number, name, pin_type, x, y)``; the attributes name
    their pin by the PIN record's own id, which is the V3 rule. ``tag`` only makes
    the record ids unique, so one document can be written twice under one uuid
    (the "the export copied this symbol" shape) without the copies colliding.
    """
    lines = [_record("DOCHEAD", None, {"docType": "SYMBOL", "uuid": uuid})]
    for part_id in parts:
        lines.append(_record("PART", part_id, {"title": ""}))
    for index, (number, name, pin_type, x, y) in enumerate(pins, start=1):
        pin_id = f"{uuid}{tag}-p{index}"
        lines.append(_record("PIN", pin_id, {"x": x, "y": y, "zIndex": index}))
        lines.append(_attr(f"{pin_id}-num", pin_id, "Pin Number", number))
        if name:
            lines.append(_attr(f"{pin_id}-name", pin_id, "Pin Name", name))
        if pin_type:
            lines.append(_attr(f"{pin_id}-type", pin_id, "Pin Type", pin_type))
    meta: dict = {"title": title, "docType": doc_type}
    if source is not None:
        meta["source"] = source
    lines.append(_record("META", f"{uuid}{tag}-meta", meta))
    return lines


def _device_doc(uuid: str, *, title: str, designator: str, symbol: str) -> list[str]:
    return [
        _record("DOCHEAD", None, {"docType": "DEVICE", "uuid": uuid}),
        _record("META", f"{uuid}-meta", {"title": title, "attributes": {
            "Designator": designator, "Symbol": symbol,
        }}),
    ]


def _page(*lines: str) -> list[str]:
    return [_record("DOCHEAD", None, {"docType": "SCH_PAGE", "uuid": PAGE}), *lines]


def _project(tmp_path: Path, lines: list[str], name: str = "synth.epro2") -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("synth.epru", "\n".join(lines) + "\n")
        archive.writestr("project2.json", json.dumps({"title": "synthetic"}))
    return path


#: A block instance's trailing attributes, exactly the shape the real one has:
#: ``Symbol`` present, ``Reuse Block``/``Designator``/``Name`` all ``null``.
def _block_attrs(uid: str, symbol: str | None = BLOCK_SYM) -> list[str]:
    attrs = []
    if symbol is not None:
        attrs.append(_attr(f"{uid}-sym", uid, "Symbol", symbol))
    attrs.append(_attr(f"{uid}-reuse", uid, "Reuse Block", None))
    attrs.append(_attr(f"{uid}-des", uid, "Designator", None))
    attrs.append(_attr(f"{uid}-name", uid, "Name", None))
    return attrs


def _block_doc(doc_type=17, *, source: str | None = f"{SRC_SYM}|{SRC_CBB}",
               title: str = "BLK", pins: tuple = (), tag: str = "") -> list[str]:
    return _symbol_doc(
        BLOCK_SYM, [BLOCK_PART], doc_type=doc_type, title=title,
        source=source, pins=pins, tag=tag,
    )


#: An ordinary part, its device and its symbol; also the docType-2 symbol that
#: declares the *block's* part id (the "same part id, two identities" case).
_ORD_PINS = (("1", "1", "Passive", -10.0, 0.0), ("2", "2", "Passive", 10.0, 0.0))


def _ordinary_documents() -> list[str]:
    return _symbol_doc(
        ORD_SYM, [ORD_PART], doc_type=2, title="CAP0402", pins=_ORD_PINS,
    ) + _device_doc(ORD_DEV, title="CAP0402", designator="C?", symbol=ORD_SYM)


def _ordinary_lines() -> list[str]:
    return [*_page(*_ordinary_instance()), *_ordinary_documents()]


def _ordinary_instance() -> list[str]:
    return [
        _component("c1", ORD_PART, 11, 10.0, -10.0, 2),
        _attr("c1-des", "c1", "Designator", "C1"),
        _attr("c1-val", "c1", "Value", "100nF"),
        _attr("c1-dev", "c1", "Device", ORD_DEV),
        _attr("c1-sym", "c1", "Symbol", ORD_SYM),
    ]


# --------------------------------------------------------------------------
# 1. the three anchors, the disclosure, and the pose
# --------------------------------------------------------------------------


def _one_block_project(tmp_path: Path, *, block_attrs=None) -> Path:
    """A page with a frame, one ordinary part, one flag, one block, plus the
    docType-17 symbol document that no instance uses."""
    frame_attrs = [
        _attr("f-w", "frame", "Width", "1170"),
        _attr("f-h", "frame", "Height", "825"),
        _attr("f-ps", "frame", "Page Size", "A4"),
    ]
    lines = _page(
        *frame_attrs,
        _component("frame", FRAME_PART, 1, 0.0, 0.0, None),
        _component("blk1", BLOCK_PART, 20, 100.0, -50.0, 1),
        *(block_attrs if block_attrs is not None else _block_attrs("blk1")),
        *_ordinary_instance(),
        _component("flag1", FLAG_PART, 30, 30.0, -30.0, 4),
        _attr("flag1-sym", "flag1", "Symbol", FLAG_SYM),
        _attr("flag1-net", "flag1", "Global Net Name", "GND"),
        _attr("flag1-name", "flag1", "Name", "GND"),
    )
    return _project(tmp_path, lines + _block_doc() + [
        *_symbol_doc(FRAME_SYM, [FRAME_PART], doc_type=19, title="A4"),
        *_symbol_doc(FLAG_SYM, [FLAG_PART], doc_type=18, title="GND"),
        *_symbol_doc(UNPLACED_SYM, [UNPLACED_PART], doc_type=17, title="IDLE"),
        *_ordinary_documents(),
    ])


def test_a_placed_block_is_read_through_its_three_anchors(tmp_path):
    path = _one_block_project(tmp_path)
    rows = collect_block_instances(path)
    assert len(rows) == 1
    row = rows[0]
    assert row.page_uuid == PAGE
    assert row.primitive_id == "blk1"
    assert row.part_id == BLOCK_PART
    # anchor 2: the ATTR value is the document the PART id lives in, verbatim
    assert row.symbol_attr == BLOCK_SYM
    assert row.local_symbol == BLOCK_SYM
    # anchor 3 held too, and the source is two hops away, two segments
    assert row.identity_status == BLOCK_VERIFIED
    assert row.identity_reason == ""
    assert (row.source_symbol, row.source_cbb) == (SRC_SYM, SRC_CBB)
    assert row.title == "BLK"
    # the pose is the page's own: canvas y = -stored y, and the block carries
    # rotation/mirror/zIndex rather than any normalised "unit" placement
    assert (row.x, row.y) == (100.0, 50.0)
    assert (row.rotation, row.is_mirror, row.z_index) == (0.0, False, 1)
    # zero PIN records in the symbol: an empty tuple is the reading, not a gap
    assert row.ports == ()
    # the real block carries these all empty; they are disclosure, not identity
    assert (row.designator, row.reuse_block) == ("", "")


def test_rotation_and_mirror_are_disclosed_as_stored(tmp_path):
    path = _project(tmp_path, _page(
        _component("blk1", BLOCK_PART, 20, -40.0, 60.0, 3,
                   rotation=270.0, is_mirror=True),
        *_block_attrs("blk1"),
    ) + _block_doc())
    (row,) = collect_block_instances(path)
    assert row.identity_status == BLOCK_VERIFIED
    assert (row.x, row.y, row.rotation, row.is_mirror, row.z_index) == (
        -40.0, -60.0, 270.0, True, 3,
    )


def test_a_blocks_ports_come_from_the_existing_symbol_pin_reader(tmp_path):
    """Synthetic only: the measured block has no pins at all.

    This proves the port path is the *existing* SYMBOL pin reader (number, name,
    type, symbol-local point) — it does **not** prove that a real block with
    ports is read, which no sample has shown yet.
    """
    path = _project(tmp_path, _page(
        _component("blk1", BLOCK_PART, 20, 0.0, 0.0, 1),
        *_block_attrs("blk1"),
    ) + _block_doc(pins=(
        ("1", "IN", "Input", -100.0, 20.0),
        ("2", "OUT", "Output", 100.0, -20.0),
    )))
    (row,) = collect_block_instances(path)
    assert [(p.number, p.name, p.pin_type, p.point) for p in row.ports] == [
        ("1", "IN", "Input", (-100.0, -20.0)),
        ("2", "OUT", "Output", (100.0, 20.0)),
    ]


# --------------------------------------------------------------------------
# 2. what must not become a block
# --------------------------------------------------------------------------


def test_ordinary_parts_the_frame_flags_and_an_unplaced_block_symbol_are_not_blocks(
    tmp_path,
):
    """Every negative control the task book names, on one page.

    The ordinary part satisfies anchors 1 and 2 (its ``partId`` *is* a ``PART``
    id of its own symbol document) and fails only anchor 3 — which is exactly why
    ``docType`` decides. The frame and the flag are the placements that carry no
    designator by nature. The docType-17 document with no instance is the trap
    the analysis warned about: a 17 on its own does not put a block on the page.
    """
    path = _one_block_project(tmp_path)
    rows = collect_block_instances(path)
    assert [row.primitive_id for row in rows] == ["blk1"]
    assert {row.part_id for row in rows} == {BLOCK_PART}

    stats = ParseStats()
    model = build_project_model(path, parse_stats=stats)
    assert sorted(model.boards[0].components) == ["C1"]
    # the block is not a component (no fake part), and nothing was counted as a
    # part that lost its designator: the false signal is gone at the source
    assert stats.instances_without_designator == 0
    assert collect_part_devices(path) == {"C1": ORD_DEV}


def test_an_ordinary_project_reads_the_same_with_and_without_a_block(tmp_path):
    """Components, nets and designators are the ordinary readings, unchanged."""
    plain = _project(tmp_path, _ordinary_lines(), name="plain.epro2")
    with_block = _one_block_project(tmp_path)

    def readings(path: Path):
        stats = ParseStats()
        model = build_project_model(path, parse_stats=stats)
        board = model.boards[0]
        return (
            {name: (part.value, part.lcsc_part) for name, part in board.components.items()},
            {name: sorted(designator for designator, _pin in net.pins)
             for name, net in board.nets.items()},
            collect_part_devices(path),
            stats.instances_without_designator,
        )

    plain_components, plain_nets, plain_devices, plain_unnamed = readings(plain)
    block_components, block_nets, block_devices, block_unnamed = readings(with_block)
    assert block_components == plain_components == {"C1": ("100nF", "")}
    assert block_devices == plain_devices == {"C1": ORD_DEV}
    assert block_unnamed == plain_unnamed == 0
    # the block adds no wire and no component, so the netlist is the ordinary one
    assert block_nets == plain_nets
    assert [row.identity_status for row in collect_block_instances(plain)] == []


# --------------------------------------------------------------------------
# 3. anchor 1 matched, anchor 2 did not: an open question, never a part
# --------------------------------------------------------------------------


def test_a_block_without_its_symbol_attribute_is_unresolved(tmp_path):
    path = _one_block_project(tmp_path, block_attrs=_block_attrs("blk1", None))
    (row,) = collect_block_instances(path)
    assert row.identity_status == BLOCK_UNRESOLVED
    assert row.identity_reason == BLOCK_SYMBOL_MISSING
    assert (row.local_symbol, row.symbol_attr) == ("", "")
    assert (row.source_symbol, row.source_cbb, row.title, row.ports) == ("", "", "", ())
    # not a verified block, not an ordinary part, and — the point of the batch —
    # no longer counted as an ordinary placement that lost its name
    stats = ParseStats()
    build_project_model(path, parse_stats=stats)
    assert stats.instances_without_designator == 0


def test_a_block_whose_symbol_names_another_document_is_unresolved(tmp_path):
    path = _one_block_project(tmp_path, block_attrs=_block_attrs("blk1", ORD_SYM))
    (row,) = collect_block_instances(path)
    assert row.identity_status == BLOCK_UNRESOLVED
    assert row.identity_reason == BLOCK_SYMBOL_MISMATCH
    # the disagreeing value is disclosed verbatim, and nothing is inferred from
    # the document it happens to name
    assert (row.symbol_attr, row.local_symbol, row.title) == (ORD_SYM, "", "")
    stats = ParseStats()
    build_project_model(path, parse_stats=stats)
    assert stats.instances_without_designator == 0


#: The page frame's template part id: declared by the frame's symbol document
#: **and** by a block document, which is the shape a CBB import leaves behind.
SHARED_PART = FRAME_PART
SHARED_BLOCK_SYM = "5e5e5e5e5e5e5e5e"


def _shared_part_id_project(tmp_path: Path, *, symbol: str | None,
                            name: str = "shared.epro2") -> Path:
    """One instance on a shared template id, with the ``Symbol`` the caller says.

    Two symbol documents declare ``SHARED_PART``: the frame's plain one (docType
    19) and a block one (docType 17). The frame itself binds to the plain one, so
    a page's frame is not an open question.
    """
    instance_attrs = []
    if symbol is not None:
        instance_attrs.append(_attr("blk1-sym", "blk1", "Symbol", symbol))
    instance_attrs.append(_attr("blk1-des", "blk1", "Designator", None))
    lines = _page(
        _attr("f-w", "frame", "Width", "1170"),
        _component("frame", SHARED_PART, 1, 0.0, 0.0, None),
        _attr("frame-sym", "frame", "Symbol", FRAME_SYM),
        _component("blk1", SHARED_PART, 20, 10.0, -10.0, 1),
        *instance_attrs,
    ) + _symbol_doc(FRAME_SYM, [SHARED_PART], doc_type=19, title="A4") + _symbol_doc(
        SHARED_BLOCK_SYM, [SHARED_PART], doc_type=17, title="SOME BLOCK",
        source=f"{SRC_SYM}|{SRC_CBB}",
    )
    return _project(tmp_path, lines, name=name)


@pytest.mark.parametrize(
    "symbol, reason",
    [
        (None, BLOCK_SYMBOL_MISSING),
        # a document that declares no such PART id at all: anchor 1 matched a
        # block, anchor 2 names something else
        ("6f6f6f6f6f6f6f6f", BLOCK_SYMBOL_MISMATCH),
    ],
)
def test_a_shared_part_id_with_a_block_still_opens_the_question(
    tmp_path, symbol, reason,
):
    """The contract is *the part id matched a block*, not *only one document does*.

    A shared template id is declared by a block document **and** plain ones at
    once, so a placement carrying it with no usable ``Symbol`` must not fall back
    to "just a part" silently — that is the unresolved case, reported, and never
    counted as a part that lost its designator.
    """
    path = _shared_part_id_project(tmp_path, symbol=symbol)
    (row,) = collect_block_instances(path)
    assert row.primitive_id == "blk1"
    assert row.identity_status == BLOCK_UNRESOLVED
    assert row.identity_reason == reason
    assert (row.local_symbol, row.source_symbol, row.source_cbb) == ("", "", "")
    stats = ParseStats()
    build_project_model(path, parse_stats=stats)
    assert stats.instances_without_designator == 0


def test_a_resolving_symbol_still_decides_when_the_part_id_is_shared(tmp_path):
    """A ``Symbol`` that resolves is not overruled by an open question elsewhere.

    Naming the plain document that declares the same id makes the placement an
    ordinary one (anchor 3 fails); naming the block document makes it a block.
    Both instances share one ``partId`` and do not share an identity.
    """
    plain = _shared_part_id_project(tmp_path, symbol=FRAME_SYM, name="plain.epro2")
    assert collect_block_instances(plain) == []

    block = _shared_part_id_project(
        tmp_path, symbol=SHARED_BLOCK_SYM, name="block.epro2",
    )
    (row,) = collect_block_instances(block)
    assert (row.identity_status, row.local_symbol, row.part_id) == (
        BLOCK_VERIFIED, SHARED_BLOCK_SYM, SHARED_PART,
    )
    assert (row.source_symbol, row.source_cbb) == (SRC_SYM, SRC_CBB)


# --------------------------------------------------------------------------
# 4. source: two segments or nothing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source, reason",
    [
        ("", BLOCK_SOURCE_EMPTY),
        (None, BLOCK_SOURCE_EMPTY),
        (SRC_SYM, BLOCK_SOURCE_MALFORMED),                       # one segment
        (f"{SRC_SYM}|{SRC_CBB}|{SRC_SYM}", BLOCK_SOURCE_MALFORMED),  # three
        (f"{SRC_SYM}|", BLOCK_SOURCE_MALFORMED),                 # empty second
        (f"|{SRC_CBB}", BLOCK_SOURCE_MALFORMED),                 # empty first
        (f"{SRC_SYM}| {SRC_CBB}", BLOCK_SOURCE_MALFORMED),       # padded second
        (f" {SRC_SYM}|{SRC_CBB}", BLOCK_SOURCE_MALFORMED),       # padded first
    ],
)
def test_an_unreadable_source_is_reported_not_guessed(tmp_path, source, reason):
    """A block with no readable ``META.source`` is still a block — but unsourced.

    The three anchors are what make it a block, so the row keeps its local
    symbol, title and ports and names no source at all: half a pair, a third
    segment, an empty or padded segment are all "not stated", never a guess.
    The two segments themselves are opaque — see the next test.
    """
    path = _project(tmp_path, _page(
        _component("blk1", BLOCK_PART, 20, 0.0, 0.0, 1),
        *_block_attrs("blk1"),
    ) + _block_doc(source=source))
    (row,) = collect_block_instances(path)
    assert row.identity_status == BLOCK_SOURCE_UNRESOLVED
    assert row.identity_reason == reason
    assert (row.source_symbol, row.source_cbb) == ("", "")
    assert (row.local_symbol, row.title) == (BLOCK_SYM, "BLK")


def test_source_segments_are_opaque_and_kept_verbatim(tmp_path):
    """No shape is imposed on either segment — they are identities, not formats.

    The container writes bare hex ids today, and this batch must not turn that
    measurement into a rule: a name-shaped id survives unchanged (no trimming, no
    lower-casing, no rejection), because the contract only says the field has two
    segments.
    """
    path = _project(tmp_path, _page(
        _component("blk1", BLOCK_PART, 20, 0.0, 0.0, 1),
        *_block_attrs("blk1"),
    ) + _block_doc(source="Local Block Symbol|Some CBB 2026"))
    (row,) = collect_block_instances(path)
    assert row.identity_status == BLOCK_VERIFIED
    assert (row.source_symbol, row.source_cbb) == (
        "Local Block Symbol", "Some CBB 2026",
    )


# --------------------------------------------------------------------------
# 5. identity is per instance, and labels do not decide it
# --------------------------------------------------------------------------


def test_one_part_id_two_instances_keeps_their_identities_apart(tmp_path):
    """Same ``partId`` on two placements: the ``Symbol`` decides each one.

    One instance names the block symbol, the other names a docType-2 symbol that
    declares the very same ``PART`` id. The first is a block; the second is an
    ordinary part (anchor 3 fails) and must not inherit the block's row.
    """
    lines = _page(
        _component("blk1", BLOCK_PART, 20, 10.0, -10.0, 1),
        *_block_attrs("blk1"),
        _component("blk2", BLOCK_PART, 21, 60.0, -10.0, 2),
        _attr("blk2-sym", "blk2", "Symbol", ORD_SYM),
        _attr("blk2-des", "blk2", "Designator", "C7"),
    ) + _block_doc() + _symbol_doc(
        ORD_SYM, [BLOCK_PART], doc_type=2, title="LOOKALIKE",
    )
    path = _project(tmp_path, lines)
    rows = collect_block_instances(path)
    assert [(row.primitive_id, row.local_symbol, row.x) for row in rows] == [
        ("blk1", BLOCK_SYM, 10.0),
    ]
    # both instances are on the page, and the ordinary one is a real component
    model = build_project_model(path)
    assert sorted(model.boards[0].components) == ["C7"]


def test_a_hand_filled_designator_and_reuse_block_change_nothing(tmp_path):
    """The measured block has all three fields empty — so none of them is a test.

    A user may type a designator onto a block, and a future editor may fill
    ``Reuse Block``: neither may flip the judgement, and — the 038Q17 audit's
    second finding — neither may turn the block into a model ``Component``. A
    block has no ``Device`` document and no library part behind it, so a typed
    label cannot make it one; the ordinary netlist stays the ordinary netlist.
    """
    attrs = [
        _attr("blk1-sym", "blk1", "Symbol", BLOCK_SYM),
        _attr("blk1-reuse", "blk1", "Reuse Block", "SOMETHING"),
        _attr("blk1-des", "blk1", "Designator", "CBB1"),
        _attr("blk1-name", "blk1", "Name", "typed name"),
    ]
    path = _project(tmp_path, _page(
        _component("blk1", BLOCK_PART, 20, 0.0, 0.0, 1),
        *attrs,
    ) + _block_doc())
    (row,) = collect_block_instances(path)
    assert row.identity_status == BLOCK_VERIFIED
    assert (row.source_symbol, row.local_symbol) == (SRC_SYM, BLOCK_SYM)
    assert (row.designator, row.reuse_block) == ("CBB1", "SOMETHING")

    stats = ParseStats()
    model = build_project_model(path, parse_stats=stats)
    # no component, no net, and no false "nameless part" signal either
    assert model.boards[0].components == {}
    assert model.boards[0].nets == {}
    assert stats.instances_without_designator == 0
    # and the block view still identifies it
    assert [r.primitive_id for r in collect_block_instances(path)] == ["blk1"]


def test_a_doc_type_17_string_is_not_the_block_number(tmp_path):
    """``META.docType`` must be the number ``17``, not the string ``"17"``."""
    path = _project(tmp_path, _page(
        _component("blk1", BLOCK_PART, 20, 0.0, 0.0, 1),
        *_block_attrs("blk1"),
    ) + _block_doc(doc_type="17"))
    assert collect_block_instances(path) == []


# --------------------------------------------------------------------------
# 6. the record-type drift that was not drift
# --------------------------------------------------------------------------


def test_table_and_universal_are_known_while_a_real_unknown_still_reports(tmp_path):
    assert {"TABLE", "UNIVERSAL"} <= KNOWN_RECORD_TYPES
    lines = _page(
        _record("TABLE", "t1", {"rows": 1}),
        _record("UNIVERSAL", "u1", {"option": True}),
        _record("MYSTERY", "m1", {"payload": 1}),
        _component("blk1", BLOCK_PART, 20, 0.0, 0.0, 1),
        *_block_attrs("blk1"),
    ) + _block_doc()
    path = _project(tmp_path, lines)
    stats = ParseStats()
    build_project_model(path, parse_stats=stats)
    assert stats.unknown_types == {"MYSTERY": 1}
    assert stats.records_by_type["TABLE"] == 1
    assert stats.records_by_type["UNIVERSAL"] == 1
    # and the blocker record types do not disturb the block reading
    assert [row.primitive_id for row in collect_block_instances(path)] == ["blk1"]


# --------------------------------------------------------------------------
# 7. one uuid, several copies: the block view reads the first and counts the rest
# --------------------------------------------------------------------------

#: A second part id, only used to prove that record order is not a difference.
SECOND_PART = "aaaabbbbccccdddd"


def _twice(tmp_path: Path, second: list[str], *, first: list[str] | None = None,
           name: str = "twice.epro2") -> Path:
    """A page with one block instance and the same symbol document written twice."""
    return _project(tmp_path, _page(
        _component("blk1", BLOCK_PART, 20, 0.0, 0.0, 1),
        *_block_attrs("blk1"),
    ) + (first if first is not None else _block_doc()) + second, name=name)


def test_the_first_copy_of_a_block_document_is_the_one_read(tmp_path):
    """Same uuid twice: ``META``, source and ports all come from the **first** copy.

    A V4 export copies a used symbol into every page that places it, so the block
    index (``META``/``source``/``PART`` ids) and the pin reader (ports) both meet
    that uuid more than once. Last-wins in one and first-wins in the other would
    build a row out of two documents — copy B's document type and source with
    copy A's pins — which is the bug this test pins.
    """
    second = _symbol_doc(
        BLOCK_SYM, [BLOCK_PART], doc_type=2, title="BLK",
        source="deadbeefdeadbeef|feedfacefeedface", tag="-2",
    )
    path = _twice(tmp_path, second)
    (row,) = collect_block_instances(path)
    assert (row.identity_status, row.title, row.source_symbol, row.source_cbb) == (
        BLOCK_VERIFIED, "BLK", SRC_SYM, SRC_CBB,
    )
    stats = ParseStats()
    model = build_project_model(path, parse_stats=stats)
    # one differing copy -> one count, and neither the false nameless signal nor a
    # component invented out of it
    assert stats.conflicting_library_documents == 1
    assert stats.instances_without_designator == 0
    assert model.boards[0].components == {}


def test_identical_and_reordered_copies_add_no_conflict(tmp_path):
    """A copy that says the same thing is not a conflict — record order included."""
    same = _twice(tmp_path, _block_doc(tag="-2"), name="same.epro2")
    stats = ParseStats()
    build_project_model(same, parse_stats=stats)
    assert stats.conflicting_library_documents == 0
    (row,) = collect_block_instances(same)
    assert (row.identity_status, row.source_symbol) == (BLOCK_VERIFIED, SRC_SYM)

    reordered = _twice(
        tmp_path,
        _symbol_doc(BLOCK_SYM, [SECOND_PART, BLOCK_PART], doc_type=17, title="BLK",
                    source=f"{SRC_SYM}|{SRC_CBB}", tag="-2"),
        first=_symbol_doc(BLOCK_SYM, [BLOCK_PART, SECOND_PART], doc_type=17,
                          title="BLK", source=f"{SRC_SYM}|{SRC_CBB}"),
        name="reordered.epro2",
    )
    stats = ParseStats()
    build_project_model(reordered, parse_stats=stats)
    assert stats.conflicting_library_documents == 0
    assert [r.identity_status for r in collect_block_instances(reordered)] == [
        BLOCK_VERIFIED,
    ]


def test_a_pin_only_difference_stays_with_the_pin_reader(tmp_path):
    """The new comparison must not double-count what ``_collect_symbols`` counts.

    The two copies agree on title, document type, source and part ids and differ
    only in their pins: the document view counts nothing, the existing pin reader
    counts the one conflict, and the row's ports are the first copy's.
    """
    path = _twice(
        tmp_path,
        _block_doc(tag="-2", pins=(
            ("1", "IN", "Input", -100.0, 0.0),
            ("2", "OUT", "Output", 100.0, 0.0),
        )),
        first=_block_doc(pins=(("1", "IN", "Input", -100.0, 0.0),)),
        name="pins.epro2",
    )
    stats = ParseStats()
    build_project_model(path, parse_stats=stats)
    assert stats.conflicting_library_documents == 1
    (row,) = collect_block_instances(path)
    assert [port.number for port in row.ports] == ["1"]
