"""Multi-threaded ranged download of FFmpeg (gyan.dev) — much faster than single stream."""
import concurrent.futures
import pathlib
import sys
import threading
import urllib.request

BASE = pathlib.Path(__file__).resolve().parent.parent
ZIP = BASE / ".wheels" / "ffmpeg-gyan.zip"
URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
THREADS = 8
CHUNK = 1 << 20

_lock = threading.Lock()


def _fetch_range(start, end, buf, offset):
    req = urllib.request.Request(URL, headers={"Range": f"bytes={start}-{end}", "User-Agent": "format-factory"})
    with urllib.request.urlopen(req) as r:
        pos = 0
        while True:
            data = r.read(256 * 1024)
            if not data:
                break
            with _lock:
                buf[offset + pos : offset + pos + len(data)] = data
            pos += len(data)
    return pos


def main():
    ZIP.parent.mkdir(parents=True, exist_ok=True)
    head = urllib.request.Request(URL, method="HEAD", headers={"User-Agent": "format-factory"})
    with urllib.request.urlopen(head) as r:
        total = int(r.headers.get("Content-Length") or 0)
        accept_ranges = r.headers.get("Accept-Ranges")
    print(f"total={total} accept-ranges={accept_ranges}")
    if not total or accept_ranges != "bytes":
        print("server does not support ranges; falling back to single stream")
        req = urllib.request.Request(URL, headers={"User-Agent": "format-factory"})
        with urllib.request.urlopen(req) as r, open(ZIP, "wb") as f:
            while True:
                d = r.read(CHUNK)
                if not d:
                    break
                f.write(d)
        print("done (single)")
        return 0
    buf = bytearray(total)
    part = total // THREADS
    jobs = []
    for i in range(THREADS):
        start = i * part
        end = total - 1 if i == THREADS - 1 else start + part - 1
        jobs.append((start, end, buf, start))
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as ex:
        futs = [ex.submit(_fetch_range, *j) for j in jobs]
        done = 0
        for fut in concurrent.futures.as_completed(futs):
            done += fut.result()
            print(f"part complete, {done/1e6:.0f}/{total/1e6:.0f} MB", flush=True)
    with open(ZIP, "wb") as f:
        f.write(buf)
    print("done (ranged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
