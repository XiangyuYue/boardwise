"""548J-A：`serviceGroups` 的数据合同 —— 宿主侧支路组的联合座位声明。

这一批只做**公开解析与封闭负例**：一组宿主本地支路（配置上拉、去耦对）用
`{"id", "branches"}` 说出「这些支路作为一个整体读、一组供、一组回流」，支路用
`{"part", "from", "to"}` 说出电气形状；宿主脚侧、姿态、端子行、节距、旗位、文字和
frame 全部由消费方按真实 CircuitSpec + profile + 候选推导，本批不实现、也不声称
改变任何几何。钉住：

1. **不写 = 不读不写出**：旧文档规范 JSON 无这个键，摘要仍是 `50b112…`；
   `[]` 与不写等价。
2. **显式声明可往返**：组封闭两键、支路封闭三键，支路声明顺序逐字保留，
   `from_dict(to_jsonable()) == spec`、重复解析幂等、`dump`/`load` 一致。
3. **具名拒绝**：重复组 id、组内/跨组/跨 `seriesBranches`/跨 `panelGroups` 的重复
   器件、`from == to`、未声明或跨模块器件、空字段/空支路、未知键、坐标键，一律
   `PresentationSpecError` 并点名路径。组不带 `side`/`columns`/`gap`/`pitch`/`frame`。
4. **旧位置构造兼容**：新字段追加在现有字段最后，旧位置参数一位不挪。

不写这一批没做的事：联合座位与旗域几何、页面切片、电路两脚校验、宿主唯一性、
V3/V4 真机、容器 parser、多板、CBB、Rust 迁移。"parser 接受"不等于电气合同已验证。
"""

from __future__ import annotations

import dataclasses
import json
import re

import pytest

from boardwise.core.presentationspec import (
    DEFAULT_SIDE_PREFERENCES,
    SERVICE_BRANCH_KEYS,
    SERVICE_GROUP_KEYS,
    SERVICE_MIN_BRANCHES,
    LabelPolicy,
    PanelBranch,
    PresentationSpec,
    PresentationSpecError,
    ServiceGroup,
)

#: `_DOCUMENT` 的摘要，由**改动前**那棵树算出来（与 548B1 / 548D 钉的同一个数）。
_BASE_DIGEST = "50b112989558bb4b3dff6765d3d3ae67cff6b21228a8d2a18cded25abde3f5ea"

#: 一份 053 时期的普通文档，形状照 053A 的 `_presentation()`（照抄而不是 import）。
_DOCUMENT = {
    "modules": [{"id": "m-divider", "parts": ["R1", "R2"],
                 "role": "voltage divider"}],
    "mainPaths": [{"id": "main",
                   "chain": ["net:VIN", "part:R1", "net:TAP", "part:R2",
                             "net:GND"]}],
    "portRoles": {"VIN": "input", "TAP": "output"},
    "grammarRef": "voltage-divider",
    "directWiringObligations": [{"nets": ["TAP"], "note": "the tap is a stub"}],
    "labelPolicy": {"local": "wire", "crossModule": "label", "highFanout": "label"},
    "sidePreferences": {"input": "left", "power": "top"},
    "userLocks": [{"partId": "J1", "x": 320.0, "y": 200.0, "rotation": 0}],
}

_SERVICE_MODULES = [
    {"id": "m-cfg", "parts": ["R1", "R2", "R3"], "role": "config pull-ups"},
    {"id": "m-dec", "parts": ["C1", "C2"], "role": "decoupling pair"},
]


def _presentation(**overrides):
    payload = dict(_DOCUMENT)
    payload.update(overrides)
    return payload


def _service_document(**overrides):
    payload = {"modules": [dict(module) for module in _SERVICE_MODULES]}
    payload.update(overrides)
    return payload


def _branch(part, from_net="CFG", to_net="PWR"):
    return {"part": part, "from": from_net, "to": to_net}


def _group(**overrides):
    entry = {
        "id": "config-pullups",
        "branches": [
            _branch("R1", "CFG_A"),
            _branch("R2", "CFG_B"),
            _branch("R3", "CFG_C"),
        ],
    }
    entry.update(overrides)
    return entry


def _canonical(spec):
    return json.dumps(
        spec.to_jsonable(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


# --------------------------------------------------------- 默认关闭（缺省等价）


def test_a_spec_that_states_no_service_group_keeps_its_digest():
    """没写这个键的文档，规范 JSON 里不许出现它，摘要一位都不许动。"""
    spec = PresentationSpec.from_dict(_presentation())
    assert spec.service_groups == []
    assert "serviceGroups" not in _canonical(spec)
    assert spec.sha256() == _BASE_DIGEST, (
        f"未改动的 053 文档必须与本键出现之前逐字节同摘要（得到 {spec.sha256()}）"
    )


def test_an_empty_list_is_the_same_statement_as_no_key():
    """`[]` 与不写等价：同样不写出、同样摘要、同样不带任何组。"""
    empty = PresentationSpec.from_dict(_service_document(serviceGroups=[]))
    plain = PresentationSpec.from_dict(_service_document())
    assert empty.service_groups == []
    assert "serviceGroups" not in _canonical(empty)
    assert _canonical(empty) == _canonical(plain)
    assert empty.sha256() == plain.sha256()


def test_the_contract_vocabulary_is_what_it_says():
    assert SERVICE_GROUP_KEYS == ("id", "branches")
    assert SERVICE_BRANCH_KEYS == ("part", "from", "to")
    assert SERVICE_MIN_BRANCHES == 1


# --------------------------------------------------------------- 正例 round-trip


def test_a_single_branch_group_round_trips(tmp_path):
    """单支路组合法：一个支路就是一条座位声明。"""
    spec = PresentationSpec.from_dict(_service_document(
        serviceGroups=[{"id": "cfg-a", "branches": [_branch("R1", "CFG_A")]}]
    ))
    assert spec.service_groups == [ServiceGroup(
        id="cfg-a",
        branches=(PanelBranch(from_net="CFG_A", to_net="PWR", part="R1"),),
    )]
    written = spec.to_jsonable()["serviceGroups"]
    assert written == [{
        "id": "cfg-a",
        "branches": [{"part": "R1", "from": "CFG_A", "to": "PWR"}],
    }]
    assert set(written[0]) == set(SERVICE_GROUP_KEYS)
    assert set(written[0]["branches"][0]) == set(SERVICE_BRANCH_KEYS)
    assert PresentationSpec.from_dict(spec.to_jsonable()) == spec
    path = tmp_path / "service.presentation.json"
    spec.dump(path)
    assert PresentationSpec.load(path) == spec


def test_a_multi_branch_group_keeps_the_declared_order():
    """多支路：声明顺序只用于稳定遍历与具名拒绝，不是端子行的几何次序。"""
    spec = PresentationSpec.from_dict(_service_document(
        serviceGroups=[
            _group(),
            {"id": "decoupling", "branches": [
                _branch("C1", "VCC", "GND"),
                _branch("C2", "VCC", "GND"),
            ]},
        ]
    ))
    assert [group.id for group in spec.service_groups] == [
        "config-pullups", "decoupling",
    ]
    assert [branch.part for branch in spec.service_groups[0].branches] == [
        "R1", "R2", "R3",
    ]
    assert [branch.from_net for branch in spec.service_groups[1].branches] == [
        "VCC", "VCC",
    ]
    written = spec.to_jsonable()["serviceGroups"]
    assert [branch["part"] for branch in written[0]["branches"]] == [
        "R1", "R2", "R3",
    ]
    assert PresentationSpec.from_dict(spec.to_jsonable()) == spec
    assert PresentationSpec.from_dict(
        PresentationSpec.from_dict(spec.to_jsonable()).to_jsonable()
    ).to_jsonable() == spec.to_jsonable()


def test_groups_of_different_modules_coexist_with_panel_groups():
    """不同模块、不同器件的 panel/service 组允许共存，不做全页互斥。"""
    modules = [
        {"id": "m-key", "parts": ["S1", "S2"], "role": "keys"},
        {"id": "m-cfg", "parts": ["R1", "R2"], "role": "config"},
    ]
    spec = PresentationSpec.from_dict({
        "modules": modules,
        "panelGroups": [{
            "id": "keys",
            "side": "bottom",
            "columns": 2,
            "branches": [
                {"from": "K1", "to": "GND", "part": "S1"},
                {"from": "K2", "to": "GND", "part": "S2"},
            ],
        }],
        "serviceGroups": [{
            "id": "cfg",
            "branches": [
                {"part": "R1", "from": "CFG_A", "to": "PWR"},
                {"part": "R2", "from": "CFG_B", "to": "PWR"},
            ],
        }],
    })
    assert len(spec.panel_groups) == 1 and len(spec.service_groups) == 1
    assert PresentationSpec.from_dict(spec.to_jsonable()) == spec


# ------------------------------------------------------------------- 负例


def test_a_group_needs_at_least_one_branch():
    for branches in ([],):
        with pytest.raises(
            PresentationSpecError, match=r"\$\.serviceGroups\[0\]\.branches names 0"
        ):
            PresentationSpec.from_dict(_service_document(
                serviceGroups=[_group(branches=branches)]
            ))


@pytest.mark.parametrize("spot,group", [
    ("id", _group(id="")),
    ("id", _group(id=None)),
    ("branches", {key: value for key, value in _group().items()
                  if key != "branches"}),
    ("branches", _group(branches=None)),
    ("branches[0].part", _group(branches=[
        {"from": "CFG_A", "to": "PWR"}, _branch("R2", "CFG_B"),
    ])),
    ("branches[0].from", _group(branches=[
        {"part": "R1", "to": "PWR"}, _branch("R2", "CFG_B"),
    ])),
    ("branches[0].from", _group(branches=[
        _branch("R1", "   "), _branch("R2", "CFG_B"),
    ])),
    ("branches[0].to", _group(branches=[
        {"part": "R1", "from": "CFG_A"}, _branch("R2", "CFG_B"),
    ])),
    ("branches[1].part", _group(branches=[
        _branch("R1", "CFG_A"), _branch("", "CFG_B"),
    ])),
])
def test_missing_and_empty_fields_are_refused_with_their_path(spot, group):
    with pytest.raises(PresentationSpecError, match=re.escape(spot)):
        PresentationSpec.from_dict(_service_document(serviceGroups=[group]))


def test_a_branch_needs_two_different_nets():
    with pytest.raises(
        PresentationSpecError,
        match=r"\$\.serviceGroups\[0\]\.branches\[1\]\.to is 'PWR', the same net as \.from",
    ):
        PresentationSpec.from_dict(_service_document(
            serviceGroups=[_group(branches=[
                _branch("R1", "CFG_A"),
                _branch("R2", "PWR", "PWR"),
            ])]
        ))


def test_a_group_id_is_unique():
    duplicate = _group(branches=[_branch("C1", "VCC", "GND")])
    with pytest.raises(
        PresentationSpecError, match=r"\$\.serviceGroups\[1\]\.id is 'config-pullups'"
    ):
        PresentationSpec.from_dict(_service_document(
            serviceGroups=[_group(), duplicate]
        ))


def test_a_part_belongs_to_one_service_branch_only():
    """组内重复与跨组重复同样拒绝：一个支路一个座位。"""
    inside = _group(branches=[_branch("R1", "CFG_A"), _branch("R1", "CFG_B")])
    with pytest.raises(
        PresentationSpecError,
        match=r"\$\.serviceGroups\[0\]\.branches\[1\]\.part is 'R1'",
    ):
        PresentationSpec.from_dict(_service_document(serviceGroups=[inside]))
    first = _group(id="one", branches=[_branch("R1", "CFG_A")])
    second = _group(id="two", branches=[_branch("R2", "CFG_B")])
    third = _group(id="three", branches=[_branch("C1", "VCC", "GND"),
                                         _branch("R2", "CFG_C")])
    with pytest.raises(
        PresentationSpecError,
        match=r"\$\.serviceGroups\[2\]\.branches\[1\]\.part is 'R2'",
    ):
        PresentationSpec.from_dict(_service_document(
            serviceGroups=[first, second, third]
        ))


@pytest.mark.parametrize("part,message", [
    ("D9", r"branches\[1\]\.part is 'D9', which the modules do not declare"),
])
def test_an_undeclared_part_is_refused(part, message):
    with pytest.raises(PresentationSpecError, match=message):
        PresentationSpec.from_dict(_service_document(
            serviceGroups=[_group(branches=[_branch("R1", "CFG_A"),
                                            _branch(part, "CFG_B")])]
        ))


def test_a_group_must_not_span_two_modules():
    """联合座位是一个宿主的邻域：跨模块器件按名拒绝，不静默拆分。"""
    with pytest.raises(
        PresentationSpecError,
        match=r"\$\.serviceGroups\[0\]\.branches\[1\]\.part is 'C1', which shares "
              r"no module",
    ):
        PresentationSpec.from_dict(_service_document(
            serviceGroups=[_group(branches=[_branch("R1", "CFG_A"),
                                            _branch("C1", "VCC", "GND")])]
        ))


def test_a_series_arm_part_cannot_join_a_service_group():
    series = [{
        "id": "status-led",
        "from": "GPIO_STAT",
        "to": "GND",
        "parts": ["R1", "R2"],
        "middleNet": "LED_A",
    }]
    with pytest.raises(
        PresentationSpecError,
        match=r"part is 'R1', which seriesBranches arm 'status-led'",
    ):
        PresentationSpec.from_dict(_service_document(
            seriesBranches=series,
            serviceGroups=[_group(branches=[_branch("R1", "CFG_A")])],
        ))


def test_a_panel_branch_part_cannot_join_a_service_group():
    """一个器件只能落在 panelGroups / serviceGroups 之一，不静默择一。"""
    modules = [{"id": "m", "parts": ["R1", "R2", "R3"], "role": "mixed"}]
    with pytest.raises(
        PresentationSpecError,
        match=r"part is 'R1', which panelGroups group 'panel' already names",
    ):
        PresentationSpec.from_dict({
            "modules": modules,
            "panelGroups": [{
                "id": "panel",
                "side": "bottom",
                "columns": 1,
                "branches": [
                    {"from": "K1", "to": "GND", "part": "R1"},
                    {"from": "K2", "to": "GND", "part": "R2"},
                ],
            }],
            "serviceGroups": [{"id": "cfg", "branches": [
                {"part": "R1", "from": "CFG_A", "to": "PWR"},
            ]}],
        })


def test_the_group_and_branch_objects_are_closed():
    """两键/三键之外一律拒绝：side、列数、间距、节距、frame 都不从这里进来。"""
    for group in (
        _group(side="right"),
        _group(columns=2),
        _group(gap=40),
        _group(pitch=50),
        _group(frame=[0, 0, 100, 100]),
    ):
        with pytest.raises(
            PresentationSpecError, match=r"\$\.serviceGroups\[0\]: unknown key\(s\)"
        ):
            PresentationSpec.from_dict(_service_document(serviceGroups=[group]))
    extra = _group(branches=[
        {**_branch("R1", "CFG_A"), "pin": 1},
        _branch("R2", "CFG_B"),
    ])
    with pytest.raises(
        PresentationSpecError,
        match=r"\$\.serviceGroups\[0\]\.branches\[0\]: unknown key\(s\)",
    ):
        PresentationSpec.from_dict(_service_document(serviceGroups=[extra]))


@pytest.mark.parametrize("key,value", [
    ("x", 0),
    ("points", [[0, 0], [1, 1]]),
])
def test_a_coordinate_on_a_group_is_refused_as_a_coordinate(key, value):
    with pytest.raises(
        PresentationSpecError,
        match=rf"\$\.serviceGroups\[0\]\.{key} is a coordinate-shaped key",
    ):
        PresentationSpec.from_dict(_service_document(
            serviceGroups=[_group(**{key: value})]
        ))


@pytest.mark.parametrize("key,value", [
    ("x", 0),
    ("at", {"x": 0, "y": 0}),
    ("wirePoints", [[0, 0], [1, 1]]),
])
def test_a_coordinate_on_a_branch_is_refused_as_a_coordinate(key, value):
    broken = _group(branches=[
        {**_branch("R1", "CFG_A"), key: value},
        _branch("R2", "CFG_B"),
    ])
    with pytest.raises(
        PresentationSpecError,
        match=rf"\$\.serviceGroups\[0\]\.branches\[0\]\.{key} is a coordinate-shaped key",
    ):
        PresentationSpec.from_dict(_service_document(serviceGroups=[broken]))


def test_a_group_and_its_branches_must_be_the_declared_shapes():
    with pytest.raises(
        PresentationSpecError, match=r"\$\.serviceGroups\[0\] must be a JSON object"
    ):
        PresentationSpec.from_dict(_service_document(serviceGroups=["cfg"]))
    with pytest.raises(
        PresentationSpecError,
        match=r"\$\.serviceGroups\[0\]\.branches must be a list",
    ):
        PresentationSpec.from_dict(_service_document(
            serviceGroups=[_group(branches={"part": "R1"})]
        ))


def test_the_serialised_group_carries_no_geometry():
    """写回的组只有两键，支路只有三键：没有 side/columns/gap/pitch/frame。"""
    spec = PresentationSpec.from_dict(_service_document(
        serviceGroups=[_group()]
    ))
    written = spec.to_jsonable()["serviceGroups"]
    assert written[0].keys() == {"id", "branches"}
    assert written[0]["branches"][0].keys() == {"part", "from", "to"}
    canonical = _canonical(spec)
    for forbidden in ("side", "columns", "gap", "pitch", "frame"):
        assert f'"{forbidden}"' not in canonical


# ------------------------------------------------- 旧位置构造兼容（字段追加在最后）


def test_the_new_field_is_appended_after_every_old_field():
    """新字段必须是最后一个：旧位置参数一位不挪。

    548M 追加了 `rail_cluster_radius`（轨旗聚簇的半径），548P104 又追加了
    `flag_share_groups`（同网本地旗的显式分组），因此尾部三位的期望值顺延一格：
    断言本身**没有放宽**——它仍然要求"既有字段的相对顺序不变、新字段排在最后"，
    只是最后那个名字随最近一次追加而更新。真正护住旧位置参数的是紧随其后的那条
    位置构造用例，它用 23 个旧位置参数构造并要求每个都落回原字段。
    """
    names = [item.name for item in dataclasses.fields(PresentationSpec)]
    assert names[-1] == "flag_share_groups"
    assert names[-2] == "rail_cluster_radius"
    assert names[-3] == "service_groups"
    assert names[-4] == "spec_version"


def test_a_positional_spec_keeps_every_old_position():
    """按旧位置参数构造仍然落到原字段，新字段只留默认空。"""
    spec = PresentationSpec(
        [], None, [], [], 0, None, 12.0, 7.5, None, [], [], {},
        "voltage-divider", [], [], [], [],
        LabelPolicy(), dict(DEFAULT_SIDE_PREFERENCES), [], {}, "native-attr", 1,
    )
    assert spec.modules == []
    assert spec.islands is None
    assert spec.flag_lead_limit == 12.0
    assert spec.gnd_cluster_radius == 7.5
    assert spec.grammar_ref == "voltage-divider"
    assert spec.text_placement == "native-attr"
    assert spec.spec_version == 1
    assert spec.service_groups == []
    written = spec.to_jsonable()
    assert "serviceGroups" not in written
    assert PresentationSpec.from_dict(written) == spec
