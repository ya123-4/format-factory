"""GUI smoke tests (Task 15) — window construction, no mainloop."""
import tkinter as tk

import pytest

from app.config import Config
from app.gui.main_window import MainWindow


@pytest.fixture(scope="module")
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def _clean(root):
    for w in root.winfo_children():
        w.destroy()


def _make_window(root, tmp_path, monkeypatch):
    _clean(root)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return MainWindow(root, Config())


def test_window_constructs_and_lists_columns(root, tmp_path, monkeypatch):
    mw = _make_window(root, tmp_path, monkeypatch)
    cols = list(mw.file_list.tree["columns"])
    assert cols == ["name", "kind", "size", "format", "status"]
    assert "添加文件" in mw.toolbar_button_text()


def test_progress_callback_updates_label(root, tmp_path, monkeypatch):
    mw = _make_window(root, tmp_path, monkeypatch)
    mw.progress.set_progress(2, 4)
    assert "2/4" in mw.progress.progress_label.cget("text")


def test_file_list_add_and_targets(root, tmp_path, monkeypatch):
    mw = _make_window(root, tmp_path, monkeypatch)
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "报告.docx").write_bytes(b"x")
    mw.file_list.add_file(str(tmp_path / "a.mp4"))
    mw.file_list.add_file(str(tmp_path / "报告.docx"))
    assert len(mw.file_list.jobs()) == 2
    targets = mw.file_list.targets_for(str(tmp_path / "报告.docx"))
    assert "pdf" in targets and "xlsx" not in targets
