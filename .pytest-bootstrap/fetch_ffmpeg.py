"""Download FFmpeg static build and place ffmpeg.exe/ffprobe.exe into tools/ffmpeg.

Sandbox-safe: plain mkdir + zipfile, no tempfile.mkdtemp.
Primary: BtbN win64-gpl; fallback: gyan.dev release essentials.
"""
import pathlib
import sys
import urllib.request
import zipfile

BASE = pathlib.Path(__file__).resolve().parent.parent
ZIP = BASE / ".wheels" / "ffmpeg.zip"
OUT = BASE / "tools" / "ffmpeg"

URLS = [
    ("btbn", "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"),
    ("gyan", "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"),
]


def download(url):
    print(f"downloading {url}", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "format-factory-bootstrap"})
    with urllib.request.urlopen(req) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        with open(ZIP, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"  {done / 1e6:.0f}/{total / 1e6:.0f} MB", flush=True)
    print("download complete", flush=True)


def extract():
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP) as zf:
        ffmpeg = None
        ffprobe = None
        for name in zf.namelist():
            low = name.lower()
            if low.endswith("/bin/ffmpeg.exe") and not low.endswith("bin/ffmpeg.exe"):
                pass
            if low.endswith("bin/ffmpeg.exe"):
                ffmpeg = name
            elif low.endswith("bin/ffprobe.exe"):
                ffprobe = name
        assert ffmpeg and ffprobe, "bin/ffmpeg.exe or ffprobe.exe not found in archive"
        for src, dst in ((ffmpeg, "ffmpeg.exe"), (ffprobe, "ffprobe.exe")):
            with zf.open(src) as s, open(OUT / dst, "wb") as d:
                d.write(s.read())
            print(f"extracted {dst}")


def main():
    if (OUT / "ffmpeg.exe").exists() and (OUT / "ffprobe.exe").exists():
        print("already present")
        return 0
    ZIP.parent.mkdir(parents=True, exist_ok=True)
    last_err = None
    for tag, url in URLS:
        try:
            download(url)
            extract()
            print("OK")
            return 0
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"{tag} failed: {e}", flush=True)
            if ZIP.exists():
                ZIP.unlink()
    print(f"all sources failed: {last_err}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
