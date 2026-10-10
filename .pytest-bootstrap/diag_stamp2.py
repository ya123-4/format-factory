"""Detect the stamp: red-pixel regions in render + red vector paths."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path("libs").resolve()))

import fitz
from PIL import Image

# 1. 渲染图红色区域
img = Image.open(".tmp-tests/stamp-page.png").convert("RGB")
w, h = img.size
red_px = 0
min_x, min_y, max_x, max_y = w, h, -1, -1
for y in range(0, h, 2):
    for x in range(0, w, 2):
        r, g, b = img.getpixel((x, y))
        if r > 150 and g < 110 and b < 110 and r - g > 60:
            red_px += 1
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
print(f"render {w}x{h}, red pixels (sampled): {red_px}")
if red_px > 0:
    print(f"red region bbox: ({min_x},{min_y})-({max_x},{max_y}) ~ {(max_x-min_x)}x{(max_y-min_y)} px")
else:
    print("no red region in render")

# 2. 矢量路径颜色统计
src = Path(r"C:\Users\ybc12\Desktop\已完成作业\中文电子成绩单.pdf")
doc = fitz.open(str(src))
page = doc[0]
from collections import Counter

colors = Counter()
red_paths = 0
for d in page.get_drawings():
    c = d.get("color")
    if c is not None:
        colors[tuple(round(v, 2) for v in c)] += 1
        r, g, b = c
        if r > 0.6 and g < 0.45 and b < 0.45:
            red_paths += 1
print("distinct stroke colors:", len(colors))
print("red-ish vector paths:", red_paths)
for c, n in colors.most_common(5):
    print("  color", c, "count", n)
doc.close()
