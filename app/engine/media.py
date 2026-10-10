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


_MUXER = {
    "mp4": "mp4", "m4a": "mp4", "mov": "mov", "mkv": "matroska",
    "avi": "avi", "webm": "webm", "gif": "gif",
    "mp3": "mp3", "wav": "wav", "flac": "flac", "aac": "adts", "ogg": "ogg",
}
_MP4_FAMILY = {"mp4", "m4a"}


def _pipe_out(dst: str) -> list[str]:
    """Output spec for stdout-pipe mode: muxer name + pipe target."""
    tgt = dst.rsplit(".", 1)[-1].lower()
    muxer = _MUXER.get(tgt, tgt)
    out = ["-f", muxer]
    if tgt in _MP4_FAMILY:
        # mp4 是索引式容器，流式输出需要分片化
        out += ["-movflags", "frag_keyframe+empty_moov"]
    return out + ["pipe:1"]


def build_media_args(
    src: str,
    dst: str,
    src_meta: MediaMeta,
    quality: str,
    copy_ok: bool,
    hls_input: bool = False,
    pipe_mode: bool = False,
    aac_bsf: bool = False,
) -> list[str]:
    def _finish(encoded: list[str]) -> list[str]:
        if pipe_mode:
            return args + encoded + _pipe_out(dst)
        return args + encoded + [dst]

    args = ["-y", "-hide_banner", "-nostats"]
    if hls_input:
        # cosblaster 式 HLS 分片无扩展名，ffmpeg 安全策略默认拦截
        args += ["-allowed_extensions", "ALL"]
    args += ["-i", src]
    if copy_ok:
        enc = ["-c", "copy"]
        if aac_bsf:
            # TS/HLS 源的 ADTS AAC 流入 mp4 需要转换封装
            enc += ["-bsf:a", "aac_adtstoasc"]
        return _finish(enc)
    tgt = dst.rsplit(".", 1)[-1].lower()
    if tgt in VIDEO_FORMATS:
        if tgt == "gif":
            return _finish(["-vf", "fps=10,scale=320:-1"])
        if tgt == "webm":
            return _finish(
                ["-c:v", "libvpx-vp9", "-crf", CRF[quality],
                 "-c:a", "libopus", "-b:a", AUDIO_BITRATE[quality]]
            )
        return _finish(
            ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", CRF[quality],
             "-c:a", "aac", "-b:a", AUDIO_BITRATE[quality]]
        )
    if tgt in AUDIO_FORMATS:
        enc = []
        if src_meta.kind == "video":
            enc += ["-vn"]
        if tgt == "wav":
            enc += ["-c:a", "pcm_s16le"]
        elif tgt == "flac":
            enc += ["-c:a", "flac"]
        else:
            enc += ["-c:a", _AUDIO_ENCODER[tgt], "-b:a", AUDIO_BITRATE[quality]]
        return _finish(enc)
    return _finish([])


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
        is_hls = "hls" in (meta.container or "").lower()
        needs_aac_bsf = is_hls or "mpegts" in (meta.container or "").lower()
        args = build_media_args(
            job.src_path, job.final_path, meta, quality, copy_ok,
            hls_input=is_hls, pipe_mode=True, aac_bsf=needs_aac_bsf,
        )
        self._run([self._ffmpeg] + args, job.final_path, self._stop)
        return note


def _default_prober(ffprobe_path: str, ffmpeg_path: str):
    if ffprobe_path and os.path.exists(ffprobe_path):
        return FfprobeMediaProber(ffprobe_path)
    return FfmpegTextProber(ffmpeg_path)


def _default_run(cmd, dst, stop_event):
    from app.engine.runner import atomic_output_pipe

    atomic_output_pipe(cmd, dst, stop_event)
