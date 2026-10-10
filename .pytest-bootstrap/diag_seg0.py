"""Inspect segment 0 header and playlist key lines."""
import pathlib

base = pathlib.Path(
    r"D:\新建文件夹 (2)\新建文件夹 (2)\LissAV  超级漂亮coser穿着婚纱早上来叫醒我先来一炮 无码_2180588050.vdat_contents"
)
seg0 = base / "0"
data = seg0.read_bytes()[:32]
print("segment 0 head hex:", data.hex(" "))
print("segment 0 head ascii:", repr(data[:16]))

# 检查是否存在 314
print("314 exists:", (base / "314").exists())
print("315 exists:", (base / "315").exists())

# 清单 key 行
pl = pathlib.Path(
    r"D:\新建文件夹 (2)\新建文件夹 (2)\LissAV  超级漂亮coser穿着婚纱早上来叫醒我先来一炮 无码_2180588050.vdat"
)
text = pl.read_text(encoding="utf-8", errors="replace")
print("EXT-X-KEY present:", "#EXT-X-KEY" in text)
print("EXT-X-MAP present:", "#EXT-X-MAP" in text)
# 统计分片编号
import re

uris = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
nums = sorted(int(u.rsplit("/", 1)[-1]) for u in uris)
print("segment count:", len(nums), "range:", nums[0], "..", nums[-1])
missing = [n for n in range(nums[0], nums[-1] + 1) if not (base / str(n)).exists()]
print("missing on disk:", missing[:20], "total missing:", len(missing))
