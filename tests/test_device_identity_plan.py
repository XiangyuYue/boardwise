"""device-identity batch: a planned part may be named by its library device pair.

The public contract this file pins down (and the one `draw apply` implements):

* :class:`~boardwise.core.changeplan.PlanDrawPart` gains **optional**
  ``device_uuid``/``library_uuid`` (JSON ``deviceUuid``/``libraryUuid``). Both
  default to empty and the serializer **omits both keys** when they are empty, so
  a plan written before the field existed keeps its bytes, its version, its call
  sequence and its output exactly.
* The pair is one identity: stating only one half is refused, on the plan and on
  the CircuitSpec side alike. A part with **no** ``lcsc`` and no pair is still
  refused — the old rule is not relaxed, it is joined by a second legitimate way
  to name a device.
* When a plan states both, the pair wins at apply — the connector's own order
  (``actions.ts`` tests ``deviceUuid`` before ``lcsc``). The placement call then
  carries ``deviceUuid``+``libraryUuid`` and **no** ``lcsc`` parameter at all.
  A plan with no pair emits the call it always emitted, key for key: the LCSC
  path and its 038D2a/534A fallbacks are not touched.
* The pair is verified after placement, not assumed: ``sch.geometry`` reports the
  placed component's own ``state.Component.uuid`` / ``state.Component.libraryUuid``
  and it must equal the plan's. Same coordinates and same pins are **not** the
  same device — two library devices can share a symbol — so a different (or
  unreadable) identity refuses the run before any wire, with a structured
  ``reason`` and exit code 2.

The CircuitSpec side reads the pair from ``parts[].params`` (``deviceUuid`` /
``libraryUuid``), which is where a real V4 CircuitSpec already carries it; it is
**not** a new top-level `SpecPart` field.

The editor and the plan builder are the ones `tests/test_054_draw_cli.py`
already uses (imported, never modified): the fake really lands placements and
answers them back through `sch.geometry`, so "the identity was read back" is a
claim about the flow rather than about a hand-written answer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core.changeplan import ChangePlan, ChangePlanError
from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler

import test_054_draw_cli as b054

#: The verified library device the fixture's R1 is named by instead of a
#: Supplier Part. The values are arbitrary (the fake library answers geometry by
#: LCSC/digest, not by these), and that is the point: the flow compares them
#: against what the page says it placed.
R1_DEVICE = "b13dfd2f0653b0b8"
R1_LIBRARY = "0819f05c4eef4c71ace90d822a990e87"
R1_OTHER_DEVICE = "74cd908888b29f82"


#: The live V4 measurement this contract rests on: the plan asks for the library
#: device, the page answers a *different* document-record id in
#: `state.Component.uuid`, and only the library can say what the device is.
R1_DOC_RECORD = "6fe130e2666a04e2"
DOC_SYMBOL_RECORD = "b13dfd2f0653b0b8"
LIB_SYMBOL = "e23085a8f904493eb2ce369cbc1b267c"
LIB_SYMBOL_NAME = "0603WAF1002T5E_SYMBOL"
LIB_SUBPART = "0603WAF1002T5E.1"
LIB_MANUFACTURER = "0603WAF1002T5E"
LIB_SUPPLIER = "C25804"
OTHER_SYMBOL = "00000000000000000000000000000001"

#: A page record that agrees with the library on every field the identity leg
#: compares — and deliberately **not** on either document id: live V4 measured
#: that `state.Component.uuid` is the document's device record (6fe130e2…) and
#: `state.Symbol.uuid` is the document's symbol record (0/47 of the P1 page's
#: symbol uuids matched the library's `association.symbolUuid`).
CONSISTENT = {
    "component": R1_DOC_RECORD,
    "symbolRecord": DOC_SYMBOL_RECORD,
    "symbolName": LIB_SYMBOL_NAME,
    "subPart": LIB_SUBPART,
    "manufacturerId": LIB_MANUFACTURER,
    "supplierId": LIB_SUPPLIER,
}


def _library_answer(*, found: bool = True,
                    sub_part_names: list[str] | None = None,
                    manufacturer_id: str = LIB_MANUFACTURER,
                    supplier_id: str = LIB_SUPPLIER,
                    symbol_uuid: str = LIB_SYMBOL) -> dict:
    """`lib.device.get`'s own envelope for the device the plan asks for.

    ``sub_part_names`` defaults to the usual single entry; ``['']`` is the shape
    the live library answers for some devices (22/22 found, one C22P among them),
    and it means "no sub-part evidence", not "the sub-part is empty".
    """
    return {
        "uuid": R1_DEVICE,
        "libraryUuid": R1_LIBRARY,
        "found": found,
        "item": {
            "uuid": R1_DEVICE,
            "libraryUuid": R1_LIBRARY,
            "association": {
                "symbolUuid": symbol_uuid,
                "symbol": {"uuid": symbol_uuid, "libraryUuid": R1_LIBRARY},
            },
            "subPartNames": (
                [LIB_SUBPART] if sub_part_names is None else list(sub_part_names)
            ),
            "property": {
                "manufacturerId": manufacturer_id,
                "supplierId": supplier_id,
            },
        },
    }


class _IdentityEditor(b054._FakeEditor):
    """The 054 fake, plus the evidence the identity leg reads on both sides.

    * the page states what a live V4 page states: `state.Component.uuid` is the
      document's own device-record id (different from the library device uuid by
      construction), while `state.Symbol.uuid` / `state.SubPartName` /
      `state.ManufacturerId` / `state.SupplierId` carry the library facts;
    * `lib.device.get` answers the library's own entry for the requested device.

    Nothing else about the fake changes: placements still land, and the pins come
    from the same (R0402) geometry 054 uses.
    """

    def __init__(self, identities, library=None, symbols=None, **kwargs):
        #: The library's pin geometry comes from the **symbol**, not from the
        #: orderable number: a device named by its pair has no LCSC number at all,
        #: so the fake answers its (R0402) tips under the empty key as well.
        kwargs.setdefault(
            "pin_offsets",
            {"": dict(b054.PIN_OFFSETS["C25744"]), **b054.PIN_OFFSETS},
        )
        super().__init__(**kwargs)
        self.identities = dict(identities)
        self.library = dict(library or {})
        #: library symbol uuid -> the name `lib.symbol.get` answers. A name the
        #: library does not state is an unresolvable symbol, which the flow must
        #: refuse rather than compare document ids instead.
        self.symbols = dict(
            {LIB_SYMBOL: LIB_SYMBOL_NAME} if symbols is None else symbols
        )
        self.library_calls: list[dict] = []
        self.symbol_calls: list[dict] = []

    def geometry(self):
        dump = super().geometry()
        for entry in dump.get("components") or []:
            state = entry.get("state") or {}
            name = str(state.get("Designator") or "")
            record = self.identities.get(name)
            if not record:
                continue
            state["Component"] = {"uuid": record["component"],
                                  "libraryUuid": R1_LIBRARY, "name": name}
            state["Symbol"] = {"uuid": record["symbolRecord"],
                               "libraryUuid": R1_LIBRARY,
                               "name": record["symbolName"]}
            state["SubPartName"] = record["subPart"]
            state["ManufacturerId"] = record["manufacturerId"]
            state["SupplierId"] = record["supplierId"]
        return dump

    async def call(self, action, params=None, **_route):
        if action == "lib.symbol.get":
            params = dict(params or {})
            self.calls.append(action)
            self.symbol_calls.append(params)
            uuid = str(params.get("uuid") or "")
            name = self.symbols.get(uuid)
            if not name:
                return {"uuid": uuid,
                        "libraryUuid": str(params.get("libraryUuid") or ""),
                        "found": False, "item": {}}
            return {"uuid": uuid, "libraryUuid": str(params.get("libraryUuid") or ""),
                    "found": True, "item": {"uuid": uuid, "name": name}}
        if action == "lib.device.get":
            params = dict(params or {})
            self.calls.append(action)
            self.library_calls.append(params)
            uuid = str(params.get("uuid") or "")
            answer = self.library.get(uuid)
            if answer is None:
                return {"uuid": uuid, "libraryUuid": str(params.get("libraryUuid") or ""),
                        "found": False, "item": {}}
            return answer
        return await super().call(action, params, **_route)


def _circuit_with_identity(**params: str) -> CircuitSpec:
    """The 054 divider, with its first part named by a library pair in ``params``."""
    circuit = CircuitSpec.load(b054.CIRCUIT)
    part = circuit.parts[0]
    part.lcsc = ""
    part.params = dict(part.params or {})
    part.params.update(params)
    return circuit


def _identity_plan(tmp_path: Path, *, circuit: CircuitSpec | None = None,
                   name: str = "identity-plan.json"):
    """A plan for that circuit, built the way `draw plan` builds it.

    Only R2 is given an LCSC number: R1 must be placeable **because of** the
    pair, so a plan that still demanded its `lcsc` would refuse here instead of
    producing the file the apply test then lands.
    """
    circuit = circuit if circuit is not None else _circuit_with_identity(
        deviceUuid=R1_DEVICE, libraryUuid=R1_LIBRARY,
    )
    presentation = PresentationSpec.load(b054.PRESENTATION)
    profiles = drawapply.load_library(b054.LIBRARY)
    compiled = drawcompiler.compile(
        circuit, presentation, profiles,
        drawcompiler.CompileBudget(
            page_box=tuple(float(item) for item in b054.PAGE_BOX.split(","))
        ),
    )
    assert compiled.ok, compiled.render_failures()
    plan = drawapply.module_plan(
        compiled.candidates[0], circuit, presentation, profiles,
        lcsc_by_part={"R2": "C25744"},
    )
    path = tmp_path / name
    plan.dump(path)
    return path, plan


def _identities(plan: ChangePlan, record: dict | None) -> dict:
    """What the page will say it placed, per designator (``None`` = no symbol record)."""
    return {
        part.designator: (dict(record) if record is not None else None)
        for part in plan.change.draw_parts
        if part.device_uuid
    }


# ------------------------------------------------------- the plan's own contract


def test_an_old_plan_roundtrips_without_the_pair_and_still_requires_lcsc(tmp_path):
    """No pair, no new keys: the old document's bytes survive a load/dump cycle.

    The second half is the rule this batch does **not** relax: taking an LCSC
    number away without stating a pair is still a refusal, and it is the same
    refusal (`lcsc is empty`) as before — a silent skip would place nothing and
    say nothing.
    """
    plan_path, _plan = b054._plan(tmp_path, name="old-plan.json")
    original = plan_path.read_text(encoding="utf-8")
    payload = json.loads(original)
    for row in payload["change"]["parts"]:
        assert "deviceUuid" not in row, row
        assert "libraryUuid" not in row, row

    loaded = ChangePlan.load(plan_path)
    assert all(
        part.device_uuid == "" and part.library_uuid == ""
        for part in loaded.change.draw_parts
    )
    again = tmp_path / "old-plan-again.json"
    loaded.dump(again)
    assert again.read_text(encoding="utf-8") == original, (
        "a plan with no identity pair must keep the exact bytes it had"
    )

    broken = json.loads(original)
    broken["change"]["parts"][0].pop("lcsc")
    with pytest.raises(ChangePlanError, match="lcsc is empty"):
        ChangePlan.from_jsonable(broken)


def test_a_part_with_a_verified_pair_and_no_lcsc_makes_a_plan(tmp_path):
    """The pair is enough: R1 has no Supplier Part at all and still plans."""
    plan_path, plan = _identity_plan(tmp_path)
    r1 = next(part for part in plan.change.draw_parts if part.designator == "R1")
    assert r1.lcsc == ""
    assert (r1.device_uuid, r1.library_uuid) == (R1_DEVICE, R1_LIBRARY)

    row = next(
        item for item in json.loads(plan_path.read_text(encoding="utf-8"))["change"]["parts"]
        if item["designator"] == "R1"
    )
    assert (row["deviceUuid"], row["libraryUuid"]) == (R1_DEVICE, R1_LIBRARY)

    reloaded = ChangePlan.load(plan_path)
    again = next(part for part in reloaded.change.draw_parts if part.designator == "R1")
    assert (again.device_uuid, again.library_uuid) == (R1_DEVICE, R1_LIBRARY)


@pytest.mark.parametrize("half", ["deviceUuid", "libraryUuid"])
def test_one_half_of_the_pair_is_refused_on_both_documents(tmp_path, half):
    """One uuid is not an identity — refused by the plan reader and by the planner."""
    plan_path, _plan = _identity_plan(tmp_path)
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    row = next(item for item in payload["change"]["parts"] if item["designator"] == "R1")
    row.pop(half)
    with pytest.raises(ChangePlanError, match="the pair is one identity"):
        ChangePlan.from_jsonable(payload)

    # A blank half is the same statement as an absent one, and still one half.
    with pytest.raises(drawapply.DrawPlanError, match="the pair is one identity"):
        _identity_plan(
            tmp_path,
            circuit=_circuit_with_identity(deviceUuid=R1_DEVICE, libraryUuid="  "),
            name="half-plan.json",
        )


def test_a_blank_pair_falls_back_to_the_old_lcsc_requirement(tmp_path):
    """Both halves blank is "no pair": the part then needs its LCSC number again."""
    with pytest.raises(drawapply.DrawPlanError, match="has no LCSC number"):
        _identity_plan(
            tmp_path,
            circuit=_circuit_with_identity(deviceUuid=" ", libraryUuid=""),
            name="blank-plan.json",
        )


# ------------------------------------------------------------ what apply emits


def _apply_identity(monkeypatch, tmp_path, capsys, *, record=CONSISTENT,
                    library=None, symbols=None):
    """Run `draw apply` on the pair-carrying plan against an evidence-aware fake."""
    plan_path, plan = _identity_plan(tmp_path)
    editor = _IdentityEditor(
        _identities(plan, record),
        library={R1_DEVICE: _library_answer()} if library is None else library,
        symbols=symbols,
        exists=False,
        netlists=[{"components": {}}, b054._live_netlist_for(plan)],
    )
    code, payload, printed = b054._apply(monkeypatch, tmp_path, plan_path, editor, capsys)
    return code, payload, printed, editor, plan


def test_apply_places_by_the_explicit_pair_and_sends_no_lcsc(
    monkeypatch, tmp_path, capsys
):
    """A live-shaped page proves the identity without `Component.uuid`.

    The page's `state.Component.uuid` is the document's device-record id and is
    deliberately **different** from the library device uuid (the live shape), so a
    run that passes here can only have proven identity through the library's own
    evidence: the requested uuid resolves, the symbol / sub-part / properties
    agree. R2 keeps the old LCSC call, key for key.
    """
    code, payload, printed, editor, _plan = _apply_identity(
        monkeypatch, tmp_path, capsys
    )
    assert code == 0, printed
    places = [params for action, params in editor.writes
              if action == "sch.place_component"]
    r1 = [params for params in places if params.get("designator") == "R1"]
    assert len(r1) == 1, places
    assert "lcsc" not in r1[0], (
        "a part placed by its verified pair must not send its (absent) Supplier Part"
    )
    assert r1[0]["deviceUuid"] == R1_DEVICE
    assert r1[0]["libraryUuid"] == R1_LIBRARY
    r2 = [params for params in places if params.get("designator") == "R2"]
    assert len(r2) == 1 and r2[0]["lcsc"] == "C25744", places
    assert "deviceUuid" not in r2[0] and "libraryUuid" not in r2[0]
    identity = payload["write"]["deviceIdentity"]
    assert identity["problems"] == []
    basis = identity["identityBasis"]
    assert "document record ids do NOT take part" in basis, basis
    assert "state.Symbol.name" in basis, basis
    evidence = identity["libraryEvidence"][f"{R1_DEVICE}/{R1_LIBRARY}"]
    assert evidence["symbolUuid"] == LIB_SYMBOL
    assert evidence["symbolName"] == LIB_SYMBOL_NAME
    assert evidence["subPartEvidence"] == "available"
    assert editor.library_calls == [
        {"uuid": R1_DEVICE, "libraryUuid": R1_LIBRARY}
    ], editor.library_calls
    assert editor.symbol_calls == [
        {"uuid": LIB_SYMBOL, "libraryUuid": R1_LIBRARY}
    ], editor.symbol_calls


@pytest.mark.parametrize(
    "record, needle",
    [
        ({**CONSISTENT, "symbolName": "SOME_OTHER_SYMBOL"}, "symbol"),
        ({**CONSISTENT, "subPart": "OTHER.1"}, "SubPartName"),
        ({**CONSISTENT, "manufacturerId": "SOMETHING_ELSE"}, "ManufacturerId"),
    ],
)
def test_a_page_whose_library_facts_disagree_is_refused(
    monkeypatch, tmp_path, capsys, record, needle
):
    """Symbol / sub-part / copied property: any disagreement is a different device.

    The coordinates and pins are untouched in every case, which is exactly why the
    identity cannot be read off them.
    """
    code, payload, printed, editor, _plan = _apply_identity(
        monkeypatch, tmp_path, capsys, record=record
    )
    assert code == 2, printed
    assert payload["ok"] is False
    assert payload["reason"] == "device_identity_disagrees", payload.get("reason")
    problems = payload["write"]["deviceIdentity"]["problems"]
    assert any("R1" in item and needle in item for item in problems), problems
    actions = [action for action, _params in editor.writes]
    assert "sch.place_wire" not in actions, actions
    assert "sch.doc.save" not in actions, actions


def test_a_document_symbol_id_that_differs_from_the_library_is_not_a_mismatch(
    monkeypatch, tmp_path, capsys
):
    """Live shape: `state.Symbol.uuid` is a document record, not the library uuid.

    All 47 parts of the old P1 page answered a `state.Symbol.uuid` that matched no
    library `association.symbolUuid` (0/47). The identity is therefore proven by
    the library symbol's **name**, which does agree here — a run that failed on the
    id would refuse every one of those parts.
    """
    code, payload, printed, editor, _plan = _apply_identity(
        monkeypatch, tmp_path, capsys,
        record={**CONSISTENT, "symbolRecord": OTHER_SYMBOL},
    )
    assert code == 0, printed
    assert payload["write"]["deviceIdentity"]["problems"] == []
    assert editor.symbol_calls == [
        {"uuid": LIB_SYMBOL, "libraryUuid": R1_LIBRARY}
    ], editor.symbol_calls


def test_a_library_symbol_that_cannot_be_named_is_refused(monkeypatch, tmp_path, capsys):
    """`lib.symbol.get` unanswered is a refusal — never a fallback to ids.

    The page would look consistent, and the association uuid does resolve as a
    *string*; what is missing is the library's name. Comparing document ids instead
    is exactly the bug this batch exists to remove, so the run stops before the
    first placement.
    """
    code, payload, printed, editor, _plan = _apply_identity(
        monkeypatch, tmp_path, capsys, symbols={}
    )
    assert code == 2, printed
    assert payload["reason"] == "device_identity_evidence_unavailable", payload.get("reason")
    actions = [action for action, _params in editor.writes]
    assert "sch.place_component" not in actions, actions


def test_a_library_that_states_no_sub_part_passes_on_the_other_evidence(
    monkeypatch, tmp_path, capsys
):
    """`subPartNames: ['']` is no evidence, not a mismatch (measured live).

    The page's `SubPartName` is empty by construction here. The identity may still
    be proven — the requested uuid resolves, its symbol is the page's symbol, and
    the copied properties agree — but the report has to say that the sub-part half
    was unavailable rather than pretend it checked it. `Component.uuid` stays out
    of the comparison throughout.
    """
    code, payload, printed, editor, _plan = _apply_identity(
        monkeypatch, tmp_path, capsys,
        record={**CONSISTENT, "subPart": ""},
        library={R1_DEVICE: _library_answer(sub_part_names=[""])},
    )
    assert code == 0, printed
    evidence = payload["write"]["deviceIdentity"]["libraryEvidence"][
        f"{R1_DEVICE}/{R1_LIBRARY}"
    ]
    assert evidence["subPartNames"] == []
    assert evidence["subPartEvidence"] == "unavailable"
    assert "subPartEvidence=unavailable" in payload["write"]["deviceIdentity"]["identityBasis"]
    assert payload["write"]["deviceIdentity"]["problems"] == []


def test_empty_copied_properties_are_unavailable_evidence_not_a_mismatch(
    monkeypatch, tmp_path, capsys
):
    """The live V4 shape: the host places by deviceUuid and copies no properties.

    Measured on the 47-part P1 page: both ``state.ManufacturerId`` and
    ``state.SupplierId`` are empty on 40 parts (the other 7 carried copied
    properties), while ``state.Symbol.name`` and ``state.Symbol.libraryUuid``
    agree with the library exactly. An empty page
    field is **unavailable copied evidence**, not a value that disagrees, so the
    run continues — and the report names the fields it could not read back instead
    of pretending it compared them.
    """
    code, payload, printed, editor, _plan = _apply_identity(
        monkeypatch, tmp_path, capsys,
        record={**CONSISTENT, "manufacturerId": "", "supplierId": ""},
    )
    assert code == 0, printed
    identity = payload["write"]["deviceIdentity"]
    assert identity["problems"] == []
    assert identity["copiedPropertyEvidenceUnavailable"] == [
        "R1.ManufacturerId", "R1.SupplierId",
    ], identity
    assert "copiedPropertyEvidenceUnavailable" in identity["identityBasis"]
    actions = [action for action, _params in editor.writes]
    assert "sch.place_wire" in actions and "sch.doc.save" in actions, actions


def test_empty_sub_part_and_empty_copied_properties_still_pass_on_the_rest(
    monkeypatch, tmp_path, capsys
):
    """`subPartNames: ['']` **and** no copied properties: the authorised case.

    The library states a symbol name, a library uuid and the manufacturer/supplier
    properties; the page copied neither the sub-part nor the two properties. The
    identity then rests on the library symbol name, the library uuid and the fresh
    pin/body geometry — and the report has to carry both unavailability facts
    (``subPartEvidence`` and ``copiedPropertyEvidenceUnavailable``) so the pass is
    not read as a comparison that happened.
    """
    code, payload, printed, editor, _plan = _apply_identity(
        monkeypatch, tmp_path, capsys,
        record={
            **CONSISTENT, "subPart": "", "manufacturerId": "", "supplierId": "",
        },
        library={R1_DEVICE: _library_answer(sub_part_names=[""])},
    )
    assert code == 0, printed
    identity = payload["write"]["deviceIdentity"]
    assert identity["problems"] == []
    evidence = identity["libraryEvidence"][f"{R1_DEVICE}/{R1_LIBRARY}"]
    assert evidence["subPartEvidence"] == "unavailable"
    assert identity["copiedPropertyEvidenceUnavailable"] == [
        "R1.ManufacturerId", "R1.SupplierId",
    ], identity
    actions = [action for action, _params in editor.writes]
    assert "sch.place_wire" in actions and "sch.doc.save" in actions, actions


def test_a_non_empty_supplier_id_that_differs_is_still_refused(
    monkeypatch, tmp_path, capsys
):
    """The other half of the same rule: a stated value that differs is a refusal.

    Only the **empty** page field is excused. A page that copied a Supplier Part
    the library does not state names a different device, and the run stops after
    placement with no wire and no save.
    """
    code, payload, printed, editor, _plan = _apply_identity(
        monkeypatch, tmp_path, capsys,
        record={**CONSISTENT, "supplierId": "C99999"},
    )
    assert code == 2, printed
    assert payload["ok"] is False
    assert payload["reason"] == "device_identity_disagrees", payload.get("reason")
    problems = payload["write"]["deviceIdentity"]["problems"]
    assert any("R1.SupplierId" in item and "C99999" in item for item in problems), problems
    actions = [action for action, _params in editor.writes]
    assert "sch.place_wire" not in actions, actions
    assert "sch.doc.save" not in actions, actions


def test_a_library_with_neither_sub_part_nor_properties_is_refused(
    monkeypatch, tmp_path, capsys
):
    """`['']` plus no manufacturer/supplier fact leaves nothing to judge by."""
    code, payload, printed, editor, _plan = _apply_identity(
        monkeypatch, tmp_path, capsys,
        record={**CONSISTENT, "subPart": ""},
        library={
            R1_DEVICE: _library_answer(
                sub_part_names=[""], manufacturer_id="", supplier_id=""
            )
        },
    )
    assert code == 2, printed
    assert payload["reason"] == "device_identity_disagrees", payload.get("reason")
    problems = payload["write"]["deviceIdentity"]["problems"]
    assert any("no evidence left" in item for item in problems), problems


def test_an_unresolvable_device_uuid_is_refused_before_any_write(
    monkeypatch, tmp_path, capsys
):
    """`lib.device.get` answering found:false is not evidence — and no fallback.

    The page here would even look consistent; the refusal comes from the library,
    before the first placement, because a device uuid nothing resolves names
    nothing that can be verified afterwards.
    """
    code, payload, printed, editor, _plan = _apply_identity(
        monkeypatch, tmp_path, capsys, library={}
    )
    assert code == 2, printed
    assert payload["ok"] is False
    assert payload["reason"] == "device_identity_unresolved", payload.get("reason")
    actions = [action for action, _params in editor.writes]
    assert "sch.place_component" not in actions, actions
