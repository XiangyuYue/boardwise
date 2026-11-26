"""623A-05: a capacitor's MPN is never read as a resistance on a real path.

The observation behind 623A-05 is true at the **reader**: `mpn_resistance_readings`
does not gate, by contract — its docstring says the caller must already know the
part is a resistor, and the reader answers what the token's letters spell
(`CC0603KRX7R9BB104` carries `7R9`, `CL10B104KB8NNNC` carries `4K`/`104K`).

What this pin records is that the production paths do gate, so that looseness
cannot become a wrong resistance on a capacitor:

* `rules/params.py::_kind_of` decides the kind from the shelf category first and
  then from the board's own value field; a `100nF` value is a capacitor and the
  MPN reader is not asked at all;
* `engines/checkup.py`'s resistor classifier returns early on the `C`/`L`/`FB`/
  `RV`/`RT` designator prefixes *before* its `mpn_resistance_candidates` branch;
* `core/metaparams.py` asks the resistance reader only in its non-capacitor
  branch.

A resistor-declared part carrying a capacitor's MPN is a mislabelled board, and
there the resistance reading is the honest answer to the question the caller
asked — it is not this batch's to guess away.
"""

from __future__ import annotations

from boardwise.core.model import Component
from boardwise.rules.params import _kind_of


def test_a_capacitors_value_decides_the_kind_before_its_mpn_is_read():
    cap = Component(uid="u1", designator="C1", value="100nF", mpn="CC0603KRX7R9BB104")
    assert _kind_of(cap, None) == ("capacitor", "")


def test_a_capacitor_value_with_no_mpn_still_reads_as_a_capacitor():
    cap = Component(uid="u2", designator="C2", value="4.7u", mpn="")
    assert _kind_of(cap, None) == ("capacitor", "")
