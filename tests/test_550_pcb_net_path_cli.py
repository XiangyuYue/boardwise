"""550 CLI — `boardwise pcb net-path` is an archive reader with three verdicts.

What this file pins is the **adapter**, not the judgement: the judgement lives in
``core/netpath.py`` and its own test file owns it. So every assertion here is
about one of the four things the assembly layer can get wrong:

* **the container**: only ``.epro2`` and ``.eprj3`` are read; KiCad, a lone
  ``.epcb2``, an ``.eprj2`` and a folder without its index are refused *by name*,
  so the review runner's wider container support cannot quietly widen this
  command;
* **the board**: several boards without ``--board`` is a refusal (never 「the
  first one」), a name that matches nothing or two boards is a refusal, and a
  title or board uuid selects exactly one;
* **the exit code**: 0 CONNECTED, 2 NOT_PROVEN, 3 INDETERMINATE or any refusal —
  while argparse keeps its own 2 for a usage error, which is what makes
  ``--through``/``--layer``/``--json``/``--project`` refusals instead of silent
  no-ops;
* **the invariants**: stdout is one JSON document with every contract array
  present, the same input twice is byte-identical, ``pcb gate`` is untouched,
  and nothing is written anywhere.

The two real fixtures are read-only anonymous samples already in ``tests/
fixtures``; the folder project is synthetic because a real multi-board ``.eprj3``
is not public.
"""

from __future__ import annotations

import io
import json
import shutil
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.commands import assembly as assembly_commands

FIXTURES = Path(__file__).resolve().parent / "fixtures"
# `llc_board.epro2` is the single-board ASCII-named sample: CN3.1 → U9.2 is a
# real walked path, C7.1 → C8.1 is the same net with no supported copper
# between them, and CN3.1 → CN3.1 is the degenerate same-pad query.
LLC = FIXTURES / "llc_board.epro2"
# Two boards in one archive: the N8 case needs a container that really holds
# several, and `PCB2`/`PCB1` are the titles the review runner reports for it.
TWO_BOARDS = FIXTURES / "DCDC-12V9V转5V3V3_2026-09-27.epro2"


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def _payload(argv: list[str]) -> tuple[int, dict]:
    code, out, _err = _run(argv)
    return code, json.loads(out)


# ---------------------------------------------------------------------------
# the three verdicts, on a real read-only archive
# ---------------------------------------------------------------------------
def test_connected_pad_pair_exits_zero_with_walked_path() -> None:
    code, report = _payload(
        ["pcb", "net-path", str(LLC), "--from", "CN3.1", "--to", "U9.2"]
    )
    assert code == 0
    assert report["schema"] == "boardwise.pcbNetPath/1"
    assert report["verdict"] == "CONNECTED"
    # A walked path, not a netlist claim: it starts and ends on the queried pads
    # and every hop carries an id/kind/layers.
    assert report["path"][0]["kind"] == "pad"
    assert report["path"][-1]["kind"] == "pad"
    assert {row["kind"] for row in report["path"]} <= {"pad", "track", "via"}
    assert all("id" in row and "layers" in row for row in report["path"])
    tracks = [row for row in report["path"] if row["kind"] == "track"]
    assert tracks, "the walked path must contain the copper that joins the pads"
    assert all({"width", "start", "end"} <= set(row) for row in tracks)
    assert report["hopCount"] == len(report["path"]) - 1


def test_not_proven_same_net_pair_exits_two_and_never_says_open_circuit() -> None:
    code, report = _payload(
        ["pcb", "net-path", str(LLC), "--from", "C7.1", "--to", "C8.1"]
    )
    assert code == 2
    assert report["verdict"] == "NOT_PROVEN"
    assert report["path"] == []
    # The negative answer must be scoped: pour/PLANE/ARC are outside the graph,
    # and they were excluded by decision rather than found to be absent.
    assert "pour" in json.dumps(report["scope"]).lower()
    assert report["ignored"], "an excluded-by-decision list must be disclosed"


def test_same_pad_is_indeterminate_not_a_zero_hop_pass() -> None:
    code, report = _payload(
        ["pcb", "net-path", str(LLC), "--from", "CN3.1", "--to", "CN3.1"]
    )
    assert code == 3
    assert report["verdict"] == "INDETERMINATE"
    assert report["path"] == []
    assert {"same_pad"} <= {row["code"] for row in report["errors"]}


def test_every_contract_array_is_present_even_when_empty() -> None:
    _code, report = _payload(
        ["pcb", "net-path", str(LLC), "--from", "CN3.1", "--to", "U9.2"]
    )
    for key in ("unknown", "ignored", "errors"):
        assert isinstance(report[key], list), key
    for key in ("viaCount", "coverage", "source", "query", "scope"):
        assert key in report, key
    assert report["source"]["container"] == ".epro2"
    assert report["source"]["boardCount"] == 1
    assert report["source"]["title"] == "PCB1"
    assert (report["query"]["from"]["ref"], report["query"]["from"]["pad"]) == ("CN3", "1")


def test_a_malformed_reference_is_indeterminate_with_bad_ref() -> None:
    code, report = _payload(["pcb", "net-path", str(LLC), "--from", "C7", "--to", "C8.1"])
    assert code == 3
    assert report["verdict"] == "INDETERMINATE"
    assert {"bad_ref"} <= {row["code"] for row in report["errors"]}


def test_same_input_twice_is_byte_identical() -> None:
    argv = ["pcb", "net-path", str(LLC), "--from", "CN3.1", "--to", "U9.2"]
    first, second = _run(argv), _run(argv)
    assert first[0] == second[0] == 0
    assert first[1] == second[1]


# ---------------------------------------------------------------------------
# N4/N5: the flags this batch does not have are refused, not ignored
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "flag",
    [
        ["--through", "U9.1"],
        ["--layer", "1"],
        ["--json"],
        ["--project", "anything"],
    ],
)
def test_unexposed_flags_are_argparse_usage_errors(flag: list[str]) -> None:
    argv = ["pcb", "net-path", str(LLC), "--from", "CN3.1", "--to", "U9.2", *flag]
    with pytest.raises(SystemExit) as excinfo:
        _run(argv)
    # 2 is argparse's own usage code — the refusal happens before any read, and
    # the contract keeps that code for a usage error rather than 3.
    assert excinfo.value.code == 2


def test_the_command_has_no_through_layer_json_or_project_options() -> None:
    parser = cli.build_parser()
    # Walk the subparser table instead of grepping help text: a flag added
    # later without a decision here would have to be visible in this set.
    pcb = None
    for action in parser._actions:  # noqa: SLF001 - argparse has no public walk
        if getattr(action, "choices", None) and "pcb" in action.choices:
            pcb = action.choices["pcb"]
    assert pcb is not None
    net_path = None
    for action in pcb._actions:  # noqa: SLF001
        if getattr(action, "choices", None) and "net-path" in action.choices:
            net_path = action.choices["net-path"]
    assert net_path is not None
    options = {
        option
        for action in net_path._actions  # noqa: SLF001
        for option in action.option_strings
    }
    assert options == {"-h", "--help", "--from", "--to", "--board"}


# ---------------------------------------------------------------------------
# N8 and the board identity: never 「the first board」
# ---------------------------------------------------------------------------
def test_multi_board_container_without_board_is_refused_before_any_read() -> None:
    code, out, err = _run(
        ["pcb", "net-path", str(TWO_BOARDS), "--from", "CN1.1", "--to", "U1.1"]
    )
    assert code == 3
    # 550's minimal output contract: a front-end refusal is stderr + empty stdout,
    # never a fabricated verdict the caller could mistake for a completed query.
    assert out == ""
    assert "verdict" not in err
    assert "--board" in err
    assert "PCB2" in err and "PCB1" in err
    assert "first board" in err


def test_multi_board_container_selects_by_title() -> None:
    code, report = _payload(
        [
            "pcb", "net-path", str(TWO_BOARDS),
            "--from", "CN1.1", "--to", "U1.1", "--board", "PCB2",
        ]
    )
    assert code == 0
    assert report["source"]["boardCount"] == 2
    assert report["source"]["title"] == "PCB2"


def test_multi_board_container_selects_by_board_uuid() -> None:
    code, report = _payload(
        [
            "pcb", "net-path", str(TWO_BOARDS),
            "--from", "CN1.1", "--to", "U1.1", "--board", "58a7a8743965dadb",
        ]
    )
    assert code == 0
    assert report["source"]["title"] == "PCB2"
    assert report["source"]["uuid"] == "58a7a8743965dadb"


def test_board_name_that_matches_nothing_is_refused_with_the_choices() -> None:
    code, err = _run(
        [
            "pcb", "net-path", str(TWO_BOARDS),
            "--from", "CN1.1", "--to", "U1.1", "--board", "NOT_A_BOARD",
        ]
    )[0::2]
    assert code == 3
    assert "matches no board" in err
    assert "PCB2" in err


def test_a_single_board_container_needs_no_board_flag() -> None:
    code, report = _payload(
        ["pcb", "net-path", str(LLC), "--from", "CN3.1", "--to", "U9.2"]
    )
    assert code == 0
    assert report["source"]["boardCount"] == 1


def test_board_flag_that_is_wrong_on_a_single_board_is_still_refused() -> None:
    code, err = _run(
        ["pcb", "net-path", str(LLC), "--from", "CN3.1", "--to", "U9.2", "--board", "PCB2"]
    )[0::2]
    assert code == 3
    assert "matches no board" in err


# ---------------------------------------------------------------------------
# the container: two formats in, everything else refused by name
# ---------------------------------------------------------------------------
def test_other_containers_are_refused_by_name(tmp_path: Path) -> None:
    # The files exist on purpose: a missing file would be refused for the wrong
    # reason (no such path), and the point here is that a *readable* KiCad board
    # is still outside this batch even though the review runner can read it.
    for name, reason in (
        ("board.kicad_pcb", "KiCad"),
        ("board.epcb2", ".epcb2"),
        ("proj.eprj2", ".epro2"),
    ):
        target = tmp_path / name
        target.write_text("", encoding="utf-8")
        code, err = _run(["pcb", "net-path", str(target), "--from", "A.1", "--to", "A.2"])[0::2]
        assert code == 3, name
        assert reason in err, (name, err)
        # A refusal that names the container must not also answer the question.
        assert "verdict" not in err


def test_missing_file_is_refused_without_a_traceback() -> None:
    code, err = _run(["pcb", "net-path", str(FIXTURES / "nope.epro2"), "--from", "A.1", "--to", "A.2"])[0::2]
    assert code == 3
    assert "does not exist" in err
    assert "Traceback" not in err


# ---------------------------------------------------------------------------
# synthetic .eprj3: the folder container reaches the same adapter
# ---------------------------------------------------------------------------
def _record(envelope: dict, body: dict | None = None) -> str:
    head = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    if body is None:
        return head + "|||"
    return (
        head
        + "||"
        + json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        + "|"
    )


def _pcb_stream(*, uuid: str, title: str) -> str:
    """One board document: header, title, canvas, one placed part, one ATTR."""
    lines = [
        _record({"type": "DOCHEAD"}, {"docType": "PCB", "uuid": uuid, "editVersion": "4.1.60"}),
        _record({"type": "META", "id": "META"}, {"title": title, "docType": 3}),
        _record(
            {"type": "CANVAS", "id": "CANVAS"},
            {"originX": 0, "originY": 1000.0, "yAxisDirection": "up"},
        ),
        _record(
            {"type": "COMPONENT", "id": "part-u1"},
            {"partId": "part-u1", "x": 10.0, "y": 20.0, "rotation": 0, "zIndex": 1},
        ),
        _record(
            {"type": "ATTR", "id": "attr-u1"},
            {"parentId": "part-u1", "key": "Designator", "value": "U1"},
        ),
    ]
    return "\n".join(lines) + "\n"


def _write_folder_project(root: Path, *, boards: dict[str, str], titles: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    index: dict = {
        "name": root.name,
        "owner_uuid": "0123456789abcdef0123456789abcdef",
        "format": "folder",
        "profile": {
            "schematics": {},
            "sheets": {},
            "pcbs": {
                uuid: {"uuid": uuid, "title": title} for uuid, title in titles.items()
            },
        },
    }
    (root / f"{root.name}.eprj3").write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8"
    )
    for relative, text in boards.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def test_synthetic_folder_project_reaches_the_same_adapter(tmp_path: Path) -> None:
    project = _write_folder_project(
        tmp_path / "proj",
        boards={"pcb/PCB1.epcb2": _pcb_stream(uuid="pcb-1", title="PCB1")},
        titles={"pcb-1": "PCB1"},
    )
    # The synthetic board carries no pads, so the query cannot resolve — but it
    # is answered (exit 3, INDETERMINATE) rather than refused as a container,
    # which is what proves the folder went through the same reader chain.
    code, report = _payload(["pcb", "net-path", str(project), "--from", "U1.1", "--to", "U1.2"])
    assert code == 3
    assert report["verdict"] == "INDETERMINATE"
    assert report["source"]["container"] == ".eprj3"
    assert report["source"]["boardCount"] == 1
    assert report["source"]["title"] == "PCB1"
    # A folder project's boards carry no schematic-board link, so the runner
    # reports an empty uuid — the title is the whole identity here.
    assert report["source"]["uuid"] is None


def test_the_index_file_form_is_the_same_eprj3_container(tmp_path: Path) -> None:
    # `looks_like_eprj3` reads a `.eprj3` **file** by its own path, so pointing
    # the command at the index instead of its folder must answer the same
    # question *and* label the container `.eprj3`. Labelling it `.epro2` would
    # name a container this run never read.
    project = _write_folder_project(
        tmp_path / "proj",
        boards={"pcb/PCB1.epcb2": _pcb_stream(uuid="pcb-1", title="PCB1")},
        titles={"pcb-1": "PCB1"},
    )
    index_file = project / f"{project.name}.eprj3"

    code, report = _payload(
        ["pcb", "net-path", str(index_file), "--from", "U1.1", "--to", "U1.2"]
    )
    assert code == 3
    assert report["verdict"] == "INDETERMINATE"
    assert report["source"]["container"] == ".eprj3"
    assert report["source"]["boardCount"] == 1
    assert report["source"]["title"] == "PCB1"

    # Same container, same answer: the folder and its index are one input. Only
    # `path` differs, because it echoes the argument the caller actually gave.
    folder_code, folder_report = _payload(
        ["pcb", "net-path", str(project), "--from", "U1.1", "--to", "U1.2"]
    )
    assert folder_code == code
    assert folder_report["verdict"] == report["verdict"]
    assert {
        key: value for key, value in folder_report["source"].items() if key != "path"
    } == {key: value for key, value in report["source"].items() if key != "path"}
    assert report["source"]["path"] == str(index_file)


def test_synthetic_folder_project_with_two_boards_requires_board(tmp_path: Path) -> None:
    project = _write_folder_project(
        tmp_path / "multi",
        boards={
            "pcb/PCB1.epcb2": _pcb_stream(uuid="pcb-1", title="PCB1"),
            "pcb/PCB2.epcb2": _pcb_stream(uuid="pcb-2", title="PCB2"),
        },
        titles={"pcb-1": "PCB1", "pcb-2": "PCB2"},
    )
    code, err = _run(["pcb", "net-path", str(project), "--from", "U1.1", "--to", "U1.2"])[0::2]
    assert code == 3
    assert "PCB1" in err and "PCB2" in err and "first board" in err

    code, report = _payload(
        ["pcb", "net-path", str(project), "--from", "U1.1", "--to", "U1.2", "--board", "PCB2"]
    )
    assert code == 3  # no pads on the synthetic board, but the board was chosen
    assert report["source"]["boardCount"] == 2
    assert report["source"]["title"] == "PCB2"


def test_a_folder_without_its_index_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "noindex"
    folder.mkdir()
    (folder / "stray.epcb2").write_text("", encoding="utf-8")
    code, err = _run(["pcb", "net-path", str(folder), "--from", "A.1", "--to", "A.2"])[0::2]
    assert code == 3
    assert ".eprj3" in err


def test_duplicate_titles_are_an_ambiguous_refusal(tmp_path: Path) -> None:
    project = _write_folder_project(
        tmp_path / "dup",
        boards={
            "pcb/PCB1.epcb2": _pcb_stream(uuid="pcb-1", title="PCB1"),
            "pcb/PCB2.epcb2": _pcb_stream(uuid="pcb-2", title="PCB1"),
        },
        titles={"pcb-1": "PCB1", "pcb-2": "PCB1"},
    )
    code, err = _run(
        ["pcb", "net-path", str(project), "--from", "U1.1", "--to", "U1.2", "--board", "PCB1"]
    )[0::2]
    assert code == 3
    assert "matches 2 boards" in err
    assert "uuid" in err

    # The refusal names the uuid remedy, and the uuid route itself is proven on a
    # real archive by `test_multi_board_container_selects_by_board_uuid`: a
    # synthetic folder reports no board uuid at all, so it cannot prove that half.
    assert "duplicate titles" in err


# ---------------------------------------------------------------------------
# invariants: nothing is written, and `pcb gate` is untouched
# ---------------------------------------------------------------------------
def test_nothing_is_written_next_to_the_archive(tmp_path: Path) -> None:
    archive = tmp_path / "copy.epro2"
    shutil.copyfile(LLC, archive)
    before = (archive.stat().st_size, archive.read_bytes())
    listing = sorted(p.name for p in tmp_path.iterdir())
    _run(["pcb", "net-path", str(archive), "--from", "CN3.1", "--to", "U9.2"])
    assert (archive.stat().st_size, archive.read_bytes()) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == listing


def test_pcb_gate_still_routes_to_its_own_adapter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list = []

    def gate(args, checkup, bridge):
        seen.append((args.command, args.pcb_command, args.out, callable(checkup), callable(bridge)))
        return 7

    monkeypatch.setattr(assembly_commands, "dispatch_pcb_gate", gate)
    assert cli.main(["pcb", "gate", "--out", str(tmp_path / "route")]) == 7
    assert seen == [("pcb", "gate", str(tmp_path / "route"), True, True)]


def test_net_path_routing_does_not_touch_the_gate_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    touched: list = []
    monkeypatch.setattr(
        assembly_commands,
        "dispatch_pcb_gate",
        lambda *a, **k: touched.append("gate") or 99,
    )
    code, _out, _err = _run(
        ["pcb", "net-path", str(LLC), "--from", "CN3.1", "--to", "U9.2"]
    )
    assert code == 0
    assert touched == []


def test_the_public_review_units_seam_keeps_the_lazy_tuple_shape() -> None:
    """550 A: assembly reaches review through the public name, not `_review_units`.

    Both code paths are pinned here so a future edit cannot make the wrapper a
    second implementation: the public call must return exactly what the in-layer
    private one returns, with the readers still deferred (a tuple of four, the
    last two callable, the board read only when called).
    """
    from boardwise.engines import pcbreview

    public = pcbreview.review_units(LLC)
    private = pcbreview._review_units(LLC)
    assert len(public) == len(private) == 1
    title, board_uuid, read_board, read_model = public[0]
    assert (title, board_uuid) == (private[0][0], private[0][1])
    assert title == "PCB1" and callable(read_board) and callable(read_model)
    assert len(read_board().pads) == len(private[0][2]().pads)
