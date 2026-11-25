"""571-C-1: 退火选解必须是**字典序**——硬违规不得被软成本买断。

============================ 这批要治的病 ============================

`engines/placement._energy` 把硬项按 `W_HARD=200` 折进同一个标量，而
`_best_of` / `_anneal_with_seed` 的 best 跟踪只比这个标量。于是「软成本低一点、
带硬违规」的图可以赢过「软成本高一点、完全干净」的图：挖洞批 571 的
`outputs/hole571/c/probes/probe_energy.py` 实测四组 clean/dirty
（500/400、200/100、10/9.2、2780/2595）dirty **全胜**。

本文件钉的是**选择路径**本身，不是新 helper 自己的算术：

1. `_best_of` 在两个 restart 之间必须选干净的那个，哪怕它的标量更贵；
2. `_anneal_with_seed` 的 best 跟踪不得因为候选标量更低就把硬违规状态收成 best；
3. 负控：两个都干净时仍按标量选小的（不许退化成「随便选」或恒选第一个）；
4. 两个都带硬违规时，先比硬项总量，再比标量。

三个用例里的代价表都按生产形状写：`evaluate` 无论干净与否都会追加
`page`/`keepout`/`overlap` 三条 `hard=True` 的项（`placement.py` :2417-2420），
干净图里它们值 0，所以「有没有硬项」只有按**值**读才有意义。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
for _extra in (ROOT / "src", ROOT / "tests"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from boardwise.core.symbolprofile import (  # noqa: E402
    SymbolPin,
    SymbolPose,
    SymbolProfile,
)
from boardwise.engines import placement as pl  # noqa: E402


# --------------------------------------------------------------- 合成输入


def _pin(number: str, name: str, tip: tuple[float, float],
         direction: str) -> SymbolPin:
    return SymbolPin(number=number, tip=tip, name=name, direction=direction)


def _resistor(ref: str) -> SymbolProfile:
    """横放两脚电阻：pin1 左、pin2 右，针尖 ±20（与 201B 同形）。"""
    return SymbolProfile(
        symbol_ref=ref, body=(-10.5, -4.5, 10.5, 4.5),
        pins=[_pin("1", "1", (-20.0, 0.0), "left"),
              _pin("2", "2", (20.0, 0.0), "right")],
    )


_POSE = SymbolPose(rotation=0, mirror=False)


def _request(*, restarts: int = 1, iterations: int = 30) -> pl.PlacementInput:
    """两个自由件的最小请求：够搜索提出移动，不需要任何关系。"""
    parts = (
        pl.PlacementPart("R1", _resistor("R1"), (_POSE,)),
        pl.PlacementPart("R2", _resistor("R2"), (_POSE,)),
    )
    return pl.PlacementInput(
        parts=parts, grid=5.0, restarts=restarts, iterations=iterations,
        seed=201,
    )


def _state(origins: dict[str, tuple[float, float]]) -> pl._State:
    return pl._State(dict(origins), {part_id: _POSE for part_id in origins})


#: 干净图的代价表：三条硬项在值上都是 0，软成本由参数给。
def _clean_terms(soft: float) -> list[pl.CostTerm]:
    return [
        pl.CostTerm("out-of-page", 0.0, "nothing leaves the sheet", hard=True),
        pl.CostTerm("keepout", 0.0, "nothing sits on a keep-out", hard=True),
        pl.CostTerm("overlap", 0.0, "no two parts share area", hard=True),
        pl.CostTerm("wire-length", soft, "synthetic soft cost"),
    ]


#: 带硬违规的代价表：一个出页项按值上真的违规，软成本同样由参数给。
def _dirty_terms(soft: float, out_of_page: float = 0.2) -> list[pl.CostTerm]:
    return [
        pl.CostTerm("out-of-page", out_of_page,
                    f"outside the sheet: R2 by {out_of_page:g} units",
                    hard=True),
        pl.CostTerm("keepout", 0.0, "nothing sits on a keep-out", hard=True),
        pl.CostTerm("overlap", 0.0, "no two parts share area", hard=True),
        pl.CostTerm("wire-length", soft, "synthetic soft cost"),
    ]


def _scalar(terms: list[pl.CostTerm]) -> float:
    """生产自己的 `_energy`——期望值不在这里重写第二遍。"""
    return pl._energy(terms)


_CLEAN_ORIGINS = {"R1": (0.0, 0.0), "R2": (60.0, 0.0)}
_DIRTY_ORIGINS = {"R1": (0.0, 0.0), "R2": (60.0, 5.0)}


# ------------------------------------------- §一 `_best_of` 的 restart 选择


def test_best_of_prefers_a_clean_drawing_over_a_cheaper_hard_one(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """两个 restart：干净 500 vs 带硬违规 440 —— 必须选干净的那个。

    440 < 500 是修复前的判据（`_energy` 把 0.2×W_HARD=40 折进标量），所以这条
    用例在旧代码上必须是红的；它走的是 `_best_of` 真实的 restart 循环。
    """
    clean_terms = _clean_terms(500.0)
    dirty_terms = _dirty_terms(400.0)
    # 这条断言把「旧代码为什么会选错」写下来，而不是靠注释。
    assert _scalar(dirty_terms) < _scalar(clean_terms)

    def fake_anneal(request, state, seed, plans=(), panels=(), services=()):
        return (
            _state(_CLEAN_ORIGINS) if seed == request.seed
            else _state(_DIRTY_ORIGINS)
        ), 7, 3

    def fake_evaluate(request, state, plans=(), panels=(), services=()):
        return (
            clean_terms if state.origins == _CLEAN_ORIGINS else dirty_terms
        )

    monkeypatch.setattr(pl, "_anneal_with_seed", fake_anneal)
    monkeypatch.setattr(pl, "evaluate", fake_evaluate)

    request = _request(restarts=2)
    energy, state, _iterations, _accepted, _attempt = pl._best_of(
        request, _state(_CLEAN_ORIGINS))

    assert state.origins == _CLEAN_ORIGINS, (
        "the restart with a hard violation won because its scalar was cheaper: "
        f"{state.origins}"
    )
    assert energy == _scalar(clean_terms)


# --------------------------------- §二 `_anneal_with_seed` 的 best 跟踪


def test_anneal_best_tracking_does_not_hand_the_win_to_a_hard_state(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """先给一个干净的贵解，再给一串便宜的硬违规候选：best 不许被换掉。

    搜到第一个候选时 `delta_energy` 是负的，所以候选**一定被接受**（Metropolis
    不需要掷硬币），这条用例因此真的把搜索带进了带硬违规的状态；随后要钉的是
    best 跟踪没有跟着标量走。
    """
    clean_terms = _clean_terms(500.0)
    dirty_terms = _dirty_terms(400.0)
    assert _scalar(dirty_terms) < _scalar(clean_terms)
    calls: list[dict[str, tuple[float, float]]] = []

    def fake_evaluate(request, state, plans=(), panels=(), services=()):
        calls.append(dict(state.origins))
        return clean_terms if len(calls) == 1 else dirty_terms

    monkeypatch.setattr(pl, "evaluate", fake_evaluate)

    request = _request(iterations=30)
    seed = _state(_CLEAN_ORIGINS)
    best, _iterations, accepted = pl._anneal_with_seed(
        request, seed, request.seed)

    assert len(calls) > 1, "the search never priced a candidate"
    assert accepted >= 1, "the cheaper hard state was never accepted"
    assert best.origins == _CLEAN_ORIGINS, (
        "best tracking followed the cheaper scalar into a hard-violating state: "
        f"{best.origins}"
    )


# --------------------------------------------------- §三 负控：两个都干净


def test_best_of_still_picks_the_cheaper_drawing_when_both_are_clean(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """两个 restart 都干净时，仍然按标量选小的——不许退化成「恒选第一个」。"""
    cheap_terms = _clean_terms(400.0)
    dear_terms = _clean_terms(500.0)
    cheap_origins = {"R1": (0.0, 0.0), "R2": (0.0, 0.0)}
    dear_origins = _CLEAN_ORIGINS

    def fake_anneal(request, state, seed, plans=(), panels=(), services=()):
        return (
            _state(dear_origins) if seed == request.seed
            else _state(cheap_origins)
        ), 5, 2

    def fake_evaluate(request, state, plans=(), panels=(), services=()):
        return cheap_terms if state.origins == cheap_origins else dear_terms

    monkeypatch.setattr(pl, "_anneal_with_seed", fake_anneal)
    monkeypatch.setattr(pl, "evaluate", fake_evaluate)

    request = _request(restarts=2)
    energy, state, _iterations, _accepted, _attempt = pl._best_of(
        request, _state(dear_origins))

    assert state.origins == cheap_origins
    assert energy == _scalar(cheap_terms)


# ------------------------------------- §四 两个都违规时：先比硬项，再比标量


def test_best_of_ranks_two_hard_drawings_by_the_hard_cost_first(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """二十倍小的硬违规 + 更贵的软成本，必须赢过更大的硬违规。

    `_energy` 的标量把「0.2 单位越页」和「0.3 单位越页」压成了 640 与 460，
    于是旧代码选了越页更多的那张图。字典序的第二位（硬项总量）就是这一位。
    """
    small_hard = _dirty_terms(600.0, out_of_page=0.2)   # scalar 640
    big_hard = _dirty_terms(400.0, out_of_page=0.3)     # scalar 460
    assert _scalar(big_hard) < _scalar(small_hard)
    small_origins = _CLEAN_ORIGINS
    big_origins = _DIRTY_ORIGINS

    def fake_anneal(request, state, seed, plans=(), panels=(), services=()):
        return (
            _state(small_origins) if seed == request.seed
            else _state(big_origins)
        ), 6, 2

    def fake_evaluate(request, state, plans=(), panels=(), services=()):
        return small_hard if state.origins == small_origins else big_hard

    monkeypatch.setattr(pl, "_anneal_with_seed", fake_anneal)
    monkeypatch.setattr(pl, "evaluate", fake_evaluate)

    request = _request(restarts=2)
    energy, state, _iterations, _accepted, _attempt = pl._best_of(
        request, _state(big_origins))

    assert state.origins == small_origins, (
        "the drawing with the larger hard violation won on its cheaper scalar: "
        f"{state.origins}"
    )
    assert energy == _scalar(small_hard)
