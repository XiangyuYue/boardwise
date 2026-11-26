"""624B — 规格闸的两条 fail-open 与岛模型的两把尺。

来源 `outputs/hole624/b/REPRO.md`（624B-01…04）：

* **624B-01**（高）：电源网里混进 gnd 口（轨对地短路）时 `power-tree` 先把 gnd 口滤掉
  （`:971 rails`），五闸全 pass、报告 `verdict: may proceed`；
* **624B-02**（中）：一条网只要有一个非 signal 口，`levels` 就整条 `continue`（`:860`），
  3V3 信号口接 GND 口零 finding——两闸互相推诿；
* **624B-03**（中）：legacy `parse_islands` 放行「同一岛内重复 part」（`['R1','R1','R2']`），
  同文件 archipelago 分支（`:532`）拒绝——两把尺；
* **624B-04**（低）：一件属两岛时 `part_island_map` 取末个、`island_of_part` 取首个，两个
  公开函数答案相反且都静默。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core.blocks import load_board_spec
from boardwise.core.islands import (
    IslandError,
    LayoutIsland,
    island_of_part,
    parse_islands,
    part_island_map,
)
from boardwise.engines.validate_spec import UNDECIDABLE, VIOLATION, validate_spec

# ---------------------------------------------------------------- fixtures


def _port(role: str, net_class: str = "signal", **fields) -> dict:
    body = {"role": role, "net": role, "net_class": net_class, "position": [0.0, 0.0]}
    body.update(fields)
    return body


def _template(name: str, ports: list[dict]) -> dict:
    pins = ("1", "2", "3")
    return {
        "kind": "boardwise-block-template",
        "version": 1,
        "name": name,
        "description": "",
        "provenance": {
            "kind": "textbook",
            "source": "hand",
            "designators": ["U1"],
            "note": "",
        },
        "origin_file": [0.0, 0.0],
        "bbox_file": [0.0, 0.0, 100.0, 100.0],
        "notes": [],
        "interface": ports,
        "params": [],
        "symbols": {
            "sym1": {
                "offsets": {n: [10.0 * i, 0.0] for i, n in enumerate(pins)},
                "body": None,
                "pin_names": {n: n for n in pins},
            }
        },
        "components": [
            {
                "ref": "U1",
                "symbol": "sym1",
                "placement": {"x": 0.0, "y": 0.0, "rotation": 0.0, "mirror": False},
                "device": {"lcsc": "C1", "name": "Part"},
                "footprint": "0402",
                "params": {},
                "pins": [],
            }
        ],
        "geometry": {
            "wires": [{"net": "", "points": [[0.0, 0.0], [10.0, 0.0]]}],
            "flags": [],
            "labels": [],
        },
    }


def _build(tmp_path: Path, *, blocks: list[dict], connections: list[dict],
           templates: dict[str, dict]):
    for name, body in templates.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")
    for block in blocks:
        if not str(block.get("template", "")).endswith(".json"):
            block["template"] = f"{block['template']}.json"
    raw = {
        "kind": "boardwise-board-spec",
        "version": 1,
        "name": "t",
        "description": "",
        "provenance": {"kind": "textbook", "source": "hand", "note": ""},
        "sheet": {"attrs": {}, "origin": [0.0, 0.0]},
        "blocks": blocks,
        "connections": connections,
        "params": {},
    }
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return load_board_spec(path)


def _rules(gate) -> set[str]:
    return {finding.rule for finding in gate.findings}


def _two_block_spec(tmp_path: Path, *, ports_a: list[dict], ports_b: list[dict],
                    ports: list[list[str]], net: str = "N1"):
    return _build(
        tmp_path,
        blocks=[{"id": "a", "template": "ta", "at": [0.0, 0.0]},
                {"id": "b", "template": "tb", "at": [0.0, 0.0]}],
        connections=[{"net": net, "ports": ports}],
        templates={"ta": _template("ta", ports_a), "tb": _template("tb", ports_b)},
    )


# ---------------------------------------------------------------- 624B-01


def test_a_rail_shorted_to_a_ground_port_is_refused(tmp_path: Path) -> None:
    """轨与地共一条网：`power-tree` 必须先看见「两类口同网」，而不是先把地口滤掉。

    修前读数（REPRO §624B-01）：`ok=True`、`verdict: may proceed`、`power-tree: ('pass', [])`。
    """
    spec = _two_block_spec(
        tmp_path,
        ports_a=[_port("VCC", "power", direction="source", voltage="5V")],
        ports_b=[_port("GND", "gnd")],
        ports=[["a", "VCC"], ["b", "GND"]],
        net="5V",
    )
    report = validate_spec(spec)
    gate = report.gate("power-tree")
    assert gate is not None
    assert report.ok is False
    assert "class-mix" in _rules(gate), [f.rule for f in gate.findings]
    finding = next(f for f in gate.findings if f.rule == "class-mix")
    assert finding.kind == VIOLATION
    assert "5V" in finding.message
    assert any("a.VCC" in row and "b.GND" in row for row in finding.evidence), finding.evidence


# ---------------------------------------------------------------- 624B-02


def test_a_signal_port_joined_to_a_ground_port_does_not_switch_the_level_check_off(
    tmp_path: Path,
) -> None:
    """信号口（写了 3V3）与地口同网：`levels` 不许整条跳过。

    修前读数（REPRO §624B-02）：`ok=True`，`levels: ('pass', [])`——两闸各自把整条网
    让给对方，谁都没判。判 UNDECIDABLE 而不是 VIOLATION：地口可以是 strap 的另一端，
    但这张网的两个口从未被比较过，按模块的 fail-closed 口径不许读成 pass。
    """
    spec = _two_block_spec(
        tmp_path,
        ports_a=[_port("SIG", "signal", level="3V3")],
        ports_b=[_port("GND", "gnd")],
        ports=[["a", "SIG"], ["b", "GND"]],
    )
    report = validate_spec(spec)
    gate = report.gate("levels")
    assert gate is not None
    assert report.ok is False
    assert "level-domain" in _rules(gate), [f.rule for f in gate.findings]
    finding = next(f for f in gate.findings if f.rule == "level-domain")
    assert finding.kind == UNDECIDABLE
    assert "b.GND" in finding.message or any("b.GND" in row for row in finding.evidence)


def test_a_clean_rail_and_a_clean_signal_net_stay_pass(tmp_path: Path) -> None:
    """对照：两条干净网照旧 pass——加的是「一次也没判过」的那一条，不是把闸门关小。"""
    spec = _two_block_spec(
        tmp_path,
        ports_a=[
            _port("VCC", "power", direction="source", voltage="5V"),
            _port("SIG", "signal", level="3V3"),
        ],
        ports_b=[
            _port("VIN", "power", direction="sink", voltage="5V"),
            _port("SIG2", "signal", level="3V3"),
        ],
        ports=[["a", "VCC"], ["b", "VIN"]],
        net="5V",
    )
    report = validate_spec(spec)
    assert report.ok is True, [f.render() for f in report.violations]


# ---------------------------------------------------------------- 624B-03


def test_the_legacy_reader_refuses_a_part_named_twice_in_one_island() -> None:
    """legacy 读法与 archipelago 读法同一把尺：岛内重复 part 即拒。

    修前读数（REPRO §624B-03）：`ACCEPTED parts=['R1', 'R1', 'R2']`。
    """
    with pytest.raises(IslandError, match="repeats part"):
        parse_islands([{"id": "a", "parts": ["R1", "R1", "R2"]}], ["R1", "R2"])


def test_the_archipelago_reader_still_refuses_it() -> None:
    """archipelago 分支的既有钉子（`:532`）不动。"""
    modules = [{"id": "m1", "parts": ["R1", "R2"], "core": "U1"}]
    with pytest.raises(IslandError, match="repeats part"):
        parse_islands(
            [{"id": "a", "parts": ["R1", "R1", "R2"], "group": "m1",
              "owner": "U1", "kind": "core"}],
            ["R1", "R2"],
            modules=modules,
        )


def test_a_legacy_island_without_repeats_still_parses() -> None:
    """对照：不重复的 legacy 岛照旧可读。"""
    islands = parse_islands([{"id": "a", "parts": ["R1", "R2"]}], ["R1", "R2"])
    assert islands[0].parts == ["R1", "R2"]


# ---------------------------------------------------------------- 624B-04


def test_one_part_in_two_islands_is_one_answer_not_two() -> None:
    """`part_island_map` 与 `island_of_part` 必须给同一个答案——两个都抛。

    修前读数（REPRO §624B-04）：`part_island_map[R1]='b'` 而 `island_of_part(R1)='a'`，
    两个公开函数对同一份内存文档给出相反答案，且都不报错。
    """
    islands = [LayoutIsland(id="a", parts=["R1"]), LayoutIsland(id="b", parts=["R1"])]
    with pytest.raises(IslandError, match="two islands"):
        part_island_map(islands)
    with pytest.raises(IslandError, match="two islands"):
        island_of_part(islands, "R1")


def test_a_well_formed_partition_answers_the_same_way_from_both_readers() -> None:
    """对照：一份合法分区两个读数一致。"""
    islands = [LayoutIsland(id="a", parts=["R1", "R2"]), LayoutIsland(id="b", parts=["R3"])]
    assert part_island_map(islands) == {"R1": "a", "R2": "a", "R3": "b"}
    assert island_of_part(islands, "R3") == "b"
    assert island_of_part(islands, "R9") is None
