"""623A-01: a four-digit value code must not be read as its last three digits.

`values.mpn_value_code` answers three-figure EIA codes only (its docstring says
so: "the finder is dumb; callers gate").  On a four-digit resistor code such as
`RTT034702FTP` (47 kΩ) the last three figures sat right before a letter tail,
so they passed the existing "after the code comes a letter" rule and came back
as `'702'` — a capacitance code, which `core/decap.py` then read as a value.
Measured on this tree before the fix: `'702'`.

The fix keeps the finder dumb: a three-figure reading must be a **whole** digit
run, so a four-digit code has no three-figure reading at all (`None`), and the
consumers see "cannot decode" instead of a wrong capacitance.
"""

from __future__ import annotations

from boardwise.core.values import mpn_value_code


def test_a_four_digit_code_is_refused_whole():
    assert mpn_value_code("RTT034702FTP") is None, (
        "the tail of a four-digit code is not a three-figure value code"
    )


def test_a_bare_four_digit_run_carries_no_three_figure_reading():
    assert mpn_value_code("4702") is None
    assert mpn_value_code("1002") is None


def test_three_figure_codes_keep_their_readings():
    assert mpn_value_code("FRC0805J471 TS") == "471"
    assert mpn_value_code("CL10A225KA8NNNC") == "225"
    assert mpn_value_code("CC0603KRX7R9BB104") == "104"
    assert mpn_value_code("CGA0603X5R105K500JT") == "105"
    assert mpn_value_code("CH340G") == "340"


def test_a_mid_letter_value_spelling_is_not_a_value_code():
    # 623A-02 (fixed in this batch): `R010` states 0.01 Ω to the value grammar,
    # so the finder must not answer the three figures inside it as a code.  The
    # value grammar's own reading is pinned in test_623a_notation_readings.py.
    assert mpn_value_code("R010") is None
    assert mpn_value_code("4K7") is None
    # But a three-figure code with only letters after it stays a code: `472M` is
    # the trade's code-with-tolerance spelling and 86's `4.7 nF` reading is built
    # on the `472` inside it, even though the value grammar reads `M` as mega.
    assert mpn_value_code("472M") == "472"
