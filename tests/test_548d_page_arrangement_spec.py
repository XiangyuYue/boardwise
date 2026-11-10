"""548D：`pageArrangement` 的数据合同，以及「没写」到底意味着什么。

这一批只做**声明语法**：页面用 `{"strategy": "compact"}` 说「按模块净距把已有的
frame 排紧」，不接收任何页框、间隙、禁入区、band、坐标或第二个模块顺序。所以这里
钉住的是三件事：

1. **不写 = 不读不写出**：旧文档的规范 JSON 里没有这个键，摘要仍是改动前那棵树算
   出来的 `50b112…`。**只有键缺失才是 `None`**：显式 `null` 不是"未声明"，而是非
   对象，同样拒绝（§30B，并点名路径）。
2. **显式声明可往返**：`{"strategy": "compact"}` 读成 `PageArrangement`，写回同一
   个对象，`from_dict(to_jsonable()) == spec` 且重复解析幂等；`moduleOrder` /
   `moduleColumns` / `flow` 的含义不被它改写。
3. **对象是封闭的一键 schema**：非对象（含 `null`）、未知 strategy、额外键、坐标
   形状的键、空串/非字符串/缺 strategy，一律 `PresentationSpecError` 并点名路径。
   `userLocks` 仍是唯一坐标入口。

不写这一批没做的事：不接 pagecompiler、不解析 bands/页框/gap/keep-out、不宣称整页
排得下。默认关闭的证据是"什么都不声明时字节不变"，不是"compact 排不出来"。
"""

from __future__ import annotations

import json

import pytest

from boardwise.core.presentationspec import (
    PAGE_ARRANGEMENT_COMPACT,
    PAGE_ARRANGEMENT_KEYS,
    PAGE_ARRANGEMENT_STRATEGIES,
    PageArrangement,
    PresentationSpec,
    PresentationSpecError,
)

#: `_presentation()` 的摘要，由**改动前**那棵树算出来（与 548B1 钉的是同一个数：
#: 那一版之后没有任何默认序列化被改动）。钉死数字而不是跟自己比：整个"条件序列化"
#: 的意义就是这个文档的字节不许动。
_BASE_DIGEST = "50b112989558bb4b3dff6765d3d3ae67cff6b21228a8d2a18cded25abde3f5ea"

#: 一份 053 时期的普通文档，形状照 053A 的 `_presentation()`（照抄而不是 import：
#: 那一个 helper 是 053 的合同，本批不该跟着它一起变）。
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


def _presentation(**overrides):
    payload = dict(_DOCUMENT)
    payload.update(overrides)
    return payload


def _compact(**overrides):
    entry = {"strategy": PAGE_ARRANGEMENT_COMPACT}
    entry.update(overrides)
    return entry


def _canonical(spec):
    return json.dumps(
        spec.to_jsonable(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


# ------------------------------------------------------- 默认关闭（缺省等价）


def test_a_spec_that_states_no_page_arrangement_keeps_its_digest():
    """没写这个键的文档，规范 JSON 里不许出现它，摘要一位都不许动。"""
    spec = PresentationSpec.from_dict(_presentation())
    assert spec.page_arrangement is None
    assert "pageArrangement" not in _canonical(spec), (
        "没声明时写出这个键会移动每份既有 spec 的摘要，连带移动所有由它编译出来的"
        " LayoutPlan"
    )
    assert spec.sha256() == _BASE_DIGEST, (
        f"未改动的 053 文档必须与本键出现之前逐字节同摘要（得到 {spec.sha256()}）"
    )


def test_only_a_missing_key_means_none_and_an_explicit_null_is_refused():
    """只有键缺失是「未声明」；显式 `null` 是非对象，按 §30B 拒绝并点名路径。"""
    missing = _presentation()
    assert "pageArrangement" not in missing
    plain = PresentationSpec.from_dict(missing)
    assert plain.page_arrangement is None
    assert "pageArrangement" not in _canonical(plain)
    assert plain.sha256() == _BASE_DIGEST

    with pytest.raises(
        PresentationSpecError, match=r"\$\.pageArrangement is null"
    ):
        PresentationSpec.from_dict(_presentation(pageArrangement=None))


# --------------------------------------------------------------- 正例 round-trip


def test_a_compact_strategy_round_trips_and_promises_no_geometry(tmp_path):
    """显式声明只增加一个 strategy 键，别处逐字节不动。"""
    arranged = PresentationSpec.from_dict(
        _presentation(pageArrangement=_compact())
    )
    assert arranged.page_arrangement == PageArrangement(strategy="compact")
    written = arranged.to_jsonable()
    assert written["pageArrangement"] == {"strategy": "compact"}
    assert set(written["pageArrangement"]) == set(PAGE_ARRANGEMENT_KEYS)
    # 除了这个键，整份文档与默认那份逐键相同：策略不改写 moduleOrder/columns/flow。
    assert {
        key: value for key, value in written.items() if key != "pageArrangement"
    } == PresentationSpec.from_dict(_presentation()).to_jsonable()
    assert arranged.sha256() != _BASE_DIGEST, "声明了策略的文档不应与默认文档同摘要"
    assert PresentationSpec.from_dict(written) == arranged
    assert PresentationSpec.from_dict(
        PresentationSpec.from_dict(written).to_jsonable()
    ).to_jsonable() == written
    # 文件往返：`dump` / `load` 与内存形式一致。
    path = tmp_path / "arranged.presentation.json"
    arranged.dump(path)
    assert PresentationSpec.load(path) == arranged


def test_the_other_layout_statements_keep_their_meaning_beside_the_strategy():
    """`flow` / `moduleOrder` / `moduleColumns` 的读法与含义不变。"""
    payload = _presentation(
        modules=[
            {"id": "m-divider", "parts": ["R1", "R2"], "role": "voltage divider"},
            {"id": "m-port", "parts": ["J1"], "role": "inlet"},
        ],
        flow=[{"from": "m-port", "to": "m-divider", "mainPath": True}],
        moduleOrder=["m-port", "m-divider"],
        moduleColumns=2,
        pageArrangement=_compact(),
    )
    spec = PresentationSpec.from_dict(payload)
    assert spec.module_order == ["m-port", "m-divider"]
    assert spec.module_columns == 2
    assert [(edge.from_module, edge.to_module, edge.main_path) for edge in spec.flow] \
        == [("m-port", "m-divider", True)]
    assert spec.page_arrangement == PageArrangement(strategy="compact")
    assert PresentationSpec.from_dict(spec.to_jsonable()) == spec


def test_the_vocabulary_is_exactly_one_strategy():
    """本批只认 `compact`：词表本身就是这个承诺。"""
    assert PAGE_ARRANGEMENT_STRATEGIES == ("compact",)
    assert PAGE_ARRANGEMENT_COMPACT == "compact"
    assert PAGE_ARRANGEMENT_KEYS == ("strategy",)


# ------------------------------------------------------------------- 负例


@pytest.mark.parametrize("value", ["compact", [], 1, 0.5, True, ["compact"]])
def test_page_arrangement_must_be_a_json_object(value):
    with pytest.raises(
        PresentationSpecError, match=r"\$\.pageArrangement must be a JSON object"
    ):
        PresentationSpec.from_dict(_presentation(pageArrangement=value))


@pytest.mark.parametrize("strategy", ["widths", "grid", "Compact", "compact2", "pack"])
def test_an_unknown_strategy_is_refused_and_named(strategy):
    with pytest.raises(
        PresentationSpecError, match=r"\$\.pageArrangement\.strategy is "
    ):
        PresentationSpec.from_dict(
            _presentation(pageArrangement=_compact(strategy=strategy))
        )


@pytest.mark.parametrize("extra", [
    {"gap": 40},
    {"bands": [{"id": "left"}]},
    {"pageBox": {"width": 1170, "height": 825}},
    {"keepouts": [[0, 0, 10, 10]]},
    {"moduleOrder": ["m-divider"]},
    {"compact": True},
])
def test_an_extra_key_is_refused_even_with_a_known_strategy(extra):
    """封闭 schema：页框/间隙/band/第二个顺序都不许从这里进来。"""
    with pytest.raises(
        PresentationSpecError, match=r"\$\.pageArrangement: unknown key\(s\)"
    ):
        PresentationSpec.from_dict(
            _presentation(pageArrangement=_compact(**extra))
        )


@pytest.mark.parametrize("key,value", [
    ("x", 0),
    ("y", 10.5),
    ("points", [[0, 0], [1, 1]]),
    ("wirePoints", [[0, 0], [1, 1]]),
    ("at", {"x": 0, "y": 0}),
])
def test_a_coordinate_inside_page_arrangement_is_refused_as_a_coordinate(
    key, value
):
    """坐标照旧只许出现在 `userLocks`，这里连字典都不许带 x/points。"""
    payload = _presentation(pageArrangement=_compact(**{key: value}))
    with pytest.raises(
        PresentationSpecError,
        match=rf"\$\.pageArrangement\.{key} is a coordinate-shaped key",
    ):
        PresentationSpec.from_dict(payload)


@pytest.mark.parametrize("entry,message", [
    ({}, "is required and missing"),
    ({"strategy": None}, "is required and missing"),
    ({"strategy": ""}, "is empty"),
    ({"strategy": "   "}, "is empty"),
    ({"strategy": 1}, "must be a string"),
    ({"strategy": ["compact"]}, "must be a string"),
])
def test_the_strategy_must_be_a_non_empty_string(entry, message):
    with pytest.raises(
        PresentationSpecError,
        match=rf"\$\.pageArrangement\.strategy {message}",
    ):
        PresentationSpec.from_dict(_presentation(pageArrangement=entry))
