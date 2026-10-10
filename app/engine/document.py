"""Document conversion (spec §4.5 rev 4+).

Office formats: DSH LibreOffice Kit (Node CLI).
PDF source: in-process engines — PyMuPDF extraction, pdf2docx layout
rebuild (fallback: minimal text-flow docx), PyMuPDF find_tables +
openpyxl for xlsx, PyMuPDF page rendering + python-pptx for slides,
RapidOCR for scanned pages without a text layer.
"""
import os
import shutil
import threading
import uuid
from pathlib import Path

from app.engine.errors import ToolMissing, UnsupportedFormat

# Support matrix (spec §4.5 rev 4 + extensions):
# - LibreOffice Kit capabilities for office formats (measured)
# - pdf source handled in-process
_DOC_MATRIX = {
    ("docx", "pdf"), ("docx", "docx"), ("docx", "odt"), ("docx", "txt"),
    ("odt", "pdf"), ("odt", "docx"), ("odt", "odt"), ("odt", "txt"),
    ("xlsx", "pdf"), ("xlsx", "xlsx"), ("xlsx", "csv"),
    ("pptx", "pdf"), ("pptx", "pptx"),
    ("pdf", "docx"), ("pdf", "txt"), ("pdf", "xlsx"), ("pdf", "pptx"),
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


def _fitz():
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise ToolMissing("PDF 转换组件缺失（PyMuPDF 未安装）") from e
    return fitz


class DocConverter:
    """Single-instance document converter (Kit backend + in-process PDF engines)."""

    _lock = threading.Lock()

    def __init__(self, node_path: str, cli_path: str, stop_event=None):
        self._node = node_path
        self._cli = cli_path
        self._stop = stop_event

    def convert(self, job) -> str | None:
        """Returns a note for the log (OCR/degrade), or None."""
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
        return None

    # ---------- PDF source engines ----------

    def _convert_pdf(self, job, tgt_ext: str) -> str | None:
        _fitz()
        tmp_dir = Path(job.final_path).parent / f".pdf-tmp-{uuid.uuid4().hex}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        part = f"{job.final_path}.part.{uuid.uuid4().hex}{Path(job.final_path).suffix}"
        try:
            note = None
            if tgt_ext == "txt":
                text, note = self._extract_text(job.src_path, tmp_dir)
                Path(part).write_text(text, encoding="utf-8")
            elif tgt_ext == "docx":
                note = self._pdf_to_docx(job.src_path, part, tmp_dir)
            elif tgt_ext == "xlsx":
                self._pdf_to_xlsx(job.src_path, part)
            elif tgt_ext == "pptx":
                self._pdf_to_pptx(job.src_path, part, tmp_dir)
            if not Path(part).exists():
                raise UnsupportedFormat(f"pdf converter did not produce {Path(part).name}")
            os.replace(part, job.final_path)
            return note
        except BaseException:
            try:
                os.unlink(part)
            except OSError:
                pass
            raise
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _extract_text(self, src: str, tmp_dir: Path) -> tuple[str, str | None]:
        """Text layer if present, else render pages and OCR. Returns (text, note)."""
        from app.engine.ocr import ocr_image, pdf_has_text_layer

        fitz = _fitz()
        if pdf_has_text_layer(src):
            doc = fitz.open(src)
            try:
                return "\n\n".join(page.get_text() for page in doc), None
            finally:
                doc.close()
        doc = fitz.open(src)
        try:
            chunks = []
            for i, page in enumerate(doc):
                png = tmp_dir / f"page-{i}.png"
                page.get_pixmap(dpi=200).save(str(png))
                chunks.append(ocr_image(str(png)))
            return "\n\n".join(chunks), "已启用 OCR 识别（源 PDF 无文本层）"
        finally:
            doc.close()

    def _pdf_to_docx(self, src: str, part: str, tmp_dir: Path) -> str | None:
        """pdf2docx layout rebuild; fallback to text-flow minimal docx."""
        try:
            from pdf2docx import Converter as Pdf2Docx
        except ImportError:
            text, note = self._extract_text(src, tmp_dir)
            paragraphs = [p for p in text.split("\n\n") if p.strip()]
            _write_minimal_docx(paragraphs, part)
            return "；".join(
                n for n in (note, "已降级文本流还原（pdf2docx 未安装，不重建版式）") if n
            )
        cv = Pdf2Docx(src)
        try:
            cv.convert(part)
        finally:
            cv.close()
        return None

    def _pdf_to_xlsx(self, src: str, part: str) -> None:
        """PyMuPDF find_tables -> openpyxl workbook (one sheet per table)."""
        try:
            from openpyxl import Workbook
        except ImportError as e:
            raise ToolMissing("xlsx 导出组件缺失（openpyxl 未安装）") from e
        fitz = _fitz()
        doc = fitz.open(src)
        try:
            wb = Workbook()
            wb.remove(wb.active)
            found = False
            for pno, page in enumerate(doc):
                tables = page.find_tables()
                if not tables or not tables.tables:
                    continue
                for tno, table in enumerate(tables.tables):
                    found = True
                    title = f"P{pno + 1}-T{tno + 1}"
                    ws = wb.create_sheet(title=title)
                    for row in table.extract():
                        ws.append([None if v is None else str(v) for v in row])
            if not found:
                raise UnsupportedFormat("PDF 中未检测到表格，无法转换为 xlsx")
            wb.save(part)
        finally:
            doc.close()

    def _pdf_to_pptx(self, src: str, part: str, tmp_dir: Path) -> None:
        """Text-layer pages -> editable text boxes at original coordinates;
        pages without text (scans) -> full-bleed picture slides."""
        try:
            from pptx import Presentation
        except ImportError as e:
            raise ToolMissing("pptx 导出组件缺失（python-pptx 未安装）") from e
        fitz = _fitz()
        doc = fitz.open(src)
        try:
            prs = Presentation()
            sw, sh = prs.slide_width, prs.slide_height
            blank = prs.slide_layouts[6]
            for i, page in enumerate(doc):
                slide = prs.slides.add_slide(blank)
                pw, ph = page.rect.width, page.rect.height
                scale = min(sw / pw, sh / ph)
                off_x = (sw - pw * scale) / 2
                off_y = (sh - ph * scale) / 2
                text_added = False
                for block in page.get_text("dict").get("blocks", []):
                    if block.get("type") != 0:
                        continue  # 非文本块（图片等）跳过
                    x0, y0, x1, y1 = block["bbox"]
                    lines = [
                        " ".join(s["text"] for s in line.get("spans", []))
                        for line in block.get("lines", [])
                    ]
                    text = "\n".join(ln for ln in lines if ln.strip())
                    if not text.strip():
                        continue
                    box = slide.shapes.add_textbox(
                        int(off_x + x0 * scale),
                        int(off_y + y0 * scale),
                        max(int((x1 - x0) * scale), 1000),
                        max(int((y1 - y0) * scale), 1000),
                    )
                    box.text_frame.text = text
                    text_added = True
                if not text_added:
                    # 无文本层（扫描件）：整页图片
                    png = tmp_dir / f"page-{i}.png"
                    page.get_pixmap(dpi=150).save(str(png))
                    slide.shapes.add_picture(
                        str(png),
                        int(off_x),
                        int(off_y),
                        width=int(pw * scale),
                        height=int(ph * scale),
                    )
            prs.save(part)
        finally:
            doc.close()
