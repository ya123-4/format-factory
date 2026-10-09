"""Document conversion tests (Task 11, rev 3) — LibreOffice Kit matrix."""
import threading
import time
from pathlib import Path

import pytest

from app.engine.document import DocConverter, build_kit_args, doc_supported
from app.engine.errors import ToolMissing, UnsupportedFormat
from app.engine.models import ConversionJob


def test_doc_matrix_supported():
    assert doc_supported("docx", "pdf") is True
    assert doc_supported("odt", "docx") is True
    assert doc_supported("docx", "txt") is True
    assert doc_supported("xlsx", "csv") is True
    assert doc_supported("xlsx", "pdf") is True
    assert doc_supported("pptx", "pdf") is True
    # 矩阵外（Kit 实测不支持）
    assert doc_supported("txt", "pdf") is False
    assert doc_supported("pdf", "txt") is False
    assert doc_supported("docx", "xlsx") is False
    assert doc_supported("pptx", "txt") is False
    assert doc_supported("xlsx", "txt") is False
    assert doc_supported("docx", "csv") is False


def test_build_kit_args():
    args = build_kit_args("node.exe", "cli.js", "a.docx", "out.pdf")
    assert args == ["node.exe", "cli.js", "convert", "--input", "a.docx", "--output", "out.pdf"]


def test_single_instance_lock():
    lock = DocConverter._lock
    assert isinstance(lock, type(threading.Lock()))
    results = []

    def holder():
        with lock:
            results.append("held")
            time.sleep(0.4)

    t = threading.Thread(target=holder)
    t.start()
    time.sleep(0.1)
    assert results == ["held"]
    assert lock.acquire(timeout=0.2) is False  # 同一把类级锁，被持有（失败不占锁）
    t.join()


def _doc_job(tmp_path, fmt="pdf"):
    j = ConversionJob(src_path="a.docx", out_dir=str(tmp_path), target_fmt=fmt)
    j.final_path = str(tmp_path / f"a.{fmt}")
    return j


def test_convert_runs_kit_and_moves(tmp_path, monkeypatch):
    from app.engine import runner as runner_mod

    calls = []

    def fake_run_tool(cmd, cwd, stop_event=None):
        calls.append((cmd, cwd))
        Path(cmd[cmd.index("--output") + 1]).write_text("PDFDATA")

    monkeypatch.setattr(runner_mod, "run_tool", fake_run_tool)
    job = _doc_job(tmp_path)
    DocConverter("node", "cli", None).convert(job)
    assert Path(job.final_path).read_text() == "PDFDATA"
    assert not list(tmp_path.glob(".doc-tmp-*"))  # 临时目录已清理
    cmd, cwd = calls[0]
    assert cmd[:4] == ["node", "cli", "convert", "--input"]


def test_convert_no_output_raises(tmp_path, monkeypatch):
    from app.engine import runner as runner_mod

    def fake_run_tool(cmd, cwd, stop_event=None):
        return None  # Kit 没有产出文件

    monkeypatch.setattr(runner_mod, "run_tool", fake_run_tool)
    job = _doc_job(tmp_path)
    with pytest.raises(UnsupportedFormat):
        DocConverter("node", "cli", None).convert(job)
    assert not list(tmp_path.glob(".doc-tmp-*"))


def test_convert_missing_kit_paths_raises_tool_missing(tmp_path):
    job = _doc_job(tmp_path)
    with pytest.raises(ToolMissing):
        DocConverter("", "", None).convert(job)
