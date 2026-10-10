"""Set origin URL with embedded PAT and push (openssl + SteamTools chain)."""
import json
import pathlib
import subprocess
import sys

CONFIG = pathlib.Path.home() / ".dsh" / "github-publisher" / "config.json"
data = json.loads(CONFIG.read_text(encoding="utf-8"))
token = data["token"]
owner = data.get("owner") or "ya123-4"

ROOT = pathlib.Path(__file__).resolve().parent.parent
CA = ROOT / ".tmp" / "git-ca.pem"

subprocess.run(
    [
        "git", "remote", "set-url", "origin",
        f"https://x-access-token:{token}@github.com/{owner}/format-factory.git",
    ],
    cwd=ROOT, check=True,
)
r = subprocess.run(
    [
        "git", "-c", "credential.helper=",
        "-c", "http.sslBackend=openssl",
        "-c", f"http.sslCAInfo={CA}",
        "push", "-u", "origin", "master",
    ],
    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
)
print(r.stdout[-600:])
print(r.stderr[-600:])
print("exit:", r.returncode)
sys.exit(r.returncode)
