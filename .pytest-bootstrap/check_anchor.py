"""Check anchored image positions in the converted docx."""
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path("libs").resolve()))

docx_path = Path(r".tmp-tests\real-verify\中文电子成绩单.docx")
with zipfile.ZipFile(docx_path) as z:
    xml = z.read("word/document.xml").decode("utf-8")

anchors = re.findall(
    r"<wp:anchor.*?<wp:positionH relativeFrom=\"page\"><wp:posOffset>(\d+)</wp:posOffset></wp:positionH>"
    r"<wp:positionV relativeFrom=\"page\"><wp:posOffset>(\d+)</wp:posOffset></wp:positionV>"
    r".*?<wp:extent cx=\"(\d+)\" cy=\"(\d+)\"",
    xml, re.S,
)
print(f"anchors: {len(anchors)}")
PT = 12700
for x, y, w, h in anchors:
    print(
        f"  pos=({int(x)/PT:.1f}, {int(y)/PT:.1f})pt "
        f"size=({int(w)/PT:.1f} x {int(h)/PT:.1f})pt"
    )
print("expected: 普通图 (16.1,39.8) 63.1x87.0pt; 印章 (416.5,722.9) 119.1x119.1pt")
