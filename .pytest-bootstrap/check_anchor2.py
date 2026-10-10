"""Raw count of inline/anchor elements in converted docx."""
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path("libs").resolve()))

docx_path = Path(r".tmp-tests\real-verify\中文电子成绩单.docx")
with zipfile.ZipFile(docx_path) as z:
    xml = z.read("word/document.xml").decode("utf-8")

print("wp:anchor count:", xml.count("<wp:anchor"))
print("wp:inline count:", xml.count("<wp:inline"))
print("positionH page:", xml.count('relativeFrom="page"'))
# 打印第一个 drawing 的原始片段
m = re.search(r"<w:drawing>.*?</w:drawing>", xml, re.S)
print("first drawing:", m.group(0)[:600] if m else "NONE")
