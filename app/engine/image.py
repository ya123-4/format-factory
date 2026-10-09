"""Image conversion via FFmpeg (spec §4.4)."""
from app.engine.runner import atomic_output

IMAGE_FORMATS = ["jpg", "png", "webp", "bmp", "tiff"]

JPG_Q = {"high": "2", "medium": "4", "low": "7"}  # -q:v, 2-31 reverse scale
WEBP_Q = {"high": "90", "medium": "80", "low": "65"}  # -quality, 0-100


def build_image_args(src: str, dst: str, tgt_fmt: str, quality: str) -> list[str]:
    args = ["-y", "-hide_banner", "-nostats", "-i", src]
    if tgt_fmt == "jpg":
        args += ["-q:v", JPG_Q[quality]]
    elif tgt_fmt == "webp":
        args += ["-quality", WEBP_Q[quality]]
    # png / bmp / tiff: lossless, no quality args
    return args + [dst]


class ImageConverter:
    def __init__(self, ffmpeg_path: str, stop_event=None, quality: str = "high"):
        self._ffmpeg = ffmpeg_path
        self._stop = stop_event
        self._quality = quality

    def convert(self, job) -> None:
        args = build_image_args(
            job.src_path, job.final_path, job.target_fmt, self._quality
        )
        atomic_output([self._ffmpeg] + args, job.final_path, self._stop)
