"""vdat adapter tests (Task 14)."""
import pytest

from app.config import Config
from app.engine import converter as converter_mod
from app.engine.errors import UnsupportedFormat
from app.engine.models import ConversionJob, InputKind, JobStatus
from app.engine.vdat import route_vdat


class _FakeProber:
    def probe(self, path):
        raise AssertionError("prober should not be needed for MP4_VARIANT")


def test_mp4_variant_routes_to_video(tmp_path):
    p = tmp_path / "rec.vdat"
    p.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 56)
    assert route_vdat(str(p), _FakeProber()) == InputKind.VIDEO


def test_hls_playlist_routes_to_video(tmp_path):
    p = tmp_path / "rec.vdat"
    p.write_bytes(b"#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:1.0,\nrec.vdat_contents/0\n")
    (tmp_path / "rec.vdat_contents").mkdir()
    (tmp_path / "rec.vdat_contents" / "0").write_bytes(b"x")
    assert route_vdat(str(p), _FakeProber()) == InputKind.VIDEO


def test_hls_playlist_missing_segments_dir_raises(tmp_path):
    from app.engine.errors import FileNotFound

    p = tmp_path / "rec.vdat"
    p.write_bytes(b"#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:1.0,\nrec.vdat_contents/0\n")
    with pytest.raises(FileNotFound) as ei:
        route_vdat(str(p), _FakeProber())
    assert "contents" in str(ei.value) or "分片" in str(ei.value)


def test_hls_renamed_vdat_with_original_dir_ok(tmp_path):
    # 用户把 .vdat 改名，但清单引用的是原文件名目录（目录还在）→ 可直接转换
    (tmp_path / "original.vdat_contents").mkdir()
    (tmp_path / "original.vdat_contents" / "0").write_bytes(b"x")
    p = tmp_path / "1.vdat"
    p.write_bytes(
        b"#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:1.0,\noriginal.vdat_contents/0\n"
    )
    assert route_vdat(str(p), _FakeProber()) == InputKind.VIDEO


def test_hls_repairs_refs_to_existing_dir(tmp_path):
    # 清单引用的目录不存在，但同目录有别的 *.vdat_contents → 自动重写清单
    (tmp_path / "actual.vdat_contents").mkdir()
    (tmp_path / "actual.vdat_contents" / "0").write_bytes(b"x")
    p = tmp_path / "1.vdat"
    p.write_bytes(
        b"#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:1.0,\noriginal.vdat_contents/0\n"
    )
    assert route_vdat(str(p), _FakeProber()) == InputKind.VIDEO
    text = p.read_text(encoding="utf-8")
    assert "actual.vdat_contents/0" in text  # 清单已重写指向实际目录


def test_hls_repairs_doubled_name_refs(tmp_path):
    # 曾被重写坏的清单：URI 文件名重复两次，磁盘目录是单重名 → 修复
    (tmp_path / "orig.vdat_contents").mkdir()
    (tmp_path / "orig.vdat_contents" / "0").write_bytes(b"x")
    p = tmp_path / "orig.vdat"
    p.write_bytes(
        b"#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:1.0,\norig orig.vdat_contents/0\n"
    )
    assert route_vdat(str(p), _FakeProber()) == InputKind.VIDEO
    text = p.read_text(encoding="utf-8")
    assert "orig orig.vdat_contents" not in text  # 双重复引用已修
    assert "orig.vdat_contents/0" in text


def test_unknown_vdat_raises_unsupported_with_hex(tmp_path):
    p = tmp_path / "rec.vdat"
    p.write_bytes(b"\x12\x34\x56\x78" + b"\x99" * 60)
    with pytest.raises(UnsupportedFormat) as ei:
        route_vdat(str(p), _FakeProber())
    assert "hex" in str(ei.value).lower() or any(
        c in str(ei.value) for c in "0123456789abcdef"
    )


class FakeEngine:
    def __init__(self):
        self.calls = []

    def __call__(self, job):
        self.calls.append(job)
        return None


def test_vdat_conversion_uses_media_engine(tmp_path):
    p = tmp_path / "rec.vdat"
    p.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 56)
    job = ConversionJob(src_path=str(p), out_dir=str(tmp_path), target_fmt="mp4")
    eng = FakeEngine()
    c = converter_mod.Converter(
        jobs=[job],
        engines={InputKind.VIDEO: eng},
        prober=None,
        config=Config(out_dir=str(tmp_path), conflict="overwrite"),
    )
    summary = c.run()
    assert job.status == JobStatus.DONE
    assert eng.calls == [job]
    assert summary.done == 1
