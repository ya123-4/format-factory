"""Pure probe logic tests (Task 5)."""
from app.engine.models import InputKind
from app.engine.probe import VdatKind, classify_extension, detect_vdat_magic


def test_classify_known_extensions():
    assert classify_extension("a.mp4") == InputKind.VIDEO
    assert classify_extension("a.mkv") == InputKind.VIDEO
    assert classify_extension("a.mp3") == InputKind.AUDIO
    assert classify_extension("a.flac") == InputKind.AUDIO
    assert classify_extension("a.png") == InputKind.IMAGE
    assert classify_extension("a.pdf") == InputKind.DOCUMENT
    assert classify_extension("a.docx") == InputKind.DOCUMENT


def test_classify_case_insensitive():
    assert classify_extension("A.MP4") == InputKind.VIDEO
    assert classify_extension("a.Mp3") == InputKind.AUDIO


def test_classify_vdat_is_unknown():
    assert classify_extension("a.vdat") == InputKind.UNKNOWN


def test_classify_unknown_ext():
    assert classify_extension("a.xyz") == InputKind.UNKNOWN
    assert classify_extension("noext") == InputKind.UNKNOWN


def test_detect_vdat_mp4_variant(tmp_path):
    p = tmp_path / "rec.vdat"
    p.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 56)
    assert detect_vdat_magic(str(p)) == VdatKind.MP4_VARIANT


def test_detect_vdat_unknown(tmp_path):
    p = tmp_path / "rec.vdat"
    p.write_bytes(b"\x12\x34\x56\x78" + b"\x99" * 60)
    assert detect_vdat_magic(str(p)) == VdatKind.UNKNOWN
