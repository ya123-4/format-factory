"""Verify vendored libs work without PYTHONPATH, then run a real pdf->docx rebuild."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path("libs").resolve()))
sys.path.insert(0, str(Path(".").resolve()))

for mod in ["fitz", "pdf2docx", "rapidocr_onnxruntime", "openpyxl", "pptx", "cv2", "onnxruntime"]:
    __import__(mod)
    print(mod, "ok")

# 真实场景：用户桌面的中文成绩单 → docx（pdf2docx 版式重建路径）
from app.config import Config
from app.engine.converter import Converter
from app.engine.document import DocConverter
from app.engine.models import ConversionJob, InputKind

src = Path(r"C:\Users\ybc12\Desktop\已完成作业\中文电子成绩单.pdf")
if not src.exists():
    print("sample not found, skip real conversion")
    sys.exit(0)
out_dir = Path(".tmp-tests/real-verify")
out_dir.mkdir(parents=True, exist_ok=True)
job = ConversionJob(src_path=str(src), out_dir=str(out_dir), target_fmt="docx")
conv = Converter(
    jobs=[job],
    engines={InputKind.DOCUMENT: DocConverter("", "", None).convert},
    prober=None,
    config=Config(out_dir=str(out_dir), conflict="overwrite"),
)
summary = conv.run()
print("summary:", summary)
print("status:", job.status.name)
print("error:", job.error)
out = Path(job.final_path)
print("output:", out, "exists:", out.exists(), "size:", out.stat().st_size if out.exists() else 0)

# 图片计数核对（普通图 + 内联印章）
if out.exists():
    import zipfile

    with zipfile.ZipFile(out) as z:
        media = [n for n in z.namelist() if n.startswith("word/media/")]
    print("docx media images:", len(media), media)
