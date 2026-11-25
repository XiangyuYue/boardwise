"""572-G-1: the duplicate-carrier floor measures the row that **prints**.

572's hole batch froze the shape and measured it on the working tree of
`961b3b7`:

* a visible `native` name whose reserved box stands past its own run is
  re-seated onto that run by ``_native_carrier_cover`` (543I, the
  "run is long enough -> shift the row in" branch), and the seat is recorded in
  ``built.native_carrier_rows`` -- which is only what ``attributeMoves`` reads;
* the rows the duplicate-carrier floor reads are ``built.name_carriers``, and
  the label pass wrote the entry for a visible `native` label with the layout's
  **reserved** box (053T: ``carrier_row`` for a native label *is* ``label.bbox``);
* nothing wrote the seat back into that book, so ``_duplicate_carrier_problems``
  compared a box nobody prints.

Measured on 572-G: the seat landed at ``[185, 0, 215, 7]``, the reservation stood
165 units away at ``[380, 0, 410, 7]``, the two names printed **1** unit apart
while the floor is 20, and the gate reported ``gate_gap_AB=134``,
``dup_problems=[]`` -- ``FALSE_GREEN``.

What this file pins:

* the 572-G shape on a minimal page (two visible native carriers of one net, 1
  unit apart after the seat): the reservations alone are a false green, the seat
  is what the floor must read, and the floor then refuses the pair by name;
* the negative control on the same page -- a seat that clears the floor stays
  green, and the book still holds the seat (the pass is not simply silent).

The page is assembled from the production books, not from a second model: the
``name_carriers`` entries are written exactly as the label pass writes them
(``drawapply.module_plan``, 053T/534), so a test that passes here cannot be
passing on bookkeeping production does not do.
"""

from __future__ import annotations

from boardwise.core.changeplan import PlanDrawPart, PlanDrawPin, PlanDrawWire
from boardwise.core.layoutplan import LayoutLabel, LayoutPlan
from boardwise.engines import drawapply
from boardwise.engines import drawcompiler as dc

PAGE_BOX = (0.0, 0.0, 600.0, 600.0)

#: The CH343 connector's own pin block, as the p1e page places it: one pin column
#: at ``x = 200``, the body centre at ``y = 705``, and rows mirrored about it
#: (``A6``/``A7`` at +-5, ``B6``/``B7`` at -+15). 543L pairs this block by that
#: mirror; these four carriers are the pairs it declares.
_BODY = (139.5, 639.5, 190.5, 770.5)
_PINS = (("A6", 5.0), ("A7", -5.0), ("B6", -15.0), ("B7", 15.0))
_ROW = (213.0, 227.0)  # x span of a carrier row (print width 14)


def _declared_page(gap_second_x=246.0, with_partners=True):
    """Four carriers of two nets on one mirrored pin block (572-G-2).

    ``D+`` prints on ``A6`` and ``B6`` -- two rows of one pin column, each the
    mirror of a ``D-`` row (``A7``/``B7``). That is the block 543L declared, and
    the floor must read the pair as declared, not as one name printed twice. The
    second row is 19 units from the first unless ``gap_second_x`` moves it out;
    ``with_partners=False`` drops the ``D-`` half, leaving two carriers whose
    mirrors nobody prints (the negative control).
    """
    built = drawapply._Built()
    built.parts.append(
        PlanDrawPart(
            spec_id="USB1", designator="USB1", symbol_ref="SYM",
            x=165.0, y=705.0,
            pins=[
                PlanDrawPin(number=pin, dx=35.0, dy=offset)
                for pin, offset in _PINS
            ],
        )
    )
    carriers = [("D+", "A6", 710.0), ("D+", "B6", 690.0)]
    if with_partners:
        carriers += [("D-", "A7", 700.0), ("D-", "B7", 720.0)]
    for index, (net, pin, y) in enumerate(carriers):
        built.wires.append(
            PlanDrawWire(
                net=net, points=[(200.0, y), (240.0, y)],
                from_pin=f"USB1.{pin}",
            )
        )
        left = _ROW[0] if pin in ("A6", "A7") else gap_second_x
        built.name_carriers.append(
            (net, f"wire[{index}]", (left, y - 4.5, left + 14.0, y + 4.5))
        )
    return built


def _floor(built):
    built.posed_bodies = {"USB1": _BODY}
    return drawapply._duplicate_carrier_problems(built)


class _Wire:
    def __init__(self, net, points, from_pin=""):
        self.net = net
        self.points = [(float(x), float(y)) for x, y in points]
        self.from_pin = from_pin


def _label(net, x, y, bbox):
    return LayoutLabel(
        net=net, text=net, bbox=bbox, x=x, y=y,
        text_mode=dc.TEXT_MODE_NATIVE,
    )


def _page(second_y):
    """Two visible native carriers of one net; the subject is re-seated.

    ``subject`` rides the 30-unit run ``x 185..215`` and reserved a 30-unit box
    165 units past its far end, so the cover can only seat it by shifting it in
    (the run is exactly as long as the row). ``other`` already prints on its own
    run, so its entry is untouched: the pair whose distance the floor has to
    read is ``subject``'s seat against ``other``'s real row.
    """
    subject = _label("SIG", 215.0, 103.5, (380.0, 100.0, 410.0, 107.0))
    other = _label(
        "SIG", 200.0, second_y,
        (170.0, second_y - 3.5, 200.0, second_y + 3.5),
    )
    wires = [
        _Wire("SIG", [(185, 103.5), (215, 103.5)]),
        _Wire("SIG", [(150, second_y), (250, second_y)]),
    ]
    labels = [subject, other]
    built = drawapply._Built()
    built.wires.extend(wires)
    for index, label in enumerate(labels):
        # The label pass's own write (drawapply.py:1605-1611): a visible
        # `native` label riding wire `index` records that wire as the carrier
        # and the layout's **reserved** box as the row it prints (053T).
        built.name_carriers.append(
            (str(label.net), f"wire[{index}]", tuple(float(v) for v in label.bbox))
        )
    return built, labels, wires


def _covered(built, labels):
    return drawapply._native_carrier_cover(
        built, LayoutPlan(labels=list(labels)), {}, {}, [], PAGE_BOX,
    )


def test_572g_a_reseated_row_is_the_row_the_duplicate_floor_measures():
    """The false green, then the refusal it should have been (572-G)."""
    # On the reservations alone the floor says nothing -- that is the defect,
    # stated as an assertion: 180 units between boxes, 1 between printed rows.
    reserved, _, _ = _page(95.5)
    assert drawapply._duplicate_carrier_problems(reserved) == []

    built, labels, wires = _page(95.5)
    assert _covered(built, labels) == []
    seated = built.native_carrier_rows[id(labels[0])]
    assert seated == (185.0, 100.0, 215.0, 107.0), seated

    # 572-G-1: the carrier the floor reads is the carrier the name prints on.
    entry = [
        row for _net, identity, row in built.name_carriers
        if identity == "wire[0]"
    ]
    assert entry == [seated], built.name_carriers
    # The other carrier already printed on its own run: it must keep its row.
    other = [
        row for _net, identity, row in built.name_carriers
        if identity == "wire[1]"
    ]
    assert other == [(170.0, 92.0, 200.0, 99.0)], built.name_carriers

    problems = drawapply._duplicate_carrier_problems(built)
    assert len(problems) == 1, problems
    text = problems[0]
    assert "wire[0] and wire[1]" in text, text
    assert "1 units apart" in text, text
    assert "(185, 100)-(215, 107)" in text, text
    assert "(170, 92)-(200, 99)" in text, text
    assert "20-unit duplicate-carrier floor" in text, text


def test_572g_a_reseated_row_clear_of_the_floor_stays_green():
    """The negative control: the same page, a real gap above the floor."""
    control, _, _ = _page(43.5)
    assert drawapply._duplicate_carrier_problems(control) == []

    built, labels, wires = _page(43.5)
    assert _covered(built, labels) == []
    seated = built.native_carrier_rows[id(labels[0])]
    assert seated == (185.0, 100.0, 215.0, 107.0), seated

    # The seat is still written into the book the floor reads -- green here is
    # a real distance, not a book nobody updates.
    entry = [
        row for _net, identity, row in built.name_carriers
        if identity == "wire[0]"
    ]
    assert entry == [seated], built.name_carriers
    assert drawapply._duplicate_carrier_problems(built) == []
    # The 543I gate reads the same seat and has nothing to say either.
    assert drawapply.native_carrier_problems(
        labels, built.wires, PAGE_BOX, built.native_carrier_rows,
    ) == []


def test_572g2_a_declared_mirrored_block_is_not_a_duplicate():
    """572-G-2: two rows 19 apart on a block 543L declared are a pair.

    ``D+`` prints on two rows of one pin column, and each of those pins' mirror
    is printed too -- on the one other net ``D-``. The compiler paired exactly
    this block and gave each pair one run length, so the 19-unit row gap is the
    declared picture, not one statement printed twice.
    """
    built = _declared_page()
    assert _floor(built) == []


def test_572g2_a_non_mirrored_pair_at_19_is_still_refused():
    """The negative control: the same rows, no mirror partners printed.

    ``D+``'s two carriers still leave the same pins 19 apart, but nothing prints
    ``A6``'s or ``B6``'s mirror, so no mirrored pair is declared for them: the
    floor names the pair. This is the shape 岳's ruling forbade exempting -- two
    carriers of one net and nothing else.
    """
    built = _declared_page(with_partners=False)
    problems = _floor(built)
    assert len(problems) == 1, problems
    text = problems[0]
    assert "net D+: carriers wire[0] and wire[1]" in text, text
    assert "19 units apart" in text, text
    assert "(213, 705.5)-(227, 714.5)" in text, text
    assert "(246, 685.5)-(260, 694.5)" in text, text


def test_572g2_a_declared_block_clear_of_the_floor_stays_green():
    """The other control: a declared block whose rows really clear the floor."""
    built = _declared_page(gap_second_x=247.0)
    assert _floor(built) == []
