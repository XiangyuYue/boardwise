"""548B1：`seriesBranches` 的数据合同，以及「没写」到底意味着什么。

这一批只做**文档语法**，不做任何电气判断：一条支路点名两个件、两端和两件之间的
节点，至于电路里这两件是不是真的那样连着，只有同时持有 `CircuitSpec` 的消费者才能
查（本批不碰）。所以这里钉住的是三件事：

1. **不写 = 不读不写出**：旧文档的规范 JSON 里没有这个键，摘要仍是从改动前那棵树
   算出来的 `50b112…`；写 `[]` 与不写完全等价（同样不写出，同样摘要）。
2. **顺序是文档唯一能说的话**：网表只给无向分区，`parts` 的列表次序就是阅读方向，
   读回来必须逐字、逐位一致，`from_dict(to_jsonable()) == spec` 且重复解析幂等。
3. **条目是封闭的五个键**：未知键、缺字段、类型不对、空 id、`parts` 不是恰好两个
   不同件、重复 id、重复完整声明、任何数字或坐标形状的键，一律
   `PresentationSpecError` 并点名路径。`userLocks` 仍是唯一坐标入口。

不写这一批没做的事：跨文档 V1–V8、provenance 派生、编译/页面/真机、同形状两件的
自动识别。默认关闭的证据是"什么都不声明时字节不变"，不是"自动识别不出来"。
"""

from __future__ import annotations

import json

import pytest

from boardwise.core.presentationspec import (
    SERIES_BRANCH_KEYS,
    PresentationSpec,
    PresentationSpecError,
    SeriesBranch,
)

#: `_presentation()` 的摘要，由**改动前**那棵树算出来（同一个文档在
#: 548B1 之前的 `presentationspec.py` 上跑一次）。钉死数字而不是跟自己比：
#: 整个"条件序列化"的意义就是这个文档的字节不许动。
_SERIES_BASE_DIGEST = (
    "50b112989558bb4b3dff6765d3d3ae67cff6b21228a8d2a18cded25abde3f5ea"
)

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


def _arm(**overrides):
    entry = {
        "id": "status-led",
        "from": "GPIO_STAT",
        "to": "GND",
        "parts": ["R2", "LED1"],
        "middleNet": "LED_A",
    }
    entry.update(overrides)
    return entry


def _canonical(spec):
    return json.dumps(
        spec.to_jsonable(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


# ------------------------------------------------------- 默认关闭（C1、C2、C5）


def test_a_spec_that_states_no_series_branch_keeps_its_digest():
    """没写这个键的文档，规范 JSON 里不许出现它，摘要一位都不许动。"""
    spec = PresentationSpec.from_dict(_presentation())
    assert "seriesBranches" not in _canonical(spec), (
        "没声明时写出这个键（哪怕是空数组）会移动每份既有 spec 的摘要，连带移动"
        "所有由它编译出来的 LayoutPlan"
    )
    assert spec.series_branches == []
    assert spec.sha256() == _SERIES_BASE_DIGEST, (
        f"未改动的 053 文档必须与本键出现之前逐字节同摘要（得到 {spec.sha256()}）"
    )


def test_an_empty_list_is_the_same_statement_as_no_key_at_all():
    """`[]` 与不写等价：同样不写出、同样摘要、同样不带任何支路。"""
    empty = PresentationSpec.from_dict(_presentation(seriesBranches=[]))
    assert empty.series_branches == []
    assert "seriesBranches" not in _canonical(empty)
    assert empty.sha256() == _SERIES_BASE_DIGEST
    assert empty.to_jsonable() == PresentationSpec.from_dict(
        _presentation()
    ).to_jsonable()


def test_a_same_shaped_pair_is_not_recognised_without_being_declared():
    """默认关闭：电路里有两件串联的形状，文档不声明就一条支路都没有。"""
    undeclared = PresentationSpec.from_dict(_presentation(
        modules=[{"id": "m-led", "parts": ["R2", "LED1"], "role": "status led"}],
        mainPaths=[],
        directWiringObligations=[],
        seriesBranches=[],
    ))
    assert undeclared.series_branches == []
    assert "seriesBranches" not in _canonical(undeclared)


# --------------------------------------------------------------- 正例 round-trip


def test_the_series_arm_round_trips_field_by_field_in_reading_order():
    stated = _arm()
    spec = PresentationSpec.from_dict(_presentation(seriesBranches=[stated]))
    assert spec.series_branches == [
        SeriesBranch(
            id="status-led",
            from_net="GPIO_STAT",
            to_net="GND",
            parts=("R2", "LED1"),
            middle_net="LED_A",
        )
    ]
    branch = spec.series_branches[0]
    assert (branch.id, branch.from_net, branch.to_net, branch.middle_net) == (
        "status-led", "GPIO_STAT", "GND", "LED_A",
    )
    # 顺序就是文档写的顺序：贴着宿主端的件在前，贴近终端的那件在后。
    assert branch.parts == ("R2", "LED1")
    # 序列化回来的五键逐字一致，键序就是合同的读法。
    written = spec.to_jsonable()["seriesBranches"]
    assert written == [stated]
    assert list(written[0]) == list(SERIES_BRANCH_KEYS)
    assert spec.sha256() != _SERIES_BASE_DIGEST, (
        "声明了一条支路的文档必须换摘要——否则消费者根本看不出它说了什么"
    )


def test_parsing_the_written_form_again_is_idempotent():
    spec = PresentationSpec.from_dict(
        _presentation(seriesBranches=[_arm(), _arm(
            id="power-led", **{"from": "3V3", "to": "GND",
                               "parts": ["R3", "LED2"], "middleNet": "LED_B"},
        )])
    )
    once = PresentationSpec.from_dict(spec.to_jsonable())
    twice = PresentationSpec.from_dict(once.to_jsonable())
    assert once == spec
    assert twice == spec
    assert once.to_jsonable() == spec.to_jsonable()
    # 文档顺序保持，不被排序或合并。
    assert [item.id for item in twice.series_branches] == ["status-led", "power-led"]


def test_an_entry_carries_five_strings_and_nothing_numeric():
    spec = PresentationSpec.from_dict(_presentation(seriesBranches=[_arm()]))
    entry = spec.to_jsonable()["seriesBranches"][0]
    assert set(entry) == set(SERIES_BRANCH_KEYS)
    for key, value in entry.items():
        if key == "parts":
            assert isinstance(value, list) and len(value) == 2
            assert all(isinstance(item, str) for item in value)
        else:
            assert isinstance(value, str), f"{key} must be an id, got {value!r}"
    assert not any(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in entry.values()
    ), "条目里没有数字：第几由 parts 的列表次序说，间距与坐标不进合同"


def test_user_locks_stay_the_only_coordinate_entry():
    """同样的 x/y：在锁里合法，在支路里拒绝。"""
    lock = PresentationSpec.from_dict(_presentation())
    assert lock.user_locks[0].x == 320.0
    with pytest.raises(PresentationSpecError, match="coordinate-shaped key"):
        PresentationSpec.from_dict(_presentation(
            seriesBranches=[_arm(x=320.0, y=200.0)]
        ))


# ------------------------------------------------------------------- 负例逐项


def _without(key):
    entry = _arm()
    del entry[key]
    return [entry]


@pytest.mark.parametrize("entries, match", [
    # 封闭键集：第五个键之外的一切都拒，path 必须点名。
    ([_arm(colour="red")], r"\$\.seriesBranches\[0\]: unknown key\(s\) colour"),
    ([_arm(note="为什么选这条链")], r"unknown key\(s\) note"),
    ([_arm(provenance="ai_asserted")], r"unknown key\(s\) provenance"),
    ([_arm(module="m-led")], r"unknown key\(s\) module"),
    ([_arm(order=1)], r"unknown key\(s\) order"),
    ([_arm(gap=30)], r"unknown key\(s\) gap"),
    ([_arm(position={"x": 120, "y": 45})], r"seriesBranches\[0\]\.position\.x is a coordinate"),
    ([_arm(rotation=90)], r"seriesBranches\[0\]\.rotation is a coordinate"),
    # 必填：缺哪个键就点名哪个键。
    (_without("id"), r"\$\.seriesBranches\[0\]\.id is required and missing"),
    (_without("from"), r"\$\.seriesBranches\[0\]\.from is required and missing"),
    (_without("to"), r"\$\.seriesBranches\[0\]\.to is required and missing"),
    (_without("parts"), r"\.parts must be a list of exactly two"),
    (_without("middleNet"), r"\.middleNet is required and missing"),
    # 类型。
    ([_arm(id=7)], r"\.id must be a string, got 7"),
    ([_arm(**{"from": 5})], r"\.from must be a string, got 5"),
    ([_arm(to=True)], r"\.to must be a string, got True"),
    ([_arm(parts="R2")], r"\.parts must be a list"),
    ([_arm(parts={"first": "R2", "second": "LED1"})], r"\.parts must be a list"),
    ([_arm(middleNet=["LED_A"])], r"\.middleNet must be a string"),
    (["status-led"], r"seriesBranches\[0\] must be a JSON object"),
    # 空字符串（含纯空白）。
    ([_arm(id="")], r"\.id is empty"),
    ([_arm(id="   ")], r"\.id is empty"),
    ([_arm(**{"from": ""})], r"\.from is empty"),
    ([_arm(to=" ")], r"\.to is empty"),
    ([_arm(middleNet="")], r"\.middleNet is empty"),
    ([_arm(parts=["", "LED1"])], r"\.parts\[0\] is empty"),
    ([_arm(parts=["R2", "  "])], r"\.parts\[1\] is empty"),
    # parts 恰好两个不同件。
    ([_arm(parts=[])], r"names 0 part\(s\)"),
    ([_arm(parts=["R2"])], r"names 1 part\(s\)"),
    ([_arm(parts=["R2", "LED1", "C3"])], r"names 3 part\(s\)"),
    ([_arm(parts=["R2", "R2"])], r"names 'R2' twice"),
    # 身份：一条支路一个 id；同一条支路只有一种写法。
    ([_arm(), _arm(**{"from": "3V3"})],
     r"\.seriesBranches\[1\]\.id is 'status-led' and \$\.seriesBranches\[0\] already"),
    ([_arm(), _arm(id="status-led-again")],
     r"\.seriesBranches\[1\] states the same arm as \$\.seriesBranches\[0\]"),
])
def test_malformed_series_branches_are_refused(entries, match):
    with pytest.raises(PresentationSpecError, match=match):
        PresentationSpec.from_dict(_presentation(seriesBranches=entries))


def test_the_series_branch_list_itself_must_be_a_list():
    with pytest.raises(PresentationSpecError, match=r"\$\.seriesBranches must be a list"):
        PresentationSpec.from_dict(
            _presentation(seriesBranches={"id": "status-led"})
        )
