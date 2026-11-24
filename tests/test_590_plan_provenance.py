"""590 W-R1: the plan's *route* and the seal that goes stale when geometry moves.

hole568's D-1/D-2/D-3 measured three things this batch fixes:

* **D-1** — a hand-edited `LayoutPlan` whose `geometrySha256` was recomputed loaded
  as `verdict: pass` with the compiler's own `notes`: the document said "self
  consistent" and nothing said "this is not the picture that was compiled". The
  seal below (``provenanceSha256``) is computed from the versioned domain, the
  route and the geometry digest, so an edit that updates only `geometrySha256`
  leaves a **stale seal** and is refused. It detects staleness, not authorship:
  anyone who recomputes every public hash re-seals the document, and no test here
  claims otherwise.
* **D-2** — `reference-replay` had no machine-readable form anywhere in
  `src`/`tests`/`contracts`/`dsh-plugin`. `route` is now a closed three-value
  vocabulary, and a document that predates it reads as `reference-replay`
  **without** gaining a key: load -> dump is still byte for byte the old file.
* **D-3** — a successful compile's JSON had no route at all, while the failure
  path pinned `route: agent-adjusted` as a constant. A successful compile now
  states `route`/`mode`/`provenance`, and a zero-candidate one still says
  `agent-adjusted` (it is not an automatic drawing).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.core.layoutplan import (
    LayoutPart,
    LayoutPlan,
    LayoutPlanError,
    LayoutSegment,
    LayoutSource,
    PLAN_ROUTES,
    ROUTE_AGENT_ADJUSTED,
    ROUTE_AUTOMATIC,
    ROUTE_REFERENCE_REPLAY,
)
from boardwise.core.pagelayoutplan import (
    PageLayoutPlan,
    PageLayoutPlanError,
    PageModule,
    PagePort,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "outputs" / "054_drawcompile"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "drawapply"
LIBRARY = FIXTURES / "library.json"
CIRCUIT = FIXTURES / "divider.circuit.json"
PRESENTATION = FIXTURES / "divider.presentation.json"
PAGE_BOX = "0,-1000,1200,0"
HASH = "a" * 64
PROV = "verified_recipe"


# ------------------------------------------------------------------ fixtures


def _plan() -> LayoutPlan:
    """A plan as the compiler builds one: constructed, so `automatic` by default."""
    return LayoutPlan(
        source=LayoutSource(circuit_sha256=HASH, presentation_sha256=HASH),
        parts=[
            LayoutPart(part_id="R1", reference="R101", symbol_ref="R0402",
                       symbol_hash=HASH, x=0.0, y=0.0),
            LayoutPart(part_id="R2", reference="R102", symbol_ref="R0402",
                       symbol_hash=HASH, x=0.0, y=-140.0),
        ],
        segments=[LayoutSegment(net="N1", points=[(0.0, 0.0), (10.0, 0.0)])],
    )


def _page() -> PageLayoutPlan:
    plan = _plan()
    return PageLayoutPlan(
        plan=plan,
        modules=[PageModule(
            id="m1", grammar_ref="ic-periphery", parts=["R1", "R2"],
            origin=(0.0, 0.0), frame=(0.0, 0.0, 100.0, 100.0),
            internal_geometry_sha256=HASH,
            ports=[PagePort(module="m1", net="N1", kind="label", x=0.0, y=0.0)],
        )],
        page_box=(0.0, 0.0, 300.0, 200.0),
    )


def _write(tmp_path: Path, name: str, body: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def _geometry_digest_of(body: dict, *, page: bool) -> str:
    """The geometry digest of a payload, computed the way any reader can.

    The digest is route-independent by contract (route and seal stay out of it),
    so the payload is read with those two claims taken off: the point of this
    batch is that a *stale* seal cannot be used to compute anything.
    """
    stripped = {key: value for key, value in body.items()
                if key not in ("geometrySha256", "provenanceSha256", "route")}
    if page:
        return PageLayoutPlan.from_dict(stripped).page_geometry_sha256()
    return LayoutPlan.from_dict(stripped).geometry_sha256()


def _resealed_plan_doc() -> dict:
    """The D-1 forgery, step by step: edit geometry, then recompute *only* geometrySha256.

    The digest is recomputed from the edited payload (the attacker has the same
    public code), which is why `geometrySha256` alone cannot be the guard.
    """
    body = _plan().to_jsonable()
    body["parts"][0]["x"] += 10.0
    body["geometrySha256"] = _geometry_digest_of(body, page=False)
    return body


def _resealed_page_doc() -> dict:
    body = _page().to_jsonable()
    body["modules"][0]["frame"][2] += 10.0
    body["geometrySha256"] = _geometry_digest_of(body, page=True)
    return body


# ===================== D-1: a stale seal is refused, geometry alone is not enough


def test_an_automatic_plan_states_its_route_and_its_seal() -> None:
    body = _plan().to_jsonable()
    assert body["route"] == ROUTE_AUTOMATIC
    assert len(body["provenanceSha256"]) == 64
    assert body["provenanceSha256"] == _plan().provenance_sha256()


def test_editing_geometry_and_recomputing_only_the_digest_is_refused(tmp_path) -> None:
    body = _resealed_plan_doc()
    assert body["geometrySha256"] == _geometry_digest_of(body, page=False), (
        "the forgery's geometry digest is correct — that is the point"
    )
    with pytest.raises(LayoutPlanError) as caught:
        LayoutPlan.load(_write(tmp_path, "plan.json", body))
    message = str(caught.value)
    assert "provenanceSha256" in message and "seal" in message, message


def test_editing_a_page_frame_and_recomputing_only_the_digest_is_refused(tmp_path) -> None:
    body = _resealed_page_doc()
    with pytest.raises(PageLayoutPlanError) as caught:
        PageLayoutPlan.load(_write(tmp_path, "page.json", body))
    message = str(caught.value)
    assert "provenanceSha256" in message and "seal" in message, message


def test_a_missing_seal_on_an_automatic_plan_is_refused(tmp_path) -> None:
    body = _plan().to_jsonable()
    body.pop("provenanceSha256")
    with pytest.raises(LayoutPlanError) as caught:
        LayoutPlan.load(_write(tmp_path, "plan.json", body))
    assert "provenanceSha256" in str(caught.value), str(caught.value)


def test_a_missing_seal_on_an_automatic_page_is_refused(tmp_path) -> None:
    body = _page().to_jsonable()
    body.pop("provenanceSha256")
    with pytest.raises(PageLayoutPlanError) as caught:
        PageLayoutPlan.load(_write(tmp_path, "page.json", body))
    assert "provenanceSha256" in str(caught.value), str(caught.value)


def test_a_seal_that_disagrees_with_its_own_route_is_refused(tmp_path) -> None:
    """The domain and the route are in the digest: a seal cannot be transplanted."""
    body = _plan().to_jsonable()
    body["route"] = ROUTE_AGENT_ADJUSTED
    with pytest.raises(LayoutPlanError) as caught:
        LayoutPlan.load(_write(tmp_path, "plan.json", body))
    assert "seal" in str(caught.value) or "route" in str(caught.value)


# ===================== D-2: three routes, one closed vocabulary


def test_the_route_vocabulary_is_closed() -> None:
    assert PLAN_ROUTES == (
        ROUTE_AUTOMATIC, ROUTE_REFERENCE_REPLAY, ROUTE_AGENT_ADJUSTED,
    )
    assert sorted(PLAN_ROUTES) == ["agent-adjusted", "automatic", "reference-replay"]


@pytest.mark.parametrize("route", [ROUTE_REFERENCE_REPLAY, ROUTE_AGENT_ADJUSTED])
def test_an_explicit_non_automatic_route_round_trips_without_a_seal(tmp_path, route) -> None:
    body = _plan().to_jsonable()
    body.pop("provenanceSha256")
    body["route"] = route
    path = _write(tmp_path, "plan.json", body)
    plan = LayoutPlan.load(path)
    assert plan.route == route
    assert "provenanceSha256" not in plan.to_jsonable()
    assert plan.to_jsonable()["route"] == route
    again = tmp_path / "again.json"
    plan.dump(again)
    assert LayoutPlan.load(again).route == route


def test_a_non_automatic_plan_refuses_a_seal(tmp_path) -> None:
    body = _plan().to_jsonable()
    body["route"] = ROUTE_AGENT_ADJUSTED
    with pytest.raises(LayoutPlanError) as caught:
        LayoutPlan.load(_write(tmp_path, "plan.json", body))
    assert "provenanceSha256" in str(caught.value), str(caught.value)


@pytest.mark.parametrize("bad", ["automatic ", "Automatic", "", "manual", None, 7])
def test_an_unknown_route_is_refused_by_name(tmp_path, bad) -> None:
    body = _plan().to_jsonable()
    body["route"] = bad
    with pytest.raises(LayoutPlanError) as caught:
        LayoutPlan.load(_write(tmp_path, "plan.json", body))
    assert "route" in str(caught.value), str(caught.value)


def test_an_old_document_reads_as_reference_replay_and_gains_no_key(tmp_path) -> None:
    """A document from before this contract: no route, no seal, no byte moved."""
    body = _plan().to_jsonable()
    body.pop("route")
    body.pop("provenanceSha256")
    path = _write(tmp_path, "old.json", body)
    plan = LayoutPlan.load(path)
    assert plan.route == ROUTE_REFERENCE_REPLAY
    assert plan.route != ROUTE_AUTOMATIC, "silence is not an automatic drawing"
    assert plan.route_declared is False
    out = tmp_path / "rt.json"
    plan.dump(out)
    assert out.read_bytes() == path.read_bytes()


def test_an_automatic_document_round_trips_byte_for_byte(tmp_path) -> None:
    first = tmp_path / "first.json"
    _plan().dump(first)
    document = LayoutPlan.load(first)
    assert document.route == ROUTE_AUTOMATIC and document.route_declared is True
    second = tmp_path / "second.json"
    document.dump(second)
    assert second.read_bytes() == first.read_bytes()

    page_first = tmp_path / "page1.json"
    _page().dump(page_first)
    page = PageLayoutPlan.load(page_first)
    assert page.route == ROUTE_AUTOMATIC and page.plan.route == ROUTE_AUTOMATIC
    page_second = tmp_path / "page2.json"
    page.dump(page_second)
    assert page_second.read_bytes() == page_first.read_bytes()


def test_deleting_the_geometry_digest_does_not_bypass_the_seal(tmp_path) -> None:
    """590B: the seal is compared whenever it is stated, digest or no digest.

    The 590 rule compared the seal only when `geometrySha256` was present, so the
    same forgery with that derived key deleted loaded as `automatic`.
    """
    body = _resealed_plan_doc()
    body.pop("geometrySha256")
    with pytest.raises(LayoutPlanError) as caught:
        LayoutPlan.load(_write(tmp_path, "plan.json", body))
    message = str(caught.value)
    assert "provenanceSha256" in message and "seal" in message, message


def test_deleting_a_page_geometry_digest_does_not_bypass_the_seal(tmp_path) -> None:
    body = _resealed_page_doc()
    body.pop("geometrySha256")
    with pytest.raises(PageLayoutPlanError) as caught:
        PageLayoutPlan.load(_write(tmp_path, "page.json", body))
    message = str(caught.value)
    assert "provenanceSha256" in message and "seal" in message, message


def test_an_automatic_document_may_omit_the_geometry_digest(tmp_path) -> None:
    """Negative control: the derived display key stays optional.

    An untouched automatic document whose `geometrySha256` is left out is still a
    document — its seal matches its geometry, which is all the seal promises.
    """
    body = _plan().to_jsonable()
    body.pop("geometrySha256")
    plan = LayoutPlan.load(_write(tmp_path, "plan.json", body))
    assert plan.route == ROUTE_AUTOMATIC
    assert plan.geometry_sha256() == _plan().geometry_sha256()


def test_an_automatic_page_may_omit_the_page_geometry_digest(tmp_path) -> None:
    body = _page().to_jsonable()
    body.pop("geometrySha256")
    page = PageLayoutPlan.load(_write(tmp_path, "page.json", body))
    assert page.route == ROUTE_AUTOMATIC
    assert page.page_geometry_sha256() == _page().page_geometry_sha256()


def test_the_layout_digest_is_not_moved_by_the_route_keys() -> None:
    body = _plan().to_jsonable()
    plan = LayoutPlan.from_dict({key: value for key, value in body.items()
                                 if key != "geometrySha256"})
    assert plan.geometry_sha256() == body["geometrySha256"]
    assert "route" not in plan.geometry_json()
    assert "provenanceSha256" not in plan.geometry_json()


# ===================== old-contract documents keep their bytes


@pytest.fixture(scope="module")
def real_samples() -> list[Path]:
    """Whatever the 054 output directory holds now — working artifacts, not a fixture.

    The directory has been rewritten by real compiles since 054, so a candidate
    here may already state `route`/`provenanceSha256`. The old-contract shapes are
    derived from them below instead of being assumed on disk.
    """
    layouts = sorted(SAMPLES.glob("cand*.layout.json"))
    pages = sorted(SAMPLES.glob("cand*.page.json"))
    assert layouts and pages, "the 054 candidates are the compiler's real output"
    return layouts + pages


def _pre_590_shape(source: Path, target: Path) -> None:
    """Write the bytes a pre-590 compiler would have written for ``source``.

    590 adds exactly two keys — `route` and, on an automatic document, its
    `provenanceSha256` — and neither is part of `geometry_json`. Taking the two
    claims off a real candidate therefore leaves the document the previous
    contract produced, byte for byte, and the result no longer depends on
    whether the output directory has been recompiled since.
    """
    cls = PageLayoutPlan if source.name.endswith(".page.json") else LayoutPlan
    document = cls.load(source).to_jsonable()
    document.pop("route", None)
    document.pop("provenanceSha256", None)
    if "plan" in document:  # a page embeds its merged plan, sealed the same way
        document["plan"].pop("route", None)
        document["plan"].pop("provenanceSha256", None)
    target.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def pre_590_samples(tmp_path_factory, real_samples) -> list[Path]:
    root = tmp_path_factory.mktemp("pre590")
    shapes: list[Path] = []
    for source in real_samples:
        target = root / source.name  # same name, so the class is picked the same way
        _pre_590_shape(source, target)
        shapes.append(target)
    return shapes


def test_pre_590_shapes_read_as_reference_replay_and_dump_unchanged(
    tmp_path, pre_590_samples
) -> None:
    for source in pre_590_samples:
        cls = PageLayoutPlan if source.name.endswith(".page.json") else LayoutPlan
        document = cls.load(source)
        assert document.route == ROUTE_REFERENCE_REPLAY, source.name
        assert document.route_declared is False, source.name
        out = tmp_path / f"{source.stem}.rt{source.suffix}"
        document.dump(out)
        assert out.read_bytes() == source.read_bytes(), (
            f"{source.name}: an old document must not gain route/provenance keys"
        )


def test_real_candidates_state_their_route_and_a_seal_of_their_own(real_samples) -> None:
    """The other end of the same contract: what the compiler writes now.

    A candidate that states a route says `automatic`, carries a seal, and the
    seal is *that document's* (route + geometry digest) — not a value moved in
    from elsewhere. A candidate nobody has recompiled since 590 still reads as
    an old document with no key gained, which is the compatibility half.
    """
    automatic = 0
    for source in real_samples:
        cls = PageLayoutPlan if source.name.endswith(".page.json") else LayoutPlan
        document = cls.load(source)
        body = document.to_jsonable()
        if not document.route_declared:
            assert document.route == ROUTE_REFERENCE_REPLAY, source.name
            assert "route" not in body and "provenanceSha256" not in body, source.name
            continue
        automatic += 1
        assert document.route == ROUTE_AUTOMATIC, source.name
        assert body["route"] == ROUTE_AUTOMATIC, source.name
        assert body["provenanceSha256"] == document.provenance_sha256(), source.name
    assert automatic, "no candidate carries the post-590 compass at all"


# ===================== D-3: a successful compile says what it is


def _compile(tmp_path: Path, *, page: bool = False) -> tuple[int, dict, Path]:
    out = tmp_path / "previews"
    report = tmp_path / "compile.json"
    circuit, presentation = CIRCUIT, PRESENTATION
    if page:
        circuit, presentation = _page_specs(tmp_path)
    code = cli.main([
        "draw", "compile",
        "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE_BOX,
        "--out", str(out), "--json", str(report),
    ])
    return code, json.loads(report.read_text(encoding="utf-8")), out


def _page_specs(tmp_path: Path) -> tuple[Path, Path]:
    circuit = {"parts": [
        {"id": "U1", "symbolRef": "AMS1117-3.3", "value": "AMS1117-3.3",
         "lcsc": "C6186", "provenance": PROV},
        {"id": "C1", "symbolRef": "C0402", "value": "10uF", "lcsc": "C15525",
         "provenance": PROV},
        {"id": "R1", "symbolRef": "R0402", "value": "10k", "lcsc": "C25744",
         "provenance": PROV},
        {"id": "R2", "symbolRef": "R0402", "value": "10k", "lcsc": "C25744",
         "provenance": PROV},
    ], "nets": [
        {"id": "VIN", "class": "power", "members": ["U1.3", "C1.1", "R1.1"],
         "provenance": PROV},
        {"id": "3V3", "class": "power", "members": ["U1.2"], "provenance": PROV},
        {"id": "TAP", "class": "signal", "members": ["R1.2", "R2.1"],
         "provenance": PROV},
        {"id": "GND", "class": "gnd", "members": ["U1.1", "C1.2", "R2.2"],
         "provenance": PROV},
    ]}
    presentation = {
        "modules": [
            {"id": "pwr", "parts": ["U1", "C1"], "role": "regulator",
             "grammarRef": "ldo"},
            {"id": "sense", "parts": ["R1", "R2"], "role": "divider",
             "grammarRef": "voltage-divider"},
        ],
        "flow": [["pwr", "sense"]],
        "portRoles": {"VIN": "input", "3V3": "output"},
    }
    circuit_path = tmp_path / "page.circuit.json"
    presentation_path = tmp_path / "page.presentation.json"
    circuit_path.write_text(json.dumps(circuit), encoding="utf-8")
    presentation_path.write_text(json.dumps(presentation), encoding="utf-8")
    return circuit_path, presentation_path


def test_a_successful_compile_states_route_mode_and_provenance(tmp_path, capsys) -> None:
    code, payload, out = _compile(tmp_path)
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert payload["ok"] is True
    assert payload["route"] == ROUTE_AUTOMATIC
    assert payload["mode"] == ROUTE_AUTOMATIC
    provenance = payload["provenance"]
    assert provenance["mode"] == ROUTE_AUTOMATIC
    assert provenance["attestation"] == "self-consistency-only"
    assert "recovery" not in payload, "a successful compile is not a manual route"
    plan = LayoutPlan.load(out / "cand1.layout.json")
    assert plan.route == ROUTE_AUTOMATIC
    seals = {item["geometrySha256"]: item["provenanceSha256"]
             for item in payload["candidates"]}
    assert seals[plan.geometry_sha256()] == plan.provenance_sha256()


def test_a_successful_page_compile_states_route_mode_and_provenance(
    tmp_path, capsys
) -> None:
    code, payload, out = _compile(tmp_path, page=True)
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert payload["document"] == "page"
    assert payload["route"] == ROUTE_AUTOMATIC and payload["mode"] == ROUTE_AUTOMATIC
    assert payload["provenance"]["attestation"] == "self-consistency-only"
    page = PageLayoutPlan.load(out / "cand1.page.json")
    assert page.route == ROUTE_AUTOMATIC
    assert page.plan.route == ROUTE_AUTOMATIC, "the merged drawing is sealed too"
    assert payload["pages"][0]["provenanceSha256"] == page.page_provenance_sha256()


def test_a_zero_candidate_compile_does_not_call_itself_automatic(tmp_path, capsys) -> None:
    spec = json.loads(CIRCUIT.read_text(encoding="utf-8"))
    spec["nets"][1]["members"] = ["R1.2", "R2.9"]
    broken = tmp_path / "broken.circuit.json"
    broken.write_text(json.dumps(spec), encoding="utf-8")
    report = tmp_path / "compile.json"
    code = cli.main([
        "draw", "compile", "--circuit", str(broken),
        "--presentation", str(PRESENTATION), "--profiles", str(LIBRARY),
        "--page-box", PAGE_BOX, "--out", str(tmp_path / "out"),
        "--json", str(report),
    ])
    capsys.readouterr()
    assert code == 5
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert "route" not in payload and "mode" not in payload
    assert "provenance" not in payload
    assert payload["recovery"]["route"] == ROUTE_AGENT_ADJUSTED


def test_a_recompiled_plan_keeps_every_old_field_and_coordinate(tmp_path, capsys) -> None:
    code, payload, out = _compile(tmp_path)
    capsys.readouterr()
    assert code == 0
    body = json.loads((out / "cand1.layout.json").read_text(encoding="utf-8"))
    for key in ("kind", "planVersion", "source", "target", "parts", "segments",
                "junctions", "labels", "powerSymbols", "texts", "evidence",
                "verdict", "geometrySha256", "notes"):
        assert key in body, key
    assert body["verdict"] == payload["candidates"][0]["verdict"]
    assert body["geometrySha256"] == payload["candidates"][0]["geometrySha256"]
