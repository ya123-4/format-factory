"""MediaProber interface tests (Task 6) — fake injection, no external tools."""
import json

from app.engine.media_prober import FfprobeMediaProber, MediaMeta, parse_ffprobe_json


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
