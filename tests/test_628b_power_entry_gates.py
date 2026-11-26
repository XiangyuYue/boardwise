"""628B：`power_entry.py` + `grammar/__init__.py` 的七条洞。

主题与前几批同族：**入口链上的串联件、第二张地网、第二个入口**都是电路里的事实，
不能由网名排序静默裁决；**在册但没绑上的件**必须点名；**注册表与文档**必须同数。

夹具复用 `test_088_power_entry`（岳样板的连接器 + 支路构造器）。
"""

from __future__ import annotations

import test_088_power_entry as t088

from boardwise.engines import grammar as registry

PROV = t088.PROV
RAIL = t088.RAIL
GND = t088.GND


def _text(result) -> str:
    return " ".join(item.evidence for item in result.bindings)


def _fuse_chain() -> t088.CircuitSpec:
    """`J1 → F1 → VIN → {C1, D1}`：入口之后先串一只保险丝。"""
    return t088.circuit(
        [
            t088.part("J1", "XT30PW-M", "XT30"),
            t088.part("F1", "FUSE", "5A"),
            t088.part("C1", "C0402", "100n"),
            t088.part("D1", "TVS", "SMBJ24A"),
        ],
        [
            t088.net("VIN_IN", "power", ["J1.1", "F1.1"]),
            t088.net("VIN", "power", ["F1.2", "C1.1", "D1.1"]),
            t088.net("GND", "gnd", ["J1.2", "C1.2", "D1.2"]),
        ],
        interfaces=[{"net": "VIN_IN", "direction": "input", "role": "rail",
                     "part": "J1", "provenance": PROV}],
    )


def _two_grounds(second: str) -> t088.CircuitSpec:
    """J1 与 C1 在 GND，C7 从 VIN 回到**第二张**地网。"""
    return t088.circuit(
        [
            t088.part("J1", "XT30PW-M", "XT30"),
            t088.part("C1", "C0402", "100n"),
            t088.part("C7", "C0402", "100n"),
        ],
        [
            t088.net("VIN", "power", ["J1.1", "C1.1", "C7.1"]),
            t088.net("GND", "gnd", ["J1.2", "C1.2"]),
            t088.net(second, "gnd", ["C7.2"]),
        ],
        interfaces=[{"net": "VIN", "direction": "input", "role": "rail",
                     "part": "J1", "provenance": PROV}],
    )


def _two_entries() -> t088.CircuitSpec:
    """USB 与 DC 各一个入口，各带一条支路。"""
    return t088.circuit(
        [
            t088.part("J_DC", "XT30PW-M", "DC"),
            t088.part("J_USB", "USB-C-16P", "USB"),
            t088.part("C1", "C0402", "100n"),
            t088.part("C2", "C0402", "100n"),
        ],
        [
            t088.net("VDC", "power", ["J_DC.1", "C1.1"]),
            t088.net("VUSB", "power", ["J_USB.1", "C2.1"]),
            t088.net("GND", "gnd", ["J_DC.2", "J_USB.2", "C1.2", "C2.2"]),
        ],
        interfaces=[
            {"net": "VDC", "direction": "input", "role": "rail", "part": "J_DC",
             "provenance": PROV},
            {"net": "VUSB", "direction": "input", "role": "rail", "part": "J_USB",
             "provenance": PROV},
        ],
    )


# ================================================================== 628B-01
def test_b01_a_fuse_in_the_entry_chain_does_not_hide_the_branches_behind_it():
    """F1 串在 `VIN_IN`（声明了入口的网）与 `VIN` 之间，C1/D1 挂在 `VIN` 上。

    旧读数：`_shunts` 只收「恰跨 rail 与 gnd」的件，rail 落在 `VIN_IN`，于是
    串联件与它后面所有支路一起掉出绑定集合，`ok=true`、0 约束，`owned-branch`
    的理由串写「no branch」。应有的答案必须把这件与它后面的支路说出来。
    """
    result = t088.bind(_fuse_chain(), t088.inlet_presentation())

    assert result.ok is True, "".join(item.detail for item in result.failures)
    # 支路要真的**绑上**（不是只出现在某条 net 的 members 里）。
    assert set(result.parts_of("shunt")) == {"C1", "D1"}, result.parts_of("shunt")
    text = _text(result)
    assert "F1" in text, text
    assert "entry chain" in text, text


# ================================================================== 628B-02
def test_b02_the_entry_parts_own_ground_wins_over_the_net_id_order():
    """第二张地网叫 `AGND`（id 序在 `GND` 前）：入口 J1 在 `GND` 上。

    旧读数：`_ground_of` 按 id 取 `[0]`，选到 `AGND`，于是 J1 被判「不是跨
    VIN 与 AGND 的二端件」而假拒；把它改名 `ZGND` 又变成 `ok=true` 且 C7 消失。
    两个读数都不该由网名决定：先取入口件自己所在的地，再把第二条返回说出来。
    """
    for second in ("AGND", "ZGND"):
        result = t088.bind(_two_grounds(second), t088.inlet_presentation())
        assert result.ok is True, (second, "".join(
            item.detail for item in result.failures))
        text = _text(result)
        assert "C7" in text and second in text, (second, text)


# ================================================================== 628B-03
def test_b03_two_entry_nets_are_refused_naming_both():
    """`VDC` 与 `VUSB` 各声明了一个入口：一个模块一次只画一个输入。

    旧读数：`_rail_of` 按 id 取第一个（`VDC`），另一路 `J_USB`/`C2`/`VUSB`
    零字，`ok=true`。
    """
    result = t088.bind(_two_entries(), t088.inlet_presentation())

    assert result.ok is False
    detail = " ".join(item.detail for item in result.failures)
    assert "VDC" in detail and "VUSB" in detail, detail
    assert "J_DC" in detail and "J_USB" in detail, detail


# ================================================================== 628B-04
def test_b04_a_three_pin_part_and_a_one_pin_part_are_named():
    """Q1 三脚跨 VIN/GND/DRN，C9 只有一脚被点名 —— 两件都不该零字。

    旧读数：`ok=true`、无 failure、无 evidence 句，与「这两件不在册」不可区分。
    """
    circuit = t088.circuit(
        [
            t088.part("J1", "XT30PW-M", "XT30"),
            t088.part("C1", "C0402", "100n"),
            t088.part("Q1", "SOT-23", "MMBT3904"),
            t088.part("C9", "C0402", "100n"),
        ],
        [
            t088.net("VIN", "power", ["J1.1", "C1.1", "Q1.1", "C9.1"]),
            t088.net("GND", "gnd", ["J1.2", "C1.2", "Q1.2"]),
            t088.net("DRN", "signal", ["Q1.3"]),
        ],
        interfaces=[{"net": "VIN", "direction": "input", "role": "rail",
                     "part": "J1", "provenance": PROV}],
    )
    result = t088.bind(circuit, t088.inlet_presentation())

    assert result.ok is True
    text = _text(result)
    assert "Q1" in text, text
    assert "C9" in text, text
    assert "not usable as a branch" in text, text


# ================================================================== 628B-05
def test_b05_the_published_role_table_checks_the_bindings():
    """`ROLES_BY_GRAMMAR` 不能只是 `__all__` 里的一行字符串。

    本批把校验挂在注册表入口：绑定出的每个 role 都必须在**那本文法自己的**角色表里，
    否则是这本语法在说它没承诺过的角色（编程错误，不是输入问题）。
    """
    check = getattr(registry, "check_result_roles")
    # 每本文法的公开角色表与注册表逐项一致（漂移即红）。
    import sys

    for name in registry.NAMES:
        instance = registry.grammar_for(name)
        module = sys.modules[type(instance).__module__]
        published = tuple(module.ROLES) + tuple(getattr(module, "EXTRA_ROLES", ()))
        assert published == registry.ROLES_BY_GRAMMAR[name], name

    # 表外角色必须被点名拒绝。
    class _Fake:
        role = "not-a-role"
        part_id = "X1"
        evidence = ""

    with_res = type("R", (), {"bindings": (_Fake(),), "ok": True})()
    try:
        check(registry.NAMES[0], with_res)
    except registry.GrammarRoleError as exc:
        assert "not-a-role" in str(exc)
    else:
        raise AssertionError("role outside the published table was accepted")


# ================================================================== 628B-06
def test_b06_the_registry_documents_and_the_names_are_the_same_count():
    """同一条注册表被描述成七 / 六 / 三本 —— 对外承诺面比实现少四本。"""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    init = (root / "src/boardwise/engines/grammar/__init__.py").read_text(
        encoding="utf-8")
    draw = (root / "docs/draw.md").read_text(encoding="utf-8")
    assert "The six grammar names" not in init
    assert "seven grammar names" in init
    assert "Grammars today: voltage divider, RC low-pass, LDO" not in draw
    assert "flyback" in draw.split("\n")[9] or "seven" in draw.split("\n")[9], (
        draw.split("\n")[9])


# ================================================================== 628B-07
def test_b07_the_side_table_and_the_defaults_have_one_definition_each():
    """四值侧表与 `DEFAULT_SIDE_PREFERENCES` 至少五处拷贝：改一处即静默漂移。"""
    from boardwise.core import presentationspec
    from boardwise.engines.grammar import base, flyback, ldo, power_entry

    assert getattr(base, "SIDE_KIND") is not None
    for module in (power_entry, flyback, ldo):
        assert module.SIDE_KIND is base.SIDE_KIND, module.__name__
        assert module.SIDE_KIND["top"] == base.ABOVE

    from boardwise.engines import placement

    assert placement.DEFAULT_SIDE_PREFERENCES is (
        presentationspec.DEFAULT_SIDE_PREFERENCES
    )
