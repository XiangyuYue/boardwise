"""565f — the draw CLI contract faces S5-H2 / S5-H3, pinned in memory.

Two holes, both reproduced by `outputs/hole565/s5/probes/s5_cli_probes.ps1`:

* **S5-H2** — the eleven parent `draw` options (`--from --spec --golden --yes
  --screenshot --overrides --render --solver --naming --port-meta --library`)
  are accepted by argparse beside a subcommand and read by no subcommand, so
  ``draw --spec <missing> compile ...`` used to exit 0 and ignore the path.
* **S5-H3** — ``draw plan --layout`` reads a PageLayoutPlan; a compile-written
  ``candN.layout.json`` (a single-module LayoutPlan) used to be refused as a
  closed-schema "unknown key(s)" list that never named the file it wants
  (``candN.page.json``).

Every call is in-process (`build_parser()` + the `_cmd_*` / `dispatch_draw`
handler) and fully offline. **No `tmp_path`**: on this machine Python 3.14
writes a restricted DACL for ``os.mkdir(mode=0o700)``, so a `tmp_path` test
fails with `PermissionError [WinError 5]` and swallows the summary line; the
directories this file needs live under the batch's own ``.tmp_565f/``.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from boardwise import cli as cli_module

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "drawapply"
CIRCUIT = FIXTURES / "divider.circuit.json"
PRESENTATION = FIXTURES / "divider.presentation.json"
PROFILES = FIXTURES / "library.json"
#: A captured `sch.geometry` dump for `draw lint --snapshot` (§⑦'s replay path).
SNAPSHOT = ROOT / "tests" / "fixtures" / "ch340_p1_geometry.json"


def _workdir(name: str) -> Path:
    """A fresh directory under `.tmp_565f/`, never a pytest `tmp_path`."""
    out = ROOT / ".tmp_565f" / "pytest" / f"{name}-{uuid.uuid4().hex[:10]}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _inputs() -> list[str]:
    """The three inputs both `compile` and `plan` read."""
    return [
        "--circuit", str(CIRCUIT),
        "--presentation", str(PRESENTATION),
        "--profiles", str(PROFILES),
    ]


def _compile_argv(out: Path) -> list[str]:
    """`compile` and its inputs — the caller supplies the leading `draw`."""
    return ["compile", *_inputs(), "--out", str(out)]


def _parse(argv: list[str]):
    return cli_module.build_parser().parse_args(argv)


def _dispatch(args) -> int:
    return cli_module.dispatch_draw(
        args, cli_module.DRAW_COMMANDS, cli_module._cmd_draw
    )


#: Every parent `draw` option and an argument that states it was given.
PARENT_OPTIONS = [
    ("--from", "no-such-565f.epro2"),
    ("--spec", "no-such-565f.spec.json"),
    ("--golden", "no-such-565f-golden.epro2"),
    ("--yes", None),
    ("--screenshot", "no-such-565f.png"),
    ("--overrides", "no-such-565f.overrides.json"),
    ("--render", "no-such-565f-render.png"),
    ("--solver", None),
    ("--naming", "wire"),
    ("--port-meta", "no-such-565f-port-meta.json"),
    ("--library", "no-such-565f-library.json"),
]


def test_s5h2_parent_spec_beside_compile_is_refused(capsys):
    """S5-H2's own reproduction: `draw --spec <missing> compile` is a refusal.

    Before the guard this returned 0 and compiled three candidates, so a
    `--spec` path that does not exist was accepted as if it had been read.
    """
    args = _parse(
        ["draw", "--spec", "no-such-565f.spec.txt", *_compile_argv(_workdir("h2"))]
    )
    assert _dispatch(args) == 2
    err = capsys.readouterr().err
    assert "--spec" in err
    assert "compile" in err
    # The message has to say *why*: the option belongs to the legacy flow.
    assert "legacy" in err
    assert "subcommand" in err


@pytest.mark.parametrize("option,value", PARENT_OPTIONS)
def test_s5h2_every_parent_option_is_named(option, value, capsys):
    """One guard, all eleven options: each is named, each exits 2.

    A test that only pinned `--spec` would stay green if the guard were
    rewritten to special-case one field, so every parent option is passed.
    """
    argv = ["draw", option] + ([] if value is None else [value])
    argv += _compile_argv(_workdir("h2-all"))
    args = _parse(argv)
    assert _dispatch(args) == 2
    err = capsys.readouterr().err
    assert option in err
    assert "legacy" in err


def test_s5h2_defaults_keep_the_subcommand_route(capsys):
    """The compatibility half: no parent option given, `compile` still runs.

    This is the behaviour the guard must leave byte-for-byte unchanged — a
    guard that refused every `draw <subcommand>` would pass the two tests above
    and break every script.
    """
    out = _workdir("h2-default")
    args = _parse(["draw", *_compile_argv(out)])
    assert _dispatch(args) == 0
    printed = capsys.readouterr().out
    assert "cand1.svg" in printed
    assert (out / "cand1.layout.json").exists()


def _render_svg() -> Path:
    """A minimal captured render for `draw lint --snapshot` (565f §⑦)."""
    path = _workdir("render") / "render.svg"
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<text x="10" y="10">R1</text></svg>\n',
        encoding="utf-8",
    )
    return path


def test_s5h2_render_position_is_read_from_the_parse():
    """§⑦: the flag list is parse-time truth, not a value comparison.

    `--render` after `lint` is `lint`'s own option (consumed); `--render`
    before `lint` is the parent's and is overwritten by the subparser's default.
    Both end up with the same namespace value only in one direction — seen flags
    keep the position that the value cannot.
    """
    from boardwise.commands import draw as draw_commands

    sandbox = _workdir("render-position")
    svg = sandbox / "x.svg"
    snap = sandbox / "s.json"
    after = _parse(["draw", "lint", "--render", str(svg), "--snapshot", str(snap)])
    assert draw_commands._parent_draw_options_given(after) == []
    before = _parse(["draw", "--render", str(svg), "lint", "--snapshot", str(snap)])
    assert draw_commands._parent_draw_options_given(before) == ["--render"]


def test_s5h2_render_before_lint_is_refused_by_position(capsys):
    """§⑦'s reproduction: a `--render` written *before* `lint` is swallowed by
    `lint`'s own default, so the run must refuse and say to write it after."""
    args = _parse(
        [
            "draw", "--render", str(_render_svg()),
            "lint", "--snapshot", str(SNAPSHOT),
        ]
    )
    assert _dispatch(args) == 2
    err = capsys.readouterr().err
    assert "--render" in err
    assert "after the subcommand" in err
    assert "legacy" not in err


def test_s5h2_render_after_lint_is_still_consumed(capsys):
    """The other direction must stay working: after the subcommand it is lint's."""
    args = _parse(
        [
            "draw", "lint", "--render", str(_render_svg()),
            "--snapshot", str(SNAPSHOT),
        ]
    )
    assert _dispatch(args) == 0
    captured = capsys.readouterr()
    assert "boardwise draw:" not in captured.err


@pytest.mark.parametrize("value", ["auto", "wire"])
def test_s5h2_explicit_default_is_still_given(value, capsys):
    """§⑦: `--naming auto` equals the default by value and is still *given*.

    A value comparison cannot see it; the parent Action can, which is why the
    guard reads the parsed flag list rather than the namespace values.
    """
    args = _parse(
        ["draw", "--naming", value, *_compile_argv(_workdir("h2-explicit"))]
    )
    assert _dispatch(args) == 2
    err = capsys.readouterr().err
    assert "--naming" in err
    assert "legacy" in err


def test_s5h3_module_layout_names_the_page_candidate(capsys):
    """S5-H3: compile's own `candN.layout.json` is refused by *name*.

    The compile output is produced here rather than hand-written, so the test
    pins the actual artifact `draw compile` writes: a single-module LayoutPlan
    (`kind == boardwise-layout-plan`). `draw plan --layout` takes the page
    candidate (`candN.page.json`); the refusal must say so instead of listing
    the closed schema's unknown keys.
    """
    out = _workdir("h3")
    assert cli_module._cmd_draw_compile(_parse(["draw", *_compile_argv(out)])) == 0
    capsys.readouterr()
    layout = out / "cand1.layout.json"
    assert layout.exists()
    assert json.loads(layout.read_text(encoding="utf-8"))["kind"] == (
        "boardwise-layout-plan"
    )

    args = _parse(["draw", "plan", *_inputs(), "--layout", str(layout)])
    assert cli_module._cmd_draw_plan(args) == 5
    err = capsys.readouterr().err
    assert "candN.page.json" in err
    assert "single-module LayoutPlan" in err
    # The old diagnosis — a closed-schema unknown-key list — must be gone.
    assert "unknown key" not in err
    assert "closed on purpose" not in err
