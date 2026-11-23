"""Shared EasyEDA netlist reading and instance-aware queries (563A).

The thin reader (:class:`NetlistPin` / :class:`NetlistPart` / :class:`Netlist`,
:func:`read_netlist_document`) used to live inside ``engines/drawlint.py``; the
draw pipeline's candidate projection parsed the *same* host document a second
time in ``core/candidate.py``. Two readers of one document is one reader too
many, so the thin one moved here and both consumers read this copy. The
drawlint names stay importable aliases, and every field the L12 electrical
gates read is unchanged.

:class:`NetlistView` is the query layer on top: pins are addressed **by
instance**, never by designator alone. Two host entries answering to ``U15``
are two *instances* — multi-unit packaging or a repeated placement, and the
name alone does not decide which — so a query that does not say which instance
it means is refused (:class:`AmbiguousPinError`) instead of answered by
whichever came first. The same law separates two pins of one number inside one
entry, which the host keys apart.

Nothing here derives circuit meaning. It reports the facts a netlist states —
which pin sits on which net, who else is there — and the disagreements the
document itself carries (repeated designators, unproven nets). ``parallel`` /
``series`` / decap style readings are a later projection (563B) and are
deliberately absent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .model import DesignModel

__all__ = [
    "AmbiguousPinError",
    "Netlist",
    "NetlistPart",
    "NetlistPin",
    "NetlistView",
    "PinRef",
    "UnknownPinError",
    "read_netlist_document",
]


# ------------------------------------------------------------- the thin reader


@dataclass
class NetlistPin:
    """One pin of one netlist component: its number, its name, its net.

    ``key`` is the host's own key in ``pinInfoMap`` (a list-shaped pin map has
    no keys, so its positional index is the surrogate), kept because it is part
    of a pin's *identity*: one host entry may carry two pins of the same number
    under different keys, and folding them by number alone would drop one.
    ``number`` is the pin number the document states.

    ``name`` is the gating reading: the document's name, or the pin number when
    the document spells none (L12's ``_numeric_pin_name`` depends on that).
    ``raw_name`` is the name **exactly as spelled**, ``""`` included — a
    projection onto the normalized model must keep an unnamed pin unnamed
    instead of borrowing its number (537d's ``pinName: ""``).
    """

    number: str
    name: str
    net: str
    key: str = ""
    raw_name: str = ""


@dataclass
class NetlistPart:
    """One netlist component, reduced to what the electrical gates read.

    ``source_id`` is the host entry key (the ``components`` mapping key), which
    is what makes two same-designator entries separately addressable;
    ``props`` is the property mapping the entry declares (``{}`` when it
    declares none — the whole component is **not** substituted, so a consumer
    reading values cannot mistake the entry's own keys for properties);
    ``entry_uid`` is the entry-level ``Unique ID``, which the candidate
    projection has always preferred over the property one.
    """

    designator: str
    pins: list[NetlistPin] = field(default_factory=list)
    source_id: str = ""
    props: dict[str, Any] = field(default_factory=dict)
    entry_uid: str = ""


@dataclass
class Netlist:
    """The parsed ``sch.netlist`` answer, only the electrical facts.

    Nothing here is a layout model: no values, no MPNs, no poses. The three
    gates in ``engines.drawlint.check_netlist_electrical`` are the electrical
    questions a *page* screenshot cannot answer, which is why they are a
    separate family and why a run without a netlist must never claim to have
    asked them.
    """

    parts: list[NetlistPart] = field(default_factory=list)

    def pin_nets(self) -> set[str]:
        return {pin.net for part in self.parts for pin in part.pins if pin.net}

    def pin_count(self) -> int:
        return sum(len(part.pins) for part in self.parts)


def read_netlist_document(document: Any) -> Netlist:
    """Parse the two shapes a netlist arrives in, or raise ``ValueError``.

    * the ``sch.netlist`` answer — ``{"type": "EasyEDA", "text": "<JSON>"}``
      (``text`` may also already be the decoded mapping);
    * the EasyEDA netlist itself — ``{"version": ..., "components": {...}}``.

    Anything else is a **refusal**, never a silent skip: the caller prints the
    reason and exits 2. A netlist this reader cannot understand is not
    evidence that the board is consistent.
    """
    payload: Any = document
    if isinstance(payload, dict) and "components" not in payload and "text" in payload:
        text = payload.get("text")
        if isinstance(text, str):
            try:
                payload = json.loads(text)
            except ValueError as exc:
                raise ValueError(f"the netlist `text` is not JSON ({exc})") from exc
        elif isinstance(text, dict):
            payload = text
    if not isinstance(payload, dict):
        raise ValueError("not a netlist document (expected a JSON object)")
    components = payload.get("components")
    if components is None:
        raise ValueError("no `components` member — this is not an EasyEDA netlist")
    if isinstance(components, dict):
        entries = list(components.items())
    elif isinstance(components, list):
        entries = [(str(index), row) for index, row in enumerate(components)]
    else:
        raise ValueError("`components` is neither a mapping nor a list")
    parts: list[NetlistPart] = []
    for key, component in entries:
        if not isinstance(component, dict):
            continue
        declared = component.get("props")
        props = declared if isinstance(declared, dict) else {}
        designator = str(props.get("Designator") or component.get("Designator") or "").strip()
        if not designator:
            continue
        pin_map = component.get("pinInfoMap")
        if not isinstance(pin_map, (dict, list)):
            pin_map = component.get("pins")
        pins: list[NetlistPin] = []
        if isinstance(pin_map, dict):
            pin_items = [(str(number), row) for number, row in pin_map.items()]
        elif isinstance(pin_map, list):
            # No host keys exist in a list-shaped pin map; the positional index
            # is the stable surrogate so two same-number pins stay two pins.
            pin_items = [(str(index), row) for index, row in enumerate(pin_map)]
        else:
            pin_items = []
        for number, info in pin_items:
            if not isinstance(info, dict):
                continue
            pin_number = str(info.get("number") or number or "")
            pin_props = info.get("props")
            raw_name = str(info.get("name") or "")
            name = str(
                info.get("name")
                or (pin_props.get("Pin Name") if isinstance(pin_props, dict) else "")
                or pin_number
            ).strip()
            pins.append(
                NetlistPin(
                    number=pin_number,
                    name=name,
                    net=str(info.get("net") or "").strip(),
                    key=number,
                    raw_name=raw_name,
                )
            )
        parts.append(
            NetlistPart(
                designator=designator,
                pins=pins,
                source_id="" if key is None else str(key),
                props=props,
                entry_uid=str(component.get("Unique ID") or ""),
            )
        )
    if not parts:
        raise ValueError("no component carries a designator — nothing to gate")
    return Netlist(parts=parts)


# ------------------------------------------------------------ instance identity


class AmbiguousPinError(LookupError):
    """A query named a pin that more than one instance answers to.

    Raised instead of picking one. Two same-designator host entries are two
    *instances* — multi-unit packaging or a repeated placement, and the name
    alone does not say which — so a caller that did not say which one it means
    cannot be answered. The same holds inside one entry: two pins of one
    number under different host keys are two pins.
    """


class UnknownPinError(LookupError):
    """A query named a pin, designator or instance this netlist does not hold."""


@dataclass(frozen=True)
class PinRef:
    """One **instance's** pin: ``DESIGNATOR.NUMBER`` plus its host identity.

    ``source_id`` is the host ``components`` key the instance came from (the
    model component's uid when the view is built from a :class:`DesignModel`),
    so two same-designator entries stay two addressable pins. ``pin_key`` is
    the host ``pinInfoMap`` key (a stable positional index for a model pin),
    which separates two pins of one number inside one entry.

    Equality and hashing cover all four fields: identity, not name. ``pin_key``
    empty means 「this reference did not name a key」 — a query may then match
    any key and is refused when that is more than one pin.

    A user string is split on the **last** dot — ``"U15.1"`` is designator
    ``U15``, pin ``1``, and a designator that itself carries dots
    (``"U9.3"``) stays whole when the string is ``"U9.3.1"``. Nothing is
    borrowed from a longer pin number: ``U9.3`` and ``U9.33`` are distinct.
    """

    designator: str
    number: str
    source_id: str = ""
    pin_key: str = ""

    @property
    def ref(self) -> str:
        return f"{self.designator}.{self.number}"

    @classmethod
    def parse(cls, text: str) -> "PinRef":
        """Split ``"DESIGNATOR.NUMBER"`` on its last dot."""
        designator, sep, number = str(text).rpartition(".")
        designator, number = designator.strip(), number.strip()
        if not sep or not designator or not number:
            raise ValueError(
                f"not a DESIGNATOR.NUMBER pin reference: {text!r}"
            )
        return cls(designator=designator, number=number)


def _split_pin(text: str, number: str) -> tuple[str, str]:
    """``("U15.1", "")`` / ``("U15", "1")`` -> ``("U15", "1")``; no guessing."""
    if number:
        return str(text).strip(), str(number).strip()
    ref = PinRef.parse(text)
    return ref.designator, ref.number


# ------------------------------------------------------------------- the view


class NetlistView:
    """Instance-aware queries over one netlist or one normalized model.

    Built from either source (:class:`Netlist` — the host document as read;
    :class:`DesignModel` — the merged/synthetic model the rest of the codebase
    holds). Members come from the source in its own order and keep repeated
    instances; pins are taken from the source's component table. A model that
    dropped a placement is not repaired here.

    Query law:

    - ``net_of`` refuses an unnamed-ambiguous pin (:class:`AmbiguousPinError`)
      and answers exactly once a ``source_id`` is given;
    - ``neighbors`` is "other pins on my net" and nothing else, so a
      single-member net has none;
    - ``nets_of`` follows the part's own pin order, deduplicated, and skips
      empty nets;
    - ``unconnected`` is exactly the empty-net pins — a named single-pin net is
      a statement of intent, not a dangling stub;
    - ``duplicate_designators`` discloses clashes; it never merges or picks.
    """

    def __init__(self, source: Netlist | DesignModel) -> None:
        self.source: Netlist | DesignModel = source
        self._members: dict[str, list[PinRef]] = {}
        self._pins: list[PinRef] = []
        self._instances: dict[PinRef, PinRef] = {}
        self._instance_ids: dict[str, list[str]] = {}
        self._nets_by_part: dict[tuple[str, str], list[str]] = {}
        self._net_by_pin: dict[PinRef, str] = {}
        self._duplicates: list[str] = []
        self._unproven: dict[str, tuple[str, ...]] = {}
        if isinstance(source, Netlist):
            self._read_netlist(source)
        elif isinstance(source, DesignModel):
            self._read_model(source)
        else:
            raise TypeError(
                "NetlistView reads a Netlist or a DesignModel, "
                f"not {type(source).__name__}"
            )

    # -- construction helpers

    @classmethod
    def from_netlist(cls, netlist: Netlist) -> "NetlistView":
        return cls(netlist)

    @classmethod
    def from_model(cls, model: DesignModel) -> "NetlistView":
        return cls(model)

    def _add_pin(self, ref: PinRef, net: str) -> None:
        """Register one instance pin; ``net`` is ``""`` for unconnected."""
        if ref not in self._instances:
            self._instances[ref] = ref
            self._pins.append(ref)
            ids = self._instance_ids.setdefault(ref.designator, [])
            if ref.source_id not in ids:
                ids.append(ref.source_id)
        if net:
            nets = self._nets_by_part.setdefault((ref.designator, ref.source_id), [])
            if net not in nets:
                nets.append(net)
            self._net_by_pin.setdefault(ref, net)

    def _read_netlist(self, netlist: Netlist) -> None:
        seen: dict[str, int] = {}
        for part in netlist.parts:
            seen[part.designator] = seen.get(part.designator, 0) + 1
            for pin in part.pins:
                ref = PinRef(part.designator, pin.number, part.source_id, pin.key)
                self._add_pin(ref, pin.net)
                if pin.net:
                    self._members.setdefault(pin.net, []).append(ref)
        self._duplicates = [name for name, count in seen.items() if count > 1]

    def _read_model(self, model: DesignModel) -> None:
        for designator, component in model.components.items():
            source_id = str(getattr(component, "uid", "") or "")
            for index, pin in enumerate(component.pins):
                # A model pin has no host key; its position inside the
                # component is the stable one, and it keeps two same-number
                # pins of one component two pins (it invents no pin).
                ref = PinRef(designator, str(pin.number), source_id, str(index))
                self._add_pin(ref, (pin.net or "").strip())
        # Membership is whatever the model states (``model.nets``), in its own
        # order, repeated instances included. A member whose component the
        # model no longer holds is listed — that is the model's fact — but it
        # is not made addressable, because no pin of it survives to read. A
        # member whose number matches more than one pin of its component keeps
        # ``pin_key=""``: the model did not say which pin it meant, and this
        # reading will not claim it resolved one.
        for name, node in (model.nets or {}).items():
            for designator, number in node.pins:
                component = model.components.get(str(designator))
                source_id = str(getattr(component, "uid", "") or "") if component else ""
                pin_key = ""
                if component is not None:
                    matches = [
                        str(index)
                        for index, item in enumerate(component.pins)
                        if str(item.number) == str(number)
                    ]
                    if len(matches) == 1:
                        pin_key = matches[0]
                self._members.setdefault(name, []).append(
                    PinRef(str(designator), str(number), source_id, pin_key)
                )
        self._duplicates = [str(name) for name in (model.duplicate_designators or [])]
        self._unproven = {
            str(name): tuple(pages) for name, pages in (model.unproven_nets or {}).items()
        }

    # -- lookups

    def _instances_of(
        self,
        designator: str,
        *,
        number: str | None = None,
        source_id: str | None = None,
        pin_key: str | None = None,
    ) -> list[PinRef]:
        out: list[PinRef] = []
        for ref in self._instances:
            if ref.designator != designator:
                continue
            if number is not None and ref.number != number:
                continue
            if source_id is not None and ref.source_id != source_id:
                continue
            if pin_key is not None and ref.pin_key != pin_key:
                continue
            out.append(ref)
        return out

    def _resolve(
        self, designator: str | PinRef, number: str = "", source_id: str | None = None
    ) -> PinRef:
        if isinstance(designator, PinRef):
            matches = self._instances_of(
                designator.designator,
                number=designator.number,
                source_id=(
                    source_id if source_id is not None else (designator.source_id or None)
                ),
                pin_key=designator.pin_key or None,
            )
        else:
            wanted_designator, wanted_number = _split_pin(designator, number)
            matches = self._instances_of(
                wanted_designator, number=wanted_number, source_id=source_id
            )
        if not matches:
            label = designator if isinstance(designator, str) else designator.ref
            raise UnknownPinError(f"no pin {label} in this netlist")
        if len(matches) > 1:
            label = matches[0].ref
            others = ", ".join(
                f"{ref.source_id or '<no source id>'}:{ref.pin_key or '<no key>'}"
                for ref in matches
            )
            raise AmbiguousPinError(
                f"pin {label} is addressed by {len(matches)} instances ({others}) "
                "— name the source_id and pin key, this reading will not pick one"
            )
        return matches[0]

    # -- readings

    def members(self, net: str) -> tuple[PinRef, ...]:
        """Every pin the source places on ``net``, in source order."""
        return tuple(self._members.get(net or "", ()))

    def net_names(self) -> tuple[str, ...]:
        """Net names in first-appearance order (empty nets are not nets)."""
        return tuple(self._members)

    def pin_refs(self) -> tuple[PinRef, ...]:
        """Every addressable instance pin, in source order."""
        return tuple(self._pins)

    def net_of(
        self, designator: str | PinRef, number: str = "", source_id: str | None = None
    ) -> str:
        """The net one instance pin sits on; ``""`` when it sits on none."""
        ref = self._resolve(designator, number, source_id)
        return self._net_by_pin.get(ref, "")

    def neighbors(
        self, designator: str | PinRef, number: str = "", source_id: str | None = None
    ) -> tuple[PinRef, ...]:
        """The *other* pins on this pin's net — ``()`` if it has no net or sits
        alone on one. A single-member auto net is not a connection."""
        ref = self._resolve(designator, number, source_id)
        net = self._net_by_pin.get(ref, "")
        if not net:
            return ()
        return tuple(other for other in self._members.get(net, ()) if other != ref)

    def nets_of(self, designator: str, source_id: str | None = None) -> tuple[str, ...]:
        """The nets one part's pins sit on, in pin order, deduplicated."""
        name = str(designator).strip()
        ids = list(self._instance_ids.get(name, ()))
        if source_id is not None:
            if source_id not in ids:
                raise UnknownPinError(
                    f"no part {name} with source_id {source_id!r} in this netlist"
                )
            ids = [source_id]
        elif not ids:
            raise UnknownPinError(f"no part {name} in this netlist")
        elif len(ids) > 1:
            raise AmbiguousPinError(
                f"part {name} is addressed by {len(ids)} instances "
                f"({', '.join(source or '<no source id>' for source in ids)}) "
                "— name the source_id, this reading will not pick one"
            )
        out: list[str] = []
        for source in ids:
            for net in self._nets_by_part.get((name, source), ()):
                if net not in out:
                    out.append(net)
        return tuple(out)

    def unconnected(self) -> tuple[PinRef, ...]:
        """The empty-net pins, in source order. A named one-pin net is not one."""
        return tuple(ref for ref in self._pins if not self._net_by_pin.get(ref))

    def duplicate_designators(self) -> tuple[str, ...]:
        """Designators more than one instance answers to, in source order."""
        return tuple(self._duplicates)

    def ambiguous_designators(self) -> tuple[str, ...]:
        """Every designator this view cannot resolve to exactly one instance.

        For a raw netlist that is exactly :meth:`duplicate_designators`: the
        document states repeated entries and says nothing more. For a model it
        is ``model.repeated_designators()`` — the duplicates **and** the
        same-name placements the merge saw on different pages, which it cannot
        tell apart either. Disclosure only: 563B excludes these names from any
        functional projection, and nothing here merges or judges them.
        """
        if isinstance(self.source, DesignModel):
            return tuple(str(name) for name in self.source.repeated_designators())
        return tuple(self._duplicates)

    @property
    def unproven_nets(self) -> dict[str, tuple[str, ...]]:
        """``model.unproven_nets`` as disclosed (empty for a raw Netlist).

        Disclosure only: 563A derives nothing from it, least of all a
        connection. A name here means membership was welded by name, not read.
        """
        return dict(self._unproven)
