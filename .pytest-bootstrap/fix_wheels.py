"""Replace wrongly-picked wheels (win32/cp310/cp311) with py314-compatible ones."""
import json
import pathlib
import shutil
import sys
import urllib.request
import zipfile

BASE = pathlib.Path(__file__).resolve().parent.parent
LIBS = BASE / ".pytest-libs"
WHEELS = BASE / ".wheels"

TARGETS = {
    "opencv-python-headless": ["opencv_python_headless", "cv2"],
    "onnxruntime": ["onnxruntime"],
    "pillow": ["PIL", "pillow"],
    "lxml": ["lxml"],
}

def pick_wheel(urls):
    wheels = [u for u in urls if u["packagetype"] == "bdist_wheel"]
    scored = []
    for u in wheels:
        fn = u["filename"]
        score = 0
        if "win32" in fn:
            score -= 100
        if "win_amd64" in fn:
            score += 10
        if "cp314t" in fn:
            score -= 50  # free-threaded build — standard CPython cannot load it
        if "cp314" in fn:
            score += 5
        if "abi3" in fn:
            score += 3
        scored.append((score, u))
    return max(scored, key=lambda t: t[0])[1]

def main():
    for name, dirs in TARGETS.items():
        # 清理旧的错误版本目录
        for d in dirs:
            p = LIBS / d
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
        for dist in LIBS.glob(f"{name.replace('-', '_')}-*.dist-info"):
            shutil.rmtree(dist, ignore_errors=True)
        for dist in LIBS.glob(f"{name.replace('-', '_').replace('_', '_')}-*.dist-info"):
            shutil.rmtree(dist, ignore_errors=True)
        # 下载正确版本
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
        print(f"  extracted", flush=True)
    print("FIX DONE")

if __name__ == "__main__":
    sys.exit(main())
