import json
import pathlib
import urllib.request

CONFIG = pathlib.Path.home() / ".dsh" / "github-publisher" / "config.json"
data = json.loads(CONFIG.read_text(encoding="utf-8"))
req = urllib.request.Request(
    "https://api.github.com/repos/ya123-4/format-factory/releases/tags/v1.0.0",
    headers={"Authorization": f"token {data['token']}", "User-Agent": "check"},
)
with urllib.request.urlopen(req) as r:
    rel = json.loads(r.read().decode("utf-8"))
for a in rel.get("assets", []):
    print(f"{a['name']}  {a['size']/1e6:.1f} MB  {a['browser_download_url']}")
