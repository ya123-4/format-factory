"""Convert the user's real vdat (HLS, extension-less segments) to mp4."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))
sys.path.insert(0, str(Path("libs").resolve()))

from app.config import Config
from app.engine.converter import Converter
from app.engine.media import MediaEngine
from app.engine.models import ConversionJob, InputKind

src = r"D:\新建文件夹 (2)\新建文件夹 (2)\LissAV  超级漂亮coser穿着婚纱早上来叫醒我先来一炮 无码_2180588050.vdat"
out_dir = Path(".tmp-tests/user-vdat-out")
out_dir.mkdir(parents=True, exist_ok=True)

job = ConversionJob(src_path=src, out_dir=str(out_dir), target_fmt="mp4")
media = MediaEngine(
    str(Path("tools/ffmpeg/ffmpeg.exe").resolve()), "", Config(), None
)
conv = Converter(
    jobs=[job],
    engines={InputKind.VIDEO: media.convert, InputKind.AUDIO: media.convert},
    prober=None,
    config=Config(out_dir=str(out_dir), conflict="overwrite"),
)
summary = conv.run()
print("summary:", summary)
print("status:", job.status.name)
print("error:", job.error)
out = Path(job.final_path)
print("output:", out, "exists:", out.exists())
if out.exists():
    print("size MB:", round(out.stat().st_size / 1e6, 1))
