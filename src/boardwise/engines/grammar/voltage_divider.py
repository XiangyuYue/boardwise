"""voltage-divider: 053 sec.3's first grammar, executed.

The table (053 sec.3, verbatim):

    | voltage-divider | upper_arm / lower_arm / tap / in / gnd |
    两电阻竖排同轴，upper 上 lower 下，tap 中点水平引出 |
    in→upper→tap→lower→gnd 全链直连；抽头直接可见（stub+标签/端口） |
    横排镜像、多抽头、并联支路 |

**The binding judgment, one level finer than the table.** The table names the
roles; what decides which part plays which is a walk of the *net graph of
two-terminal parts*:

1. `gnd` is a net whose `class` is `gnd`, `in` is a net whose `class` is
   `power`. Those two facts are input the grammar cannot derive — a net that
   states neither is a `facts-missing` refusal naming the class to fill in (the
   spec's own default is `signal`, which is not a ground).
2. An **arm** is a part with exactly two mentioned pins on two *different* nets
   (:func:`~boardwise.engines.grammar.base.two_terminal_parts`): a part whose two
   pins sit on one net is a short, not an arm, and is never bound as one.
3. A **chain** is a simple path `in → … → gnd` through at least **two** arms. One
   arm between `in` and `gnd` is not a divider — it has no midpoint — and if both
   arms of a "divider" are wired that way they are in parallel, which is the
   `circuit-invalid` case this grammar reports by name.
4. The chain's first arm is `upper_arm` (the power-side end), the last is
   `lower_arm` (the ground-side end), every net strictly between two arms is a
   `tap`, and an arm strictly between the two ends is a `middle_arm` (the table
   has no name for it; see below).
5. Where the presentation declares `modules`, the whole chain must live inside
   one of them; a chain that spans two declared modules is refused with a
   `circuit-invalid` naming each arm's module (052 sec.5's "不跨模块", made
   checkable).

`upper_arm` means the **power-side end**, so when `sidePreferences` puts power at
the bottom or on a side the roles keep their meaning and the geometry follows
the intent: the axis becomes horizontal and the ordering kind `left-of` /
`right-of`. That is what makes 053 sec.3's "横排镜像" a variant of this grammar
rather than a second grammar, and why no scenario-specific constant is needed.

**Two role names the table does not have.** The table names the two end arms of
a two-arm divider; the multi-tap ladder and the parallel branch need names for
what they add, and having them is the difference between the compiler knowing a
part belongs to this grammar and it having to guess:

* `middle_arm` — an arm strictly between the two ends of a chain of three or
  more arms (053 sec.3 "多抽头"; without it such a ladder has an arm nobody
  named).
* `tap_branch` — a two-terminal part hanging on a tap net, other than the
  chain's own arms (053 sec.3 "并联支路").

Both are *additions to*, not replacements for, the table: `upper_arm`,
`lower_arm`, `tap`, `in`, `gnd` bind exactly as the table says, and `ROLES`
below is the table itself.

**A signal-driven top (057 sec.7.1).** Step 1 reads the top of the chain from
the net's `power` class. A divider driven by a *signal* source (a sensor output
scaled into an ADC, a logic level divided down) has no power net to start from,
and until 057 it was refused as `facts-missing` with nothing the author could
state to get it drawn. The second branch accepts a `signal`-class top **only
when the author says it is a port** — the net is declared an explicit input
(`PresentationSpec.portRoles[net]` or `CircuitSpec.openInterfaces[].direction`
is `input` or `source`, :data:`SIGNAL_TOP_DIRECTIONS`). Declared, not guessed:
"the net at the end of the chain that is not ground" would bind any series pair
in any circuit. The branch is consulted **only when the power branch finds no
chain**, so every circuit that binds from a power rail binds exactly as before
(same chain, same evidence, same refusals) — the power reading stays the
first reading.

**A family of independent chains (548D3D-F1).** Two status LEDs on one page are
two dividers: `LED1_K→R2→LED1_A→D1→GND` and `LED2_K→R3→LED2_A→D2→GND`. Reading
only the first leaves the second one unbound, and an unbound twin is the "成对
支路偶然不一致" defect the drawing line refuses (boardwise-draw sec.3). So a bind
may consume a **family**: chains in the canonical order that share **no arm and
no tap** with one already read, and that live in the **same module**. Two
readings of one ladder — a chain that reuses an arm, or one that hangs on a tap
this chain already owns — are not another chain, and saying otherwise would
draw one divider twice. The shared power and ground nets are not a reason to
duplicate a binding either: `in` and `gnd` are bound once per net.

The family reading is **opt-in on the page's two layout declarations** (548D3D-F1A):
a stated `serviceLayout` **and** a stated `labelPolicy.stubMin` above zero. Both
are the author asking for served seats and real name stubs — the reading a pair
of twin branches is drawn for — and neither is `textPlacement: native-attr`,
which the first build used and which turned the compiler's page-wide paired
reading on for unrelated islands. The predicate is restated here rather than
imported, so this module keeps its own judgment. A page that states neither, a
page whose `stubMin` is zero or absent, and every **power**-driven divider keeps
the single-chain result byte for byte — only a declared signal top reads a
family, because that is the measured two-branch island and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ...core.circuitspec import CircuitSpec
from ...core.presentationspec import PresentationSpec
from ...core.symbolprofile import SymbolProfile
from .base import (
    ABOVE,
    BELOW,
    DIRECT_WIRE,
    FAILURE_CIRCUIT_INVALID,
    FAILURE_FACTS_MISSING,
    HORIZONTAL_TAP,
    LEFT_OF,
    MAX_CHAIN_ARMS,
    NEAR,
    OWNED_BRANCH,
    RIGHT_OF,
    SAME_COLUMN,
    SAME_ROW,
    VERTICAL_TAP,
    VISIBLE_TAP,
    GrammarFailure,
    GrammarObligation,
    GrammarResult,
    RelativeConstraint,
    RoleBinding,
    bound_result,
    connected_net_sets,
    declares_modules,
    evidence,
    modules_of_part,
    net_clause,
    net_provenance,
    nets_of_class,
    part_clause,
    part_provenance,
    pins_of_part,
    refused_result,
    series_paths,
    shared_module,
    two_terminal_parts,
    weakest_provenance,
)

__all__ = [
    "EXTRA_ROLES",
    "GRAMMAR",
    "MIN_ARMS",
    "NAME",
    "ROLES",
    "VoltageDividerGrammar",
    "grammar",
]

NAME = "voltage-divider"

#: The role table, verbatim from 053 sec.3.
ROLES: tuple[str, ...] = ("upper_arm", "lower_arm", "tap", "in", "gnd")

#: Roles added by this batch for the variants the table lists but does not name.
#: Kept apart from `ROLES` so a reader sees the table intact.
EXTRA_ROLES: tuple[str, ...] = ("middle_arm", "tap_branch")

MIDDLE_ARM = "middle_arm"
TAP_BRANCH = "tap_branch"

#: A divider needs a midpoint: a single arm from power to ground is not one.
MIN_ARMS = 2

#: The port directions that make a `signal`-class net an acceptable top of the
#: chain (057 sec.7.1): the net is an explicit input the divider is driven from.
#: The vocabulary is `circuitspec.PORT_DIRECTIONS`; `load`, `output` and
#: `feedback` describe a net the divider drives or reads back, not its source.
SIGNAL_TOP_DIRECTIONS: tuple[str, ...] = ("input", "source")

#: What kind of net the top of a chain is: the table's power rail, or a declared
#: signal input port (the 057 branch).
TOP_POWER = "power"
TOP_SIGNAL = "signal"


@dataclass(frozen=True)
class _Chain:
    """One in→gnd ladder, as the walk found it."""

    in_net: str
    gnd_net: str
    arms: tuple[str, ...]
    taps: tuple[str, ...]
    module: str = ""
    top: str = TOP_POWER

    def describe(self) -> str:
        """``VIN→R1→TAP→R2→GND`` — the spelling a report prints."""
        steps: list[str] = [self.in_net]
        for index, arm in enumerate(self.arms):
            steps.append(arm)
            if index < len(self.taps):
                steps.append(self.taps[index])
        steps.append(self.gnd_net)
        return "→".join(steps)


class VoltageDividerGrammar:
    """053 sec.3's voltage-divider grammar."""

    name = NAME

    def __init__(self, profiles: Mapping[str, SymbolProfile] | None = None) -> None:
        # The divider's judgment is purely topological, so nothing here reads
        # the profiles; they are accepted for a uniform construction across the
        # grammars, and carried for the compiler's own use.
        self.profiles: dict[str, SymbolProfile] = dict(profiles or {})

    # -------------------------------------------------------------- binding

    def bind(
        self,
        circuit: CircuitSpec,
        presentation: PresentationSpec,
        *,
        intent: object | None = None,
    ) -> GrammarResult:
        # 095 A4's contract is taken and not read: only `power-entry` states a
        # branch order a decision could place (088b's `branchOrder` is its own
        # field), so this grammar has no clause for a contract entry to fill —
        # accepted for the uniform signature the dispatcher calls with.
        power = nets_of_class(circuit, "power")
        ground = nets_of_class(circuit, "gnd")
        signal_tops = _signal_tops(circuit, presentation)
        # A declared signal input stands in for the missing rail (057 sec.7.1);
        # with neither, the refusal is the table's own, word for word.
        missing = _missing_class_failures(power or signal_tops, ground)
        if missing:
            return refused_result(missing)

        edges = two_terminal_parts(circuit)
        chains, failures = self._chains(presentation, edges, power, ground)
        if failures:
            return refused_result(failures)
        if not chains and signal_tops:
            chains, failures = self._chains(
                presentation, edges, signal_tops, ground, top=TOP_SIGNAL
            )
            if failures:
                return refused_result(failures)
            if not chains:
                return refused_result([_no_chain_failure(
                    circuit, edges, power + signal_tops, ground
                )])
        if not chains:
            return refused_result([_no_chain_failure(circuit, edges, power, ground)])
        family = _family(presentation, chains)
        others = [chain for chain in chains if not any(chain is taken for taken in family)]
        return self._result(circuit, presentation, edges, family, others)

    # ------------------------------------------------------------- internals

    def _chains(
        self,
        presentation: PresentationSpec,
        edges: dict[str, tuple[str, str]],
        power: tuple[str, ...],
        ground: tuple[str, ...],
        *,
        top: str = TOP_POWER,
    ) -> tuple[list[_Chain], list[GrammarFailure]]:
        """Every candidate ladder, canonically ordered, plus any refusal.

        Order: longer ladders first (a multi-tap ladder is the more specific
        reading of one rail), then by net and part id. It is a stable tie-break,
        not a claim that the first candidate is the only reading — the runners-up
        are named in every binding's evidence.

        ``power`` is the set of nets a chain may start from: the power rails, or
        (``top=TOP_SIGNAL``) the declared signal input ports.
        """
        found: list[_Chain] = []
        for in_net in power:
            for gnd_net in ground:
                for arms, nets in series_paths(
                    edges, in_net, gnd_net, max_arms=MAX_CHAIN_ARMS
                ):
                    if len(arms) < MIN_ARMS:
                        continue
                    found.append(
                        _Chain(
                            in_net=in_net,
                            gnd_net=gnd_net,
                            arms=arms,
                            taps=nets[1:-1],
                            module=shared_module(presentation, arms),
                            top=top,
                        )
                    )
        found.sort(
            key=lambda chain: (
                -len(chain.arms), chain.in_net, chain.gnd_net, chain.arms, chain.taps
            )
        )
        if declares_modules(presentation):
            scoped = [chain for chain in found if chain.module]
            if not scoped and found:
                return [], [_cross_module_failure(presentation, found[0])]
            found = scoped
        return found, []

    def _result(
        self,
        circuit: CircuitSpec,
        presentation: PresentationSpec,
        edges: dict[str, tuple[str, str]],
        family: list[_Chain],
        others: list[_Chain],
    ) -> GrammarResult:
        runners = _runner_up_note(len(family), others)
        input_side = _input_pair_side(circuit, presentation, family)
        power_side = input_side or presentation.side_for("power") or "top"
        gnd_side = presentation.side_for("gnd") or "bottom"
        axis, order_kind, tap_kind = _orientation(power_side, gnd_side)
        # Every arm of the family: a part that is one chain's arm is never
        # another chain's tap branch (548D3D-F1).
        family_arms = frozenset(arm for chain in family for arm in chain.arms)
        # `in`/`gnd` are bound once per net: two branches returning to one
        # ground share the ground role, they do not duplicate it.
        ends_bound: set[tuple[str, str]] = set()
        branches_bound: set[str] = set()

        bindings: list[RoleBinding] = []
        constraints: list[RelativeConstraint] = []
        obligations: list[GrammarObligation] = []

        for chain in family:
            chain_nets = (chain.in_net, *chain.taps, chain.gnd_net)
            prov = weakest_provenance(
                *(net_provenance(circuit, net_id) for net_id in chain_nets),
                *(part_provenance(circuit.part(arm)) for arm in chain.arms),
            )
            chain_constraints: list[RelativeConstraint] = []
            branch_constraints: list[RelativeConstraint] = []
            chain_obligations: list[GrammarObligation] = []
            chain_branches: list[str] = []

            for index, arm in enumerate(chain.arms):
                role = _arm_role(index, len(chain.arms))
                bindings.append(
                    RoleBinding(
                        role=role,
                        part_id=arm,
                        evidence=evidence(
                            f"role={role}: {_arm_clause(index, chain)}",
                            part_clause(circuit, arm),
                            f"chain chosen: {chain.describe()}",
                            f"provenance={prov}",
                            runners,
                        ),
                    )
                )

            for role, net_id in (("in", chain.in_net), ("gnd", chain.gnd_net)):
                if (role, net_id) in ends_bound:
                    continue
                ends_bound.add((role, net_id))
                if role == "in" and chain.top == TOP_SIGNAL:
                    end = (
                        "signal-input end (a declared input port, not a rail: "
                        f"{_port_clause(circuit, presentation, net_id)} — 057 sec.7.1)"
                    )
                else:
                    end = f"{'power' if role == 'in' else 'ground'} end"
                bindings.append(
                    RoleBinding(
                        role=role,
                        part_id=net_id,
                        evidence=evidence(
                            f"role={role}: the {end} of the chain "
                            f"{chain.describe()}",
                            _spec_net_clause(circuit, net_id),
                            f"provenance={net_provenance(circuit, net_id)}",
                            runners,
                        ),
                    )
                )

            for index, tap in enumerate(chain.taps):
                upper = chain.arms[index]
                lower = chain.arms[index + 1]
                branches = _branches(
                    presentation, edges, chain, tap, family_arms, branches_bound
                )
                bindings.append(
                    RoleBinding(
                        role="tap",
                        part_id=tap,
                        evidence=evidence(
                            f"role=tap: the net between arm {index + 1} ({upper}) and "
                            f"arm {index + 2} ({lower}) of the chain",
                            _spec_net_clause(circuit, tap),
                            part_clause(circuit, upper),
                            part_clause(circuit, lower),
                            f"provenance={weakest_provenance(net_provenance(circuit, tap), prov)}",
                            runners,
                        ),
                    )
                )
                chain_constraints.append(
                    RelativeConstraint(
                        kind=SAME_COLUMN if axis == "vertical" else SAME_ROW,
                        subject=upper,
                        object=lower,
                        reason=(
                            "053 sec.3: the two arms of a divider share one "
                            f"{'column' if axis == 'vertical' else 'row'} — segment "
                            f"{index + 1}/{len(chain.taps)} of {chain.describe()}"
                        ),
                    )
                )
                chain_constraints.append(
                    RelativeConstraint(
                        kind=order_kind,
                        subject=upper,
                        object=lower,
                        reason=(
                            f"053 sec.3: upper_arm {_order_words(order_kind)} lower_arm "
                            f"— {upper} is the end nearer {chain.in_net} "
                            f"(sidePreferences.{'input' if input_side else 'power'}={power_side}, "
                            f"sidePreferences.gnd={gnd_side})"
                        ),
                    )
                )
                chain_constraints.append(
                    RelativeConstraint(
                        kind=tap_kind,
                        subject=upper,
                        object=lower,
                        reason=(
                            f"053 sec.3: the tap leaves the junction of {upper} and "
                            f"{lower} "
                            f"{'horizontally' if tap_kind == HORIZONTAL_TAP else 'vertically'}"
                            f" (tap={tap}) — stub plus label or port, directly visible"
                        ),
                    )
                )
                chain_obligations.append(
                    GrammarObligation(
                        kind=VISIBLE_TAP,
                        nets=(tap,),
                        reason=(
                            "053 sec.3: the tap is directly visible (stub + label or "
                            "port), not absorbed by the upper/lower junction"
                        ),
                    )
                )
                for branch in branches:
                    chain_branches.append(branch)
                    bindings.append(
                        RoleBinding(
                            role=TAP_BRANCH,
                            part_id=branch,
                            evidence=evidence(
                                f"role={TAP_BRANCH}: a two-terminal part hanging on "
                                f"tap {tap}, not an arm of the chain",
                                part_clause(circuit, branch),
                                f"chain chosen: {chain.describe()}",
                                f"provenance={weakest_provenance(net_provenance(circuit, tap), part_provenance(circuit.part(branch)))}",
                            ),
                        )
                    )
                    branch_constraints.append(
                        RelativeConstraint(
                            kind=NEAR,
                            subject=branch,
                            object=upper,
                            reason=(
                                f"053 sec.3: a parallel branch on the tap stays with "
                                f"the tap node — {branch} is placed next to {upper} "
                                "(the arm the tap leaves), not across a module boundary"
                            ),
                        )
                    )
                if branches:
                    chain_obligations.append(
                        GrammarObligation(
                            kind=OWNED_BRANCH,
                            nets=(tap,),
                            reason=(
                                f"053 sec.3: the parallel branch on {tap} reads as "
                                "owned by the tap node"
                            ),
                        )
                    )

            # The chain's own relations first, then the branches hanging off it:
            # that is the order a reader follows the drawing in.
            branches_bound.update(chain_branches)
            constraints.extend(chain_constraints)
            constraints.extend(branch_constraints)
            chain_obligations.insert(
                0,
                GrammarObligation(
                    kind=DIRECT_WIRE,
                    nets=chain_nets,
                    reason=(
                        "053 sec.3: in→upper→tap→lower→gnd is wired end to end — a "
                        "divider is never read by chasing labels"
                    ),
                ),
            )
            obligations.extend(chain_obligations)

        # Sibling chains of one module are read **side by side** (548D3D-F1):
        # the corresponding arms of two chains share one row (one column when
        # the chains are drawn horizontally), which is boardwise-draw sec.3's
        # "同向、对齐" stated as a relation instead of left to a search. Only
        # chains of one length can be aligned arm by arm; a ladder of another
        # length is a different shape and keeps the ties it states itself.
        if len(family) > 1 and len({len(chain.arms) for chain in family}) == 1:
            align_kind = SAME_ROW if axis == "vertical" else SAME_COLUMN
            head = family[0]
            for index in range(len(head.arms)):
                for chain in family[1:]:
                    constraints.append(
                        RelativeConstraint(
                            kind=align_kind,
                            subject=head.arms[index],
                            object=chain.arms[index],
                            reason=(
                                "548D3D-F1: two independent chains of one module are "
                                f"read side by side — {head.arms[index]} and "
                                f"{chain.arms[index]} are both arm {index + 1} of "
                                f"their own chain and share one "
                                f"{'row' if align_kind == SAME_ROW else 'column'} "
                                "(same direction, same reading rule)"
                            ),
                        )
                    )
        return bound_result(bindings, constraints, obligations)


GRAMMAR = VoltageDividerGrammar


def grammar(
    profiles: Mapping[str, SymbolProfile] | None = None,
) -> VoltageDividerGrammar:
    """A divider grammar, optionally holding the library profiles."""
    return VoltageDividerGrammar(profiles)


# ------------------------------------------------------------- the judgment


def _missing_class_failures(
    power: tuple[str, ...], ground: tuple[str, ...]
) -> list[GrammarFailure]:
    """The net-class facts the judgment cannot do without."""
    out: list[GrammarFailure] = []
    if not ground:
        out.append(
            GrammarFailure(
                category=FAILURE_FACTS_MISSING,
                detail=(
                    "no net of class 'gnd': the bottom of a divider is ground, "
                    "and the drawing grammar has to be told which net that is"
                ),
                action=(
                    "write the class in CircuitSpec.nets[].class — the class a "
                    "net gets when nothing says is 'signal', which is not ground"
                ),
            )
        )
    if not power:
        out.append(
            GrammarFailure(
                category=FAILURE_FACTS_MISSING,
                detail=(
                    "no net of class 'power': the top of a divider is a supply "
                    "rail, and the grammar has to be told which net that is"
                ),
                action=(
                    "write the class in CircuitSpec.nets[].class (power), or "
                    "restate the circuit if the divider hangs on something else"
                ),
            )
        )
    return out


def _signal_tops(
    circuit: CircuitSpec, presentation: PresentationSpec
) -> tuple[str, ...]:
    """The `signal`-class nets the author declared as the divider's input port.

    Two places may say it, and either is a declaration: the presentation's
    ``portRoles`` (how the drawing should read the net) and the circuit's
    ``openInterfaces`` (the net is exposed, not terminated). The direction has
    to be one of :data:`SIGNAL_TOP_DIRECTIONS`; id-sorted, like every other net
    list this grammar walks, so two runs start from the same net.
    """
    declared = {
        net_id for net_id, direction in presentation.port_roles.items()
        if direction in SIGNAL_TOP_DIRECTIONS
    } | {
        item.net for item in circuit.open_interfaces
        if item.direction in SIGNAL_TOP_DIRECTIONS
    }
    return tuple(sorted(
        net.id for net in circuit.nets
        if net.cls == "signal" and net.id in declared
    ))


def _port_clause(
    circuit: CircuitSpec, presentation: PresentationSpec, net_id: str
) -> str:
    """Where the signal top was declared a port, for the binding's evidence."""
    places = []
    if presentation.port_roles.get(net_id) in SIGNAL_TOP_DIRECTIONS:
        places.append(f"portRoles[{net_id}]={presentation.port_roles[net_id]}")
    places.extend(
        f"openInterfaces[{item.net}].direction={item.direction}"
        for item in circuit.open_interfaces
        if item.net == net_id and item.direction in SIGNAL_TOP_DIRECTIONS
    )
    return ", ".join(places) or f"{net_id} (declared)"


def _arm_role(index: int, count: int) -> str:
    if index == 0:
        return "upper_arm"
    if index == count - 1:
        return "lower_arm"
    return MIDDLE_ARM


def _arm_clause(index: int, chain: _Chain) -> str:
    if index == 0:
        return "the power-side end of the series chain"
    if index == len(chain.arms) - 1:
        return "the ground-side end of the series chain"
    return (
        f"arm {index + 1} of a {len(chain.arms)}-arm chain, strictly between the "
        "two ends (053 sec.3's multi-tap variant)"
    )


def _input_pair_side(
    circuit: CircuitSpec,
    presentation: PresentationSpec,
    family: list[_Chain],
) -> str | None:
    """Repair the mixed-axis fallback for two matching, declared input chains.

    Same-axis power/ground layouts keep their old meaning. Only a horizontal
    input opposite ground can replace the fallback: the compiler's horizontal
    progress already reads input, while vertical progress still reads power.
    More than two chains can change that compiler's axis vote, so this rule is
    limited to the pair whose corresponding arms the grammar aligns.
    """
    if len(family) != 2 or not _paired_layout(presentation):
        return None
    if len(family[0].arms) != len(family[1].arms):
        return None
    if any(chain.top != TOP_SIGNAL for chain in family):
        return None
    if (presentation.side_for("power") or "top") not in ("top", "bottom"):
        return None
    input_side = presentation.side_for("input")
    if {input_side, presentation.side_for("gnd")} != {"left", "right"}:
        return None
    for chain in family:
        directions = {
            item.direction for item in circuit.open_interfaces
            if item.net == chain.in_net and item.direction
        }
        role = presentation.port_roles.get(chain.in_net)
        if role:
            directions.add(role)
        if directions != {"input"}:
            return None
    return input_side


def _orientation(power_side: str, gnd_side: str) -> tuple[str, str, str]:
    """``(axis, ordering kind, tap-stub kind)`` from the side preferences.

    Both ends on a vertical side → vertical axis, tap stub horizontal (the
    table's default drawing). Both on a horizontal side → the "横排镜像"
    variant. A mixed pair is not a chain direction, so the book's default
    (power top, ground bottom) is used and the choice is visible in the
    constraint reasons.
    """
    if power_side in ("top", "bottom") and gnd_side in ("top", "bottom"):
        return ("vertical", ABOVE if power_side == "top" else BELOW, HORIZONTAL_TAP)
    if power_side in ("left", "right") and gnd_side in ("left", "right"):
        return (
            "horizontal",
            LEFT_OF if power_side == "left" else RIGHT_OF,
            VERTICAL_TAP,
        )
    return ("vertical", ABOVE, HORIZONTAL_TAP)


def _order_words(order_kind: str) -> str:
    return {
        ABOVE: "above",
        BELOW: "below",
        LEFT_OF: "left-of",
        RIGHT_OF: "right-of",
    }[order_kind]


def _paired_layout(presentation: PresentationSpec) -> bool:
    """The page's two layout declarations (548D3D-F1A), restated not imported.

    A stated `serviceLayout` and a stated `labelPolicy.stubMin` above zero: the
    author asked for served seats and real name stubs, which is the layout a
    pair of twin branches is drawn for. `textPlacement: native-attr` is **not**
    part of the question — the first build keyed on it and that turned the
    compiler's page-wide paired reading on for islands that had nothing to do
    with this grammar (measured: two unrelated modules lost every candidate).
    """
    return (
        presentation.service_layout is not None
        and presentation.label_policy.stub_min > 0.0
    )


def _family(presentation: PresentationSpec, chains: list[_Chain]) -> list[_Chain]:
    """The chains one bind consumes, in the order the walk found them.

    One chain, unless the page asks for the paired layout and its top is a
    declared signal port (548D3D-F1's measured two-branch island): a power
    divider keeps the single-chain result byte for byte.

    A candidate joins the family only when it lives in the **same module** as
    the family and shares **no arm and no tap** with any chain already read.
    Reusing an arm is the same ladder read another way; hanging on a tap the
    family already owns is a parallel branch on a node this divider owns, not a
    second divider. Both are named in the runner-up note instead of being bound
    twice.
    """
    if not chains:
        return []
    first = chains[0]
    if first.top != TOP_SIGNAL or not _paired_layout(presentation):
        return [first]
    family = [first]
    arms = set(first.arms)
    taps = set(first.taps)
    for chain in chains[1:]:
        if chain.module != first.module:
            continue
        if set(chain.arms) & arms or set(chain.taps) & taps:
            continue
        family.append(chain)
        arms.update(chain.arms)
        taps.update(chain.taps)
    return family


def _branches(
    presentation: PresentationSpec,
    edges: dict[str, tuple[str, str]],
    chain: _Chain,
    tap: str,
    arms: frozenset[str],
    taken: set[str],
) -> tuple[str, ...]:
    """Two-terminal parts on this tap that are not arms of the family.

    Restricted to the chain's module where one is declared: a branch reaching
    into another module is that module's business, not this grammar's (052
    sec.5). ``arms`` is every arm of the consumed family, so one chain's arm is
    never another chain's branch, and ``taken`` names the branches an earlier
    chain in the family already bound (a part hanging on two chains' taps is
    bound once).
    """
    out: list[str] = []
    for part_id in sorted(edges):
        if part_id in arms or part_id in taken or tap not in edges[part_id]:
            continue
        if chain.module:
            here = modules_of_part(presentation, part_id)
            if chain.module not in here:
                continue
        out.append(part_id)
    return tuple(out)


def _runner_up_note(bound: int, others: list[_Chain]) -> str:
    """``other candidates not bound: …`` — the readings this bind did not take."""
    if not others:
        return ""
    shown = "; ".join(chain.describe() for chain in others[:5])
    more = "" if len(others) <= 5 else f"; +{len(others) - 5} more"
    count = "one chain" if bound <= 1 else f"{bound} independent chains"
    return (
        "other in→gnd chains found but not bound (this grammar instance bound "
        f"{count}): {shown}{more}"
    )


def _cross_module_failure(
    presentation: PresentationSpec, chain: _Chain
) -> GrammarFailure:
    """The chain exists but the presentation's modules split it."""
    where = ", ".join(
        f"{arm} in {'/'.join(modules_of_part(presentation, arm)) or 'no module'}"
        for arm in chain.arms
    )
    return GrammarFailure(
        category=FAILURE_CIRCUIT_INVALID,
        subject=chain.arms[0],
        detail=(
            f"the ladder {chain.describe()} crosses the declared module split: "
            f"{where} — a divider is one functional group (052 sec.5: a branch or "
            "a chain is not drawn across modules)"
        ),
        action=(
            "put every arm of this ladder in one PresentationSpec.modules[] "
            "entry, or fix the module split if the circuit is not one divider"
        ),
    )


def _spec_net_clause(circuit: CircuitSpec, net_id: str) -> str:
    """``net VIN: class=power provenance=…`` or a bare mention when absent."""
    net = circuit.net(net_id)
    return net_clause(net) if net else f"net {net_id}: not declared in nets[]"


def _no_chain_failure(
    circuit: CircuitSpec,
    edges: dict[str, tuple[str, str]],
    power: tuple[str, ...],
    ground: tuple[str, ...],
) -> GrammarFailure:
    """Why no ladder was found — naming what the parts *are* connected to.

    The two shapes worth naming are the parallel pair (both arms across the same
    two nets: no midpoint exists) and the dead-ended chain (the walk stopped
    somewhere that is not ground). Both are `circuit-invalid`: the connections,
    not a missing fact, are why the topology does not match. A *single* part
    across the rails is not a parallel pair — it is one arm short of
    :data:`MIN_ARMS`, and the no-chain branch says so instead of inventing a
    second arm.
    """
    parallel = sorted(
        part_id
        for part_id, nets in edges.items()
        if (nets[0] in power and nets[1] in ground)
        or (nets[1] in power and nets[0] in ground)
    )
    listing = _connection_listing(circuit, edges)
    if parallel and len(parallel) >= 2:
        crossing = ", ".join(f"{pid}({','.join(edges[pid])})" for pid in parallel)
        detail = (
            f"{crossing} sit directly across a power rail and ground — two arms "
            "in parallel, not in series: they share no midpoint, so no net can be "
            "the tap (053 sec.5 scenario 11's shorted/parallel case)"
        )
        action = (
            "the arms of a divider share one midpoint: rewire one arm's end from "
            "ground (or power) onto the tap net, or restate the circuit if it is "
            "not a divider"
        )
    else:
        detail = (
            f"no chain of two or more two-terminal arms runs from {list(power)} to "
            f"{list(ground)} inside the {MAX_CHAIN_ARMS}-arm budget (the grammar "
            f"needs at least MIN_ARMS={MIN_ARMS} arms on one chain; this page "
            f"reads {len(edges)} two-terminal "
            f"{'arm' if len(edges) == 1 else 'arms'}); what the parts on this page "
            f"connect is: {listing}"
        )
        action = (
            "check the CircuitSpec connections (a missing arm, an arm ending on "
            "an unmentioned net, a wrong net class), or enlarge the grammar's "
            "budget if the ladder really is longer than "
            f"{MAX_CHAIN_ARMS} arms"
        )
    return GrammarFailure(
        category=FAILURE_CIRCUIT_INVALID,
        subject="",
        detail=detail,
        action=action,
    )


def _pin_phrase(count: int) -> str:
    """``1 pin`` / ``3 pins`` — the real pin count of a part that is not an arm."""
    return f"{count} pin" if count == 1 else f"{count} pins"


def _connection_listing(
    circuit: CircuitSpec, edges: dict[str, tuple[str, str]]
) -> str:
    """``R1(VIN,TAP), R2(TAP,X), U1(3 pins, not an arm: GND/VIN/X)``.

    Bounded and sorted, for a failure message. The listing names every part that
    states a connection, not only the two-terminal arms: a part that is **not**
    an arm — three or more pins, or two pins sitting on one net — is tagged with
    its real pin count and ``not an arm``, so the reader never reads it as one.
    """
    items = [f"{part_id}({','.join(edges[part_id])})" for part_id in sorted(edges)]
    net_sets = connected_net_sets(circuit)
    others = sorted(set(net_sets) - set(edges))
    items.extend(
        f"{part_id}({_pin_phrase(len(pins_of_part(circuit, part_id)))}, not an "
        f"arm: {'/'.join(net_sets[part_id])})"
        for part_id in others[:4]
    )
    if len(items) > 12:
        return ", ".join(items[:12]) + f", … (+{len(items) - 12} more)"
    return ", ".join(items) or "no part states a connection"
