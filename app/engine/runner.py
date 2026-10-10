"""Subprocess executor: run tools, capture stderr tail, stop process trees (spec §7)."""
import collections
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass

from app.engine.errors import ConversionFailed, DiskFull, PermissionDenied

STDERR_TAIL_LINES = 20
_DISK_FULL_MARKERS = (
    "no space left",
    "disk full",
    "not enough space",
    "磁盘空间不足",
    "空间不足",
)
_PERMISSION_MARKERS = (
    "permission denied",
    "access is denied",
    "拒绝访问",
    "没有权限",
)


class Cancelled(Exception):
    """Internal signal: conversion stopped via stop_event."""


@dataclass
class ToolResult:
    exit_code: int
    stderr_tail: str


def stderr_tail(lines: list[str], n: int = STDERR_TAIL_LINES) -> str:
    return "\n".join(lines[-n:])


def _classify_failure(tail: str, exit_code: int) -> ConversionError:
    low = tail.lower()
    if any(m in low for m in _DISK_FULL_MARKERS):
        return DiskFull(f"tool reported disk-full: {tail}")
    if any(m in low for m in _PERMISSION_MARKERS):
        return PermissionDenied(
            f"输出路径无写入权限：{tail}（建议更换输出目录，或确认目标磁盘可写）"
        )
    return ConversionFailed(f"tool exited with code {exit_code}", exit_code, tail)


def stop_tree(proc) -> None:
    """taskkill /F /T kills the whole tree (Popen.terminate leaves orphans on Windows)."""
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
        capture_output=True,
    )


def run_tool(cmd: list[str], cwd: str, stop_event=None) -> ToolResult:
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    tail_lines = collections.deque(maxlen=STDERR_TAIL_LINES)

    def reader():
        try:
            for line in proc.stderr:
                tail_lines.append(line.rstrip("\n"))
        except Exception:
            pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    try:
        while True:
            try:
                rc = proc.wait(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                if stop_event is not None and stop_event.is_set():
                    stop_tree(proc)
                    try:
                        rc = proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        rc = proc.returncode if proc.returncode is not None else -9
                    raise Cancelled("stopped by user")
    finally:
        t.join(timeout=5)
    tail = "\n".join(tail_lines)
    if rc != 0:
        raise _classify_failure(tail, rc)
    return ToolResult(rc, tail)


def _tmp_work_dir() -> str:
    """System temp staging dir for tool outputs.

    Some AV/security products deny unknown exes (like the bundled ffmpeg)
    from writing into user folders; writing to the temp area and letting
    Python move the result sidesteps those blocks.
    """
    import tempfile

    base = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
    d = os.path.join(base, "format-factory-tmp")
    os.makedirs(d, exist_ok=True)
    return d


def atomic_output(cmd: list[str], dst: str, stop_event) -> None:
    """Run the tool with its output staged in the system temp dir, then move
    the result into place (cross-drive move = copy + delete).

    The temp name keeps the target extension so tools that pick the muxer
    from the file extension (ffmpeg) still work. dst is absolutized: a
    relative dst combined with a relative cwd would be resolved twice and
    produce a non-existent directory.
    """
    import shutil

    dst = os.path.abspath(dst)
    suffix = os.path.splitext(dst)[1]
    work = _tmp_work_dir()
    part = os.path.join(work, f"{uuid.uuid4().hex}{suffix}")
    part_cmd = cmd[:-1] + [part]
    try:
        run_tool(part_cmd, work, stop_event=stop_event)
        shutil.move(part, dst)
    except BaseException:
        try:
            os.unlink(part)
        except OSError:
            pass
        raise
