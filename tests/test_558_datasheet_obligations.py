"""558: 手册异常件的义务分类与诚实结案路径.

The batch's premise (555's real pilot, ``evidence/558/``): the report answered
**one** template for every part. A mounting screw was handed
``(没有 MPN) datasheet pdf`` and weakly name-matched an unrelated MCU's PDF
(``m3`` is a substring of ``stm32…``), and U-designated connectors were asked
for the seven IC facts. Both claims are false — a datasheet would not have
helped either part — and a false worklist is worse than a short one.

Each test below pins one **causal hunk** of ``engines/checkup.py``:

1. mechanical declaration → ``no-ic-facts`` + ``ok:null/applicable:false`` and
   the folder is never consulted (mutate the mechanical branch out → red);
2. connector → ``connector-pinout``, no seven keys, pinout queries
   (mutate the connector branch out → the seven keys come back → red);
3. a shape-valid C-number is not "no identity" — the ``is_c_number`` half of
   :func:`datasheet_obligation` (remove it → ``identity-unresolved`` → red);
4. an unidentifiable part → ``identity-unresolved`` rather than seven keys,
   while 190's declared-passive exemption is unchanged;
5. ``screw terminal`` / ``螺丝端子`` are connectors, not fasteners; the same
   designator on two boards stays two rows; 522's machine tier is untouched.

The file uses synthetic components only — no real project, board, net or part
of a shipped design enters it (the names it does spell — ``M3螺丝``, ``EST026``,
``MX1.25-LT-3`` — are the pilot's *reported* identities, already in the task
book and ``evidence/558/``).
"""

from __future__ import annotations

import json

from boardwise.core.model import BoardModel, BoardRef, Component, DesignModel, Net, Pin
from boardwise.core.model import ProjectModel
from boardwise.core.parts import FACTS_KEYS, IDENTITY_NAME, PartEntry, PartLibrary
from boardwise.engines.checkup import (
    BASIS_MECHANICAL_DECLARATION,
    CHANNEL_ENGINEER,
    CHANNEL_LCSC,
    CHANNEL_OFFICIAL,
    OBLIGATION_CONNECTOR_PINOUT,
    OBLIGATION_IC_FACTS,
    OBLIGATION_IDENTITY_UNRESOLVED,
    OBLIGATION_NO_IC_FACTS,
    OBLIGATION_ORDER,
    PINOUT_SOURCE_NONE,
    REASON_CLASS_MACHINE_UNCONFIRMED,
    REASON_CLASS_MISSING_MATERIAL,
    REASON_CLASS_NO_IC_FACTS,
    REASON_CLASS_UNDECODABLE,
    TRIGGER_FACTS,
    TRIGGER_MARKED,
    UNKNOWN_REASON_MACHINE_UNCONFIRMED,
    UNKNOWN_REASON_UNDECODABLE,
    _local_datasheet,
    datasheet_obligation,
    mechanical_declaration,
    needs_datasheet_section,
    render_report_markdown,
    unreviewed_classes,
    unreviewed_counts_by_class,
    unreviewed_parts,
)


# ---------------------------------------------------------------------------
# tiny builders (same idioms as tests/test_190_part_kind.py)
# ---------------------------------------------------------------------------


def _comp(
    designator: str,
    *,
    value: str = "",
    footprint: str = "",
    mpn: str = "",
    lcsc: str = "",
    props: dict | None = None,
    pins=(),
) -> Component:
    return Component(
        uid=f"u-{designator}",
        designator=designator,
        value=value,
        footprint=footprint,
        mpn=mpn,
        lcsc_part=lcsc,
        props=dict(props or {}),
        pins=[Pin(str(number), str(name), net) for number, name, net in pins],
    )


def _three(designator: str, **kwargs) -> Component:
    """Three pins: 127b's floor cannot be the reason for any answer here."""
    kwargs["pins"] = [("1", "1", "A"), ("2", "2", "B"), ("3", "3", "C")]
    return _comp(designator, **kwargs)


def _two(designator: str, **kwargs) -> Component:
    kwargs["pins"] = [("1", "1", "A"), ("2", "2", "B")]
    return _comp(designator, **kwargs)


def _model(*components: Component) -> DesignModel:
    model = DesignModel(components={c.designator: c for c in components})
    nets: dict[str, Net] = {}
    for component in components:
        for pin in component.pins:
            if pin.net:
                nets.setdefault(pin.net, Net(name=pin.net)).pins.append(
                    (component.designator, pin.number)
                )
    model.nets = nets
    return model


def _board(title: str, *components: Component) -> BoardModel:
    return BoardModel(
        nets={},
        components={c.designator: c for c in components},
        board=BoardRef(uuid=f"b-{title}", title=title, page_uuids=(f"p-{title}",)),
    )


def _entry(**kwargs) -> PartEntry:
    return PartEntry(**kwargs)


def _row(report_rows: list[dict], designator: str, board: str = "") -> dict:
    """The row for one placement — the same designator can appear per board."""
    matches = [
        row
        for row in report_rows
        if row["designator"] == designator
        and (not board or board in json.dumps(row.get("boards") or [], ensure_ascii=False))
    ]
    assert matches, f"{designator} not in {[row['designator'] for row in report_rows]}"
    return matches[0]


def _report(rows: list[dict], needs: list[dict]) -> dict:
    """A report body just big enough for the renderer and the completion gate."""
    return {
        "schema": "boardwise.checkup/7",
        "summary": {
            "unreviewedParts": len(rows),
            "unreviewedByReason": {},
            "unreviewedByClass": unreviewed_counts_by_class(rows),
            "mayClaimPassed": False,
        },
        "unreviewed_parts": rows,
        "needs_datasheet": needs,
        "reviewedByShelf": [],
        "accepted_unknown": [],
        "warning_triage": [],
        "findings": [],
        "completion": {"scope": {"rules": 1, "boards": 1, "pages": 1}},
    }


# ---------------------------------------------------------------------------
# 1. a mechanical part owes no facts, no PDF and no query
# ---------------------------------------------------------------------------


def test_a_mechanical_part_owes_no_ic_facts_and_never_reads_the_folder(tmp_path):
    """``M3螺丝``: no identity, no obligation — and the STM32 PDF must stay out.

    555 measured the whole failure in one row: the screw had no MPN, so the
    query template read ``(没有 MPN) datasheet pdf``, and ``_local_datasheet``'s
    normalised pass matched it to an unrelated MCU's document because the
    identity token of ``M3螺丝`` is ``m3``, a substring of ``stm32…``. The row
    then reported 「engineer 有手册」 about a screw. The fix is not a better
    matcher: the folder is not this part's channel at all.
    """
    folder = tmp_path / "ds"
    folder.mkdir()
    (folder / "STM32H743VIT6.pdf").write_bytes(b"%PDF-1.4 fake")

    screw = _comp("SCREW1", props={"device_name": "M3螺丝"}, pins=[("1", "1", "GND")])
    # The trap is real, and it is the matcher's own reading — not this test's.
    trap, trap_by = _local_datasheet(
        folder, ("", "mpn"), ("", "lcsc"), ("M3螺丝", IDENTITY_NAME)
    )
    assert trap is not None and trap.name == "STM32H743VIT6.pdf"
    assert trap_by == IDENTITY_NAME

    (row,) = unreviewed_parts(_model(screw), library=PartLibrary(), datasheet_dir=folder)
    assert row["obligation"] == OBLIGATION_NO_IC_FACTS
    assert row["obligationBasis"] == BASIS_MECHANICAL_DECLARATION
    assert row["missingFacts"] == []
    assert row["channels"][CHANNEL_ENGINEER]["ok"] is None
    assert row["channels"][CHANNEL_ENGINEER]["applicable"] is False
    assert row["channels"][CHANNEL_ENGINEER]["path"] == ""
    assert row["channels"][CHANNEL_ENGINEER]["matchedBy"] == ""
    assert row["channels"][CHANNEL_LCSC]["ok"] is None
    assert row["channels"][CHANNEL_LCSC]["applicable"] is False
    assert row["channels"][CHANNEL_OFFICIAL]["suggestedQueries"] == []
    assert "accept-unknown" in row["question"]
    assert "datasheet pdf" not in json.dumps(row, ensure_ascii=False)

    # The row is still work — it is just not *document* work.
    assert unreviewed_classes(row) == [REASON_CLASS_NO_IC_FACTS]
    assert REASON_CLASS_MISSING_MATERIAL not in unreviewed_classes(row)
    assert unreviewed_counts_by_class([row]) == {REASON_CLASS_NO_IC_FACTS: 1}


def test_a_mechanical_row_leaves_the_hunt_worklist_but_not_the_gate():
    """`needs_datasheet` is what the hunt consumes; the gate is another question.

    558 §2: a ``no-ic-facts`` row does not become a **facts trigger** — and 555's
    pilot is the reason (that seed carried the query and the channels, so the hunt
    searched `(没有 MPN) datasheet pdf` for a screw). The row still stays in
    ``unreviewed_parts[]`` and the verdict still stays ``incomplete``.

    A reviewer's **explicit** ``marked`` entry is a different claim: a person
    asking for a document outranks a template, so it is kept **and** it still
    carries the part's own obligation — otherwise the surviving entry would be an
    empty shell that cannot say what the part owes. 「保留 marked 外壳」 is not the
    contract; the four fields being readable on it is.
    """
    screw = _comp("SCREW1", props={"device_name": "M3螺丝"}, pins=[("1", "1", "GND")])
    (row,) = unreviewed_parts(_model(screw), library=PartLibrary(), datasheet_dir=None)

    # No facts trigger of its own: the facts-only worklist is empty.
    assert needs_datasheet_section([row], [], []) == []

    marked = needs_datasheet_section(
        [row], [{"part": "SCREW1", "pin": "", "reason": "人要看结构图"}], []
    )
    assert [entry["part"] for entry in marked] == ["SCREW1"]
    assert marked[0]["trigger"] == TRIGGER_MARKED
    # The seed still travelled: the obligation is machine-readable on the entry.
    assert marked[0]["obligation"] == OBLIGATION_NO_IC_FACTS
    assert marked[0]["obligationBasis"] == BASIS_MECHANICAL_DECLARATION
    assert marked[0]["obligationBasis"] == row["obligationBasis"]
    assert marked[0]["kind"] == row["kind"] == "unknown"
    # …the rest of the seed too, so the row is not a shell.
    assert marked[0]["factSeed"] is True
    assert marked[0]["channels"] == row["channels"]
    assert marked[0]["missingFacts"] == []
    # A mechanical seed never carries a pinout source (that is a connector's key).
    assert marked[0]["pinoutSource"] == ""

    from boardwise.cli import _completion_from_report

    report = _report([row], [])
    completion = _completion_from_report(report, needs_datasheet=[marked[0]])
    assert completion["verdict"] == "incomplete"
    assert report["summary"]["mayClaimPassed"] is False

    markdown = render_report_markdown(report)
    assert f"**{REASON_CLASS_NO_IC_FACTS}**（1）：`SCREW1`" in markdown
    assert "accept-unknown" in row["question"]


# ---------------------------------------------------------------------------
# 2. a connector owes a pin table, not seven IC facts
# ---------------------------------------------------------------------------


def _connector_shelf(**kwargs) -> PartLibrary:
    return PartLibrary(
        parts=[_entry(key="conn.mx3", mpn="MX1.25-LT-3", lcsc="C9900097986",
                      category="connector", **kwargs)]
    )


def test_a_connector_is_asked_for_a_pinout_not_for_seven_ic_facts():
    """U-designated 3-pin MX header: ``connector-pinout``, ``missingFacts == []``.

    555's second measured complaint. The seven keys are the **ic-facts**
    obligation's list; asking a header for ``ldo``/``required_caps`` is asking
    the wrong question, and the query words have to change with it.
    """
    header = _three(
        "U3",
        mpn="MX1.25-LT-3",
        lcsc="C9900097986",
        props={"device_name": "MX1.25-LT-3"},
    )
    (row,) = unreviewed_parts(_model(header), library=_connector_shelf(), datasheet_dir=None)
    assert row["kind"] == "connector"
    assert row["obligation"] == OBLIGATION_CONNECTOR_PINOUT
    assert row["pinoutSource"] == PINOUT_SOURCE_NONE
    assert row["missingFacts"] == []
    queries = row["channels"][CHANNEL_OFFICIAL]["suggestedQueries"]
    assert queries and all("datasheet" not in query for query in queries)
    assert "pinout" in queries[0] and "引脚定义" in queries[0]
    assert "脚位图" in queries[1]
    # The gate itself does not move: still unreviewed, still a seed, still open.
    assert row["isIc"] is True
    assert REASON_CLASS_MISSING_MATERIAL in unreviewed_classes(row)

    (seed,) = needs_datasheet_section([row], [], [])
    assert seed["trigger"] == TRIGGER_FACTS
    assert seed["obligation"] == OBLIGATION_CONNECTOR_PINOUT
    assert seed["obligationBasis"] == row["obligationBasis"]
    assert seed["kind"] == "connector"
    assert seed["pinoutSource"] == PINOUT_SOURCE_NONE
    assert seed["missingFacts"] == []

    from boardwise.cli import _completion_from_report

    completion = _completion_from_report(_report([row], [seed]), needs_datasheet=[seed])
    assert completion["verdict"] == "incomplete"


# ---------------------------------------------------------------------------
# 3. a shape-valid C-number is not "nobody knows what this is"
# ---------------------------------------------------------------------------


def test_a_valid_c_number_keeps_a_part_off_the_identity_list():
    """EST026's shape: catalog-associated, no MPN — and **not** unresolved.

    ``is_c_number`` is a shape test and nothing more (its own contract: whether
    the catalog knows the number is the service's answer). The obligation
    vocabulary needs that shape test for one thing only — to stop
    「no MPN」 from being read as 「unidentifiable」 — and this test pins both
    sides of it:

    * the EST026-shaped **connector** (shelf declares the category) is
      ``connector-pinout``;
    * a non-connector part holding the same shape-valid code is ``ic-facts``,
      never ``identity-unresolved``.

    Removing the ``is_c_number`` half turns the second part red.
    """
    shelf = PartLibrary(
        parts=[_entry(key="conn.est026", lcsc="C52878", category="connector")]
    )
    est = _two(
        "CN5",
        lcsc="C52878",
        props={"device_name": "EST026", "Supplier Footprint": "插件"},
    )
    coded_ic = _three("U9", lcsc="C123456", props={"device_name": "ACME9"})
    rows = unreviewed_parts(_model(est, coded_ic), library=shelf, datasheet_dir=None)

    est_row = _row(rows, "CN5")
    assert est_row["mpn"] == ""
    assert est_row["obligation"] == OBLIGATION_CONNECTOR_PINOUT
    assert est_row["obligation"] != OBLIGATION_IDENTITY_UNRESOLVED
    assert est_row["pinoutSource"] == PINOUT_SOURCE_NONE
    assert est_row["missingFacts"] == []

    ic_row = _row(rows, "U9")
    assert ic_row["mpn"] == ""
    assert ic_row["supplier"] == "C123456"
    assert ic_row["obligation"] == OBLIGATION_IC_FACTS
    assert ic_row["missingFacts"] == [key for key in FACTS_KEYS]


# ---------------------------------------------------------------------------
# 4. an unidentifiable part says so, and 190's exemption is unchanged
# ---------------------------------------------------------------------------


def test_a_part_without_identity_is_identity_unresolved_not_mechanical():
    """No MPN, no C-number, three pins: the row owes an **identity**.

    Neither of the two traps may claim it: it is not mechanical (nothing declares
    it so — an unknown ``kind`` is not a declaration, which is 025's own rule for
    the prefix), and it must not be handed the seven keys, because a facts list
    about a part nobody can name is a question with no answer.
    """
    mystery = _three("U9", props={"device_name": "ACME-UNKNOWN"})
    (row,) = unreviewed_parts(_model(mystery), library=PartLibrary(), datasheet_dir=None)
    assert row["obligation"] == OBLIGATION_IDENTITY_UNRESOLVED
    assert row["obligation"] != OBLIGATION_NO_IC_FACTS
    assert row["missingFacts"] == []
    assert row["isIc"] is True
    assert mechanical_declaration(mystery) == ""


def test_190_declared_passive_exemption_is_unchanged():
    """A ``U``-designated 330 kΩ stays exempt — this batch adds no new exemption.

    190/192B's rule reads a **declared** passive with ≤ 2 pins out of the IC
    question, and its trail is ``completion.declaredPassiveExempt``. 558 touches
    neither the exemption nor its pin ceiling: the same part without the metadata
    declaration is still listed (with the ic-facts obligation).
    """
    declared = _two(
        "U7",
        value="330K",
        mpn="RS-330K",
        lcsc="C12345",
        props={"LCSC Part Name": "330kΩ 电阻", "device_name": "330K"},
    )
    undeclared = _two("U8", value="330K", mpn="RS-330K", lcsc="C12345",
                      props={"device_name": "330K"})

    rows = unreviewed_parts(_model(declared, undeclared), library=PartLibrary(),
                            datasheet_dir=None)
    listed = {row["designator"] for row in rows}
    assert "U7" not in listed
    assert "U8" in listed
    assert _row(rows, "U8")["obligation"] == OBLIGATION_IC_FACTS


# ---------------------------------------------------------------------------
# 5. the negative controls: screw terminal, cross-board rows, the machine tier
# ---------------------------------------------------------------------------


def test_screw_terminal_is_a_connector_not_a_fastener():
    """§4.5: the English word alone must not make a part mechanical.

    ``screw`` is the one word that appears on both sides of the line: a screw is
    a fastener and a screw **terminal** is a connector. A part that names itself
    a terminal wins, in English and in Chinese (``螺丝端子`` is the same part),
    and its obligation is the connector's — even though the fastener word is
    right there in the name.
    """
    for name in ("KF128 screw terminal 5.08", "螺丝端子 5.08", "接线柱-2P"):
        component = _comp("CN9", props={"device_name": name})
        assert mechanical_declaration(component) == "", name
        read = datasheet_obligation(component, library=PartLibrary())
        assert read["obligation"] != OBLIGATION_NO_IC_FACTS, name

    # …while the declarations that really are mechanical still read as such.
    for name, word in (
        ("M3螺丝", "螺丝"),
        ("M3 铜柱", "铜柱"),
        ("Mounting Hole M2", "mounting hole"),
        ("standoff M3x8", "standoff"),
    ):
        component = _comp("SCREW1", props={"device_name": name})
        assert mechanical_declaration(component) == word
        assert datasheet_obligation(component)["obligation"] == OBLIGATION_NO_IC_FACTS


def test_the_same_designator_on_two_boards_stays_two_rows():
    """§2: identical designators with different identities are never merged.

    The pilot's ``SCREW1``…``SCREW4`` appear on **both** boards, and the
    connector ``U2`` is a 2x6 header on one board and something else on another.
    Each placement keeps its own row, its own obligation and its own boards list;
    folding them would have to pick one identity for two parts.
    """
    screw_a = _comp("SCREW1", props={"device_name": "M3螺丝"}, pins=[("1", "1", "GND")])
    screw_b = _comp("SCREW1", props={"device_name": "M3螺丝"}, pins=[("1", "1", "PGND")])
    project = ProjectModel(
        boards=[_board("控制板", screw_a), _board("驱动板", screw_b)],
        source="in-memory",
    )
    rows = unreviewed_parts(project, library=PartLibrary(), datasheet_dir=None)
    screws = [row for row in rows if row["designator"] == "SCREW1"]
    assert len(screws) == 2
    titles = {row["boards"][0]["board"] for row in screws}
    assert titles == {"控制板", "驱动板"}
    assert {row["obligation"] for row in screws} == {OBLIGATION_NO_IC_FACTS}

    # The fold is per designator, and each distinct identity stays a per-board row;
    # a mechanical part contributes no facts seed at all.
    assert needs_datasheet_section(rows, [], []) == []


def test_the_machine_verified_tier_and_its_class_are_untouched():
    """§4.5: 522's tier keeps its row, its reason and its bucket.

    The obligation is ``ic-facts`` — a machine-verified fact set is exactly the
    case where facts are owed and are there — and the row is still
    「机器核验待人工确认」. 558 adds vocabulary beside the tier; it does not
    relax it.
    """
    facts = {
        "supply_pins": {"pin": "1"},
        "required_caps": [],
        "nc_pins": [],
        "must_connect": [],
        "led": {},
        "ldo": {},
        "pull_required": [],
    }
    shelf = PartLibrary(
        parts=[_entry(
            key="ic.mcu", value="ACME1", mpn="ACME1", lcsc="C111",
            category="ic.mcu", facts=dict(facts), facts_trust="machine_verified",
        )]
    )
    mcu = _three("U1", mpn="ACME1", lcsc="C111", props={"device_name": "ACME1"})
    (row,) = unreviewed_parts(_model(mcu), library=shelf, datasheet_dir=None)
    assert row["factsTrust"] == "machine_verified"
    assert row["obligation"] == OBLIGATION_IC_FACTS
    assert UNKNOWN_REASON_MACHINE_UNCONFIRMED in row["reasons"]
    assert unreviewed_classes(row) == [REASON_CLASS_MACHINE_UNCONFIRMED]
    assert unreviewed_counts_by_class([row]) == {REASON_CLASS_MACHINE_UNCONFIRMED: 1}


def test_the_four_obligations_are_the_whole_vocabulary():
    """One list, four values, each with a different next act (§2)."""
    assert OBLIGATION_ORDER == (
        OBLIGATION_NO_IC_FACTS,
        OBLIGATION_CONNECTOR_PINOUT,
        OBLIGATION_IDENTITY_UNRESOLVED,
        OBLIGATION_IC_FACTS,
    )
    assert PINOUT_SOURCE_NONE == "none"
    # A row written before this batch carries no `obligation` key at all: its
    # classes still read off its reasons, unchanged.
    legacy = {"designator": "U9", "reasons": [UNKNOWN_REASON_UNDECODABLE]}
    assert unreviewed_classes(legacy) == [REASON_CLASS_UNDECODABLE]


# ---------------------------------------------------------------------------
# 6. 560: an electrical connector's own words beat a mechanical word beside them
# ---------------------------------------------------------------------------


def test_a_header_naming_a_mounting_hole_is_still_a_connector():
    """``Mounting Hole Header 2x3``: connector first, fastener only as a hint.

    Measured (``evidence/560/mounting-header-repro.txt``): ``classify_part`` read
    the part's own ``HEADER`` as ``connector`` on basis ``metadata``, the same
    name matched ``mounting hole``, and the obligation came back ``no-ic-facts``
    — which drops an **electrical connector** out of the hunt and files it as a
    mechanical row a person has to close by hand. A mechanical declaration is a
    fallback for parts with no electrical connector identity, not a veto on one.

    The boundary is the basis, not the word: a *designator prefix* is the hint
    ``mechanical_declaration`` already refuses to trust, so an ``H1``
    ``安装孔`` stays mechanical, and ``M3螺丝`` keeps leaving the hunt.
    """
    header = _comp(
        "J1", props={"device_name": "Mounting Hole Header 2x3"}, pins=[("1", "1", "GND")]
    )
    read = datasheet_obligation(header, library=PartLibrary())
    assert read == {
        "obligation": OBLIGATION_CONNECTOR_PINOUT,
        "obligationBasis": "metadata",
        "kind": "connector",
        "pinoutSource": PINOUT_SOURCE_NONE,
    }
    # The mechanical word is still *reported* — it just does not decide.
    assert mechanical_declaration(header) == "mounting hole"

    (row,) = unreviewed_parts(_model(header), library=PartLibrary(), datasheet_dir=None)
    assert row["obligation"] == OBLIGATION_CONNECTOR_PINOUT
    assert row["kind"] == "connector"
    assert row["pinoutSource"] == PINOUT_SOURCE_NONE
    assert row["missingFacts"] == []
    # …so it stays in the hunt as a pin-table job, and the gate stays shut.
    (seed,) = needs_datasheet_section([row], [], [])
    assert seed["part"] == "J1"
    assert seed["trigger"] == TRIGGER_FACTS
    assert seed["obligation"] == OBLIGATION_CONNECTOR_PINOUT
    assert seed["pinoutSource"] == PINOUT_SOURCE_NONE

    from boardwise.cli import _completion_from_report

    completion = _completion_from_report(_report([row], [seed]), needs_datasheet=[seed])
    assert completion["verdict"] == "incomplete"

    # Negative controls: the mechanical side is untouched, word for word.
    for name, designator in (("M3螺丝", "SCREW1"), ("安装孔", "H1")):
        part = _comp(designator, props={"device_name": name}, pins=[("1", "1", "GND")])
        assert datasheet_obligation(part)["obligation"] == OBLIGATION_NO_IC_FACTS, name
        (mechanical,) = unreviewed_parts(
            _model(part), library=PartLibrary(), datasheet_dir=None
        )
        assert mechanical["missingFacts"] == []
        assert needs_datasheet_section([mechanical], [], []) == []
        assert unreviewed_classes(mechanical) == [REASON_CLASS_NO_IC_FACTS]

    # …and a screw terminal is the connector it names itself, not a fastener.
    for name in ("KF128 screw terminal 5.08", "螺丝端子 5.08", "接线柱-2P"):
        terminal = _comp("CN9", props={"device_name": name})
        assert datasheet_obligation(terminal)["obligation"] == (
            OBLIGATION_CONNECTOR_PINOUT
        ), name
