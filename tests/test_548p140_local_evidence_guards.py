"""548P140：五个本地证据回归的模块级守卫与路径清单机器钉。

P118/P122/P123/P124/P126 读取 `evidence/` 下的真实本机输入（未跟踪）。clone 上
没有这些文件时，它们必须在 **import 阶段** 明确 skip，而不是拖到调用时炸
FileNotFoundError；本机证据齐全时必须照常运行，不能用 skip 遮生产缺口。

这里只静态读源码，不依赖 `evidence/` 是否存在，因此 clone 上也应通过。
守卫的诚实性由三条钉住：

1. 恰好一个模块级 `pytest.skip(..., allow_module_level=True)`，条件来自
   `_missing = [p for p in INPUTS if not p.exists()]` 的 `if _missing:`；
2. `INPUTS` 精确等于盘点 §1.3 的本地路径清单，且所有 `*.load()` 都在守卫之后；
3. P126 的守卫在 import 期生效，而 P138 在模块顶部从 P126 导入 `SPEC`/`_context`，
   因此 P126 skip 时 P138 同样 skip。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

#: 盘点 `.tmp_548p140/docs-test-inventory.md` §1.3 的本地输入清单（路径相对仓库根）。
EXPECTED = {
    "test_548p118_terminal_clearance.py": {
        "evidence/548P4/circuit.wifi.p44.json",
        "evidence/548O/spec-3groups.json",
        "evidence/548J/wifi-canvas/calibrated.library.json",
    },
    "test_548p122_led_columns.py": {
        "evidence/548P120/circuit.full.pinmap.json",
        "evidence/548P122/full.presentation.led-direct.json",
        "evidence/548P59/full.library.json",
    },
    "test_548p123_mcu_roles.py": {
        "evidence/548P120/circuit.full.pinmap.json",
        "evidence/548P123/full.presentation.mcu-roles.json",
        "evidence/548P59/full.library.json",
    },
    "test_548p124_p43_regression.py": {
        "evidence/548D/host-binding/live-reference/circuit_hostbound.json",
        "evidence/548D/host-binding/p43/presentation_hostbound.json",
        "evidence/548D/host-binding/live-reference/profiles_hostbound.json",
    },
    "test_548p126_service_host_feedback.py": {
        "evidence/548P125/circuit.full.g3c.pinmap.json",
        "evidence/548P126/full.presentation.service-feedback.json",
        "evidence/548P59/full.library.json",
    },
}

LOADERS = {"CircuitSpec", "PresentationSpec", "drawapply"}


def _parse(name: str):
    path = TESTS / name
    assert path.is_file(), f"{name} must exist under tests/"
    source = path.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(path))


def _toplevel_assignments(tree) -> dict[str, ast.Assign]:
    assignments: dict[str, ast.Assign] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node
    return assignments


def _is_module_skip(call: ast.Call) -> bool:
    if not (isinstance(call.func, ast.Attribute) and call.func.attr == "skip"):
        return False
    for keyword in call.keywords:
        if keyword.arg == "allow_module_level":
            return keyword.value.value is True
    return False


def _skip_calls(tree) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _is_module_skip(node)
    ]


def _guard(tree) -> ast.If | None:
    for node in tree.body:
        if isinstance(node, ast.If) and any(
                isinstance(stmt, ast.Call) and _is_module_skip(stmt)
                for stmt in ast.walk(node)):
            return node
    return None


def _load_calls(tree) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "load"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in LOADERS
    ]


def _guard_inputs(tree, guard: ast.If, source: str):
    """Return (INPUTS referenced names, evidence suffixes, _missing expression)."""
    assignments = _toplevel_assignments(tree)
    assert "ROOT" in assignments, "ROOT must be defined at module level"
    assert "INPUTS" in assignments, "INPUTS must be defined at module level"
    inputs = assignments["INPUTS"]
    assert isinstance(inputs.value, (ast.Tuple, ast.List)), (
        "INPUTS must be a literal tuple/list of path constants")
    names = [
        element.id for element in inputs.value.elts
        if isinstance(element, ast.Name)
    ]
    assert len(names) == len(inputs.value.elts), "INPUTS entries must be names"

    paths: set[str] = set()
    for name in names:
        assignment = assignments.get(name)
        assert assignment is not None, f"INPUTS entry {name} is not module-level"
        assert assignment.lineno < guard.lineno, (
            f"{name} must be defined before the module guard")
        value = assignment.value
        assert isinstance(value, ast.BinOp) and isinstance(value.op, ast.Div), (
            f"{name} must be ROOT / '<evidence path>'")
        assert isinstance(value.left, ast.Name) and value.left.id == "ROOT"
        assert isinstance(value.right, ast.Constant) and isinstance(
            value.right.value, str)
        paths.add(value.right.value)

    assert "_missing" in assignments, "_missing must be computed at module level"
    missing = assignments["_missing"]
    assert missing.lineno < guard.lineno, "compute _missing before the guard"
    missing_source = ast.get_source_segment(source, missing.value) or ""
    assert ".exists()" in missing_source, (
        "_missing must test path existence, not an unconditional skip")
    assert "INPUTS" in missing_source, "_missing must iterate over INPUTS"
    assert isinstance(guard.test, ast.Name) and guard.test.id == "_missing", (
        "guarded by `if _missing:` only")
    return names, paths, missing_source


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_local_evidence_regressions_skip_at_import_only_when_missing(name):
    """每个文件在 import 期只有一条守卫，且在任何 load/fixture 之前。"""
    source, tree = _parse(name)
    guard = _guard(tree)
    assert guard is not None, f"{name} needs a module-level pytest.skip guard"
    skips = _skip_calls(tree)
    assert len(skips) == 1, f"{name} must carry exactly one skip guard"
    assert guard.lineno < min(call.lineno for call in skips), (
        "the skip must live inside the module guard")

    guard_source = ast.get_source_segment(source, guard) or ""
    assert "requires local" in guard_source, "skip reason must say 'requires local'"
    assert "evidence" in guard_source, "skip reason must name the evidence dependency"
    assert "allow_module_level=True" in guard_source

    _names, _paths, _missing = _guard_inputs(tree, guard, source)

    loads = _load_calls(tree)
    assert loads, f"{name} should load local evidence, found no *.load() calls"
    for call in loads:
        assert call.lineno > guard.lineno, (
            f"{name}:{call.lineno} loads before the module guard at {guard.lineno}")
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            first_line = min(
                [node.lineno] + [item.lineno for item in node.decorator_list])
            assert first_line > guard.lineno, (
                f"{name}: fixture/test {node.name} is defined before the guard")
        if isinstance(node, ast.ClassDef):
            assert node.lineno > guard.lineno, (
                f"{name}: class {node.name} is defined before the guard")

    assert "Path(__file__).resolve().parents[1]" in source


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_local_evidence_path_lists_match_the_inventory_exactly(name):
    """INPUTS 精确钉住 §1.3 清单；每个 load 只用清单里的常量。"""
    _source, tree = _parse(name)
    guard = _guard(tree)
    assert guard is not None, f"{name} needs a module-level guard"
    _names, paths, _missing = _guard_inputs(tree, guard, _source)
    expected = EXPECTED[name]
    assert paths == expected, (
        f"{name}: local evidence list drifted from inventory §1.3; "
        f"extra={sorted(paths - expected)}, missing={sorted(expected - paths)}")

    assignments = _toplevel_assignments(tree)
    root_paths = {
        target: assignment
        for target, assignment in assignments.items()
        if isinstance(assignment.value, ast.BinOp)
        and isinstance(assignment.value.op, ast.Div)
        and isinstance(assignment.value.left, ast.Name)
        and assignment.value.left.id == "ROOT"
    }
    for call in _load_calls(tree):
        assert call.args, f"{name}: load() without an input path"
        argument = call.args[0]
        if isinstance(argument, ast.Name):
            assert argument.id in root_paths, (
                f"{name}: load() uses {argument.id}, not a ROOT path constant")
        elif (isinstance(argument, ast.BinOp)
              and isinstance(argument.op, ast.Div)
              and isinstance(argument.left, ast.Name)
              and argument.left.id == "ROOT"
              and isinstance(argument.right, ast.Name)):
            assert argument.right.id in root_paths, (
                f"{name}: load() uses ROOT / {argument.right.id}, not in INPUTS")
        else:
            raise AssertionError(
                f"{name}: load() must take a module-level ROOT path constant, "
                f"got {ast.unparse(argument)}")


def test_p126_guard_also_skips_p138_through_its_import():
    """P138 在模块顶部从 P126 取 SPEC/_context；P126 skip 会先于 P138 任何代码。"""
    source, tree = _parse("test_548p138_joint_3v3_seat.py")
    imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "test_548p126_service_host_feedback"
    ]
    assert imports, "P138 is expected to import from the P126 regression"
    imported = {alias.name for alias in imports[0].names}
    assert {"SPEC", "_context"} <= imported, imported
    assert imports[0].lineno < min(
        node.lineno for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ), "P138 must import P126 before its own tests are defined"
    assert "_context(PresentationSpec.load" in source
