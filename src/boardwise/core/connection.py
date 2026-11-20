"""Online copper-connection evidence between two pads (task 559, batch B1/B2).

The question this module answers is narrower than 550's offline path question and
the two must not be confused: *did the running editor itself hand back proof that
these two named pads sit on the same copper?* The host evidence comes from
``pcb.connection_probe`` (connector ``actions.ts``), which only reads — two
`REF.PAD` ends, each end's resolved pad identity and its
``getConnectedPrimitives(false)`` answer. This module is the **verdict** half, and
it is a pure function over that response: no host call, no file, no bridge.

**Direct-only, because ``getEntireTrack`` was measured and rejected (559B).** On
one real net the offline 550 model separates into six disconnected copper
components, while ``getEntireTrack(true)`` answered 76 ids with
``truncated: true``, four of them belonging to *other* components
(``evidence/559/entire-track-rejection.json``). Membership in an id set is
therefore not a connected component and cannot prove physical connectivity, so
the production probe no longer collects it and no proof kind may use it. A legacy
payload that still carries a non-empty ``tracks[]`` is disclosed as
``entire-track-unsupported`` and blocks a negative; it is never read as evidence.

**Verdicts are three, and the third one is the honest default.**

* :data:`CONNECTED` — at least one *typed, sourced* direct intersection was found
  (see :data:`_PROOF_KINDS`): both ends' direct answers name the same typed
  ``Line``/``Arc``, or one end's direct answer names the other end's pad id. A
  proof names both ends and the call that answered; an id that merely appears in
  two untyped id arrays is not evidence and is refused.
* :data:`NOT_PROVEN` — no proof **and no gap**: both ends resolved to exactly one
  pad each, every related host call answered completely and nothing was unknown.
  It means 「direct 范围内没有共享图元」, not 「开路」 — via/fill/pour adjacency and
  multi-hop copper are outside this contract, so a directly connected primitive of
  any other type is a **named gap** (``direct-non-proof-type``) and a negative
  never survives one, whether or not the host sent its own ``unknown`` row for it.
* :data:`INDETERMINATE` — a prerequisite does not hold (an end not resolved, one
  pad id, an empty or differing net, ``direct.ok`` false, a response that does not
  describe a read-only PCB page, a legacy ``tracks[]``) **or** any gap could
  change a negative answer: response ``errors``/``unknown``, a directly connected
  non-proof type, ``resolution.readErrors``/``truncated``, a non-``ok`` or
  truncated direct call, missing coverage.
  A **positive** answer is never overturned by a gap: a proven intersection stays
  :data:`CONNECTED`, and the gaps are still disclosed beside it.

**Refusal is not a verdict.** A non-PCB focus, a page that is not read-only and a
bridge-side failure all leave **stdout empty** with one line on stderr at exit
``3``: the connector's own ``requirePcbFocus`` refuses before it reads anything,
and :mod:`boardwise.pcb_connection` turns that into a refusal rather than a
payload. The ``page-not-pcb`` / ``not-read-only`` checks below only fire on a probe
response that *arrived* and described something else, so they are a second gate,
not the one an operator meets first.

**``coverage.complete`` is a hint, never a premise.** It is the connector's own
one-field summary, and every gap below is re-derived from the individual
readings; ``coverage.complete == false`` is itself a gap (so a negative needs more
than a true bit), but a true bit is never accepted in place of the readings.

**No path, on purpose.** The payload has no ``path``/``hopCount``/``viaCount``:
what this contract reads is a direct answer, not an ordered walk, and inventing
hop order from it would be a fabricated geometry claim. What is emitted is
``proofs[]`` (which intersection, with which sources) and ``sharedIds[]`` (the
same intersection keyed by primitive identity).

**Determinism.** Ends are visited ``from`` then ``to``, direct items in their
answer order, ``sharedIds``/``proofs`` are sorted by their own keys, and the
projection is written with ``sort_keys=True`` — the same response always produces
byte-identical JSON.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CONNECTED",
    "INDETERMINATE",
    "NOT_PROVEN",
    "SCHEMA",
    "ConnectionResult",
    "project_connection",
]

#: The JSON contract this result projects into. Bumped only with a contract
#: change; readers pin it.
SCHEMA = "boardwise.pcbConnection/1"

CONNECTED = "CONNECTED"
NOT_PROVEN = "NOT_PROVEN"
INDETERMINATE = "INDETERMINATE"

#: The two types whose *direct* answers can be shared copper (the same types
#: ``getEntireTrack`` is declared for — which this contract no longer calls).
_TRACK_TYPES = frozenset({"Line", "Arc"})

#: Types that can be the *other pad*, and therefore direct evidence on their own.
_PAD_TYPES = frozenset({"Pad", "ComponentPad"})

#: The two ends, in the order the probe reports them.
_ENDS: tuple[str, str] = ("from", "to")

#: The proof kinds this contract accepts, and they are **direct only**: copper
#: that 「touches」 through a via, fill, pour, polyline or an unknown type is not
#: the same claim as 「same direct primitive」, and ``getEntireTrack`` was measured
#: returning ids of other, disconnected copper components (559B), so no proof may
#: come from an id set.
_PROOF_KINDS: tuple[str, ...] = (
    "direct-shared-track",
    "direct-other-pad",
)

#: What the evidence covers, spelled out in every result.
_SCOPE: dict[str, Any] = {
    "supports": [
        "host getConnectedPrimitives(false) on the resolved ComponentPad of each end",
        "direct primitive whose host type is Line/Arc, shared by both ends",
        "direct primitive whose host type is Pad/ComponentPad, naming the other end's pad",
        "typed intersections only, each one carrying its end and the call that answered",
    ],
    "excludes": [
        "any getEntireTrack answer: measured to span other, disconnected copper components "
        "(evidence/559/entire-track-rejection.json), so an id set is never proof",
        "multi-hop copper paths (getAdjacentPrimitives has no contract or live validation here)",
        "ordered hop geometry, net length, impedance, clearance or DRC conclusions",
        "via / fill / pour / polyline adjacency (host semantics unconfirmed)",
        "net-name-only connectivity",
        "any write, any page change, any automatic document open",
    ],
    "note": (
        "NOT_PROVEN 只表示「在这条 direct-only 范围内两端没有共享图元」，不是电气开路；"
        "via/fill/pour 一旦出现在直接连接响应里就作为具名 unknown（direct-non-proof-type）"
        "披露并压住否定结论——宿主漏发 unknown 也照样如此——且从不用于补路。"
        "整个契约不读 getEntireTrack：真实板上它返回的 ID 集合跨越多个离线分离铜分量且 truncated，"
        "成员资格不能证明连通；legacy payload 的非空 tracks[] 记为 entire-track-unsupported 并压住否定。"
        "CONNECTED 只复述宿主给出的同一 direct 图元，不等于 DRC 通过。"
        "非 PCB 焦点/非只读是 refusal（stderr 一行、stdout 为空、退 3），不是带 verdict 的 "
        "INDETERMINATE 载荷。"
    ),
}


def _text(value: Any) -> str | None:
    """A non-empty string, or ``None`` — never a coerced ``""``."""
    return value if isinstance(value, str) and value else None


def _count(value: Any) -> int | None:
    """A non-negative int, or ``None`` when the counter was not a number."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def _issue(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """One ``unknown`` / ``ignored`` row; ``sort_keys`` sorts it at projection."""
    row: dict[str, Any] = {"code": code, "message": message}
    for key, value in extra.items():
        row[key] = value
    return row


def _source(end: str, call: str) -> dict[str, Any]:
    """One end of a proof: which end, which call answered."""
    return {"end": end, "call": call}


def _end_query(raw: Any) -> dict[str, Any]:
    """One end's identity as ``query`` writes it (nulls where nothing was read)."""
    row = raw if isinstance(raw, dict) else {}
    ref = row.get("ref") if isinstance(row.get("ref"), dict) else {}
    pad = row.get("pad") if isinstance(row.get("pad"), dict) else {}
    return {
        "ref": {"designator": _text(ref.get("designator")), "pad": _text(ref.get("pad"))},
        "padId": _text(pad.get("primitiveId")),
        "padNumber": _text(pad.get("padNumber")),
        "net": _text(pad.get("net")),
        "type": _text(pad.get("type")),
    }


@dataclass(frozen=True)
class _End:
    """One end after it passed every prerequisite: identity plus typed answers."""

    key: str
    pad_id: str
    net: str
    #: ``primitiveId → host type`` for direct answers of type Line/Arc.
    tracks_by_id: dict[str, str]
    #: Direct answers whose host type can be the other pad, by id.
    pad_ids: frozenset[str]


@dataclass
class ConnectionResult:
    """The answer to one ``pcb.connection_probe`` response, and its JSON form.

    ``unknown`` is never a 「maybe connected」: it is the list of readings that
    could change a **negative** verdict. ``ignored`` is the opposite — what this
    contract excludes by decision — and it must never be used to escalate.
    ``sharedIds``/``proofs`` are the positive evidence, and they are empty
    whenever the input does not hold, so no verdict can be built on a net the
    caller did not establish.
    """

    verdict: str = INDETERMINATE
    source: dict[str, Any] = field(default_factory=dict)
    query: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    shared_ids: list[dict[str, Any]] = field(default_factory=list)
    proofs: list[dict[str, Any]] = field(default_factory=list)
    unknown: list[dict[str, Any]] = field(default_factory=list)
    ignored: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    scope: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(_SCOPE))
    schema: str = SCHEMA

    def as_dict(self) -> dict[str, Any]:
        """The :data:`SCHEMA` payload. Every array is present, empty or not."""
        return {
            "schema": self.schema,
            "verdict": self.verdict,
            "source": dict(self.source),
            "query": copy.deepcopy(self.query),
            "evidence": copy.deepcopy(self.evidence),
            "sharedIds": [dict(row) for row in self.shared_ids],
            "proofs": copy.deepcopy(self.proofs),
            "unknown": copy.deepcopy(self.unknown),
            "ignored": copy.deepcopy(self.ignored),
            "errors": copy.deepcopy(self.errors),
            "coverage": copy.deepcopy(self.coverage),
            "scope": copy.deepcopy(self.scope),
        }

    def to_json(self, *, indent: int | None = None) -> str:
        """The payload as canonical JSON (sorted keys, UTF-8 friendly)."""
        return json.dumps(
            self.as_dict(),
            sort_keys=True,
            ensure_ascii=False,
            indent=indent,
            allow_nan=False,
        )


class _Collector:
    """Every gap the run finds, kept in the shape it will be reported in."""

    def __init__(self) -> None:
        self.hard: list[dict[str, Any]] = []
        self.gaps: list[dict[str, Any]] = []
        self.ignored: list[dict[str, Any]] = []
        self.unknown_rows: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []

    def refuse(self, code: str, message: str, **extra: Any) -> None:
        """A prerequisite that does not hold: no verdict but INDETERMINATE."""
        self.hard.append(_issue(code, message, **extra))

    def gap(self, code: str, message: str, **extra: Any) -> None:
        """A reading that could change a negative answer."""
        self.gaps.append(_issue(code, message, **extra))

    def gap_count(self) -> int:
        """Gaps that block a second kind of answer: the whole decision rule."""
        return len(self.gaps) + len(self.unknown_rows) + len(self.errors)


def _check_resolution(raw: Any, key: str, collector: _Collector) -> None:
    """One end's ``resolution`` block: identity must be complete and unique."""
    row = raw if isinstance(raw, dict) else {}
    resolution = row.get("resolution")
    if not isinstance(resolution, dict):
        collector.gap("resolution-missing", f"{key}: the probe reported no resolution block")
        return None
    read_errors = resolution.get("readErrors")
    if not isinstance(read_errors, list):
        collector.gap(
            "resolution-read-errors-unreadable",
            f"{key}: resolution.readErrors is {type(read_errors).__name__}, not an array",
        )
    elif read_errors:
        collector.gap(
            "resolution-read-errors",
            f"{key}: {len(read_errors)} component/pad read(s) failed during the scan",
            readErrors=[str(line) for line in read_errors],
        )
    if resolution.get("truncated") is not False:
        collector.gap(
            "resolution-truncated",
            f"{key}: the component scan did not report truncated=false, so an absent pad is not a fact",
            truncated=resolution.get("truncated"),
        )
    if resolution.get("complete") is not True:
        collector.gap(
            "resolution-incomplete",
            f"{key}: the component scan did not report complete=true",
            complete=resolution.get("complete"),
        )
    matches = resolution.get("matches")
    if _count(matches) != 1:
        collector.refuse(
            "pad-not-unique",
            f"{key}: {matches!r} component pads answered this REF.PAD — a connection needs exactly one",
            matches=matches,
        )
    candidates = resolution.get("candidates")
    if isinstance(candidates, list):
        unique = sorted({c for c in candidates if _text(c)})
        if len(unique) > 1:
            collector.refuse(
                "pad-not-unique",
                f"{key}: {len(unique)} distinct pad primitive ids were candidates — taking one would be a guess",
                candidates=unique,
            )


def _check_direct(raw: Any, key: str, collector: _Collector) -> dict[str, Any] | None:
    """One end's ``direct`` call: ids *and* their types, or the gap that stood in."""
    row = raw if isinstance(raw, dict) else {}
    direct = row.get("direct")
    if not isinstance(direct, dict):
        collector.refuse(
            "direct-missing",
            f"{key}: the probe reported no direct getConnectedPrimitives answer",
        )
        collector.gap("direct-missing", f"{key}: no direct answer, so no intersection can be excluded")
        return None
    if direct.get("ok") is not True:
        collector.refuse(
            "direct-not-ok",
            f"{key}: direct.ok is {direct.get('ok')!r}"
            + (f" — {direct['error']}" if isinstance(direct.get("error"), str) else ""),
        )
        return None

    ids = direct.get("ids")
    if not isinstance(ids, list):
        collector.gap(
            "direct-ids-unreadable",
            f"{key}: direct.ids is {type(ids).__name__}, not an array",
        )
        ids = []
    items = direct.get("items")
    if not isinstance(items, list):
        collector.gap(
            "direct-items-unreadable",
            f"{key}: direct.items is {type(items).__name__}, not an array of typed primitives",
        )
        items = []
    if direct.get("truncated") is not False:
        collector.gap(
            "direct-truncated",
            f"{key}: the direct answer did not report truncated=false — more connected primitives may exist",
            truncated=direct.get("truncated"),
        )
    unreadable = direct.get("unreadable")
    unreadable_count = _count(unreadable) or 0
    if unreadable_count:
        collector.gap(
            "direct-unreadable",
            f"{key}: {unreadable_count} connected primitive(s) answered no readable PrimitiveId",
            unreadable=unreadable_count,
        )

    tracks_by_id: dict[str, str] = {}
    pad_ids: set[str] = set()
    seen: set[str] = set()
    for at, item in enumerate(items):
        if not isinstance(item, dict):
            collector.gap(
                "direct-item-unreadable",
                f"{key}: direct item #{at} is {type(item).__name__}, not an object",
                index=at,
            )
            continue
        primitive_id = _text(item.get("primitiveId"))
        kind = _text(item.get("type"))
        if primitive_id is None or kind is None:
            collector.gap(
                "direct-item-untyped",
                f"{key}: direct item #{at} has no readable primitive id and type, so it cannot be "
                "compared",
                index=at,
            )
            continue
        if primitive_id in seen:
            collector.ignored.append(
                _issue(
                    "duplicate-direct-item",
                    f"{key}: primitive {primitive_id} appears more than once in the direct answer",
                    end=key,
                    primitiveId=primitive_id,
                )
            )
            continue
        seen.add(primitive_id)
        if kind in _TRACK_TYPES:
            tracks_by_id[primitive_id] = kind
        elif kind in _PAD_TYPES:
            pad_ids.add(primitive_id)
        else:
            # Not a proof type, so it is never proof — but it could overturn a
            # negative, and the projection may not lean on the host's own `unknown`.
            collector.gap(
                "direct-non-proof-type",
                f"{key}: a directly connected {kind} is not a proof type — via/fill/pour/polyline "
                "adjacency is outside this contract, so it could change a negative answer and is "
                "disclosed as unknown",
                end=key,
                primitiveId=primitive_id,
                type=kind,
            )
            collector.ignored.append(
                _issue(
                    "not-a-track-type",
                    f"{key}: a directly connected {kind} is not a proof type and was not used to prove "
                    "anything",
                    end=key,
                    primitiveId=primitive_id,
                    type=kind,
                )
            )

    untyped = [primitive_id for primitive_id in ids if _text(primitive_id) not in seen]
    if untyped:
        collector.gap(
            "direct-ids-without-type",
            f"{key}: {len(untyped)} id(s) in direct.ids carry no typed item — two bare id arrays are "
            "not an intersection",
            ids=sorted(str(value) for value in untyped),
        )
        collector.ignored.append(
            _issue(
                "untyped-id-array",
                f"{key}: direct.ids was compared only through typed items, never on its own",
                end=key,
            )
        )
    return {"tracks": tracks_by_id, "pads": frozenset(pad_ids)}


def _check_legacy_tracks(raw: Any, key: str, collector: _Collector) -> None:
    """A non-empty legacy ``tracks[]``: disclosed, and never read as evidence.

    Before 559B the probe collected one ``getEntireTrack(true)`` answer per
    directly reached ``Line``/``Arc`` and this module intersected those id sets.
    That was withdrawn: the call was measured returning ids of other, offline
    disconnected copper components with ``truncated: true``
    (``evidence/559/entire-track-rejection.json``), so membership in the set says
    nothing about physical connectivity. The production probe no longer sends the
    key at all; if an older payload does, the gap is **named** (it blocks a
    negative) and the ids are dropped here rather than being interpreted. An
    empty array is simply absent — there is nothing to withhold.
    """
    row = raw if isinstance(raw, dict) else {}
    tracks = row.get("tracks")
    if tracks is None or (isinstance(tracks, list) and not tracks):
        return
    if not isinstance(tracks, list):
        collector.gap(
            "entire-track-unsupported",
            f"{key}: tracks is {type(tracks).__name__} — this contract reads direct answers only and "
            "never interprets a getEntireTrack answer",
            end=key,
        )
        return
    ids = sorted(
        {
            str(entry["primitiveId"])
            for entry in tracks
            if isinstance(entry, dict) and _text(entry.get("primitiveId"))
        }
    )
    collector.gap(
        "entire-track-unsupported",
        f"{key}: {len(tracks)} legacy entireTrack entr(ies) were reported — a getEntireTrack id set was "
        "measured to span other, disconnected copper components, so it is not evidence of connectivity "
        "and is not used for or against a proof",
        end=key,
        tracks=len(tracks),
        primitiveIds=ids,
    )


def _check_coverage(payload: dict[str, Any], collector: _Collector) -> None:
    """The coverage summary: a hint to compare against, never a premise."""
    coverage = payload.get("coverage")
    if not isinstance(coverage, dict):
        collector.gap("coverage-missing", "the response carried no coverage block")
        return
    if coverage.get("complete") is not True:
        collector.gap(
            "coverage-incomplete",
            "coverage.complete is not true — the probe itself says something was withheld",
            complete=coverage.get("complete"),
        )
    scan = coverage.get("scan")
    if isinstance(scan, dict):
        if scan.get("complete") is not True:
            collector.gap("coverage-scan-incomplete", "coverage.scan.complete is not true")
        if scan.get("truncated") is not False:
            collector.gap(
                "coverage-scan-truncated",
                "coverage.scan.truncated is not false — the component walk was capped",
                truncated=scan.get("truncated"),
            )
        read_errors = _count(scan.get("readErrors")) or 0
        if read_errors:
            collector.gap(
                "coverage-scan-read-errors",
                f"coverage.scan.readErrors is {read_errors}",
                readErrors=read_errors,
            )
    direct = coverage.get("direct")
    if isinstance(direct, dict):
        truncated = direct.get("truncated")
        if isinstance(truncated, dict):
            for key in _ENDS:
                if truncated.get(key) is not False and key in truncated:
                    collector.gap(
                        "coverage-direct-truncated",
                        f"coverage.direct.truncated.{key} is not false",
                        end=key,
                        truncated=truncated.get(key),
                    )


def _collect_proofs(
    ends: dict[str, _End], collector: _Collector
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Typed, sourced intersections only; sorted so two runs write the same bytes."""
    found: dict[tuple[str, str], dict[str, Any]] = {}

    def add(
        kind: str, primitive_id: str, kind_type: str, left: dict[str, Any], right: dict[str, Any]
    ) -> None:
        mark = (kind, primitive_id)
        if mark in found:
            return
        found[mark] = {
            "kind": kind,
            "primitiveId": primitive_id,
            "type": kind_type,
            "from": left,
            "to": right,
        }

    left, right = ends["from"], ends["to"]
    for here, there in ((left, right), (right, left)):
        # 1. Both ends' direct answers name the same Line/Arc.
        for primitive_id in sorted(here.tracks_by_id):
            if primitive_id in there.tracks_by_id:
                add(
                    "direct-shared-track",
                    primitive_id,
                    here.tracks_by_id[primitive_id],
                    _source(here.key, "direct"),
                    _source(there.key, "direct"),
                )
    # 2. One end's direct answer explicitly names the other end's pad.
    if right.pad_id in left.pad_ids:
        add(
            "direct-other-pad",
            right.pad_id,
            "Pad",
            _source(left.key, "direct"),
            _source(right.key, "pad"),
        )
    if left.pad_id in right.pad_ids:
        add(
            "direct-other-pad",
            left.pad_id,
            "Pad",
            _source(right.key, "direct"),
            _source(left.key, "pad"),
        )

    proofs = list(found.values())
    shared: dict[tuple[str, str], dict[str, Any]] = {}
    for proof in proofs:
        unique = (proof["type"], proof["primitiveId"])
        entry = shared.setdefault(
            unique,
            {"primitiveId": proof["primitiveId"], "type": proof["type"], "sources": []},
        )
        for side in ("from", "to"):
            source = dict(proof[side])
            if source not in entry["sources"]:
                entry["sources"].append(source)
    for entry in shared.values():
        entry["sources"] = sorted(entry["sources"], key=lambda row: (row["end"], row["call"]))
    shared_ids = sorted(shared.values(), key=lambda row: (row["type"], row["primitiveId"]))
    proofs = sorted(
        proofs,
        key=lambda row: (
            row["kind"],
            row["primitiveId"],
            row["from"]["end"],
            row["to"]["end"],
        ),
    )
    return proofs, shared_ids


def project_connection(payload: Any) -> ConnectionResult:
    """Read one ``pcb.connection_probe`` response and project its verdict.

    Pure and read-only: the response is copied into ``evidence`` and never
    mutated, no host call is made, and no file is read. A response that does not
    hold (wrong page, not read-only, unresolved end, one pad, empty or differing
    net, failed direct call) yields :data:`INDETERMINATE` with the reason in
    ``errors``; a gap beside no proof also yields :data:`INDETERMINATE`; only a
    complete negative answer is :data:`NOT_PROVEN`.
    """
    collector = _Collector()
    result = ConnectionResult()
    box = payload if isinstance(payload, dict) else {}
    if not isinstance(payload, dict):
        collector.refuse(
            "payload-not-an-object",
            f"the response is {type(payload).__name__}, not a pcb.connection_probe object",
        )

    # ---- page and read-only identity -------------------------------------
    page = box.get("page")
    page = page if isinstance(page, dict) else {}
    page_type = _text(page.get("type"))
    page_uuid = _text(page.get("uuid"))
    if page_type is None or page_type.strip().lower() != "pcb":
        collector.refuse(
            "page-not-pcb",
            f"the probe did not report a PCB page (page.type {page_type!r}) — a connection between two "
            "pads needs the focused PCB, not 「a PCB exists」",
            pageType=page_type,
        )
    if page_uuid is None:
        collector.gap("page-identity-missing", "page.uuid is not readable, so the read has no document identity")
    if box.get("readOnly") is not True:
        collector.refuse(
            "not-read-only",
            f"readOnly is {box.get('readOnly')!r}; this contract only reads and only accepts a read-only probe",
        )

    result.source = {
        "host": "easyeda-pro",
        "connector": "pcb.connection_probe",
        "page": {"uuid": page_uuid, "type": page_type},
        "readOnly": box.get("readOnly") is True,
    }

    # ---- response-level gaps ---------------------------------------------
    response_errors = box.get("errors")
    if not isinstance(response_errors, list):
        collector.gap(
            "response-errors-unreadable",
            f"errors is {type(response_errors).__name__}, not an array",
        )
        response_errors = []
    for line in response_errors:
        collector.errors.append(
            _issue("connector-error", str(line) if not isinstance(line, str) else line)
        )
    unknown = box.get("unknown")
    if not isinstance(unknown, list):
        collector.gap(
            "response-unknown-unreadable",
            f"unknown is {type(unknown).__name__}, not an array",
        )
        unknown = []
    for row in unknown:
        collector.unknown_rows.append(copy.deepcopy(row) if isinstance(row, dict) else _issue(
            "unknown-row-unreadable", f"an unknown row is {type(row).__name__}, not an object"
        ))
    ignored = box.get("ignored")
    if not isinstance(ignored, list):
        collector.gap(
            "response-ignored-unreadable",
            f"ignored is {type(ignored).__name__}, not an array",
        )
        ignored = []
    for row in ignored:
        collector.ignored.append(copy.deepcopy(row) if isinstance(row, dict) else _issue(
            "ignored-row-unreadable", f"an ignored row is {type(row).__name__}, not an object"
        ))

    # ---- both ends: identity, then typed answers -------------------------
    identified: dict[str, _End] = {}
    for key in _ENDS:
        raw = box.get(key)
        if not isinstance(raw, dict):
            collector.refuse(
                "end-missing",
                f"{key}: the probe reported no end object ({type(raw).__name__})",
                end=key,
            )
            continue
        status = raw.get("status")
        if status != "resolved":
            collector.refuse(
                "end-not-resolved",
                f"{key}: status is {status!r}"
                + (f" — {raw['error']}" if isinstance(raw.get("error"), str) else ""),
                end=key,
                status=status if isinstance(status, str) else None,
            )
            continue
        _check_resolution(raw, key, collector)
        view = _end_query(raw)
        pad_id = view["padId"]
        net = view["net"]
        if pad_id is None:
            collector.refuse(
                "pad-id-missing",
                f"{key}: the resolved pad has no readable primitive id, so nothing can be matched to it",
                end=key,
            )
            continue
        if net is None:
            collector.refuse(
                "net-missing",
                f"{key}: the resolved pad reports no net — an empty net cannot be the same copper",
                end=key,
            )
            continue
        direct = _check_direct(raw, key, collector)
        if direct is None:
            continue
        _check_legacy_tracks(raw, key, collector)
        identified[key] = _End(
            key=key,
            pad_id=pad_id,
            net=net,
            tracks_by_id=direct["tracks"],
            pad_ids=direct["pads"],
        )

    result.query = {"from": _end_query(box.get("from")), "to": _end_query(box.get("to"))}
    result.evidence = {
        "from": copy.deepcopy(box.get("from")),
        "to": copy.deepcopy(box.get("to")),
    }

    # ---- identity between the two ends -----------------------------------
    left, right = identified.get("from"), identified.get("to")
    if left is not None and right is not None:
        if left.pad_id == right.pad_id:
            collector.refuse(
                "same-pad",
                f"both ends resolve to pad {left.pad_id} — a pad is not connected to itself",
                primitiveId=left.pad_id,
            )
        elif left.net != right.net:
            collector.refuse(
                "different-net",
                f"the ends are on different nets ({left.net!r} vs {right.net!r}) — an intersection across "
                "nets is an input error, not a connection",
                fromNet=left.net,
                toNet=right.net,
            )
    _check_coverage(box, collector)

    # ---- proofs, then the verdict ----------------------------------------
    proofs: list[dict[str, Any]] = []
    shared_ids: list[dict[str, Any]] = []
    if not collector.hard and left is not None and right is not None:
        proofs, shared_ids = _collect_proofs({"from": left, "to": right}, collector)
        if not proofs:
            collector.ignored.append(
                _issue(
                    "no-intersection",
                    "the two ends' typed Line/Arc and pad answers share no primitive; pour, fill, via and "
                    "polyline adjacency is not proof under this contract",
                )
            )

    if collector.hard:
        result.verdict = INDETERMINATE
    elif proofs:
        result.verdict = CONNECTED
    elif collector.gap_count():
        result.verdict = INDETERMINATE
    else:
        result.verdict = NOT_PROVEN

    result.proofs = proofs
    result.shared_ids = shared_ids
    result.unknown = [*collector.unknown_rows, *collector.gaps]
    result.ignored = collector.ignored
    result.errors = [*collector.hard, *collector.errors]
    result.coverage = copy.deepcopy(box.get("coverage")) if isinstance(box.get("coverage"), dict) else {}
    result.coverage = {
        **result.coverage,
        "projection": {
            "proofs": len(proofs),
            "sharedIds": len(shared_ids),
            "gaps": collector.gap_count(),
            "hardErrors": len(collector.hard),
        },
    }
    return result
