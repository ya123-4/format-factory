"""File list treeview: add/remove, per-row target format, status column."""
import os
from tkinter import ttk

from app.engine.document import doc_supported
from app.engine.image import IMAGE_FORMATS
from app.engine.media import FORMAT_MAP
from app.engine.models import ConversionJob, InputKind, JobStatus
from app.engine.pathing import target_filename
from app.engine.probe import classify_extension

STATUS_TEXT = {
    JobStatus.PENDING: "待转换",
    JobStatus.RUNNING: "转换中",
    JobStatus.DONE: "完成",
    JobStatus.FAILED: "失败",
    JobStatus.CANCELLED: "已取消",
    JobStatus.SKIPPED: "跳过",
}

KIND_TEXT = {
    InputKind.VIDEO: "视频",
    InputKind.AUDIO: "音频",
    InputKind.IMAGE: "图片",
    InputKind.DOCUMENT: "文档",
    InputKind.UNKNOWN: "未知",
}

DOC_TARGETS = ["pdf", "docx", "odt", "txt", "xlsx", "pptx"]


def targets_for(path: str) -> list[str]:
    kind = classify_extension(path)
    if kind == InputKind.VIDEO:
        return FORMAT_MAP["video"]
    if kind == InputKind.AUDIO:
        return FORMAT_MAP["audio"]
    if kind == InputKind.IMAGE:
        return IMAGE_FORMATS
    if kind == InputKind.DOCUMENT:
        src = os.path.splitext(path)[1].lower().lstrip(".")
        return [t for t in DOC_TARGETS if doc_supported(src, t)]
    if path.lower().endswith(".vdat"):
        return ["mp4"]
    return []


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n} GB"


class FileListFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.columns = ("name", "kind", "size", "format", "status")
        self.tree = ttk.Treeview(self, columns=self.columns, show="headings", height=12)
        for col, text, width in (
            ("name", "文件名", 260),
            ("kind", "类型", 60),
            ("size", "大小", 90),
            ("format", "目标格式", 80),
            ("status", "状态", 70),
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("failed", foreground="red")
        self._jobs_by_item = {}
        self._menu = None

    targets_for = staticmethod(targets_for)

    def add_file(self, path: str, rel_subdir: str = "") -> ConversionJob:
        fmt = targets_for(path)[0] if targets_for(path) else ""
        job = ConversionJob(
            src_path=path, out_dir="", target_fmt=fmt, rel_subdir=rel_subdir
        )
        job.target_filename = target_filename(os.path.basename(path), fmt) if fmt else ""
        size = _human_size(os.path.getsize(path)) if os.path.exists(path) else "?"
        item = self.tree.insert(
            "",
            "end",
            values=(
                os.path.basename(path),
                KIND_TEXT.get(classify_extension(path), "未知"),
                size,
                fmt,
                STATUS_TEXT[job.status],
            ),
        )
        self._jobs_by_item[item] = job
        return job

    def jobs(self) -> list[ConversionJob]:
        return list(self._jobs_by_item.values())

    def selected_jobs(self) -> list[ConversionJob]:
        return [self._jobs_by_item[i] for i in self.tree.selection() if i in self._jobs_by_item]

    def set_format_for_selected(self, fmt: str) -> None:
        for item in self.tree.selection():
            job = self._jobs_by_item.get(item)
            if job is None:
                continue
            job.target_fmt = fmt
            job.target_filename = target_filename(job.src_path, fmt)
            self.tree.set(item, "format", fmt)
            self._refresh_status(item)

    def delete_selected(self) -> None:
        for item in self.tree.selection():
            self.tree.delete(item)
            self._jobs_by_item.pop(item, None)

    def clear_finished(self) -> None:
        for item in list(self._jobs_by_item):
            job = self._jobs_by_item[item]
            if job.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.SKIPPED):
                self.tree.delete(item)
                self._jobs_by_item.pop(item, None)

    def reset_selected(self) -> None:
        for item in self.tree.selection():
            job = self._jobs_by_item.get(item)
            if job is None:
                continue
            try:
                job.reset()
            except ValueError:
                continue
            self._refresh_status(item)

    def update_status(self, job: ConversionJob) -> None:
        for item, j in self._jobs_by_item.items():
            if j is job:
                self._refresh_status(item)
                return

    def _refresh_status(self, item) -> None:
        job = self._jobs_by_item[item]
        self.tree.set(item, "status", STATUS_TEXT[job.status])
        self.tree.set(item, "format", job.target_fmt)
        tags = ("failed",) if job.status == JobStatus.FAILED else ()
        self.tree.item(item, tags=tags)

    def item_of(self, job: ConversionJob):
        for item, j in self._jobs_by_item.items():
            if j is job:
                return item
        return None
