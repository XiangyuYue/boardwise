"""053f：三条改变默认行为的规则，改成**规格声明**——不写就回到旧行为。

上一批（534/535/536）把三个判断写进了编译器：地网默认按 100 就近分簇、名字桩
默认最短 40、名字行默认以锚点居中。它们对**我们的**图纸是对的，但对别人的图纸是
静默的行为变更——全量 44 个失败就是这么来的。这一批把三者变成文档的语句：

| 开关 | 写法 | 不写时 |
| --- | --- | --- |
| 地网分簇 | `gndClustering: {"radius": 100}` | `CompileBudget.gnd_cluster_radius = 0`，`_gnd_clusters` **一次都不调用** |
| 桩最小长 | `labelPolicy.stubMin: 40` | `LayoutLabel.stub_min = 0`，阶梯首档回到旧式子（短盒 = 10） |
| 行模型 | `labelPolicy.rowModel: "centered"` | `LayoutLabel.row_model = "anchored"`，行是 `wire_name_box` 的原样 |

所以这个文件钉两件事：**声明了就按声明来**，以及**不声明时逐字节是旧的**。后者
不能用「改前跑一次、改后跑一次」证明（这一批不许碰 git），所以它被拆成单元级的
断言：旧档位的数值、旧盒子的数值、「分簇函数没被调用」。三个数字都是旧代码自己的
输出，不是这一批重新定义的。
"""

from __future__ import annotations

import json
import math
import types

import pytest

import test_053b_drawcompiler as b053

from boardwise.core import textmetrics
from boardwise.core import layoutplan
from boardwise.core.layoutplan import LayoutLabel, LayoutPlan
from boardwise.core.presentationspec import (
    LABEL_ROW_MODEL_ANCHORED,
    LABEL_ROW_MODEL_CENTERED,
    PresentationSpec,
    PresentationSpecError,
)
from boardwise.engines import drawapply
from boardwise.engines import drawcompiler as dc
from boardwise.engines.drawapply import SOFT_FLOOR_TEXT_GAP
from boardwise.engines.drawapply import LABEL_ROW_FLOOR


def base() -> dict:
    """The smallest spec this build writes, as a dict to hang keys on."""
    return PresentationSpec().to_jsonable()


def gnd_symbols(plan):
    return [symbol for symbol in plan.power_symbols if symbol.net == "GND"]


# ------------------------------------------------------------- schema 往返


def test_none_of_the_three_keys_is_written_when_the_document_says_nothing():
    """默认不写出：三个键一个都不出现，所以旧文档序列化后逐字节不变。"""
    payload = base()
    assert "gndClustering" not in payload
    assert "stubMin" not in payload["labelPolicy"]
    assert "rowModel" not in payload["labelPolicy"]
    # 也不能是「写了默认值」：键本身不在。
    assert set(payload["labelPolicy"]) == {"local", "crossModule", "highFanout"}


def test_declared_values_survive_a_round_trip():
    payload = base()
    payload["gndClustering"] = {"radius": 100}
    payload["labelPolicy"] = dict(payload["labelPolicy"], stubMin=40, rowModel="centered")
    spec = PresentationSpec.from_dict(payload)
    assert spec.gnd_cluster_radius == 100.0
    assert spec.label_policy.stub_min == 40.0
    assert spec.label_policy.row_model == LABEL_ROW_MODEL_CENTERED
    # 写回去还在，并且再读一次还是同一个对象（规范形的定义）。
    again = spec.to_jsonable()
    assert again["gndClustering"] == {"radius": 100}
    assert again["labelPolicy"]["stubMin"] == 40.0
    assert again["labelPolicy"]["rowModel"] == "centered"
    assert PresentationSpec.from_dict(again).to_jsonable() == again
    assert PresentationSpec.from_dict(again).sha256() == spec.sha256()


def test_a_declared_spec_writes_the_keys_only_where_it_declared_them():
    """只声明圆心半径：另两个键仍然不写（三个开关互相独立）。"""
    payload = base()
    payload["gndClustering"] = {"radius": 100}
    spec = PresentationSpec.from_dict(payload)
    assert "gndClustering" in spec.to_jsonable()
    assert "stubMin" not in spec.to_jsonable()["labelPolicy"]
    assert spec.label_policy.stub_min == 0.0
    assert spec.label_policy.row_model == LABEL_ROW_MODEL_ANCHORED


@pytest.mark.parametrize("radius", [0, -1, -0.5, float("nan"), float("inf"), "100", True])
def test_radius_must_be_a_positive_finite_number_and_the_refusal_names_it(radius):
    payload = base()
    payload["gndClustering"] = {"radius": radius}
    with pytest.raises(PresentationSpecError) as caught:
        PresentationSpec.from_dict(payload)
    assert "$.gndClustering.radius" in str(caught.value)


def test_gnd_clustering_is_a_closed_object():
    payload = base()
    payload["gndClustering"] = {"radius": 100, "mode": "clubs"}
    with pytest.raises(PresentationSpecError) as caught:
        PresentationSpec.from_dict(payload)
    assert "mode" in str(caught.value)


@pytest.mark.parametrize("stub_min", [0, -5, float("nan"), float("inf"), "40", True])
def test_stub_min_must_be_a_positive_finite_number(stub_min):
    payload = base()
    payload["labelPolicy"] = dict(payload["labelPolicy"], stubMin=stub_min)
    with pytest.raises(PresentationSpecError) as caught:
        PresentationSpec.from_dict(payload)
    assert "labelPolicy.stubMin" in str(caught.value)


def test_row_model_is_a_closed_vocabulary():
    payload = base()
    payload["labelPolicy"] = dict(payload["labelPolicy"], rowModel="middle")
    with pytest.raises(PresentationSpecError) as caught:
        PresentationSpec.from_dict(payload)
    message = str(caught.value)
    assert "labelPolicy.rowModel" in message
    assert "anchored" in message and "centered" in message


def test_the_document_on_disk_is_the_same_document(tmp_path):
    payload = base()
    payload["gndClustering"] = {"radius": 100}
    payload["labelPolicy"] = dict(payload["labelPolicy"], stubMin=40, rowModel="centered")
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    spec = PresentationSpec.load(path)
    assert spec.gnd_cluster_radius == 100.0
    assert spec.label_policy.stub_min == 40.0
    assert spec.label_policy.row_model == "centered"


# ------------------------------------------------ 桩最小长：不写 = 旧档位


def _short_label(**kwargs) -> LayoutLabel:
    """A label whose text box reaches 30 units right — the pre-536 head was 10."""
    return LayoutLabel(net="TXD", text="TXD", x=0.0, y=0.0, bbox=(20.0, -5.0, 30.0, 5.0), **kwargs)


def test_stub_min_off_restores_the_old_first_rung():
    """不写 stubMin：首档 = 旧值 10，与没有这个字段的 label 逐项相同。

    `stub_min == 0` 走的是改前的式子
    ``max(DRAW_GRID, (min(LABEL_STUB_LENGTH, max(DRAW_GRID, reach)) // DRAW_GRID) * DRAW_GRID)``，
    reach 30 → min(10, 30) = 10 → 首档 10。这是 057 的档，也是 534 之前每一张图
    的第一档。
    """
    rungs = drawapply._label_stub_candidates(_short_label())
    assert rungs[0].points[-1] == (10.0, 0.0), rungs[0].shape
    assert rungs[0].shape == "right 10"
    # 一个**根本没有** stub_min 属性的对象（旧 plan、测试里的 SimpleNamespace）
    # 读出完全相同的候选序列——`.getattr(..., 0.0)` 就是这条兼容性。
    legacy = types.SimpleNamespace(
        net="TXD", text="TXD", x=0.0, y=0.0, bbox=(20.0, -5.0, 30.0, 5.0),
    )
    assert [run.points for run in drawapply._label_stub_candidates(legacy)] == [
        run.points for run in rungs
    ]


def test_stub_min_on_raises_the_head_but_keeps_the_ladder():
    """写了 stubMin=40：首档 40（536 的形状），后面的短档仍然留着兜底。"""
    stated = drawapply._label_stub_candidates(_short_label(stub_min=40.0))
    old = drawapply._label_stub_candidates(_short_label())
    assert stated[0].points[-1] == (40.0, 0.0), stated[0].shape
    assert stated[0].shape == "right 40"
    # 40 不是终点：短档还在阶梯里（拥挤的列要靠它画得出来，536 fix r1）。
    lengths = [run.points[-1][0] for run in stated if len(run.points) == 2]
    assert 10.0 in lengths and 5.0 in lengths
    # 旧序列的首档不是新序列的首档：这正是「默认变了」的那一维。
    assert old[0].points[-1] != stated[0].points[-1]


# ------------------------------------------------- 行模型：不写 = 旧盒子


RUN = drawapply._StubRun(points=((0.0, 0.0), (10.0, 0.0)), side=(1.0, 0.0), shape="", family="")


def test_row_model_off_is_the_measured_box():
    """不写 rowModel：行就是 `textmetrics.wire_name_box` 的原样（锚点**上方**）。"""
    anchored = drawapply._stub_name_row(RUN, "AB")
    measured = textmetrics.wire_name_box([(0.0, 0.0), (10.0, 0.0)], "AB")
    assert measured is not None
    assert tuple(anchored) == tuple(measured)


def test_row_model_on_centres_the_row_on_the_anchor():
    """写了 rowModel=centered：横向行 `y ± WIRE_NAME_ROW/2`（534 r25）。"""
    measured = textmetrics.wire_name_box([(0.0, 0.0), (10.0, 0.0)], "AB")
    centred = drawapply._stub_name_row(RUN, "AB", "centered")
    half = textmetrics.WIRE_NAME_ROW / 2.0
    assert tuple(centred) == (
        measured[0], measured[1] - half, measured[2], measured[1] + half,
    )


def test_label_row_floor_is_centered_only():
    """`LABEL_ROW_FLOOR = 1` 只在 centered 下对「标签对标签」生效。"""
    label_row = "the layout label box of net GND"
    assert drawapply._row_floor(label_row, "centered") == LABEL_ROW_FLOOR
    assert drawapply._row_floor(label_row, "anchored") == SOFT_FLOOR_TEXT_GAP
    assert drawapply._row_floor(label_row) == SOFT_FLOOR_TEXT_GAP
    # 非标签的行，两种模型都按 S-21 的 2。
    assert drawapply._row_floor("wire of net GND", "centered") == SOFT_FLOOR_TEXT_GAP


def test_row_clearance_uses_the_label_floor_only_when_centered():
    """同一对相切的两行：anchored 记 1 单位不足，centered 判通过。"""
    row = (0.0, 0.0, 10.0, 10.0)
    # 相隔 1.5 单位：S-21 的 2 不够，534 的「相邻表行」1 单位够。
    close = (0.0, 11.5, 10.0, 21.5)
    taken = [("the layout label box of net GND", close)]
    gap, why = drawapply._row_clearance(row, taken, "anchored")
    assert gap == 1.5
    assert why is not None and "S-21" in why
    gap, why = drawapply._row_clearance(row, taken, "centered")
    assert gap == 1.5
    assert why is None
    # 相切（0）在两种模型下都不通过：锚点行也要求非负间隔。
    gap, why = drawapply._row_clearance(
        row, [(taken[0][0], (0.0, 10.0, 10.0, 20.0))], "centered",
    )
    assert gap == 0.0 and why is not None


# ---------------------------------------------- 地网分簇：不写 = 不分簇


def _compiled(scene, radius: float):
    """Compile ``scene`` with the stated radius, recording every cluster call."""
    calls: list[float] = []
    real = dc._gnd_clusters

    def spy(points, radius_=dc.GND_LOCAL_RADIUS):
        calls.append(radius_)
        return real(points, radius_)

    dc._gnd_clusters = spy
    try:
        from dataclasses import replace

        result = dc.compile(
            scene.circuit, scene.presentation, b053.library(),
            replace(scene.budget, gnd_cluster_radius=radius),
        )
    finally:
        dc._gnd_clusters = real
    return result, calls


def test_gnd_clustering_off_never_splits_a_ground():
    """不写 gndClustering：`_gnd_clusters` 一次都不被调用，图上没有 535 的痕迹。"""
    scene = b053.scenes()[8]  # LDO：三个 GND 焊盘互距 ≥120，是最容易被分簇的场景
    result, calls = _compiled(scene, 0.0)
    assert calls == [], "0 就是关：分簇函数不许被调用"
    plan = result.candidates[0]
    assert not [note for note in plan.notes if "535" in note]
    assert len(gnd_symbols(plan)) == 1, "旧路径：一个地网一枚旗标"


def test_gnd_clustering_on_splits_the_ground_at_the_stated_radius():
    """写了 radius=100：分簇函数被调用，且半径就是文档写的那个。"""
    scene = b053.scenes()[8]
    result, calls = _compiled(scene, 100.0)
    assert result.ok, [failure.detail for failure in result.failures]
    assert calls and set(calls) == {100.0}, calls
    plan = result.candidates[0]
    assert [note for note in plan.notes if "535" in note], plan.notes
    assert len(gnd_symbols(plan)) > 1, "分簇之后每簇一枚旗标"


def test_the_declared_radius_is_the_budget_the_module_compiler_reads():
    """`pagecompiler._module_budget_for` 像 flagLeadLimit 一样把这个值传下去。"""
    from dataclasses import replace

    from boardwise.engines import pagecompiler as pc

    module_budget = dc.CompileBudget(gnd_cluster_radius=120.0)
    built = pc._module_budget_for(module_budget, pc.PageCompileBudget())
    assert built.gnd_cluster_radius == 120.0
    assert built.flag_lead_limit == module_budget.flag_lead_limit
    # 默认 0 逐字传过去，模块预算不会凭空打开分簇。
    assert pc._module_budget_for(dc.CompileBudget(), pc.PageCompileBudget()).gnd_cluster_radius == 0.0
    assert replace(dc.CompileBudget(), gnd_cluster_radius=0.0).gnd_cluster_radius == 0.0


# -------------------------------------------------- layoutplan 的序列化面


def test_layoutplan_writes_the_label_policy_only_when_stated():
    """`stubMin`/`rowModel` 只在非默认时写；默认标签的 geometry 摘要不动。"""
    plain = LayoutLabel(net="A", text="A", bbox=(0.0, 0.0, 10.0, 10.0))
    body = LayoutPlan(labels=[plain])._label_payload(plain, ownership=True)
    assert "stubMin" not in body and "rowModel" not in body
    stated = LayoutLabel(
        net="A", text="A", bbox=(0.0, 0.0, 10.0, 10.0),
        stub_min=40.0, row_model="centered",
    )
    body = LayoutPlan(labels=[stated])._label_payload(stated, ownership=True)
    assert body["stubMin"] == 40.0 and body["rowModel"] == "centered"
    # 只写一个：另一个仍然不写。
    half = LayoutLabel(net="A", text="A", bbox=(0.0, 0.0, 10.0, 10.0), stub_min=40.0)
    body = LayoutPlan(labels=[half])._label_payload(half, ownership=True)
    assert body["stubMin"] == 40.0 and "rowModel" not in body


def test_a_plan_reads_back_the_two_fields_and_keeps_them():
    """文档 → 数据 → 文档：两个字段往返不丢，默认那份仍然一个字都不多。"""
    plain = LayoutLabel(net="A", text="A", bbox=(0.0, 0.0, 10.0, 10.0))
    stated = LayoutLabel(
        net="B", text="B", bbox=(0.0, 0.0, 10.0, 10.0),
        stub_min=40.0, row_model="centered",
    )
    # 走 plan 自己的读者（`_labels_from`）：字段在 JSON 里往返不丢，默认那份
    # 的 `stubMin`/`rowModel` 键根本不出现。
    payloads = [
        LayoutPlan(labels=[item])._label_payload(item, ownership=True)
        for item in (plain, stated)
    ]
    assert "stubMin" not in payloads[0] and "rowModel" not in payloads[0]
    again = layoutplan._labels_from(payloads)
    assert [(item.stub_min, item.row_model) for item in again] == [
        (0.0, "anchored"), (40.0, "centered"),
    ]
    # 默认那份的 geometry 摘要与「从没听过这两个键」的标签一致。
    assert LayoutPlan(labels=[plain]).geometry_sha256() == (
        LayoutPlan(labels=[LayoutLabel(net="A", text="A", bbox=(0.0, 0.0, 10.0, 10.0))])
        .geometry_sha256()
    )
