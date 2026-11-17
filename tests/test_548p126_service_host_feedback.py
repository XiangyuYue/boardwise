"""548P126：真实 MCU 五条服务支路按显式 `branchOrder` 落座，被拒支路的已选宿主脚回馈。

因果对象只有两个，都由生产入口测量：

1. `modules[].branchOrder` 在 `localSeats` 页面决定服务模板的**声明顺序**（C1→C3→BZ1→C2→R1），
   未写 `branchOrder` 的页面仍是设计ator序（BZ1→C1→C2→C3→R1）；
2. 被拒绝的服务计划必须把它**已经选中的宿主脚**交回 `_service_seats_in_flag_room`，
   该脚进入退休集合与 `seen` 键——否则 C1/C2 永远重复 host 13，C2 试不到 3 和 1。

读数不是自造尺：真实 `dc._place` 在首次 `allSeated=True` 时立即停止，避免把独立的
3V3 旗房拒绝误当服务落座失败。宿主脚取 seat 自己的 `host_token`；`C2` 的 13→3→1
推进取同一运行中 binder 每次尝试的已选脚（失败计划用内部只读 `tried_hosts`），并逐个
核对 `plan.seated`，不把“有宿主记录”误当“已经落座”。
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler as dc, pagecompiler as pc, placement

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

#: The MCU module's own statement (the spec input, unchanged by this batch).
STATED_ORDER = ("C1", "C3", "BZ1", "C2", "R1")
#: What the page produced before this batch: designator order, BZ1 first.
DECLARATION_ORDER = ("BZ1", "C1", "C2", "C3", "R1")
#: The measured seat every branch must land on (P125's 5/5 reverse experiment).
HOSTS = {
    "service:C1": "13",
    "service:C3": "7",
    "service:BZ1": "8",
    "service:C2": "1",
    "service:R1": "61",
}


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


def _templates(context: dc._Context):
    templates, failure = dc._service_templates(
        context, (0.0, 0.0), tuple(sorted(context.slots)))
    assert failure is None, failure.detail
    return templates


def _chosen(plan, template):
    """The host foot this plan's own template selected, seated or refused."""
    if plan.cells:
        return plan.cells[0].host_token
    return {part: token for part, token in getattr(plan, "tried_hosts", ())}.get(
        template.cell.part_id)


class _FirstFiveOfFive(Exception):
    """Stop before the independent downstream 3V3 flag-room refusal."""


@pytest.fixture(scope="module")
def placed_answer(ctx):
    """Stop at the first genuinely 5/5-seated answer, recording real attempts."""
    calls: list[dict] = []
    real = placement._bind_service_sequence

    def spy(request, templates, origins, poses, walls, **kwargs):
        plans, moved = real(request, templates, origins, poses, walls, **kwargs)
        row = {
            "offset": kwargs.get("rung_offset"),
            "hosts": {
                template.cell.part_id: _chosen(plan, template)
                for template, plan in zip(templates, plans)
            },
            "seated": {
                template.cell.part_id: plan.seated
                for template, plan in zip(templates, plans)
            },
        }
        row["allSeated"] = len(plans) == 5 and all(plan.seated for plan in plans)
        calls.append(row)
        if row["allSeated"] and row["hosts"].get("C2") == "1":
            raise _FirstFiveOfFive
        return plans, moved

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(placement, "_bind_service_sequence", spy)
    try:
        dc._place(ctx, dc._variants(ctx)[0])
    except _FirstFiveOfFive:
        pass
    finally:
        monkeypatch.undo()
    return calls


# ------------------------------------------------- ① branchOrder 决定声明顺序


def test_the_mcu_branch_order_is_the_service_declaration_order(ctx):
    """写进 MCU 模块的 `branchOrder` 就是服务模板的顺序，不加任何坐标。"""
    assert tuple(template.cell.part_id for template in _templates(ctx)) == STATED_ORDER


def test_base_and_topology_requests_carry_one_stated_order(ctx):
    """两个真实请求构造入口读同一份模板顺序与同一组开关，不是各修一个。"""
    topology = dc._topology_request(ctx)
    poses = {part.part_id: part.poses[0] for part in topology.parts}
    base = dc._series_placement_request(
        ctx, (), poses, service_templates=_templates(ctx))
    for request in (base, topology):
        assert request.service_joint_order is True
        assert request.service_host_choice is True
        assert tuple(
            template.cell.part_id for template in request.service_templates
        ) == STATED_ORDER


# ------------------------------------------------- ② 拒绝计划的宿主脚回馈


def test_c2_walks_13_3_1_and_all_five_service_branches_seat(placed_answer):
    """同一失败输入：C1 保持 13，C2 按 13→3→1 推进，最终 5/5 落座。"""
    calls = placed_answer
    final = calls[-1]
    assert final["allSeated"], calls
    assert {
        f"service:{part}": host for part, host in final["hosts"].items()
    } == HOSTS
    assert final["seated"] == {part: True for part in STATED_ORDER}
    assert final["offset"] == 0
    assert {row["hosts"].get("C1") for row in calls} <= {None, "13"}

    # `tried_hosts` also exists on refused plans, so only `seated` can prove a
    # complete answer. Compress consecutive duplicate host choices, but keep the
    # real order of the attempts; the first complete answer stops the fixture.
    refused: list[str] = []
    for row in calls[:-1]:
        chosen = row["hosts"].get("C2")
        if chosen and (not refused or refused[-1] != chosen):
            refused.append(chosen)
    assert refused == ["13", "3"], refused


# ------------------------------------------------- ③ 兼容与负控


def test_a_page_without_branch_order_keeps_the_declaration_order():
    """没写 `branchOrder` 的页面（只开 localSeats）顺序与旧版逐项相同。"""
    payload = json.loads(SPEC.read_text(encoding="utf-8"))
    module = next(item for item in payload["modules"] if item["id"] == "mcu")
    module.pop("branchOrder")
    local_only = PresentationSpec.from_dict(payload)
    assert tuple(
        template.cell.part_id for template in _templates(_context(local_only))
    ) == DECLARATION_ORDER


def test_a_stated_host_foot_is_never_replaced_by_bans(ctx):
    """文档点名的宿主脚不被 bans 替换：退休只对页面自己选的脚生效。"""
    templates = {template.cell.part_id: template for template in _templates(ctx)}
    stated = templates["C3"]
    stated = dataclasses.replace(stated, cell=dataclasses.replace(
        stated.cell, host_token="7", host_allowed=("7",)))
    request = dataclasses.replace(
        dc._topology_request(ctx), service_templates=(stated,))
    resolved, unanswered = placement._resolve_service_hosts(
        request, request.service_templates, {},
        {"service:C3": frozenset({"7"})})
    assert not unanswered, unanswered
    assert resolved[0].cell.host_token == "7"
    assert resolved[0].cell.host_allowed == ("7",)
