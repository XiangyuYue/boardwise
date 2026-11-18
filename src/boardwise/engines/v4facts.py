"""Read-only facts from a V4 (``.eprj3``) folder project — ``boardwise.v4-facts/1``.

The V4 audit (``evidence/v4-info-audit.md``) proved there is **no V4-only
semantic field**: an ``.eprj3`` project is the same record stream an ``.epro2``
carries, cut into one file per page. Its real advantage is attribution — which
page a flag/label/pin came from — and two distinctions the shared ``DesignModel``
merges away: a ``Global Net Name`` **flag** versus a page ``NET`` **label**, and
the raw ``Pin Type`` code. This module is the thin evidence layer for those
distinctions. It reads; it does not build a model, a layout or a second parser.

What it deliberately does **not** do:

* it never maps ``Pin Type`` (``"1"``, ``"Power"``, …) to a direction or an
  electrical function — the code table is not calibrated;
* it never derives ``class`` from a net name. ``gnd`` / ``power`` come only from
  the flag symbol's own ``META.title`` (``Ground-*`` / ``Power-*``), otherwise
  the class stays ``""``;
* it never treats a same-named flag on two pages (or a flag plus a label) as
  proof that the pages are electrically connected. ``crossPageConnectivityProven``
  is always ``False`` and :func:`open_questions` says so;
* it does not extract BUS/BUSENTRY members — it only counts the records.

The output is ordinary JSON-safe Python data, deterministic under
``json.dumps(..., sort_keys=True)``: reads follow the parser's path/stream order,
and every list is built in that order (or explicitly sorted).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from ..core.circuitspec import CircuitSpec, DEFAULT_NET_CLASS
from ..core.presentationspec import PresentationModule, PresentationSpec
from ..core.symbolprofile import SymbolPose
from ..parsers.eprj3 import load_eprj3_text
from ..parsers.epru_stream import iter_epru_records
from ..parsers.schematic import build_project_model

#: Schema id of the fact document this module returns.
SCHEMA = "boardwise.v4-facts/1"

#: The attribute key of a power/ground **flag** instance (project scope).
FLAG_KEY = "Global Net Name"
#: The attribute key of a page **net label** (page scope).
LABEL_KEY = "NET"


def _text(value: Any) -> str:
    """The record field as the string it is; ``None`` becomes ``""``."""
    return "" if value is None else str(value)


def _class_from_symbol_title(title: str) -> str:
    """``Ground-*`` → ``gnd``, ``Power-*`` → ``power``, anything else → ``""``.

    The title arrives from the symbol's own ``META.title``; a net *name* never
    reaches this function. The literal prefixes are the audit's contract, so a
    title such as ``"GND"`` stays unclassified instead of being guessed.
    """
    if title.startswith("Ground-"):
        return "gnd"
    if title.startswith("Power-"):
        return "power"
    return ""


def _page_keys(evidence: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Distinct ``(pageUuid, page)`` pairs of one net's evidence, sorted."""
    return sorted(
        {
            (_text(entry.get("pageUuid")), _text(entry.get("page")))
            for entry in evidence
        }
    )


def select_board_model(path: str | Path, board: str = ""):
    """Return one board model/ref, never a merged multi-board approximation."""
    project = build_project_model(path)
    titles = project.board_titles()
    if len(project.boards) > 1 and not board:
        raise ValueError(
            "this is a multi-board project; select --board explicitly: "
            + ", ".join(titles)
        )
    if board:
        matches = [
            item for item in project.boards
            if item.board.uuid == board or item.board.title == board
        ]
        if len(matches) != 1:
            raise ValueError(
                f"board {board!r} does not identify exactly one board; choices: "
                + ", ".join(titles)
            )
        selected = matches[0]
    elif project.boards:
        selected = project.boards[0]
    else:
        raise ValueError("the project contains no board model")
    return selected, selected.board


def read_v4_facts(path: str | Path, board: str = "") -> dict[str, Any]:
    """Read one ``.eprj3`` project (index file or folder) into evidence facts.

    Records come from :func:`~boardwise.parsers.eprj3.load_eprj3_text` — the one
    existing V4 container reader, y-flip included — and are decoded with
    :func:`~boardwise.parsers.epru_stream.iter_epru_records`. Document heads are
    used only to attribute a record to a page or a SYMBOL document; no second
    parser and no ``DesignModel`` is built.
    """

    _selected_model, selected_board = select_board_model(path, board)
    selected_pages = set(selected_board.page_uuids)
    text, meta = load_eprj3_text(path)
    page_names = [_text(name) for name in (meta.get("pages") or [])]

    pages: list[dict[str, str]] = []
    net_evidence: dict[str, list[dict[str, str]]] = {}
    net_order: list[str] = []
    symbols: dict[str, dict[str, Any]] = {}
    symbol_order: list[str] = []
    instance_symbols: dict[tuple[str, str], str] = {}
    instance_designators: dict[tuple[str, str], str] = {}
    instance_rows: list[dict[str, Any]] = []
    bus_counts = {"BUS": 0, "BUSENTRY": 0}

    current_page_uuid = ""
    current_page_name = ""
    page_seen = 0
    symbol_buffer: list[Any] = []

    def commit_symbol() -> None:
        """Turn the buffered SYMBOL document into one ``symbols`` entry."""
        nonlocal symbol_buffer
        if not symbol_buffer:
            return
        head = symbol_buffer[0].body or {}
        uuid = _text(head.get("uuid"))
        title = ""
        pins: dict[str, dict[str, str]] = {}
        pin_order: list[dict[str, str]] = []
        for record in symbol_buffer[1:]:
            body = record.body or {}
            if record.type == "META":
                if not title:
                    title = _text(body.get("title"))
                continue
            if record.type == "PIN":
                pin_id = _text(record.id)
                pin = {"number": "", "name": "", "pinType": ""}
                pins[pin_id] = pin
                pin_order.append(pin)
                continue
            if record.type != "ATTR":
                continue
            pin = pins.get(_text(body.get("parentId")))
            if pin is None:
                continue
            key = _text(body.get("key"))
            value = _text(body.get("value"))
            if key == "Pin Number":
                pin["number"] = value
            elif key == "Pin Name":
                pin["name"] = value
            elif key == "Pin Type":
                # Verbatim: no direction/electrical mapping happens here.
                pin["pinType"] = value
        if uuid and uuid not in symbols:
            symbols[uuid] = {"uuid": uuid, "title": title, "pins": pin_order}
            symbol_order.append(uuid)
        symbol_buffer = []

    for record in iter_epru_records(text):
        body = record.body or {}

        if record.type == "DOCHEAD":
            commit_symbol()
            doc_type = _text(body.get("docType"))
            if doc_type == "SCH_PAGE":
                page_uuid = _text(body.get("uuid"))
                page_name = (
                    page_names[page_seen] if page_seen < len(page_names) else ""
                )
                pages.append({"uuid": page_uuid, "name": page_name})
                current_page_uuid = page_uuid
                current_page_name = page_name
                page_seen += 1
            elif doc_type == "SYMBOL":
                symbol_buffer = [record]
            continue

        if record.type == "COMPONENT":
            part_id = _text(body.get("partId"))
            if part_id and current_page_uuid:
                instance_rows.append({
                    "partId": part_id,
                    "instanceId": _text(record.id),
                    "designator": "",
                    "symbolUuid": "",
                    "symbolTitle": "",
                    "pageUuid": current_page_uuid,
                    "page": current_page_name,
                    "rotation": body.get("rotation", 0),
                    "isMirror": bool(body.get("isMirror", False)),
                })
            continue

        if record.type == "BUS":
            bus_counts["BUS"] += 1
        elif record.type == "BUSENTRY":
            bus_counts["BUSENTRY"] += 1

        if symbol_buffer:
            symbol_buffer.append(record)

        if record.type != "ATTR":
            continue
        parent_id = _text(body.get("parentId"))
        key = _text(body.get("key"))
        value = _text(body.get("value"))
        if key == "Symbol" and parent_id:
            instance_symbols[(current_page_uuid, parent_id)] = value
        elif key == "Designator" and parent_id:
            instance_designators[(current_page_uuid, parent_id)] = value
        if key not in (FLAG_KEY, LABEL_KEY) or not value:
            continue
        kind = "flag" if key == FLAG_KEY else "label"
        if value not in net_evidence:
            net_evidence[value] = []
            net_order.append(value)
        net_evidence[value].append(
            {
                "kind": kind,
                "pageUuid": current_page_uuid,
                "page": current_page_name,
                "parentId": parent_id,
                "key": key,
                "value": value,
                "symbolUuid": "",
                "symbolTitle": "",
            }
        )

    commit_symbol()

    if selected_pages:
        pages = [page for page in pages if page["uuid"] in selected_pages]
        instance_rows = [
            instance for instance in instance_rows
            if instance["pageUuid"] in selected_pages
        ]
        net_evidence = {
            name: [entry for entry in evidence if entry["pageUuid"] in selected_pages]
            for name, evidence in net_evidence.items()
        }
        net_evidence = {name: evidence for name, evidence in net_evidence.items() if evidence}
        net_order = [name for name in net_order if name in net_evidence]

    # Flag evidence names its symbol through a separate ATTR, which may sit
    # after the net ATTR itself (the fixture's flag does), so resolve it once all
    # records — and all symbol documents — have been seen.
    for evidence in net_evidence.values():
        for entry in evidence:
            if entry["kind"] != "flag":
                continue
            symbol_uuid = instance_symbols.get(
                (entry["pageUuid"], entry["parentId"]), ""
            )
            entry["symbolUuid"] = symbol_uuid
            entry["symbolTitle"] = _text(
                symbols.get(symbol_uuid, {}).get("title")
            )

    for instance in instance_rows:
        key = (instance["pageUuid"], instance["instanceId"])
        part_key = (instance["pageUuid"], instance["partId"])
        symbol_uuid = instance_symbols.get(key) or instance_symbols.get(part_key, "")
        instance["designator"] = (
            instance_designators.get(key) or instance_designators.get(part_key, "")
        )
        instance["symbolUuid"] = symbol_uuid
        instance["symbolTitle"] = _text(symbols.get(symbol_uuid, {}).get("title"))

    if selected_pages:
        used_symbols = {
            _text(instance.get("symbolUuid"))
            for instance in instance_rows if instance.get("symbolUuid")
        }
        used_symbols.update(
            _text(entry.get("symbolUuid"))
            for evidence in net_evidence.values() for entry in evidence
            if entry.get("kind") == "flag" and entry.get("symbolUuid")
        )
        symbol_order = [uuid for uuid in symbol_order if uuid in used_symbols]

    nets: list[dict[str, Any]] = []
    for name in net_order:
        evidence = net_evidence[name]
        flags = [entry for entry in evidence if entry["kind"] == "flag"]
        # The flag decides scope/class/identity; it does not decide connectivity.
        deciding = flags[0] if flags else evidence[0]
        flag_classes: list[str] = []
        for entry in flags:
            cls = _class_from_symbol_title(_text(entry.get("symbolTitle")))
            if cls and cls not in flag_classes:
                flag_classes.append(cls)
        net_class = flag_classes[0] if len(flag_classes) == 1 else ""
        nets.append(
            {
                "name": name,
                "scope": "project" if flags else "page",
                "class": net_class,
                "pageUuid": deciding["pageUuid"],
                "page": deciding["page"],
                "parentId": deciding["parentId"],
                "key": deciding["key"],
                "crossPageConnectivityProven": False,
                "evidence": evidence,
            }
        )

    return {
        "schema": SCHEMA,
        "source": str(Path(path)),
        "sourceBoard": {
            "uuid": _text(selected_board.uuid), "title": _text(selected_board.title),
        },
        "meta": meta,
        "pages": pages,
        "instances": instance_rows,
        "nets": nets,
        "symbols": [symbols[uuid] for uuid in symbol_order],
        "bus": {
            "recordCounts": dict(bus_counts),
            "memberSemanticsProven": False,
        },
        "notes": [
            "V4 shares the V3 record stream; this reader adds page/file attribution, "
            "not a V4-only semantic field.",
            "Pin Type is preserved verbatim and is not mapped to a direction or "
            "electrical function.",
            "A Global Net Name flag and a NET label of the same name are one name; "
            "the flag decides project scope/class, which does not prove the pages "
            "are electrically connected.",
            "BUS/BUSENTRY records are counted only; no bus member is extracted.",
        ],
    }


def power_rails(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Deep copies of the nets whose class is ``gnd`` or ``power``.

    A copy, so a draft built from these facts cannot mutate the evidence the
    report cites.
    """
    return [
        copy.deepcopy(net)
        for net in facts.get("nets", [])
        if net.get("class") in ("gnd", "power")
    ]


def signal_interfaces(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Deep copies of page-scope nets, with direction explicitly unclaimed.

    ``direction`` is a human/工单 fact: the evidence layer cannot derive it, so
    it is ``""`` and ``directionProvenance`` says the field is empty rather than
    letting a consumer read a missing direction as a known one.
    """
    interfaces: list[dict[str, Any]] = []
    for net in facts.get("nets", []):
        if net.get("scope") != "page":
            continue
        interface = copy.deepcopy(net)
        interface["direction"] = ""
        interface["directionProvenance"] = ""
        interfaces.append(interface)
    return interfaces


def open_questions(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """The unknowns these facts do **not** resolve, as ``{kind, detail}`` rows.

    Deterministic order: uncalibrated Pin Type values (sorted), BUS counts, then
    project-scope nets with evidence on more than one page (sorted by name), then
    any flag-symbol class disagreement. Nothing here is a pass: every row names
    the fact that is missing.
    """
    questions: list[dict[str, Any]] = []

    pin_type_counts: dict[str, int] = {}
    for symbol in facts.get("symbols", []):
        for pin in symbol.get("pins", []):
            pin_type = _text(pin.get("pinType"))
            if pin_type:
                pin_type_counts[pin_type] = pin_type_counts.get(pin_type, 0) + 1
    for pin_type in sorted(pin_type_counts):
        questions.append(
            {
                "kind": "pin-type-uncalibrated",
                "detail": (
                    f"Pin Type {pin_type!r} appears on {pin_type_counts[pin_type]} "
                    "pin(s); the code table is not calibrated, so the value is kept "
                    "verbatim and no direction or electrical function is claimed."
                ),
            }
        )

    bus = facts.get("bus") or {}
    record_counts = bus.get("recordCounts") or {}
    bus_total = sum(
        int(record_counts.get(name) or 0) for name in ("BUS", "BUSENTRY")
    )
    if bus_total:
        questions.append(
            {
                "kind": "bus-members-unproven",
                "detail": (
                    f"BUS={int(record_counts.get('BUS') or 0)}, "
                    f"BUSENTRY={int(record_counts.get('BUSENTRY') or 0)} records were "
                    "counted; bus member semantics are not proven and no member was "
                    "extracted."
                ),
            }
        )

    multi_page: list[tuple[str, list[tuple[str, str]]]] = []
    for net in facts.get("nets", []):
        if net.get("scope") != "project":
            continue
        keys = _page_keys(net.get("evidence") or [])
        if len(keys) > 1:
            multi_page.append((_text(net.get("name")), keys))
    for name, keys in sorted(multi_page):
        page_labels = sorted({page or uuid for uuid, page in keys})
        questions.append(
            {
                "kind": "cross-page-connectivity-unproven",
                "detail": (
                    f"Project-scope net {name!r} has evidence on {len(keys)} page(s) "
                    f"({', '.join(page_labels)}); a Global Net Name flag plus per-page "
                    "files does not prove those pages are electrically connected."
                ),
            }
        )

    for net in facts.get("nets", []):
        classes = sorted(
            {
                _class_from_symbol_title(_text(entry.get("symbolTitle")))
                for entry in net.get("evidence", [])
                if entry.get("kind") == "flag"
            }
            - {""}
        )
        if len(classes) > 1:
            questions.append(
                {
                    "kind": "net-class-conflict",
                    "detail": (
                        f"Net {net.get('name')!r} has flags whose symbol titles imply "
                        f"different classes ({', '.join(classes)}); the class is left "
                        "empty instead of choosing one."
                    ),
                }
            )

    return questions


def enrich_circuit_spec(
    facts: dict[str, Any], circuit: CircuitSpec,
) -> tuple[CircuitSpec, dict[str, Any]]:
    """Fill existing ``SpecNet.scope/cls`` from flag evidence, never from names.

    The circuit supplies every net and every member. This function only changes
    metadata on a net it can match exactly by name: a flag raises neutral
    ``signal`` to its symbol-proven class and ``page`` to ``project``. An
    existing non-default class or a scope the evidence would weaken is kept and
    recorded as a conflict. Unknown nets are never added, and the original
    object is left untouched.
    """
    enriched = copy.deepcopy(circuit)
    fact_by_name = {
        _text(net.get("name")): net for net in facts.get("nets", [])
    }
    report: dict[str, Any] = {
        "changes": [],
        "conflicts": [],
        "unmatchedFacts": [],
        "openQuestions": open_questions(facts),
    }

    for net in enriched.nets:
        fact = fact_by_name.get(net.id)
        if fact is None:
            continue
        evidence = copy.deepcopy(fact.get("evidence") or [])
        scope = _text(fact.get("scope"))
        if scope and net.scope != scope:
            before = net.scope
            if not before or (before == "page" and scope == "project"):
                net.scope = scope
                report["changes"].append({
                    "net": net.id, "field": "scope", "before": before,
                    "after": scope, "evidence": evidence,
                })
            else:
                report["conflicts"].append({
                    "net": net.id, "field": "scope", "kept": before,
                    "candidate": scope, "evidence": evidence,
                })

        net_class = _text(fact.get("class"))
        if net_class and net.cls != net_class:
            before = net.cls
            if before in ("", DEFAULT_NET_CLASS):
                net.cls = net_class
                report["changes"].append({
                    "net": net.id, "field": "class", "before": before,
                    "after": net_class, "evidence": evidence,
                })
            else:
                report["conflicts"].append({
                    "net": net.id, "field": "class", "kept": before,
                    "candidate": net_class, "evidence": evidence,
                })

    circuit_names = {net.id for net in enriched.nets}
    report["unmatchedFacts"] = sorted(
        name for name in fact_by_name if name not in circuit_names
    )
    return enriched, report


def presentation_evidence(facts: dict[str, Any]) -> dict[str, Any]:
    """Build a page-evidence sidecar, not a PresentationSpec or module guess.

    A page is an attribution boundary, not a functional island. Each group keeps
    the instances and net evidence physically declared on that page, so an AI or
    engineer can propose modules without mistaking same-named evidence on two
    pages for proven cross-page connectivity or a functional assignment.
    """
    groups: list[dict[str, Any]] = []
    for page in facts.get("pages", []):
        page_uuid = _text(page.get("uuid"))
        page_name = _text(page.get("name"))
        instances = [
            copy.deepcopy(instance)
            for instance in facts.get("instances", [])
            if _text(instance.get("pageUuid")) == page_uuid
        ]
        nets: list[dict[str, Any]] = []
        for net in facts.get("nets", []):
            evidence = [
                copy.deepcopy(entry)
                for entry in net.get("evidence", [])
                if _text(entry.get("pageUuid")) == page_uuid
            ]
            if not evidence:
                continue
            deciding = evidence[0]
            nets.append({
                "name": _text(net.get("name")),
                "scope": _text(net.get("scope")),
                "class": _text(net.get("class")),
                "pageUuid": page_uuid,
                "page": page_name,
                "parentId": _text(deciding.get("parentId")),
                "key": _text(deciding.get("key")),
                "crossPageConnectivityProven": False,
                "evidence": evidence,
            })
        groups.append({
            "pageUuid": page_uuid,
            "page": page_name,
            "instances": instances,
            "nets": nets,
        })
    return {
        "schema": "boardwise.v4-presentation-evidence/1",
        "source": _text(facts.get("source")),
        "pageGroups": groups,
        "openQuestions": open_questions(facts),
        "notes": [
            "A page group is an attribution boundary, not a functional island "
            "or a module declaration. AI/engineer judgement is still required.",
            "Instances keep identity and pose only; no x/y coordinates are copied "
            "into this planning sidecar.",
            "Same-named evidence on multiple pages does not prove cross-page "
            "connectivity; every page group's flag is explicitly unproven.",
        ],
    }


def presentation_seed_from_facts(
    facts: dict[str, Any], circuit: CircuitSpec,
) -> tuple[PresentationSpec, dict[str, Any]]:
    """Return a page-grouped seed for the existing islands proposal, no verdict.

    The temporary modules only hold parts that the CircuitSpec actually has.
    ``islands`` stays ``None`` so the existing propose/apply judgement path, not
    this seed, decides the functional partition. No role, core, flow or branch
    order is inferred from page membership.
    """
    circuit_parts = set(circuit.part_ids())
    modules: list[PresentationModule] = []
    report_modules: list[dict[str, Any]] = []
    unassigned: list[str] = []
    for page in facts.get("pages", []):
        page_uuid = _text(page.get("uuid"))
        page_name = _text(page.get("name"))
        parts: list[str] = []
        for instance in facts.get("instances", []):
            if _text(instance.get("pageUuid")) != page_uuid:
                continue
            designator = _text(instance.get("designator"))
            if designator in circuit_parts:
                parts.append(designator)
            else:
                unassigned.append(_text(instance.get("partId")) or designator)
        if not parts:
            continue
        module_id = f"page-{len(modules) + 1}"
        parts = sorted(parts)
        modules.append(PresentationModule(id=module_id, parts=parts, role="unassigned"))
        report_modules.append({
            "id": module_id, "pageUuid": page_uuid, "page": page_name,
            "parts": parts,
        })
    if not modules:
        raise ValueError("no V4 instance matches a CircuitSpec part; no seed to propose")
    questions = open_questions(facts)
    if unassigned:
        questions.append({
            "kind": "instances-not-in-circuit",
            "detail": (
                "Instance(s) not represented in the CircuitSpec were left out of "
                "the page-grouped seed: " + ", ".join(sorted(unassigned))
            ),
        })
    return PresentationSpec(modules=modules), {
        "modules": report_modules,
        "openQuestions": questions,
        "unassignedInstances": sorted(unassigned),
    }


def with_instance_poses(
    profiles: dict[str, Any], facts: dict[str, Any], circuit: CircuitSpec,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Add V4 instance poses to a profile book without inventing text geometry.

    Rotation/mirror is an instance fact, not a new text or pin measurement. The
    report therefore keeps ``geometryVerified=False`` and requires the compiler
    and lint to re-prove the drawing. Existing poses and profile objects are
    preserved; only missing, explicitly observed poses are appended.
    """
    instances = {
        _text(instance.get("designator")): instance
        for instance in facts.get("instances", [])
        if instance.get("designator")
    }
    out = copy.deepcopy(profiles)
    additions: list[dict[str, Any]] = []
    unmatched: list[str] = []
    missing_instances: list[str] = []
    for part in circuit.parts:
        profile = out.get(part.symbol_ref)
        if profile is None:
            unmatched.append(part.id)
            continue
        instance = instances.get(part.id)
        if instance is None:
            missing_instances.append(part.id)
            continue
        rotation = int(instance.get("rotation", 0))
        if rotation not in (0, 90, 180, 270):
            raise ValueError(f"unsupported instance rotation {rotation!r} on {part.id}")
        pose = SymbolPose(rotation=rotation, mirror=bool(instance.get("isMirror")))
        if pose in profile.poses:
            continue
        profile.poses.append(pose)
        profile.notes.append(
            f"instance pose evidence: {part.id} rotation={rotation} "
            f"mirror={pose.mirror}; text/pin geometry is not re-measured"
        )
        additions.append({
            "part": part.id, "symbolRef": part.symbol_ref,
            "rotation": rotation, "mirror": pose.mirror,
            "pageUuid": _text(instance.get("pageUuid")),
        })
    return out, {
        "addedPoses": additions,
        "unmatchedProfiles": sorted(unmatched),
        "missingInstances": sorted(missing_instances),
        "geometryVerified": False,
    }
