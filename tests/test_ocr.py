"""OCR engine tests — text-layer detection now; recognition needs onnxruntime."""
import pytest

from app.engine.ocr import pdf_has_text_layer


def _make_pdf(tmp_path, with_text=True):
    import fitz

    out = tmp_path / "in.pdf"
    doc = fitz.open()
    page = doc.new_page()
    if with_text:
        page.insert_text((72, 72), "This is a normal text PDF page with enough characters to detect.")
    doc.save(str(out))
    doc.close()
    return out


def test_pdf_has_text_layer_true(tmp_path):
    assert pdf_has_text_layer(str(_make_pdf(tmp_path, with_text=True))) is True


def test_pdf_has_text_layer_false_for_blank(tmp_path):
    assert pdf_has_text_layer(str(_make_pdf(tmp_path, with_text=False))) is False


def _onnx_available():
    try:
        import onnxruntime  # noqa: F401
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _onnx_available(), reason="rapidocr deps not installed")
def test_ocr_image_recognizes_rendered_text(tmp_path):
    import fitz

    from app.engine.ocr import ocr_image

    pdf = tmp_path / "src.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=200)
    page.insert_text((40, 100), "OCR TEST LINE 123", fontsize=28)
    doc.save(str(pdf))
    doc.close()
    png = tmp_path / "page.png"
    src = fitz.open(str(pdf))
    try:
        src[0].get_pixmap(dpi=200).save(str(png))
    finally:
        src.close()
    text = ocr_image(str(png))
    assert "OCR" in text.upper() or "TEST" in text.upper()