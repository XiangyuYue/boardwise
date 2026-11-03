"""Which host a two-terminal shunt capacitor serves (543A).

The drawing chain already knows that a decoupling capacitor belongs *with* its
IC (``PresentationSpec`` modules, ``attach``, the page compiler's grouping). It
does not know **which** supply pin the capacitor is shunting, and until that is
answered a layout cannot place the pair relative to the pin it protects. This
module answers exactly that question, read-only, from:

* the circuit partition (:class:`~boardwise.core.circuitspec.CircuitSpec`) —
  which pins are one net, and which of those nets are ground;
* the presentation intent
  (:class:`~boardwise.core.presentationspec.PresentationSpec`) — which part each
  module is arranged around (``core``) and which module is attached to which
  host (``attach``);
* the shared component-classification contract
  (:func:`boardwise.core.decap.looks_like_capacitor`) — whether a part is a
  capacitor at all.

Nothing here reads geometry, a reference page, a designator number or a net
name to infer the relation. A capacitor is a capacitor because the shared
classifier says so from its declarations; a host is a host because the
presentation spec names its module's core (or, failing that, because a module
core is on the same net); the served net is the capacitor's non-ground terminal.
Rename every part id and every net id consistently and the same answer comes
back, which is the property the batch's tests assert.

Two honesty rules carried over from the review side apply here because the
answer feeds a drawing decision:

* **one answer or none.** Several hosts at the same priority are reported as
  :data:`STATUS_AMBIGUOUS_HOST` with the candidate set — never as the first
  candidate. Several service nets for one host are
  :data:`STATUS_AMBIGUOUS_NET` for the same reason.
* **a set of pins is not a pin.** A host may put several equivalent supply
  pins on the served net (a Type-C receptacle's two VBUS contacts). All of them
  are returned in :attr:`DecouplingService.host_pins`; none is promoted to
  "the" pin by pin-number order.

This batch does not call the module from the compiler. It is the read-only
relation table 543B will consume.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.circuitspec import CircuitSpec, SpecNet
from ..core.decap import looks_like_capacitor
from ..core.model import is_ground_net
from ..core.presentationspec import PresentationModule, PresentationSpec

__all__ = [
    "BASIS_ATTACH_CORE",
    "BASIS_MODULE_CORE",
    "BASIS_NETLIST_CORE",
    "STATUS_AMBIGUOUS_HOST",
    "STATUS_AMBIGUOUS_NET",
    "STATUS_NO_HOST",
    "STATUS_NOT_DECOUPLING",
    "STATUS_SERVED",
    "STATUSES",
    "DecouplingAnalysis",
    "DecouplingService",
    "analyze_decoupling",
]

#: A unique host and a unique served net were found.
STATUS_SERVED = "served"
#: Several hosts tie at the winning priority; none is chosen.
STATUS_AMBIGUOUS_HOST = "ambiguous_host"
#: One host, but more than one service net could be the one it is shunted by.
STATUS_AMBIGUOUS_NET = "ambiguous_net"
#: A capacitor was read, but no host core touches its service net.
STATUS_NO_HOST = "no_host"
#: The part is not a two-terminal grounded capacitor, so it has no service
#: relation at all.
STATUS_NOT_DECOUPLING = "not_decoupling"

STATUSES = (
    STATUS_SERVED,
    STATUS_AMBIGUOUS_HOST,
    STATUS_AMBIGUOUS_NET,
    STATUS_NO_HOST,
    STATUS_NOT_DECOUPLING,
)

#: The host was named by the core of the module the capacitor itself sits in.
BASIS_MODULE_CORE = "module-core"
#: The capacitor's module has no core; its `attach` host's core answered.
BASIS_ATTACH_CORE = "attach-core"
#: Neither of the above touched the net; a module core on the net answered.
BASIS_NETLIST_CORE = "netlist-core"


@dataclass(frozen=True)
class DecouplingService:
    """The service relation of one part, resolved or honestly unresolved.

    ``host_pins`` holds every pin of the host that sits on ``net_id``, in the
    net's own member order. It is deliberately a tuple rather than a scalar:
    two equivalent supply contacts are two candidates, and a reader that wants
    "the" pin has to say so itself.

    ``service_pin`` / ``return_pin`` are the capacitor's own two terminals
    (``return_pin`` is the grounded one). They are pin names from the spec, not
    designators, so a renamed part keeps the same relation.
    """

    part_id: str
    status: str
    reason: str
    net_id: str | None = None
    host_id: str | None = None
    host_module: str | None = None
    host_pins: tuple[str, ...] = ()
    host_candidates: tuple[str, ...] = ()
    service_pin: str = ""
    return_pin: str = ""
    basis: str = ""

    @property
    def resolved(self) -> bool:
        return self.status == STATUS_SERVED

    @property
    def has_unique_host_pin(self) -> bool:
        """True only when exactly one host pin sits on the served net."""
        return self.status == STATUS_SERVED and len(self.host_pins) == 1


@dataclass(frozen=True)
class DecouplingAnalysis:
    """Every part's service relation, in circuit part order."""

    services: tuple[DecouplingService, ...] = ()

    def for_part(self, part_id: str) -> DecouplingService | None:
        for service in self.services:
            if service.part_id == part_id:
                return service
        return None

    @property
    def capacitors(self) -> tuple[DecouplingService, ...]:
        return tuple(
            service
            for service in self.services
            if service.status != STATUS_NOT_DECOUPLING
        )

    @property
    def resolved(self) -> tuple[DecouplingService, ...]:
        return tuple(service for service in self.services if service.resolved)


def analyze_decoupling(
    circuit: CircuitSpec,
    presentation: PresentationSpec,
    library: object | None = None,
) -> DecouplingAnalysis:
    """Read every part's decoupling service relation from circuit + intent.

    ``library`` is the optional **parts shelf** the shared classifier can consult
    (:func:`boardwise.core.decap.looks_like_capacitor`); the symbol-profile
    library the compiler uses is geometry and is not needed here. Omitting it
    leaves classification to the part's own declarations, which is how the
    CH343 input reads without one.
    """
    parts = tuple(circuit.parts)
    by_pin = _nets_by_pin(circuit)
    declared_modules = _modules_by_part(presentation, parts)
    return DecouplingAnalysis(
        services=tuple(
            _service_for_part(
                part.id,
                getattr(part, "value", "") or "",
                getattr(part, "mpn", "") or "",
                getattr(part, "lcsc", "") or "",
                getattr(part, "symbol_ref", "") or "",
                by_pin.get(part.id, {}),
                presentation,
                declared_modules,
                library,
            )
            for part in parts
        )
    )


# ------------------------------------------------------------------ reading


def _nets_by_pin(circuit: CircuitSpec) -> dict[str, dict[str, tuple[SpecNet, ...]]]:
    """part id -> pin -> the nets that pin sits on (normally exactly one)."""
    found: dict[str, dict[str, list[SpecNet]]] = {}
    for net in circuit.nets:
        for member in net.members:
            split = _split_member(member)
            if split is None:
                continue
            part_id, pin = split
            bucket = found.setdefault(part_id, {}).setdefault(pin, [])
            if all(existing.id != net.id for existing in bucket):
                bucket.append(net)
    return {
        part_id: {pin: tuple(nets) for pin, nets in pins.items()}
        for part_id, pins in found.items()
    }


def _split_member(member: object) -> tuple[str, str] | None:
    text = str(member or "")
    part_id, separator, pin = text.partition(".")
    if not separator or not part_id or not pin:
        return None
    return part_id, pin


def _modules_by_part(
    presentation: PresentationSpec, parts: tuple[object, ...]
) -> dict[str, tuple[PresentationModule, ...]]:
    """Every module declaring a part, in document order, per part id."""
    declared: dict[str, list[PresentationModule]] = {
        getattr(part, "id", ""): [] for part in parts
    }
    for module in presentation.modules:
        for part_id in module.parts:
            declared.setdefault(part_id, []).append(module)
    return {part_id: tuple(modules) for part_id, modules in declared.items()}


def _service_for_part(
    part_id: str,
    value: str,
    mpn: str,
    lcsc: str,
    symbol_ref: str,
    pins: dict[str, tuple[SpecNet, ...]],
    presentation: PresentationSpec,
    declared_modules: dict[str, tuple[PresentationModule, ...]],
    library: object | None,
) -> DecouplingService:
    if not looks_like_capacitor(
        part_id, value, mpn, lcsc, library, name=symbol_ref
    ):
        return DecouplingService(
            part_id=part_id,
            status=STATUS_NOT_DECOUPLING,
            reason=(
                "the shared component classifier does not read this part as a "
                "capacitor, so it is not a decoupling shunt"
            ),
        )
    if len(pins) != 2:
        return DecouplingService(
            part_id=part_id,
            status=STATUS_NOT_DECOUPLING,
            reason=(
                "a decoupling capacitor is a two-terminal shunt; this part has "
                f"{len(pins)} terminal(s) on named nets"
            ),
        )
    terminals = tuple(pins.items())
    for pin, nets in terminals:
        if len(nets) != 1:
            return DecouplingService(
                part_id=part_id,
                status=STATUS_NOT_DECOUPLING,
                reason=(
                    f"pin {pin} sits on {len(nets)} nets, so the part is not a "
                    "clean two-terminal shunt"
                ),
            )
    (pin_a, nets_a), (pin_b, nets_b) = terminals
    net_a, net_b = nets_a[0], nets_b[0]
    if net_a.id == net_b.id:
        return DecouplingService(
            part_id=part_id,
            status=STATUS_NOT_DECOUPLING,
            reason=(
                f"both terminals sit on net {net_a.id!r}; the part does not "
                "bridge a supply to a return"
            ),
        )
    ground_a, ground_b = _is_ground(net_a), _is_ground(net_b)
    if ground_a and ground_b:
        return DecouplingService(
            part_id=part_id,
            status=STATUS_NOT_DECOUPLING,
            reason="both terminals sit on ground nets; there is no served rail",
        )
    service_terminals = [
        (pin, net)
        for pin, net, ground in (
            (pin_a, net_a, ground_a),
            (pin_b, net_b, ground_b),
        )
        if not ground
    ]
    return_pin = pin_a if ground_a else pin_b

    candidates: list[tuple[int, str, str, SpecNet, str]] = []
    for service_pin, service_net in service_terminals:
        for level, basis, hosts in _candidate_levels(
            part_id, service_net, presentation, declared_modules.get(part_id, ())
        ):
            for host_id in hosts:
                candidates.append((level, basis, service_pin, service_net, host_id))

    if not candidates:
        nets = ", ".join(repr(net.id) for _pin, net in service_terminals)
        return DecouplingService(
            part_id=part_id,
            status=STATUS_NO_HOST,
            reason=(
                f"no module core touches service net(s) {nets}; the presentation "
                "spec names no host for this capacitor"
            ),
            return_pin=return_pin,
            service_pin=service_terminals[0][0],
        )

    best_level = min(level for level, _basis, _pin, _net, _host in candidates)
    best = [item for item in candidates if item[0] == best_level]
    basis = best[0][1]
    hosts = _ordered_unique(host for _level, _basis, _pin, _net, host in best)
    if len(hosts) > 1:
        return DecouplingService(
            part_id=part_id,
            status=STATUS_AMBIGUOUS_HOST,
            reason=(
                f"{len(hosts)} hosts tie at the {basis} priority "
                f"({', '.join(hosts)}); refusing to pick the first one"
            ),
            host_candidates=hosts,
            return_pin=return_pin,
            service_pin=service_terminals[0][0],
            basis=basis,
        )

    host_id = hosts[0]
    served_nets = _ordered_unique(
        net for _level, _basis, _pin, net, host in best if host == host_id
    )
    host_modules = _ordered_unique(
        module.id
        for module in declared_modules.get(part_id, ())
        if module.core == host_id
    )
    if not host_modules:
        host_modules = _ordered_unique(
            module.id for module in presentation.modules if module.core == host_id
        )
    host_module = host_modules[0] if host_modules else None

    if len(served_nets) > 1:
        return DecouplingService(
            part_id=part_id,
            status=STATUS_AMBIGUOUS_NET,
            reason=(
                f"host {host_id!r} touches both service nets "
                f"({', '.join(net.id for net in served_nets)}); cannot tell "
                "which rail this shunt serves"
            ),
            host_id=host_id,
            host_module=host_module,
            host_candidates=(host_id,),
            return_pin=return_pin,
            service_pin=service_terminals[0][0],
            basis=basis,
        )

    served_net = served_nets[0]
    service_pin = next(
        pin for _level, _basis, pin, net, host in best
        if net.id == served_net.id and host == host_id
    )
    host_pins = _pins_of(served_net, host_id)
    note = (
        f"{len(host_pins)} equivalent pins on the net are all kept; no single "
        "pin is chosen"
        if len(host_pins) > 1
        else "the host has one pin on the net"
    )
    return DecouplingService(
        part_id=part_id,
        status=STATUS_SERVED,
        reason=(
            f"{basis}: {host_id!r} is the host core of net {served_net.id!r} "
            f"and has {len(host_pins)} pin(s) there ({', '.join(host_pins)}); "
            f"{note}"
        ),
        net_id=served_net.id,
        host_id=host_id,
        host_module=host_module,
        host_pins=host_pins,
        host_candidates=(host_id,),
        service_pin=service_pin,
        return_pin=return_pin,
        basis=basis,
    )


def _candidate_levels(
    cap_id: str,
    net: SpecNet,
    presentation: PresentationSpec,
    own_modules: tuple[PresentationModule, ...],
) -> list[tuple[int, str, tuple[str, ...]]]:
    """Hosts on ``net``, grouped by the three stated priorities, best first.

    A core that has no pin on the net cannot be served by it, so it is not a
    candidate at any level. A module claiming to be its own capacitor's core is
    ignored for the same reason a part cannot serve itself.
    """

    def hosts(candidates: list[str]) -> tuple[str, ...]:
        return _ordered_unique(
            core
            for core in candidates
            if core and core != cap_id and _pins_of(net, core)
        )

    module_cores = hosts([module.core for module in own_modules])
    attach_cores = hosts(
        [
            host_module.core
            for module in own_modules
            if module.attach is not None
            for host_module in [presentation.module(module.attach.to)]
            if host_module is not None
        ]
    )
    netlist_cores = hosts([module.core for module in presentation.modules])

    levels: list[tuple[int, str, tuple[str, ...]]] = []
    for level, (basis, found) in enumerate(
        (
            (BASIS_MODULE_CORE, module_cores),
            (BASIS_ATTACH_CORE, attach_cores),
            (BASIS_NETLIST_CORE, netlist_cores),
        )
    ):
        if found:
            levels.append((level, basis, found))
    return levels


def _pins_of(net: SpecNet, part_id: str) -> tuple[str, ...]:
    pins: list[str] = []
    for member in net.members:
        split = _split_member(member)
        if split is not None and split[0] == part_id:
            pins.append(split[1])
    return tuple(pins)


def _is_ground(net: SpecNet) -> bool:
    return net.cls == "gnd" or is_ground_net(net.id)


def _ordered_unique(items) -> tuple:
    """The items in first-seen order, dropping ``None``/empty text and repeats."""
    seen: list[object] = []
    for item in items:
        if item is None or (isinstance(item, str) and not item):
            continue
        if item not in seen:
            seen.append(item)
    return tuple(seen)
