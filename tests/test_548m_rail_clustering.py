"""548M：把 053f 的就近分簇开到 **电源轨**（`railClustering`），默认关闭。

## 这一批要解决的问题（实测背景）

548J/548L 的 wifi 页上 `3V3` 一颗网挂了 **6 枚**旗，其中三枚挤在去耦对上方、彼此只
隔 7.2 单位。岳的人工参照页是「三件共享一条短轨 + 一枚旗」。仓库里早就有这套能力：
053f 的 `gndClustering.radius` 把同网焊盘按半径分组、写进 `_Expression.clusters`，
绘制侧对 `len(clusters) >= 2` 的网逐簇各画一枚旗 + 短轨。本批给**电源轨**开同一套
能力，用新显式键 `railClustering: {"radius": N}`，**默认关闭**。

## 样式与作用域（548M 裁决）

* **不改 053 sec.7 的默认**：没写这个键的页，高扇出电源网仍是逐脚一枚旗，一行不动；
* **按声明变更样式**：写了 `railClustering`（预算里 `rail_cluster_radius > 0`）且本网
  是 `power`、焊盘 ≥ 2 时，`_expression_style` 返回 `wire` —— 这条轨按簇画短轨、
  一簇一旗。这是**文档的显式声明**，不是对 053 默认的覆盖（默认那一页仍走原分支）；
* **power 与 gnd 都生效**：岳的人工 P44 页要求「去耦对共享一枚 GND 旗、宿主 GND 就近
  独立一枚」，而这页 `gndClustering` 没写；`railClustering` 一条语句说"一枚旗可以汇聚
  半径内的焊盘"，对两类网是同一句话。`gndClustering` 的既有语义一行不动：两者对同一
  gnd 网都适用时取**较大者**，只写 `gndClustering` 的页读法与 053f 完全相同。

## 本文件钉住什么

1. 正例：7 焊盘的电源网在半径 100 下分成 4 簇时，`powerSymbols` 的该网条目数
   **== 簇数（4），不是焊盘数（7）**，每簇一枚，簇号注记 1/4…4/4 齐全；
2. 默认关闭：同一页不写这个键 → 旗数回到焊盘数 7，几何摘要等于钉住的常量；
3. 作用域：写了 `railClustering` 的页上返回轨也一簇一枚（2 枚，与 P44 同形）；
   只写 `gndClustering` 的既有页读数完全相同（053f 未被改）；
4. 网类门：`_cluster_radius_for` 把 `railClustering` 给 power 与 gnd，从不给 signal；
5. 参数：`radius` 必须是正的有限数、对象封闭、缺省不写进规范 JSON。

夹具照 ``tests/test_548k_stub_lane.py`` 的 builder 照抄（自包含，不 import 他人夹具）：
真宿主、真二端件、真生产尺，不写坐标表、不用 userLocks、不缩字、不调
``near``/``max_nodes``/``GAP``。器件名与网名是通用的。
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec, PresentationSpecError
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc

PROV = "verified_recipe"
PAGE = (0.0, 0.0, 1170.0, 825.0)
STUB_MIN = 40.0
PARTS = ["U1", "R1", "R2", "R3", "C1", "C2"]
RAIL_RADIUS = 100.0
#: The page with **no** `railClustering`: the reading this fixture has when the
#: key is absent (measured, `test_without_the_switch…`). That the absent-key
#: reading is byte-identical to the pre-548M build is measured on the **real**
#: 548J page: there it lands on 548L's recorded `8802d317cfae…` (交卷读数).
PRE_548M_GEOMETRY = (
    "57e87566d051ed4461bcac0a3ebb985ca9735919246fffb3f268a23a5d225f04"
)
#: 7 焊盘的电源轨在半径 100 下的实测分簇（sizes）；正例钉的就是它。
PWR_CLUSTER_SIZES = [3, 1, 1, 2]
#: 5 焊盘的返回轨在半径 100 下的实测分簇（`gndClustering` 那条老路径）。
RET_CLUSTER_SIZES = [2, 3]


# ------------------------------------------------------------------ 真实夹具


def _pin(number: str, tip, direction: str) -> dict:
    return {"number": number, "name": number, "tip": list(tip),
            "direction": direction, "length": 10.0, "pinType": "passive"}


def _symbol(ref: str, body, pins) -> dict:
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": list(body), "pins": pins,
            "source": "test fixture (548M, builder copied from 548K)"}


def _profile_payloads() -> dict[str, dict]:
    return {
        "HOST8": _symbol("HOST8", [-70.0, -60.0, 70.0, 60.0], [
            _pin("VDD2", [80.0, 80.0], "right"),
            _pin("SIG_C", [80.0, 55.0], "right"),
            _pin("VDD", [80.0, 45.0], "right"),
            _pin("SIG_B", [-80.0, 15.0], "left"),
            _pin("SIG_A", [-80.0, 5.0], "left"),
            _pin("GND", [-80.0, -45.0], "left"),
            _pin("GND2", [-80.0, -25.0], "left"),
            _pin("GND3", [-80.0, -5.0], "left"),
        ]),
        "R": _symbol("R", [-10.5, -4.5, 10.5, 4.5], [
            _pin("1", [-20.0, 0.0], "left"),
            _pin("2", [20.0, 0.0], "right"),
        ]),
        "C": _symbol("C", [-5.5, -8.5, 5.5, 8.5], [
            _pin("1", [0.0, 20.0], "up"),
            _pin("2", [0.0, -20.0], "down"),
        ]),
        "PWR-PWR": _symbol("PWR-PWR", [-6.0, 0.0, 6.0, 18.0], []),
        "PWR-RET": _symbol("PWR-RET", [-6.0, 0.0, 6.0, 18.0], []),
    }


def _book() -> dict[str, SymbolProfile]:
    return {
        ref: SymbolProfile.from_dict(copy.deepcopy(payload))
        for ref, payload in _profile_payloads().items()
    }


def _part(part_id: str, symbol: str, value: str = "") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value,
            "provenance": PROV}


def _net(net_id: str, cls: str, members) -> dict:
    return {"id": net_id, "class": cls, "members": list(members),
            "provenance": PROV}


def _parts() -> list[dict]:
    return [
        _part("U1", "HOST8", "HOST"),
        _part("R1", "R", "10k"), _part("R2", "R", "10k"),
        _part("R3", "R", "10k"),
        _part("C1", "C", "100n"), _part("C2", "C", "100n"),
    ]


def _nets() -> list[dict]:
    return [
        # 7 焊盘的电源轨：没写开关时超过 high_fanout，走 053 sec.7 的逐脚旗。
        _net("PWR", "power",
             ["U1.VDD", "U1.VDD2", "R1.2", "R2.2", "R3.2", "C1.1", "C2.1"]),
        # 5 焊盘的返回轨：gnd 永远是 wire 样式，簇直接决定旗数。
        _net("RET", "gnd",
             ["U1.GND", "U1.GND2", "U1.GND3", "C1.2", "C2.2"]),
        _net("SIG_A", "signal", ["U1.SIG_A", "R1.1", "R3.1"]),
        _net("SIG_B", "signal", ["U1.SIG_B", "R2.1"]),
        _net("SIG_C", "signal", ["U1.SIG_C"]),
    ]


def _circuit() -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": copy.deepcopy(_parts()),
        "nets": copy.deepcopy(_nets()),
    })


def _document(rail_radius: float | None = None,
              gnd_radius: float | None = None) -> dict:
    document = {
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right",
                            "load": "right", "source": "left",
                            "power": "top", "gnd": "bottom"},
        "modules": [{
            "id": "m", "parts": list(PARTS),
            "role": "host island", "grammarRef": "ic-periphery", "core": "U1",
        }],
        "labelPolicy": {
            "local": "wire", "crossModule": "label", "highFanout": "label",
            "stub": "straight", "rowModel": "centered", "stubMin": STUB_MIN,
            "stubLaneReserve": True,
        },
    }
    if rail_radius is not None:
        document["railClustering"] = {"radius": rail_radius}
    if gnd_radius is not None:
        document["gndClustering"] = {"radius": gnd_radius}
    return document


def _spec(rail_radius: float | None = None,
          gnd_radius: float | None = None) -> PresentationSpec:
    return PresentationSpec.from_dict(
        copy.deepcopy(_document(rail_radius, gnd_radius))
    )


def _budget() -> dc.CompileBudget:
    # 这一页的返回轨叫 RET，旗库里的符号就叫 PWR-RET：给它自己的旗，簇才有
    # 可数的图形（关掉旗就没有"每簇一枚"这回事可言）。
    return dc.CompileBudget(
        max_candidates=4, page_box=PAGE, gnd_flag="PWR-RET",
    )


def _compile(rail_radius: float | None = None,
             gnd_radius: float | None = None):
    spec = _spec(rail_radius, gnd_radius)
    result = dc.compile(_circuit(), spec, _book(), _budget())
    return spec, result


def _plan_or_fail(rail_radius: float | None = None,
                  gnd_radius: float | None = None):
    spec, result = _compile(rail_radius, gnd_radius)
    assert result.ok, [
        (item.category, item.subject, item.detail, item.action)
        for item in result.failures
    ]
    plan = result.best()
    assert plan is not None
    return spec, plan


def _tips(plan, book) -> dict[str, tuple[float, float]]:
    out = {}
    for part in plan.parts:
        profile = book[part.symbol_ref]
        for pin in profile.pins:
            out[f"{part.part_id}.{pin.number}"] = transform_point(
                pin.tip[0], pin.tip[1], rotation=part.rotation,
                mirror=part.mirror, ox=part.x, oy=part.y,
            )
    return out


def _clusters(plan, net_id: str, radius: float):
    """The compiler's own partition of one net's pads at ``radius`` (053f)."""
    book = _book()
    tips = _tips(plan, book)
    members = next(net.members for net in _circuit().nets if net.id == net_id)
    pads = tuple((member, tips[member]) for member in members)
    return pads, dc._gnd_clusters(pads, radius)


def _flags(plan, net_id: str):
    return [flag for flag in plan.power_symbols if flag.net == net_id]


# ------------------------------------------------------------------ 1. 正例


def test_a_declared_rail_radius_draws_one_flag_per_cluster():
    """写入 `railClustering`：旗数 == 簇数（不是焊盘数），每簇一枚。

    这一页的电源轨 PWR 有 7 个焊盘、在半径 100 下分成 **4** 个街区（实测
    ``sizes == [3, 1, 1, 2]``）。不写开关时它是 7 枚逐脚旗（053 sec.7 的默认，
    见下一条）；写了就变成 4 枚——一枚落在每个街区里（535 的簇号注记 1/4…4/4）。
    """
    spec, plan = _plan_or_fail(RAIL_RADIUS)
    assert spec.rail_cluster_radius == RAIL_RADIUS
    pads, clusters = _clusters(plan, "PWR", RAIL_RADIUS)
    assert len(pads) == 7
    assert [len(group) for group in clusters] == PWR_CLUSTER_SIZES
    flags = _flags(plan, "PWR")
    assert len(flags) == len(clusters), [(f.x, f.y) for f in flags]
    for group in clusters:
        near = [
            flag for flag in flags
            if any(
                abs(flag.x - point[0]) <= RAIL_RADIUS
                and abs(flag.y - point[1]) <= RAIL_RADIUS
                for _member, point in group
            )
        ]
        assert near, ([member for member, _p in group], [(f.x, f.y) for f in flags])
    notes = [note for note in plan.notes if "net PWR" in note]
    named = {
        index for index in range(1, len(clusters) + 1)
        if any(f"cluster {index}/{len(clusters)}" in note for note in notes)
    }
    assert named == set(range(1, len(clusters) + 1)), notes


def test_without_the_switch_the_page_is_the_pre_548m_drawing():
    """默认关闭：同一页不写这个键 → 与能力引入前逐字节相同。

    `PRE_548M_GEOMETRY` 是本夹具在改动前的实测摘要；电源轨回到 053 sec.7 的
    逐脚答案（7 枚），返回轨 1 枚。这一条就是"默认关闭不是跳过，而是旧读数"
    的机器读法。
    """
    spec, plan = _plan_or_fail(None)
    assert spec.rail_cluster_radius == 0.0
    assert plan.geometry_sha256() == PRE_548M_GEOMETRY, plan.geometry_sha256()
    assert len(_flags(plan, "PWR")) == 7
    assert len(_flags(plan, "RET")) == 1


# --------------------------------------------------------------- 2. 作用域


def test_rail_clustering_also_splits_a_ground():
    """`railClustering` 对 gnd 同样生效：返回轨一簇一枚（岳的 P44 同形）。

    同一条 5 焊盘的返回轨，半径 100 下分成两个街区（``[2, 3]``）：去耦对那一侧
    共享一枚旗，宿主 GND 就近一枚。写了 `railClustering` 的页上就是 **2 枚**——
    岳的人工 P44 页（`RULES.md` §1：去耦对共享一枚、宿主 GND 就近独立一枚）就是
    这个形状；把地线绕成一枚旗的"GND 外框"是 548D 时代被拒过的画法。
    """
    spec, plan = _plan_or_fail(RAIL_RADIUS)
    assert spec.rail_cluster_radius == RAIL_RADIUS
    assert spec.gnd_cluster_radius == 0.0
    pads, clusters = _clusters(plan, "RET", RAIL_RADIUS)
    assert [len(group) for group in clusters] == RET_CLUSTER_SIZES
    assert len(pads) == 5
    flags = _flags(plan, "RET")
    assert len(flags) == len(clusters) == 2, [(f.x, f.y) for f in flags]
    notes = [note for note in plan.notes if "net RET" in note]
    for index in (1, 2):
        assert any(f"cluster {index}/2" in note for note in notes), notes


def test_gnd_clustering_still_draws_the_return_rail_per_cluster():
    """`gndClustering` 的既有语义一行不动：它单独声明时仍是同样的分簇。

    地半径的搬运是 053f 自己的事（页级由 pagecompiler 搬，单模块调用里由调用方
    在 budget 上写明——`tests/test_053e_ground_clusters.py` 的同一惯例）。本批
    **没有**给 `gndClustering` 加任何搬运，所以这里显式写在 budget 上；同一半径
    下它的读数与上面那条 `railClustering` 的完全相同，是"既有金标准没被改"的读法。
    """
    spec = _spec(None, gnd_radius=RAIL_RADIUS)
    assert spec.gnd_cluster_radius == RAIL_RADIUS
    budget = dc.CompileBudget(
        max_candidates=4, page_box=PAGE, gnd_flag="PWR-RET",
        gnd_cluster_radius=RAIL_RADIUS,
    )
    result = dc.compile(_circuit(), spec, _book(), budget)
    assert result.ok, [(item.category, item.detail) for item in result.failures]
    plan = result.best()
    _pads, clusters = _clusters(plan, "RET", RAIL_RADIUS)
    assert [len(group) for group in clusters] == RET_CLUSTER_SIZES
    flags = _flags(plan, "RET")
    assert len(flags) == len(clusters) == 2
    notes = [note for note in plan.notes if "net RET" in note]
    for index in (1, 2):
        assert any(f"cluster {index}/2" in note for note in notes), notes


# ------------------------------------------------------------ 3. 网类门


def test_the_radius_reaches_power_and_gnd_and_never_a_signal():
    """`_cluster_radius_for`：rail 给 power **和** gnd，gnd 另认 `gndClustering`。

    这一条是**网类门的单元读法**：它不经过布局，所以能把它和"这一页碰巧怎么摆"
    分开。同一张 gnd 网两条都适用时取较大者（两条都说了"一枚旗能走多远"，窄的
    那条会把宽的那条悄悄丢掉）。
    """
    rail = dc.CompileBudget(rail_cluster_radius=RAIL_RADIUS)
    gnd = dc.CompileBudget(gnd_cluster_radius=130.0)
    both = dc.CompileBudget(
        rail_cluster_radius=RAIL_RADIUS, gnd_cluster_radius=130.0)
    assert dc._cluster_radius_for(rail, "power") == RAIL_RADIUS
    assert dc._cluster_radius_for(rail, "gnd") == RAIL_RADIUS
    assert dc._cluster_radius_for(rail, "signal") == 0.0
    assert dc._cluster_radius_for(gnd, "gnd") == 130.0
    assert dc._cluster_radius_for(gnd, "power") == 0.0
    assert dc._cluster_radius_for(both, "power") == RAIL_RADIUS
    assert dc._cluster_radius_for(both, "gnd") == 130.0
    assert dc._cluster_radius_for(dc.CompileBudget(), "power") == 0.0


# --------------------------------------------------------- 4. 参数与规范形


@pytest.mark.parametrize("bad", [0, -5, "x", True, float("nan"), float("inf")])
def test_a_rail_radius_must_be_a_positive_finite_number(bad):
    document = _document()
    document["railClustering"] = {"radius": bad}
    with pytest.raises(PresentationSpecError) as caught:
        PresentationSpec.from_dict(document)
    assert "$.railClustering.radius" in str(caught.value)


def test_a_rail_clustering_object_is_closed():
    document = _document()
    document["railClustering"] = {"radius": 100, "mode": "clubs"}
    with pytest.raises(PresentationSpecError) as caught:
        PresentationSpec.from_dict(document)
    assert "railClustering" in str(caught.value)
    assert "mode" in str(caught.value)


def test_the_canonical_form_leaves_the_key_out_when_it_is_absent():
    """不写 = 旧文档：键不出现、往返摘要不动（与 548K 的开关同一口径）。"""
    spec = PresentationSpec.from_dict(copy.deepcopy(_document()))
    payload = spec.to_jsonable()
    assert "railClustering" not in payload
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert "railClustering" not in canonical
    assert spec.sha256() == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    again = PresentationSpec.from_dict(copy.deepcopy(payload))
    assert again.to_jsonable() == payload
    assert again.sha256() == spec.sha256()
    stated = _spec(RAIL_RADIUS)
    assert stated.to_jsonable()["railClustering"] == {"radius": RAIL_RADIUS}
    assert PresentationSpec.from_dict(
        stated.to_jsonable()
    ).sha256() == stated.sha256()
