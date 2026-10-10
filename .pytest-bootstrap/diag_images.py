"""Diagnose images inside a PDF and whether they can be extracted."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path("libs").resolve()))

import fitz

src = Path(r"C:\Users\ybc12\Desktop\已完成作业\中文电子成绩单.pdf")
if not src.exists():
    print("sample not found")
    sys.exit(1)

doc = fitz.open(str(src))
print(f"pages: {len(doc)}")
for pno, page in enumerate(doc):
    images = page.get_images(full=True)
    print(f"page {pno + 1}: {len(images)} image(s)")
    for img in images:
        xref = img[0]
        info = doc.extract_image(xref)
        print(
            f"  xref={xref} {info['ext']} "
            f"{info['width']}x{info['height']} bytes={len(info['image'])}"
        )
doc.close()
