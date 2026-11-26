"""623A-04: a decimal number with a bare unit letter is a capacitance.

`0.1u`, `4.7u` and `2.2n` read as nothing while `0.1uF` read fine: the suffix
grammar demanded the trailing `F`, and the trade's mid-letter notation never
covers a decimal point (`4u7` is its shape) nor a four-figure integer run.

Only the **decimal** form is opened here. An integer run with a bare letter is
the mid-letter notation's field and its length is bounded there — `12345n` and
`1000u` stay refused by that scan, which 102 pinned on purpose.

623A-03 (`0R` not reading as 0 Ω) is deliberately **not** in this batch: making
the board grammar read it moves three parts in `rules/pcb/derating.py`'s
resistor/0 Ω-jumper classification, and `tests/test_153_derating_package.py`
pins the current split by name. That is a cross-layer decision, not a spelling
repair, and it is recorded as open in `evidence/623a/REPORT.md`.
"""

from __future__ import annotations

import pytest

from boardwise.core.values import parse_capacitance_farads, parse_resistance_ohms


def test_a_decimal_number_with_a_bare_unit_letter_is_a_capacitance():
    assert parse_capacitance_farads("0.1u") == pytest.approx(1e-7)
    assert parse_capacitance_farads("4.7u") == pytest.approx(4.7e-6)
    assert parse_capacitance_farads("2.2n") == pytest.approx(2.2e-9)


def test_the_capacitance_spellings_that_already_read_keep_their_values():
    assert parse_capacitance_farads("0.1uF") == pytest.approx(1e-7)
    assert parse_capacitance_farads("100nF") == pytest.approx(1e-7)
    assert parse_capacitance_farads("4u7") == pytest.approx(4.7e-6)
    assert parse_capacitance_farads("2n2") == pytest.approx(2.2e-9)


def test_a_zero_capacitance_is_no_reading():
    assert parse_capacitance_farads("0n") is None
    assert parse_capacitance_farads("0u") is None
    assert parse_capacitance_farads("0.0u") is None


def test_the_refusals_this_batch_does_not_open_stay_closed():
    assert parse_capacitance_farads("100F") is None, "the unit needs its own letter"
    assert parse_capacitance_farads("2N2222") is None, "a transistor is not a capacitance"
    assert parse_capacitance_farads("0u1") is None, "the leading-zero mid-letter spelling is not owned"
    assert parse_capacitance_farads("100nF63V") is None, "a merchant tail is not a value"
    assert parse_capacitance_farads("12345n") is None, "an integer run's length is the mid-letter scan's rule (102)"
    assert parse_capacitance_farads("1000u") is None, "same rule: a four-figure integer run is not opened here"


def test_zero_ohm_jumper_spellings_read_as_zero():
    # 623A-03 (岳 2026-11-26 裁决：`0R` 该读). `0R` was the one spelling the board
    # grammar refused while `0R0`/`R0`/`0Ω` read as 0 Ω.
    assert parse_resistance_ohms("0R") == 0.0
    assert parse_resistance_ohms("0R0") == 0.0
    assert parse_resistance_ohms("R0") == 0.0
    assert parse_resistance_ohms("0Ω") == 0.0


def test_resistance_spellings_keep_their_values():
    assert parse_resistance_ohms("4R7") == pytest.approx(4.7)
    assert parse_resistance_ohms("47R") == pytest.approx(47.0)
    assert parse_resistance_ohms("0R1") == pytest.approx(0.1)
    assert parse_resistance_ohms("R010") == pytest.approx(0.01)
    assert parse_resistance_ohms("4K7") == pytest.approx(4700.0)
    assert parse_resistance_ohms("0K1") is None, "only R owns the leading zero"
