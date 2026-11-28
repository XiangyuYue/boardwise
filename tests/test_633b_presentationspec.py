"""633 缝 B：`presentationspec` 边界上的六条。

岳 2026-11-28 对五条待裁的口径（全按主代理建议）：

* **B-01** 侧偏好键的词表 = `_net_class()` 的集合 —— 它住在 `engines/placement.py`，
  `core` 里导入它会成环，所以这条搬到引擎那一批做；
* **B-02** 模块 `role` 没人读，**取消必填**（保留为自由文本）；
* **B-04** flow 两端必须是本文档声明过的模块，**边界拒**；
* **B-05** 一件两模块必须是**显式声明的共享件** —— 要新增 `sharedParts` 这个文档键
  （字段 + 序列化 + 往返），单独一批；
* **B-06** **缺席**与 `"modules": []` 分开：缺席拒，空表合法 —— **口径已裁、暂未落地**，
  替换面是仓库级（174/2688 条测试用缺席表示空图纸），单开一批。

本文件钉的是落地的 B-02 / B-03 / B-04 / B-07 / B-08，另有两处**留档用例**记录
B-05 / B-06 的现状。
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


# ------------------------------------------------------------------ 633B-02


def test_b02_a_module_may_omit_its_role():
    """没人读的字段不该是必填：`role` 的读者只有透传与回写。"""
    spec = build(
        modules=[
            {"id": "pwr", "parts": ["R1"]},
            {"id": "sense", "parts": ["C1"]},
        ]
    )
    assert [module.role for module in spec.modules] == ["", ""]


def test_b02_a_stated_role_is_still_stored():
    """对照：写了就还在（这条洞不是删字段，是取消必填）。"""
    assert [module.role for module in build().modules] == ["input", "output"]


# ------------------------------------------------------------------ 633B-03


def test_b03_a_document_of_another_kind_is_refused():
    with pytest.raises(PresentationSpecError) as exc:
        build(kind="some-other-document")
    message = str(exc.value)
    assert "some-other-document" in message, message
    assert PRESENTATION_SPEC_KIND in message, message


def test_b03_omitting_the_kind_is_still_accepted():
    document = copy.deepcopy(BASE)
    document.pop("kind")
    assert PresentationSpec.from_dict(document).to_jsonable()["kind"] == PRESENTATION_SPEC_KIND


# ------------------------------------------------------------------ 633B-04


def test_b04_a_flow_edge_to_an_undeclared_module_is_refused():
    with pytest.raises(PresentationSpecError) as exc:
        build(flow=[["pwr", "ghost"]])
    message = str(exc.value)
    assert "'ghost'" in message, message
    assert "does not declare" in message, message


def test_b04_a_flow_edge_between_declared_modules_still_works():
    spec = build(flow=[["pwr", "sense"]])
    assert [(e.from_module, e.to_module) for e in spec.flow] == [("pwr", "sense")]


# ------------------------------------------------------------------ 633B-06


def test_b06_a_missing_modules_key_is_still_the_house_shorthand():
    """**留档，未修**：B-06 的口径已裁（缺席拒、`[]` 合法），但落地成本是**仓库级**。

    实测 174/2688 条测试用 `{"grammarRef": …}` 建空图纸——「缺席」就是这套测试自己
    的既有写法。把两者分开要清扫几十个夹具，那是单独一批，不能夹在 B-02/B-04 里
    顺手动。这条用例让「06 还没改」有机器读数，而不是只写在报告里。
    """
    document = copy.deepcopy(BASE)
    document.pop("modules")
    assert PresentationSpec.from_dict(document).modules == []


def test_b06_an_explicit_empty_list_is_a_legal_empty_drawing():
    """对照组：显式写空表就是「这一页不摆东西」，仍然读得进来。"""
    spec = build(modules=[])
    assert spec.modules == []
    assert spec.effective_islands(), "空文档仍有一张空隐式岛，是既有行为"


# ------------------------------------------------------------------ 633B-07


def test_b07_a_padded_id_is_refused_rather_than_rewritten():
    document = copy.deepcopy(BASE)
    document["modules"][0]["id"] = "  pwr  "
    with pytest.raises(PresentationSpecError) as exc:
        PresentationSpec.from_dict(document)
    message = str(exc.value)
    assert "whitespace" in message, message
    assert "'  pwr  '" in message, message


def test_b07_an_ordinary_id_is_untouched():
    assert [module.id for module in build().modules] == ["pwr", "sense"]


# ------------------------------------------------------------------ 633B-08


def test_b08_a_part_twice_in_one_module_is_refused():
    document = copy.deepcopy(BASE)
    document["modules"][0]["parts"] = ["R1", "R1"]
    with pytest.raises(PresentationSpecError) as exc:
        PresentationSpec.from_dict(document)
    message = str(exc.value)
    assert "repeats" in message and "'R1'" in message, message


def test_b05_an_undeclared_shared_part_is_left_to_the_page_compiler():
    """**口径**：边界**不拒**未声明的共享件——页面路径会具名报 `presentation-poor`。

    633B-05 的修法是「让『故意的共享』有地方写」，不是「把下游那条诊断搬到边界」：
    仓库里有八条测试专门构造这个形状来证明下游会点名它（`test_056`/`test_053b`/
    `test_627a`/`test_548b`），搬到边界等于把一条具名的下游失败换成加载期报错。
    """
    spec = build(
        modules=[
            {"id": "pwr", "parts": ["R1"], "role": "input"},
            {"id": "sense", "parts": ["R1"], "role": "output"},
        ]
    )
    assert spec.shared_parts == []
    assert spec.modules_of_part("R1") == ["pwr", "sense"]


def test_b05_a_declared_shared_part_keeps_both_answers():
    """对照：声明之后，`modules_of_part` 的两个答案就是**说过的**答案。"""
    spec = build(
        modules=[
            {"id": "pwr", "parts": ["R1"], "role": "input"},
            {"id": "sense", "parts": ["R1"], "role": "output"},
        ],
        sharedParts=["R1"],
    )
    assert spec.shared_parts == ["R1"]
    assert spec.modules_of_part("R1") == ["pwr", "sense"]
    assert spec.declared_part_ids() == ["R1"]


def test_b05_a_shared_part_that_is_only_in_one_module_is_refused():
    """一条什么都没说的声明本身就是缺陷。"""
    with pytest.raises(PresentationSpecError) as exc:
        build(sharedParts=["R1"])
    assert "not shared" in str(exc.value), str(exc.value)


def test_b05_a_shared_part_nobody_declares_is_refused():
    with pytest.raises(PresentationSpecError) as exc:
        build(sharedParts=["ZZ9"])
    assert "no module declares" in str(exc.value), str(exc.value)


def test_b05_the_key_is_written_only_when_it_is_used():
    """没共享件的文档字节不变——这条键是 opt-in，不能改既有摘要。"""
    assert "sharedParts" not in build().to_jsonable()
    shared = build(
        modules=[
            {"id": "pwr", "parts": ["R1"], "role": "input"},
            {"id": "sense", "parts": ["R1"], "role": "output"},
        ],
        sharedParts=["R1"],
    )
    again = PresentationSpec.from_dict(shared.to_jsonable())
    assert again.shared_parts == ["R1"], "往返不许丢声明"
    assert again == shared
