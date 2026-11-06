"""The third persistence state, and the only thing that can establish it.

`saved_verified` means the content survived a close-and-reopen. No bridge action
can establish it — `doc.open` moves the focused tab without reloading it from
disk and there is no close-project action (M0-P0d audit E) — so the reopen is a
human act and `boardwise persistence` is what turns its result into an exit
code. These tests drive that comparison offline, against the **real** measured
dumps (`tests/fixtures/ch340_p1_editor_netlist.json`,
`ch340_p1_geometry.json`), so the shapes under test are the host's own.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pytest

from boardwise.bridge.protocol import ErrorCodes
from boardwise.cli import _cmd_persistence, _compare_persistence
from boardwise.engines.draw import fingerprint_total, geometry_fingerprint

FIXTURES = Path(__file__).resolve().parent / "fixtures"
NETLIST_FIXTURE = FIXTURES / "ch340_p1_editor_netlist.json"
GEOMETRY_FIXTURE = FIXTURES / "ch340_p1_geometry.json"


def _netlist_text() -> str:
    return NETLIST_FIXTURE.read_text(encoding="utf-8")


def _geometry() -> dict:
    return json.loads(GEOMETRY_FIXTURE.read_text(encoding="utf-8"))


def _snapshot(netlist_text: str | None = None, geometry: dict | None = None) -> dict:
    return {
        "netlist": {
            "type": "EasyEDA",
            "source": "getNetlistFile",
            "size": len(netlist_text or ""),
            "text": _netlist_text() if netlist_text is None else netlist_text,
        },
        "geometry": _geometry() if geometry is None else geometry,
    }


def _audit_records(home: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted((home / "audit").glob("*.jsonl")):
        records.extend(
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        )
    return records


# --------------------------------------------------------------------------
# geometry_fingerprint: id-free, or the check would be worthless
# --------------------------------------------------------------------------


def test_the_fingerprint_ignores_generated_ids():
    """The editor mints ids per render; comparing them would always differ.

    Two dumps of the same page that differ only in `primitiveId` must fingerprint
    equal, or every reopened project would report a difference.
    """
    first = _geometry()
    second = json.loads(json.dumps(first))
    for index, entry in enumerate(second["components"]):
        entry["primitiveId"] = f"regenerated-{index}"
        if isinstance(entry.get("state"), dict):
            entry["state"]["PrimitiveId"] = f"regenerated-{index}"
    for index, entry in enumerate(second["wires"]):
        entry["primitiveId"] = f"regenerated-w{index}"

    assert first != second, "the ids really did change"
    assert geometry_fingerprint(first) == geometry_fingerprint(second)


def test_the_fingerprint_counts_the_real_dump_by_list_and_type():
    """Positive control on the measured host shape.

    The dump has no `primitives` list at all (audit, 2026-09-18), so a reader
    looking for one would see an empty page. This pins what is actually there.
    """
    fingerprint = geometry_fingerprint(_geometry())
    assert fingerprint["components"] == 35
    assert fingerprint["components/part"] == 17
    assert fingerprint["components/netflag"] == 17
    assert fingerprint["wires"] == 33
    assert "primitives" not in _geometry(), "the host shape is the four lists"


def test_the_fingerprint_is_empty_rather_than_zero_for_an_unreadable_dump():
    """Empty means "nothing we know how to read" — the caller must not pass it."""
    assert geometry_fingerprint(None) == {}
    assert geometry_fingerprint({}) == {}
    assert geometry_fingerprint({"something": "else"}) == {}


def test_the_total_does_not_double_count_the_per_type_breakdown():
    """Summing the whole fingerprint counts every primitive twice.

    The per-list total and the per-type entries describe the *same* records, so
    the naive `sum(fingerprint.values())` reported 136 for a page holding 68
    primitives (measured while wiring this up).
    """
    fingerprint = geometry_fingerprint(_geometry())
    assert sum(fingerprint.values()) > 68, "the naive sum really does over-count"
    assert fingerprint_total(fingerprint) == 68
    assert fingerprint_total({}) == 0


# --------------------------------------------------------------------------
# the comparison
# --------------------------------------------------------------------------


def test_an_identical_reopen_is_saved_verified(tmp_path, monkeypatch):
    """The pass case — and it is the only one allowed to print `saved_verified`."""
    from boardwise.bridge import daemon as daemon_module

    monkeypatch.setattr(daemon_module, "BOARDWISE_HOME", tmp_path)
    code = _compare_persistence(_snapshot(), _snapshot())

    assert code == 0
    records = _audit_records(tmp_path)
    assert [r["action"] for r in records] == [daemon_module.AUDIT_PERSISTENCE_VERIFIED]
    assert records[0]["persistence"] == "saved_verified"
    assert records[0]["components"] == 17
    assert records[0]["primitives"] == 35 + 33


def test_a_reopen_that_lost_connectivity_is_not_verified(capsys):
    """The regression the upstream issue #216 describes: the page came back wrong."""
    changed = json.loads(_netlist_text())
    first = next(iter(changed["components"].values()))
    pin = next(iter(first["pinInfoMap"].values()))
    pin["net"] = "SOMETHING_ELSE"

    code = _compare_persistence(
        _snapshot(), _snapshot(netlist_text=json.dumps(changed))
    )
    printed = capsys.readouterr().out
    assert code == 1
    assert "NOT what was drawn" in printed
    assert "persistence: NOT saved_verified" in printed
    assert "persistence: saved_verified" not in printed, (
        "a failed comparison may not also print the pass line"
    )


def test_a_reopen_with_a_different_page_is_not_verified(capsys):
    """The geometry half catches content the netlist half cannot see."""
    fewer = _geometry()
    fewer["wires"] = fewer["wires"][:-3]

    code = _compare_persistence(_snapshot(), _snapshot(geometry=fewer))
    printed = capsys.readouterr().out
    assert code == 1
    assert "primitives differ" in printed
    assert "wires/Wire: 33 -> 30" in printed


# --------------------------------------------------------------------------
# the subset rule: "is what I snapshotted still there?"
# --------------------------------------------------------------------------


def _grown_netlist() -> str:
    """The measured netlist plus one component, one net and one net member.

    The shape a snapshot-then-work-on-other-pages run leaves behind: the
    snapshot's own content is untouched, everything new is additive.
    """
    grown = json.loads(_netlist_text())
    grown["components"]["gge999"] = {
        "props": {
            "Designator": "R99",
            "Value": "10k",
            "Footprint": "0402",
            "Supplier Part": "C25744",
        },
        "pinInfoMap": {
            "1": {"name": "1", "number": "1", "net": "GND", "props": {}},
            "2": {"name": "2", "number": "2", "net": "NEWNET", "props": {}},
        },
    }
    return json.dumps(grown)


def test_a_reopen_that_only_gained_content_is_still_verified(capsys, tmp_path, monkeypatch):
    """The subset rule, on the shape that was measured on 2026-09-28.

    A snapshot whose own content came back **complete** was still judged NOT
    saved_verified because 20 components and 40 net members had been drawn on
    other pages after it was taken (all of them "extra in candidate"). What a
    reopen can answer is "did the snapshot's content survive", and content added
    afterwards answers that the same way an unchanged project does.
    """
    from boardwise.bridge import daemon as daemon_module

    monkeypatch.setattr(daemon_module, "BOARDWISE_HOME", tmp_path)
    code = _compare_persistence(_snapshot(), _snapshot(netlist_text=_grown_netlist()))
    printed = capsys.readouterr().out

    assert code == 0, "an additive change is not a failed save"
    assert "persistence: saved_verified" in printed
    assert "the page has since grown" in printed
    assert "extras: 3 item(s)" in printed, "counted and said out loud"
    assert "component extra in candidate" in printed
    assert "net extra in candidate" in printed
    assert "member extra in candidate" in printed
    assert "NOT saved_verified" not in printed
    # Only a pass writes the audit line, and this is a pass.
    records = _audit_records(tmp_path)
    assert [r["action"] for r in records] == [daemon_module.AUDIT_PERSISTENCE_VERIFIED]


def test_an_unchanged_reopen_reports_no_extras(capsys, tmp_path, monkeypatch):
    """`extras: 0` is the unchanged project, and it reads exactly as it did before."""
    from boardwise.bridge import daemon as daemon_module

    monkeypatch.setattr(daemon_module, "BOARDWISE_HOME", tmp_path)
    code = _compare_persistence(_snapshot(), _snapshot())
    printed = capsys.readouterr().out

    assert code == 0
    assert "extras:" not in printed
    assert "persistence: saved_verified" in printed


def test_a_component_lost_in_the_reopen_is_not_verified(capsys):
    """The subset rule is a subset, not a truce: a loss still fails the run."""
    thinned = json.loads(_netlist_text())
    del thinned["components"]["gge57"]

    code = _compare_persistence(_snapshot(), _snapshot(netlist_text=json.dumps(thinned)))
    printed = capsys.readouterr().out
    assert code == 1
    assert "the reopened page is NOT what was drawn" in printed
    assert "component missing in candidate" in printed
    assert "NOT saved_verified" in printed
    assert "persistence: saved_verified" not in printed


def test_a_value_changed_in_the_reopen_is_not_verified(capsys):
    """A field that came back different is a loss of what was snapshotted."""
    changed = json.loads(_netlist_text())
    changed["components"]["gge55"]["props"]["Value"] = "9.1K"

    code = _compare_persistence(_snapshot(), _snapshot(netlist_text=json.dumps(changed)))
    printed = capsys.readouterr().out
    assert code == 1
    assert "value differs" in printed
    assert "1 snapshot item(s) missing or changed" in printed


def test_the_census_tolerates_primitives_gained_but_not_lost(capsys):
    """Same split on the geometry half, in both directions.

    `sch.geometry` reads the focused page, so "gained" here means the page grew
    after the snapshot — as tolerated as the netlist's extras. A primitive the
    snapshot held and the page no longer does is the failure the census exists
    for.
    """
    geometry = _geometry()
    fewer = json.loads(json.dumps(geometry))
    fewer["wires"] = fewer["wires"][:-3]

    code = _compare_persistence(_snapshot(geometry=fewer), _snapshot(geometry=geometry))
    printed = capsys.readouterr().out
    assert code == 0
    assert "primitives gained since the snapshot" in printed
    assert "wires/Wire: 30 -> 33" in printed
    assert "persistence: saved_verified" in printed

    code = _compare_persistence(_snapshot(geometry=geometry), _snapshot(geometry=fewer))
    printed = capsys.readouterr().out
    assert code == 1
    assert "primitives the snapshot had are gone" in printed
    assert "wires/Wire: 33 -> 30" in printed


def test_every_extra_direction_is_declared_and_nothing_else_is():
    """A subset run classifies by direction, so the directions are pinned here.

    Scanned against the module's own literals rather than enumerated by hand: a
    new difference branch in `compare_models` whose direction is "candidate
    only" must be declared in `EXTRA_DETAILS`, or `boardwise persistence
    --baseline` would fail a run for content that was merely added later.
    """
    from boardwise.core import compare as compare_module

    source = Path(compare_module.__file__).read_text(encoding="utf-8")
    literals = set(re.findall(r'"([^"]*extra in candidate)"', source))
    assert literals, "the scan found no directions at all — the pattern drifted"
    assert literals == set(compare_module.EXTRA_DETAILS)


def test_a_missing_netlist_is_undecidable_not_a_pass(capsys):
    """`sch.netlist` returns nothing for a never-saved project (measured).

    That is the exact shape a failed save leaves behind, so it must read as
    "cannot decide" — never as "identical", which is what an empty-string
    comparison would quietly produce.
    """
    code = _compare_persistence(_snapshot(), _snapshot(netlist_text=""))
    captured = capsys.readouterr()
    assert code == 3
    assert "cannot decide" in captured.err
    assert "saved_verified" not in captured.out


def test_a_missing_geometry_is_undecidable_not_a_pass(capsys):
    code = _compare_persistence(_snapshot(), _snapshot(geometry={}))
    captured = capsys.readouterr()
    assert code == 3
    assert "census came back empty" in captured.err
    assert "saved_verified" not in captured.out


def test_an_unparseable_netlist_is_undecidable(capsys):
    code = _compare_persistence(_snapshot(), _snapshot(netlist_text="{ not json"))
    captured = capsys.readouterr()
    assert code == 3
    assert "malformed" in captured.err


# --------------------------------------------------------------------------
# the command surface
# --------------------------------------------------------------------------


def test_the_command_asks_for_one_of_its_two_modes_before_touching_the_bridge(capsys):
    """No flags is a usage error, not a silent snapshot nobody reads."""
    args = argparse.Namespace(out=None, baseline=None)
    assert _cmd_persistence(args) == 2
    assert "give --out" in capsys.readouterr().err


class _FakeBridgeClient:
    """A ``BridgeClient`` stand-in, so the command's failure paths are testable
    without an editor (the pattern ``test_bridge_cli.py`` uses)."""

    opened_with = ""
    answers: dict = {}
    fail_open: BaseException | None = None
    calls: list = []

    @classmethod
    async def open(cls, uri, token, role, client=""):
        cls.opened_with = uri
        cls.calls = []
        if cls.fail_open is not None:
            raise cls.fail_open
        return cls()

    async def call(self, action, params=None):
        type(self).calls.append(action)
        answer = type(self).answers.get(action)
        if isinstance(answer, BaseException):
            raise answer
        return {} if answer is None else answer

    async def close(self):
        return None


@pytest.fixture
def fake_bridge(monkeypatch, tmp_path):
    """Isolated BOARDWISE_HOME (the command opens a CLI token) + a fake client."""
    monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path))
    import boardwise.bridge.client as client_module

    _FakeBridgeClient.fail_open = None
    _FakeBridgeClient.calls = []
    monkeypatch.setattr(client_module, "BridgeClient", _FakeBridgeClient)
    return tmp_path


def test_a_snapshot_writes_the_file_and_says_what_to_do_next(fake_bridge, capsys, tmp_path):
    _FakeBridgeClient.answers = {
        "sch.netlist": {"type": "EasyEDA", "text": _netlist_text()},
        "sch.geometry": _geometry(),
    }
    out = tmp_path / "snap.json"
    args = argparse.Namespace(out=str(out), baseline=None)

    assert _cmd_persistence(args) == 0
    snapshot = json.loads(out.read_text(encoding="utf-8"))
    assert set(snapshot) == {"netlist", "geometry"}
    assert snapshot["netlist"]["text"] == _netlist_text()
    # Read-only: nothing but the two reads reached the editor.
    assert _FakeBridgeClient.calls == ["sch.netlist", "sch.geometry"]
    printed = capsys.readouterr().out
    assert "close the project in the editor, reopen it" in printed


def test_an_action_error_is_reported_and_exits_two(fake_bridge, capsys):
    """A connector-side failure is a usage-level answer, not a traceback.

    Measured 2026-09-18 on this host: `sch.netlist` currently answers
    `CONNECTOR_ERROR: both netlist exports failed` — the export really is the
    fragile step, so the command has to carry that message out intact.
    """
    from boardwise.bridge.protocol import BridgeError

    _FakeBridgeClient.answers = {
        "sch.netlist": BridgeError(
            ErrorCodes.CONNECTOR_ERROR, "both netlist exports failed"
        )
    }
    args = argparse.Namespace(out=None, baseline="whatever.json")
    assert _cmd_persistence(args) == 2
    captured = capsys.readouterr()
    assert "CONNECTOR_ERROR: both netlist exports failed" in captured.err


def test_an_unreachable_daemon_exits_two(fake_bridge, capsys):
    _FakeBridgeClient.fail_open = OSError("connection refused")
    args = argparse.Namespace(out="snap.json", baseline=None)
    assert _cmd_persistence(args) == 2
    assert "daemon not reachable" in capsys.readouterr().err


def test_a_missing_baseline_file_exits_two(fake_bridge, capsys, tmp_path):
    _FakeBridgeClient.answers = {
        "sch.netlist": {"type": "EasyEDA", "text": _netlist_text()},
        "sch.geometry": _geometry(),
    }
    args = argparse.Namespace(out=None, baseline=str(tmp_path / "nope.json"))
    assert _cmd_persistence(args) == 2
    assert "nope.json" in capsys.readouterr().err


def test_the_arguments_parse_as_advertised():
    from boardwise.cli import build_parser

    args = build_parser().parse_args(["persistence", "--out", "s.json"])
    assert (args.command, args.out, args.baseline) == ("persistence", "s.json", None)

    args = build_parser().parse_args(["persistence", "--baseline", "s.json"])
    assert (args.out, args.baseline) == (None, "s.json")


# --------------------------------------------------------------------------
# 543N: auto-generated net names are renumbered across a reopen
# --------------------------------------------------------------------------
#
# Measured on `test V4` P38 (evidence/543n/): the page came back with 11
# components, the same geometry and the same partition, but the four unnamed
# nets the editor had called `$19N5 …` were now `$1N5 …`. Comparing those names
# verbatim reported 12 phantom differences on a save that had persisted
# perfectly. The fix is a *narrow* one — an auto→auto rename is excused only
# when the member set is identical — and the tests below pin both the excuse
# and every shape it must not cover.

#: The fixture's editor-generated names, renumbered the way the host does it.
AUTO_RENUMBER = {
    "$1N5": "$19N5",
    "$1N22": "$19N19",
    "$1N23": "$19N20",
    "$1N35": "$19N35",
    "$1N40": "$19N40",
    "$1N42": "$19N42",
}


def _rewritten(mutate=None) -> str:
    """The fixture netlist, auto names renumbered, then `mutate(netlist)`.

    The mutation runs *after* the renumbering, so a shape is described against
    the names the reopened page would really carry.
    """
    netlist = json.loads(_netlist_text())
    for component in netlist["components"].values():
        for pin in component["pinInfoMap"].values():
            net = pin.get("net")
            pin["net"] = AUTO_RENUMBER.get(net, net)
    if mutate is not None:
        mutate(netlist)
    return json.dumps(netlist)


def _renamed(netlist: dict, old: str, new: str) -> None:
    """Rename every pin carrying `old` — a whole-cluster rename, same members."""
    for component in netlist["components"].values():
        for pin in component["pinInfoMap"].values():
            if pin.get("net") == old:
                pin["net"] = new


def _set_pin(netlist: dict, component_id: str, number: str, net: str) -> None:
    netlist["components"][component_id]["pinInfoMap"][number]["net"] = net


def _nets_of(netlist_text: str) -> dict[str, set[tuple[str, str]]]:
    netlist = json.loads(netlist_text)
    nets: dict[str, set[tuple[str, str]]] = {}
    for component_id, component in netlist["components"].items():
        for number, pin in component["pinInfoMap"].items():
            nets.setdefault(pin.get("net") or "", set()).add((component_id, number))
    return nets


def test_an_auto_net_renumbering_is_saved_verified(capsys, tmp_path, monkeypatch):
    """The measured P38 shape: only editor-generated names moved."""
    from boardwise.bridge import daemon as daemon_module

    monkeypatch.setattr(daemon_module, "BOARDWISE_HOME", tmp_path)
    reopened = _rewritten()
    assert _nets_of(reopened) != _nets_of(_netlist_text()), "the names really moved"
    before = json.loads(_netlist_text())
    after = json.loads(reopened)
    assert sorted(before["components"]) == sorted(after["components"])

    code = _compare_persistence(_snapshot(), _snapshot(netlist_text=reopened))
    printed = capsys.readouterr().out

    assert code == 0, "a renumbering of auto names is not a failed save"
    assert "persistence: saved_verified" in printed
    assert "NOT saved_verified" not in printed
    assert "matched by member set, not by name" in printed, (
        "the pass must disclose that this is a membership match, not name stability"
    )
    assert "$19N5 -> $1N5" in printed
    assert "extras:" not in printed, "the reconcile leaves nothing extra behind"
    records = _audit_records(tmp_path)
    assert [r["action"] for r in records] == [daemon_module.AUDIT_PERSISTENCE_VERIFIED]
    assert records[0]["persistence"] == "saved_verified"


def test_the_reconcile_note_counts_every_renumbered_net(capsys):
    reopened = _rewritten()
    code = _compare_persistence(_snapshot(), _snapshot(netlist_text=reopened))
    printed = capsys.readouterr().out
    assert code == 0
    assert f"({len(AUTO_RENUMBER)})" in printed


@pytest.mark.parametrize(
    "detail, mutate",
    [
        (
            "pin moved to another auto net",
            lambda netlist: _set_pin(netlist, "gge45_1", "1", "$19N6"),
        ),
        (
            "auto net split in two",
            lambda netlist: _set_pin(netlist, "gge45_1", "1", "$19N50"),
        ),
        (
            "two auto nets merged",
            lambda netlist: (
                _renamed(netlist, "$19N20", "$19N99"),
                _renamed(netlist, "$19N35", "$19N99"),
            ),
        ),
    ],
    ids=["pin-moved", "split", "merged"],
)
def test_a_real_electrical_change_on_auto_nets_still_fails(detail, mutate, capsys):
    """A renumbered *name* is excused; a changed *partition* never is."""
    reopened = _rewritten(mutate)
    code = _compare_persistence(_snapshot(), _snapshot(netlist_text=reopened))
    printed = capsys.readouterr().out
    assert code == 1, detail
    assert "net missing in candidate" in printed or "member missing in candidate" in printed
    assert "pin net mapping differs" in printed
    assert "NOT saved_verified" in printed
    assert "persistence: saved_verified" not in printed


@pytest.mark.parametrize(
    "detail, mutate",
    [
        ("named net renamed", lambda n: _renamed(n, "RX", "RXD_ALT")),
        ("named net renamed to an auto name", lambda n: _renamed(n, "RX", "$19N77")),
        ("auto net renamed to a user name", lambda n: _renamed(n, "$19N5", "USB_D_P")),
    ],
    ids=["named-renamed", "named-to-auto", "auto-to-named"],
)
def test_a_user_named_net_is_never_excused_by_the_auto_rule(detail, mutate, capsys):
    """Same members is not the same net when a name that means something moved."""
    reopened = _rewritten(mutate)
    code = _compare_persistence(_snapshot(), _snapshot(netlist_text=reopened))
    printed = capsys.readouterr().out
    assert code == 1, detail
    assert "NOT saved_verified" in printed
    assert "persistence: saved_verified" not in printed


def test_a_component_lost_in_a_renumbered_reopen_still_fails(capsys):
    """The auto rule only touches net names; a lost part is still a loss."""
    netlist = json.loads(_rewritten())
    del netlist["components"]["gge57"]
    code = _compare_persistence(_snapshot(), _snapshot(netlist_text=json.dumps(netlist)))
    printed = capsys.readouterr().out
    assert code == 1
    assert "component missing in candidate" in printed
    assert "NOT saved_verified" in printed


# --------------------------------------------------------------------------
# the contract underneath: `reconcile_names(..., auto_only=True)`
# --------------------------------------------------------------------------


def _model(netlist_text: str):
    from boardwise.core.candidate import candidate_from_netlist

    return candidate_from_netlist(netlist_text, "EasyEDA")


def test_the_default_reconcile_is_unchanged_and_auto_only_is_the_narrow_one():
    """Calibration still renames by membership, names included.

    ``auto_only`` is off by default: the default call renames the user-named
    ``RX`` cluster to the golden ``GND``-style name it matches, and the narrowed
    call must not. Both directions are pinned here so "off by default" is a
    measurement, not a claim.
    """
    from boardwise.core.compare import reconcile_names

    golden = _model(_netlist_text())
    named_rename = _model(_rewritten(lambda netlist: _renamed(netlist, "RX", "RX_ALT")))

    default = reconcile_names(named_rename, golden)
    narrowed = reconcile_names(named_rename, golden, auto_only=True)

    assert "RX_ALT" not in default.nets, "the default path still matches by membership"
    assert "RX" in default.nets
    assert "RX_ALT" in narrowed.nets, "auto_only may not rename a user-named net"
    assert "RX" not in narrowed.nets

    renumbered = _model(_rewritten())
    assert "$19N5" not in reconcile_names(renumbered, golden).nets
    assert "$19N5" not in reconcile_names(renumbered, golden, auto_only=True).nets, (
        "auto→auto is the case the narrow mode is for"
    )


def test_the_narrow_reconcile_keeps_the_safety_metadata():
    """Same rebuild, same four fields — a truncated weld still refuses."""
    from boardwise.core.compare import reconcile_names
    from boardwise.core.model import TRUNCATED_BY_DESIGNATOR

    golden = _model(_netlist_text())
    candidate = _model(_rewritten())
    candidate.duplicate_designators = ["R1"]
    candidate.cross_page_designators = {"R1": ["page-1", "page-2"]}
    candidate.unproven_nets = {"GND": ("page-a", "page-b")}
    candidate.unproven_reasons = {
        "GND": (TRUNCATED_BY_DESIGNATOR, "2nd placement of 'R1' left out")
    }

    out = reconcile_names(candidate, golden, auto_only=True)

    assert out.duplicate_designators == ["R1"]
    assert out.cross_page_designators == {"R1": ["page-1", "page-2"]}
    assert out.unproven_nets == {"GND": ("page-a", "page-b")}
    assert out.unproven_reasons == candidate.unproven_reasons


def test_compare_models_itself_is_still_strict_about_net_names():
    """The tolerance lives in the persistence caller, never in the referee.

    `boardwise diff` and calibration read `compare_models` directly; if this
    function had learned to forgive a renumbering, every consumer would gain a
    verdict it never asked for.
    """
    from boardwise.core.compare import compare_models

    report = compare_models(_model(_netlist_text()), _model(_rewritten()))
    details = [d.detail for d in report.differences]
    assert "net missing in candidate" in details
    assert "net extra in candidate" in details
    assert "pin net mapping differs" in details
