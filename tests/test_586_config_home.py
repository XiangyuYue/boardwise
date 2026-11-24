"""586: the configuration path and the honesty of a write (569-F-1/2/4/6).

Four answers the settings file owes a user, none of which it gave at HEAD:

* an **unwritable** home is a named refusal (``ConfigError`` / exit 2, no
  traceback, no half-written temporary file) — not an ``OSError`` out of
  ``mkdir``/``write``/``replace``;
* a ``config.json`` that **exists but is not a regular file** is an error, never
  the defaults: "there is no file" and "I cannot read the file" are different
  answers, and a run that silently fell back to ``off`` makes the user's ``on``
  a lie;
* a **relative** ``BOARDWISE_HOME`` is refused by name — it used to re-resolve
  against the current directory, so the same environment variable meant two
  different homes before and after a ``chdir``;
* a home whose final component ends in a **dot or whitespace** is refused:
  Windows strips those silently, so ``...\\home.`` and ``...\\home`` became the
  same profile under two spellings.

The legitimate spellings — an absolute path, non-ASCII characters, spaces inside
the name, UNC and ``\\\\?\\`` forms — keep working, and a *missing* settings file
still means "the defaults".
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.core.config import (
    ConfigError,
    boardwise_home,
    read_config,
    set_setting,
)

SRC = Path(__file__).resolve().parents[1] / "src"
_KEY = "review.aesthetics"
_SET = ["config", "set", _KEY, "on"]


def _run(home: str, *argv: str) -> subprocess.CompletedProcess[str]:
    """One real CLI run in a child process, the way the repro measured it."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["BOARDWISE_HOME"] = home
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from boardwise.cli import main; sys.exit(main(sys.argv[1:]))",
            *argv,
        ],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=60,
    )


# --------------------------------------------------------------------------
# F-1: an unusable home is a named refusal, not a traceback
# --------------------------------------------------------------------------


def test_a_file_where_the_home_parent_belongs_is_refused_with_exit_two(tmp_path):
    """The measured F-1 case: ``%HOME%\\..`` is a file, so ``mkdir`` fails."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    result = _run(str(blocker / "home"), *_SET)
    assert result.returncode == 2, result.stderr
    assert result.stderr.strip().startswith("boardwise config set:")
    assert "Traceback" not in result.stderr


def test_set_setting_wraps_a_write_failure_as_config_error(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        set_setting(_KEY, True, home=blocker / "home")
    assert "Traceback" not in str(caught.value)
    assert isinstance(caught.value.__cause__, OSError)


def test_a_directory_at_the_config_path_leaves_no_temporary_behind(
    capsys, tmp_path, monkeypatch
):
    home = tmp_path / "home"
    (home / "config.json").mkdir(parents=True)
    monkeypatch.setenv("BOARDWISE_HOME", str(home))
    assert cli.main(_SET) == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "boardwise config set:" in captured.err
    assert sorted(child.name for child in home.iterdir()) == ["config.json"]


# --------------------------------------------------------------------------
# F-2: a config path that exists but is not a file is an error, not defaults
# --------------------------------------------------------------------------


def test_a_config_directory_is_refused_by_get_and_show(capsys, tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "config.json").mkdir(parents=True)
    monkeypatch.setenv("BOARDWISE_HOME", str(home))

    assert cli.main(["config", "get", _KEY]) == 2
    captured = capsys.readouterr()
    assert captured.out.strip() == "", "no value may be printed for an unreadable file"
    assert "boardwise config get:" in captured.err
    assert "config.json" in captured.err

    assert cli.main(["config", "show"]) == 2
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert "boardwise config show:" in captured.err
    assert "Traceback" not in captured.err

    assert cli.main(["config", "show", "--json"]) == 2
    assert "Traceback" not in capsys.readouterr().err

    with pytest.raises(ConfigError):
        read_config(home=home)


def test_a_missing_config_still_means_the_defaults(capsys, tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("BOARDWISE_HOME", str(home))
    assert read_config(home=home) == {}
    assert cli.main(["config", "get", _KEY]) == 0
    assert capsys.readouterr().out.strip() == "off"


# --------------------------------------------------------------------------
# F-4: a relative home is refused; an absolute one does not drift on chdir
# --------------------------------------------------------------------------


def test_a_relative_home_is_refused_and_never_follows_the_working_directory(
    capsys, tmp_path, monkeypatch
):
    monkeypatch.setenv("BOARDWISE_HOME", "relative-home")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["config", "get", _KEY]) == 2
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert "relative-home" in captured.err and "absolute" in captured.err.lower()

    (tmp_path / "relative-home").mkdir()
    assert cli.main(_SET) == 2
    assert not (tmp_path / "relative-home" / "config.json").exists()

    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    assert cli.main(["config", "get", _KEY]) == 2
    assert cli.main(["config", "show"]) == 2
    assert "Traceback" not in capsys.readouterr().err
    with pytest.raises(ConfigError):
        boardwise_home()


def test_an_absolute_home_reads_the_same_settings_after_chdir(
    capsys, tmp_path, monkeypatch
):
    home = tmp_path / "home"
    monkeypatch.setenv("BOARDWISE_HOME", str(home))
    monkeypatch.chdir(tmp_path)
    assert cli.main(_SET) == 0
    capsys.readouterr()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert cli.main(["config", "get", _KEY]) == 0
    assert capsys.readouterr().out.strip() == "on"


# --------------------------------------------------------------------------
# F-6: a trailing dot or space in the home is refused at the boundary
# --------------------------------------------------------------------------


@pytest.mark.parametrize("suffix", [".", " "])
def test_a_home_whose_final_component_ends_in_a_dot_or_space_is_refused(
    capsys, tmp_path, monkeypatch, suffix
):
    monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path / ("home" + suffix)))
    for argv in (
        ["config", "get", _KEY],
        _SET,
        ["config", "show"],
    ):
        assert cli.main(argv) == 2, argv
        captured = capsys.readouterr()
        assert captured.out.strip() == ""
        assert "BOARDWISE_HOME" in captured.err
        assert "Traceback" not in captured.err
    assert not (tmp_path / "home").exists(), "no alias of the stripped name"


# --------------------------------------------------------------------------
# The legitimate spellings stay legitimate
# --------------------------------------------------------------------------


def test_dots_and_spaces_inside_the_home_name_are_not_the_edges(
    capsys, tmp_path, monkeypatch
):
    home = tmp_path / "home.v1 dir"
    monkeypatch.setenv("BOARDWISE_HOME", str(home))
    assert cli.main(_SET) == 0
    capsys.readouterr()
    assert (home / "config.json").is_file()
    assert cli.main(["config", "get", _KEY]) == 0
    assert capsys.readouterr().out.strip() == "on"


def test_a_non_ascii_home_with_spaces_still_round_trips(capsys, tmp_path, monkeypatch):
    home = tmp_path / "配置 home 目录"
    monkeypatch.setenv("BOARDWISE_HOME", str(home))
    assert cli.main(_SET) == 0
    capsys.readouterr()
    assert (home / "config.json").is_file()
    assert cli.main(["config", "get", _KEY]) == 0
    assert capsys.readouterr().out.strip() == "on"


def test_a_forward_slash_absolute_home_is_accepted(capsys, tmp_path, monkeypatch):
    home = (tmp_path / "slash home").as_posix()
    monkeypatch.setenv("BOARDWISE_HOME", home)
    assert cli.main(_SET) == 0
    capsys.readouterr()
    assert (tmp_path / "slash home" / "config.json").is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="\\\\?\\ is a Windows path form")
def test_an_extended_length_home_is_accepted(capsys, tmp_path, monkeypatch):
    target = tmp_path / "ext home"
    monkeypatch.setenv("BOARDWISE_HOME", "\\\\?\\" + str(target))
    assert cli.main(_SET) == 0
    capsys.readouterr()
    assert (target / "config.json").is_file()
    assert cli.main(["config", "get", _KEY]) == 0
    assert capsys.readouterr().out.strip() == "on"
