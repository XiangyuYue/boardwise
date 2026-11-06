"""Normalized design model for boardwise.

Stage 1 only consumes EasyEDA Pro schematic netlists (``.enet``), but this
model is the long-term contract: the review engine, and later the generator
and the simulator, all operate on these types.

The ``role`` / ``block`` fields on :class:`Component` are reserved intent
metadata for the stage-2 generator. Nothing populates them yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Net-name prefixes treated as ground. Module-level so it can become
#: configurable later without touching rule code. ``VEE`` is deliberately
#: absent: it is a *negative supply* in analog/ECL circuits, not a ground
#: (2026-09-18 ruling, M0-P0c).
#:
#: ``EARTH`` joined in 171, and why it belongs **here** rather than in a rule's
#: own word list: it is the commonest English spelling of a board's ground, and
#: this tuple is 「the one place this repo calls a name ground」 (143d). 164a's D2
#: measured the cost of its absence from the other side —
#: ``rules/pcb/focground.GROUND_DOMAIN_POWER_PREFIXES`` names ``EARTH`` as a
#: power-domain word, so ``split_ground_domains`` had to sieve with a **union**
#: (``domain_of`` ∨ :func:`is_ground_net`) or a bare ``EARTH`` net vanished from
#: every domain in silence. The union sieve stays (it is redundant for ``EARTH``
#: now and still carries ``P_GND`` / ``POWER_GND``, which core does not claim);
#: what changed is that the vocabulary can answer for the name. Being a member
#: means being matched with ``startswith``, so ``EARTHING`` / ``EARTHED`` are
#: ground-class too — the same over-reach ``GNDX_RAIL`` has had all along (145a
#: pins it), and cheaper than a second, exact-name list to keep in step.
GROUND_NET_PREFIXES: tuple[str, ...] = (
    "GND",
    "AGND",
    "DGND",
    "PGND",
    "EGND",
    "SGND",
    "VSS",
    "EARTH",
)

#: The same ground words, read as the **last** ``_``-separated token of a
#: compound name (``SEC_GND``, ``ISO_VSS``). 145a: the prefix rule alone called
#: the flyback's secondary-side return ``SEC_GND`` "not a ground name", and
#: `engines.drawapply.flag_kind` (143d's cross-check, which reads this function
#: as "the one place a name is called ground") then refused to hang the ground
#: glyph 岳's own page draws on that net — a ground symbol on a rail-looking name
#: is exactly the disagreement 143d exists to catch, so the vocabulary, not the
#: check, is what had to grow. A ground word at the end of a name is the same
#: statement as one at the front.
GROUND_NET_SUFFIX_WORDS: tuple[str, ...] = GROUND_NET_PREFIXES


def is_ground_net(name: str | None) -> bool:
    """Return True for common ground net names (GND, AGND, PGND, VSS, ...).

    A ground word at the **front** of the upper-cased name (``GNDA`` and ``VSSA``
    count) or as its **last** ``_``-separated token (``SEC_GND``, ``ISO_VSS`` —
    145a). ``None`` and empty names are never ground.

    ``EARTH`` is one of the words as of 171 (see
    :data:`GROUND_NET_PREFIXES`), so the bare ``EARTH`` a board's earthing net is
    usually called now reads as a ground name, and so do ``EARTH_PGND`` /
    ``SEC_EARTH``. The prefix rule means ``EARTHING`` counts as well — the same
    over-reach the GND family has always had (``GNDX_RAIL``).

    **The name is only a candidate.** A net's role should come from declared
    intent and from device facts (a part's pin function, a rail's source); this
    inference exists so that rules have something to say about a name they were
    handed, and it is deliberately narrow — a name it does not recognise is
    "not known to be ground", not "not ground". ``VEE`` used to be listed here,
    which made a negative supply read as ground; it is now left to the
    declarations and device facts that should have been deciding it.
    """
    if not name:
        return False
    upper = name.upper()
    if any(upper.startswith(prefix) for prefix in GROUND_NET_PREFIXES):
        return True
    _head, separator, tail = upper.rpartition("_")
    return bool(separator) and tail in GROUND_NET_SUFFIX_WORDS


@dataclass
class Pin:
    """One pin of a component."""

    number: str
    name: str
    net: str | None = None


#: Why a reading cannot prove a net. ``WELDED_BY_NAME`` is issue #19's gap —
#: the per-page merge joined two pages because they spelled a net name the same
#: way, which may be two boards. The two truncation codes are 107's: the parser
#: kept only the first placement of a repeated designator (049's one-designator-
#: one-component contract), so a placement that is drawn on the sheet and does
#: connect to the net is missing from ``Net.pins`` — the net's member list came
#: out short, and a rule that looks a part up *on that net* is looking at a
#: netlist with a hole in it.
WELDED_BY_NAME = "welded-by-name"
TRUNCATED_BY_DESIGNATOR = "truncated-by-duplicate-designator"
TRUNCATED_BY_CROSS_PAGE_DESIGNATOR = "truncated-by-cross-page-designator"

#: 041 §3: the only evidence level a cross-board **unproven** edge may cite, and
#: what this reading can actually establish. ``E0`` is "the two sides spell the
#: same net name", which is string equality — it proves neither a connection nor
#: a disconnection. ``E1`` (a connector-looking designator, a matching footprint,
#: a datasheet that shorts two pins *inside* one part, two boards numbering
#: ``CN1``) cannot say which pin of one board meets which pin of another either,
#: and there is no ``E2`` before a host netlist cross-check exists (041 §7 S3,
#: deferred). The level lives here rather than in a rule because it is a
#: statement about what the model may claim, and the claim is "not proven".
EVIDENCE_LEVEL_BY_NAME = "E0"


@dataclass
class Component:
    """One placed component, keyed by designator inside the model."""

    uid: str
    designator: str
    value: str = ""
    footprint: str = ""
    lcsc_part: str = ""
    manufacturer: str = ""
    mpn: str = ""
    datasheet: str = ""
    props: dict[str, Any] = field(default_factory=dict)
    pins: list[Pin] = field(default_factory=list)
    # Reserved intent metadata for the stage-2 generator. Unused today.
    role: str | None = None
    block: str | None = None


@dataclass
class Net:
    """One named net. ``pins`` holds (designator, pin_number) tuples."""

    name: str
    pins: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class DesignModel:
    """The normalized board model.

    - ``components``: designator -> Component
    - ``nets``: net name -> Net (reverse-built by the parser)
    - ``raw``: untouched top-level blocks from the source file
      (designRule / differentialPair / netClass / equalLengthNetGroup),
      kept verbatim because future rules will consume them.
    """

    components: dict[str, Component] = field(default_factory=dict)
    nets: dict[str, Net] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    #: Designators placed **twice on one page**: two parts answer to one name
    #: in one netlist, which is what CONN-1 is about. The dict key above keeps
    #: only the first placement, so without this list the clash would be silent
    #: (task 011c sec.3.2). Empty for single-page boards without clashes.
    duplicate_designators: list[str] = field(default_factory=list)
    #: Designator -> the pages it is placed on, for designators that appear on
    #: **more than one page** (one placement each). A multi-board project
    #: numbers each board's parts independently, so this is information, not a
    #: defect — 040 §WI-3 split it out of ``duplicate_designators``, which used
    #: to hold both kinds under one name. ``repeated_designators()`` is what a
    #: consumer that merely needs "is this name ambiguous here?" should call.
    cross_page_designators: dict[str, list[str]] = field(default_factory=dict)
    #: Net names whose **membership is not a verified connection**, with the
    #: pages each name was seen on. Empty for every model that comes out of one
    #: export — which is every model except the merged per-page one (issue #19,
    #: :func:`boardwise.cli._merge_schematic_models`): within one board, a single
    #: export's netlist *is* its connectivity, so its nets are proven by
    #: construction. Cross-board ties are a different, explicitly unproven
    #: question answered by :class:`NetInstance` / :attr:`ProjectModel.unproven_edges`.
    #:
    #: The per-page tier reads one page at a time and holds no document that says
    #: which board a page belongs to. Merging two pages by net **name** therefore
    #: welds two boards' netlists together wherever the names agree (`VCC`,
    #: `+5V`, `GND` are the common ones), and a rule that then finds a capacitor
    #: on "VCC" cannot tell whose board it is on. A name listed here was seen on
    #: more than one page, so a rule whose conclusion depends on which *other*
    #: parts sit on it must refuse (``boardwise.rules.unproven``) rather than
    #: conclude pass or fail.
    #:
    #: The value is the page uuids the name was seen on. As with
    #: :attr:`cross_page_designators`, an **empty tuple** is what a caller states
    #: when it knows the name is on more than one page but cannot name them (a
    #: merge of models that carry no page ids) — so the test is ``is not None``,
    #: never truthiness.
    unproven_nets: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: net name -> ``(reason code, one sentence naming the placements that were
    #: left out)`` for the names this reading cannot prove **and why**, per the
    #: codes above. An absent entry means :data:`WELDED_BY_NAME` — the issue #19
    #: merge, which is still the whole story for a model that came out of one
    #: export — so a reader written before this field keeps its wording, and a
    #: net whose membership a dropped placement may have truncated says so
    #: instead of being read as a net two pages happened to share a name with
    #: (107). The sentence is stored rather than rebuilt because only the parser
    #: knows which placement it dropped; it is quoted, never parsed.
    unproven_reasons: dict[str, tuple[str, str]] = field(default_factory=dict)
    #: Where the drawing put each pin, and where its **WIRE** segments run — the
    #: geometry a cross-view reader needs and a netlist cannot carry (527C2).
    #:
    #: ``None`` is the honest answer for every model with no drawing behind it to
    #: measure — KiCad, ``.enet``, a hand-built model — so a consumer keeps its
    #: old generic wording instead of pretending to a geometry it never read.
    #: KiCad's own endpoint-or-interior pin rule is *not* the EasyEDA one, so a
    #: later KiCad projection must bring its own ``binding`` rather than reuse
    #: this one's.
    #:
    #: When a parser does fill it, the dict holds:
    #:
    #: - ``binding``: how a pin counts as *on* a wire. ``"endpoint"`` is the
    #:   schematic view's own law (040): the pin's posed point lands **exactly**
    #:   on a segment end.
    #: - ``pins``: ``(designator, pin number) -> (page uuid, x, y)``, canvas
    #:   space, taken from the one placement the model keeps (049/105).
    #: - ``wires``: ``page uuid -> [(Point, Point), ...]`` — the segments a
    #:   ``WIRE`` head owns and nothing else. A placed symbol's own graphics are
    #:   not copper (040 §WI-2), and neither pages nor boards are ever merged: a
    #:   page is its own coordinate system.
    #:
    #: It is a reading, not a ruling: it says where the lines are, never whether
    #: a pin should have been on one.
    pin_wires: dict[str, Any] | None = None

    def unproven_pages(self, name: str | None) -> tuple[str, ...] | None:
        """The pages ``name`` was seen on when it is unproven, else ``None``.

        ``()`` is a real answer ("more than one page, page ids unknown"), so
        callers test ``is not None``.
        """
        if not name:
            return None
        return self.unproven_nets.get(name)

    def unproven_reason(self, name: str | None) -> tuple[str, str]:
        """``(reason code, detail)`` for an unproven ``name``.

        :data:`WELDED_BY_NAME` with an empty detail is what a name listed in
        :attr:`unproven_nets` without one says — the pre-107 shape, which is
        every net of a single-export reading and every name the per-page merge
        welded.
        """
        if not name:
            return (WELDED_BY_NAME, "")
        return self.unproven_reasons.get(name, (WELDED_BY_NAME, ""))

    def repeated_designators(self) -> list[str]:
        """Every designator this model cannot resolve to exactly one placement.

        Both kinds are ambiguous for a *consumer* even though only one of them
        is a defect: a repair plan or a per-page report cannot tell which
        placement is meant. Rules that judge the drawing use
        :attr:`duplicate_designators` instead — the distinction is 040 §WI-3's
        whole point.
        """
        return sorted(set(self.duplicate_designators) | set(self.cross_page_designators))


class MultiBoardProjectError(ValueError):
    """A single-board consumer was handed a multi-board project (040b §WI-2).

    Raised instead of returning one board's model or a pooled one: both would be
    silent — the first drops boards, the second re-welds them (040's F1/F2/F3
    exist because that weld was read as a board reading). A ``ValueError``
    subclass so existing ``except ValueError`` handlers degrade to a message
    rather than a traceback.

    It lives in ``core`` because it is a statement about the model contract, and
    because the façade below has to be able to raise it without importing a
    parser (``core`` must not import ``parsers``).
    """


@dataclass(frozen=True)
class BoardRef:
    """Which board a model belongs to, and which pages it was drawn on.

    040b: a project's pages are grouped into boards through the container's own
    document chain (see :func:`boardwise.parsers.schematic.board_partition`);
    this is that grouping as data. ``uuid`` is the container's board id and is
    empty for a board that exists only implicitly (a project with no BOARD
    document, or a folder project whose index has no ``profile.boards``).

    A board may hold **several pages** (measured: 毕设 Board1 owns page
    ``5f0f…`` and the empty ``b034…``), which is why pages, not boards, are
    what a ``COMPONENT`` record's coordinates belong to.
    """

    uuid: str = ""
    title: str = ""
    page_uuids: tuple[str, ...] = ()


@dataclass(frozen=True)
class NetInstance:
    """One board's net, as its own node — ``(board_uuid, net_name)`` (041 §2).

    ``GND`` on Board1 and ``GND`` on Board3 are **two** instances: the same
    spelling is E0 evidence and nothing more (041 §3), so a multi-board project's
    default reading is that no two boards share a node. A tie between two
    instances needs an explicit engineer declaration (041 §4.1, S2); this class
    deliberately carries no field in which one could be implied.

    ``board_uuid`` is the container's BOARD document id and must be **non-empty**:
    there is no instance of "some board". A project with no BOARD document is one
    *implicit* board whose uuid is empty, and an unregistered page of a
    multi-board project lands in the empty-uuid ``unattached`` group; both are
    non-addressable and get no instance at all (041 §1). The missing uuid is
    never replaced by the title, a page position or a hash — a position-derived
    ``board#0`` moves with the export order, which is the mistake the task book
    vetoes.

    ``net_name`` is read as-is, no case folding and no stripping: two names are
    the same name only when they are the same string, because that is the only
    question E0 can answer.
    """

    board_uuid: str
    net_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.board_uuid, str) or not self.board_uuid.strip():
            raise ValueError(
                "a NetInstance needs a real BOARD uuid: a project with no BOARD "
                "document, or a page no board registers, is non-addressable and "
                "has no instance (041 §1). Titles display only, and no id is "
                "invented from position, title or page number."
            )


@dataclass(frozen=True)
class UnprovenNetEdge:
    """Two net instances this reading **cannot** show to be one node (041 §4.1).

    It is not an edge in the netlist sense: it is a recorded question. The
    default pair of labels is the whole vocabulary of this batch —
    ``E0`` / ``welded-by-name`` says "these two instances spell the same net
    name", which is why they are worth asking about, not that they are connected
    and not that they are open (``proven-open`` is a conclusion 041 does not issue
    at all, §3).

    No consumer may read this as a connection; the rule is the opposite one — a
    consumer that needs "what sits on this net" must refuse to pool the two
    boards rather than pick one (041 §4.2). Both ends are :class:`NetInstance`,
    so both boards are addressable: an unattached page cannot appear on either
    side.

    The two ends must be **different** instances (``__post_init__`` refuses
    ``first == second``): one net compared with itself is not a question about two
    nodes, and a self-loop would let a consumer count a single instance twice.
    Nothing else about the ends is restricted — the same board's two nets are two
    nodes and may be paired.
    """

    first: NetInstance
    second: NetInstance
    reason: str = WELDED_BY_NAME
    evidence_level: str = EVIDENCE_LEVEL_BY_NAME

    def __post_init__(self) -> None:
        for side, instance in (("first", self.first), ("second", self.second)):
            if not isinstance(instance, NetInstance):
                raise TypeError(
                    f"UnprovenNetEdge.{side} must be a NetInstance, not "
                    f"{type(instance).__name__}: an edge joins two addressable "
                    "boards' nets, never a board, a title or a page"
                )
        if self.first == self.second:
            # One net compared with itself is not a question about two nodes, and
            # a self-loop would let a consumer count one instance twice (a board
            # "affected" on both ends of one non-connection). The name itself is
            # not restricted: the same board's two nets are two nodes.
            raise ValueError(
                f"UnprovenNetEdge cannot join {self.first!r} to itself — a net is "
                "not unproven against its own instance"
            )


@dataclass
class BoardModel(DesignModel):
    """One board's design model — the unit every rule runs on (040b §WI-2).

    "One designator, one component" is narrowed to **one board**: two boards may
    each hold their own ``R1``, and both placements live on in their own board's
    model instead of the later one silently overwriting the earlier (which is
    what a project-wide dict did).

    ``cross_board_designators`` is the one project-scoped fact a board model
    carries: for a designator placed on more than one board, the *titles of every
    board that has it*, in project order (so the first entry is the board that
    reports it — see :class:`boardwise.rules.connectivity.DuplicateDesignators`).
    A rule that only ever sees one board can therefore still say "this name is
    also used on Board3", which is the difference between a same-board repeat
    and a cross-board one (040b §WI-3; the oracle's A1 ruling is unchanged).
    """

    board: BoardRef = field(default_factory=BoardRef)
    cross_board_designators: dict[str, list[str]] = field(default_factory=dict)

    def repeated_designators(self) -> list[str]:
        """As :meth:`DesignModel.repeated_designators`, plus the cross-board names.

        On a board, a designator resolves to one placement *within* the board;
        it is still ambiguous for a consumer that has to name a part in a
        project-scoped artefact (a BOM, an edit plan), which is why the
        cross-board names are included here and not in
        :attr:`duplicate_designators`.
        """
        return sorted(
            set(super().repeated_designators()) | set(self.cross_board_designators)
        )


@dataclass
class ProjectModel:
    """A project's boards, each a :class:`BoardModel` (040b §WI-2).

    What this replaces: a single designator-keyed dict fed by every page of the
    project. That shape could not hold a multi-board project at all — the second
    board's ``C1`` overwrote the first's (040 measured 30 such refs on the 毕设
    board, and 040b's two U2s are the worked example).

    **The single-board façade.** ``components``, ``nets``,
    ``duplicate_designators`` and ``cross_page_designators`` read straight
    through to the project's one board, so a consumer written before boards
    existed keeps working — and a **multi-board** project raises
    :class:`MultiBoardProjectError` naming the boards instead of quietly
    answering with board 0. That refusal is the point: the alternative
    (first-board-wins) is exactly the silent loss this batch removes, one level
    up. Consumers that can be board-aware use :attr:`boards` directly.

    ``unproven_nets`` is read here too, with one deliberate difference — it
    **answers** on a multi-board project instead of raising, because there is
    nothing welded to report there (see its own docstring). A rule is handed
    whatever model the caller has, so "cannot answer" must not become a crash.

    ``project_raw`` keeps the untouched top-level blocks of the *project*;
    ``raw`` (the façade) keeps reading the single board's, as before.

    **Cross-board nets** (041) are a separate channel:
    :meth:`net_instances`, :meth:`cross_board_net_instances`,
    :attr:`unproven_edges` and :meth:`non_addressable_pages` describe what a
    multi-board project *cannot* prove — that two boards' same-named nets are one
    node — without changing a single finding, severity or verdict. They are kept
    out of ``unproven_nets`` on purpose: that one is the page weld a rule must
    refuse, and it would refuse on every board if cross-board names were put
    there.
    """

    boards: list[BoardModel] = field(default_factory=list)
    source: str = ""
    project_raw: dict[str, Any] = field(default_factory=dict)

    # --- board-aware reads (what multi-board consumers use) -----------------

    def board_titles(self) -> list[str]:
        """Every board title, in project order (what a finding's ``board`` names)."""
        return [board.board.title for board in self.boards]

    def designators(self) -> list[str]:
        """The project's distinct designators, sorted (names, not placements)."""
        return sorted({name for board in self.boards for name in board.components})

    def component_count(self) -> int:
        """Placed parts across every board (155 for the 毕设 project, not 121 names)."""
        return sum(len(board.components) for board in self.boards)

    def net_count(self) -> int:
        """Net instances across every board — per-board nets are not one netlist."""
        return sum(len(board.nets) for board in self.boards)

    def multi_board_designators(self) -> dict[str, list[str]]:
        """Designator -> the titles of every board carrying it, for names on >1 board."""
        seen: dict[str, list[str]] = {}
        for board in self.boards:
            for designator in board.components:
                titles = seen.setdefault(designator, [])
                if board.board.title not in titles:
                    titles.append(board.board.title)
        return {
            designator: titles
            for designator, titles in sorted(seen.items())
            if len(titles) > 1
        }

    def repeated_designators(self) -> list[str]:
        """Every name a project-scoped consumer cannot resolve to one placement."""
        names = {name for board in self.boards for name in board.repeated_designators()}
        return sorted(names)

    # --- cross-board nets (041 §1: instances, disclosure, no verdict) --------

    def net_instances(self) -> list[NetInstance]:
        """Every addressable board's nets, as instances, in project order.

        Board order first, net name second, so the answer is stable across runs
        and across a reload of the same project. A board with an empty uuid is
        skipped: it is the implicit board of a project that declares none, or an
        ``unattached`` page group, and neither can be paired with anything —
        :meth:`non_addressable_pages` is where the latter is disclosed.

        The list is flat and every entry names its own board. There is no
        project-scoped net answering to this name, which is the point: a single
        name-keyed dict for the whole project is the weld 040b removed one level
        up, and it is what makes two boards' ``GND`` look like one node.
        """
        instances: list[NetInstance] = []
        for board_model in self.boards:
            uuid = board_model.board.uuid
            if not uuid:
                continue
            for name in sorted(board_model.nets):
                instances.append(NetInstance(uuid, name))
        return instances

    def cross_board_net_instances(self) -> dict[str, list[NetInstance]]:
        """Net name -> its instances, for names carried by more than one board.

        The net-shaped counterpart of :meth:`multi_board_designators`, with one
        deliberate difference: the values are *instances* (board **uuid** + name),
        never titles, because a title is display and a uuid is identity (041 §1).

        A group here is a **question**, not a merge: its members remain separate
        nodes, and :attr:`unproven_edges` is the record of that. Names carried by
        one board only are absent, so an empty dict means "no name is shared",
        not "no boards".
        """
        groups: dict[str, list[NetInstance]] = {}
        for instance in self.net_instances():
            members = groups.setdefault(instance.net_name, [])
            if instance not in members:
                members.append(instance)
        return {
            name: members
            for name, members in sorted(groups.items())
            if len({member.board_uuid for member in members}) > 1
        }

    @property
    def unproven_edges(self) -> tuple[UnprovenNetEdge, ...]:
        """Every pair of same-named instances on different boards, in order.

        Derived, not stored: the same project always yields the same tuple
        (net-name order, then project board order), so a report can print it and
        a test can compare it. One edge per unordered pair — three boards sharing
        ``GND`` is three questions, not one.

        Nothing is read from a file and nothing is declared here: this property
        derives ``E0`` / ``welded-by-name`` from the model alone, and no host
        cross-check exists yet (S3). An engineer's declaration is a *separate*
        input — read by :mod:`boardwise.core.interconnect` from the path a caller
        names and disclosed beside these edges — and it changes nothing here: a
        declared pair does not remove an edge from this tuple, nor promote the
        same-named group it mentions out of ``E0`` (041 S2 §1). It is also **not**
        the same channel as :attr:`unproven_nets` — that one marks membership a
        rule must refuse, and feeding cross-board names into it would make every
        member rule report UNKNOWN on every multi-board project (041 §1's
        compatibility ruling).
        """
        edges: list[UnprovenNetEdge] = []
        for members in self.cross_board_net_instances().values():
            for position, first in enumerate(members):
                for second in members[position + 1:]:
                    edges.append(UnprovenNetEdge(first, second))
        return tuple(edges)

    def non_addressable_pages(self) -> tuple[tuple[str, str], ...]:
        """``(page_uuid, board_title)`` for pages that belong to no board (041 §1).

        Disclosure only. A page whose ``schematic`` reference dangles lands in the
        empty-uuid ``unattached`` group, so it is not an addressable board: it
        takes part in no instance and no edge, and a declaration file may not name
        it (S2). Listing it is the honest alternative to picking a board for it —
        and no id is minted for the guess.

        Empty for a single-board project: there an empty uuid is the **implicit**
        board (a project that declares no BOARD document), which has no
        cross-board question to disclose. Empty as well when every board is a real
        one, which is what the two real multi-board fixtures are.
        """
        if len(self.boards) < 2:
            return ()
        return tuple(
            (page_uuid, board_model.board.title)
            for board_model in self.boards
            if not board_model.board.uuid
            for page_uuid in board_model.board.page_uuids
        )

    # --- single-board façade (refuses a multi-board project by name) --------

    def single_board(self) -> BoardModel:
        """The project's one board, or :class:`MultiBoardProjectError`."""
        if len(self.boards) != 1:
            raise MultiBoardProjectError(
                f"this project has {len(self.boards)} boards "
                f"({', '.join(self.board_titles()) or 'none'}) — ask for a board "
                "model instead of reading the project as one"
            )
        return self.boards[0]

    @property
    def components(self) -> dict[str, Component]:
        """The one board's components (040b façade; refuses a multi-board project)."""
        return self.single_board().components

    @property
    def nets(self) -> dict[str, Net]:
        """The one board's nets (040b façade)."""
        return self.single_board().nets

    @property
    def raw(self) -> dict[str, Any]:
        """The one board's raw blocks (040b façade)."""
        return self.single_board().raw

    @property
    def duplicate_designators(self) -> list[str]:
        """The one board's same-page repeats (040b façade)."""
        return self.single_board().duplicate_designators

    @property
    def cross_page_designators(self) -> dict[str, list[str]]:
        """The one board's several-page repeats (040b façade)."""
        return self.single_board().cross_page_designators

    @property
    def unproven_nets(self) -> dict[str, tuple[str, ...]]:
        """The project's welded net names — empty unless it is one merged board.

        Not the raising façade the fields above use, deliberately: a **multi-board
        project** has nothing welded *within* this legacy page-merge channel,
        because the container's own document chain attributes every page to a
        board (:func:`boardwise.parsers.schematic.board_partition`), so each
        board's netlist is its own. The separate :attr:`unproven_edges` channel
        says which cross-board ties remain unproven; it never feeds these legacy
        rule refusals. And the rules are handed whatever model the caller has, so
        a read that cannot answer "unproven?" must answer "no" rather than raise
        out of a rule run.
        """
        if len(self.boards) != 1:
            return {}
        return self.boards[0].unproven_nets

    def unproven_pages(self, name: str | None) -> tuple[str, ...] | None:
        """As :meth:`DesignModel.unproven_pages`, on the project's one board.

        ``None`` for a multi-board project: each net is attributed and proven
        **within its own board**; cross-board ties are not answered here.
        """
        if len(self.boards) != 1:
            return None
        return self.boards[0].unproven_pages(name)

    @property
    def unproven_reasons(self) -> dict[str, tuple[str, str]]:
        """The one board's reasons for its unproven names — ``{}`` if many."""
        if len(self.boards) != 1:
            return {}
        return self.boards[0].unproven_reasons

    def unproven_reason(self, name: str | None) -> tuple[str, str]:
        """As :meth:`DesignModel.unproven_reason`, on the project's one board.

        ``WELDED_BY_NAME`` for a multi-board project, like every net there.
        """
        if len(self.boards) != 1:
            return (WELDED_BY_NAME, "")
        return self.boards[0].unproven_reason(name)
