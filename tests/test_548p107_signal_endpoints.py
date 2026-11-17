"""548P107: placement measures a declared signal side from the core pin."""

from __future__ import annotations

from boardwise.engines import placement
from boardwise.engines.grammar.base import LEFT_OF, RIGHT_OF, RelativeConstraint


ORIGINS = {"U1": (0.0, 0.0), "C4": (-30.0, 10.0)}
PART_NETS = {"U1": {"1": "LCD_BLK"}}


def _relation_points(relation, *, pin1_x=-20.0):
    pin_points = {"U1": {"1": (pin1_x, 0.0)}}
    return placement.relation_points_between(
        relation,
        nets_of=lambda part_id: PART_NETS.get(part_id, {}),
        origin_of=lambda part_id: ORIGINS.get(part_id),
        pin_of=lambda part_id, token: pin_points.get(part_id, {}).get(token),
        class_of=lambda net_id: "signal",
    )


def _miss(relation, points):
    return placement.relation_miss(
        relation.kind,
        points,
        grid=10.0,
        near_limit=100.0,
        lateral=(0.0, 1.0),
        progress=(1.0, 0.0),
    )


def test_signal_net_left_of_core_uses_the_core_pin_and_preserves_endpoint_order():
    relation = RelativeConstraint(
        kind=LEFT_OF,
        subject="LCD_BLK",
        object="U1",
        reason="the output port reads on the left",
    )

    points = _relation_points(relation)

    assert points == ((-20.0, 0.0), (0.0, 0.0))
    assert _miss(relation, points) == 0.0
    opposite_side_points = _relation_points(relation, pin1_x=20.0)
    assert _miss(relation, opposite_side_points) > 0.0


def test_core_right_of_signal_net_keeps_the_reversed_endpoint_order():
    relation = RelativeConstraint(
        kind=RIGHT_OF,
        subject="U1",
        object="LCD_BLK",
        reason="the core reads to the right of its output port",
    )

    points = _relation_points(relation)

    assert points == ((0.0, 0.0), (-20.0, 0.0))
    assert _miss(relation, points) == 0.0
    opposite_side_points = _relation_points(relation, pin1_x=20.0)
    assert _miss(relation, opposite_side_points) > 0.0


def test_component_order_relations_keep_using_origins():
    relation = RelativeConstraint(
        kind=LEFT_OF,
        subject="C4",
        object="U1",
        reason="the decoupler sits left of the core",
    )

    assert _relation_points(relation) == ((-30.0, 10.0), (0.0, 0.0))


def test_unmatched_net_endpoint_remains_unmeasurable():
    relation = RelativeConstraint(
        kind=LEFT_OF,
        subject="VCC",
        object="U1",
        reason="VCC is not a member of the core",
    )

    assert _relation_points(relation) is None
