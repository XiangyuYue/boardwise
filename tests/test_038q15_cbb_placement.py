"""038Q15: `sch.place_cbb` in the daemon-facing catalogue and the docs.

The connector half (guards, the exact host call, the post-placement readback,
the partial answers) is pinned against the real `buildHandlers()` registry in
`connector/tests/cbb-placement.test.mjs`. What is checked here is what the
**daemon** and a reader of the docs see, because those are the two places a
write action can silently degrade:

* the catalogue entry is connector-owned, `risk="write"` and a `design_write`,
  with exactly the closed parameter set the handler accepts — `risk` is what
  the CLI's `--read-only` gate and the daemon's create gate consult, so a
  mis-tiered entry either opens a write to a delegated caller or locks the
  action out;
* the declared summary/schema state the traps out loud: the module is re-read
  through `lib_Cbb.get`, project/page identity is checked before **and** after,
  `lib_Symbol.get`'s unreadable answer is only allowed with the caller's
  explicit `allowUnverifiedSourceSymbol: true`, the placed primitive must be
  `block_symbol`, and a failure after the call is `partial` with its evidence
  rather than a silent success;
* the `docs/bridge.md` §4 row exists and says the same things (the row set is
  already compared with the catalogue by `contract-drift.test.mjs`; this checks
  the *content* of this one row);
* the generated CLI contract carries the action, i.e. the epilog was actually
  regenerated rather than left stale;
* the source keeps its two structural promises: it reuses `libCbbGet` (one
  identity reader, not a second copy) and it never reaches a library write
  (`lib_Cbb.create` / `modify` / `delete` / `copy` / `openSymbolInEditor`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from boardwise.bridge.protocol import PLACEMENT_TIMEOUT, action_spec, timeout_for

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "bridge.md"
SOURCE = ROOT / "connector" / "src" / "cbb-placement.ts"
CONTRACT = ROOT / "contracts" / "cli" / "v1.json"

PARAMS = (
    "uuid", "libraryUuid", "expectedName", "symbolUuid", "projectUuid",
    "pageUuid", "x", "y", "rotation", "mirror", "allowUnverifiedSourceSymbol",
)


def _flat(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def _row() -> str:
    """The §4 table row for `sch.place_cbb` — the only row starting with it."""
    rows = [
        line for line in DOC.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `sch.place_cbb` |")
    ]
    assert len(rows) == 1, f"expected exactly one sch.place_cbb row, got {len(rows)}"
    return re.sub(r"\s+", " ", rows[0])


def test_the_action_is_a_connector_owned_design_write():
    spec = action_spec("sch.place_cbb")
    assert spec is not None, "sch.place_cbb is not in the catalogue"
    assert spec.owner == "connector"
    assert spec.risk == "write", "a placement is never anything but a write"
    assert spec.design_write is True, "it puts an object into the user's document"
    assert spec.params == PARAMS, (
        "the catalogue's parameter set is the handler's closed set; "
        f"got {spec.params}"
    )


def test_the_catalogue_states_the_identity_and_partial_contract():
    spec = action_spec("sch.place_cbb")
    summary = spec.summary
    for token in (
        "lib_Cbb.get",
        "expectedName",
        "dmt_Project.getCurrentProjectInfo",
        "dmt_SelectControl.getCurrentDocumentInfo",
        "documentType === 1",
        "lib_Symbol.get",
        "allowUnverifiedSourceSymbol",
        "unverified-source-symbol",
        "block_symbol",
        "getAllPinsByPrimitiveId",
        "partial: true",
        "verified: false",
    ):
        assert token in summary, f"the summary lost {token!r}"

    schema = spec.params_schema
    for token in (
        "PAGE_MISMATCH",
        "detail.guard",
        "0|90|180|270",
        "boolean",
        "backed by another host reading",
        "reported as unverified, never as verified",
    ):
        assert token in schema, f"the params_schema lost {token!r}"


def test_the_docs_row_carries_the_same_contract():
    row = _row()
    for token in (
        "createCbbSymbol",
        "block_symbol",
        "allowUnverifiedSourceSymbol",
        "PAGE_MISMATCH",
        "zero writes",
        "partial: true, verified: false",
        "an empty array is a real reading",
    ):
        assert token in row, f"the docs row lost {token!r}"
    for param in PARAMS:
        assert param in row, f"the docs row does not name {param}"


def test_the_cli_contract_was_regenerated():
    """The daemon's `--help` epilog is a generated artifact; a stale one lies."""
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    text = json.dumps(payload, ensure_ascii=False)
    assert "sch.place_cbb" in text, (
        "contracts/cli/v1.json does not mention sch.place_cbb — regenerate it "
        "with `PYTHONPATH=. python tools/cli_contract.py --write`"
    )


def test_the_source_reuses_the_one_identity_reader_and_writes_nothing_else():
    source = _flat(SOURCE)
    assert "from './library-cbb'" in source and "libCbbGet" in source, (
        "the module identity must come from the existing lib.cbb.get action, "
        "not from a second copy of that read"
    )
    for forbidden in (
        "lib_Cbb.create",
        "lib_Cbb.modify",
        "lib_Cbb.delete",
        "lib_Cbb.copy",
        "openProjectInEditor",
        "openSymbolInEditor",
    ):
        assert forbidden not in source, f"sch.place_cbb must never reach {forbidden}"
    assert "createCbbSymbol" in source
    assert "block_symbol" in source
    assert "getAllPinsByPrimitiveId" in source


def test_cbb_placement_uses_the_placement_timeout():
    assert timeout_for("sch.place_cbb") == PLACEMENT_TIMEOUT
