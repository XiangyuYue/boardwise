"""548D3X §30B：页级二维排布器（纯矩形几何，不碰电路语义）。

这一批只钉排布器的合同，不把它接到 pagecompiler、不重画整页，也不宣称整页改善。
测试要证明的是六件事：

1. **二维回填不是换名字的行架**：左侧高框 + 右侧参差短框的夹具里，短框各按自己
   的真实高度叠放，四只短框占满 240×400 页的下半/右列；按最大行高铺的行架至少
   要 360+40+360 = 760 高，这个夹具它根本放不下。
2. **净距就是检查器的净距**：`frame_gap` 是逐轴 `max(...,0)` 后 `hypot`；恰 40 可过，
   39.5 不可过，且失败与"预算截断"分开报。
3. **吸附只许移远**：97 宽的框 + 40 隙给出 137 的原始角点，吸附到 140，净距变成 43；
   吸附后再验一遍页面/keepout/相邻框，绝不靠缩距换取落位。
4. **刚性**：宽高原样、不旋转、不缩放；`origin` 就是把本地 frame 平移到最终 frame 的
   那个平移量；attach 已合成的占位框按一只矩形参与，不会被再拆开。
5. **封闭输入**：未知/重复/缺失 order、非法框、非法页、非法 keepout、非法参数一律
   `rejected`，带具名 code，不抛异常、不留半张重叠的图。
6. **确定性**：与映射插入顺序无关；两个不同 `PYTHONHASHSEED` 的子进程给出逐字节
   相同的 JSON。

夹具全部是手写数字，不读 SmartMedicineBox、不读生产 presentation、不接 consumer。
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from boardwise.engines import pagepacking
from boardwise.engines.pagepacking import (
    FAILURE_BUDGET_EXHAUSTED,
    FAILURE_DUPLICATE_ORDER,
    FAILURE_INVALID_ARGUMENT,
    FAILURE_INVALID_FRAME,
    FAILURE_INVALID_KEEPOUT,
    FAILURE_INVALID_ORDER,
    FAILURE_INVALID_PAGE,
    FAILURE_MISSING_ORDER,
    FAILURE_UNKNOWN_ORDER,
    FAILURE_UNSAT,
    GAP_EPSILON,
    STATUS_PACKED,
    STATUS_REJECTED,
    STATUS_TRUNCATED,
    STATUS_UNSAT,
    frame_gap,
    pack_frames,
)

EPS = 1e-9

# 548D page-layout README 的真实 frame 数字（只当数字用，不接生产）：
# MCU 743×604、WiFi 590.5×200、env+bmp280 合成框 564×169。
PAGE = (0.0, 0.0, 1170.0, 825.0)

TALL_LEFT: dict[str, tuple[float, float, float, float]] = {
    "left": (0.0, 0.0, 100.0, 360.0),
    "short_a": (0.0, 0.0, 100.0, 80.0),
    "short_b": (0.0, 0.0, 100.0, 80.0),
    "short_c": (0.0, 0.0, 100.0, 80.0),
    "short_d": (0.0, 0.0, 100.0, 40.0),
}
TALL_LEFT_ORDER = ("left", "short_a", "short_b", "short_c", "short_d")


def _assert_inside(result, page=PAGE) -> None:
    for name, box in result.frames.items():
        assert box[0] >= page[0] - EPS, name
        assert box[1] >= page[1] - EPS, name
        assert box[2] <= page[2] + EPS, name
        assert box[3] <= page[3] + EPS, name


def _assert_pairwise_gap(result, gap=40.0) -> None:
    names = list(result.frames)
    for index, first in enumerate(names):
        for second in names[index + 1:]:
            distance = frame_gap(result.frames[first], result.frames[second])
            assert distance > gap - GAP_EPSILON, (first, second, distance)


def test_tall_left_and_ragged_right_is_two_dimensional():
    """左侧高框 + 右侧四只参差短框：紧凑解只有二维回填给得出来。

    行架（每行用最大行高）在这里需要 360+40+360 = 760 高；实际解 240×400，
    四只短框 y 为 0/120/240/360，各行高度就是自己的 80/80/80/40。
    """

    snapshot = dict(TALL_LEFT)
    result = pack_frames(TALL_LEFT, TALL_LEFT_ORDER, (0.0, 0.0, 240.0, 400.0))

    assert TALL_LEFT == snapshot  # 输入不被改写
    assert result.status == STATUS_PACKED
    assert result.ok and not result.truncated
    assert tuple(result.frames) == TALL_LEFT_ORDER
    assert result.frames == {
        "left": (0.0, 0.0, 100.0, 360.0),
        "short_a": (140.0, 0.0, 240.0, 80.0),
        "short_b": (140.0, 120.0, 240.0, 200.0),
        "short_c": (140.0, 240.0, 240.0, 320.0),
        "short_d": (140.0, 360.0, 240.0, 400.0),
    }
    assert (result.width, result.height) == (240.0, 400.0)
    _assert_inside(result, (0.0, 0.0, 240.0, 400.0))
    _assert_pairwise_gap(result)
    # 四只短框各占一行，行高不同 —— 这正是行架表达不了的形状。
    assert {result.frames[name][1] for name in TALL_LEFT_ORDER[1:]} == {0.0, 120.0, 240.0, 360.0}
    # short_b 的 x 来自 left 的右边线、y 来自 short_a 的顶边线：候选是两只不同
    # 框边线的交叉，不是一行统一的槽位。
    assert result.frames["short_b"][:2] == (
        result.frames["left"][2] + 40.0,
        result.frames["short_a"][3] + 40.0,
    )
    # 每只框的宽高原样（刚性），且都落在 5 的栅格上。
    for name, local in TALL_LEFT.items():
        box = result.frames[name]
        assert (box[2] - box[0], box[3] - box[1]) == (local[2] - local[0], local[3] - local[1])
        assert box[0] % 5.0 == 0.0 and box[1] % 5.0 == 0.0


def test_gap_exactly_40_is_legal():
    frames = {"a": (0.0, 0.0, 100.0, 100.0), "b": (0.0, 0.0, 100.0, 100.0)}

    result = pack_frames(frames, ("a", "b"), (0.0, 0.0, 240.0, 100.0), grid=0.5)

    assert result.ok
    assert result.frames["a"][0] == 0.0
    assert result.frames["b"][0] == 140.0
    assert frame_gap(result.frames["a"], result.frames["b"]) == 40.0


def test_page_too_narrow_for_40_is_refused_as_page_bound():
    """页界负例：239.5 宽只容 39.5，第二框根本落不进页，未到净距判定。

    这条**不**覆盖 pair gap guard —— 主代理变异实测把 guard 改成 `if False`
    它仍然绿（候选因出界被拒）。净距 guard 的直接负例见下一条斜向用例。
    """

    frames = {"a": (0.0, 0.0, 100.0, 100.0), "b": (0.0, 0.0, 100.0, 100.0)}

    result = pack_frames(frames, ("a", "b"), (0.0, 0.0, 239.5, 100.0), grid=0.5)

    assert result.status == STATUS_UNSAT
    assert not result.ok and not result.truncated
    assert result.failure is not None and result.failure.code == FAILURE_UNSAT
    assert result.placements == ()


def test_diagonal_gap_under_40_is_refused_by_the_pair_guard(monkeypatch):
    """净距 guard 的直接负例：两框都在页内、无面积重叠，只有斜距违规。

    a=(0,0,100,100)、b 唯一候选 (110,110)：b 的框 (110,110,130,130) 在 300×300
    页内，与 a 的 x/y 都只隔 10（面积不重叠），但 frame_gap=hypot(10,10)≈14.1<40。
    候选被 monkeypatch 成唯一位置，所以唯一能拒绝它的是 pagepacking.py 的
    `if any(frame_gap(...) <= gap - GAP_EPSILON ...): continue`；该行改成
    `if False` 时本测试必须红（会 pack 出 a@(0,0)、b@(110,110)）。
    """

    calls = []

    def only_two_corners(placed, keepouts, page, gap, grid):
        calls.append(len(placed))
        return [(110.0, 110.0)] if placed else [(0.0, 0.0)]

    monkeypatch.setattr(pagepacking, "_candidates", only_two_corners)

    frames = {"a": (0.0, 0.0, 100.0, 100.0), "b": (0.0, 0.0, 20.0, 20.0)}
    result = pagepacking.pack_frames(
        frames, ("a", "b"), (0.0, 0.0, 300.0, 300.0), grid=0.0
    )

    # 前提自检：都在页内、无面积重叠、唯一违规是净距。
    assert frame_gap((0.0, 0.0, 100.0, 100.0), (110.0, 110.0, 130.0, 130.0)) == pytest.approx(
        math.sqrt(200.0)
    )
    assert calls == [0, 1]
    assert result.status == STATUS_UNSAT
    assert not result.ok and not result.truncated
    assert result.failure is not None and result.failure.code == FAILURE_UNSAT
    assert result.placements == ()


def test_grid_snap_moves_away_and_never_shrinks_gap():
    frames = {"a": (0.0, 0.0, 97.0, 100.0), "b": (0.0, 0.0, 97.0, 100.0)}

    result = pack_frames(frames, ("a", "b"), (0.0, 0.0, 300.0, 100.0), gap=40.0, grid=5.0)

    assert result.ok
    # 原始角点 97+40=137，向下吸附会变成 135（净距 38）——必须向上到 140。
    assert result.frames["b"][0] == 140.0
    assert frame_gap(result.frames["a"], result.frames["b"]) >= 40.0
    assert result.frames["b"][0] % 5.0 == 0.0


def test_page_origin_snaps_inwards_not_outwards():
    result = pack_frames(
        {"a": (0.0, 0.0, 100.0, 100.0)}, ("a",), (3.0, 0.0, 300.0, 100.0), grid=5.0
    )

    assert result.ok
    assert result.frames["a"][0] == 5.0


def test_frame_larger_than_page_is_unsat():
    result = pack_frames({"a": (0.0, 0.0, 200.0, 100.0)}, ("a",), (0.0, 0.0, 100.0, 100.0))

    assert result.status == STATUS_UNSAT
    assert result.failure is not None and result.failure.code == FAILURE_UNSAT
    assert result.placements == ()


def test_keepout_blocks_the_only_remaining_slot():
    frames = {"a": (0.0, 0.0, 100.0, 100.0), "b": (0.0, 0.0, 100.0, 100.0)}

    result = pack_frames(
        frames, ("a", "b"), (0.0, 0.0, 240.0, 100.0), keepouts=[(140.0, 0.0, 240.0, 100.0)]
    )

    assert result.status == STATUS_UNSAT
    assert result.failure is not None and result.failure.code == FAILURE_UNSAT


def test_keepout_edge_may_be_touched():
    frames = {"a": (0.0, 0.0, 100.0, 100.0), "b": (0.0, 0.0, 100.0, 100.0)}

    result = pack_frames(
        frames, ("a", "b"), (0.0, 0.0, 300.0, 100.0), keepouts=[(100.0, 0.0, 200.0, 100.0)]
    )

    assert result.ok
    xs = sorted((result.frames["a"][0], result.frames["b"][0]))
    assert xs == [0.0, 200.0]


def test_empty_input_is_an_empty_packing():
    result = pack_frames({}, (), (0.0, 0.0, 100.0, 100.0))

    assert result.status == STATUS_PACKED
    assert result.placements == () and result.frames == {}
    assert (result.width, result.height, result.nodes) == (0.0, 0.0, 0)


def test_origin_is_the_translation_of_the_local_frame():
    result = pack_frames({"a": (-10.0, -20.0, 70.0, 50.0)}, ("a",), (0.0, 0.0, 300.0, 300.0))

    assert result.ok
    assert result.frames["a"] == (0.0, 0.0, 80.0, 70.0)
    assert result.origins == {"a": (10.0, 20.0)}


def test_composed_attach_frame_is_one_rigid_box():
    # env+bmp280 已由上游合成为一个 564×169 的占位框；排布器只看见一只矩形。
    frames = {"env": (0.0, 0.0, 564.0, 169.0), "wifi": (0.0, 0.0, 590.5, 200.0)}

    result = pack_frames(frames, ("env", "wifi"), (0.0, 0.0, 1194.5, 200.0), grid=0.0)

    assert result.ok
    assert len(result.placements) == 2
    assert result.frames["env"] == (0.0, 0.0, 564.0, 169.0)
    assert result.frames["wifi"] == (604.0, 0.0, 1194.5, 200.0)
    assert frame_gap(result.frames["env"], result.frames["wifi"]) == 40.0


def test_real_1170x825_page_cannot_hold_mcu_beside_wifi():
    # README §5 的手算下界：743+40+590.5=1373.5>1170，竖叠 604+40+200=844>825。
    frames = {"mcu": (0.0, 0.0, 743.0, 604.0), "wifi": (0.0, 0.0, 590.5, 200.0)}

    result = pack_frames(frames, ("mcu", "wifi"), PAGE)

    assert result.status == STATUS_UNSAT
    assert not result.truncated
    assert result.failure is not None and result.failure.code == FAILURE_UNSAT


def test_frame_gap_is_the_page_compilers_measure():
    assert frame_gap((0.0, 0.0, 10.0, 10.0), (14.0, 0.0, 24.0, 10.0)) == 4.0
    assert frame_gap((0.0, 0.0, 10.0, 10.0), (13.0, 13.0, 23.0, 23.0)) == pytest.approx(
        math.hypot(3.0, 3.0)
    )
    assert frame_gap((0.0, 0.0, 10.0, 10.0), (5.0, 5.0, 15.0, 15.0)) == 0.0


def test_module_does_not_import_compilers_or_placement():
    import ast
    import importlib

    module = importlib.import_module("boardwise.engines.pagepacking")
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {"drawcompiler", "placement", "pagecompiler"}
    assert not {name for name in imported if name.split(".")[-1] in forbidden}


@pytest.mark.parametrize(
    ("order", "code"),
    [
        (("a", "z"), FAILURE_UNKNOWN_ORDER),
        (("a", "a"), FAILURE_DUPLICATE_ORDER),
        (("a",), FAILURE_MISSING_ORDER),
        ("ab", FAILURE_INVALID_ORDER),
        (("a", 3), FAILURE_INVALID_ORDER),
    ],
)
def test_order_refusals_are_named(order, code):
    frames = {"a": (0.0, 0.0, 10.0, 10.0), "b": (0.0, 0.0, 10.0, 10.0)}

    result = pack_frames(frames, order, (0.0, 0.0, 100.0, 100.0))

    assert result.status == STATUS_REJECTED
    assert result.failure is not None and result.failure.code == code
    assert result.placements == () and result.nodes == 0


@pytest.mark.parametrize(
    "frame",
    [
        (0.0, 0.0, 0.0, 10.0),
        (10.0, 10.0, 0.0, 0.0),
        (0.0, 0.0, 10.0),
        (0.0, 0.0, float("nan"), 10.0),
        (0.0, 0.0, float("inf"), 10.0),
        (0.0, 0.0, True, 10.0),
        "box",
    ],
)
def test_invalid_frame_is_rejected(frame):
    result = pack_frames({"a": frame}, ("a",), (0.0, 0.0, 100.0, 100.0))

    assert result.status == STATUS_REJECTED
    assert result.failure is not None and result.failure.code == FAILURE_INVALID_FRAME


def test_invalid_page_is_rejected():
    for page in [(0.0, 0.0, 0.0, 100.0), (0.0, 0.0, 100.0), "page"]:
        result = pack_frames({"a": (0.0, 0.0, 10.0, 10.0)}, ("a",), page)
        assert result.status == STATUS_REJECTED
        assert result.failure is not None and result.failure.code == FAILURE_INVALID_PAGE


def test_invalid_keepout_is_rejected():
    result = pack_frames(
        {"a": (0.0, 0.0, 10.0, 10.0)},
        ("a",),
        (0.0, 0.0, 100.0, 100.0),
        keepouts=[(0.0, 0.0, 10.0)],
    )

    assert result.status == STATUS_REJECTED
    assert result.failure is not None and result.failure.code == FAILURE_INVALID_KEEPOUT


@pytest.mark.parametrize(
    "kwargs",
    [
        {"gap": -1.0},
        {"gap": float("nan")},
        {"grid": -1.0},
        {"grid": float("inf")},
        {"max_nodes": 0},
        {"max_nodes": 1.5},
        {"max_nodes": True},
    ],
)
def test_invalid_arguments_are_rejected(kwargs):
    result = pack_frames(
        {"a": (0.0, 0.0, 10.0, 10.0)}, ("a",), (0.0, 0.0, 100.0, 100.0), **kwargs
    )

    assert result.status == STATUS_REJECTED
    assert result.failure is not None and result.failure.code == FAILURE_INVALID_ARGUMENT


def test_result_is_independent_of_mapping_insertion_order():
    forward = {name: TALL_LEFT[name] for name in TALL_LEFT_ORDER}
    backward = {name: TALL_LEFT[name] for name in reversed(TALL_LEFT_ORDER)}

    first = pack_frames(forward, TALL_LEFT_ORDER, (0.0, 0.0, 240.0, 400.0))
    second = pack_frames(backward, TALL_LEFT_ORDER, (0.0, 0.0, 240.0, 400.0))

    assert first == second


_HASH_SCRIPT = r"""
import json

from boardwise.engines.pagepacking import pack_frames

geo = {
    "left": (0.0, 0.0, 100.0, 360.0),
    "short_a": (0.0, 0.0, 100.0, 80.0),
    "short_b": (0.0, 0.0, 100.0, 80.0),
    "short_c": (0.0, 0.0, 100.0, 80.0),
    "short_d": (0.0, 0.0, 100.0, 40.0),
}
order = ["left", "short_a", "short_b", "short_c", "short_d"]
frames = {name: geo[name] for name in set(geo)}
result = pack_frames(frames, order, (0.0, 0.0, 240.0, 400.0), gap=40.0, grid=5.0)
print(json.dumps({
    "status": result.status,
    "frames": [list(item) for item in result.frames.items()],
    "width": result.width,
    "height": result.height,
    "nodes": result.nodes,
}, sort_keys=True))
"""


def test_hash_seed_equivalence():
    src = str(Path(__file__).resolve().parents[1] / "src")
    outputs = []
    for seed in ("0", "424242"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
        run = subprocess.run(
            [sys.executable, "-c", _HASH_SCRIPT],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert run.returncode == 0, run.stderr
        outputs.append(run.stdout.strip())
    assert outputs[0] == outputs[1]


def test_budget_stop_is_reported_separately_from_unsat():
    frames = {
        "a": (0.0, 0.0, 100.0, 100.0),
        "b": (0.0, 0.0, 100.0, 100.0),
        "c": (0.0, 0.0, 100.0, 100.0),
    }

    truncated = pack_frames(frames, ("a", "b", "c"), (0.0, 0.0, 1000.0, 1000.0), max_nodes=2)

    assert truncated.status == STATUS_TRUNCATED
    assert truncated.truncated is True and not truncated.ok
    assert truncated.failure is not None and truncated.failure.code == FAILURE_BUDGET_EXHAUSTED
    assert truncated.nodes == 2
    assert truncated.placements == ()

    full = pack_frames(frames, ("a", "b", "c"), (0.0, 0.0, 1000.0, 1000.0))

    assert full.ok and full.nodes > 2
    _assert_inside(full, (0.0, 0.0, 1000.0, 1000.0))
    _assert_pairwise_gap(full)
