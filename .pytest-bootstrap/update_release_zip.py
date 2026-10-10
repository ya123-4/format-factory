"""Update Release v1.0.0: remove old exe asset, upload the onedir zip."""
import json
import pathlib
import sys
import urllib.error
import urllib.request

CONFIG = pathlib.Path.home() / ".dsh" / "github-publisher" / "config.json"
data = json.loads(CONFIG.read_text(encoding="utf-8"))
token = data["token"]
owner = data.get("owner") or "ya123-4"
REPO = "format-factory"
TAG = "v1.0.0"

ROOT = pathlib.Path(__file__).resolve().parent.parent
ZIP = ROOT / "dist" / "FormatFactory-v1.0.0.zip"


def api(path, method="GET", body=None, headers=None):
    h = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "format-factory-publisher",
    }
    if headers:
        h.update(headers)
    req = urllib.request.Request(
        path if path.startswith("http") else f"https://api.github.com{path}",
        method=method,
        headers=h,
    )
    if body is not None:
        if isinstance(body, (dict, list)):
            req.data = json.dumps(body).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        else:
            req.data = body
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode("utf-8")
            return r.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        return e.code, json.loads(raw) if raw.strip() else {}


status, rel = api(f"/repos/{owner}/{REPO}/releases/tags/{TAG}")
if status != 200:
    print("release not found:", status)
    sys.exit(2)
release_id = rel["id"]

# 删除旧 onefile exe 资产（onedir 版已解决火绒 TEMP 拦截问题）
for a in rel.get("assets", []):
    if a["name"] == "FormatFactory.exe":
        s, _ = api(f"/repos/{owner}/{REPO}/releases/assets/{a['id']}", "DELETE")
        print("deleted old exe asset:", s)

# 上传 zip
existing = [a["name"] for a in rel.get("assets", [])]
if ZIP.name in existing:
    print("zip already uploaded")
else:
    print(f"uploading {ZIP.name} ({ZIP.stat().st_size/1e6:.1f} MB) ...", flush=True)
    s, resp = api(
        f"https://uploads.github.com/repos/{owner}/{REPO}/releases/{release_id}/assets?name={ZIP.name}",
        "POST",
        ZIP.read_bytes(),
        headers={"Content-Type": "application/zip"},
    )
    print("zip upload:", s, resp.get("browser_download_url") or resp)
    if s != 201:
        sys.exit(3)
print("DONE")
