"""Progress area: file-count progress bar, quality selects, start/stop, log."""
import tkinter as tk
from tkinter import ttk


class ProgressFrame(ttk.Frame):
    def __init__(self, master, on_start, on_stop):
        super().__init__(master)
        self._on_start = on_start
        self._on_stop = on_stop

        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="音视频质量:").pack(side="left")
        self.media_quality = ttk.Combobox(
            row, state="readonly", width=10,
            values=["同源无损", "高质量", "中等", "低质量"],
        )
        self.media_quality.set("高质量")
        self.media_quality.pack(side="left", padx=(0, 12))
        ttk.Label(row, text="图片质量:").pack(side="left")
        self.image_quality = ttk.Combobox(
            row, state="readonly", width=8, values=["高质量", "中等", "低"]
        )
        self.image_quality.set("高质量")
        self.image_quality.pack(side="left", padx=(0, 12))

        self.start_button = ttk.Button(row, text="开始转换", command=on_start)
        self.start_button.pack(side="left", padx=4)
        self.stop_button = ttk.Button(row, text="停止", command=on_stop, state="disabled")
        self.stop_button.pack(side="left")

        prows = ttk.Frame(self)
        prows.pack(fill="x", pady=2)
        self.progress_bar = ttk.Progressbar(prows, maximum=1, value=0)
        self.progress_bar.pack(side="left", fill="x", expand=True)
        self.progress_label = ttk.Label(prows, text="0/0", width=10)
        self.progress_label.pack(side="left")

        self.log_text = tk.Text(self, height=6, state="disabled", wrap="none")
        self.log_text.pack(fill="both", expand=True, pady=(2, 0))

    def set_progress(self, done: int, total: int) -> None:
        self.progress_bar.configure(maximum=max(total, 1), value=done)
        self.progress_label.configure(text=f"{done}/{total}")

    def append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def set_running(self, running: bool) -> None:
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
