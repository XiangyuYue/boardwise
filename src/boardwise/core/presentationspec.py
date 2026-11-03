"""PresentationSpec: how a circuit should **read** (053 stage A, 052 sec.4).

The second contract. The same netlist has many electrically equivalent drawings,
and this is the one that says which expression the author wants: which parts
form a module, which chain is the main path, which ports the circuit exposes,
which drawing grammar applies, where labels are allowed instead of wires, and
where the engineer has already decided a part's place.

Two properties are enforced here rather than trusted:

* **The model entry point does not accept coordinates.** The only place a
  coordinate may appear in this document is :attr:`PresentationSpec.user_locks`
  (an engineer's decision). Anywhere else — a `parts` entry carrying an `x`, a
  `wirePoints` list, a connector action — is refused by :func:`_refuse_coordinates`
  **before** anything is parsed, so the answer is a refusal and not a silent
  clean-up (052 sec.4: "默认模型入口不接受原始坐标、wire points 和 connector
  动作；工程师显式锁定或手工编辑仍有合法入口").
* **The label policy's hard-coded half.** 053 sec.7: "标签策略硬编码：局部直连
  义务优先，跨模块/高扇出才许标签". So `local` may only be `wire`; the two
  outer cases may be `wire` (a stricter choice) or `label`.

**The one stated exception to "a local net is wired"** is
`localLabelObligations`: a net the author *names* is expressed by a name at each
of its pins even inside a single module. It is a per-net exemption, not a second
label policy — `labelPolicy.local` is still `wire` for every net nobody named —
and the reason it has to exist is physical: a reversible connector's pins are
mirrored, and a wire between two of them is the U-line crossing that makes the
drawing lie about which pin is which (the Type-C case). One entry lists the nets
(`nets`) and says why (`note`); duplicate declarations are refused because two
entries for one net would be two intents for one drawing. Like `flow`, the key
is written only when stated, so every document that says nothing about it keeps
its digest — and therefore every plan compiled from it.

**A module is a group on a page, and a page holds several of them.** The module
list is not decoration: the phase-C page compiler (056) compiles *each module on
its own* — as a call to the single-module pipeline — and places the resulting
frames on the page. So a module may state the two things that are true of one
group and not of the page:

* `grammar_ref` — which drawing grammar the module follows. A single-grammar
  page states it once at the top; a page that mixes an LDO with a divider states
  it per module, and a module that states none inherits the document's.
* `presentation` — the module's own overrides, of which this build reads
  `sidePreferences`: the sides a grammar should read along are a property of the
  *symbols in that group* (the repo's measured AMS1117 puts its input and output
  on the same side), and one page can hold a group whose symbols want the
  default sides and one whose symbols do not.

`flow` is the module-level main-flow partial order — "this group feeds that
one". It is a **soft** reading aid and never a hard constraint: the page
compiler places modules in an order that respects it, and a diagram that
contradicts it is a ranking loss rather than a refusal. The two forms are the
plain pair (``["pwr", "sense"]``) and the object
(``{"from": "pwr", "to": "sense", "mainPath": true}``); `mainPath` marks the
edge the reader is meant to follow, which is the one edge the page may draw as a
*whole wire* across the module boundary instead of naming it at both ends.

What this module deliberately does **not** check: that `modules[*].parts`,
`flow` endpoints, `mainPaths` steps and `userLocks[*].partId` name parts and
modules that exist. Those are CircuitSpec facts (and module-name facts), and the
cross-check belongs to whoever holds both documents — the phase-B compiler and,
for modules, the page compiler. Validating them here would either duplicate the
circuit schema in this file or accept a document that silently refers to nothing.

`islands` is the one group this file *does* check, and for the opposite reason:
its facts are **this document's own** (which of the parts the modules name sits
in which block) and nothing outside can decide them. The reading lives in
`islands.py` — this file holds the key, the field and the boundary — because a
block that a spec states as data is not a block the layout has to invent.

**Serialisation stays byte-stable for a document that says nothing new.** The
`grammarRef` / `presentation` / `branchOrder` keys of a module and the top-level
`flow` list are written **only when stated**, because a LayoutPlan's geometry
digest pins the presentation digest: an untouched 053 spec has to hash — and
therefore compile — to exactly the plan it did before this batch. The fields are
additions, not changes: absent reads as "this module inherits" (or, for the
order, "no order stated"), and a page that declares no flow is the page whose
modules are read in name order. `islands` (520j) is an addition on the same
terms: a spec that states none serialises exactly as it did before the key
existed, and is read as one implicit island holding every part.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .circuitspec import PORT_DIRECTIONS
from .islands import (
    IslandError,
    LayoutIsland,
    declared_part_ids,
    implicit_island,
    parse_islands,
    validate_archipelago_structure,
)
from .symbolprofile import POSE_ROTATIONS

__all__ = [
    "DEFAULT_SIDE_PREFERENCES",
    "GRAMMARS",
    "LABEL_LABEL",
    "LABEL_MODES",
    "LABEL_ROW_MODELS",
    "LABEL_ROW_MODEL_ANCHORED",
    "LABEL_ROW_MODEL_CENTERED",
    "LABEL_STUB_AUTO",
    "LABEL_STUB_MODES",
    "LABEL_STUB_STRAIGHT",
    "LABEL_WIRE",
    "LOCK_SCOPES",
    "LOCK_SCOPE_MODULE",
    "LOCK_SCOPE_PAGE",
    "MODULE_PRESENTATION_KEYS",
    "PATH_STEP_NET",
    "PATH_STEP_PART",
    "PRESENTATION_SPEC_KIND",
    "PRESENTATION_SPEC_VERSION",
    "SERVICE_LAYOUT_KEYS",
    "SIDES",
    "_FLOW_EDGE_KEYS",
    "DirectWiringObligation",
    "FlowEdge",
    "LabelPolicy",
    "LayoutIsland",
    "LocalLabelObligation",
    "PresentationModule",
    "PresentationPath",
    "PresentationSpec",
    "PresentationSpecError",
    "ServiceLayout",
    "UserLock",
    "main_path_wire",
    "presentation_sha256",
]

#: Identifies the document; see `circuitspec.CIRCUIT_SPEC_KIND` for the rule.
PRESENTATION_SPEC_KIND = "boardwise-presentation-spec"

#: Same rule as `changeplan.PLAN_VERSION`: a stated version this build does not
#: have is refused rather than guessed at.
PRESENTATION_SPEC_VERSION = 1

#: The drawing grammars this build knows (053 sec.2 — "本批只认这三个字面量", 088
#: adds the fourth, `power-entry`, and 098 the fifth, `ic-periphery`). Empty means
#: the spec does not choose one; a literal that is not in this tuple is a refusal,
#: not a fallback to a generic layout: a grammar is a set of promises about what
#: will be visible, and pretending to keep promises nobody wrote is worse than
#: saying the grammar is not known.
GRAMMARS: tuple[str, ...] = (
    "voltage-divider", "rc-lowpass", "ldo", "power-entry", "ic-periphery",
    "flyback",
)

#: How a net may be expressed locally (052 sec.5: a key local topology is drawn
#: as wire; a label across modules or at high fan-out).
LABEL_WIRE = "wire"
LABEL_LABEL = "label"
LABEL_MODES: tuple[str, ...] = (LABEL_WIRE, LABEL_LABEL)

#: How a label's name stub leaves its pin. ``auto`` is the historical ladder
#: (straight, then a one-step-aside bend when every straight rung is blocked).
#: ``straight`` is the V4/534B policy: the text box is pushed out along the
#: pin's own escape direction first, and a bent carrier is not a substitute for
#: a straight one. It is opt-in so existing documents keep their geometry.
LABEL_STUB_AUTO = "auto"
LABEL_STUB_STRAIGHT = "straight"
LABEL_STUB_MODES: tuple[str, ...] = (LABEL_STUB_AUTO, LABEL_STUB_STRAIGHT)

#: Where the host prints a label's **name row** relative to the stub's anchor
#: (534 r25, 053f). ``anchored`` is the historical reading — the row buys its ink
#: above the anchor (``textmetrics.wire_name_box``: ``y .. y + WIRE_NAME_ROW``
#: for a horizontal run) — and it is the default precisely because it is what
#: every document written before this key was drawn with. ``centered`` is the
#: 534 r25 measurement (the host's own netlabel row sits centred on the anchor,
#: `(591,735.5)-(615,744.5)` about `y = 740`), opt-in so that a page which wants
#: the measured row states it instead of inheriting it.
LABEL_ROW_MODEL_ANCHORED = "anchored"
LABEL_ROW_MODEL_CENTERED = "centered"
LABEL_ROW_MODELS: tuple[str, ...] = (
    LABEL_ROW_MODEL_ANCHORED, LABEL_ROW_MODEL_CENTERED,
)

#: The one key `gndClustering` carries (053f): the neighbourhood radius a
#: ground's pads are grouped by. The object is closed for the same reason every
#: other schema here is — a key nobody reads is an intent nobody honours.
GND_CLUSTERING_KEYS: tuple[str, ...] = ("radius",)

#: The one key `serviceLayout` carries (543B): the distance a uniquely served
#: shunt keeps from the host pin it serves. Closed like every other object here.
SERVICE_LAYOUT_KEYS: tuple[str, ...] = ("pinGap",)

#: The four sides a preference may name. Preferences are defaults; a user lock
#: wins over them (053 sec.2: "默认可被锁定覆盖").
SIDES: tuple[str, ...] = ("left", "right", "top", "bottom")

#: The four sides a part's own reference/value rows may be declared on (053d).
#: The vocabulary is the compiler's, not :data:`SIDES`': it is handed straight to
#: `drawcompiler._line_boxes`, which names its sides ``above``/``below`` too. A
#: part's text is one **block** — the reference and the value move *together* —
#: so this names a side, never a place per line.
PART_TEXT_SIDES: tuple[str, ...] = ("above", "below", "left", "right")

#: The one non-default value of the top-level `textPlacement` switch (053S).
#: ``native-attr`` says "place this drawing's text with the host's attribute API
#: where the layout put it, instead of trusting the host's own anchors". Absent
#: means the historical reading — the key is not written at all and no plan
#: carries `attributeMoves`.
TEXT_PLACEMENT_NATIVE = "native-attr"
TEXT_PLACEMENTS: tuple[str, ...] = (TEXT_PLACEMENT_NATIVE,)

#: The book's defaults: an input enters from the left, an output leaves to the
#: right, a rail is above and ground below. Defaults, not rules — 052 sec.6 says
#: outright that "all signals left to right" is not a global law.
DEFAULT_SIDE_PREFERENCES: dict[str, str] = {
    "input": "left",
    "output": "right",
    "power": "top",
    "gnd": "bottom",
}

#: A path step names what it is: a chain mixes parts and nets, and an untyped
#: string would leave the reader guessing which of the two an id is.
PATH_STEP_PART = "part:"
PATH_STEP_NET = "net:"

_TOP_KEYS = (
    "kind",
    "specVersion",
    "modules",
    "islands",
    "flow",
    "moduleOrder",
    "moduleColumns",
    "flagLeadLimit",
    "gndClustering",
    "serviceLayout",
    "mainPaths",
    "feedbackPaths",
    "portRoles",
    "grammarRef",
    "directWiringObligations",
    "localLabelObligations",
    "labelPolicy",
    "sidePreferences",
    "userLocks",
    "partTexts",
    "textPlacement",
)
_MODULE_KEYS = (
    "id", "parts", "role", "grammarRef", "presentation", "branchOrder", "core",
    "attach",
)
#: The sides a module may be attached to its host on (053c), and the two nested
#: defaults. `bottom` is the decoupling row's side — a block of capacitors under
#: the IC is what a reader expects — and 10 units is a visible but close gap.
#: An attach pair is placed at that declared `gap` and is **exempt** from the
#: page's own module gap; every other pair of frames keeps it, and two frames
#: that share area are still refused (053K; see
#: `pagecompiler._attach_shift` and `readability._check_frame_separation`).
ATTACH_SIDES: tuple[str, ...] = ("bottom", "top", "left", "right")
ATTACH_SIDE_DEFAULT = "bottom"
ATTACH_GAP_DEFAULT = 10.0
_ATTACH_KEYS = ("to", "side", "gap")
#: What a module's own `presentation` object may override. Closed for the same
#: reason every schema here is closed: a key this build does not read would be
#: an intent nobody honours. The side preferences are the ones a *group's
#: symbols* decide; `userLocks` and the label policy are page-wide facts.
MODULE_PRESENTATION_KEYS = ("sidePreferences",)
_PATH_KEYS = ("id", "chain", "note")
_FLOW_EDGE_KEYS = ("from", "to", "mainPath")
_OBLIGATION_KEYS = ("nets", "note")
_LABEL_POLICY_KEYS = ("local", "crossModule", "highFanout", "stub", "stubMin", "rowModel")
_LOCK_KEYS = ("partId", "x", "y", "rotation", "scope")

#: What a lock's coordinates are relative to (057 sec.3). ``module`` — the
#: default, and the only reading before 057 — is the module's own drawing: the
#: page translates the lock with its module. ``page`` pins the part to a point
#: of the *page*: the page compiler derives the module's origin from it.
LOCK_SCOPE_MODULE = "module"
LOCK_SCOPE_PAGE = "page"
LOCK_SCOPES: tuple[str, ...] = (LOCK_SCOPE_MODULE, LOCK_SCOPE_PAGE)

#: Keys that mean "a place on the canvas" — refused everywhere except inside a
#: `userLocks` entry (052 sec.4).
_COORDINATE_KEYS = frozenset({
    "x", "y", "rotation", "angle", "mirror", "isMirror", "dx", "dy",
    "x1", "y1", "x2", "y2",
    "points", "point", "wirePoints", "polyline", "waypoints", "route",
    "segments", "junctions", "bbox", "at", "anchor",
    "connectorAction", "connectorActions", "actions", "primitiveId",
})


class PresentationSpecError(ValueError):
    """The presentation spec is not one this build can read."""


@dataclass
class PresentationModule:
    """One functional group: its parts, what the group is for, and how it draws.

    The module is what makes "电容归侧" decidable — a decoupling capacitor and
    the IC it belongs to are one group, and a group has one place on the page.
    It is also the unit the page compiler (056) compiles: each module goes
    through the single-module pipeline on its own, so the two fields below are
    *this group's* answers rather than the page's.

    ``grammar_ref`` empty means "the document's grammar"; ``side_preferences``
    empty means "the document's sides". Both are overrides, and both are
    per-group because both are properties of the symbols in the group (053
    sec.3's measured AMS1117 needs a non-default output side; a divider's
    default sides are fine) rather than of the page they sit on.

    ``branch_order`` is the group's own statement of the order its parallel
    branches are drawn in, **from the inlet end outwards** — 088b §二, 岳
    2026-10-02: a TVS belongs nearest the inlet so a spike is clamped before it
    reaches anything else, and *which* part is the TVS is a fact about values and
    packages, which no grammar may read (053 sec.6). So the order is declared
    here and the grammar only carries it out (see `power_entry`): the document
    states the intent, the grammar keeps the evidence. Empty means "no order
    stated" — the drawing then keeps 088's designator order, and a document that
    states nothing serialises exactly as it did before this field existed.

    ``core`` is the group's own statement of **which part the drawing is arranged
    around** (098 §一) — the one fact a grammar cannot derive from the partition,
    because every part of a module is a shape with pins and nothing about the
    connections says which of them the others hang off. It is an optional key for
    the same reason `branch_order` is: absent means "not stated" (the grammar then
    reads the intent, then the partition, and refuses when none of them answers), a
    key this build does not read would be an intent nobody honours, and a document
    that states nothing serialises exactly as it did before the field existed —
    same bytes, same digest, same plan.
    """

    id: str
    parts: list[str] = field(default_factory=list)
    role: str = ""
    grammar_ref: str = ""
    side_preferences: dict[str, str] = field(default_factory=dict)
    branch_order: list[str] = field(default_factory=list)
    core: str = ""
    attach: "ModuleAttach | None" = None


@dataclass(frozen=True)
class ModuleAttach:
    """Place this module **beside** its host on the page instead of on its own (053c).

    The page compiler places every module it is given on its own grid slot, which
    is right for a USB inlet and wrong for a decoupling block: the block belongs
    to the IC's island, and a grid slot far from the IC is exactly what makes the
    page read as two drawings. ``attach`` says so in the document: the page lays
    the host out first and puts this module against the named side of the host's
    *placed* frame, keeping ``gap`` canvas units between the two frames. It is a
    placement statement and nothing else — the two modules stay two modules
    (their own drawings, their own frames, their own entry in `page.modules`),
    and every net between them is still stated the way any cross-module net is
    (a flag or a label at each end), never as a page-drawn wire.

    ``to`` is required and must name another module of the same document; a
    module may not attach to itself, one host may carry at most one attached
    module, and an attached module may not itself be a host — the relation is one
    level deep, refused at parse time rather than drawn half-way.
    """

    to: str
    side: str = ATTACH_SIDE_DEFAULT
    gap: float = ATTACH_GAP_DEFAULT


@dataclass(frozen=True)
class FlowEdge:
    """One module-level flow direction: ``from`` feeds ``to`` (056 sec.1).

    A partial order, not a path: the page compiler places the modules in an
    order that respects every edge, and a page that states no edge is read in
    module-name order. ``main_path`` marks the edge the reader is meant to
    follow — the one case where the cross-module connection may be drawn as a
    whole wire instead of naming the net at both ends (056 sec.2).
    """

    from_module: str
    to_module: str
    main_path: bool = False


@dataclass
class PresentationPath:
    """A chain the drawing must keep recognisable (main or feedback path).

    ``chain`` is ordered and typed: ``"net:VIN"``, ``"part:R1"``, ``"part:C1"``…
    The order is the electrical direction the reader should follow, which is the
    whole point of declaring it — 052 sec.6: a feedback channel stays visible,
    it is not flattened into an acyclic left-to-right picture.
    """

    id: str = ""
    chain: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class DirectWiringObligation:
    """A local topology that must be **wired**, not expressed with a label.

    052 sec.5: "关键局部拓扑优先直连". Stated per net because the label decision
    is made per net; a pin-level obligation would be a second way of saying it,
    checked against nothing this document carries.
    """

    nets: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class LocalLabelObligation:
    """A net that must be **named at each of its pins**, even inside one module.

    The exception 053 sec.7's hard-coded rule needs and cannot state: "a key
    local topology is drawn as a wire" is right for almost every local net, and
    wrong for the one the author *names* — a reversible connector's mirrored
    pins, where a wire between two of them is a U-line crossing that says the
    wrong pin is the right one. It is a per-net exemption, **not** a second
    label policy: `labelPolicy.local` stays `wire` for every net nobody named
    here, and a power or ground net may never be listed (a rail is a flag —
    069 sec.7).

    Stated per net for the same reason `DirectWiringObligation` is: the label
    decision is per net, and a pin-level obligation would be a second way of
    saying it that nothing in this document checks.
    """

    nets: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class LabelPolicy:
    """When a label may stand in for a wire (053 sec.2, hard-coded in sec.7).

    ``local`` is ``wire`` and stays ``wire``: a key local topology is drawn as a
    wire, and the label exceptions are the two outer cases plus the nets the
    document **names** in `localLabelObligations` — that key is where a stated
    local exception lives, not this policy (so a net nobody named cannot become
    a label by asking this object).
    """

    local: str = LABEL_WIRE
    cross_module: str = LABEL_LABEL
    high_fanout: str = LABEL_LABEL
    #: ``auto`` keeps 057/099f's straight-then-bent ladder; ``straight`` makes
    #: the compiler reserve the text box on the pin's own escape ray and refuse
    #: to fall back to a bent stub. Default ``auto`` preserves every existing
    #: document byte for byte.
    stub: str = LABEL_STUB_AUTO
    #: The shortest name stub a label may leave its pin on (053f). ``0`` is the
    #: historical ladder, whose first rung is 057's two-lattice-step run; a
    #: positive value raises that rung (536 measured 60 as the spacing the
    #: reference board reads at). It travels to
    #: :attr:`~boardwise.core.layoutplan.LayoutLabel.stub_min`, where
    #: `drawapply._label_stub_candidates` reads it.
    stub_min: float = 0.0
    #: ``anchored`` (default, the historical row above the anchor) or
    #: ``centered`` (534 r25's measured row). Travels to
    #: :attr:`~boardwise.core.layoutplan.LayoutLabel.row_model`.
    row_model: str = LABEL_ROW_MODEL_ANCHORED


@dataclass
class UserLock:
    """A part the engineer has already placed (052 sec.4).

    The one legitimate coordinate in this document, and the one input the
    compiler may not quietly ignore: 053 sec.5 scenario 12 requires a lock that
    conflicts with the grammar to be *reported*, never dropped.

    ``scope`` says what ``x``/``y`` are measured in (057 sec.3):

    * ``module`` (the default, and every lock written before 057) — the
      module's own drawing. The page translates the lock with its module;
      ``rotation`` is part of the lock.
    * ``page`` — the page itself. The part lands at exactly ``(x, y)`` in every
      page candidate, and the page compiler derives the module's origin from it
      (``origin = P − L(generation)``). A page lock pins a **position**: the
      part's pose is its module's drawing (a module lock states it), so a page
      lock carries no rotation.

    One part may carry one lock of each scope: the module lock arranges the part
    inside its module, the page lock puts that arrangement on the page.
    """

    part_id: str
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    scope: str = LOCK_SCOPE_MODULE

    @property
    def is_page(self) -> bool:
        return self.scope == LOCK_SCOPE_PAGE


@dataclass(frozen=True)
class ServiceLayout:
    """How close a uniquely served shunt sits to its host's supply pin (543B).

    This is a **construction interval**, not a coordinate: the compiler still
    decides the side and the pose from the symbol, the relations and the net
    partition. ``pin_gap`` is the distance the shunt's service pin keeps from
    the host pin it serves, and it is read only when

    * the presentation states the key (an absent key keeps every old document's
      bytes, digest and drawing), and
    * the 543A service relation for that part is resolved, the host is the
      branch's owner, the served net is the branch's shared net, and the host
      has **exactly one** pin on it.

    An ambiguous relation, several hosts or several equivalent host pins are
    left alone: this key states a distance, not a licence to guess.
    """

    #: The service pin's distance from the host pin, in canvas units (> 0).
    pin_gap: float


@dataclass
class PresentationSpec:
    """The whole presentation intent, in normal form."""

    modules: list[PresentationModule] = field(default_factory=list)
    #: The layout islands the page is arranged in (520j,
    #: `docs/multi-island-design.md`). ``None`` means **the document states
    #: none**, which reads as one implicit island holding every part — a spec
    #: that says nothing about islands is a spec whose layout is what it always
    #: was, and that is a promise this field keeps rather than a convention
    #: downstream code has to remember (ask
    #: :meth:`effective_islands`, never test for `None`). Declaring islands is
    #: the only thing that switches multi-island layout on, and it is read by
    #: the layout layer only — `modules` keeps its own meaning (a
    #: grammar-binding scope) and is not a second way of stating this.
    islands: list[LayoutIsland] | None = None
    #: Module-level flow directions (056 sec.1). A partial order over module ids:
    #: the page compiler reads it to order the page and to find the edges it may
    #: wire as one whole connection. Empty = read the modules in name order.
    flow: list[FlowEdge] = field(default_factory=list)
    #: The page's module placement order, left-to-right / top-to-bottom. Empty
    #: means "derive it from `flow`, then module name" — the historical reading.
    #: Stating it is a layout statement, not a circuit one: decoupling islands can
    #: be placed beside the IC they serve without pretending they are a signal
    #: stage. Must be a permutation of `modules`.
    module_order: list[str] = field(default_factory=list)
    #: The number of module columns the page's placement search must use. ``0``
    #: keeps the historical auto-search (one column through N); a positive value
    #: states the grid shape, so a row of satellites can sit beside its core on
    #: the same row instead of being pushed to a second row.
    module_columns: int = 0
    #: The farthest a power/ground flag lead may reach from its pad. ``0`` keeps
    #: the compiler's 60-unit default; a crowded core states a longer lead so its
    #: flag can leave the label lane without crossing a conductor.
    flag_lead_limit: float = 0.0
    #: The radius a **ground's** pads are grouped by, in canvas units (053f).
    #: ``0`` means the document states no clustering, and the compiler then draws
    #: every ground exactly as it did before 535 existed — one rail, one flag.
    #: A positive value switches `drawcompiler`'s neighbourhood split on and is
    #: what `gndClustering` writes.
    gnd_cluster_radius: float = 0.0
    #: 543B's construction interval for a **uniquely served** shunt: ``None``
    #: (every document written before this key, and the default) keeps the
    #: compiler's branch ladder exactly as it was. A stated value asks the
    #: branch that 543A resolved to place its service pin ``pin_gap`` away from
    #: the one host pin it serves; it is not written unless stated, so old
    #: digests and drawings do not move.
    service_layout: "ServiceLayout | None" = None
    main_paths: list[PresentationPath] = field(default_factory=list)
    feedback_paths: list[PresentationPath] = field(default_factory=list)
    #: net id -> one of :data:`PORT_DIRECTIONS`. The same vocabulary the
    #: CircuitSpec's `openInterfaces` uses, defined once in `circuitspec.py`.
    port_roles: dict[str, str] = field(default_factory=dict)
    #: Which grammar the drawing follows, or "" when the spec does not choose.
    grammar_ref: str = ""
    direct_wiring_obligations: list[DirectWiringObligation] = field(default_factory=list)
    #: The stated exception to "a local net is wired": nets named here are
    #: expressed by a label at each pin even inside one module
    #: (:class:`LocalLabelObligation`). Empty = the document states none, which
    #: is the rule every spec written before this key followed.
    local_label_obligations: list[LocalLabelObligation] = field(default_factory=list)
    label_policy: LabelPolicy = field(default_factory=LabelPolicy)
    side_preferences: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_SIDE_PREFERENCES)
    )
    user_locks: list[UserLock] = field(default_factory=list)
    #: part id -> the side its reference/value rows are declared on (053d). The
    #: two rows are one block and move together; declaring a side only says
    #: *where to try first* — when every rung there is blocked the compiler
    #: falls back to its own ladder, so a stated side can never make a drawing
    #: worse than the one this key did not exist for. Empty = the historical
    #: reading, and the key is then not written at all.
    part_texts: dict[str, str] = field(default_factory=dict)
    #: How the drawing's text gets onto the canvas (053S). ``""`` — the default
    #: and the only reading before this key existed — leaves every text where the
    #: host draws it. :data:`TEXT_PLACEMENT_NATIVE` asks the landing to move each
    #: reference/value and each label wire's name to the box the layout reserved,
    #: through the host's attribute API (`attributeMoves`). A host or connector
    #: without that API refuses before writing a part, so stating it can never
    #: silently fall back to a drawing nobody asked for.
    text_placement: str = ""
    spec_version: int = PRESENTATION_SPEC_VERSION

    # ------------------------------------------------------------ derived

    @property
    def is_archipelago(self) -> bool:
        """Are these islands the 536 archipelago reading?

        Decided by the islands' own new fields (``group`` / ``owner`` / ``kind`` /
        ``side``) and nothing else: a list that states any of them is the reading
        :func:`boardwise.core.islands.parse_islands` accepted as an archipelago,
        and a list that states none of them is the 520j reading — the implicit
        single island, or old-style declared islands — exactly as before.

        It is **derived**, not a document key: nothing serialises it, so asking
        changes no byte of any spec (an old document keeps its digest, and with it
        every plan compiled from it), and a spec built by hand in memory answers
        the same way as one read from a file.
        """
        return any(
            island.group or island.owner or island.kind or island.side
            for island in (self.islands or ())
        )

    def locked_part_ids(self) -> list[str]:
        return [lock.part_id for lock in self.user_locks]

    def page_locks(self) -> list[UserLock]:
        """The locks measured on the page (057 sec.3), in document order."""
        return [lock for lock in self.user_locks if lock.is_page]

    def side_for(self, role: str) -> str:
        """The preferred side for a role, or "" when the spec has no preference."""
        return self.side_preferences.get(role, "")

    def module(self, module_id: str) -> PresentationModule | None:
        """The module with this id, or ``None``."""
        for item in self.modules:
            if item.id == module_id:
                return item
        return None

    def modules_of_part(self, part_id: str) -> list[str]:
        """Every module that claims this part — one, none, or the contradiction."""
        return [item.id for item in self.modules if part_id in item.parts]

    def declared_part_ids(self) -> list[str]:
        """Every part this document names, in first-mention order, no repeats.

        The parts come from the modules — that is where a presentation spec
        names its parts — and this is the reference set the island partition is
        checked against (520j). One definition, used by the parse
        (:func:`boardwise.core.islands.parse_islands`) and by
        :meth:`effective_islands`, so the implicit island and the rule that
        refuses an incomplete partition cannot disagree about which parts exist.
        """
        return declared_part_ids(module.parts for module in self.modules)

    def effective_islands(self) -> list[LayoutIsland]:
        """The islands the layout reads: the declared ones, or the implicit one.

        A spec that states no `islands` is a spec whose parts are **one block** —
        the default this batch exists to preserve. Returning that as a real
        island rather than as `None` is the whole point of the method: every
        consumer gets one shape, so no consumer can forget the case, and the
        single-island path is the same code as the multi-island one.
        """
        if self.islands is not None:
            return list(self.islands)
        return [implicit_island(self.declared_part_ids())]

    def island_of_part(self, part_id: str) -> str | None:
        """The island that owns this part, or ``None`` when none does."""
        for island in self.effective_islands():
            if part_id in island.parts:
                return island.id
        return None

    def sides_for_module(self, module: PresentationModule) -> dict[str, str]:
        """The sides a module draws with: the document's, overridden by its own."""
        merged = dict(self.side_preferences)
        merged.update(module.side_preferences)
        return merged

    def main_path_edges(self) -> list[FlowEdge]:
        """The flow edges marked `mainPath` (056 sec.2's whole-wire exception)."""
        return [edge for edge in self.flow if edge.main_path]

    # --------------------------------------------------------------- JSON

    def to_jsonable(self) -> dict[str, Any]:
        """Coordinates appear exactly once, under `userLocks`.

        The per-module `grammarRef` / `presentation` and the top-level `flow`
        are written **only when stated**: a document that says nothing new
        serialises exactly as it did before the page layer existed, which is what
        keeps an existing spec's digest (and therefore every plan compiled from
        it) byte-identical (053B's scene hashes are a contract). `islands`
        follows the same rule for the same reason (520j): a spec that states no
        islands hashes — and therefore compiles — to exactly what it did before
        this key existed.

        An **archipelago** is checked against
        :func:`boardwise.core.islands.validate_archipelago_structure` first, so a
        spec that only half-stamps its islands (or mixes the two readings) is
        refused here rather than written out as JSON its own
        :meth:`from_dict` would reject. Legacy specs get no new check: their
        islands are the 520j reading and this batch changes no byte of them.
        """
        if self.is_archipelago:
            try:
                validate_archipelago_structure(self.modules, self.islands or ())
            except IslandError as exc:
                raise PresentationSpecError(f"$.{exc}") from exc
        return {
            "kind": PRESENTATION_SPEC_KIND,
            "specVersion": self.spec_version,
            "modules": [_module_json(module) for module in self.modules],
            **(
                {"islands": [_island_json(island) for island in self.islands]}
                if self.islands is not None
                else {}
            ),
            **(
                {"flow": [
                    {"from": edge.from_module, "to": edge.to_module,
                     "mainPath": edge.main_path}
                    for edge in self.flow
                ]}
                if self.flow
                else {}
            ),
            **(
                {"moduleOrder": list(self.module_order)}
                if self.module_order
                else {}
            ),
            **(
                {"moduleColumns": self.module_columns}
                if self.module_columns
                else {}
            ),
            **(
                {"flagLeadLimit": self.flag_lead_limit}
                if self.flag_lead_limit
                else {}
            ),
            **(
                {"gndClustering": {"radius": self.gnd_cluster_radius}}
                if self.gnd_cluster_radius
                else {}
            ),
            # 543B: written only when stated, like every opt-in switch above —
            # an old document keeps its bytes, digest and drawing.
            **(
                {"serviceLayout": {"pinGap": self.service_layout.pin_gap}}
                if self.service_layout is not None
                else {}
            ),
            "mainPaths": [_path_json(path) for path in self.main_paths],
            "feedbackPaths": [_path_json(path) for path in self.feedback_paths],
            "portRoles": dict(self.port_roles),
            "grammarRef": self.grammar_ref,
            "directWiringObligations": [
                {"nets": list(item.nets), "note": item.note}
                for item in self.direct_wiring_obligations
            ],
            # Written only when stated: a spec that names no local-label
            # exception has to serialise exactly as it did before the key
            # existed, or the digest a plan pins would move under every
            # existing document.
            **(
                {"localLabelObligations": [
                    {"nets": list(item.nets), "note": item.note}
                    for item in self.local_label_obligations
                ]}
                if self.local_label_obligations
                else {}
            ),
            "labelPolicy": {
                "local": self.label_policy.local,
                "crossModule": self.label_policy.cross_module,
                "highFanout": self.label_policy.high_fanout,
                **(
                    {"stub": self.label_policy.stub}
                    if self.label_policy.stub != LABEL_STUB_AUTO
                    else {}
                ),
                # 053f: the two label switches are written only when stated —
                # a document that names no stub minimum and no row model has to
                # serialise exactly as it did before these keys existed.
                **(
                    {"stubMin": self.label_policy.stub_min}
                    if self.label_policy.stub_min
                    else {}
                ),
                **(
                    {"rowModel": self.label_policy.row_model}
                    if self.label_policy.row_model != LABEL_ROW_MODEL_ANCHORED
                    else {}
                ),
            },
            "sidePreferences": dict(self.side_preferences),
            "userLocks": [_lock_json(lock) for lock in self.user_locks],
            # Written only when stated (053d): a document that names no part text
            # side has to serialise exactly as it did before this key existed, or
            # the digest a plan pins would move under every existing document.
            **(
                {"partTexts": dict(self.part_texts)}
                if self.part_texts
                else {}
            ),
            # 053S: written only when stated, for the same reason every switch
            # above is — an old document keeps its digest, and with it every plan
            # compiled from it.
            **(
                {"textPlacement": self.text_placement}
                if self.text_placement
                else {}
            ),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> PresentationSpec:
        _refuse_coordinates(payload, "$")
        root = _object(payload, "$")
        _check_keys(root, _TOP_KEYS, "$")
        version = root.get("specVersion", PRESENTATION_SPEC_VERSION)
        if version != PRESENTATION_SPEC_VERSION:
            raise PresentationSpecError(
                f"$.specVersion is {version!r}, this build reads "
                f"{PRESENTATION_SPEC_VERSION} — regenerate the spec"
            )
        modules = _modules_from(root)
        # Islands after modules, and not merely in this order: an island's parts
        # are checked against the parts the modules name, so the modules have to
        # be read first. Nothing else in this parse depends on the order.
        return cls(
            modules=modules,
            islands=_islands_from(root, modules),
            flow=_flow_from(root),
            module_order=_module_order_from(root, modules),
            module_columns=_module_columns(root),
            flag_lead_limit=_flag_lead_limit(root),
            gnd_cluster_radius=_gnd_clustering(root),
            service_layout=_service_layout(root),
            main_paths=_paths_from(root, "mainPaths"),
            feedback_paths=_paths_from(root, "feedbackPaths"),
            port_roles=_port_roles(root),
            grammar_ref=_grammar(root),
            direct_wiring_obligations=_obligations_from(root),
            local_label_obligations=_local_labels_from(root),
            label_policy=_label_policy(root),
            side_preferences=_side_preferences(root),
            user_locks=_locks_from(root),
            part_texts=_part_texts_from(root, modules),
            text_placement=_text_placement(root),
        )

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_jsonable(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> PresentationSpec:
        """Read a spec file. Every failure is a :class:`PresentationSpecError`."""
        source = Path(path)
        try:
            text = source.read_text(encoding="utf-8")
        except OSError as exc:
            raise PresentationSpecError(f"{source}: cannot be read ({exc})") from exc
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise PresentationSpecError(f"{source}: is not JSON ({exc})") from exc
        try:
            return cls.from_dict(payload)
        except PresentationSpecError as exc:
            raise PresentationSpecError(f"{source}: {exc}") from exc

    def sha256(self) -> str:
        """Digest of the canonical form — the second hash a LayoutPlan pins."""
        return presentation_sha256(self)


def presentation_sha256(spec: PresentationSpec) -> str:
    """sha256 of the spec's canonical JSON (see :func:`circuitspec.spec_sha256`)."""
    text = json.dumps(
        spec.to_jsonable(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main_path_wire(
    spec: PresentationSpec, net_class: str | None, modules: Sequence[str]
) -> bool:
    """Is this crossing net **one whole wire** on the page, rather than a name?

    A net that crosses a module boundary is stated by its name at both ends — a
    flag for a ground or a rail, a label otherwise (:class:`LabelPolicy`'s
    ``crossModule``). The one exception is the flow edge the presentation itself
    marks ``mainPath``: that mark asks for **one run** from port to port
    (056 sec.2), which a name at each end cannot keep. 069 sec.7 keeps a *rail*
    on the same terms — "a rail is a bus at any fan-out": the member count that
    used to decide it is gone, and the flag is what 岳 reads. A **ground is never
    a wire**, so a `mainPath` mark on one is refused and named rather than
    quietly downgraded (056 sec.3).

    This function is the **single source** of that decision (096), and the two
    callers ask it instead of keeping a copy: the page compiler picks each
    port's style with it (`pagecompiler._net_style`), and the page checker
    decides with it which cross-module wire may satisfy a ``mainPath`` edge
    (`readability._check_main_paths`). The copy the checker used to keep —
    "`power` with more than `high_fanout` members is a bus" — is exactly what
    made the same net a wire to the compiler and a bus to the checker, so a
    four-member rail marked `mainPath` was drawn as a wire and refused in the
    same pass.

    ``modules`` are the modules that own the net (the rule needs exactly two),
    and ``net_class`` is the net's class in the circuit — ``None`` for a net the
    circuit does not state, which the compiler refuses elsewhere rather than
    here.
    """
    if net_class == "gnd":
        return False
    pair = set(modules)
    return len(pair) == 2 and any(
        edge.main_path and {edge.from_module, edge.to_module} == pair
        for edge in spec.flow
    )


# ------------------------------------------------------------------ readers


def _path_json(path: PresentationPath) -> dict[str, Any]:
    return {"id": path.id, "chain": list(path.chain), "note": path.note}


def _lock_json(lock: UserLock) -> dict[str, Any]:
    """One lock, in the shape its scope has.

    A module lock serialises exactly as every lock did before 057 (no `scope`
    key): a spec that says nothing new keeps its digest, and with it every plan
    compiled from it (the same rule the module overrides and `flow` follow). A
    page lock states its scope and no rotation — it pins a position.
    """
    if lock.is_page:
        return {"partId": lock.part_id, "x": lock.x, "y": lock.y, "scope": lock.scope}
    return {
        "partId": lock.part_id,
        "x": lock.x,
        "y": lock.y,
        "rotation": lock.rotation,
    }


def _module_json(module: PresentationModule) -> dict[str, Any]:
    """One module, with its overrides written only when it states them."""
    out: dict[str, Any] = {
        "id": module.id, "parts": list(module.parts), "role": module.role,
    }
    if module.grammar_ref:
        out["grammarRef"] = module.grammar_ref
    if module.side_preferences:
        out["presentation"] = {"sidePreferences": dict(module.side_preferences)}
    if module.branch_order:
        out["branchOrder"] = list(module.branch_order)
    if module.core:
        out["core"] = module.core
    if module.attach is not None:
        out["attach"] = _attach_json(module.attach)
    return out


def _attach_json(attach: ModuleAttach) -> dict[str, Any]:
    """One attach, with its two defaults written only when they are stated.

    Same rule every optional key here follows: a document that says `{"to":
    "ch343"}` asked for the default side and gap, and writing them back would be
    a statement it never made — while a document that states neither the whole
    `attach` key nor its defaults keeps every byte it had before 053c.
    """
    out: dict[str, Any] = {"to": attach.to}
    if attach.side != ATTACH_SIDE_DEFAULT:
        out["side"] = attach.side
    if attach.gap != ATTACH_GAP_DEFAULT:
        out["gap"] = attach.gap
    return out


def _island_json(island: LayoutIsland) -> dict[str, Any]:
    """One island, with its optional fields written only when it states them.

    Same rule as a module's overrides: `role`, `name` and 536's archipelago keys
    (`group` / `owner` / `kind` / `side`) are optional, so an island that states
    none of them writes none of them and reads back as `""` — an old spec's
    islands stay byte-shaped exactly as before the archipelago fields existed.
    (A spec that states no islands at all writes no `islands` key — see
    :meth:`PresentationSpec.to_jsonable`.)
    """
    out: dict[str, Any] = {"id": island.id, "parts": list(island.parts)}
    if island.role:
        out["role"] = island.role
    if island.name:
        out["name"] = island.name
    if island.group:
        out["group"] = island.group
    if island.owner:
        out["owner"] = island.owner
    if island.kind:
        out["kind"] = island.kind
    if island.side:
        out["side"] = island.side
    return out


def _islands_from(
    root: dict[str, Any], modules: Sequence[PresentationModule]
) -> list[LayoutIsland] | None:
    """Read `islands`, or ``None`` for "this document states none".

    All of the reading is :func:`boardwise.core.islands.parse_islands`' — this
    function is the boundary that hands it the reference set (the parts the
    modules name), the modules themselves (536's archipelago check reads a child
    island's group, owner and core off them), and translates its refusal into
    this module's error, so a caller of :meth:`PresentationSpec.load` sees one
    error type whatever part of the document was wrong. ``None`` means the
    *implicit* island downstream, and never reaches further than
    :meth:`PresentationSpec.effective_islands`.
    """
    try:
        return parse_islands(
            root.get("islands"),
            declared_part_ids(m.parts for m in modules),
            modules=modules,
        )
    except IslandError as exc:
        raise PresentationSpecError(f"$.{exc}") from exc


def _modules_from(root: dict[str, Any]) -> list[PresentationModule]:
    out: list[PresentationModule] = []
    seen: set[str] = set()
    for index, item in enumerate(_list(root.get("modules"), "modules")):
        spot = f"modules[{index}]"
        body = _object(item, spot)
        _check_keys(body, _MODULE_KEYS, spot)
        module_id = _text(body.get("id"), f"{spot}.id", required=True)
        if module_id in seen:
            raise PresentationSpecError(
                f"{spot}.id is {module_id!r}, already used — one id is one module"
            )
        seen.add(module_id)
        parts = _text_list(body.get("parts"), f"{spot}.parts")
        if not parts:
            raise PresentationSpecError(
                f"{spot}.parts is empty — a module with no parts is a caption, "
                "not a group the layout can place"
            )
        out.append(PresentationModule(
            id=module_id,
            parts=parts,
            role=_text(body.get("role"), f"{spot}.role", required=True),
            grammar_ref=_module_grammar(body.get("grammarRef"), f"{spot}.grammarRef"),
            side_preferences=_module_presentation(body.get("presentation"), spot),
            branch_order=_module_branch_order(body.get("branchOrder"), spot, parts),
            core=_module_core(body.get("core"), f"{spot}.core"),
            attach=_module_attach(body.get("attach"), spot, module_id),
        ))
    _check_attachments(out)
    return out


def _module_attach(
    value: Any, where: str, module_id: str
) -> ModuleAttach | None:
    """One module's `attach`, or ``None`` for "the page places it on its own".

    Only what this document can decide is decided here: that `to` names a
    string, that `side` is one of the four sides and `gap` a positive finite
    number. Whether `to` names *another module of this document*, and whether the
    relation is one level deep, needs the whole module list — that half is
    :func:`_check_attachments`. Every refusal names the module and the key, so a
    caller does not have to guess which entry of a five-module list is wrong.
    """
    if value is None:
        return None
    body = _object(value, f"{where}.attach")
    _check_keys(body, _ATTACH_KEYS, f"{where}.attach")
    to = _text(body.get("to"), f"{where}.attach.to", required=True)
    side = ATTACH_SIDE_DEFAULT
    if "side" in body:
        side = _text(body.get("side"), f"{where}.attach.side", required=True)
        if side not in ATTACH_SIDES:
            raise PresentationSpecError(
                f"module {module_id!r}: attach.side is {side!r}; the sides are "
                + ", ".join(repr(item) for item in ATTACH_SIDES)
                + " — a side is one of the host's four edges, not a place"
            )
    gap = ATTACH_GAP_DEFAULT
    if "gap" in body:
        gap = _number(body.get("gap"), f"{where}.attach.gap")
        if gap <= 0:
            raise PresentationSpecError(
                f"module {module_id!r}: attach.gap is {gap:g}; the gap is the clear "
                "space between the host's frame and this module's, so it is a "
                "positive number of canvas units"
            )
    return ModuleAttach(to=to, side=side, gap=gap)


def _check_attachments(modules: Sequence[PresentationModule]) -> None:
    """The cross-module half of `attach`: one host, one level, no self, and real.

    Read after the whole list, because every rule here is a fact about the other
    entries. All four are refusals rather than repairs: a page compiler that
    silently dropped an attach (or silently re-pointed one) would draw a page the
    document does not describe.
    """
    known = {module.id for module in modules}
    attached = {module.id: module.attach for module in modules
                if module.attach is not None}
    hosts: dict[str, str] = {}
    for module in modules:
        attach = module.attach
        if attach is None:
            continue
        if attach.to not in known:
            raise PresentationSpecError(
                f"module {module.id!r}: attach.to is {attach.to!r}, and no module "
                "has that id — `to` names the host module of this same document"
            )
        if attach.to == module.id:
            raise PresentationSpecError(
                f"module {module.id!r}: attach.to is {module.id!r} — a module "
                "cannot be attached to itself"
            )
        if attach.to in attached:
            raise PresentationSpecError(
                f"module {module.id!r}: attach.to is {attach.to!r}, which is itself "
                f"attached (to {attached[attach.to].to!r}) — attach is one level "
                "deep: an attached module cannot be a host"
            )
        if attach.to in hosts:
            raise PresentationSpecError(
                f"module {module.id!r}: attach.to is {attach.to!r}, already the host "
                f"of module {hosts[attach.to]!r} — one host carries at most one "
                "attached module"
            )
        hosts[attach.to] = module.id


def _module_core(value: Any, where: str) -> str:
    """A module's stated core, or ``""`` for "not stated".

    098 §一: the core is the group's own part, so the only thing this document can
    decide about it is that it is a part id written down — whether the circuit
    declares it, and whether it carries enough pins to be the part the others hang
    off, are readings of the *circuit* and belong to the grammar (the same split
    `branchOrder` uses, and the same reason the module's `parts` are not
    cross-checked here).
    """
    if value is None or value == "":
        return ""
    return _text(value, where, required=True)


def _module_branch_order(
    value: Any, where: str, parts: Sequence[str]
) -> list[str]:
    """A module's stated branch order, checked against its own ``parts``.

    Two things are decidable from this document alone, and both are refused here
    rather than left to the grammar: a designator named twice ("one branch has
    one place in the order") and a designator the module's own ``parts`` does not
    list — the order is stated over *this* group, and a designator from outside
    it is a statement about somebody else's parts. Whether a named part is a
    *branch* at all is a reading of the circuit (the topology), so that half
    belongs to the grammar and is refused there (088b §二).
    """
    designators = _text_list(value, f"{where}.branchOrder")
    if not designators:
        return []
    seen: set[str] = set()
    for index, designator in enumerate(designators):
        spot = f"{where}.branchOrder[{index}]"
        if designator in seen:
            raise PresentationSpecError(
                f"{spot} is {designator!r}, already named — one branch has one "
                "place in the order, and a repeat says two different things "
                "about where it goes"
            )
        seen.add(designator)
        if designator not in parts:
            raise PresentationSpecError(
                f"{spot} is {designator!r}, which {where}.parts does not list "
                f"({', '.join(parts)}) — the order is stated over this group's "
                "own parts, and a designator outside it is a statement about "
                "another group's drawing"
            )
    return designators


def _module_grammar(value: Any, where: str) -> str:
    """A module's own grammar, or "" for "the document's"."""
    if value is None or value == "":
        return ""
    grammar = _text(value, where, required=True)
    if grammar not in GRAMMARS:
        raise PresentationSpecError(
            f"{where} is {grammar!r}; this build knows {', '.join(GRAMMARS)} — a "
            "module states one of them or states nothing and inherits the "
            "document's grammarRef"
        )
    return grammar


def _module_presentation(value: Any, where: str) -> dict[str, str]:
    """A module's `presentation` overrides: this build reads side preferences."""
    if value is None:
        return {}
    body = _object(value, f"{where}.presentation")
    _check_keys(body, MODULE_PRESENTATION_KEYS, f"{where}.presentation")
    raw = body.get("sidePreferences")
    if raw is None:
        return {}
    sides = _object(raw, f"{where}.presentation.sidePreferences")
    out: dict[str, str] = {}
    for role, side in sides.items():
        if side not in SIDES:
            raise PresentationSpecError(
                f"{where}.presentation.sidePreferences.{role} is {side!r}; "
                f"expected one of {', '.join(SIDES)}"
            )
        out[str(role)] = side
    return out


def _flow_from(root: dict[str, Any]) -> list[FlowEdge]:
    """The module-level flow edges, in the two forms the spec accepts.

    A plain pair (``["pwr", "sense"]``) states direction and nothing else, and
    the object form adds the one thing a pair cannot carry — `mainPath`. Both
    normalise to :class:`FlowEdge`, so the compiler reads one shape.
    """
    out: list[FlowEdge] = []
    seen: set[tuple[str, str, bool]] = set()
    for index, item in enumerate(_list(root.get("flow"), "flow")):
        spot = f"flow[{index}]"
        if isinstance(item, list):
            if len(item) != 2:
                raise PresentationSpecError(
                    f"{spot} is a list of {len(item)} entr(ies); the short form of "
                    "a flow edge is a pair ['<from module>', '<to module>'] — the "
                    "object form {'from': …, 'to': …, 'mainPath': …} carries the "
                    "main-path mark"
                )
            edge = FlowEdge(
                from_module=_text(item[0], f"{spot}[0]", required=True),
                to_module=_text(item[1], f"{spot}[1]", required=True),
            )
        else:
            body = _object(item, spot)
            _check_keys(body, _FLOW_EDGE_KEYS, spot)
            mark = body.get("mainPath", False)
            if not isinstance(mark, bool):
                raise PresentationSpecError(
                    f"{spot}.mainPath must be a boolean, got {mark!r}"
                )
            edge = FlowEdge(
                from_module=_text(body.get("from"), f"{spot}.from", required=True),
                to_module=_text(body.get("to"), f"{spot}.to", required=True),
                main_path=mark,
            )
        if edge.from_module == edge.to_module:
            raise PresentationSpecError(
                f"{spot} flows from {edge.from_module!r} to itself — a group does "
                "not feed itself, and an edge like this says nothing about order"
            )
        key = (edge.from_module, edge.to_module, edge.main_path)
        if key in seen:
            raise PresentationSpecError(
                f"{spot} repeats the edge "
                f"{edge.from_module!r} -> {edge.to_module!r}"
                + (" (mainPath)" if edge.main_path else "")
                + " — one direction is one edge"
            )
        seen.add(key)
        out.append(edge)
    return out


def _module_order_from(
    root: dict[str, Any], modules: Sequence[PresentationModule]
) -> list[str]:
    """The stated left-to-right / top-to-bottom module order, or ``[]``.

    A page order is a layout statement, not a circuit one: the decoupling islands
    of an IC can sit beside it without pretending they are a signal stage. When
    stated it must be a **permutation** of the modules — a short list would leave
    a module placed by a fallback the author did not state, and a typo would
    silently move the wrong group.
    """
    value = root.get("moduleOrder")
    if value is None:
        return []
    order = [
        _text(item, f"moduleOrder[{index}]", required=True)
        for index, item in enumerate(_list(value, "moduleOrder"))
    ]
    names = [module.id for module in modules]
    if len(order) != len(names) or sorted(order) != sorted(names):
        raise PresentationSpecError(
            "$.moduleOrder must list every module id exactly once: the modules "
            f"are {sorted(names)!r}, the order states {order!r}"
        )
    return order


def _part_texts_from(
    root: dict[str, Any], modules: Sequence[PresentationModule]
) -> dict[str, str]:
    """The stated side for each part's own text rows, or ``{}`` (053d).

    The set of parts a document may speak about is the set its **modules**
    declare — the same reference set `moduleOrder` and the islands are checked
    against — so a typo is a refusal that names the id rather than a side nobody
    reads. The sides are a closed vocabulary because the value travels straight
    into the compiler's line placer.
    """
    value = root.get("partTexts")
    if value is None:
        return {}
    body = _object(value, "partTexts")
    known = declared_part_ids(module.parts for module in modules)
    out: dict[str, str] = {}
    for part_id, side in body.items():
        spot = f"$.partTexts[{part_id!r}]"
        if part_id not in known:
            raise PresentationSpecError(
                f"{spot} names a part this document does not declare; the "
                f"modules declare {sorted(known)!r} — partTexts is checked "
                "against them, so a typo cannot silently move no text"
            )
        if side not in PART_TEXT_SIDES:
            raise PresentationSpecError(
                f"{spot} is {side!r}; expected one of "
                f"{', '.join(PART_TEXT_SIDES)} — a part's text side is a closed "
                "vocabulary and the two rows move together"
            )
        out[str(part_id)] = side
    return out


def _text_placement(root: dict[str, Any]) -> str:
    """The stated text-placement mode, or ``""`` (053S).

    Closed vocabulary on purpose: the value is a promise about **how** the page
    is written (the host's attribute API, `attributeMoves`), and a typo that was
    silently read as "default" would produce a drawing that looks fine and puts
    every text somewhere nobody declared. ``None``/absent is the historical
    reading and stays the only way to say nothing.
    """
    value = root.get("textPlacement")
    if value is None:
        return ""
    if not isinstance(value, str) or value not in TEXT_PLACEMENTS:
        raise PresentationSpecError(
            f"$.textPlacement is {value!r}; expected "
            f"{', '.join(repr(item) for item in TEXT_PLACEMENTS)} — the switch "
            "names how text lands, and an unknown mode is refused rather than "
            "read as the default"
        )
    return value


def _module_columns(root: dict[str, Any]) -> int:
    """The stated module-column count, or ``0`` (auto-search)."""
    value = root.get("moduleColumns")
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PresentationSpecError(
            f"$.moduleColumns must be a positive integer, got {value!r}"
        )
    return value


def _flag_lead_limit(root: dict[str, Any]) -> float:
    """The stated flag-lead limit, or ``0`` (compiler default).

    053d fix r1: the value must be **finite** as well as positive. `NaN` and
    `Infinity` pass `value <= 0` (both comparisons are False) and would travel
    into `CompileBudget.flag_lead_limit`, where `_flag_anchor`'s
    `if length > limit` filter stops filtering — a document that says `NaN`
    would silently remove the 60-unit cap, while `to_jsonable`/`dump` wrote the
    bare literal back and the digest covered text that is not JSON.
    """
    value = root.get("flagLeadLimit")
    if value is None:
        return 0.0
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise PresentationSpecError(
            "$.flagLeadLimit must be a positive, finite number of canvas units, "
            f"got {value!r}"
        )
    return float(value)


def _gnd_clustering(root: dict[str, Any]) -> float:
    """The stated ground-clustering radius, or ``0`` (no clustering, 053f).

    Closed and strictly validated for the reason `_flag_lead_limit` is: the value
    travels into `CompileBudget.gnd_cluster_radius`, where a `NaN`/`Infinity`
    would make every pad-to-pad comparison false and silently put every ground
    in its own cluster. A document that states nothing gets ``0``, which is the
    reading every document written before this key had.
    """
    value = root.get("gndClustering")
    if value is None:
        return 0.0
    body = _object(value, "gndClustering")
    _check_keys(body, GND_CLUSTERING_KEYS, "gndClustering")
    radius = body.get("radius")
    if (
        isinstance(radius, bool)
        or not isinstance(radius, (int, float))
        or not math.isfinite(radius)
        or radius <= 0
    ):
        raise PresentationSpecError(
            "$.gndClustering.radius must be a positive, finite number of canvas "
            f"units, got {radius!r}"
        )
    return float(radius)


def _service_layout(root: dict[str, Any]) -> ServiceLayout | None:
    """The stated service interval, or ``None`` when the document states none.

    A missing key is the historical reading and must stay a missing key: it is
    not written by :meth:`PresentationSpec.to_jsonable`, so every document
    compiled before 543B keeps its digest and its drawing. When stated, the
    object is closed and ``pinGap`` has to be a positive finite number of canvas
    units — a zero or negative gap would place the shunt on or through the host
    pin it serves, and a `NaN` would make the branch-distance comparison false.
    """
    value = root.get("serviceLayout")
    if value is None:
        return None
    body = _object(value, "serviceLayout")
    _check_keys(body, SERVICE_LAYOUT_KEYS, "serviceLayout")
    gap = body.get("pinGap")
    if (
        isinstance(gap, bool)
        or not isinstance(gap, (int, float))
        or not math.isfinite(gap)
        or gap <= 0
    ):
        raise PresentationSpecError(
            "$.serviceLayout.pinGap must be a positive, finite number of canvas "
            f"units, got {gap!r}"
        )
    return ServiceLayout(pin_gap=float(gap))


def _paths_from(root: dict[str, Any], key: str) -> list[PresentationPath]:
    out: list[PresentationPath] = []
    for index, item in enumerate(_list(root.get(key), key)):
        spot = f"{key}[{index}]"
        body = _object(item, spot)
        _check_keys(body, _PATH_KEYS, spot)
        chain = _text_list(body.get("chain"), f"{spot}.chain")
        if not chain:
            raise PresentationSpecError(
                f"{spot}.chain is empty — a path with no steps says nothing about "
                "what the reader should be able to follow"
            )
        for step_index, step in enumerate(chain):
            _path_step(step, f"{spot}.chain[{step_index}]")
        if len(set(chain)) != len(chain):
            raise PresentationSpecError(
                f"{spot}.chain names the same step twice ({', '.join(chain)}) — a "
                "path visits each element once"
            )
        out.append(PresentationPath(
            id=_text(body.get("id"), f"{spot}.id"),
            chain=chain,
            note=_text(body.get("note"), f"{spot}.note"),
        ))
    return out


def _path_step(step: str, where: str) -> None:
    for prefix in (PATH_STEP_PART, PATH_STEP_NET):
        if step.startswith(prefix):
            if not step[len(prefix):].strip():
                raise PresentationSpecError(
                    f"{where} is {step!r} with nothing after {prefix!r}"
                )
            return
    raise PresentationSpecError(
        f"{where} is {step!r}; a path step names what it is — "
        f"'{PATH_STEP_PART}<partId>' or '{PATH_STEP_NET}<netId>'"
    )


def _obligations_from(root: dict[str, Any]) -> list[DirectWiringObligation]:
    return _obligation_entries(
        root, "directWiringObligations", DirectWiringObligation,
        "an obligation with no net obliges nothing "
        "(the local connection it protects is named by a net)",
        refuse_duplicates=False,
    )


def _local_labels_from(root: dict[str, Any]) -> list[LocalLabelObligation]:
    return _obligation_entries(
        root, "localLabelObligations", LocalLabelObligation,
        "an exception with no net excepts nothing "
        "(the net drawn by a name at each pin is named by the net)",
        refuse_duplicates=True,
    )


def _obligation_entries(
    root: dict[str, Any],
    key: str,
    entry_type: type,
    empty_nets: str,
    *,
    refuse_duplicates: bool,
) -> list[Any]:
    """One net-list obligation list, read the same way for both keys.

    The two obligations share their *shape* — ``nets`` plus a ``note`` — and
    nothing else, so the reader is shared and the two readings stay one rule
    each: `directWiringObligations` keeps the bytes and the leniency it always
    had (a net named twice is not this key's question), while
    `localLabelObligations` refuses a net named twice because two entries for
    one net are two intents for one drawing, and which one the compiler should
    honour is exactly what the document has to say.
    """
    out: list[Any] = []
    seen: dict[str, int] = {}
    for index, item in enumerate(_list(root.get(key), key)):
        spot = f"{key}[{index}]"
        body = _object(item, spot)
        _check_keys(body, _OBLIGATION_KEYS, spot)
        nets = _text_list(body.get("nets"), f"{spot}.nets")
        if not nets:
            raise PresentationSpecError(f"{spot}.nets is empty — {empty_nets}")
        if refuse_duplicates:
            for net_id in nets:
                if net_id in seen:
                    raise PresentationSpecError(
                        f"{spot}.nets names {net_id!r}, which {key}"
                        f"[{seen[net_id]}] already names — one net, one "
                        "statement: two entries would be two intents for one "
                        "drawing and this document has to say which"
                    )
                seen[net_id] = index
        out.append(entry_type(
            nets=nets, note=_text(body.get("note"), f"{spot}.note")
        ))
    return out


def _label_policy(root: dict[str, Any]) -> LabelPolicy:
    value = root.get("labelPolicy")
    if value is None:
        return LabelPolicy()
    body = _object(value, "labelPolicy")
    _check_keys(body, _LABEL_POLICY_KEYS, "labelPolicy")
    local = body.get("local", LABEL_WIRE)
    if local != LABEL_WIRE:
        raise PresentationSpecError(
            f"labelPolicy.local is {local!r}; it may only be {LABEL_WIRE!r} — a "
            "key local topology is drawn as a wire, and the label exceptions are "
            "a net the document names in localLabelObligations, a net that "
            "crosses modules, or a high-fan-out net (053 sec.7, 052 sec.5). A "
            "local exception is stated per net there, never by loosening this "
            "policy"
        )
    out = LabelPolicy(local=LABEL_WIRE)
    for key, attribute in (("crossModule", "cross_module"), ("highFanout", "high_fanout")):
        mode = body.get(key, getattr(out, attribute))
        if mode not in LABEL_MODES:
            raise PresentationSpecError(
                f"labelPolicy.{key} is {mode!r}; expected one of "
                f"{', '.join(LABEL_MODES)}"
            )
        setattr(out, attribute, mode)
    stub = body.get("stub", LABEL_STUB_AUTO)
    if stub not in LABEL_STUB_MODES:
        raise PresentationSpecError(
            f"labelPolicy.stub is {stub!r}; expected one of "
            f"{', '.join(LABEL_STUB_MODES)}"
        )
    out.stub = stub
    stub_min = body.get("stubMin")
    if stub_min is not None:
        if (
            isinstance(stub_min, bool)
            or not isinstance(stub_min, (int, float))
            or not math.isfinite(stub_min)
            or stub_min <= 0
        ):
            raise PresentationSpecError(
                "labelPolicy.stubMin must be a positive, finite number of canvas "
                f"units, got {stub_min!r}"
            )
        out.stub_min = float(stub_min)
    row_model = body.get("rowModel", LABEL_ROW_MODEL_ANCHORED)
    if row_model not in LABEL_ROW_MODELS:
        raise PresentationSpecError(
            f"labelPolicy.rowModel is {row_model!r}; expected one of "
            f"{', '.join(LABEL_ROW_MODELS)}"
        )
    out.row_model = row_model
    return out


def _side_preferences(root: dict[str, Any]) -> dict[str, str]:
    out = dict(DEFAULT_SIDE_PREFERENCES)
    value = root.get("sidePreferences")
    if value is None:
        return out
    body = _object(value, "sidePreferences")
    for role, side in body.items():
        if side not in SIDES:
            raise PresentationSpecError(
                f"sidePreferences.{role} is {side!r}; expected one of "
                f"{', '.join(SIDES)}"
            )
        out[str(role)] = side
    return out


def _port_roles(root: dict[str, Any]) -> dict[str, str]:
    value = root.get("portRoles")
    if value is None:
        return {}
    body = _object(value, "portRoles")
    out: dict[str, str] = {}
    for net_id, direction in body.items():
        if not str(net_id).strip():
            raise PresentationSpecError("portRoles has an empty net id")
        if direction not in PORT_DIRECTIONS:
            raise PresentationSpecError(
                f"portRoles[{net_id}] is {direction!r}; expected one of "
                f"{', '.join(PORT_DIRECTIONS)}"
            )
        out[str(net_id)] = direction
    return out


def _grammar(root: dict[str, Any]) -> str:
    value = root.get("grammarRef", "")
    if value not in ("", *GRAMMARS):
        raise PresentationSpecError(
            f"$.grammarRef is {value!r}; this build knows "
            f"{', '.join(GRAMMARS)} — a grammar is a promise about what the "
            "drawing will make visible, and an unknown one is refused rather "
            "than replaced with a generic layout"
        )
    return str(value)


def _locks_from(root: dict[str, Any]) -> list[UserLock]:
    out: list[UserLock] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(_list(root.get("userLocks"), "userLocks")):
        spot = f"userLocks[{index}]"
        body = _object(item, spot)
        _check_keys(body, _LOCK_KEYS, spot)
        part_id = _text(body.get("partId"), f"{spot}.partId", required=True)
        scope = body.get("scope", LOCK_SCOPE_MODULE)
        if scope not in LOCK_SCOPES:
            raise PresentationSpecError(
                f"{spot}.scope is {scope!r}; expected one of {', '.join(LOCK_SCOPES)} "
                "— a lock is measured in its module's drawing or on the page"
            )
        if (part_id, scope) in seen:
            raise PresentationSpecError(
                f"{spot}.partId is {part_id!r}, already locked"
                + (" on the page" if scope == LOCK_SCOPE_PAGE else "")
                + " — two locks on one part are two answers to where it goes"
            )
        seen.add((part_id, scope))
        numbers = [_number(body.get(key), f"{spot}.{key}") for key in ("x", "y")]
        if scope == LOCK_SCOPE_PAGE:
            if "rotation" in body:
                raise PresentationSpecError(
                    f"{spot} is a page lock with a rotation — a page lock pins where "
                    "the part lands on the page, and its pose belongs to the module's "
                    "drawing: state the pose with a module lock on the same part "
                    "(the two scopes may be combined, 057 sec.3)"
                )
            out.append(UserLock(
                part_id=part_id, x=numbers[0], y=numbers[1], scope=LOCK_SCOPE_PAGE,
            ))
            continue
        rotation = _number(body.get("rotation", 0), f"{spot}.rotation")
        if rotation not in POSE_ROTATIONS:
            raise PresentationSpecError(
                f"{spot}.rotation is {rotation!r}; a lock names one of the poses "
                f"the symbols are drawn in ({', '.join(str(r) for r in POSE_ROTATIONS)} "
                "degrees, 052 sec.6's finite legal pose set)"
            )
        out.append(UserLock(
            part_id=part_id, x=numbers[0], y=numbers[1], rotation=rotation
        ))
    return out


# ------------------------------------------------------------------ helpers


def _refuse_coordinates(payload: Any, path: str, *, locked: bool = False) -> None:
    """Coordinates are refused everywhere except inside a `userLocks` entry.

    Runs on the raw payload before parsing (052 sec.4): the point is that the
    model entry point does not accept a coordinate at all, and a refusal that
    named the offending path is what teaches the next attempt. A lock is the
    engineer's own decision, so it is the one place the rule does not apply.
    """
    if isinstance(payload, dict):
        for key, value in payload.items():
            if not (locked and key in _LOCK_KEYS) and key in _COORDINATE_KEYS:
                raise PresentationSpecError(
                    f"{path}.{key} is a coordinate-shaped key ({key!r}); the model "
                    "entry point does not accept raw coordinates, wire points or "
                    "connector actions — coordinates are compiled from this spec "
                    "(053 sec.2), and the only legitimate coordinate entry is "
                    "userLocks"
                )
            # The exemption is the lock's own three keys, not its subtree:
            # `wirePoints` smuggled into a lock is still a coordinate-shaped key.
            _refuse_coordinates(value, f"{path}.{key}", locked=key == "userLocks")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _refuse_coordinates(value, f"{path}[{index}]", locked=locked)


def _object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PresentationSpecError(
            f"{where} must be a JSON object, got {type(value).__name__}"
        )
    return value


def _list(value: Any, where: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PresentationSpecError(f"$.{where} must be a list, got {value!r}")
    return value


def _text(value: Any, where: str, required: bool = False) -> str:
    if value is None:
        if required:
            raise PresentationSpecError(f"{where} is required and missing")
        return ""
    if not isinstance(value, str):
        raise PresentationSpecError(f"{where} must be a string, got {value!r}")
    if required and not value.strip():
        raise PresentationSpecError(f"{where} is empty")
    return value.strip()


def _text_list(value: Any, where: str) -> list[str]:
    raw = _list(value, where)
    out: list[str] = []
    for index, item in enumerate(raw):
        out.append(_text(item, f"{where}[{index}]", required=True))
    return out


def _number(value: Any, where: str) -> float:
    """One number out of the document, **finite** or refused.

    ``NaN`` and ``Infinity`` are numbers to :func:`float` and to `json.loads`
    (and `json.dumps` writes them back the same way, so a document carrying one
    can be produced by any Python toolchain). They are not places on a canvas:
    a lock coordinate of ``NaN`` travelled into the compiler's displacement
    arithmetic, and the final lattice snap raised ``round(NaN)`` out of
    :func:`drawcompiler._place` as a raw ``ValueError`` — a traceback and exit 1
    where the contract is a refusal and exit 5 ("Input problems never raise",
    `drawcompiler.CompileError`). The boundary is the right place to stop it:
    every number this document carries comes through here, so the refusal names
    the path and every consumer — single module and page alike — gets a
    :class:`PresentationSpecError` instead of an arithmetic surprise.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PresentationSpecError(
            f"{where} must be a number in canvas units, got {value!r}"
        )
    number = float(value)
    if not math.isfinite(number):
        raise PresentationSpecError(
            f"{where} is {value!r}; a coordinate is a place on a canvas and "
            f"{value!r} is not a place — write a finite number in canvas units "
            "(NaN and Infinity survive JSON, and a lock is honoured exactly, so "
            "a value the compiler cannot place must be refused here)"
        )
    return number


def _check_keys(body: dict[str, Any], allowed: tuple[str, ...], where: str) -> None:
    unknown = sorted(set(body) - set(allowed))
    if unknown:
        raise PresentationSpecError(
            f"{where}: unknown key(s) {', '.join(unknown)}; allowed: "
            f"{', '.join(allowed)} — the schema is closed on purpose: a key this "
            "build does not read would otherwise be an intent nobody honours"
        )
