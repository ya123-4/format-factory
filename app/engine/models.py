"""Data models: job, status state machine, input kind (spec §4.1)."""
from dataclasses import dataclass
from enum import Enum


class InputKind(Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    DOCUMENT = "document"
    UNKNOWN = "unknown"


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


_TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.RUNNING, JobStatus.CANCELLED, JobStatus.SKIPPED},
    JobStatus.RUNNING: {JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED},
}
_TERMINAL = {JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.SKIPPED}


@dataclass
class ConversionJob:
    src_path: str
    out_dir: str
    target_fmt: str
    rel_subdir: str = ""
    target_filename: str = ""
    final_path: str | None = None
    status: JobStatus = JobStatus.PENDING
    error: str | None = None
    elapsed: float | None = None
    out_size: int | None = None

    def set_status(self, new: JobStatus) -> JobStatus:
        allowed = _TRANSITIONS.get(self.status, set())
        if new not in allowed:
            raise ValueError(f"illegal transition {self.status.name} -> {new.name}")
        self.status = new
        return new

    def reset(self) -> JobStatus:
        """The only way back to PENDING from a terminal state (GUI「重新转换」)."""
        if self.status not in _TERMINAL:
            raise ValueError(f"reset only allowed from terminal state, got {self.status.name}")
        self.status = JobStatus.PENDING
        self.error = None
        return self.status
