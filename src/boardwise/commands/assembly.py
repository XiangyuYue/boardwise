"""Assembly-owned CLI surface registration and dispatch (540B6)."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any


def register_install_skill_parser(sub: Any) -> None:
    """Register the historical `install-skill` command surface."""
    # The harness list comes from the module that writes to them: a harness added
    # there (and given a doctor line) must not need a second edit here to be
    # reachable from `--harness`, which is the shape the silently-missing Claude
    # Code copy had (issue #11).
    from .. import skill_install

    install_skill = sub.add_parser(
        "install-skill",
        help=(
            "Copy the bundled SKILL.md into the user-level skill directory of each "
            "agent harness (Kimi Code, Claude Code), or — with --agent — print the "
            "prompt that has any other harness's AI install it itself."
        ),
        description=(
            "Writes the SKILL.md this build carries where the agent reads it: "
            "~/.kimi-code/skills/boardwise/SKILL.md for Kimi Code (override the "
            "directory with BOARDWISE_SKILL_HOME) and "
            "~/.claude/skills/boardwise/SKILL.md for Claude Code (override with "
            "BOARDWISE_SKILL_HOME_CLAUDE). --harness picks one side; the default is "
            "all of them, because this toolchain is meant to work under either agent "
            "and one of them having no SOP is exactly the state that is impossible to "
            "notice from the outside. Idempotent: an identical file says 'already "
            "current' and is left alone. A *different* file is backed up to "
            "SKILL.md.bak-<YYYYMMDD-HHMMSS> first — never silently overwritten, and "
            "never overwritten by a second install on the same day either. --uninstall "
            "removes the installed copy from the selected harnesses, and each "
            "directory when it empties. --agent writes nothing: it prints the "
            "absolute path of the bundled SKILL.md and a paragraph to hand to an "
            "agent this build knows nothing about (Codex, Hermes, ...), whose skill "
            "directory *it* knows and we would only be guessing at (062)."
        ),
    )
    # `--uninstall` and `--agent` are the two that contradict each other outright
    # (tear the copy down / write nothing at all), and argparse refuses that pair
    # with a usage error (exit 2) instead of letting one silently win. `--harness`
    # stays out of the group: it legitimately combines with `--uninstall`, and a
    # group refuses *every* pair of its members, so putting all three in would
    # break `--uninstall --harness claude`. Its clash with `--agent` is refused in
    # the command instead, the same way `compare` refuses `--spec` next to a
    # candidate (the two are equally exclusive; only argparse's shape differs).
    # The default is None rather than "all" so that spelling the default out is
    # still visible to that check.
    action = install_skill.add_mutually_exclusive_group()
    action.add_argument(
        "--uninstall", action="store_true",
        help="Remove the installed copy instead of installing one.",
    )
    action.add_argument(
        "--agent", action="store_true",
        help=(
            "Print the absolute path of the bundled SKILL.md and a prompt to paste "
            "into any other agent harness, which installs it itself. Writes nothing."
        ),
    )
    install_skill.add_argument(
        "--harness", choices=(*skill_install.HARNESSES, *skill_install.ADVISORY_HARNESSES, "all"), default=None,
        help="Which agent harness to act on (default: all of them).",
    )


def dispatch_assembly(
    args: argparse.Namespace,
    handler: Callable[[argparse.Namespace], int],
) -> int:
    """Resolve an assembly-owned handler at call time."""
    return handler(args)


def register_pcb_parser(sub: Any) -> None:
    """038Y5: `pcb gate` — the read-only last step after a board change."""
    pcb = sub.add_parser(
        "pcb",
        help="Read-only PCB gate: the editor's own DRC, then a fresh checkup.",
    )
    # `pcb_sub`, not `gate_commands`: tests/test_doc_claims._cli_commands reads the
    # registration text with `(\w+)_sub = <parser>.add_subparsers`, so a variable
    # without that suffix hides `pcb gate` from the command guard entirely.
    pcb_sub = pcb.add_subparsers(dest="pcb_command", required=True)
    gate = pcb_sub.add_parser(
        "gate",
        help=(
            "Run the host PCB DRC and a fresh checkup against the active board and "
            "report one verdict (0 GREEN / 2 RED / 3 cannot be stated)."
        ),
        description=(
            "The read-only last step after a board change. `doc.list` must show the "
            "active document to be a PCB in the project the caller named — the gate "
            "never switches documents and never falls back to the first board listed — "
            "then `pcb.drc_check` (strict, no editor UI, verbose leaves) and a fresh "
            "`boardwise checkup` run on the same project/instance/port with a report "
            "directory of its own at DIR/checkup. Nothing is written to the design: "
            "there is no doc.open, no save, no autofix and no --skip-checkup, so the "
            "DRC is asked exactly once. `DIR` must be a new directory (parents may be "
            "created); an existing one is refused before anything is read, because a "
            "report already in there is some earlier run's. GREEN requires all of: DRC "
            "checked, available, untruncated, errors=0; checkup actually ran; its "
            "completion.verdict complete or complete-with-open-items; no ERROR; no "
            "declared coverage gap (modelEmpty/parseIncomplete/rulesErrored/"
            "recordsDropped/rulesRefused/pagesDropped/boardsEmpty/pcbReviewMissing); and "
            "the report's own exitCode equal to "
            "the run's. Exit 2 = RED (errors found), exit 3 = INCOMPLETE or an input, "
            "identity or output that cannot be used — an `incomplete` checkup outranks "
            "an ERROR, because a review that did not see the whole board cannot be "
            "quoted as having found them all."
        ),
    )
    gate.add_argument(
        "--out",
        required=True,
        metavar="DIR",
        help=(
            "New directory for this run's gate-report.json and the checkup inside it "
            "(DIR/checkup). Must not exist yet — the gate never reuses a directory."
        ),
    )
    gate.add_argument(
        "--project",
        default="",
        help=(
            "Which editor project to gate, by name or uuid (023). Checked verbatim "
            "against what doc.list reports; a mismatch is refused, never re-routed."
        ),
    )
    gate.add_argument(
        "--instance",
        default="",
        help=(
            "The same choice spelled as the window key `bridge status` prints — and the "
            "only identity the gate accepts when doc.list cannot prove the project."
        ),
    )
    gate.add_argument(
        "--port", type=int, default=None, help="Daemon port (default 61190)."
    )


def dispatch_pcb_gate(
    args: argparse.Namespace,
    checkup: Callable[[argparse.Namespace], int],
    bridge: Callable[[argparse.Namespace], Any],
) -> int:
    """Hand the run to the assembly-owned gate, with the two cli-side callables."""
    from .. import pcb_gate

    return pcb_gate.run_cli_gate(args, checkup=checkup, bridge=bridge)
