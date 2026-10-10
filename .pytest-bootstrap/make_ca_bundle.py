"""Prepare git CA bundle: Git's cert.pem + SteamTools root, then push."""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GIT_CERT = pathlib.Path(
    r"C:\Users\ybc12\AppData\Local\Programs\Git\mingw64\ssl\cert.pem"
)
OUT = ROOT / ".tmp" / "git-ca.pem"
OUT.parent.mkdir(exist_ok=True)

# 1. 导出 SteamTools 根证书（certutil 输出含 PEM 文本）
r = subprocess.run(
    ["certutil", "-store", "Root", "SteamTools Certificate"],
    capture_output=True, text=True, encoding="gbk", errors="replace",
)
m = re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", r.stdout, re.S)
if not m:
    print("cannot extract SteamTools root:", r.stdout[:300])
    sys.exit(2)
steam_pem = m.group(0) + "\n"

# 2. 拼接
bundle = GIT_CERT.read_text(encoding="utf-8", errors="replace") + "\n" + steam_pem
OUT.write_text(bundle, encoding="utf-8")
print("CA bundle written:", OUT, len(bundle), "bytes")
