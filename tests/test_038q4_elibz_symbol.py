"""038Q4: the single-symbol `.elibz2` reader, and the negative control it exists for.

The container shape is the one measured on 2026-11-11 (`outputs/review/038q3/`):
an `.elibz2` ZIP with one ``.elibu`` stream and one ``symbol2.json``, where the
stream writes the **same** ``SYMBOL`` ``DOCHEAD`` twice — ``META`` in the first
segment, ``CANVAS``/``PART``/``RECT``/``PIN``/``ATTR`` in the second — and names
each pin's attributes through ``parentId == <PIN row id>``.

Every stream below is synthesised here from that shape (no real project, no
upstream free text), so the file carries no fixture this batch did not write.

The first test is the one that matters: the **same** stream through the project
reader still reads a correct body box with **0 pins** (first-wins per uuid picks
the ``META``-only copy), while the new reader reads all four. That gap is what
the batch exists to close, and it is pinned before any of the new code's own
behaviour is.
"""

from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path

import pytest

from boardwise.parsers.elibz import Elibz2Error, load_elibz2_symbol
from boardwise.parsers.schematic import collect_symbol_details

SYMBOL = "0a1b2c3d4e5f60718293a4b5c6d7e8f9"
LIBRARY = "f0e1d2c3b4a5968778695a4b3c2d1e0f"
TITLE = "DEMO-1117-3.3"
CLIENT = "test-client"

#: The four pins of the measured symbol, in file coordinates: ``(number, name,
#: x, y)``. Pin 2 and pin 4 are both ``VOUT`` — that is the measured part, and
#: it is also why "two pins sharing a name" must not be treated as a duplicate.
PINS = (
    ("1", "GND", -45, -10),
    ("2", "VOUT", -45, 0),
    ("3", "VIN", -45, 10),
    ("4", "VOUT", 45, 0),
)


def _line(kind: str, ticket: int, ident: str, body: dict | None) -> str:
    envelope = {"type": kind, "ticket": ticket, "id": ident, "client": CLIENT}
    payload = "" if body is None else json.dumps(body)
    return f"{json.dumps(envelope)}||{payload}|"


def _head(*, doc_type: str = "SYMBOL", uuid: str = SYMBOL,
          edit_version: str = "4.1.93") -> str:
    body = {
        "docType": doc_type,
        "client": CLIENT,
        "uuid": uuid,
        "updateTime": 1794382137948,
        "version": str(1794382137948),
        "editVersion": edit_version,
        "user": {},
    }
    return f'{{"type":"DOCHEAD"}}||{json.dumps(body)}|'


def _body_records(
    *, pins=PINS, pin_id_prefix: str = "e",
) -> list[str]:
    """The second segment: canvas, part, one rect, the pins and their attrs."""
    out = [
        _line("CANVAS", 1, "CANVAS", {"originX": 0, "originY": 0}),
        _line("PART", 2, "pid1", {"BBOX": [-35, -20, 35, 20], "title": ""}),
        _line(
            "RECT", 3, "r0",
            {"partId": "pid1", "zIndex": 1, "dotX1": -35, "dotY1": -20,
             "dotX2": 35, "dotY2": 20, "radiusX": 0, "radiusY": 0,
             "strokeWidth": 1},
        ),
    ]
    ticket = 4
    for index, (number, name, x, y) in enumerate(pins):
        ident = f"{pin_id_prefix}{index}"
        out.append(_line("PIN", ticket, ident,
                         {"partId": "pid1", "zIndex": 3 + index * 4,
                          "x": x, "y": y, "length": 10, "rotation": 0}))
        for key, value, offset in (
            ("Pin Name", name, 0),
            ("Pin Number", number, 1),
            ("Pin Type", "Undefined", 2),
        ):
            out.append(_line("ATTR", ticket + offset + 1, f"{ident}a{offset}",
                             {"partId": "pid1", "parentId": ident, "key": key,
                              "value": value}))
        ticket += 4
    out.append(_line("ATTR", ticket, "e18", {"partId": "pid1", "parentId": "",
                                             "key": "Name", "value": TITLE}))
    out.append(_line("ATTR", ticket + 1, "e19", {"partId": "pid1", "parentId": "",
                                                 "key": "Designator", "value": "U?"}))
    return out


def _stream(
    *, heads: int = 2, meta_title: str = TITLE, second_head: str | None = None,
    body_records: list[str] | None = None,
) -> str:
    """The measured two-head shape: ``META`` first, the body after the repeat."""
    lines = [_head(), _line("META", 1, "META", {"title": meta_title, "docType": 2,
                                                "source": ""})]
    for _ in range(max(heads - 1, 0)):
        lines.append(second_head if second_head is not None else _head())
    lines.extend(body_records if body_records is not None else _body_records())
    return "\n".join(lines) + "\n"


def _manifest(
    *, symbol: str = SYMBOL, path: str = LIBRARY, title: str = TITLE,
    extra_symbols: dict | None = None, doc_type: int = 2, devices=None,
) -> str:
    symbols = {
        symbol: {
            "uuid": symbol,
            "path": path,
            "ticket": 8,
            "title": title.lower(),
            "display_title": title,
            "docType": doc_type,
        }
    }
    if extra_symbols:
        symbols.update(extra_symbols)
    return json.dumps({"devices": devices or {}, "symbols": symbols,
                       "footprints": {}, "panelLibs": {}})


def _archive(
    target: Path,
    *,
    stream: str | None = None,
    manifest: str | None = None,
    stream_name: str = "ProLib_pc_test.elibu",
    members: list[tuple[str, bytes]] | None = None,
    compression: int = zipfile.ZIP_DEFLATED,
) -> Path:
    """Write ``target`` as an ``.elibz2`` container."""
    with zipfile.ZipFile(target, "w", compression) as archive:
        for name, payload in members or [
            (stream_name, (stream if stream is not None else _stream()).encode("utf-8")),
            ("symbol2.json",
             (manifest if manifest is not None else _manifest()).encode("utf-8")),
        ]:
            archive.writestr(name, payload)
    return target


def _project(target: Path, stream: str) -> Path:
    """The same stream wrapped as a project archive — the legacy path's input."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("demo.epru", stream.encode("utf-8"))
    return target


def _read(path: Path, *, symbol: str = SYMBOL, library: str = LIBRARY):
    return load_elibz2_symbol(path, symbol_uuid=symbol, library_uuid=library)


def _attr(parent: str, key: str, value: str, ident: str) -> str:
    return _line("ATTR", 99, ident,
                 {"partId": "pid1", "parentId": parent, "key": key, "value": value})


def _drop(records: list[str], parent: str, key: str) -> list[str]:
    """The records minus one pin attribute — the pin then has no such key."""
    kept = [line for line in records
            if not (f'"parentId": "{parent}"' in line and f'"key": "{key}"' in line)]
    assert len(kept) == len(records) - 1
    return kept


def _insert_after(records: list[str], parent: str, key: str, line: str) -> list[str]:
    """``line`` right after one pin attribute, so the open run is still that pin."""
    out: list[str] = []
    done = False
    for item in records:
        out.append(item)
        if not done and f'"parentId": "{parent}"' in item and f'"key": "{key}"' in item:
            out.append(line)
            done = True
    assert done
    return out


# ------------------------------------------------------- the negative control


def test_the_project_reader_reads_zero_pins_where_the_new_reader_reads_four(tmp_path):
    """The measured failure, pinned: same stream, two readers, 0 pins against 4.

    This is the batch's reason to exist, so it is asserted before anything the
    new module claims about itself: the old path is **not** changed by 038Q4, and
    a future "cleanup" that merged repeated heads globally would turn this test
    red at exactly the place that must stay still.
    """
    stream = _stream()
    project = collect_symbol_details(_project(tmp_path / "demo.epro2", stream))
    legacy = project[SYMBOL]
    assert legacy.offsets == {}, "first-wins keeps the META-only copy: no pins"
    assert legacy.body == (-35.0, -20.0, 35.0, 20.0), "the body still reads"

    read = _read(_archive(tmp_path / "demo.elibz2", stream=stream))
    assert read.detail.offsets != {}, "the new reader must not inherit that gap"
    assert len(read.detail.offsets) == 4
    assert read.symbol_profile().pin_numbers() == ["1", "2", "3", "4"]


def test_an_old_project_archive_with_two_definitions_keeps_the_first(tmp_path):
    """The same-uuid first-wins rule of a **project** archive is untouched.

    Two copies of one uuid that disagree are a real disagreement in a project:
    the first stays, the second is counted, and neither is merged into the
    other. 038Q4's continuation merge belongs to the single-symbol container
    only — this is the anchor that says so.
    """
    first = [line for line in _body_records(pins=PINS[:1], pin_id_prefix="a")
             if '"PIN"' in line or '"Pin Number"' in line or '"Pin Name"' in line
             or '"Pin Type"' in line]
    other = _body_records(pins=PINS[1:3], pin_id_prefix="q")
    stream = "\n".join(
        [_head(), _line("META", 1, "META", {"title": TITLE}),
         _line("RECT", 3, "r0", {"dotX1": -35, "dotY1": -20, "dotX2": 35, "dotY2": 20}),
         *first,
         _head(), _line("META", 1, "META", {"title": TITLE}), *other]
    ) + "\n"
    detail = collect_symbol_details(_project(tmp_path / "two.epro2", stream))[SYMBOL]
    assert sorted(detail.offsets) == ["1"], "the first definition wins, unmerged"
    assert detail.pin_names == {"1": "GND"}
    assert detail.body == (-35.0, -20.0, 35.0, 20.0)


# ------------------------------------------------------------ the happy path


def test_the_measured_shape_maps_to_the_expected_pins_and_body(tmp_path):
    profile = _read(_archive(tmp_path / "demo.elibz2")).symbol_profile()

    assert profile.title == TITLE
    assert profile.body == (-35.0, -20.0, 35.0, 20.0)
    by_number = {pin.number: pin for pin in profile.pins}
    assert by_number["1"].tip == (-45.0, 10.0) and by_number["1"].direction == "left"
    assert by_number["2"].tip == (-45.0, 0.0) and by_number["2"].direction == "left"
    assert by_number["3"].tip == (-45.0, -10.0) and by_number["3"].direction == "left"
    assert by_number["4"].tip == (45.0, 0.0) and by_number["4"].direction == "right"
    assert [pin.name for pin in profile.pins] == ["GND", "VOUT", "VIN", "VOUT"]
    assert by_number["1"].electrical_role == "GND"
    assert by_number["3"].electrical_role == "VIN"
    assert by_number["2"].electrical_role == "VOUT"
    assert by_number["4"].electrical_role == "VOUT"


def test_the_profile_states_the_gaps_it_inherits_instead_of_hiding_them(tmp_path):
    """No field grows in this batch; the notes still say what is missing."""
    profile = _read(_archive(tmp_path / "demo.elibz2")).symbol_profile()
    joined = " ".join(profile.notes)
    assert "pin length: not available" in joined, "length is still not carried"
    assert "rotation" in joined and "SymbolDetail" in joined, (
        "the derived direction must not be passed off as the row's rotation"
    )
    assert "pin_id" in joined, "the pin key this container uses is named"
    assert "2 SYMBOL DOCHEAD(s)" in joined, "the merge is disclosed, not silent"
    assert profile.texts == []
    assert all(pin.length is None for pin in profile.pins), "no length is invented"


def test_a_second_read_of_the_same_file_is_byte_identical(tmp_path):
    path = _archive(tmp_path / "demo.elibz2")
    one, two = _read(path), _read(path)
    assert one.symbol_profile().geometry_hash() == two.symbol_profile().geometry_hash()
    assert (json.dumps(one.symbol_profile().to_jsonable(), sort_keys=True)
            == json.dumps(two.symbol_profile().to_jsonable(), sort_keys=True))


def test_the_source_carries_the_archive_hash_and_no_host_path(tmp_path):
    path = _archive(tmp_path / "demo.elibz2")
    read = _read(path)
    profile = read.symbol_profile()
    assert profile.source == f"elibz2:{SYMBOL}:sha256:{read.archive_sha256}"
    assert str(tmp_path) not in profile.source
    assert read.stream_member == "ProLib_pc_test.elibu"
    assert read.editor_version == "4.1.93"
    assert read.symbol_head_count == 2
    assert read.stream_sha256 and read.stream_sha256 != read.archive_sha256


def test_one_head_stream_is_read_the_same_way(tmp_path):
    """The merge is not the mechanism: a single-head stream reads identically."""
    one = _read(_archive(tmp_path / "one.elibz2", stream=_stream(heads=1)))
    assert one.symbol_head_count == 1
    assert sorted(one.detail.offsets) == ["1", "2", "3", "4"]


# ---------------------------------------------------- identity and manifest


def test_a_wrong_symbol_uuid_is_refused(tmp_path):
    path = _archive(tmp_path / "demo.elibz2")
    with pytest.raises(Elibz2Error, match="does not list symbol"):
        _read(path, symbol="f" * 32)


def test_a_wrong_library_uuid_is_refused(tmp_path):
    path = _archive(tmp_path / "demo.elibz2")
    with pytest.raises(Elibz2Error, match="library identity mismatch"):
        _read(path, library="e" * 32)


def test_an_extra_symbol_in_the_manifest_is_refused(tmp_path):
    path = _archive(tmp_path / "demo.elibz2", manifest=_manifest(extra_symbols={
        "9" * 32: {"uuid": "9" * 32, "path": LIBRARY, "display_title": "OTHER",
                   "docType": 2}}))
    with pytest.raises(Elibz2Error, match="more than the requested symbol"):
        _read(path)


def test_a_manifest_that_is_not_a_symbol_is_refused(tmp_path):
    with pytest.raises(Elibz2Error, match="not a symbol"):
        _read(_archive(tmp_path / "d.elibz2", manifest=_manifest(doc_type=1)))


def test_devices_in_the_manifest_are_refused_not_picked(tmp_path):
    path = _archive(tmp_path / "demo.elibz2", manifest=_manifest(
        devices={"a" * 32: {"uuid": "a" * 32}}))
    with pytest.raises(Elibz2Error, match="devices content"):
        _read(path)


def test_a_title_that_disagrees_between_manifest_and_stream_is_refused(tmp_path):
    path = _archive(tmp_path / "demo.elibz2",
                    manifest=_manifest(title="SOMETHING-ELSE"))
    with pytest.raises(Elibz2Error, match="title mismatch"):
        _read(path)


def test_both_uuids_are_required(tmp_path):
    path = _archive(tmp_path / "demo.elibz2")
    with pytest.raises(Elibz2Error, match="required"):
        load_elibz2_symbol(path, symbol_uuid="", library_uuid=LIBRARY)
    with pytest.raises(Elibz2Error, match="required"):
        load_elibz2_symbol(path, symbol_uuid=SYMBOL, library_uuid="  ")


# ---------------------------------------------------------------- the stream


@pytest.mark.parametrize(
    ("second_head", "match"),
    [
        (_head(doc_type="SCH_PAGE"), "not a SYMBOL document"),
        (_head(uuid="1" * 32), "not the"),
        (_head(edit_version="4.1.94"), "different body"),
    ],
)
def test_a_head_that_is_not_an_identical_repeat_is_refused(tmp_path, second_head, match):
    path = _archive(tmp_path / "demo.elibz2",
                    stream=_stream(second_head=second_head))
    with pytest.raises(Elibz2Error, match=match):
        _read(path)


def test_a_stream_without_a_head_is_refused(tmp_path):
    path = _archive(tmp_path / "demo.elibz2",
                    stream="\n".join(_body_records()) + "\n")
    with pytest.raises(Elibz2Error, match="before the first DOCHEAD|no DOCHEAD"):
        _read(path)


def test_a_repeated_element_id_is_refused_not_overwritten(tmp_path):
    """Same id twice: an identical body is the same record, a different one is a
    later write. Neither is allowed to overwrite — the differing body is refused."""
    doubled = _body_records()
    twin = [line for line in doubled if '"PIN"' in line][0]
    same = _archive(tmp_path / "same.elibz2",
                    stream=_stream(body_records=[*doubled, twin]))
    with pytest.raises(Elibz2Error, match="PIN record id"):
        _read(same)

    moved = twin.replace('"x": -45', '"x": -50')
    assert moved != twin
    different = _archive(tmp_path / "moved.elibz2",
                         stream=_stream(body_records=[*doubled, moved]))
    with pytest.raises(Elibz2Error, match="appears twice with different bodies"):
        _read(different)


def test_two_pins_with_one_number_are_refused(tmp_path):
    records = [line.replace('"value": "2"', '"value": "1"')
               for line in _body_records()]
    path = _archive(tmp_path / "demo.elibz2",
                    stream=_stream(body_records=records))
    with pytest.raises(Elibz2Error, match="used by two PIN"):
        _read(path)


def test_a_pin_without_a_number_is_refused(tmp_path):
    records = [line for line in _body_records()
               if '"Pin Number"' not in line or '"value": "3"' not in line]
    path = _archive(tmp_path / "demo.elibz2",
                    stream=_stream(body_records=records))
    with pytest.raises(Elibz2Error, match="carry no Pin Number"):
        _read(path)


def test_a_pin_number_filed_against_no_pin_is_refused(tmp_path):
    records = [line.replace('"parentId": "e1"', '"parentId": "ghost"')
               for line in _body_records()]
    path = _archive(tmp_path / "demo.elibz2",
                    stream=_stream(body_records=records))
    with pytest.raises(Elibz2Error, match="no PIN"):
        _read(path)


def test_an_orphan_pin_name_is_refused_not_handed_to_the_next_pin(tmp_path):
    """A dangling ``Pin Name`` parent is the fallback trap, and it is visible.

    Pin 1's own name is removed and a ``Pin Name`` whose parent names no pin is
    written after pin 1's other attributes. The project collector has no
    ``parentId`` to file it by and hands it to the **open run** — pin 1 — so the
    legacy path reports a name the file never gave that pin. The new reader
    refuses instead, which is the only answer that is not an invented fact.
    """
    records = _drop(_body_records(), "e0", "Pin Name")
    records = _insert_after(records, "e0", "Pin Type",
                            _attr("ghost", "Pin Name", "LEAK", "orphan1"))
    legacy = collect_symbol_details(
        _project(tmp_path / "orphan.epro2", _stream(heads=1, body_records=records))
    )[SYMBOL]
    assert legacy.pin_names["1"] == "LEAK", "the fallback invents that name"

    path = _archive(tmp_path / "orphan.elibz2", stream=_stream(body_records=records))
    with pytest.raises(Elibz2Error, match="no PIN record of this symbol"):
        _read(path)


def test_two_pin_types_for_one_pin_are_refused_not_retyped_elsewhere(tmp_path):
    """Pin 2's type is removed and pin 1 gets a second ``Pin Type``.

    The duplicate cannot overwrite pin 1's own type, so the collector's fallback
    carries it to the next unnamed run — pin 2 — and the symbol ends up with a
    type nobody wrote for it. The reader refuses the duplicate pair instead.
    """
    records = _drop(_body_records(), "e1", "Pin Type")
    records = _insert_after(records, "e1", "Pin Number",
                            _attr("e0", "Pin Type", "Input", "dupT"))
    legacy = collect_symbol_details(
        _project(tmp_path / "dup.epro2", _stream(heads=1, body_records=records))
    )[SYMBOL]
    assert legacy.pin_types["1"] == "Undefined"
    assert legacy.pin_types["2"] == "Input", "the duplicate is retyped onto pin 2"

    path = _archive(tmp_path / "dup.elibz2", stream=_stream(body_records=records))
    with pytest.raises(Elibz2Error, match="two Pin Type attributes"):
        _read(path)


def test_a_malformed_record_is_refused_rather_than_skipped(tmp_path):
    stream = _stream().replace(_line("CANVAS", 1, "CANVAS", {"originX": 0,
                                                             "originY": 0}),
                               "not a record at all")
    path = _archive(tmp_path / "demo.elibz2", stream=stream)
    with pytest.raises(Elibz2Error, match="unparseable"):
        _read(path)


# ------------------------------------------------------------- the container


def test_a_file_that_is_not_a_zip_is_refused(tmp_path):
    path = tmp_path / "not.elibz2"
    path.write_bytes(b"PK\x03\x04 truncated nonsense")
    with pytest.raises(Elibz2Error, match="not a readable ZIP"):
        _read(path)


def test_an_empty_file_is_refused(tmp_path):
    path = tmp_path / "empty.elibz2"
    path.write_bytes(b"")
    with pytest.raises(Elibz2Error, match="empty"):
        _read(path)


def test_an_extra_member_is_refused(tmp_path):
    path = _archive(tmp_path / "demo.elibz2", members=[
        ("ProLib_pc_test.elibu", _stream().encode()),
        ("symbol2.json", _manifest().encode()),
        ("notes.txt", b"hello"),
    ])
    with pytest.raises(Elibz2Error, match="members this single-symbol"):
        _read(path)


def test_two_streams_are_refused(tmp_path):
    path = _archive(tmp_path / "demo.elibz2", members=[
        ("a.elibu", _stream().encode()),
        ("b.elibu", _stream().encode()),
        ("symbol2.json", _manifest().encode()),
    ])
    with pytest.raises(Elibz2Error, match="exactly one"):
        _read(path)


def test_a_repeated_member_name_is_refused(tmp_path):
    path = tmp_path / "dup.elibz2"
    with pytest.warns(UserWarning), zipfile.ZipFile(path, "w") as archive:
        archive.writestr("symbol2.json", _manifest())
        archive.writestr("symbol2.json", _manifest())
        archive.writestr("ProLib_pc_test.elibu", _stream())
    with pytest.raises(Elibz2Error, match="repeats a member name"):
        _read(path)


@pytest.mark.parametrize("name", ["../escape.elibu", "/abs.elibu", "C:/x.elibu",
                                  "sub\\dir.elibu"])
def test_a_member_path_that_escapes_the_archive_is_refused(tmp_path, name):
    path = _archive(tmp_path / "demo.elibz2", members=[
        (name, _stream().encode()),
        ("symbol2.json", _manifest().encode()),
    ])
    with pytest.raises(Elibz2Error, match="member path|absolute|traversal"):
        _read(path)


def test_an_encrypted_member_is_refused(tmp_path):
    path = tmp_path / "enc.elibz2"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ProLib_pc_test.elibu", _stream())
        archive.writestr("symbol2.json", _manifest())
    raw = path.read_bytes()
    # Flip the "encrypted" flag on every local header — what a password-protected
    # export declares — and keep the rest of the bytes intact. zipfile reads
    # ``flag_bits`` off the central directory, so both records are patched.
    patched = bytearray(raw)
    for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        start = 0
        while True:
            index = patched.find(signature, start)
            if index < 0:
                break
            flags = struct.unpack_from("<H", patched, index + offset)[0] | 0x1
            struct.pack_into("<H", patched, index + offset, flags)
            start = index + 4
    path.write_bytes(bytes(patched))
    with pytest.raises(Elibz2Error, match="encrypted"):
        _read(path)


def test_a_crc_failure_is_refused(tmp_path):
    """A damaged member is refused by its CRC, not decoded into a wrong part."""
    stream = _stream().encode()
    path = tmp_path / "crc.elibz2"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("ProLib_pc_test.elibu", stream)
        archive.writestr("symbol2.json", _manifest())
    raw = bytearray(path.read_bytes())
    needle = b'"Pin Number"'
    index = raw.find(needle)
    assert index > 0
    raw[index + len(needle) - 1] = ord("x")
    path.write_bytes(bytes(raw))
    with pytest.raises(Elibz2Error, match="CRC"):
        _read(path)


def test_a_manifest_that_is_not_json_is_refused(tmp_path):
    path = _archive(tmp_path / "demo.elibz2", manifest="{not json")
    with pytest.raises(Elibz2Error, match="not JSON"):
        _read(path)
