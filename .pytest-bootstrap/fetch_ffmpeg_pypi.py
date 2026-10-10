"""Fetch ffmpeg.exe + ffprobe.exe from the static-ffmpeg PyPI wheel (fast, sandbox-safe)."""
import json
import pathlib
import sys
import urllib.request
import zipfile

BASE = pathlib.Path(__file__).resolve().parent.parent
WHEELS = BASE / ".wheels"
OUT = BASE / "tools" / "ffmpeg"


def pick_wheel(urls):
    wheels = [u for u in urls if u["packagetype"] == "bdist_wheel"]
    for u in wheels:
        if "win_amd64" in u["filename"] or "win32" in u["filename"]:
            return u
    return wheels[0]


def main():
    WHEELS.mkdir(exist_ok=True)
    with urllib.request.urlopen("https://pypi.org/pypi/static-ffmpeg/json") as r:
        info = json.load(r)
    u = pick_wheel(info["urls"])
    wheel_path = WHEELS / u["filename"]
    if not wheel_path.exists():
        print(f"download {u['filename']} ...", flush=True)
        with urllib.request.urlopen(u["url"]) as r:
            wheel_path.write_bytes(r.read())
    OUT.mkdir(parents=True, exist_ok=True)
    found = {}
    with zipfile.ZipFile(wheel_path) as zf:
        for name in zf.namelist():
            low = name.lower()
            if low.endswith("ffmpeg.exe") and "ffprobe" not in low:
                found["ffmpeg.exe"] = name
            elif low.endswith("ffprobe.exe"):
                found["ffprobe.exe"] = name
        assert set(found) == {"ffmpeg.exe", "ffprobe.exe"}, f"missing bins in wheel: {found}"
        for dst, src_name in found.items():
            with zf.open(src_name) as s, open(OUT / dst, "wb") as d:
                d.write(s.read())
            print(f"extracted {dst}")
    print("OK")


if __name__ == "__main__":
    sys.exit(main())
