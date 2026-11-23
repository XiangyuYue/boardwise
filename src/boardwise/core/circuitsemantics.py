"""Verifiable circuit semantics compiled from one netlist view (563B).

563A answered *what the document states*: which instance pin sits on which net,
who else is on it, which names clash or are unproven. This module is the next
layer — still a pure function, still no host call and no file — and it compiles
that view into one versioned document, ``boardwise.circuitSemantics/1``, plus a
deterministic C-like rendering of it. It is a **projection**, not an
interpretation: the document keeps the raw facts (every part, every pin, every
net member, empty nets included) as the verification base, states the two
derivations the netlist alone can support (``parallel`` / ``series``), and
names what it refused to derive as ``unknowns``.

**Only topology, never function.** ``two_pin`` records a unique designator with
exactly two pins and each pin's net; it does not say resistor, capacitor,
diode, or which way current flows. ``parallel`` needs two such parts whose two
non-empty, distinct nets form the *same* unordered pair — one record per pair,
nets sorted only to canonicalise, never to imply an end. ``series`` linearises
two-pin parts joined by internal nets that carry **exactly two** distinct device
pins, so a ``MID`` net with a third pin is not a chain link; chains are maximal
and simple, and their order is geometric, not electrical. Each chain states its
**two end nets** as well, so ``len(nets) == len(parts) + 1`` and an empty end
net stays empty — a reader of ``series`` alone can see the whole path. Two parts
joined by one internal net whose two far ends sit on the same net (or on no net
at all) are the parallel / dangling pair the netlist states elsewhere, not a
chain. A chain that would end on an unproven name is withheld rather than
asserted. Nothing here reads a net *name* for meaning: no ``decap``, no
``filter``, no ground/rail/supply function, no signal direction, no cross-board
same-name tie.

**Refusals are recorded, not guessed.** A designator the view cannot resolve to
one instance (repeated placement, same-name cross-page part) keeps all of its
raw pins and nets but is excluded from ``two_pin``/``parallel``/``series`` and
appears in ``unknowns``. Every net the model marks unproven is disclosed and
derives no relation — a welded-by-name net is not a connection. A ring of three
or more two-pin parts is a cycle with no honest starting point: it is recorded
as a cycle, never emitted as a ``series``. (Two parts joined at both ends are
the parallel case, not a ring, and are reported once, there.)

**Determinism and verification.** Every array follows the source's own order
(parts and pins by first appearance, net members as the source lists them), the
derived lists are sorted by identity, and ``as_dict`` hands out a deep copy. The
C-like text uses ASCII-escaped string literals so the same program renders to
byte-identical output. ``verify_semantics`` recompiles the view and compares the
**whole** structure, so an edited pin, net, unknown, relation or empty-net entry
fails; ``roundtrip_members`` compares only the raw per-pin/per-net facts and is
what a consumer re-reads the base with. Neither accepts a program it did not
compile from this view, and this batch deliberately ships **no** C parser: the
text is a projection an outside tool may read, not a second input format.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any

from .model import DesignModel
from .netlist import Netlist, NetlistView, PinRef

__all__ = [
    "SCHEMA",
    "SCHEMA_HEADER",
    "SemanticProgram",
    "compile_semantics",
    "roundtrip_members",
    "verify_semantics",
]

#: The one schema string this module reads and writes.
SCHEMA = "boardwise.circuitSemantics/1"
#: The C-like text starts with this line; it is the whole format contract.
SCHEMA_HEADER = f"// {SCHEMA}"

_Part = tuple[str, str]  # (designator, source_id) — an instance, not a name


# ------------------------------------------------------------------ the facts


def _pin_identity(ref: PinRef) -> dict[str, Any]:
    """A pin's **identity** only: number, host entry, host pin key."""
    return {
        "designator": ref.designator,
        "number": ref.number,
        "source_id": ref.source_id,
        "pin_key": ref.pin_key,
    }


def _part_fact(key: _Part) -> dict[str, Any]:
    return {"designator": key[0], "source_id": key[1]}


def _part_sort_key(part: dict[str, Any]) -> tuple[str, str]:
    return (str(part["designator"]), str(part["source_id"]))


def _pin_names(view: NetlistView) -> dict[PinRef, str]:
    """Each addressable pin's **spelled** name; ``""`` when none is spelled.

    The view answers connectivity, not names, so the names are read from the
    same source the view was built on, with the identity rules 563A states: the
    host entry key plus the ``pinInfoMap`` key for a document, the component uid
    plus the pin position for a model. A pin whose name the document leaves out
    keeps ``""`` rather than borrowing its number — this projection must not
    spell a name the netlist never spelled.
    """
    names: dict[PinRef, str] = {}
    source = view.source
    if isinstance(source, Netlist):
        for part in source.parts:
            for pin in part.pins:
                ref = PinRef(part.designator, pin.number, part.source_id, pin.key)
                names[ref] = pin.raw_name
    elif isinstance(source, DesignModel):
        for designator, component in source.components.items():
            uid = str(getattr(component, "uid", "") or "")
            for index, pin in enumerate(component.pins):
                names[PinRef(str(designator), str(pin.number), uid, str(index))] = str(
                    getattr(pin, "name", "") or ""
                )
    return names


@dataclass
class _Facts:
    """The raw projection, plus the index the derivations walk."""

    parts: list[dict[str, Any]] = field(default_factory=list)
    pins: list[dict[str, Any]] = field(default_factory=list)
    nets: list[dict[str, Any]] = field(default_factory=list)
    unconnected: list[dict[str, Any]] = field(default_factory=list)
    order: list[_Part] = field(default_factory=list)
    part_pins: dict[_Part, list[PinRef]] = field(default_factory=dict)
    by_ref: dict[PinRef, dict[str, Any]] = field(default_factory=dict)
    members: dict[str, tuple[PinRef, ...]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "parts": copy.deepcopy(self.parts),
            "pins": copy.deepcopy(self.pins),
            "nets": copy.deepcopy(self.nets),
            "unconnected": copy.deepcopy(self.unconnected),
        }


def _facts(view: NetlistView) -> _Facts:
    """Every part, pin, net member and empty-net pin the view states."""
    names = _pin_names(view)
    facts = _Facts()
    for ref in view.pin_refs():
        key: _Part = (ref.designator, ref.source_id)
        if key not in facts.part_pins:
            facts.part_pins[key] = []
            facts.order.append(key)
        facts.part_pins[key].append(ref)
        pin = {
            "designator": ref.designator,
            "number": ref.number,
            "source_id": ref.source_id,
            "pin_key": ref.pin_key,
            "name": names.get(ref, ""),
            "net": view.net_of(ref),
        }
        facts.pins.append(pin)
        facts.by_ref[ref] = pin
    for key in facts.order:
        fact = _part_fact(key)
        fact["pin_count"] = len(facts.part_pins[key])
        facts.parts.append(fact)
    for name in view.net_names():
        members = view.members(name)
        facts.members[name] = members
        facts.nets.append(
            {"name": name, "members": [_pin_identity(ref) for ref in members]}
        )
    facts.unconnected = [_pin_identity(ref) for ref in view.unconnected()]
    return facts


# -------------------------------------------------------------- the relations


def _two_pin(facts: _Facts, ambiguous: frozenset[str]) -> list[dict[str, Any]]:
    """Unique-designator parts with exactly two pins: pin identities and nets.

    No type, no polarity, no direction — an empty net stays ``""`` here so a
    half-connected two-pin part is still a two-pin part, and the derivations
    below are what refuse to relate it.
    """
    records: list[dict[str, Any]] = []
    for key in facts.order:
        if key[0] in ambiguous:
            continue
        refs = facts.part_pins[key]
        if len(refs) != 2:
            continue
        records.append(
            {
                "part": _part_fact(key),
                "pins": [
                    {
                        "number": facts.by_ref[ref]["number"],
                        "pin_key": facts.by_ref[ref]["pin_key"],
                        "name": facts.by_ref[ref]["name"],
                        "net": facts.by_ref[ref]["net"],
                    }
                    for ref in refs
                ],
            }
        )
    return records


def _parallel(
    two_pin: list[dict[str, Any]], unproven: frozenset[str]
) -> list[dict[str, Any]]:
    """One record per net pair shared by two or more eligible two-pin parts."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in two_pin:
        first, second = (pin["net"] for pin in record["pins"])
        if not first or not second or first == second:
            continue
        if first in unproven or second in unproven:
            continue
        pair = (first, second) if first < second else (second, first)
        groups.setdefault(pair, []).append(record["part"])
    out: list[dict[str, Any]] = []
    for pair in sorted(groups):
        parts = sorted(groups[pair], key=_part_sort_key)
        if len(parts) < 2:
            continue
        out.append({"parts": parts, "between": [pair[0], pair[1]]})
    return out


def _part_owner(
    facts: _Facts, two_pin: list[dict[str, Any]]
) -> dict[PinRef, _Part]:
    owner: dict[PinRef, _Part] = {}
    for record in two_pin:
        key = (record["part"]["designator"], record["part"]["source_id"])
        for ref in facts.part_pins[key]:
            owner[ref] = key
    return owner


def _degree(
    facts: _Facts,
    owner: dict[PinRef, _Part],
    unproven: frozenset[str],
) -> tuple[dict[_Part, list[tuple[str, _Part]]], dict[_Part, list[str]]]:
    """Adjacency and per-part incident nets over the two-degree internal nets.

    A net is a chain link only when it carries **exactly two distinct** device
    pins of two **different** eligible two-pin parts and is not unproven. A
    third pin (the ``MID`` counter-example), a pin of an ineligible part, a net
    welded by name, or both pins of one part are all "not a link" — the honest
    reading of the netlist alone, with nothing repaired.
    """
    links: dict[str, tuple[_Part, _Part]] = {}
    incident: dict[_Part, list[str]] = {}
    for name, members in facts.members.items():
        if name in unproven:
            continue
        distinct: list[PinRef] = []
        for ref in members:
            if ref not in distinct:
                distinct.append(ref)
        if len(distinct) != 2:
            continue
        first, second = owner.get(distinct[0]), owner.get(distinct[1])
        if first is None or second is None or first == second:
            continue
        links[name] = (first, second)
        incident.setdefault(first, []).append(name)
        incident.setdefault(second, []).append(name)
    # A part that met more than two two-degree nets cannot sit on a simple
    # chain; it is not linearised rather than guessed at.
    for key, names in list(incident.items()):
        if len(names) > 2:
            del incident[key]
    adjacency: dict[_Part, list[tuple[str, _Part]]] = {}
    for name, (first, second) in links.items():
        if first not in incident or second not in incident:
            continue
        adjacency.setdefault(first, []).append((name, second))
        adjacency.setdefault(second, []).append((name, first))
    return adjacency, incident


def _walk(
    adjacency: dict[_Part, list[tuple[str, _Part]]], start: _Part
) -> tuple[list[_Part], list[str]]:
    """Follow the one unused link at each step until an end or a revisit."""
    parts: list[_Part] = [start]
    nets: list[str] = []
    previous = ""
    current = start
    while True:
        options = [
            (net, other)
            for net, other in adjacency.get(current, [])
            if net != previous and other not in parts
        ]
        if not options:
            break
        net, following = options[0]
        nets.append(net)
        parts.append(following)
        previous, current = net, following
        if len(adjacency.get(current, [])) != 2:
            break
    return parts, nets


def _walk_cycle(
    adjacency: dict[_Part, list[tuple[str, _Part]]], start: _Part
) -> tuple[list[_Part], list[str]]:
    """Walk a ring from ``start`` and close it with the net back to ``start``."""
    parts: list[_Part] = [start]
    nets: list[str] = []
    previous = ""
    current = start
    while True:
        options = [
            (net, other) for net, other in adjacency.get(current, []) if net != previous
        ]
        if not options:
            break
        net, following = options[0]
        if following == start:
            nets.append(net)
            break
        if following in parts:
            break
        nets.append(net)
        parts.append(following)
        previous, current = net, following
    return parts, nets


def _end_net(facts: _Facts, key: _Part, adjacent: str) -> str:
    """The net a chain-end part sits on besides the chain link itself.

    ``""`` is a real answer — an unconnected end is stated as an empty end net,
    not folded away, or the chain would lose one of its two ends.
    """
    for ref in facts.part_pins[key]:
        net = facts.by_ref[ref]["net"]
        if net != adjacent:
            return net
    return ""


def _series(
    facts: _Facts,
    two_pin: list[dict[str, Any]],
    unproven: frozenset[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Maximal simple chains, and the rings that have no honest starting point."""
    owner = _part_owner(facts, two_pin)
    adjacency, incident = _degree(facts, owner, unproven)
    visited: set[_Part] = set()
    chains: list[tuple[list[_Part], list[str]]] = []
    for key in facts.order:
        if key in visited or len(adjacency.get(key, [])) != 1:
            continue
        parts, internal = _walk(adjacency, key)
        visited.update(parts)
        if len(parts) < 2 or len(internal) != len(parts) - 1:
            continue
        start_end = _end_net(facts, parts[0], internal[0])
        end_end = _end_net(facts, parts[-1], internal[-1])
        nets = [start_end, *internal, end_end]
        # A chain that ends on a name the model calls unproven is not a chain
        # this reading can stand behind: the terminal would be welded, not read.
        if {start_end, end_end} & unproven:
            continue
        # Two parts meeting on one internal net whose far ends sit on the same
        # net (or on no net at all) are the parallel / dangling pair, which the
        # netlist states as such; a two-part "chain" would restate it wrongly.
        if len(parts) == 2 and start_end == end_end:
            continue
        if parts[-1] < parts[0]:
            parts, nets = parts[::-1], nets[::-1]
        chains.append((parts, nets))
    cycles: list[tuple[list[_Part], list[str]]] = []
    for key in facts.order:
        if key in visited or len(adjacency.get(key, [])) != 2:
            continue
        parts, nets = _walk_cycle(adjacency, key)
        visited.update(parts)
        # Two parts joined at both ends are the parallel case, already stated
        # once there; only a ring of three or more is an unlinearisable cycle.
        if len(parts) < 3 or len(nets) != len(parts):
            continue
        cycles.append((parts, nets))
    series = [
        {"parts": [_part_fact(key) for key in parts], "nets": nets}
        for parts, nets in sorted(chains, key=lambda item: tuple(item[0]))
    ]
    unknown_cycles = [
        {"kind": "cycle", "parts": [_part_fact(key) for key in parts], "nets": nets}
        for parts, nets in sorted(cycles, key=lambda item: tuple(item[0]))
    ]
    return series, unknown_cycles


def _unknowns(view: NetlistView, cycles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What was refused, and why — sorted, disclosed, never concluded."""
    out: list[dict[str, Any]] = [
        {"kind": "ambiguous_designator", "designator": name}
        for name in sorted(view.ambiguous_designators())
    ]
    unproven = view.unproven_nets
    out.extend(
        {"kind": "unproven_net", "net": name, "pages": list(unproven[name])}
        for name in sorted(unproven)
    )
    out.extend(cycles)
    return out


# ---------------------------------------------------------------- the program


class SemanticProgram:
    """One compiled ``boardwise.circuitSemantics/1`` document.

    Construction copies what it is given, so a caller that keeps editing its
    dict cannot mutate the program behind its back — and a tampered dict passed
    to :func:`verify_semantics` stays tampered and fails there.
    """

    __slots__ = ("_payload",)

    def __init__(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise TypeError(f"not a semantic program: {type(payload).__name__}")
        self._payload = copy.deepcopy(payload)

    @property
    def schema(self) -> str:
        return str(self._payload.get("schema", ""))

    def as_dict(self) -> dict[str, Any]:
        """A deep copy of the whole program — editing it edits nothing."""
        return copy.deepcopy(self._payload)

    def to_c(self) -> str:
        return _render(self._payload)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"SemanticProgram(schema={self.schema!r}, parts={len(self._payload.get('parts', []))})"


def compile_semantics(view: NetlistView) -> SemanticProgram:
    """Compile one view into the versioned structure. Pure, deterministic."""
    if not isinstance(view, NetlistView):
        raise TypeError(
            f"compile_semantics reads a NetlistView, not {type(view).__name__}"
        )
    facts = _facts(view)
    ambiguous = frozenset(view.ambiguous_designators())
    unproven = frozenset(view.unproven_nets)
    two_pin = _two_pin(facts, ambiguous)
    parallel = _parallel(two_pin, unproven)
    series, cycles = _series(facts, two_pin, unproven)
    payload = {
        "schema": SCHEMA,
        "parts": facts.parts,
        "pins": facts.pins,
        "nets": facts.nets,
        "unconnected": facts.unconnected,
        "relations": {
            "two_pin": two_pin,
            "parallel": parallel,
            "series": series,
        },
        "unknowns": _unknowns(view, cycles),
    }
    return SemanticProgram(payload)


def _payload_of(program: SemanticProgram | dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(program, SemanticProgram):
        try:
            return program.as_dict()
        except Exception:  # pragma: no cover - a program cannot fail to copy
            return None
    if isinstance(program, dict):
        return program
    return None


def verify_semantics(
    view: NetlistView, program: SemanticProgram | dict[str, Any]
) -> bool:
    """Recompile the view and compare the **whole** structure.

    An edited pin, net, unknown, relation or empty-net entry, a dropped array or
    a changed schema all answer ``False`` — the comparison is the full document,
    not the relations alone, so the raw facts are verified too.
    """
    payload = _payload_of(program)
    if payload is None:
        return False
    return payload == compile_semantics(view).as_dict()


def roundtrip_members(
    view: NetlistView, program: SemanticProgram | dict[str, Any]
) -> bool:
    """Compare the program's raw facts against the view's, per pin and per net.

    This is the base a consumer re-reads: repeated instances, the two pins of
    one number, empty-net pins and net members the model can no longer resolve
    must all come back exactly as stated. Relations and unknowns are not this
    function's business.
    """
    payload = _payload_of(program)
    if payload is None:
        return False
    facts = _facts(view).as_dict()
    return all(payload.get(name) == facts[name] for name in facts)


# ------------------------------------------------------------- the C-like text


def _q(text: Any) -> str:
    """One ASCII-only, escaped string literal — same text, same bytes."""
    return json.dumps(str(text), ensure_ascii=True)


def _part_token(part: dict[str, Any]) -> str:
    token = str(part["designator"])
    if part["source_id"]:
        token += "@" + str(part["source_id"])
    return token


def _pin_token(fact: dict[str, Any]) -> str:
    token = f"{fact['designator']}.{fact['number']}"
    if fact["source_id"]:
        token += "@" + str(fact["source_id"])
    if fact["pin_key"]:
        token += "#" + str(fact["pin_key"])
    return token


def _two_pin_token(pin: dict[str, Any]) -> str:
    """``NUMBER#PIN_KEY:NET`` — the key keeps two same-number pins apart.

    An empty key adds no ``#``: the token then says exactly what the source
    says, rather than inventing a key to fill the shape.
    """
    token = str(pin["number"])
    if pin["pin_key"]:
        token += "#" + str(pin["pin_key"])
    return token + ":" + str(pin["net"])


def _render(payload: dict[str, Any]) -> str:
    """Render the program as deterministic ``function(...)`` text."""
    lines = [SCHEMA_HEADER]
    for part in payload.get("parts", []):
        lines.append(
            f"part({_q(part['designator'])}, {_q(part['source_id'])}, "
            f"pins={part['pin_count']});"
        )
    for pin in payload.get("pins", []):
        lines.append(
            "pin("
            + ", ".join(
                [
                    _q(pin["designator"]),
                    _q(pin["number"]),
                    _q(pin["source_id"]),
                    _q(pin["pin_key"]),
                    _q(pin["name"]),
                    _q(pin["net"]),
                ]
            )
            + ");"
        )
    for net in payload.get("nets", []):
        members = ", ".join(_q(_pin_token(ref)) for ref in net["members"])
        lines.append(f"net({_q(net['name'])}, [{members}]);")
    for fact in payload.get("unconnected", []):
        lines.append(f"unconnected({_q(_pin_token(fact))});")
    relations = payload.get("relations", {})
    for record in relations.get("two_pin", []):
        pins = ", ".join(_q(_two_pin_token(pin)) for pin in record["pins"])
        lines.append(f"two_pin({_q(_part_token(record['part']))}, [{pins}]);")
    for record in relations.get("parallel", []):
        parts = ", ".join(_q(_part_token(part)) for part in record["parts"])
        between = ", ".join(_q(net) for net in record["between"])
        lines.append(f"parallel([{parts}], [{between}]);")
    for record in relations.get("series", []):
        parts = ", ".join(_q(_part_token(part)) for part in record["parts"])
        nets = ", ".join(_q(net) for net in record["nets"])
        lines.append(f"series([{parts}], [{nets}]);")
    for unknown in payload.get("unknowns", []):
        kind = str(unknown.get("kind", ""))
        if kind == "ambiguous_designator":
            lines.append(
                f"unknown({_q(kind)}, {_q(unknown['designator'])});"
            )
        elif kind == "unproven_net":
            pages = ", ".join(_q(page) for page in unknown.get("pages", []))
            lines.append(f"unknown({_q(kind)}, {_q(unknown['net'])}, [{pages}]);")
        elif kind == "cycle":
            parts = ", ".join(_q(_part_token(part)) for part in unknown["parts"])
            nets = ", ".join(_q(net) for net in unknown["nets"])
            lines.append(f"unknown({_q(kind)}, [{parts}], [{nets}]);")
        else:
            lines.append(f"unknown({_q(kind)});")
    return "\n".join(lines) + "\n"
