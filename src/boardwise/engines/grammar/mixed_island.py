"""mixed-island: the same island as `ic-periphery`, with two policies relaxed.

The drawing it is for is the one the lock board's V4 P1 auto-compile keeps
refusing: a functional island whose core is a connector or a transistor-like
part that carries **no stated supply reference of its own** (the HMI island's
J5, the buzzer island's Q1), and whose two-terminal branches are not all
attached to that core (an LED chain that reaches the core only through a
signal). `ic-periphery` reads both facts as refusals — its core must sit on a
power and a ground net (098 sec.1), and a two-terminal part touching no core pin
net is `circuit-invalid` (098 sec.三).

This module adds **no layout, routing, flagging or page-anchor logic**. It
subclasses `IcPeripheryGrammar` and changes two strategy switches, both of
which default to the strict reading in the parent:

===============  =====================  ==================
switch           `ic-periphery`         `mixed-island`
===============  =====================  ==================
require_core_supply   True              False
allow_unowned_branches False            True
===============  =====================  ==================

What the relaxed reading still does, unchanged:

* the core is the same three-source fact (declaration > intent block >
  partition), with the same conflict/missing refusals;
* a rail/gnd the core really sits on is still bound by `_net_on_core`, and its
  role/obligation is still stated; a reference the core does **not** sit on is
  omitted, never invented;
* a bridge/shunt is still the same shape and still gets `near`/`adjacent` and
  the two obligations — the obligations are emitted only when their net exists,
  because `GrammarObligation` takes a net and an empty one is not a fact;
* a part touching no core pin net is simply **unbound**: it stays on the
  compiler's free shelf and receives no role. Nothing here says it is this
  core's branch when the connections do not say so.

The role table is `ic-periphery`'s own (`("core", "bridge", "shunt", "rail",
"gnd")`), re-exported rather than copied: a second vocabulary would be a second
promise, and the compiler already knows this one.
"""

from __future__ import annotations

from typing import Mapping

from ...core.presentationspec import PresentationSpec
from ...core.symbolprofile import SymbolProfile
from .ic_periphery import IcPeripheryGrammar
from .ic_periphery import ROLES as _IC_PERIPHERY_ROLES

__all__ = ["GRAMMAR", "NAME", "ROLES", "MixedIslandGrammar", "grammar"]

NAME = "mixed-island"

#: The parent's role table, re-exported under this grammar's own name. Bound as
#: an alias so the two can never drift: this grammar adds no role.
ROLES: tuple[str, ...] = _IC_PERIPHERY_ROLES


class MixedIslandGrammar(IcPeripheryGrammar):
    """An ic-periphery island whose core may state no supply and whose branches
    need not all touch the core.

    Both switches are class attributes so the parent's default reading is
    visible at a glance. The only other override is :meth:`free_parts`: it reads
    the current scope module's `freeParts`, which the parent deliberately never
    reads (548L).
    """

    name = NAME
    require_core_supply = False
    allow_unowned_branches = True

    def free_parts(
        self, presentation: PresentationSpec, scope_id: str
    ) -> tuple[str, ...]:
        """The current scope module's declared free branches (548L).

        ``modules[].freeParts`` is the engineer's statement that these
        two-terminal branches belong to the island but bind **no** core role —
        the case the real MCU island keeps refusing (decoupling/reset/BOOT/
        crystal-load branches whose core has no drawable near relation to them).
        They are not deleted: `IcPeripheryGrammar.bind` still places them, they
        still reach the page, and `_periphery` merely declines to name them.
        Only the module the bind is drawing can lend its declaration: a module's
        free part is a fact about that module's own branches.
        """
        for module in presentation.modules:
            if module.id == scope_id:
                return tuple(module.free_parts)
        return ()


GRAMMAR = MixedIslandGrammar


def grammar(
    profiles: Mapping[str, SymbolProfile] | None = None,
) -> MixedIslandGrammar:
    """A mixed-island grammar, optionally holding the library profiles."""
    return MixedIslandGrammar(profiles)
