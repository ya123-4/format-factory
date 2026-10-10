import json
import pathlib

p = pathlib.Path.home() / ".dsh" / "github-publisher" / "config.json"
print("exists:", p.exists())
if p.exists():
    data = json.loads(p.read_text(encoding="utf-8"))
    print("keys:", sorted(data.keys()))
    print("has_token:", bool(data.get("token") or data.get("pat") or data.get("github_token")))
