"""任务 589 / W-Q：S-08 正交与 S-11 交叉预算从「文档规格」变成「机器闸」。

568-A（`outputs/hole568/a/REPRO.md`）实测到的三个洞：

* H1 — `docs/schematic-style-spec.md` 的 S-08 写「100% 横平竖直，出现斜线即判废」，
  但 `draw lint` 一条正交谓词都没有：45° 导线进得了判定集（被 L6 点名），零 ERROR、exit 0。
* H2 — S-11 写「上限导线段数的 2%」，实现只有「全页 >3 个交叉 site 一条 WARN」，
  而 WARN 不进退出码：163 个 site 仍 exit 0。
* H3 — `docs/draw.md` 说「九条几何谓词」，`PREDICATES` 实际 17 个 id，模块 docstring
  的谓词表只列 11 行。

本文件钉的是三条新行为，不是「祖先绿」：

1. `L13-non-orthogonal`（ERROR）：`Wire.segments`（实际画出的子边）任一子边 x、y 同时
   变化即报；水平/垂直/零长不报；多段折线只报斜的那一段。
2. `L13-crossing-budget`（ERROR）：`sites > max(3, 2% × 实际参与检查的导线段数)`——同时严格
   超过 3 处与 2% 才报页级 ERROR（589B 的通用下限），message 带 sites / segments / 2% 的
   计算值 / 实际采用阈值 / 比例；旧 `L6-wire-crossing` 的 >3 site 页级 WARN 与逐簇
   WARN/INFO 原样保留，两条是独立 finding。
3. 文档 id 集与 `PREDICATES` 逐项相等，S-08/S-11 的文本写明对应谓词与 ERROR 级别。

**小页下限的来历（589B 收口，不是 P24 白名单）**：589 先按纯 2% 实现，验收页 P24
（2026-10-04 人工通过）实测 2 个 crossing site / 27 段 = 7.41% 因此新红——纯 2% 会把任何
不足 150 段、带一处交叉的页判废。岳裁定改成通用阈值 `max(L6_PAGE_WARN, 0.02 × 段数)`
（证据 `evidence/589/P24_s11_conflict.txt`、`evidence/589b/`）：下限保住小页，比例仍在大页
收口（21 site / 1000 段 = 2.10% ⇒ ERROR），P24 只是「需要下限」的证人与读数钉，不特判。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from boardwise.engines import drawlint

REPO = Path(__file__).resolve().parents[1]
REAL_DIR = REPO / "outputs" / "111"
ACCEPTED = ("P22", "P23", "P24")


# ------------------------------------------------------------------ helpers


def _sheet_box() -> dict:
    return {
        "primitiveId": "sheet1",
        "state": {
            "PrimitiveType": "Component",
            "ComponentType": "sheet",
            "PrimitiveId": "sheet1",
        },
    }


def _wire(primitive: str, net: str, *points: float) -> dict:
    return {
        "primitiveId": primitive,
        "state": {
            "PrimitiveType": "Wire",
            "PrimitiveId": primitive,
            "Net": net,
            "Line": list(points),
        },
    }


def _snapshot(*components: dict, wires: list[dict] | None = None) -> dict:
    return {
        "components": [_sheet_box(), *components],
        "wires": wires or [],
        "pins": [],
        "netlabels": [],
        "bboxes": {"sheet1": {"minX": 0, "minY": 0, "maxX": 1170, "maxY": 825}},
        "meta": {"sheets": ["sheet1"]},
    }


def _lint(snapshot: dict, svg: str | None = None, **kwargs):
    return drawlint.run_lint(snapshot, svg, **kwargs)


def _by_predicate(findings) -> dict:
    out: dict[str, list] = {}
    for finding in findings:
        out.setdefault(finding.predicate, []).append(finding)
    return out


def _segment_total(snapshot: dict) -> int:
    """The denominator the gate itself uses: the drawn segments of every wire
    that enters the crossing check."""
    sheet = drawlint.Sheet(snapshot)
    return sum(len(wire.segments) for wire in sheet.wires if wire.points)


def _padding_wires(segments: int) -> list[dict]:
    """Horizontal jog wires tucked inside the sheet, each *two* collinear
    segments in the host's retrace spelling — a denominator with no crossings
    of its own. They tile a 40×12 grid right of and below every crossing
    fixture, so even a 1000-segment page fits inside the 1170×825 sheet."""
    assert segments % 2 == 0
    out: list[dict] = []
    for k in range(segments // 2):
        x = 600.0 + 12.0 * (k % 40)
        y = 400.0 + 8.0 * (k // 40)
        out.append(
            _wire(
                f"pad{k}",
                f"PAD{k}",
                x, y,
                x + 8.0, y,
                x + 8.0, y,
                x + 16.0, y,
            )
        )
    return out


def _crossing_pair(index: int, y: float, *, x: float = 0.0) -> list[dict]:
    """One horizontal run crossed once by one vertical run — one cluster.

    The host reads an even-length ``Line`` **pairwise** (`_wire_segments`), so
    a two-segment run is spelled with the corner vertex retraced and each of
    these wires is honestly one segment.
    """
    return [
        _wire(f"h{index}", f"H{index}", x, y, x + 100.0, y),
        _wire(f"v{index}", f"V{index}", x + 50.0, y - 50.0, x + 50.0, y + 50.0),
    ]


def _crossing_pairs(count: int) -> list[dict]:
    """`count` independent single crossings on a 7-column grid (no pair's
    vertical reaches a neighbour's horizontal, so sites == count exactly)."""
    wires: list[dict] = []
    for index in range(count):
        column, row = index % 7, index // 7
        wires.extend(
            _crossing_pair(
                index,
                50.0 + 120.0 * row,
                x=20.0 + 150.0 * column,
            )
        )
    return wires


@pytest.fixture(scope="module")
def real_pages():
    """The four captured live snapshots + renders (skipped when absent)."""
    pages = ("P1", *ACCEPTED)
    needed = [REAL_DIR / f"geo_{page}_live.json" for page in pages]
    renders = [REAL_DIR / f"render_{page}.svg" for page in pages]
    if not all(path.exists() for path in needed + renders):
        pytest.skip("outputs/111/ live captures are not on this machine")
    return {
        page: {
            "snapshot": json.loads(
                (REAL_DIR / f"geo_{page}_live.json").read_text(encoding="utf-8")
            ),
            "render": (REAL_DIR / f"render_{page}.svg").read_text(encoding="utf-8"),
        }
        for page in pages
    }


# ------------------------------------------------------------------ S-08 / L13


def test_s08_a_diagonal_segment_is_an_error():
    """568A-H1: S-08 是 `[硬]`「出现斜线即判废」，45° 导线必须是 ERROR，
    finding 要点名 wire、子边两端坐标与 S-08。"""
    snapshot = _snapshot(wires=[_wire("wSlant", "DIAG", 100, 100, 300, 300)])
    hits = _by_predicate(_lint(snapshot))["L13-non-orthogonal"]
    assert len(hits) == 1
    assert hits[0].severity == "ERROR"
    message = hits[0].message
    assert "wSlant"[:8] in message
    assert "(100,100)" in message and "(300,300)" in message
    assert "S-08" in message
    assert hits[0].objects == ("wSlant",)


def test_s08_spares_horizontal_vertical_and_zero_length_segments():
    """负控：水平、垂直、零长段都不是斜线（P22 实测有 1 条零长段）。"""
    snapshot = _snapshot(
        wires=[
            _wire("wH", "N_H", 100, 400, 300, 400),
            _wire("wV", "N_V", 500, 200, 500, 600),
            _wire("wZero", "N_Z", 700, 700, 700, 700),
        ],
    )
    assert _by_predicate(_lint(snapshot)).get("L13-non-orthogonal") is None


def test_s08_reports_only_the_diagonal_sub_edge_of_a_polyline():
    """一条折线里只有一个斜子边时，只报那一段——不把整根线报一次，
    也不漏掉其余正交段（`Wire.segments` 是判定单位）。"""
    snapshot = _snapshot(
        wires=[
            _wire(
                "wBend", "N_BEND",
                100, 100,
                200, 100,   # 水平
                200, 100,
                200, 300,   # 垂直（retrace 拼法：host 的双段线写法）
                200, 300,
                350, 380,   # 斜
            )
        ],
    )
    hits = _by_predicate(_lint(snapshot))["L13-non-orthogonal"]
    assert len(hits) == 1
    assert "(200,300)" in hits[0].message and "(350,380)" in hits[0].message


def test_s08_accepted_pages_carry_no_diagonal(real_pages):
    """accepted 页（P22/P23/P24）与 P1 实测零斜子边——新闸不许在真页上假红。"""
    for page in ("P1", *ACCEPTED):
        data = real_pages[page]
        findings = drawlint.run_lint(data["snapshot"], data["render"])
        hits = [f for f in findings if f.predicate == "L13-non-orthogonal"]
        assert hits == [], (
            f"{page}: 正交闸在已有页上假红: " + "; ".join(h.message for h in hits)
        )


def test_s08_cli_replay_exits_1(tmp_path, capsys):
    """CLI 入口（replay，无 bridge）：斜线页必须 exit 1 并打印谓词名。"""
    from boardwise import cli as cli_module

    snapshot = _snapshot(wires=[_wire("wSlant", "DIAG", 100, 100, 300, 300)])
    snap = tmp_path / "snap.json"
    render = tmp_path / "render.svg"
    snap.write_text(json.dumps(snapshot), encoding="utf-8")
    render.write_text("<svg></svg>", encoding="utf-8")
    args = cli_module.build_parser().parse_args([
        "draw", "lint", "--snapshot", str(snap), "--render", str(render),
        "--json", str(tmp_path / "report.json"),
    ])
    assert cli_module._cmd_draw_lint(args) == 1
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["source"] == "replay"
    assert report["exitCode"] == 1
    assert any(
        row["predicate"] == "L13-non-orthogonal" and row["severity"] == "ERROR"
        for row in report["findings"]
    )
    assert "L13-non-orthogonal" in capsys.readouterr().out


# ------------------------------------------------------------------ S-11 / L13


def test_s11_three_sites_under_the_floor_stay_quiet():
    """589B 的小页下限：3 个 site / 102 段 = 2.94%（**超 2%**）但不超过 3 处，
    按 `max(3, 0.02 × 102)` 不报 ERROR。这条就是下限的因果覆盖——纯 2% 实现下它会红。"""
    snapshot = _snapshot(wires=_padding_wires(96) + _crossing_pairs(3))
    assert _segment_total(snapshot) == 102
    assert _by_predicate(_lint(snapshot)).get("L13-crossing-budget") is None


def test_s11_four_sites_over_both_limits_are_an_error():
    """4 个 site / 102 段 = 3.92%：同时严格超过 3 处与 2%（2.04）⇒ 页级 ERROR。
    message 要同时给出 sites、segments、2% 计算值、实际采用阈值与比例。"""
    snapshot = _snapshot(wires=_padding_wires(94) + _crossing_pairs(4))
    segments = _segment_total(snapshot)
    assert segments == 102
    hits = _by_predicate(_lint(snapshot))["L13-crossing-budget"]
    assert len(hits) == 1
    assert hits[0].severity == "ERROR"
    message = hits[0].message
    assert "4 distinct crossing sites" in message
    assert "102" in message
    assert "2%" in message and "0.02" in message
    assert "2.04" in message  # 2% 的计算值
    assert "= 3 sites" in message  # 实际采用的下限（3 > 2.04）
    assert "3.92%" in message


def test_s11_the_ratio_binds_on_a_large_page():
    """大页强正例：2% 仍是真约束。21 个 site / 1000 段 = 2.10%，
    max(3, 0.02 × 1000 = 20.00) = 20 ⇒ 21 > 20 报 ERROR（此时下限不参与判定）。"""
    snapshot = _snapshot(wires=_padding_wires(958) + _crossing_pairs(21))
    segments = _segment_total(snapshot)
    assert segments == 1000
    hits = _by_predicate(_lint(snapshot))["L13-crossing-budget"]
    assert len(hits) == 1 and hits[0].severity == "ERROR"
    message = hits[0].message
    assert "21 distinct crossing sites" in message
    assert "1000" in message
    assert "20.00" in message  # 2% × 1000
    assert "= 20 sites" in message  # 采用阈值：比例赢了下限
    assert "2.10%" in message


def test_s11_exactly_at_the_ratio_threshold_stays_quiet():
    """负控：sites == max(3, 2% × segments) 恰好不报（20 site / 1000 段 = 20.0），
    判据是严格大于——比例边界不许被写成 `>=`。"""
    snapshot = _snapshot(wires=_padding_wires(960) + _crossing_pairs(20))
    assert _segment_total(snapshot) == 1000
    assert _by_predicate(_lint(snapshot)).get("L13-crossing-budget") is None


def test_s11_zero_wires_and_zero_crossings_are_silent():
    """零导线、零交叉都不许产生除法假红（也不许 ZeroDivisionError）。"""
    assert _by_predicate(_lint(_snapshot())).get("L13-crossing-budget") is None
    no_cross = _snapshot(
        wires=[
            _wire("wH", "N_H", 100, 400, 300, 400),
            _wire("wV", "N_V", 500, 200, 500, 600),
        ],
    )
    assert _by_predicate(_lint(no_cross)).get("L13-crossing-budget") is None


def test_s11_keeps_the_legacy_page_warn_beside_the_new_error():
    """旧的 >3 site 页级 WARN 不许被新 ERROR 顶掉：5 个 site / 10 段时，
    `L6-wire-crossing` 的页级 WARN 与 `L13-crossing-budget` 的 ERROR 同时在场，
    是两条独立 finding（此时下限 3 就是采信阈值：max(3, 0.20)）。"""
    snapshot = _snapshot(wires=_crossing_pairs(5))
    assert _segment_total(snapshot) == 10
    findings = _lint(snapshot)
    page_warns = [
        f for f in findings
        if f.predicate == "L6-wire-crossing"
        and f.severity == "WARN"
        and "the page carries 5 distinct crossing sites" in f.message
    ]
    assert len(page_warns) == 1
    assert "more than 3" in page_warns[0].message
    budget = _by_predicate(findings)["L13-crossing-budget"]
    assert len(budget) == 1 and budget[0].severity == "ERROR"
    assert "0.20" in budget[0].message and "= 3 sites" in budget[0].message


def test_s11_accepted_pages_stay_under_the_floor_and_readings_are_pinned(real_pages):
    """accepted 页负控 + 读数钉（589B 起这是通用下限，不是 P24 白名单）。

    P22 0/31、P23 0/16 静默；P24 2 site / 27 段 = 7.41%，在 2% 之上但不超过
    3 处，`max(3, 0.54) = 3` 放行 ⇒ 无 `L13-crossing-budget`。读数仍钉死，
    防止有人把 P24 的数字改小（或用"分母改大"凑绿）。
    """
    readings = {}
    for page in ACCEPTED:
        data = real_pages[page]
        snapshot = data["snapshot"]
        segments = _segment_total(snapshot)
        findings = drawlint.run_lint(snapshot, data["render"])
        hits = [f for f in findings if f.predicate == "L13-crossing-budget"]
        assert hits == [], (
            f"{page}: accepted 页在通用下限下仍被判废: " + "; ".join(h.message for h in hits)
        )
        l6_sites = len([
            f for f in findings
            if f.predicate == "L6-wire-crossing" and "time(s) near" in f.message
        ])
        readings[page] = (l6_sites, segments)
    assert readings == {"P22": (0, 31), "P23": (0, 16), "P24": (2, 27)}, readings
    # P24 仍在 2% 之上：正是这条读数要求下限，删掉下限它就会红
    assert readings["P24"][0] > drawlint.S11_CROSSING_BUDGET * readings["P24"][1]
    assert readings["P24"][0] <= drawlint.L6_PAGE_WARN


# ------------------------------------------------------------------ H3 文档/机器一致


def _documented_ids() -> tuple[set[str], set[str]]:
    """`docs/draw.md` 落图 SOP 段的两组机器可读谓词清单（几何闸 / 仅网表闸）。"""
    draw = (REPO / "docs" / "draw.md").read_text(encoding="utf-8")
    assert "几何闸（" in draw and "仅网表闸（" in draw, (
        "docs/draw.md 落图 SOP 段缺了谓词清单（几何闸（…）/ 仅网表闸（…）两行）"
    )
    geometry_start = draw.index("几何闸（")
    netlist_start = draw.index("仅网表闸（", geometry_start)
    netlist_end = draw.index("\n\n", netlist_start)
    id_re = re.compile(r"`(L\d+[a-z]?-[a-z-]+)`")
    return (
        set(id_re.findall(draw[geometry_start:netlist_start])),
        set(id_re.findall(draw[netlist_start:netlist_end])),
    )


def test_predicates_match_the_document_id_sets():
    """568A-H3：文档列出的 id 集合与 `PREDICATES` / `NETLIST_PREDICATES` 完全相同，
    条数也相同——删一项（文档或代码）即红。"""
    geometry, netlist = _documented_ids()
    live = {predicate for predicate, _ in drawlint.PREDICATES}
    assert geometry | netlist == live, (
        "docs/draw.md 的谓词清单与 PREDICATES 不一致: "
        f"文档多 {sorted((geometry | netlist) - live)}，代码多 {sorted(live - (geometry | netlist))}"
    )
    assert netlist == set(drawlint.NETLIST_PREDICATES)
    assert geometry.isdisjoint(netlist)
    draw = (REPO / "docs" / "draw.md").read_text(encoding="utf-8")
    assert f"几何闸（{len(geometry)} 条" in draw
    assert f"仅网表闸（{len(netlist)} 条" in draw


def test_the_module_table_lists_every_predicate_id():
    """`drawlint.py` 顶部谓词表逐 id 列全（不再写 eleven / 省略六个家族），
    且每条 id 的行内级别与 `PREDICATES` 一致。"""
    doc = drawlint.__doc__ or ""
    levels = dict(drawlint.PREDICATES)
    for predicate, level in drawlint.PREDICATES:
        assert f"``{predicate}``" in doc, f"谓词表漏了 {predicate}"
        assert level in doc, f"谓词表少了级别 {level}（{predicate}）"
    assert "eleven" not in doc


def test_s08_and_s11_read_as_error_gates_in_the_documents():
    """S-08/S-11 的文本写出对应谓词 id 与 ERROR 级别；规格与机器不再各说各话。"""
    spec = (REPO / "docs" / "schematic-style-spec.md").read_text(encoding="utf-8")
    for token in (
        "L13-non-orthogonal",
        "L13-crossing-budget",
        "`Wire.segments`",
        "distinct crossing site",
    ):
        assert token in spec, f"docs/schematic-style-spec.md 少了 {token!r}"
    levels = dict(drawlint.PREDICATES)
    for predicate in ("L13-non-orthogonal", "L13-crossing-budget"):
        assert levels[predicate] == "ERROR"
