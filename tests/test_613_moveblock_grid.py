"""613 — `moveblock.on_grid` on non-finite input and a non-positive grid.

570-D4 (``outputs/hole570/d/REPRO.md``): `on_grid(nan)` raised
``ValueError``, `on_grid(inf)` raised ``OverflowError`` and `on_grid(10.0, 0.0)``
raised ``ZeroDivisionError``, so `check_grid` could not answer with the module's
own ``MoveRefused``. The predicate now answers ``False`` instead; a non-finite
delta or pose is then refused by the existing branch with its existing wording.
"""

from __future__ import annotations

import math

import pytest

from boardwise.engines import moveblock as mb


NAN = float("nan")
INF = float("inf")


# --------------------------------------------------------------------------
# 1. the predicate: illegal numbers are simply not on the grid
# --------------------------------------------------------------------------


def test_a_non_finite_coordinate_is_not_on_the_grid():
    assert mb.on_grid(NAN) is False
    assert mb.on_grid(INF) is False
    assert mb.on_grid(-INF) is False


def test_a_non_finite_grid_is_not_a_grid():
    assert mb.on_grid(10.0, NAN) is False
    assert mb.on_grid(10.0, INF) is False
    assert mb.on_grid(10.0, -INF) is False


def test_a_zero_or_negative_grid_is_not_a_grid():
    assert mb.on_grid(10.0, 0.0) is False
    assert mb.on_grid(10.0, -5.0) is False
    assert mb.on_grid(0.0, 0.0) is False


def test_a_grid_step_that_still_works():
    assert mb.GRID == 5.0
    assert mb.on_grid(10.0) is True
    assert mb.on_grid(300.0) is True
    assert mb.on_grid(302.0) is False


def test_the_float_tolerance_is_unchanged():
    # 5 * 0.1 is 0.5000000000000001 in binary; the 1e-6 allowance is 037's.
    assert mb.on_grid(1e-7) is True
    assert mb.on_grid(5.0000001) is True
    assert mb.on_grid(5.001) is False


# --------------------------------------------------------------------------
# 2. the refusal: the existing MoveRefused, not a Python math exception
# --------------------------------------------------------------------------


def _group(x: float = 300.0, y: float = 300.0) -> list[mb.Part]:
    return [mb.Part(
        designator="U1", primitive_id="p-U1", x=x, y=y, rotation=0.0, at=(x, y),
    )]


def test_a_non_finite_delta_is_a_move_refused():
    for dx, dy in ((NAN, 0.0), (INF, 0.0), (0.0, NAN), (0.0, -INF)):
        with pytest.raises(mb.MoveRefused) as caught:
            mb.check_grid(_group(), dx, dy)
        assert "delta" in str(caught.value)
        assert "not a multiple of the 5-unit grid" in str(caught.value)


def test_a_non_finite_pose_is_a_move_refused():
    with pytest.raises(mb.MoveRefused) as caught:
        mb.check_grid(_group(x=NAN), 100.0, 0.0)
    assert "U1" in str(caught.value)
    assert "is not on the 5-unit grid" in str(caught.value)
    with pytest.raises(mb.MoveRefused) as caught:
        mb.check_grid(_group(y=INF), 100.0, 0.0)
    assert "U1" in str(caught.value)


def test_no_math_exception_escapes_check_grid():
    # The three exception types 570-D4 read were ValueError, OverflowError and
    # ZeroDivisionError; one message-shaped refusal covers all of them.
    for dx, dy in ((NAN, NAN), (INF, -INF)):
        try:
            mb.check_grid(_group(), dx, dy)
        except mb.MoveRefused:
            pass
        except (ValueError, OverflowError, ZeroDivisionError) as exc:  # pragma: no cover
            pytest.fail(f"{type(exc).__name__} escaped check_grid: {exc}")


# --------------------------------------------------------------------------
# 3. the negative control: legal input and the old refusals are untouched
# --------------------------------------------------------------------------


def test_a_grid_aligned_move_still_passes():
    mb.check_grid(_group(), 100.0, 0.0)
    mb.check_grid(_group(), 0.0, -50.0)


def test_an_off_grid_delta_keeps_its_original_wording():
    with pytest.raises(mb.MoveRefused) as caught:
        mb.check_grid(_group(), 102.0, 0.0)
    assert "not a multiple of the 5-unit grid" in str(caught.value)
    assert "网格歪了线就再也接不上" in str(caught.value)


def test_an_off_grid_pose_keeps_its_original_wording():
    with pytest.raises(mb.MoveRefused) as caught:
        mb.check_grid(_group(x=302.0), 100.0, 0.0)
    assert "U1 is not on the 5-unit grid" in str(caught.value)
    assert "先把器件摆回网格" in str(caught.value)


def test_the_grid_constant_is_still_five():
    assert mb.GRID == 5.0
    assert math.isfinite(mb.GRID)
