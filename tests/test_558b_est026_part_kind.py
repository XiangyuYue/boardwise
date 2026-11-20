"""558B: ``EST026`` is a connector because its own family word says so.

558's real recompute left three rows (``U1`` / ``U3`` / ``U5``) on the
``ic-facts`` obligation with all seven facts missing, although the public
catalogue lists the part under *Through Hole Quick Connects/Disconnects* and
the scanned drawing is titled 「6.3端子(双脚内固定式)技术图纸」. Those two
readings support **品类识别 only** — they name no MPN and print no pin table
(``evidence/558/est026-visual.json``), so the batch's whole delivery is one
exact family word in the shared connector vocabulary, and the obligation then
falls out of the existing ``classify_part`` read instead of a second 判型 copy
in ``checkup``.

Everything here is synthetic and cheap; the real-side comparison is
``.tmp_558b/after/comparison.json`` (read-only recompute of ``.tmp_555``).
"""

from __future__ import annotations

from boardwise.core.model import Component, DesignModel, Net, Pin
from boardwise.core.partkind import (
    BASIS_METADATA,
    BASIS_PIN_FLOOR,
    BASIS_PREFIX,
    CONNECTOR_WORDS,
    KIND_CAPACITOR,
    KIND_CONNECTOR,
    KIND_IC,
    classify_part,
)
from boardwise.engines.checkup import (
    OBLIGATION_CONNECTOR_PINOUT,
    OBLIGATION_IC_FACTS,
    PINOUT_SOURCE_NONE,
    datasheet_obligation,
)
from boardwise.rules.connectivity import DecouplingPerIC

#: The schematic-side shape 555 wrote for the part: a ``U`` designator, the
#: catalogue's own name in ``device_name``, and 「插件」 as the supplier
#: footprint. No shelf entry, no MPN — which is exactly why the designator
#: letter was the only signal the read had.
EST026_PROPS = {"device_name": "EST026", "Supplier Footprint": "插件"}


def _comp(designator: str, *, value: str = "", footprint: str = "", mpn: str = "",
          lcsc: str = "", props: dict | None = None, pins=()) -> Component:
    return Component(
        uid=f"u-{designator}",
        designator=designator,
        value=value,
        footprint=footprint,
        mpn=mpn,
        lcsc_part=lcsc,
        props=dict(props or {}),
        pins=[Pin(str(number), str(name), net) for number, name, net in pins],
    )


def _two(designator: str, **kwargs) -> Component:
    kwargs["pins"] = [("1", "1", "A"), ("2", "2", "B")]
    return _comp(designator, **kwargs)


def _three(designator: str, **kwargs) -> Component:
    kwargs["pins"] = [("1", "1", "A"), ("2", "2", "B"), ("3", "3", "C")]
    return _comp(designator, **kwargs)


def _model(*components: Component) -> DesignModel:
    model = DesignModel(components={c.designator: c for c in components})
    nets: dict[str, Net] = {}
    for component in components:
        for pin in component.pins:
            if pin.net:
                nets.setdefault(pin.net, Net(name=pin.net)).pins.append(
                    (component.designator, pin.number)
                )
    model.nets = nets
    return model


def test_the_est026_terminal_reads_as_a_connector_from_its_own_word():
    """The vocabulary, not the designator: ``EST026`` decides, and it is exact.

    ``EST`` alone must **not** be a word — it would swallow every part whose
    MPN happens to start with those three letters, which is the false-positive
    shape 192B ① measured for ``MOS``/``USB``. The family word is the code
    itself, matched on a token boundary like the rest of the ASCII vocabulary.
    """
    assert "EST026" in CONNECTOR_WORDS
    assert "EST" not in CONNECTOR_WORDS

    read = classify_part(_two("U1", lcsc="C52878", props=EST026_PROPS))
    assert read.kind == KIND_CONNECTOR, read
    assert read.basis == BASIS_METADATA, read
    assert "EST026" in read.reason, read.reason


def test_the_terminal_owes_a_pinout_and_not_the_seven_ic_facts():
    """``checkup``'s own obligation reader, unmodified — it only had to be fed."""
    term = _two("U1", lcsc="C52878", props=EST026_PROPS)
    row = datasheet_obligation(term)
    assert row["obligation"] == OBLIGATION_CONNECTOR_PINOUT, row
    assert row["kind"] == KIND_CONNECTOR, row
    # No pin table has been obtained: the row asks for one and claims nothing.
    assert row["pinoutSource"] == PINOUT_SOURCE_NONE, row


def test_another_est_part_number_is_not_a_connector():
    """The word is ``EST026``; a different EST-numbered IC keeps its reading."""
    read = classify_part(_three("U7", mpn="EST0701"))
    assert read.kind == KIND_IC, read
    assert read.basis == BASIS_PREFIX, read

    row = datasheet_obligation(_three("U7", mpn="EST0701"))
    assert row["obligation"] == OBLIGATION_IC_FACTS, row


def test_an_ordinary_three_pin_ic_is_still_ic_facts():
    """The unchanged half of the vocabulary: no declaration, no word, ``U``."""
    ic = _comp(
        "U2", mpn="ACME3", pins=[("1", "VIN", "A"), ("2", "GND", "GND"), ("3", "OUT", "B")]
    )
    assert classify_part(ic).kind == KIND_IC
    row = datasheet_obligation(ic)
    assert row["obligation"] == OBLIGATION_IC_FACTS, row


def test_the_decoupling_rule_does_not_read_the_terminal_as_an_ic():
    """The rule that asks 「does this IC need a capacitor?」, at the part in hand.

    The terminal's two pins are on ``A``/``B``; nothing else is on the board, so
    the only way a row could appear is by reading ``U1`` as an IC. The three-pin
    control keeps the rule honest: it must still speak when it should.
    """
    term = _two("U1", lcsc="C52878", props=EST026_PROPS)
    assert classify_part(term).kind == KIND_CONNECTOR
    assert DecouplingPerIC().check(_model(term)) == []

    ic = _comp("U2", pins=[("1", "VIN", "A"), ("2", "GND", "GND"), ("3", "OUT", "B")])
    assert len(DecouplingPerIC().check(_model(ic))) == 1


def test_the_u_designated_resistor_and_the_passives_are_unchanged():
    """190's anchors: the floor still clears the resistor, a value still a cap."""
    resistor = classify_part(_two("U6", footprint="R1206", mpn="FRC1206J334 TS"))
    assert resistor.kind != KIND_IC, resistor
    assert resistor.basis == BASIS_PIN_FLOOR, resistor

    assert classify_part(_two("C1", value="100nF")).kind == KIND_CAPACITOR
