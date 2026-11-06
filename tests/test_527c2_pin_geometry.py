"""527C2 片 1: the parser's geometry projection, and what it must not weld.

The cross-view check of 189A2 asks a question no netlist can answer — *is this
pin on a line at all?* — so the parser has to hand the geometry over. This file
pins the projection itself (``DesignModel.pin_wires``), not its disclosure: the
section/note half of 527C2 is 片 2's, and nothing here reads the engine.

What the field must state, and what these tests hold it to:

* a pin's posed page point and the page it sits on, from the placement the
  model **keeps** (049/105);
* the wire segments per page — and only the groups a ``WIRE`` head owns, so a
  placed symbol's own graphic can never make a pin look drawn-on (040 §WI-2);
* no merging across pages or across boards: two feet, two sheets and two boards
  each keep their own lines even when the coordinates are *identical*, which is
  the shape a "project the whole file into one list" reading would weld;
* ``None`` for every model with no drawing behind it — a KiCad/``.enet``/manual
  model keeps the old generic wording instead of pretending to a geometry.

The last test is the one that can surprise us: a real archived fixture, read
twice, with every pin of every component accounted for. If that ever goes red,
the projection is dropping feet, not merely agreeing with a synthetic stream.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from boardwise.core.geometry import transform_point
from boardwise.core.model import BoardModel, DesignModel, Net
from boardwise.parsers.schematic import build_project_model

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "ch340_golden.epro2"
FOC = FIXTURES / "ProPrj_毕设FOC驱动板_2026-09-17.epro2"

# --------------------------------------------------------------------------
# synthesised streams (the same record grammar test_189a2_schematic_nets uses)
# --------------------------------------------------------------------------


def _record(type_: str, body: dict | None = None, id_: str | None = None) -> str:
    envelope: dict = {"type": type_, "ticket": 1}
    if id_ is not None:
        envelope["id"] = id_
    payload = json.dumps(body, separators=(",", ":")) if body is not None else ""
    return json.dumps(envelope, separators=(",", ":")) + "||" + payload + "|"


def _symbol(uuid: str, title: str, pins: list[tuple[str, float, float]]) -> list[str]:
    """One ``SYMBOL`` document; ``pins`` are ``(number, x, y)`` in canvas space."""
    out = [
        _record("DOCHEAD", {"docType": "SYMBOL", "uuid": uuid}),
        _record("META", {"title": title, "docType": "SYMBOL"}, id_=f"meta-{uuid}"),
    ]
    for index, (number, x, y) in enumerate(pins):
        pin_id = f"{uuid}-pin{number}"
        out.append(_record("PIN", {"x": x, "y": -y, "zIndex": index + 1}, id_=pin_id))
        out.append(_record(
            "ATTR", {"parentId": pin_id, "key": "Pin Number", "value": number},
            id_=f"{pin_id}-n",
        ))
    return out


def _component(
    *, part_id: str, designator: str, symbol: str, x: float, y: float,
    rotation: float = 0.0, mirror: bool = False, z_index: int = 1,
) -> list[str]:
    """One placed part, in **canvas** coordinates (y negated on the way out)."""
    return [
        _record("COMPONENT", {
            "partId": part_id, "x": x, "y": -y, "rotation": rotation,
            "isMirror": mirror, "zIndex": z_index,
        }, id_=f"c-{part_id}"),
        _record("ATTR", {"parentId": part_id, "key": "Designator", "value": designator},
                id_=f"d-{part_id}"),
        _record("ATTR", {"parentId": part_id, "key": "Symbol", "value": symbol},
                id_=f"s-{part_id}"),
        _record("ATTR", {"parentId": part_id, "key": "Device", "value": f"dev-{symbol}"},
                id_=f"v-{part_id}"),
    ]


def _wire(group: str, points: list[tuple[float, float]], net: str = "") -> list[str]:
    """A ``WIRE`` head plus the ``LINE`` pieces through ``points`` (canvas space)."""
    out = [_record("WIRE", {"zIndex": 40}, id_=group)]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        out.append(_record("LINE", {
            "lineGroup": group, "startX": x0, "startY": -y0,
            "endX": x1, "endY": -y1,
        }, id_=f"{group}-{x0}-{y0}"))
    if net:
        out.append(_record("ATTR", {"parentId": group, "key": "NET", "value": net},
                           id_=f"net-{group}"))
    return out


def _graphic(group: str, points: list[tuple[float, float]]) -> list[str]:
    """A placed symbol's own graphic: a head no ``WIRE`` owns, plus its lines."""
    out = [_record("POLYLINE", {"zIndex": 1}, id_=group)]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        out.append(_record("LINE", {
            "lineGroup": group, "startX": x0, "startY": -y0,
            "endX": x1, "endY": -y1,
        }, id_=f"{group}-g{x0}-{y0}"))
    return out


def _page(uuid: str, schematic: str | None = None) -> list[str]:
    out = [_record("DOCHEAD", {"docType": "SCH_PAGE", "uuid": uuid})]
    if schematic is not None:
        out.append(_record("META", {"schematic": schematic, "docType": "SCH_PAGE"},
                           id_=f"meta-{uuid}"))
    return out


def _board_chain(board: str, schematic: str, title: str, z_index: int) -> list[str]:
    """One ``BOARD`` + one ``SCH``: the container's own page↔board chain (040b)."""
    return [
        _record("DOCHEAD", {"docType": "BOARD", "uuid": board}),
        _record("META", {"title": title, "zIndex": z_index, "docType": "BOARD"},
                id_=f"meta-{board}"),
        _record("DOCHEAD", {"docType": "SCH", "uuid": schematic}),
        _record("META", {"board": board, "docType": "SCH"}, id_=f"meta-{schematic}"),
    ]


def _archive(tmp_path: Path, name: str, lines: list[str]) -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("synth.epru", "\n".join(lines) + "\n")
        archive.writestr("project2.json", json.dumps({"title": "synthetic"}))
    return path


#: A symmetric two-pin part: its two feet end up on opposite sides of the
#: placement, so "both pins on one wire" is a mistake with no coincidental cover.
TWO_PIN = [("1", -20.0, 0.0), ("2", 20.0, 0.0)]

#: The 189A2 shape: a one-sided three-pin part, where a quarter turn plus a
#: mirror moves the pins in two independent directions.
MUX_PINS = [("1", -20.0, 10.0), ("2", -20.0, 0.0), ("3", -20.0, -10.0)]


def _one_board(tmp_path: Path, lines: list[str]) -> BoardModel:
    project = build_project_model(_archive(tmp_path, "one.epro2", lines))
    assert len(project.boards) == 1
    return project.boards[0]


# --------------------------------------------------------------------------
# the shape of the field
# --------------------------------------------------------------------------


def test_the_field_states_the_endpoint_binding_and_the_pages_it_read(tmp_path):
    """``binding`` is the schematic view's own law, and every page of the board
    is a key — a sheet with no line is a reading, not a missing page."""
    board = _one_board(tmp_path, [
        *_symbol("sym-r2", "R2K", TWO_PIN),
        *_page("page-1"),
        *_component(part_id="inst-u9", designator="U9", symbol="sym-r2",
                    x=100.0, y=100.0),
        *_wire("g-left", [(80.0, 100.0), (80.0, 60.0)], net="LEFT"),
        *_wire("g-right", [(120.0, 100.0), (120.0, 60.0)], net="RIGHT"),
        *_page("page-empty"),
    ])
    assert board.pin_wires is not None
    assert board.pin_wires["binding"] == "endpoint"
    assert sorted(board.pin_wires["wires"]) == ["page-1", "page-empty"]
    assert board.pin_wires["wires"]["page-empty"] == [], "no line is not no page"
    assert board.pin_wires["pins"][("U9", "1")] == ("page-1", 80.0, 100.0)
    assert board.pin_wires["pins"][("U9", "2")] == ("page-1", 120.0, 100.0)


def test_two_feet_on_one_page_keep_their_own_segments(tmp_path):
    """The negative control for a single page: the segment list is exactly the
    two separate wires, in group order, and each foot sits on one of them."""
    board = _one_board(tmp_path, [
        *_symbol("sym-r2", "R2K", TWO_PIN),
        *_page("page-1"),
        *_component(part_id="inst-u9", designator="U9", symbol="sym-r2",
                    x=100.0, y=100.0),
        *_wire("g-left", [(80.0, 100.0), (80.0, 60.0)], net="LEFT"),
        *_wire("g-right", [(120.0, 100.0), (120.0, 60.0)], net="RIGHT"),
    ])
    wires = board.pin_wires["wires"]["page-1"]
    assert wires == [
        ((80.0, 100.0), (80.0, 60.0)),
        ((120.0, 100.0), (120.0, 60.0)),
    ]
    ends = [{segment[0], segment[1]} for segment in wires]
    pin1 = board.pin_wires["pins"][("U9", "1")][1:]
    pin2 = board.pin_wires["pins"][("U9", "2")][1:]
    assert sum(pin1 in segment for segment in ends) == 1
    assert sum(pin2 in segment for segment in ends) == 1
    assert not any(pin1 in seg and pin2 in seg for seg in ends), (
        "two feet on one wire is exactly the weld this field must not make"
    )


def test_two_pages_with_identical_coordinates_are_not_merged(tmp_path):
    """Same drawing, twice, on two sheets: each page keeps its own segment and
    each pin names its own page. A single merged list would read as one net."""
    halves: list[str] = []
    for index, page_uuid in enumerate(("page-a", "page-b")):
        halves += _page(page_uuid)
        halves += _component(part_id=f"inst-u{index}", designator=f"U{index}",
                             symbol="sym-r2", x=100.0, y=100.0)
        halves += _wire(f"g-{page_uuid}", [(80.0, 100.0), (80.0, 60.0)])
        halves += _wire(f"h-{page_uuid}", [(120.0, 100.0), (120.0, 60.0)])
    board = _one_board(tmp_path, [*_symbol("sym-r2", "R2K", TWO_PIN), *halves])
    geometry = board.pin_wires
    assert sorted(geometry["wires"]) == ["page-a", "page-b"]
    for page_uuid in ("page-a", "page-b"):
        assert geometry["wires"][page_uuid] == [
            ((80.0, 100.0), (80.0, 60.0)),
            ((120.0, 100.0), (120.0, 60.0)),
        ]
    # the page a pin reports is the page its placement sits on, not "some page"
    assert geometry["pins"][("U0", "1")][0] == "page-a"
    assert geometry["pins"][("U1", "1")][0] == "page-b"


def test_two_boards_with_identical_coordinates_are_not_merged(tmp_path):
    """Two boards numbering their own ``R1`` at the same spot with the same
    wire. Each board's model carries its own page only — 040b's partition is
    the batch this projection inherits, and it must not be undone here."""
    lines: list[str] = list(_symbol("sym-r2", "R2K", TWO_PIN))
    for index, (board, schematic, page_uuid) in enumerate((
        ("b1", "s1", "page-1"), ("b2", "s2", "page-2"),
    )):
        lines += _board_chain(board, schematic, f"B{index + 1}", index + 1)
        lines += _page(page_uuid, schematic)
        lines += _component(part_id=f"inst-r1-{board}", designator="R1",
                            symbol="sym-r2", x=100.0, y=100.0)
        lines += _wire(f"g-{board}", [(80.0, 100.0), (80.0, 60.0)], net="VCC")
    project = build_project_model(_archive(tmp_path, "two.epro2", lines))
    assert project.board_titles() == ["B1", "B2"]
    first, second = project.boards
    assert sorted(first.pin_wires["wires"]) == ["page-1"]
    assert sorted(second.pin_wires["wires"]) == ["page-2"]
    assert first.pin_wires["pins"][("R1", "1")][0] == "page-1"
    assert second.pin_wires["pins"][("R1", "1")][0] == "page-2"
    assert first.pin_wires["wires"]["page-1"] == [((80.0, 100.0), (80.0, 60.0))]


def test_a_symbols_own_graphic_is_not_a_wire(tmp_path):
    """The graphic sits line-for-line on the pins and joins nothing: it is in
    ``segments`` but no ``WIRE`` head owns it, so it must not reach ``wires``
    (040 §WI-2 — one such graphic shorted a whole capacitor bank for real)."""
    board = _one_board(tmp_path, [
        *_symbol("sym-r2", "R2K", TWO_PIN),
        *_page("page-1"),
        *_component(part_id="inst-u9", designator="U9", symbol="sym-r2",
                    x=100.0, y=100.0),
        *_graphic("g-bracket", [(80.0, 100.0), (80.0, 60.0), (120.0, 60.0),
                                (120.0, 100.0)]),
        *_wire("g-real", [(80.0, 100.0), (80.0, 40.0)], net="REAL"),
    ])
    assert board.pin_wires["wires"]["page-1"] == [((80.0, 100.0), (80.0, 40.0))]
    # the two feet are on two different nets: the bracket welded nothing
    assert board.components["U9"].pins[0].net != board.components["U9"].pins[1].net


def test_the_posed_point_is_the_one_the_netlist_used(tmp_path):
    """Rotation and mirror are the model's own law, not a second opinion: the
    recorded point is exactly ``transform_point``'s output for that placement."""
    board = _one_board(tmp_path, [
        *_symbol("sym-mux3", "MUX3", MUX_PINS),
        *_page("page-1"),
        *_component(part_id="inst-u9", designator="U9", symbol="sym-mux3",
                    x=100.0, y=100.0, rotation=90.0, mirror=True),
    ])
    for number, local_x, local_y in MUX_PINS:
        posed = transform_point(local_x, local_y, rotation=90.0, mirror=True,
                                ox=100.0, oy=100.0)
        assert board.pin_wires["pins"][("U9", number)] == ("page-1", *posed)


def test_a_model_with_no_drawing_behind_it_carries_no_geometry():
    """KiCad, ``.enet`` and every hand-built model keep ``None`` — the old
    wording, not a fabricated empty geometry. The old field order is untouched:
    ``components`` is still the first positional field (527C2 appends)."""
    manual = DesignModel({"GND": Net(name="GND")})
    assert manual.pin_wires is None
    assert manual.nets == {}, "positional order: components is still field 1"
    assert "GND" in manual.components
    assert DesignModel().pin_wires is None
    assert BoardModel().pin_wires is None


def test_a_repeated_designator_reports_the_placement_the_model_kept(tmp_path):
    """Two ``U1`` on one page: the model keeps the first placement (049/105), so
    that is the position the geometry reports. A second copy's point would name
    a part this netlist does not carry."""
    board = _one_board(tmp_path, [
        *_symbol("sym-r2", "R2K", TWO_PIN),
        *_page("page-1"),
        *_component(part_id="inst-u1a", designator="U1", symbol="sym-r2",
                    x=100.0, y=100.0, z_index=1),
        *_component(part_id="inst-u1b", designator="U1", symbol="sym-r2",
                    x=300.0, y=300.0, z_index=2),
    ])
    assert board.duplicate_designators == ["U1"]
    assert board.pin_wires["pins"][("U1", "1")] == ("page-1", 80.0, 100.0)
    assert board.pin_wires["pins"][("U1", "2")] == ("page-1", 120.0, 100.0)


# --------------------------------------------------------------------------
# the real archive: read twice, every foot accounted for
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def golden() -> BoardModel:
    (board,) = build_project_model(GOLDEN).boards
    return board


def test_a_real_archive_projects_reproducibly_and_loses_no_foot(golden):
    again = build_project_model(GOLDEN).boards[0]
    assert golden.pin_wires == again.pin_wires, "same file, same projection"
    geometry = golden.pin_wires
    assert geometry is not None and geometry["binding"] == "endpoint"
    assert geometry["wires"], "a real board has wires"
    assert set(geometry["wires"]) <= set(golden.board.page_uuids)
    # every pin the model carries has a position, and no extra position is
    # invented for a pin the model does not carry
    model_pins = {
        (designator, pin.number)
        for designator, component in golden.components.items()
        for pin in component.pins
    }
    assert model_pins, "the golden board's parts have pins"
    assert model_pins == set(geometry["pins"]), sorted(
        model_pins ^ set(geometry["pins"])
    )
    assert {page for page, _x, _y in geometry["pins"].values()} <= set(
        golden.board.page_uuids
    )


def test_a_real_multi_board_archive_keeps_its_pages_apart():
    """The 毕设 project's boards are three boards, not one drawing: no page of
    one board's projection appears in another's (040b measured the same fact on
    the netlists; this is the geometry half)."""
    project = build_project_model(FOC)
    assert len(project.boards) >= 2
    seen: set[str] = set()
    for board in project.boards:
        pages = set(board.pin_wires["wires"])
        assert pages <= set(board.board.page_uuids)
        assert not pages & seen, "two boards sharing a page's wires"
        seen |= pages
        assert {page for page, _x, _y in board.pin_wires["pins"].values()} <= pages
