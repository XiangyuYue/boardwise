"""615: ``BOARDWISE_HOME="~/bw"`` is one home for every consumer.

570-D10 left one spelling behind: 586/587/598 taught the reader to refuse a
relative home, and ``~/bw`` — a legal way to name the user's home — was caught
by that refusal because nothing expanded the ``~`` first. The older code had the
opposite bug (it created a literal ``~`` under the working directory).

What this file pins, and each test is a way the fix could be wrong:

1. **``~`` means the user's home** — ``~/bw`` and a bare ``~`` resolve through
   ``Path.expanduser``, come back absolute, and carry no unexpanded ``~``;
2. **both consumers, one path** — ``core.config`` and ``bridge.daemon`` (plus
   the dynamic ``daemon.BOARDWISE_HOME``, ``config_path()``, the token, the
   audit directory and the autostart log) answer the same directory, including
   when the same home is spelled once with ``~`` and once literally;
3. **``~`` is not the door for relative paths** — ``data/bw`` is still refused,
   in the working directory it would have moved with, and nothing gets created;
4. **an unresolvable ``~`` is the named refusal** — not the working directory,
   not a bare ``RuntimeError``, and the message keeps the original spelling;
5. **the rest of the contract stands** — empty/unset means ``.boardwise``,
   literal absolute paths come back as written, trailing dot or space and the
   extended-length prefix behave exactly as 586 measured, and the environment
   is read on every call.

Every test drives HOME/``USERPROFILE`` and ``BOARDWISE_HOME`` with
``monkeypatch.setenv`` into ``tmp_path``, so the real user profile, settings
file and audit log are neither read nor written.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from boardwise import home
from boardwise.bridge import autostart, daemon
from boardwise.core import config
from boardwise.home import BoardwiseHomeError, ConfigError


def _set_user_home(monkeypatch, path: Path) -> None:
    """Make ``Path.home()`` and ``~`` name ``path`` — through the environment only."""
    monkeypatch.setenv("USERPROFILE", str(path))
    monkeypatch.setenv("HOME", str(path))


def _resolved(tmp_path: Path, monkeypatch, spelling: str) -> Path:
    """Resolve ``spelling`` with the user profile parked under ``tmp_path``."""
    _set_user_home(monkeypatch, tmp_path / "profile-615")
    monkeypatch.setenv("BOARDWISE_HOME", spelling)
    return home.boardwise_home()


# --------------------------------------------------------------------------
# 1. `~` is the user's home, and both readers agree
# --------------------------------------------------------------------------


def test_a_tilde_home_is_the_user_home(tmp_path, monkeypatch):
    resolved = _resolved(tmp_path, monkeypatch, "~/bw")
    assert resolved == tmp_path / "profile-615" / "bw"
    assert resolved.is_absolute()
    assert "~" not in str(resolved)
    assert not resolved.exists(), "resolving a home must not create or touch it"


def test_a_bare_tilde_is_the_user_home(tmp_path, monkeypatch):
    resolved = _resolved(tmp_path, monkeypatch, "~")
    assert resolved == tmp_path / "profile-615"
    assert resolved.is_absolute()
    assert "~" not in str(resolved)


def test_both_consumers_and_their_paths_share_one_expanded_home(tmp_path, monkeypatch):
    profile = tmp_path / "profile-615"
    expected = profile / "bw"
    _set_user_home(monkeypatch, profile)
    monkeypatch.setenv("BOARDWISE_HOME", "~/bw")

    assert home.boardwise_home() == expected
    assert config.boardwise_home() == expected
    assert daemon.boardwise_home() == expected
    assert daemon.BOARDWISE_HOME == expected
    assert config.config_path() == expected / "config.json"
    assert daemon.token_path() == expected / "token"
    assert daemon.connector_token_path() == expected / "connector-token"
    assert daemon.audit_dir() == expected / "audit"
    assert autostart.log_dir() == expected / "log"
    assert autostart.stamp_path() == expected / autostart.START_STAMP_NAME


def test_a_tilde_and_a_literal_spelling_of_one_home_agree(tmp_path, monkeypatch):
    profile = tmp_path / "profile-615"
    _set_user_home(monkeypatch, profile)

    monkeypatch.setenv("BOARDWISE_HOME", "~/bw")
    from_tilde = (home.boardwise_home(), config.boardwise_home(), daemon.boardwise_home())

    monkeypatch.setenv("BOARDWISE_HOME", str(profile / "bw"))
    from_literal = (home.boardwise_home(), config.boardwise_home(), daemon.boardwise_home())

    assert from_tilde == from_literal == (profile / "bw",) * 3


# --------------------------------------------------------------------------
# 2. `~` does not legalise relative paths
# --------------------------------------------------------------------------


def test_a_plain_relative_home_is_still_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for spelling in ("bw", "data/bw", "./bw", "bw/../other"):
        monkeypatch.setenv("BOARDWISE_HOME", spelling)
        for reader in (home.boardwise_home, config.boardwise_home, daemon.boardwise_home):
            with pytest.raises(BoardwiseHomeError):
                reader()
        assert not (tmp_path / "bw").exists(), spelling
        assert not (tmp_path / "data").exists(), spelling
    assert Path.cwd() == tmp_path


# --------------------------------------------------------------------------
# 3. An unresolvable `~` is the named refusal, never the working directory
# --------------------------------------------------------------------------


def test_an_unresolvable_tilde_user_is_named_not_the_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # A profile whose basename is not the current user's name: the platform
    # cannot guess ``~someone`` and reports the path unchanged (pathlib raises).
    _set_user_home(monkeypatch, tmp_path / "profile-615")
    spelling = "~nosuchuser615/bw"
    monkeypatch.setenv("BOARDWISE_HOME", spelling)

    for reader in (home.boardwise_home, config.boardwise_home, daemon.boardwise_home):
        with pytest.raises(BoardwiseHomeError) as caught:
            reader()
        assert isinstance(caught.value, ConfigError)
        assert spelling in str(caught.value)
        assert "expand" in str(caught.value).lower()

    assert not (tmp_path / "~nosuchuser615").exists()
    assert not (tmp_path / "bw").exists()
    assert Path.cwd() == tmp_path


# --------------------------------------------------------------------------
# 4. The contract 586/587/598 measured stands
# --------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["", None])
def test_an_empty_or_unset_override_is_still_the_default(tmp_path, monkeypatch, value):
    _set_user_home(monkeypatch, tmp_path / "profile-615")
    if value is None:
        monkeypatch.delenv("BOARDWISE_HOME", raising=False)
    else:
        monkeypatch.setenv("BOARDWISE_HOME", value)

    expected = tmp_path / "profile-615" / ".boardwise"
    assert home.boardwise_home() == expected
    assert config.boardwise_home() == expected
    assert daemon.boardwise_home() == expected
    assert daemon.BOARDWISE_HOME == expected
    assert config.config_path() == expected / "config.json"


def test_the_environment_is_read_on_every_call(tmp_path, monkeypatch):
    first = tmp_path / "first-profile"
    second = tmp_path / "second-profile"

    _set_user_home(monkeypatch, first)
    assert home.boardwise_home() == first / ".boardwise"

    _set_user_home(monkeypatch, second)
    assert home.boardwise_home() == second / ".boardwise"

    monkeypatch.setenv("BOARDWISE_HOME", "~/bw")
    assert home.boardwise_home() == second / "bw"
    assert daemon.BOARDWISE_HOME == second / "bw"

    monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path / "explicit"))
    assert config.boardwise_home() == tmp_path / "explicit"


def test_an_absolute_home_is_returned_as_written(tmp_path, monkeypatch):
    target = tmp_path / "absolute home"
    monkeypatch.setenv("BOARDWISE_HOME", str(target))
    assert home.boardwise_home() == target
    assert str(home.boardwise_home()) == str(target)
    assert not target.exists()


@pytest.mark.parametrize("suffix", [".", " "])
def test_a_trailing_dot_or_space_is_still_refused(tmp_path, monkeypatch, suffix):
    monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path / ("bw" + suffix)))
    for reader in (home.boardwise_home, config.boardwise_home, daemon.boardwise_home):
        with pytest.raises(BoardwiseHomeError):
            reader()
    assert not (tmp_path / "bw").exists(), "no alias of the stripped name"


@pytest.mark.skipif(sys.platform != "win32", reason="\\\\?\\ is a Windows path form")
def test_an_extended_length_home_is_accepted_as_written(tmp_path, monkeypatch):
    spelling = "\\\\?\\" + str(tmp_path / "bw.")
    monkeypatch.setenv("BOARDWISE_HOME", spelling)
    assert home.boardwise_home() == Path(spelling)
    assert daemon.token_path() == Path(spelling) / "token"
