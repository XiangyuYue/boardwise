"""551: `pcb.net_class.list` — the catalogue entry, and the boundaries around it.

The connector-side behaviour (which two members are called, what `null` versus
`[]` means, the page guard) is pinned against a fake `eda` in
`connector/tests/net-class-list.test.mjs`; this file pins the **Python** half,
which is what the daemon, the CLI and the read-only gate actually consult:

* the catalogue entry exists, is graded ``read``, is **not** a design write, and
  its parameters/returns say what the 551 contract says;
* ``bridge call --read-only`` can certify it (a ``read`` action travels; the
  gate is only safe because the risk grade is honest);
* its neighbours are unchanged — `pcb.drc_ruleset` keeps its narrow read and
  its own member list, so adding net classes here did not widen it;
* no ``pcb.net_class.*`` **write** (create / delete / modify / add / remove) is
  in the catalogue at all: this batch ships one read and no write surface;
* `docs/bridge.md` §4 lists the action (a reader can discover it) and names the
  `pcbNetClassList` capability, because an old connector omitting that key is the
  one signal a caller has that the action does not exist there.
"""

from __future__ import annotations

import re
from pathlib import Path

from boardwise.bridge.protocol import ACTIONS, action_spec

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DOC = ROOT / "docs" / "bridge.md"

NAME = "pcb.net_class.list"


def test_the_action_is_in_the_catalogue_as_a_plain_read() -> None:
    spec = action_spec(NAME)
    assert spec.name == NAME
    assert spec.risk == "read", "a net-class listing that was graded write would be unusable read-only"
    assert spec.design_write is False, "reporting the classes a board already has writes no design byte"
    assert spec.owner == "connector"
    assert spec.params == ("maxChars",)


def test_the_returns_say_what_the_contract_says() -> None:
    returns = action_spec(NAME).returns
    for key in ("classes", "netRules", "count", "reads", "missing", "unreadable", "readOnly"):
        assert key in returns, key
    assert "pcb_Drc" in returns, "the source is the host namespace, not a boardwise invention"


def test_no_net_class_write_action_is_reachable() -> None:
    # The namespace carries createNetClass/deleteNetClass/... on the host. None of
    # them may become a bridge action in this batch: the slice is a read.
    net_class_actions = [entry.name for entry in ACTIONS if entry.name.startswith("pcb.net_class.")]
    assert net_class_actions == [NAME], net_class_actions


def test_the_narrow_rule_set_read_was_not_widened() -> None:
    ruleset = action_spec("pcb.drc_ruleset")
    assert ruleset.params == ("maxChars", "all"), (
        "551 must not have grown a net-class parameter onto the rule-set read"
    )
    assert "getAllNetClasses" not in ruleset.summary
    assert "net-class" in ruleset.summary, (
        "the rule-set entry still records that the net-class family is off its list"
    )


def test_bridge_doc_lists_the_action_in_the_table() -> None:
    text = BRIDGE_DOC.read_text(encoding="utf-8")
    rows = [
        line for line in text.splitlines()
        if line.startswith(f"| `{NAME}` ")
    ]
    assert len(rows) == 1, f"expected exactly one §4 row for {NAME}, found {len(rows)}"
    row = rows[0]
    assert "| connector | read |" in row, "the risk column must say read"
    assert "getAllNetClasses" in row and "getNetRules" in row
    # The two answers this entry exists to keep apart.
    assert "never" in row and "`[]`" in row, "「could not read」 ≠ 「there are none」 must be stated"
    assert "PAGE_MISMATCH" in row


def test_bridge_doc_names_the_capability() -> None:
    text = BRIDGE_DOC.read_text(encoding="utf-8")
    assert "pcbNetClassList" in text, (
        "an old connector omits the key; the doc has to say that is the signal for "
        "'this build does not have the action'"
    )
    # Declared beside the older flag, not in place of it.
    assert re.search(r"pcbRenderViewport: true, pcbNetClassList: true", text)


def test_the_heuristic_width_ladder_is_not_dressed_as_a_net_class() -> None:
    # The one confusion this action must never create: a name/voltage guess is
    # not a persisted class. Both the catalogue entry and the doc row say so.
    spec = action_spec(NAME)
    assert "heuristic" in spec.summary.lower()
    row = next(
        line for line in BRIDGE_DOC.read_text(encoding="utf-8").splitlines()
        if line.startswith(f"| `{NAME}` ")
    )
    assert "heuristic" in row.lower() and "not" in row.lower()
