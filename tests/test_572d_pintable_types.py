"""572-D regressions: pin-table input typing, pin-number keys, `.ioc` contradictions.

Each test names the hole it closes:

* **D-1** — ``notes`` must be a list. Iterating a non-list let ``5`` raise a
  ``TypeError`` out of the CLI and turned ``"abc"`` into three notes;
* **D-2** — one pin-number key (``pin_key``) for ``cross_check``, gate 2 and
  gate 3. ``pa5`` against ``PA5`` must not be a false defect, and ``PA5`` +
  ``pa5`` in one table must be a duplicate row;
* **D-4** — a non-UTF-8 table file is named "not UTF-8", never "not JSON";
* **D-5** — a net/function *contradiction* with the ``.ioc`` baseline is a
  blocking finding; only absence stays an open question;
* **D-6** — ``version`` is strictly ``int`` 1: ``True`` / ``1.0`` / ``"1"``
  are refused (``True == 1`` is why the value comparison passed).

D-3 (gate 1 unreachable from the CLI) is deliberately **not** here: it needs
CLI arguments and lives outside this batch's file domain.
"""

from __future__ import annotations

import json

import pytest

from boardwise.core.blocks import BlockConnection, BlockInstance, BoardSpec, template_from_json
from boardwise.core.pintable import (
    PinTableError,
    cross_check,
    load_pin_table,
    parse_ioc,
    pin_key,
    pin_table_from_json,
)
from boardwise.engines.pintable_check import (
    DEFECT,
    IOC_CONTRADICTION_KINDS,
    OPEN_QUESTION,
    PinReport,
    check_pin_table,
    ioc_findings,
)


# --------------------------------------------------------------------------
# helpers (same shapes as tests/test_pintable.py)
# --------------------------------------------------------------------------


def table(*pins, **extra):
    body = {
        "kind": "boardwise-firmware-pintable",
        "version": 1,
        "mcu": "ic.stm32g431rbt6",
        "pins": [
            {"number": number, "name": number, "function": function, "net": net}
            for number, function, net in pins
        ],
    }
    body.update(extra)
    return pin_table_from_json(body, where="synthetic")


def mcu_template(*pin_numbers: str, ref: str = "U1"):
    return template_from_json(
        {
            "kind": "boardwise-block-template", "version": 1, "name": "mcu",
            "description": "", "provenance": {"kind": "textbook", "source": "hand"},
            "origin_file": [0.0, 0.0], "bbox_file": [0.0, 0.0, 10.0, 10.0], "notes": [],
            "interface": [
                {"role": number, "net": number, "net_class": "signal"}
                for number in pin_numbers
            ] + [{"role": "GND", "net": "GND", "net_class": "gnd"}],
            "params": [],
            "symbols": {
                "u": {
                    "offsets": {number: [0.0, 0.0] for number in pin_numbers},
                    "body": [0.0, 0.0, 5.0, 5.0],
                    "pin_names": {number: number for number in pin_numbers},
                }
            },
            "components": [
                {
                    "ref": ref, "symbol": "u",
                    "placement": {"x": 0.0, "y": 0.0},
                    "device": {"lcsc": "C431633"}, "footprint": "LQFP-64", "params": {},
                    "pins": [],
                }
            ],
            "geometry": {"wires": [], "flags": [], "labels": []},
        },
        where="mcu-block",
    )


def spec_connecting(template, *pairs, block_id: str = "mcu"):
    return BoardSpec(
        name="synthetic", description="", provenance_kind="textbook",
        provenance_source="hand", provenance_note="",
        blocks=[BlockInstance(id=block_id, template_path="/t/mcu.json",
                              template=template, at=(0.0, 0.0))],
        connections=[
            BlockConnection(net=net, ports=[(block_id, role), ("other", role)])
            for net, role in pairs
        ],
        params={}, sheet_attrs={}, sheet_origin=(0.0, 0.0),
    )


def ioc(**pins) -> str:
    lines = ["Mcu.Name=STM32G431R(6-8-B)Tx", "Mcu.CPN=STM32G431RBT6"]
    for index, (pin, body) in enumerate(pins.items()):
        lines.append(f"Mcu.Pin{index}={pin}")
        if isinstance(body, tuple):
            signal, label = body
        else:
            signal, label = body, ""
        if signal:
            lines.append(f"{pin}.Signal={signal}")
        if label:
            lines.append(f"{pin}.GPIO_Label={label}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# D-1: `notes` is a list of strings, or the table is refused
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,type_name",
    [
        (5, "int"),
        ("abc", "str"),
        ({"a": 1}, "dict"),
        (None, "NoneType"),
    ],
)
def test_notes_that_is_not_a_list_is_refused_by_name(value, type_name):
    with pytest.raises(PinTableError) as caught:
        table(("PA5", "GPIO", "LED1"), notes=value)
    message = str(caught.value)
    assert ".notes" in message, "the error must name the field"
    assert "list" in message
    assert type_name in message, "the error must name the type that was found"


def test_a_string_notes_is_never_split_into_one_note_per_character():
    # The old code did `[... for n in (raw.get("notes") or [])]`, so "abc"
    # became ['a', 'b', 'c'] and the table was accepted.
    with pytest.raises(PinTableError):
        table(("PA5", "GPIO", "LED1"), notes="abc")


def test_notes_may_be_omitted_and_a_list_is_kept():
    assert table(("PA5", "GPIO", "LED1")).notes == []
    assert table(("PA5", "GPIO", "LED1"), notes=["measured from main.h"]).notes == [
        "measured from main.h"
    ]


# --------------------------------------------------------------------------
# D-6: `version` is strictly the integer 1
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "version,type_name",
    [
        (True, "bool"),
        (False, "bool"),
        (1.0, "float"),
        ("1", "str"),
        (2, "int"),
    ],
)
def test_version_must_be_the_integer_one(version, type_name):
    with pytest.raises(PinTableError) as caught:
        table(("PA5", "GPIO", "LED1"), version=version)
    message = str(caught.value)
    assert ".version" in message
    assert type_name in message, "the error must name the type that was found"


def test_the_integer_version_one_is_accepted_and_written_back_as_int():
    parsed = table(("PA5", "GPIO", "LED1"), version=1)
    assert parsed.as_json()["version"] == 1
    assert type(parsed.as_json()["version"]) is int


# --------------------------------------------------------------------------
# D-2: one pin-number key for every gate
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spelling,key",
    [
        ("pa5", "PA5"),
        ("  pa05  ", "PA5"),
        ("PA5.signal", "PA5"),
        ("PA5", "PA5"),
        ("01", "1"),
        ("1", "1"),
        ("PF0-OSC_IN", "PF0"),
    ],
)
def test_pin_key_is_one_spelling_for_one_pin(spelling, key):
    assert pin_key(spelling) == key


def test_gate2_flags_pa5_and_PA5_as_one_pin_under_two_names():
    parsed = table(("PA5", "GPIO", "LED1"), ("pa5", "GPIO", "LED2"))
    report = check_pin_table(parsed)
    assert [finding.rule for finding in report.defects] == ["one-pin-one-row"]
    assert not report.ok


def test_gate2_still_passes_a_table_with_distinct_pins():
    parsed = table(("PA5", "GPIO", "LED1"), ("PA6", "GPIO", "LED2"))
    assert check_pin_table(parsed).ok


def test_gate3_accepts_pa5_against_a_spec_ball_spelled_PA5():
    # Before 572-D-2 this was a false defect: the firmware's `pa5` was compared
    # raw against the spec's ball `PA5`.
    template = mcu_template("PA5", "PA3")
    spec = spec_connecting(template, ("LED1", "PA5"))
    report = check_pin_table(
        table(("pa5", "GPIO", "LED1")), spec=spec, mcu_block_id="mcu"
    )
    assert report.ok, [finding.message for finding in report.defects]
    assert report.matched_nets == 1


def test_cross_check_and_the_gates_agree_on_pa5():
    # `cross_check` always normalized; this pins that it still does, and that
    # a `pa5` table is not reported twice as "missing" against a `PA5` project.
    project = parse_ioc(ioc(PA5=("GPIO_Output", "LED1")))
    assert cross_check(table(("pa5", "GPIO", "LED1")), project) == []


# --------------------------------------------------------------------------
# D-4: a non-UTF-8 table file is named as such
# --------------------------------------------------------------------------


def test_a_non_utf8_table_is_reported_as_not_utf8(tmp_path):
    bad = tmp_path / "non_utf8.json"
    bad.write_bytes(b'{"kind":"boardwise-firmware-pintable","mcu":"\xff\xfe"}')
    with pytest.raises(PinTableError) as caught:
        load_pin_table(bad)
    message = str(caught.value)
    assert "not UTF-8" in message
    assert "not JSON" not in message, (
        "the decode failure must not be reported as a JSON syntax error"
    )


def test_a_malformed_json_table_is_still_reported_as_not_json(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text('{"kind": "boardwise-firmware-pintable",', encoding="utf-8")
    with pytest.raises(PinTableError) as caught:
        load_pin_table(bad)
    message = str(caught.value)
    assert "not JSON" in message
    assert "not UTF-8" not in message


# --------------------------------------------------------------------------
# D-5: a `.ioc` contradiction blocks; absence stays an open question
# --------------------------------------------------------------------------


def test_the_contradiction_kinds_are_named():
    assert IOC_CONTRADICTION_KINDS == {"function_mismatch", "net_mismatch"}


def test_function_contradiction_with_the_ioc_is_a_blocking_finding():
    project = parse_ioc(ioc(PA5=("I2C1_SCL", "LED1")))
    findings = ioc_findings(table(("PA5", "GPIO", "LED1")), project)
    assert [finding.kind for finding in findings] == [DEFECT]
    assert "I2C1_SCL" in findings[0].message
    report = PinReport(findings=list(findings))
    assert not report.ok, "a contradiction with the .ioc must block"


def test_net_contradiction_with_the_ioc_is_a_blocking_finding():
    project = parse_ioc(ioc(PA5=("GPIO_Output", "LED_RED")))
    findings = ioc_findings(table(("PA5", "GPIO", "LED1")), project)
    assert [finding.kind for finding in findings] == [DEFECT]
    assert "LED_RED" in findings[0].message
    assert not PinReport(findings=list(findings)).ok


def test_a_pin_the_ioc_does_not_list_is_an_open_question_not_a_defect():
    # Absence is not contradiction: the CubeMX project may simply be older.
    # Two absences here — the firmware's PA5 is not in the project, and the
    # project's PB6 is not in the firmware — and both stay open questions.
    project = parse_ioc(ioc(PB6=("USART1_TX", "")))
    findings = ioc_findings(table(("PA5", "GPIO", "LED1")), project)
    assert [finding.kind for finding in findings] == [OPEN_QUESTION, OPEN_QUESTION]
    assert PinReport(findings=list(findings)).ok


def test_a_firmware_only_net_is_an_open_question_not_a_defect():
    project = parse_ioc(ioc(PA5="GPIO_Output"))
    findings = ioc_findings(table(("PA5", "GPIO", "LED1")), project)
    assert [finding.kind for finding in findings] == [OPEN_QUESTION]
    assert PinReport(findings=list(findings)).ok


def test_a_consistent_ioc_produces_no_findings_at_all():
    project = parse_ioc(ioc(PA5=("GPIO_Output", "LED1")))
    assert ioc_findings(table(("PA5", "GPIO", "LED1")), project) == []
    # and the JSON shape the CLI prints is a report with nothing in it
    assert json.loads(json.dumps(PinReport().as_json()))["ok"] is True
