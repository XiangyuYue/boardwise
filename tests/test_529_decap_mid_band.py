"""Task 529: the mid band (1 µF < c < 10 µF) is a decoupling role, not ``unknown``.

528 §4 measured the blank: ``HF_FARADS`` is 1 µF, ``BULK_FARADS`` is 10 µF, and
every 2.2 µF / 4.7 µF input ceramic fell into ``unknown`` — a role that means
「nobody wrote a value」 being used for parts whose value *was* written. 529 adds
:data:`~boardwise.rules.pcb.distance.CAP_ROLE_MID`, puts it in the measured pool
on the **same four rail tiers**, and withdraws 191D's temporary
「only WARN when the pool is empty」 narrowing (it existed to dodge the blank).

What this module pins, in order:

1. the role boundaries: ``>= 10 µF`` bulk, ``<= 1 µF`` hf, the band mid, and
   ``unknown`` kept for the two cases it really covers (no value, not a value);
2. that mid adds **no** farad constant and **no** distance tier — the four
   ``200 / 300 / 800 / 200`` mil lines are untouched;
3. that a mid part is graded by each of those four tiers, at the line and one
   step past it;
4. the two shapes the corpus moved (2.2 µF inside its tier → silence; DCDC's
   4.7 µF at 522.6 mil → the recovered WARN), plus the negative anchors 529 must
   not soften: no capacitor at all, bulk-only, unreadable-only, and a genuinely
   far 100 nF;
5. the neighbours 529 must not touch: ``mcusupply``'s ceiling, ``regulator``'s
   bypass pool and ``foc``'s 100 µF storage pool.

Pads are 40x40 mil at the stated coordinates, so the edge-to-edge gap is
``|x_ic - x_cap| - 40`` on one axis — derived by hand next to each assertion.
"""

from __future__ import annotations

import pytest

from boardwise.core.geometry import BoardGeometry, ComponentPlacement, PadGeometry
from boardwise.core.model import Component, DesignModel, Net, Pin
from boardwise.rules.pcb.base import PcbReviewContext
from boardwise.rules.pcb.distance import (
    BULK_FARADS,
    CAP_ROLE_BULK,
    CAP_ROLE_HF,
    CAP_ROLE_MID,
    CAP_ROLE_UNKNOWN,
    DECAP_TIER_CONSUMER,
    DECAP_TIER_MIL,
    DECAP_TIER_ORDER,
    DECAP_TIER_PINS,
    DECAP_TIER_REGULATOR_IN,
    DECAP_TIER_REGULATOR_OUT,
    DECAP_TIER_UNDECLARED,
    DecapDistance,
    HF_FARADS,
    capacitor_role,
)

#: A supply net the rule's own reader knows by name.
RAIL = "+5V"
#: The capacitor's other terminal — a ground net that is not the IC's own.
BRIDGE = "AGND"


# ---------------------------------------------------------------------------
# builders (the shape test_126b / test_190 / test_191d use for this rule)
# ---------------------------------------------------------------------------


def _comp(designator: str, *, value: str = "", footprint: str = "", pins=()) -> Component:
    return Component(
        uid=f"u-{designator}",
        designator=designator,
        value=value,
        footprint=footprint,
        pins=[Pin(str(number), str(name), net) for number, name, net in pins],
    )


def _model(components: list[Component]) -> DesignModel:
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


def _pad(component: str, pin: str, *, x: float, y: float, net: str) -> PadGeometry:
    """One axis-aligned 40x40 mil pad: it spans ``[x-20, x+20]`` × ``[y-20, y+20]``."""
    return PadGeometry(
        id=f"{component}.{pin}",
        component=component,
        pin_number=pin,
        net=net,
        footprint_layer_id=1,
        x=x,
        y=y,
        width=40.0,
        height=40.0,
    )


def _place(designator: str, x: float, y: float) -> ComponentPlacement:
    return ComponentPlacement(
        id=f"c-{designator}", designator=designator, x=x, y=y, layer_id=1
    )


def _rows(pin_name: str, pool: list[tuple[str, float]]) -> list:
    """One IC whose ``RAIL`` pin is named ``pin_name``, and one cap per (value, x)."""
    ic = _comp(
        "U1",
        pins=[("1", pin_name, RAIL), ("2", "OUT", "SIG"), ("3", "GND", "GND")],
    )
    caps = [
        # ``0603`` inside the value: a capacitor whose value is *not* a
        # capacitance must still be identified as a capacitor, so that the
        # ``unknown`` role is what the rule sees (C + chip-size shape,
        # ``core.decap.looks_like_capacitor``).
        _comp(
            f"C{index}",
            value=value,
            footprint="0603",
            pins=[("1", "1", RAIL), ("2", "2", BRIDGE)],
        )
        for index, (value, _x) in enumerate(pool, start=1)
    ]
    model = _model([ic, *caps])
    pads = [
        _pad("U1", "1", x=0.0, y=0.0, net=RAIL),
        _pad("U1", "2", x=0.0, y=20.0, net="SIG"),
        _pad("U1", "3", x=0.0, y=40.0, net="GND"),
    ]
    for index, (_value, x) in enumerate(pool, start=1):
        pads.append(_pad(f"C{index}", "1", x=x, y=0.0, net=RAIL))
        pads.append(_pad(f"C{index}", "2", x=x, y=20.0, net=BRIDGE))
    board = BoardGeometry(
        source="synthetic",
        name="SYNTH",
        components=[_place("U1", 0.0, 0.0)]
        + [_place(f"C{index}", x, 0.0) for index, (_v, x) in enumerate(pool, start=1)],
        pads=pads,
    )
    return DecapDistance().check(
        PcbReviewContext(board=board, board_title="SYNTH", model=model)
    )


# ---------------------------------------------------------------------------
# 1. the role boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "declared, expected_role",
    [
        ("330uF", CAP_ROLE_BULK),
        ("10uF", CAP_ROLE_BULK),      # bulk floor, inclusive
        ("9.9uF", CAP_ROLE_MID),      # just under it
        ("4.7uF", CAP_ROLE_MID),      # PCB1's C17
        ("2.2uF", CAP_ROLE_MID),      # PCB1's C28/C29/C38, FOC's input filter
        ("1.1uF", CAP_ROLE_MID),      # just over the HF ceiling
        ("1uF", CAP_ROLE_HF),         # HF ceiling, inclusive
        ("100nF", CAP_ROLE_HF),
        ("", CAP_ROLE_UNKNOWN),       # nobody wrote a value down
        ("C104", CAP_ROLE_UNKNOWN),   # a net name, not a capacitance
    ],
)
def test_the_mid_band_is_a_role_and_unknown_is_only_what_cannot_be_read(
    declared, expected_role
):
    """``> 1 µF && < 10 µF`` is mid; ``unknown`` keeps its two honest cases.

    The boundaries stay **inclusive** exactly as 127b and 191D pinned them
    (``>= BULK_FARADS`` bulk, ``<= HF_FARADS`` hf), so 529 changed no threshold:
    it filled the band between two thresholds that already existed.
    """
    model = _model([_comp("C1", value=declared)])
    candidate = type("Candidate", (), {"designator": "C1"})()
    role = capacitor_role(candidate, model)
    assert role.role == expected_role, role.reason
    if expected_role == CAP_ROLE_MID:
        assert "mid-band decoupling" in role.reason, role.reason
        assert role.farads is not None
    if expected_role == CAP_ROLE_UNKNOWN:
        assert role.farads is None, "an unreadable value stays unreadable"


def test_mid_adds_no_farad_constant_and_no_distance_tier():
    """The four thresholds are 岳's (2026-10-17) and 529 leaves them alone.

    ``mid`` reuses the **rail's** tier; it is a pool membership, not a grade. If
    this ever grows a fifth line, or a ``MID_FARADS`` beside the two existing
    boundaries, the change is a re-tuning of 191D rather than a classifier fix
    and has to go back to 岳.
    """
    assert BULK_FARADS == 10e-6
    assert HF_FARADS == 1e-6
    assert DECAP_TIER_MIL == {
        DECAP_TIER_CONSUMER: 200.0,
        DECAP_TIER_REGULATOR_IN: 300.0,
        DECAP_TIER_REGULATOR_OUT: 800.0,
        DECAP_TIER_UNDECLARED: 200.0,
    }
    assert DECAP_TIER_ORDER == (
        DECAP_TIER_CONSUMER,
        DECAP_TIER_REGULATOR_IN,
        DECAP_TIER_REGULATOR_OUT,
    )
    assert CAP_ROLE_MID not in DECAP_TIER_PINS.values(), (
        "a role is not a tier: the pin-name table grades rails, not capacitors"
    )
    from boardwise.rules.pcb import distance as _distance

    assert not hasattr(_distance, "MID_FARADS"), (
        "mid is the open band between two boundaries, not a third number"
    )


# ---------------------------------------------------------------------------
# 2. mid is graded by every existing rail tier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pin_name", "tier", "limit"),
    [
        ("VCC", DECAP_TIER_CONSUMER, 200.0),
        ("VIN", DECAP_TIER_REGULATOR_IN, 300.0),
        ("VOUT", DECAP_TIER_REGULATOR_OUT, 800.0),
        ("1", DECAP_TIER_UNDECLARED, 200.0),
    ],
)
def test_a_mid_candidate_is_graded_by_the_rail_tier_like_any_decoupling_part(
    pin_name, tier, limit
):
    """At the line → silence; one printable step past it → WARN naming the tier."""
    assert DECAP_TIER_MIL[tier] == limit

    assert _rows(pin_name, [("2.2uF", limit + 40.0)]) == [], (
        f"a 2.2 µF part exactly at the {tier} line is inside it"
    )

    (row,) = _rows(pin_name, [("2.2uF", limit + 40.1)])
    assert row.severity == "WARN"
    assert row.target.measurement["value"] == round(limit + 0.1, 1)
    assert f"{tier} {limit:.0f} mil，实测 {limit + 0.1:.1f} mil" in row.message, row.message
    assert "candidate C1 mid:" in " | ".join(row.evidence), (
        "the evidence says which role put the part in the pool"
    )


def test_a_mid_part_inside_its_tier_is_silence_and_a_far_one_is_a_warn():
    """The two 毕设FOC shapes in one test: 31.7 mil silent, 460 mil a WARN.

    ``C28`` (``2.2uF``) sits 31.7 mil from ``U11``'s ``VIN`` pad on this board and
    ``C38`` 47.0 mil from ``U13``'s — both inside the 300 mil 输入档, which is why
    those rails went quiet in 529. A mid part at 460 mil is over the same line.
    """
    assert _rows("VIN", [("2.2uF", 71.7)]) == []  # 71.7 - 40 = 31.7 mil
    (row,) = _rows("VIN", [("2.2uF", 500.0)])     # 500 - 40 = 460.0 mil
    assert row.severity == "WARN"
    assert row.target.measurement["value"] == 460.0
    assert row.target.counterpart_ref == "C1"


def test_the_dcdc_shape_now_speaks_522_6_mil_and_that_is_intended():
    """DCDC ``U9@+12V``: a 4.7 µF is the **only** decoupling, 522.6 mil out.

    Before 529 the pool was empty of readable parts, so the input tier's WARN was
    muted by 191D's 「a candidate exists」 guard — the candidate being a 4.7 µF the
    classifier could not name. With mid it is measured, and the reading is over
    the 300 mil input line. This row is 529 **恢复检测能力后的有意发现**
    (task book §3) and is pinned here so nobody can quiet it by re-widening the
    pool or re-narrowing the guard.
    """
    (row,) = _rows("VIN", [("4.7uF", 562.6)])  # 562.6 - 40 = 522.6 mil
    assert row.severity == "WARN"
    assert row.target.measurement["value"] == 522.6
    assert f"{DECAP_TIER_REGULATOR_IN} 300 mil，实测 522.6 mil" in row.message


# ---------------------------------------------------------------------------
# 3. the negative anchors 529 must not soften
# ---------------------------------------------------------------------------


def test_a_rail_with_no_capacitor_at_all_still_warns_on_the_input_tier():
    """The真实无电容 case 191D's 岳 2026-10-19 ruling raised. Kept."""
    (row,) = _rows("VIN", [])
    assert row.severity == "WARN"
    assert "regulator input" in row.message
    assert row.target.measurement is None
    assert "no high-frequency or mid-band capacitor" in " | ".join(row.evidence)


def test_a_bulk_only_input_pool_stays_info_but_keeps_the_bulk_message():
    """127b's 岳裁定 5b 特例, on the input tier: 「只有 bulk」 is still an INFO.

    Bulk is a capacitor; 「the pool is all bulk」 is a statement about its size,
    not about the rail having no filtering, and 529 does not move this row — the
    withdrawal of 191D's narrowing applies to the *general* 「no HF/mid」 pool
    (bulk + unreadable, unreadable-only, nothing at all), not to a pool that has
    a capacitor able to be reported as bulk.
    """
    (row,) = _rows("VIN", [("22uF", 500.0)])
    assert row.severity == "INFO", row.message
    assert "bulk (C1)" in row.message
    assert "regulator input" not in row.message
    assert row.target.measurement is None
    assert "no high-frequency or mid-band candidate" in " | ".join(row.evidence)


def test_an_unreadable_only_input_pool_warns_since_the_narrowing_is_gone():
    """191D's ``not candidates`` guard is withdrawn: unknown is not decoupling.

    A capacitor whose value nobody wrote down is in neither pool, so it cannot
    stand in for the input filter — that is the difference between 「no HF/mid
    decoupling」 and 「no capacitor at all」 that the task book names.
    """
    (row,) = _rows("VIN", [("C104", 500.0), ("C103", 600.0)])
    assert row.severity == "WARN", row.message
    assert row.target.measurement is None
    joined = " | ".join(row.evidence)
    assert "candidate C1 unknown:" in joined and "candidate C2 unknown:" in joined


def test_a_bulk_plus_unreadable_input_pool_warns_too():
    """智能药箱's ``U11@+5V``: bulk + no value used to be muted by 「has candidates」."""
    (row,) = _rows("VIN", [("22uF", 500.0), ("C104", 600.0)])
    assert row.severity == "WARN", row.message
    joined = " | ".join(row.evidence)
    assert "candidate C1 bulk:" in joined and "candidate C2 unknown:" in joined


def test_the_bulk_only_message_stays_info_on_a_consumer_rail():
    """127b's 岳裁定 5b row is unchanged where it was: a rail the part *eats*."""
    (row,) = _rows("VCC", [("330uF", 500.0)])
    assert row.severity == "INFO", row.message
    assert "no high-frequency or mid-band decoupling candidate" in row.message


def test_an_hf_candidate_is_measured_exactly_as_before():
    """The rule keeps its teeth: 100 nF at 310 mil is a WARN, at 60 mil is silent."""
    assert _rows("VCC", [("100nF", 100.0)]) == []  # 100 - 40 = 60.0 mil, inside 200
    (row,) = _rows("VCC", [("100nF", 350.0)])      # 350 - 40 = 310.0 mil, over it
    assert row.severity == "WARN"
    assert row.target.measurement["value"] == 310.0
    assert "candidate C1 hf:" in " | ".join(row.evidence)


# ---------------------------------------------------------------------------
# 4. the neighbours keep their own numbers
# ---------------------------------------------------------------------------


def test_the_neighbouring_rules_keep_their_own_farad_pools():
    """``HF_FARADS`` is shared, so its consumer rules must not move with 529.

    ``mcusupply`` pins its ceiling to :data:`HF_FARADS`; ``regulator`` keeps its
    own ``HF_POOL_FARADS``; ``foc`` keeps a 100 µF storage pool and the TI
    proximity figure. 529 added a decap role and touched none of them — this
    assertion is the tripwire if a later change "simplifies" the three into one.
    """
    from boardwise.rules.pcb import foc, mcusupply, regulator

    assert mcusupply.HF_CEILING_FARADS == HF_FARADS == 1e-6
    assert regulator.HF_POOL_FARADS == 1e-6
    assert foc.BULK_FARADS == 100e-6
    assert foc.TI_DECAP_REFERENCE_MIL == DECAP_TIER_MIL[DECAP_TIER_CONSUMER]
