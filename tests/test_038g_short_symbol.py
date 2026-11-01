"""038g: a ``Short-Symbol`` placement is a jumper, not a net name.

The reported defect: ten ``Short-Symbol`` placements on the 038g sample's
second sheet, every one of them placed with a pin on each half of one net and
nothing in between. The two halves therefore arrived as two separate nets, and
because those placements carry no designator the flag pass read their device
title — ``Short-Symbol`` — as a flag name and split off ``Symbol``, a net the
editor has never heard of.

What this file pins, on synthesised boards only:

* the join itself — the two halves at a short's pins are one net;
* the name of that net: a power flag first, then the explicit ``NET`` label on
  the side that carries the real part pins, then the old alphabetical order of
  whatever labels the cluster has. A short's pin side is **not** a fixed
  direction, and a chain of shorts has to carry the pin-side label across it;
* the degenerate halves — one pin on nothing joins nothing (no empty net), and
  a short's device title never becomes a net name;
* the untouched paths, as controls: a plain cluster still prefers its own
  ``NET`` label over a ground flag (the V3 calibration behaviour), two plain
  labels in one cluster still come out alphabetical, another flag's title still
  names its net, and two pages that happen to draw a short at the same
  coordinate are still two nets.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from boardwise.core.model import BoardModel
from boardwise.parsers.schematic import build_project_model

# --------------------------------------------------------------------------
# synthesised streams (the shape tests/test_038_eprj3.py and
# tests/test_189a2_schematic_nets.py already write)
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
        _record("DOCHEAD", {"docType": "SYMBOL", "uuid": uuid, "editVersion": "3.2.186"}),
        _record("META", {"title": title, "docType": "SYMBOL"}, id_=f"meta-{uuid}"),
    ]
    for index, (number, x, y) in enumerate(pins):
        pin_id = f"{uuid}-pin{number}"
        out.append(_record("PIN", {"x": x, "y": -y, "zIndex": index + 2}, id_=pin_id))
        out.append(_record(
            "ATTR", {"parentId": pin_id, "key": "Pin Number", "value": number},
            id_=f"{pin_id}-n",
        ))
    return out


def _device(uuid: str, title: str) -> list[str]:
    return [
        _record("DOCHEAD", {"docType": "DEVICE", "uuid": uuid, "editVersion": "3.2.186"}),
        _record("META", {"title": title, "docType": 20}, id_=f"meta-{uuid}"),
    ]


def _page(uuid: str) -> str:
    return _record("DOCHEAD", {"docType": "SCH_PAGE", "uuid": uuid})


def _placed(
    *, part_id: str, symbol: str, device: str, x: float, y: float,
    designator: str = "", rotation: float = 0.0, mirror: bool = False,
    z_index: int = 1,
) -> list[str]:
    """One placement in **canvas** coordinates (the stored y is the negation)."""
    out = [
        _record("COMPONENT", {
            "partId": part_id, "x": x, "y": -y, "rotation": rotation,
            "isMirror": mirror, "zIndex": z_index,
        }, id_=f"c-{part_id}"),
        _record("ATTR", {"parentId": part_id, "key": "Symbol", "value": symbol},
                id_=f"s-{part_id}"),
        _record("ATTR", {"parentId": part_id, "key": "Device", "value": device},
                id_=f"v-{part_id}"),
    ]
    if designator:
        out.append(_record(
            "ATTR", {"parentId": part_id, "key": "Designator", "value": designator},
            id_=f"d-{part_id}",
        ))
    return out


def _wire(group: str, points: list[tuple[float, float]], net: str = "") -> list[str]:
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


SHORT = "Short-Symbol"
SHORT_PINS = [("1", -10.0, 0.0), ("2", 10.0, 0.0)]
RES_PINS = [("1", 0.0, 0.0), ("2", 0.0, -20.0)]
FLAG_PINS = [("1", 0.0, 0.0)]
Y = 100.0


def _common_docs() -> list[str]:
    out: list[str] = []
    out += _symbol("sym-short", SHORT, SHORT_PINS)
    out += _device("dev-short", SHORT)
    out += _symbol("sym-r", "R0402", RES_PINS)
    out += _device("dev-r", "R0402")
    out += _symbol("sym-flag", "Ground-PGND", FLAG_PINS)
    out += _device("dev-flag", "Ground-PGND")
    out += _symbol("sym-vcc", "Power-VCC", FLAG_PINS)
    out += _device("dev-vcc", "Power-VCC")
    return out


def _board(tmp_path: Path, lines: list[str], name: str = "038g") -> BoardModel:
    text = "\n".join(_common_docs() + lines) + "\n"
    path = tmp_path / f"{name}.epro2"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("synth.epru", text)
        archive.writestr("project2.json", json.dumps({"title": "synthetic"}))
    project = build_project_model(path)
    assert len(project.boards) == 1
    return project.boards[0]


def _lead(
    group: str, short_pin_x: float, part_x: float, net: str = ""
) -> list[str]:
    """A wire from a short's pin through a resistor's **both** pins.

    ``R0402``'s pins are ``(0, 0)`` and ``(0, -20)``, so a part at ``x`` puts
    them at ``(x, Y)`` and ``(x, Y - 20)``: routing the wire through both keeps
    every pin of the fixture on copper, and the only dangling pin in the file
    is the one a test deliberately leaves dangling.
    """
    return _wire(group, [(short_pin_x, Y), (part_x, Y), (part_x, Y - 20.0)], net=net)


def _pin_net(board: BoardModel, designator: str, number: str) -> str | None:
    return next(p.net for p in board.components[designator].pins if p.number == number)


def _members(board: BoardModel, name: str) -> list[tuple[str, str]]:
    return sorted(board.nets[name].pins)


# --------------------------------------------------------------------------
# 1. the join: a short's two halves are one net, and it is named by the side
#    that carries the parts — not by the alphabet
# --------------------------------------------------------------------------


def test_a_short_joins_the_two_halves_it_bridges(tmp_path):
    """Two parts, one on each half, share one net — and the short is the join.

    Nothing else connects the halves: ``R2`` sits on the left stub, ``R1`` on
    the right one, and the only edge between them is the ``Short-Symbol``
    placement. The name is ``LEFT`` because both sides carry a part and the
    cluster's labels then fall to alphabetical order.
    """
    lines = [_page("page-1")]
    lines += _placed(part_id="s1", symbol="sym-short", device="dev-short", x=100.0, y=Y)
    lines += _placed(part_id="r1", symbol="sym-r", device="dev-r", designator="R1",
                     x=170.0, y=Y, z_index=2)
    lines += _placed(part_id="r2", symbol="sym-r", device="dev-r", designator="R2",
                     x=60.0, y=Y, z_index=3)
    lines += _lead("g-left", 90.0, 60.0, net="LEFT")
    lines += _lead("g-right", 110.0, 170.0, net="RIGHT")
    board = _board(tmp_path, lines)

    left = _pin_net(board, "R2", "1")
    right = _pin_net(board, "R1", "1")
    assert left == right == "LEFT", (
        f"the short must join both halves into one net; got R2.1={left!r} R1.1={right!r}"
    )
    assert _members(board, "LEFT") == [("R1", "1"), ("R1", "2"), ("R2", "1"), ("R2", "2")]


def test_the_pin_bearing_side_names_the_net_even_against_the_alphabet(tmp_path):
    """``AAA`` labels the partless stub, ``ZZZ`` the side with the resistor.

    The net is ``ZZZ``: a label on a stub no part touches is a sense name, not
    the name of the copper that carries the part. Alphabetical order would say
    ``AAA``, which is what the defect produced.
    """
    lines = [_page("page-1")]
    lines += _placed(part_id="s1", symbol="sym-short", device="dev-short", x=100.0, y=Y)
    lines += _placed(part_id="r1", symbol="sym-r", device="dev-r", designator="R1",
                     x=170.0, y=Y, z_index=2)
    lines += _wire("g-stub", [(90.0, Y), (60.0, Y)], net="AAA")
    lines += _lead("g-live", 110.0, 170.0, net="ZZZ")
    board = _board(tmp_path, lines)

    assert _pin_net(board, "R1", "1") == "ZZZ"
    assert "AAA" not in board.nets, "the partless stub must not survive as a net"


def test_a_chain_of_shorts_carries_the_pin_side_label_across_it(tmp_path):
    """Two shorts in series: only the far half carries a part.

    ``AAA`` labels the far stub, ``ZZZ`` the half with the resistor, and the
    wire between the two shorts is unnamed. The pin-side label has to travel
    the whole chain, so the net is ``ZZZ`` — not the alphabetically earlier
    ``AAA``, and not an auto ``NETn``.
    """
    lines = [_page("page-1")]
    lines += _placed(part_id="s1", symbol="sym-short", device="dev-short", x=100.0, y=Y)
    lines += _placed(part_id="s2", symbol="sym-short", device="dev-short", x=130.0, y=Y,
                     z_index=2)
    lines += _placed(part_id="r1", symbol="sym-r", device="dev-r", designator="R1",
                     x=170.0, y=Y, z_index=3)
    lines += _wire("g-stub", [(60.0, Y), (90.0, Y)], net="AAA")
    lines += _wire("g-mid", [(110.0, Y), (120.0, Y)])
    lines += _lead("g-live", 140.0, 170.0, net="ZZZ")
    board = _board(tmp_path, lines)

    assert _pin_net(board, "R1", "1") == "ZZZ"


def test_a_power_flag_outranks_the_pin_side_label(tmp_path):
    """A rail flag on the bridged net is the drawing's own name for it.

    ``PGND`` wins over the ``ZZZ`` label on the part-bearing side; the short is
    still joined, which is why the flag reaches the resistor at all.
    """
    lines = [_page("page-1")]
    lines += _placed(part_id="s1", symbol="sym-short", device="dev-short", x=100.0, y=Y)
    lines += _placed(part_id="f1", symbol="sym-flag", device="dev-flag", x=75.0, y=Y,
                     z_index=2)
    lines += _placed(part_id="r1", symbol="sym-r", device="dev-r", designator="R1",
                     x=170.0, y=Y, z_index=3)
    lines += _wire("g-stub", [(90.0, Y), (75.0, Y), (60.0, Y)], net="AAA")
    lines += _lead("g-live", 110.0, 170.0, net="ZZZ")
    board = _board(tmp_path, lines)

    assert _pin_net(board, "R1", "1") == "PGND"
    assert "ZZZ" not in board.nets


@pytest.mark.parametrize("flag_first", [True, False])
def test_the_power_flag_wins_whichever_order_the_stream_lists_it(tmp_path, flag_first):
    """Flag record before or after the short: same net, same name.

    The forced-name pass runs in stream order, so a flag that arrives *before*
    the placement it names is the case that has to keep working.
    """
    short = _placed(part_id="s1", symbol="sym-short", device="dev-short", x=100.0, y=Y)
    flag = _placed(part_id="f1", symbol="sym-flag", device="dev-flag", x=75.0, y=Y,
                   z_index=2)
    lines = [_page("page-1")] + (flag + short if flag_first else short + flag)
    lines += _placed(part_id="r1", symbol="sym-r", device="dev-r", designator="R1",
                     x=170.0, y=Y, z_index=3)
    lines += _wire("g-stub", [(90.0, Y), (75.0, Y), (60.0, Y)], net="AAA")
    lines += _lead("g-live", 110.0, 170.0, net="ZZZ")
    board = _board(tmp_path, lines)

    assert _pin_net(board, "R1", "1") == "PGND"


def test_two_shorts_sharing_one_side_still_pick_the_part_side_name(tmp_path):
    """The measured pair: ``SLC`` and ``IC+`` bridged onto one mid wire.

    The mid wire is the one carrying the resistor and it is unnamed, so the
    pin-side rule has nothing to say and the alphabetical fallback over *this
    cluster's* labels decides: ``IC+``, not ``SLC``.
    """
    lines = [_page("page-1")]
    lines += _placed(part_id="s1", symbol="sym-short", device="dev-short", x=100.0, y=Y)
    lines += _placed(part_id="s2", symbol="sym-short", device="dev-short", x=100.0, y=140.0,
                     z_index=2)
    lines += _placed(part_id="r1", symbol="sym-r", device="dev-r", designator="R1",
                     x=145.0, y=120.0, z_index=3)
    lines += _wire("g-slc", [(90.0, Y), (60.0, Y)], net="SLC")
    # the mid wire: s1's right pin, the resistor's two pins, s2's right pin
    lines += _wire("g-mid", [(110.0, Y), (145.0, Y), (145.0, 120.0), (145.0, 140.0),
                             (110.0, 140.0)])
    lines += _wire("g-icp", [(90.0, 140.0), (60.0, 140.0)], net="IC+")
    board = _board(tmp_path, lines)

    assert _pin_net(board, "R1", "1") == "IC+"
    assert _pin_net(board, "R1", "2") == "IC+"
    assert "SLC" not in board.nets


# --------------------------------------------------------------------------
# 2. the degenerate halves: no empty net, no invented name
# --------------------------------------------------------------------------


def test_a_short_with_a_dangling_pin_joins_nothing_and_names_nothing(tmp_path):
    """One pin on the wire, one pin on bare canvas: no join, no new net.

    The wired half keeps the net it already had, and the model gains nothing —
    an empty net would be a connection nobody drew.
    """
    lines = [_page("page-1")]
    # pin 2 lands on (120, Y), where this board draws no wire at all
    lines += _placed(part_id="s1", symbol="sym-short", device="dev-short", x=110.0, y=Y)
    lines += _placed(part_id="r1", symbol="sym-r", device="dev-r", designator="R1",
                     x=60.0, y=Y, z_index=2)
    lines += _wire("g-live", [(100.0, Y), (60.0, Y), (60.0, Y - 20.0)], net="AAA")
    board = _board(tmp_path, lines)

    assert _pin_net(board, "R1", "1") == "AAA"
    assert sorted(board.nets) == ["AAA"]


def test_a_short_never_lends_its_device_title_to_a_net(tmp_path):
    """No ``Symbol`` net, ever — the defect's own invented name.

    ``Short-Symbol`` must not resolve through the flag path (which takes the
    half after the hyphen), so the joined net is ``ZZZ`` and nothing in the
    model is called ``Symbol``.
    """
    lines = [_page("page-1")]
    lines += _placed(part_id="s1", symbol="sym-short", device="dev-short", x=100.0, y=Y)
    lines += _placed(part_id="r1", symbol="sym-r", device="dev-r", designator="R1",
                     x=170.0, y=Y, z_index=2)
    lines += _wire("g-stub", [(90.0, Y), (60.0, Y)], net="AAA")
    lines += _lead("g-live", 110.0, 170.0, net="ZZZ")
    board = _board(tmp_path, lines)

    assert "Symbol" not in board.nets
    assert sorted(board.nets) == ["ZZZ"]


def test_another_flags_title_still_names_its_net(tmp_path):
    """The title gate is exact: ``Power-VCC`` is still ``VCC``.

    The control for the new gate — only the jumper's own title is excluded, so
    the flag path that ten other boards depend on is untouched.
    """
    lines = [_page("page-1")]
    lines += _placed(part_id="f1", symbol="sym-vcc", device="dev-vcc", x=125.0, y=Y)
    lines += _placed(part_id="r1", symbol="sym-r", device="dev-r", designator="R1",
                     x=170.0, y=Y, z_index=2)
    lines += _wire("g-rail", [(110.0, Y), (125.0, Y), (170.0, Y), (170.0, Y - 20.0)])
    board = _board(tmp_path, lines)

    assert _pin_net(board, "R1", "1") == "VCC"


# --------------------------------------------------------------------------
# 3. the untouched paths (controls)
# --------------------------------------------------------------------------


def test_a_plain_cluster_still_prefers_its_label_over_a_ground_flag(tmp_path):
    """V3's calibration behaviour: a hand-written label beats the flag name.

    Nothing here is a short, so the priority order is the old one — this test
    fails if the short rule were applied to every cluster.
    """
    lines = [_page("page-1")]
    lines += _placed(part_id="f1", symbol="sym-flag", device="dev-flag", x=125.0, y=Y)
    lines += _placed(part_id="r1", symbol="sym-r", device="dev-r", designator="R1",
                     x=170.0, y=Y, z_index=2)
    lines += _wire("g-sig", [(110.0, Y), (125.0, Y), (170.0, Y), (170.0, Y - 20.0)],
                   net="SIG")
    board = _board(tmp_path, lines)

    assert _pin_net(board, "R1", "1") == "SIG"


def test_two_plain_labels_in_one_cluster_stay_alphabetical(tmp_path):
    """The control for the short rule: two wires meeting at a point are one
    cluster with two labels, and it still picks the first one alphabetically."""
    lines = [_page("page-1")]
    lines += _placed(part_id="r1", symbol="sym-r", device="dev-r", designator="R1",
                     x=100.0, y=Y)
    lines += _wire("g-b", [(100.0, Y), (100.0, Y - 20.0)], net="B1")
    lines += _wire("g-a", [(100.0, Y - 20.0), (60.0, Y - 20.0)], net="A1")
    board = _board(tmp_path, lines)

    assert _pin_net(board, "R1", "1") == _pin_net(board, "R1", "2") == "A1"


def test_two_pages_at_one_coordinate_are_two_nets(tmp_path):
    """Same coordinate, two sheets: a page is its own coordinate system.

    A short on page 1 must not reach across to page 2's wires, and each half
    keeps the name its own page gave it.
    """
    lines: list[str] = []
    for tag in ("P1", "P2"):
        lines.append(_page(f"page-{tag}"))
        lines += _placed(part_id=f"s-{tag}", symbol="sym-short", device="dev-short",
                         x=100.0, y=Y)
        lines += _placed(part_id=f"r-{tag}", symbol="sym-r", device="dev-r",
                         designator=f"R{tag}", x=170.0, y=Y, z_index=2)
        lines += _wire(f"g-stub-{tag}", [(90.0, Y), (60.0, Y)], net=f"{tag}_STUB")
        lines += _lead(f"g-live-{tag}", 110.0, 170.0, net=f"{tag}_LIVE")
    board = _board(tmp_path, lines)

    assert _pin_net(board, "RP1", "1") == "P1_LIVE"
    assert _pin_net(board, "RP2", "1") == "P2_LIVE"
    assert "P1_STUB" not in board.nets and "P2_STUB" not in board.nets
    assert _members(board, "P1_LIVE") == [("RP1", "1"), ("RP1", "2")]
    assert _members(board, "P2_LIVE") == [("RP2", "1"), ("RP2", "2")]
