"""One-off demo: batch-convert several formats to show real coverage."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, ".")
from app.config import Config
from app.engine.converter import Converter
from app.engine.image import ImageConverter
from app.engine.media import MediaEngine
from app.engine.models import ConversionJob, InputKind

ROOT = Path(".").resolve()
FF = str(ROOT / "tools" / "ffmpeg" / "ffmpeg.exe")
WORK = ROOT / ".tmp-tests" / "demo"
OUT = WORK / "输出"
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(exist_ok=True)


def gen(args, out):
    r = subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args + [str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return out


# 1. 素材：2 秒带音轨视频、纯音频、图片
video = gen(["-f", "lavfi", "-i", "testsrc=size=128x72:rate=10",
             "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"], WORK / "演示视频.mp4")
audio = gen(["-f", "lavfi", "-i", "sine=frequency=440", "-t", "2", "-c:a", "flac"], WORK / "歌曲.flac")
image = gen(["-f", "lavfi", "-i", "testsrc=size=64x64", "-frames:v", "1"], WORK / "照片.bmp")

jobs = [
    ConversionJob(src_path=str(video), out_dir=str(OUT), target_fmt="mkv"),
    ConversionJob(src_path=str(video), out_dir=str(OUT), target_fmt="webm"),
    ConversionJob(src_path=str(video), out_dir=str(OUT), target_fmt="gif"),
    ConversionJob(src_path=str(audio), out_dir=str(OUT), target_fmt="mp3"),
    ConversionJob(src_path=str(audio), out_dir=str(OUT), target_fmt="wav"),
    ConversionJob(src_path=str(audio), out_dir=str(OUT), target_fmt="ogg"),
    ConversionJob(src_path=str(image), out_dir=str(OUT), target_fmt="png"),
    ConversionJob(src_path=str(image), out_dir=str(OUT), target_fmt="jpg"),
    ConversionJob(src_path=str(image), out_dir=str(OUT), target_fmt="webp"),
]

media = MediaEngine(FF, "", Config(out_dir=str(OUT), conflict="overwrite"), None)
img = ImageConverter(FF, None, "high")
conv = Converter(
    jobs=jobs,
    engines={InputKind.VIDEO: media.convert, InputKind.AUDIO: media.convert, InputKind.IMAGE: img.convert},
    prober=None,
    config=Config(out_dir=str(OUT), conflict="overwrite"),
)
summary = conv.run()
print(f"SUMMARY done={summary.done} failed={summary.failed} skipped={summary.skipped}")
for j in jobs:
    out = Path(j.final_path)
    size = out.stat().st_size if out.exists() else 0
    print(f"{j.status.name:8} {Path(j.src_path).name:12} -> {j.target_fmt:5} {size/1024:8.1f} KB  {j.error or ''}")
