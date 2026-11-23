"""548M 页级传递：`railClustering.radius` 不能死在 `_module_view` 上。

548M 把 `railClustering.radius` 接进了单模块 `drawcompiler.compile`：预算里
`rail_cluster_radius > 0` 的页按"每簇一枚旗"画电源/地轨。但页级路径上声明会
**两次丢失**：

* `pagecompiler._module_view` 新建 `PresentationSpec` 时逐字段搬运，既没带
  `rail_cluster_radius` 也没带 `gnd_cluster_radius`——模块视图上两个字段都是缺省 0；
* `compile_page` 只把 `gndClustering.radius` 写进 `module_budget`（053f），
  `_module_budget_for` 也只传 `gnd_cluster_radius`，`railClustering` 没人接。

结果：`railClustering: {radius: 120}` 的页，模块预算与模块视图都是 0/0，页上
仍然逐脚旗，而单模块 `dc.compile(整页文档)` 却分簇——同一份文档两个入口给出
两种图。

本文件钉三件事（诊断/修复都只碰 pagecompiler）：

1. `_module_view` 保留两个声明（模块视图上读得到 120/130）；
2. `dc.compile(module_view)` 不另给预算也按声明分簇——簇数不是逐脚；
3. `compile_page` 交给 `dc.compile` 的模块预算里，两个半径都是声明值；无声明时
   两者为 0，页仍走旧读数。

夹具照 ``tests/test_548m_rail_clustering.py`` 的 builder（自包含，不 import
他人夹具）：真宿主、真二端件、真生产尺，不写坐标表、不调阈值。
"""

from __future__ import annotations

import copy

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc

PROV = "verified_recipe"
PAGE = (0.0, 0.0, 1170.0, 825.0)
STUB_MIN = 40.0
PARTS = ["U1", "R1", "R2", "R3", "C1", "C2"]
RAIL_RADIUS = 100.0
GND_RADIUS = 130.0
#: 7 焊盘的电源轨在半径 100 下的实测分簇（与 548M 同一条读数）：4 枚旗，
#: 不写开关时是 7 枚逐脚旗。
RAIL_FLAGS = 4
PER_PIN_FLAGS = 7


# ------------------------------------------------------------------ 真实夹具


def _pin(number: str, tip, direction: str) -> dict:
    return {"number": number, "name": number, "tip": list(tip),
            "direction": direction, "length": 10.0, "pinType": "passive"}


def _symbol(ref: str, body, pins) -> dict:
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": list(body), "pins": pins,
            "source": "test fixture (rail page view, builder from 548M)"}


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


def _circuit() -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": [
            _part("U1", "HOST8", "HOST"),
            _part("R1", "R", "10k"), _part("R2", "R", "10k"),
            _part("R3", "R", "10k"),
            _part("C1", "C", "100n"), _part("C2", "C", "100n"),
        ],
        "nets": [
            _net("PWR", "power",
                 ["U1.VDD", "U1.VDD2", "R1.2", "R2.2", "R3.2",
                  "C1.1", "C2.1"]),
            _net("RET", "gnd",
                 ["U1.GND", "U1.GND2", "U1.GND3", "C1.2", "C2.2"]),
            _net("SIG_A", "signal", ["U1.SIG_A", "R1.1", "R3.1"]),
            _net("SIG_B", "signal", ["U1.SIG_B", "R2.1"]),
            _net("SIG_C", "signal", ["U1.SIG_C"]),
        ],
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


def _module_budget() -> dc.CompileBudget:
    # 返回轨的旗符号：给它自己的旗，簇才有可数的图形。
    return dc.CompileBudget(max_candidates=4, page_box=PAGE, gnd_flag="PWR-RET")


def _page_budget() -> pc.PageCompileBudget:
    # 页级预算必须带图纸（`_check_budget`）；模板块的搜索深度也一并收窄。
    return pc.PageCompileBudget(
        page_box=PAGE, max_candidates=4,
        module_budget=_module_budget(),
    )


def _flags(plan, net_id: str):
    return [flag for flag in plan.power_symbols if flag.net == net_id]


class _Recorded(RuntimeError):
    """模板块记录的哨兵：记录到第一次模块编译就停，不装整页成功。"""


def _recorder():
    seen: list[dict] = []

    def fake(circuit, presentation, profiles=None, budget=None, **kwargs):
        seen.append({
            "modules": [module.id for module in presentation.modules],
            "view_rail": getattr(presentation, "rail_cluster_radius", None),
            "view_gnd": getattr(presentation, "gnd_cluster_radius", None),
            "budget_rail": getattr(budget, "rail_cluster_radius", None),
            "budget_gnd": getattr(budget, "gnd_cluster_radius", None),
            "budget": budget,
        })
        raise _Recorded()

    return seen, fake


# ------------------------------------------------- 1. 模块视图保留两个声明


def test_module_view_keeps_the_declared_rail_and_gnd_radius():
    """`_module_view` 是逐字段搬运的：两个半径都必须在切片上活着。"""
    spec = _spec(RAIL_RADIUS, GND_RADIUS)
    module = spec.modules[0]
    _sub_circuit, sub_presentation = pc._module_view(_circuit(), spec, module)
    assert sub_presentation.rail_cluster_radius == RAIL_RADIUS
    assert sub_presentation.gnd_cluster_radius == GND_RADIUS


def test_module_view_without_the_switches_keeps_zero():
    """没声明时切片上仍是 0：旧页的字节不变不能说成"被默认成某个半径"。"""
    spec = _spec()
    _sub_circuit, sub_presentation = pc._module_view(
        _circuit(), spec, spec.modules[0])
    assert sub_presentation.rail_cluster_radius == 0.0
    assert sub_presentation.gnd_cluster_radius == 0.0


# ------------------------------- 2. 直接编译模块视图也按声明分簇（因果项）


def test_direct_compile_of_the_module_view_clusters_the_rail():
    """`dc.compile(sub_circuit, sub_presentation)`（不另给半径）就分簇。

    这正是 548M 在 `compile` 入口做的承诺（文档上的半径写进预算）；页级路径
    把声明丢在 `_module_view` 上时，同一次调用会退回逐脚旗（对照条）。
    """
    spec = _spec(RAIL_RADIUS)
    sub_circuit, sub_presentation = pc._module_view(
        _circuit(), spec, spec.modules[0])
    assert sub_presentation.rail_cluster_radius == RAIL_RADIUS

    result = dc.compile(sub_circuit, sub_presentation, _book(), _module_budget())
    assert result.ok, [
        (item.category, item.subject, item.detail) for item in result.failures
    ]
    plan = result.best()
    assert plan is not None
    assert len(_flags(plan, "PWR")) == RAIL_FLAGS


def test_the_same_view_without_the_radius_is_the_per_pin_reading():
    """对照：把声明从视图上抹掉，同一次编译回到 7 枚逐脚旗。

    没有这一条，上面那条只证明"编译成功"，证明不了它读的是声明。
    """
    spec = _spec(RAIL_RADIUS)
    sub_circuit, sub_presentation = pc._module_view(
        _circuit(), spec, spec.modules[0])
    stripped = copy.deepcopy(sub_presentation)
    stripped.rail_cluster_radius = 0.0

    result = dc.compile(sub_circuit, stripped, _book(), _module_budget())
    assert result.ok, [
        (item.category, item.subject, item.detail) for item in result.failures
    ]
    plan = result.best()
    assert plan is not None
    assert len(_flags(plan, "PWR")) == PER_PIN_FLAGS


# ------------------------------ 3. 页级把两个声明写进模块预算（含默认）


def test_compile_page_states_both_radii_on_the_module_budget(monkeypatch):
    """`compile_page` 交给 `dc.compile` 的预算里，两个半径都是声明值。"""
    seen, fake = _recorder()
    monkeypatch.setattr(pc.drawcompiler, "compile", fake)
    with pytest.raises(_Recorded):
        pc.compile_page(_circuit(), _spec(RAIL_RADIUS, GND_RADIUS), _book(), _page_budget())

    assert [item["modules"] for item in seen] == [["m"]]
    record = seen[0]
    assert record["view_rail"] == RAIL_RADIUS
    assert record["view_gnd"] == GND_RADIUS
    assert record["budget_rail"] == RAIL_RADIUS
    assert record["budget_gnd"] == GND_RADIUS


def test_compile_page_without_the_switches_states_zero(monkeypatch):
    """无声明：视图与预算两边都是 0，模块预算不因本批改动多出半径。"""
    seen, fake = _recorder()
    monkeypatch.setattr(pc.drawcompiler, "compile", fake)
    with pytest.raises(_Recorded):
        pc.compile_page(_circuit(), _spec(), _book(), _page_budget())

    record = seen[0]
    assert record["view_rail"] == 0.0
    assert record["view_gnd"] == 0.0
    assert record["budget_rail"] == 0.0
    assert record["budget_gnd"] == 0.0


def test_the_carried_radius_never_clusters_a_signal(monkeypatch):
    """声明只作用于电源/地轨：signal 网的簇半径仍是 0（548M 的作用域）。"""
    seen, fake = _recorder()
    monkeypatch.setattr(pc.drawcompiler, "compile", fake)
    with pytest.raises(_Recorded):
        pc.compile_page(_circuit(), _spec(RAIL_RADIUS, GND_RADIUS), _book(), _page_budget())

    budget = seen[0]["budget"]
    assert dc._cluster_radius_for(budget, "signal") == 0.0
    assert dc._cluster_radius_for(budget, "power") == RAIL_RADIUS
    # 同一张地网上两个键都适用时取较大者：130 胜出（既有合同）。
    assert dc._cluster_radius_for(budget, "gnd") == GND_RADIUS
