"""587: ``BOARDWISE_HOME`` is read when it is used, not when the module is imported.

569-F-3 measured two reading points for one variable: ``core.config`` and
``resources`` resolved it on every call, while ``bridge.daemon`` froze it into a
module constant at import time and ``bridge.autostart`` re-used that constant.
A process that changed the environment ended up with its settings under home B
and its token / audit log / daemon logs under home A — two identities, one
profile, and no message saying so.

What is pinned here, and why each one is a way the fix could be worse:

1. **every consumer follows the environment** — token, connector token, audit
   directory, autostart log directory and stamp, and a fresh ``BridgeDaemon``'s
   default home all agree with ``core.config.boardwise_home()`` *after* the
   value changed in-process;
2. **an explicit ``home=`` still wins** — the argument is how tests and second
   profiles pin a directory; the environment must not override a caller that
   said what it meant;
3. **the legacy name is not a stale snapshot** — ``daemon.BOARDWISE_HOME``
   keeps existing (``from ... import BOARDWISE_HOME`` must not break), but it
   resolves through the same single function, so a reader after the change gets
   the new home rather than the import-time one. Checked in a child process so
   ``monkeypatch.setattr`` in other test files cannot colour the result;
4. **one home, one failure** — an unusable value (relative) is the same
   ``ConfigError`` from every consumer instead of a silent relative directory in
   one place and a refusal in another;
5. **logging still never breaks a call** — ``audit()``'s promise survives the
   change of error type it can now see.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from boardwise.bridge import autostart, daemon
from boardwise.core.config import ConfigError, boardwise_home

SRC = Path(__file__).resolve().parents[1] / "src"


def test_token_paths_and_audit_dir_follow_the_environment(tmp_path, monkeypatch):
    """The measurement 569-F-3 made: import once, change the home, read again."""
    home_a = tmp_path / "home-a"
    home_b = tmp_path / "home-b"

    monkeypatch.setenv("BOARDWISE_HOME", str(home_a))
    assert daemon.token_path() == home_a / "token"
    assert daemon.connector_token_path() == home_a / "connector-token"
    assert daemon.audit_dir() == home_a / "audit"

    monkeypatch.setenv("BOARDWISE_HOME", str(home_b))
    assert daemon.token_path() == home_b / "token"
    assert daemon.connector_token_path() == home_b / "connector-token"
    assert daemon.audit_dir() == home_b / "audit"

    # The single source of truth: not merely "changed", but the same answer
    # core.config gives for every consumer (config/resources already did this).
    assert daemon.token_path() == boardwise_home() / "token"
    assert daemon.connector_token_path() == boardwise_home() / "connector-token"
    assert daemon.audit_dir() == boardwise_home() / "audit"


def test_autostart_log_and_stamp_follow_the_environment(tmp_path, monkeypatch):
    home_a = tmp_path / "home-a"
    home_b = tmp_path / "home-b"

    monkeypatch.setenv("BOARDWISE_HOME", str(home_a))
    assert autostart.log_dir() == home_a / "log"
    assert autostart.stamp_path() == home_a / autostart.START_STAMP_NAME

    monkeypatch.setenv("BOARDWISE_HOME", str(home_b))
    assert autostart.log_dir() == home_b / "log"
    assert autostart.stamp_path() == home_b / autostart.START_STAMP_NAME
    assert autostart.log_dir() == boardwise_home() / "log"


def test_a_new_daemon_defaults_to_the_current_home(tmp_path, monkeypatch):
    home_a = tmp_path / "home-a"
    home_b = tmp_path / "home-b"

    monkeypatch.setenv("BOARDWISE_HOME", str(home_a))
    assert daemon.BridgeDaemon(token="t").home == home_a

    monkeypatch.setenv("BOARDWISE_HOME", str(home_b))
    first = daemon.BridgeDaemon(token="t")
    assert first.home == home_b
    assert first.home == boardwise_home()


def test_the_default_without_an_override_is_still_the_user_home(monkeypatch):
    monkeypatch.delenv("BOARDWISE_HOME", raising=False)
    assert boardwise_home() == Path.home() / ".boardwise"
    assert daemon.token_path() == Path.home() / ".boardwise" / "token"
    assert autostart.log_dir() == Path.home() / ".boardwise" / "log"


def test_an_explicit_home_wins_over_the_environment(tmp_path, monkeypatch):
    """Negative control: the environment set to B must not reach a pinned A."""
    home_b = tmp_path / "home-b"
    explicit = tmp_path / "explicit"
    monkeypatch.setenv("BOARDWISE_HOME", str(home_b))

    assert daemon.token_path(explicit) == explicit / "token"
    assert daemon.connector_token_path(explicit) == explicit / "connector-token"
    assert daemon.audit_dir(explicit) == explicit / "audit"
    assert autostart.log_dir(explicit) == explicit / "log"
    assert autostart.stamp_path(explicit) == explicit / autostart.START_STAMP_NAME
    assert daemon.BridgeDaemon(token="t", home=explicit).home == explicit

    for path in (
        daemon.token_path(explicit),
        daemon.connector_token_path(explicit),
        daemon.audit_dir(explicit),
        autostart.log_dir(explicit),
        autostart.stamp_path(explicit),
        daemon.BridgeDaemon(token="t", home=explicit).home,
    ):
        assert home_b not in path.parents


def test_the_public_name_is_not_a_frozen_snapshot(tmp_path):
    """``from boardwise.bridge.daemon import BOARDWISE_HOME`` must stay importable.

    Its value has to be the home of the moment it is read, not the one the
    module was imported with — otherwise the very import the 569-F-3 repro used
    would keep lying to existing callers. Measured in a child process: other
    test files pin this module attribute through ``monkeypatch``, and after
    their undo the module dict may hold their value.
    """
    home_a = tmp_path / "home-a"
    home_b = tmp_path / "home-b"
    env = os.environ.copy()
    env["BOARDWISE_HOME"] = str(home_a)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env.pop("PYTHONWARNINGS", None)
    script = (
        "import os, sys\n"
        "from boardwise.bridge.daemon import BOARDWISE_HOME\n"
        "import boardwise.bridge.daemon as d\n"
        "print(BOARDWISE_HOME)\n"
        "os.environ['BOARDWISE_HOME'] = sys.argv[1]\n"
        "print(d.BOARDWISE_HOME)\n"
        "print(d.token_path().parent)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(home_b)],
        capture_output=True,
        encoding="utf-8",
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    first, second, third = result.stdout.splitlines()
    assert Path(first) == home_a
    assert Path(second) == home_b
    assert Path(third) == home_b


def test_an_unusable_home_is_one_named_error_everywhere(monkeypatch):
    """A relative home is refused by name (586); every consumer must agree."""
    monkeypatch.setenv("BOARDWISE_HOME", "relative-home")
    with pytest.raises(ConfigError):
        boardwise_home()
    for read in (
        daemon.token_path,
        daemon.connector_token_path,
        daemon.audit_dir,
        autostart.log_dir,
        autostart.stamp_path,
        lambda: daemon.BridgeDaemon(token="t").home,
    ):
        with pytest.raises(ConfigError):
            read()


def test_audit_still_never_raises_even_for_a_configuration_error(monkeypatch):
    """``audit()``'s promise is "logging must not break a call".

    Before 587 the only way ``append_audit`` could fail to resolve its home was
    an ``OSError``; now the shared resolver can also refuse a bad value, and
    that refusal must not turn into a broken request.
    """

    def refuse(home=None):
        raise ConfigError("BOARDWISE_HOME is not usable")

    monkeypatch.setattr(daemon, "audit_dir", refuse)
    daemon.append_audit(None, action="587-audit-guard")
