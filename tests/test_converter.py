"""Scheduler tests (Task 10) — fake engines, no external tools."""
import threading

import pytest

from app.config import Config
from app.engine import converter
from app.engine.errors import ConversionFailed, PermissionDenied
from app.engine.models import ConversionJob, JobStatus


class FakeEngine:
    """EngineCallable double; call_behavior: callable(job, engine_self)."""

    def __init__(self, behavior=None):
        self.calls = []
        self._behavior = behavior

    def __call__(self, job):
        self.calls.append(job)
        if self._behavior is not None:
            return self._behavior(job, self)
        return None


def _mk_job(src, fmt, out_dir):
    return ConversionJob(src_path=str(src), out_dir=str(out_dir), target_fmt=fmt)


def _cfg(tmp_path, conflict="overwrite"):
    return Config(out_dir=str(tmp_path), conflict=conflict)


def test_run_order_and_progress(tmp_path):
    s1, s2 = tmp_path / "a.mp4", tmp_path / "b.mp4"
    s1.write_bytes(b"1")
    s2.write_bytes(b"2")
    jobs = [_mk_job(s1, "mkv", tmp_path), _mk_job(s2, "mkv", tmp_path)]
    prog = []
    eng = FakeEngine()
    c = converter.Converter(
        jobs=jobs,
        engines={eng_key("video"): eng},
        prober=None,
        config=_cfg(tmp_path),
        on_progress=lambda done, total: prog.append((done, total)),
    )
    summary = c.run()
    assert [j.src_path for j in eng.calls] == [str(s1), str(s2)]
    assert prog == [(1, 2), (2, 2)]
    assert summary.done == 2 and summary.failed == 0


def eng_key(name):
    from app.engine.models import InputKind

    return getattr(InputKind, name.upper())


def test_engine_failure_isolates_and_continues(tmp_path):
    s1, s2 = tmp_path / "a.mp4", tmp_path / "b.mp4"
    s1.write_bytes(b"1")
    s2.write_bytes(b"2")
    jobs = [_mk_job(s1, "mkv", tmp_path), _mk_job(s2, "mkv", tmp_path)]
    eng = FakeEngine(behavior=lambda job, self: (_ for _ in ()).throw(
        ConversionFailed("boom", 1, "tail")) if len(self.calls) == 1 else None)
    c = converter.Converter(jobs=jobs, engines={eng_key("video"): eng},
                            prober=None, config=_cfg(tmp_path))
    summary = c.run()
    assert jobs[0].status == JobStatus.FAILED
    assert jobs[1].status == JobStatus.DONE
    assert summary.failed == 1 and summary.done == 1


def test_skip_policy_marks_skipped(tmp_path):
    s1 = tmp_path / "a.mp4"
    s1.write_bytes(b"1")
    (tmp_path / "a.mkv").write_bytes(b"exists")
    jobs = [_mk_job(s1, "mkv", tmp_path)]
    eng = FakeEngine()
    c = converter.Converter(jobs=jobs, engines={eng_key("video"): eng},
                            prober=None, config=_cfg(tmp_path, conflict="skip"))
    summary = c.run()
    assert jobs[0].status == JobStatus.SKIPPED
    assert eng.calls == []
    assert summary.skipped == 1


def test_source_missing_before_run(tmp_path):
    s1 = tmp_path / "gone.mp4"  # 不存在
    jobs = [_mk_job(s1, "mkv", tmp_path)]
    eng = FakeEngine()
    c = converter.Converter(jobs=jobs, engines={eng_key("video"): eng},
                            prober=None, config=_cfg(tmp_path))
    summary = c.run()
    assert jobs[0].status == JobStatus.FAILED
    assert "FileNotFound" in jobs[0].error
    assert summary.failed == 1


def test_output_dir_creation_failure(tmp_path, monkeypatch):
    s1 = tmp_path / "a.mp4"
    s1.write_bytes(b"1")
    jobs = [_mk_job(s1, "mkv", tmp_path)]

    def boom(path):
        raise PermissionDenied("no access")

    monkeypatch.setattr(converter, "ensure_output_dir", boom)
    eng = FakeEngine()
    c = converter.Converter(jobs=jobs, engines={eng_key("video"): eng},
                            prober=None, config=_cfg(tmp_path))
    summary = c.run()
    assert jobs[0].status == JobStatus.FAILED
    assert "PermissionDenied" in jobs[0].error
    assert summary.failed == 1


def test_cancel_sets_remaining_cancelled(tmp_path):
    stop = threading.Event()
    jobs = [_mk_job(tmp_path / f"{i}.mp4", "mkv", tmp_path) for i in range(3)]
    for i, j in enumerate(jobs):
        (tmp_path / f"{i}.mp4").write_bytes(b"x")
    eng = FakeEngine(behavior=lambda job, self: stop.set())
    c = converter.Converter(jobs=jobs, engines={eng_key("video"): eng},
                            prober=None, config=_cfg(tmp_path), stop_event=stop)
    summary = c.run()
    assert jobs[0].status == JobStatus.DONE
    assert jobs[1].status == JobStatus.CANCELLED
    assert jobs[2].status == JobStatus.CANCELLED
    assert summary.cancelled == 2


def test_rerun_only_pending(tmp_path):
    s1 = tmp_path / "a.mp4"
    s1.write_bytes(b"1")
    jobs = [_mk_job(s1, "mkv", tmp_path)]
    eng = FakeEngine(behavior=lambda job, self: (_ for _ in ()).throw(
        ConversionFailed("boom", 1, "t")))
    c = converter.Converter(jobs=jobs, engines={eng_key("video"): eng},
                            prober=None, config=_cfg(tmp_path))
    c.run()
    assert jobs[0].status == JobStatus.FAILED
    before = len(eng.calls)
    c.run()  # 第二轮：FAILED 不复活
    assert len(eng.calls) == before
    assert jobs[0].status == JobStatus.FAILED


def test_required_tools(tmp_path):
    v = _mk_job(tmp_path / "a.mp4", "mkv", tmp_path)
    d = _mk_job(tmp_path / "a.docx", "pdf", tmp_path)
    assert converter.required_tools([v]) == {"ffmpeg"}
    assert converter.required_tools([d]) == {"soffice"}
    assert converter.required_tools([v, d]) == {"ffmpeg", "soffice"}
