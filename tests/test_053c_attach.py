"""053c：`attach` —— 把一个模块贴到宿主模块的指定一侧。

本文件只验两件事，各自独立：

1. **schema**（`core/presentationspec.py`）：`attach` 是可选键，`to` / `side` /
   `gap` 三个字段有默认值，默认值不写出（旧文档字节不变），自指、链式、同一宿主
   被贴两次、未知宿主、非法 side / gap 都在解析期拒绝，消息点名模块 id 与键名；
2. **摆放**（`engines/pagecompiler.py`）：被贴模块不进网格、而是按宿主已放置的
   frame 定位；它仍是独立模块（`page.modules` 里仍在），图形与 frame 不被合并，
   两个模块之间的网仍然只是跨模块旗标/标签，页面不新增一条连接线。

规则（`side` 的四种方向、`gap` 是下限、页面自身 module gap 仍是地板）在
`_attach_shift` 的 docstring 里；这里断言的是它的可观测结果，不断言具体坐标。
"""

from __future__ import annotations

import json

import pytest

import test_056_pagecompiler as p056

from boardwise.core.presentationspec import (
    ATTACH_GAP_DEFAULT,
    ATTACH_SIDE_DEFAULT,
    ModuleAttach,
    PresentationSpec,
    PresentationSpecError,
)
from boardwise.engines import pagecompiler as pc

#: The same A4-landscape sheet the 056 scenes are compiled onto.
PAGE = pc.PageCompileBudget(page_box=(0.0, 0.0, 1169.0, 826.0))


# ------------------------------------------------------------------ schema


def spec_payload(*modules: dict) -> dict:
    """A minimal document: the closed top level reads everything else by default."""
    return {"modules": list(modules), "flow": []}


def module_payload(module_id: str, parts: list[str], **extra) -> dict:
    return {"id": module_id, "parts": list(parts), "role": "group", **extra}


def assert_refused(payload: dict, *fragments: str) -> None:
    with pytest.raises(PresentationSpecError) as caught:
        PresentationSpec.from_dict(payload)
    message = str(caught.value)
    for fragment in fragments:
        assert fragment in message, (
            f"{fragment!r} is not in the refusal: {message}"
        )


def test_attach_round_trips_byte_stable():
    payload = spec_payload(
        module_payload("host", ["U1"]),
        module_payload("caps", ["C1", "C2"], attach={"to": "host"}),
    )
    first = PresentationSpec.from_dict(payload)
    written = json.dumps(first.to_jsonable(), ensure_ascii=False, indent=2)
    second = PresentationSpec.from_dict(json.loads(written))
    assert json.dumps(second.to_jsonable(), ensure_ascii=False, indent=2) == written
    assert PresentationSpec.from_dict(second.to_jsonable()) == second
    attach = next(m for m in second.modules if m.id == "caps").attach
    assert attach == ModuleAttach(to="host")
    assert attach.side == ATTACH_SIDE_DEFAULT == "bottom"
    assert attach.gap == ATTACH_GAP_DEFAULT == 10.0


def test_an_explicit_side_and_gap_round_trip_byte_stable():
    payload = spec_payload(
        module_payload("host", ["U1"]),
        module_payload(
            "caps", ["C1"], attach={"to": "host", "side": "right", "gap": 25},
        ),
    )
    first = PresentationSpec.from_dict(payload)
    written = json.dumps(first.to_jsonable(), ensure_ascii=False, indent=2)
    second = PresentationSpec.from_dict(json.loads(written))
    assert json.dumps(second.to_jsonable(), ensure_ascii=False, indent=2) == written
    attach = next(m for m in second.modules if m.id == "caps").attach
    assert (attach.side, attach.gap) == ("right", 25.0)


def test_the_defaults_are_not_written_and_an_absent_attach_writes_nothing():
    payload = spec_payload(
        module_payload("host", ["U1"]),
        module_payload("other", ["R1"]),
        module_payload("plain", ["C1"]),
        module_payload(
            "defaults", ["C2"], attach={"to": "host"},
        ),
        module_payload(
            "explicit", ["C3"],
            attach={"to": "other", "side": "top", "gap": 30},
        ),
    )
    written = {
        module["id"]: module
        for module in PresentationSpec.from_dict(payload).to_jsonable()["modules"]
    }
    assert "attach" not in written["host"]
    assert "attach" not in written["plain"]
    assert written["defaults"]["attach"] == {"to": "host"}
    assert written["explicit"]["attach"] == {
        "to": "other", "side": "top", "gap": 30.0,
    }


@pytest.mark.parametrize(
    ("attach", "fragments"),
    [
        ({"to": "nowhere"}, ("caps", "attach.to", "nowhere")),
        ({"to": "caps"}, ("caps", "attach.to", "itself")),
        ({"to": "host", "side": "middle"},
         ("caps", "attach.side", "middle")),
        ({"to": "host", "gap": 0}, ("caps", "attach.gap")),
        ({"to": "host", "gap": -5}, ("caps", "attach.gap")),
        ({"to": "host", "gap": "ten"}, ("attach.gap",)),
        ({"side": "bottom"}, ("attach.to", "required")),
        ({"to": "host", "colour": "red"}, ("unknown key", "colour")),
        ("host", ("attach", "JSON object")),
    ],
)
def test_a_bad_attach_is_refused_at_parse_time(attach, fragments):
    payload = spec_payload(
        module_payload("host", ["U1"]),
        module_payload("caps", ["C1"], attach=attach),
    )
    assert_refused(payload, *fragments)


def test_a_chain_of_two_attaches_is_refused():
    payload = spec_payload(
        module_payload("a", ["U1"]),
        module_payload("b", ["C1"], attach={"to": "a"}),
        module_payload("c", ["C2"], attach={"to": "b"}),
    )
    assert_refused(payload, "c", "attach.to", "one level")


def test_one_host_carries_at_most_one_attached_module():
    payload = spec_payload(
        module_payload("host", ["U1"]),
        module_payload("left", ["C1"], attach={"to": "host", "side": "left"}),
        module_payload("right", ["C2"], attach={"to": "host", "side": "right"}),
    )
    assert_refused(payload, "attach.to", "host", "at most one")


def test_an_old_document_without_attach_keeps_its_bytes():
    payload = spec_payload(
        module_payload("host", ["U1"]),
        module_payload("caps", ["C1", "C2"]),
    )
    spec = PresentationSpec.from_dict(payload)
    text = json.dumps(spec.to_jsonable(), ensure_ascii=False, sort_keys=True)
    again = PresentationSpec.from_dict(
        json.loads(json.dumps(spec.to_jsonable(), ensure_ascii=False))
    )
    assert json.dumps(again.to_jsonable(), ensure_ascii=False, sort_keys=True) == text
    assert all(
        "attach" not in module
        for module in spec.to_jsonable()["modules"]
    )


# -------------------------------------------------------------- pagecompile


def plain_chain() -> PresentationSpec:
    return p056.chain_spec()


def attached_chain(
    attach: dict | None = None, host: str = "rc", module_id: str = "div"
) -> PresentationSpec:
    """The 056 chain, with one module attached to another of the same document.

    Built by injecting the key into the chain's own canonical JSON: the document
    parsed here is the one the serializer writes, so the parser, the compiler and
    the round-trip tests all read the same shape.
    """
    payload = p056.chain_spec().to_jsonable()
    statement = {"to": host} if attach is None else dict(attach)
    for module in payload["modules"]:
        if module["id"] == module_id:
            module["attach"] = statement
    return PresentationSpec.from_dict(payload)


def compile_chain(presentation: PresentationSpec):
    return pc.compile_page(
        p056.chain_circuit(), presentation, p056.library(), PAGE,
    )


def page_modules(page) -> dict:
    return {module.id: module for module in page.modules}


def page_parts(page) -> dict:
    return {part.part_id: part for part in page.plan.parts}


def inside(point: tuple[float, float], frame) -> bool:
    return (
        frame[0] - 1e-6 <= point[0] <= frame[2] + 1e-6
        and frame[1] - 1e-6 <= point[1] <= frame[3] + 1e-6
    )


def segments_between(page, left: str, right: str) -> list:
    """Segments with one end in each of two modules' frames — the drawn crossing."""
    frames = {module.id: module.frame for module in page.modules}
    out = []
    for segment in page.plan.segments:
        ends = (inside(segment.points[0], frames[left]),
                inside(segment.points[-1], frames[left]))
        others = (inside(segment.points[0], frames[right]),
                  inside(segment.points[-1], frames[right]))
        if any(ends) and any(others):
            out.append(segment)
    return out


def test_attach_compiles_and_keeps_both_modules_on_the_page():
    attached = attached_chain()
    result = compile_chain(attached)
    assert result.pages, [failure.detail for failure in result.failures]
    page = result.pages[0]
    assert page.verdict == "pass"
    ids = [module.id for module in page.modules]
    assert ids == ["pwr", "rc", "div"], ids
    assert any(
        "module div is attached to rc on its bottom side" in note
        for note in page.notes
    ), page.notes


def test_the_attached_module_keeps_its_own_drawing_at_the_placement_offset():
    plain = compile_chain(plain_chain())
    attached = compile_chain(attached_chain())
    assert plain.pages and attached.pages
    plain_page, attached_page = plain.pages[0], attached.pages[0]
    plain_div = page_modules(plain_page)["div"]
    attached_div = page_modules(attached_page)["div"]
    plain_parts, attached_parts = page_parts(plain_page), page_parts(attached_page)

    # The drawing is the module's own: the same parts around the origin, and the
    # same frame size — attach translates the module, it never merges it.
    for part_id in ("R2", "R3"):
        local = (
            plain_parts[part_id].x - plain_div.origin[0],
            plain_parts[part_id].y - plain_div.origin[1],
        )
        assert attached_parts[part_id].x == pytest.approx(
            attached_div.origin[0] + local[0], abs=1e-6
        )
        assert attached_parts[part_id].y == pytest.approx(
            attached_div.origin[1] + local[1], abs=1e-6
        )
    assert attached_div.frame[2] - attached_div.frame[0] == pytest.approx(
        plain_div.frame[2] - plain_div.frame[0], abs=1e-6
    )
    assert attached_div.frame[3] - attached_div.frame[1] == pytest.approx(
        plain_div.frame[3] - plain_div.frame[1], abs=1e-6
    )


def test_the_attached_module_sits_on_the_named_side_of_its_host():
    page = compile_chain(attached_chain({"to": "rc", "side": "bottom", "gap": 10})).pages[0]
    modules = page_modules(page)
    host, attached = modules["rc"], modules["div"]
    # Below the host (y grows upwards), and no closer than the page's own module
    # gap: the document's 10 is a lower bound, the page's floor is the contract.
    separation = host.frame[1] - attached.frame[3]
    assert separation >= PAGE.module_gap - 1e-6, separation
    assert attached.frame[3] < host.frame[3]
    # Centred on the host's horizontal span (within one lattice step).
    centre = (host.frame[0] + host.frame[2]) / 2
    placed = (attached.frame[0] + attached.frame[2]) / 2
    assert abs(centre - placed) <= PAGE.grid + 1e-6
    # The host's frame is its own drawing, not a union with the attached one.
    plain_host = page_modules(compile_chain(plain_chain()).pages[0])["rc"]
    assert host.frame[2] - host.frame[0] == pytest.approx(
        plain_host.frame[2] - plain_host.frame[0], abs=1e-6
    )
    assert host.frame[3] - host.frame[1] == pytest.approx(
        plain_host.frame[3] - plain_host.frame[1], abs=1e-6
    )


@pytest.mark.parametrize("side", ["bottom", "top", "left", "right"])
def test_every_side_places_the_module_on_that_side(side):
    page = compile_chain(attached_chain({"to": "rc", "side": side})).pages[0]
    modules = page_modules(page)
    host, attached = modules["rc"], modules["div"]
    if side == "bottom":
        assert attached.frame[3] <= host.frame[1] - PAGE.module_gap + 1e-6
    elif side == "top":
        assert attached.frame[1] >= host.frame[3] + PAGE.module_gap - 1e-6
    elif side == "left":
        assert attached.frame[2] <= host.frame[0] - PAGE.module_gap + 1e-6
    else:
        assert attached.frame[0] >= host.frame[2] + PAGE.module_gap - 1e-6


def test_attach_adds_no_wire_between_the_two_modules():
    plain = compile_chain(plain_chain())
    attached = compile_chain(attached_chain())
    plain_page, attached_page = plain.pages[0], attached.pages[0]
    # Same drawing, one module translated: the wire count cannot grow.
    assert len(attached_page.plan.segments) == len(plain_page.plan.segments)
    assert segments_between(attached_page, "rc", "div") == []
    # And the nets that span the two are still stated by a name/flag at each end.
    shared = {
        port.net
        for module in attached_page.modules
        if module.id in ("rc", "div")
        for port in module.ports
    }
    assert shared, "the two modules must still share a net to test the statement"
    assert all(
        port.kind != "wire"
        for module in attached_page.modules
        for port in module.ports
    )


def test_a_failing_attached_module_is_still_reported_by_its_own_name():
    payload = p056.chain_spec().to_jsonable()
    for module in payload["modules"]:
        if module["id"] == "div":
            module["parts"].append("C9")  # a part the circuit does not declare
            module["attach"] = {"to": "rc"}
    result = compile_chain(PresentationSpec.from_dict(payload))
    assert not result.pages
    assert any(
        "modules[div]" in (failure.subject or "") for failure in result.failures
    ), [failure.subject for failure in result.failures]
