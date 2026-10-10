import pathlib

p = pathlib.Path(
    r"D:\新建文件夹 (2)\新建文件夹 (2)\LissAV  超级漂亮coser穿着婚纱早上来叫醒我先来一炮 无码_2180588050.vdat"
)
text = p.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()
print("total lines:", len(lines))
for ln in lines[:8]:
    print(repr(ln))
print("...")
for ln in lines[-2:]:
    print(repr(ln))
