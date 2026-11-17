"""548J-A：`serviceGroups` 的页面切片（整组携带 / 整组省略 / 跨模块共存）。

本批只做**页面切片与公开合同**，不做联合座位：`_module_view` 把文档切成每模块
一份时，一个服务组要么整组跟着走，要么整组不出现，任何情况下都不许半组。判据
见 `tasks/548j_pullup_joint_seats.md`「548J-A 公开绘制合同与集成边界」。

不编译、不进几何、不读 `evidence/`：这里只构造两件轻量文档（手写 CircuitSpec +
`PresentationSpec(...)`），然后直接看切片。`ServiceGroup` 与 `PanelBranch` 的字段
就是 parser 的字段（组 `id/branches`，支路 `part/from_net/to_net`），测试不新增
任何字段，也不碰 parser 所在文件。
"""

from __future__ import annotations

import copy
import dataclasses

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import (
    PanelBranch,
    PanelGroup,
    PresentationModule,
    PresentationSpec,
    ServiceGroup,
)
from boardwise.engines import pagecompiler as pc

PROV = "verified_recipe"

PARTS = [
    {"id": "U1", "symbolRef": "MCU32", "value": "MCU", "provenance": PROV},
    {"id": "R1", "symbolRef": "R0402", "value": "10k", "provenance": PROV},
    {"id": "R2", "symbolRef": "R0402", "value": "10k", "provenance": PROV},
    {"id": "R3", "symbolRef": "R0402", "value": "10k", "provenance": PROV},
    {"id": "C1", "symbolRef": "C0402", "value": "100n", "provenance": PROV},
    {"id": "C2", "symbolRef": "C0402", "value": "100n", "provenance": PROV},
]

NETS = [
    {"id": "CFG_A", "class": "signal", "members": ["U1.PA1", "R1.1"],
     "provenance": PROV},
    {"id": "CFG_B", "class": "signal", "members": ["U1.PA2", "R2.1"],
     "provenance": PROV},
    {"id": "BOOT", "class": "signal", "members": ["U1.PB0", "R3.1"],
     "provenance": PROV},
    {"id": "PWR", "class": "power", "members": ["U1.VDD", "R1.2", "R2.2",
                                               "R3.2", "C1.1", "C2.1"],
     "provenance": PROV},
    {"id": "GND", "class": "gnd", "members": ["U1.VSS", "C1.2", "C2.2"],
     "provenance": PROV},
]

#: `mcu` 只持宿主，`pwr` 持上拉与去耦对：两个模块各有一份自己的联合座位。
MODULES = [
    PresentationModule(id="mcu", parts=["U1"]),
    PresentationModule(id="pwr", parts=["R1", "R2", "R3", "C1", "C2"]),
]


def _circuit() -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": copy.deepcopy(PARTS),
        "nets": copy.deepcopy(NETS),
    })


def _branch(part: str, from_net: str, to_net: str) -> PanelBranch:
    return PanelBranch(from_net=from_net, to_net=to_net, part=part)


def _group(group_id: str, *branches: PanelBranch) -> ServiceGroup:
    return ServiceGroup(id=group_id, branches=tuple(branches))


def _presentation(**overrides) -> PresentationSpec:
    payload = {
        "modules": [
            PresentationModule(id=module.id, parts=list(module.parts))
            for module in MODULES
        ],
    }
    payload.update(overrides)
    return PresentationSpec(**payload)


def _view(presentation: PresentationSpec, module_id: str):
    _sub_circuit, sub_presentation = pc._module_view(
        _circuit(), presentation, presentation.module(module_id)
    )
    return sub_presentation


# ------------------------------------------------------- 整组携带、整组省略


def test_a_single_group_travels_whole_into_its_own_module():
    """一个组的全部支路都在 `pwr` 里：整组进 `pwr` 的切片，字段原样。"""
    group = _group(
        "config-pullups",
        _branch("R1", "CFG_A", "PWR"),
        _branch("R2", "CFG_B", "PWR"),
    )
    sub = _view(_presentation(service_groups=[group]), "pwr")

    assert [item.id for item in sub.service_groups] == ["config-pullups"], (
        "同模块的服务组被切片丢掉了：模块编译拿到的文档里没有这个联合座位"
    )
    carried = sub.service_groups[0]
    assert carried == group, "切片不许改写组：字段就是 parser 声明的那几个"
    assert [(branch.part, branch.from_net, branch.to_net)
            for branch in carried.branches] == [
                ("R1", "CFG_A", "PWR"),
                ("R2", "CFG_B", "PWR"),
            ]


def test_one_branch_group_is_a_legal_seating_statement():
    """单支路组合法：一条对宿主的支路仍是一个联合座位声明。"""
    sub = _view(
        _presentation(service_groups=[_group("single", _branch("R3", "BOOT", "PWR"))]),
        "pwr",
    )
    assert [item.id for item in sub.service_groups] == ["single"]
    assert len(sub.service_groups[0].branches) == 1


def test_a_group_with_one_foreign_branch_is_omitted_whole():
    """`C1` 被挪到 `mcu`：组里一支在 `mcu`、一支在 `pwr`，两边都不许有半组。"""
    group = _group(
        "half-here",
        _branch("R1", "CFG_A", "PWR"),
        _branch("C1", "PWR", "GND"),
    )
    presentation = _presentation(
        modules=[
            PresentationModule(id="mcu", parts=["U1", "C1"]),
            PresentationModule(id="pwr", parts=["R1", "R2", "R3", "C2"]),
        ],
        service_groups=[group],
    )
    for module_id in ("mcu", "pwr"):
        sub = _view(presentation, module_id)
        assert sub.service_groups == [], (
            f"{module_id} 只拥有组里的一部分支路，整组必须省略而不是切成半组"
        )


def test_a_module_holding_no_branch_of_a_group_drops_it():
    """组属于 `pwr`，`mcu` 一件都不持有：`mcu` 的切片里没有这个组。"""
    sub = _view(
        _presentation(service_groups=[
            _group("config-pullups", _branch("R1", "CFG_A", "PWR")),
        ]),
        "mcu",
    )
    assert sub.service_groups == []


# ------------------------------------------------- 跨模块共存：两种组、多个组


def test_two_service_groups_on_two_modules_each_travel_to_their_own_slice():
    """`mcu` 与 `pwr` 各有一个服务组：切片各带各的，互不吞并。"""
    presentation = _presentation(
        modules=[
            PresentationModule(id="mcu", parts=["U1", "R3"]),
            PresentationModule(id="pwr", parts=["R1", "R2", "C2"]),
        ],
        service_groups=[
            _group("boot-pullup", _branch("R3", "BOOT", "PWR")),
            _group("config-pullups", _branch("R1", "CFG_A", "PWR")),
        ],
    )

    assert [item.id for item in _view(presentation, "mcu").service_groups] == [
        "boot-pullup"
    ]
    assert [item.id for item in _view(presentation, "pwr").service_groups] == [
        "config-pullups"
    ]


def test_panel_and_service_groups_coexist_on_one_page():
    """同一页里 `panelGroups` 与 `serviceGroups` 不互斥，各模块各拿自己的。"""
    panel = PanelGroup(
        id="decoupling-row",
        side="bottom",
        columns=2,
        branches=(
            _branch("C1", "PWR", "GND"),
            _branch("C2", "PWR", "GND"),
        ),
    )
    presentation = _presentation(
        panel_groups=[panel],
        service_groups=[
            _group("config-pullups",
                   _branch("R1", "CFG_A", "PWR"),
                   _branch("R2", "CFG_B", "PWR")),
        ],
    )

    pwr = _view(presentation, "pwr")
    assert [item.id for item in pwr.panel_groups] == ["decoupling-row"]
    assert [item.id for item in pwr.service_groups] == ["config-pullups"]

    mcu = _view(presentation, "mcu")
    assert mcu.panel_groups == []
    assert mcu.service_groups == []


# --------------------------------------------------- 缺省 / `[]` 的旧行为


def test_no_key_and_an_empty_list_change_nothing():
    """未声明与 `[]` 是同一条旧文档：切片里没有组，切片本身逐字段相同。"""
    bare = _presentation()
    empty = _presentation(service_groups=[])

    assert _view(bare, "pwr").service_groups == []
    assert _view(empty, "pwr").service_groups == []
    assert _view(bare, "pwr") == _view(empty, "pwr"), (
        "空数组不许让切片与未声明时长得不一样"
    )


def test_the_old_view_carries_no_other_new_field():
    """本批只加 `serviceGroups` 切片，不虚构别的字段、不动别的键。"""
    barer = _view(_presentation(), "pwr")
    declared = _view(
        _presentation(service_groups=[
            _group("config-pullups", _branch("R1", "CFG_A", "PWR")),
        ]),
        "pwr",
    )
    assert barer.service_groups == []
    assert [item.id for item in declared.service_groups] == ["config-pullups"]
    # 组只活在 `serviceGroups` 里：没被顺手塞进 panel 或 series 声明。
    assert declared.panel_groups == []
    assert declared.series_branches == []


def test_the_sliced_group_carries_only_the_declared_fields():
    """切片不虚构字段：组只有 `id/branches`，支路只有 `part/from/to`。"""
    group = _group("config-pullups", _branch("R1", "CFG_A", "PWR"))
    sub = _view(_presentation(service_groups=[group]), "pwr")

    assert dataclasses.asdict(sub.service_groups[0]) == {
        "id": "config-pullups",
        "branches": ({"from_net": "CFG_A", "to_net": "PWR", "part": "R1"},),
    }, "切片给组加了字段（side/columns/gap/pitch/frame/坐标一律不许有）"


def test_a_sliced_view_without_groups_keeps_the_old_json():
    """无键与 `[]` 的切片序列化逐字节相同，且都不写 `serviceGroups`。"""
    bare = _view(_presentation(), "pwr")
    empty = _view(_presentation(service_groups=[]), "pwr")

    assert "serviceGroups" not in bare.to_jsonable()
    assert bare.to_jsonable() == empty.to_jsonable()
    assert bare == empty


def test_a_carried_group_keeps_its_document_shape_through_the_slice():
    """带组的切片写回的还是文档那两键三键，不是切片自己的一门方言。"""
    sub = _view(
        _presentation(service_groups=[
            _group("config-pullups", _branch("R1", "CFG_A", "PWR")),
        ]),
        "pwr",
    )
    assert sub.to_jsonable()["serviceGroups"] == [{
        "id": "config-pullups",
        "branches": [{"part": "R1", "from": "CFG_A", "to": "PWR"}],
    }]
