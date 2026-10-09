"""Injectable media prober: pure JSON parsing + ffprobe-backed implementation.

Tests inject a fake; the FfprobeMediaProber itself is covered by
integration tests (Task 16).
"""
import json
import subprocess
from dataclasses import dataclass
from typing import Protocol

from app.engine.errors import InputCorrupt


@dataclass
class MediaMeta:
    kind: str  # "video" | "audio" | "image"
    codec: str  # e.g. "h264"
    container: str  # e.g. "mp4"
    has_audio: bool = False


class MediaProber(Protocol):
    def probe(self, path: str) -> MediaMeta: ...


def parse_ffprobe_json(text: str) -> MediaMeta | None:
    """Pure parser for `ffprobe -of json` output. None when unreadable/empty."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    streams = data.get("streams") or []
    if not streams:
        return None
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is not None:
        return MediaMeta(
            kind="video",
            codec=video.get("codec_name") or "unknown",
            container="",
            has_audio=audio is not None,
        )
    if audio is not None:
        return MediaMeta(
            kind="audio",
            codec=audio.get("codec_name") or "unknown",
            container="",
            has_audio=True,
        )
    return None


class FfprobeMediaProber:
    def __init__(self, ffprobe_path: str):
        self._ffprobe = ffprobe_path

    def probe(self, path: str) -> MediaMeta:
        cmd = [
            self._ffprobe, "-v", "error",
            "-show_entries", "stream=codec_name,codec_type",
            "-of", "json", path,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise InputCorrupt(f"ffprobe failed on {path}: {r.stderr.strip()}")
        meta = parse_ffprobe_json(r.stdout)
        if meta is None:
            raise InputCorrupt(f"ffprobe could not read streams from {path}")
        return meta
