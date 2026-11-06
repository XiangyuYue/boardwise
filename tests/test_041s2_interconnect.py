"""041 S2: declaration parsing, report disclosure and the two offline CLI consumers.

041 S1 said what a multi-board reading **cannot** prove. S2 adds the other
direction: an engineer can write down that ``5V_IN`` on board A is tied to
``VSYS`` on board B, and that statement is read, checked against the real model
and disclosed. This file pins ``boardwise.core.interconnect``, the shared report
section/renderer, and ``review <file>`` / ``checkup --file`` end to end:

* a good file parses; both ends are real ``(board uuid, net)`` instances and the
  note is preserved verbatim;
* a same-named group is **not** upgraded, merged or removed from the E0 reading;
  an explicitly declared pair is disclosed separately with ``merged=false``;
* an explicit ``edges: []`` is a successful zero, while missing/broken files,
  unknown or repeated keys, wrong versions/types/declarers, wrong identities,
  non-addressable endpoints, same-board pairs and repeated pairs are refusals;
* ``projectUuid`` is optional, but when given must match the container's real
  uuid verbatim; no title, file digest or path can stand in for it;
* only the explicitly named file is opened, and online, PCB-view, finalize and
  single-board invocations refuse the flag rather than silently ignoring it.

The no-argument path keeps S1's keys, note, Markdown, findings, severity, verdict
and exit codes unchanged. A later S3 host cross-check is deliberately not here.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
from pathlib import Path

import pytest

from boardwise.core import interconnect as interconnect_module
from boardwise.core.interconnect import (
    DECLARED_BY_ENGINEER,
    INTERCONNECT_VERSION,
    InterconnectContract,
    InterconnectError,
    ProvenNetEdge,
    load_interconnect,
    parse_interconnect,
)
from boardwise.core.model import (
    BoardModel,
    BoardRef,
    DesignModel,
    Net,
    NetInstance,
    ProjectModel,
)
from boardwise.engines import review as review_engine
from boardwise.engines.checkup import (
    cross_board_net_section,
    render_cross_board_nets_markdown,
)

A = "aaaa1111"
B = "bbbb2222"
C = "cccc3333"


def _board(
    uuid: str, title: str, *, nets: tuple[str, ...] = (), pages: tuple[str, ...] = ()
) -> BoardModel:
    """One board, written down directly (no file, no parser)."""
    return BoardModel(
        nets={name: Net(name=name) for name in nets},
        board=BoardRef(uuid=uuid, title=title, page_uuids=pages),
    )


def _project(*boards: BoardModel, source: str = "in-memory") -> ProjectModel:
    return ProjectModel(boards=list(boards), source=source)


@pytest.fixture()
def project() -> ProjectModel:
    """Two addressable boards, one same-named net (``GND``) and one unique each."""
    return _project(
        _board(A, "Board1", nets=("GND", "5V_IN")),
        _board(B, "Board2", nets=("GND", "VCC", "VSYS")),
    )


def _end(board: str, net: str) -> dict[str, str]:
    return {"boardUuid": board, "net": net}


def _edge(
    source: tuple[str, str] = (A, "5V_IN"),
    target: tuple[str, str] = (B, "VSYS"),
    *,
    declared_by: str | None = DECLARED_BY_ENGINEER,
    note: object | None = None,
) -> dict[str, object]:
    edge: dict[str, object] = {"from": _end(*source), "to": _end(*target)}
    if declared_by is not None:
        edge["declaredBy"] = declared_by
    if note is not None:
        edge["note"] = note
    return edge


def _payload(edges: list[object] | object, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"interconnectVersion": 1, "edges": edges}
    payload.update(extra)
    return payload


def _parse(payload: object, project: ProjectModel, **kwargs: object) -> InterconnectContract:
    return parse_interconnect(payload, project, **kwargs)


# --------------------------------------------------------------------------
# 1. a good declaration: two real instances, one declared tie, note kept
# --------------------------------------------------------------------------


def test_two_boards_different_net_names_parse_into_one_declared_edge(
    project: ProjectModel,
) -> None:
    """The headline case: ``5V_IN@A`` ↔ ``VSYS@B`` is what a harness actually ties.

    Both ends come back as ``NetInstance`` — board uuid *and* net name — so a
    report never has to guess which board's net it is quoting.
    """
    contract = _parse(
        _payload([_edge(note="CN2 pin1-pin4 线束")]), project, source="harness.json"
    )

    assert isinstance(contract, InterconnectContract)
    assert contract.project_uuid == ""
    assert isinstance(contract.edges, tuple)
    assert len(contract.edges) == 1
    edge = contract.edges[0]
    assert isinstance(edge, ProvenNetEdge)
    assert edge.first == NetInstance(A, "5V_IN")
    assert edge.second == NetInstance(B, "VSYS")
    assert edge.declared_by == DECLARED_BY_ENGINEER == "engineer"
    assert edge.note == "CN2 pin1-pin4 线束"
    assert edge.evidence_level == "engineer-declared"


def test_the_note_is_optional_and_defaults_to_the_empty_string(
    project: ProjectModel,
) -> None:
    contract = _parse(_payload([_edge()]), project)
    assert contract.edges[0].note == ""


def test_edge_order_is_the_file_order(project: ProjectModel) -> None:
    contract = _parse(
        _payload([_edge(), _edge((A, "GND"), (B, "VCC")), _edge((A, "5V_IN"), (B, "GND"))]),
        project,
    )
    assert [(edge.first.net_name, edge.second.net_name) for edge in contract.edges] == [
        ("5V_IN", "VSYS"),
        ("GND", "VCC"),
        ("5V_IN", "GND"),
    ]


def test_the_same_net_name_on_both_boards_is_untouched_by_a_declaration(
    project: ProjectModel,
) -> None:
    """A declaration is not a netlist merge (041 S2 §2).

    ``GND`` on A and ``GND`` on B stay two instances, stay one unproven edge, and
    the declaration's own pair is not quietly added to that channel either: the
    proven channel and the unproven channel answer different questions.
    """
    instances_before = project.net_instances()
    groups_before = project.cross_board_net_instances()
    unproven_before = project.unproven_edges
    nets_before = [dict(board.nets) for board in project.boards]

    _parse(_payload([_edge()]), project)

    assert project.net_instances() == instances_before
    assert project.cross_board_net_instances() == groups_before
    assert project.unproven_edges == unproven_before
    # No board's netlist gained or lost a name, and the declaration did not
    # invent a project-wide net out of the two same-named ones.
    assert [dict(board.nets) for board in project.boards] == nets_before
    assert [len(members) for members in project.cross_board_net_instances().values()] == [2]
    assert NetInstance(A, "GND") in project.cross_board_net_instances()["GND"]
    assert NetInstance(B, "GND") in project.cross_board_net_instances()["GND"]
    proved_pairs = {frozenset((edge.first, edge.second)) for edge in project.unproven_edges}
    assert frozenset((NetInstance(A, "5V_IN"), NetInstance(B, "VSYS"))) not in proved_pairs
    # The single-board façade still refuses, i.e. nothing welded the project into
    # one netlist behind the caller's back.
    assert all(name not in project.boards[0].nets for name in ("VSYS", "VCC"))


def test_an_explicit_empty_edges_array_is_a_successful_zero(
    project: ProjectModel,
) -> None:
    """``[]`` is a real answer; only a *failed* read is not allowed to look like it."""
    contract = _parse(_payload([]), project)
    assert contract.edges == ()
    assert contract.project_uuid == ""


# --------------------------------------------------------------------------
# 2. the identity gate: projectUuid is optional, but never guessed
# --------------------------------------------------------------------------


def test_a_matching_project_uuid_is_accepted_verbatim(project: ProjectModel) -> None:
    contract = _parse(
        _payload([_edge()], projectUuid="proj-abc"),
        project,
        project_uuid="proj-abc",
    )
    assert contract.project_uuid == "proj-abc"


def test_an_omitted_project_uuid_needs_no_real_identity(project: ProjectModel) -> None:
    """Every ``.epro2`` container has no real uuid, so omission must work."""
    contract = _parse(_payload([_edge()]), project, project_uuid="")
    assert contract.project_uuid == ""


def test_a_mismatched_project_uuid_is_refused(project: ProjectModel) -> None:
    with pytest.raises(InterconnectError, match="does not match"):
        _parse(
            _payload([_edge()], projectUuid="proj-abc"),
            project,
            project_uuid="proj-other",
        )


def test_a_project_uuid_differing_only_in_case_is_refused(project: ProjectModel) -> None:
    with pytest.raises(InterconnectError, match="does not match"):
        _parse(
            _payload([_edge()], projectUuid="MyProject"),
            project,
            project_uuid="myproject",
        )


def test_a_project_uuid_given_to_a_container_without_one_is_refused(
    project: ProjectModel,
) -> None:
    """``.epro2`` has no real identity: no title, digest or path may stand in."""
    with pytest.raises(InterconnectError, match="no real projectUuid"):
        _parse(_payload([_edge()], projectUuid="proj-abc"), project)


@pytest.mark.parametrize("value", ["", 1, None, True, ["proj"]])
def test_a_project_uuid_that_is_not_a_non_empty_string_is_refused(
    project: ProjectModel, value: object
) -> None:
    with pytest.raises(InterconnectError, match="projectUuid"):
        _parse(
            _payload([_edge()], projectUuid=value),
            project,
            project_uuid="proj-abc",
        )


# --------------------------------------------------------------------------
# 3. version and root structure
# --------------------------------------------------------------------------


def test_the_only_version_is_the_integer_one() -> None:
    assert INTERCONNECT_VERSION == 1


@pytest.mark.parametrize("version", [True, False, 0, 2, "1", 1.0, None, [1]])
def test_every_other_version_is_refused(project: ProjectModel, version: object) -> None:
    """``True == 1`` in Python, so a bool version must be refused explicitly."""
    with pytest.raises(InterconnectError, match="interconnectVersion"):
        _parse({"interconnectVersion": version, "edges": []}, project)


def test_a_missing_version_is_refused(project: ProjectModel) -> None:
    with pytest.raises(InterconnectError, match="interconnectVersion"):
        _parse({"edges": []}, project)


def test_a_root_that_is_not_an_object_is_refused(project: ProjectModel) -> None:
    with pytest.raises(InterconnectError, match="must be a JSON object"):
        _parse([], project)


def test_an_unknown_root_key_is_refused(project: ProjectModel) -> None:
    with pytest.raises(InterconnectError, match="unknown key"):
        _parse(_payload([], projectID="proj-abc"), project)


@pytest.mark.parametrize("edges", [None, {}, "[]", 1, True])
def test_edges_must_be_an_array(project: ProjectModel, edges: object) -> None:
    with pytest.raises(InterconnectError, match="edges: must be an array"):
        _parse({"interconnectVersion": 1, "edges": edges}, project)


def test_a_missing_edges_key_is_refused(project: ProjectModel) -> None:
    with pytest.raises(InterconnectError, match="missing required key"):
        _parse({"interconnectVersion": 1}, project)


# --------------------------------------------------------------------------
# 4. per-edge structure: closed key set, required members, exact declarer
# --------------------------------------------------------------------------


@pytest.mark.parametrize("edge", [[], "x", 1, None, True])
def test_an_edge_that_is_not_an_object_is_refused(
    project: ProjectModel, edge: object
) -> None:
    with pytest.raises(InterconnectError, match="must be an object"):
        _parse(_payload([edge]), project)


def test_an_unknown_edge_key_is_refused(project: ProjectModel) -> None:
    raw = _edge()
    raw["merged"] = True
    with pytest.raises(InterconnectError, match="unknown key"):
        _parse(_payload([raw]), project)


@pytest.mark.parametrize("missing", ["from", "to", "declaredBy"])
def test_a_missing_required_edge_key_is_refused(
    project: ProjectModel, missing: str
) -> None:
    raw = _edge()
    del raw[missing]
    with pytest.raises(InterconnectError, match="missing required key"):
        _parse(_payload([raw]), project)


@pytest.mark.parametrize("declarer", ["Engineer", "engineer ", " engineer", "tool", ""])
def test_a_declarer_other_than_exactly_engineer_is_refused(
    project: ProjectModel, declarer: str
) -> None:
    with pytest.raises(InterconnectError, match="declaredBy"):
        _parse(_payload([_edge(declared_by=declarer)]), project)


@pytest.mark.parametrize("declarer", [None, 1, True, ["engineer"]])
def test_a_non_string_declarer_is_refused(
    project: ProjectModel, declarer: object
) -> None:
    raw = _edge()
    raw["declaredBy"] = declarer
    with pytest.raises(InterconnectError, match="declaredBy"):
        _parse(_payload([raw]), project)


@pytest.mark.parametrize("note", [1, True, None, [], {}])
def test_a_non_string_note_is_refused(project: ProjectModel, note: object) -> None:
    raw = _edge()
    raw["note"] = note
    with pytest.raises(InterconnectError, match="note"):
        _parse(_payload([raw]), project)


# --------------------------------------------------------------------------
# 5. endpoints: real board uuid, verbatim net, nothing invented
# --------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", [[], "a", 1, None])
def test_an_endpoint_that_is_not_an_object_is_refused(
    project: ProjectModel, endpoint: object
) -> None:
    with pytest.raises(InterconnectError, match="must be an object"):
        _parse(_payload([{"from": endpoint, "to": _end(B, "VSYS"), "declaredBy": "engineer"}]), project)


def test_an_unknown_endpoint_key_is_refused(project: ProjectModel) -> None:
    raw = _edge()
    raw["from"] = {**_end(A, "5V_IN"), "boardTitle": "Board1"}
    with pytest.raises(InterconnectError, match="unknown key"):
        _parse(_payload([raw]), project)


@pytest.mark.parametrize("missing", ["boardUuid", "net"])
def test_a_missing_endpoint_key_is_refused(project: ProjectModel, missing: str) -> None:
    raw = _edge()
    start = dict(_end(A, "5V_IN"))
    del start[missing]
    raw["from"] = start
    with pytest.raises(InterconnectError, match="missing required key"):
        _parse(_payload([raw]), project)


@pytest.mark.parametrize("value", ["", 1, None, True, ["x"]])
def test_an_empty_or_non_string_board_uuid_is_refused(
    project: ProjectModel, value: object
) -> None:
    raw = _edge()
    raw["from"] = {"boardUuid": value, "net": "5V_IN"}
    with pytest.raises(InterconnectError, match="boardUuid"):
        _parse(_payload([raw]), project)


@pytest.mark.parametrize("value", ["", 1, None, True])
def test_an_empty_or_non_string_net_is_refused(
    project: ProjectModel, value: object
) -> None:
    raw = _edge()
    raw["from"] = {"boardUuid": A, "net": value}
    with pytest.raises(InterconnectError, match="net"):
        _parse(_payload([raw]), project)


def test_a_board_title_where_a_uuid_belongs_is_refused(project: ProjectModel) -> None:
    """A title is display text: two boards may share one, so it cannot address."""
    with pytest.raises(InterconnectError, match="no addressable BOARD"):
        _parse(_payload([_edge(("Board1", "5V_IN"))]), project)


def test_an_unattached_page_uuid_is_refused() -> None:
    """A page no board registers is disclosed elsewhere, and declares nothing."""
    project = _project(
        _board(A, "Board1", nets=("5V_IN",)),
        _board(B, "Board2", nets=("VSYS",)),
        _board("", "unattached", nets=("ORPHAN",), pages=("page-orphan",)),
    )
    with pytest.raises(InterconnectError, match="no addressable BOARD"):
        _parse(_payload([_edge(("page-orphan", "ORPHAN"))]), project)


def test_an_unknown_board_uuid_is_refused(project: ProjectModel) -> None:
    with pytest.raises(InterconnectError, match="no addressable BOARD"):
        _parse(_payload([_edge((C, "5V_IN"))]), project)


def test_a_net_that_does_not_exist_on_that_board_is_refused(
    project: ProjectModel,
) -> None:
    with pytest.raises(InterconnectError, match="has no net"):
        _parse(_payload([_edge((A, "VSYS"), (B, "5V_IN"))]), project)


@pytest.mark.parametrize("net", ["vsys", "VSYS ", " VSYS", "Vsys"])
def test_net_names_are_compared_verbatim(project: ProjectModel, net: str) -> None:
    """No trimming, no case folding — the model's own rule, applied here."""
    with pytest.raises(InterconnectError, match="has no net"):
        _parse(_payload([_edge((A, "5V_IN"), (B, net))]), project)


# --------------------------------------------------------------------------
# 6. the pair: two different boards, declared once
# --------------------------------------------------------------------------


def test_a_self_loop_is_refused(project: ProjectModel) -> None:
    with pytest.raises(InterconnectError, match="itself|one board"):
        _parse(_payload([_edge((A, "5V_IN"), (A, "5V_IN"))]), project)


def test_two_nets_of_one_board_are_refused(project: ProjectModel) -> None:
    """A board-internal short is not a cross-board declaration (041 S2 §1)."""
    with pytest.raises(InterconnectError, match="one board"):
        _parse(_payload([_edge((A, "5V_IN"), (A, "GND"))]), project)


def test_a_repeated_pair_in_the_same_direction_is_refused(
    project: ProjectModel,
) -> None:
    with pytest.raises(InterconnectError, match="repeats edges"):
        _parse(_payload([_edge(), _edge()]), project)


def test_a_repeated_pair_in_the_opposite_direction_is_refused(
    project: ProjectModel,
) -> None:
    """Swapping ``from``/``to`` names the same unordered pair, so it is a repeat."""
    with pytest.raises(InterconnectError, match="repeats edges"):
        _parse(_payload([_edge(), _edge((B, "VSYS"), (A, "5V_IN"))]), project)


def test_a_differing_note_does_not_make_a_second_tie(project: ProjectModel) -> None:
    with pytest.raises(InterconnectError, match="repeats edges"):
        _parse(
            _payload(
                [
                    _edge(note="CN2 pin1"),
                    _edge((B, "VSYS"), (A, "5V_IN"), note="CN2 pin4"),
                ]
            ),
            project,
        )


def test_three_boards_may_declare_three_distinct_pairs() -> None:
    project = _project(
        _board(A, "Board1", nets=("5V_IN",)),
        _board(B, "Board2", nets=("VSYS",)),
        _board(C, "Board3", nets=("VIN",)),
    )
    contract = _parse(
        _payload(
            [
                _edge((A, "5V_IN"), (B, "VSYS")),
                _edge((B, "VSYS"), (C, "VIN")),
                _edge((C, "VIN"), (A, "5V_IN")),
            ]
        ),
        project,
    )
    assert len(contract.edges) == 3


# --------------------------------------------------------------------------
# 7. only a multi-board ProjectModel can carry a declaration
# --------------------------------------------------------------------------


def test_a_plain_design_model_is_refused() -> None:
    with pytest.raises(InterconnectError, match="ProjectModel"):
        _parse(_payload([_edge()]), DesignModel())


def test_one_boards_model_is_refused() -> None:
    with pytest.raises(InterconnectError, match="ProjectModel"):
        _parse(_payload([_edge()]), _board(A, "Board1", nets=("5V_IN",)))


def test_a_single_board_project_is_refused() -> None:
    project = _project(_board(A, "Board1", nets=("5V_IN",)))
    with pytest.raises(InterconnectError, match="at least two addressable"):
        _parse(_payload([]), project)


def test_an_implicit_second_board_is_not_addressable() -> None:
    """One real board plus an empty-uuid group is one addressable board."""
    project = _project(
        _board(A, "Board1", nets=("5V_IN",)),
        _board("", "Board2", nets=("VSYS",), pages=("page-2",)),
    )
    with pytest.raises(InterconnectError, match="at least two addressable"):
        _parse(_payload([]), project)


# --------------------------------------------------------------------------
# 8. loading: one explicit path, every failure named, none of them empty
# --------------------------------------------------------------------------


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_a_named_file_is_read_and_validated(project: ProjectModel, tmp_path: Path) -> None:
    path = _write(tmp_path / "harness.json", _payload([_edge(note="CN2")]))
    contract = load_interconnect(path, project, project_uuid="")
    assert [(edge.first, edge.second) for edge in contract.edges] == [
        (NetInstance(A, "5V_IN"), NetInstance(B, "VSYS"))
    ]


def test_a_missing_file_is_refused_and_names_the_path(
    project: ProjectModel, tmp_path: Path
) -> None:
    path = tmp_path / "nope.json"
    with pytest.raises(InterconnectError, match="not found") as caught:
        load_interconnect(path, project)
    assert str(path) in str(caught.value)


def test_a_directory_is_refused(project: ProjectModel, tmp_path: Path) -> None:
    with pytest.raises(InterconnectError, match="is a directory"):
        load_interconnect(tmp_path, project)


def test_broken_json_is_refused(project: ProjectModel, tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text('{"interconnectVersion": 1, "edges": [}', encoding="utf-8")
    with pytest.raises(InterconnectError, match="not valid JSON"):
        load_interconnect(path, project)


def test_an_empty_file_is_refused(project: ProjectModel, tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text("", encoding="utf-8")
    with pytest.raises(InterconnectError, match="not valid JSON"):
        load_interconnect(path, project)


def test_non_utf8_bytes_are_refused(project: ProjectModel, tmp_path: Path) -> None:
    path = tmp_path / "latin1.json"
    path.write_bytes(b'{"interconnectVersion": 1, "edges": [], "note": "\xff\xfe"}')
    with pytest.raises(InterconnectError, match="not UTF-8"):
        load_interconnect(path, project)


def test_a_repeated_json_key_at_the_root_is_refused(
    project: ProjectModel, tmp_path: Path
) -> None:
    """Last-wins would let a stale value hide behind a corrected one."""
    path = tmp_path / "dup.json"
    path.write_text(
        '{"interconnectVersion": 1, "edges": [], "edges": [{"from": {}}]}',
        encoding="utf-8",
    )
    with pytest.raises(InterconnectError, match="duplicate key") as caught:
        load_interconnect(path, project)
    assert str(path) in str(caught.value)


def test_a_repeated_json_key_inside_one_edge_is_refused(
    project: ProjectModel, tmp_path: Path
) -> None:
    path = tmp_path / "dup-edge.json"
    path.write_text(
        '{"interconnectVersion": 1, "edges": [{"from": {"boardUuid": "'
        + A
        + '", "net": "5V_IN", "net": "GND"}, "to": {"boardUuid": "'
        + B
        + '", "net": "VSYS"}, "declaredBy": "engineer"}]}',
        encoding="utf-8",
    )
    with pytest.raises(InterconnectError, match="duplicate key"):
        load_interconnect(path, project)


def test_no_file_is_discovered_next_to_the_project(
    project: ProjectModel, tmp_path: Path
) -> None:
    """A plausible default name sitting in the directory is not evidence."""
    _write(tmp_path / "interconnect.json", _payload([_edge()]))
    _write(tmp_path / "boardwise.interconnect.json", _payload([_edge()]))
    with pytest.raises(InterconnectError, match="not found"):
        load_interconnect(tmp_path / "declared.json", project)


def test_the_module_has_no_default_path_helper() -> None:
    assert [name for name in dir(interconnect_module) if "default" in name.lower()] == []


def test_loading_requires_an_explicit_path(project: ProjectModel) -> None:
    with pytest.raises(TypeError):
        load_interconnect(model=project)  # type: ignore[call-arg]


def test_a_bad_file_never_yields_an_empty_contract(
    project: ProjectModel, tmp_path: Path
) -> None:
    """The failure mode this whole section exists for: '0 declared' ≠ 'unreadable'."""
    path = tmp_path / "bad.json"
    path.write_text('{"interconnectVersion": 2, "edges": []}', encoding="utf-8")
    with pytest.raises(InterconnectError):
        load_interconnect(path, project)


# --------------------------------------------------------------------------
# 9. the data classes defend themselves too
# --------------------------------------------------------------------------


def test_the_error_is_a_value_error() -> None:
    assert issubclass(InterconnectError, ValueError)


def test_an_edge_cannot_be_built_from_a_non_instance() -> None:
    with pytest.raises(TypeError, match="NetInstance"):
        ProvenNetEdge((A, "5V_IN"), NetInstance(B, "VSYS"))  # type: ignore[arg-type]


def test_an_edge_cannot_join_one_boards_two_nets() -> None:
    with pytest.raises(InterconnectError, match="one board"):
        ProvenNetEdge(NetInstance(A, "5V_IN"), NetInstance(A, "GND"))


def test_an_edge_cannot_be_a_self_loop() -> None:
    with pytest.raises(InterconnectError, match="itself|one board"):
        ProvenNetEdge(NetInstance(A, "5V_IN"), NetInstance(A, "5V_IN"))


def test_an_edge_rejects_another_declarer() -> None:
    with pytest.raises(InterconnectError, match="declared_by"):
        ProvenNetEdge(NetInstance(A, "5V_IN"), NetInstance(B, "VSYS"), declared_by="tool")


def test_an_edge_rejects_a_non_string_note() -> None:
    with pytest.raises(InterconnectError, match="note"):
        ProvenNetEdge(NetInstance(A, "5V_IN"), NetInstance(B, "VSYS"), note=1)  # type: ignore[arg-type]


def test_an_edge_rejects_an_empty_net_name() -> None:
    with pytest.raises(InterconnectError, match="no net name"):
        ProvenNetEdge(NetInstance(A, ""), NetInstance(B, "VSYS"))


def test_a_contract_stores_its_edges_as_a_tuple() -> None:
    edge = ProvenNetEdge(NetInstance(A, "5V_IN"), NetInstance(B, "VSYS"))
    contract = InterconnectContract(project_uuid="proj", edges=[edge])  # type: ignore[arg-type]
    assert isinstance(contract.edges, tuple)
    assert contract.edges == (edge,)


def test_a_contract_is_frozen() -> None:
    contract = InterconnectContract()
    with pytest.raises(dataclasses.FrozenInstanceError):
        contract.project_uuid = "other"  # type: ignore[misc]


def test_a_contract_rejects_a_foreign_edge_object() -> None:
    with pytest.raises(InterconnectError, match="ProvenNetEdge"):
        InterconnectContract(edges=("not an edge",))  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# 10. the report disclosure: what a validated declaration adds, and what it does not
# --------------------------------------------------------------------------

OLD_NOTE = (
    "1 个网名出现在多于一块板上：跨板连通性未证明（证据级别 E0，仅网名相同），"
    "因此未合并；未证明不等于断开"
)


@pytest.fixture()
def declared(project: ProjectModel) -> InterconnectContract:
    """The one declaration this section is about: ``5V_IN@A`` tied to ``VSYS@B``."""
    return _parse(_payload([_edge(note="CN2 pin1-pin4 线束")]), project)


def test_the_section_discloses_one_declared_tie(project, declared) -> None:
    section = cross_board_net_section(project, declared)
    assert set(section) == {
        "boards",
        "count",
        "nets",
        "nonAddressablePages",
        "note",
        "provenCount",
        "proven",
    }
    assert section["provenCount"] == 1
    assert section["proven"] == [
        {
            "from": {"boardUuid": A, "boardTitle": "Board1", "netName": "5V_IN"},
            "to": {"boardUuid": B, "boardTitle": "Board2", "netName": "VSYS"},
            "declaredBy": "engineer",
            "note": "CN2 pin1-pin4 线束",
            "evidenceLevel": "engineer-declared",
            "merged": False,
        }
    ]


def test_the_note_keeps_its_old_text_and_adds_the_declared_count(project, declared) -> None:
    note = cross_board_net_section(project, declared)["note"]
    assert note.startswith(OLD_NOTE), "the S1 sentence is unchanged, only appended to"
    assert note == OLD_NOTE + "；1 条已声明跨板连接（显式工程师声明；仅披露，不合并网表）"


def test_the_markdown_says_declared_in_the_title_and_lists_both_ends(project, declared) -> None:
    text = "\n".join(
        render_cross_board_nets_markdown(cross_board_net_section(project, declared))
    )
    assert "## 跨板网络（含已声明连接）" in text
    assert "1 条已声明跨板连接（显式工程师声明；仅披露，不合并网表）" in text
    assert "`aa1111` Board1 `5V_IN`" in text
    assert "`bb2222` Board2 `VSYS`" in text
    assert "declaredBy=engineer" in text
    assert "engineer-declared" in text
    assert "merged=false" in text
    assert "note=CN2 pin1-pin4 线束" in text
    # E0 的同名组照旧披露：声明没有把它升级，也没有把它删掉
    assert "`GND`" in text
    assert "E0 / welded-by-name / merged=false" in text


def test_an_empty_declaration_is_disclosed_as_zero_not_as_silence(project) -> None:
    empty = _parse(_payload([]), project)
    section = cross_board_net_section(project, empty)
    assert section["provenCount"] == 0
    assert section["proven"] == []
    assert "0 条已声明跨板连接（显式工程师声明；仅披露，不合并网表）" in section["note"]
    text = "\n".join(render_cross_board_nets_markdown(section))
    assert "## 跨板网络（含已声明连接）" in text
    assert "0 条已声明跨板连接" in text, "0 declared must be printed, not skipped"
    assert "已声明：" not in text, "no edge row when nothing was declared"


def test_without_a_declaration_the_section_is_exactly_the_old_one(project) -> None:
    """Byte-for-byte the S1 answer: same keys, same note, same Markdown lines."""
    section = cross_board_net_section(project)
    assert section == cross_board_net_section(project, None)
    assert set(section) == {"boards", "count", "nets", "nonAddressablePages", "note"}
    assert section["note"] == OLD_NOTE
    assert render_cross_board_nets_markdown(section) == [
        "## 跨板网络（未证明）",
        "",
        "- 板：`aa1111` Board1、`bb2222` Board2",
        f"- {OLD_NOTE}",
        "- `GND`：`aa1111` Board1、`bb2222` Board2 —— E0 / welded-by-name / merged=false",
        "",
    ]


def test_the_declaration_merges_and_upgrades_nothing(project, declared) -> None:
    before_edges = project.unproven_edges
    old = cross_board_net_section(project)
    section = cross_board_net_section(project, declared)
    assert project.unproven_edges == before_edges
    assert section["nets"] == old["nets"], "the E0 groups are not rewritten"
    assert section["count"] == old["count"]
    gnd = [row for row in section["nets"] if row["name"] == "GND"][0]
    assert gnd["evidenceLevel"] == "E0"
    assert gnd["reason"] == "welded-by-name"
    assert gnd["merged"] is False
    assert [instance["boardUuid"] for instance in gnd["instances"]] == [A, B]


def test_checkup_and_review_print_the_same_declaration(project, declared) -> None:
    section = cross_board_net_section(project, declared)
    checkup_text = "\n".join(render_cross_board_nets_markdown(section))
    review_text = review_engine.render_markdown(
        [], {"source": "in-memory", "cross_board_nets": section}
    )
    assert checkup_text in review_text
    assert "1 条已声明跨板连接（显式工程师声明；仅披露，不合并网表）" in review_text
    assert "declaredBy=engineer" in review_text
    assert "note=CN2 pin1-pin4 线束" in review_text


def test_declared_rows_keep_the_file_order(project) -> None:
    contract = _parse(
        _payload(
            [
                _edge((A, "5V_IN"), (B, "VSYS"), note="first"),
                _edge((A, "5V_IN"), (B, "VCC"), note="second"),
            ]
        ),
        project,
    )
    section = cross_board_net_section(project, contract)
    assert section["provenCount"] == 2
    assert [row["note"] for row in section["proven"]] == ["first", "second"]


def test_a_section_that_was_not_given_a_contract_is_refused(project) -> None:
    with pytest.raises(TypeError, match="InterconnectContract"):
        cross_board_net_section(project, {"edges": []})


# --------------------------------------------------------------------------
# 11. one uuid, two boards: the declaration is refused, never resolved
# --------------------------------------------------------------------------


def _same_uuid_project(*, shadow_first: bool) -> ProjectModel:
    """Two boards minted with **one** uuid and disagreeing netlists, plus ``B``.

    ``Board1`` carries ``5V_IN`` and the shadow does not: a first-board-wins
    lookup would resolve ``boardUuid: A`` to ``Board1`` and quietly accept the
    declaration below, while the shadow board's netlist says A has no ``5V_IN``
    at all. That accept is exactly what must not happen.
    """
    first = _board(A, "Board1", nets=("GND", "5V_IN"))
    shadow = _board(A, "Board1-shadow", nets=("GND", "VSYS"))
    other = _board(B, "Board2", nets=("GND", "VCC", "VSYS"))
    return _project(*(shadow, first, other) if shadow_first else (first, shadow, other))


@pytest.mark.parametrize("shadow_first", [False, True])
def test_a_repeated_board_uuid_is_refused_not_resolved(shadow_first: bool) -> None:
    model = _same_uuid_project(shadow_first=shadow_first)
    payload = _payload([_edge((A, "5V_IN"), (B, "VSYS"))])
    with pytest.raises(InterconnectError, match="same BOARD uuid") as caught:
        _parse(payload, model)
    assert A in str(caught.value)
    assert "Board1" in str(caught.value) and "Board1-shadow" in str(caught.value)


def test_a_repeated_uuid_does_not_get_through_as_zero_declarations() -> None:
    """The gate runs before ``edges`` is read: no duplicate ids, not even for ``[]``."""
    with pytest.raises(InterconnectError, match="same BOARD uuid"):
        _parse(_payload([]), _same_uuid_project(shadow_first=False))


def test_the_very_edge_first_board_wins_would_have_accepted_is_refused() -> None:
    """The control for the negative: without the duplicate, this edge *is* accepted."""
    payload = _payload([_edge((A, "5V_IN"), (B, "VSYS"))])
    accepted = _parse(
        payload,
        _project(
            _board(A, "Board1", nets=("GND", "5V_IN")),
            _board(B, "Board2", nets=("GND", "VCC", "VSYS")),
        ),
    )
    assert len(accepted.edges) == 1
    with pytest.raises(InterconnectError, match="same BOARD uuid"):
        _parse(payload, _same_uuid_project(shadow_first=False))

# --------------------------------------------------------------------------
# 10. the two CLI consumers (041 S2 §3): `--interconnect` on file reviews
# --------------------------------------------------------------------------
#
# Everything above pins the module and the section without a CLI. Here the flag
# is wired through `review` and `checkup --file` on the real three-board FOC
# fixture, because that is where the contract's hard parts live: the identity
# gate has no real `projectUuid` to match on a `.epro2`, the two reports must
# disclose the *same* reading, and a refusal must leave no report behind.
#
# The declared pair is picked from the model rather than written as a literal:
# the fixture's uuids and net names are what they are, and a test that hard-coded
# them would start passing for the wrong reason the day the fixture changes.

FIXTURES = Path(__file__).parent / "fixtures"
FOC = FIXTURES / "ProPrj_毕设FOC驱动板_2026-09-17.epro2"
MOTOR = FIXTURES / "ProPrj_高速电机控制器_2026-09-16.epro2"
GOLDEN = FIXTURES / "ch340_golden.epro2"

#: The two numbers this fixture measured before S2 (S1 froze them): the review's
#: 45 rows / 30-1-14 and checkup's **239** rows / 50-20-169 with `incomplete`. A
#: declaration is disclosure only, so not one of them may move.
#:
#: 241 / 50-21-170 was S1's reading and is **no longer** the fixture's: 529 put
#: the mid-distance decoupling band in (2.2 µF / 4.7 µF count as mid-range caps
#: now), so one `decap-required-caps` WARN and the INFO that carried it left the
#: run — 239 = 50 E + 20 W + 169 I. That move belongs to 529's rule change, and
#: S2's own claim is narrower: the declaration neither adds a row nor moves one,
#: which is why the review reading (30/1/14) is untouched.
REVIEW_SUMMARY = {"ERROR": 30, "WARN": 1, "INFO": 14}
CHECKUP_COUNTS = (50, 20, 169)

#: The two-board fixture's review reading, frozen by S1 in
#: `test_041_cross_board_nets.py` (22 ERROR / 1 WARN / 48 INFO = 71 rows). Its
#: checkup numbers are *not* written down here: only the declaration path is new,
#: and the test compares the two checkup runs instead of guessing a constant.
REVIEW_MOTOR_SUMMARY = {"ERROR": 22, "WARN": 1, "INFO": 48}


@pytest.fixture(scope="module")
def foc_model():  # noqa: ANN201 — the parser's own ProjectModel
    from boardwise.parsers.schematic import build_project_model

    return build_project_model(FOC)


@pytest.fixture(scope="module")
def motor_model():  # noqa: ANN201 — the parser's own ProjectModel
    from boardwise.parsers.schematic import build_project_model

    return build_project_model(MOTOR)


def _pair_with_distinct_names(model):  # noqa: ANN001, ANN202
    """Two boards that each own at least one net name the other does not."""
    boards = list(model.boards)
    for first, second in itertools.combinations(boards, 2):
        left = sorted(set(first.nets) - set(second.nets))
        right = sorted(set(second.nets) - set(first.nets))
        if left and right:
            return first, left[0], second, right[0]
    raise AssertionError("the fixture is expected to hold two boards with names of their own")


def _pair_with_a_shared_name(model):  # noqa: ANN001, ANN202
    """Two boards whose net lists already share a name (the E0 ``GND`` group)."""
    boards = list(model.boards)
    for first, second in itertools.combinations(boards, 2):
        shared = sorted(set(first.nets) & set(second.nets))
        if shared:
            return first, shared[0], second
    raise AssertionError("the fixture is expected to share at least one net name")


def _declaration(path: Path, edges: list[dict], **extra: object) -> Path:
    payload: dict[str, object] = {
        "interconnectVersion": INTERCONNECT_VERSION,
        "edges": edges,
    }
    payload.update(extra)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _end_of(board_uuid: str, net: str) -> dict[str, str]:
    return {"boardUuid": board_uuid, "net": net}


def _section_text(markdown: str) -> str:
    """One report's cross-board section, heading included, up to the next section."""
    start = markdown.index("## 跨板网络")
    end = markdown.find("\n## ", start + 1)
    return markdown[start:] if end == -1 else markdown[start:end]


def test_a_declared_tie_reaches_both_reports_and_moves_no_number(tmp_path, foc_model):
    """Requirement 1: one declaration, two products, the same reading.

    ``checkup --file`` keeps its exit 1, its 239 findings and its 50/20/169 with
    ``completion.verdict == incomplete``; ``review`` keeps its exit 1 and its 45
    findings with 30/1/14. What is *added* is ``provenCount: 1`` and one row
    naming both real ends — in `report.json`, in `report.md` and in
    `review --md`, while `review --json` grows no field at all.
    """
    from boardwise import cli

    first, first_net, second, second_net = _pair_with_distinct_names(foc_model)
    note = "CN2 pin1-pin4 线束"
    decl = _declaration(
        tmp_path / "declaration.json",
        [
            {
                "from": _end_of(first.board.uuid, first_net),
                "to": _end_of(second.board.uuid, second_net),
                "declaredBy": DECLARED_BY_ENGINEER,
                "note": note,
            }
        ],
    )

    out = tmp_path / "checkup"
    assert cli.main(
        ["checkup", "--file", str(FOC), "--interconnect", str(decl), "--out", str(out)]
    ) == 1, "exit 1 = ERROR findings present, measured on this fixture before S2"

    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert len(report["findings"]) == 239, "041 adds a channel, not findings"
    summary = report["summary"]
    assert (summary["errorCount"], summary["warnCount"], summary["infoCount"]) == (
        CHECKUP_COUNTS
    )
    assert report["completion"]["verdict"] == "incomplete", (
        "the gate's word is the pre-S2 reading; a declaration is not evidence "
        "enough to move it"
    )

    section = report["source"]["crossBoardNets"]
    assert section["count"] == 39, "the model's own 39 shared names are unchanged"
    assert section["provenCount"] == 1
    (row,) = section["proven"]
    assert row["from"] == {
        "boardUuid": first.board.uuid,
        "boardTitle": first.board.title,
        "netName": first_net,
    }
    assert row["to"] == {
        "boardUuid": second.board.uuid,
        "boardTitle": second.board.title,
        "netName": second_net,
    }
    assert row["declaredBy"] == DECLARED_BY_ENGINEER
    assert row["note"] == note, "the engineer's note is quoted verbatim"
    assert row["evidenceLevel"] == "engineer-declared"
    assert row["merged"] is False, "a declared tie is disclosed, never welded"

    markdown = (out / "report.md").read_text(encoding="utf-8")
    assert "## 跨板网络（含已声明连接）" in markdown
    assert "1 条已声明跨板连接" in markdown
    assert note in markdown

    md, js = tmp_path / "review.md", tmp_path / "review.json"
    assert cli.main([
        "review", str(FOC), "--md", str(md), "--json", str(js),
        "--interconnect", str(decl),
    ]) == 1
    payload = json.loads(js.read_text(encoding="utf-8"))
    assert set(payload) == {"findings", "summary"}, (
        "review --json is still the findings array — the declaration is not a field"
    )
    assert payload["summary"] == REVIEW_SUMMARY
    assert len(payload["findings"]) == 45

    review_md = md.read_text(encoding="utf-8")
    assert _section_text(review_md) == _section_text(markdown), (
        "one renderer, two reports: the disclosed section must be identical"
    )


def test_real_two_board_declaration_preserves_both_report_baselines(tmp_path, motor_model):
    """The same contract on the real two-board fixture, where every group is a pair.

    The FOC project is three boards, so its section mixes 34 pairs with 5 triples.
    This one is the pure pair case (2 boards, 156 instances, 38 shared names, 38
    unproven edges), and the declared pair is read out of the model — never a
    literal uuid or net name — so a changed fixture cannot pass by coincidence.

    What must hold: `review --json` is **byte-identical** with and without the
    declaration (it is still the findings array, no field, no row), both commands
    keep their exit code, checkup's `findings`/`summary`/`completion`/
    `warning_triage` are equal run-to-run, and the declared reading adds one
    `proven` row *beside* the 38 E0 groups without moving, merging or deleting
    one of them. The two Markdown reports print that section verbatim.
    """
    from boardwise import cli

    first, first_net, second, second_net = _pair_with_distinct_names(motor_model)
    note = "CN2 pin1-pin4 线束"
    decl = _declaration(
        tmp_path / "declaration.json",
        [
            {
                "from": _end_of(first.board.uuid, first_net),
                "to": _end_of(second.board.uuid, second_net),
                "declaredBy": DECLARED_BY_ENGINEER,
                "note": note,
            }
        ],
    )

    plain_json, declared_json = tmp_path / "plain.json", tmp_path / "declared.json"
    plain_rc = cli.main(["review", str(MOTOR), "--json", str(plain_json)])
    review_md = tmp_path / "review.md"
    declared_rc = cli.main([
        "review", str(MOTOR), "--md", str(review_md), "--json", str(declared_json),
        "--interconnect", str(decl),
    ])
    assert plain_rc == declared_rc == 1, "ERROR findings present either way"
    assert declared_json.read_bytes() == plain_json.read_bytes(), (
        "review --json is still the findings array: a declaration adds no field "
        "and no row, so the two runs must agree byte for byte"
    )
    payload = json.loads(declared_json.read_text(encoding="utf-8"))
    assert set(payload) == {"findings", "summary"}
    assert payload["summary"] == REVIEW_MOTOR_SUMMARY
    assert len(payload["findings"]) == 71, "22 + 1 + 48, the pre-S2 row count"

    declared_rows = [
        line
        for line in _section_text(review_md.read_text(encoding="utf-8")).splitlines()
        if line.startswith("- 已声明：")
    ]
    assert len(declared_rows) == 1, "one declared tie, one row"
    (declared_row,) = declared_rows
    for piece in (
        first.board.uuid[-6:], second.board.uuid[-6:],
        first.board.title, second.board.title,
        f"`{first_net}`", f"`{second_net}`", note,
    ):
        assert piece in declared_row, piece

    out_plain = tmp_path / "checkup-plain"
    out_declared = tmp_path / "checkup-declared"
    assert cli.main(
        ["checkup", "--file", str(MOTOR), "--out", str(out_plain)]
    ) == plain_rc
    assert cli.main([
        "checkup", "--file", str(MOTOR), "--interconnect", str(decl),
        "--out", str(out_declared),
    ]) == declared_rc, "a declaration is disclosure, not a re-measurement"

    plain = json.loads((out_plain / "report.json").read_text(encoding="utf-8"))
    declared = json.loads((out_declared / "report.json").read_text(encoding="utf-8"))
    for key in ("findings", "summary", "completion", "warning_triage"):
        assert declared[key] == plain[key], key

    plain_section = plain["source"]["crossBoardNets"]
    assert "proven" not in plain_section and "provenCount" not in plain_section, (
        "the no-argument path keeps S1's key set exactly"
    )
    assert plain_section["count"] == 38, "two boards: one group per shared name"

    section = declared["source"]["crossBoardNets"]
    assert section["count"] == 38
    assert section["nets"] == plain_section["nets"], (
        "not one E0 group moved, merged or disappeared"
    )
    assert section["boards"] == plain_section["boards"]
    assert section["provenCount"] == 1
    (row,) = section["proven"]
    assert row["from"] == {
        "boardUuid": first.board.uuid,
        "boardTitle": first.board.title,
        "netName": first_net,
    }
    assert row["to"] == {
        "boardUuid": second.board.uuid,
        "boardTitle": second.board.title,
        "netName": second_net,
    }
    assert row["declaredBy"] == DECLARED_BY_ENGINEER
    assert row["note"] == note
    assert row["evidenceLevel"] == "engineer-declared"
    assert row["merged"] is False
    for net in section["nets"]:
        assert net["evidenceLevel"] == "E0", net["name"]
        assert net["merged"] is False, net["name"]

    checkup_md = (out_declared / "report.md").read_text(encoding="utf-8")
    assert _section_text(checkup_md) == _section_text(
        review_md.read_text(encoding="utf-8")
    ), "one renderer, two reports: the disclosed section cannot drift"


def test_a_declared_same_name_group_upgrades_only_the_named_endpoints(tmp_path, foc_model):
    """Requirement 2: declaring ``GND@A <-> GND@B`` proves that pair and nothing else.

    The other 38 same-named groups keep their E0 / welded-by-name / merged=false
    reading, and the group the declaration names stays in that list too: the
    declaration is added beside it, not written over or deleted from it.
    """
    from boardwise import cli

    first, shared, second = _pair_with_a_shared_name(foc_model)
    decl = _declaration(
        tmp_path / "same-name.json",
        [
            {
                "from": _end_of(first.board.uuid, shared),
                "to": _end_of(second.board.uuid, shared),
                "declaredBy": DECLARED_BY_ENGINEER,
            }
        ],
    )
    out = tmp_path / "checkup"
    assert cli.main(
        ["checkup", "--file", str(FOC), "--interconnect", str(decl), "--out", str(out)]
    ) == 1

    section = json.loads((out / "report.json").read_text(encoding="utf-8"))[
        "source"
    ]["crossBoardNets"]
    assert section["count"] == 39, "no group was merged away or added"
    assert section["provenCount"] == 1
    (row,) = section["proven"]
    assert row["from"]["netName"] == shared and row["to"]["netName"] == shared
    assert row["from"]["boardUuid"] != row["to"]["boardUuid"]
    assert row["note"] == "", "an omitted note is the empty string, not missing"

    declared_group = [net for net in section["nets"] if net["name"] == shared]
    assert declared_group, "the same-named group the declaration names is still listed"
    group = declared_group[0]
    assert group["evidenceLevel"] == "E0" and group["reason"] == "welded-by-name"
    assert group["merged"] is False
    assert {end["boardUuid"] for end in group["instances"]} >= {
        first.board.uuid, second.board.uuid,
    }, "the group still names both instances — the declaration proves *a* pair"
    for net in section["nets"]:
        assert net["evidenceLevel"] == "E0", net["name"]
        assert net["merged"] is False, net["name"]
    assert section["provenCount"] == 1, "39 groups do not each become a proven tie"


def test_a_bad_declaration_is_refused_before_any_report_is_written(tmp_path, foc_model, capsys):
    """Requirement 3: a failed read never degrades into "0 declared ties".

    A missing file, broken JSON and a `projectUuid` pinned against a container
    with no real identity (a `.epro2`) all exit 2 — and neither the review's
    `--md`/`--json` nor checkup's `report.json`/`report.md` appears. An explicit
    ``[]`` on the same project *is* a successful zero, disclosed as such.
    """
    from boardwise import cli

    missing = tmp_path / "missing.json"
    broken = tmp_path / "broken.json"
    broken.write_text("{not json at all", encoding="utf-8")
    # A `.epro2` carries no project uuid (`_snapshot_identity` measures that), so
    # a file that pins one can only be refused — a file-name digest is not an id.
    pinned = _declaration(
        tmp_path / "pinned.json", [], projectUuid="d5c055266ef55000"
    )
    out = tmp_path / "checkup"
    assert cli.main(
        ["checkup", "--file", str(FOC), "--interconnect", str(missing), "--out", str(out)]
    ) == 2
    assert not (out / "report.json").exists()
    assert not (out / "report.md").exists()

    md, js = tmp_path / "review.md", tmp_path / "review.json"
    for bad in (missing, broken, pinned):
        assert cli.main([
            "review", str(FOC), "--md", str(md), "--json", str(js),
            "--interconnect", str(bad),
        ]) == 2, bad.name
        assert not md.exists(), (bad.name, "no Markdown report for a refused run")
        assert not js.exists(), (bad.name, "no JSON report for a refused run")

    captured = capsys.readouterr()
    assert "已声明跨板连接" not in captured.out, (
        "a refused declaration must not be spoken of as zero declared ties"
    )
    assert "Traceback" not in captured.err

    empty = _declaration(tmp_path / "empty.json", [])
    out2 = tmp_path / "checkup-empty"
    assert cli.main(
        ["checkup", "--file", str(FOC), "--interconnect", str(empty), "--out", str(out2)]
    ) == 1
    section = json.loads((out2 / "report.json").read_text(encoding="utf-8"))[
        "source"
    ]["crossBoardNets"]
    assert section["provenCount"] == 0
    assert section["proven"] == []
    assert "0 条已声明跨板连接" in (out2 / "report.md").read_text(encoding="utf-8")


def test_the_flag_is_refused_wherever_there_is_no_board_list(tmp_path, monkeypatch, foc_model):
    """Requirement 4: live, PCB view, finalize, online checkup and one board.

    The online refusals are decided **before** anything is read: the loader is
    replaced by a tripwire, and `--out` (with its lock carrier) is never created.
    """
    from boardwise import cli

    first, first_net, second, second_net = _pair_with_distinct_names(foc_model)
    decl = _declaration(
        tmp_path / "declaration.json",
        [{
            "from": _end_of(first.board.uuid, first_net),
            "to": _end_of(second.board.uuid, second_net),
            "declaredBy": DECLARED_BY_ENGINEER,
        }],
    )
    online_calls: list[str] = []
    monkeypatch.setattr(
        cli, "_load_model_online",
        lambda *a, **k: online_calls.append("online"),
    )

    assert cli.main(["review", "--live", "--interconnect", str(decl)]) == 2
    assert cli.main([
        "review", str(FOC), "--view", "pcb", "--interconnect", str(decl),
    ]) == 2
    assert cli.main([
        "review", "finalize", "--out", str(tmp_path / "out"),
        "--interconnect", str(decl),
    ]) == 2, "finalize refuses it instead of ignoring it"

    online_out = tmp_path / "checkup-online"
    assert cli.main([
        "checkup", "--interconnect", str(decl), "--out", str(online_out),
    ]) == 2
    assert not online_out.exists(), (
        "the online refusal runs in the preflight: no --out, no .checkup.lock"
    )
    assert online_calls == [], "no refusal above may reach the online loader"

    single_out = tmp_path / "checkup-single"
    assert cli.main([
        "checkup", "--file", str(GOLDEN), "--interconnect", str(decl),
        "--out", str(single_out),
    ]) == 2, "one board has no cross-board endpoint to declare"
    assert not (single_out / "report.json").exists()

    single_md = tmp_path / "single.md"
    assert cli.main([
        "review", str(GOLDEN), "--md", str(single_md), "--interconnect", str(decl),
    ]) == 2, "the review refuses a one-board project for the same reason"
    assert not single_md.exists()

# --------------------------------------------------------------------------
# 11. the audit's two holes: an empty path is not "no path", and a blank BOARD
#     uuid must not escape as the model's own `ValueError`
# --------------------------------------------------------------------------


def _empty_flag_argv(command: str, tmp_path: Path) -> list[str]:
    """The three online/one-board-free shapes, each with an **empty** path."""
    if command == "review-live":
        return ["review", "--live", "--interconnect", ""]
    if command == "review-finalize":
        return ["review", "finalize", "--out", str(tmp_path / "out"), "--interconnect", ""]
    if command == "checkup-online":
        return ["checkup", "--interconnect", "", "--out", str(tmp_path / "online")]
    raise AssertionError(command)


@pytest.mark.parametrize(
    "command", ["review-live", "review-finalize", "checkup-online"]
)
def test_an_explicitly_empty_path_is_refused_where_the_flag_is_refused(
    command: str, tmp_path: Path, monkeypatch
) -> None:
    """`--interconnect ""` is a *given* flag, so the refusal cannot be a truth test.

    The parser's default is ``None``; the gate is ``is not None``. The tripwire
    proves the online loader is never reached, and `--out` (with its lock
    carrier) is never created.
    """
    from boardwise import cli

    calls: list[str] = []
    monkeypatch.setattr(
        cli, "_load_model_online", lambda *a, **k: calls.append("online")
    )
    assert cli.main(_empty_flag_argv(command, tmp_path)) == 2
    assert calls == [], "a refused invocation must not reach the online loader"
    assert not (tmp_path / "online").exists()
    assert not (tmp_path / "out").exists()


def test_an_explicitly_empty_path_is_refused_offline_before_any_report(tmp_path):
    """Offline it is the reader that refuses it — and still nothing is written.

    The path is `""`, which is a directory-less, file-less location: the reader
    answers "not found", not "zero declared ties".
    """
    from boardwise import cli

    md, js = tmp_path / "review.md", tmp_path / "review.json"
    assert cli.main([
        "review", str(FOC), "--md", str(md), "--json", str(js), "--interconnect", "",
    ]) == 2
    assert not md.exists() and not js.exists()


def test_the_parser_default_is_none_so_no_argument_keeps_the_old_call(tmp_path):
    """`review <file>` without the flag still means "no declaration was given"."""
    from boardwise import cli

    args = cli.build_parser().parse_args(["review", "board.epro2"])
    assert args.interconnect is None
    checkup_args = cli.build_parser().parse_args(["checkup", "--file", "board.epro2"])
    assert checkup_args.interconnect is None
    given = cli.build_parser().parse_args(["review", "board.epro2", "--interconnect", ""])
    assert given.interconnect == "", "an empty path is a value, not an absence"


@pytest.mark.parametrize("bad_uuid", ["", "   ", "\t\n", "  aaaa1111  "])
def test_a_blank_board_uuid_is_not_addressable_and_never_escapes_as_a_bare_value_error(
    bad_uuid: str,
) -> None:
    """A blank uuid is skipped, not looked up: the model raises its own `ValueError`.

    The control is the last case: a uuid with surrounding spaces is **not** blank,
    so it stays addressable as-is and the file's `"aaaa1111"` simply does not
    match it — verbatim comparison, no trimming on either side.
    """
    payload = _payload([_edge((A, "5V_IN"), (B, "VSYS"))])
    project = _project(
        _board(bad_uuid, "Board1", nets=("GND", "5V_IN")),
        _board(B, "Board2", nets=("GND", "VSYS")),
    )
    with pytest.raises(InterconnectError) as raised:
        _parse(payload, project)
    assert type(raised.value) is InterconnectError, (
        "the model's own ValueError (a NetInstance built from a blank uuid) must "
        "not be what reaches the caller"
    )
    if bad_uuid.strip():
        assert "no addressable BOARD has uuid" in str(raised.value)
    else:
        assert "at least two addressable boards" in str(raised.value)


def test_a_blank_uuid_does_not_disturb_the_two_real_boards() -> None:
    """The control: one blank board alongside two real ones changes nothing."""
    payload = _payload([_edge((A, "5V_IN"), (B, "VSYS"))])
    accepted = _parse(
        payload,
        _project(
            _board("   ", "shadow", nets=("GND",)),
            _board(A, "Board1", nets=("GND", "5V_IN")),
            _board(B, "Board2", nets=("GND", "VSYS")),
        ),
    )
    assert len(accepted.edges) == 1
