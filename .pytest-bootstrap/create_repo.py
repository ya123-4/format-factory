"""Create the GitHub repo (idempotent) using the stored PAT."""
import json
import pathlib
import sys
import urllib.request

CONFIG = pathlib.Path.home() / ".dsh" / "github-publisher" / "config.json"
data = json.loads(CONFIG.read_text(encoding="utf-8"))
token = data["token"]
owner = data.get("owner") or "ya123-4"

REPO = "format-factory"
DESCRIPTION = (
    "格式工厂（自用版）：Windows 多格式转换器。音视频/图片/文档互转，支持 cosblaster .vdat(HLS) "
    "转 mp4、PDF 版式重建与 OCR、批量队列。Tkinter + FFmpeg + PyMuPDF/pdf2docx/RapidOCR，120+ 测试。"
)


def api(path, method="GET", body=None):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        method=method,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "format-factory-publisher",
        },
    )
    if body is not None:
        import json as j

        req.data = j.dumps(body).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


status, resp = api(f"/repos/{owner}/{REPO}")
if status == 200:
    print(f"repo exists: {resp['html_url']}")
elif status == 404:
    status, resp = api(
        "/user/repos", "POST",
        {"name": REPO, "description": DESCRIPTION[:340], "private": False},
    )
    if status == 201:
        print(f"created: {resp['html_url']}")
    else:
        print(f"create failed {status}: {resp}")
        sys.exit(2)
else:
    print(f"unexpected {status}: {resp}")
    sys.exit(2)
print("REPO_READY", f"https://github.com/{owner}/{REPO}")
