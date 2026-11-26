"""623A-06 / 623A-07: SI prefixes on voltage and current; the exponent's ceiling.

623A-06 — `1KV` / `500mV` / `10mV` / `1MV` and `100nA` / `1kA` read as nothing
while a bare `100` read as 100.0: the voltage grammar had no prefix branch and
the current grammar knew only `m`/`u`, so the two spellings every datasheet
prints were the ones refused.

623A-07 — the EIA exponent is the code's third **digit**, so the grammar's own
ceiling is 9. 岳's ruling (2026-11-26): real capacitors do exist at 108 (10 x
10^8 pF = 1 mF), so the ceiling stays 9 and only a *four*-figure code is
refused.  This pin records that reading: `108`/`109` are read, `1010` is not.
"""

from __future__ import annotations

import pytest

from boardwise.core.values import (
    decode_eia_3digit,
    parse_current_amps,
    parse_voltage_volts,
)


def test_voltage_prefixes_are_read():
    assert parse_voltage_volts("1KV") == pytest.approx(1000.0)
    assert parse_voltage_volts("1kV") == pytest.approx(1000.0)
    assert parse_voltage_volts("1MV") == pytest.approx(1e6)
    assert parse_voltage_volts("500mV") == pytest.approx(0.5)
    assert parse_voltage_volts("10mV") == pytest.approx(0.01)


def test_voltage_spellings_that_already_read_keep_their_values():
    assert parse_voltage_volts("3V3") == pytest.approx(3.3)
    assert parse_voltage_volts("3.30V") == pytest.approx(3.3)
    assert parse_voltage_volts("3.3") == pytest.approx(3.3)
    assert parse_voltage_volts("310VDC") == pytest.approx(310.0)
    assert parse_voltage_volts("V_310V") == pytest.approx(310.0)


def test_current_prefixes_are_read():
    assert parse_current_amps("100nA") == pytest.approx(1e-7)
    assert parse_current_amps("1kA") == pytest.approx(1000.0)
    assert parse_current_amps("500mA") == pytest.approx(0.5)
    assert parse_current_amps("5A") == pytest.approx(5.0)


def test_units_this_batch_does_not_open_stay_closed():
    assert parse_current_amps("5") is None, "a current needs its unit"
    assert parse_current_amps("5V") is None
    assert parse_voltage_volts("1M") is None, "a prefix without a unit is not a voltage"
    assert parse_voltage_volts("1K") is None


def test_the_eia_exponent_ceiling_is_the_digit_itself():
    # 623A-07, 岳 2026-11-26: real capacitors exist at 108 (1 mF), so the
    # ceiling stays 9 -- the third digit -- and a four-figure code has no
    # reading at all.
    assert decode_eia_3digit("108", 1e-12) == pytest.approx(1e-3)
    assert decode_eia_3digit("109", 1e-12) == pytest.approx(1e-2)
    assert decode_eia_3digit("1010", 1e-12) is None
    assert decode_eia_3digit("9999", 1.0) is None
