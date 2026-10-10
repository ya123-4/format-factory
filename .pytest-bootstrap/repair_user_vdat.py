"""Repair the user's corrupted playlist with the new logic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))
sys.path.insert(0, str(Path("libs").resolve()))

from app.engine.vdat import _hls_segments_ready, _repair_playlist_refs, route_vdat

p = Path(
    r"D:\新建文件夹 (2)\新建文件夹 (2)\LissAV  超级漂亮coser穿着婚纱早上来叫醒我先来一炮 无码_2180588050.vdat"
)
print("ready before:", _hls_segments_ready(p))
print("repaired:", _repair_playlist_refs(p))
print("ready after:", _hls_segments_ready(p))
print("route:", route_vdat(str(p), None))
text = p.read_text(encoding="utf-8", errors="replace")
line = text.splitlines()[4]
print("sample line now:", line[:80])
