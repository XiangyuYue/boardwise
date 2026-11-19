"""552: one physical part, several units — identity from the file, not from the name.

The defect (DSH 审查 2026-11-19): a dual op-amp is drawn as ``U15.1`` and
``U15.2``, two ``COMPONENT`` placements that answer to one designator. The
review reported four same-page duplicate-designator ERRORs (``U15``/``U16``/
``U17``/``U20``) and then truncated 17 nets, because the parser had two readings
to blame:

* it threw away each ``PIN`` record's ``partId`` in :func:`_commit_symbol`, so a
  SYMBOL document's *every* unit's pins were one flat pin set on every
  placement, and
* ``components.setdefault(designator, component)`` kept the **first** placement,
  so the second unit's own net — the one its pins are drawn on — was dropped.

Deleting the ERROR alone would leave a wrong netlist, which is what this file
refuses: the unit pins have to land on the nets the drawing puts them on.

The identity this batch reads is the file's own:

* both placements carry the same non-empty ``Unique ID``;
* both carry the same non-empty ``Device``;
* their ``partId`` values differ (``TLV9062IDR.1`` / ``TLV9062IDR.2``) — and
  the SYMBOL's own ``PIN`` rows carry the same ``partId`` per unit, which is how
  each placement gets its own pins back.

Nothing else may be used to guess a physical part: not MPN, not Value, not the
footprint, not the title, not the coordinates. The negatives below are the
reason — a copied part keeps its ``partId`` and is still two parts
(``DCDC``'s ``100NF``/``10UF``), a name across pages of one board is still a
clash (the injected ``R24``), and an identity with an empty ``Unique ID`` or an
empty ``Device`` is a duplicate whatever its ``partId`` says.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from boardwise.core.model import BoardModel
from boardwise.parsers.epru_stream import iter_epru_records, load_epru_text
from boardwise.parsers.schematic import (
    TRUNCATED_BY_DESIGNATOR,
    build_project_model,
    build_schematic_model,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"
FOC = FIXTURES / "ProPrj_毕设FOC驱动板_2026-09-17.epro2"
MOTOR = FIXTURES / "ProPrj_高速电机控制器_2026-09-16.epro2"
DCDC = FIXTURES / "DCDC-12V9V转5V3V3_2026-09-27.epro2"
INJECTED = REPO / "reviewsets" / "injected" / "duplicate-designator.epro2"


# --------------------------------------------------------------------------
# the file's own unit map: PIN.partId -> the pin numbers that unit declares
# --------------------------------------------------------------------------


def _unit_pins_from_records(path: Path, symbol_uuid: str) -> dict[str, list[str]]:
    """Read the SYMBOL document the way the parser *should*: per ``partId``.

    This is the evidence the assertions below are held to, taken from the raw
    records rather than from the parser's output — otherwise a parser that
    flattened the units could be checked against its own mistake.
    """
    text, _meta = load_epru_text(path)
    doc = ""
    numbers: dict[str, str] = {}
    runs: list[tuple[str, str, str]] = []  # (partId, pin id, synthesised ref)
    for record in iter_epru_records(text):
        body = record.body or {}
        if record.type == "DOCHEAD":
            doc = str(body.get("docType") or "")
            if doc == "SYMBOL" and str(body.get("uuid") or "") != symbol_uuid:
                doc = "OTHER_SYMBOL"
            continue
        if doc != "SYMBOL":
            continue
        if record.type == "PIN":
            runs.append((
                str(body.get("partId") or ""),
                str(record.id or ""),
                f"e{body.get('zIndex')}",
            ))
        elif record.type == "ATTR" and body.get("key") == "Pin Number":
            parent = str(body.get("parentId") or "")
            value = str(body.get("value") or "")
            if value:
                numbers.setdefault(parent, value)
    out: dict[str, list[str]] = {}
    for part_id, pin_id, ref in runs:
        number = numbers.get(pin_id) or numbers.get(ref)
        if number:
            out.setdefault(part_id, []).append(number)
    return {part_id: sorted(values) for part_id, values in out.items()}


def _symbol_uuid(path: Path, title: str) -> str:
    text, _meta = load_epru_text(path)
    symbol, doc = "", ""
    for record in iter_epru_records(text):
        body = record.body or {}
        if record.type == "DOCHEAD":
            doc = str(body.get("docType") or "")
            if doc == "SYMBOL":
                symbol = str(body.get("uuid") or "")
            continue
        if doc == "SYMBOL" and record.type == "META" and body.get("title") == title:
            return symbol
    raise AssertionError(f"{path.name}: no SYMBOL titled {title!r}")


def _board_with(path: Path, designators: tuple[str, ...]) -> BoardModel:
    """The board that carries every one of ``designators``.

    Selected by content rather than by title: a title is a label the designer
    types, and the identity this file is about is not a label.
    """
    project = build_project_model(path)
    for board in project.boards:
        if all(designator in board.components for designator in designators):
            return board
    raise AssertionError(f"{path.name}: no board carries {designators}")


DUAL_UNITS = ("U15", "U16", "U17", "U20")
FOC_UNITS = ("U15", "U16")

#: The readings the drawings give, pin by pin -- unit ``.1`` owns ``1..4`` and
#: ``8``, unit ``.2`` owns ``5/6/7``. Read from the archive's own wires and
#: ``NET`` labels, and only members that the net the pin names actually carries.
MOTOR_READINGS = {
    "U15": {"1": "IA", "2": "NET16", "3": "NET21", "4": "AGND", "5": "NET28",
            "6": "NET7", "7": "IB", "8": "VCCA"},
    "U16": {"1": "IC", "2": "NET5", "3": "NET22", "4": "AGND", "5": "VCC/2",
            "6": "NET86", "7": "NET86", "8": "VCCA"},
    "U17": {"1": "UC", "2": "UC", "3": "NET13", "4": "AGND", "5": "NET14",
            "6": "UBUS", "7": "UBUS", "8": "VCCA"},
    "U20": {"1": "UA", "2": "UA", "3": "NET11", "4": "AGND", "5": "NET12",
            "6": "UB", "7": "UB", "8": "VCCA"},
}
FOC_READINGS = {
    "U15": {"1": "IA", "2": "NET19", "3": "NET24", "4": "AGND", "5": "NET31",
            "6": "NET3", "7": "IB", "8": "VCCA"},
    # U16's second unit is this board's spare channel: its three pins are drawn
    # with no wire at all, so they read no net. Carrying the pins is the point
    # of the fix; naming a net for them would be the invented connection.
    "U16": {"1": "IC", "2": "NET5", "3": "NET25", "4": "AGND", "5": None,
            "6": None, "7": None, "8": "VCCA"},
}
READINGS = {MOTOR: MOTOR_READINGS, FOC: FOC_READINGS}


def _numbers(board: BoardModel, designator: str) -> list[str]:
    return sorted(pin.number for pin in board.components[designator].pins)


def _net_of(board: BoardModel, designator: str, number: str) -> str | None:
    return next(
        pin.net for pin in board.components[designator].pins if pin.number == number
    )


def _members_of(board: BoardModel, name: str) -> list[tuple[str, str]]:
    return [tuple(member) for member in board.nets[name].pins]


# --------------------------------------------------------------------------
# 1. the two committed archives with dual-unit op-amps
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,designators",
    [(MOTOR, DUAL_UNITS), (FOC, FOC_UNITS)],
    ids=["motor-driver-4-units", "foc-board1-2-units"],
)
def test_a_dual_unit_part_is_one_component_carrying_both_units(path, designators):
    """Every unit's pins are the root component's pins — and every unit's pins
    are members of the net that unit's own placement reads.

    The pin sets come from the SYMBOL's ``PIN.partId`` groups, so a flattened
    symbol (all units' pins on every placement) or a dropped second placement
    (first placement only) both fail here, and neither can be satisfied by
    deleting the duplicate-designator ERROR.
    """
    board = _board_with(path, designators)
    symbol = _symbol_uuid(path, "TLV9062IDR")
    units = _unit_pins_from_records(path, symbol)
    assert len(units) == 2 and all(units.values()), units
    expected = sorted({number for numbers in units.values() for number in numbers})
    seen_units = 0
    for designator in designators:
        assert _numbers(board, designator) == expected, designator
        reading = {pin.number: pin.net for pin in board.components[designator].pins}
        assert reading == READINGS[path][designator], designator
        for number, net in reading.items():
            if net is None:
                continue  # a pin the drawing leaves unwired; see FOC_READINGS
            members = _members_of(board, net)
            assert (designator, number) in members, (designator, number, net)
            assert members.count((designator, number)) == 1, (designator, number)
        # the units are not two parts: neither repeat list may name them
        assert designator not in board.duplicate_designators
        assert designator not in board.cross_page_designators
        for name, reason in board.unproven_reasons.items():
            assert reason != TRUNCATED_BY_DESIGNATOR or designator not in name
        seen_units += 1
    assert seen_units == len(designators)
    assert board.unproven_reasons == {}, sorted(board.unproven_reasons)


def test_the_second_units_pins_are_not_the_first_units():
    """The concrete loss the flattening caused: unit 2's signals read nets that
    nothing else on the part touches, so a component whose pin set came from one
    placement cannot pass this."""
    board = _board_with(MOTOR, DUAL_UNITS)
    units = _unit_pins_from_records(MOTOR, _symbol_uuid(MOTOR, "TLV9062IDR"))
    first, second = sorted(units)
    for designator in DUAL_UNITS:
        nets_by_unit = {
            part: {_net_of(board, designator, number) for number in units[part]}
            for part in (first, second)
        }
        assert nets_by_unit[first] != nets_by_unit[second], designator
        # what the second unit's own output pin is on must be a net this part's
        # first unit has no pin on (measured: OUTA/OUTB are different signals)
        assert "7" in units[second], units
        out_b = _net_of(board, designator, "7")
        assert out_b not in nets_by_unit[first], designator


def test_the_foc_board_has_no_same_page_duplicate_left():
    """Board1's only two same-page repeats were the two units of U15/U16; with
    the units merged, the board's duplicate list is empty — not silenced, read."""
    board = _board_with(FOC, FOC_UNITS)
    assert board.duplicate_designators == []
    assert board.cross_page_designators == {}
    units = _unit_pins_from_records(FOC, _symbol_uuid(FOC, "TLV9062IDR"))
    for designator in FOC_UNITS:
        assert _numbers(board, designator) == sorted(
            {number for numbers in units.values() for number in numbers}
        )


# --------------------------------------------------------------------------
# 2. the negatives: a real duplicate stays a real duplicate
# --------------------------------------------------------------------------


def test_a_copied_part_with_the_same_part_id_is_still_two_parts():
    """DCDC's ``100NF`` x4 and ``10UF`` x2 are copies of one library part, so
    their ``partId`` is identical; 552 must not merge them, and the netlist
    guard from 105 must still see them as repeats."""
    board = build_schematic_model(DCDC)
    assert board.duplicate_designators == ["100NF", "10UF"]
    assert board.unproven_nets, "a dropped copy still truncates its nets"
    for designator in ("100NF", "10UF"):
        assert _numbers(board, designator) == ["1", "2"]


def test_the_injected_cross_page_copy_is_still_a_clash():
    board = build_schematic_model(INJECTED)
    assert "R24" in board.cross_page_designators
    assert len(board.cross_page_designators["R24"]) == 2


# --------------------------------------------------------------------------
# 3. synthetic streams: the identity gate, one attribute at a time
# --------------------------------------------------------------------------


def _record(type_: str, body: dict | None = None, id_: str | None = None) -> str:
    envelope: dict = {"type": type_, "ticket": 1}
    if id_ is not None:
        envelope["id"] = id_
    payload = json.dumps(body, separators=(",", ":")) if body is not None else ""
    return json.dumps(envelope, separators=(",", ":")) + "||" + payload + "|"


def _doc_head(doc_type: str, uuid: str) -> str:
    return _record("DOCHEAD", {"docType": doc_type, "uuid": uuid,
                               "editVersion": "3.2.186"})


#: The dual op-amp, as the measured symbol declares it: five pins in unit ``.1``
#: (two of them signals the second unit does not have) and three in ``.2``.
#: Pin ``9`` is the supply pair drawn on **both** units — the same physical pin
#: number declared twice, which is what the conflict rule is about.
UNIT1 = [("1", 0.0, 0.0), ("2", 0.0, -10.0), ("3", 10.0, -20.0), ("9", 20.0, -20.0)]
UNIT2 = [("5", 0.0, 0.0), ("6", 0.0, -10.0), ("7", 10.0, -20.0), ("9", 20.0, -20.0)]

NETS = {"1": "OUTA", "2": "INA_MINUS", "3": "VPLUS", "5": "INB_PLUS",
        "6": "OUTB", "7": "OUTB2", "9": "VPLUS"}


def _symbol() -> list[str]:
    out = [_doc_head("SYMBOL", "sym-u2"), _record("META", {"title": "TLV9062IDR"})]
    for part, pins in (("dev.1", UNIT1), ("dev.2", UNIT2)):
        for number, x, y in pins:
            out.append(_record("PIN", {"x": x, "y": -y, "zIndex": len(out),
                                       "partId": part}))
            out.append(_record("ATTR", {"key": "Pin Number", "value": number,
                                        "parentId": f"e{len(out) - 1}"}))
    return out


def _placement(part_id: str, designator: str, attrs: dict[str, str], x: float,
               y: float) -> list[str]:
    out = [_record("COMPONENT", {"partId": part_id, "x": x, "y": -y,
                                 "rotation": 0, "zIndex": len(part_id)},
                   id_=f"c-{part_id}-{x}")]
    out.append(_record("ATTR", {"parentId": part_id, "key": "Symbol",
                                "value": "sym-u2"}))
    out.append(_record("ATTR", {"parentId": part_id, "key": "Designator",
                                "value": designator}))
    for key, value in attrs.items():
        out.append(_record("ATTR", {"parentId": part_id, "key": key, "value": value}))
    return out


def _wire(group: str, points: list[tuple[float, float]], net: str) -> list[str]:
    out = [_record("WIRE", {"zIndex": 40}, id_=group)]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        out.append(_record("LINE", {"lineGroup": group, "startX": x0, "startY": -y0,
                                    "endX": x1, "endY": -y1},
                           id_=f"{group}-{x0}-{y0}"))
    out.append(_record("ATTR", {"parentId": group, "key": "NET", "value": net}))
    return out


def _board_stream(
    tmp_path: Path, *, uid: str | None = "uid-1", device: str | None = "dev-uuid",
    parts: tuple[str, str] = ("dev.1", "dev.2"), designators: tuple[str, str] = ("U1", "U1"),
    wire_units: tuple[bool, bool] = (True, True),
) -> BoardModel:
    """The dual-unit board, with any identity field removed on demand.

    Each unit's pins are wired to their own labelled stub, so "did this
    placement's own net survive" is a question the drawing answers. The supply
    pin ``9`` is drawn on both units and labelled ``VPLUS`` on both — the
    declarations agree on the net, which is the only case 552 may merge.
    """
    attrs: dict[str, str] = {}
    if uid is not None:
        attrs["Unique ID"] = uid
    if device is not None:
        attrs["Device"] = device
    lines = [_doc_head("SCH_PAGE", "page1")]
    for index, (part, designator, wired) in enumerate(
        zip(parts, designators, wire_units)
    ):
        x, y = (0.0, 0.0) if index == 0 else (120.0, 0.0)
        lines += _placement(part, designator, attrs, x, y)
        if not wired:
            continue
        # wire the pins this placement *declares*: with the same partId twice
        # both placements declare unit 1's pins, so nothing but the identity
        # gate can separate them (a mismatch here would let the pin-conflict
        # gate mask that gate, which is how this fixture was first written).
        unit = UNIT1 if part.endswith(".1") else UNIT2
        for number, px, py in unit:
            cx, cy = px + x, py + y
            # a 4-unit stub: long enough to be a wire, short enough that it
            # cannot touch the next pin's stub (pins 7 and 9 are 10 apart)
            lines += _wire(f"g{index}-{number}", [(cx, cy), (cx + 4.0, cy)],
                           NETS[number])
    text = "\n".join(_symbol() + lines) + "\n"
    path = tmp_path / "units.epro2"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("synth.epru", text)
        archive.writestr("project2.json", json.dumps({"title": "synthetic"}))
    project = build_project_model(path)
    assert len(project.boards) == 1
    return project.boards[0]


def test_the_two_units_of_one_device_share_the_parts_pins_and_nets(tmp_path):
    board = _board_stream(tmp_path)
    assert board.duplicate_designators == []
    assert board.cross_page_designators == {}
    assert _numbers(board, "U1") == ["1", "2", "3", "5", "6", "7", "9"]
    assert {_net_of(board, "U1", number) for number in ("1", "2", "3", "5", "6", "7")} == {
        "OUTA", "INA_MINUS", "VPLUS", "INB_PLUS", "OUTB", "OUTB2"
    }
    # the shared supply pin number: declared twice, one net -> one member
    assert _net_of(board, "U1", "9") == "VPLUS"
    assert _members_of(board, "VPLUS").count(("U1", "9")) == 1
    assert board.unproven_nets == {}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"uid": None},
        {"uid": ""},
        {"device": None},
        {"device": ""},
        {"parts": ("dev.1", "dev.1")},
        {"parts": ("dev.1", "dev.1"), "designators": ("U1", "U1")},
    ],
    ids=["no-unique-id", "empty-unique-id", "no-device", "empty-device",
         "same-part-id", "same-part-id-same-uid"],
)
def test_an_identity_that_the_file_does_not_carry_is_still_a_duplicate(tmp_path, kwargs):
    """Without the three fields the file's own identity rests on, the two
    placements are two parts answering to one name — the old reading, kept."""
    board = _board_stream(tmp_path, **kwargs)
    assert board.duplicate_designators == ["U1"]
    # only the first placement's unit is this component: the second is another
    # part, so its pins may not join
    assert _numbers(board, "U1") == ["1", "2", "3", "9"]


def test_a_shared_pin_number_whose_nets_disagree_is_not_merged(tmp_path):
    """Two units declaring pin ``9`` is only mergeable while both read the same
    net. Here the second unit's stub is unconnected, so the readings are one
    net and one nothing — "一有一无" is not proof, and the clash stands."""
    board = _board_stream(tmp_path, wire_units=(True, False))
    # the second unit's own stub carries no wire at all: every pin it declares
    # reads nothing, so the shared number 9 cannot be confirmed equal
    assert board.duplicate_designators == ["U1"]
    assert _numbers(board, "U1") == ["1", "2", "3", "9"]
    assert _net_of(board, "U1", "9") == "VPLUS"


def test_a_shared_pin_number_on_two_different_nets_is_not_merged(tmp_path):
    """The conflict itself: both units wire pin ``9``, to different labels."""
    path = tmp_path / "conflict.epro2"
    lines = [_doc_head("SCH_PAGE", "page1")]
    for index, part in enumerate(("dev.1", "dev.2")):
        x = 0.0 if index == 0 else 100.0
        lines += _placement(part, "U1", {"Unique ID": "uid-1", "Device": "dev-uuid"},
                            x, 0.0)
        label = "VPLUS" if index == 0 else "VPLUS_B"
        for number, px, py in (UNIT1 if index == 0 else UNIT2):
            cx, cy = px + x, py
            lines += _wire(f"g{index}-{number}", [(cx, cy), (cx + 4.0, cy)],
                           label if number == "9" else NETS[number])
    text = "\n".join(_symbol() + lines) + "\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("synth.epru", text)
        archive.writestr("project2.json", json.dumps({"title": "synthetic"}))
    board = build_project_model(path).boards[0]
    assert board.duplicate_designators == ["U1"], "a conflicting pin is not proof"
    assert _numbers(board, "U1") == ["1", "2", "3", "9"]


def test_a_shared_pin_number_one_unit_leaves_no_connect_is_not_merged(tmp_path):
    """``NO_CONNECT`` is a reading — "this pin is on no net" — and it has to vote.

    Both units declare pin ``9``, both are drawn on a wire labelled ``VPLUS``,
    and the second unit marks its own pin ``9`` no-connect. The file's identity
    still says "one part" (same ``Unique ID``, same ``Device``, ``partId`` .1/.2),
    but the pin readings disagree on that one number: one unit says ``VPLUS``,
    the other says nothing at all. Contract §4 is explicit that "一有一无" is
    not proof, so the old duplicate-designator reading stands. Merging here
    would put a member on ``VPLUS`` for a pin whose own ``Pin.net`` is ``None``.
    """
    path = tmp_path / "nc.epro2"
    lines = [_doc_head("SCH_PAGE", "page1")]
    lines += [_doc_head("SYMBOL", "sym-u2"), _record("META", {"title": "TLV9062IDR"})]
    for part, number, z, x, y in (
        ("dev.1", "1", 1, 0.0, 0.0), ("dev.1", "9", 2, 10.0, -20.0),
        ("dev.2", "5", 3, 0.0, 0.0), ("dev.2", "9", 4, 10.0, -20.0),
    ):
        lines.append(_record("PIN", {"x": x, "y": -y, "zIndex": z, "partId": part}))
        lines.append(_record("ATTR", {"key": "Pin Number", "value": number,
                                      "parentId": f"e{z}"}))
    for index, part in enumerate(("dev.1", "dev.2")):
        x = 0.0 if index == 0 else 100.0
        lines += _placement(part, "U1", {"Unique ID": "uid-1", "Device": "dev-uuid"},
                            x, 0.0)
        # both units draw pin 9 on a wire of the same name; the signal pin of
        # each unit gets its own label so neither unit is the trivial case
        lines += _wire(f"g{index}-9", [(10.0 + x, -20.0), (14.0 + x, -20.0)], "VPLUS")
        lines += _wire(f"g{index}-s", [(x, 0.0), (4.0 + x, 0.0)],
                       "OUTA" if index == 0 else "OUTB")
    # the second unit's own pin 9, addressed through the instance's container id
    # exactly as the production form does: "<container>-e<pin element id>"
    lines.append(_record("ATTR", {"key": "NO_CONNECT", "value": "",
                                  "parentId": "dev.2-e4"}))
    text = "\n".join(lines) + "\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("synth.epru", text)
        archive.writestr("project2.json", json.dumps({"title": "synthetic"}))
    board = build_project_model(path).boards[0]
    assert board.duplicate_designators == ["U1"], (
        "one unit says VPLUS, the other says nothing: not proof of one net"
    )
    assert _numbers(board, "U1") == ["1", "9"]
    # the kept unit's own reading, and no member for the number the other unit
    # declared no-connect
    assert _net_of(board, "U1", "9") == "VPLUS"
    assert _members_of(board, "VPLUS") == [("U1", "9")]


def test_a_placement_whose_part_id_is_not_in_the_symbol_keeps_the_whole_set(tmp_path):
    """Exact hit or nothing: a ``partId`` the SYMBOL does not declare (an older
    library copy, a renamed part) falls back to the symbol's full pin set rather
    than guessing a unit."""
    board = _board_stream(tmp_path, parts=("dev.9", "dev.2"), designators=("U1", "U2"))
    assert _numbers(board, "U1") == ["1", "2", "3", "5", "6", "7", "9"]
    assert _numbers(board, "U2") == ["5", "6", "7", "9"]
