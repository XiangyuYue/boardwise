"""610: add-component identity — resolve a designator the way the host does, allocate a free one.

Two holes from `outputs/hole570/d/REPRO.md`:

* **D6** `primitive_id_of` returned the first page part with the exact designator,
  while `core.changeplan.resolve_on_page` (the connector's own rule) calls two
  parts sharing a designator ambiguous and folds case. The reader that returns an
  id must give the same verdict as the reader the host is asked through — a
  duplicate read as ``"p1"`` is a later read/write aimed at a part chosen by
  position.
* **D7** `allocate_designator(["C11"], "C1")` returned ``"C11"``: the pool entry's
  parsed prefix is ``"C"``, the requested prefix was ``"C1"``, so the used set
  stayed empty and the allocator handed back a name the page already carries.

The controls in this file are the behaviour that must **not** change: a unique
designator still resolves, ``OtherProperty.Designator`` still resolves,
``state.PrimitiveId`` is still the fallback for a dump whose id is not top-level,
and a legal ``C``/``c`` prefix still gets the lowest free number in the caller's
own case.
"""

from __future__ import annotations

import pytest

from boardwise.engines.addcomponent import allocate_designator, primitive_id_of


def _page(*entries):
    return {"components": list(entries)}


def _part(primitive_id, designator, **state):
    body = {"Designator": designator}
    body.update(state)
    entry = {"state": body}
    if primitive_id is not None:
        entry["primitiveId"] = primitive_id
    return entry


# --------------------------------------------------------------------------
# D6: primitive_id_of must answer like resolve_on_page, not by first match
# --------------------------------------------------------------------------


def test_duplicate_designator_is_not_resolved_by_position():
    """Two R1s: the answer is "cannot tell", never p1 and never p2."""
    geometry = _page(
        _part("p1", "R1", X=0, Y=0),
        _part("p2", "R1", X=100, Y=0),
    )
    resolved = primitive_id_of(geometry, "R1")
    assert resolved == ""
    assert resolved not in {"p1", "p2"}


def test_duplicate_designator_mixed_id_channels_is_still_ambiguous():
    """One R1 carries a top-level id, the other only a state id — still two."""
    geometry = _page(
        _part("p1", "R1"),
        _part(None, "R1", PrimitiveId="sp-2"),
    )
    assert primitive_id_of(geometry, "R1") == ""
    assert primitive_id_of(geometry, "r1") == ""


def test_duplicate_designator_differing_only_in_case_is_still_ambiguous():
    geometry = _page(_part("p1", "R1"), _part("p2", "r1"))
    assert primitive_id_of(geometry, "R1") == ""


def test_lowercase_designator_resolves_like_the_host():
    geometry = _page(_part("p1", "R1"))
    assert primitive_id_of(geometry, "r1") == "p1"
    assert primitive_id_of(geometry, " R1 ") == "p1"


def test_other_property_designator_resolves():
    geometry = _page(
        {"primitiveId": "p7", "state": {"OtherProperty": {"Designator": "U3"}}}
    )
    assert primitive_id_of(geometry, "u3") == "p7"


def test_unique_designator_control():
    geometry = _page(
        _part("p1", "R1"),
        _part("p2", "C1"),
    )
    assert primitive_id_of(geometry, "C1") == "p2"
    assert primitive_id_of(geometry, "R1") == "p1"
    assert primitive_id_of(geometry, "R9") == ""


def test_state_primitive_id_fallback_control():
    """609's read-back can report the id only in state; that must still work."""
    geometry = _page(_part(None, "C4", PrimitiveId="sp-4"))
    assert primitive_id_of(geometry, "C4") == "sp-4"
    assert primitive_id_of(geometry, "c4") == "sp-4"


def test_non_geometry_input_stays_empty():
    assert primitive_id_of(None, "R1") == ""
    assert primitive_id_of({}, "R1") == ""
    assert primitive_id_of(_page(_part("p1", "R1")), "") == ""


# --------------------------------------------------------------------------
# D7: allocate_designator must never hand back a name the pool already has
# --------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["C1", "R12", "1", "", " ", "C 1", "C_1", "C-1", "C1a"])
def test_non_letter_prefix_is_a_named_refusal(prefix):
    with pytest.raises(ValueError) as caught:
        allocate_designator(["C11"], prefix)
    message = str(caught.value)
    assert "prefix" in message
    assert "letters" in message


def test_digit_suffixed_prefix_never_returns_a_pool_name():
    names = ["C11"]
    with pytest.raises(ValueError):
        allocate_designator(names, "C1")


def test_allocator_never_returns_a_name_already_in_the_pool():
    pools = [
        (["C1", "C2", "C4"], "C", "C3"),
        (["c1", "C2"], "C", "C3"),
        (["R1"], "c", "c1"),
        (["C12", "c13"], "c", "c1"),
        ([], "C", "C1"),
        (["U1", "TP1", "C1?"], "C", "C1"),
    ]
    for names, prefix, expected in pools:
        allocated = allocate_designator(names, prefix)
        assert allocated == expected
        assert allocated.casefold() not in {name.casefold() for name in names}


def test_legal_prefix_keeps_caller_case_and_lowest_free_number():
    assert allocate_designator([], "C") == "C1"
    assert allocate_designator([], "c") == "c1"
    assert allocate_designator(["C1", "C3"], "C") == "C2"
    assert allocate_designator(["C1", "C2", "C3"], "C") == "C4"
    assert allocate_designator(["C1"], "R") == "R1"


def test_non_designator_pool_names_do_not_take_numbers():
    assert allocate_designator(["C", "Cx", "C1?", "C 1"], "C") == "C1"
