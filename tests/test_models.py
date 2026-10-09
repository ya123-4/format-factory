"""Data model and status state machine tests (Task 4)."""
import pytest

from app.engine.models import ConversionJob, InputKind, JobStatus


def test_legal_transitions():
    j = ConversionJob(src_path="a.mp4", out_dir="out", target_fmt="mkv")
    assert j.status == JobStatus.PENDING
    j.set_status(JobStatus.RUNNING)
    j.set_status(JobStatus.DONE)
    assert j.status == JobStatus.DONE

    j2 = ConversionJob(src_path="b.mp4", out_dir="out", target_fmt="mkv")
    j2.set_status(JobStatus.RUNNING)
    j2.set_status(JobStatus.FAILED)

    j3 = ConversionJob(src_path="c.mp4", out_dir="out", target_fmt="mkv")
    j3.set_status(JobStatus.CANCELLED)  # PENDING -> CANCELLED 合法

    j4 = ConversionJob(src_path="d.mp4", out_dir="out", target_fmt="mkv")
    j4.set_status(JobStatus.SKIPPED)  # PENDING -> SKIPPED 合法


def test_illegal_transition_raises():
    j = ConversionJob(src_path="a.mp4", out_dir="out", target_fmt="mkv")
    j.set_status(JobStatus.RUNNING)
    j.set_status(JobStatus.DONE)
    with pytest.raises(ValueError):
        j.set_status(JobStatus.PENDING)  # 终态无出边
    j2 = ConversionJob(src_path="b.mp4", out_dir="out", target_fmt="mkv")
    with pytest.raises(ValueError):
        j2.set_status(JobStatus.DONE)  # PENDING 不能直接 DONE


def test_reset_from_terminal_to_pending():
    for status in (JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.DONE):
        j = ConversionJob(src_path="a.mp4", out_dir="out", target_fmt="mkv")
        j.set_status(JobStatus.RUNNING)
        j.set_status(status)
        j.reset()
        assert j.status == JobStatus.PENDING
    # SKIPPED 从 PENDING 直接进入（执行前冲突检测），不走 RUNNING
    j = ConversionJob(src_path="a.mp4", out_dir="out", target_fmt="mkv")
    j.set_status(JobStatus.SKIPPED)
    j.reset()
    assert j.status == JobStatus.PENDING


def test_job_fields_default():
    j = ConversionJob(src_path="a.mp4", out_dir="out", target_fmt="mkv")
    assert j.rel_subdir == ""
    assert j.target_filename == ""
    assert j.final_path is None
    assert j.error is None
    assert j.elapsed is None
    assert j.out_size is None


def test_input_kind_members():
    assert {k.name for k in InputKind} == {"VIDEO", "AUDIO", "IMAGE", "DOCUMENT", "UNKNOWN"}
