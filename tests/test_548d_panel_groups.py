"""548D3X3A：`panelGroups` 的数据合同 —— 重复二端支路的阅读分组。

这一批只做**声明语法**：一组同类二端支路（按键阵列、状态灯排）用
`{"id", "side", "columns", "branches"}` 说出「读在哪一侧宿主、读成几列、支路按
什么次序读」，几何（座位、节距、文字、旗标）由解释器按真实度量推导，本批不实现、
也不声称改变任何候选。钉住三件事：

1. **不写 = 不读不写出**：旧文档规范 JSON 无这个键，摘要仍是 `50b112…`；
   `[]` 与不写等价。
2. **显式声明可往返**：组/支路的封闭键、支路声明顺序逐字保留，`from_dict(to_jsonable())
   == spec`、重复解析幂等、`dump`/`load` 一致。
3. **组是封闭四键、支路封闭三键**：少于两支路、非正整数或超过支路数的 `columns`、
   非四向 `side`、重复 id、重复/未声明器件、与 `seriesBranches` 冲突、空字段、
   额外键、坐标键，一律 `PresentationSpecError` 并点名路径。
   `userLocks` 仍是唯一坐标入口。

不写这一批没做的事：电路拓扑与两脚校验、宿主唯一性、页面切片、任何几何落图；
"parser 接受"不等于电气合同已验证。
"""

from __future__ import annotations

import json
import re

import pytest

from boardwise.core.presentationspec import (
    PANEL_BRANCH_KEYS,
    PANEL_GROUP_KEYS,
    PANEL_MIN_BRANCHES,
    PanelBranch,
    PanelGroup,
    PresentationSpec,
    PresentationSpecError,
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

_PANEL_MODULES = [
    {"id": "m-keys", "parts": ["S1", "S2", "S3", "S4"], "role": "keys"},
    {"id": "m-row", "parts": ["D1", "D2"], "role": "status row"},
]


def _presentation(**overrides):
    payload = dict(_DOCUMENT)
    payload.update(overrides)
    return payload


def _panel_document(**overrides):
    payload = {"modules": [dict(module) for module in _PANEL_MODULES]}
    payload.update(overrides)
    return payload


def _branch(part, from_net, to_net="GND"):
    return {"from": from_net, "to": to_net, "part": part}


def _branches(*parts):
    return [
        _branch(part, from_net=f"KEY{index + 1}")
        for index, part in enumerate(parts)
    ]


def _group(**overrides):
    entry = {
        "id": "keys",
        "side": "bottom",
        "columns": 2,
        "branches": _branches("S1", "S2", "S3", "S4"),
    }
    entry.update(overrides)
    return entry


def _canonical(spec):
    return json.dumps(
        spec.to_jsonable(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


# --------------------------------------------------------- 默认关闭（缺省等价）


def test_a_spec_that_states_no_panel_keeps_its_digest():
    """没写这个键的文档，规范 JSON 里不许出现它，摘要一位都不许动。"""
    spec = PresentationSpec.from_dict(_presentation())
    assert spec.panel_groups == []
    assert "panelGroups" not in _canonical(spec)
    assert spec.sha256() == _BASE_DIGEST, (
        f"未改动的 053 文档必须与本键出现之前逐字节同摘要（得到 {spec.sha256()}）"
    )


def test_an_empty_list_is_the_same_statement_as_no_key():
    """`[]` 与不写等价：同样不写出、同样摘要、同样不带任何面板。"""
    empty = PresentationSpec.from_dict(_panel_document(panelGroups=[]))
    plain = PresentationSpec.from_dict(_panel_document())
    assert empty.panel_groups == []
    assert "panelGroups" not in _canonical(empty)
    assert _canonical(empty) == _canonical(plain)
    assert empty.sha256() == plain.sha256()


# --------------------------------------------------------------- 正例 round-trip


def test_a_panel_round_trips_through_json_and_a_file(tmp_path):
    """合法组：四键/三键形状逐字写回，支路顺序即声明顺序。"""
    spec = PresentationSpec.from_dict(_panel_document(panelGroups=[_group()]))
    group = spec.panel_groups[0]
    assert group == PanelGroup(
        id="keys",
        side="bottom",
        columns=2,
        branches=(
            PanelBranch(from_net="KEY1", to_net="GND", part="S1"),
            PanelBranch(from_net="KEY2", to_net="GND", part="S2"),
            PanelBranch(from_net="KEY3", to_net="GND", part="S3"),
            PanelBranch(from_net="KEY4", to_net="GND", part="S4"),
        ),
    )
    written = spec.to_jsonable()["panelGroups"]
    assert written == [{
        "id": "keys",
        "side": "bottom",
        "columns": 2,
        "branches": [
            {"from": "KEY1", "to": "GND", "part": "S1"},
            {"from": "KEY2", "to": "GND", "part": "S2"},
            {"from": "KEY3", "to": "GND", "part": "S3"},
            {"from": "KEY4", "to": "GND", "part": "S4"},
        ],
    }]
    assert set(written[0]) == set(PANEL_GROUP_KEYS)
    assert set(written[0]["branches"][0]) == set(PANEL_BRANCH_KEYS)
    assert PresentationSpec.from_dict(spec.to_jsonable()) == spec
    assert PresentationSpec.from_dict(
        PresentationSpec.from_dict(spec.to_jsonable()).to_jsonable()
    ).to_jsonable() == spec.to_jsonable()
    path = tmp_path / "panel.presentation.json"
    spec.dump(path)
    assert PresentationSpec.load(path) == spec


def test_the_declared_side_and_columns_travel_verbatim():
    """四个阅读侧都合法；columns 等于支路数是上界内的合法值。"""
    for side in ("bottom", "top", "left", "right"):
        spec = PresentationSpec.from_dict(_panel_document(
            panelGroups=[_group(side=side, columns=4)]
        ))
        assert spec.panel_groups[0].side == side
        assert spec.panel_groups[0].columns == 4
        assert PresentationSpec.from_dict(spec.to_jsonable()) == spec


def test_the_contract_vocabulary_is_what_it_says():
    assert PANEL_GROUP_KEYS == ("id", "side", "columns", "branches")
    assert PANEL_BRANCH_KEYS == ("from", "to", "part")
    assert PANEL_MIN_BRANCHES == 2


# ------------------------------------------------------------------- 负例


def test_a_panel_needs_at_least_two_branches():
    for branches in ([], _branches("S1")):
        with pytest.raises(PresentationSpecError, match=r"\$\.panelGroups\[0\]\.branches"):
            PresentationSpec.from_dict(_panel_document(
                panelGroups=[_group(branches=branches)]
            ))


@pytest.mark.parametrize("columns,message", [
    (0, "is 0; a panel has at least one reading column"),
    (-1, "is -1; a panel has at least one reading column"),
    (True, "must be a positive integer"),
    (2.0, "must be a positive integer"),
    ("2", "must be a positive integer"),
    ([2], "must be a positive integer"),
    (5, "is 5, and the group names 4 branch"),
    (None, "is required and missing"),
])
def test_columns_must_be_a_positive_integer_within_the_branch_count(
    columns, message
):
    with pytest.raises(
        PresentationSpecError,
        match=rf"\$\.panelGroups\[0\]\.columns {message}",
    ):
        PresentationSpec.from_dict(_panel_document(
            panelGroups=[_group(columns=columns)]
        ))


@pytest.mark.parametrize("side", ["middle", "Bottom", "", "   ", None])
def test_the_side_is_one_of_the_four_edges(side):
    with pytest.raises(PresentationSpecError, match=r"\$\.panelGroups\[0\]\.side"):
        PresentationSpec.from_dict(_panel_document(
            panelGroups=[_group(side=side)]
        ))


@pytest.mark.parametrize("spot,group", [
    ("id", _group(id="")),
    ("id", _group(id=None)),
    ("side", _group(side=None)),
    ("columns", {key: value for key, value in _group().items() if key != "columns"}),
    ("branches", {key: value for key, value in _group().items() if key != "branches"}),
    ("branches[0].from", _group(branches=[_branch("S1", "  "), _branch("S2", "KEY2")])),
    ("branches[0].to", _group(branches=[{"from": "KEY1", "part": "S1"},
                                        _branch("S2", "KEY2")])),
    ("branches[1].part", _group(branches=[_branch("S1", "KEY1"),
                                          _branch("", "KEY2")])),
])
def test_missing_and_empty_fields_are_refused_with_their_path(spot, group):
    with pytest.raises(PresentationSpecError, match=re.escape(spot)):
        PresentationSpec.from_dict(_panel_document(panelGroups=[group]))


def test_the_group_and_branch_objects_are_closed():
    """四键/三键之外一律拒绝：行数、间距、origin 都不从这里进来。"""
    for group in (
        _group(rows=2),
        _group(gap=40),
        _group(origin=[0, 0]),
    ):
        with pytest.raises(
            PresentationSpecError, match=r"\$\.panelGroups\[0\]: unknown key\(s\)"
        ):
            PresentationSpec.from_dict(_panel_document(panelGroups=[group]))
    extra = _group(branches=[{"from": "KEY1", "to": "GND", "part": "S1",
                              "column": 0},
                             _branch("S2", "KEY2")])
    with pytest.raises(
        PresentationSpecError,
        match=r"\$\.panelGroups\[0\]\.branches\[0\]: unknown key\(s\)",
    ):
        PresentationSpec.from_dict(_panel_document(panelGroups=[extra]))


@pytest.mark.parametrize("key,value", [
    ("x", 0),
    ("points", [[0, 0], [1, 1]]),
])
def test_a_coordinate_on_a_group_is_refused_as_a_coordinate(key, value):
    with pytest.raises(
        PresentationSpecError,
        match=rf"\$\.panelGroups\[0\]\.{key} is a coordinate-shaped key",
    ):
        PresentationSpec.from_dict(_panel_document(
            panelGroups=[_group(**{key: value})]
        ))


@pytest.mark.parametrize("key,value", [
    ("x", 0),
    ("at", {"x": 0, "y": 0}),
    ("wirePoints", [[0, 0], [1, 1]]),
])
def test_a_coordinate_on_a_branch_is_refused_as_a_coordinate(key, value):
    broken = _group(branches=[
        {**_branch("S1", "KEY1"), key: value},
        _branch("S2", "KEY2"),
    ])
    with pytest.raises(
        PresentationSpecError,
        match=rf"\$\.panelGroups\[0\]\.branches\[0\]\.{key} is a coordinate-shaped key",
    ):
        PresentationSpec.from_dict(_panel_document(panelGroups=[broken]))


def test_a_group_and_its_branches_must_be_the_declared_shapes():
    with pytest.raises(
        PresentationSpecError, match=r"\$\.panelGroups\[0\] must be a JSON object"
    ):
        PresentationSpec.from_dict(_panel_document(panelGroups=["keys"]))
    with pytest.raises(
        PresentationSpecError,
        match=r"\$\.panelGroups\[0\]\.branches must be a list",
    ):
        PresentationSpec.from_dict(_panel_document(
            panelGroups=[_group(branches={"from": "KEY1"})]
        ))


def test_a_group_id_is_unique():
    duplicate = _group(branches=_branches("D1"))
    duplicate["id"] = "keys"
    with pytest.raises(
        PresentationSpecError, match=r"\$\.panelGroups\[1\]\.id is 'keys'"
    ):
        PresentationSpec.from_dict(_panel_document(
            panelGroups=[_group(), duplicate]
        ))


def test_a_part_belongs_to_one_panel_branch_only():
    """组内重复与跨组重复同样拒绝：一个支路一个座位。"""
    inside = _group(branches=_branches("S1", "S1"))
    with pytest.raises(
        PresentationSpecError, match=r"branches\[1\]\.part is 'S1'"
    ):
        PresentationSpec.from_dict(_panel_document(panelGroups=[inside]))
    across = _group(id="keys", branches=_branches("S1", "S2"))
    second = _group(id="row", branches=_branches("D1", "D2"))
    third = _group(id="more", branches=_branches("D1", "S3"))
    with pytest.raises(
        PresentationSpecError, match=r"\$\.panelGroups\[2\]\.branches\[0\]\.part is 'D1'"
    ):
        PresentationSpec.from_dict(_panel_document(
            panelGroups=[across, second, third]
        ))


def test_an_undeclared_part_is_refused():
    with pytest.raises(
        PresentationSpecError, match=r"branches\[1\]\.part is 'D9'"
    ):
        PresentationSpec.from_dict(_panel_document(
            panelGroups=[_group(branches=_branches("S1", "D9"))]
        ))


def test_a_series_arm_part_cannot_join_a_panel():
    """一个器件不能同时属于 panel 与 seriesBranches。"""
    series = [{
        "id": "status-led",
        "from": "GPIO_STAT",
        "to": "GND",
        "parts": ["D1", "D2"],
        "middleNet": "LED_A",
    }]
    with pytest.raises(
        PresentationSpecError, match=r"part is 'D1', which seriesBranches arm 'status-led'"
    ):
        PresentationSpec.from_dict(_panel_document(
            seriesBranches=series,
            panelGroups=[_group(branches=_branches("S1", "D1"))],
        ))
    # 不冲突时两者可并存：series 的五键合同不变，面板也不复制它的电气声明。
    both = PresentationSpec.from_dict(_panel_document(
        seriesBranches=series,
        panelGroups=[_group(branches=_branches("S1", "S2", "S3", "S4"))],
    ))
    assert len(both.series_branches) == 1 and len(both.panel_groups) == 1
    assert PresentationSpec.from_dict(both.to_jsonable()) == both
