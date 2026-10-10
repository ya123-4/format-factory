"""Inspect available wheels for Python 3.14 compatibility."""
import json
import urllib.request

for name in ["onnxruntime", "opencv-python-headless", "pillow", "lxml"]:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json") as r:
        info = json.load(r)
    print(f"== {name} {info['info']['version']} ==")
    for u in info["urls"]:
        if u["packagetype"] == "bdist_wheel":
            fn = u["filename"]
            good = "cp314" in fn or "abi3" in fn or "py3-none-any" in fn
            if "win_amd64" in fn and (good or "cp313" in fn):
                print("  CAND:", fn)
            elif "win32" in fn and good:
                print("  (win32):", fn)
