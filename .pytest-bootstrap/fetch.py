"""Bootstrap pytest into workspace-local .pytest-libs without pip (sandbox-safe).

DSH sandbox: pip's tempfile.mkdtemp (0o700 DACL) cannot be written to.
Download wheels via urllib (works with system cert store incl. SteamTools root)
and extract with zipfile using plain mkdir.
"""
import json
import pathlib
import sys
import urllib.request
import zipfile

BASE = pathlib.Path(__file__).resolve().parent.parent
LIBS = BASE / ".pytest-libs"
WHEELS = BASE / ".wheels"

PACKAGES = ["pytest", "iniconfig", "packaging", "pluggy", "pygments", "colorama"]


def pick_wheel(urls):
    wheels = [u for u in urls if u["packagetype"] == "bdist_wheel"]
    # prefer pure-python wheels
    for u in wheels:
        if "py3-none-any" in u["filename"] or "py2.py3-none-any" in u["filename"]:
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
            print(f"download {u['filename']} ...", flush=True)
            with urllib.request.urlopen(u["url"]) as r:
                wheel_path.write_bytes(r.read())
        with zipfile.ZipFile(wheel_path) as zf:
            zf.extractall(LIBS)
        print(f"extracted {u['filename']}")
    print("done. PYTHONPATH=.pytest-libs")


if __name__ == "__main__":
    sys.exit(main())
