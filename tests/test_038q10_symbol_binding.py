"""038Q10: the modules bound to the managed symbol book, and the ones that are not.

038Q12 extended this file: the CH340C block is bound as well, so the assertions
below hold for both bound modules and the two remaining assets stay untouched.

The generator side of the opt-in is pinned in Rust
(`rust/crates/boardwise-core/tests/module_import.rs`: the whole-file digest, the
per-profile digest, LCSC/MPN, an exact pin match, a wildcard module and a
`role_topology` asset are each refused there). This file asks the other
question, the one the published tree has to answer: does the module that asked
for the book really carry the book's `symbolRef` — in the catalog *and* in the
CircuitSpec — and did the modules that did not ask stay exactly where they
were?

Nothing here runs the CLI or the editor, reads no `outputs/`, and adds no second
geometry algorithm: the book's own contract is `tools/check_symbol_book.py`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts" / "module-import"
MODULES = ROOT / "blocklib" / "modules"
CIRCUITS = MODULES / "circuits"
BOOK_DIR = ROOT / "blocklib" / "symbols"

BOUND_IDS = ("block.ch340c_usb_serial", "block.sy8089_buck_3v3")
OTHER_IDS = ("block.ams1117_ldo_3v3", "lib.sy8089_buck_3v3_live")
STEMS = {
    "block.ch340c_usb_serial": "ch340c_usb_serial",
    "block.sy8089_buck_3v3": "sy8089_buck_3v3",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _catalog() -> dict:
    return _read(MODULES / "catalog.json")


def _module(catalog: dict, module_id: str) -> dict:
    return next(module for module in catalog["modules"] if module["id"] == module_id)


def _spec(stem: str) -> dict:
    return _read(CIRCUITS / f"{stem}.circuit.json")


def _book_binding(device_uuid: str) -> dict:
    """The one index entry that binds this device, with that binding."""
    hits = [
        (entry, binding)
        for entry in _read(BOOK_DIR / "index.json")["profiles"]
        for binding in entry["bindings"]
        if binding["deviceUuid"] == device_uuid
    ]
    assert len(hits) == 1, f"{device_uuid} is bound by {len(hits)} entries"
    return {"symbolRef": hits[0][0]["symbolRef"], **hits[0][1]}


# --------------------------------------------------------------------------
# the opt-in is declared, and only once


def test_curation_declares_the_book_and_the_bound_assets_ask_for_it() -> None:
    curation = _read(CONTRACTS / "curation.json")
    book = curation["symbolBook"]
    assert book == {
        "defaultIdentity": "generic",
        "index": "blocklib/symbols/index.json",
        "profiles": "blocklib/symbols/profiles.json",
    }
    asking = {
        asset["id"]: asset["identityBinding"]
        for asset in curation["assets"]
        if "identityBinding" in asset
    }
    assert asking == {module_id: "book" for module_id in BOUND_IDS}, asking
    for asset in curation["assets"]:
        assert asset["kind"] in {"block_template", "role_topology"}
        if asset["kind"] == "role_topology":
            assert "identityBinding" not in asset, "this batch refuses the role topology"
        if asset["id"] not in BOUND_IDS:
            for field in ("pinGroups", "portPins", "nc"):
                assert field not in asset, f"{asset['id']} states {field} unbound"


def test_the_book_is_an_input_of_the_import_and_is_never_republished() -> None:
    manifest = _read(MODULES / "manifest.json")
    inputs = {entry["path"]: entry["sha256"] for entry in manifest["inputs"]}
    for name in ("index.json", "profiles.json"):
        relative = f"blocklib/symbols/{name}"
        assert relative in inputs, sorted(inputs)
        assert inputs[relative] == _sha256(ROOT / relative), relative
    outputs = {entry["path"] for entry in manifest["outputs"]}
    assert not any("symbols/" in path for path in outputs), sorted(outputs)
    assert not (MODULES / "symbols").exists(), "the book is read where it lives"


# --------------------------------------------------------------------------
# the bound module


def test_every_part_is_bound_to_the_same_symbol_in_catalog_and_circuit() -> None:
    standard = _read(CONTRACTS / "standard-parts.json")["parts"]
    blocks = {
        module_id: _read(CONTRACTS / "blocks" / f"{stem}.json")["parts"]
        for module_id, stem in STEMS.items()
    }
    for module_id, stem in STEMS.items():
        module = _module(_catalog(), module_id)
        spec = _spec(stem)
        circuit_parts = {part["id"]: part for part in spec["parts"]}
        assert {part["role"] for part in module["parts"]} == set(circuit_parts)
        roles = {entry["role"]: entry for entry in module["parts"]}
        parts = blocks[module_id]

        for role, catalog_part in roles.items():
            symbol_ref = catalog_part["symbolRef"]
            assert len(symbol_ref) == 32, f"{role}: {symbol_ref!r} is not a resolved symbolRef"
            assert not symbol_ref.startswith("GENERIC-"), role
            binding = _book_binding(catalog_part["deviceUuid"])
            assert symbol_ref == binding["symbolRef"], role
            # The part and the binding describe one component, not two.
            assert catalog_part["lcsc"] == binding["lcsc"], role
            assert catalog_part["mpn"] == binding["mpn"], role
            assert standard[parts[role]["part"]]["deviceUuid"] == catalog_part["deviceUuid"], role
            # A device UUID is never a symbolRef, in either document.
            assert symbol_ref != catalog_part["deviceUuid"], role
            assert circuit_parts[role]["symbolRef"] == symbol_ref, role


def test_every_pin_the_module_writes_is_a_pin_of_its_profile() -> None:
    """The published circuit's members are all reachable through the profile."""
    book = _read(BOOK_DIR / "profiles.json")["profiles"]
    profiles = {profile["symbolRef"]: profile for profile in book}
    for module_id, stem in STEMS.items():
        spec = _spec(stem)
        module = _module(_catalog(), module_id)
        by_role = {entry["role"]: profiles[entry["symbolRef"]] for entry in module["parts"]}

        members = {member for net in spec["nets"] for member in net["members"]}
        assert members, f"{module_id} has members to check"
        for member in members:
            role, pin = member.split(".", 1)
            profile = by_role[role]
            assert any(
                pin in (candidate["number"], candidate["name"])
                for candidate in profile["pins"]
            ), f"{member} is not a pin of {profile['symbolRef']}"


def test_the_bound_modules_still_make_no_draw_claim() -> None:
    for module_id in BOUND_IDS:
        module = _module(_catalog(), module_id)
        assert module["maturity"] == "candidate", module_id
        assert module["notForDrawCompile"] is True, module_id
        assert module["unresolvedWildcards"] == [], module_id
        text = " ".join(module["limitations"])
        assert "blocklib/symbols/profiles.json" in text, module_id
        assert _read(BOOK_DIR / "index.json")["profileBookSha256"] in text, module_id
        assert "no SymbolProfile has been read" not in text, "the bound module read one"
        assert "GENERIC-" not in text, "nothing in this module falls back to the placeholder"
        for claim in ("ready to manufacture", "interchangeable", "投板", "可互换"):
            assert claim not in text, (module_id, claim)
        assert "unfinished" in text, "offline compile / editor / hardware are all unproven"


# --------------------------------------------------------------------------
# everybody else


def test_the_other_two_modules_are_untouched() -> None:
    catalog = _catalog()
    for module_id in OTHER_IDS:
        module = _module(catalog, module_id)
        assert module["identityStatus"] == "unverified", module_id
        assert module["maturity"] == "candidate"
        assert module["notForDrawCompile"] is True
        assert "identityBinding" not in module
        for part in module["parts"]:
            assert part["symbolRef"] == "", f"{module_id}: {part['role']}"
        stem = next(
            asset["output"].split("/")[-1].removesuffix(".circuit.json")
            for asset in _read(CONTRACTS / "curation.json")["assets"]
            if asset["id"] == module_id
        )
        for part in _spec(stem)["parts"]:
            assert part["symbolRef"] == f"GENERIC-{part['id']}", (stem, part["id"])


def test_a_wildcard_module_may_not_be_bound() -> None:
    """The generator refuses it; this pins that nobody quietly enabled it."""
    catalog = _catalog()
    for module in catalog["modules"]:
        if module["unresolvedWildcards"]:
            assert module["identityStatus"] != "bound", module["id"]
            assert all(part["symbolRef"] == "" for part in module["parts"]), module["id"]


def test_the_book_itself_was_not_edited() -> None:
    index = _read(BOOK_DIR / "index.json")
    assert index["profileBookSha256"] == _sha256(BOOK_DIR / "profiles.json")
    assert index["notForDrawCompile"] is True
    for entry in index["profiles"]:
        assert entry["maturity"] == "candidate"
    bound = _spec("sy8089_buck_3v3")
    refs = {part["symbolRef"] for part in bound["parts"]}
    assert refs <= {entry["symbolRef"] for entry in index["profiles"]}
