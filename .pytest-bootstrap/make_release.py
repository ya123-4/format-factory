"""Create GitHub Release v1.0.0 and upload FormatFactory.exe as an asset."""
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

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXE = ROOT / "dist" / "FormatFactory.exe"

TAG = "v1.0.0"
BODY = """# 格式工厂（自用版）v1.0.0

Windows 多格式转换器（独立 exe，无需安装 Python）。

## 支持格式

- 视频：mp4 / mkv / avi / mov / webm / gif
- 音频：mp3 / wav / flac / m4a / aac / ogg
- 图片：jpg / png / webp / bmp / tiff
- 文档：pdf→docx（版式重建+图片原位还原）/ txt（扫描件自动 OCR）/ xlsx（表格提取）/ pptx（可编辑文本）；docx/odt/xlsx/pptx→pdf 等
- 特殊：cosblaster `.vdat`（HLS 清单 + `_contents` 分片）→ mp4 无损流复制；行车记录仪 MP4 变体 `.vdat`

## 使用

1. 下载 FormatFactory.exe，放到任意位置双击运行
2. 添加文件（可 Ctrl 多选）/ 文件夹（递归）
3. 选择目标格式 → 开始转换
4. `.vdat` 转换要求：`.vdat` 与 `<同名>.vdat_contents` 文件夹在同一目录

## 构建

见 README（源码仓库）；`powershell -ExecutionPolicy Bypass -File .pytest-bootstrap\\build_exe.ps1`

## 校验

- SHA-256 见下方资产（`Get-FileHash FormatFactory.exe -Algorithm SHA256`）
- FFmpeg 4.4-essentials（GPL）；LibreOffice Kit（DSH bundled）；PyMuPDF/pdf2docx/RapidOCR（AGPL/MIT）
"""


def api(path, method="GET", body=None, headers=None):
    h = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "format-factory-publisher",
    }
    if headers:
        h.update(headers)
    req = urllib.request.Request(
        f"https://api.github.com{path}", method=method, headers=h
    )
    if body is not None:
        if isinstance(body, (dict, list)):
            req.data = json.dumps(body).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        else:
            req.data = body
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


# 1. 创建/复用 Release
status, rel = api(f"/repos/{owner}/{REPO}/releases/tags/{TAG}")
if status == 404:
    status, rel = api(
        f"/repos/{owner}/{REPO}/releases",
        "POST",
        {"tag_name": TAG, "name": "FormatFactory v1.0.0", "body": BODY, "draft": False},
    )
    if status != 201:
        print(f"release create failed {status}: {rel}")
        sys.exit(2)
    print("release created:", rel["html_url"])
else:
    print("release exists:", rel["html_url"])

release_id = rel["id"]

# 2. 上传 exe 资产（若已有同名则跳过）
existing = [a["name"] for a in rel.get("assets", [])]
if EXE.name in existing:
    print("asset already uploaded, skip")
    sys.exit(0)

print(f"uploading {EXE.name} ({EXE.stat().st_size/1e6:.1f} MB) ...", flush=True)
import time

data_bytes = EXE.read_bytes()
last_err = None
for attempt in range(1, 8):
    try:
        status, resp = api(
            f"https://uploads.github.com/repos/{owner}/{REPO}/releases/{release_id}/assets?name={EXE.name}",
            "POST",
            data_bytes,
            headers={"Content-Type": "application/octet-stream"},
        )
        print("asset upload:", status, resp.get("browser_download_url") or resp)
        if status == 201:
            sys.exit(0)
        last_err = f"status {status}"
        break
    except Exception as e:  # noqa: BLE001 — DNS 间歇故障重试
        last_err = str(e)
        print(f"attempt {attempt} failed ({last_err[:80]}), retry in 30s", flush=True)
        time.sleep(30)
print("upload failed after retries:", last_err)
sys.exit(3)
