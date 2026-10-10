"""Fetch document/OCR deps into .pytest-libs (sandbox-safe wheel download + extract).

Adds: pdf2docx (layout rebuild), RapidOCR (onnxruntime, scanned PDFs),
openpyxl (xlsx writing), python-pptx+Pillow (pptx rendering), shared deps.
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
    "opencv-python-headless",   # pdf2docx + rapidocr shared
    "onnxruntime",
    "rapidocr-onnxruntime",
    "Pillow",
    "lxml",
    "pdf2docx",
    "python-docx",
    "python-pptx",
    "openpyxl",
    "et-xmlfile",
    "XlsxWriter",
    "fire",
    "six",
]


def pick_wheel(urls):
    wheels = [u for u in urls if u["packagetype"] == "bdist_wheel"]
    for u in wheels:
        fn = u["filename"]
        if "win_amd64" in fn or "win32" in fn or "py3-none-any" in fn or "py2.py3-none-any" in fn:
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
            print(f"downloaded {u['filename']}", flush=True)
        with zipfile.ZipFile(wheel_path) as zf:
            zf.extractall(LIBS)
        print(f"extracted {u['filename']}", flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    sys.exit(main())
