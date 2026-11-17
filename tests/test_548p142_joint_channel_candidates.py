"""548P142：service 通道 detour 与 rail 成员路径在同一联合答案里生成。

因果对象只有两个，都由真实生产入口测量：

1. `_build_path_first_variant` 之前，`_seat_first_service_host_detours` 只对**真的撞上**
   固定 terminal lead/glyph 的 service host path 调用既有 `_seat_first_router`，把绕行同时写回
   `cell.host_path` 与 `plan.host_paths`——只改一处会让 `_panel_channels` 画一条没人承诺的线；
2. `_seat_first_plans` 把 `len(points) > 2` 的 detour 作为 `foreign` 注入既有 P138 联合选择，
   让 3V3 chain 在**同一次**候选枚举里避开 BUZZ 的绕行，而不是先定 channel 再让 chain 被动接受。

基线（本批生产改动前）首拒是 C3.2 固定 terminal；只做 detour 时 C1.1/U1.13 在 (-160,85) 与
BUZZ 共点（P139 已测）。修复后的真实读数应到 C1.2 固定 terminal，且不再出现 C3.2/C1.1/U1.13
的 BUZZ 冲突。C1.2 是**下一独立首拒**，本批不宣称整图 ok。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler as dc, pagecompiler as pc

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT = ROOT / "evidence/548P125/circuit.full.g3c.pinmap.json"
SPEC = ROOT / "evidence/548P126/full.presentation.service-feedback.json"
LIBRARY = ROOT / "evidence/548P59/full.library.json"
INPUTS = (CIRCUIT, SPEC, LIBRARY)

_missing = [str(path.relative_to(ROOT)) for path in INPUTS if not path.exists()]
if _missing:
    pytest.skip(
        "requires local 548P126 evidence (gitignored, local-only); "
        f"missing: {_missing}",
        allow_module_level=True,
    )


def _context(spec: PresentationSpec) -> dc._Context:
    """The MCU island alone, through the page compiler's own module view."""
    circuit = CircuitSpec.load(CIRCUIT)
    book = drawapply.load_library(LIBRARY)
    module = next(item for item in spec.modules if item.id == "mcu")
    sub_circuit, sub_spec = pc._module_view(circuit, spec, module)
    binding = dc.bind_grammar(sub_circuit, sub_spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_series_arms(binding, sub_spec)
    binding = dc._with_panel_groups(binding, sub_spec, sub_circuit)
    binding = dc._with_service_groups(binding, sub_spec, sub_circuit, book)
    prepared = dc._prepare(sub_circuit, sub_spec, binding, book, dc.CompileBudget())
    assert prepared.context is not None, [item.detail for item in prepared.failures]
    return prepared.context


@pytest.fixture(scope="module")
def ctx() -> dc._Context:
    return _context(PresentationSpec.load(SPEC))


def _placed(ctx: dc._Context) -> dc._Placement:
    """The real placement, with the independent flag-room refusal switched off.

    The service seats are already 5/5 here (P126); `_service_flag_room_ok` is a
    separate 3V3 flag-room refusal, and this batch measures the build that comes
    after a seated page, so the fixture states the placement is seated rather
    than re-litigating that independent gate.
    """
    original = dc._service_flag_room_ok
    dc._service_flag_room_ok = lambda *_args: True
    try:
        placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    finally:
        dc._service_flag_room_ok = original
    assert placed is not None, failure
    return placed


def _build(
    ctx: dc._Context, placed: dc._Placement,
) -> tuple[dc._Built | None, dc.GrammarFailure | None, list[str]]:
    return dc._build_one_variant(
        ctx, dc._variants(ctx)[0], [], placement_override=placed)


def _buzz_plan(placed: dc._Placement):
    return next(plan for plan in placed.service_plans
                if plan.group_id == "service:BZ1")


# ------------------------------------------------- ① 修复后的联合答案


def test_joint_channel_detours_buzz_and_stops_at_c12(ctx):
    """detour 与 3V3 chain 在同一答案里成立，下一首拒是 C1.2 固定 terminal。"""
    placed = _placed(ctx)
    built, failure, _notes = _build(ctx, placed)
    detail = failure.detail if failure is not None else ""
    assert built is None, "the page must still refuse; C1.2 is the next refusal"
    assert "C3.2" not in detail, detail
    assert "C1.1" not in detail and "U1.13" not in detail, detail
    assert "C1.2" in detail, detail
    assert "fixed terminal is not moved" in detail, detail


def test_buzz_host_path_and_channel_wall_are_the_same_detour(ctx):
    """绕行同时写回 cell.host_path 与 plan.host_paths，通道墙与线一致。"""
    placed = _placed(ctx)
    _built, _failure, _notes = _build(ctx, placed)
    plan = _buzz_plan(placed)
    cell = plan.cells[0]
    path = tuple(cell.host_path)
    host = dc._pin_point(
        ctx, plan.host_part, cell.host_token, placed.poses, placed.origins)
    assert host is not None
    assert path[0] == host, (path[0], host)
    assert path[-1] == cell.from_seat, (path[-1], cell.from_seat)
    # A detour, not the placement's direct two-point span.
    assert len(path) > 2, path
    assert plan.host_paths == (path,), plan.host_paths
    channels, problem = dc._panel_channels(ctx, placed, service_only=True)
    assert problem is None, problem
    buzz = [
        segment for net, segments in channels.items() if net == "BUZZ"
        for segment in segments
    ]
    assert len(buzz) == 1, channels
    assert tuple(buzz[0].points) == path, (buzz[0].points, path)


# ------------------------------------------------- ② 因果负控：没有 detour 就还是 C3.2


def test_without_the_detour_the_c32_fixed_terminal_is_still_covered(
    ctx, monkeypatch,
):
    """关掉 detour 生成，首拒回到 C3.2 的固定 terminal——detour 是因果项。"""
    monkeypatch.setattr(
        dc, "_seat_first_service_host_detours", lambda *_args, **_kwargs: None)
    placed = _placed(ctx)
    _built, failure, _notes = _build(ctx, placed)
    assert failure is not None
    assert "C3.2" in failure.detail, failure.detail
    plan = _buzz_plan(placed)
    assert len(plan.cells[0].host_path) == 2, plan.cells[0].host_path
