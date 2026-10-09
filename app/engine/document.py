"""Document conversion via DSH LibreOffice Kit (spec §4.5 rev 3)."""
import os
import shutil
import threading
import uuid
from pathlib import Path

from app.engine.errors import ToolMissing, UnsupportedFormat

# Support matrix (spec §4.5 rev 3 + PDF extension):
# - LibreOffice Kit capabilities for office formats (measured)
# - pdf source handled in-process by PyMuPDF/pdf2docx
_DOC_MATRIX = {
    ("docx", "pdf"), ("docx", "docx"), ("docx", "odt"), ("docx", "txt"),
    ("odt", "pdf"), ("odt", "docx"), ("odt", "odt"), ("odt", "txt"),
    ("xlsx", "pdf"), ("xlsx", "xlsx"), ("xlsx", "csv"),
    ("pptx", "pdf"), ("pptx", "pptx"),
    ("pdf", "docx"), ("pdf", "txt"),
}


def doc_supported(src_ext: str, tgt_ext: str) -> bool:
    return (src_ext.lower(), tgt_ext.lower()) in _DOC_MATRIX


def build_kit_args(node: str, cli: str, src: str, out: str) -> list[str]:
    return [node, cli, "convert", "--input", src, "--output", out]


def _write_minimal_docx(paragraphs: list[str], path: str) -> None:
    """Write a minimal OOXML .docx with the given paragraphs (stdlib only)."""
    import zipfile
    from xml.sax.saxutils import escape

    body = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{escape(t)}</w:t></w:r></w:p>'
        for t in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}<w:sectPr/></w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/_rels/document.xml.rels", doc_rels)


class DocConverter:
    """Single-instance document converter backed by LibreOffice Kit."""

    _lock = threading.Lock()

    def __init__(self, node_path: str, cli_path: str, stop_event=None):
        self._node = node_path
        self._cli = cli_path
        self._stop = stop_event

    def convert(self, job) -> None:
        src_ext = Path(job.src_path).suffix.lower().lstrip(".")
        tgt_ext = job.target_fmt.lower()
        if not doc_supported(src_ext, tgt_ext):
            raise UnsupportedFormat(
                f"document conversion {src_ext} -> {tgt_ext} not supported"
            )
        if src_ext == "pdf":
            return self._convert_pdf(job, tgt_ext)
        if not self._node or not self._cli:
            raise ToolMissing("LibreOffice Kit 路径未配置（config.json 的 kit_node/kit_cli）")
        tmp_dir = Path(job.final_path).parent / f".doc-tmp-{uuid.uuid4().hex}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_out = tmp_dir / f"out.{tgt_ext}"
        cmd = build_kit_args(self._node, self._cli, job.src_path, str(tmp_out))
        from app.engine.runner import run_tool

        with self._lock:
            try:
                run_tool(cmd, str(tmp_dir), stop_event=self._stop)
                if not tmp_out.exists():
                    raise UnsupportedFormat(
                        f"kit did not produce {tmp_out.name}"
                    )
                os.replace(str(tmp_out), job.final_path)
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _convert_pdf(self, job, tgt_ext: str) -> None:
        """In-process PDF conversion: PyMuPDF text extraction, python-docx writer."""
        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            raise ToolMissing("PDF 转换组件缺失（PyMuPDF 未安装）") from e
        part = f"{job.final_path}.part.{uuid.uuid4().hex}{Path(job.final_path).suffix}"
        try:
            if tgt_ext == "txt":
                doc = fitz.open(job.src_path)
                try:
                    text = "\n\n".join(page.get_text() for page in doc)
                finally:
                    doc.close()
                Path(part).write_text(text, encoding="utf-8")
            else:  # docx：文本流还原（段落级，最小 OOXML，Word/WPS 可打开）
                src = fitz.open(job.src_path)
                try:
                    paragraphs = []
                    for page in src:
                        blocks = sorted(
                            (b for b in page.get_text("blocks") if str(b[4]).strip()),
                            key=lambda b: (round(b[1], 1), b[0]),
                        )
                        paragraphs.extend(str(b[4]).strip() for b in blocks)
                    _write_minimal_docx(paragraphs, part)
                finally:
                    src.close()
            if not Path(part).exists():
                raise UnsupportedFormat(f"pdf converter did not produce {Path(part).name}")
            os.replace(part, job.final_path)
        except BaseException:
            try:
                os.unlink(part)
            except OSError:
                pass
            raise
