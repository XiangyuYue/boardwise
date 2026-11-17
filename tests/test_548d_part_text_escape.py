"""548D3D-H4：本件文字避开**本件**水平引脚的首段逃逸带（合同验收）。

任务书：`tasks/548d_part_text_escape.md`；真实几何与根因：
`evidence/548D/host-binding/h3/pin48-geometry.md` §5–§7（U1 自己的 ``U1`` 文字行
横在右列引脚的 ``FLAG_LEAD`` 出线上，pin48 的 3V3 旗因此无座）。

本文件钉的是**几何事实**，不是开关：

* 未启用 ``serviceLayout.localSeats`` 的页，宿主两行仍由历史梯子决定（右侧第一档），
  而这一档**真实穿过**它自己水平脚的逃逸段——旧行为逐字节不变，缺陷也原样在场；
* 同一几何启用 ``localSeats`` 后，本件两行不与**本件**任何水平脚的首段逃逸带相交，
  两行仍在一起、仍是 ``U1``/``XU``；
* 逃逸方向读**位姿**：同一符号转 180° 后水平脚朝左，落在右侧的两行是合法的，
  与关闭开关时逐字节相同（把方向读成符号本地值就会把这两行错误挪走）；
* 180°+镜像（真实 U1 的位姿，h3 §1）下逃逸带回到右侧，两行让开；
* 带只约束**本件**文字：另一件的水平脚逃逸带横穿宿主两行时宿主两行不动，
  而那一件自己的两行让开自己的带；
* 文档声明的 ``partTexts`` 侧仍先试：侧在带上时让出的是一档（仍留在声明侧），
  侧不在带上时与历史答案逐字节相同。

逃逸带由本文件自己从符号脚（``direction``）与 plan 的位姿用
``core.geometry.transform_point`` 复算，长度取编译器自己的 :data:`FLAG_LEAD`，
横向余量取 :data:`FLAG_CLEARANCE`（旗与导线之间的既有余量）；不读实现的私有函数
当期望。**不测什么**：不构造 ``panelGroups`` 页，不跑整页 compile（那是实现者的
real64 证据），不钉 ladder 的具体档位序号。
"""

from __future__ import annotations

import copy
import math

import test_548d_cross_side_host as h3

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile, SymbolPose
from boardwise.engines import drawcompiler as dc

PROV = h3.PROV
XU_BODY = (-60.0, -40.0, 60.0, 60.0)
#: The clearance a flag keeps from a wire; the corridor the rows must leave free.
BAND_HALF = dc.FLAG_CLEARANCE

IDENTITY = {"U1": SymbolPose(0, False), "R1": SymbolPose(0, False),
            "R2": SymbolPose(0, False)}
TURNED = {"U1": SymbolPose(180, False), "R1": SymbolPose(0, False),
          "R2": SymbolPose(0, False)}
MIRRORED = {"U1": SymbolPose(180, True), "R1": SymbolPose(0, False),
            "R2": SymbolPose(0, False)}
APART = {"U1": (0.0, 0.0), "R1": (85.0, 42.0), "R2": (110.0, -10.0)}


# ------------------------------------------------------------------ 夹具


def _book() -> dict:
    """The host with **only** right-hand horizontal pins, plus a vertical R1.

    The host's rows therefore have exactly one horizontal side to fight with, so
    "kept clear" vs "printed across" is a statement about one corridor; the pins
    sit on the two row centres (17 / 3) so the historical right-side row really
    does lie inside them.
    """
    return {
        "XU": SymbolProfile.from_dict(copy.deepcopy(h3._symbol(
            "XU", XU_BODY,
            [h3._pin("SIGA", [70.0, 17.0], "right"),
             h3._pin("SIGB", [70.0, 3.0], "right"),
             h3._pin("NC", [70.0, 47.0], "right"),
             h3._pin("SIGC", [70.0, -23.0], "right")]))),
        "RY": SymbolProfile.from_dict(copy.deepcopy(h3._symbol(
            "RY", [-10.5, -4.5, 10.5, 4.5],
            [h3._pin("1", [0.0, 20.0], "up"),
             h3._pin("2", [0.0, -20.0], "down")]))),
        # a three-pin neighbour (wiper tied to one end), so the page keeps one
        # ordinary ladder-seated part besides the core: a two-foot branch would
        # be a service cell and its rows would never reach the ladder at all.
        "RX": SymbolProfile.from_dict(copy.deepcopy(h3._symbol(
            "RX", [-10.5, -4.5, 10.5, 4.5],
            [h3._pin("1", [-20.0, 0.0], "left"),
             h3._pin("2", [20.0, 0.0], "right"),
             h3._pin("3", [0.0, -20.0], "down")]))),
        "PWR-3V3": SymbolProfile(
            symbol_ref="PWR-3V3", title="PWR-3V3",
            body=(-6.0, 0.0, 6.0, 18.0), pins=[]),
        "PWR-GND": SymbolProfile(
            symbol_ref="PWR-GND", title="PWR-GND",
            body=(-10.0, 0.0, 10.0, -19.0), pins=[]),
    }


def _circuit(neighbour: bool = False) -> CircuitSpec:
    parts = [h3._part("U1", "XU", "XU"), h3._part("R1", "RY", "10k")]
    nets = [
        h3._net("3V3", "power", ["U1.SIGA", "U1.NC"]),
        h3._net("GND", "gnd", ["U1.SIGB", "R1.2"]),
        h3._net("BOOT0", "signal", ["U1.SIGC", "R1.1"]),
    ]
    if neighbour:
        parts.append(h3._part("R2", "RX", "3p"))
        nets = [
            h3._net("3V3", "power", ["U1.SIGA", "U1.NC"]),
            h3._net("GND", "gnd", ["U1.SIGB", "R1.2"]),
            h3._net("BOOT0", "signal", ["U1.SIGC", "R1.1", "R2.1"]),
            h3._net("SENSE", "signal", ["R2.2", "R2.3"]),
        ]
    return CircuitSpec.from_dict({"parts": parts, "nets": nets})


def _spec(local_seats: bool, stated=None, neighbour: bool = False):
    parts = ["U1", "R1", "R2"] if neighbour else ["U1", "R1"]
    body = {
        "grammarRef": "ic-periphery",
        "modules": [{"id": "host", "parts": parts, "role": "host island",
                     "grammarRef": "ic-periphery", "core": "U1"}],
        "serviceLayout": {"pinGap": 30, "localSeats": local_seats},
    }
    if stated:
        body["partTexts"] = dict(stated)
    return PresentationSpec.from_dict(body)


def _context(local_seats: bool, stated=None, neighbour: bool = False) -> dc._Context:
    """The prepared compile context, through the ladder's own entries."""
    circuit = _circuit(neighbour)
    spec = _spec(local_seats, stated, neighbour)
    book = _book()
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, spec, circuit)
    prepared = dc._prepare(
        circuit, spec, binding, book, dc.CompileBudget(max_candidates=4))
    assert prepared.context is not None, [f.detail for f in prepared.failures]
    return prepared.context


# --------------------------------------------------------------- 独立几何


def _layout(ctx, poses, neighbour: bool = False):
    """Run the text pass on one placement and hand back its rows (real boxes)."""
    origins = {"U1": APART["U1"], "R1": APART["R1"]}
    placed_poses = {"U1": poses["U1"], "R1": poses["R1"]}
    if neighbour:
        origins["R2"] = APART["R2"]
        placed_poses["R2"] = poses["R2"]
    placed = dc._Placement(origins=origins, poses=placed_poses)
    occupied, walls = dc._seat_first_text_inputs(ctx, placed)
    texts, failure = dc._part_texts(ctx, placed, occupied, walls)
    assert failure is None, (failure.category, failure.detail)
    return placed, texts


def _rows(texts, part_id: str) -> list[tuple[str, str, tuple[float, ...]]]:
    rows = [(item.kind, item.text, item.bbox)
            for item in texts if item.part_id == part_id]
    assert rows, f"no text rows for {part_id!r}"
    return rows


def _part_box(ctx, placed, part_id: str):
    return dc._part_box(
        ctx.profile(part_id), placed.poses[part_id], placed.origins[part_id])


def _escape_bands(ctx, placed, part_id: str):
    """``(pin, start, end)`` for each **horizontal** pin's first escape run.

    Derived here from the symbol's own ``direction`` and the plan's pose — the
    same two facts the drawing is made from — with the compiler's own
    :data:`~boardwise.engines.drawcompiler.FLAG_LEAD` as the run length. A pin
    whose posed direction is vertical states no corridor the rows travel along
    and is left out, which is the contract's "horizontal pins" clause.
    """
    profile = ctx.profile(part_id)
    pose, origin = placed.poses[part_id], placed.origins[part_id]
    bands = []
    for pin in profile.pins:
        unit = {"left": (-1.0, 0.0), "right": (1.0, 0.0),
                "up": (0.0, 1.0), "down": (0.0, -1.0)}[pin.direction]
        tip = transform_point(pin.tip[0], pin.tip[1], rotation=pose.rotation,
                               mirror=pose.mirror, ox=origin[0], oy=origin[1])
        ahead = transform_point(pin.tip[0] + unit[0], pin.tip[1] + unit[1],
                                rotation=pose.rotation, mirror=pose.mirror,
                                ox=origin[0], oy=origin[1])
        dx, dy = ahead[0] - tip[0], ahead[1] - tip[1]
        span = math.hypot(dx, dy) or 1.0
        dx, dy = dx / span, dy / span
        if abs(dx) <= abs(dy):
            continue
        east = 1.0 if dx > 0.0 else -1.0
        bands.append((pin.number, (tip[0], tip[1]),
                      (tip[0] + east * dc.FLAG_LEAD, tip[1])))
    return bands


def _crosses(box, band, half: float = BAND_HALF) -> bool:
    """Does the row share area with the run's corridor?

    ``half`` is the clearance **across** the run only: a row beyond the run's far
    end is not on it (the flag's own glyph lives there, not the run).
    """
    _pin, (ax, ay), (bx, by) = band
    assert abs(ay - by) <= 1e-9
    corridor = (min(ax, bx), ay - half, max(ax, bx), ay + half)
    return dc._overlaps(box, corridor)


def _crossings(rows, bands):
    return sorted({
        (kind, pin)
        for kind, _text, box in rows
        for pin, _a, _b in bands
        if _crosses(box, (pin, _a, _b))
    })


def _side(box, part) -> str:
    if box[0] >= part[2]:
        return "right"
    if box[2] <= part[0]:
        return "left"
    if box[1] >= part[3]:
        return "above"
    return "below"


def _legacy_rows(ctx, placed, part_id: str, side: str, rung: int = 1):
    """The documented ladder answer for one side/rung — computed, not read back."""
    box = _part_box(ctx, placed, part_id)
    lines = [text for _kind, text in dc._part_lines(ctx, part_id)]
    return dc._line_boxes(box, lines, side, rung)


def _boxes(rows):
    return [tuple(box) for _kind, _text, box in rows]


# =========================== 1. 旧页：历史答案，且它真的压在逃逸带上


def test_the_old_page_still_prints_the_host_rows_across_its_own_escape():
    """关闭 `localSeats`：右侧第一档，逐字节是历史答案；它确实穿过 SIGA/SIGB 的逃逸段。"""
    ctx = _context(local_seats=False)
    placed, texts = _layout(ctx, IDENTITY)
    rows = _rows(texts, "U1")

    assert [(kind, text) for kind, text, _box in rows] == [
        ("reference", "U1"), ("value", "XU")]
    assert _boxes(rows) == [tuple(box) for box in _legacy_rows(
        ctx, placed, "U1", "right", 1)]
    assert _crossings(rows, _escape_bands(ctx, placed, "U1")) == [
        ("reference", "SIGA"), ("value", "SIGB")]


# ====================== 2. localSeats 页：本件两行让开本件自己的逃逸带


def test_local_seats_keeps_the_host_rows_out_of_its_own_escape():
    ctx = _context(local_seats=True)
    placed, texts = _layout(ctx, IDENTITY)
    rows = _rows(texts, "U1")

    assert [(kind, text) for kind, text, _box in rows] == [
        ("reference", "U1"), ("value", "XU")]
    assert _crossings(rows, _escape_bands(ctx, placed, "U1")) == []
    assert _boxes(rows) != [tuple(box) for box in _legacy_rows(
        ctx, placed, "U1", "right", 1)], (
        "the rows were left where the old ladder puts them; this claim is stale")
    # both rows are one block on one side, not scattered around the body
    part = _part_box(ctx, placed, "U1")
    assert len({_side(box, part) for _kind, _text, box in rows}) == 1


# ================= 3. 方向读位姿：转 180° 后带在左，右侧两行保持不动


def test_the_escape_follows_the_pose_not_the_symbol_frame():
    for local_seats in (False, True):
        ctx = _context(local_seats=local_seats)
        placed, texts = _layout(ctx, TURNED)
        bands = _escape_bands(ctx, placed, "U1")
        assert bands, "the turned host states no horizontal escape run"
        assert all(end[0] < start[0] for _pin, start, end in bands), bands
        rows = _rows(texts, "U1")
        assert _boxes(rows) == [tuple(box) for box in _legacy_rows(
            ctx, placed, "U1", "right", 1)], (
            f"localSeats={local_seats}: the rows moved although the band is "
            "on the other side")
        assert _crossings(rows, bands) == []


# ================== 4. 转 180°+镜像（真实 U1 的位姿）：带回到右侧


def test_a_mirrored_pose_brings_the_band_back_and_the_rows_step_off():
    off = _context(local_seats=False)
    placed_off, texts_off = _layout(off, MIRRORED)
    rows_off = _rows(texts_off, "U1")
    assert _crossings(rows_off, _escape_bands(off, placed_off, "U1")) == [
        ("reference", "SIGB"), ("value", "SIGA")]
    assert _boxes(rows_off) == [tuple(box) for box in _legacy_rows(
        off, placed_off, "U1", "right", 1)]

    on = _context(local_seats=True)
    placed_on, texts_on = _layout(on, MIRRORED)
    rows_on = _rows(texts_on, "U1")
    assert _crossings(rows_on, _escape_bands(on, placed_on, "U1")) == []


# =========== 5. 带只约束本件：别件的带横穿本行，本行不动；别件让开自己的带


def test_only_the_part_that_owns_the_pin_gives_way():
    ctx = _context(local_seats=True, neighbour=True)
    placed, texts = _layout(ctx, TURNED, neighbour=True)

    host_rows = _rows(texts, "U1")
    assert _boxes(host_rows) == [tuple(box) for box in _legacy_rows(
        ctx, placed, "U1", "right", 1)], (
        "the host's own rows moved: another part's escape band reached the "
        "page-wide obstacles")
    neighbour_bands = _escape_bands(ctx, placed, "R2")
    reached = [
        pin for pin, _a, _b in neighbour_bands
        if any(_crosses(box, (pin, _a, _b)) for _kind, _text, box in host_rows)
    ]
    assert reached == ["1"], (
        "the probe no longer places the neighbour's escape run across the "
        f"host's rows: {reached}")

    neighbour_rows = _rows(texts, "R2")
    assert _crossings(neighbour_rows, neighbour_bands) == [], (
        "the neighbour's own rows are printed across its own escape run")


# ============ 6. 明确 partTexts：侧先试，带只让出一档，不改声明侧


def test_a_stated_side_is_still_tried_first_and_only_the_rung_gives_way():
    stated = {"U1": "left"}
    off = _context(local_seats=False, stated=stated)
    placed_off, texts_off = _layout(off, TURNED)
    rows_off = _rows(texts_off, "U1")
    assert _boxes(rows_off) == [tuple(box) for box in _legacy_rows(
        off, placed_off, "U1", "left", 1)]
    assert _crossings(rows_off, _escape_bands(off, placed_off, "U1")) == [
        ("reference", "SIGB"), ("value", "SIGA")]

    on = _context(local_seats=True, stated=stated)
    placed_on, texts_on = _layout(on, TURNED)
    rows_on = _rows(texts_on, "U1")
    assert _crossings(rows_on, _escape_bands(on, placed_on, "U1")) == []
    part = _part_box(ctx=on, placed=placed_on, part_id="U1")
    assert {_side(box, part) for _kind, _text, box in rows_on} == {"left"}, (
        "the stated side was abandoned instead of stepping the row out")
    assert _boxes(rows_on) != _boxes(rows_off)


def test_a_stated_side_that_does_not_meet_the_band_is_printed_unchanged():
    stated = {"U1": "right"}
    off = _context(local_seats=False, stated=stated)
    placed_off, texts_off = _layout(off, TURNED)
    rows_off = _rows(texts_off, "U1")
    assert _boxes(rows_off) == [tuple(box) for box in _legacy_rows(
        off, placed_off, "U1", "right", 1)]

    on = _context(local_seats=True, stated=stated)
    placed_on, texts_on = _layout(on, TURNED)
    assert _boxes(_rows(texts_on, "U1")) == _boxes(rows_off)
    assert _crossings(_rows(texts_on, "U1"),
                      _escape_bands(on, placed_on, "U1")) == []
