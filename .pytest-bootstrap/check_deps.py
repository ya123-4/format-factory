import sys

sys.path.insert(0, ".")
for mod in ["fitz", "pdf2docx", "numpy", "cv2", "fontTools", "docx", "fire"]:
    try:
        __import__(mod)
        print(mod, "ok")
    except ImportError as e:
        print(mod, "MISSING:", e)
