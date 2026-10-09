"""Pure input recognition: extension classification and .vdat magic sniffing.

No external dependencies — all functions are pure (spec §4.2).
"""
from enum import Enum
from pathlib import Path

from app.engine.models import InputKind

VIDEO_EXTS = {"mp4", "mkv", "avi", "mov", "webm", "gif"}
AUDIO_EXTS = {"mp3", "wav", "flac", "m4a", "aac", "ogg"}
IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "bmp", "tiff"}
DOC_EXTS = {"pdf", "docx", "xlsx", "pptx", "odt", "txt"}


class VdatKind(Enum):
    MP4_VARIANT = "mp4_variant"
    HLS_PLAYLIST = "hls_playlist"
    OTHER = "other"
    UNKNOWN = "unknown"


def classify_extension(path: str) -> InputKind:
    ext = Path(path).suffix.lower().lstrip(".")
    if ext in VIDEO_EXTS:
        return InputKind.VIDEO
    if ext in AUDIO_EXTS:
        return InputKind.AUDIO
    if ext in IMAGE_EXTS:
        return InputKind.IMAGE
    if ext in DOC_EXTS:
        return InputKind.DOCUMENT
    return InputKind.UNKNOWN


def detect_vdat_magic(path: str) -> VdatKind:
    with open(path, "rb") as f:
        head = f.read(64)
    if len(head) >= 8 and head[4:8] == b"ftyp":
        return VdatKind.MP4_VARIANT
    if head.startswith(b"#EXTM3U"):
        # cosblaster-style: .vdat is an HLS playlist; segments live in
        # <name>.vdat_contents/ next to it.
        return VdatKind.HLS_PLAYLIST
    return VdatKind.UNKNOWN
