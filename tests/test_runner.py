"""Subprocess runner tests (Task 9) — pure unit tests, no real tools."""
import io

import pytest

from app.engine import runner
from app.engine.errors import ConversionFailed, DiskFull
from app.engine.runner import stderr_tail


def test_stderr_tail_truncates_to_20():
    lines = [f"line{i}" for i in range(50)]
    tail = stderr_tail(lines)
    assert tail.splitlines() == [f"line{i}" for i in range(30, 50)]
    assert stderr_tail(["only"]) == "only"


class _FakeProc:
    def __init__(self, returncode=0, stderr_lines=()):
        self.returncode = returncode
        self.pid = 4242
        self.stderr = iter(stderr_lines)
        self.killed = False

    def wait(self, timeout=None):
        return self.returncode


def _patch_popen(monkeypatch, fake_proc):
    captured = {}

    def fake_popen(cmd, **kw):
        captured["cmd"] = cmd
        captured["kw"] = kw
        return fake_proc

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    return captured


def test_args_are_list_with_chinese(monkeypatch):
    fake = _FakeProc(returncode=0)
    captured = _patch_popen(monkeypatch, fake)
    result = runner.run_tool(["ff.exe", "我的 视频.mp4", "out 目录.mp4"], cwd="cwd")
    assert isinstance(captured["cmd"], list)
    assert captured["cmd"][1] == "我的 视频.mp4"
    assert result.exit_code == 0


def test_disk_full_classified(monkeypatch):
    fake = _FakeProc(returncode=1, stderr_lines=["error:", "No space left on device"])
    _patch_popen(monkeypatch, fake)
    with pytest.raises(DiskFull):
        runner.run_tool(["ff.exe", "a", "b"], cwd="cwd")


def test_permission_denied_classified(monkeypatch):
    from app.engine.errors import PermissionDenied

    fake = _FakeProc(
        returncode=1,
        stderr_lines=["C:/Users/x/Desktop/out.mp4.part.abc.mp4: Permission denied"],
    )
    _patch_popen(monkeypatch, fake)
    with pytest.raises(PermissionDenied):
        runner.run_tool(["ff.exe", "a", "b"], cwd="cwd")


def test_disk_full_chinese_message_classified(monkeypatch):
    fake = _FakeProc(returncode=1, stderr_lines=["磁盘空间不足"])
    _patch_popen(monkeypatch, fake)
    with pytest.raises(DiskFull):
        runner.run_tool(["ff.exe", "a", "b"], cwd="cwd")


def test_conversion_failed_carries_tail(monkeypatch):
    lines = [f"e{i}" for i in range(50)]
    fake = _FakeProc(returncode=1, stderr_lines=lines)
    _patch_popen(monkeypatch, fake)
    with pytest.raises(ConversionFailed) as ei:
        runner.run_tool(["ff.exe", "a", "b"], cwd="cwd")
    assert ei.value.exit_code == 1
    assert ei.value.stderr_tail.splitlines() == [f"e{i}" for i in range(30, 50)]


def test_stop_tree_uses_taskkill(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    fake = _FakeProc()
    runner.stop_tree(fake)
    assert calls[0][:4] == ["taskkill", "/F", "/T", "/PID"]
    assert calls[0][4] == "4242"


def test_atomic_output_cleans_part_on_failure(tmp_path, monkeypatch):
    dst = tmp_path / "out.mp4"

    def boom(cmd, cwd, stop_event=None):
        # 模拟工具启动并留下临时文件
        part = cmd[-1]
        open(part, "w").write("partial")
        raise ConversionFailed("boom", 1, "tail")

    monkeypatch.setattr(runner, "run_tool", boom)
    with pytest.raises(ConversionFailed):
        runner.atomic_output(["ff.exe", "-i", "a", str(dst)], str(dst), None)
    assert not list(tmp_path.glob("*.part.*"))


def test_atomic_output_moves_part_to_dst(tmp_path, monkeypatch):
    dst = tmp_path / "out.mp4"
    calls = []

    def fake_run_tool(cmd, cwd, stop_event=None):
        calls.append(cmd)
        part = cmd[-1]
        open(part, "w").write("done")

    monkeypatch.setattr(runner, "run_tool", fake_run_tool)
    runner.atomic_output(["ff.exe", "-i", "a", str(dst)], str(dst), None)
    assert dst.read_text() == "done"
    assert not list(tmp_path.glob("*.part.*"))


def test_atomic_output_part_keeps_extension(tmp_path, monkeypatch):
    dst = tmp_path / "out.mkv"
    calls = []

    def fake_run_tool(cmd, cwd, stop_event=None):
        calls.append(cmd)
        open(cmd[-1], "w").write("done")

    monkeypatch.setattr(runner, "run_tool", fake_run_tool)
    runner.atomic_output(["ff.exe", "-i", "a", str(dst)], str(dst), None)
    part = calls[0][-1]
    assert part.endswith(".mkv"), f"part must keep extension for muxer detection: {part}"


def test_atomic_output_absolutizes_relative_dst(tmp_path, monkeypatch):
    """相对 dst + 相对 cwd 会双重解析导致 ffmpeg 找不到输出目录 → 必须转绝对路径。"""
    import os

    calls = []

    def fake_run_tool(cmd, cwd, stop_event=None):
        calls.append((cmd, cwd))
        open(cmd[-1], "w").write("done")

    monkeypatch.setattr(runner, "run_tool", fake_run_tool)
    rel = os.path.relpath(str(tmp_path / "out.mp4"))
    runner.atomic_output(["ff.exe", "-i", "a", rel], rel, None)
    cmd, cwd = calls[0]
    assert os.path.isabs(cmd[-1])
    assert os.path.isabs(cwd)


def test_atomic_output_stages_in_temp_dir(tmp_path, monkeypatch):
    """工具输出先写系统 TEMP 暂存（绕开杀软对未知 exe 写用户目录的拦截），再移动到目标。"""
    import os

    fake_temp = tmp_path / "fake-temp"
    fake_temp.mkdir()
    monkeypatch.setenv("TEMP", str(fake_temp))
    calls = []

    def fake_run_tool(cmd, cwd, stop_event=None):
        calls.append((cmd, cwd))
        open(cmd[-1], "w").write("done")

    monkeypatch.setattr(runner, "run_tool", fake_run_tool)
    dst = tmp_path / "out.mp4"
    runner.atomic_output(["ff.exe", "-i", "a", str(dst)], str(dst), None)
    cmd, cwd = calls[0]
    assert str(fake_temp) in cmd[-1]  # 输出暂存在 TEMP
    assert dst.read_text() == "done"  # 已移动到目标
