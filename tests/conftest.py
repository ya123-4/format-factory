"""Shared fixtures: ffmpeg/ffprobe paths and lavfi sample-media factory."""
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools" / "ffmpeg"


@pytest.fixture
def tmp_path(request):
    """Override pytest's builtin tmp_path: DSH sandbox rejects tempfile.mkdtemp
    (0o700 DACL); use plain mkdir under the workspace instead."""
    d = ROOT / ".tmp-tests" / f"{request.node.name}-{uuid.uuid4().hex[:6]}"
    d.mkdir(parents=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="session")
def ffmpeg() -> str:
    p = TOOLS / "ffmpeg.exe"
    assert p.exists(), "ffmpeg.exe missing — copy a gyan/BtbN build into tools/ffmpeg"
    return str(p)


@pytest.fixture(scope="session")
def kit_works() -> bool:
    """Probe once whether the LibreOffice Kit can spawn its backend here.

    DSH sandbox blocks Node spawn with pipe stdio (EPERM); outside the
    sandbox (real GUI runs) the Kit works. Skipped tests document this.
    """
    import subprocess

    from app.config import DEFAULTS

    node, cli = DEFAULTS["kit_node"], DEFAULTS["kit_cli"]
    if not (Path(node).exists() and Path(cli).exists()):
        return False
    src = Path(__file__).parent / "fixtures" / "hello.docx"
    out_dir = ROOT / ".tmp-tests" / "kit-probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "probe.pdf"
    try:
        r = subprocess.run(
            [node, cli, "convert", "--input", str(src), "--output", str(out)],
            capture_output=True, text=True, timeout=120,
        )
    except Exception:  # noqa: BLE001
        return False
    return r.returncode == 0 and out.exists()


@pytest.fixture(scope="session")
def make_sample_media(ffmpeg):
    """Generate 2s test material via lavfi. kind: video|audio|image."""

    def _make(kind: str, out_path) -> Path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if kind == "video":
            cmd = [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=size=128x72:rate=10",
                "-f", "lavfi", "-i", "sine=frequency=440",
                "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                str(out),
            ]
        elif kind == "audio":
            cmd = [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2",
                "-c:a", "flac", str(out),
            ]
        elif kind == "image":
            cmd = [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=size=64x64", "-frames:v", "1",
                str(out),
            ]
        else:
            raise ValueError(f"unknown kind: {kind}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        assert r.returncode == 0, f"lavfi generation failed: {r.stderr}"
        assert out.exists()
        return out

    return _make
