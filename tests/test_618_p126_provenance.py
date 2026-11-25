"""618 — 548P126 的「可重放」必须是真的：`PROVENANCE.md` 与重算结果逐项对齐。

548P126 当年只落了几何指纹，没留 argv 与模块级三件套。618 的做法不是补写一条
猜出来的命令，而是用候选 LayoutPlan 自己钉住的 `source.circuitSha256` /
`source.presentationSha256` 在盘上指认输入，再用当前生产引擎真实重算：

- `evidence/548P126/PROVENANCE.md` 的机器可读块是唯一事实源；
- 它记录的每个输入路径必须存在且 sha256 与块内一致；
- 块内的 canonical hash 必须等于原候选自己的 `source`；
- 块内的 geometry 必须同时等于原报告与 `replay/result.json`；
- P43 必须能在当前树上重算出同一 geometry、同一逐脚分区。

本文件不钉「新图过了三关」，也不声称真机；它只钉证据链的自洽与可重放。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler as dc, readability

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = ROOT / "evidence/548P126/PROVENANCE.md"
RESULT = ROOT / "evidence/548P126/replay/result.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)
ORIGINALS = {
    "p43": ROOT / "evidence/548P126/p43-compile/cand1.layout.json",
    "wifi": ROOT / "evidence/548P126/wifi-compile/cand1.layout.json",
}
REPORTS = {
    "p43": ROOT / "evidence/548P126/p43-compile-report.json",
    "wifi": ROOT / "evidence/548P126/wifi-compile-report.json",
}
INPUT_KINDS = ("circuit", "presentation", "profiles")

_missing = [str(path.relative_to(ROOT)) for path in
            (PROVENANCE, RESULT, *ORIGINALS.values(), *REPORTS.values())
            if not path.exists()]
if _missing:
    pytest.skip(
        "requires local 548P126 replay evidence (gitignored, local-only); "
        f"missing: {_missing}", allow_module_level=True)


def _payload() -> dict:
    text = PROVENANCE.read_text(encoding="utf-8")
    start = text.index("```json")
    end = text.index("```", start + len("```json"))
    return json.loads(text[start + len("```json"):end])


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(plan_path: Path) -> dict:
    return json.loads(plan_path.read_text(encoding="utf-8"))["source"]


def test_the_record_does_not_claim_the_original_argv_was_kept():
    """原始 argv 没保留：记录只能说「按 source hash 指认输入后重建」，不能伪造原命令。"""
    payload = _payload()
    assert payload["status"] == "reference-replay (reconstructed-input)"
    assert set(payload["cases"]) == set(ORIGINALS)
    for case, row in payload["cases"].items():
        assert row["originalArgv"]["preserved"] is False, case
        assert "no argv" in row["originalArgv"]["why"].lower(), case
        assert row["originalArgv"]["identifiedBy"] == [
            "source.circuitSha256", "source.presentationSha256"], case


def test_every_recorded_input_exists_and_keeps_its_hash():
    """输入路径存在、文件 hash 与块内一致，canonical hash 与原候选 source 一致。"""
    payload = _payload()
    for case, row in payload["cases"].items():
        for kind in INPUT_KINDS:
            path = ROOT / row["inputs"][kind]
            assert path.exists(), f"{case}.{kind}: {path} is gone"
            assert _sha(path) == row["sha256"][kind], f"{case}.{kind}: file moved"
        circuit = CircuitSpec.load(ROOT / row["inputs"]["circuit"])
        spec = PresentationSpec.load(ROOT / row["inputs"]["presentation"])
        assert circuit.sha256() == row["canonical"]["circuit"], case
        assert spec.sha256() == row["canonical"]["presentation"], case
        source = _source(ORIGINALS[case])
        assert row["canonical"]["circuit"] == source["circuitSha256"], case
        assert row["canonical"]["presentation"] == source["presentationSha256"], case


def test_the_record_agrees_with_the_stored_result_and_the_original_reports():
    """块内 geometry / 引擎 hash 必须与磁盘结果和原报告三方一致。"""
    payload = _payload()
    assert payload["result"] == "evidence/548P126/replay/result.json"
    stored = json.loads(RESULT.read_text(encoding="utf-8"))
    assert stored["engineSha256"] == payload["engineSha256"]
    for case, row in payload["cases"].items():
        assert case in stored["cases"], case
        assert stored["cases"][case]["candidateCount"] == 1, case
        assert stored["cases"][case]["ok"] is True, case
        assert stored["cases"][case]["geometryReplay"] == row["geometrySha256"], case
        report = json.loads(REPORTS[case].read_text(encoding="utf-8"))
        assert report["candidates"][0]["geometrySha256"] == row["geometrySha256"], case
        assert ORIGINALS[case].exists(), case
        original = json.loads(ORIGINALS[case].read_text(encoding="utf-8"))
        assert original["geometrySha256"] == row["geometrySha256"], case


@pytest.fixture(scope="module")
def p43_replay():
    payload = _payload()["cases"]["p43"]
    circuit = CircuitSpec.load(ROOT / payload["inputs"]["circuit"])
    spec = PresentationSpec.load(ROOT / payload["inputs"]["presentation"])
    profiles = drawapply.load_library(ROOT / payload["inputs"]["profiles"])
    result = dc.compile(
        circuit, spec, profiles, dc.CompileBudget(page_box=PAGE_BOX))
    return result, circuit, payload, dc._profile_book(profiles)


def test_p43_still_replays_to_the_recorded_geometry(p43_replay):
    """真实重跑一条：当前树上 P43 必须给出记录里的 geometry 与 source。"""
    result, _circuit, payload, _book = p43_replay
    assert result.ok, [item.detail for item in result.failures]
    assert len(result.candidates) == 1, [item.detail for item in result.failures]
    plan = result.candidates[0]
    assert plan.geometry_sha256() == payload["geometrySha256"]
    assert plan.source.circuit_sha256 == payload["canonical"]["circuit"]
    assert plan.source.presentation_sha256 == payload["canonical"]["presentation"]


def test_p43_replays_to_the_recorded_foot_partition(p43_replay):
    """逐脚分区独立复算：20 条声明脚各在自己网的导体上，U1 其余 48 脚是 NC。"""
    result, circuit, payload, book = p43_replay
    plan = result.candidates[0]
    parts = readability._placed_parts(plan, book)
    tips = {f"{part.part_id}.{number}": (float(point[0]), float(point[1]))
            for part in parts for number, point in part.pins.items()}

    conductors: dict[str, list] = {}
    for segment in plan.segments:
        conductors.setdefault(segment.net, []).append(
            [(float(x), float(y)) for x, y in segment.points])
    stated: dict[str, list] = {}
    for symbol in plan.power_symbols:
        stated.setdefault(symbol.net, []).append((symbol.x, symbol.y))
    for label in plan.labels:
        if label.net:
            stated.setdefault(label.net, []).append((label.x, label.y))

    def on_polyline(point, points) -> bool:
        for start, end in zip(points, points[1:]):
            if (min(start[0], end[0]) - 1e-6 <= point[0]
                    <= max(start[0], end[0]) + 1e-6
                    and min(start[1], end[1]) - 1e-6 <= point[1]
                    <= max(start[1], end[1]) + 1e-6):
                return True
        return False

    declared = [(net.id, member) for net in circuit.nets for member in net.members]
    problems, declared_u1 = [], set()
    for net_id, member in declared:
        point = tips.get(member)
        assert point is not None, member
        if member.startswith("U1."):
            declared_u1.add(member.split(".", 1)[1])
        own = any(on_polyline(point, run) for run in conductors.get(net_id, ()))
        own = own or any(abs(point[0] - x) <= 1e-6 and abs(point[1] - y) <= 1e-6
                         for x, y in stated.get(net_id, ()))
        if not own:
            problems.append(f"{member}: no {net_id} conductor at {point}")
    assert not problems, problems

    nc = []
    for part in parts:
        if part.part_id != "U1":
            continue
        for number, point in part.pins.items():
            if number in declared_u1:
                continue
            nc.append(number)
            touched = any(on_polyline(point, run) for runs in conductors.values()
                          for run in runs) or any(
                abs(point[0] - x) <= 1e-6 and abs(point[1] - y) <= 1e-6
                for points in stated.values() for x, y in points)
            assert not touched, f"U1.{number} at {point} is drawn, but is NC"

    assert len(declared) == payload["partition"]["declaredFeet"]
    assert len(nc) == payload["partition"]["ncFeet"]
