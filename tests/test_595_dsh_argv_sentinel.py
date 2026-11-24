"""595 / W-DSH: the argv sentinel must actually catch the renames it exists for.

`tests/test_dsh_plugin_sync.py` now checks the plugin's argv against the
production argparse tree. These tests prove that check is live rather than
decorative: each case copies `dsh-plugin/src` to a temporary directory, performs
one rename in the copy (the production tree is never touched), and asserts the
sentinel names the drifted module, path and token. The same three renames were
green under the old first-token / flat-name guard (hole568-C-01), so a future
refactor that quietly degrades the extractor reds here first.
"""

import shutil

import test_dsh_plugin_sync as sync


def _mutated_copy(tmp_path, module_name: str, old: str, new: str):
    """A copy of dsh-plugin/src with exactly one literal rename applied."""
    source = tmp_path / "src"
    shutil.copytree(sync.PLUGIN_SRC, source)
    target = source / module_name
    text = target.read_text(encoding="utf-8")
    assert text.count(old) == 1, (
        f"test setup lost its footing: {module_name} contains {old!r} "
        f"{text.count(old)} times, not once"
    )
    target.write_text(text.replace(old, new), encoding="utf-8")
    return source


def _problems(tmp_path, module_name: str, old: str, new: str) -> tuple[str, list[str]]:
    source = _mutated_copy(tmp_path, module_name, old, new)
    problems = sync.argv_problems(source)
    return "\n".join(problems), problems


def test_renamed_v4_facts_subcommand_is_caught(tmp_path):
    """`draw v4-facts` → `draw v4facts`: the tail token was invisible to the old guard."""
    text, problems = _problems(
        tmp_path, "draw-tools.ts", "['draw', 'v4-facts',", "['draw', 'v4facts',"
    )
    assert problems, "the sentinel stayed green on a renamed subcommand path"
    assert any(
        "draw-tools.ts" in problem and "`draw v4facts`" in problem and "not a command path" in problem
        for problem in problems
    ), f"the rename was not named as a missing path:\n{text}"


def test_renamed_out_circuit_flag_is_caught(tmp_path):
    """`--out-circuit` → `--write-circuit`: a flag carried by `{ flag: … }` literals."""
    text, problems = _problems(
        tmp_path, "draw-tools.ts", "{ flag: '--out-circuit'", "{ flag: '--write-circuit'"
    )
    assert problems, "the sentinel stayed green on a renamed flag"
    assert any(
        "draw-tools.ts" in problem
        and "`draw v4-facts`" in problem
        and "'--write-circuit'" in problem
        for problem in problems
    ), f"the rename was not named as an unknown flag:\n{text}"


def test_parent_path_moved_from_draw_to_edit_is_caught(tmp_path):
    """`draw lint` → `edit lint`: same tail token, different parent — needs full paths."""
    text, problems = _problems(
        tmp_path, "draw-tools.ts", "['draw', 'lint',", "['edit', 'lint',"
    )
    assert problems, "the sentinel stayed green on a command moved to another parent"
    assert any(
        "draw-tools.ts" in problem and "`edit lint`" in problem and "not a command path" in problem
        for problem in problems
    ), f"the moved parent was not named as a missing path:\n{text}"


def test_the_real_plugin_tree_has_no_missing_paths_or_flags():
    """The same checker, over the real sources: fourteen tools, zero problems."""
    invocations = sync.plugin_invocations()
    paths = {invocation.path for invocation in invocations}
    assert len(paths) == len(sync.EXPECTED_PATHS) == 14, (
        f"the plugin now spawns {len(paths)} distinct command paths, {len(sync.EXPECTED_PATHS)} "
        "expected — a new tool must be added to EXPECTED_PATHS (and a removed one is exactly the "
        "drift this file exists for)"
    )
    assert sync.argv_problems() == []
