"""OCR support for scanned PDFs (RapidOCR/onnxruntime, lazy singleton engine)."""
import threading

_engine = None
_engine_lock = threading.Lock()


def _get_engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            from rapidocr_onnxruntime import RapidOCR

            _engine = RapidOCR()
        return _engine


def ocr_available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def ocr_image(path: str) -> str:
    """OCR one image file; returns recognized text lines joined by newlines."""
    from app.engine.errors import ToolMissing

    if not ocr_available():
        raise ToolMissing("OCR 组件缺失（rapidocr-onnxruntime 未安装）")
    engine = _get_engine()
    result, _ = engine(path)
    if not result:
        return ""
    return "\n".join(str(item[1]) for item in result)


def pdf_has_text_layer(src_pdf: str, min_chars_per_page: int = 20) -> bool:
    """True when the PDF has an extractable text layer (no OCR needed)."""
    import fitz

    doc = fitz.open(src_pdf)
    try:
        total = sum(len(page.get_text().strip()) for page in doc)
        pages = max(len(doc), 1)
        return total / pages >= min_chars_per_page
    finally:
        doc.close()
