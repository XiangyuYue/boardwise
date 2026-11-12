#!/usr/bin/env python3
"""Check the managed symbol book: `blocklib/symbols/{profiles.json,index.json}`.

    .venv/Scripts/python.exe tools/check_symbol_book.py [--root DIR]

The book is the clean-checkout face of 038Q4/Q5/Q7/Q9's measured profiles: the
currently admitted profiles that a drawing *could* use, kept beside the
Rust-generated module domain rather than inside it. This checker is the whole
contract, and it reads **only** the two managed files plus
`blocklib/modules/catalog.json` — no `outputs/`, no live editor, no network.
Evidence paths inside the index are provenance notes, so a missing `outputs/`
tree must leave this checker green: that is exactly what a fresh clone looks
like.

What it proves, one error line per object and field:

1. `engines.drawapply.load_library` really parses `profiles.json` into the
   `SymbolProfile`s, and the index names them in the same order;
2. every hash is recomputed here — the whole book, each profile object, each
   geometry (`SymbolProfile.geometry_hash()`) and each `source`/`archiveSha256`
   pair, which must also agree with the profile's own `symbolRef`;
3. every binding's `deviceUuid` is a part the module catalog declares, and the
   fields both sides spell out (`lcsc`, `mpn`, and the catalog's `footprint`
   label) agree. A catalog part that omits a field is not filled in here;
4. `evidence[]` is provenance only: records, not files to open, and never a
   machine-absolute path;
5. `notForDrawCompile`/`maturity=candidate` still say what they mean — the book
   is not a runtime drawing gate, and this checker does not make it one;
6. the catalog's *own* `symbolRef` is the book's answer for that part's device.
   A module that declared `identityStatus: bound` may not point at another
   profile and may not fall back to `""`; a module that did not declare it may
   carry nothing else. Item 3 only proves the catalog *has* the device — this
   one proves the catalog spells the identity the book spells, so a catalog and
   a circuit can no longer be wrong together.

Exit is 0 when the book is consistent (the per-profile summary goes to stdout),
1 when it is not (every error to stderr). There is no SKIP: an absent file, an
unreadable profile and a missing evidence file all report differently, and only
the first two are failures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from boardwise.core.symbolprofile import SymbolProfile  # noqa: E402
from boardwise.engines.drawapply import DrawPlanError, load_library  # noqa: E402

BOOK_SCHEMA = "boardwise.symbol-book/1"
BOOK_DIR = Path("blocklib") / "symbols"
BOOK_FILE = BOOK_DIR / "profiles.json"
INDEX_FILE = BOOK_DIR / "index.json"
CATALOG_FILE = Path("blocklib") / "modules" / "catalog.json"

#: Entry fields the contract names one by one; a book that drops one is not a
#: smaller book, it is an unverifiable one.
ENTRY_TEXT_FIELDS = (
    "symbolRef",
    "libraryUuid",
    "title",
    "maturity",
    "source",
    "archiveSha256",
    "geometryHash",
    "profileSha256",
    "reader",
    "editorVersion",
    "sourceTier",
    "acquiredOn",
)
ENTRY_HASH_FIELDS = ("archiveSha256", "geometryHash", "profileSha256")

_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
_EVIDENCE_KINDS = frozenset({"profile", "archive", "device", "acceptance"})
_SOURCE_TIER = "measured-live"
_READER = "boardwise.parsers.elibz.load_elibz2_symbol"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def profile_sha256(obj: dict[str, Any]) -> str:
    """**The** definition, and the only one: insertion key order, no sorting.

    ``sort_keys`` would make the number a statement about the sorted view
    instead of the object the book actually stores, and two books that differ
    only in key order would hash alike — the field exists to catch exactly that.
    """
    text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    return _sha256_bytes(text.encode("utf-8"))


def _absolute_path_problem(value: str) -> str | None:
    """Why `value` reads as a machine-absolute path, or ``None`` when it does not."""
    if value.startswith("/") or value.startswith("\\"):
        return "starts with a path separator"
    if re.match(r"\A[A-Za-z]:", value):
        return "starts with a drive letter"
    if value.startswith("\\\\"):
        return "is a UNC path"
    if "\\" in value:
        return "uses backslashes"
    if value.startswith("~"):
        return "is home-relative"
    return None


def _check_evidence(entry: dict[str, Any], where: str, errors: list[str]) -> None:
    evidence = entry.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append(f"{where}.evidence: must be a non-empty list of provenance records")
        return
    for index, record in enumerate(evidence):
        spot = f"{where}.evidence[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{spot}: must be an object {{kind, path, sha256?}}")
            continue
        extra = sorted(set(record) - {"kind", "path", "sha256", "note"})
        if extra:
            errors.append(f"{spot}: unknown key(s) {extra}")
        kind = record.get("kind")
        if kind not in _EVIDENCE_KINDS:
            errors.append(f"{spot}.kind: {kind!r} is not one of {sorted(_EVIDENCE_KINDS)}")
        path = record.get("path")
        if not isinstance(path, str) or not path:
            errors.append(f"{spot}.path: must be a non-empty string")
            continue
        problem = _absolute_path_problem(path)
        if problem is not None:
            errors.append(f"{spot}.path: {path!r} {problem}; evidence must be repo-relative")
        if ".." in Path(path).parts:
            errors.append(f"{spot}.path: {path!r} reaches outside the repository")
        digest = record.get("sha256")
        if digest is not None and not (isinstance(digest, str) and _HEX64.match(digest)):
            errors.append(f"{spot}.sha256: {digest!r} is not a lowercase sha256 hex digest")


def _catalog_parts(root: Path, errors: list[str]) -> list[dict[str, Any]] | None:
    path = root / CATALOG_FILE
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{path}: cannot be read ({exc})")
        return None
    except ValueError as exc:
        errors.append(f"{path}: is not JSON ({exc})")
        return None
    modules = catalog.get("modules") if isinstance(catalog, dict) else None
    if not isinstance(modules, list):
        errors.append(f"{path}: .modules must be a list")
        return None
    parts: list[dict[str, Any]] = []
    for index, module in enumerate(modules):
        declared = module.get("parts") if isinstance(module, dict) else None
        if not isinstance(declared, list):
            errors.append(f"{path}: modules[{index}].parts must be a list")
            continue
        for item in declared:
            if not isinstance(item, dict):
                errors.append(f"{path}: modules[{index}].parts entries must be objects")
                continue
            parts.append(
                {
                    "module": module.get("id", f"[{index}]"),
                    "moduleIdentityStatus": module.get("identityStatus"),
                    **item,
                }
            )
    return parts


def _book_symbol_refs(entries: list[Any], errors: list[str]) -> dict[str, str]:
    """`deviceUuid -> symbolRef`, exactly as the book's `bindings[]` declare it.

    Two entries binding one device is not a book with two answers: the catalog
    has one `symbolRef` to be compared, so the ambiguity is reported and the
    device is left out of the map (rather than letting the last entry win).
    """
    seen: dict[str, list[str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        symbol_ref = entry.get("symbolRef")
        bindings = entry.get("bindings")
        if not (isinstance(symbol_ref, str) and symbol_ref) or not isinstance(bindings, list):
            continue
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            uuid = binding.get("deviceUuid")
            if isinstance(uuid, str) and uuid:
                seen.setdefault(uuid, []).append(symbol_ref)
    refs: dict[str, str] = {}
    for uuid, found in seen.items():
        distinct = sorted(set(found))
        if len(distinct) > 1:
            errors.append(
                f"index.profiles: device {uuid} is bound to {distinct}; the catalog "
                "declares one symbolRef per device and the book must not give two"
            )
            continue
        refs[uuid] = found[0]
    return refs


def _check_catalog_symbol_refs(
    parts: list[dict[str, Any]], book_refs: dict[str, str], errors: list[str]
) -> None:
    """The catalog's `symbolRef` per part, against the book's, both ways.

    `bound` is the module's own declaration (`identityStatus: bound`), not
    "some book entry happens to bind this device": a module that never opted in
    still says `""` even though its AMS1117 *is* in the book, and calling that a
    conflict would be red on a catalog nobody touched.
    """
    for part in parts:
        uuid = part.get("deviceUuid")
        if not isinstance(uuid, str) or not uuid:
            continue
        where = (
            f"{CATALOG_FILE}: module {part.get('module')!r} part {part.get('role')!r} "
            f"(device {uuid})"
        )
        declared = part.get("symbolRef", "")
        if not isinstance(declared, str):
            errors.append(
                f"{where}.symbolRef: {declared!r} is not a string — '' is how an "
                "unbound part says it names no symbol"
            )
            continue
        expected = book_refs.get(uuid)
        if part.get("moduleIdentityStatus") != "bound":
            if declared:
                errors.append(
                    f"{where}.symbolRef: {declared!r} but the module's identityStatus is "
                    f"{part.get('moduleIdentityStatus')!r}; a part of an unbound module "
                    f"carries '' (the book's answer for this device is {expected!r})"
                )
            continue
        if expected is None:
            errors.append(
                f"{where}.symbolRef: the module is bound to the book but no book entry "
                f"binds device {uuid}"
            )
            continue
        if declared != expected:
            errors.append(
                f"{where}.symbolRef: {declared!r} != the book's {expected!r} for that "
                "device — a bound module names the book's symbol in the catalog too"
            )


def _check_bindings(
    entry: dict[str, Any], where: str, parts: list[dict[str, Any]], errors: list[str]
) -> None:
    bindings = entry.get("bindings")
    if not isinstance(bindings, list) or not bindings:
        errors.append(f"{where}.bindings: must be a non-empty list")
        return
    for index, binding in enumerate(bindings):
        spot = f"{where}.bindings[{index}]"
        if not isinstance(binding, dict):
            errors.append(f"{spot}: must be an object")
            continue
        for field in ("deviceUuid", "lcsc", "mpn", "footprintUuid"):
            value = binding.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"{spot}.{field}: must be a non-empty string")
        uuid = binding.get("deviceUuid")
        if not isinstance(uuid, str) or not uuid:
            continue
        matches = [part for part in parts if part.get("deviceUuid") == uuid]
        if not matches:
            errors.append(
                f"{spot}.deviceUuid: {uuid} is not a part of any module in {CATALOG_FILE}"
            )
            continue
        for field in ("lcsc", "mpn"):
            declared = binding.get(field)
            named = {
                part[field]
                for part in matches
                if isinstance(part.get(field), str) and part[field]
            }
            if not named:
                continue
            for part in matches:
                if field in part and part[field] != declared:
                    errors.append(
                        f"{spot}.{field}: {declared!r} contradicts module "
                        f"{part['module']}'s part {part.get('role')!r} ({part[field]!r})"
                    )
        # The catalog's own ``footprint`` is an EasyEDA footprint label, not the
        # supplier family the device response carries, so the two are compared
        # only through a label the binding copies from the catalog on purpose.
        catalog_footprints = {
            part["footprint"]
            for part in matches
            if isinstance(part.get("footprint"), str) and part["footprint"]
        }
        if len(catalog_footprints) > 1:
            errors.append(
                f"{spot}.deviceUuid: catalog modules disagree on the footprint "
                f"{sorted(catalog_footprints)} for {uuid}"
            )
        declared_footprint = binding.get("catalogFootprint")
        if catalog_footprints and not declared_footprint:
            errors.append(
                f"{spot}.catalogFootprint: the catalog declares "
                f"{sorted(catalog_footprints)[0]!r} for {uuid}; the binding must carry it"
            )
        elif declared_footprint and declared_footprint not in catalog_footprints:
            errors.append(
                f"{spot}.catalogFootprint: {declared_footprint!r} contradicts the "
                f"catalog's {sorted(catalog_footprints)} for {uuid}"
            )
        elif declared_footprint is None and not catalog_footprints:
            continue


def check_book(root: str | Path) -> list[str]:
    """Every inconsistency the checks above can see, in book order."""
    root = Path(root)
    errors: list[str] = []
    index_path = root / INDEX_FILE
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f"{index_path}: cannot be read ({exc})"]
    except ValueError as exc:
        return [f"{index_path}: is not JSON ({exc})"]
    if not isinstance(index, dict):
        return [f"{index_path}: root must be an object"]

    schema = index.get("schema")
    if schema != BOOK_SCHEMA:
        errors.append(f"index.schema: {schema!r} != {BOOK_SCHEMA!r}")
    if index.get("notForDrawCompile") is not True:
        errors.append(
            "index.notForDrawCompile: must be exactly true — the book is a candidate "
            "library, not a runtime drawing gate, and this flag is the statement of that"
        )
    if not isinstance(index.get("libraryUuid"), str) or not index.get("libraryUuid"):
        errors.append("index.libraryUuid: must be a non-empty string")
    entries = index.get("profiles")
    if not isinstance(entries, list) or not entries:
        return errors + ["index.profiles: must be a non-empty list"]

    # 1. the existing loader, unchanged: this is the reader the book is for.
    book_path = root / BOOK_FILE
    try:
        book = load_library(book_path)
    except DrawPlanError as exc:
        return errors + [f"{book_path}: the draw loader refuses the book ({exc})"]

    book_refs = list(book)
    index_refs = [entry.get("symbolRef") for entry in entries if isinstance(entry, dict)]
    if len(index_refs) != len(entries):
        errors.append("index.profiles: every entry must be an object")
    # A symbolRef that is not a string is a malformed entry, not a sort key:
    # `sorted()` would raise `TypeError` on a mixed list and take the whole
    # report down with it, so each one is reported where it sits and the
    # ordering comparison waits until every entry has a string to compare.
    typed = [ref for ref in index_refs if isinstance(ref, str) and ref]
    for position, ref in enumerate(index_refs):
        if not (isinstance(ref, str) and ref):
            errors.append(
                f"index.profiles[{position}].symbolRef: {ref!r} is not a non-empty string"
            )
    if len(typed) != len(index_refs):
        errors.append(
            f"index.profiles: {len(index_refs) - len(typed)} entry(ies) carry no string "
            "symbolRef, so the order cannot be compared with the book"
        )
    positions_by_ref: dict[str, list[int]] = {}
    for position, ref in enumerate(typed):
        positions_by_ref.setdefault(ref, []).append(position)
    for ref, positions in positions_by_ref.items():
        if len(positions) > 1:
            errors.append(
                f"index.profiles: symbolRef {ref} names {len(positions)} entries at "
                f"positions {positions}; one symbolRef, one entry"
            )
    if len(typed) == len(index_refs):
        if index_refs != book_refs:
            missing = [ref for ref in book_refs if ref not in index_refs]
            extra = [ref for ref in index_refs if ref not in book_refs]
            errors.append(
                f"index.profiles: symbolRefs {index_refs} are not the book's {book_refs} "
                f"in the same order (missing {missing}, extra {extra})"
            )
        elif index_refs != sorted(index_refs):
            errors.append(f"index.profiles: {index_refs} is not sorted by symbolRef")

    # 2. every hash, recomputed.
    try:
        book_bytes = book_path.read_bytes()
    except OSError as exc:
        return errors + [f"{book_path}: cannot be read ({exc})"]
    book_sha = _sha256_bytes(book_bytes)
    if index.get("profileBookSha256") != book_sha:
        errors.append(
            f"index.profileBookSha256: {index.get('profileBookSha256')!r} != the "
            f"file's {book_sha}"
        )
    try:
        raw_profiles = json.loads(book_bytes.decode("utf-8"))["profiles"]
    except (ValueError, KeyError, UnicodeDecodeError) as exc:
        return errors + [f"{book_path}: cannot be re-read for profiling ({exc})"]

    parts = _catalog_parts(root, errors)
    if parts is not None:
        _check_catalog_symbol_refs(parts, _book_symbol_refs(entries, errors), errors)
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue

        # Every message names the object it is about: the position alone would
        # send the reader hunting for which profile moved.
        label = entry.get("symbolRef")
        where = f"index.profiles[{position}]"
        if isinstance(label, str) and label:
            where = f"{where} ({label})"
        for field in ENTRY_TEXT_FIELDS:
            if not isinstance(entry.get(field), str) or not entry.get(field):
                errors.append(f"{where}.{field}: must be a non-empty string")
        for field in ENTRY_HASH_FIELDS:
            value = entry.get(field)
            if value is not None and not (isinstance(value, str) and _HEX64.match(value)):
                errors.append(f"{where}.{field}: {value!r} is not a lowercase sha256 hex")
        if entry.get("maturity") != "candidate":
            errors.append(
                f"{where}.maturity: {entry.get('maturity')!r} != 'candidate' — the book "
                "holds unverified candidates only"
            )
        if entry.get("reader") != _READER:
            errors.append(f"{where}.reader: {entry.get('reader')!r} != {_READER!r}")
        if entry.get("sourceTier") != _SOURCE_TIER:
            errors.append(f"{where}.sourceTier: {entry.get('sourceTier')!r} != {_SOURCE_TIER!r}")
        if entry.get("editorVersion") != "4.1.93":
            errors.append(f"{where}.editorVersion: {entry.get('editorVersion')!r} != '4.1.93'")
        if entry.get("libraryUuid") != index.get("libraryUuid"):
            errors.append(
                f"{where}.libraryUuid: {entry.get('libraryUuid')!r} != the book's "
                f"{index.get('libraryUuid')!r}"
            )

        symbol_ref = entry.get("symbolRef")
        if not (isinstance(symbol_ref, str) and symbol_ref):
            # Reported above, by position: an unhashable ref (a list, an int
            # key that is not a symbol) cannot be a dict key, so membership is
            # not where the malformed entry should be discovered.
            continue
        if symbol_ref not in book:
            errors.append(f"{where}.symbolRef: {symbol_ref!r} is not a profile of the book")
            continue
        profile: SymbolProfile = book[symbol_ref]
        if profile.symbol_ref != symbol_ref:
            errors.append(
                f"{where}.symbolRef: the loader read {profile.symbol_ref!r} from this entry"
            )
        if position < len(raw_profiles):
            obj = raw_profiles[position]
            if not isinstance(obj, dict) or obj.get("symbolRef") != symbol_ref:
                errors.append(f"{where}: the book's entry at this position is a different profile")
            else:
                recomputed = profile_sha256(obj)
                if entry.get("profileSha256") != recomputed:
                    errors.append(
                        f"{where}.profileSha256: {entry.get('profileSha256')!r} != the "
                        f"profile object's {recomputed}"
                    )
                if entry.get("title") is not None and entry.get("title") != obj.get("title"):
                    errors.append(
                        f"{where}.title: {entry.get('title')!r} != the profile's "
                        f"{obj.get('title')!r}"
                    )
                source = obj.get("source")
                if entry.get("source") != source:
                    errors.append(
                        f"{where}.source: {entry.get('source')!r} != the profile's {source!r}"
                    )
                archive_sha = entry.get("archiveSha256")
                expected_source = f"elibz2:{symbol_ref}:sha256:{archive_sha}"
                if source != expected_source:
                    errors.append(
                        f"{where}.source: the profile's source {source!r} does not bind "
                        f"this symbolRef and archiveSha256 ({expected_source!r})"
                    )
        geometry = profile.geometry_hash()
        if entry.get("geometryHash") != geometry:
            errors.append(
                f"{where}.geometryHash: {entry.get('geometryHash')!r} != the profile's {geometry}"
            )
        _check_evidence(entry, where, errors)
        if parts is not None:
            _check_bindings(entry, where, parts, errors)

    return errors


def validate_book(root: str | Path) -> list[str]:
    """The messages :func:`check_book` found, ready to print. Empty means green."""
    return check_book(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_symbol_book",
        description=(
            "Verify blocklib/symbols/{profiles.json,index.json} against the catalog. "
            "Reads no outputs/ and no editor."
        ),
    )
    parser.add_argument("--root", default=str(ROOT), help="repository root (default: this checkout)")
    args = parser.parse_args(argv)
    root = Path(args.root)
    errors = validate_book(root)
    if errors:
        for message in errors:
            print(message, file=sys.stderr)
        print(f"symbol book: {len(errors)} problem(s)", file=sys.stderr)
        return 1
    index = json.loads((root / INDEX_FILE).read_text(encoding="utf-8"))
    print(f"symbol book: ok — {len(index['profiles'])} candidate profile(s), "
          f"profileBookSha256 {index['profileBookSha256']}")
    for entry in index["profiles"]:
        print(f"  {entry['symbolRef']}  {entry['title']}  "
              f"geometry {entry['geometryHash'][:12]}  archive {entry['archiveSha256'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
