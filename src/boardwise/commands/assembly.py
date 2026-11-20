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

    net_path = pcb_sub.add_parser(
        "net-path",
        help=(
            "Offline copper-path evidence between two pads of one board "
            "(0 CONNECTED / 2 NOT_PROVEN / 3 INDETERMINATE or refused)."
        ),
        description=(
            "Read-only, offline, no report file: is there an ordered chain of the "
            "copper primitives this batch supports (pad, straight track, via) that "
            "physically joins these two pads of this net on this board? The answer is "
            "machine JSON on stdout and one of three verdicts. CONNECTED means a path "
            "was walked; every hop shares a copper layer and the pair's copper bodies "
            "meet under the repository's own measurement, and a net *name* is never "
            "the evidence. NOT_PROVEN means the supported graph had no path **and** "
            "nothing unknown could change that — it says 「this batch's copper "
            "inventory did not prove a connection」, not 「开路」: copper pour, PLANE "
            "layers and ARC copper are outside the graph (see `ignored` and `scope`), "
            "so read the JSON's `scope` before quoting a negative. INDETERMINATE "
            "means the input does not hold (a reference that is not REF.PAD, an "
            "unknown or ambiguous pad, two nets, or an unreadable layer table) or some "
            "evidence gap could overturn a negative answer. `FILE` must be an .epro2 "
            "archive or an .eprj3 folder project — KiCad, a lone .epcb2 and the live "
            "editor are refused by name, because this batch reads archives only. A "
            "container with several boards needs `--board`, matched verbatim against "
            "the title or board uuid the review runner reports; the first board is "
            "never assumed. This batch does not expose --through, --layer, --json or "
            "--project: order and measurement are the core batch's next step, and a "
            "loose flag would promise evidence that is not there."
        ),
    )
    net_path.add_argument(
        "file",
        metavar="FILE",
        help="An .epro2 archive or an .eprj3 folder project (read-only).",
    )
    net_path.add_argument(
        "--from",
        dest="from_ref",
        required=True,
        metavar="REF.PAD",
        help="Start pad as DESIGNATOR.PAD, for example U9.2.",
    )
    net_path.add_argument(
        "--to",
        dest="to_ref",
        required=True,
        metavar="REF.PAD",
        help="Destination pad as DESIGNATOR.PAD, for example CN3.1.",
    )
    net_path.add_argument(
        "--board",
        default="",
        metavar="TITLE_OR_UUID",
        help=(
            "Which board to ask about, by title or board uuid. Required when the "
            "container holds more than one board; a name that matches nothing or "
            "several boards is refused, never resolved by position."
        ),
    )

    connection = pcb_sub.add_parser(
        "connection",
        help=(
            "Online, read-only host evidence that two pads sit on the same copper "
            "(0 CONNECTED / 2 NOT_PROVEN / 3 INDETERMINATE or refused)."
        ),
        description=(
            "Read-only, online, no report file: did the running editor itself hand "
            "back proof that these two named pads share copper? The answer is one "
            "machine JSON on stdout (`schema` = `boardwise.pcbConnection/1`) and one "
            "of three verdicts. `CONNECTED` means a **typed, sourced direct** "
            "intersection was found — both ends' `getConnectedPrimitives(false)` "
            "answers name the same Line/Arc, or one end's direct answer names the "
            "other end's pad — and every `sharedId` names the calls it came from. "
            "**This contract is direct-only**: it never reads `getEntireTrack`, "
            "because on a real net that call answered ids belonging to copper "
            "components the offline model separates (see the action's "
            "`evidence/559/entire-track-rejection.json` entry), so an id set is not "
            "a connected component. Multi-hop copper needs its own graph contract "
            "and is not claimed. **`sharedIds` is intersection evidence, not a "
            "path**: no hop order, net length or DRC conclusion is claimed. "
            "`NOT_PROVEN` (exit 2) means the host gave no direct shared primitive "
            "**and** nothing was withheld — it says 「在 direct 范围内两端没有共享图元」, "
            "**not 「开路」**: via/fill/pour adjacency and multi-hop copper are "
            "outside this contract and appear in `unknown`/`scope`. When the probe "
            "answers, `INDETERMINATE` (exit 3) is a **measured** answer: an end that "
            "did not resolve to exactly one pad, an empty or differing net, a failed "
            "direct call, a directly connected primitive that is not a proof type "
            "(`direct-non-proof-type`), a legacy `tracks[]` "
            "(`entire-track-unsupported`), or any "
            "other gap that could overturn a negative. A **refusal** is a different "
            "thing and never prints a verdict: a focus that is not a read-only PCB "
            "page, a missing connector, an older build without the action and a "
            "malformed REF.PAD each write one line on stderr with an **empty stdout** "
            "at exit 3, so an unasked question is never printed as a verdict. The "
            "focused PCB **is** the board identity: there is no FILE, no `--board` "
            "and no `--live`, the command never opens or switches a document, and "
            "it never writes a design — the only two actions it reaches are "
            "`sys.probe` (the version pair, whose unreadable half is named in "
            "`missing` with a reason in `error`) and the `risk: read` "
            "`pcb.connection_probe`."
        ),
    )
    connection.add_argument(
        "--from",
        dest="from_ref",
        required=True,
        metavar="REF.PAD",
        help="One end as DESIGNATOR.PAD, for example U9.2.",
    )
    connection.add_argument(
        "--to",
        dest="to_ref",
        required=True,
        metavar="REF.PAD",
        help="The other end as DESIGNATOR.PAD, for example CN3.1.",
    )
    connection.add_argument(
        "--project",
        default="",
        help=(
            "Which editor project to ask, by name or uuid (023). Passed to the "
            "daemon's router; a mismatch is refused there, never re-routed."
        ),
    )
    connection.add_argument(
        "--instance",
        default="",
        help="The same choice spelled as the window key `bridge status` prints.",
    )
    connection.add_argument(
        "--port", type=int, default=None, help="Daemon port (default 61190)."
    )


def dispatch_pcb(
    args: argparse.Namespace,
    checkup: Callable[[argparse.Namespace], int],
    bridge: Callable[[argparse.Namespace], Any],
) -> int:
    """Route `pcb` by its subcommand, keeping `gate` on its own adapter."""
    if getattr(args, "pcb_command", "") == "connection":
        from .. import pcb_connection

        return pcb_connection.run_cli_connection(args, bridge=bridge)
    if getattr(args, "pcb_command", "") == "net-path":
        from .. import pcb_netpath

        return pcb_netpath.run_cli_net_path(args)
    return dispatch_pcb_gate(args, checkup=checkup, bridge=bridge)


def dispatch_pcb_gate(
    args: argparse.Namespace,
    checkup: Callable[[argparse.Namespace], int],
    bridge: Callable[[argparse.Namespace], Any],
) -> int:
    """Hand the run to the assembly-owned gate, with the two cli-side callables."""
    from .. import pcb_gate

    return pcb_gate.run_cli_gate(args, checkup=checkup, bridge=bridge)
