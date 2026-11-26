"""623A-09: an all-zero EIA code states no value, so it has no reading.

`decode_eia_3digit("000", base)` returned `0.0` for either base -- a zero-farad
capacitance (and a zero-ohm resistance) read out of a code that says nothing.
Zero-ohm jumpers are spelled `0R`/`0R0` and are read by the value grammar, not
by this decoder; a zero capacitance is not a value any rule can use.  The
decoder therefore refuses the code instead of answering `0.0`, which keeps
"cannot decode" and "decoded to nothing" apart the same way the rest of the
module does.
"""

from __future__ import annotations

import pytest

from boardwise.core.values import decode_eia_3digit


def test_an_all_zero_code_is_refused_not_answered_as_zero():
    assert decode_eia_3digit("000", 1.0) is None, "0 Ω comes from the value grammar, not this decoder"
    assert decode_eia_3digit("000", 1e-12) is None, "a zero-farad capacitance is no reading"


def test_the_three_figure_decoding_itself_is_unchanged():
    assert decode_eia_3digit("471", 1.0) == pytest.approx(470.0)
    assert decode_eia_3digit("104", 1e-12) == pytest.approx(1e-7)
    assert decode_eia_3digit("225", 1e-12) == pytest.approx(2.2e-6)


def test_anything_that_is_not_three_figures_is_still_refused():
    assert decode_eia_3digit("1002", 1.0) is None
    assert decode_eia_3digit("47", 1.0) is None
    assert decode_eia_3digit("47R", 1.0) is None
