"""Queue scheduler: serial execution, failure isolation, skip/cancel semantics (spec §6)."""
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable

from app.config import Config
from app.engine.errors import (
    ConversionError,
    FileNotFound,
    UnsupportedFormat,
)
from app.engine.media_prober import MediaProber
from app.engine.models import ConversionJob, InputKind, JobStatus
from app.engine.pathing import ensure_output_dir, resolve_output_path, target_filename
from app.engine.probe import classify_extension
from app.engine.runner import Cancelled

EngineCallable = Callable[[ConversionJob], str | None]


@dataclass
class Summary:
    done: int = 0
    failed: int = 0
    skipped: int = 0
    cancelled: int = 0


def required_tools(jobs: list[ConversionJob]) -> set[str]:
    tools = set()
    for job in jobs:
        kind = classify_extension(job.src_path)
        if kind == InputKind.DOCUMENT:
            # PDF 源走进程内引擎（PyMuPDF/pdf2docx），不依赖外部工具
            if not job.src_path.lower().endswith(".pdf"):
                tools.add("soffice")
        else:
            tools.add("ffmpeg")  # VIDEO/AUDIO/IMAGE/UNKNOWN 均需 ffmpeg
    return tools


class Converter:
    def __init__(
        self,
        jobs: list[ConversionJob],
        engines: dict[InputKind, EngineCallable],
        prober: MediaProber,
        config: Config,
        on_progress: Callable[[int, int], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        stop_event: threading.Event | None = None,
    ):
        self._jobs = jobs
        self._engines = engines
        self._prober = prober
        self._config = config
        self._on_progress = on_progress or (lambda done, total: None)
        self._on_log = on_log or (lambda msg: None)
        self._stop = stop_event

    def cancel(self) -> None:
        if self._stop is not None:
            self._stop.set()

    def run(self) -> Summary:
        summary = Summary()
        total = len(self._jobs)
        for job in self._jobs:
            if job.status != JobStatus.PENDING:
                continue
            if self._stop is not None and self._stop.is_set():
                job.set_status(JobStatus.CANCELLED)
                summary.cancelled += 1
                continue
            try:
                self._execute_one(job)
                if job.status == JobStatus.SKIPPED:
                    summary.skipped += 1
            except Cancelled:
                job.set_status(JobStatus.CANCELLED)
                summary.cancelled += 1
                # 停止：剩余 PENDING 全部置 CANCELLED
                for rest in self._jobs:
                    if rest.status == JobStatus.PENDING:
                        rest.set_status(JobStatus.CANCELLED)
                        summary.cancelled += 1
                break
            except ConversionError as e:
                if job.status == JobStatus.PENDING:
                    job.set_status(JobStatus.RUNNING)
                job.set_status(JobStatus.FAILED)
                job.error = f"{type(e).__name__}: {e}"
                if getattr(e, "stderr_tail", ""):
                    job.error += f"\n{getattr(e, 'stderr_tail')}"
                self._on_log(f"[失败] {job.src_path}: {job.error}")
                summary.failed += 1
            else:
                summary.done += 1
            self._on_progress(summary.done + summary.failed, total)
        return summary

    def _execute_one(self, job: ConversionJob) -> None:
        if not job.target_filename:
            job.target_filename = target_filename(job.src_path, job.target_fmt)
        final = resolve_output_path(
            job.target_filename, job.rel_subdir, job.out_dir, self._config.conflict
        )
        if final is None:
            job.set_status(JobStatus.SKIPPED)
            return
        job.final_path = final
        ensure_output_dir(final)
        if not os.path.exists(job.src_path):
            raise FileNotFound(f"source missing: {job.src_path}")
        kind = classify_extension(job.src_path)
        if kind == InputKind.UNKNOWN and job.src_path.lower().endswith(".vdat"):
            from app.engine.vdat import route_vdat

            kind = route_vdat(job.src_path, self._prober)
        engine = self._engines.get(kind)
        if engine is None:
            raise UnsupportedFormat(f"no engine for kind {kind.name}: {job.src_path}")
        job.set_status(JobStatus.RUNNING)
        start = time.monotonic()
        note = engine(job)
        job.elapsed = round(time.monotonic() - start, 3)
        if os.path.exists(final):
            job.out_size = os.path.getsize(final)
        job.set_status(JobStatus.DONE)
        if note:
            self._on_log(f"[提示] {job.src_path}: {note}")
        self._on_log(f"[完成] {job.src_path} → {final} ({job.elapsed}s)")
