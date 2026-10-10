""".vdat adapter: route by magic bytes (spec §4.6).

Routing: MP4 variant -> plain media engine. HLS playlist (cosblaster style)
-> media engine, with segment-directory checks: the playlist may reference
the ORIGINAL file name (users often rename the .vdat), so refs are verified
and auto-repaired to an actually-present *.vdat_contents directory.
"""
import binascii
import re
from pathlib import Path

from app.engine.errors import FileNotFound, UnsupportedFormat
from app.engine.models import InputKind
from app.engine.probe import VdatKind, detect_vdat_magic

HEADER_HEX_BYTES = 32

_SEG_REF_RE = re.compile(r'([^/\r\n"\s]+?\.vdat_contents)/')


def _hls_segments_ready(path: Path) -> bool:
    """True when every *.vdat_contents directory referenced by the playlist exists."""
    text = path.read_text(encoding="utf-8", errors="replace")
    refs = set(_SEG_REF_RE.findall(text))
    if not refs:
        return True  # 无目录引用（裸分片文件名），交给 ffmpeg
    return all((path.parent / r).is_dir() for r in refs)


def _repair_playlist_refs(path: Path) -> bool:
    """Rewrite broken segment-dir refs to an actually-present sibling directory."""
    text = path.read_text(encoding="utf-8", errors="replace")
    refs = set(_SEG_REF_RE.findall(text))
    candidates = [d.name for d in path.parent.glob("*.vdat_contents")]
    if not refs or not candidates:
        return False
    for ref in refs:
        text = text.replace(ref + "/", candidates[0] + "/")
    path.write_text(text, encoding="utf-8")
    return True


def route_vdat(path: str, prober=None) -> InputKind:
    kind = detect_vdat_magic(path)
    if kind == VdatKind.MP4_VARIANT:
        return InputKind.VIDEO
    if kind == VdatKind.HLS_PLAYLIST:
        p = Path(path)
        if _hls_segments_ready(p) or _repair_playlist_refs(p):
            return InputKind.VIDEO
        raise FileNotFound(
            f"HLS 分片目录缺失：请把 <文件名>.vdat_contents 文件夹与 .vdat 文件放在同一目录"
            f"（清单引用的目录在 {p.parent} 下不存在）"
        )
    with open(path, "rb") as f:
        head = f.read(HEADER_HEX_BYTES)
    digest = binascii.hexlify(head).decode("ascii")
    raise UnsupportedFormat(
        f"unrecognized .vdat container (header hex: {digest})"
    )
