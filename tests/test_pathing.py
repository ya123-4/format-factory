"""Path resolution and conflict policy tests (Task 7)."""
import pytest

from app.engine import pathing
from app.engine.errors import PermissionDenied


def test_target_filename_keeps_chinese_and_spaces():
    assert pathing.target_filename("我的 视频.mp4", "mkv") == "我的 视频.mkv"
    assert pathing.target_filename("rec 01.vdat", "mp4") == "rec 01.mp4"


def test_rename_increment(tmp_path):
    (tmp_path / "name.mp4").write_bytes(b"x")
    r1 = pathing.resolve_output_path("name.mp4", "", str(tmp_path), "rename")
    assert r1 == str(tmp_path / "name_1.mp4")
    (tmp_path / "name_1.mp4").write_bytes(b"x")
    r2 = pathing.resolve_output_path("name.mp4", "", str(tmp_path), "rename")
    assert r2 == str(tmp_path / "name_2.mp4")


def test_rename_avoids_self_overwrite(tmp_path):
    # 源=目标同一文件（mp4→mp4 同目录）→ 必须递增防自覆盖
    (tmp_path / "a.mp4").write_bytes(b"x")
    r = pathing.resolve_output_path("a.mp4", "", str(tmp_path), "rename")
    assert r == str(tmp_path / "a_1.mp4")


def test_skip_returns_none_when_exists(tmp_path):
    (tmp_path / "name.mp4").write_bytes(b"x")
    assert pathing.resolve_output_path("name.mp4", "", str(tmp_path), "skip") is None
    assert (
        pathing.resolve_output_path("other.mp4", "", str(tmp_path), "skip")
        == str(tmp_path / "other.mp4")
    )


def test_overwrite_returns_original(tmp_path):
    (tmp_path / "name.mp4").write_bytes(b"x")
    assert (
        pathing.resolve_output_path("name.mp4", "", str(tmp_path), "overwrite")
        == str(tmp_path / "name.mp4")
    )


def test_rel_subdir_joined(tmp_path):
    r = pathing.resolve_output_path(
        "rec01.mp4", "视频/旅行", str(tmp_path), "rename"
    )
    assert r == str(tmp_path / "视频" / "旅行" / "rec01.mp4")


def test_ensure_output_dir_creates_and_raises(tmp_path, monkeypatch):
    pathing.ensure_output_dir(str(tmp_path / "视频" / "旅行" / "x.mp4"))
    assert (tmp_path / "视频" / "旅行").is_dir()

    import os

    def boom(*a, **k):
        raise OSError("access denied")

    monkeypatch.setattr(os, "makedirs", boom)
    with pytest.raises(PermissionDenied):
        pathing.ensure_output_dir(str(tmp_path / "y" / "z.mp4"))
