"""Dump the drawing XML to inspect placement mode."""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path("libs").resolve()))

docx_path = Path(r".tmp-tests\real-verify\中文电子成绩单.docx")
with zipfile.ZipFile(docx_path) as z:
    xml = z.read("word/document.xml").decode("utf-8")
    import re

    drawings = re.findall(r"<w:drawing>.*?</w:drawing>", xml, re.S)
    for i, d in enumerate(drawings):
        print(f"--- drawing {i} ({len(d)} chars) ---")
        print(d[:1500])
        print("...")
