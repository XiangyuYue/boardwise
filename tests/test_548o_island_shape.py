"""548O 的真实缺口：RST 多余绕行与三组整页编译失败。

岳 2026-11-14 明确授权以 P44 样例修正机械指标。P44 原点纵向跨度仅 25，
因此旧的 y-span >= 2 * pinGap 不是可读性的合法判据；这里不再用跨度代替检查导线。
548M 的无 serviceGroups 规格虽可编译，RST 两脚导线却长 420、直达距离仅 240。
该同侧短直连的目标来自 P44；它不是所有带障碍导线的全局最短路规则。

三组 serviceGroups（R4/R5 右、R6 左、C8/C9 去耦）仍须整页可编译。
两条 strict xfail 都是尚未关闭的目标，XPASS 后才可改成正式通过断言。
真实校准件只在本地 evidence/；缺件明确 skip，skip 不算通过。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawcompiler as dc
from boardwise.engines.drawapply import load_library

ROOT = Path(__file__).resolve().parents[1]
WIFI = ROOT / "evidence/548J/wifi-canvas"
CIRCUIT = WIFI / "calibrated-wifi-island.circuit.json"
LIBRARY = WIFI / "calibrated.library.json"
TWO_GROUPS = ROOT / "evidence/548M/presentation.rail.json"
THREE_GROUPS = ROOT / "evidence/548O/spec-3groups.json"
PAGE = (0.0, 0.0, 1170.0, 825.0)

RST_DETOUR = "548M ESP_RST still takes an unnecessary 420-unit route for a 240-unit connection"
THREE_GROUP_FAILURE = "548P: the calibrated three-group page still fails the production gate"


def _require(*paths: Path) -> None:
    missing = [str(path.relative_to(ROOT)) for path in paths if not path.exists()]
    if missing:
        pytest.skip(
            "the calibrated WiFi page lives under evidence/ (local-only, "
            f"gitignored); missing: {missing}")


def _compile(spec_path: Path):
    _require(CIRCUIT, LIBRARY, spec_path)
    circuit = CircuitSpec.load(CIRCUIT)
    book = load_library(LIBRARY)
    spec = PresentationSpec.load(spec_path)
    return spec, dc.compile(circuit, spec, book, dc.CompileBudget(page_box=PAGE))


def _tip(plan, book, member: str) -> tuple[float, float]:
    part_id, _, token = member.partition(".")
    part = plan.part(part_id)
    assert part is not None, member
    pin = next(pin for pin in book[part.symbol_ref].pins
               if pin.number == token or pin.name == token)
    return transform_point(
        *pin.tip, rotation=part.rotation, mirror=part.mirror,
        ox=part.x, oy=part.y,
    )


def _manhattan(a, b) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@pytest.mark.xfail(strict=True, reason=RST_DETOUR)
def test_the_calibrated_rst_branch_has_no_gratuitous_detour():
    """P3: 检查最终两脚 RST 导线，不能用扩展纵向跨度来假装解决绕线。

    此规格没有 serviceGroups。P44 的同侧 RST 支路是短直连；该窄目标要求解释器
    为它提供不绕回的可读座位，不推广为任意障碍环境的最短路径断言。
    两脚网的全部导线总长还会计入悬空多余枝节，不能靠增加旁路掩盖旧绕线。
    """
    _spec, result = _compile(TWO_GROUPS)
    assert result.ok, [item.detail for item in result.failures]
    plan = result.best()
    assert plan is not None
    book = load_library(LIBRARY)
    runs = [segment for segment in plan.segments if segment.net == "ESP_RST"]
    assert runs, "the two-pin RST connection must have visible wire geometry"
    drawn = sum(_manhattan(a, b)
                for segment in runs
                for a, b in zip(segment.points, segment.points[1:]))
    direct = _manhattan(_tip(plan, book, "J2.RST"), _tip(plan, book, "R5.2"))
    assert drawn == pytest.approx(direct), (
        f"ESP_RST drawn wire {drawn:g}, direct Manhattan {direct:g}, "
        f"excess {drawn - direct:g}; inspect the actual path, not origin span")


@pytest.mark.xfail(strict=True, reason=THREE_GROUP_FAILURE)
def test_the_calibrated_three_group_page_compiles():
    """岳裁 (b) 的三组声明必须整页可编译。

    548O 之前拒因是 `J2.GND has no clear upright hang`；548O 之后同一句消失、换成
    `ESP_RXD` 穿 `J2` 本体。该历史现象不证明原点跨度是根因。整页 `ok=True`
    是 548P 的完成条件之一，不是本文件已经达到的状态。
    """
    _spec, result = _compile(THREE_GROUPS)
    assert result.ok, [
        f"[{item.category}] {item.subject}: {item.detail}"
        for item in result.failures]
    assert len(result.candidates) >= 1, "a legal page must produce a candidate"
