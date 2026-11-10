"""548C5：长值行（548C B2）——支路节距与「同类支路靠近宿主」的实测冲突。

548C 的 B2 变体只换表面：把 547A 岛内器件的 value 行换成带单位/容差/封装的完整
行（`LONG_VALUES`，与 `evidence/548C/variants/build_variants.py` 逐字相同，这里
内联，测试运行不读 ignored 的 evidence）。电气、位号、网名、符号一概不动。

改前的第一次测量是 **0 候选**，首拒为文字座椅在 60 单位的支路节距下四方向 ×
四梯级全被挡，于是回退到首选侧并把 159.5 宽的值行印在邻件身上：

    [text-overlap] texts[5] 'Red LED 2.0 V 20 mA 0603' [188,23.5,347.5,32.5]
                 × parts[D2] [213,19.5,227,30.5]

548C5 试过的两条路都实测失败，证书见 `evidence/548C5/README.md`：

* **全局加宽节距**（`_chain_and_shelf_layout` 的 chain pitch 与支路 seat step 同时
  加一个闭式算出的文字余量）：文字越界消失，但 `near(D2, U1)` 被拒——九个座位
  各加一档把行推到 `NEAR_LIMIT = 300` 之外；
* **只把闸点名的那一件往外推**（按 `texts[i] × parts[j]` 的实测越界量逐件加、
  后续座位继承）：`near(S1, U1)` 同样被拒，原因相同。

548C5 当时交回的判据是：159.5 宽的值行 × 10 件的行，在 `NEAR_LIMIT = 300` 下
**不存在**既容纳每行又让每件都「靠近」其宿主的单一节距；那不是节距算得不够细，
而是必须换一层。当时用 strict xfail 钉住首拒与被压器件，等待另一层补上这个缺口。

**548C6 的收口**（2026-11-08）：那条 strict xfail 已实测 XPASS，因为同岛二维
支路座位（`drawcompiler._seat_branch_stack`，只在构造梯级与加宽轮都无候选时的救援轮
运行）把每件支路放上各自的**横向行**，逃逸距离仍是梯级的第一档，`near` 不再被吃掉。
本文件当前全部是正向回归：长值行各印一次、D2 在位、可读性硬闸为空；未改值的 547A
指纹不变。"单一节距无解"这条历史结论仍然成立——它被另一层（座位轴）补上，
不是被更细的节距推翻，更不是靠换行或分岛绕开。
"""

from __future__ import annotations

import copy

import test_547_repeated_shunts as m547
from test_548c4_text_label_repair import _module_view, _profiles

from boardwise.engines import drawcompiler as dc
from boardwise.engines import readability as rd

#: 548C B2's surface change, verbatim from
#: ``evidence/548C/variants/build_variants.py`` (``LONG_VALUES``). Inlined on
#: purpose: a test may not depend on ignored evidence to run.
LONG_VALUES = {
    "U1": "STM32G431RBT6 ARM Cortex-M4 170 MHz LQFP-64",
    "C1": "100 nF ±10% 50 V X7R 0603",
    "R1": "10 kΩ ±1% 1/10 W 50 V 0603",
    "S1": "Tactile switch SPST-NO 12 V 50 mA 6×6 mm",
    "S2": "Tactile switch SPST-NO 12 V 50 mA 6×6 mm",
    "S3": "Tactile switch SPST-NO 12 V 50 mA 6×6 mm",
    "S4": "Tactile switch SPST-NO 12 V 50 mA 6×6 mm",
    "D1": "Red LED 2.0 V 20 mA 0603",
    "D2": "Green LED 2.1 V 20 mA 0603",
}

#: The unrenamed 547A island, as this worktree measures it (548C4's baseline).
BASELINE_GEOMETRY = (
    "b71fcbcf21ce4584a8f6cb982b1d6a47235d4137aed8da7d1eb48942f5815d9d"
)

ISLAND_PARTS = 10
ISLAND_NETS = 26

_CACHE: dict[bool, tuple] = {}


def _island(long_values: bool):
    """``(result, spec, presentation, book)`` for the 547A mcu island."""
    if long_values not in _CACHE:
        circuit_payload = copy.deepcopy(m547._circuit())
        presentation_payload = copy.deepcopy(m547._presentation())
        if long_values:
            for part in circuit_payload["parts"]:
                if part["id"] in LONG_VALUES:
                    part["value"] = LONG_VALUES[part["id"]]
        circuit, presentation = _module_view(circuit_payload, presentation_payload)
        book = _profiles()
        _CACHE[long_values] = (
            dc.compile(circuit, presentation, book), circuit, presentation, book,
        )
    return _CACHE[long_values]


def test_the_long_value_island_draws_at_the_seat_pitch():
    """548C6 closed this gap: the island now draws, and the seats are still the
    ladder's own pitch — the row is held by the branches' **line** coordinates,
    not by spending the escape distance `near` measures."""
    result, spec, _presentation, _book = _island(True)

    assert len(spec.parts) == ISLAND_PARTS
    assert len(spec.nets) == ISLAND_NETS

    assert result.ok, result.render_failures()
    assert len(result.candidates) == 1
    plan = result.candidates[0]
    assert plan.geometry_sha256()


def test_the_long_value_row_and_the_neighbouring_part_both_print_whole():
    """The two objects the 548C5 refusal named — `'Red LED 2.0 V 20 mA 0603'` and
    `parts[D2]` — are now separated by the seat instead of overlapped: the row is
    printed character for character, D2 is placed, and the readability gate has
    no hard violation. The pair is kept by name so this file still fails first if
    the row is shortened, wrapped or printed across the neighbour again."""
    result, spec, presentation, book = _island(True)
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    row = next(part.value for part in spec.parts if part.id == "D1")
    assert row == "Red LED 2.0 V 20 mA 0603"
    assert [text.text for text in plan.texts if text.kind == "value"].count(row) == 1
    assert plan.part("D2") is not None
    checked = rd.check(plan, spec, presentation, book)
    assert [item.render() for item in checked.hard_violations] == []


def test_the_unrenamed_island_has_not_moved():
    """The surface change above is the only thing that differs: the page that
    keeps its short value rows is byte-for-byte the drawing it was."""
    result, spec, _presentation, _book = _island(False)
    assert result.ok, result.render_failures()
    assert len(result.candidates) == 1
    plan = result.candidates[0]
    assert plan.geometry_sha256() == BASELINE_GEOMETRY, (
        "the unrenamed 547A island moved: " + plan.geometry_sha256())
    assert sorted(part.id for part in spec.parts) == sorted(m547._MCU_PARTS)
