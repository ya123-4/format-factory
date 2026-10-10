"""Check each media image for red pixels (stamp presence)."""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path("libs").resolve()))

from PIL import Image

docx_path = Path(r".tmp-tests\real-verify\中文电子成绩单.docx")
with zipfile.ZipFile(docx_path) as z:
    for name in sorted(n for n in z.namelist() if n.startswith("word/media/")):
        import io

        img = Image.open(io.BytesIO(z.read(name))).convert("RGB")
        w, h = img.size
        red = 0
        for y in range(0, h, 4):
            for x in range(0, w, 4):
                r, g, b = img.getpixel((x, y))
                if r > 150 and g < 110 and b < 110 and r - g > 60:
                    red += 1
        print(f"{name}: {w}x{h} red-samples={red}")
