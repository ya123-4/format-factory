import socket
import ssl

# 1. 当前解析
for host in ["uploads.github.com", "api.github.com"]:
    try:
        print(host, "->", sorted({i[4][0] for i in socket.getaddrinfo(host, 443)})[:3])
    except OSError as e:
        print(host, "FAILED:", e)

# 2. 127.0.0.1:443 直连测试（SteamTools 本地代理）
try:
    s = socket.create_connection(("127.0.0.1", 443), timeout=10)
    ctx = ssl.create_default_context()
    tls = ctx.wrap_socket(s, server_hostname="uploads.github.com")
    print("127.0.0.1:443 TLS OK:", tls.version(), "cert:", tls.getpeercert()["subject"][0][0][1][:40])
    tls.close()
except Exception as e:
    print("127.0.0.1:443 FAILED:", repr(e)[:200])

# 3. alambic-origin 直连测试
try:
    s = socket.create_connection(("20.205.243.161", 443), timeout=10)
    ctx = ssl.create_default_context()
    tls = ctx.wrap_socket(s, server_hostname="uploads.github.com")
    print("alambic-origin direct TLS OK:", tls.version())
    tls.close()
except Exception as e:
    print("alambic-origin FAILED:", repr(e)[:200])
