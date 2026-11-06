"""543H / 201G: the flyback island page's **accepted disclosure ceiling**.

201G asked why the flyback page produced no candidate.  The answer was that it no
longer walks the path the 0 was measured on: since the document declares five
`islands[]`, `drawcompiler.compile` takes the island page
(:func:`drawcompiler._try_island_variants`), whose gate is the *readability*
checker — the grammar's relations are recorded as findings and the page is
delivered with them.  542 accepted that delivery (13 grammar relation findings,
`hard_violations == []`), and 543H re-measured it on the current tree.

This file pins the **contract that acceptance rests on** — not "the relations are
satisfied".  It is a ceiling and a checklist:

* the page compiles: `ok=True`, exactly one candidate;
* the disclosure is **exactly** these 13 relations, kind-for-kind, in the
  compiler's own order, and `same-column(Q1, R5)` is among them — the relation
  201G opened the diagnosis for;
* `near(R15, R3)` is **not** among them (it is kept: the two arms stand 76 units
  apart against a 300-unit `near_limit`);
* the two accounts stay separate: these are *grammar* findings, and
  `island_gate_violations` — the island page's hard/tolerated split — is fed only
  `HardViolation`s.  Today it refuses nothing and tolerates nothing on this page,
  and no relation finding ever appears in either half;
* `SEC_12V`'s flag is a **measured** seat on `D3.1`: recomputed from the symbol
  profile and the part's pose, the pad tip and the flag are 30 units apart on one
  vertical, joined by a `SEC_12V` conductor.

**Changing any item is a deliberate contract change.**  A 14th finding, a finding
that disappears silently, `same-column(Q1, R5)` dropping off the list, or a
tolerated row appearing in the other account must fail here and be re-accepted
with fresh evidence — the numbers below are 543H's reading (`.tmp_543h_201g/`),
not a property that is allowed to drift with a layout tweak.

The expectations are written out as values (not read from `.tmp_543h_201g/*.json`)
so the test measures the production API it is pinning: a regenerated probe cannot
turn a broken page green.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolPose, SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import readability as rb

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
STEM = "flyback_uc3845"

#: The 13 relations 543H measured as delivered-with (201G report §2), in the
#: compiler's own order: `(kind, subject, object)`.  A tuple, not a set — the
#: order is part of the checklist so that "one finding moved" is visible too.
ACCEPTED_RELATION_DISCLOSURES: tuple[tuple[str, str, str], ...] = (
    ("below", "Q1", "T1"),
    ("same-column", "Q1", "R5"),
    ("near", "R15", "T1"),
    ("near", "R3", "T1"),
    ("near", "C5", "T1"),
    ("below", "C11", "D3"),
    ("near", "D3", "T1"),
    ("near", "C11", "T1"),
    ("near", "C13", "T1"),
    ("left-of", "R8", "U4"),
    ("right-of", "C10", "U5"),
    ("below", "C10", "U5"),
    ("near", "C10", "U5"),
)

#: 543H: the seat the flag ladder found for the rail that had none (201G's
#: suspicion B) — `D3.1`'s own pad, one vertical, 30 units, inside the 60-unit
#: `FLAG_LEAD_LIMIT`.
SEC_12V_LEAD = 30.0
SEC_12V_PIN = "D3.1"


def _library() -> dict[str, SymbolProfile]:
    payload = json.loads((SPECS / f"{STEM}.library.json").read_text(encoding="utf-8"))
    book: dict[str, SymbolProfile] = {}
    for entry in payload["profiles"]:
        profile = SymbolProfile.from_dict(entry)
        book[profile.symbol_ref] = profile
    return book


def _inputs():
    return (
        CircuitSpec.load(SPECS / f"{STEM}.circuit.json"),
        PresentationSpec.load(SPECS / f"{STEM}.presentation.json"),
        _library(),
    )


@pytest.fixture(scope="module")
def compiled():
    """The real page through the production entry 542 delivered (one candidate)."""
    circuit, presentation, book = _inputs()
    result = dc.compile(
        circuit, presentation, book, dc.CompileBudget(max_candidates=64),
    )
    return result, circuit, presentation, book


def _pin_tip(plan, circuit, book, part_id: str, token: str):
    """A pad tip, recomputed from the profile and the part's own pose.

    Deliberately the profile/pose arithmetic and not a coordinate typed in from
    the probe: the claim is "the compiler's page puts the pad here", and a
    transposed or mirrored symbol is exactly what would move it.
    """
    part = plan.part(part_id)
    assert part is not None, part_id
    profile = book[circuit.part(part_id).symbol_ref]
    pin = next(pin for pin in profile.pins if pin.number == token)
    return dc._posed(
        pin.tip, SymbolPose(int(part.rotation), bool(part.mirror)), (part.x, part.y)
    )


def _ids(finding) -> tuple[str, str]:
    """`GrammarFinding.objects` are `parts[X]` names; this is the pair, bare."""
    return tuple(
        name[len("parts["):-1] if name.startswith("parts[") else name
        for name in finding.objects
    )


#: `check_grammar` renders the relation itself into the finding's detail (the
#: finding's own `kind` is the class, `grammar-relation-broken`, for every one of
#: them), so the pair this file checks is read from the sentence the page is
#: actually delivered with.
_RELATION_IN_DETAIL = re.compile(
    r"the relation (\S+) between (\S+) and (\S+) is not kept"
)


def _relation_pairs(findings) -> tuple[tuple[str, str, str], ...]:
    out: list[tuple[str, str, str]] = []
    for item in findings:
        match = _RELATION_IN_DETAIL.search(item.detail)
        assert match, item.detail[:300]
        kind, subject, obj = match.groups()
        assert _ids(item) == (subject, obj), (item.objects, match.groups())
        out.append((kind, subject, obj))
    return tuple(out)


# --------------------------------------------------------------- 1. the page


def test_the_island_page_is_delivered_with_one_candidate(compiled):
    """201G's symptom (0 candidates) was measured on a document without islands.

    On *this* document the island path delivers: one candidate, no hard violation,
    and the candidate is the ranked leader.  A refusal here means the page moved
    off 542's accepted shape, not that 201G reopened.
    """
    result, _circuit, _presentation, _book = compiled
    assert result.ok, [item.detail[:400] for item in result.failures]
    assert len(result.candidates) == 1, len(result.candidates)
    assert result.rejected == [], [item.reason[:200] for item in result.rejected]
    assert result.failures == []
    plan = result.candidates[0]
    assert plan.evidence.hard_violations == []
    assert plan.evidence.grammar_findings  # the disclosure is what §2/§3 are about


# ------------------------------------------- 2. the disclosure, item by item


def test_the_disclosure_is_exactly_the_13_accepted_relations(compiled):
    """Item-for-item against 201G report §2 — kind, pair, and order.

    `check_grammar` is the independent re-binding the gate itself uses, so this
    compares the *rule* the page is graded by, not the strings the compile kept
    (`evidence.grammar_findings` is then asserted to be that same list rendered).
    """
    result, circuit, presentation, book = compiled
    plan = result.candidates[0]
    findings = dc.check_grammar(plan, circuit, presentation, book)
    measured = _relation_pairs(findings)
    assert measured == ACCEPTED_RELATION_DISCLOSURES
    assert all(item.kind.startswith("grammar-") for item in findings)
    assert len(findings) == 13

    rendered = plan.evidence.grammar_findings
    assert rendered == [item.render() for item in findings]
    assert all(line.startswith(f"[{dc.KIND_RELATION_BROKEN}] ") for line in rendered)


def test_same_column_q1_r5_is_disclosed_and_near_r15_r3_is_kept(compiled):
    """The two relations 201G named, read in opposite directions.

    `same-column(Q1, R5)` is one of the delivered-with findings (the sense
    resistor does **not** stand in the switch's column on this page); `near(R15,
    R3)` is **not**, because the two clamp arms are 76 units apart against the
    300-unit limit.  This is the pair of statements the 201G report makes, and
    they must not collapse into "one of the two".
    """
    result, circuit, presentation, book = compiled
    plan = result.candidates[0]
    findings = dc.check_grammar(plan, circuit, presentation, book)
    measured = set(_relation_pairs(findings))

    assert ("same-column", "Q1", "R5") in measured
    assert ("near", "R15", "R3") not in measured

    by_relation = {pair: item for pair, item in zip(_relation_pairs(findings), findings)}
    detail = by_relation[("same-column", "Q1", "R5")].detail
    assert "the relation same-column between Q1 and R5 is not kept" in detail

    binding = dc.bind_grammar(circuit, presentation, book)
    arm = next(
        item for item in binding.constraints
        if item.kind == "near" and item.subject == "R15" and item.object == "R3"
    )
    points = dc._points_for_relation(
        circuit, arm,
        origin_of=lambda part_id: dc._plan_origin(plan, part_id),
        pin_of=lambda part_id, token: dc._plan_pin(plan, book, part_id, token),
    )
    assert points is not None
    (x0, y0), (x1, y1) = points
    distance = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    assert distance < dc.NEAR_LIMIT, distance


# --------------------------------- 3. grammar findings are not gate violations


def test_the_grammar_findings_never_enter_the_island_gate_account(compiled):
    """Two books, kept apart — the island page's delivery policy is not widened.

    `island_gate_violations` splits the *readability* checker's `HardViolation`s
    into refused/tolerated; the grammar's relations are a different layer and are
    never one of those objects.  On this page both halves are empty (the page is
    delivered with no host-printed row forgiven), while the grammar layer carries
    the 13 findings of §2 — so "tolerated: …" lines appearing here would mean the
    two accounts had been mixed, and a relation finding would then be pretending
    to be a gate exception.
    """
    result, circuit, presentation, book = compiled
    plan = result.candidates[0]

    checked = rb.check(
        plan, circuit, presentation, book,
        grammar_checker=dc.check_grammar,
    )
    kinds = [item.kind for item in checked.hard_violations]
    assert dc.KIND_RELATION_BROKEN not in kinds
    assert all(isinstance(item, rb.HardViolation) for item in checked.hard_violations)
    assert len(checked.grammar_findings) == len(ACCEPTED_RELATION_DISCLOSURES)

    refusing, tolerated = dc.island_gate_violations(checked.hard_violations)
    assert refusing == []
    assert tolerated == []
    assert plan.evidence.hard_violations == []
    assert [note for note in result.notes if note.startswith("tolerated: ")] == []


# ----------------------------------- 4. SEC_12V's flag seat on D3.1, measured


def test_sec_12v_flag_sits_30_units_off_d3_pin1_and_is_wired(compiled):
    """201G suspicion B, closed by measurement rather than by the compiler's note.

    The pad tip comes from the profile + pose (§ `_pin_tip`), the flag from
    `plan.power_symbols`, the join from a `SEC_12V` segment whose consecutive
    points are exactly the pad and the seat.  `+y` is canvas-up, so the flag hangs
    *above* the cathode — the power side `sidePreferences` asks for.
    """
    result, circuit, book = compiled[0], compiled[1], compiled[3]
    plan = result.candidates[0]

    part_token = SEC_12V_PIN.split(".")
    tip = _pin_tip(plan, circuit, book, part_token[0], part_token[1])
    seats = [flag for flag in plan.power_symbols if flag.net == "SEC_12V"]
    assert seats, "SEC_12V must be stated by a flag on this page (069 sec.1)"

    matching = [
        flag for flag in seats
        if abs(flag.x - tip[0]) < 1e-6 and abs(abs(flag.y - tip[1]) - SEC_12V_LEAD) < 1e-6
    ]
    assert len(matching) == 1, [(flag.x, flag.y) for flag in seats]
    seat = matching[0]
    assert seat.y == tip[1] + SEC_12V_LEAD, "the seat hangs above the pad (canvas y-up)"
    assert SEC_12V_LEAD <= dc.FLAG_LEAD_LIMIT

    runs = [
        run
        for segment in plan.segments if segment.net == "SEC_12V"
        for run in zip(segment.points, segment.points[1:])
    ]
    joined = [
        run for run in runs
        if {tuple(run[0]), tuple(run[1])} == {tuple(tip), (seat.x, seat.y)}
    ]
    assert joined, (
        "the flag is not joined to the pad it sits on: "
        f"tip={tip}, seat=({seat.x}, {seat.y}), runs={runs}"
    )
