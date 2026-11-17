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


# ------------------------------- 闸门边界：net 端点是姿态偏好，不是页面硬闸
#
# 548P143-B 的最终语义（主代理裁定）：net→part 的次序关系量的是
# 「object 自己在该网上的引脚」与「object 的 origin」——同属一个零件，平移同时
# 移动两点，548P141 已拒绝修复它。所以它可以度量（P107 的单成员读法、P143 的
# 多成员不可度量都保留），但**不能**作页面硬闸；零件↔零件的次序关系不在此列。

from boardwise.core.circuitspec import CircuitSpec, SpecNet, SpecPart
from boardwise.engines import drawcompiler as dc
from boardwise.engines.grammar.base import GrammarResult, RelativeConstraint


def _gate_circuit() -> CircuitSpec:
    return CircuitSpec(
        parts=[SpecPart(id="U1", symbol_ref="U"), SpecPart(id="C3", symbol_ref="C")],
        nets=[
            SpecNet(id="DSR", cls="signal", members=["U1.5"]),
            SpecNet(id="V3", cls="power", members=["U1.1", "C3.1"]),
        ],
    )


def _violations(subject: str, object_: str):
    binding = GrammarResult(
        ok=True,
        constraints=(RelativeConstraint(
            kind=pl.LEFT_OF, subject=subject, object=object_,
            reason="the port reads on the left of its core",
        ),),
    )
    return dc._relation_violations(
        _gate_circuit(), binding,
        origin_of=lambda part_id: {"U1": (0.0, 0.0), "C3": (20.0, 0.0)}.get(part_id),
        pin_of=lambda part_id, token: (45.0, 5.0),
        grid=10.0, near_limit=100.0, lateral=(0.0, 1.0), progress=(1.0, 0.0),
        net_members={"DSR": 1, "V3": 2},
    )


def test_the_gate_does_not_refuse_a_single_member_net_endpoint():
    """声明左边、引脚在右边：可度量（P107），但不产 violation。"""
    assert _points(_relation(pl.LEFT_OF, "DSR", "U1"), {"DSR": 1}) == (
        (45.0, 5.0), (0.0, 0.0))
    assert _violations("DSR", "U1") == []


def test_the_gate_does_not_refuse_the_reversed_part_to_net_order():
    """端点序反过来（core 在左、网在右）同样不产 violation。"""
    binding = GrammarResult(
        ok=True,
        constraints=(RelativeConstraint(
            kind=pl.RIGHT_OF, subject="U1", object="DSR",
            reason="the core reads to the right of its output port",
        ),),
    )
    assert dc._relation_violations(
        _gate_circuit(), binding,
        origin_of=lambda part_id: {"U1": (0.0, 0.0)}.get(part_id),
        pin_of=lambda part_id, token: (45.0, 5.0),
        grid=10.0, near_limit=100.0, lateral=(0.0, 1.0), progress=(1.0, 0.0),
        net_members={"DSR": 1},
    ) == []


def test_the_gate_still_refuses_a_part_to_part_order():
    """零件↔零件两个 origin 可以分开摆，因此仍硬判（这条不是偏好）。"""
    found = _violations("C3", "U1")
    assert len(found) == 1, found
    item, points = found[0]
    assert (item.subject, item.object) == ("C3", "U1")
    assert points == ((20.0, 0.0), (0.0, 0.0))
