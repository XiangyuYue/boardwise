"""Drift guard (045 §7, upgraded by 595): the dsh plugin wraps CLI commands **by
name and by flag**.

Every module under `dsh-plugin/src/` builds a boardwise CLI argv — `index.ts` for
most tools, `review-finalize.ts` for `review finalize`. Renaming or removing such
a command breaks the plugin on every dsh machine, silently from pytest's point of
view — unless this guard is watching. The reverse direction (a new CLI command not
yet wrapped) is a release-checklist judgment, not a failure: see
`tasks/045-dsh-plugin.md` §7.

hole568-C-01: this guard used to compare *sets of first tokens* — `const argv = […]`
contributed only its head token, and the CLI side was every `add_parser("name")`
string anywhere under `src/boardwise`. So `v4-facts → v4facts` and
`--out-circuit → --write-circuit` both stayed green. 595 replaces both sides with
the production tree: `boardwise.cli.build_parser()` is walked into
`(path) -> option strings`, and each plugin argv contributes its **complete**
leading command path plus every flag it can spell (array literals, `argv.push(…)`
literals and constants, and `{ flag: '--…' }` literals feeding `argv.push(item.flag)`).
A missing path and a flag the path does not define are separate, named failures.

`review finalize` also gets its own pin: the top-level `review` group surviving in
cli.py says nothing about the subcommand, which is not a subparser at all — the
`review` command takes a positional `file` and dispatches on it. The plugin's
`['review', 'finalize', …]` argv **and** the CLI dispatch to `_cmd_review_finalize`
are both asserted by name (537D3a), and `DISPATCHED` is only honoured while
that dispatch evidence is present.
"""

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
CLI = SRC / "boardwise" / "cli.py"
PLUGIN_SRC = REPO / "dsh-plugin" / "src"
REVIEW_FINALIZE_MODULE = PLUGIN_SRC / "review-finalize.ts"
PLUGIN_PKG = REPO / "dsh-plugin" / "package.json"
PLUGIN_README = REPO / "dsh-plugin" / "README.md"

# 067: peer range and the dsh versions we actually ran, kept in lockstep with
# dsh-plugin/README.md "已验证的 dsh 版本". Widening/narrowing the range or
# leaving a stale README is a release judgment — make it a red test instead.
PEER_RANGE = ">=0.0.1-rc.1 <0.3.0 || >=0.1.7-rc.2 <0.2.0-0 || >=0.2.0-rc.1 <0.3.0-0"
VERIFIED_DSH = ("0.1.7-rc.2", "0.2.0-rc.1")

# The fourteen command paths the plugin wrapped when 595 landed. Pinned as a
# *subset*: a new tool may be added without touching this line, but losing or
# renaming one of these paths (or a parse that stops seeing argv arrays) is red.
EXPECTED_PATHS = frozenset({
    ("arch",),
    ("bridge", "call"),
    ("checkup",),
    ("doctor",),
    ("draw", "compile"),
    ("draw", "lint"),
    ("draw", "plan"),
    ("draw", "v4-facts"),
    ("parts", "hunt"),
    ("pcb", "connection"),
    ("review", "finalize"),
    ("review-evidence",),
    ("review-read",),
    ("triage-batch",),
})

# `review finalize` is spelled as a positional value of `review`, not as a
# subparser (537D3a). The tree walk therefore has no node for it; this maps the
# plugin's path onto the node whose option strings the CLI parses it with. The
# mapping is only honoured while the dispatch itself is still in cli.py, so it
# cannot outlive the subcommand it borrows options from.
DISPATCHED = {("review", "finalize"): ("review",)}

# `['review', 'finalize'` with any spacing / quote style.
REVIEW_FINALIZE_ARGV = re.compile(r"\[\s*(['\"])review\1\s*,\s*(['\"])finalize\2")
# The CLI dispatch, either spelling: `getattr(args, "file", None) == "finalize"`
# (today's code) or `args.file == "finalize"`.
REVIEW_FINALIZE_DISPATCH = re.compile(
    r'(?:getattr\(\s*args\s*,\s*(["\'])file\1\s*(?:,\s*None\s*)?\)|args\.file)'
    r'\s*==\s*(["\'])finalize\2'
)
REVIEW_FINALIZE_HANDLER = "_cmd_review_finalize("


@dataclass(frozen=True)
class Invocation:
    """One `const argv = […]` a plugin module hands to the CLI."""

    module: str
    tool: str
    path: tuple[str, ...]
    flags: frozenset[str]


def cli_command_tree() -> dict[tuple[str, ...], frozenset[str]]:
    """Every argparse command path, mapped to the option strings it accepts.

    The tree comes from the parser the CLI actually builds at dispatch time, so
    a registration that moved into a line-owned command module is still found,
    and a nested command path keeps its parent (`draw lint` is not `lint`). Only
    the path's *own* options are recorded: `--version` on the root is not
    accepted after a subcommand, so folding it in would hide a real mismatch.
    """
    from boardwise.cli import build_parser

    tree: dict[tuple[str, ...], frozenset[str]] = {}

    def walk(parser: argparse.ArgumentParser, path: tuple[str, ...]) -> None:
        if path:
            tree[path] = frozenset(
                option for action in parser._actions for option in action.option_strings
            )
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, sub in action.choices.items():
                    walk(sub, path + (name,))

    walk(build_parser(), ())
    return tree


_LITERAL = re.compile(r"""^(['"])(.*)\1$""", re.S)
_CONST_FLAG = re.compile(
    r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*['\"](--?[\w-]+)['\"]", re.M
)
_TOOL_NAME = re.compile(r"^\s*name:\s*['\"]boardwise_(\w+)['\"]", re.M)
_FLAG_LITERAL = re.compile(r"\{\s*flag:\s*['\"](--?[\w-]+)['\"]")
_HELPER_DEF = re.compile(r"^(?:export\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", re.M)
_ARGV_ARRAY = re.compile(r"const\s+argv[^=\n]*=\s*\[")
_PUSH = re.compile(r"argv\.push\s*\(")
_DYNAMIC_FLAG = re.compile(r"[\w$]+\.flag$")


_REGEX_PRECEDERS = frozenset("(,=:[!&|?{};+-*%<>~^")
_REGEX_KEYWORDS = ("return", "typeof", "case", "in", "of", "new", "delete", "void", "throw")


def _sanitize_source(text: str) -> str:
    """Blank comments and regex-literal bodies, keeping the code's shape.

    Brace and argument-list matching run over this text. Prose comments carry
    apostrophes ("the CLI's") that would otherwise open an unterminated string,
    regex literals carry quotes (`/No module named ['"]?boardwise/`), and a
    commented-out `argv.push(…)` must not count as a flag. Newlines are kept so
    the line-anchored `^function` / `name:` scanners still land.
    """
    out: list[str] = []
    quote: str | None = None
    last = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if quote is not None:
            out.append(ch)
            if ch == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"`":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if text.startswith("//", i):
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = len(text) if end < 0 else end + 2
            out.append("\n" * text.count("\n", i, end))
            i = end
            continue
        tail = "".join(out[-12:]).rstrip()
        starts_regex = last in _REGEX_PRECEDERS or not tail or tail.endswith(_REGEX_KEYWORDS)
        if ch == "/" and starts_regex:
            j = i + 1
            in_class = False
            while j < len(text):
                inner = text[j]
                if inner == "\\":
                    j += 2
                    continue
                if inner == "[":
                    in_class = True
                elif inner == "]":
                    in_class = False
                elif inner == "/" and not in_class:
                    break
                j += 1
            out.append(" " * (j - i + 1))
            i = j + 1
            while i < len(text) and text[i].isalpha():
                out.append(" ")
                i += 1
            last = "x"
            continue
        out.append(ch)
        if not ch.isspace():
            last = ch
        i += 1
    return "".join(out)


def _close_index(text: str, start: int, opener: str, closer: str) -> int:
    """Index of the `closer` matching the `opener` at `start`, quotes respected."""
    depth = 0
    quote: str | None = None
    i = start
    while i < len(text):
        ch = text[i]
        if quote is not None:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"unbalanced {opener}{closer} starting at offset {start}")


def _balanced(text: str, start: int, opener: str, closer: str) -> str:
    """Inner text of the bracketed span opening at `start`."""
    return text[start + 1: _close_index(text, start, opener, closer)]


def _split_top_level(text: str) -> list[str]:
    """Split an argument list on commas that are not inside quotes or brackets."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote is not None:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(text):
                buf.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
            buf.append(ch)
        elif ch in "([{":
            depth += 1
            buf.append(ch)
        elif ch in ")]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return [part for part in parts if part]


def _literal(token: str) -> str | None:
    """The string a single-quoted/double-quoted literal token holds, else None."""
    match = _LITERAL.match(token)
    return match.group(2) if match else None


def _helper_bodies(text: str) -> dict[str, str]:
    """Module-scope `function name(…) { … }` bodies, so argv helpers are seen."""
    bodies: dict[str, str] = {}
    for match in _HELPER_DEF.finditer(text):
        # Skip a destructured parameter object: the body brace comes after the
        # parameter list closes, not after the signature's first `{`.
        params_close = _close_index(text, match.end() - 1, "(", ")")
        brace = text.find("{", params_close + 1)
        if brace < 0:
            continue
        bodies[match.group(1)] = _balanced(text, brace, "{", "}")
    return bodies


def _flag_tokens(tokens: list[str], consts: dict[str, str], flag_literals: set[str]) -> set[str]:
    """Every flag a list of argument tokens can spell."""
    flags: set[str] = set()
    for token in tokens:
        literal = _literal(token)
        if literal is not None:
            if literal.startswith("-"):
                flags.add(literal)
        elif token in consts:
            flags.add(consts[token])
        elif _DYNAMIC_FLAG.match(token):
            # `argv.push(item.flag, …)` — the values come from the segment's
            # `{ flag: '--…' }` literals.
            flags |= flag_literals
    return flags


def _segment_invocations(
    module: str,
    tool: str,
    segment: str,
    consts: dict[str, str],
    helpers: dict[str, str],
) -> list[Invocation]:
    helper_text = "".join(
        body
        for name, body in helpers.items()
        if re.search(rf"(?<![\w$.]){re.escape(name)}\s*\(\s*argv\b", segment)
    )
    scoped = segment + helper_text
    flag_literals = set(_FLAG_LITERAL.findall(scoped))
    arrays = [_balanced(segment, match.end() - 1, "[", "]") for match in _ARGV_ARRAY.finditer(segment)]
    pushes = [_balanced(scoped, match.end() - 1, "(", ")") for match in _PUSH.finditer(scoped)]

    push_tokens: list[str] = []
    for body in pushes:
        push_tokens.extend(_split_top_level(body))
    flags = _flag_tokens(push_tokens, consts, flag_literals)
    for body in arrays:
        flags |= _flag_tokens(_split_top_level(body), consts, flag_literals)

    invocations: list[Invocation] = []
    for body in arrays:
        path: list[str] = []
        for token in _split_top_level(body):
            literal = _literal(token)
            # The command path is the leading run of quoted literals; the first
            # non-literal (a value) or first flag ends it.
            if literal is None or literal.startswith("-"):
                break
            path.append(literal)
        if not path:
            if body.lstrip().startswith("..."):
                # `[...cli.prefix, …]` is the spawn wrapper, not a command.
                continue
            raise ValueError(
                f"{module}: {tool}: `const argv = […]` starts with no literal command token "
                f"({body.strip().splitlines()[0][:80]!r}) — the sentinel cannot read this argv"
            )
        invocations.append(Invocation(module, tool, tuple(path), frozenset(flags)))
    return invocations


def plugin_invocations(src_root: Path = PLUGIN_SRC) -> list[Invocation]:
    """Every CLI invocation spelled under `src_root`, one per argv array.

    Function bodies are scoped to the tool they belong to (`name: 'boardwise_x'`
    registration blocks); a module without such blocks (review-finalize.ts) is
    one segment. Flags pushed by a module-scope helper that receives this argv
    (`requireDesign(argv, …)`) are attributed to the tool that calls it.
    """
    invocations: list[Invocation] = []
    for module in sorted(src_root.glob("*.ts")):
        text = _sanitize_source(module.read_text(encoding="utf-8"))
        consts = dict(_CONST_FLAG.findall(text))
        helpers = _helper_bodies(text)
        bounds = [(match.start(), match.group(1)) for match in _TOOL_NAME.finditer(text)]
        segments = (
            [
                (start, bounds[index + 1][0] if index + 1 < len(bounds) else len(text), tool)
                for index, (start, tool) in enumerate(bounds)
            ]
            if bounds
            else [(0, len(text), module.stem)]
        )
        for start, end, tool in segments:
            invocations.extend(
                _segment_invocations(module.name, tool, text[start:end], consts, helpers)
            )
    return invocations


def _dispatch_is_pinned() -> bool:
    return bool(REVIEW_FINALIZE_DISPATCH.search(CLI.read_text(encoding="utf-8")))


def argv_problems(src_root: Path = PLUGIN_SRC) -> list[str]:
    """Named mismatches between the plugin's argv and the production parser tree."""
    tree = cli_command_tree()
    problems: list[str] = []
    for invocation in plugin_invocations(src_root):
        spelled = " ".join(invocation.path)
        node = invocation.path if invocation.path in tree else DISPATCHED.get(invocation.path)
        if node is None or node not in tree:
            problems.append(
                f"{invocation.module}: {invocation.tool} spawns `{spelled}`, which is not a "
                "command path in the CLI parser"
            )
            continue
        if node != invocation.path and not _dispatch_is_pinned():
            problems.append(
                f"{invocation.module}: {invocation.tool} spawns `{spelled}` on the strength of a "
                "dispatch that cli.py no longer contains"
            )
            continue
        unknown = sorted(set(invocation.flags) - tree[node])
        if unknown:
            problems.append(
                f"{invocation.module}: {invocation.tool} spawns `{spelled}` with flags the CLI "
                f"does not define for that path: {unknown}"
            )
    return problems


def test_every_command_the_dsh_plugin_spawns_exists_in_the_cli():
    invocations = plugin_invocations()
    assert invocations, "guard vacuous: no argv arrays found under dsh-plugin/src/*.ts"
    discovered = {invocation.path for invocation in invocations}
    lost = sorted(EXPECTED_PATHS - discovered)
    assert not lost, (
        f"the argv sentinel no longer sees command paths the plugin used to wrap: {lost} — "
        "either a tool/command was renamed (mirror it in dsh-plugin, 045 §7) or argv "
        "extraction stopped following this module's shape"
    )
    flagless = sorted({invocation.tool for invocation in invocations if not invocation.flags})
    assert not flagless, (
        f"no flags extracted for {flagless} — the flag extraction (array literals, argv.push, "
        "`{ flag: … }`) stopped seeing this tool's argv, so the flag half is vacuous"
    )
    problems = argv_problems()
    assert not problems, (
        "dsh-plugin argv no longer matches the CLI parser:\n  " + "\n  ".join(problems)
    )


def test_review_finalize_subcommand_is_wrapped_and_still_dispatched():
    """537D3a: the subcommand is pinned on both sides, not just its `review` group."""
    plugin = REVIEW_FINALIZE_MODULE.read_text(encoding="utf-8")
    assert REVIEW_FINALIZE_ARGV.search(plugin), (
        "dsh-plugin/src/review-finalize.ts no longer builds a `['review', 'finalize', …]` argv — "
        "a surviving top-level `review` command does not keep the finalize subcommand alive"
    )

    cli = CLI.read_text(encoding="utf-8")
    dispatch = REVIEW_FINALIZE_DISPATCH.search(cli)
    assert dispatch, (
        "src/boardwise/cli.py no longer dispatches `review finalize` on args.file == \"finalize\""
    )
    window = cli[dispatch.start(): dispatch.start() + 400]
    assert REVIEW_FINALIZE_HANDLER in window, (
        "the `review finalize` dispatch no longer calls _cmd_review_finalize — "
        "the subcommand is wired to a handler that moved or disappeared"
    )


def _plugin_package() -> dict:
    return json.loads(PLUGIN_PKG.read_text(encoding="utf-8"))


def test_peer_range_is_the_one_we_tested():
    """`<0.2.0` hard-fails `npm install` against dsh-tools 0.2.x (066 §2b)."""
    peers = _plugin_package()["peerDependencies"]
    assert peers["@deepseek-ai/dsh-tools"] == PEER_RANGE, (
        f"dsh-tools peer range drifted: {peers['@deepseek-ai/dsh-tools']!r} != "
        f"{PEER_RANGE!r} — if the range moved deliberately, re-run the dsh matrix "
        "(outputs/066_dsh_matrix/) and update README 已验证的 dsh 版本 together"
    )


def test_readme_lists_the_verified_dsh_versions():
    readme = PLUGIN_README.read_text(encoding="utf-8")
    missing = [v for v in VERIFIED_DSH if v not in readme]
    assert not missing, (
        f"dsh-plugin/README.md lost the verified dsh versions: {missing} — "
        "the 已验证的 dsh 版本 table is the only place we record what was actually run"
    )


def test_readme_install_snippet_matches_the_packed_version():
    readme = PLUGIN_README.read_text(encoding="utf-8")
    version = _plugin_package()["version"]
    assert f"boardwise-dsh-{version}.tgz" in readme, (
        f"dsh-plugin/README.md install snippet does not name boardwise-dsh-{version}.tgz "
        "(a version bump must carry the README tarball path along)"
    )
