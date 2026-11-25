"""608（570-B2-2）：岛块的 bbox 必须覆盖器件**体**，不是只覆盖锚点。

`outputs/hole570/b2/REPRO.md` 的 570-B2-2 实测 `IslandBlock.bbox()` 自称
"everything the block draws"，但 parts 只贡献 `(part.x, part.y)` 一个退化点：
`power_entry` 4 件里 **3 件**（C115 / CN1 / D1）的姿态后体盒落在自己 block 的 bbox
之外，packer 的 keep-out 结算与 `_page_floor` 的 x 区间因此看不见器件体。
`flyback` 19 件体盒当前全在 bbox 内，所以它是**几何不变对照**：本批修完之后
它的 floor、页框、每岛 bbox 必须逐值不动。

本文件钉五件事：

1. **先红断言**：每个 block 的每个 `profile.body is not None` 的器件，其
   `pose_box(body, rotation, mirror, x, y)` 被所属 `block.bbox()` 包含
   （修前 power_entry 3 件不成立），且 `PackedPage.bbox()` 一并覆盖。
2. **一一对应**：`part_boxes` 与 `parts` 等长同序，每个条目就是该器件自己的体盒；
   body=None 的器件保留锚点退化盒，不错位。
3. **平移**：`translated(dx, dy)` 对每盒施加同一 dx/dy，**不重算姿态**
   （用非栅格 delta 证明没有 snap / 没有二次 pose）。
4. **负控**：flyback 的 floor / 页框 / 每岛 bbox 与 570-B2 读到的基线逐值一致，
   且每岛 bbox 等于独立重算的"块内所有对象"并集——修 bbox 不是"改所有几何"。
5. **旧行为**：手工构造/无 part_boxes 的块仍按锚点量，空块仍是 `(0,0,0,0)`，
   texts/labels/segments/power_boxes 的覆盖不回归。

判定全部用本文件自写的 `_in_box`，不从 `IslandBlock.bbox()` 自证：体盒由
`symbolprofile.pose_box` 从 `LayoutPart` 的 x/y/rotation/mirror 与 library 的
profile.body 独立重算。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core import pageframe, symbolprofile
from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolPin, SymbolProfile
from boardwise.engines import islandlayout as il

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"

#: The sheet the island page is compiled onto — the same one 570-B2 measured on.
SHEET = (0.0, 0.0, 1170.0, 825.0)
#: ``570-B2`` readings (`outputs/hole570/b2/readings/oracle_rerun.json`), i.e. the
#: page **before** this batch: the flyback control has to keep every one of them.
FLYBACK_FLOOR = 190.0
FLYBACK_PAGE_BBOX = (
    20.535064572425824, 190.0, 1023.1874485165794, 570.5,
)
FLYBACK_BLOCK_BBOX = {
    "primary": (20.535064572425824, 190.0, 264.83493193717277, 460.0),
    "secondary": (799.5, 190.0, 1023.1874485165794, 315.5),
    "feedback": (342.35405235602093, 465.5, 718.7121116928447, 570.5),
    "bridge": (365.4840209424084, 190.0, 704.4450261780105, 275.0),
    "control": (22.593256544502623, 500.0, 259.4450261780105, 569.5),
}

PROV = "verified_recipe"


# ------------------------------------------------------------------ fixtures


def _library(stem: str) -> dict[str, SymbolProfile]:
    payload = json.loads(
        (SPECS / f"{stem}.library.json").read_text(encoding="utf-8")
    )
    book: dict[str, SymbolProfile] = {}
    for entry in payload["profiles"]:
        profile = SymbolProfile.from_dict(entry)
        book[profile.symbol_ref] = profile
    return book


def _triplet(stem: str):
    return (
        CircuitSpec.load(SPECS / f"{stem}.circuit.json"),
        PresentationSpec.load(SPECS / f"{stem}.presentation.json"),
        _library(stem),
    )


def _page(stem: str) -> tuple[il.PackedPage, dict[str, SymbolProfile]]:
    """The island page exactly as the compiler packs it onto the stated sheet."""
    circuit, presentation, book = _triplet(stem)
    page = il.island_page(
        circuit, presentation, book,
        page_budget=il.PageBudget(
            page_box=SHEET,
            keepouts=tuple(pageframe.title_block_keepouts(SHEET)),
        ),
    )
    return page, book


# ------------------------------------------------------- independent readings


def _in_box(inner, outer, tol: float = 1e-9) -> bool:
    return (
        outer[0] - tol <= inner[0] and outer[1] - tol <= inner[1]
        and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol
    )


def _body(part, profile) -> tuple[float, float, float, float] | None:
    """The box a placed part's body occupies — recomputed, never read off the block."""
    if profile.body is None:
        return None
    return symbolprofile.pose_box(
        profile.body, rotation=part.rotation, mirror=part.mirror,
        ox=part.x, oy=part.y,
    )


def _bodies(block, book) -> list[tuple[str, tuple[float, float, float, float]]]:
    out = []
    for part in block.parts:
        body = _body(part, book[part.symbol_ref])
        if body is not None:
            out.append((part.part_id, body))
    return out


def _drawn_box(block, book):
    """Everything the block draws, unioned — bodies, rows, names, flags, wires."""
    boxes = [tuple(text.bbox) for text in block.texts]
    boxes.extend(tuple(label.bbox) for label in block.labels)
    boxes.extend(tuple(box) for box in block.power_boxes)
    boxes.extend(box for _pid, box in _bodies(block, book))
    for part in block.parts:
        boxes.append((part.x, part.y, part.x, part.y))
    for segment in block.segments:
        boxes.extend((x, y, x, y) for x, y in segment.points)
    return (
        min(box[0] for box in boxes), min(box[1] for box in boxes),
        max(box[2] for box in boxes), max(box[3] for box in boxes),
    )


# ================================== 1. the hole itself (red before this batch)


def test_power_entry_bodies_fit_their_own_block_bbox() -> None:
    """570-B2-2's own reproduction: three of four bodies outside their block.

    Before this batch `bbox()` let a part contribute its anchor point only, so
    `C115`, `CN1` and `D1` hung outside the box the packer treats as the block's
    footprint.  The floor and the keep-out arithmetic read that box, so "packer
    says no conflict" did not mean "the bodies were looked at".
    """
    page, book = _page("power_entry_xt30")
    assert len(page.blocks) == 1
    block = page.blocks[0]
    bodies = _bodies(block, book)
    assert len(bodies) == 4, "the fixture must carry four bodies to measure four"
    outside = [
        (part_id, body) for part_id, body in bodies
        if not _in_box(body, block.bbox())
    ]
    assert outside == [], (
        "every body must be inside its own block's bbox; outside: "
        f"{[(pid, [round(v, 1) for v in box]) for pid, box in outside]} "
        f"(block bbox {[round(v, 1) for v in block.bbox()]})"
    )
    page_box = page.bbox()
    assert all(_in_box(body, page_box) for _pid, body in bodies), (
        "PackedPage.bbox() must carry the bodies up from the blocks"
    )


def test_part_boxes_are_one_per_part_in_block_parts_order() -> None:
    """`part_boxes` is parallel to `parts`: same length, same order, the body itself.

    Re-priced per part from the library, so a list that slipped one entry (a
    body-less part dropped, a `sorted()` order mismatch) shows up as a wrong box
    against the part it is stored beside.
    """
    for stem in ("power_entry_xt30", "flyback_uc3845"):
        page, book = _page(stem)
        for block in page.blocks:
            assert len(block.part_boxes) == len(block.parts), block.island_id
            for part, stored in zip(block.parts, block.part_boxes):
                body = _body(part, book[part.symbol_ref])
                if body is None:
                    assert tuple(stored) == pytest.approx(
                        (part.x, part.y, part.x, part.y)
                    ), f"{stem}/{block.island_id}/{part.part_id}"
                    continue
                assert tuple(stored) == pytest.approx(body), (
                    f"{stem}/{block.island_id}/{part.part_id}: stored "
                    f"{tuple(stored)} is not the body {body}"
                )


# ====================================== 2. the flyback control: nothing moves


def test_flyback_geometry_is_unchanged_by_the_body_boxes() -> None:
    """The negative control 570-B2 handed us: 19 bodies already inside, 0 moving.

    Every number here is what 570-B2 read **before** this batch.  If a body box
    changes a flyback island's footprint, the fix has grown past "the block draws
    its bodies" and into re-laying-out the page.
    """
    page, book = _page("flyback_uc3845")
    assert page.floor == pytest.approx(FLYBACK_FLOOR)
    assert tuple(page.bbox()) == pytest.approx(FLYBACK_PAGE_BBOX)
    assert page.keepout_conflicts == []
    assert {block.island_id for block in page.blocks} == set(FLYBACK_BLOCK_BBOX)
    total_bodies = 0
    for block in page.blocks:
        assert tuple(block.bbox()) == pytest.approx(
            FLYBACK_BLOCK_BBOX[block.island_id]
        ), block.island_id
        bodies = _bodies(block, book)
        total_bodies += len(bodies)
        assert [pid for pid, body in bodies
                if not _in_box(body, block.bbox())] == []
        # The bbox is the union of everything the block draws: on the control the
        # bodies were already inside that union, so adding them adds no extent.
        assert tuple(block.bbox()) == pytest.approx(_drawn_box(block, book))
    assert total_bodies == 19


# ===================================================== 3. moving the block whole


def test_translated_moves_every_part_box_by_the_same_delta() -> None:
    """Rigid means rigid: the same non-grid delta, applied — never re-posed."""
    page, book = _page("power_entry_xt30")
    block = page.blocks[0]
    dx, dy = 137.5, -41.25
    moved = block.translated(dx, dy)
    assert len(moved.part_boxes) == len(block.part_boxes)
    for before, after in zip(block.part_boxes, moved.part_boxes):
        assert tuple(after) == pytest.approx(
            (before[0] + dx, before[1] + dy, before[2] + dx, before[3] + dy)
        )
    assert tuple(moved.bbox()) == pytest.approx(
        (block.bbox()[0] + dx, block.bbox()[1] + dy,
         block.bbox()[2] + dx, block.bbox()[3] + dy)
    )
    outside = [
        part_id for part_id, body in _bodies(moved, book)
        if not _in_box(body, moved.bbox())
    ]
    assert outside == [], f"after the move these bodies fell out: {outside}"


# ================================================ 4. the old reading, unchanged


def test_a_block_built_by_hand_is_measured_by_its_anchors_as_before() -> None:
    """No library, no `part_boxes`: the block measures exactly what it did."""
    block = il.IslandBlock(
        island_id="hand", role="", anchor="U1",
        parts=[
            il.LayoutPart(part_id="U1", symbol_ref="IC", x=10.0, y=20.0),
            il.LayoutPart(part_id="R1", symbol_ref="R", x=60.0, y=70.0),
        ],
        segments=[il.LayoutSegment(net="S", points=[(10.0, 20.0), (5.0, 70.0)])],
    )
    assert block.bbox() == (5.0, 20.0, 60.0, 70.0)
    assert block.part_boxes == []
    assert il.IslandBlock(
        island_id="empty", role="", anchor="U1",
    ).bbox() == (0.0, 0.0, 0.0, 0.0)


def test_texts_labels_flags_and_wires_still_count() -> None:
    """530A's coverage is not traded away for the bodies."""
    block = il.IslandBlock(
        island_id="hand", role="", anchor="U1",
        parts=[
            il.LayoutPart(part_id="U1", symbol_ref="IC", x=0.0, y=0.0),
            il.LayoutPart(part_id="R1", symbol_ref="R", x=10.0, y=0.0),
        ],
        part_boxes=[
            (-5.0, -5.0, 5.0, 5.0),
            (5.0, -5.0, 15.0, 5.0),
        ],
        texts=[il.LayoutText(kind="value", text="1k", bbox=(-90.0, 20.0, -60.0, 30.0))],
        labels=[il.LayoutLabel(net="S", text="S", bbox=(40.0, 40.0, 60.0, 50.0))],
        power_boxes=[(0.0, -80.0, 20.0, -60.0)],
        segments=[il.LayoutSegment(net="S", points=[(100.0, 0.0), (100.0, -30.0)])],
    )
    assert block.bbox() == (-90.0, -80.0, 100.0, 50.0)


# ==================================== 5. a part with no body never slips the list


def _ic(ref: str, pins: int) -> SymbolProfile:
    return SymbolProfile(
        symbol_ref=ref, title=ref, body=(-30.0, -40.0, 30.0, 40.0),
        pins=[
            SymbolPin(
                number=str(index + 1), tip=(-50.0, 30.0 - 10.0 * index),
                name=f"P{index + 1}", direction="left", length=10.0,
            )
            for index in range(pins)
        ],
    )


def _pins_only(ref: str = "R-NOBODY") -> SymbolProfile:
    """A profile whose drawn extent the parser never found: pins, no body."""
    return SymbolProfile(
        symbol_ref=ref, title=ref, body=None,
        pins=[
            SymbolPin(number="1", tip=(0.0, 50.0), name="1", direction="up",
                      length=10.0),
            SymbolPin(number="2", tip=(0.0, -50.0), name="2", direction="down",
                      length=10.0),
        ],
    )


def _part(part_id: str, symbol: str, value: str = "") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value, "provenance": PROV}


def _net(net_id: str, cls: str, members: list[str]) -> dict:
    return {
        "id": net_id, "class": cls, "members": list(members),
        "provenance": PROV,
    }


def test_a_part_without_a_body_keeps_its_anchor_and_the_lists_line_up() -> None:
    """`body is None` is not skipped: it takes the anchor box its bbox already had.

    Dropping the entry would shift every later box onto the wrong part, which is
    the failure mode a one-for-one list exists to make impossible.
    """
    book = {"IC8": _ic("IC8", 4), "R-NOBODY": _pins_only()}
    circuit = CircuitSpec.from_dict({
        "parts": [_part("U1", "IC8", "MCU"), _part("R1", "R-NOBODY", "1k")],
        "nets": [_net("SIG", "signal", ["U1.1", "R1.1"])],
    })
    presentation = PresentationSpec.from_dict({
        "grammarRef": "flyback",
        "modules": [{"id": "main", "parts": ["U1", "R1"], "role": "tube"}],
        "islands": [{"id": "a", "role": "", "parts": ["U1", "R1"]}],
    })
    block = il.layout_island(
        circuit, il.island_subgraphs(circuit, presentation)[0], book,
    )
    assert len(block.part_boxes) == len(block.parts) == 2
    for part, stored in zip(block.parts, block.part_boxes):
        if part.part_id == "R1":
            assert tuple(stored) == pytest.approx(
                (part.x, part.y, part.x, part.y)
            ), "the body-less part must keep its anchor, not a neighbour's box"
        else:
            assert tuple(stored) == pytest.approx(
                symbolprofile.pose_box(
                    book["IC8"].body, rotation=part.rotation,
                    mirror=part.mirror, ox=part.x, oy=part.y,
                )
            )
    assert _in_box(block.part_boxes[0], block.bbox())
