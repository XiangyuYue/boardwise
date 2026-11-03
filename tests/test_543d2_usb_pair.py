"""543D-2: the USB/CC island split that lets the receptacle face its partner.

The batch moves R1/R2 out of `usb_c` into their own `cc` island (agent
partition, no locks, no coordinates). With no CC branches hanging off the
receptacle, the compiler may choose the mirrored/rotated core pose that points
the data pins right; the D+/D- names then sit right of A6/A7 and the CH343's
left of U1.5/U1.6, and the pair faces across the gap. The CC nets are still
named on both islands — the split may not delete a wire or add a name to hide a
break.

These tests pin the split, the CC connectivity, the pose and the landing plan.
The page-level direction assertions live in `test_543d_label_layout.py`; this
file is the batch's own evidence that the partition and the CC channel hold.
"""

from __future__ import annotations

import test_543d_label_layout as d543

from boardwise.engines import drawcompiler as dc
from boardwise.engines import readability


def _pose(profile, label: str):
    return next(item for item in profile.poses if item.label() == label)


def _guard(presentation):
    ctx = d543._context(
        d543.CIRCUIT, presentation, presentation.module("usb_c")
    )
    return ctx, ctx.profile("USB1")


def test_label_side_pose_guard_rejects_the_left_pointing_pose():
    ctx, profile = _guard(d543._presentation())
    assert dc._label_side_pose_ok(ctx, "USB1", profile, _pose(profile, "0")) is False


def test_label_side_pose_guard_accepts_the_mirrored_pose():
    ctx, profile = _guard(d543._presentation())
    assert (
        dc._label_side_pose_ok(ctx, "USB1", profile, _pose(profile, "0+mirror"))
        is True
    )


def test_label_side_pose_guard_is_off_without_native_or_service():
    for presentation in (
        d543._presentation(native=False),
        d543._presentation(service=False),
    ):
        ctx, profile = _guard(presentation)
        assert dc._label_side_pose_ok(
            ctx, "USB1", profile, _pose(profile, "0")
        ) is True, "the guard must not act without both opt-in keys"


def _page():
    page = d543._page()
    usb = next(module for module in page.modules if module.id == "usb_c")
    cc = next(module for module in page.modules if module.id == "cc")
    return page, usb, cc


def test_the_cc_pull_downs_are_their_own_island():
    page, usb, cc = _page()
    assert "R1" not in usb.parts and "R2" not in usb.parts
    assert set(cc.parts) == {"R1", "R2"}
    assert "USB1" in usb.parts
    assert usb.frame[2] < next(
        module.frame[0] for module in page.modules if module.id == "ch343"
    )


def test_cc1_and_cc2_still_connect_receptacle_to_pull_down():
    page, _usb, _cc = _page()
    derived = readability.derive_netlist(page.plan, d543.BOOK)
    expected = {
        "CC1": {"USB1.A5", "R1.1"},
        "CC2": {"USB1.B5", "R2.1"},
    }
    for net_id, members in expected.items():
        group = set(derived.group_of("USB1.A5" if net_id == "CC1" else "USB1.B5"))
        assert group == members, f"{net_id} draws {sorted(group)}"
    # Both pull-downs still return to the spec's single ground.
    gnd = set(derived.group_of("R1.2"))
    assert {"R1.2", "R2.2"} <= gnd
    pin_net = {
        member: net.id for net in d543.CIRCUIT.nets for member in net.members
    }
    for group in derived.groups:
        nets = {pin_net[pin] for pin in group if pin in pin_net}
        assert len(nets) <= 1, f"one node mixes spec nets {sorted(nets)}"


def test_the_receptacle_is_turned_so_its_data_pins_leave_right():
    page, _usb, _cc = _page()
    part = next(item for item in page.plan.parts if item.part_id == "USB1")
    assert part.mirror or part.rotation in (180.0, 90.0, 270.0), (
        "the receptacle is still in its left-pointing pose: the stated load side "
        f"is right but pose is rotation={part.rotation} mirror={part.mirror}"
    )
    for net, member in (("D+", "USB1.A6"), ("D-", "USB1.A7")):
        printed = [
            label for label in d543._labels(page, net, "usb_c")
            if d543._visible(label)
        ]
        assert len(printed) == 1
        box = printed[0].bbox
        centre_x = (box[0] + box[2]) / 2.0
        assert centre_x > d543._pin(page.plan, member)[0], (
            f"{net} box centre {centre_x:g} is not right of {member}"
        )
    # The pair keeps its natural order (D+ above D-).
    d_plus = [
        label for label in d543._labels(page, "D+", "usb_c")
        if d543._visible(label)
    ][0]
    d_minus = [
        label for label in d543._labels(page, "D-", "usb_c")
        if d543._visible(label)
    ][0]
    assert d_plus.y > d_minus.y


def test_the_landing_plan_runs_each_stub_toward_its_partner():
    page, _usb, _cc = _page()
    change = d543._change_plan(page)
    wires = change["wires"]
    moves = {
        move["owner"]["index"]: move for move in change["attributeMoves"]
        if move["owner"]["kind"] == "wire"
    }
    service = {
        ("usb_c", "D+"): d543._pin(page.plan, "USB1.A6"),
        ("usb_c", "D-"): d543._pin(page.plan, "USB1.A7"),
        ("ch343", "D+"): d543._pin(page.plan, "U1.5"),
        ("ch343", "D-"): d543._pin(page.plan, "U1.6"),
    }
    seen = set()
    for label in page.plan.labels:
        key = (d543._module_of(page, label.part_id), label.net)
        if key not in service or not d543._visible(label):
            continue
        index = next(
            index for index, wire in enumerate(wires)
            if wire.get("net") == label.net
            and any(
                abs(point[0] - label.x) < 1e-6
                and abs(point[1] - label.y) < 1e-6
                for point in wire["points"]
            )
        )
        seen.add(key)
        (x1, _y1), (x2, _y2) = wires[index]["points"]
        target_x = moves[index]["to"]["x"]
        pin_x = service[key][0]
        if key[0] == "usb_c":
            assert min(x1, x2) >= pin_x and max(x1, x2) > pin_x
            assert target_x > pin_x
        else:
            assert max(x1, x2) <= pin_x and min(x1, x2) < pin_x
            assert target_x < pin_x
    assert seen == set(service)


def test_every_spec_pin_is_still_on_its_net_node():
    page, _usb, _cc = _page()
    derived = readability.derive_netlist(page.plan, d543.BOOK)
    for net in d543.CIRCUIT.nets:
        group = set(derived.group_of(net.members[0]))
        assert group == set(net.members), (
            f"net {net.id!r} draws {sorted(group)}, spec says {sorted(net.members)}"
        )
