"""622-A：pin-tip 修复趟必须与 `_best_of` 用同一把尺（`_selection_key`）。

============================ 这批要治的病 ============================

`place` 的修复趟（`placement.py` 里 `healed_energy < energy - 1e-9`）还在按
**标量**判优：`_energy` 把 hard 项乘 200，可是有限罚分总能被软项省下的钱买回，
于是一个带硬违规（出页 / 压 keep-out / 重叠）却更便宜的修复解，会顶掉干净的第一
解。`571-C-1` 已经在 `_best_of` 上修过同一件事（`_selection_key` + `_key_better`
的字典序，`:8753`），`:8615` 是漏掉的第二处。

下面四条：前三条钉纯函数 `_repair_beats` 的判据，第四条钉整链——修复趟真的返回
「带 hard 的更便宜解」时，`place()` 必须保留第一解。

1. healed 带一条 hard 项、总标量更小 → **不许**采纳；
2. healed 全软且更小 → 采纳；
3. 两者都 clean（hard 项在场、值为 0）且 healed 更小 → 采纳；
4. 整链：monkeypatch `_anneal_with_seed`，断言 `place()` 不采纳并保留第一解。
"""

from __future__ import annotations

import dataclasses
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from boardwise.core.symbolprofile import SymbolPin, SymbolPose, SymbolProfile  # noqa: E402
from boardwise.engines import placement as pl  # noqa: E402


# ------------------------------------------------------------------ 合成零件

def _pin(number: str, name: str, tip: tuple[float, float], direction: str) -> SymbolPin:
    return SymbolPin(number=number, tip=tip, name=name, direction=direction)


def _resistor(ref: str = "R") -> SymbolProfile:
    """横放两脚电阻：pin1 左、pin2 右，针尖 ±20（与 201B 同一形状）。"""
    return SymbolProfile(
        symbol_ref=ref, body=(-10.5, -4.5, 10.5, 4.5),
        pins=[_pin("1", "1", (-20.0, 0.0), "left"),
              _pin("2", "2", (20.0, 0.0), "right")],
    )


ALL_POSES = tuple(
    SymbolPose(rotation=rotation, mirror=mirror)
    for rotation in (0, 90, 180, 270)
    for mirror in (False, True)
)


def _term(name: str, value: float, *, hard: bool = False) -> pl.CostTerm:
    return pl.CostTerm(name, value, f"622-A 合成项 {name}", hard=hard)


# ------------------------------------------------------- §一 纯函数：同一把尺


def test_a_cheaper_healed_answer_that_carries_a_hard_term_is_rejected():
    """标量更小但带一条 hard 项 → 修复解**不许**顶掉干净解（本批因果项）。

    healed 的 201 比 current 的 400 便宜，旧标量比较会采纳它；字典序必须先看
    hard 在不在效（`_selection_key[0]`），在效就一律排在干净解之后。
    """
    current = [_term("page", 0.0, hard=True), _term("wire-length", 400.0)]
    healed = [_term("keepout", 1.0, hard=True), _term("wire-length", 1.0)]
    assert pl._energy(healed) < pl._energy(current), "前提：标量上 healed 更便宜"
    assert pl._selection_key(healed)[0] is True
    assert pl._selection_key(current)[0] is False
    assert pl._repair_beats(healed, current) is False


def test_a_cheaper_all_soft_healed_answer_is_accepted():
    """全软且更小 → 采纳：修复趟该干的活不能因为加严而丢掉。"""
    current = [_term("wire-length", 40.0)]
    healed = [_term("wire-length", 10.0)]
    assert pl._energy(healed) < pl._energy(current)
    assert pl._repair_beats(healed, current) is True


def test_a_cheaper_clean_healed_answer_is_accepted():
    """两者都 clean（`evaluate` 总会附上三条 hard 项、值为 0）且更小 → 采纳。

    hard 项「在场」不等于「在效」：presence 判定会把每张干净的图都判脏，
    所以键读的是 `CostTerm.violated`，不是 `hard` 这个旗标。
    """
    zeros = [_term("page", 0.0, hard=True),
             _term("keepout", 0.0, hard=True),
             _term("overlap", 0.0, hard=True)]
    current = zeros + [_term("wire-length", 40.0)]
    healed = zeros + [_term("wire-length", 10.0)]
    assert pl._selection_key(current)[0] is False
    assert pl._energy(healed) < pl._energy(current)
    assert pl._repair_beats(healed, current) is True


# ------------------------------------------------------------- §二 整链：place


def _chain_request() -> pl.PlacementInput:
    """两脚件两颗，`pin_clearance=True`——修复趟唯一会跑的条件。

    keep-out 只让 healed 解压到 1 平方单位（hard 200），这样「更便宜但带 hard」
    才成立；`same-column(R1, R2)` 让第一解贵 37.5（关系项），是它贵的来源。
    """
    return pl.PlacementInput(
        parts=(
            pl.PlacementPart("R1", _resistor("R0603"), ALL_POSES),
            pl.PlacementPart("R2", _resistor("R0603"), ALL_POSES),
        ),
        nets=(
            pl.PlacementNet("A", (("R1", "1"), ("R2", "1"))),
            pl.PlacementNet("B", (("R1", "2"), ("R2", "2"))),
        ),
        relations=(
            pl.PlacementRelation("same-column", "R1", "R2", "622-A 整链场景"),
        ),
        progress=(1.0, 0.0), lateral=(0.0, 1.0),
        iterations=20, restarts=1, seed=3,
        pin_clearance=True,
        keepouts=((195.0, 0.0, 200.0, 0.2),),
    )


def test_place_keeps_the_clean_first_answer_over_a_cheaper_dirty_repair(
    monkeypatch: pytest.MonkeyPatch,
):
    """整链：修复趟返回「带 hard 的更便宜解」，`place()` 必须保留第一解。

    第一解 A：R1 (0,0) / R2 (40,0)，两条异网针尖重合（`pin-clearance` 10），
    干净但贵。修复趟 B：R1 (200,0) / R2 (200,40)，压 keep-out 1 平方单位
    （hard），标量更便宜。旧标量规则采纳 B（图带硬违规），本批之后必须留在 A。
    """
    request = _chain_request()
    state_a = pl._State(
        {"R1": (0.0, 0.0), "R2": (40.0, 0.0)},
        {"R1": SymbolPose(0, False), "R2": SymbolPose(0, False)},
    )
    state_b = pl._State(
        {"R1": (200.0, 0.0), "R2": (200.0, 40.0)},
        {"R1": SymbolPose(0, False), "R2": SymbolPose(0, False)},
    )
    first_terms = pl.evaluate(dataclasses.replace(request, pin_clearance=False),
                              state_a, (), ())
    healed_terms = pl.evaluate(request, state_b, (), ())
    # 前提：旧规则（标量）会采纳 B，而 B 带硬违规、A 干净。
    assert pl._energy(healed_terms) < pl._energy(first_terms), (
        "前提：修复解标量更便宜"
    )
    assert pl._selection_key(healed_terms)[0] is True, "前提：修复解带 hard"
    assert pl._selection_key(first_terms)[0] is False, "前提：第一解干净"

    def _fake_anneal(request, state, attempt, plans=(), panels=(), services=()):
        # 修复趟以 `pin_clearance=True` 的请求进入；第一趟是 `plain`。
        if request.pin_clearance:
            return state_b, 3, 1
        return state_a, 5, 2

    monkeypatch.setattr(pl, "_anneal_with_seed", _fake_anneal)
    result = pl.place(request)

    assert result.origins == state_a.origins, (
        f"place() 采纳了带 hard 的更便宜修复解：{result.origins}"
    )
    assert result.hard == [], [item.render() for item in result.hard]
    assert result.iterations == 5, "修复趟的迭代数不该记进未被采纳的答案"
