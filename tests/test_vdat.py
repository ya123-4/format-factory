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
