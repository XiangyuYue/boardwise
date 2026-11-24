"""582: the two draw documents' own load contract (hole569 E-02…E-07).

`LayoutPlan` and `PageLayoutPlan` are the two documents a drawing lands by, and
hole569 measured six ways their readers were looser than the documents they
write:

* **E-02** — NaN/Inf/`1e400` went straight into a plan and came back out as the
  `NaN`/`Infinity` tokens JSON does not have (`nan < x` is false, so the box
  ordering test never fired either);
* **E-03** — a non-UTF-8 file leaked `UnicodeDecodeError` (a `ValueError`, not
  the `OSError` the readers caught) out of `load`;
* **E-04/E-05** — `planVersion` and `kind` were optional on the way in, so a
  document with no version read as v1 and a document with no identity read as
  whatever the caller hoped;
* **E-06** — a real page candidate loaded and re-dumped was two bytes longer:
  the writer's `sum(...)` metric `0` came back as `0.0`;
* **E-07** — `_point` took `[x, y, z]` and silently dropped `z`.

Every assertion below goes through the production readers (`load`/`from_dict`)
on a document written by the production writer (`to_jsonable`), except E-03's
non-UTF-8 bytes and E-02's `1e400`, which no writer can produce.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from boardwise.core.layoutplan import (
    LayoutEvidence,
    LayoutJunction,
    LayoutLabel,
    LayoutPart,
    LayoutPlan,
    LayoutPlanError,
    LayoutPowerSymbol,
    LayoutSegment,
    LayoutSource,
    LayoutText,
)
from boardwise.core.pagelayoutplan import (
    PageLayoutPlan,
    PageLayoutPlanError,
    PageModule,
    PagePort,
)
from boardwise.core import layoutplan as layoutplan_module
from boardwise.core import pagelayoutplan as pagelayoutplan_module

HASH = "a" * 64
ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "outputs" / "054_drawcompile"

NON_FINITE = [float("nan"), float("inf"), float("-inf")]


# ------------------------------------------------------------------ fixtures


def _layout_plan() -> LayoutPlan:
    return LayoutPlan(
        source=LayoutSource(circuit_sha256=HASH, presentation_sha256=HASH),
        parts=[LayoutPart(
            part_id="R1", symbol_ref="R0402", symbol_hash=HASH, x=0.0, y=0.0,
        )],
        segments=[LayoutSegment(net="N1", points=[(0.0, 0.0), (10.0, 0.0)])],
        junctions=[LayoutJunction(net="N1", x=0.0, y=0.0)],
        labels=[LayoutLabel(
            net="N1", text="N1", bbox=(0.0, 0.0, 10.0, 4.0), x=0.0, y=0.0,
        )],
        power_symbols=[LayoutPowerSymbol(
            symbol_ref="PWR-N1", symbol_hash=HASH, net="N1", x=0.0, y=0.0,
        )],
        texts=[LayoutText(kind="note", text="note", bbox=(0.0, 0.0, 5.0, 5.0))],
        evidence=LayoutEvidence(
            checker="test/1", soft_metrics={"k": 0.0},
        ),
    )


def _layout_doc() -> dict:
    """A valid layout document with every derived claim removed.

    They are removed so a mutated coordinate is refused for *itself*: a stale
    `geometrySha256` would otherwise refuse the document first and hide whether
    the number gate exists (569-E measured exactly that masking). Since 590 the
    document also *states how it was made* (`route`) and seals that with a digest
    over its own geometry, so "no derived claims" covers the route and its seal
    too (590B: the seal is a promise about the geometry, and 590C keeps this
    fixture free of it rather than leaving a stale promise behind).
    """
    body = _layout_plan().to_jsonable()
    for key in ("verdict", "geometrySha256", "route", "provenanceSha256"):
        body.pop(key)
    return body


def _page_doc() -> dict:
    plan = _layout_plan()
    page = PageLayoutPlan(
        plan=plan,
        modules=[PageModule(
            id="m1", grammar_ref="ic-periphery", parts=["R1"],
            origin=(0.0, 0.0), frame=(0.0, 0.0, 100.0, 100.0),
            internal_geometry_sha256=HASH,
            ports=[PagePort(module="m1", net="N1", kind="label", x=0.0, y=0.0)],
        )],
        page_box=(0.0, 0.0, 300.0, 200.0),
        page_evidence=LayoutEvidence(checker="test-page/1", soft_metrics={"k": 0.0}),
    )
    body = page.to_jsonable()
    # 590C: the same four keys at both levels — the page's own route/seal and the
    # nested plan's, so neither layer keeps a stale provenance promise.
    for key in ("verdict", "geometrySha256", "route", "provenanceSha256"):
        body.pop(key)
        body["plan"].pop(key)
    return body


def _set(doc: dict, path: tuple, value) -> dict:
    target = doc
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return doc


def _write(tmp_path: Path, name: str, body: dict) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


LAYOUT_NUMBER_PATHS = [
    ("parts", 0, "x"),
    ("parts", 0, "y"),
    ("segments", 0, "points"),
    ("junctions", 0, "x"),
    ("labels", 0, "x"),
    ("powerSymbols", 0, "y"),
    ("texts", 0, "bbox"),
    ("texts", 0, "x"),
    ("evidence", "softMetrics", "k"),
]

PAGE_NUMBER_PATHS = [
    ("modules", 0, "origin"),
    ("modules", 0, "frame"),
    ("modules", 0, "ports", 0, "x"),
    ("modules", 0, "ports", 0, "y"),
    ("pageBox",),
    ("pageEvidence", "softMetrics", "k"),
]


def _with_non_finite(body: dict, path: tuple, bad: float) -> dict:
    """Put `bad` at `path`, keeping every list-shaped slot list-shaped."""
    if path[-1] == "points":
        return _set(body, path, [[0.0, 0.0], [bad, 0.0]])
    current = body
    for key in path:
        current = current[key]
    if isinstance(current, (list, tuple)) and len(current) in (2, 4):
        return _set(body, path, [bad, *current[1:]])
    return _set(body, path, bad)


# ===================== E-02: a non-finite number is not a position


@pytest.mark.parametrize("where", LAYOUT_NUMBER_PATHS)
@pytest.mark.parametrize("bad", NON_FINITE, ids=["nan", "inf", "-inf"])
def test_layout_refuses_a_non_finite_number(tmp_path, where, bad) -> None:
    path = _write(tmp_path, "plan.json", _with_non_finite(_layout_doc(), where, bad))
    with pytest.raises(LayoutPlanError) as caught:
        LayoutPlan.load(path)
    assert "finite" in str(caught.value), str(caught.value)


@pytest.mark.parametrize("where", PAGE_NUMBER_PATHS)
@pytest.mark.parametrize("bad", NON_FINITE, ids=["nan", "inf", "-inf"])
def test_page_refuses_a_non_finite_number(tmp_path, where, bad) -> None:
    path = _write(tmp_path, "page.json", _with_non_finite(_page_doc(), where, bad))
    with pytest.raises(PageLayoutPlanError) as caught:
        PageLayoutPlan.load(path)
    assert "finite" in str(caught.value), str(caught.value)


@pytest.mark.parametrize("literal", ["1e400", "-1e400"])
def test_a_number_that_overflows_a_float_is_refused(tmp_path, literal) -> None:
    """`1e400` is valid JSON and parses to `inf`; `10**400` is a huge int."""
    body = _layout_doc()
    path = _write(tmp_path, "plan.json", body)
    text = path.read_text(encoding="utf-8").replace(
        '"x": 0.0', f'"x": {literal}', 1
    )
    assert literal in text
    path.write_text(text, encoding="utf-8")
    with pytest.raises(LayoutPlanError) as caught:
        LayoutPlan.load(path)
    assert "finite" in str(caught.value), str(caught.value)


def test_an_integer_literal_too_large_for_a_float_is_refused(tmp_path) -> None:
    path = _write(tmp_path, "plan.json", _set(_layout_doc(), ("parts", 0, "x"), 10**400))
    with pytest.raises(LayoutPlanError) as caught:
        LayoutPlan.load(path)
    assert "finite" in str(caught.value), str(caught.value)


def test_dump_never_writes_a_json_nan(tmp_path) -> None:
    """A plan built in Python with a NaN cannot be saved as if it were JSON."""
    plan = _layout_plan()
    bad = dataclasses.replace(plan, parts=[dataclasses.replace(plan.parts[0], x=float("nan"))])
    out = tmp_path / "bad-layout.json"
    with pytest.raises(ValueError):
        bad.dump(out)
    assert not out.exists(), "a refused dump must not leave half a document behind"


def test_page_dump_never_writes_a_json_nan(tmp_path) -> None:
    page = PageLayoutPlan.load(_write(tmp_path, "page.json", _page_doc()))
    bad = dataclasses.replace(page, page_box=(float("inf"), 0.0, 10.0, 10.0))
    out = tmp_path / "bad-page.json"
    with pytest.raises(ValueError):
        bad.dump(out)
    assert not out.exists()


def test_normal_integers_and_floats_keep_their_semantics() -> None:
    """The finite gate must not turn a number into something else."""
    plan = LayoutPlan.from_dict(_layout_doc())
    assert plan.parts[0].x == 0.0 and isinstance(plan.parts[0].x, float)
    body = _set(_layout_doc(), ("parts", 0, "x"), -12)
    assert LayoutPlan.from_dict(body).parts[0].x == -12.0


# ===================== E-03: a non-UTF-8 file is a typed failure


@pytest.mark.parametrize("cls", [LayoutPlan, PageLayoutPlan], ids=["layout", "page"])
def test_a_non_utf8_file_is_refused_with_the_documents_own_error(tmp_path, cls) -> None:
    path = tmp_path / "bad.json"
    path.write_bytes(b"\xff\xfe{\x00}\x00")
    with pytest.raises((LayoutPlanError, PageLayoutPlanError)) as caught:
        cls.load(path)
    message = str(caught.value)
    assert "not UTF-8" in message, message
    assert str(path) in message, message


@pytest.mark.parametrize("cls", [LayoutPlan, PageLayoutPlan], ids=["layout", "page"])
def test_the_old_refusals_keep_their_wording(tmp_path, cls) -> None:
    """Bad JSON and a directory still say what they said."""
    bad_json = tmp_path / "not.json"
    bad_json.write_text("{ nope", encoding="utf-8")
    with pytest.raises((LayoutPlanError, PageLayoutPlanError)) as caught:
        cls.load(bad_json)
    assert "is not JSON" in str(caught.value), str(caught.value)

    missing = tmp_path / "absent.json"
    with pytest.raises((LayoutPlanError, PageLayoutPlanError)) as caught:
        cls.load(missing)
    assert "cannot be read" in str(caught.value), str(caught.value)


# ===================== E-04 / E-05: version and identity are stated


@pytest.mark.parametrize("cls,doc", [
    (LayoutPlan, _layout_doc), (PageLayoutPlan, _page_doc),
], ids=["layout", "page"])
@pytest.mark.parametrize("version", [True, False, 1.0, "1"])
def test_plan_version_must_be_the_integer_of_this_build(tmp_path, cls, doc, version) -> None:
    body = doc()
    body["planVersion"] = version
    path = _write(tmp_path, "doc.json", body)
    with pytest.raises((LayoutPlanError, PageLayoutPlanError)) as caught:
        cls.load(path)
    assert "planVersion" in str(caught.value), str(caught.value)


@pytest.mark.parametrize("cls,doc", [
    (LayoutPlan, _layout_doc), (PageLayoutPlan, _page_doc),
], ids=["layout", "page"])
def test_plan_version_must_be_stated(tmp_path, cls, doc) -> None:
    body = doc()
    body.pop("planVersion")
    path = _write(tmp_path, "doc.json", body)
    with pytest.raises((LayoutPlanError, PageLayoutPlanError)) as caught:
        cls.load(path)
    assert "planVersion" in str(caught.value), str(caught.value)


@pytest.mark.parametrize("cls,doc", [
    (LayoutPlan, _layout_doc), (PageLayoutPlan, _page_doc),
], ids=["layout", "page"])
def test_a_future_plan_version_is_still_refused_by_name(tmp_path, cls, doc) -> None:
    body = doc()
    body["planVersion"] = 2
    path = _write(tmp_path, "doc.json", body)
    with pytest.raises((LayoutPlanError, PageLayoutPlanError)) as caught:
        cls.load(path)
    assert "recompile" in str(caught.value), str(caught.value)


@pytest.mark.parametrize("cls,doc", [
    (LayoutPlan, _layout_doc), (PageLayoutPlan, _page_doc),
], ids=["layout", "page"])
def test_kind_must_be_stated(tmp_path, cls, doc) -> None:
    body = doc()
    body.pop("kind")
    path = _write(tmp_path, "doc.json", body)
    with pytest.raises((LayoutPlanError, PageLayoutPlanError)) as caught:
        cls.load(path)
    assert "kind" in str(caught.value), str(caught.value)


@pytest.mark.parametrize("cls,doc,wrong", [
    (LayoutPlan, _layout_doc, "boardwise-page-layout-plan"),
    (PageLayoutPlan, _page_doc, "boardwise-layout-plan"),
], ids=["layout", "page"])
def test_a_document_of_the_other_kind_is_refused_by_name(
    tmp_path, cls, doc, wrong
) -> None:
    body = doc()
    body["kind"] = wrong
    path = _write(tmp_path, "doc.json", body)
    with pytest.raises((LayoutPlanError, PageLayoutPlanError)) as caught:
        cls.load(path)
    assert wrong in str(caught.value), str(caught.value)


# ===================== E-06: a real candidate survives load -> dump


def _page_samples() -> list[Path]:
    return sorted(SAMPLES.glob("cand*.page.json"))


def _layout_samples() -> list[Path]:
    return sorted(SAMPLES.glob("cand*.layout.json"))


@pytest.fixture(scope="module")
def samples() -> list[Path]:
    found = _page_samples() + _layout_samples()
    assert len(_page_samples()) >= 4 and len(_layout_samples()) >= 3, (
        "the 054 candidates are the real writer's output; without them this "
        "round-trip has nothing measured to hold"
    )
    return found


def test_a_real_page_candidate_round_trips_byte_for_byte(tmp_path, samples) -> None:
    pages = [path for path in samples if path.name.endswith(".page.json")]
    assert pages
    for source in pages:
        page = PageLayoutPlan.load(source)
        first = tmp_path / f"{source.stem}.rt1.json"
        page.dump(first)
        assert first.read_bytes() == source.read_bytes(), (
            f"{source.name}: dump(load(x)) must be x — the writer computed "
            "`sum(...)` metrics as int 0 and the reader turned them into 0.0"
        )
        second = tmp_path / f"{source.stem}.rt2.json"
        PageLayoutPlan.load(first).dump(second)
        assert second.read_bytes() == first.read_bytes(), source.name


def test_a_real_layout_candidate_keeps_its_bytes_and_its_digests(tmp_path, samples) -> None:
    layouts = [path for path in samples if path.name.endswith(".layout.json")]
    assert layouts
    for source in layouts:
        plan = LayoutPlan.load(source)
        out = tmp_path / f"{source.stem}.rt.json"
        plan.dump(out)
        assert out.read_bytes() == source.read_bytes(), source.name


def test_a_real_page_keeps_its_geometry_and_source(tmp_path, samples) -> None:
    for source in (path for path in samples if path.name.endswith(".page.json")):
        stated = json.loads(source.read_text(encoding="utf-8"))
        page = PageLayoutPlan.load(source)
        assert page.page_geometry_sha256() == stated["geometrySha256"], source.name
        assert page.page_geometry_sha256() == PageLayoutPlan.load(
            _write(tmp_path, "rt.json", page.to_jsonable())
        ).page_geometry_sha256(), source.name
        assert page.plan.source.circuit_sha256 == stated["source"]["circuitSha256"]
        assert page.plan.source.presentation_sha256 == stated["source"]["presentationSha256"]


# ===================== E-07: a point is exactly two components


def test_a_third_point_component_is_refused_by_name(tmp_path) -> None:
    body = _set(_layout_doc(), ("segments", 0, "points"), [[0.0, 0.0, 999.0], [10.0, 0.0]])
    path = _write(tmp_path, "plan.json", body)
    with pytest.raises(LayoutPlanError) as caught:
        LayoutPlan.load(path)
    message = str(caught.value)
    assert "segments[0].points[0]" in message and "exactly" in message, message


def test_a_page_origin_with_three_components_is_refused(tmp_path) -> None:
    body = _set(_page_doc(), ("modules", 0, "origin"), [0.0, 0.0, 5.0])
    path = _write(tmp_path, "page.json", body)
    with pytest.raises(PageLayoutPlanError) as caught:
        PageLayoutPlan.load(path)
    assert "exactly" in str(caught.value), str(caught.value)


def test_a_one_component_point_is_refused(tmp_path) -> None:
    body = _set(_layout_doc(), ("segments", 0, "points"), [[0.0], [10.0, 0.0]])
    path = _write(tmp_path, "plan.json", body)
    with pytest.raises(LayoutPlanError):
        LayoutPlan.load(path)


def test_a_two_component_point_keeps_both_list_and_tuple_forms() -> None:
    assert layoutplan_module._point([1, 2], "p") == (1.0, 2.0)
    assert layoutplan_module._point((1, 2), "p") == (1.0, 2.0)
    assert pagelayoutplan_module._point([1, 2], "p") == (1.0, 2.0)
    assert pagelayoutplan_module._point((1.5, -2.5), "p") == (1.5, -2.5)
