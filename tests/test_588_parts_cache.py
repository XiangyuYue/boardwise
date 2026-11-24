"""588 / 569-F-5: a **failed** save must not leave a ghost on the shelf.

The reproduction (``outputs/hole569/f/probes/f6_parts_failed_save.py``): the
memo in ``core.parts`` used to hand back the one parsed ``PartLibrary``, and
``load_parts → .parts.append → save_parts`` therefore appended **inside the
memo**. When the save failed (a read-only shelf is a real Windows state), the
next ``load_parts`` in the same process answered with an entry the file never
had — disk=1, memory=2.

What is pinned here:

* a failed save changes neither the file nor the next read;
* a successful save is read back, and its new bytes are a **new** digest (the
  memo must not let the old bytes win);
* a reader can mutate what it was handed — the list, and the containers inside
  an entry — without that reaching the memo;
* ``load_parts`` still parses each digest **once** (perf-02A's contract: the
  parse counter, not object identity);
* ``save_parts`` writes through a sibling temporary plus ``os.replace``, keeps
  the old file when the replace cannot land, and leaves no temporary behind.

The last one is the negative control for the fix itself: reverting either half
(memo isolation, atomic save) turns at least one test here red.
"""

from __future__ import annotations

import json
import os
import stat

import pytest

from boardwise.core import parts as parts_module
from boardwise.core.parts import (
    PartEntry,
    PartError,
    PartLibrary,
    library_to_json,
    load_parts,
    save_parts,
)


def _entry(key: str, lcsc: str, **overrides) -> PartEntry:
    body = dict(
        key=key,
        value=key,
        mpn=key.upper(),
        lcsc=lcsc,
        manufacturer="ACME",
        deviceUuid=f"dev-{key}",
        libraryUuid="0819f05c4eef4c71ace90d822a990e87",
        footprint_name="SOT-23-5",
    )
    body.update(overrides)
    return PartEntry(**body)


def _shelf(path, *keys):
    save_parts(
        PartLibrary(parts=[_entry(key, f"C{index + 1}") for index, key in enumerate(keys)]),
        path,
    )
    return path


@pytest.fixture
def parse_counter(monkeypatch):
    """Count real parses: ``load_parts`` calls ``library_from_json`` by name."""
    calls = {"n": 0}
    real = parts_module.library_from_json

    def counted(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(parts_module, "library_from_json", counted)
    return calls


def test_a_failed_save_leaves_no_ghost_behind_for_the_next_read(tmp_path):
    """The F-5 reproduction, without the probe's scratch home."""
    shelf = _shelf(tmp_path / "shelf.json", "ic.one")
    library = load_parts(shelf)  # the writer's read
    library.parts.append(_entry("ic.two", "C2"))  # the writer's edit
    library.parts.sort(key=lambda p: p.key)

    os.chmod(shelf, stat.S_IREAD)
    try:
        with pytest.raises((PartError, OSError)):
            save_parts(library, shelf)
    finally:
        os.chmod(shelf, stat.S_IWRITE)

    on_disk = json.loads(shelf.read_text(encoding="utf-8"))
    assert [p["key"] for p in on_disk["parts"]] == ["ic.one"]
    again = load_parts(shelf)
    assert [p.key for p in again.parts] == ["ic.one"], (
        "a failed save must not reach the memo: disk=1 but the next read saw "
        f"{[p.key for p in again.parts]}"
    )
    leftovers = sorted(p.name for p in tmp_path.iterdir() if p.name != shelf.name)
    assert leftovers == [], f"the failed save left {leftovers} behind"


def test_a_successful_save_lands_and_its_new_bytes_are_read(tmp_path, parse_counter):
    """The other half of the control: save → the entry is on disk and readable."""
    shelf = _shelf(tmp_path / "shelf.json", "ic.one")
    library = load_parts(shelf)
    assert parse_counter["n"] == 1
    library.parts.append(_entry("ic.two", "C2"))
    library.parts.sort(key=lambda p: p.key)
    save_parts(library, shelf)

    reloaded = load_parts(shelf)
    assert [p.key for p in reloaded.parts] == ["ic.one", "ic.two"]
    assert parse_counter["n"] == 2, "new bytes must be a new parse, not the old memo"
    assert json.loads(shelf.read_text(encoding="utf-8"))["parts"][-1]["key"] == "ic.two"


def test_a_reader_cannot_pollute_the_memo_through_an_entry(tmp_path):
    """Isolation is deeper than the ``parts`` list: the containers inside too."""
    shelf = _shelf(tmp_path / "shelf.json", "ic.one")
    raw = json.loads(shelf.read_text(encoding="utf-8"))
    raw["parts"][0]["params"] = {"Resistance": "5.1kΩ ±1%"}
    raw["parts"][0]["notes"] = ["hand written"]
    raw["parts"][0]["provenance"] = {"kind": "board-extract", "designators": ["R1"]}
    raw["parts"][0]["category_provenance"] = {
        "source": "https://example.com/ds.pdf",
        "page": 3,
        "quote": "5.1k",
    }
    shelf.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    first = load_parts(shelf)
    first.parts[0].params["Resistance"] = "999"
    first.parts[0].notes.append("polluted")
    first.parts[0].provenance.designators.append("R9")
    first.parts[0].category_provenance["page"] = 999
    first.parts.clear()

    second = load_parts(shelf)
    assert [p.key for p in second.parts] == ["ic.one"]
    assert second.parts[0].params == {"Resistance": "5.1kΩ ±1%"}
    assert second.parts[0].notes == ["hand written"]
    assert second.parts[0].provenance.designators == ["R1"]
    assert second.parts[0].category_provenance["page"] == 3


def test_the_shelf_is_parsed_once_per_digest_and_handed_back_separately(
    tmp_path, parse_counter
):
    """perf-02A's contract is the *parse* count, not shared object identity."""
    shelf = _shelf(tmp_path / "shelf.json", "ic.one")
    first = load_parts(shelf)
    second = load_parts(shelf)
    third = load_parts(str(shelf))  # same file, spelled differently
    assert parse_counter["n"] == 1
    assert first is not second and second is not third
    assert first == second == third
    assert [p.key for p in third.parts] == ["ic.one"]


def test_a_save_that_cannot_be_replaced_keeps_the_old_file_and_no_temporary(
    tmp_path, monkeypatch
):
    """Atomicity itself: the file only changes when ``os.replace`` lands."""
    shelf = _shelf(tmp_path / "shelf.json", "ic.one")
    before = shelf.read_bytes()

    def refuse(source, target):
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(parts_module.os, "replace", refuse)
    with pytest.raises((PartError, OSError)):
        save_parts(
            PartLibrary(parts=[_entry("ic.one", "C1"), _entry("ic.two", "C2")]), shelf
        )

    assert shelf.read_bytes() == before
    leftovers = sorted(p.name for p in tmp_path.iterdir() if p.name != shelf.name)
    assert leftovers == [], f"the interrupted save left {leftovers} behind"


def test_a_successful_save_writes_the_bytes_the_old_writer_wrote(tmp_path):
    """The write moved through a temporary; its **content** did not change."""
    shelf = tmp_path / "shelf.json"
    library = PartLibrary(parts=[_entry("ic.one", "C1"), _entry("ic.two", "C2")])
    save_parts(library, shelf)

    oracle = tmp_path / "oracle.json"
    oracle.write_text(
        json.dumps(library_to_json(library), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    assert shelf.read_bytes() == oracle.read_bytes()
