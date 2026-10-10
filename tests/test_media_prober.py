"""MediaProber interface tests (Task 6) — fake injection, no external tools."""
import json

from app.engine.media_prober import (
    FfprobeMediaProber,
    FfmpegTextProber,
    MediaMeta,
    parse_ffmpeg_text,
    parse_ffprobe_json,
)


class FakeProber:
    """Test double implementing the MediaProber protocol."""

    def __init__(self, meta: MediaMeta):
        self._meta = meta
        self.calls = []

    def probe(self, path: str) -> MediaMeta:
        self.calls.append(path)
        return self._meta


def consume(prober, path: str) -> MediaMeta:
    """Minimal consumer exercising the injectable interface."""
    return prober.probe(path)


def test_fake_prober_injection():
    meta = MediaMeta(kind="video", codec="h264", container="mp4", has_audio=True)
    fake = FakeProber(meta)
    result = consume(fake, "rec01.vdat")
    assert result == meta
    assert fake.calls == ["rec01.vdat"]


def test_media_meta_fields():
    m = MediaMeta(kind="audio", codec="flac", container="flac", has_audio=True)
    assert m.kind == "audio"
    assert m.codec == "flac"
    assert m.container == "flac"
    assert m.has_audio is True


def test_parse_ffprobe_json_extracts_streams():
    payload = {
        "streams": [
            {"codec_name": "h264", "codec_type": "video"},
            {"codec_name": "aac", "codec_type": "audio"},
        ]
    }
    meta = parse_ffprobe_json(json.dumps(payload))
    assert meta.kind == "video"
    assert meta.codec == "h264"
    assert meta.has_audio is True


def test_parse_ffprobe_json_audio_only():
    payload = {"streams": [{"codec_name": "mp3", "codec_type": "audio"}]}
    meta = parse_ffprobe_json(json.dumps(payload))
    assert meta.kind == "audio"
    assert meta.codec == "mp3"
    assert meta.has_audio is True


def test_parse_ffprobe_json_empty_streams():
    assert parse_ffprobe_json(json.dumps({"streams": []})) is None
    assert parse_ffprobe_json("not json") is None


FFMPEG_STDERR_SAMPLE = """\
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'x.mp4':
  Duration: 00:00:02.00, start: 0.000000, bitrate: 98 kb/s
  Stream #0:0(und): Video: h264 (High) (avc1 / 0x31637661), yuv420p, 128x72
  Stream #0:1(und): Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz, mono
At least one output file must be specified
"""

FFMPEG_AUDIO_ONLY = """\
Input #0, flac, from 'x.flac':
  Stream #0:0: Audio: flac, 44100 Hz, mono
At least one output file must be specified
"""


def test_parse_ffmpeg_text_extracts_codecs():
    meta = parse_ffmpeg_text(FFMPEG_STDERR_SAMPLE)
    assert meta.kind == "video"
    assert meta.codec == "h264"
    assert meta.has_audio is True
    assert meta.container == "mov,mp4,m4a,3gp,3g2,mj2"


def test_parse_ffmpeg_text_hls_container():
    hls_sample = (
        "Input #0, hls,applehttp, from 'x.vdat':\n"
        "  Duration: 00:10:00.00, start: 0.000000\n"
        "  Stream #0:0: Video: h264 (High), yuv420p\n"
        "  Stream #0:1: Audio: aac (LC), 44100 Hz\n"
        "At least one output file must be specified\n"
    )
    meta = parse_ffmpeg_text(hls_sample)
    assert meta.kind == "video"
    assert meta.codec == "h264"
    assert meta.container == "hls,applehttp"


class _FakeRunner:
    """Fake subprocess.run for probe retry tests."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        return self._responses.pop(0)


def test_probe_retries_hls_with_allowed_extensions():
    import subprocess as sp

    from app.engine.media_prober import FfmpegTextProber

    fail = sp.CompletedProcess([], 1, "", "Filename extension is not a common multimedia extension... allowed_extensions... Invalid data")
    ok = sp.CompletedProcess(
        [], 0, "",
        "Input #0, hls,applehttp, from 'x':\n"
        "  Stream #0:0: Video: h264 (High), yuv420p\n"
        "At least one output file must be specified\n",
    )
    runner = _FakeRunner([fail, ok])
    prober = FfmpegTextProber("ff.exe", runner=runner)
    meta = prober.probe("x.vdat")
    assert meta.kind == "video"
    # 第二次调用带 -allowed_extensions ALL
    assert any(
        cmd[2] == "-allowed_extensions" and cmd[3] == "ALL" for cmd in runner.calls
    )


def test_parse_ffmpeg_text_audio_only():
    meta = parse_ffmpeg_text(FFMPEG_AUDIO_ONLY)
    assert meta.kind == "audio"
    assert meta.codec == "flac"
    assert meta.has_audio is True


def test_parse_ffmpeg_text_invalid():
    assert parse_ffmpeg_text("Invalid data found when processing input") is None
    assert parse_ffmpeg_text("") is None
