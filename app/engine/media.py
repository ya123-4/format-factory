"""FFmpeg argument builder, copy-compatibility matrix, media engine (spec §4.3)."""
import os
import threading

from app.config import Config
from app.engine.errors import InputCorrupt
from app.engine.media_prober import FfmpegTextProber, FfprobeMediaProber, MediaMeta

FORMAT_MAP = {
    "video": ["mp4", "mkv", "avi", "mov", "webm", "gif"],
    "audio": ["mp3", "wav", "flac", "m4a", "aac", "ogg"],
}

VIDEO_FORMATS = set(FORMAT_MAP["video"])
AUDIO_FORMATS = set(FORMAT_MAP["audio"])

CRF = {"high": "18", "medium": "23", "low": "28"}
AUDIO_BITRATE = {"high": "192k", "medium": "128k", "low": "96k"}

# Fixed matrix (spec §4.3): anything outside it is NOT copy-compatible.
_VIDEO_COPY = {
    "h264": {"mp4", "mkv", "mov"},
    "hevc": {"mp4", "mkv", "mov"},
    "av1": {"mp4", "mkv", "webm"},
    "vp9": {"mkv", "webm"},
    "vp8": {"webm"},
}
_AUDIO_COPY = {
    "mp3": {"mp3"},
    "aac": {"mp4", "m4a", "aac", "mkv"},
    "flac": {"flac"},
    "pcm_s16le": {"wav"},
    "opus": {"ogg"},
    "vorbis": {"ogg"},
}

_AUDIO_ENCODER = {
    "mp3": "libmp3lame",
    "m4a": "aac",
    "aac": "aac",
    "ogg": "libopus",
}


def copy_compatible(src_meta: MediaMeta, target_fmt: str) -> bool | None:
    """True = stream-copy ok; False = re-encode; None = codec unknown."""
    codec = (src_meta.codec or "").lower()
    if not codec or codec == "unknown":
        return None
    if src_meta.kind == "video":
        return target_fmt in _VIDEO_COPY.get(codec, set())
    if src_meta.kind == "audio":
        return target_fmt in _AUDIO_COPY.get(codec, set())
    return None


def build_media_args(
    src: str, dst: str, src_meta: MediaMeta, quality: str, copy_ok: bool
) -> list[str]:
    args = ["-y", "-hide_banner", "-nostats", "-i", src]
    if copy_ok:
        return args + ["-c", "copy", dst]
    tgt = dst.rsplit(".", 1)[-1].lower()
    if tgt in VIDEO_FORMATS:
        if tgt == "gif":
            return args + ["-vf", "fps=10,scale=320:-1", dst]
        if tgt == "webm":
            args += ["-c:v", "libvpx-vp9", "-crf", CRF[quality]]
            args += ["-c:a", "libopus", "-b:a", AUDIO_BITRATE[quality]]
            return args + [dst]
        args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", CRF[quality]]
        args += ["-c:a", "aac", "-b:a", AUDIO_BITRATE[quality]]
        return args + [dst]
    if tgt in AUDIO_FORMATS:
        if src_meta.kind == "video":
            args += ["-vn"]
        if tgt == "wav":
            return args + ["-c:a", "pcm_s16le", dst]
        if tgt == "flac":
            return args + ["-c:a", "flac", dst]
        return args + ["-c:a", _AUDIO_ENCODER[tgt], "-b:a", AUDIO_BITRATE[quality], dst]
    return args + [dst]


class MediaEngine:
    """media EngineCallable registered in the converter (spec §4.3 decision flow)."""

    def __init__(
        self,
        ffmpeg_path: str,
        ffprobe_path: str,
        config: Config,
        stop_event: threading.Event | None,
        prober=None,
        run=None,
    ):
        self._ffmpeg = ffmpeg_path
        self._prober = prober or _default_prober(ffprobe_path, ffmpeg_path)
        self._config = config
        self._stop = stop_event
        self._run = run or _default_run

    def convert(self, job) -> str | None:
        """Returns a downgrade note for the log, or None."""
        meta = self._prober.probe(job.src_path)
        if meta is None:
            raise InputCorrupt(f"cannot read media streams from {job.src_path}")
        compat = copy_compatible(meta, job.target_fmt)
        quality = self._config.media_quality
        note = None
        if compat is True:
            copy_ok = True
        elif compat is False:
            copy_ok = False
            quality = "high"
            note = f"已降级重编码：源编码 {meta.codec} 与目标容器 {job.target_fmt} 不兼容"
        else:
            copy_ok = False
            quality = "high"
            note = "源编码未知，已按高质量重编码"
        args = build_media_args(job.src_path, job.final_path, meta, quality, copy_ok)
        self._run([self._ffmpeg] + args, job.final_path, self._stop)
        return note


def _default_prober(ffprobe_path: str, ffmpeg_path: str):
    if ffprobe_path and os.path.exists(ffprobe_path):
        return FfprobeMediaProber(ffprobe_path)
    return FfmpegTextProber(ffmpeg_path)


def _default_run(cmd, dst, stop_event):
    from app.engine.runner import atomic_output

    atomic_output(cmd, dst, stop_event)
