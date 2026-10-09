"""Image conversion argument tests (Task 12)."""
from app.engine.image import IMAGE_FORMATS, build_image_args


def test_jpg_quality_map():
    for quality, qv in (("high", "2"), ("medium", "4"), ("low", "7")):
        args = build_image_args("a.bmp", "b.jpg", "jpg", quality)
        i = args.index("-q:v")
        assert args[i + 1] == qv


def test_webp_quality_map():
    for quality, q in (("high", "90"), ("medium", "80"), ("low", "65")):
        args = build_image_args("a.png", "b.webp", "webp", quality)
        i = args.index("-quality")
        assert args[i + 1] == q


def test_png_has_no_quality_arg():
    args = build_image_args("a.bmp", "b.png", "png", "high")
    assert "-q:v" not in args
    assert "-quality" not in args


def test_tiff_and_bmp_lossless():
    for fmt in ("tiff", "bmp"):
        args = build_image_args("a.png", f"b.{fmt}", fmt, "low")
        assert "-q:v" not in args
        assert "-quality" not in args
        assert args[-1] == f"b.{fmt}"


def test_image_formats_list():
    assert IMAGE_FORMATS == ["jpg", "png", "webp", "bmp", "tiff"]
