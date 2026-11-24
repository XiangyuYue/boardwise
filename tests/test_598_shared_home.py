"""598: one dynamic ``BOARDWISE_HOME`` reader at the package root.

596's layer sweep caught 587's fix: ``bridge/daemon.py`` imported ``core.config``
for the home reader, a ``bridge -> core`` arrow the layer table forbids. A
reverse delegation was no option either (``core`` may not import ``bridge``), so
the reader moved to :mod:`boardwise.home`, below the layer roots, and both
consumers import that instead.

What is pinned here, and why each one is a way the move could be worse:

1. **one home, two readers** — the settings file, the token, the audit log, the
   autostart log and a fresh daemon's default all answer the same directory, and
   all of them follow ``BOARDWISE_HOME`` *after* it changed in-process (587
   pinned the consumers; this pins the reader they now share);
2. **an explicit ``home=`` still wins** — the argument is how tests and second
   profiles pin a directory, and a shared reader must not override it;
3. **one shared failure** — an unusable value raises
   ``boardwise.home.BoardwiseHomeError`` from both sides, and
   ``core.config.ConfigError`` derives from it, so every historical
   ``except ConfigError`` still catches the refusal while the bridge catches the
   shared name (the audit log must not break a call over the home);
4. **no arrow re-introduced** — ``core/config.py`` does not import ``bridge``,
   ``bridge/daemon.py`` does not import ``core``, and ``home.py`` imports
   nothing from the package and nothing outside the standard library.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from boardwise import home
from boardwise.bridge import autostart, daemon
from boardwise.core import config

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "boardwise"


def _imported_names(path: Path) -> set[str]:
    """Top-level names imported by ``path`` (relative imports keep their dots)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                names.add("." * node.level + (node.module or ""))
            else:
                names.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
    return names


# --------------------------------------------------------------------------
# The reader itself: stdlib only, no package import at any depth
# --------------------------------------------------------------------------


def test_the_root_reader_imports_nothing_from_the_package():
    """Any in-package import would re-create the arrow this module removed."""
    assert {name for name in _imported_names(PACKAGE / "home.py") if name.startswith(".")} == set()
    assert "boardwise" not in _imported_names(PACKAGE / "home.py")


def test_the_root_reader_depends_on_the_standard_library_only():
    names = _imported_names(PACKAGE / "home.py")
    assert names <= set(sys.stdlib_module_names), names


# --------------------------------------------------------------------------
# one home, two (three, four) readers
# --------------------------------------------------------------------------


def test_every_consumer_reads_the_same_home_and_follows_the_environment(
    tmp_path, monkeypatch
):
    home_a = tmp_path / "home-a"
    home_b = tmp_path / "home-b"

    monkeypatch.setenv("BOARDWISE_HOME", str(home_a))
    assert home.boardwise_home() == home_a
    assert config.boardwise_home() == home_a
    assert daemon.boardwise_home() == home_a
    assert config.config_path() == home_a / "config.json"
    assert daemon.token_path() == home_a / "token"
    assert daemon.connector_token_path() == home_a / "connector-token"
    assert daemon.audit_dir() == home_a / "audit"
    assert autostart.log_dir() == home_a / "log"
    assert daemon.BridgeDaemon(token="t").home == home_a

    # 569-F-3: the import happened once; the value must still be this call's.
    monkeypatch.setenv("BOARDWISE_HOME", str(home_b))
    assert home.boardwise_home() == home_b
    assert config.boardwise_home() == home_b
    assert daemon.boardwise_home() == home_b
    assert config.config_path() == home_b / "config.json"
    assert daemon.token_path() == home_b / "token"
    assert daemon.audit_dir() == home_b / "audit"
    assert autostart.log_dir() == home_b / "log"
    assert daemon.BridgeDaemon(token="t").home == home_b


def test_the_default_without_an_override_is_the_user_home(monkeypatch):
    monkeypatch.delenv("BOARDWISE_HOME", raising=False)
    expected = Path.home() / ".boardwise"
    assert home.boardwise_home() == expected
    assert config.boardwise_home() == expected
    assert daemon.boardwise_home() == expected
    assert autostart.log_dir() == expected / "log"
    assert config.config_path() == expected / "config.json"


def test_an_explicit_home_still_wins_over_the_environment(tmp_path, monkeypatch):
    explicit = tmp_path / "explicit"
    monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path / "from-env"))

    assert config.config_path(explicit) == explicit / "config.json"
    assert daemon.token_path(explicit) == explicit / "token"
    assert daemon.connector_token_path(explicit) == explicit / "connector-token"
    assert daemon.audit_dir(explicit) == explicit / "audit"
    assert autostart.log_dir(explicit) == explicit / "log"
    assert autostart.stamp_path(explicit) == explicit / autostart.START_STAMP_NAME
    assert daemon.BridgeDaemon(token="t", home=explicit).home == explicit


# --------------------------------------------------------------------------
# one shared failure, catchable from both sides
# --------------------------------------------------------------------------


def test_the_refusal_is_one_class_for_both_sides(monkeypatch):
    """587's contract ("the same ConfigError from every consumer") survives.

    ``ConfigError`` must stay the settings module's public name *and* stay a
    subclass of the shared refusal, because the bridge catches ``OSError`` plus
    the shared base and everything that used to say ``except ConfigError`` must
    keep catching a bad home.
    """
    assert config.ConfigError is home.ConfigError
    assert issubclass(config.ConfigError, home.BoardwiseHomeError)

    monkeypatch.setenv("BOARDWISE_HOME", "relative-home")
    for read in (
        home.boardwise_home,
        config.boardwise_home,
        daemon.boardwise_home,
        daemon.token_path,
        daemon.audit_dir,
        autostart.log_dir,
    ):
        with pytest.raises(home.BoardwiseHomeError) as caught:
            read()
        assert isinstance(caught.value, config.ConfigError), read
        assert "absolute" in str(caught.value)


def test_audit_still_never_raises_for_the_shared_refusal(monkeypatch):
    """The bridge's logging promise must survive the class it now sees."""
    error = home.BoardwiseHomeError("BOARDWISE_HOME is not usable")

    def refuse(home=None):
        raise error

    monkeypatch.setattr(daemon, "audit_dir", refuse)
    daemon.append_audit(None, action="598-audit-guard")


# --------------------------------------------------------------------------
# no arrow re-introduced
# --------------------------------------------------------------------------


def test_config_does_not_reach_for_the_bridge():
    names = _imported_names(PACKAGE / "core" / "config.py")
    assert "bridge" not in names
    assert not any(name.startswith("..bridge") for name in names)


def test_the_bridge_does_not_reach_for_core():
    names = _imported_names(PACKAGE / "bridge" / "daemon.py")
    assert "core" not in names
    assert not any(name.startswith("..core") for name in names)
    assert names & {"..home", ".."}, names
