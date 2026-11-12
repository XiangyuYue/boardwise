"""038Q12: the CH340C module's explicit electrical pin contract.

The generator side is pinned in Rust
(`rust/crates/boardwise-core/tests/module_import.rs`): five wildcard groups, a
missing or extra group, an empty group, a cross-role member, an unknown pin, a
composite number split in half, a pin name carried by two pads, an NC on a net, a
port pin the port does not carry, `portPins` on a `port_pin_only` port and a
contract stated on an unbound asset are each refused there. This file asks what
the published tree has to answer:

* the five groups are gone and the twelve physical members are on the right
  nets, with the composite numbers (`A1B12`, `B1A12`, `A4B9`, `B4A9`) kept whole;
* `U.DTR#`/`U.RTS#` are the exact pins (not a fuzzy match), and `U.7` is the only
  no-connect;
* every profile pin of the seven parts is connected, NC or unstated — the three
  classes are disjoint and together cover the profiles;
* the identity is bound, while `maturity`/`notForDrawCompile`/`draft` stay where
  they were: an explicit pin map is not a drawing, a compile or a board.

Nothing here runs the CLI, reads the editor, expands a prefix or adds a second
geometry algorithm.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts" / "module-import"
MODULES = ROOT / "blocklib" / "modules"
CIRCUITS = MODULES / "circuits"
BOOK_DIR = ROOT / "blocklib" / "symbols"

MODULE_ID = "block.ch340c_usb_serial"
STEM = "ch340c_usb_serial"

#: The one NC the symbol itself states (`NC.` on pin 7). Every other unused pin
#: carries no connection declaration and is therefore unstated, never NC.
NC_PINS = ["U.7"]

#: Pin groups as curated, and the physical pins each of them stands for.
PIN_GROUPS = {
    "D_ESD.I/O1*": ["D_ESD.1", "D_ESD.6"],
    "D_ESD.I/O2*": ["D_ESD.3", "D_ESD.4"],
    "J_USB.EP*": ["J_USB.8", "J_USB.9", "J_USB.10", "J_USB.11"],
    "J_USB.GND*": ["J_USB.A1B12", "J_USB.B1A12"],
    "J_USB.VBUS*": ["J_USB.A4B9", "J_USB.B4A9"],
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog() -> dict:
    return _read(MODULES / "catalog.json")


def _module() -> dict:
    return next(entry for entry in _catalog()["modules"] if entry["id"] == MODULE_ID)


def _spec() -> dict:
    return _read(CIRCUITS / f"{STEM}.circuit.json")


def _nets() -> dict[str, list[str]]:
    return {net["id"]: net["members"] for net in _spec()["nets"]}


def _profile_of(role: str) -> dict:
    """The published profile of one role, reached through the catalog."""
    catalog_part = next(part for part in _module()["parts"] if part["role"] == role)
    profiles = _read(BOOK_DIR / "profiles.json")["profiles"]
    return next(
        profile
        for profile in profiles
        if profile["symbolRef"] == catalog_part["symbolRef"]
    )


# --------------------------------------------------------------------------
# curation states one group at a time, and nothing else


def test_curation_states_the_contract_on_the_bound_block_only() -> None:
    assets = {asset["id"]: asset for asset in _read(CONTRACTS / "curation.json")["assets"]}
    ch340 = assets[MODULE_ID]
    assert ch340["identityBinding"] == "book"
    assert ch340["pinGroups"] == PIN_GROUPS
    assert ch340["portPins"] == {"VBUS_5V": ["J_USB.A4B9", "J_USB.B4A9"]}
    assert ch340["nc"] == NC_PINS
    # VBUS_5V is the module's 5V boundary, realised by the receptacle, and still
    # a load; the signal ports keep their port_pin_only net source.
    assert ch340["ports"]["VBUS_5V"] == {
        "class": "power",
        "direction": "load",
        "part": "J_USB",
    }
    for name in ("DTR", "RTS", "TXD", "RXD"):
        assert ch340["ports"][name]["netSource"] == "port_pin_only", name
    for asset in assets.values():
        if asset["id"] == MODULE_ID:
            continue
        # The SY8089 block is bound (038Q10) but states no pin contract of its
        # own; nothing else is bound at all.
        if asset["id"] != "block.sy8089_buck_3v3":
            assert "identityBinding" not in asset, asset["id"]
        for field in ("pinGroups", "portPins", "nc"):
            assert field not in asset, (asset["id"], field)


def test_the_upstream_block_is_untouched() -> None:
    """The electrical ruling lives in curation; the pinned sample says nothing."""
    block = _read(CONTRACTS / "blocks" / f"{STEM}.json")
    assert block["id"] == MODULE_ID
    # The upstream file still carries the five wildcard members verbatim.
    members = [member for net in block["internal_nets"] for member in net]
    for wildcard in PIN_GROUPS:
        assert wildcard in members, wildcard
    assert _module()["source"]["sha256"] == _sha_of_ledger("ch340c_usb_serial")


def _sha_of_ledger(stem: str) -> str:
    ledger = _read(CONTRACTS / "source-manifest.json")
    path = f"internal/blocks/data/{stem}.json"
    entry = next(item for item in ledger["files"] if item["upstreamPath"] == path)
    return entry["originalSha256"]


# --------------------------------------------------------------------------
# the wildcard groups are gone, their pads are wired


def test_every_group_member_lands_on_the_net_its_group_was_on() -> None:
    upstream = _read(CONTRACTS / "blocks" / f"{STEM}.json")
    published = _nets()
    for index, raw_net in enumerate(upstream["internal_nets"]):
        port = next(
            (token[len("PORT:") :] for token in raw_net if token.startswith("PORT:")),
            None,
        )
        expected = []
        for token in raw_net:
            if token.startswith("PORT:"):
                continue
            expected.extend(PIN_GROUPS.get(token, [token]))
        if port is not None:
            net_id = f"port.{port}"
        else:
            hits = [name for name, members in published.items() if set(expected) <= set(members)]
            assert len(hits) == 1, (index, expected, hits)
            net_id = hits[0]
        assert published[net_id] == sorted(expected), (index, net_id)
    text = json.dumps(_spec())
    assert "*" not in text, "a bound module writes no wildcard member"
    assert '"J_USB.VBUS"' not in text, "the group name never becomes a third pin"


def test_the_composite_pin_numbers_are_kept_whole() -> None:
    published = _nets()
    gnd = published["port.GND"]
    vbus = published["port.VBUS_5V"]
    for pin in ("J_USB.A1B12", "J_USB.B1A12"):
        assert pin in gnd, pin
    for pin in ("J_USB.A4B9", "J_USB.B4A9"):
        assert pin in vbus, pin
    # Not split into the halves a reader might invent.
    for fragment in ("A1", "B12", "A4", "B9", "A12", "B1"):
        assert f"J_USB.{fragment}" not in gnd + vbus, fragment


def test_the_usb_esd_pins_are_all_wired_not_internally_shorted() -> None:
    published = _nets()
    minus = published["auto:D_ESD.1|D_ESD.6|J_USB.DN1|J_USB.DN2|U.D-"]
    plus = published["auto:D_ESD.3|D_ESD.4|J_USB.DP1|J_USB.DP2|U.D+"]
    assert {"D_ESD.1", "D_ESD.6"} <= set(minus)
    assert {"D_ESD.3", "D_ESD.4"} <= set(plus)
    # The profile really does carry both pins of each I/O pair.
    profile = _profile_of("D_ESD")
    names = {pin["number"]: pin["name"] for pin in profile["pins"]}
    assert names["1"] == names["6"] == "I/O1"
    assert names["3"] == names["4"] == "I/O2"


def test_the_port_pins_are_the_pads_the_port_name_carries() -> None:
    published = _nets()
    assert set(published["port.VBUS_5V"]) >= {"J_USB.A4B9", "J_USB.B4A9"}
    # The port pin alone is not the net: VCC and the bulk cap sit on it too.
    for member in ("U.VCC", "C_VCC.1", "D_ESD.VBUS"):
        assert member in published["port.VBUS_5V"], member
    assert "U.V3" not in published["port.VBUS_5V"], "V3 is not the 5V boundary"
    assert "U.V3" in published["auto:C_V3.1|U.V3"]


def test_the_serial_pins_are_exact_and_only_u7_is_nc() -> None:
    published = _nets()
    assert published["port.DTR"] == ["U.DTR#"]
    assert published["port.RTS"] == ["U.RTS#"]
    assert published["port.TXD"] == ["U.TXD"]
    assert published["port.RXD"] == ["U.RXD"]
    profile = _profile_of("U")
    numbers = {pin["name"]: pin["number"] for pin in profile["pins"]}
    assert numbers["DTR#"] == "13" and numbers["RTS#"] == "14"
    assert numbers["NC."] == "7"

    assert _spec()["nc"] == [{"pin": pin, "provenance": "ai_asserted"} for pin in NC_PINS]
    connected = {member for members in published.values() for member in members}
    assert "U.7" not in connected
    module = _module()
    for pin in ("U.OUT#", "U.CTS#", "U.DSR#", "U.RI#", "U.DCD#", "U.R232"):
        assert pin not in module["unstatedPins"], f"{pin} spelled as a name is not a pad"
    for pin in ("U.8", "U.9", "U.10", "U.11", "U.12", "U.15"):
        assert pin in module["unstatedPins"], pin


# --------------------------------------------------------------------------
# reconciliation: connected, NC, unstated


def _pin_numbers(token: str) -> set[str]:
    """Every profile pin number this written member identifies."""
    role, part = token.split(".", 1)
    profile = _profile_of(role)
    hits = {
        pin["number"]
        for pin in profile["pins"]
        if part in (pin["number"], pin["name"])
    }
    assert hits, f"{token} is not a pad of {profile['symbolRef']}"
    return {f"{role}.{number}" for number in hits}


def test_every_profile_pin_is_connected_nc_or_unstated() -> None:
    module = _module()
    connected: set[str] = set()
    for members in _nets().values():
        for member in members:
            connected |= _pin_numbers(member)
    nc = set(NC_PINS)
    unstated = set(module["unstatedPins"])

    assert not (connected & nc), connected & nc
    assert not (connected & unstated), connected & unstated
    assert not (nc & unstated), nc & unstated

    profile_pins = {
        f"{part['role']}.{pin['number']}"
        for part in module["parts"]
        for pin in _profile_of(part["role"])["pins"]
    }
    assert connected | nc | unstated == profile_pins, sorted(
        profile_pins ^ (connected | nc | unstated)
    )
    # The unused CH340C functions and the Type-C SBUs are unstated, not NC.
    assert unstated == {
        "J_USB.A8",
        "J_USB.B8",
        "U.10",
        "U.11",
        "U.12",
        "U.15",
        "U.8",
        "U.9",
    }


def test_the_profile_pin_numbers_are_unique_per_profile() -> None:
    seen = {}
    for part in _module()["parts"]:
        profile = _profile_of(part["role"])
        numbers = [pin["number"] for pin in profile["pins"]]
        assert len(numbers) == len(set(numbers)), part["role"]
        # Two pads may share a name (I/O1, I/O2, EP, VBUS, GND); the number is the
        # atom a member resolves to.
        seen[part["role"]] = numbers
    assert seen["J_USB"].count("A1B12") == 1
    assert "A1" not in seen["J_USB"] and "B12" not in seen["J_USB"]


def test_the_identity_is_bound_but_nothing_else_moved() -> None:
    module = _module()
    assert module["identityStatus"] == "bound"
    assert module["unresolvedWildcards"] == []
    assert module["maturity"] == "candidate"
    assert module["notForDrawCompile"] is True
    assert _spec()["draft"] is True
    assert len(_spec()["parts"]) == 7
    assert len(_spec()["nets"]) == 11
    assert len(_spec()["openInterfaces"]) == 6
    # Seven real symbolRefs, all of them profiles of the managed book.
    refs = {part["symbolRef"] for part in _spec()["parts"]}
    assert len(refs) == 5, sorted(refs)
    book = {entry["symbolRef"] for entry in _read(BOOK_DIR / "index.json")["profiles"]}
    assert refs <= book
    for part in module["parts"]:
        assert len(part["symbolRef"]) == 32, part["role"]
        assert part["symbolRef"] in book, part["role"]
    text = " ".join(module["limitations"])
    for claim in ("internally", "datasheet", "offline compile", "hardware acceptance"):
        assert claim in text, claim
    assert "short" in text


def test_the_other_three_circuits_and_the_book_are_untouched() -> None:
    """The three other circuit outputs keep the bytes 038Q10 published."""
    for stem in ("ams1117_ldo_3v3", "sy8089_buck_3v3", "sy8089_buck_3v3_live"):
        path = CIRCUITS / f"{stem}.circuit.json"
        spec = _read(path)
        assert spec["draft"] is True
        assert spec["nc"] == []
        assert "J_USB." not in json.dumps(spec)
    index = _read(BOOK_DIR / "index.json")
    assert index["notForDrawCompile"] is True
    assert index["profileBookSha256"] == _sha256(BOOK_DIR / "profiles.json")


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
