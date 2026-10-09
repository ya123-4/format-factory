"""Document conversion via LibreOffice headless (spec §4.5)."""
import os
import threading
import uuid
from pathlib import Path

from app.engine.errors import UnsupportedFormat

# Fixed support matrix (spec §4.5). Value = LibreOffice output filter name.
_DOC_MATRIX = {
    ("pdf", "pdf"): "writer_pdf_Export",
    ("pdf", "odt"): "writer8",
    ("pdf", "txt"): "Text (encoded)",
    ("docx", "pdf"): "writer_pdf_Export",
    ("docx", "docx"): "MS Word 2007 XML",
    ("docx", "odt"): "writer8",
    ("docx", "txt"): "Text (encoded)",
    ("odt", "pdf"): "writer_pdf_Export",
    ("odt", "docx"): "MS Word 2007 XML",
    ("odt", "odt"): "writer8",
    ("odt", "txt"): "Text (encoded)",
    ("txt", "pdf"): "writer_pdf_Export",
    ("txt", "docx"): "MS Word 2007 XML",
    ("txt", "odt"): "writer8",
    ("txt", "txt"): "Text (encoded)",
    ("xlsx", "pdf"): "calc_pdf_Export",
    ("xlsx", "txt"): "Text - txt - csv (StarCalc)",  # CSV 导出语义
    ("xlsx", "xlsx"): "Calc MS Excel 2007 XML",
    ("pptx", "pdf"): "impress_pdf_Export",
    ("pptx", "txt"): "impress_html_Export",  # 演示大纲导出语义
    ("pptx", "pptx"): "Impress MS PowerPoint 2007 XML",
}


def doc_supported(src_ext: str, tgt_ext: str) -> bool:
    return (src_ext.lower(), tgt_ext.lower()) in _DOC_MATRIX


def build_soffice_args(src: str, out_dir: str, tgt_ext: str, profile_dir: str) -> list[str]:
    filter_name = _DOC_MATRIX[(Path(src).suffix.lower().lstrip("."), tgt_ext.lower())]
    uri = Path(profile_dir).as_uri()
    return [
        "soffice",
        "--headless",
        "--convert-to", f"{tgt_ext}:{filter_name}",
        "--outdir", out_dir,
        f"-env:UserInstallation={uri}",
        src,
    ]


class DocConverter:
    """Single-instance soffice converter (spec §4.5: one instance at a time)."""

    _lock = threading.Lock()

    def __init__(self, soffice_path: str, profile_dir: str, stop_event=None):
        self._soffice = soffice_path
        self._profile = profile_dir
        self._stop = stop_event

    def convert(self, job) -> None:
        src_ext = Path(job.src_path).suffix.lower().lstrip(".")
        tgt_ext = job.target_fmt.lower()
        if not doc_supported(src_ext, tgt_ext):
            raise UnsupportedFormat(
                f"document conversion {src_ext} -> {tgt_ext} not supported"
            )
        tmp_dir = str(Path(job.final_path).parent / f".doc-tmp-{uuid.uuid4().hex}")
        os.makedirs(tmp_dir, exist_ok=True)
        args = build_soffice_args(job.src_path, tmp_dir, tgt_ext, self._profile)
        cmd = [self._soffice] + args[1:]
        from app.engine.runner import run_tool

        with self._lock:
            try:
                run_tool(cmd, tmp_dir, stop_event=self._stop)
                produced = Path(tmp_dir) / (Path(job.src_path).stem + "." + tgt_ext)
                if not produced.exists():
                    raise UnsupportedFormat(
                        f"soffice did not produce {produced.name}"
                    )
                os.replace(str(produced), job.final_path)
            finally:
                import shutil

                shutil.rmtree(tmp_dir, ignore_errors=True)
