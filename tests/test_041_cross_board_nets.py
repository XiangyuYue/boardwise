"""041 S1: cross-board net instances — the model-layer contract.

041 asks one question without answering it: in a multi-board project, are
Board1's ``GND`` and Board3's ``GND`` one electrical node, or two coincidences?
The model's answer is "unknown", said as data: every **addressable** board's net
is its own :class:`NetInstance`, and two instances that merely spell the same net
name get an :class:`UnprovenNetEdge` — a recorded problem, never a proof, and
never a "disconnected" verdict either.

What this file pins (the batch's negative control, model layer only):

* same net name on two boards = two independent instances + one unproven edge,
  and ``run_review`` files nothing new about it;
* three boards = one edge per pair, in project order, deterministic across calls;
* board identity is the uuid, never the title — two boards both called
  ``Board1`` stay two boards, and the group values are uuids;
* an implicit board (no BOARD document) and an unattached page (empty uuid) never
  become instances or edges; the unattached page is **disclosed**, and no
  ``board#0``-style id is invented for it;
* a datasheet's "pins 1-2 are shorted inside the part" and PCB copper-layer
  separation are not cross-board evidence: this channel has no vocabulary for
  ``proven`` or ``proven-open`` at all;
* the existing ``unproven_nets`` channel (issue #19 / 107) and ``run_review``'s
  findings are unchanged — 041 adds a data channel, not a finding.

Deliberately **not** here: the ``checkup``/``review`` disclosure section (S1 §2)
and the explicit declaration file with its ``proven`` edges (S2). There is no
``proven`` field to test, and these tests assert its absence rather than its
behaviour.
"""

from __future__ import annotations

import collections
import dataclasses
import json
from pathlib import Path

import pytest

from boardwise.core.model import (
    EVIDENCE_LEVEL_BY_NAME,
    WELDED_BY_NAME,
    BoardModel,
    BoardRef,
    Component,
    DesignModel,
    MultiBoardProjectError,
    Net,
    NetInstance,
    Pin,
    ProjectModel,
    UnprovenNetEdge,
)
from boardwise.engines import checkup as checkup_engine
from boardwise.engines.checkup import (
    cross_board_net_section,
    render_cross_board_nets_markdown,
    render_report_markdown,
    warning_triage_slots,
)
from boardwise.engines.review import render_markdown, run_review
from boardwise.parsers.schematic import build_project_model

FIXTURES = Path(__file__).parent / "fixtures"
FOC = FIXTURES / "ProPrj_毕设FOC驱动板_2026-09-17.epro2"
MOTOR = FIXTURES / "ProPrj_高速电机控制器_2026-09-16.epro2"
GOLDEN = FIXTURES / "ch340_golden.epro2"
EPRJ3_SYNTH = FIXTURES / "eprj3_synth"


def _board(
    uuid: str,
    title: str,
    *,
    nets: tuple[str, ...] = (),
    pins: dict[str, list[tuple[str, str]]] | None = None,
    pages: tuple[str, ...] = (),
    components: tuple[Component, ...] = (),
) -> BoardModel:
    """One board of a project, written down directly (no file, no parser)."""
    pins = pins or {}
    return BoardModel(
        nets={name: Net(name=name, pins=list(pins.get(name, ()))) for name in nets},
        components={component.designator: component for component in components},
        board=BoardRef(uuid=uuid, title=title, page_uuids=pages),
    )


def _project(*boards: BoardModel, source: str = "in-memory") -> ProjectModel:
    return ProjectModel(boards=list(boards), source=source)


def _signatures(project: ProjectModel) -> list[tuple[str, str, str]]:
    return [
        (finding.rule_id, finding.severity, finding.message)
        for finding in sorted(
            run_review(project),
            key=lambda f: (f.rule_id, f.severity, f.message),
        )
    ]


# --------------------------------------------------------------------------
# 1. two boards, one net name: two instances, one unproven edge, no finding
# --------------------------------------------------------------------------


def test_the_same_net_name_on_two_boards_is_two_instances_and_one_unproven_edge():
    """The batch's headline: ``GND`` on both boards is *not* one node.

    Two instances, neither of which references the other, plus exactly one edge —
    and that edge is filed as an unproven **name collision**, not as a proven tie
    and not as a disconnection.
    """
    project = _project(
        _board("aaaa1111", "Board1", nets=("GND", "VCC")),
        _board("bbbb2222", "Board2", nets=("GND",)),
    )

    instances = project.net_instances()
    assert instances == [
        NetInstance("aaaa1111", "GND"),
        NetInstance("aaaa1111", "VCC"),
        NetInstance("bbbb2222", "GND"),
    ], "project board order, then net name — and one board's nets never join another's"

    groups = project.cross_board_net_instances()
    assert set(groups) == {"GND"}, "VCC is on one board only, so it is not a group"
    assert groups["GND"] == [
        NetInstance("aaaa1111", "GND"),
        NetInstance("bbbb2222", "GND"),
    ]
    assert NetInstance("aaaa1111", "GND") != NetInstance("bbbb2222", "GND")

    edges = project.unproven_edges
    assert edges == (
        UnprovenNetEdge(
            NetInstance("aaaa1111", "GND"),
            NetInstance("bbbb2222", "GND"),
        ),
    )
    (edge,) = edges
    assert edge.reason == WELDED_BY_NAME == "welded-by-name"
    assert edge.evidence_level == EVIDENCE_LEVEL_BY_NAME == "E0"


def test_the_new_channel_files_no_finding_and_moves_no_severity():
    """Disclosure, not a verdict: two projects differing only in whether the net
    names collide produce byte-identical findings.

    The pair is the control the batch needs — if the cross-board derivation ever
    leaked into a rule, the two rows would diverge.
    """
    same_name = _project(
        _board("aaaa1111", "Board1", nets=("GND",)),
        _board("bbbb2222", "Board2", nets=("GND",)),
    )
    distinct_names = _project(
        _board("aaaa1111", "Board1", nets=("GND",)),
        _board("bbbb2222", "Board2", nets=("GND_B",)),
    )
    assert same_name.unproven_edges, "the weld is what differs"
    assert not distinct_names.unproven_edges
    assert _signatures(same_name) == _signatures(distinct_names)
    assert not [
        finding for finding in run_review(same_name)
        if "cross" in finding.rule_id or "board-net" in finding.rule_id
    ], "041 owns no rule and files no finding"


# --------------------------------------------------------------------------
# 2. three boards: one edge per pair, deterministic
# --------------------------------------------------------------------------


def test_three_boards_with_one_shared_name_produce_one_edge_per_pair():
    project = _project(
        _board("aaaa1111", "Board1", nets=("GND",)),
        _board("bbbb2222", "Board2", nets=("GND",)),
        _board("cccc3333", "Board3", nets=("GND",)),
    )
    assert list(project.cross_board_net_instances()) == ["GND"]
    assert len(project.cross_board_net_instances()["GND"]) == 3
    assert project.unproven_edges == (
        UnprovenNetEdge(NetInstance("aaaa1111", "GND"), NetInstance("bbbb2222", "GND")),
        UnprovenNetEdge(NetInstance("aaaa1111", "GND"), NetInstance("cccc3333", "GND")),
        UnprovenNetEdge(NetInstance("bbbb2222", "GND"), NetInstance("cccc3333", "GND")),
    ), "every unordered pair, ordered by project board position"
    # A second read is the same read: nothing is derived from dict iteration order
    # that a reload or a re-export could shuffle.
    assert project.unproven_edges == project.unproven_edges
    assert list(project.cross_board_net_instances()) == ["GND"]


def test_two_names_on_three_boards_pair_within_each_name_only():
    project = _project(
        _board("aaaa1111", "Board1", nets=("GND", "VCC")),
        _board("bbbb2222", "Board2", nets=("GND", "VCC")),
        _board("cccc3333", "Board3", nets=("VCC",)),
    )
    groups = project.cross_board_net_instances()
    assert list(groups) == ["GND", "VCC"], "net-name order, so two runs agree"
    assert len(groups["GND"]) == 2 and len(groups["VCC"]) == 3
    pairs = {(edge.first.net_name, edge.first.board_uuid,
              edge.second.net_name, edge.second.board_uuid) for edge in project.unproven_edges}
    assert pairs == {
        ("GND", "aaaa1111", "GND", "bbbb2222"),
        ("VCC", "aaaa1111", "VCC", "bbbb2222"),
        ("VCC", "aaaa1111", "VCC", "cccc3333"),
        ("VCC", "bbbb2222", "VCC", "cccc3333"),
    }, "GND@A and VCC@B are never paired: different names are not one edge"


# --------------------------------------------------------------------------
# 3. identity is the uuid; the title only displays
# --------------------------------------------------------------------------


def test_two_boards_with_the_same_title_stay_two_boards():
    """The title is the user's, is editable and may repeat; the uuid is the
    container's. A group keyed by title would merge two boards a user happened to
    name alike, which is the mistake 041 §1 rules out."""
    project = _project(
        _board("aaaa1111", "Board1", nets=("GND",)),
        _board("bbbb2222", "Board1", nets=("GND",)),
    )
    instances = project.net_instances()
    assert len(instances) == 2
    assert {instance.board_uuid for instance in instances} == {"aaaa1111", "bbbb2222"}
    assert "Board1" not in {instance.board_uuid for instance in instances}
    assert len(project.unproven_edges) == 1
    assert [instance.board_uuid
            for instance in project.cross_board_net_instances()["GND"]] == [
        "aaaa1111", "bbbb2222",
    ]


def test_an_empty_board_uuid_is_refused_outright():
    """There is no instance of "some board" — the contract's first line is that a
    ``NetInstance`` carries a **real** BOARD uuid. Asking for one without is a
    programming error, not a value to carry around and filter later."""
    with pytest.raises(ValueError):
        NetInstance("", "GND")
    with pytest.raises(ValueError):
        NetInstance(board_uuid="", net_name="GND")
    with pytest.raises(ValueError):
        NetInstance("   ", "GND")
    assert NetInstance("aaaa1111", "GND").board_uuid == "aaaa1111"


# --------------------------------------------------------------------------
# 4. implicit boards and unattached pages: never instances, sometimes disclosed
# --------------------------------------------------------------------------


def test_an_implicit_board_has_no_instances_edges_or_disclosure():
    """A project with no BOARD document is one implicit board with an empty uuid
    (``parsers/schematic.py``'s ``Board1``). It has no cross-board problem to
    describe, so 041 says nothing about it — no instance, no edge, and no
    non-addressable row either (it is not an unattached page)."""
    implicit = _project(_board("", "Board1", nets=("GND", "VCC"), pages=("page-1",)))
    assert implicit.net_instances() == []
    assert implicit.cross_board_net_instances() == {}
    assert implicit.unproven_edges == ()
    assert implicit.non_addressable_pages() == ()

    # ... and the real folder fixture (no ``profile.boards``) is that same board.
    real = build_project_model(EPRJ3_SYNTH)
    assert real.boards[0].board.uuid == ""
    assert real.net_instances() == []
    assert real.unproven_edges == ()
    assert real.non_addressable_pages() == ()


def test_unattached_pages_are_disclosed_but_join_no_instance_and_no_edge():
    """040b §WI-0.2's ``unattached`` group has an empty uuid. It is **non
    addressable**: it cannot be paired with a board, so it produces no instance
    and no edge — and it is not silently dropped either, it is listed."""
    project = _project(
        _board("aaaa1111", "Board1", nets=("GND",), pages=("p1",)),
        _board("bbbb2222", "Board2", nets=("GND",), pages=("p2",)),
        _board("", "unattached", nets=("GND", "CN1_NET"), pages=("p9", "p10")),
    )
    assert {instance.board_uuid for instance in project.net_instances()} == {
        "aaaa1111", "bbbb2222",
    }
    assert len(project.cross_board_net_instances()["GND"]) == 2, (
        "the unattached page does not make GND a three-board group"
    )
    assert "CN1_NET" not in project.cross_board_net_instances()
    assert len(project.unproven_edges) == 1
    assert project.non_addressable_pages() == (
        ("p9", "unattached"),
        ("p10", "unattached"),
    ), "page uuid + the group's title, project order, page order"

    # No invented identity of any kind: not a position-derived key, not the
    # title, not a hash. Every uuid in the channel is one the container wrote.
    written = {instance.board_uuid for instance in project.net_instances()}
    for edge in project.unproven_edges:
        written |= {edge.first.board_uuid, edge.second.board_uuid}
    assert written == {"aaaa1111", "bbbb2222"}
    assert not [uuid for uuid in written if uuid.startswith("board#")]


def test_a_page_with_no_board_is_only_disclosed_in_a_multi_board_project():
    """In a one-board project an empty uuid is the *implicit* board (nothing to
    disclose); in a multi-board project it is an orphan page that must be named."""
    assert _project(_board("", "Board1", pages=("p1",))).non_addressable_pages() == ()
    assert _project(
        _board("aaaa1111", "Board1", pages=("p1",)),
        _board("", "unattached", pages=("p9",)),
    ).non_addressable_pages() == (("p9", "unattached"),)


# --------------------------------------------------------------------------
# 5. what is *not* evidence: datasheet shorts, copper layers, same designators
# --------------------------------------------------------------------------


def _connector(designator: str, *, short_note: bool = True) -> Component:
    """A 4-pin connector whose stored props claim an internal 1-2 short.

    The claim may well be true of **that part** (the datasheet says so) — it says
    nothing at all about which pin of another board's connector it meets.
    """
    props = {"Datasheet": "https://example.invalid/conn.pdf", "Package": "HDR-1X4"}
    if short_note:
        props.update({"Pin1": "5V_IN", "Pin2": "5V_IN", "internal short": "1-2"})
    return Component(
        uid=f"uid-{designator}",
        designator=designator,
        value="HDR-1X4",
        footprint="HDR-1X4",
        props=props,
        pins=[Pin(number="1", name="P1", net="5V_IN"), Pin(number="2", name="P2", net="5V_IN")],
    )


def test_the_same_cn_designator_is_not_interconnect_evidence():
    """Two ``CN1``s with different footprints are still not a mating pair.

    The name collision remains A1's independent ERROR; it produces no net edge
    and no new 041 finding. This is the exact negative control for reading a
    connector-shaped designator as if it were board-to-board evidence.
    """
    first = _connector("CN1")
    second = _connector("CN1")
    second.footprint = "HDR-1X6"
    second.pins = [
        Pin(number="1", name="P1", net="VSYS"),
        Pin(number="2", name="P2", net="VSYS"),
    ]
    project = _project(
        _board("aaaa1111", "Board1", nets=("5V_IN",), components=(first,)),
        _board("bbbb2222", "Board2", nets=("VSYS",), components=(second,)),
    )
    # build_project_model populates this project-scoped field after parsing;
    # the in-memory board needs the same input for A1's independent rule.
    for board_model in project.boards:
        board_model.cross_board_designators = {"CN1": ["Board1", "Board2"]}
    assert project.cross_board_net_instances() == {}
    assert project.unproven_edges == ()
    duplicates = [
        finding for finding in run_review(project)
        if finding.rule_id == "conn-duplicate-designators"
    ]
    assert len(duplicates) == 1 and duplicates[0].severity == "ERROR"
    assert not [finding for finding in run_review(project) if "cross" in finding.rule_id]


def test_a_datasheet_short_and_independent_copper_prove_nothing_across_boards():
    """E0/E1 only (041 §3): connector-shaped parts and a datasheet that shorts
    two pins inside one part produce no tie, and the model has no field in which
    "proven" or "proven-open" could even be written."""
    project = _project(
        _board("aaaa1111", "Board1", nets=("GND", "5V_IN"), components=(_connector("CN1"),)),
        _board("bbbb2222", "Board2", nets=("GND", "VSYS"), components=(_connector("CN2"),)),
    )
    groups = project.cross_board_net_instances()
    assert set(groups) == {"GND"}, (
        "5V_IN/VSYS are different names and CN1/CN2 are different designators; "
        "neither is an edge — only the shared GND name is even a group"
    )
    assert {edge.reason for edge in project.unproven_edges} == {WELDED_BY_NAME}
    assert {edge.evidence_level for edge in project.unproven_edges} == {"E0"}

    # The vocabulary itself: nothing here can say "connected" or "open".
    edge_fields = {field.name for field in dataclasses.fields(UnprovenNetEdge)}
    assert edge_fields == {"first", "second", "reason", "evidence_level"}
    for forbidden in ("proven", "merged", "connected", "disconnected", "open", "severity"):
        assert forbidden not in edge_fields, forbidden

    model_fields = set(dir(ProjectModel))
    provenance_names = {name for name in model_fields if "proven" in name}
    assert provenance_names == {
        "unproven_edges", "unproven_nets", "unproven_pages", "unproven_reason",
        "unproven_reasons",
    }, "no ``proven_*`` reader exists yet — that is S2, and it is not here"
    assert not [name for name in model_fields if "proven_open" in name]
    assert not [name for name in model_fields if name.endswith("_proven")]


# --------------------------------------------------------------------------
# 6. the existing "unproven" channel is untouched
# --------------------------------------------------------------------------


def test_the_old_unproven_channel_keeps_its_meaning():
    """``DesignModel.unproven_nets`` is issue #19's per-page weld: same name on
    two *pages*, membership unknown. 041 does not reuse or extend it — putting
    cross-board names there would make every member rule report UNKNOWN on every
    multi-board project, which the batch forbids."""
    welded = DesignModel(
        nets={"VCC": Net(name="VCC")},
        unproven_nets={"VCC": ("p1", "p2")},
    )
    assert welded.unproven_nets == {"VCC": ("p1", "p2")}
    assert welded.unproven_pages("VCC") == ("p1", "p2")
    assert welded.unproven_reason("VCC") == (WELDED_BY_NAME, "")
    assert welded.unproven_reasons == {}

    one_board = ProjectModel(boards=[BoardModel(
        nets=welded.nets,
        unproven_nets=dict(welded.unproven_nets),
        board=BoardRef(uuid="aaaa1111", title="Board1"),
    )])
    assert one_board.unproven_nets == {"VCC": ("p1", "p2")}, "façade reads through"
    assert one_board.unproven_pages("VCC") == ("p1", "p2")


def test_the_new_derivation_writes_nothing_back_into_the_old_channel():
    project = _project(
        _board("aaaa1111", "Board1", nets=("GND",)),
        _board("bbbb2222", "Board2", nets=("GND",)),
    )
    assert project.unproven_nets == {}, "a multi-board project has nothing page-welded"
    assert project.unproven_pages("GND") is None
    assert project.unproven_reason("GND") == (WELDED_BY_NAME, "")
    project.net_instances()
    project.cross_board_net_instances()
    project.unproven_edges
    project.non_addressable_pages()
    assert project.unproven_nets == {}, (
        "reading the new channel must not populate the old one — a rule that "
        "consults #19's weld would otherwise start refusing on every board"
    )
    assert all(board.unproven_nets == {} for board in project.boards)


# --------------------------------------------------------------------------
# 7. the real multi-board fixtures: boards, groups and findings unmoved
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def foc() -> ProjectModel:
    return build_project_model(FOC)


@pytest.fixture(scope="module")
def motor() -> ProjectModel:
    return build_project_model(MOTOR)


def test_the_real_three_board_project_yields_instances_groups_and_pairs(foc):
    assert foc.board_titles() == ["Board1", "Board2", "Board3"]
    assert all(board.board.uuid for board in foc.boards)
    assert len(foc.net_instances()) == foc.net_count() == 146, (
        "one instance per (addressable board, net name)"
    )
    groups = foc.cross_board_net_instances()
    assert len(groups) == 39, "measured on this fixture: 34 two-board + 5 three-board"
    assert "GND" in groups and "VCC" in groups
    assert all(len({instance.board_uuid for instance in members}) > 1
               for members in groups.values())
    assert len(foc.unproven_edges) == 49, "34 pairs + 5 triples = 34 + 15"
    assert foc.unproven_nets == {}
    assert foc.non_addressable_pages() == ()


def test_the_real_two_board_project_yields_instances_groups_and_pairs(motor):
    assert len(motor.boards) == 2
    assert all(board.board.uuid for board in motor.boards)
    assert len(motor.net_instances()) == motor.net_count() == 156
    assert len(motor.cross_board_net_instances()) == 38
    assert len(motor.unproven_edges) == 38, "one pair per shared name, two boards"
    assert motor.unproven_nets == {}
    assert motor.non_addressable_pages() == ()


#: Severity counts per real multi-board fixture, measured on the pre-041 model
#: (2026-11-05, `.venv/Scripts/python.exe -c` over `build_project_model` +
#: `run_review`). 041 adds a data channel and no rule, so these must not move:
#: a moved row here means the derivation reached into a rule.
_PRE_041_SEVERITIES = {
    "foc": {"ERROR": 30, "WARN": 1, "INFO": 14},
    "motor": {"ERROR": 22, "WARN": 1, "INFO": 48},
}


@pytest.mark.parametrize("which", sorted(_PRE_041_SEVERITIES))
def test_the_multi_board_findings_are_unchanged(which, foc, motor, request):
    project = request.getfixturevalue(which)
    counts = collections.Counter(finding.severity for finding in run_review(project))
    assert dict(counts) == _PRE_041_SEVERITIES[which]
    assert sum(counts.values()) == sum(_PRE_041_SEVERITIES[which].values())
    # Every finding still names its own board, and boards still own their rules.
    assert {finding.board for finding in run_review(project)} <= set(project.board_titles())


# --------------------------------------------------------------------------
# 8. the disclosure section (S1 §2): shape, count=0, non-addressable, no proven
# --------------------------------------------------------------------------


def _two_boards_one_name() -> ProjectModel:
    return _project(
        _board("aaaa1111", "Board1", nets=("GND", "VCC"), pages=("p1",)),
        _board("bbbb2222", "Board2", nets=("GND",), pages=("p2",)),
    )


def test_the_section_names_boards_by_uuid_and_merges_nothing():
    """`source.crossBoardNets`'s whole contract, key by key.

    Boards carry the real uuid plus the title (display); each net row carries the
    instances, the evidence level, the reason and `merged: false`. With **no**
    declaration given there is no `proven`/`provenCount`/"declared connection" key
    at all — S2 adds those two keys only for a contract that validated, so this
    reading is still the pre-S2 one.
    """
    section = cross_board_net_section(_two_boards_one_name())
    assert section["boards"] == [
        {"uuid": "aaaa1111", "title": "Board1"},
        {"uuid": "bbbb2222", "title": "Board2"},
    ]
    assert section["count"] == 1
    assert section["nets"] == [{
        "name": "GND",
        "instances": [
            {"boardUuid": "aaaa1111", "boardTitle": "Board1", "netName": "GND"},
            {"boardUuid": "bbbb2222", "boardTitle": "Board2", "netName": "GND"},
        ],
        "evidenceLevel": "E0",
        "reason": "welded-by-name",
        "merged": False,
    }]
    assert section["nonAddressablePages"] == []
    assert section["note"]
    assert set(section) == {"boards", "count", "nets", "nonAddressablePages", "note"}
    assert not [key for key in section if "proven" in key.lower()]
    assert set(section["nets"][0]) == {
        "name", "instances", "evidenceLevel", "reason", "merged",
    }


def test_a_multi_board_project_with_no_shared_name_says_it_looked():
    """`count=0` is content, not absence: the reader must be able to tell "checked,
    nothing shared" from "this report knows nothing about it" (a single-board
    project omits the key entirely, below).

    And the Markdown says **the section's own note**, not a sentence the renderer
    re-invents: the JSON's `note` and the report's prose are one text, so a reader
    (or a diff of the two products) cannot find them disagreeing.
    """
    section = cross_board_net_section(_project(
        _board("aaaa1111", "Board1", nets=("GND",)),
        _board("bbbb2222", "Board2", nets=("VSS",)),
    ))
    assert section["count"] == 0
    assert section["nets"] == []
    assert len(section["boards"]) == 2
    assert section["note"]
    text = "\n".join(render_cross_board_nets_markdown(section))
    assert section["note"] in text, "the renderer prints the note verbatim"
    assert "已检查" in text, "count=0 must read as checked, not as silence"

    # A hand-built section from before the note existed still renders: the
    # fallback line is the count-only sentence, and the net rows still print.
    legacy = {"boards": [{"uuid": "aaaa1111", "title": "Board1"}], "count": 1,
              "nets": [{"name": "GND",
                        "instances": [{"boardUuid": "aaaa1111", "boardTitle": "Board1",
                                       "netName": "GND"},
                                      {"boardUuid": "bbbb2222", "boardTitle": "Board2",
                                       "netName": "GND"}],
                        "evidenceLevel": "E0", "reason": "welded-by-name",
                        "merged": False}],
              "nonAddressablePages": []}
    legacy_text = "\n".join(render_cross_board_nets_markdown(legacy))
    assert "1 个网名出现在多于一块板上" in legacy_text
    assert "`GND`" in legacy_text and "welded-by-name" in legacy_text


def test_an_empty_project_has_no_section_and_no_net_walk():
    """`ProjectModel()` (no boards at all) is not "one board": it has no nets to
    attribute and nothing to disclose. It must not fall through to a single-board
    read — that raised `MultiBoardProjectError` out of the triage before this fix —
    and it must not render a section claiming it checked two boards."""
    empty = ProjectModel()
    assert empty.boards == []
    assert cross_board_net_section(empty) == {}
    assert render_cross_board_nets_markdown(cross_board_net_section(empty)) == []
    slots = warning_triage_slots(
        model=empty, drc=_drc_on_net("GND"), findings=[], modules=_pwr_modules(),
    )
    assert _attribution_of(slots) is None, "no board, no module to attribute to"
    with pytest.raises(MultiBoardProjectError):
        checkup_engine._model_nets(empty)


def test_no_section_for_a_plain_model_a_board_or_an_implicit_project():
    """041 §1: a project with no BOARD document has no cross-board question, and a
    one-board project has nobody to ask it about. Both render nothing at all."""
    assert cross_board_net_section(DesignModel(nets={"GND": Net(name="GND")})) == {}
    assert cross_board_net_section(_project(
        _board("aaaa1111", "Board1", nets=("GND",)),
    )) == {}
    implicit = build_project_model(EPRJ3_SYNTH)
    assert cross_board_net_section(implicit) == {}
    assert render_cross_board_nets_markdown({}) == []


def test_unattached_pages_are_disclosed_in_the_section_and_join_no_net_row():
    section = cross_board_net_section(_project(
        _board("aaaa1111", "Board1", nets=("GND",), pages=("p1",)),
        _board("bbbb2222", "Board2", nets=("GND",), pages=("p2",)),
        _board("", "unattached", nets=("GND",), pages=("p9",)),
    ))
    assert section["boards"] == [
        {"uuid": "aaaa1111", "title": "Board1"},
        {"uuid": "bbbb2222", "title": "Board2"},
    ], "the empty-uuid group is not a board row"
    assert section["nonAddressablePages"] == [
        {"pageUuid": "p9", "boardTitle": "unattached"},
    ]
    (row,) = section["nets"]
    assert [instance["boardUuid"] for instance in row["instances"]] == [
        "aaaa1111", "bbbb2222",
    ], "the orphan page is not an instance — it is neither merged nor guessed into one"


def test_the_markdown_spells_short_uuids_with_titles_and_claims_nothing():
    """The reader gets uuid short codes (disambiguation without inventing an id)
    and the E0 label; the words are about a *reading*, never about a connection.

    The short code is the uuid's **last six** characters — the same convention
    `canvasrender` already uses for a board uuid (041 DRAFT §1), not the first
    eight: the tail is what differs between uuids a container mints in sequence.
    """
    lines = render_cross_board_nets_markdown(cross_board_net_section(_two_boards_one_name()))
    text = "\n".join(lines)
    assert lines[0].startswith("## ")
    assert "跨板网络" in lines[0]
    assert "`aa1111`" in text and "Board1" in text
    assert "`bb2222`" in text and "Board2" in text
    assert "`aaaa1111`" not in text, "the first-8 form is the wrong convention"
    assert "GND" in text
    assert "E0" in text and "welded-by-name" in text
    assert "未证明" in text
    for claim in ("已证明相连", "已连接", "已断开", "proven"):
        assert claim not in text, claim


# --------------------------------------------------------------------------
# 9. the two real reports: the key is wired, the findings are not
# --------------------------------------------------------------------------


def test_the_checkup_report_json_and_markdown_carry_the_section(tmp_path, foc):
    """End to end on the real three-board archive: `report.json` gets
    `source.crossBoardNets`, `report.md` gets its own section, and the findings
    count is the pre-041-S1 reading (241, measured before this batch)."""
    from boardwise import cli

    out = tmp_path / "checkup"
    out.mkdir()
    assert cli.main(["checkup", "--file", str(FOC), "--out", str(out)]) == 1, (
        "exit 1 = ERROR findings present; measured on this fixture"
    )

    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    section = report["source"]["crossBoardNets"]
    assert section["count"] == 39, "the model's 39 shared names reach the JSON"
    assert [(board["uuid"], board["title"]) for board in section["boards"]] == [
        (board.board.uuid, board.board.title) for board in foc.boards
    ]
    assert section["nonAddressablePages"] == []
    assert len(report["findings"]) == 241, "041-S1 adds a channel, not findings"
    summary = report["summary"]
    assert (summary["errorCount"], summary["warnCount"], summary["infoCount"]) == (
        50, 21, 170,
    ), "frozen from the pre-041-S1 checkup run on this fixture"
    assert report["completion"]["verdict"] == "incomplete", (
        "measured on this fixture: parts missing datasheets plus 21 untriaged "
        "WARNs, so the gate cannot claim complete — 041 must not move that word"
    )
    attributed = [
        row for row in report["warning_triage"]
        if (row.get("attribution") or {}).get("module")
    ]
    assert len(attributed) == 7, (
        "the pre-fix run had 8: the one that went away was "
        "`pcb-component-spacing` on R18, filed under 'Board1/P1' by "
        "first-board-wins. R18 is placed on Board1 *and* Board3 (an A1 repeat) "
        "and the PCB finding names 'PCB1', not a schematic board — so the honest "
        "answer is no module, and 7 is what per-board reading measures"
    )
    r18 = [
        row for row in report["warning_triage"]
        if "R18" in str(row.get("key") or "")
    ]
    assert r18, "the fixture still files a triage row for R18"
    assert all(
        (row.get("attribution") or {}).get("module") is None for row in r18
    ), "an ambiguous ref keeps its None: R18 is on Board1 and Board3"

    markdown = (out / "report.md").read_text(encoding="utf-8")
    assert "## 跨板网络（未证明）" in markdown
    assert "39 个网名" in markdown
    assert "provenCount" not in markdown
    assert "已证明相连" not in markdown


def test_review_md_discloses_while_review_json_keeps_its_findings(tmp_path):
    """`review --md` reads the same section through meta; `review --json`'s findings
    array is untouched. 041 S2 gave the command `--interconnect`; what this S1
    test still pins is that *without* it the reading is exactly S1's — and that a
    path the caller names but that does not exist is a refusal (exit 2, no
    report), not an empty "0 declared ties"."""
    from boardwise import cli

    md, js = tmp_path / "review.md", tmp_path / "review.json"
    assert cli.main([
        "review", str(FOC), "--md", str(md), "--json", str(js),
    ]) == 1, "exit 1 = ERROR findings present, which is what this fixture has"
    text = md.read_text(encoding="utf-8")
    assert "## 跨板网络（未证明）" in text
    assert "`GND`" in text and "welded-by-name" in text

    payload = json.loads(js.read_text(encoding="utf-8"))
    assert payload["summary"] == {"ERROR": 30, "WARN": 1, "INFO": 14}
    assert len(payload["findings"]) == 45, (
        "the same 45 run_review rows the model batch froze — 041 adds no finding"
    )

    absent = tmp_path / "no-such-declaration.json"
    assert not absent.exists(), "the refusal below must be about a missing file"
    assert cli.main(["review", str(FOC), "--interconnect", str(absent)]) == 2


def test_both_reports_say_the_same_thing_and_neither_draws_a_conclusion(foc):
    """One derivation, two products (S1 §3.2): the review report's section and the
    checkup section are the same object, so they cannot disagree — and the
    no-findings path must disclose too, which is where a report most tempts a
    reader into "nothing to say"."""
    section = cross_board_net_section(foc)
    checkup_text = "\n".join(render_cross_board_nets_markdown(section))
    review_text = render_markdown([], {
        "source": "foc", "components": 0, "nets": 0, "cross_board_nets": section,
    })
    assert "No findings." in review_text
    assert "## 跨板网络（未证明）" in review_text
    assert review_text.index("## 跨板网络") < review_text.index("No findings.")
    shared = [name for name in section["nets"]]
    assert len(shared) == 39
    for name in ("GND", "VCC", "PGND"):
        assert name in checkup_text and name in review_text
    for claim in ("已证明相连", "已连接", "已断开"):
        assert claim not in checkup_text and claim not in review_text


# --------------------------------------------------------------------------
# 10. the consumer: triage must not answer "which module" across boards
# --------------------------------------------------------------------------


def _drc_on_net(net: str) -> dict:
    """A DRC section shaped like `drc.py`'s: one PCB warning leaf on ``net``."""
    return {"schematic": {}, "pcb": {"groups": [{"index": 0, "leafs": [{
        "ruleName": "Clearance", "explanation": "too close", "net": net,
        "severity": "warn", "severitySource": "host", "globalIndex": "w1",
    }]}]}}


def _pwr_modules() -> list[dict]:
    return [{"name": "PWR", "components": ["U1"]}]


def _board_modules(board: str, name: str = "PWR") -> list[dict]:
    """A module row as a multi-board report writes it: ``board`` carries the title."""
    return [{"name": name, "board": board, "components": ["U1"]}]


def _attribution_of(slots: list[dict]) -> object:
    (slot,) = [s for s in slots if s["source"] == "pcb-drc"]
    return slot["attribution"]["module"]


def test_triage_refuses_a_net_that_two_boards_both_carry():
    """The negative control of §3.1: `GND` exists on both boards, so "which module
    is this net in" has two answers — the triage must give neither, and it must
    not fall back to the first board's."""
    u1 = Component(uid="u1", designator="U1", pins=[Pin(number="1", name="P1", net="GND")])
    on_net = {"GND": [("U1", "1")]}
    two_boards = _project(
        _board("aaaa1111", "Board1", nets=("GND",), pins=on_net, components=(u1,)),
        _board("bbbb2222", "Board2", nets=("GND",), pins=on_net, components=(u1,)),
    )
    slots = warning_triage_slots(
        model=two_boards,
        drc=_drc_on_net("GND"),
        findings=[],
        modules=_board_modules("Board1") + _board_modules("Board2", "SIG"),
    )
    assert _attribution_of(slots) is None

    # A host DRC leaf has no board identity. Even a name carried by only one
    # board may come from a stale PCB, so multi-board DRC rows never borrow a
    # module from the net name alone.
    split = _project(
        _board("aaaa1111", "Board1", nets=("GND",), pins=on_net, components=(u1,)),
        _board("bbbb2222", "Board2", nets=("VSS",), pins={"VSS": [("U1", "2")]},
               components=(u1,)),
    )
    assert _attribution_of(warning_triage_slots(
        model=split, drc=_drc_on_net("GND"), findings=[], modules=_board_modules("Board1"),
    )) is None

    # ... and the single-board path is the pre-041 one, unchanged.
    one_board = _project(
        _board("aaaa1111", "Board1", nets=("GND",), pins=on_net, components=(u1,))
    )
    assert _attribution_of(warning_triage_slots(
        model=one_board, drc=_drc_on_net("GND"), findings=[], modules=_pwr_modules(),
    )) == "PWR"
    plain = DesignModel(
        nets={"GND": Net(name="GND", pins=[("U1", "1")])},
        components={"U1": u1},
    )
    assert _attribution_of(warning_triage_slots(
        model=plain, drc=_drc_on_net("GND"), findings=[], modules=_pwr_modules(),
    )) == "PWR"


def test_triage_counts_an_unattached_group_as_a_second_owner():
    """`unattached` has no uuid, but its pages still spell the name. A module
    attribution would be a claim about a page nobody can address, so the row keeps
    its `None` — the same answer the addressable pair gets."""
    u1 = Component(uid="u1", designator="U1", pins=[Pin(number="1", name="P1", net="GND")])
    project = _project(
        _board("aaaa1111", "Board1", nets=("GND",), pins={"GND": [("U1", "1")]},
               components=(u1,)),
        _board("", "unattached", nets=("GND",), pages=("p9",)),
    )
    assert _attribution_of(warning_triage_slots(
        model=project, drc=_drc_on_net("GND"), findings=[], modules=_pwr_modules(),
    )) is None


def _c1() -> Component:
    return Component(uid="c1", designator="C1", pins=[Pin(number="1", name="P1", net="")])


def _rule_module(model, modules, *, board: str, ref: str = "C1") -> object:
    """The module a WARN finding on ``ref`` was attributed to, on ``board``."""
    finding = {"rule_id": "some-rule", "severity": "WARN", "message": "m",
               "refs": [ref], "board": board}
    (slot,) = [
        slot for slot in warning_triage_slots(
            model=model, drc={}, findings=[finding], modules=modules)
        if slot["source"] == "boardwise-rule"
    ]
    return slot["attribution"]["module"]


def test_triage_reads_each_boards_own_modules_for_findings():
    """Review-fix P1: the flat ``designator -> module`` map let the first board win.

    Host DRC leaves carry no board identity, so both multi-board rows below stay
    unattributed. A boardwise finding is different: it names its board, and its
    refs are read only against that board's modules, never the first board's.
    """
    c1 = _c1()
    project = _project(
        _board("aaaa1111", "Board1", nets=("VCC",), pins={"VCC": [("C1", "1")]},
               components=(c1,)),
        _board("bbbb2222", "Board2", nets=("SIG_NET",), pins={"SIG_NET": [("C1", "1")]},
               components=(c1,)),
    )
    modules = [
        {"name": "PWR", "board": "Board1", "components": ["C1"]},
        {"name": "SIG", "board": "Board2", "components": ["C1"]},
    ]
    assert _attribution_of(warning_triage_slots(
        model=project, drc=_drc_on_net("SIG_NET"), findings=[], modules=modules,
    )) is None, "a DRC leaf has no board identity, even for a board-unique net"
    assert _attribution_of(warning_triage_slots(
        model=project, drc=_drc_on_net("VCC"), findings=[], modules=modules,
    )) is None

    assert _rule_module(project, modules, board="Board1") == "PWR"
    assert _rule_module(project, modules, board="Board2") == "SIG"
    # A finding that names a board the project does not have gets no module: the
    # row is already wrong, and guessing a board is how the weld came back.
    assert _rule_module(project, modules, board="Board9") is None
    # Two candidates are counted by **board + module**, not by module name alone:
    # even when both boards call their module "PWR", they are still two choices.
    same_name_modules = [
        {"name": "PWR", "board": "Board1", "components": ["C1"]},
        {"name": "PWR", "board": "Board2", "components": ["C1"]},
    ]
    assert _rule_module(project, same_name_modules, board="PCB9") is None
    # A cropped module list does not erase the model's proof that C1 exists on
    # both boards: one surviving candidate is still not a unique placement.
    assert _rule_module(project, modules[:1], board="PCB9") is None


def test_triage_attributes_nothing_when_two_boards_share_a_title():
    """Two boards both called ``Board1`` cannot be told apart by a module row's
    ``board`` field, which carries the title. The conservative answer is no
    attribution — a title is display, so it is not an identity to guess with."""
    c1 = _c1()
    project = _project(
        _board("aaaa1111", "Board1", nets=("VCC",), pins={"VCC": [("C1", "1")]},
               components=(c1,)),
        _board("bbbb2222", "Board1", nets=("SIG_NET",), pins={"SIG_NET": [("C1", "1")]},
               components=(c1,)),
    )
    modules = [
        {"name": "PWR", "board": "Board1", "components": ["C1"]},
        {"name": "SIG", "board": "Board1", "components": ["C1"]},
    ]
    assert _attribution_of(warning_triage_slots(
        model=project, drc=_drc_on_net("VCC"), findings=[], modules=modules,
    )) is None
    assert _attribution_of(warning_triage_slots(
        model=project, drc=_drc_on_net("SIG_NET"), findings=[], modules=modules,
    )) is None
    assert _rule_module(project, modules, board="Board1") is None

    # One board of that name is not ambiguous, and the single-board path is the
    # pre-041 one: the flat map, board key or not.
    single = _project(
        _board("aaaa1111", "Board1", nets=("VCC",), pins={"VCC": [("C1", "1")]},
               components=(c1,)),
    )
    for rows in (modules[:1], [{"name": "PWR", "components": ["C1"]}]):
        assert _attribution_of(warning_triage_slots(
            model=single, drc=_drc_on_net("VCC"), findings=[], modules=rows,
        )) == "PWR"
        assert _rule_module(single, rows, board="Board1") == "PWR"


def test_model_nets_refuses_a_multi_board_project():
    """§3.1's guard: the helper that merged nets by name now goes through
    `single_board()`, so a future caller cannot quietly reintroduce the weld."""
    project = _two_boards_one_name()
    with pytest.raises(MultiBoardProjectError):
        checkup_engine._model_nets(project)

    single = _project(_board("aaaa1111", "Board1", nets=("GND", "VCC")))
    nets = checkup_engine._model_nets(single)
    assert sorted(nets) == ["GND", "VCC"]
    assert nets["GND"] == Net(name="GND")

    plain = DesignModel(nets={"GND": Net(name="GND")})
    assert checkup_engine._model_nets(plain) is plain.nets


# --------------------------------------------------------------------------
# 11. the single-board and implicit texts do not move
# --------------------------------------------------------------------------


def test_single_board_outputs_are_byte_identical(tmp_path):
    """041's keys are additive: an absent section renders as nothing, and a
    one-board project's review Markdown is what it was before the batch."""
    base = {"source": "golden", "components": 17, "nets": 13}
    assert render_markdown([], base) == render_markdown([], {**base, "cross_board_nets": {}})
    assert render_markdown([], base) == (
        "# boardwise review report\n\n- Source: golden\n- Components: 17\n"
        "- Nets: 13\n- Findings: 0 ERROR, 0 WARN, 0 INFO\n\nNo findings.\n"
    )
    report = render_report_markdown({"source": {"file": "golden"}})
    assert "跨板网络" not in report

    from boardwise import cli

    out = tmp_path / "single.md"
    assert cli.main(["review", str(GOLDEN), "--md", str(out)]) in (0, 3)
    text = out.read_text(encoding="utf-8")
    assert "跨板网络" not in text
    assert "No findings." not in text, "this board does produce findings"


# --------------------------------------------------------------------------
# 12. the edge is not a loop, and the real run's own verdict
# --------------------------------------------------------------------------


def test_an_edge_is_never_a_self_loop():
    """``first == second`` is not a question about two nodes — it is one node
    written twice, and a "unproven connection" from a net to itself would let a
    reader count a board as "affected" twice. Refused at construction."""
    gnd = NetInstance("aaaa1111", "GND")
    with pytest.raises(ValueError):
        UnprovenNetEdge(gnd, gnd)
    with pytest.raises(ValueError):
        UnprovenNetEdge(first=gnd, second=NetInstance("aaaa1111", "GND"))
    # The same board's *other* net is two nodes, and stays allowed — 041 puts no
    # restriction on the name itself.
    assert UnprovenNetEdge(gnd, NetInstance("aaaa1111", "VCC")).reason == WELDED_BY_NAME
