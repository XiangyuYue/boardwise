"""Hermetic smoke tests for ``tools/dsh_plugin_install.mjs``.

The profile, tarball, pnpm store and backup all live under pytest's tmp_path.
No real DSH profile is read and pnpm is forced offline: the synthetic package has
no dependencies, so the actual install path needs no network or shared store.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "dsh_plugin_install.mjs"
NAME = "boardwise-dsh"
VERSION = "9.9.9-test"


def _require_tools() -> None:
    for tool in ("node", "pnpm", "tar"):
        if shutil.which(tool) is None:
            pytest.skip(f"{tool} is required for the installer smoke test")


def _profile(tmp_path: Path) -> Path:
    profile = tmp_path / "profiles" / "desktop with space"
    profile.mkdir(parents=True)
    manifest = {
        "name": "synthetic-dsh-profile",
        "private": True,
        "dependencies": {},
        "dsh": {"profile": {"bundles": []}},
    }
    (profile / "package.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return profile


def _tarball(tmp_path: Path) -> Path:
    source = tmp_path / "tarball-source"
    source.mkdir()
    manifest = source / "package.json"
    manifest.write_text(
        json.dumps({"name": NAME, "version": VERSION}) + "\n", encoding="utf-8"
    )
    tarball = tmp_path / "boardwise-dsh test.tgz"
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(manifest, arcname="package/package.json")
    return tarball


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    home = tmp_path / "isolated-home"
    env.update({
        "CI": "1",
        "HOME": str(home),
        "USERPROFILE": str(home),
        "PNPM_HOME": str(tmp_path / "pnpm-home"),
        "npm_config_cache": str(tmp_path / "npm-cache"),
        "npm_config_store_dir": str(tmp_path / "pnpm-store"),
        "npm_config_offline": "true",
    })
    return subprocess.run(
        ["node", str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )


def _backups(profile: Path) -> list[Path]:
    return [
        target
        for base in (profile.parent, profile.parent.parent, profile)
        for target in base.glob(f"_backup_{NAME}_*")
    ]


def test_dry_run_reports_the_plan_without_writing(tmp_path: Path) -> None:
    _require_tools()
    profile = _profile(tmp_path)
    tarball = _tarball(tmp_path)
    manifest = profile / "package.json"
    before = manifest.read_bytes()

    result = _run(
        tmp_path, "--profile", str(profile), "--tarball", str(tarball), "--dry-run"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "dry-run: nothing written." in result.stdout
    assert manifest.read_bytes() == before
    assert not (profile / "node_modules").exists()
    assert _backups(profile) == []


def test_install_backs_up_registers_and_verifies_the_version(tmp_path: Path) -> None:
    _require_tools()
    profile = _profile(tmp_path)
    tarball = _tarball(tmp_path)
    original = json.loads((profile / "package.json").read_text(encoding="utf-8"))

    result = _run(tmp_path, "--profile", str(profile), "--tarball", str(tarball))

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"installed: {NAME} {VERSION}" in result.stdout
    manifest = json.loads((profile / "package.json").read_text(encoding="utf-8"))
    assert manifest["dependencies"][NAME] == f"file:{tarball.as_posix()}"
    assert manifest["dsh"]["profile"]["bundles"] == [NAME]
    installed = json.loads(
        (profile / "node_modules" / NAME / "package.json").read_text(encoding="utf-8")
    )
    assert installed["version"] == VERSION

    backups = _backups(profile)
    assert len(backups) == 1
    backup_manifest = json.loads((backups[0] / "package.json").read_text(encoding="utf-8"))
    assert backup_manifest == original
