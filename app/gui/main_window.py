"""Main window: toolbar, file list, format select, progress; worker thread bridge."""
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app.config import Config, app_data_dir
from app.engine.converter import Converter, required_tools
from app.engine.document import DocConverter
from app.engine.image import ImageConverter
from app.engine.logsetup import setup_file_logger
from app.engine.media import MediaEngine
from app.engine.models import InputKind, JobStatus
from app.gui.file_list import FileListFrame, targets_for
from app.gui.progress import ProgressFrame

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FFMPEG_DIR = PROJECT_ROOT / "tools" / "ffmpeg"

MEDIA_QUALITY_MAP = {"同源无损": "copy", "高质量": "high", "中等": "medium", "低质量": "low"}
IMAGE_QUALITY_MAP = {"高质量": "high", "中等": "medium", "低": "low"}


def _ffmpeg_bin() -> str:
    p = FFMPEG_DIR / "ffmpeg.exe"
    return str(p) if p.exists() else ""


def _ffprobe_bin() -> str:
    p = FFMPEG_DIR / "ffprobe.exe"
    return str(p) if p.exists() else ""


def _soffice_bin(config: Config) -> str:
    if config.soffice_path and os.path.exists(config.soffice_path):
        return config.soffice_path
    return ""


class MainWindow:
    def __init__(self, root: tk.Tk, config: Config):
        self.root = root
        self.config = config
        self._queue = queue.Queue()
        self._converter = None
        self._stop_event = None
        self._worker = None
        self.logger = setup_file_logger(app_data_dir() / "logs")

        root.title("格式工厂（自用版）")
        root.geometry("820x560")

        toolbar = ttk.Frame(root, padding=(6, 4))
        toolbar.pack(fill="x")
        self._toolbar_buttons = []
        for text, cmd in (
            ("添加文件", self.add_files),
            ("添加文件夹", self.add_folder),
            ("粘贴路径", self.paste_paths),
        ):
            b = ttk.Button(toolbar, text=text, command=cmd)
            b.pack(side="left", padx=2)
            self._toolbar_buttons.append(text)
        ttk.Button(toolbar, text="打开输出目录", command=self.open_out_dir).pack(
            side="right", padx=2
        )
        self.out_dir_var = tk.StringVar(value=config.out_dir or "（默认：源文件所在目录）")
        ttk.Button(toolbar, text="输出目录…", command=self.choose_out_dir).pack(
            side="right", padx=2
        )
        ttk.Label(toolbar, textvariable=self.out_dir_var).pack(side="right", padx=6)

        self.file_list = FileListFrame(root)
        self.file_list.pack(fill="both", expand=True, padx=6)

        fmts = ttk.Frame(root, padding=(6, 2))
        fmts.pack(fill="x")
        ttk.Label(fmts, text="目标格式:").pack(side="left")
        self.format_combo = ttk.Combobox(fmts, state="readonly", width=10)
        self.format_combo.pack(side="left", padx=4)
        ttk.Button(fmts, text="应用到选中", command=self.apply_format).pack(side="left", padx=2)
        ttk.Button(fmts, text="重新转换", command=self.file_list.reset_selected).pack(
            side="left", padx=2
        )
        ttk.Button(fmts, text="删除", command=self.file_list.delete_selected).pack(
            side="left", padx=2
        )
        ttk.Button(fmts, text="清空已完成", command=self.file_list.clear_finished).pack(
            side="left", padx=2
        )
        self.file_list.tree.bind("<<TreeviewSelect>>", self._on_select)

        self.progress = ProgressFrame(root, on_start=self.start, on_stop=self.stop)
        self.progress.pack(fill="x", padx=6, pady=(0, 6))

    # -- toolbar helpers (used by smoke tests) --
    def toolbar_button_text(self) -> str:
        return " ".join(self._toolbar_buttons)

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(title="选择文件")
        for p in paths:
            self.file_list.add_file(p)

    def add_folder(self) -> None:
        d = filedialog.askdirectory(title="选择文件夹（递归添加）")
        if not d:
            return
        for dirpath, dirnames, filenames in os.walk(d):
            dirnames[:] = [x for x in dirnames if not x.startswith(".")]
            for fn in filenames:
                if fn.startswith("."):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(dirpath, d)
                self.file_list.add_file(full, "" if rel == "." else rel)

    def paste_paths(self) -> None:
        text = self.root.clipboard_get().strip()
        if not text:
            messagebox.showinfo("提示", "剪贴板为空")
            return
        for line in text.splitlines():
            line = line.strip().strip('"')
            if not line:
                continue
            if os.path.isdir(line):
                for dirpath, dirnames, filenames in os.walk(line):
                    dirnames[:] = [x for x in dirnames if not x.startswith(".")]
                    for fn in filenames:
                        full = os.path.join(dirpath, fn)
                        rel = os.path.relpath(dirpath, line)
                        self.file_list.add_file(full, "" if rel == "." else rel)
            elif os.path.exists(line):
                self.file_list.add_file(line)

    def choose_out_dir(self) -> None:
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.config.out_dir = d
            self.config.save()
            self.out_dir_var.set(d)

    def open_out_dir(self) -> None:
        d = self.config.out_dir or ""
        if d and os.path.isdir(d):
            os.startfile(d)  # type: ignore[attr-defined]
        else:
            messagebox.showinfo("提示", "尚未设置输出目录")

    def _on_select(self, _event) -> None:
        selected = self.file_list.selected_jobs()
        if selected:
            self.format_combo.configure(values=targets_for(selected[0].src_path))
            self.format_combo.set(selected[0].target_fmt)

    def apply_format(self) -> None:
        fmt = self.format_combo.get()
        if fmt:
            self.file_list.set_format_for_selected(fmt)

    # -- run control --
    def start(self) -> None:
        jobs = [j for j in self.file_list.jobs() if j.status == JobStatus.PENDING]
        if not jobs:
            messagebox.showinfo("提示", "没有待转换的文件")
            return
        out_dir = self.config.out_dir or ""
        for j in jobs:
            j.out_dir = out_dir or os.path.dirname(j.src_path)
            j.final_path = None
        missing = self._check_tools(jobs)
        if missing:
            messagebox.showwarning("缺少工具", "缺少以下工具，无法开始：\n" + "\n".join(missing))
            return
        self.config.media_quality = MEDIA_QUALITY_MAP[self.progress.media_quality.get()]
        self.config.image_quality = IMAGE_QUALITY_MAP[self.progress.image_quality.get()]
        self.config.save()

        stop = threading.Event()
        self._stop_event = stop
        ffmpeg = _ffmpeg_bin()
        soffice = _soffice_bin(self.config)
        profile_dir = app_data_dir() / "soffice-profile"
        media = MediaEngine(ffmpeg, _ffprobe_bin(), self.config, stop)
        image = ImageConverter(ffmpeg, stop, self.config.image_quality)
        doc = DocConverter(soffice, str(profile_dir), stop)
        engines = {
            InputKind.VIDEO: media.convert,
            InputKind.AUDIO: media.convert,
            InputKind.IMAGE: image.convert,
            InputKind.DOCUMENT: doc.convert,
        }
        conv = Converter(
            jobs=jobs,
            engines=engines,
            prober=None,
            config=self.config,
            on_progress=lambda d, t: self._queue.put(("prog", d, t)),
            on_log=lambda s: self._queue.put(("log", s)),
            stop_event=stop,
        )
        self._converter = conv
        self.progress.set_running(True)
        self.progress.set_progress(0, len(jobs))
        self._worker = threading.Thread(target=self._run_worker, args=(conv,), daemon=True)
        self._worker.start()
        self.root.after(100, self._poll)

    def _run_worker(self, conv: Converter) -> None:
        summary = conv.run()
        self._queue.put(("summary", summary))

    def _poll(self) -> None:
        while True:
            try:
                msg = self._queue.get_nowait()
            except queue.Empty:
                break
            if msg[0] == "prog":
                self.progress.set_progress(msg[1], msg[2])
            elif msg[0] == "log":
                self.progress.append_log(msg[1])
                self.logger.info(msg[1])
            elif msg[0] == "summary":
                s = msg[1]
                self.progress.set_running(False)
                for j in self.file_list.jobs():
                    self.file_list.update_status(j)
                messagebox.showinfo(
                    "转换完成",
                    f"成功 {s.done} / 失败 {s.failed} / 跳过 {s.skipped} / 已取消 {s.cancelled}",
                )
                return
        if self._worker is not None and self._worker.is_alive():
            self.root.after(100, self._poll)
        else:
            self.progress.set_running(False)

    def stop(self) -> None:
        if self._converter is not None:
            self._converter.cancel()
            self.progress.append_log("[停止] 已请求停止，正在终止当前任务…")

    def _check_tools(self, jobs) -> list[str]:
        needed = required_tools(jobs)
        missing = []
        if "ffmpeg" in needed and not _ffmpeg_bin():
            missing.append("FFmpeg（tools/ffmpeg/ffmpeg.exe）")
        if "soffice" in needed and not _soffice_bin(self.config):
            missing.append("LibreOffice（请在配置中设置 soffice 路径）")
        return missing
