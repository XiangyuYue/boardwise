"""038: the eprj3 folder format, read-only (tier A) — and V3 untouched.

The container seam is one function (`load_epru_text`), so these tests are about
three things and nothing else: the folder reader glues the pages into the stream
every consumer already reads, the `yAxisDirection` transform puts an `up` file back
into the frame V3 uses (both branches), and the PIN-attribute key is the one the
file's own format uses (eprj3: the PIN row's `id`; V3: the synthesised
`e<zIndex>` — the V3 fixtures are the arbiter, and they are 12 rows away from
being the same key).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.parsers import eprj3
from boardwise.parsers.epru_stream import load_epru_text
from boardwise.parsers.schematic import (
    _collect_symbols,
    _pin_key_for,
    build_schematic_model,
)

FIXTURE = Path("tests/fixtures/eprj3_synth")


# --------------------------------------------------------------------------
# a builder, so a test can make the variants (up / no-canvas) it needs
# --------------------------------------------------------------------------


def _record(envelope: dict, body: dict | None = None) -> str:
    head = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    return head + "|||" if body is None else (
        head + "||" + json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "|"
    )


def _symbol(uuid: str, title: str, pins: list[tuple[str, float, float]],
            names: list[str] | None = None) -> list[str]:
    out = [_record({"type": "DOCHEAD"},
                   {"docType": "SYMBOL", "uuid": uuid, "editVersion": "2.3.0"}),
           _record({"type": "META", "id": "META"}, {"title": title, "docType": "SYMBOL"})]
    for index, (number, x, y) in enumerate(pins):
        pin_id = f"e{index + 1}"
        out.append(_record({"type": "PIN", "id": pin_id},
                           {"x": x, "y": y, "zIndex": index + 2}))
        out.append(_record({"type": "ATTR", "id": f"n{index}"},
                           {"parentId": pin_id, "key": "Pin Number", "value": number}))
        if names is not None:
            out.append(_record({"type": "ATTR", "id": f"m{index}"},
                               {"parentId": pin_id, "key": "Pin Name",
                                "value": names[index]}))
        out.append(_record({"type": "ATTR", "id": f"t{index}"},
                           {"parentId": pin_id, "key": "Pin Type", "value": "1"}))
    return out


def _page(*, y_up: bool, canvas: bool = True) -> list[str]:
    marker = {"yAxisDirection": "up"} if y_up else {}
    sign = -1.0 if y_up else 1.0

    def y(value: float) -> float:
        return sign * value

    out = [_record({"type": "DOCHEAD", **marker},
                   {"docType": "SCH_PAGE", "uuid": "page-1"})]
    if canvas:
        body = {"originX": 0, "originY": y(0), "unit": "0.01inch"}
        if y_up:
            body["yAxisDirection"] = "up"
        out.append(_record({"type": "CANVAS", **marker}, body))
    out += _symbol("sym-1", "R", [("1", 0.0, 0.0), ("2", 20.0, 0.0)])
    for name, part, x in (("U1", "inst-u1", 300.0), ("U2", "inst-u2", 400.0)):
        out.append(_record({"type": "COMPONENT", "id": f"c-{part}", **marker},
                           {"partId": part, "x": x, "y": y(-500.0), "rotation": 0,
                            "isMirror": False, "zIndex": 10}))
        out.append(_record({"type": "ATTR", "id": f"d-{part}"},
                           {"parentId": part, "key": "Designator", "value": name}))
        out.append(_record({"type": "ATTR", "id": f"s-{part}"},
                           {"parentId": part, "key": "Symbol", "value": "sym-1"}))
    out.append(_record({"type": "WIRE", "id": "grp-1", **marker}, {"zIndex": 40}))
    out.append(_record({"type": "LINE", **marker},
                       {"lineGroup": "grp-1", "startX": 300.0, "startY": y(-500.0),
                        "endX": 400.0, "endY": y(-500.0)}))
    out.append(_record({"type": "ATTR", "id": "net-1"},
                       {"parentId": "grp-1", "key": "NET", "value": "SIG_A"}))
    return out


def _index(root: Path) -> None:
    (root / "synth.eprj3").write_text(json.dumps({
        "name": "synth",
        "owner_uuid": "0123456789abcdef0123456789abcdef",
        "format": "folder",
        "profile": {"schematics": {}, "sheets": {}, "pcbs": {}},
    }, ensure_ascii=False), encoding="utf-8")


def _write(root: Path, *, y_up: bool = False, canvas: bool = True) -> Path:
    page_dir = root / "sch" / "Schematic1"
    page_dir.mkdir(parents=True, exist_ok=True)
    _index(root)
    (page_dir / "P1.esch2").write_text(
        "\n".join(_page(y_up=y_up, canvas=canvas)) + "\n", encoding="utf-8")
    return root


# --------------------------------------------------------------------------
# 1. the container: a folder becomes the one stream everything already reads
# --------------------------------------------------------------------------


def test_a_folder_project_loads_as_one_record_stream():
    text, meta = load_epru_text(FIXTURE)
    assert meta["format"] == "eprj3"
    assert meta["name"] == "eprj3_synth"
    assert meta["owner_uuid"] == "0123456789abcdef0123456789abcdef"
    assert meta["pages"] == ["P1"]
    assert '"docType":"SCH_PAGE"' in text and '"docType":"SYMBOL"' in text
    assert text.count('{"type":"DOCHEAD"}') >= 2, (
        "each page file is its own stream and every one carries its DOCHEAD"
    )


def test_a_folder_without_pages_is_refused_by_name(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    (root / "empty.eprj3").write_text("{}", encoding="utf-8")
    with pytest.raises(Exception) as caught:
        load_epru_text(root)
    assert "no schematic page" in str(caught.value)


def test_a_folder_without_an_index_is_not_a_folder_project(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    (root / "readme.txt").write_text("x", encoding="utf-8")
    assert eprj3.looks_like_eprj3(root) is False


# --------------------------------------------------------------------------
# 2. the model: absolute assertions on the synthetic fixture
# --------------------------------------------------------------------------


def test_the_synthetic_page_builds_the_model_it_was_written_to_be():
    model = build_schematic_model(FIXTURE)
    assert sorted(model.components) == ["U1", "U2"]
    assert [(pin.number, pin.net) for pin in model.components["U1"].pins] == [
        ("1", "SIG_A"), ("2", "NET1")]
    assert model.nets["SIG_A"].pins == [("U1", "1"), ("U2", "1")]
    assert model.duplicate_designators == []


def _fingerprint(path) -> tuple:
    """The model **and the geometry** as data the two frames must agree on.

    The layout matters here: a missing y-flip leaves every connectivity fact
    intact and moves every part, so a fingerprint that only compared components
    and nets would pass the very mutant this pair of fixtures exists for.
    """
    from boardwise.parsers.schematic import collect_page_layout

    layout = collect_page_layout(path)
    model = build_schematic_model(path)
    return (
        tuple(sorted(
            (name, comp.value,
             tuple((pin.number, pin.name, pin.net) for pin in comp.pins))
            for name, comp in model.components.items()
        )),
        tuple(sorted((net, tuple(node.pins)) for net, node in model.nets.items())),
        tuple(model.duplicate_designators),
        tuple(sorted(
            (item.designator, round(item.x, 3), round(item.y, 3), round(item.rotation, 3))
            for item in (layout.parts or [])
        )),
        tuple(sorted(
            (run.group, run.net,
             tuple((round(point[0], 3), round(point[1], 3)) for point in run.points))
            for run in (layout.wires or [])
        )),
    )


def test_y_axis_up_reads_the_same_board_as_the_default_frame(tmp_path):
    """The spec's marker: `up` files are cartesian, so the reader flips y back.

    The two fixtures describe the *same* board in the two frames — the `up` one
    has every schematic y negated — so the model they build has to be identical.
    Without the flip the parts land mirrored about the page centre and the wire
    misses both pins, which is exactly the mutant this test is here to catch.
    """
    down = _write(tmp_path / "down")
    up = _write(tmp_path / "up", y_up=True)
    assert _fingerprint(down) == _fingerprint(up)


def test_a_missing_marker_and_a_down_marker_mean_the_same_thing(tmp_path):
    """The spec: a missing `yAxisDirection` is `down` — not a third state."""
    plain = _write(tmp_path / "plain")
    plain = _write(tmp_path / "plain")
    down = _write(tmp_path / "down")
    assert _fingerprint(plain) == _fingerprint(down)


def test_only_the_literal_up_flips_and_the_marker_is_stripped(tmp_path):
    text = _page(y_up=False)[0]
    marked = text.replace('"type":"DOCHEAD"', '"type":"DOCHEAD","yAxisDirection":"up"', 1)
    flipped = eprj3.flip_line(marked)
    assert "yAxisDirection" not in flipped
    body = json.loads(flipped.split("||", 1)[1][:-1])
    unchanged = json.loads(text.split("||", 1)[1][:-1])
    assert {key: value for key, value in body.items() if key != "yAxisDirection"} == unchanged

    other = text.replace('"type":"DOCHEAD"', '"type":"DOCHEAD","yAxisDirection":"cloud"', 1)
    assert "yAxisDirection" not in eprj3.flip_line(other)


def test_amplitude_fields_are_never_flipped(tmp_path):
    """Only coordinates flip: `height`/`radius`/`rotation` are symmetric."""
    line = _record({"type": "CIRCLE", "yAxisDirection": "up"},
                   {"centerY": 100, "radius": 25, "rotation": 30, "height": 12,
                    "text": {"y": 130, "content": "hi"}})
    body = json.loads(eprj3.flip_line(line).split("||", 1)[1][:-1])
    assert body["centerY"] == -100 and body["text"]["y"] == -130
    assert body["radius"] == 25 and body["rotation"] == 30 and body["height"] == 12


def test_a_schematic_section_without_canvas_is_tolerated(tmp_path):
    """Measured on the official example: the SCH_PAGE section carries no CANVAS."""
    root = _write(tmp_path / "nocanvas", y_up=False, canvas=False)
    assert '"type":"CANVAS"' not in "".join(
        path.read_text(encoding="utf-8") for path in eprj3.page_files(root))
    model = build_schematic_model(root)
    assert sorted(model.components) == ["U1", "U2"]


# --------------------------------------------------------------------------
# 3. the PIN attribute key: the format decides
# --------------------------------------------------------------------------


def test_the_pin_key_follows_the_format_and_v3_is_the_default():
    assert _pin_key_for({"format": "eprj3"}) == "pin_id"
    assert _pin_key_for({}) == "zIndex"
    assert _pin_key_for({"format": "epro2"}) == "zIndex"


def test_the_pin_key_reads_the_pin_rows_own_id_for_an_eprj3_stream():
    text, meta = load_epru_text(FIXTURE)
    from boardwise.parsers.epru_stream import iter_epru_records

    records = list(iter_epru_records(text))
    by_id = _collect_symbols(records, None, pin_key=_pin_key_for(meta))
    by_z = _collect_symbols(records, None, pin_key="zIndex")
    pins_by_id = by_id["sym-1"].pins
    pins_by_z = by_z["sym-1"].pins
    assert pins_by_id["1"][1] == "e1" and pins_by_id["2"][1] == "e2"
    assert pins_by_z["1"][1] == "e2" and pins_by_z["2"][1] == "e3", (
        "the synthesised key disagrees with the PIN row's own id — which is why "
        "the V3 fixtures decide this branch"
    )


def test_the_v3_fixture_still_keys_pins_by_zindex():
    """The V3 red line, at the level where the key is chosen: a `.epro2` file
    carries no `format`, so nothing about its parse changes."""
    _, meta = load_epru_text(Path("tests/fixtures/llc_board.epro2"))
    assert _pin_key_for(meta) == "zIndex"
    model = build_schematic_model(Path("tests/fixtures/llc_board.epro2"))
    assert len(model.components) == 47 and len(model.nets) == 40


# --------------------------------------------------------------------------
# 4. the CLI seams
# --------------------------------------------------------------------------


def test_the_pcb_view_of_a_folder_project_without_a_board_is_refused_by_name():
    """038F5: the pcb view is now answered through 038F4's adapter, so a folder
    project with no ``pcb/*.epcb2`` is refused by **that** adapter's own words —
    still a refusal, never an empty model (SKILL pit 14)."""
    with pytest.raises(ValueError) as caught:
        cli._load_model(FIXTURE, view="pcb")
    assert ".epcb2" in str(caught.value) and "pcb/" in str(caught.value)
    model, board = cli._load_model(FIXTURE, view="schematic")
    assert len(model.components) == 2 and board is None


def test_a_folder_project_gives_its_project_uuid():
    project_uuid, page_uuid, _host, notes = cli._snapshot_identity(FIXTURE)
    assert project_uuid == "0123456789abcdef0123456789abcdef"
    assert page_uuid == "", "one folder holds many pages, so no single page is named"
    assert any("eprj3 index" in note for note in notes)


def test_latest_recognises_a_folder_project(tmp_path):
    root = _write(tmp_path / "proj")
    found = cli._project_backups(tmp_path)
    assert root in found
    assert cli._newest_project_backup([tmp_path]) == root or root in found


def test_review_reads_a_folder_project(monkeypatch, tmp_path, capsys):
    """The offline chain end to end: `review` on an eprj3 folder, no editor."""
    code = cli.main(["review", str(FIXTURE), "--view", "schematic",
                     "--json", str(tmp_path / "r.json")])
    assert code in (0, 1), capsys.readouterr().out
    payload = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert payload.get("findings") is not None
    assert "2 components" in capsys.readouterr().out


def test_review_needs_no_view_spelling_for_a_folder_project(tmp_path, capsys):
    """047: the file default is the schematic view, which is the folder's only one.

    Before the flip a bare `review <folder>` was refused by name ("B 档未开"),
    because the *pcb* view was what a bare call asked for. The refusal was
    correct — the folder has no board tier — but it is no longer what the
    default names, so the same call now reads the folder it was pointed at.
    Pinned here because the SKILL's "必须显式 --view schematic" line is about the
    old default.
    """
    code = cli.main(["review", str(FIXTURE), "--json", str(tmp_path / "r.json")])
    out = capsys.readouterr().out
    assert code in (0, 1), out
    assert "2 components" in out
    assert (tmp_path / "r.json").is_file()


# --------------------------------------------------------------------------
# 5. the same library document on both pages: one row, one meaning (V4)
# --------------------------------------------------------------------------

#: One two-pin part, and the two identities a pin has (number and name).
_LIB_PINS = [("1", 0.0, 0.0), ("2", 20.0, 0.0)]
_LIB_PIN_NAMES = ["A", "B"]


def _library_documents() -> list[str]:
    """A V4 export copies a used part's library into **every** page that uses it.

    So the same ``SYMBOL`` and the same ``DEVICE`` document arrive once per page,
    byte-for-byte identical and under the same uuid — the folder reader glues the
    pages into one stream, and it is the merge (not the reader) that has to keep
    the repetition out of the model.
    """
    out = _symbol("sym-1", "R", _LIB_PINS, _LIB_PIN_NAMES)
    out.append(_record({"type": "DOCHEAD"},
                       {"docType": "DEVICE", "uuid": "dev-1", "editVersion": "2.3.0"}))
    out.append(_record({"type": "META"},
                       {"title": "R-0603", "docType": "DEVICE", "attributes": {
                           "Symbol": "sym-1", "Name": "R?", "Designator": "R?",
                           "Supplier Part": "C25804",
                           "Manufacturer Part": "0603WAF1001T5E",
                       }}))
    return out


def _page_with_library(page: str, designator: str, *, library: bool) -> list[str]:
    out = [_record({"type": "DOCHEAD"},
                   {"docType": "SCH_PAGE", "uuid": f"page-{page}"})]
    if library:
        out += _library_documents()
    part = f"inst-{page}"
    out.append(_record({"type": "COMPONENT", "id": f"c-{page}"},
                       {"partId": part, "x": 300.0, "y": -500.0, "rotation": 0,
                        "isMirror": False, "zIndex": 10}))
    for ident, key, value in (("d", "Designator", designator),
                              ("s", "Symbol", "sym-1"),
                              ("v", "Device", "dev-1")):
        out.append(_record({"type": "ATTR", "id": f"{ident}-{page}"},
                           {"parentId": part, "key": key, "value": value}))
    return out


def _write_pages(root: Path, pages: list[tuple[str, str, bool]]) -> Path:
    """``pages`` is ``(page name, designator, carry the library documents)``."""
    page_dir = root / "sch" / "Schematic1"
    page_dir.mkdir(parents=True, exist_ok=True)
    _index(root)
    for page, designator, library in pages:
        (page_dir / f"{page}.esch2").write_text(
            "\n".join(_page_with_library(page, designator, library=library)) + "\n",
            encoding="utf-8")
    return root


def _model_fingerprint(path) -> tuple:
    """The model as data — identity, pins (number **and** name) and nets."""
    model = build_schematic_model(path)
    return (
        tuple(sorted(
            (name, comp.uid, comp.value, comp.lcsc_part, comp.mpn,
             comp.props.get("device_uuid"),
             comp.props.get("library_symbol_uuid"),
             comp.props.get("device_name"),
             tuple((pin.number, pin.name, pin.net) for pin in comp.pins))
            for name, comp in model.components.items()
        )),
        tuple(sorted((net, tuple(node.pins)) for net, node in model.nets.items())),
        tuple(model.duplicate_designators),
        tuple(sorted((name, tuple(pages))
                     for name, pages in model.cross_page_designators.items())),
    )


def test_a_library_document_copied_into_both_pages_stays_one_row(tmp_path):
    """Two pages, the same SYMBOL and the same DEVICE on each: one symbol row,
    and the two pages' placements of it read identically — same pin count, same
    pin numbers and names, same library identity.

    A duplicate document that overwrote its twin (rather than being ignored)
    would be invisible to a pin *count*; it is the pin **name** and the joined
    library identity that show a second document landing on the first.
    """
    from boardwise.parsers.epru_stream import iter_epru_records

    root = _write_pages(tmp_path / "twice",
                        [("P1", "U1", True), ("P2", "U2", True)])

    text, meta = load_epru_text(root)
    assert meta["pages"] == ["P1", "P2"]
    documents = [
        (json.loads(line.split("||", 1)[0])["type"],
         json.loads(line.split("||", 1)[1][:-1]))
        for line in text.splitlines()
    ]
    heads = [(kind, body) for kind, body in documents if kind == "DOCHEAD"]
    assert [body["uuid"] for _, body in heads if body.get("docType") == "SYMBOL"] == [
        "sym-1", "sym-1"], "both pages carry the symbol document…"
    assert [body["uuid"] for _, body in heads if body.get("docType") == "DEVICE"] == [
        "dev-1", "dev-1"], "…and both carry the device document"

    symbols = _collect_symbols(list(iter_epru_records(text)), None,
                               pin_key=_pin_key_for(meta))
    assert list(symbols) == ["sym-1"], "…and the merge keeps exactly one symbol row"
    assert sorted(symbols["sym-1"].pins) == ["1", "2"]
    assert symbols["sym-1"].pin_names == {"1": "A", "2": "B"}

    model = build_schematic_model(root)
    assert sorted(model.components) == ["U1", "U2"]
    first, second = model.components["U1"], model.components["U2"]
    assert [(pin.number, pin.name) for pin in first.pins] == [
        ("1", "A"), ("2", "B")]
    assert [(pin.number, pin.name) for pin in second.pins] == [
        ("1", "A"), ("2", "B")]
    assert (first.uid, first.lcsc_part, first.mpn,
            first.props.get("device_uuid"),
            first.props.get("library_symbol_uuid"),
            first.props.get("device_name")) == (
        second.uid, second.lcsc_part, second.mpn,
        second.props.get("device_uuid"),
        second.props.get("library_symbol_uuid"),
        second.props.get("device_name")) == (
        "sym-1", "C25804", "0603WAF1001T5E", "dev-1", "sym-1", "R-0603")
    assert model.duplicate_designators == []
    assert model.cross_page_designators == {}


def test_a_duplicated_library_document_does_not_change_the_model(tmp_path):
    """The control: the same two pages, the library documents on the first only.

    V4 writes them per page, V3 wrote them once — the model the two shapes build
    has to be the same model, or a project's reading would depend on which pages
    happened to place a part.
    """
    twice = _write_pages(tmp_path / "twice",
                         [("P1", "U1", True), ("P2", "U2", True)])
    once = _write_pages(tmp_path / "once",
                        [("P1", "U1", True), ("P2", "U2", False)])
    assert sum('"docType":"SYMBOL"' in path.read_text(encoding="utf-8")
               for path in eprj3.page_files(twice)) == 2
    second = once / "sch" / "Schematic1" / "P2.esch2"
    assert '"docType":"SYMBOL"' not in second.read_text(encoding="utf-8"), (
        "the control really is the shape without the copy on the second page"
    )
    assert _model_fingerprint(twice) == _model_fingerprint(once)
