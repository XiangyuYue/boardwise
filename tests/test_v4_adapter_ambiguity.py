"""The DesignModel adapter must not choose one of several measured symbols."""
import pytest

from boardwise.core.model import Component, DesignModel, Net
from boardwise.core.symbolprofile import SymbolProfile, SymbolPose
from boardwise.engines.v4circuitspec import circuit_spec_from_design_model


def _model():
    return DesignModel(
        components={"U1": Component(uid="u1", designator="U1", lcsc_part="C2844153",
                                    props={"device_uuid": "source-device"})},
        nets={"SIG": Net(name="SIG", pins=[("U1", "1")])},
    )


def _profiles(refs):
    return {ref: SymbolProfile(symbol_ref=ref, poses=[SymbolPose(rotation=0, mirror=False)])
            for ref in refs}


def test_profile_binding_refuses_all_ambiguous_candidates_in_either_order():
    refs = ["variant-a-C2844153", "variant-b-C2844153"]
    messages = []
    for order in (refs, list(reversed(refs))):
        with pytest.raises(ValueError) as error:
            circuit_spec_from_design_model(_model(), _profiles(order))
        message = str(error.value)
        assert "ambiguous" in message and "C2844153" in message
        assert all(ref in message for ref in refs)
        messages.append(message)
    assert messages[0] == messages[1]


def test_profile_binding_keeps_unique_and_no_profile_paths():
    spec, _report = circuit_spec_from_design_model(_model(), _profiles(["unique-C2844153"]))
    assert spec.parts[0].symbol_ref == "unique-C2844153"
    spec, _report = circuit_spec_from_design_model(_model())
    assert spec.parts[0].symbol_ref == "source-device"
    with pytest.raises(ValueError, match="no measured profile/LCSC binding"):
        circuit_spec_from_design_model(_model(), {})


def test_unrelated_ambiguous_profiles_do_not_block_a_unique_binding():
    spec, _report = circuit_spec_from_design_model(
        _model(), _profiles(["unique-C2844153", "other-a-C1", "other-b-C1"]),
    )
    assert spec.parts[0].symbol_ref == "unique-C2844153"
