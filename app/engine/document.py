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


def _count_docx_media(docx_path: str) -> int:
    import zipfile

    with zipfile.ZipFile(docx_path) as z:
        return len([n for n in z.namelist() if n.startswith("word/media/")])


def _pdf_image_inventory(src: str) -> list[dict]:
    """Every visual image in the PDF, including inline images (xref=0) that
    get_images() cannot see. Items: {'type':'extract'|'clip', 'page', 'bbox',
    plus info/data for extract}. bbox is the on-page rect in PDF points."""
    import fitz

    doc = fitz.open(src)
    try:
        items = []
        for pno, page in enumerate(doc):
            info_map = {}
            for im in page.get_image_info(xrefs=True):
                if im.get("xref"):
                    info_map[im["xref"]] = im["bbox"]
            for img in page.get_images(full=True):
                xref = img[0]
                info = doc.extract_image(xref)
                info["page"] = pno + 1
                info["bbox"] = info_map.get(xref)
                items.append(
                    {
                        "type": "extract",
                        "info": info,
                        "data": info["image"],
                        "page": pno,
                        "bbox": info_map.get(xref),
                    }
                )
            for im in page.get_image_info(xrefs=True):
                if im.get("xref") == 0:  # 内联图像：只能按位置裁剪渲染
                    items.append(
                        {
                            "type": "clip",
                            "page": pno,
                            "bbox": fitz.Rect(im["bbox"]),
                        }
                    )
        return items
    finally:
        doc.close()


def _pdf_images_missing_from_docx(src: str, docx_path: str) -> list:
    """When the docx has fewer images than the PDF, return every PDF image
    (duplicating beats dropping)."""
    items = _pdf_image_inventory(src)
    if not items:
        return []
    if len(items) > _count_docx_media(docx_path):
        return items
    return []


def _write_image_with_alpha(info: dict, data: bytes, out_path) -> None:
    """Write extracted image as PNG; merge smask (alpha channel) when present."""
    if info.get("smask"):
        import io

        from PIL import Image

        base = Image.open(io.BytesIO(data)).convert("RGB")
        alpha = Image.open(io.BytesIO(info["smask"])).convert("L")
        base.putalpha(alpha)
        base.save(str(out_path))
    elif info.get("ext") == "png":
        out_path.write_bytes(data)
    else:
        import io

        from PIL import Image

        Image.open(io.BytesIO(data)).save(str(out_path))


def _set_page_size(d, src: str) -> None:
    """Match the docx section size to the PDF page size (anchor coords depend on it)."""
    import fitz

    doc = fitz.open(src)
    try:
        page = doc[0]
        w_pt, h_pt = page.rect.width, page.rect.height
    finally:
        doc.close()
    from docx.shared import Emu

    for section in d.sections:
        section.page_width = Emu(int(w_pt * 12700))
        section.page_height = Emu(int(h_pt * 12700))


def _all_paragraphs(d):
    """Every paragraph in the document, including those inside tables."""
    for p in d.paragraphs:
        yield p
    for table in d.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p


def _strip_drawings(paragraph) -> None:
    """Remove every <w:drawing> from a paragraph's runs."""
    from docx.oxml.ns import qn

    for run in paragraph.runs:
        for drawing in run._r.findall(qn("w:drawing")):
            run._r.remove(drawing)


def _page_anchor_map(d, src: str) -> dict:
    """Map PDF page index -> docx paragraph to anchor that page's images to."""
    import fitz

    doc = fitz.open(src)
    try:
        first_lines = []
        for page in doc:
            first = ""
            for ln in page.get_text().splitlines():
                t = ln.strip()
                if t:
                    first = t[:24]
                    break
            first_lines.append(first)
    finally:
        doc.close()
    paras = d.paragraphs
    anchors = {}
    for pno, first in enumerate(first_lines):
        if not first:
            continue
        for para in paras:
            ptext = para.text.strip()
            if len(ptext) >= 4 and (ptext.startswith(first[:8]) or first[:8] in ptext[:60]):
                anchors[pno] = para
                break
    fallback = paras[0] if paras else None
    last = fallback
    for pno in range(len(first_lines)):
        if pno in anchors:
            last = anchors[pno]
        else:
            anchors[pno] = last
    return anchors


def _clip_dpi(page, bbox) -> int:
    """Render dpi for an inline image: match its native pixel density."""
    import fitz

    best = 300
    for im in page.get_image_info(xrefs=True):
        r = fitz.Rect(im["bbox"])
        if r.intersects(bbox):
            w_px = im.get("width", 0)
            if w_px and r.width > 0:
                dpi = w_px / r.width * 72
                best = max(best, int(min(dpi, 400)))
    return best


def _insert_anchored_picture(d, para, img_path, x_emu, y_emu, w_emu, h_emu) -> None:
    """Insert a picture floating at absolute page coordinates (wp:anchor)."""
    from docx.oxml.ns import qn
    from lxml import etree

    run = para.add_run()
    run.add_picture(str(img_path), width=w_emu, height=h_emu)
    drawing = run._r.find(qn("w:drawing"))
    if drawing is None:
        return
    inline = drawing.find(qn("wp:inline"))
    if inline is None:
        return
    # inline -> anchor，并补绝对定位元素（OOXML 子元素顺序敏感）
    inline.tag = qn("wp:anchor")
    for attr, val in (
        ("wp:distT", "0"), ("wp:distB", "0"), ("wp:distL", "0"), ("wp:distR", "0"),
        ("wp:simplePos", "0"), ("wp:relativeHeight", "0"), ("wp:behindDoc", "0"),
        ("wp:locked", "0"), ("wp:layoutInCell", "1"), ("wp:allowOverlap", "1"),
    ):
        inline.set(qn(attr), val)
    extent = inline.find(qn("wp:extent"))
    if extent is not None:
        simple_pos = etree.SubElement(inline, qn("wp:simplePos"))
        simple_pos.set("x", "0")
        simple_pos.set("y", "0")
        pos_h = etree.SubElement(inline, qn("wp:positionH"))
        pos_h.set(qn("wp:relativeFrom"), "page")
        off_h = etree.SubElement(pos_h, qn("wp:posOffset"))
        off_h.text = str(int(x_emu))
        pos_v = etree.SubElement(inline, qn("wp:positionV"))
        pos_v.set(qn("wp:relativeFrom"), "page")
        off_v = etree.SubElement(pos_v, qn("wp:posOffset"))
        off_v.text = str(int(y_emu))
        # 保持顺序：simplePos, positionH, positionV, extent
        for el in (simple_pos, pos_h, pos_v):
            extent.addprevious(el)
        wrap = etree.SubElement(inline, qn("wp:wrapNone"))
        doc_pr = inline.find(qn("wp:docPr"))
        if doc_pr is not None:
            doc_pr.addprevious(wrap)


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
        """pdf2docx layout rebuild; fallback to text-flow minimal docx.

        Image safeguard: if the produced docx contains fewer images than the
        source PDF (pdf2docx skips some image encodings), extract them with
        PyMuPDF and append to the document end.
        """
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
        images = _pdf_image_inventory(src)
        if images:
            self._reposition_images(part, src, tmp_dir, images)
            return f"已按原位置重插 {len(images)} 张图片"
        return None

    def _reposition_images(self, docx_path: str, src: str, tmp_dir: Path, items: list) -> None:
        """Remove pdf2docx drawings and re-insert every PDF image as a page-
        anchored floating picture at its original coordinates."""
        try:
            from docx import Document
        except ImportError as e:
            raise ToolMissing("docx 图片定位组件缺失（python-docx 未安装）") from e
        fitz = _fitz()
        d = Document(docx_path)
        _set_page_size(d, src)
        # 1. 删除所有既有 drawing（pdf2docx 插入的图片统一重插，含表格内）
        for p in _all_paragraphs(d):
            _strip_drawings(p)
        # 2. 页锚点：PDF 每页首行文本 → docx 段落索引
        anchors = _page_anchor_map(d, src)
        # 3. 按页、按位置插入浮动图片
        from docx.shared import Emu

        doc = fitz.open(src)
        try:
            for idx, item in enumerate(items):
                if item["bbox"] is None:
                    continue
                page_no = item["page"]
                img_path = tmp_dir / f"repos-{idx}.png"
                if item["type"] == "extract":
                    _write_image_with_alpha(item["info"], item["data"], img_path)
                else:
                    # 内联图：按原像素密度渲染裁剪（尽量还原原图清晰度）
                    bbox = item["bbox"]
                    dpi = _clip_dpi(doc[page_no], bbox)
                    doc[page_no].get_pixmap(clip=bbox, dpi=dpi).save(str(img_path))
                x0, y0, x1, y1 = item["bbox"]
                para = anchors.get(page_no, d.paragraphs[0])
                _insert_anchored_picture(
                    d, para, img_path,
                    x_emu=Emu(int(x0 * 12700)),
                    y_emu=Emu(int(y0 * 12700)),
                    w_emu=Emu(int((x1 - x0) * 12700)),
                    h_emu=Emu(int((y1 - y0) * 12700)),
                )
        finally:
            doc.close()
        d.save(docx_path)

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
