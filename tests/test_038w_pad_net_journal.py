"""038W: one pin can own several live ``PAD_NET`` records.

A ``PAD_NET``'s atomic id carries the **pad element id** besides
``(component, pin)``, so the consistency view legitimately keeps the pre-edit
and the post-edit record of one pin — an editor that replaces a footprint hands
the same pin a new pad element id. The per-pin projection
(:attr:`boardwise.parsers.epru.PcbContext.pad_nets_by_pin`) is narrower than
that, so it has to adjudicate the versions itself: highest ticket, then largest
source client (``record.client``, else the ``DOCHEAD`` client), one live record
kept verbatim — and a group the rule cannot order leaves the pin **absent**
plus one ``consistency_unresolved``, never a stream-order guess and never the
old value.

Everything here is synthesised in memory; no fixture is read or written.
"""

from __future__ import annotations

import json

import pytest

from boardwise.core.geometry import ParseStats
from boardwise.parsers.epro2_model import build_design_model
from boardwise.parsers.epru import (
    Epro2Source,
    build_pads,
    collect_pcb_context,
    extract_board,
)
from boardwise.parsers.epru_stream import (
    Document,
    EpruRecord,
    split_documents,
)

COMPONENT = "c1"
PIN = "1"


def _pad_net(
    pad_id: str,
    net: str,
    *,
    pin: str = PIN,
    ticket: int | None = 1,
    client: str | None = None,
    body: dict | None | bool = True,
) -> EpruRecord:
    """One ``PAD_NET`` record; ``body=False`` writes an empty-body tombstone."""
    return EpruRecord(
        line_no=0,
        type="PAD_NET",
        ticket=ticket,
        id=f'["PAD_NET","{COMPONENT}","{pin}","{pad_id}"]',
        first_ticket=ticket,
        body=(
            {
                "componentId": COMPONENT,
                "padNum": pin,
                "padId": pad_id,
                "padNet": net,
            }
            if body is True
            else None
        ),
        client=client,
    )


def _pcb(records: list[EpruRecord], client: str | None = None) -> Document:
    return Document(
        doc_type="PCB",
        uuid="pcb-1",
        edit_version="3.2.186",
        records=records,
        client=client,
    )


def _line(record: EpruRecord) -> str:
    """One ``.epru`` record line, the shape ``iter_epru_records`` reads."""
    envelope: dict = {"type": record.type}
    if record.ticket is not None:
        envelope["ticket"] = record.ticket
    if record.id is not None:
        envelope["id"] = record.id
    if record.client is not None:
        envelope["client"] = record.client
    if record.first_ticket is not None:
        envelope["firstTicket"] = record.first_ticket
    text = json.dumps(envelope)
    return f"{text}|||" if record.body is None else f"{text}||{json.dumps(record.body)}|"


def _head(client: str | None = None) -> str:
    body: dict = {"docType": "PCB", "uuid": "pcb-1", "editVersion": "3.2.186"}
    if client is not None:
        body["client"] = client
    return f"{json.dumps({'type': 'DOCHEAD', 'ticket': 0})}||{json.dumps(body)}|"


def _consistent_document(*lines: str) -> tuple[Document, ParseStats]:
    """The view production reads: ``split_documents(..., consistent=True)``."""
    stats = ParseStats()
    documents = split_documents("\n".join(lines), stats, consistent=True)
    assert [document.doc_type for document in documents] == ["PCB"]
    return documents[0], stats


def _project(
    records: list[EpruRecord], client: str | None = None
) -> tuple[object, ParseStats]:
    stats = ParseStats()
    context = collect_pcb_context(_pcb(records, client=client), {}, stats)
    return context, stats


# --------------------------------------------------------------------------
# 1–2. the new value wins in both file orders, and an empty new net overrides
# --------------------------------------------------------------------------


@pytest.mark.parametrize("new_first", [False, True], ids=["old-first", "new-first"])
def test_new_empty_net_overrides_old_in_both_orders(new_first: bool) -> None:
    """改板把一脚从 ``TIM1_CH1`` 断开：新记录的空网必须覆盖旧网，两种顺序一致。"""
    old = _pad_net("e100", "TIM1_CH1", ticket=185273)
    new = _pad_net("e200", "", ticket=193923)
    records = [new, old] if new_first else [old, new]

    context, stats = _project(records)

    assert context.pad_nets_by_pin[(COMPONENT, PIN)] is None
    assert stats.consistency_unresolved == 0
    # 3: the pad-id table keeps its own shape — both element ids are present.
    assert context.pad_nets_by_pad == {
        (COMPONENT, "e100"): "TIM1_CH1",
        (COMPONENT, "e200"): None,
    }


@pytest.mark.parametrize("new_first", [False, True], ids=["old-first", "new-first"])
def test_new_net_overrides_old_empty_in_both_orders(new_first: bool) -> None:
    """旧空网 → 新 ``DAC1``；新记录（高 ticket）写在文件前面也必须赢。"""
    old = _pad_net("e100", "", ticket=10)
    new = _pad_net("e200", "DAC1", ticket=20)
    records = [old, new] if new_first else [new, old]

    context, stats = _project(records)

    assert context.pad_nets_by_pin[(COMPONENT, PIN)] == "DAC1"
    assert stats.consistency_unresolved == 0


# --------------------------------------------------------------------------
# 3. ticket tie: the larger client wins, document client as the fallback
# --------------------------------------------------------------------------


def test_same_ticket_larger_record_client_wins() -> None:
    context, stats = _project(
        [
            _pad_net("e100", "FROM_A", ticket=7, client="a"),
            _pad_net("e200", "FROM_B", ticket=7, client="b"),
        ]
    )

    assert context.pad_nets_by_pin[(COMPONENT, PIN)] == "FROM_B"
    assert stats.consistency_unresolved == 0


def test_missing_record_client_falls_back_to_dochead_client() -> None:
    """The record with no client of its own speaks for the ``DOCHEAD`` client."""
    context, stats = _project(
        [
            _pad_net("e100", "FROM_DOCHEAD", ticket=7, client=None),
            _pad_net("e200", "FROM_RECORD", ticket=7, client="aaa"),
        ],
        client="zzz",
    )

    assert context.pad_nets_by_pin[(COMPONENT, PIN)] == "FROM_DOCHEAD"
    assert stats.consistency_unresolved == 0


def test_dochead_client_loses_to_a_larger_record_client() -> None:
    context, _ = _project(
        [
            _pad_net("e100", "FROM_DOCHEAD", ticket=7, client=None),
            _pad_net("e200", "FROM_RECORD", ticket=7, client="zzz"),
        ],
        client="aaa",
    )

    assert context.pad_nets_by_pin[(COMPONENT, PIN)] == "FROM_RECORD"


# --------------------------------------------------------------------------
# 4. groups the rule cannot order: absent key, one diagnosis, no old value
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "records, client",
    [
        pytest.param(
            [
                _pad_net("e100", "OLD", ticket=None),
                _pad_net("e200", "NEW", ticket=20),
            ],
            None,
            id="missing-ticket",
        ),
        pytest.param(
            [
                _pad_net("e100", "OLD", ticket=7, client=None),
                _pad_net("e200", "NEW", ticket=7, client=None),
            ],
            None,
            id="tie-without-any-client",
        ),
        pytest.param(
            [
                _pad_net("e100", "OLD", ticket=7, client="a"),
                _pad_net("e200", "NEW", ticket=7, client="a"),
            ],
            None,
            id="same-client-same-ticket-different-nets",
        ),
    ],
)
def test_unorderable_group_leaves_the_pin_absent(
    records: list[EpruRecord], client: str | None
) -> None:
    context, stats = _project(records, client=client)

    assert (COMPONENT, PIN) not in context.pad_nets_by_pin
    assert stats.consistency_unresolved == 1


# --------------------------------------------------------------------------
# 5. a lone live record keeps the historic answer, ticket or not
# --------------------------------------------------------------------------


def test_single_record_without_ticket_is_kept() -> None:
    context, stats = _project([_pad_net("e100", "SOLO", ticket=None)])

    assert context.pad_nets_by_pin[(COMPONENT, PIN)] == "SOLO"
    assert stats.consistency_unresolved == 0


def test_a_winning_tombstone_deletes_the_element_in_the_production_view() -> None:
    """The consistency view first, then the projection — the order production uses.

    ``collect_pcb_context`` is only ever handed documents that already went
    through ``split_documents(..., consistent=True)`` (``load_epro2_source``).
    There a winning empty body is a **tombstone**: it keeps its own slot as an
    ordering boundary and deletes every live version of that element id, so the
    pin has no live record left. The projection then has nothing to adjudicate
    and the pin key is simply absent — the pre-edit ``TIM1_CH1`` is gone rather
    than retained. This used to read the raw stream instead, where the tombstone
    is invisible to :func:`_pad_net_pin_projection` and the old net survived;
    that reading is not what any consumer sees, so it is not kept as a test.
    """
    document, stats = _consistent_document(
        _head(),
        _line(_pad_net("e100", "TIM1_CH1", ticket=10)),
        _line(_pad_net("e100", "", ticket=20, body=False)),
    )
    assert [(record.type, record.body) for record in document.records[1:]] == [
        ("PAD_NET", None)
    ], "the tombstone wins the element id; the live version of it is deleted"
    assert stats.consistency_duplicate_groups == 1
    assert stats.consistency_unresolved == 0

    context = collect_pcb_context(document, {}, stats)

    assert (COMPONENT, PIN) not in context.pad_nets_by_pin, (
        "no live record left: the pin reads 「未判优」, never the deleted net"
    )
    assert (COMPONENT, "e100") not in context.pad_nets_by_pad, (
        "the pad-id table carries no reading for a deleted element either"
    )


# --------------------------------------------------------------------------
# 6. one pin's adjudication does not leak to another pin
# --------------------------------------------------------------------------


def test_other_pins_keep_their_own_nets() -> None:
    context, stats = _project(
        [
            _pad_net("e100", "OLD", ticket=10),
            _pad_net("e200", "NEW", ticket=20),
            _pad_net("e300", "OTHER_PIN", pin="2"),
            _pad_net("e400", "THIRD_PIN", pin="3", ticket=10),
            _pad_net("e500", "", pin="3", ticket=20),
        ]
    )

    assert context.pad_nets_by_pin[(COMPONENT, PIN)] == "NEW"
    assert context.pad_nets_by_pin[(COMPONENT, "2")] == "OTHER_PIN"
    assert context.pad_nets_by_pin[(COMPONENT, "3")] is None
    assert stats.consistency_unresolved == 0


# --------------------------------------------------------------------------
# 7. both public consumers read the same per-pin winner
# --------------------------------------------------------------------------


def _source(
    records: list[EpruRecord], pad_id: str, *, pad_num: str = PIN
) -> tuple[Epro2Source, Document]:
    """A PCB document plus one FOOTPRINT document holding pad ``pad_id``.

    ``pad_num`` is the footprint's **own** pin number for that pad — the value
    ``PAD_NET``'s ``padNum`` has to agree with for the pad-id table to be about
    the same pin.
    """
    footprint = Document(
        doc_type="FOOTPRINT",
        uuid="fp-1",
        edit_version="3.2.186",
        records=[
            EpruRecord(
                line_no=0,
                type="PAD",
                id=pad_id,
                body={
                    "num": pad_num,
                    "layerId": 1,
                    "centerX": 0,
                    "centerY": 0,
                    "defaultPad": {"padType": "RECT", "width": 10, "height": 10},
                },
            )
        ],
    )
    pcb = _pcb(
        [
            EpruRecord(
                line_no=0,
                type="COMPONENT",
                id=COMPONENT,
                body={"x": 0, "y": 0, "rotation": 0, "layerId": 1},
            ),
            EpruRecord(
                line_no=1,
                type="ATTR",
                id=None,
                body={"parentId": COMPONENT, "key": "Footprint", "value": "fp-1"},
            ),
            *records,
        ]
    )
    return Epro2Source(documents=[pcb, footprint]), pcb


@pytest.mark.parametrize(
    "records, expected",
    [
        pytest.param(
            [
                _pad_net("e200", "", ticket=193323),
                _pad_net("e200", "", ticket=193923),
                _pad_net("e201", "", ticket=193424),
            ],
            None,
            id="winner-is-empty",
        ),
        pytest.param(
            [
                _pad_net("e201", "", ticket=10),
                _pad_net("e201", "DAC1", ticket=20),
            ],
            "DAC1",
            id="winner-names-a-net",
        ),
    ],
)
def test_build_pads_and_build_design_model_agree(
    records: list[EpruRecord], expected: str | None
) -> None:
    """PCB geometry and the netlist read one per-pin winner, never two views."""
    source, pcb = _source(records, pad_id="e201")
    stats = ParseStats()

    board = extract_board(pcb, source.footprints(), stats)
    model = build_design_model(source)

    pad = board.pads[0]
    pin = model.components[COMPONENT].pins[0]
    assert pad.pin_number == PIN
    assert pin.number == PIN
    assert pad.net == expected
    assert pin.net == expected
    assert stats.pad_net_pin_mismatch == 0, "a consistent pad counts nothing"


# --------------------------------------------------------------------------
# 8. a pad id whose PAD_NET names another pin (B5 fixA) — disclosed, not corrected
# --------------------------------------------------------------------------


def test_a_renumbered_pad_is_disclosed_and_keeps_its_pad_id_net() -> None:
    """``PAD_NET.padNum`` ≠ ``FOOTPRINT`` ``num``: counted, and the reading stays.

    A board edit renumbers a pad, so a live net record still names the *old* pin
    beside that pad element id (``padNum`` 1) while the footprint's pad with the
    same id now says ``num`` 33. Both records are legitimate survivors of the
    consistency view — different element ids, 038W §1.

    B5 first answered this by handing the pad the per-pin winner; the ruling on
    that repair is that the geometry must **not** be rewritten. Reading pin 1's
    winner onto pin 33's pad put two pins of one part on one net that the
    schematic keeps apart (``C3`` on ROBOT: ``OSC-OUT`` + ``GND``), and the pour
    connectivity then counted an extra ``GND`` island. So the pad-id reading
    stays — the net the file wrote *for this element* — and the disagreement is
    **disclosed** only: ``stats.pad_net_pin_mismatch`` counts the pad, once.
    The count reports that the two records disagree; it does not claim which one
    the board means, and it drops nothing.

    Both public consumers read the pad-id table here, so they agree — the
    netlist puts pin 33 on ``OLD_PIN_NET`` because the pad carries it, and pin 1
    on the same net because its per-pin winner is the same record. That
    agreement is the whole point: one board, one answer.
    """
    source, pcb = _source(
        [
            _pad_net("e204", "OLD_PIN_NET", pin=PIN, ticket=185273),
            _pad_net("e33", "PIN33_NET", pin="33", ticket=193923),
        ],
        pad_id="e204",
        pad_num="33",
    )
    stats = ParseStats()

    board = extract_board(pcb, source.footprints(), stats)
    model = build_design_model(source)

    pad = board.pads[0]
    assert pad.id == "e204" and pad.pin_number == "33"
    assert pad.net == "OLD_PIN_NET", "the pad-id net is kept; the count only reports"

    pins = {pin.number: pin.net for pin in model.components[COMPONENT].pins}
    assert pins == {PIN: "OLD_PIN_NET", "33": "OLD_PIN_NET"}, (
        "the netlist follows the geometry: pin 33 reads the net its own pad carries"
    )
    assert stats.pad_net_pin_mismatch == 1, "the disagreement is disclosed, once"
    assert stats.pads_without_net == 0, "the mismatch counter is not a drop counter"


def test_a_caller_without_the_mapping_keeps_the_old_pad_id_path() -> None:
    """``build_pads`` stays backward compatible: no mapping, old path, no count.

    The mapping is keyword-optional because every pre-B5 caller (and every test
    that builds pads from raw tables) hands five or six arguments. Without it the
    pad-id table is preferred exactly as before — and, with no pairing to compare,
    nothing is disclosed either.
    """
    source, pcb = _source(
        [
            _pad_net("e204", "OLD_PIN_NET", pin=PIN, ticket=185273),
            _pad_net("e33", "PIN33_NET", pin="33", ticket=193923),
        ],
        pad_id="e204",
        pad_num="33",
    )
    stats = ParseStats()
    context = collect_pcb_context(pcb, source.footprints(), stats)

    assert context.pad_pin_by_pad[("c1", "e204")] == PIN

    manual = ParseStats()
    pads = build_pads(
        context.placements,
        source.footprints(),
        context.pad_nets_by_pad,
        context.pad_nets_by_pin,
        manual,
    )

    assert [pad.net for pad in pads] == ["OLD_PIN_NET"], "old path verbatim"
    assert manual.pad_net_pin_mismatch == 0, "no mapping, nothing to correct"


def test_a_consistent_pad_keeps_the_pad_id_reading_verbatim() -> None:
    """``padNum`` agrees with ``num``: nothing to correct, nothing to count."""
    source, pcb = _source(
        [_pad_net("e201", "DAC1", ticket=20)], pad_id="e201", pad_num=PIN
    )
    stats = ParseStats()

    board = extract_board(pcb, source.footprints(), stats)
    model = build_design_model(source)

    assert board.pads[0].net == "DAC1"
    assert model.components[COMPONENT].pins[0].net == "DAC1"
    assert stats.pad_net_pin_mismatch == 0
