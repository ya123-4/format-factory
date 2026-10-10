"""Isolate: does a bare uploads.github.com urllib request resolve?"""
import socket
import urllib.request

# 仅 DNS
try:
    print("getaddrinfo:", sorted({i[4][0] for i in socket.getaddrinfo("uploads.github.com", 443)})[:4])
except OSError as e:
    print("getaddrinfo FAILED:", e)

# 仅小 GET（无 api 前置）
try:
    req = urllib.request.Request(
        "https://uploads.github.com/",
        headers={"User-Agent": "test"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        print("GET status:", r.status)
except Exception as e:
    print("GET FAILED:", repr(e)[:150])
