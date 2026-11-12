"""038Q8: the managed symbol book (`blocklib/symbols/`) and its checker.

The book is what a clean checkout can still read after 038Q4/Q5/Q7/Q9's evidence
directories are gone, so every test here works on a **copy inside `tmp_path`**
and the two questions are always asked together:

* does the real nineteen-profile book pass, and does it keep passing with no
  `outputs/` at all (a fresh clone);
* does *each* tampering with it turn the checker red — a profile byte, a
  geometry, a binding, an evidence path, the release flag.

The negative cases are the contract: a checker that stays green when a hash no
longer describes its object has replaced verification with a JSON parse. Any
test that only asserted "no exception" would pass against such a checker.

`tools/check_symbol_book.py` is imported by path (`tools/` is not a package).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "blocklib" / "symbols" / "profiles.json"
INDEX = ROOT / "blocklib" / "symbols" / "index.json"
CATALOG = ROOT / "blocklib" / "modules" / "catalog.json"
MANIFEST = ROOT / "blocklib" / "modules" / "manifest.json"

#: The admissions whose identity the tests name by hand: Q8's six plus Q9's thirteen
#: make the nineteen the catalog's unique device uuids need. Naming them keeps a
#: reordering from silently retargeting a case.
AMS1117 = "06f50e10ab7d460599b3fe3ee8717a78"  # C6186 (Q4)
C440198 = "2e54d9f6ef024fd6a073cb020500c9e8"  # C440198 (Q5)
C1525 = "5d54ad1e3ff64cdb9e7c9f449679d79f"  # C1525 (Q5)
C45783 = "a945ad0780e84529829fad9eef7941b6"  # C45783 (Q5)
SY8089AAAC = "ef98186cdedd4b58bd8e66a11ff8b5be"  # C78988 (Q7)
SY8089A1AAC = "f88e34d680e646e38a7b77e29201ff30"  # C479074 (Q7)

#: Every admission the book holds (Q4/Q5/Q7 + Q9), sorted by symbolRef.
EXPECTED_REFS = sorted(
    [
        AMS1117,
        C440198,
        C1525,
        C45783,
        SY8089AAAC,
        SY8089A1AAC,
        "059e3f9d3b884a399517577d11f54751",  # C250183 NLCV32T-2R2M-PF (Q9)
        "061a2c804ac94030b09af596bddca03c",  # C14663 CC0603KRX7R9BB104 (Q9)
        "2f97b34f1fa641a1843a6926dc1e817c",  # C26980 0402WGF4532TCE (Q9)
        "57ad86cbeb22465ab7194a01944810c5",  # C2960862 FRC0603F2212TS (Q9)
        "6d3562bdc96243ae97feaf073d2c8f4e",  # C25803 0603WAF1003T5E (Q9)
        "7ee12203ce22419bb02b8b8f01c8a92c",  # C84681 CH340C (Q9)
        "9807320b9dfe4ddb9f43a24d13de0ff6",  # C25905 0402WGF5101TCE (Q9)
        "b4bb0b94f5d04a92a4e5542845335d53",  # C25744 0402WGF1002TCE (Q9)
        "c097c689214f4468a4ffe59d5170bf50",  # C167206 FXL0420-2R2-M (Q9)
        "d49b09d836ac44e783bde982fab4579b",  # C1653 CL10C220JB8NNNC (Q9)
        "ddf6b4a961904b0e8967696126378ed5",  # C9900012665 USB3.1TYPE-C16P (Q9)
        "e23085a8f904493eb2ce369cbc1b267c",  # C25804 0603WAF1002T5E (Q9)
        "e5c8198e70f04987968abe2e8a11202b",  # C2687116 USBLC6-2SC6 (Q9)
    ]
)


def _checker():
    name = "boardwise_test_check_symbol_book"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "check_symbol_book.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _tmp_book(tmp_path: Path) -> Path:
    """A copy of the managed book plus the catalog, and **no** `outputs/`."""
    root = tmp_path / "repo"
    (root / "blocklib" / "symbols").mkdir(parents=True, exist_ok=True)
    (root / "blocklib" / "modules").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BOOK, root / "blocklib" / "symbols" / "profiles.json")
    shutil.copyfile(INDEX, root / "blocklib" / "symbols" / "index.json")
    shutil.copyfile(CATALOG, root / "blocklib" / "modules" / "catalog.json")
    return root


def _reseal(root: Path) -> None:
    """Recompute `profileBookSha256` so a test isolates one other failure."""
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    book = (root / "blocklib" / "symbols" / "profiles.json").read_bytes()
    index["profileBookSha256"] = hashlib.sha256(book).hexdigest()
    _write(index_path, index)


def _profile_sha(payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _entry(index: dict, symbol_ref: str) -> dict:
    for entry in index["profiles"]:
        if entry["symbolRef"] == symbol_ref:
            return entry
    raise AssertionError(f"{symbol_ref} is not in the index")


def _messages(root: Path) -> list[str]:
    return _checker().validate_book(root)


def _joined(root: Path) -> str:
    messages = _messages(root)
    assert messages, "the checker should have refused this book"
    return "\n".join(messages)


# --------------------------------------------------------------------------
# the real book, and the clean checkout it has to survive


def test_the_real_book_is_green_with_exactly_the_nineteen_admissions():
    checker = _checker()
    assert checker.validate_book(ROOT) == []
    index = _read(INDEX)
    assert [entry["symbolRef"] for entry in index["profiles"]] == EXPECTED_REFS
    assert index["schema"] == "boardwise.symbol-book/1"
    assert index["notForDrawCompile"] is True
    assert all(entry["maturity"] == "candidate" for entry in index["profiles"])
    library = checker.load_library(BOOK)
    assert list(library) == EXPECTED_REFS, "the draw loader reads the book in its own order"


def test_the_book_names_every_unique_identity_the_catalog_declares():
    """Nineteen admissions for the catalog's nineteen unique device uuids.

    Two identities sharing a part number (the two SY8089) stay two entries: a
    book that merged them would report 18 device uuids for 19 catalog uuids.
    """
    catalog = _read(CATALOG)
    declared = {
        part["deviceUuid"]
        for module in catalog["modules"]
        for part in module["parts"]
        if part.get("deviceUuid")
    }
    assert len(declared) == 19, sorted(declared)
    index = _read(INDEX)
    covered = {
        binding["deviceUuid"]
        for entry in index["profiles"]
        for binding in entry["bindings"]
    }
    assert covered == declared, (
        f"missing {sorted(declared - covered)}, unknown to the catalog {sorted(covered - declared)}"
    )
    assert len(index["profiles"]) == len(EXPECTED_REFS) == len(covered)

    sy = [entry for entry in index["profiles"] if entry["symbolRef"] in (SY8089AAAC, SY8089A1AAC)]
    assert len(sy) == 2, "the two SY8089 identities were merged or dropped"
    sy_uuids = [entry["bindings"][0]["deviceUuid"] for entry in sy]
    assert len(set(sy_uuids)) == 2 and set(sy_uuids) <= declared


def test_the_book_passes_with_no_outputs_directory_at_all(tmp_path):
    root = _tmp_book(tmp_path)
    assert not (root / "outputs").exists(), "the fixture must not carry evidence"
    assert _messages(root) == []


def test_the_index_and_book_carry_no_machine_absolute_path():
    book = BOOK.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    for text in (book, index):
        assert "C:\\" not in text and "/home/" not in text and "/Users/" not in text
    assert "outputs/" in index, "provenance is expected to point at the evidence area"


def test_the_evidence_area_is_not_a_checkout_dependency(tmp_path):
    """The evidence paths were real when the book was built — and are not needed."""
    root = _tmp_book(tmp_path)
    index = _read(root / "blocklib" / "symbols" / "index.json")
    paths = [item["path"] for entry in index["profiles"] for item in entry["evidence"]]
    assert paths, "every entry names where it came from"
    for entry in index["profiles"]:
        assert any(item["kind"] == "archive" for item in entry["evidence"])
        assert any(item["kind"] == "device" for item in entry["evidence"])
    assert not any((root / path).exists() for path in paths), "the copy carries no evidence"
    assert _messages(root) == []


# --------------------------------------------------------------------------
# hashes: one character of any of them is a different book


@pytest.mark.parametrize("field", ["archiveSha256", "geometryHash", "profileSha256"])
def test_one_character_of_an_entry_hash_is_red(tmp_path, field):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    entry = _entry(index, AMS1117)
    value = entry[field]
    entry[field] = ("0" if value[0] != "0" else "1") + value[1:]
    _write(index_path, index)
    messages = _joined(root)
    assert field in messages
    assert AMS1117 in messages


def test_one_character_of_the_book_hash_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    index["profileBookSha256"] = index["profileBookSha256"].replace("a", "b", 1)
    _write(index_path, index)
    assert "profileBookSha256" in _joined(root)


def test_a_source_that_names_the_wrong_archive_is_red(tmp_path):
    """`source` is checkable on its own: it must bind symbolRef **and** archiveSha256.

    A copy of the index whose `archiveSha256` moved is caught by the entry/profile
    comparison alone, which is why this case moves the *profile's* `source` too —
    then the only remaining statement about the archive is the `source` string,
    and a checker that stopped reading it would stay green here.
    """
    root = _tmp_book(tmp_path)
    book_path = root / "blocklib" / "symbols" / "profiles.json"
    index_path = root / "blocklib" / "symbols" / "index.json"
    book = _read(book_path)
    symbol_ref = C440198
    profile = next(item for item in book["profiles"] if item["symbolRef"] == symbol_ref)
    wrong = "elibz2:" + symbol_ref + ":sha256:" + "0" * 64
    profile["source"] = wrong
    _write(book_path, book)
    index = _read(index_path)
    _entry(index, symbol_ref)["source"] = wrong
    _write(index_path, index)
    _reseal(root)
    messages = _joined(root)
    assert "does not bind this symbolRef and archiveSha256" in messages, messages
    assert symbol_ref in messages


def test_the_profile_hash_uses_insertion_order_not_sort_keys():
    """`profileSha256` is defined on the object as stored — never on sorted keys."""
    index = _read(INDEX)
    profiles = _read(BOOK)["profiles"]
    for entry, payload in zip(index["profiles"], profiles):
        assert entry["profileSha256"] == _profile_sha(payload)
        sorted_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        sorted_sha = hashlib.sha256(sorted_text.encode("utf-8")).hexdigest()
        assert sorted_sha != entry["profileSha256"], (
            f"{payload['symbolRef']}: the recorded hash is the sorted-keys one"
        )


def test_a_pin_tip_move_changes_the_geometry_hash(tmp_path):
    root = _tmp_book(tmp_path)
    book_path = root / "blocklib" / "symbols" / "profiles.json"
    index_path = root / "blocklib" / "symbols" / "index.json"
    book = _read(book_path)
    symbol_ref = C45783
    profile = next(item for item in book["profiles"] if item["symbolRef"] == symbol_ref)
    tip = profile["pins"][0]["tip"]
    profile["pins"][0]["tip"] = [tip[0] + 1.0, tip[1]]
    _write(book_path, book)
    index = _read(index_path)
    entry = _entry(index, symbol_ref)
    old_geometry = entry["geometryHash"]
    entry["profileSha256"] = _profile_sha(profile)
    _write(index_path, index)
    _reseal(root)
    messages = _joined(root)
    assert "geometryHash" in messages, messages
    assert entry["profileSha256"] not in messages
    assert symbol_ref in messages
    assert old_geometry != _checker().load_library(book_path)[symbol_ref].geometry_hash()


def test_value_row_and_texts_change_the_profile_hash_but_not_the_geometry(tmp_path):
    root = _tmp_book(tmp_path)
    book_path = root / "blocklib" / "symbols" / "profiles.json"
    index_path = root / "blocklib" / "symbols" / "index.json"
    book = _read(book_path)
    symbol_ref = AMS1117
    profile = next(item for item in book["profiles"] if item["symbolRef"] == symbol_ref)
    profile["valueRow"] = "AMS1117-3.3 (SOT-223)"
    profile["texts"] = [
        {"kind": "value", "x": 4.0, "y": -20.0, "bbox": None, "rotation": None, "mirror": None}
    ]
    _write(book_path, book)
    _reseal(root)
    messages = _joined(root)
    assert "profileSha256" in messages, messages
    assert "geometryHash" not in messages, "texts are excluded from geometry on purpose"
    assert symbol_ref in messages
    index = _read(index_path)
    assert _entry(index, symbol_ref)["geometryHash"] == _checker().load_library(
        book_path
    )[symbol_ref].geometry_hash()


# --------------------------------------------------------------------------
# membership: the two SY8089 identities may not be merged or dropped


def test_dropping_one_sy8089_from_the_book_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    book_path = root / "blocklib" / "symbols" / "profiles.json"
    book = _read(book_path)
    book["profiles"] = [
        item for item in book["profiles"] if item["symbolRef"] != SY8089AAAC
    ]
    _write(book_path, book)
    _reseal(root)
    assert "index.profiles" in _joined(root)


def test_dropping_one_sy8089_from_the_index_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    index["profiles"] = [
        entry for entry in index["profiles"] if entry["symbolRef"] != SY8089AAAC
    ]
    _write(index_path, index)
    _reseal(root)
    assert "index.profiles" in _joined(root)


def test_merging_the_two_sy8089_identities_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    merged = json.loads(json.dumps(_entry(index, SY8089A1AAC)))
    merged["title"] = "SY8089AAAC"
    index["profiles"] = [
        merged if entry["symbolRef"] == SY8089AAAC else entry
        for entry in index["profiles"]
    ]
    _write(index_path, index)
    _reseal(root)
    messages = _joined(root)
    assert SY8089AAAC in messages or SY8089A1AAC in messages


def test_reordering_the_book_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    book_path = root / "blocklib" / "symbols" / "profiles.json"
    book = _read(book_path)
    book["profiles"][0], book["profiles"][1] = book["profiles"][1], book["profiles"][0]
    _write(book_path, book)
    _reseal(root)
    messages = _joined(root)
    assert "index.profiles" in messages


@pytest.mark.parametrize("broken", [None, 42, "", ["06f50e10"]])
def test_a_symbol_ref_that_is_not_a_string_is_reported_not_raised(tmp_path, broken):
    """A malformed entry must not take the report down with it.

    `sorted()` over a mixed list raises `TypeError`, so a checker that sorted
    the refs before typing them would crash here and print nothing — the worst
    outcome for a validator, because the reader cannot tell an unreadable book
    from a broken checker.
    """
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    index["profiles"][0]["symbolRef"] = broken
    _write(index_path, index)
    _reseal(root)
    messages = _messages(root)  # must return, not raise
    assert messages, "a book whose first entry names no symbol is not consistent"
    joined = "\n".join(messages)
    assert "index.profiles[0].symbolRef" in joined
    assert "is not a non-empty string" in joined
    assert "cannot be compared with the book" in joined


def test_a_duplicated_symbol_ref_is_reported_by_name(tmp_path):
    """Two entries for one profile is a merge, and the message must say so."""
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    index["profiles"][0]["symbolRef"] = EXPECTED_REFS[1]
    _write(index_path, index)
    _reseal(root)
    joined = _joined(root)
    assert f"symbolRef {EXPECTED_REFS[1]} names 2 entries" in joined
    assert "positions [0, 1]" in joined


def test_a_book_of_non_string_refs_still_reports_every_entry(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    for position, entry in enumerate(index["profiles"]):
        entry["symbolRef"] = position
    _write(index_path, index)
    _reseal(root)
    messages = _messages(root)
    assert len([item for item in messages if "is not a non-empty string" in item]) == len(EXPECTED_REFS)
    assert any("cannot be compared with the book" in item for item in messages)


# --------------------------------------------------------------------------
# the profile schema stays the loader's, not a second shape written here


def test_a_device_uuid_inside_a_profile_is_refused_by_the_existing_loader(tmp_path):
    root = _tmp_book(tmp_path)
    book_path = root / "blocklib" / "symbols" / "profiles.json"
    book = _read(book_path)
    book["profiles"][2]["deviceUuid"] = "87bb635d0b2f489a9f60e7cd225beb3c"
    _write(book_path, book)
    _reseal(root)
    messages = _joined(root)
    assert "draw loader refuses the book" in messages
    with pytest.raises(Exception) as caught:
        _checker().load_library(book_path)
    assert "deviceUuid" in str(caught.value)


# --------------------------------------------------------------------------
# bindings against `blocklib/modules/catalog.json`


def test_binding_lcsc_conflict_with_the_catalog_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    _entry(index, C1525)["bindings"][0]["lcsc"] = "C999999"
    _write(index_path, index)
    messages = _joined(root)
    assert "bindings[0].lcsc" in messages
    assert "C999999" in messages


def test_binding_footprint_label_conflict_with_the_catalog_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    binding = _entry(index, AMS1117)["bindings"][0]
    assert binding["catalogFootprint"] == "SOT-223-3"
    binding["catalogFootprint"] = "SOT-23-5"
    _write(index_path, index)
    assert "catalogFootprint" in _joined(root)


def test_binding_whose_device_uuid_is_unknown_to_the_catalog_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    _entry(index, SY8089A1AAC)["bindings"][0]["deviceUuid"] = "0" * 32
    _write(index_path, index)
    messages = _joined(root)
    assert "deviceUuid" in messages
    assert "0" * 32 in messages


def test_a_binding_that_drops_the_catalog_footprint_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    binding = _entry(index, C440198)["bindings"][0]
    del binding["catalogFootprint"]
    _write(index_path, index)
    messages = _joined(root)
    assert "catalogFootprint" in messages, "a declared catalog field may not go missing"


def test_bindings_carry_only_fields_the_evidence_read():
    allow = {
        "deviceUuid",
        "lcsc",
        "mpn",
        "footprintUuid",
        "supplierFootprint",
        "footprintName",
        "catalogFootprint",
    }
    for entry in _read(INDEX)["profiles"]:
        for binding in entry["bindings"]:
            assert set(binding) <= allow, binding
            assert binding["deviceUuid"]


# --------------------------------------------------------------------------
# provenance and the release flag


def test_an_absolute_evidence_path_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    _entry(index, AMS1117)["evidence"][0]["path"] = "C:\\Users\\someone\\profile.json"
    _write(index_path, index)
    messages = _joined(root)
    assert "evidence[0].path" in messages


def test_a_home_relative_or_escaping_evidence_path_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    _entry(index, AMS1117)["evidence"][0]["path"] = "../../tmp/profile.json"
    _write(index_path, index)
    assert "evidence[0].path" in _joined(root)


def test_not_for_draw_compile_false_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    index["notForDrawCompile"] = False
    _write(index_path, index)
    assert "notForDrawCompile" in _joined(root)


def test_a_profile_that_stops_being_a_candidate_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    _entry(index, C45783)["maturity"] = "verified"
    _write(index_path, index)
    assert "maturity" in _joined(root)


def test_a_wrong_reader_or_source_tier_is_red(tmp_path):
    root = _tmp_book(tmp_path)
    index_path = root / "blocklib" / "symbols" / "index.json"
    index = _read(index_path)
    entry = _entry(index, AMS1117)
    entry["reader"] = "boardwise.parsers.somewhere.else"
    entry["sourceTier"] = "self-authored"
    _write(index_path, index)
    messages = _joined(root)
    assert "reader" in messages and "sourceTier" in messages


# --------------------------------------------------------------------------
# the CLI


def test_cli_is_green_on_the_real_checkout(capsys):
    status = _checker().main([])
    out = capsys.readouterr().out
    assert status == 0
    assert "19 candidate profile(s)" in out


def test_cli_reports_and_exits_nonzero_on_a_broken_book(tmp_path, capsys):
    root = _tmp_book(tmp_path)
    book_path = root / "blocklib" / "symbols" / "profiles.json"
    book_path.write_bytes(book_path.read_bytes() + b"\n")
    status = _checker().main(["--root", str(root)])
    err = capsys.readouterr().err
    assert status == 1
    assert "profileBookSha256" in err


# --------------------------------------------------------------------------
# what this batch promised not to touch


def test_the_module_catalog_keeps_its_release_flags_and_symbol_refs():
    catalog = _read(CATALOG)
    assert catalog["modules"], "the catalog must still hold its modules"
    for module in catalog["modules"]:
        assert module["notForDrawCompile"] is True, module["id"]
        # 038Q10 binds the SY8089 block to the managed book and 038Q12 binds the
        # CH340C block; every other part still carries no symbolRef, which is
        # what this batch's flag protects.
        bound = module["id"] in {"block.sy8089_buck_3v3", "block.ch340c_usb_serial"}
        for part in module["parts"]:
            if bound:
                assert len(part.get("symbolRef", "")) == 32, part["role"]
            else:
                assert part.get("symbolRef", "") == "", (
                    f"{module['id']}: a catalog part grew a symbolRef, which 038Q8 must not do"
                )


def test_the_symbol_book_is_not_a_module_and_is_an_input_not_an_output():
    assert not (ROOT / "blocklib" / "modules" / "symbols").exists()
    # 038Q10 reads the book from where it lives and publishes no copy: both files
    # are manifest *inputs*, and the module tree never carries them.
    manifest = _read(MANIFEST)
    inputs = {entry["path"] for entry in manifest["inputs"]}
    assert {
        "blocklib/symbols/index.json",
        "blocklib/symbols/profiles.json",
    } <= inputs, sorted(inputs)
    outputs = {entry["path"] for entry in manifest["outputs"]}
    assert not any("symbols/" in path for path in outputs), sorted(outputs)


def test_no_circuit_spec_gained_a_real_symbol_uuid():
    specs = ROOT / "blocklib" / "specs"
    hits = []
    for path in sorted(specs.glob("*.circuit.json")):
        text = path.read_text(encoding="utf-8")
        for ref in EXPECTED_REFS:
            if ref in text:
                hits.append(f"{path.name}: {ref}")
    assert hits == [], hits


# --------------------------------------------------------------------------
# the catalog's own symbolRef: a module bound to the book may not point elsewhere


#: `block.ch340c_usb_serial`'s two ends of the same question: its own U part and
#: the Type-C connector of the very same module, which is a real symbolRef and
#: therefore the most plausible wrong answer a copy-paste can produce.
CH340C_UUID = "4951b3094e3e48a7b4c8c708b64932e4"  # C84681
CH340C_REF = "7ee12203ce22419bb02b8b8f01c8a92c"
TYPE_C_REF = "ddf6b4a961904b0e8967696126378ed5"  # C9900012665


def _set_catalog_symbol_ref(root: Path, module_id: str, role: str, value: str) -> str:
    """Rewrite one catalog part's `symbolRef` in the copy; return what it was."""
    path = root / "blocklib" / "modules" / "catalog.json"
    catalog = _read(path)
    module = next(item for item in catalog["modules"] if item["id"] == module_id)
    part = next(item for item in module["parts"] if item["role"] == role)
    before = part["symbolRef"]
    part["symbolRef"] = value
    _write(path, catalog)
    return before


def test_a_bound_catalog_part_pointing_at_another_profiles_symbol_is_red(tmp_path):
    """Non-empty is not enough: the catalog must name the book's own string.

    CH340C's U part pointed at the Type-C symbol of the same module keeps the
    catalog self-consistent (a real 32-hex ref, a real part of the same block),
    so nothing but a comparison against the book's binding can see it.
    """
    root = _tmp_book(tmp_path)
    assert _set_catalog_symbol_ref(root, "block.ch340c_usb_serial", "U", TYPE_C_REF) == CH340C_REF
    joined = _joined(root)
    assert CH340C_UUID in joined, joined
    assert CH340C_REF in joined and TYPE_C_REF in joined, joined
    assert "block.ch340c_usb_serial" in joined and "'U'" in joined, joined


def test_a_bound_catalog_part_that_falls_back_to_an_empty_symbol_is_red(tmp_path):
    """The bound module promised no part falls back; an empty ref is the fallback."""
    root = _tmp_book(tmp_path)
    symbol_ref = "5d54ad1e3ff64cdb9e7c9f449679d79f"
    assert _set_catalog_symbol_ref(root, "block.ch340c_usb_serial", "C_VCC", "") == symbol_ref
    joined = _joined(root)
    assert "87bb635d0b2f489a9f60e7cd225beb3c" in joined, joined
    assert symbol_ref in joined, joined


def test_an_unbound_module_that_grew_a_symbol_ref_is_red(tmp_path):
    """AMS1117's part is bound *in the book*, but its module never opted in."""
    root = _tmp_book(tmp_path)
    assert _set_catalog_symbol_ref(root, "block.ams1117_ldo_3v3", "U", AMS1117) == ""
    joined = _joined(root)
    assert "block.ams1117_ldo_3v3" in joined, joined
    assert AMS1117 in joined, joined


def test_every_bound_catalog_part_carries_the_books_symbol_and_no_other_does():
    """The real catalog, read the way the checker reads it: nothing is vacuous."""
    catalog = _read(CATALOG)
    by_device = {
        binding["deviceUuid"]: entry["symbolRef"]
        for entry in _read(INDEX)["profiles"]
        for binding in entry["bindings"]
    }
    bound_modules = set()
    for module in catalog["modules"]:
        bound = module["identityStatus"] == "bound"
        if bound:
            bound_modules.add(module["id"])
        for part in module["parts"]:
            if bound:
                assert part["symbolRef"] == by_device[part["deviceUuid"]], (
                    module["id"],
                    part["role"],
                )
            else:
                assert part["symbolRef"] == "", (module["id"], part["role"])
    assert bound_modules, "the bound modules are what this rule is about"


# --------------------------------------------------------------------------
# the checkout itself: these files are hashed, so git may not rewrite newlines


def _managed_json_paths() -> list[str]:
    relative = [
        "blocklib/symbols/profiles.json",
        "blocklib/symbols/index.json",
        "blocklib/modules/catalog.json",
        "blocklib/modules/manifest.json",
    ]
    circuits = sorted((ROOT / "blocklib" / "modules" / "circuits").glob("*.json"))
    assert circuits, "the module tree has circuits to cover"
    return relative + [f"blocklib/modules/circuits/{path.name}" for path in circuits]


def test_the_hashed_json_is_pinned_to_lf_by_git_attributes():
    """A fresh clone with `core.autocrlf=true` must reproduce the hashed bytes.

    The question is asked of git itself (`check-attr`), not of a matcher written
    here: `**` spanning zero directories is exactly the kind of thing a local
    reimplementation would get wrong and then report green.
    """
    git = shutil.which("git")
    if git is None:
        pytest.skip("no git on this machine, so the attributes cannot be asked")
    paths = _managed_json_paths() + ["blocklib/specs/sy8089_buck_3v3.circuit.json"]
    completed = subprocess.run(
        [git, "-C", str(ROOT), "check-attr", "text", "eol", "--", *paths],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip(f"git cannot read this checkout's attributes: {completed.stderr.strip()}")
    attributes: dict[str, dict[str, str]] = {}
    for line in completed.stdout.splitlines():
        path, _, rest = line.partition(": ")
        attr, _, value = rest.partition(": ")
        attributes.setdefault(path, {})[attr] = value
    for path in paths[:-1]:
        assert attributes[path].get("text") == "set", (path, attributes.get(path))
        assert attributes[path].get("eol") == "lf", (path, attributes.get(path))
    # Pinning *every* JSON in the repository was not the point.
    assert attributes[paths[-1]].get("eol") == "unspecified", attributes.get(paths[-1])
    rules = [
        line.strip()
        for line in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert "*.json text eol=lf" not in rules, rules


def test_no_managed_json_carries_a_crlf_in_the_working_tree():
    for relative in _managed_json_paths():
        assert b"\r\n" not in (ROOT / relative).read_bytes(), relative


def test_a_crlf_rewritten_book_is_exactly_what_the_lf_pin_prevents(tmp_path):
    """Why the pin exists: one `autocrlf` rewrite moves the whole-file digest."""
    root = _tmp_book(tmp_path)
    book_path = root / "blocklib" / "symbols" / "profiles.json"
    book_path.write_bytes(book_path.read_bytes().replace(b"\n", b"\r\n"))
    assert "profileBookSha256" in _joined(root)
