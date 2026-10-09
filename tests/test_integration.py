"""End-to-end integration tests (Task 16) — real ffmpeg + LibreOffice Kit."""
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from app.config import Config, DEFAULTS
from app.engine.converter import Converter, required_tools
from app.engine.document import DocConverter
from app.engine.image import ImageConverter
from app.engine.media import MediaEngine
from app.engine.models import ConversionJob, InputKind, JobStatus
from app.engine.runner import Cancelled, atomic_output

FIXTURES = Path(__file__).parent / "fixtures"


def _media_readable(ffmpeg, path) -> bool:
    r = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def _convert_one(ffmpeg, src, out_dir, fmt):
    job = ConversionJob(src_path=str(src), out_dir=str(out_dir), target_fmt=fmt)
    media = MediaEngine(ffmpeg, "", _cfg(out_dir), None)
    conv = Converter(
        jobs=[job],
        engines={InputKind.VIDEO: media.convert, InputKind.AUDIO: media.convert},
        prober=None,
        config=_cfg(out_dir),
    )
    return conv.run(), job


def _cfg(out_dir):
    from app.config import Config

    return Config(out_dir=str(out_dir), conflict="overwrite")


def test_video_mp4_to_mkv_copy(make_sample_media, ffmpeg, tmp_path):
    src = make_sample_media("video", tmp_path / "in.mp4")
    summary, job = _convert_one(ffmpeg, src, tmp_path, "mkv")
    assert summary.done == 1
    assert job.status == JobStatus.DONE
    assert Path(job.final_path).exists()
    assert _media_readable(ffmpeg, job.final_path)


def test_video_mp4_to_webm_reencode(make_sample_media, ffmpeg, tmp_path):
    src = make_sample_media("video", tmp_path / "in.mp4")
    summary, job = _convert_one(ffmpeg, src, tmp_path, "webm")
    assert summary.done == 1
    assert _media_readable(ffmpeg, job.final_path)


def test_audio_flac_to_mp3(make_sample_media, ffmpeg, tmp_path):
    src = make_sample_media("audio", tmp_path / "in.flac")
    summary, job = _convert_one(ffmpeg, src, tmp_path, "mp3")
    assert summary.done == 1
    assert _media_readable(ffmpeg, job.final_path)


def test_image_bmp_to_png_and_jpg(make_sample_media, ffmpeg, tmp_path):
    src = make_sample_media("image", tmp_path / "in.bmp")
    jobs = [
        ConversionJob(src_path=str(src), out_dir=str(tmp_path), target_fmt=fmt)
        for fmt in ("png", "jpg")
    ]
    eng = ImageConverter(ffmpeg, None, "high")
    conv = Converter(
        jobs=jobs,
        engines={InputKind.IMAGE: eng.convert},
        prober=None,
        config=_cfg(tmp_path),
    )
    summary = conv.run()
    assert summary.done == 2
    for fmt in ("png", "jpg"):
        out = tmp_path / f"in.{fmt}"
        assert out.exists() and out.stat().st_size > 0


def test_document_docx_to_pdf(tmp_path, kit_works):
    if not kit_works:
        pytest.skip("LibreOffice Kit backend blocked in DSH sandbox (spawn EPERM)")
    src = FIXTURES / "hello.docx"
    job = ConversionJob(src_path=str(src), out_dir=str(tmp_path), target_fmt="pdf")
    doc = DocConverter(DEFAULTS["kit_node"], DEFAULTS["kit_cli"], None)
    conv = Converter(
        jobs=[job],
        engines={InputKind.DOCUMENT: doc.convert},
        prober=None,
        config=_cfg(tmp_path),
    )
    summary = conv.run()
    assert summary.done == 1
    out = Path(job.final_path)
    assert out.exists() and out.stat().st_size > 0


def test_document_xlsx_to_csv(tmp_path, kit_works):
    if not kit_works:
        pytest.skip("LibreOffice Kit backend blocked in DSH sandbox (spawn EPERM)")
    src = FIXTURES / "data.xlsx"
    job = ConversionJob(src_path=str(src), out_dir=str(tmp_path), target_fmt="csv")
    doc = DocConverter(DEFAULTS["kit_node"], DEFAULTS["kit_cli"], None)
    conv = Converter(
        jobs=[job],
        engines={InputKind.DOCUMENT: doc.convert},
        prober=None,
        config=_cfg(tmp_path),
    )
    summary = conv.run()
    assert summary.done == 1
    text = Path(job.final_path).read_text(encoding="utf-8", errors="replace")
    assert "苹果" in text


def test_vdat_mp4_variant_end_to_end(make_sample_media, ffmpeg, tmp_path):
    mp4 = make_sample_media("video", tmp_path / "real.mp4")
    vdat = tmp_path / "rec01.vdat"
    vdat.write_bytes(mp4.read_bytes())
    summary, job = _convert_one(ffmpeg, vdat, tmp_path, "mp4")
    assert summary.done == 1
    assert _media_readable(ffmpeg, job.final_path)


def test_vdat_hls_playlist_end_to_end(make_sample_media, ffmpeg, tmp_path):
    # 模拟 cosblaster 布局：.vdat 是 M3U8 清单，分片在 <name>.vdat_contents/
    src = make_sample_media("video", tmp_path / "src.mp4")
    segdir = tmp_path / "play.vdat_contents"
    segdir.mkdir()
    r = subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(src), "-c", "copy",
         "-hls_time", "1", "-hls_list_size", "0",
         "-hls_segment_filename", str(segdir / "seg%d.ts"),
         str(tmp_path / "play.m3u8")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    # ffmpeg 生成的清单段引用是裸文件名；改写为 cosblaster 风格（相对清单的子目录引用）
    m3u8 = tmp_path / "play.m3u8"
    m3u8.write_text(
        m3u8.read_text(encoding="utf-8").replace(
            "seg0.ts", "play.vdat_contents/seg0.ts"
        ),
        encoding="utf-8",
    )
    vdat = tmp_path / "play.vdat"
    m3u8.replace(vdat)
    summary, job = _convert_one(ffmpeg, vdat, tmp_path, "mp4")
    assert summary.done == 1
    assert _media_readable(ffmpeg, job.final_path)


def test_vdat_hls_missing_segments_fails_cleanly(make_sample_media, ffmpeg, tmp_path):
    # 只有清单没有分片：应 FAILED（InputCorrupt/ConversionFailed），不崩溃
    vdat = tmp_path / "play.vdat"
    vdat.write_text(
        "#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:1.0,\nplay.vdat_contents/seg0.ts\n",
        encoding="utf-8",
    )
    summary, job = _convert_one(ffmpeg, vdat, tmp_path, "mp4")
    assert summary.failed == 1
    assert job.status == JobStatus.FAILED
    assert job.error


def test_folder_recursive_keeps_rel_dirs(make_sample_media, ffmpeg, tmp_path):
    inner = tmp_path / "视频" / "旅行"
    src = make_sample_media("video", inner / "rec.mp4")
    job = ConversionJob(
        src_path=str(src),
        out_dir=str(tmp_path / "输出"),
        target_fmt="mkv",
        rel_subdir="视频/旅行",
    )
    media = MediaEngine(ffmpeg, "", _cfg(tmp_path / "输出"), None)
    conv = Converter(
        jobs=[job],
        engines={InputKind.VIDEO: media.convert},
        prober=None,
        config=Config(out_dir=str(tmp_path / "输出"), conflict="overwrite"),
    )
    summary = conv.run()
    assert summary.done == 1
    assert (tmp_path / "输出" / "视频" / "旅行" / "rec.mkv").exists()


def test_skip_policy_integration(make_sample_media, ffmpeg, tmp_path):
    src = make_sample_media("video", tmp_path / "in.mp4")
    (tmp_path / "in.mkv").write_bytes(b"exists")
    job = ConversionJob(src_path=str(src), out_dir=str(tmp_path), target_fmt="mkv")
    media = MediaEngine(ffmpeg, "", _cfg(tmp_path), None)
    conv = Converter(
        jobs=[job],
        engines={InputKind.VIDEO: media.convert},
        prober=None,
        config=Config(out_dir=str(tmp_path), conflict="skip"),
    )
    summary = conv.run()
    assert summary.skipped == 1
    assert job.status == JobStatus.SKIPPED


def test_stop_interrupts_and_no_part_left(tmp_path):
    dst = tmp_path / "out.bin"
    stop = threading.Event()
    # cmd 契约：最后一个参数是输出文件（atomic_output 会替换为 .part 临时名）
    cmd = [sys.executable, "-c", "import time; time.sleep(60)", str(dst)]
    errors = []

    def worker():
        try:
            atomic_output(cmd, str(dst), stop)
        except Cancelled:
            errors.append("cancelled")

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(1.0)
    stop.set()
    t.join(timeout=40)
    assert errors == ["cancelled"]
    assert not list(tmp_path.glob("*.part.*"))
    assert not dst.exists()


def test_required_tools_doc_only():
    job = ConversionJob(src_path="a.docx", out_dir="out", target_fmt="pdf")
    assert required_tools([job]) == {"soffice"}
