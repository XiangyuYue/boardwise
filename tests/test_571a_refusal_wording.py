"""571-A-H2 / 571-A-H3：拒因措辞必须与判据一致（只钉措辞与分支归属）。

- A-H2：`_connection_listing` 会把**不是臂**的器件也追加进 listing（三脚器件、
  同网短接器件），旧句子却把整条 listing 称作 "what the two-terminal parts
  connect is" / "every two-terminal part reaches ground directly ...: listing"，
  读者按拒因去查会读到一条假事实。
- A-H3：`parallel` 只要有一个 `edges` 项跨 power↔gnd 就成立，单个
  `R1(VIN,GND)` 被说成 "two arms in parallel"（实际只有一个臂，真实原因是
  `MIN_ARMS` 不足）。

本文件只断言**措辞**与**走哪个拒因分支**；接受/拒绝的判定不在本文件加严或放宽
（判定不变性由 `evidence/571a2/REPORT.md` 的逐例表给出）。A-H4（RC 低通被整本
绑成分压器、电容当 lower_arm）**不在本批**，这里不碰 `_chains`/`_candidates`。
"""

from __future__ import annotations

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines.grammar import rc_lowpass, voltage_divider
from boardwise.engines.grammar.base import FAILURE_CIRCUIT_INVALID

PROV = "verified_recipe"


def _part(part_id: str, symbol: str = "R0402", value: str = "10k") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value, "provenance": PROV}


def _net(net_id: str, cls: str, members: list[str]) -> dict:
    return {
        "id": net_id,
        "class": cls,
        "members": list(members),
        "provenance": PROV,
    }


def _circuit(parts: list[dict], nets: list[dict]) -> CircuitSpec:
    return CircuitSpec.from_dict({"parts": parts, "nets": nets})


def _presentation(grammar_ref: str) -> PresentationSpec:
    return PresentationSpec.from_dict({"grammarRef": grammar_ref})


def _only_failure(result):
    assert result.ok is False
    (failure,) = result.failures
    assert failure.category == FAILURE_CIRCUIT_INVALID
    return failure


# ---------------------------------------------------------------- A-H2 inputs


def _vd_dead_end_with_three_pin_part() -> CircuitSpec:
    """VIN→R1→TAP→R2→X：链死在 X（不是地），页上还有一个三脚器件和一条短路。

    R3 两脚同网（GND）——`two_terminal_parts` 同样不把它当臂；U1 三脚三个网——
    也不是臂。两者都会被 `_connection_listing` 追加到拒因里，旧句子把整条
    listing 称作 "two-terminal parts"。
    """
    return _circuit(
        [_part("R1"), _part("R2"), _part("R3"), _part("U1", "SOT23-5", "NPN")],
        [
            _net("VIN", "power", ["R1.1", "U1.3"]),
            _net("TAP", "signal", ["R1.2", "R2.1"]),
            _net("X", "signal", ["R2.2", "U1.1"]),
            _net("GND", "gnd", ["U1.2", "R3.1", "R3.2"]),
        ],
    )


def _rc_all_to_ground_with_three_pin_part() -> CircuitSpec:
    """所有两脚器件都直接对地（没有串联件），页上另有一个三脚器件。"""
    return _circuit(
        [_part("C1", "C0402", "100n"), _part("C2", "C0402", "1u"),
         _part("U1", "SOT23-5", "NPN")],
        [
            _net("VIN", "power", ["C1.1", "U1.3"]),
            _net("OUT", "signal", ["C2.1", "U1.1"]),
            _net("GND", "gnd", ["C1.2", "C2.2", "U1.2"]),
        ],
    )


def test_vd_dead_end_listing_does_not_call_the_three_pin_part_two_terminal():
    failure = _only_failure(
        voltage_divider.grammar().bind(
            _vd_dead_end_with_three_pin_part(), _presentation("voltage-divider")
        )
    )

    # 旧句子："... what the two-terminal parts connect is: R1(...), R2(...),
    # R3(GND), U1(GND,VIN,X)" —— 整条 listing 被冠以 two-terminal parts。
    assert "two-terminal parts connect" not in failure.detail, failure.detail
    assert "parts on this page" in failure.detail, failure.detail
    # 不是臂的器件自己说清楚：真实脚数 + not an arm。
    assert "U1(3 pins, not an arm" in failure.detail, failure.detail
    assert "R3(2 pins, not an arm" in failure.detail, failure.detail


def test_rc_all_to_ground_listing_does_not_call_the_three_pin_part_two_terminal():
    failure = _only_failure(
        rc_lowpass.grammar().bind(
            _rc_all_to_ground_with_three_pin_part(), _presentation("rc-lowpass")
        )
    )

    assert "two-terminal parts connect" not in failure.detail, failure.detail
    assert "parts on this page" in failure.detail, failure.detail
    assert "U1(3 pins, not an arm" in failure.detail, failure.detail


# ---------------------------------------------------------------- A-H3 inputs


def _vd_single_crossing() -> CircuitSpec:
    """一个电阻直接跨 VIN↔GND：一个臂，没有中点——真实原因是臂数不足。"""
    return _circuit(
        [_part("R1")],
        [
            _net("VIN", "power", ["R1.1"]),
            _net("GND", "gnd", ["R1.2"]),
        ],
    )


def _vd_two_arms_in_parallel() -> CircuitSpec:
    """负控：两个器件都跨 VIN↔GND，才是真正的两臂并联。"""
    return _circuit(
        [_part("R1"), _part("R2")],
        [
            _net("VIN", "power", ["R1.1", "R2.1"]),
            _net("GND", "gnd", ["R1.2", "R2.2"]),
        ],
    )


def _vd_normal_divider() -> CircuitSpec:
    """负控：正常双臂分压链，判定必须仍是 ok=True。"""
    return _circuit(
        [_part("R1"), _part("R2")],
        [
            _net("VIN", "power", ["R1.1"]),
            _net("TAP", "signal", ["R1.2", "R2.1"]),
            _net("GND", "gnd", ["R2.2"]),
        ],
    )


def test_vd_single_crossing_is_not_reported_as_two_arms_in_parallel():
    failure = _only_failure(
        voltage_divider.grammar().bind(
            _vd_single_crossing(), _presentation("voltage-divider")
        )
    )

    # 旧 detail：'R1(GND,VIN) sit directly across a power rail and ground —
    # two arms in parallel, ...' —— 实际只有一个臂，且掩盖了 MIN_ARMS 门槛。
    assert "two arms in parallel" not in failure.detail, failure.detail
    assert "parallel" not in failure.detail, failure.detail
    assert "MIN_ARMS" in failure.detail, failure.detail
    assert "1 two-terminal arm" in failure.detail, failure.detail
    # 判定不变：仍然拒绝，只是走 no-chain 分支。
    assert failure.action


def test_vd_two_arms_in_parallel_is_still_the_parallel_branch():
    failure = _only_failure(
        voltage_divider.grammar().bind(
            _vd_two_arms_in_parallel(), _presentation("voltage-divider")
        )
    )

    assert "parallel" in failure.detail, failure.detail
    assert "two arms in parallel" in failure.detail, failure.detail
    assert "R1(GND,VIN)" in failure.detail and "R2(GND,VIN)" in failure.detail


def test_vd_normal_divider_still_binds_ok():
    result = voltage_divider.grammar().bind(
        _vd_normal_divider(), _presentation("voltage-divider")
    )

    assert result.ok is True
    assert result.failures == ()
    assert result.parts_of("upper_arm") == ("R1",)
    assert result.parts_of("lower_arm") == ("R2",)
