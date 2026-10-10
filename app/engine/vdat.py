""".vdat adapter: route by magic bytes (spec §4.6).

Routing: MP4 variant -> plain media engine. HLS playlist (cosblaster style)
-> media engine, with a friendly check that the <name>.vdat_contents/
segment directory sits beside the playlist.
"""
import binascii
from pathlib import Path

from app.engine.errors import FileNotFound, UnsupportedFormat
from app.engine.models import InputKind
from app.engine.probe import VdatKind, detect_vdat_magic

HEADER_HEX_BYTES = 32


def route_vdat(path: str, prober=None) -> InputKind:
    kind = detect_vdat_magic(path)
    if kind == VdatKind.MP4_VARIANT:
        return InputKind.VIDEO
    if kind == VdatKind.HLS_PLAYLIST:
        # HLS 播放列表：ffmpeg 直接读；分片必须与 .vdat 同目录
        seg_dir = Path(path).with_name(Path(path).name + "_contents")
        if not seg_dir.is_dir():
            raise FileNotFound(
                f"HLS 分片目录缺失：{seg_dir.name}。"
                "请把 <文件名>.vdat_contents 文件夹与 .vdat 文件放在同一目录"
            )
        return InputKind.VIDEO
    with open(path, "rb") as f:
        head = f.read(HEADER_HEX_BYTES)
    digest = binascii.hexlify(head).decode("ascii")
    raise UnsupportedFormat(
        f"unrecognized .vdat container (header hex: {digest})"
    )
