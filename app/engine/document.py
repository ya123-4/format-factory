"""Document conversion via DSH LibreOffice Kit (spec §4.5 rev 3)."""
import os
import shutil
import threading
import uuid
from pathlib import Path

from app.engine.errors import ToolMissing, UnsupportedFormat

# Kit capability matrix, measured (spec §4.5 rev 3): anything outside -> UnsupportedFormat.
_DOC_MATRIX = {
    ("docx", "pdf"), ("docx", "docx"), ("docx", "odt"), ("docx", "txt"),
    ("odt", "pdf"), ("odt", "docx"), ("odt", "odt"), ("odt", "txt"),
    ("xlsx", "pdf"), ("xlsx", "xlsx"), ("xlsx", "csv"),
    ("pptx", "pdf"), ("pptx", "pptx"),
}


def doc_supported(src_ext: str, tgt_ext: str) -> bool:
    return (src_ext.lower(), tgt_ext.lower()) in _DOC_MATRIX


def build_kit_args(node: str, cli: str, src: str, out: str) -> list[str]:
    return [node, cli, "convert", "--input", src, "--output", out]


class DocConverter:
    """Single-instance document converter backed by LibreOffice Kit."""

    _lock = threading.Lock()

    def __init__(self, node_path: str, cli_path: str, stop_event=None):
        self._node = node_path
        self._cli = cli_path
        self._stop = stop_event

    def convert(self, job) -> None:
        if not self._node or not self._cli:
            raise ToolMissing("LibreOffice Kit 路径未配置（config.json 的 kit_node/kit_cli）")
        src_ext = Path(job.src_path).suffix.lower().lstrip(".")
        tgt_ext = job.target_fmt.lower()
        if not doc_supported(src_ext, tgt_ext):
            raise UnsupportedFormat(
                f"document conversion {src_ext} -> {tgt_ext} not supported"
            )
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
