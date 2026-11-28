"""633B-01：`sidePreferences` 里「本图没有任何网类读它」的键要被点名。

洞的原话是「打错的偏好被静默接受且永不生效」。岳 2026-11-28 的口径是 (b)：词表从
`_net_class()` 的集合推，不新造。`_net_class(request, net_id)` 读的是 `net.cls`，所以
**本图实际出现的网类集合**就是那份词表——一个键既不是引擎恒问的那四个、也没有任何网
带着这个 class，它就是一条存下来没人问的偏好。

落点在页编译器的 notes（它已经有披露通道，且 `sides_for_module()` 在这里合并文档级与
模块级偏好）。**没有加任何拒绝**：J3 的「松一点，但要让 agent 知道」。
"""

from __future__ import annotations

import dataclasses

import test_056_pagecompiler as base

import boardwise.engines.pagecompiler as pc

BUDGET = pc.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0))


def compile_with(spec):
    scene = base.scenes()[1]
    return pc.compile_page(scene.circuit, spec, base.library(), BUDGET)


def test_b01_a_preference_no_net_carries_is_named():
    document = base.regulator_plus_divider_spec()
    spec = dataclasses.replace(
        document,
        side_preferences={**document.side_preferences, "imput": "right"},
    )
    result = compile_with(spec)
    text = " ".join(result.notes)
    assert "'imput'" in text, text
    assert "no net in this circuit has that class" in text, text
    assert "stored and never asked for" in text, text


def test_b01_the_four_roles_the_engine_asks_for_are_never_reported():
    """对照组：一张没有地网的页不是「打错」，是这张图没有地。

    四个默认角色永远不进这条披露——否则每张没有某种网类的图都会多一条噪声。
    """
    document = base.regulator_plus_divider_spec()
    spec = dataclasses.replace(
        document,
        side_preferences={
            "input": "left",
            "output": "right",
            "power": "top",
            "gnd": "bottom",
        },
    )
    result = compile_with(spec)
    assert "no net in this circuit has that class" not in " ".join(result.notes), result.notes


def test_b01_a_role_a_net_actually_carries_is_not_reported():
    """对照组：本图真的有这个 class 的网时，偏好会被读到，不许报「没人问」。

    这里用文法自己的网类名（`regulator_plus_divider_spec` 的场景里存在的那一个），
    所以它必须**不**出现在披露里。
    """
    scene = base.scenes()[1]
    classes = {net.cls for net in scene.circuit.nets if net.cls}
    assert classes, "这个场景至少要有一个带 class 的网，否则用例没有意义"
    carried = sorted(classes)[0]
    document = base.regulator_plus_divider_spec()
    spec = dataclasses.replace(
        document,
        side_preferences={**document.side_preferences, carried: "top"},
    )
    result = compile_with(spec)
    text = " ".join(result.notes)
    assert f"'{carried}'" not in text, (carried, text)
