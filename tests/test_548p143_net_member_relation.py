"""548P143：多成员网端点不可由单一坐标裁决左右。

网→part 的单成员网继续使用 P107 的“核心引脚 + origin”；多成员网没有唯一
几何端点，返回 None。未传 net_members 的旧调用与零件↔零件关系完全不变。
"""
from __future__ import annotations

from boardwise.core.symbolprofile import SymbolPin, SymbolPose, SymbolProfile
from boardwise.engines import placement as pl


def _relation(kind: str, subject: str, object_: str) -> pl.PlacementRelation:
    return pl.PlacementRelation(kind, subject, object_)


def _points(relation, members):
    return pl.relation_points_between(
        relation,
        nets_of=lambda part_id: {"U1": {"5": "DSR"}}.get(part_id, {}),
        origin_of=lambda part_id: {"U1": (0.0, 0.0), "C3": (20.0, 0.0)}.get(part_id),
        pin_of=lambda part_id, token: (45.0, 5.0),
        net_members=members,
    )


def test_multi_member_net_has_no_unique_left_of_endpoint():
    assert _points(_relation(pl.LEFT_OF, "DSR", "U1"), {"DSR": 2}) is None


def test_multi_member_net_has_no_unique_right_of_endpoint():
    assert _points(_relation(pl.RIGHT_OF, "U1", "DSR"), {"DSR": 2}) is None


def test_single_member_net_keeps_the_core_pin_and_origin():
    assert _points(_relation(pl.LEFT_OF, "DSR", "U1"), {"DSR": 1}) == (
        (45.0, 5.0), (0.0, 0.0))
    assert _points(_relation(pl.RIGHT_OF, "U1", "DSR"), {"DSR": 1}) == (
        (0.0, 0.0), (45.0, 5.0))


def test_omitting_net_members_keeps_the_old_single_pin_reading():
    assert _points(_relation(pl.LEFT_OF, "DSR", "U1"), None) == (
        (45.0, 5.0), (0.0, 0.0))


def test_part_to_part_relation_is_unchanged_by_net_membership():
    assert _points(_relation(pl.LEFT_OF, "C3", "U1"), {"DSR": 2}) == (
        (20.0, 0.0), (0.0, 0.0))


def _request(multi: bool) -> pl.PlacementInput:
    profile = SymbolProfile(
        symbol_ref="U",
        body=(-10.0, -10.0, 10.0, 10.0),
        pins=[SymbolPin(number="5", name="5", tip=(45.0, 5.0), direction="right")],
    )
    parts = [pl.PlacementPart("U1", profile, (SymbolPose(),))]
    members = [("U1", "5")]
    if multi:
        parts.append(pl.PlacementPart("C3", profile, (SymbolPose(),)))
        members.append(("C3", "5"))
    return pl.PlacementInput(
        parts=tuple(parts),
        nets=(pl.PlacementNet("DSR", tuple(members)),),
        relations=(pl.PlacementRelation(pl.LEFT_OF, "DSR", "U1"),),
        iterations=1,
        restarts=1,
    )


def test_relation_points_uses_only_the_request_net_slice():
    relation = pl.PlacementRelation(pl.LEFT_OF, "DSR", "U1")
    pins = {"U1": {"5": (45.0, 5.0)}}
    origins = {"U1": (0.0, 0.0), "C3": (20.0, 0.0)}
    assert pl.relation_points(_request(False), relation, pins, origins) == (
        (45.0, 5.0), (0.0, 0.0))
    assert pl.relation_points(_request(True), relation, pins, origins) is None
