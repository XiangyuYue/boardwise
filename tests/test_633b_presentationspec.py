"""633 缝 B：`presentationspec` 边界上**不改合法文档**的三条。

八条里先落了三条，另五条退回裁定清单——不是没做，是**做了会把仓库现在真实构建
的文档判死**，实测过的：

| 洞 | 为什么不在这里 |
|---|---|
| **633B-01** 侧偏好角色无词表 | 合法键不是 `DEFAULT_SIDE_PREFERENCES` 那四个：`placement.py:2150` 按 `_net_class()` 取，真文档里用 `load` 之类的**网类**名。按四个收口，全量面大面积变红 |
| **633B-02** 模块 `role` 无词表 | 这个 build 全树没有模块角色词表（`ISLAND_ROLES` 只管岛），也没有读者——词表得先定 |
| **633B-04** flow 幽灵边 | 在 spec 边界拒会打掉 `test_053a_specs` 里用 flow 当「四个模块两两成对」的既有夹具；**两条路径两种下场**这一事实本身仍成立，但要先决定幽灵边是文档缺陷还是容忍 |
| **633B-05** 一件两模块 | 共享件是 623 已经承认的形态（`sharedParts` 点名），拒绝等于判死真板 |
| **633B-06** `modules=[]` | 多处用空表示「不画东西」的 spec，拒绝后读不进来 |

留下的三条共同点：**坏文档被读成好文档**，而**好文档一个字都不受影响**。

* **B-03**（中）`kind` 在 `_TOP_KEYS` 里却从不比对，别的文档被 `to_jsonable` 洗成本文档；
* **B-07**（低）`_text` 无条件 strip，`"  pwr  "` 被静默改写成 `pwr`——身份字段被改写，
  而重复检测、flow 引用、岛引用随后都按一个文件里并不存在的名字对齐；
* **B-08**（低）同一模块内 `parts` 重复被接受，`module.parts` 留两份、`declared_part_ids`
  只留一份，走 `module.parts` 的消费者会把同一件处理两次。
"""

from __future__ import annotations

import copy

import pytest

from boardwise.core.presentationspec import (
    PRESENTATION_SPEC_KIND,
    PRESENTATION_SPEC_VERSION,
    PresentationSpec,
    PresentationSpecError,
)

BASE = {
    "kind": PRESENTATION_SPEC_KIND,
    "specVersion": PRESENTATION_SPEC_VERSION,
    "modules": [
        {"id": "pwr", "parts": ["R1"], "role": "input"},
        {"id": "sense", "parts": ["C1"], "role": "output"},
    ],
}


def build(**over) -> PresentationSpec:
    document = copy.deepcopy(BASE)
    document.update(over)
    return PresentationSpec.from_dict(document)


# ------------------------------------------------------------------ 633B-03


def test_b03_a_document_of_another_kind_is_refused():
    """`kind` 只被当成一个允许出现的键名，从来没被比对过。"""
    with pytest.raises(PresentationSpecError) as exc:
        build(kind="some-other-document")
    message = str(exc.value)
    assert "some-other-document" in message, message
    assert PRESENTATION_SPEC_KIND in message, message


def test_b03_omitting_the_kind_is_still_accepted():
    """对照组：缺省即补默认，这条只掐「写错」不掐「没写」。"""
    document = copy.deepcopy(BASE)
    document.pop("kind")
    assert PresentationSpec.from_dict(document).to_jsonable()["kind"] == PRESENTATION_SPEC_KIND


# ------------------------------------------------------------------ 633B-07


def test_b07_a_padded_id_is_refused_rather_than_rewritten():
    """`"  pwr  "` 曾被读成 `pwr`：文件里写的名字与读进来的名字不是同一个。"""
    document = copy.deepcopy(BASE)
    document["modules"][0]["id"] = "  pwr  "
    with pytest.raises(PresentationSpecError) as exc:
        PresentationSpec.from_dict(document)
    message = str(exc.value)
    assert "whitespace" in message, message
    assert "'  pwr  '" in message, message


def test_b07_an_ordinary_id_is_untouched():
    """对照组：这条不是把名字收紧，只是不许改写。"""
    spec = build()
    assert [module.id for module in spec.modules] == ["pwr", "sense"]


# ------------------------------------------------------------------ 633B-08


def test_b08_a_part_twice_in_one_module_is_refused():
    document = copy.deepcopy(BASE)
    document["modules"][0]["parts"] = ["R1", "R1"]
    with pytest.raises(PresentationSpecError) as exc:
        PresentationSpec.from_dict(document)
    message = str(exc.value)
    assert "repeats" in message and "'R1'" in message, message


def test_b08_a_part_in_two_modules_is_still_accepted():
    """**对照兼留档**：跨模块共享件仍被接受——那是 633B-05 的裁定面，不是本条的修法。

    这条用例的存在是为了让「B-05 还没修」有机器读数，而不是靠报告里的一句话。
    """
    spec = build(
        modules=[
            {"id": "pwr", "parts": ["R1"], "role": "input"},
            {"id": "sense", "parts": ["R1"], "role": "output"},
        ]
    )
    assert spec.modules_of_part("R1") == ["pwr", "sense"]
