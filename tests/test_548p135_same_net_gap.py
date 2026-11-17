"""548P135: the duplicate-net gap re-read in the complete-picture re-selection.

`_local_label_candidate` is handed **one net's** rows by every caller, so its
``L5_DUPLICATE_NET_GAP`` check is a *same-net* ruler. The complete-picture
re-selection in `_local_label_carriers` sees every carrier of the pass at once,
and 548P133 read the gap against all of them: on the real MCU sheet every
candidate rung of LCD_SCK/LED1_K/LED2_K was refused for standing near another
net's row (34/34), so the promised run was left with ``no free name box`` and the
page never compiled. The ruler is the same one; only its rows are filtered to
this net's earlier rows (:func:`drawcompiler._same_net_row_gap`).

The two negative controls below are the causal pair: a **same-net** near row must
still refuse a run (the gap is not loosened), a **foreign-net** near row must not
(refusing on it is the defect), and a row the same net prints **later** in the
pass is not consulted at all.
"""

from __future__ import annotations

from boardwise.engines import drawcompiler as dc
from boardwise.engines.drawlint import L5_DUPLICATE_NET_GAP

#: Two rows whose boxes are ``dy`` apart, the first above the second.
def _row(y: float) -> tuple[float, float, float, float]:
    return (0.0, y, 40.0, y + 9.0)


def _far(y: float) -> tuple[float, float]:
    return (50.0, y)


def test_a_same_net_row_closer_than_the_gap_still_refuses_the_run():
    """The gap itself is untouched: this net's own two names 5 units apart."""
    row_of = [_row(0.0), None, _row(14.0)]
    nets = ["LCD_SDA", "LCD_SCK", "LCD_SDA"]
    reason = dc._same_net_row_gap(_row(9.0), _far(9.0), row_of, nets, 2)
    assert reason is not None
    assert gap_text(reason) == "<20"
    assert "net LCD_SDA" in reason


def test_a_foreign_net_row_closer_than_the_gap_is_not_a_duplicate():
    """A neighbouring net's row is not a duplicate of this one: it must pass."""
    row_of = [_row(0.0), _row(9.0)]
    nets = ["LCD_SDA", "LCD_SCK"]
    assert dc._same_net_row_gap(_row(5.0), _far(5.0), row_of, nets, 1) is None


def test_a_row_the_same_net_prints_later_is_not_consulted():
    """Only rows already printed count: a later carrier cannot refuse this run."""
    row_of = [_row(0.0), _row(4.0)]
    nets = ["LCD_SCK", "LCD_SDA"]
    assert dc._same_net_row_gap(_row(0.0), _far(0.0), row_of, nets, 0) is None


def test_a_same_net_row_at_the_gap_distance_is_legal():
    """The ruler is drawlint's: exactly ``L5_DUPLICATE_NET_GAP`` is not close."""
    row_of = [_row(0.0)]
    nets = ["LCD_SCK"]
    row = (0.0, row_of[0][3] + L5_DUPLICATE_NET_GAP, 40.0,
           row_of[0][3] + L5_DUPLICATE_NET_GAP + 9.0)
    assert dc._row_gap(row, row_of[0]) == L5_DUPLICATE_NET_GAP
    assert dc._same_net_row_gap(row, _far(row[1]), row_of, nets, 0) is None


def gap_text(reason: str) -> str:
    """The measured gap inside the refusal sentence, as a comparison token."""
    number = float(reason.split("would print ")[1].split(" units")[0])
    assert number < L5_DUPLICATE_NET_GAP
    return "<20"


# ------------------------------------- the real page: the promise is re-examined

def test_a_promised_run_is_re_examined_only_after_its_box_is_refused():
    """Wiring: the re-selection is the box phase's own fallback, for promises only.

    The complete-picture re-selection is what lifted the real MCU sheet's
    ``no free name box for the run to (-105, -25)`` (LCD_SCK): a promised run
    (``preplan``) whose box is refused is re-asked here; a run the ordinary ladder
    chose is not. The measured reading of that page is in
    ``evidence/548P135/`` (probe, not a pytest: reaching the carrier pass needs
    the P128 joint-seat repair scaffolding the baseline page does not yet do).
    """
    import inspect

    source = inspect.getsource(dc._local_label_carriers)
    fallback = source.split("if trial is None and reserved_flags[index]:", 1)
    assert len(fallback) == 2, "the box phase has no re-selection fallback"
    body = fallback[1]
    assert "_same_net_row_gap(" in body
    assert "_local_label_paths(" in body
    assert "_local_label_trial_box(" in body
    # The defect itself: the whole picture's rows may not be the duplicate ruler.
    assert "for other in rows" not in body
