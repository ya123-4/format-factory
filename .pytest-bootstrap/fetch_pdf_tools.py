"""Fetch PDF-conversion deps (PyMuPDF, pdf2docx + transitive deps) into .pytest-libs.

Sandbox-safe wheel download + zipfile extract (no pip, no mkdtemp).
"""
import json
import pathlib
import sys
import urllib.request
import zipfile

BASE = pathlib.Path(__file__).resolve().parent.parent
LIBS = BASE / ".pytest-libs"
WHEELS = BASE / ".wheels"

PACKAGES = [
    "python-docx", "lxml",
]


def pick_wheel(urls):
    wheels = [u for u in urls if u["packagetype"] == "bdist_wheel"]
    for u in wheels:
        if "win_amd64" in u["filename"] or "py3-none-any" in u["filename"] or "py2.py3-none-any" in u["filename"]:
            return u
    return wheels[0]


def main():
    LIBS.mkdir(exist_ok=True)
    WHEELS.mkdir(exist_ok=True)
    for name in PACKAGES:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json") as r:
            info = json.load(r)
        u = pick_wheel(info["urls"])
        wheel_path = WHEELS / u["filename"]
        if not wheel_path.exists():
            print(f"download {u['filename']} ({u['size']/1e6:.1f} MB) ...", flush=True)
            with urllib.request.urlopen(u["url"]) as r:
                wheel_path.write_bytes(r.read())
        with zipfile.ZipFile(wheel_path) as zf:
            zf.extractall(LIBS)
        print(f"extracted {u['filename']}")
    print("done")


if __name__ == "__main__":
    sys.exit(main())
