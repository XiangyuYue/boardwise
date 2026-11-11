"""038Q2: the upstream module seed, read back through the circuit loader.

The Rust side (`rust/crates/boardwise-core/tests/module_import.rs`) pins the
normaliser's refusals. What is checked here is the deliverable itself:

* the four candidate circuits load with the **existing** ``CircuitSpec`` loader,
  so "one net, many members", the port nets and the draft flag mean the same
  thing to the rest of the repository as any other circuit;
* every curated port lands on the net, direction and class the curation decided,
  ``VIN``/``EN`` are not shorted by their shared ``default_net`` suggestion,
  wildcard pin groups stay as written, and Block attribution is structured;
* the published module tree is exactly four circuits + catalog + manifest +
  the upstream licence, and the manifest digests every input and output (itself
  excepted) while the licence is byte-identical to the curated copy;
* nothing that upstream keeps as free text or as a coordinate reaches the
  published files. The *names* of those historical strings are never written
  here: when ``.tmp_038q2_upstream/`` is present they are collected from the raw
  samples at run time and searched for; when it is absent the structural
  allowlist below still runs, so a fresh clone checks the same shape without
  carrying any identifier in the repository.

The raw upstream downloads live in ``.tmp_038q2_upstream/`` and never enter the
repository.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts" / "module-import"
MODULES = ROOT / "blocklib" / "modules"
CIRCUITS = MODULES / "circuits"
RAW = ROOT / ".tmp_038q2_upstream"

UPSTREAM_COMMIT = "69af00c0db3960757bff36a68edb286adcd64458"

#: module id -> output stem
ASSETS = {
    "block.ams1117_ldo_3v3": "ams1117_ldo_3v3",
    "block.sy8089_buck_3v3": "sy8089_buck_3v3",
    "lib.sy8089_buck_3v3_live": "sy8089_buck_3v3_live",
    "block.ch340c_usb_serial": "ch340c_usb_serial",
}

#: stem -> (parts, nets, open interfaces)
#:
#: ``ch340c_usb_serial`` is 7/11/6 rather than 7/7/6: its upstream
#: ``internal_nets`` carry no TXD/RXD/DTR#/RTS# membership at all, and curation
#: rules those four ports ``port_pin_only``, so each gets a one-member
#: ``port.<name>`` net. Dropping them would have discarded four curated ports and
#: left four declared interfaces with no net; inventing a connection would have
#: been worse. The loader refuses an interface over a net the spec does not
#: declare, so 7 + 4 = 11 nets and 6 interfaces is both the honest and the
#: loadable shape.
EXPECTED_COUNTS = {
    "ams1117_ldo_3v3": (4, 3, 3),
    "sy8089_buck_3v3": (7, 6, 4),
    "sy8089_buck_3v3_live": (10, 6, 3),
    "ch340c_usb_serial": (7, 11, 6),
}

#: stem -> port name -> (net id, direction, class)
EXPECTED_PORTS = {
    "ams1117_ldo_3v3": {
        "VIN_5V": ("port.VIN_5V", "source", "power"),
        "3V3": ("port.3V3", "load", "power"),
        "GND": ("port.GND", "", "gnd"),
    },
    "sy8089_buck_3v3": {
        "VIN": ("port.VIN", "source", "power"),
        "3V3": ("port.3V3", "load", "power"),
        "EN": ("port.EN", "input", "signal"),
        "GND": ("port.GND", "", "gnd"),
    },
    "sy8089_buck_3v3_live": {
        "POWER_IN": ("port.POWER_IN", "source", "power"),
        "POWER_OUT": ("port.POWER_OUT", "load", "power"),
        "GND": ("port.GND", "", "gnd"),
    },
    "ch340c_usb_serial": {
        "VBUS_5V": ("port.VBUS_5V", "load", "power"),
        "GND": ("port.GND", "", "gnd"),
        "TXD": ("port.TXD", "output", "signal"),
        "RXD": ("port.RXD", "input", "signal"),
        "DTR": ("port.DTR", "output", "signal"),
        "RTS": ("port.RTS", "output", "signal"),
    },
}

#: The source allowlist: exactly the fields the redaction may carry. A key that
#: is not here is a leak, whatever sample it came from.
ALLOWED_INPUT_KEYS = {
    "blocks/demo": {
        "id", "category", "author", "contributors", "parts", "internal_nets", "ports",
    },
    "block.part": {"part", "qty", "value_override"},
    "block.port": {"dir", "at", "default_net"},
    "topology": {"schemaVersion", "kind", "module"},
    "topology.module": {"id", "title", "maturity", "parts", "nets", "verification"},
    "topology.part": {"role", "lcsc", "device", "footprint", "pins"},
    "topology.device": {"libraryUuid", "deviceUuid", "name"},
    "topology.pin": {"number", "name", "net", "connectionState"},
    "topology.net": {"id", "members", "port"},
    "topology.verification": {
        "pinNetReadback", "deviceIdentityResolution", "geometry", "pcb", "bringup",
    },
    "standard-parts": {"libraryUuid", "parts"},
    "standard-part": {
        "value", "mpn", "lcsc", "manufacturer", "deviceUuid", "footprint", "package", "basic",
    },
    "curation": {
        "schema", "upstream", "assets", "standardParts", "sourceManifest", "license",
    },
    "curation.asset": {
        "id", "kind", "output", "ports", "source", "sourcePath", "sourceSha256",
        "upstreamMaturity",
    },
    "curation.ruling": {"direction", "class", "part", "netSource"},
    "source-manifest": {"schema", "upstream", "files", "filters"},
    "source-manifest.file": {
        "upstreamPath", "originalSha256", "redactedPath", "redactedSha256",
    },
}

#: Fields upstream keeps as prose. Their *values* are the identifiers that must
#: not be republished; the names themselves are part of the contract's filter.
FREE_TEXT_KEYS = frozenset({
    "_doc",
    "bom_note",
    "desc",
    "keepout",
    "note",
    "pcb_layout",
    "placement",
    "reason",
    "route",
    "schematic_layout",
    "schematic_notes",
    "source",
    "validated",
    "_internal_nets_note",
})

#: Keys that would mean a place on a canvas, or a claim this batch cannot make.
BANNED_KEYS = frozenset({
    "schematic_layout",
    "pcb_layout",
    "bom_note",
    "desc",
    "validated",
    "x",
    "y",
    "at",
    "rotation",
    "points",
})

#: A run is deterministic, so nothing may record when it happened.
TIMESTAMP_KEYS = frozenset({"generatedAt", "timestamp", "mtime", "createdAt"})

#: Deleting files is not this batch's business, in code either.
DELETION_CALLS = ("remove_dir_all", "remove_dir(", "remove_file(", "TempDir")

OWN_SOURCES = (
    ROOT / "rust/crates/boardwise-core/src/module_import.rs",
    ROOT / "rust/crates/boardwise-core/tests/module_import.rs",
    ROOT / "rust/crates/boardwise-cli/src/module_import.rs",
    ROOT / "rust/crates/boardwise-cli/tests/module_import.rs",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def texts_under(directory: Path) -> list[tuple[Path, str]]:
    return [
        (path, path.read_text(encoding="utf-8"))
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    ]


def keys_of(payload) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            found.add(key)
            found |= keys_of(value)
    elif isinstance(payload, list):
        for item in payload:
            found |= keys_of(item)
    return found


def free_text_strings(payload) -> set[str]:
    """Every string value stored under one of ``FREE_TEXT_KEYS``, however deep."""
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in FREE_TEXT_KEYS:
                found |= _strings(value)
            else:
                found |= free_text_strings(value)
    elif isinstance(payload, list):
        for item in payload:
            found |= free_text_strings(item)
    return found


def _strings(value) -> set[str]:
    if isinstance(value, str):
        return {value}
    found: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            found |= _strings(item)
    elif isinstance(value, list):
        for item in value:
            found |= _strings(item)
    return found


def allowlist_violations(payload, kind: str) -> set[str]:
    """Keys carried by one input document that the allowlist does not name."""
    named = ALLOWED_INPUT_KEYS[kind]
    return {key for key in payload} - named


@pytest.fixture(scope="module")
def catalog() -> dict:
    return load_json(MODULES / "catalog.json")


@pytest.fixture(scope="module")
def manifest() -> dict:
    return load_json(MODULES / "manifest.json")


@pytest.fixture(scope="module")
def curation() -> dict:
    return load_json(CONTRACTS / "curation.json")


@pytest.fixture(scope="module")
def circuits() -> dict[str, CircuitSpec]:
    return {
        stem: CircuitSpec.load(CIRCUITS / f"{stem}.circuit.json")
        for stem in EXPECTED_COUNTS
    }


def test_exactly_the_four_candidates_and_the_licence_are_published() -> None:
    assert sorted(path.name for path in CIRCUITS.glob("*.json")) == sorted(
        f"{stem}.circuit.json" for stem in EXPECTED_COUNTS
    )
    assert (MODULES / "catalog.json").is_file()
    assert (MODULES / "manifest.json").is_file()
    assert (MODULES / "upstream" / "LICENSE").is_file()
    assert (MODULES / "upstream" / "LICENSE").read_bytes() == (
        CONTRACTS / "LICENSE"
    ).read_bytes(), "the published licence is the curated upstream copy, byte for byte"


def test_every_circuit_loads_with_the_existing_loader(circuits) -> None:
    for stem, spec in circuits.items():
        parts, nets, interfaces = EXPECTED_COUNTS[stem]
        assert (len(spec.parts), len(spec.nets), len(spec.open_interfaces)) == (
            parts,
            nets,
            interfaces,
        ), stem
        assert spec.nc == [], f"{stem}: a Block leaves unmentioned pins unmentioned"
        assert spec.draft is True, f"{stem}: imported facts are unconfirmed"
        assert spec.operating_conditions == {}
        for part in spec.parts:
            assert part.provenance == "ai_asserted"
            assert part.symbol_ref, "the loader refuses an empty symbolRef"
        for net in spec.nets:
            assert net.provenance == "ai_asserted"
            assert net.members, f"{stem} {net.id}: a net with no members"
            assert net.member_provenance == {}
        for interface in spec.open_interfaces:
            assert interface.provenance == "ai_asserted"


def test_every_curated_port_lands_where_the_ruling_said(circuits, catalog) -> None:
    by_id = {module["id"]: module for module in catalog["modules"]}
    for module_id, stem in ASSETS.items():
        spec = circuits[stem]
        interfaces = {entry.net: entry for entry in spec.open_interfaces}
        expect = EXPECTED_PORTS[stem]
        assert set(expect) == {entry.role for entry in spec.open_interfaces}, stem
        assert len(expect) == len(spec.open_interfaces), f"{stem}: one interface per port"
        catalog_ports = {port["name"]: port for port in by_id[module_id]["ports"]}
        assert set(catalog_ports) == set(expect)
        for name, (net_id, direction, net_class) in expect.items():
            interface = interfaces[net_id]
            assert interface.role == name
            assert interface.direction == direction, f"{stem} {name}"
            net = spec.net(net_id)
            assert net is not None, f"{stem} {name}: interface references a missing net"
            assert net.cls == net_class, f"{stem} {name}"
            assert catalog_ports[name]["net"] == net_id
            assert catalog_ports[name]["direction"] == direction
            assert catalog_ports[name]["class"] == net_class


def test_a_shared_default_net_does_not_short_vin_and_en(circuits, catalog) -> None:
    spec = circuits["sy8089_buck_3v3"]
    vin = spec.net("port.VIN")
    en = spec.net("port.EN")
    assert vin is not None and en is not None
    assert set(vin.members).isdisjoint(en.members)
    assert sorted(en.members) == ["U.EN"]
    hints = {
        port["name"]: port["defaultNet"]
        for port in next(
            module
            for module in catalog["modules"]
            if module["id"] == "block.sy8089_buck_3v3"
        )["ports"]
    }
    # The suggestion is recorded, and it did not become wiring.
    assert hints["VIN"] == hints["EN"] == "VSYS"


def test_wildcard_pins_are_kept_as_written_and_flag_the_module(circuits, catalog) -> None:
    by_id = {module["id"]: module for module in catalog["modules"]}
    ams = circuits["ams1117_ldo_3v3"]
    assert "U.VOUT*" in ams.net("port.3V3").members
    assert by_id["block.ams1117_ldo_3v3"]["unresolvedWildcards"] == ["U.VOUT*"]

    ch340 = circuits["ch340c_usb_serial"]
    for member in ("J_USB.GND*", "J_USB.EP*", "J_USB.VBUS*"):
        assert member in ch340.net("port.GND").members + ch340.net("port.VBUS_5V").members
    assert by_id["block.ch340c_usb_serial"]["unresolvedWildcards"] == [
        "D_ESD.I/O1*",
        "D_ESD.I/O2*",
        "J_USB.EP*",
        "J_USB.GND*",
        "J_USB.VBUS*",
    ]
    for module_id, module in by_id.items():
        text = json.dumps(module)
        if module["unresolvedWildcards"]:
            assert module["notForDrawCompile"] is True, module_id
            for wildcard in module["unresolvedWildcards"]:
                assert wildcard.endswith("*")
                assert wildcard in text


def test_the_usb_interface_keeps_its_receptacle(circuits, catalog) -> None:
    spec = circuits["ch340c_usb_serial"]
    vbus = next(entry for entry in spec.open_interfaces if entry.net == "port.VBUS_5V")
    assert vbus.part == "J_USB"
    assert spec.part("J_USB") is not None
    module = next(
        entry for entry in catalog["modules"] if entry["id"] == "block.ch340c_usb_serial"
    )
    assert (
        next(port for port in module["ports"] if port["name"] == "VBUS_5V")["part"] == "J_USB"
    )
    # The four signal ports have no upstream net; their net is the pin alone.
    for name, pin in (
        ("TXD", "U.TXD"),
        ("RXD", "U.RXD"),
        ("DTR", "U.DTR#"),
        ("RTS", "U.RTS#"),
    ):
        net = spec.net(f"port.{name}")
        assert net is not None and net.members == [pin]


def test_every_module_is_a_candidate_not_for_draw_compile(catalog) -> None:
    assert catalog["schema"] == "boardwise.module-catalog/1"
    assert catalog["upstream"]["commit"] == UPSTREAM_COMMIT
    assert [module["id"] for module in catalog["modules"]] == sorted(ASSETS)
    for module in catalog["modules"]:
        assert module["maturity"] == "candidate"
        assert module["identityStatus"] == "unverified"
        assert module["notForDrawCompile"] is True
        assert module["circuit"].startswith("circuits/")
        assert module["source"].keys() == {"commit", "path", "sha256"}
        assert module["source"]["commit"] == UPSTREAM_COMMIT
        assert len(module["source"]["sha256"]) == 64
        assert module["source"]["path"]
        assert module["limitations"], "a candidate states why it is not ready"
        assert any("GENERIC-" in line for line in module["limitations"])
        for part in module["parts"]:
            assert part["symbolRef"] == "", "no symbol was identified"


def test_attribution_is_structured_and_only_where_upstream_states_it(catalog) -> None:
    by_id = {module["id"]: module for module in catalog["modules"]}
    for module_id in (
        "block.ams1117_ldo_3v3",
        "block.sy8089_buck_3v3",
        "block.ch340c_usb_serial",
    ):
        attribution = by_id[module_id]["attribution"]
        assert set(attribution) == {"author", "contributors"}
        assert attribution["author"], module_id
        assert isinstance(attribution["contributors"], list)
    assert by_id["block.ch340c_usb_serial"]["attribution"]["contributors"] == ["Codex"]
    assert by_id["block.ams1117_ldo_3v3"]["attribution"]["contributors"] == []
    assert "attribution" not in by_id["lib.sy8089_buck_3v3_live"], (
        "a role topology states no author, so none is invented"
    )


def test_the_catalog_carries_no_prose_and_no_coordinates() -> None:
    for path, text in texts_under(MODULES):
        payload = json.loads(text) if path.suffix == ".json" else None
        if payload is not None:
            found = keys_of(payload) & BANNED_KEYS
            assert not found, f"{path} carries {found}"
            found = keys_of(payload) & TIMESTAMP_KEYS
            assert not found, f"{path} carries {found}"


def test_the_redacted_inputs_stay_inside_the_source_allowlist() -> None:
    for name in ("ams1117_ldo_3v3", "sy8089_buck_3v3", "ch340c_usb_serial"):
        block = load_json(CONTRACTS / "blocks" / f"{name}.json")
        assert not allowlist_violations(block, "blocks/demo"), name
        for role, part in block["parts"].items():
            assert not allowlist_violations(part, "block.part"), f"{name} {role}"
        for port, entry in block["ports"].items():
            assert not allowlist_violations(entry, "block.port"), f"{name} {port}"
    topology = load_json(CONTRACTS / "topologies" / "sy8089_buck_3v3_live.json")
    assert not allowlist_violations(topology, "topology")
    module = topology["module"]
    assert not allowlist_violations(module, "topology.module")
    for part in module["parts"]:
        assert not allowlist_violations(part, "topology.part"), part["role"]
        assert not allowlist_violations(part["device"], "topology.device")
        for pin in part["pins"]:
            assert not allowlist_violations(pin, "topology.pin")
    for net in module["nets"]:
        assert not allowlist_violations(net, "topology.net")
    assert not allowlist_violations(module["verification"], "topology.verification")

    standard = load_json(CONTRACTS / "standard-parts.json")
    assert not allowlist_violations(standard, "standard-parts")
    for reference, part in standard["parts"].items():
        assert not allowlist_violations(part, "standard-part"), reference

    curation = load_json(CONTRACTS / "curation.json")
    assert not allowlist_violations(curation, "curation")
    for asset in curation["assets"]:
        assert not allowlist_violations(asset, "curation.asset"), asset["id"]
        for port, ruling in asset["ports"].items():
            assert not allowlist_violations(ruling, "curation.ruling"), port

    source_manifest = load_json(CONTRACTS / "source-manifest.json")
    assert not allowlist_violations(source_manifest, "source-manifest")
    for entry in source_manifest["files"]:
        assert not allowlist_violations(entry, "source-manifest.file")


def test_the_manifest_recomputes_every_digest(manifest, curation) -> None:
    assert manifest["schema"] == "boardwise.module-import-manifest/1"
    assert manifest["upstream"]["commit"] == UPSTREAM_COMMIT
    paths = [entry["path"] for entry in manifest["inputs"]]
    assert paths == sorted(paths), "inputs are written in a stable order"
    for expected in (
        "contracts/module-import/curation.json",
        "contracts/module-import/source-manifest.json",
        "contracts/module-import/LICENSE",
    ):
        assert expected in paths, expected
    for entry in manifest["inputs"]:
        assert sha256(ROOT / entry["path"]) == entry["sha256"], entry["path"]
    outputs = [entry["path"] for entry in manifest["outputs"]]
    assert outputs == sorted(outputs)
    assert "manifest.json" not in outputs, "a manifest cannot digest itself"
    assert "upstream/LICENSE" in outputs
    for entry in manifest["outputs"]:
        assert sha256(MODULES / entry["path"]) == entry["sha256"], entry["path"]
    assert {path.name for path in CIRCUITS.glob("*.json")} | {
        "catalog.json"
    } <= {Path(entry["path"]).name for entry in manifest["outputs"]}
    assert set(outputs) == {
        "catalog.json",
        "upstream/LICENSE",
        *(f"circuits/{stem}.circuit.json" for stem in EXPECTED_COUNTS),
    }
    assert len(curation["assets"]) == 4
    assert curation["license"] == "contracts/module-import/LICENSE"
    assert curation["sourceManifest"] == "contracts/module-import/source-manifest.json"


def test_the_files_are_lf_with_a_final_newline() -> None:
    """No timestamps, no ordering drift: the same inputs give the same bytes."""
    for path, text in texts_under(MODULES) + texts_under(CONTRACTS):
        assert "\r\n" not in text, f"{path} is not LF"
        assert text.endswith("\n"), f"{path} misses the final newline"


def test_the_batch_deletes_nothing_in_code_either() -> None:
    for path in OWN_SOURCES:
        text = path.read_text(encoding="utf-8")
        for call in DELETION_CALLS:
            assert call not in text, f"{path.name} uses {call}"


@pytest.mark.skipif(not RAW.exists(), reason="raw upstream samples are not in this checkout")
def test_no_free_text_from_the_pinned_originals_is_republished() -> None:
    """The banned strings are collected at run time, never written down here."""
    sample_paths = [
        RAW / "internal/blocks/data/ams1117_ldo_3v3.json",
        RAW / "internal/blocks/data/sy8089_buck_3v3.json",
        RAW / "internal/blocks/data/ch340c_usb_serial.json",
        RAW / ".agents/skills/easyeda-agent/library/modules/sy8089-buck-3v3.topology.json",
        RAW / ".agents/skills/easyeda-agent/references/standard-parts.json",
    ]
    prose: set[str] = set()
    for path in sample_paths:
        prose |= free_text_strings(load_json(path))
    prose = {text.strip() for text in prose if len(text.strip()) >= 8}
    assert len(prose) > 20, "the samples do contain free text to check against"
    assert any(len(text) > 60 for text in prose), (
        "an evidence sentence was collected, not just short labels"
    )

    published = texts_under(MODULES) + texts_under(CONTRACTS)
    for path, text in published:
        for fragment in prose:
            assert fragment not in text, f"{path} republishes upstream free text"


@pytest.mark.skipif(not RAW.exists(), reason="raw upstream samples are not in this checkout")
def test_the_redaction_is_faithful_to_the_pinned_originals() -> None:
    declared = load_json(RAW / "source-manifest.json")
    assert declared["commit"] == UPSTREAM_COMMIT
    originals = {entry["path"]: entry["sha256"] for entry in declared["files"]}
    for path, digest in originals.items():
        assert sha256(RAW / path) == digest, f"{path} is not the pinned sample"

    source_manifest = load_json(CONTRACTS / "source-manifest.json")
    assert source_manifest["schema"] == "boardwise.module-import-source-manifest/1"
    assert source_manifest["upstream"]["commit"] == UPSTREAM_COMMIT
    for entry in source_manifest["files"]:
        assert entry["originalSha256"] == originals[entry["upstreamPath"]]
        assert sha256(CONTRACTS / entry["redactedPath"]) == entry["redactedSha256"]
        if not entry["redactedPath"].endswith(".json"):
            continue
        derived = load_json(CONTRACTS / entry["redactedPath"])
        # The redacted input keeps the upstream `at` hint; prose and layout are gone.
        assert not (keys_of(derived) & (BANNED_KEYS - {"at"})), entry["redactedPath"]
    by_path = {
        entry["upstreamPath"]: entry["originalSha256"] for entry in source_manifest["files"]
    }
    for asset in load_json(CONTRACTS / "curation.json")["assets"]:
        assert by_path[asset["sourcePath"]] == asset["sourceSha256"], asset["id"]


@pytest.mark.skipif(not RAW.exists(), reason="raw upstream samples are not in this checkout")
def test_the_licence_is_the_upstream_one_byte_for_byte() -> None:
    upstream = RAW / "LICENSE"
    assert (CONTRACTS / "LICENSE").read_bytes() == upstream.read_bytes()
    assert (MODULES / "upstream" / "LICENSE").read_bytes() == upstream.read_bytes()
    declared = load_json(RAW / "source-manifest.json")
    licence_sha = next(
        entry["sha256"] for entry in declared["files"] if entry["path"] == "LICENSE"
    )
    assert sha256(CONTRACTS / "LICENSE") == licence_sha
    assert sha256(MODULES / "upstream" / "LICENSE") == licence_sha
