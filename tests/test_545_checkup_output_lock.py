"""545: one `checkup` per `--out` — the lock, every way it is released, and the rerun note.

The contract has five parts, and each has its own test below:

* two invocations naming the same ``--out`` are **serialised** — the second is
  refused with exit 2 before it reads a model, asks the daemon or writes a
  report (``test_second_concurrent_checkup_is_refused_before_anything_is_read``,
  driven by a **real second process**, not a thread);
* a sequential rerun stays legal and the console says what a rerun means —
  machine artifacts are regenerated, human content is merged by the existing
  rules (``test_sequential_rerun_is_allowed_and_says_what_changes``);
* the lock is released on an ordinary return, on a 544 write error, and on an
  exception out of the body;
* arguments the command already refuses create no lock carrier at all (545's
  negative control, next to 544's own two refusals);
* different ``--out`` directories do not block each other.

Offline and deterministic: the archive is the real ``.epro2`` fixture and no
bridge, daemon or editor is touched. The cross-process test spawns exactly one
child interpreter and always reaps it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.cli import _cmd_checkup

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = FIXTURES / "ch340_golden.epro2"

#: A second **process** that holds the same lock the command takes, and says so.
#: ``mode=crash`` makes it exit without running ``lock.release()`` — a holder that
#: dies the way a crash dies, so the next run's recovery is what is under test.
CHILD_HOLD = '''\
import os, sys, time
from pathlib import Path

src, out, ready, release, mode = sys.argv[1:6]
sys.path.insert(0, src)
from boardwise import cli

lock = cli._checkup_lock_acquire(Path(out))
Path(ready).write_text(str(os.getpid()), encoding="utf-8")
deadline = time.time() + 180.0
while time.time() < deadline and not Path(release).exists():
    time.sleep(0.05)
if mode == "crash":
    os._exit(9)
lock.release()
'''


def _args(**overrides) -> argparse.Namespace:
    base = {"file": str(GOLDEN), "project": "", "instance": "", "out": "checkup", "port": None}
    base.update(overrides)
    return argparse.Namespace(**base)


def _no_traceback(captured: "pytest.CaptureResult") -> bool:
    return "Traceback" not in captured.out and "Traceback" not in captured.err


def _start_holder(tmp_path: Path, out: Path, mode: str = "release") -> tuple[subprocess.Popen, Path]:
    """Spawn the child, wait until it really holds the lock, return (proc, release)."""
    ready = tmp_path / "holder.ready"
    release = tmp_path / "holder.release"
    script = tmp_path / "hold_lock.py"
    script.write_text(CHILD_HOLD, encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.Popen(
        [sys.executable, str(script), str(SRC), str(out), str(ready), str(release), mode],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 120.0
    while time.time() < deadline:
        if ready.is_file():
            return proc, release
        if proc.poll() is not None:
            stderr = (proc.stderr.read() if proc.stderr else b"").decode("utf-8", "replace")
            raise AssertionError(f"holder 子进程没拿到锁就退出了：{stderr}")
        time.sleep(0.05)
    proc.kill()
    raise AssertionError("holder 子进程 120s 内没有拿到锁")


def _stop_holder(proc: subprocess.Popen, release: Path) -> int:
    release.write_text("go", encoding="utf-8")
    try:
        return proc.wait(timeout=120)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=60)
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()


# --- the core contract: a real second process gets a clean refusal ----------


def test_second_concurrent_checkup_is_refused_before_anything_is_read(
    tmp_path, capsys
):
    """Another **process** holds the lock → exit 2, one sentence, nothing written.

    The refusal has to come before the model read and before the daemon tier, so
    the evidence is negative on purpose: no report, no console output of a run,
    no traceback — and the same `--out` works the instant the holder is gone.
    """
    out = tmp_path / "out"
    proc, release = _start_holder(tmp_path, out)
    try:
        assert _cmd_checkup(_args(out=str(out))) == 2
        captured = capsys.readouterr()

        assert _no_traceback(captured)
        assert captured.err.startswith("boardwise checkup:")
        assert "另一个 boardwise checkup" in captured.err, "要说清是另一个审查占着这个目录"
        assert str(out) in captured.err, "要说出哪个 --out 被占用"
        assert "没有读模型" in captured.err, "要说明拒绝发生在读模型之前"
        assert captured.out == "", "拒绝必须发生在跑审查之前：stdout 一个字符都没有"
        assert not (out / "report.json").exists(), "被拒的一轮不许写报告"
    finally:
        assert _stop_holder(proc, release) == 0, "holder 应当是正常退出并释放锁"

    # 子进程退出后，同一 --out 立刻可用（锁随进程退出释放，不靠谁去删文件）
    assert (out / ".checkup.lock").is_file(), "锁载体留着是正常的：它是锁的载体，不是锁"
    retry = _cmd_checkup(_args(out=str(out)))
    captured = capsys.readouterr()

    assert retry != 2, f"holder 走了这一轮必须能跑，实际 exit {retry}"
    assert (out / "report.json").is_file()
    assert "另一个 boardwise checkup" not in captured.err


# --- a lock that cannot be taken fails **closed** (P0: no fail-open) --------


def test_lock_carrier_failure_fails_closed(tmp_path, monkeypatch, capsys):
    """If the lock cannot be *established*, the review must not start at all.

    545's contract is mutual exclusion, so "the lock broke" is not a licence to
    run unprotected: the run is refused with exit 2 and a sentence that says the
    protection could not be built. The spy on the body is the load-bearing
    assertion — it proves no model was read, no daemon was asked, no report was
    written — and the console must not promise a normal delivery.
    """
    out = tmp_path / "out"
    started: list[argparse.Namespace] = []

    def cannot_lock(out_dir):
        raise PermissionError(13, "Permission denied", str(out_dir))

    def spy_run(args):
        started.append(args)
        raise AssertionError("锁建立失败后不许启动审查")

    monkeypatch.setattr(cli, "_checkup_lock_acquire", cannot_lock)
    monkeypatch.setattr(cli, "_cmd_checkup_run", spy_run)

    assert _cmd_checkup(_args(out=str(out))) == 2
    captured = capsys.readouterr()

    assert started == [], "锁失败必须 fail-closed：审查主体一次都不许调用"
    assert _no_traceback(captured)
    assert captured.err.startswith("boardwise checkup:")
    assert "无法建立同目录互斥保护" in captured.err, "要说清是保护没建起来，不是被占用"
    assert "本次未启动审查" in captured.err
    assert "正被另一个 boardwise checkup" not in captured.err, "这不是占用，别复用 Busy 文案"
    assert "照原样产出" not in captured.err, "不许承诺照常产出"
    assert "未启用" not in captured.err, "不许出现放行口径"
    assert captured.out == "", "拒绝必须发生在任何审查输出之前"
    assert not (out / "report.json").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows 分支用 msvcrt 做注入；POSIX 分支本机未执行")
def test_a_non_contention_lock_error_is_not_reported_as_another_checkup(
    tmp_path, monkeypatch, capsys
):
    """ENOTSUP from the lock call is a failure, not "another checkup holds it"."""
    import errno
    import msvcrt

    def broken(fd, mode, count):
        raise OSError(errno.ENOTSUP, "Operation not supported")

    monkeypatch.setattr(msvcrt, "locking", broken)

    out = tmp_path / "out"
    assert _cmd_checkup(_args(out=str(out))) == 2
    captured = capsys.readouterr()

    assert _no_traceback(captured)
    assert "无法建立同目录互斥保护" in captured.err
    assert "另一个 boardwise checkup" not in captured.err, "非竞争错误不许伪装成占用"
    assert not (out / "report.json").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows 分支用 msvcrt 做注入；POSIX 分支本机未执行")
def test_lock_try_maps_only_contention_errors_to_busy(tmp_path, monkeypatch):
    """``_checkup_lock_try``: EACCES → False (raced); ENOTSUP/EIO → raised."""
    import errno
    import msvcrt

    handle = open(tmp_path / "carrier.lock", "w+b", buffering=0)
    handle.write(b"0")
    try:
        def deny(fd, mode, count):
            raise OSError(errno.EACCES, "Permission denied")

        monkeypatch.setattr(msvcrt, "locking", deny)
        assert cli._checkup_lock_try(handle) is False, "EACCES 是竞争，转 False 由调用方变 Busy"

        for code in (errno.ENOTSUP, errno.EIO, errno.EBADF):
            def broken(fd, mode, count, code=code):
                raise OSError(code, os.strerror(code))

            monkeypatch.setattr(msvcrt, "locking", broken)
            with pytest.raises(OSError) as caught:
                cli._checkup_lock_try(handle)
            assert caught.value.errno == code, f"errno {code} 必须原样上抛，不许吞成 Busy"
    finally:
        handle.close()


# --- both return paths release the lock -------------------------------------


def test_lock_is_released_after_a_544_write_error(tmp_path, monkeypatch, capsys):
    """544's write-error exit (2) must not leave the directory refused."""
    out = tmp_path / "out"
    real_write_text = Path.write_text

    def refuse(self, *args, **kwargs):
        if self.parent == out:
            raise PermissionError(13, "Permission denied", str(self))
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", refuse)

    assert _cmd_checkup(_args(out=str(out))) == 2
    captured = capsys.readouterr()
    assert "未完整写出" in captured.err, "544 的那句话不能被 545 改掉"

    # 写盘失败之后锁必须已经释放：再取一次不能抛 Busy。
    lock = cli._checkup_lock_acquire(out)
    lock.release()


def test_lock_is_released_when_the_body_raises(tmp_path, monkeypatch):
    """An exception out of the body releases the lock through the `finally`.

    The assertion is on an **explicit** ``release`` call, not on "a new acquire
    works": CPython closes the handle while unwinding the traceback (refcount),
    which would make the weaker check pass even without the `finally` — and a
    handle kept alive by a traceback is exactly the case a crash must not depend
    on. The lock is then re-acquired to prove the carrier really is free.
    """
    out = tmp_path / "out"
    releases: list[Path] = []
    real_release = cli._CheckupOutLock.release

    def spy(lock):
        releases.append(lock.carrier)
        real_release(lock)

    monkeypatch.setattr(cli._CheckupOutLock, "release", spy)

    def boom(*args, **kwargs):
        raise RuntimeError("545 injected failure")

    monkeypatch.setattr(cli, "_write_checkup_markdown", boom)

    with pytest.raises(RuntimeError):
        _cmd_checkup(_args(out=str(out)))

    assert releases == [cli._checkup_lock_carrier(out)], "异常路径必须显式释放锁"
    lock = cli._checkup_lock_acquire(out)
    lock.release()


def test_lock_is_released_after_a_successful_run(tmp_path):
    out = tmp_path / "out"
    assert _cmd_checkup(_args(out=str(out))) != 2
    lock = cli._checkup_lock_acquire(out)
    lock.release()


def test_a_crashed_holder_does_not_refuse_the_next_run(tmp_path):
    """A holder that dies without releasing must not poison the directory.

    The child leaves through ``os._exit`` — no ``lock.release()``, no ``finally``,
    no atexit: the way a crash exits. This is why the carrier is a real OS lock
    and not "the file exists": the OS drops the lock with the process, so the
    leftover carrier is inert and the next run takes it. Nobody deletes anything
    between the two runs.
    """
    out = tmp_path / "out"
    proc, release = _start_holder(tmp_path, out, mode="crash")
    release.write_text("die", encoding="utf-8")
    proc.wait(timeout=120)
    for stream in (proc.stdout, proc.stderr):
        if stream is not None:
            stream.close()
    assert proc.returncode == 9, "子进程应当是不释放锁就退出的"
    assert (out / ".checkup.lock").is_file(), "崩溃留下的载体应当还在（它是载体，不是锁）"

    # Handle teardown after a dead process can take a moment on Windows; give the
    # OS a bounded window rather than asserting on the first millisecond.
    deadline = time.time() + 30.0
    code = 2
    while time.time() < deadline:
        code = _cmd_checkup(_args(out=str(out)))
        if code != 2:
            break
        time.sleep(0.2)
    assert code != 2, "崩溃的持有者不许永久拒绝后来者——锁随进程退出释放"
    assert (out / "report.json").is_file()


# --- a sequential rerun stays legal and is described honestly ---------------


def test_sequential_rerun_is_allowed_and_says_what_changes(tmp_path, capsys):
    """Two real `_cmd_checkup` runs into one `--out`: the second must explain itself.

    It has to say that the machine half of the delivery is regenerated and that
    human content is merged by the existing rules — a blanket "人工文件不变"
    would be false for `report.md`/`board-report.md` and for review-summary's
    machine sections, which is exactly the promise this batch refuses to make.
    """
    out = tmp_path / "out"

    first = _cmd_checkup(_args(out=str(out)))
    captured = capsys.readouterr()
    assert first != 2, f"第一轮必须能跑，实际 exit {first}"
    assert "rerun:" not in captured.out, "首轮没有旧报告，不该有重跑提示"
    report_before = json.loads((out / "report.json").read_text(encoding="utf-8"))
    intent = out / "design-intent.md"
    assert intent.is_file(), "离线路径会建 design-intent.md 模板，后面用它验合并规则"
    intent.write_text(
        intent.read_text(encoding="utf-8") + "\n<!-- 545 人工标注 -->\n", encoding="utf-8"
    )

    second = _cmd_checkup(_args(out=str(out)))
    captured = capsys.readouterr()

    assert second == first, "串行重跑的退出码不该被锁改变"
    assert _no_traceback(captured)
    assert "另一个 boardwise checkup" not in captured.err, "串行不是并发，不许拒"
    assert "rerun:" in captured.out, "重跑要有明确提示"
    assert "已重算并覆盖机器生成物" in captured.out, "要说清机器生成物会更新"
    assert "report.json" in captured.out
    assert "review-summary.md" in captured.out and "按 key 保留" in captured.out
    assert "不是原样全留" in captured.out, "不得笼统承诺所有人工内容永远不变"
    assert "<!-- 545 人工标注 -->" in intent.read_text(encoding="utf-8"), (
        "design-intent.md 已存在时只读合并，人工内容不许被覆盖"
    )
    report_after = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert set(report_after) == set(report_before), "报告 schema 不许被这一批改变"
    assert report_after["findings"] == report_before["findings"], "findings 不许变"


# --- negative control: refused arguments leave no lock carrier --------------


def test_refused_arguments_create_no_lock_carrier(tmp_path, capsys):
    """`--file` + `--project` is refused before any byte or carrier exists."""
    out = tmp_path / "never"
    assert _cmd_checkup(_args(project="test", out=str(out))) == 2
    captured = capsys.readouterr()

    assert _no_traceback(captured)
    assert "--file" in captured.err
    assert not out.exists(), "无效参数不许建出输出目录"
    assert not cli._checkup_lock_carrier(out).exists(), "无效参数一个锁文件都不许留"


def test_out_that_is_a_regular_file_creates_no_lock_carrier(tmp_path, capsys):
    """544's T-E03 path: a file at `--out` is refused, untouched, and no carrier."""
    target = tmp_path / "boardwise-out"
    target.write_bytes(b"not a directory\n")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()

    assert _cmd_checkup(_args(out=str(target))) == 2
    captured = capsys.readouterr()

    assert _no_traceback(captured)
    assert "不是目录" in captured.err
    assert target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == digest
    assert [entry.name for entry in tmp_path.iterdir()] == ["boardwise-out"], (
        "拒绝路径旁边不许冒出 .checkup.lock 或目录"
    )


# --- scope: different directories, and equivalent spellings -----------------


def test_different_out_dirs_do_not_block_each_other(tmp_path, capsys):
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    held = cli._checkup_lock_acquire(out_a)
    try:
        assert _cmd_checkup(_args(out=str(out_a))) == 2, "同一个目录要拒"
        assert _cmd_checkup(_args(out=str(out_b))) != 2, "不同目录不许互相阻塞"
        assert (out_b / "report.json").is_file()
    finally:
        held.release()
    assert "boardwise" in (out_b / "report.md").read_text(encoding="utf-8")


def test_equivalent_spellings_of_one_directory_are_one_lock(tmp_path):
    """`out` and `out/../out` are the same directory, therefore the same lock."""
    out = tmp_path / "out"
    out.mkdir()
    held = cli._checkup_lock_acquire(out)
    try:
        spelled = out / ".." / "out"
        assert cli._checkup_lock_carrier(spelled).resolve() == held.carrier.resolve()
        assert _cmd_checkup(_args(out=str(spelled))) == 2
    finally:
        held.release()
