"""Fetch the verified cert chain for github.com and write a PEM bundle."""
import pathlib
import socket
import ssl

OUT = pathlib.Path(__file__).resolve().parent.parent / ".tmp" / "git-ca.pem"

ctx = ssl.create_default_context()
with socket.create_connection(("github.com", 443), timeout=30) as sock:
    with ctx.wrap_socket(sock, server_hostname="github.com") as tls:
        chain = tls.get_verified_chain()  # leaf + intermediates + root

pems = []
import base64

for der in chain:
    if not isinstance(der, bytes):
        der = der.to_der()
    body = base64.encodebytes(der).decode("ascii")
    pems.append(
        "-----BEGIN CERTIFICATE-----\n" + body + "-----END CERTIFICATE-----\n"
    )

bundle = "".join(pems)
OUT.write_text(bundle, encoding="ascii")
print(f"chain certs: {len(chain)}; bundle bytes: {len(bundle)}")
