"""543E: the fixed CH343 baseline and three same-topology perturbations.

The baseline is `evidence/543d2/effective.presentation.json` (agent partition,
no locks). Each perturbation is a **circuit/library copy in memory** or a
presentation copy — the existing fixtures are never edited:

1. H1's short value becomes its real long MPN, and the long row must not touch
   any ground conductor, flag or other text;
2. C4 is deleted (spec members and per-pin connectivity follow), and a second
   same-kind decoupling on U1.15/VCC is added; the service interval applies to
   each only because U1.15 is the unique host pin;
3. the CH343 pin pitch is doubled in a copied symbol profile (body and text
   anchors scaled with it), never in the library fixture.

Every variant compiles automatically (`ok=True`), keeps zero hard violations,
per-pin connectivity, the C3/C4 30-unit service runs where retained, and the
D+/D- direction. The added-decoupling variant is expected to **fail its own
"distinct origins" assertion**: the compiler lays C4 and C5 at the same origin
and the gate reports zero violations — a named production defect, recorded as a
strict xfail rather than hidden or worked around.

The negative controls at the end prove the checks themselves detect breakage.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import test_543d_label_layout as d543

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import layoutroles
from boardwise.engines import pagecompiler as pc
from boardwise.engines import readability

ROOT = Path(__file__).resolve().parents[1]
RAW_CIRCUIT = json.loads(
    (ROOT / "blocklib/specs/ch343_uart_534a.circuit.json").read_text(
        encoding="utf-8"
    )
)
RAW_LIBRARY = json.loads(
    (ROOT / "blocklib/specs/ch343_uart_v4.library.json").read_text(
        encoding="utf-8"
    )
)
BASE_PRESENTATION = json.loads(
    (ROOT / "evidence/543d2/effective.presentation.json").read_text(
        encoding="utf-8"
    )
)
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)
LONG_H1 = "PZ254V-22-10-A60-3000"


def _book(raw: dict | None = None) -> dict[str, SymbolProfile]:
    data = raw or RAW_LIBRARY
    return {
        item["symbolRef"]: SymbolProfile.from_dict(item)
        for item in data["profiles"]
    }


def _presentation(parts: list[str] | None = None) -> PresentationSpec:
    payload = copy.deepcopy(BASE_PRESENTATION)
    if parts is not None:
        for module in payload["modules"]:
            if module["id"] == "ch343":
                module["parts"] = parts
        declared = {part for module in payload["modules"] for part in module["parts"]}
        payload["partTexts"] = {
            key: value for key, value in payload["partTexts"].items()
            if key in declared
        }
    spec = PresentationSpec.from_dict(payload)
    assert spec.user_locks == [], "543E variants must not carry user locks"
    return spec


def _circuit(mutate=None) -> CircuitSpec:
    raw = copy.deepcopy(RAW_CIRCUIT)
    if mutate is not None:
        mutate(raw)
    return CircuitSpec.from_dict(raw)


def _compile(circuit: CircuitSpec, presentation: PresentationSpec, book):
    return pc.compile_page(
        circuit, presentation, book, pc.PageCompileBudget(page_box=PAGE_BOX)
    )


def _first_page(result):
    assert result.ok, result.render_failures()
    assert result.pages
    return result.pages[0]


def _pin(plan, member: str, book) -> tuple[float, float]:
    part_id, _, token = member.partition(".")
    part = next(item for item in plan.parts if item.part_id == part_id)
    profile = book[part.symbol_ref]
    pin = next(item for item in profile.pins if str(item.number) == token)
    return transform_point(
        pin.tip[0], pin.tip[1], rotation=part.rotation, mirror=part.mirror,
        ox=part.x, oy=part.y,
    )


def _overlap(a, b) -> bool:
    return (
        min(a[2], b[2]) - max(a[0], b[0]) > 1e-6
        and min(a[3], b[3]) - max(a[1], b[1]) > 1e-6
    )


def _run_hits_box(points, box) -> bool:
    for start, stop in zip(points, points[1:]):
        if min(start[0], stop[0]) < box[2] and max(start[0], stop[0]) > box[0]:
            if min(start[1], stop[1]) < box[3] and max(start[1], stop[1]) > box[1]:
                return True
    return False


def _service(page, cap: str, host_pin: str, net: str, book) -> dict:
    plan = page.plan
    cap_point = _pin(plan, f"{cap}.1", book)
    host_point = _pin(plan, f"U1.{host_pin}", book)
    straight = any(
        segment.net == net and len(segment.points) == 2
        and {tuple(segment.points[0]), tuple(segment.points[1])}
        == {cap_point, host_point}
        for segment in plan.segments
    )
    return {
        "manhattan": abs(cap_point[0] - host_point[0])
        + abs(cap_point[1] - host_point[1]),
        "same_row": cap_point[1] == host_point[1],
        "straight": straight,
        "cap_point": cap_point,
        "host_point": host_point,
    }


def _assert_clean(page, circuit, book, caps: tuple[str, ...]) -> None:
    """The common completion conditions for every perturbation."""
    plan = page.plan
    assert page.verdict == "pass", plan.evidence.hard_violations
    assert plan.evidence.hard_violations == []
    assert page.page_evidence.hard_violations == []

    for cap in caps:
        host = "4" if cap == "C3" else "15"
        net = "V3" if cap == "C3" else "VCC"
        service = _service(page, cap, host, net, book)
        assert service["manhattan"] == 30.0, (cap, service)
        assert service["same_row"] and service["straight"], (cap, service)

    # D+/D- keep the direction the 543D-2 split bought: right of the USB
    # service pin, left of the CH343 pin. 543I contract upgrade: the receptacle's
    # two reversible runs **each** print their own name (P32 was withdrawn for
    # hiding one), so the USB side shows two rows and both leave the pin toward
    # the stated side; the natural order holds on the pins' own row and at the
    # CH343 end (the connector's B row is mirrored by construction).
    for net, usb_pin, ch_pin in (
        ("D+", "USB1.A6", "U1.5"), ("D-", "USB1.A7", "U1.6"),
    ):
        printed = [
            label for label in plan.labels
            if label.net == net and d543._visible(label)
        ]
        usb = [
            label for label in printed
            if label.part_id == "USB1"
        ]
        ch = [label for label in printed if label.part_id == "U1"]
        assert len(usb) == 2 and len(ch) == 1, (net, len(usb), len(ch))
        for label in usb:
            centre = (label.bbox[0] + label.bbox[2]) / 2.0
            assert centre > _pin(plan, usb_pin, book)[0], (net, label.bbox)
        ch_centre = (ch[0].bbox[0] + ch[0].bbox[2]) / 2.0
        assert ch_centre < _pin(plan, ch_pin, book)[0], (net, ch[0].bbox)
    printed_p = [l for l in plan.labels if l.net == "D+" and d543._visible(l)]
    printed_m = [l for l in plan.labels if l.net == "D-" and d543._visible(l)]
    a6 = _pin(plan, "USB1.A6", book)
    a7 = _pin(plan, "USB1.A7", book)
    plus = next(l for l in printed_p if abs(l.y - a6[1]) <= 1e-6)
    minus = next(l for l in printed_m if abs(l.y - a7[1]) <= 1e-6)
    assert plus.y > minus.y, "usb_c: the A-row pair is not D+ above D-"
    ch_plus = next(
        l for l in printed_p if d543._module_of(page, l.part_id) == "ch343"
    )
    ch_minus = next(
        l for l in printed_m if d543._module_of(page, l.part_id) == "ch343"
    )
    assert ch_plus.y > ch_minus.y, "ch343"

    # UART names stay horizontal and disjoint.
    uart = [label for label in plan.labels if label.net in d543.UART]
    for label in uart:
        assert label.rotation == 0.0
        assert (label.bbox[2] - label.bbox[0]) >= (label.bbox[3] - label.bbox[1])
    for index, left in enumerate(uart):
        for right in uart[index + 1:]:
            assert not _overlap(left.bbox, right.bbox), (left.net, right.net)

    # Every spec pin is on its own net's node; no node mixes two spec nets.
    # The drawing may also carry the circuit's declared no-connect pins, but
    # each must stay a singleton node (nothing may be wired onto it).
    derived = readability.derive_netlist(plan, book)
    pin_net = {m: n.id for n in circuit.nets for m in n.members}
    for net in circuit.nets:
        assert set(derived.group_of(net.members[0])) == set(net.members), net.id
    for group in derived.groups:
        nets = {pin_net[pin] for pin in group if pin in pin_net}
        assert len(nets) <= 1, (sorted(nets), group)
    drawn = {pin for group in derived.groups for pin in group}
    no_connect = {item.pin for item in circuit.nc}
    assert set(pin_net) <= drawn
    assert drawn - set(pin_net) == no_connect, sorted(drawn - set(pin_net))
    for pin in no_connect:
        assert len(derived.group_of(pin)) == 1, pin


# --------------------------------------------------------------- baseline


def test_baseline_recompiles_to_the_543d2_digest():
    result = _compile(
        _circuit(), _presentation(), _book()
    )
    page = _first_page(result)
    # 543I contract upgrade: the baseline still recompiles byte for byte, but the
    # explicit path now prints a name on every non-continuous run (P32 was
    # withdrawn for the opposite rule), so the digest moved from the value
    # `evidence/543d2/compile/result.json` recorded (84694e2d…) to this one.
    # 543I-6: the seat question is now asked **strictly** on a page that states
    # `localLabelObligations` (`_flag_pins`), because a local-label carrier is a
    # conductor the page draws *after* the flags — the loose question was letting
    # `+5V` stand on `D+`'s carrier, which is what had made the mirrored
    # receptacle pose illegal and the page fall back to `rotation=180` (D+ below
    # D-). With the carrier reserved the mirror pose is drawn again, and the page
    # digest is this one. The straight-stub claim this file makes is unchanged.
    # 543I-6I: the printed row's anchor and the ATTR move are now **one**
    # convention (`textmetrics.host_row_box`'s own: the move's X/Y is the row's
    # lower-left), so 543I-4A's ink box moved from the reserve's centre to its
    # lower-left corner and one supply run took the room that changed
    # (`tests/test_543i_power_text_clearance.py` measures the same rows and is
    # green). The page digest moved with that obstacle; the straight-stub claim
    # this file makes is unchanged.
    # 543I-6K: the candidate that printed a local name **centred on its own
    # carrier end** is now refused (`_riding_label_failure` — the "骑脚" row), so
    # the legal **mirrored** candidate this compiler already had wins: the page is
    # back to the natural order the mirror pose buys (D+ above D−), and the digest
    # is that candidate's. The two statements above still hold — the strict seat
    # question on `localLabelObligations` pages and the lower-left anchor shared
    # by the ATTR move and 543I-4A's ink are what made this page legal at all.
    # 543I (LED) contract upgrade: this baseline states `directWiringObligations`
    # for `LED_A`, so the tap stub and its printed name are gone and the
    # indicator island's frame narrowed; the page digest moved with that
    # statement. Everything this file perturbs — and the digest it is compared
    # against — is otherwise unchanged.
    # 543L/543M contract upgrade: this baseline states `stub: straight` and the
    # mirrored `D+`/`D-` pair, so the joint length is this document's own
    # statement — `B6`/`B7` are both drawn at 60 and the page digest moved with
    # it. Verified, not assumed: the same document with `stub: auto` keeps the
    # pre-543L page (`tests/test_543l_paired_carriers.py`'s negative control) and
    # `tests/test_543f2_changeplan_bounds.py` pins that pre-fix digest.
    expected = "2ec6b700d997839830148b3c53a9abe3fe7debebed4986ce0d05cd67cc5ca095"
    assert page.page_geometry_sha256() == expected
    _assert_clean(page, _circuit(), _book(), ("C3", "C4"))


# ------------------------------------------------------ 1. long header text


def test_long_h1_value_does_not_touch_gnd_or_other_text():
    def mutate(raw):
        for part in raw["parts"]:
            if part["id"] == "H1":
                part["value"] = LONG_H1

    circuit = _circuit(mutate)
    book = _book()
    page = _first_page(_compile(circuit, _presentation(), book))
    _assert_clean(page, circuit, book, ("C3", "C4"))

    rows = [
        text for text in page.plan.texts
        if text.part_id == "H1" and text.kind == "value"
    ]
    assert len(rows) == 1
    assert rows[0].text == LONG_H1
    box = rows[0].bbox
    assert (box[2] - box[0]) > 100.0, box

    gnd_hits = [
        points for segment in page.plan.segments if segment.net == "GND"
        for points in [segment.points] if _run_hits_box(points, box)
    ]
    assert gnd_hits == []

    others = [
        ("text", item.text, item.bbox) for item in page.plan.texts
        if item is not rows[0]
    ]
    others += [("label", item.net, item.bbox) for item in page.plan.labels]
    for symbol in page.plan.power_symbols:
        profile = book.get(symbol.symbol_ref)
        if profile is not None:
            others.append((
                "flag", symbol.net,
                dc._flag_box(
                    profile, symbol.rotation, (symbol.x, symbol.y),
                    symbol.net, margin=0.0,
                ),
            ))
    collisions = [
        (kind, name) for kind, name, other in others if _overlap(box, other)
    ]
    assert collisions == []


# --------------------------------------------- 2. delete / add decoupling


def test_deleting_c4_updates_spec_members_and_keeps_the_rest():
    def mutate(raw):
        raw["parts"] = [part for part in raw["parts"] if part["id"] != "C4"]
        for net in raw["nets"]:
            net["members"] = [
                member for member in net["members"]
                if not member.startswith("C4.")
            ]

    circuit = _circuit(mutate)
    presentation = _presentation(["U1", "C3"])
    book = _book()
    page = _first_page(_compile(circuit, presentation, book))
    _assert_clean(page, circuit, book, ("C3",))

    assert "C4" not in {part.id for part in circuit.parts}
    assert not any(
        member.startswith("C4.")
        for net in circuit.nets for member in net.members
    )
    assert set(presentation.module("ch343").parts) == {"U1", "C3"}


def test_adding_a_second_vcc_decoupling_is_refused_when_the_seat_is_blocked():
    def mutate(raw):
        raw["parts"].append({
            "id": "C5", "symbolRef": "C0603-100nF-C1590", "value": "100nF",
            "lcsc": "C1590", "mpn": "CL10B104KA8NNNC",
            "provenance": "engineer_confirmed",
        })
        for net in raw["nets"]:
            if net["id"] == "VCC":
                net["members"].append("C5.1")
            if net["id"] == "GND":
                net["members"].append("C5.2")

    circuit = _circuit(mutate)
    presentation = _presentation(["U1", "C3", "C4", "C5"])
    vcc = next(net for net in circuit.nets if net.id == "VCC")
    gnd = next(net for net in circuit.nets if net.id == "GND")
    assert "C5.1" in vcc.members and "C5.2" in gnd.members
    assert set(presentation.module("ch343").parts) == {
        "U1", "C3", "C4", "C5"
    }

    # U1.15's neighbours sit 20 units away on the same side, so a vertical
    # 30-unit run crosses another pin; there is no legal orthogonal seat.
    result = _compile(circuit, presentation, _book())
    assert not result.ok
    assert result.pages == []
    failure = result.failures[0]
    assert failure.category == "layout-unsat"
    assert "C5" in failure.detail and "U1.15" in failure.detail
    assert "first shunt's origin" in failure.detail


def test_only_a_unique_host_pin_gets_the_service_interval():
    def mutate(raw):
        raw["parts"].append({
            "id": "C5", "symbolRef": "C0603-100nF-C1590", "value": "100nF",
            "lcsc": "C1590", "mpn": "CL10B104KA8NNNC",
            "provenance": "engineer_confirmed",
        })
        for net in raw["nets"]:
            if net["id"] == "VCC":
                net["members"].append("C5.1")
            if net["id"] == "GND":
                net["members"].append("C5.2")

    circuit = _circuit(mutate)
    presentation = _presentation(["U1", "C3", "C4", "C5"])
    analysis = layoutroles.analyze_decoupling(circuit, presentation)
    for cap in ("C3", "C4", "C5"):
        assert analysis.for_part(cap).has_unique_host_pin, cap
    # The USB pair's `+5V` host has several equivalent contacts, so the stated
    # interval is not allowed to pick one of them.
    for cap in ("C1", "C2"):
        assert not analysis.for_part(cap).has_unique_host_pin, cap


def test_duplicate_decoupling_is_refused_instead_of_sharing_an_origin():
    def mutate(raw):
        raw["parts"].append({
            "id": "C5", "symbolRef": "C0603-100nF-C1590", "value": "100nF",
            "lcsc": "C1590", "mpn": "CL10B104KA8NNNC",
            "provenance": "engineer_confirmed",
        })
        for net in raw["nets"]:
            if net["id"] == "VCC":
                net["members"].append("C5.1")
            if net["id"] == "GND":
                net["members"].append("C5.2")

    circuit = _circuit(mutate)
    result = _compile(
        circuit, _presentation(["U1", "C3", "C4", "C5"]), _book()
    )
    assert not result.ok, (
        "a duplicate service shunt must be refused, not drawn on the first "
        "shunt's origin"
    )
    assert result.pages == []
    assert "layout-unsat" in result.categories()


# ----------------------------------------------------- 3. CH343 pin pitch


def _pitch_library(scale: float) -> dict:
    raw = copy.deepcopy(RAW_LIBRARY)
    for item in raw["profiles"]:
        if item["symbolRef"] != "CH343G-C2844153":
            continue
        for pin in item["pins"]:
            pin["tip"] = [pin["tip"][0], pin["tip"][1] * scale]
        body = item["body"]
        item["body"] = [
            body[0], body[1] * scale, body[2], body[3] * scale,
        ]
        for text in item["texts"]:
            text["y"] = text["y"] * scale
    return raw


def test_ch343_pin_pitch_change_keeps_labels_flat_and_page_clean():
    book = _book(_pitch_library(2.0))
    circuit = _circuit()
    presentation = _presentation()
    page = _first_page(_compile(circuit, presentation, book))
    _assert_clean(page, circuit, book, ("C3", "C4"))

    profile = book["CH343G-C2844153"]
    first = next(pin for pin in profile.pins if str(pin.number) == "1")
    second = next(pin for pin in profile.pins if str(pin.number) == "2")
    assert abs(first.tip[1] - second.tip[1]) == 20.0
    body = profile.body
    assert all(
        body[1] <= pin.tip[1] <= body[3] for pin in profile.pins
    )


# ------------------------------------------------------ negative controls


def test_negative_control_a_text_over_a_ground_run_is_detected():
    box = (10.0, 10.0, 20.0, 20.0)
    assert _run_hits_box([(0.0, 15.0), (30.0, 15.0)], box) is True
    assert _run_hits_box([(0.0, 40.0), (30.0, 40.0)], box) is False


def test_negative_control_a_spec_vs_drawing_mismatch_is_detected():
    # The drawing is the baseline, but the spec claims C4.1 is on GND instead
    # of VCC. The derived netlist then mixes VCC and GND pins; the checker must
    # name it (this is the same predicate `_assert_clean` runs).
    raw = copy.deepcopy(RAW_CIRCUIT)
    for net in raw["nets"]:
        if net["id"] == "VCC":
            net["members"] = [m for m in net["members"] if m != "C4.1"]
        if net["id"] == "GND":
            net["members"].append("C4.1")
    broken = CircuitSpec.from_dict(raw)
    page = _first_page(_compile(_circuit(), _presentation(), _book()))
    derived = readability.derive_netlist(page.plan, _book())
    pin_net = {m: n.id for n in broken.nets for m in n.members}
    mixed = [
        group for group in derived.groups
        if len({pin_net[p] for p in group if p in pin_net}) > 1
    ]
    assert mixed, "a spec/drawing net mismatch must be detected"
