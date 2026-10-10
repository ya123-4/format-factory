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


def _segment_uris(text: str) -> list[str]:
    """Playlist segment URIs (non-comment lines)."""
    return [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def _hls_segments_ready(path: Path) -> bool:
    """True when every referenced segment file exists on disk."""
    text = path.read_text(encoding="utf-8", errors="replace")
    uris = _segment_uris(text)
    if not uris:
        return True  # 无分片引用，交给 ffmpeg 处理
    base = path.parent
    return all((base / uri).exists() for uri in uris)


def _repair_playlist_refs(path: Path) -> bool:
    """Rewrite broken segment URIs line-by-line to an actually-present
    *.vdat_contents directory (fixes renamed files and doubled-name refs)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    uris = _segment_uris(text)
    if not uris:
        return False
    base = path.parent
    candidates = [d.name for d in base.glob("*.vdat_contents")]
    if not candidates:
        return False
    fixed_any = False
    for uri in uris:
        if (base / uri).exists():
            continue
        file_part = uri.rsplit("/", 1)[-1]
        target = next(
            (c for c in candidates if (base / c / file_part).exists()),
            None,
        )
        if target is None:
            continue
        new_uri = f"{target}/{file_part}"
        if new_uri != uri:
            text = text.replace(uri, new_uri)
            fixed_any = True
    if fixed_any:
        path.write_text(text, encoding="utf-8")
    return fixed_any


def route_vdat(path: str, prober=None) -> InputKind:
    kind = detect_vdat_magic(path)
    if kind == VdatKind.MP4_VARIANT:
        return InputKind.VIDEO
    if kind == VdatKind.HLS_PLAYLIST:
        p = Path(path)
        if not _hls_segments_ready(p):
            _repair_playlist_refs(p)
        if _hls_segments_ready(p):
            return InputKind.VIDEO
        raise FileNotFound(
            "HLS 分片缺失：清单引用的分片文件不存在。"
            "请把 <文件名>.vdat_contents 文件夹（含全部分片）与 .vdat 文件放在同一目录"
        )
    with open(path, "rb") as f:
        head = f.read(HEADER_HEX_BYTES)
    digest = binascii.hexlify(head).decode("ascii")
    raise UnsupportedFormat(
        f"unrecognized .vdat container (header hex: {digest})"
    )
