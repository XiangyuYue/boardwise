"""038Q18: a block port drawn on a wire truncates that net's member list.

The defect this batch fixes is a **false single-member verdict**. Measured
2026-11-15 on the P47 container: the placed block's port 1 sits on the ``NRST``
wire end, ``U10.7`` is the only pin the netlist files on that net — because a
block is not a ``Component`` at all (038Q17) and nothing about its inside is
expanded — and ``arch-nrst-closure`` read the count of 1 as "the reset pin is
bare on a net label", the F3 shape.

The fix is disclosure, not an exemption: the parser files that net in the
existing ``unproven_nets`` channel with a new reason
(``TRUNCATED_BY_BLOCK_PORT``), and the rule already refuses on a net listed
there. So both directions stay withheld ("a capacitor is on it" and "nothing is
on it" are equally unproven), no global pass is granted, no threshold moves.

Everything here is **anonymous synthetic** streams built in ``tmp_path``: the
real containers stay in ``.tmp_038q_native/`` and are never copied into the
repository. What the tests pin:

* N1 — the port-on-a-wire net is marked, with a locatable detail;
* N2 — an ordinary pin with no wire is **not** marked (its single-member
  reading is still the rule's to make);
* N3 — adding the block moves no net name, no member and no pin position: the
  union-find never learns about the block, the marking only reads a root;
* the negatives — no wire under the port, empty ports, an NC port, an
  unresolved block candidate;
* rotation/mirror go through the one transform the parts pass uses;
* several blocks on one net share one entry, and an existing
  duplicate-designator reason keeps its code and gains the new detail.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import pytest

from boardwise.core.model import (
    TRUNCATED_BY_BLOCK_PORT,
    TRUNCATED_BY_DESIGNATOR,
    WELDED_BY_NAME,
)
from boardwise.parsers.schematic import build_project_model, collect_block_instances
from boardwise.rules.unproven import (
    BLOCK_PORT_TAIL,
    MIXED_TRUNCATION_TAIL,
    REFUSAL_SENTENCES,
    TRUNCATION_PHRASES,
    RefusedNet,
    is_unproven_refusal,
    unproven_missing_fact,
    unproven_nets,
    unproven_outcome,
)

PAGE = "0a0a0a0a0a0a0a0a"
BLOCK_SYM = "2222222222222222"
BLOCK_PART = "3333333333333333"
SRC_SYM = "4444444444444444"
SRC_CBB = "55" * 32
ORD_SYM = "6666666666666666"
ORD_PART = "R0402.1"
ORD_DEV = "7777777777777777"


# --------------------------------------------------------------------------
# record builders (``.epru`` lines: <envelope JSON>||<body JSON>|)
# --------------------------------------------------------------------------


def _record(type_: str, body: dict | None = None, id_: str | None = None) -> str:
    envelope: dict = {"type": type_, "ticket": 1}
    if id_ is not None:
        envelope["id"] = id_
    payload = json.dumps(body, separators=(",", ":")) if body is not None else ""
    return json.dumps(envelope, separators=(",", ":")) + "||" + payload + "|"


def _attr(uid: str, parent: str, key: str, value) -> str:
    return _record("ATTR", {"parentId": parent, "key": key, "value": value}, id_=uid)


def _symbol_doc(uuid: str, part_id: str, *, doc_type, title: str,
                source: str | None = None,
                pins: tuple[tuple[str, float, float], ...] = ()) -> list[str]:
    """One SYMBOL document; ``pins`` are ``(number, canvas x, canvas y)``.

    The stored y is the negation of the canvas y (010c), exactly as a real
    ``.epru`` writes it, so the reader's own negation is what the test exercises.
    """
    out = [_record("DOCHEAD", {"docType": "SYMBOL", "uuid": uuid}),
           _record("PART", {"title": ""}, id_=part_id)]
    for index, (number, x, y) in enumerate(pins, start=1):
        pin_id = f"{uuid}-pin{number}"
        out.append(_record("PIN", {"x": x, "y": -y, "zIndex": index}, id_=pin_id))
        out.append(_attr(f"{pin_id}-number", pin_id, "Pin Number", number))
        out.append(_attr(f"{pin_id}-name", pin_id, "Pin Name", number))
        out.append(_attr(f"{pin_id}-type", pin_id, "Pin Type", "Passive"))
    meta: dict = {"title": title, "docType": doc_type}
    if source is not None:
        meta["source"] = source
    out.append(_record("META", meta, id_=f"{uuid}-meta"))
    return out


def _device_doc(uuid: str, *, title: str, designator: str, symbol: str) -> list[str]:
    return [
        _record("DOCHEAD", {"docType": "DEVICE", "uuid": uuid}),
        _record("META", {"title": title, "attributes": {
            "Designator": designator, "Symbol": symbol,
        }}, id_=f"{uuid}-meta"),
    ]


def _placed(uid: str, part_id: str, *, x: float, y: float, z_index: int = 1,
            designator: str | None = None, symbol: str | None = None,
            rotation: float = 0.0, mirror: bool = False) -> list[str]:
    """One placement, given in **canvas** coordinates (stored y is negated)."""
    out = [_record("COMPONENT", {
        "partId": part_id, "x": x, "y": -y, "rotation": rotation,
        "isMirror": mirror, "zIndex": z_index,
    }, id_=uid)]
    if symbol is not None:
        out.append(_attr(f"{uid}-sym", uid, "Symbol", symbol))
    if designator is not None:
        out.append(_attr(f"{uid}-des", uid, "Designator", designator))
    return out


def _wire(group: str, points: list[tuple[float, float]], net: str = "") -> list[str]:
    """One ``WIRE`` head with its ``LINE`` segments, in canvas coordinates."""
    out = [_record("WIRE", {"zIndex": 40}, id_=group)]
    for index, ((x0, y0), (x1, y1)) in enumerate(zip(points, points[1:])):
        out.append(_record("LINE", {
            "lineGroup": group, "startX": x0, "startY": -y0,
            "endX": x1, "endY": -y1,
        }, id_=f"{group}-{index}"))
    if net:
        out.append(_attr(f"{group}-net", group, "NET", net))
    return out


def _page(*lines: str) -> list[str]:
    return [_record("DOCHEAD", {"docType": "SCH_PAGE", "uuid": PAGE}), *lines]


def _project(tmp_path: Path, lines: list[str], name: str = "synth.epro2") -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("synth.epru", "\n".join(lines) + "\n")
        archive.writestr("project2.json", json.dumps({"title": "synthetic"}))
    return path


# --------------------------------------------------------------------------
# the synthesised board: one block port and R1.1 on "NRST", R2.1 dangling
# --------------------------------------------------------------------------

#: Block symbol port 1, symbol-local canvas offset.
BLOCK_PIN = (-10.0, 0.0)
#: The block's placement.
BLOCK_AT = (100.0, 100.0)
#: Where that port lands: (90, 100) — the wire's left end.
PORT_POINT = (BLOCK_AT[0] + BLOCK_PIN[0], BLOCK_AT[1] + BLOCK_PIN[1])
#: R1's pin 1 lands on the wire's right end; R2 is drawn with no wire at all.
R1_AT = (140.0, 100.0)
R2_AT = (300.0, 300.0)


def _ordinary_documents() -> list[str]:
    return _symbol_doc(
        ORD_SYM, ORD_PART, doc_type=2, title="R0402",
        pins=(("1", 0.0, 0.0), ("2", 0.0, -20.0)),
    ) + _device_doc(ORD_DEV, title="R0402", designator="R?", symbol=ORD_SYM)


def _board(*, with_block: bool = True, block_designator: str = "CBB1",
           block_pins: tuple = (("1", *BLOCK_PIN),), block_at=BLOCK_AT,
           block_rotation: float = 0.0, block_mirror: bool = False,
           extra: tuple = (), extra_docs: tuple = (),
           wire_points: tuple = (PORT_POINT, (R1_AT[0], R1_AT[1])),
           ) -> tuple[list[str], list[str]]:
    """The one-page board: an ordinary part on a wire, one dangling part, a block."""
    lines = _page(
        *_wire("w-nrst", list(wire_points), net="NRST"),
        *_placed("r1", ORD_PART, x=R1_AT[0], y=R1_AT[1], designator="R1",
                 symbol=ORD_SYM),
        *_placed("r2", ORD_PART, x=R2_AT[0], y=R2_AT[1], designator="R2",
                 symbol=ORD_SYM),
    )
    documents = _ordinary_documents()
    if with_block:
        lines += _placed(
            "blk1", BLOCK_PART, x=block_at[0], y=block_at[1], z_index=1,
            designator=block_designator, symbol=BLOCK_SYM,
            rotation=block_rotation, mirror=block_mirror,
        )
        documents.extend(_symbol_doc(
            BLOCK_SYM, BLOCK_PART, doc_type=17, title="CBB BLOCK",
            source=f"{SRC_SYM}|{SRC_CBB}", pins=block_pins,
        ))
    lines.extend(extra)
    return lines, documents + list(extra_docs)


def _built(tmp_path: Path, name: str = "synth.epro2", **kwargs) -> tuple[object, Path]:
    lines, documents = _board(**kwargs)
    path = _project(tmp_path, lines + documents, name=name)
    return build_project_model(path), path


# --------------------------------------------------------------------------
# N1 — the port on a wire marks the net, and the refusal says why
# --------------------------------------------------------------------------


def test_a_block_port_on_a_wire_marks_the_net_unproven(tmp_path):
    model, path = _built(tmp_path)
    # the block is not a component and not a member: the reading is unchanged
    assert sorted(model.boards[0].components) == ["R1", "R2"]
    assert model.boards[0].nets["NRST"].pins == [("R1", "1")]
    # ... but the membership is now known to be short, with a locatable detail
    assert model.boards[0].unproven_pages("NRST") == (PAGE,)
    code, detail = model.boards[0].unproven_reason("NRST")
    assert code == TRUNCATED_BY_BLOCK_PORT
    assert "CBB1" in detail and "'1'" in detail and PAGE in detail

    found = unproven_nets(model.boards[0], ("NRST",))
    (entry,) = found
    assert entry.truncated is True
    assert entry.detail == detail
    missing = unproven_missing_fact(found)
    assert TRUNCATION_PHRASES[TRUNCATED_BY_BLOCK_PORT] in missing
    # the coverage gate counts this refusal (issue #66's family)
    assert is_unproven_refusal(missing) is True

    outcome = unproven_outcome(
        "arch-nrst-closure", "U10 pin7", found,
        what="whether anything else sits on this reset pin's net 'NRST'",
    )
    assert outcome.state == "UNKNOWN"
    assert "may have members missing from it" in outcome.message
    # and the old single-member wording is not what the reader is told
    assert "single-member" not in outcome.message

    # the block itself is still identified, and its port is still read
    (row,) = collect_block_instances(path)
    assert (row.identity_status, [port.number for port in row.ports]) == (
        "verified", ["1"],
    )


def test_the_new_reason_is_in_every_refusal_family():
    assert RefusedNet("N", (PAGE,), TRUNCATED_BY_BLOCK_PORT, "d").truncated is True
    assert TRUNCATED_BY_BLOCK_PORT in TRUNCATION_PHRASES
    assert TRUNCATION_PHRASES[TRUNCATED_BY_BLOCK_PORT] in REFUSAL_SENTENCES


# --------------------------------------------------------------------------
# N2 / N3 — an ordinary dangling pin is untouched, and no net name drifts
# --------------------------------------------------------------------------


def test_an_ordinary_pin_with_no_wire_is_not_marked(tmp_path):
    """N2: the block's presence must not exempt a真 dangling ordinary pin."""
    model, _path = _built(tmp_path)
    board = model.boards[0]
    # R2.1 has no wire at all: its own auto-named net is a real reading, and it
    # is NOT filed as unproven — the rule's single-member verdict still stands
    dangling = board.components["R2"].pins[0].net
    assert dangling and dangling != "NRST"
    assert board.unproven_pages(dangling) is None
    assert board.nets[dangling].pins == [("R2", "1")]
    assert sorted(board.unproven_nets) == ["NRST"]


def test_adding_a_block_moves_no_net_name_member_or_pin_position(tmp_path):
    """N3: the union-find never learns about the block; the marking only reads."""
    without, _ = _built(tmp_path, name="plain.epro2", with_block=False)
    with_block, _ = _built(tmp_path, name="marked.epro2")
    plain, marked = without.boards[0], with_block.boards[0]
    assert {name: net.pins for name, net in plain.nets.items()} == {
        name: net.pins for name, net in marked.nets.items()
    }
    assert plain.pin_wires == marked.pin_wires
    assert plain.unproven_nets == {}
    assert sorted(marked.unproven_nets) == ["NRST"]
    assert plain.components.keys() == marked.components.keys()


# --------------------------------------------------------------------------
# the negatives
# --------------------------------------------------------------------------


def test_a_port_with_no_wire_under_it_is_not_marked(tmp_path):
    """The wire is moved one unit away: the port is drawn, but not on copper."""
    model, _ = _built(tmp_path, wire_points=((90.0, 101.0), (R1_AT[0], R1_AT[1])))
    board = model.boards[0]
    assert board.unproven_nets == {}
    assert board.unproven_reasons == {}


def test_a_block_with_no_ports_is_not_marked(tmp_path):
    model, path = _built(tmp_path, block_pins=())
    assert model.boards[0].unproven_nets == {}
    (row,) = collect_block_instances(path)
    assert row.ports == ()


def test_an_nc_block_port_is_not_marked(tmp_path):
    """``NO_CONNECT`` skips the port for the connectivity graph, and for this."""
    lines, documents = _board()
    lines.append(_attr("nc-1", "blk1-e1", "NO_CONNECT", True))
    path = _project(tmp_path, lines + documents)
    model = build_project_model(path)
    assert model.boards[0].unproven_nets == {}


def test_an_unresolved_block_candidate_is_not_marked(tmp_path):
    """No ``Symbol`` anchor, so no ports are known: nothing is claimed."""
    lines, documents = _board(with_block=False)
    lines += _placed("blk1", BLOCK_PART, x=BLOCK_AT[0], y=BLOCK_AT[1],
                     designator=None, symbol=None)
    documents.extend(_symbol_doc(
        BLOCK_SYM, BLOCK_PART, doc_type=17, title="CBB BLOCK",
        source=f"{SRC_SYM}|{SRC_CBB}", pins=(("1", *BLOCK_PIN),),
    ))
    path = _project(tmp_path, lines + documents)
    model = build_project_model(path)
    assert model.boards[0].unproven_nets == {}
    (row,) = collect_block_instances(path)
    assert (row.identity_status, row.identity_reason) == (
        "unresolved", "symbol-missing",
    )


# --------------------------------------------------------------------------
# the pose goes through the one transform the parts pass uses
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rotation, mirror, expected",
    [
        (90.0, False, (100.0, 130.0)),   # CCW 90: local (30,0) -> (0,30)
        (0.0, True, (70.0, 100.0)),      # mirror: local (30,0) -> (-30,0)
        (90.0, True, (100.0, 130.0)),    # mirror *after* rotation: (0,30) -> (0,30)
    ],
)
def test_a_rotated_or_mirrored_port_uses_the_parts_transform(
    tmp_path, rotation, mirror, expected,
):
    """One arithmetic, not two: the port lands where ``transform_point`` says.

    Three wires are drawn — the true posed point, the two points a hand-rolled
    or differently ordered transform would produce — and only the true one may
    be marked.
    """
    decoys = {(130.0, 100.0), (100.0, 70.0), (70.0, 100.0), (90.0, 130.0)} - {expected}
    lines, documents = _board(
        block_at=(100.0, 100.0),
        block_pins=(("1", 30.0, 0.0),),
        block_rotation=rotation,
        block_mirror=mirror,
        wire_points=(expected, (expected[0] + 40.0, expected[1])),
        extra=tuple(
            line
            for index, point in enumerate(sorted(decoys))
            for line in _wire(
                f"w-decoy-{index}",
                [point, (point[0] + 20.0, point[1])],
                net=f"DECOY{index}",
            )
        ),
    )
    path = _project(tmp_path, lines + documents)
    model = build_project_model(path)
    board = model.boards[0]
    # The decoys are drawn wire ends at the points a hand-rolled or
    # differently ordered transform would produce. A port placed by either of
    # those would mark a DECOY name (or leave NRST unmarked) and fail below.
    marked = sorted(board.unproven_nets)
    assert marked == ["NRST"]


# --------------------------------------------------------------------------
# several blocks on one net, and 107's reason kept
# --------------------------------------------------------------------------


def test_two_blocks_on_one_net_share_one_entry(tmp_path):
    lines, documents = _board(
        wire_points=((PORT_POINT), (BLOCK_AT[0] + 120.0, BLOCK_AT[1]),
                     (BLOCK_AT[0] + 200.0, BLOCK_AT[1])),
        extra=tuple(_placed(
            "blk2", BLOCK_PART, x=BLOCK_AT[0] + 200.0 + 10.0, y=BLOCK_AT[1],
            designator="CBB2", symbol=BLOCK_SYM,
        )),
    )
    path = _project(tmp_path, lines + documents)
    board = build_project_model(path).boards[0]
    assert board.unproven_pages("NRST") == (PAGE,)
    code, detail = board.unproven_reason("NRST")
    assert code == TRUNCATED_BY_BLOCK_PORT
    assert "CBB1" in detail and "CBB2" in detail


def test_an_existing_duplicate_reason_keeps_its_code_and_gains_the_detail(tmp_path):
    """107's evidence is not replaced by this batch's; the detail is appended."""
    lines, documents = _board(
        extra=tuple(_placed(
            "r1-again", ORD_PART, x=R1_AT[0], y=R1_AT[1],
            designator="R1", symbol=ORD_SYM,
        )),
    )
    path = _project(tmp_path, lines + documents)
    board = build_project_model(path).boards[0]
    assert "R1" in board.duplicate_designators
    code, detail = board.unproven_reason("NRST")
    assert code == TRUNCATED_BY_DESIGNATOR  # kept, not overwritten
    assert "2nd and later placement" in detail  # 107's clause
    assert "a native block's ports are not expanded" in detail  # this batch's
    assert "CBB1" in detail
    assert board.unproven_pages("NRST") == (PAGE,)

# --------------------------------------------------------------------------
# 1. the closing clause belongs to the gap that is actually there
# --------------------------------------------------------------------------


def test_a_block_port_refusal_does_not_end_on_107s_clause(tmp_path):
    """Block-only: the old tail sent the reader hunting a duplicate designator."""
    model, _path = _built(tmp_path)
    found = unproven_nets(model.boards[0], ("NRST",))
    message = unproven_outcome(
        "arch-nrst-closure", "U10 pin7", found,
        what="whether anything else sits on this reset pin's net 'NRST'",
    ).message
    assert message.endswith(BLOCK_PORT_TAIL)
    assert not message.endswith(
        "a placement the model did not keep may be the part this judgement needs"
    )
    # and the sentence still says what the netlist is short of
    assert "a native block's ports are not expanded" in message


def test_a_judgement_hitting_both_gaps_says_both(tmp_path):
    """Mixed duplicate + block: one merged closing clause, neither half hidden."""
    lines, documents = _board(
        extra=(
            *_placed("r1-again", ORD_PART, x=R1_AT[0], y=R1_AT[1],
                     designator="R1", symbol=ORD_SYM),
            # a second, wire-only net that a block port also meets
            *_wire("w-pad", [(BLOCK_AT[0] + 300.0, BLOCK_AT[1]),
                             (BLOCK_AT[0] + 400.0, BLOCK_AT[1])], net="PAD"),
            *_placed("blk2", BLOCK_PART, x=BLOCK_AT[0] + 410.0, y=BLOCK_AT[1],
                     designator="CBB2", symbol=BLOCK_SYM),
        ),
    )
    path = _project(tmp_path, lines + documents)
    board = build_project_model(path).boards[0]
    assert board.unproven_reason("NRST")[0] == TRUNCATED_BY_DESIGNATOR
    assert board.unproven_reason("PAD")[0] == TRUNCATED_BY_BLOCK_PORT
    found = unproven_nets(board, ("NRST", "PAD"))
    message = unproven_outcome(
        "arch-nrst-closure", "U10 pin7", found, what="whether it is alone",
    ).message
    assert message.endswith(MIXED_TRUNCATION_TAIL)
    assert "a placement the model did not keep" in message
    assert "a native CBB block's ports are not expanded" in message


def test_a_107_only_or_welded_refusal_keeps_its_words():
    """The old sentences are byte-for-byte, for the two older gaps."""
    duplicate = RefusedNet("VCC", ("p1",), TRUNCATED_BY_DESIGNATOR,
                           "the 2nd and later placement of '100NF' are not in this netlist")
    message = unproven_outcome(
        "decap-required-caps", "C1", [duplicate], what="whether a capacitor sits on it",
    ).message
    assert message.endswith(
        "a placement the model did not keep may be the part this judgement needs"
    )
    assert BLOCK_PORT_TAIL not in message

    welded = RefusedNet("VCC", ("p1", "p2"), WELDED_BY_NAME, "")
    welded_message = unproven_outcome(
        "decap-required-caps", "C1", [welded], what="whether a capacitor sits on it",
    ).message
    assert welded_message.endswith(
        "whether those pages are one board is not in this reading"
    )


# --------------------------------------------------------------------------
# 2. the report's note names the two gaps apart (real checkup report)
# --------------------------------------------------------------------------


@pytest.fixture
def no_bridge(monkeypatch, tmp_path):
    """An isolated ``BOARDWISE_HOME`` and a bridge that would fail loudly if used.

    ``--file`` is the disconnected path, so the report must be built without a
    daemon: any construction/opening of a client here is a defect in the run.
    """
    monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path / "home"))
    import boardwise.bridge.client as client_module

    class _Unused:
        opened = 0

        def __init__(self, *args, **kwargs):
            pass

        def open(self, *args, **kwargs):
            type(self).opened += 1
            raise AssertionError("the --file path must not open the bridge")

        async def call(self, *args, **kwargs):
            raise AssertionError("the --file path must not call the bridge")

        async def aclose(self):
            return None

    monkeypatch.setattr(client_module, "BridgeClient", _Unused)
    return _Unused


def _checkup_note(tmp_path: Path, path: Path, no_bridge) -> dict:
    from boardwise.cli import _cmd_checkup

    args = argparse.Namespace(
        file=str(path), project="", instance="", out=str(tmp_path / "out"), port=None,
    )
    assert _cmd_checkup(args) in (0, 1, 3)
    assert no_bridge.opened == 0
    report = json.loads(
        (tmp_path / "out" / "report.json").read_text(encoding="utf-8")
    )
    return report["source"]["unprovenNets"]


def test_the_report_note_about_a_block_net_does_not_claim_a_designator_repeat(
    tmp_path, no_bridge,
):
    """Real checkup report source: a block net's note, not a string constant."""
    lines, documents = _board()
    path = _project(tmp_path, lines + documents)
    unproven = _checkup_note(tmp_path, path, no_bridge)
    assert unproven["reasons"]["NRST"] == TRUNCATED_BY_BLOCK_PORT
    note = unproven["note"]
    assert "原生 CBB 块端口" in note and "没有展开" in note
    # the *designator* sentence is not written about this net at all; the block
    # sentence may say "not a designator repeat", which is the opposite claim
    assert "成员清单可能已被位号重复截断" not in note


def test_the_report_note_keeps_107s_words_and_lists_the_two_gaps_apart(
    tmp_path, no_bridge,
):
    """A board with both gaps: two sentences, each naming its own cause."""
    lines, documents = _board(
        extra=(
            *_placed("r1-again", ORD_PART, x=R1_AT[0], y=R1_AT[1],
                     designator="R1", symbol=ORD_SYM),
            *_wire("w-pad", [(BLOCK_AT[0] + 300.0, BLOCK_AT[1]),
                             (BLOCK_AT[0] + 400.0, BLOCK_AT[1])], net="PAD"),
            *_placed("blk2", BLOCK_PART, x=BLOCK_AT[0] + 410.0, y=BLOCK_AT[1],
                     designator="CBB2", symbol=BLOCK_SYM),
        ),
    )
    path = _project(tmp_path, lines + documents)
    unproven = _checkup_note(tmp_path, path, no_bridge)
    assert unproven["reasons"]["NRST"] == TRUNCATED_BY_DESIGNATOR
    assert unproven["reasons"]["PAD"] == TRUNCATED_BY_BLOCK_PORT
    note = unproven["note"]
    designator_nets = sorted(
        name for name, reason in unproven["reasons"].items()
        if reason == TRUNCATED_BY_DESIGNATOR
    )
    block_nets = sorted(
        name for name, reason in unproven["reasons"].items()
        if reason == TRUNCATED_BY_BLOCK_PORT
    )
    # 107's sentence is still there, word for word, and lists only its own nets
    assert "成员清单可能已被位号重复截断" in note
    assert "（" + "、".join(designator_nets) + "）" in note
    assert "PAD" not in "、".join(designator_nets)
    # and the block sentence is separate and lists only its own net
    assert "原生 CBB 块端口" in note
    assert "（" + "、".join(block_nets) + "）" in note
    assert block_nets == ["PAD"]


def test_the_report_note_for_a_designator_only_board_is_unchanged(
    tmp_path, no_bridge,
):
    """No block on the page: the note is exactly the pre-038Q18 sentence."""
    lines, documents = _board(
        with_block=False,
        extra=tuple(_placed("r1-again", ORD_PART, x=R1_AT[0], y=R1_AT[1],
                            designator="R1", symbol=ORD_SYM)),
    )
    path = _project(tmp_path, lines + documents)
    unproven = _checkup_note(tmp_path, path, no_bridge)
    assert unproven["reasons"]["NRST"] == TRUNCATED_BY_DESIGNATOR
    names = sorted(
        name for name, reason in unproven["reasons"].items()
        if reason == TRUNCATED_BY_DESIGNATOR
    )
    assert unproven["note"] == (
        "这些网名（" + "、".join(names) + "）的成员清单可能已被位号重复"
        "截断：图上重复位号的第 2+ 份 placement 没有进这份网表，被丢弃的那份"
        "可能就是这张网上的关键件（去耦电容之类）；同一批规则对它们只报 "
        "UNKNOWN，通过和违规都不成立"
    )
    assert "原生 CBB 块端口" not in unproven["note"]


# --------------------------------------------------------------------------
# 3. every name filed as unproven is a net the model actually has
# --------------------------------------------------------------------------


def test_a_wire_only_block_connection_is_still_a_net(tmp_path):
    """A wire whose only connection is a block port: ``unproven`` and ``nets`` agree.

    No ordinary pin sits on it, so the reverse-built netlist had no reason to
    create the name — but the drawing has that named wire, and a name the model
    calls unproven while ``nets`` has never heard of it is a contradiction.
    """
    lines, documents = _board(
        wire_points=((PORT_POINT), (BLOCK_AT[0] + 120.0, BLOCK_AT[1])),
    )
    path = _project(tmp_path, lines + documents)
    board = build_project_model(path).boards[0]
    assert board.unproven_pages("NRST") == (PAGE,)
    assert "NRST" in board.nets
    assert board.nets["NRST"].pins == []  # empty is the reading, not a gap
    # every unproven name is one of the model's nets, board-wide
    assert set(board.unproven_nets) <= set(board.nets)


def test_the_wire_only_net_does_not_renumber_the_auto_names(tmp_path):
    """Created after the names are fixed, so NETn is where it was."""
    # The same drawing twice, once without the block: the wire then has no pin
    # on it at all, so ``NRST`` is a name only the block can put in the model.
    points = ((PORT_POINT), (BLOCK_AT[0] + 120.0, BLOCK_AT[1]))
    without, _ = _built(
        tmp_path, name="plain.epro2", with_block=False, wire_points=points,
    )
    wire_only, _ = _built(
        tmp_path, name="wireonly.epro2", wire_points=points,
    )
    plain_board, marked_board = without.boards[0], wire_only.boards[0]
    assert "NRST" not in plain_board.nets
    assert set(marked_board.nets) - set(plain_board.nets) == {"NRST"}
    assert marked_board.nets["NRST"].pins == []
    for name in plain_board.nets:
        assert plain_board.nets[name].pins == marked_board.nets[name].pins


# --------------------------------------------------------------------------
# 4. one designator, two block instances: two facts
# --------------------------------------------------------------------------


def test_two_block_instances_with_one_label_stay_two_facts(tmp_path):
    """Same ``CBB1`` on both: the detail names their primitive ids, not one port."""
    lines, documents = _board(
        wire_points=((PORT_POINT), (BLOCK_AT[0] + 120.0, BLOCK_AT[1]),
                     (BLOCK_AT[0] + 200.0, BLOCK_AT[1])),
        extra=tuple(_placed(
            "blk2", BLOCK_PART, x=BLOCK_AT[0] + 210.0, y=BLOCK_AT[1],
            designator="CBB1", symbol=BLOCK_SYM,
        )),
    )
    path = _project(tmp_path, lines + documents)
    board = build_project_model(path).boards[0]
    _code, detail = board.unproven_reason("NRST")
    assert "'blk1'" in detail and "'blk2'" in detail
    assert detail.count("port '1'") == 2
