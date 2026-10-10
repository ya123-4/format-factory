"""Fetch PyInstaller + deps into .pytest-libs (sandbox-safe)."""
import json
import pathlib
import sys
import urllib.request
import zipfile

BASE = pathlib.Path(__file__).resolve().parent.parent
LIBS = BASE / ".pytest-libs"
WHEELS = BASE / ".wheels"

PACKAGES = [
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "altgraph",
    "pefile",
    "pywin32-ctypes",
    "setuptools",
]


def pick_wheel(urls):
    wheels = [u for u in urls if u["packagetype"] == "bdist_wheel"]
    for u in wheels:
        fn = u["filename"]
        if "py3-none-any" in fn or "py2.py3-none-any" in fn:
            return u
    scored = []
    for u in wheels:
        fn = u["filename"]
        score = 0
        if "win32" in fn:
            score -= 100
        if "win_amd64" in fn:
            score += 10
        if "cp314t" in fn:
            score -= 50
        if "cp314" in fn:
            score += 5
        if "abi3" in fn:
            score += 3
        scored.append((score, u))
    return max(scored, key=lambda t: t[0])[1]


def main():
    for name in PACKAGES:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json") as r:
            info = json.load(r)
        u = pick_wheel(info["urls"])
        print(f"{name}: {u['filename']}", flush=True)
        wheel_path = WHEELS / u["filename"]
        if not wheel_path.exists():
            with urllib.request.urlopen(u["url"]) as r:
                wheel_path.write_bytes(r.read())
        with zipfile.ZipFile(wheel_path) as zf:
            zf.extractall(LIBS)
        print("  extracted", flush=True)
    print("DONE")


if __name__ == "__main__":
    sys.exit(main())
