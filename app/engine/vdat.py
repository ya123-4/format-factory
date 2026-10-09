""".vdat adapter: route by magic bytes (spec §4.6).

Default routing: MP4 variant -> plain media engine. Private-container
branches are added here once a real sample reveals them.
"""
import binascii

from app.engine.errors import UnsupportedFormat
from app.engine.models import InputKind
from app.engine.probe import VdatKind, detect_vdat_magic

HEADER_HEX_BYTES = 32


def route_vdat(path: str, prober=None) -> InputKind:
    kind = detect_vdat_magic(path)
    if kind == VdatKind.MP4_VARIANT:
        return InputKind.VIDEO
    if kind == VdatKind.HLS_PLAYLIST:
        # HLS playlist: ffmpeg reads it directly; segments must be present
        # in <name>.vdat_contents/ beside the playlist (missing segments
        # surface as ffmpeg errors on conversion).
        return InputKind.VIDEO
    with open(path, "rb") as f:
        head = f.read(HEADER_HEX_BYTES)
    digest = binascii.hexlify(head).decode("ascii")
    raise UnsupportedFormat(
        f"unrecognized .vdat container (header hex: {digest})"
    )
