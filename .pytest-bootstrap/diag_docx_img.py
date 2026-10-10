"""Inspect the converted docx: image content and placement."""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path("libs").resolve()))

docx_path = Path(r".tmp-tests\real-verify\中文电子成绩单.docx")
with zipfile.ZipFile(docx_path) as z:
    media = [n for n in z.namelist() if n.startswith("word/media/")]
    print("media:", media)
    for m in media:
        data = z.read(m)
        print(f"{m}: {len(data)} bytes, head={data[:8].hex()}")
        if m.endswith(".png") and len(data) > 8:
            print("  PNG signature ok:", data[:8] == b"\x89PNG\r\n\x1a\n")
    xml = z.read("word/document.xml").decode("utf-8")
    import re

    drawings = re.findall(r"<w:drawing>.*?</w:drawing>", xml, re.S)
    print("drawing count in document.xml:", len(drawings))
    for d in drawings[:3]:
        # 提取图片引用和尺寸
        rids = re.findall(r'r:embed="([^"]+)"', d)
        extents = re.findall(r"<wp:extent cx=\"(\d+)\" cy=\"(\d+)\"", d)
        print("  rids:", rids, "extent(EMU):", extents)
