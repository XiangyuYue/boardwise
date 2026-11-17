"""548P141：关系修复不得把网名端点当可平移零件。

DSR→U1 是合法的“网→核”关系：网端点用 U1 在该网上的引脚，另一端用 U1
origin。两点随 U1 一起平移，因此这种关系不能靠平移修复。旧代码却先算出
delta，再在 `_anneal_with_seed` 中索引 `origins['DSR']` 并抛 KeyError。
"""
from __future__ import annotations

from boardwise.core.symbolprofile import SymbolPin, SymbolPose, SymbolProfile
from boardwise.engines import placement as pl


def _profile(ref: str, token: str) -> SymbolProfile:
    return SymbolProfile(
        symbol_ref=ref,
        body=(-10.0, -10.0, 10.0, 10.0),
        pins=[SymbolPin(number=token, name=token, tip=(45.0, 5.0), direction="right")],
    )


def _request(*, with_part_relation: bool = False) -> pl.PlacementInput:
    relations = [pl.PlacementRelation(pl.LEFT_OF, "DSR", "U1")]
    parts = [pl.PlacementPart("U1", _profile("U", "5"), (SymbolPose(),))]
    if with_part_relation:
        relations.append(pl.PlacementRelation(pl.LEFT_OF, "C3", "U1"))
        parts.append(pl.PlacementPart("C3", _profile("C", "1"), (SymbolPose(),)))
    return pl.PlacementInput(
        parts=tuple(parts),
        nets=(pl.PlacementNet("DSR", (("U1", "5"),)),),
        relations=tuple(relations),
        iterations=12,
        restarts=1,
    )


def test_net_endpoint_is_not_a_translatable_part_in_either_direction():
    request = _request()
    relation = request.relations[0]
    origins = {"U1": (0.0, 0.0)}
    pins = {"U1": {"5": (45.0, 5.0)}}
    assert pl._repair_delta(request, relation, pins, origins, 0) is None
    assert pl._repair_delta(request, relation, pins, origins, 1) is None


def test_part_to_part_repair_keeps_the_original_delta():
    request = _request(with_part_relation=True)
    relation = request.relations[1]
    origins = {"U1": (0.0, 0.0), "C3": (20.0, 0.0)}
    pins = {"U1": {"5": (45.0, 5.0)}, "C3": {}}
    assert pl._repair_delta(request, relation, pins, origins, 0) == (-20.0, 0.0)
    assert pl._repair_delta(request, relation, pins, origins, 1) == (20.0, 0.0)


def test_anneal_does_not_index_a_net_name_as_a_part_origin():
    request = _request()
    state = pl._State(
        origins={"U1": (0.0, 0.0)}, poses={"U1": SymbolPose()},
    )
    # The unfixed code reaches origins['DSR'] on this short deterministic run.
    after, _iterations, _evaluations = pl._anneal_with_seed(request, state, 201)
    assert after.origins == state.origins
    assert after.poses == state.poses
