"""548D 24A：页级与岛级电源旗名回退 ``PWR-<net>`` → ``PWR-+<net>``。

548D3 把 ``PWR-3V3`` / ``PWR-+3V3`` 的裁决写进了 `drawcompiler._flag_ref`，页级
（`pagecompiler._flag_profile`）与岛级（`islandlayout._flag_ref`）仍是「只有原名」，
于是同一本冻结库、同一条 ``3V3`` 网在一条链上说两句话：岛的旗标挂 ``PWR-+3V3``，页端口
却报「库里没有旗标符号 'PWR-3V3'」而退成标签（`evidence/548D/full-page/mcu-current.json`
第 955 行就是那个旗标，`evidence/548D/mcu/cand_auto+series.plan.json` 的降级 note 就是那句话）。

本文件量的是同一条规则的三份实现（编译器 / 页 / 岛）不许分歧，以及回退的**边界**：

* **原名优先**：库里同时有原名与别名时，绝不换名——两者几何不同，换名会挪动文档从没
  要求挪的图形，所以这条用「同名不同几何」的 negative control 钉住（页端口与岛旗的
  ``symbol_ref`` / ``symbol_hash`` 都必须是原名那枚 profile 的）；
* **只在原名缺席时回退**：别名只对 rail、只对 net id 不含 ``+`` 的网、只在库里真有这枚
  符号时生效；
* **GND 永不起别名、绝不并网**：``PWR-+GND`` 不是名字，地网照旧按 `gnd_flag` /
  173C 的域选，别名一步都不许碰；
* **两边都没有时旧行为不变**：ref 仍是原名（降级 note 点名 ``PWR-3V3``），不走别名、
  不放大任何东西。

用的夹具是仓库既有的：页场景取 `test_056_pagecompiler` 的 scene 2（三个模块、两条
跨模块 rail），岛取 `test_530a_island_flags._two_islands` 的合成页（同一颗器件的两种旗
不走两套定义）。全程离线，不 import connector / cli / rules / dsh。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import test_056_pagecompiler as p056
import test_530a_island_flags as t530

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import islandlayout as il
from boardwise.engines import pagecompiler as pc

PREFIX = "PWR-"
GND_FLAG = "PWR-GND"

#: The own-name glyph and the alias glyph are deliberately **different shapes**: if
#: one is silently swapped for the other, the flags' geometry moves, and the
#: ``symbol_hash`` assertions below notice.
_OWN_BODY = (-6.0, 0.0, 6.0, 18.0)
_ALIAS_BODY = (-10.0, 0.0, 10.0, 24.0)

#: A third shape, for the island fixture's rails whose profiles come from 530A.
_BULK_BODY = (-5.5, 0.0, 5.5, 10.5)


def _flag(ref: str, body=_OWN_BODY) -> SymbolProfile:
    """A rail/ground flag: a glyph box and **no pins** (how the compiler spots one)."""
    return SymbolProfile.from_dict({
        "symbolRef": ref, "title": ref, "body": list(body), "pins": [],
    })


def _alias_book(**rails: str) -> dict[str, SymbolProfile]:
    """A book keyed by the refs it carries — ``rails`` maps net id → carried ref."""
    return {ref: _flag(ref) for ref in rails.values()}


# ------------------------------------------------------------------ 页级单元


def _page_ctx(book: dict[str, SymbolProfile]) -> SimpleNamespace:
    """Only what `_flag_profile` reads: the book and the module budget's two names."""
    return SimpleNamespace(
        book=book,
        budget=SimpleNamespace(
            module_budget=SimpleNamespace(
                power_flag_prefix=PREFIX, gnd_flag=GND_FLAG,
            ),
        ),
    )


def _circuit(*nets: tuple[str, str, list[str]]) -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": [{"id": "U1", "symbolRef": "U", "value": "U",
                   "provenance": "ai_asserted"}],
        "nets": [
            {"id": net_id, "class": cls, "members": list(members),
             "provenance": "ai_asserted"}
            for net_id, cls, members in nets
        ],
    })


def test_the_page_asks_for_a_rails_own_name_before_the_alias():
    """同名不同几何的 negative control：两枚都在库中，页只认原名那枚。

    A book that carries both spellings states two different glyphs. The page may
    not draw the alias "because it exists" — the own name is what the rule asks
    for, and the two geometries are what makes a silent swap visible here.
    """
    own, alias = _flag("PWR-3V3", _OWN_BODY), _flag("PWR-+3V3", _ALIAS_BODY)
    assert own.body != alias.body, "the control is worthless if the shapes match"
    book = {"PWR-3V3": own, "PWR-+3V3": alias}
    ctx = _page_ctx(book)
    net = _circuit(("3V3", "power", ["U1.1", "U1.2"])).net("3V3")
    profile, ref = pc._flag_profile(ctx, net)
    assert ref == "PWR-3V3"
    assert profile is own, "the page answered with the alias glyph"
    assert profile.body == _OWN_BODY


def test_the_page_falls_back_to_the_alias_only_when_the_own_name_is_absent():
    """原名缺席、别名在库中：页报的 ref 与拿到的 profile 都是别名那枚。"""
    book = {"PWR-+3V3": _flag("PWR-+3V3", _ALIAS_BODY)}
    ctx = _page_ctx(book)
    net = _circuit(("3V3", "power", ["U1.1", "U1.2"])).net("3V3")
    profile, ref = pc._flag_profile(ctx, net)
    assert ref == "PWR-+3V3"
    assert profile is book["PWR-+3V3"]
    assert profile.body == _ALIAS_BODY


def test_a_page_rail_under_neither_name_keeps_the_own_ref():
    """两边都没有：ref 仍是 ``PWR-3V3``，降级 note 点名的还是那条拼法。

    The old answer is the answer — the missing-symbol note has to name the ref the
    rule asked for, not a spelling no library entry was ever looked up under.
    """
    ctx = _page_ctx({"PWR-GND": _flag("PWR-GND", _BULK_BODY)})
    net = _circuit(("3V3", "power", ["U1.1", "U1.2"])).net("3V3")
    assert pc._flag_profile(ctx, net) == (None, "PWR-3V3")


def test_the_page_never_aliases_a_ground():
    """``PWR-+GND`` 不是名字：地网照旧取 `gnd_flag`，别名一步不碰。"""
    book = {
        "PWR-GND": _flag("PWR-GND", _BULK_BODY),
        "PWR-+GND": _flag("PWR-+GND", _ALIAS_BODY),
    }
    ctx = _page_ctx(book)
    net = _circuit(("GND", "gnd", ["U1.1", "U1.2"])).net("GND")
    profile, ref = pc._flag_profile(ctx, net)
    assert ref == GND_FLAG
    assert profile is book["PWR-GND"]


def test_a_net_id_that_already_carries_the_plus_gets_no_second_plus():
    """``+5V`` 的原名就是 ``PWR-+5V``；``PWR-++5V`` 不在任何一本书里。"""
    book = {"PWR-++5V": _flag("PWR-++5V", _ALIAS_BODY)}
    ctx = _page_ctx(book)
    net = _circuit(("+5V", "power", ["U1.1", "U1.2"])).net("+5V")
    assert pc._flag_profile(ctx, net) == (None, "PWR-+5V")


# ------------------------------------------------------------------ 岛级单元


def _island_page(book: dict[str, SymbolProfile]):
    """530A's synthetic two-island page, with its rails renamed to this batch's.

    The circuit and presentation are the fixture's own (``VBUS`` → ``3V3`` so the
    net under test is the one the alias exists for); the flag profiles are this
    file's, so every glyph a block hangs is measurable against the book it was
    given rather than against 530A's ``PWR-VBUS``.
    """
    nets = [
        {"id": "3V3", "class": "power",
         "members": ["U1.1", "R1.1", "R2.1", "D1.1"], "provenance": "verified_recipe"},
        {"id": "PGND", "class": "gnd",
         "members": ["R1.2", "R2.2", "D1.2"], "provenance": "verified_recipe"},
        {"id": "SGND", "class": "gnd", "members": ["U1.3", "R3.1"],
         "provenance": "verified_recipe"},
        {"id": "OUT", "class": "signal", "members": ["U1.2", "D1.3"],
         "provenance": "verified_recipe"},
        {"id": "SPARE", "class": "signal", "members": ["U1.4"],
         "provenance": "verified_recipe"},
    ]
    circuit, presentation, fixture_book = t530._two_islands(nets)
    parts_only = {
        ref: profile for ref, profile in fixture_book.items()
        if not ref.startswith("PWR-")
    }
    return circuit, presentation, {**parts_only, **book}


def _island_flags(book: dict[str, SymbolProfile]) -> dict[str, list]:
    circuit, presentation, full_book = _island_page(book)
    return {
        block.island_id: [symbol for symbol in block.power_symbols
                          if symbol.net == "3V3"]
        for block in il.island_blocks(circuit, presentation, full_book)
    }


def test_the_island_asks_for_a_rails_own_name_before_the_alias():
    """同名不同几何的 negative control，岛侧：两枚都在库中，岛只挂原名那枚。"""
    own, alias = _flag("PWR-3V3", _OWN_BODY), _flag("PWR-+3V3", _ALIAS_BODY)
    flags = _island_flags({
        "PWR-3V3": own, "PWR-+3V3": alias,
        "PWR-PGND": _flag("PWR-PGND", _BULK_BODY),
        "PWR-SGND": _flag("PWR-SGND", _BULK_BODY),
        "PWR-GND": _flag("PWR-GND", _BULK_BODY),
    })
    for island_id in ("a", "b"):
        assert [symbol.symbol_ref for symbol in flags[island_id]] == ["PWR-3V3"]
        assert flags[island_id][0].symbol_hash == own.geometry_hash(), (
            f"island {island_id} carries the alias glyph's hash"
        )


def test_the_island_falls_back_to_the_alias_when_the_own_name_is_absent():
    """原名缺席：岛挂 ``PWR-+3V3``，且 hash 是那枚 profile 自己的。"""
    alias = _flag("PWR-+3V3", _ALIAS_BODY)
    flags = _island_flags({
        "PWR-+3V3": alias,
        "PWR-PGND": _flag("PWR-PGND", _BULK_BODY),
        "PWR-SGND": _flag("PWR-SGND", _BULK_BODY),
        "PWR-GND": _flag("PWR-GND", _BULK_BODY),
    })
    for island_id in ("a", "b"):
        assert [symbol.symbol_ref for symbol in flags[island_id]] == ["PWR-+3V3"]
        assert flags[island_id][0].symbol_hash == alias.geometry_hash()


def test_the_island_rail_under_neither_name_keeps_its_own_ref_and_says_so():
    """两边都没有：岛退成标签，note 点名的仍是 ``PWR-3V3``——旧行为逐字不变。"""
    circuit, presentation, book = _island_page({
        "PWR-PGND": _flag("PWR-PGND", _BULK_BODY),
        "PWR-SGND": _flag("PWR-SGND", _BULK_BODY),
        "PWR-GND": _flag("PWR-GND", _BULK_BODY),
    })
    block = {item.island_id: item for item in il.island_blocks(
        circuit, presentation, book)}["a"]
    assert "3V3" not in {symbol.net for symbol in block.power_symbols}
    assert "3V3" in {label.net for label in block.labels}
    notes = [note for note in block.notes if "PWR-3V3" in note]
    assert len(notes) == 1 and "label" in notes[0], notes
    assert not [note for note in block.notes if "PWR-+3V3" in note], (
        "a ref no book entry was looked up under must not reach the note"
    )


def test_the_island_never_aliases_a_ground():
    """地网：两域时各取本名，别名 ``PWR-+PGND`` 即使在库里也不许被当成名字。"""
    book = {
        "PWR-3V3": _flag("PWR-3V3", _OWN_BODY),
        "PWR-PGND": _flag("PWR-PGND", _BULK_BODY),
        "PWR-SGND": _flag("PWR-SGND", _BULK_BODY),
        "PWR-+PGND": _flag("PWR-+PGND", _ALIAS_BODY),
    }
    circuit, presentation, full_book = _island_page(book)
    primary = {item.island_id: item for item in il.island_blocks(
        circuit, presentation, full_book)}["a"]
    assert {symbol.net: symbol.symbol_ref for symbol in primary.power_symbols} == {
        "3V3": "PWR-3V3", "PGND": "PWR-PGND", "SGND": "PWR-SGND",
    }


# --------------------------------------------------- 三份实现不许说两句话


def _dc_context(book: dict[str, SymbolProfile], net_id: str, cls: str):
    """A `_Context` carrying only what `drawcompiler._flag_ref` reads."""
    circuit = _circuit((net_id, cls, ["U1.1", "U1.2"]))
    return dc._Context(
        circuit=circuit,
        presentation=PresentationSpec.from_dict({"grammarRef": "flyback"}),
        binding=None,
        book=book,
        budget=dc.CompileBudget(),
        axis="x",
        progress=(1.0, 0.0),
        chain_net_rank={},
        slots={},
        chain=[],
        accepted={},
        body_dirs={},
    )


@pytest.mark.parametrize(
    "carried, net_id, cls, expected",
    [
        (("PWR-3V3", "PWR-+3V3"), "3V3", "power", "PWR-3V3"),
        (("PWR-+3V3",), "3V3", "power", "PWR-+3V3"),
        (("PWR-GND",), "3V3", "power", "PWR-3V3"),
        (("PWR-+5V",), "+5V", "power", "PWR-+5V"),
        (("PWR-++5V",), "+5V", "power", "PWR-+5V"),
        (("PWR-GND", "PWR-+GND"), "PGND", "gnd", "PWR-GND"),
    ],
)
def test_the_three_flag_choosers_answer_one_ref(carried, net_id, cls, expected):
    """编译器、页、岛对同一条网给出同一个 ref——548D 24A 的全部合同。

    Asked on the same book and the same net; the page side is asked through its
    own rail helper (a ground's page answer is the budget's `gnd_flag`, so the
    ground row compares the ``PWR-GND`` switch all three carry).
    """
    book = {ref: _flag(ref) for ref in carried}
    book.setdefault(GND_FLAG, _flag(GND_FLAG))
    ctx = _dc_context(book, net_id, cls)
    assert dc._flag_ref(ctx, net_id, cls) == expected

    if cls != "gnd":
        assert pc._rail_flag_ref(book, PREFIX, net_id) == expected
    else:
        page_ctx = _page_ctx(book)
        _profile, page_ref = pc._flag_profile(page_ctx, ctx.circuit.net(net_id))
        assert page_ref == expected

    island_ref = il._flag_ref(
        net_id, cls, book=book, budget=il.IslandBudget(),
        ground_domains=frozenset({"PGND", "SGND"}),
    )
    assert island_ref == expected, (
        f"{net_id} ({cls}) with {carried}: the island says {island_ref!r}, the "
        f"compiler {expected!r}"
    )


# ------------------------------------------------- 端到端：页端口与库旗一致


def _scene_two(book: dict[str, SymbolProfile]):
    scene = p056.scenes()[2]
    result = pc.compile_page(
        scene.circuit, scene.presentation, book, scene.budget,
    )
    assert result.ok, p056.render(result)
    return scene, result.pages[0]


def _ports_for(page, net_id: str) -> list[str]:
    return [
        port.kind for module in page.modules for port in module.ports
        if port.net == net_id
    ]


def _flags_for(page, net_id: str) -> list:
    return [symbol for symbol in page.plan.power_symbols if symbol.net == net_id]


def test_a_page_port_and_the_library_flag_name_one_rail_one_way():
    """页端口退成标签的那个缺口：别名在库里时，端口与旗都是 ``PWR-+3V3``。

    The frozen 548D book carries ``PWR-+3V3`` and no ``PWR-3V3``; before this
    batch the page stated ``3V3`` with labels at both module ends while the islands
    hung ``PWR-+3V3`` — one document, two answers. Now both ends are flags and the
    plan's own symbols are the alias profile, hash and all.
    """
    book = p056.library()
    del book["PWR-3V3"]
    alias = _flag("PWR-+3V3", _ALIAS_BODY)
    book["PWR-+3V3"] = alias
    _scene, page = _scene_two(book)

    assert _ports_for(page, "3V3") == [pc.PAGE_PORT_FLAG, pc.PAGE_PORT_FLAG]
    flags = _flags_for(page, "3V3")
    assert [symbol.symbol_ref for symbol in flags] == ["PWR-+3V3", "PWR-+3V3"]
    for symbol in flags:
        assert symbol.symbol_hash == alias.geometry_hash(), (
            "the page drew PWR-+3V3 with another profile's hash"
        )
    assert not [label for label in page.plan.labels if label.net == "3V3"], (
        "the rail is named by a flag at every end; a label for it would say it twice"
    )


def test_a_book_with_both_names_still_draws_the_own_name():
    """同名不同几何，端到端：两枚都在库里，页端口的旗仍是原名那枚 profile。

    The other rails (`3V3F`, `GND`, `VIN5`) are unchanged by the edit, which is
    how this test also states that the alias does not reach past the one net it
    was asked about.
    """
    own, alias = _flag("PWR-3V3", _OWN_BODY), _flag("PWR-+3V3", _ALIAS_BODY)
    book = p056.library()
    book["PWR-3V3"] = own
    book["PWR-+3V3"] = alias
    _scene, page = _scene_two(book)

    assert _ports_for(page, "3V3") == [pc.PAGE_PORT_FLAG, pc.PAGE_PORT_FLAG]
    flags = _flags_for(page, "3V3")
    assert [symbol.symbol_ref for symbol in flags] == ["PWR-3V3", "PWR-3V3"]
    for symbol in flags:
        assert symbol.symbol_hash == own.geometry_hash()
    assert [symbol.symbol_ref for symbol in _flags_for(page, "3V3F")] == [
        "PWR-3V3F", "PWR-3V3F",
    ]
    assert {symbol.symbol_ref for symbol in _flags_for(page, "GND")} == {GND_FLAG}


def test_a_book_with_neither_name_is_what_it_was():
    """两边都没有：端口照旧退成标签，页上没有 3V3 旗——旧行为不变。"""
    book = p056.library()
    del book["PWR-3V3"]
    _scene, page = _scene_two(book)

    assert _ports_for(page, "3V3") == [pc.PAGE_PORT_LABEL, pc.PAGE_PORT_LABEL]
    assert _flags_for(page, "3V3") == []
    assert {label.net for label in page.plan.labels} == {"3V3", "TAP"}
