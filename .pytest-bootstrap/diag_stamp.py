"""Diagnose the stamp: is it a bitmap, vector drawing, or masked image?"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path("libs").resolve()))

import fitz

src = Path(r"C:\Users\ybc12\Desktop\已完成作业\中文电子成绩单.pdf")
doc = fitz.open(str(src))
page = doc[0]
print(f"page size: {page.rect}")

# 1. 渲染整页看印章
pix = page.get_pixmap(dpi=100)
out = Path(".tmp-tests/stamp-page.png")
out.parent.mkdir(exist_ok=True)
pix.save(str(out))
print(f"rendered page -> {out} ({pix.width}x{pix.height})")

# 2. 位图检查（含 smask）
images = page.get_images(full=True)
print(f"images: {len(images)}")
for img in images:
    xref, smask, w, h, bpc, cs, alt_cs, name, filt, ref = img
    print(f"  xref={xref} smask={smask} {w}x{h} bpc={bpc} cs={cs} name={name} filter={filt}")
    info = doc.extract_image(xref)
    print(f"    ext={info['ext']} size={len(info['image'])} smask_ext={info.get('smask', 0)}")

# 3. 矢量图形检查（章可能用 path 画出来）
drawings = page.get_drawings()
print(f"vector drawings: {len(drawings)}")
fills = [d for d in drawings if d.get("fill")]
strokes = [d for d in drawings if d.get("color")]
print(f"  filled paths: {len(fills)}, stroked paths: {len(strokes)}")

# 4. 页面文本概况
text = page.get_text()
print(f"page text chars: {len(text.strip())}")

# 5. annotation 检查
annots = list(page.annots() or [])
print(f"annotations: {len(annots)}")
doc.close()
