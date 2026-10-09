"""Subprocess executor: run tools, capture stderr tail, stop process trees (spec §7)."""
import collections
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass

from app.engine.errors import ConversionFailed, DiskFull

STDERR_TAIL_LINES = 20
_DISK_FULL_MARKERS = (
    "no space left",
    "disk full",
    "not enough space",
    "磁盘空间不足",
    "空间不足",
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


def atomic_output(cmd: list[str], dst: str, stop_event) -> None:
    """Run with a .part.<uuid4> temp output, atomically replace on success.

    The temp name keeps the target extension so tools that pick the muxer
    from the file extension (ffmpeg) still work.
    """
    suffix = os.path.splitext(dst)[1]
    part = f"{dst}.part.{uuid.uuid4().hex}{suffix}"
    part_cmd = cmd[:-1] + [part]
    try:
        run_tool(part_cmd, os.path.dirname(dst) or ".", stop_event=stop_event)
        os.replace(part, dst)
    except BaseException:
        try:
            os.unlink(part)
        except OSError:
            pass
        raise
