"""620A — 548P126 重放证据的引擎 hash 必须是当前树的三份引擎文件。

618 的记录只钉了「PROVENANCE 的块 == result.json 的 engineSha256」以及几何/分区自洽，
没有钉这组 hash 是否等于**现在**跑着的引擎。于是 617C 把 drawcompiler 换成
`c5c6da70…` 之后，旧记录（`9ded2eb3…`）仍然全绿，证据静默过期。

本文件补的就是这一颗钉：块里的三个 sha256 必须逐字等于
`src/boardwise/engines/{drawcompiler,placement,pagecompiler}.py` 的实际内容摘要。
引擎再漂移时这里会红，正确处置是重跑 `evidence/548P126/replay/replay.py` 刷新证据
（或把状态改 `not-replayable`），不是放宽断言。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = ROOT / "evidence/548P126/PROVENANCE.md"
RESULT = ROOT / "evidence/548P126/replay/result.json"
ENGINES = ("drawcompiler", "placement", "pagecompiler")

_missing = [str(path.relative_to(ROOT)) for path in (PROVENANCE, RESULT)
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


def _current() -> dict:
    return {
        name: hashlib.sha256(
            (ROOT / "src/boardwise/engines" / f"{name}.py").read_bytes()
        ).hexdigest()
        for name in ENGINES
    }


def test_the_recorded_engine_hashes_are_the_files_on_disk():
    """块内 engineSha256 必须是当前三份引擎文件的实际摘要。"""
    payload = _payload()
    assert payload["engineSha256"] == _current()


def test_the_stored_result_carries_the_same_current_engine_hashes():
    """result.json 的 engineSha256 也必须等于当前引擎（不是旧一轮的读数）。"""
    stored = json.loads(RESULT.read_text(encoding="utf-8"))
    assert stored["engineSha256"] == _current()
