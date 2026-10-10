"""Check get_image_info for inline images (the stamp)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path("libs").resolve()))

import fitz

src = Path(r"C:\Users\ybc12\Desktop\已完成作业\中文电子成绩单.pdf")
doc = fitz.open(str(src))
page = doc[0]
infos = page.get_image_info(xrefs=True)
print(f"render image infos: {len(infos)}")
for i in infos:
    print(
        f"  xref={i.get('xref')} bbox={tuple(round(v,1) for v in i['bbox'])} "
        f"size={i.get('width')}x{i.get('height')}"
    )
doc.close()
