import socket

for host in ["uploads.github.com", "alambic-origin.githubusercontent.com", "objects.githubusercontent.com", "github.com"]:
    try:
        infos = socket.getaddrinfo(host, 443)
        ips = {i[4][0] for i in infos}
        print(host, "->", sorted(ips)[:3])
    except OSError as e:
        print(host, "FAILED:", e)
