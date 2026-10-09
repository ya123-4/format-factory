"""Rotating file logger tests (Task 13)."""
from app.engine.logsetup import setup_file_logger


def test_logger_writes_line(tmp_path):
    logger = setup_file_logger(tmp_path)
    logger.info("转换完成 你好")
    text = (tmp_path / "conversions.log").read_text(encoding="utf-8")
    assert "转换完成 你好" in text


def test_rotation_with_small_max_bytes(tmp_path):
    logger = setup_file_logger(tmp_path, max_bytes=1024, backups=2)
    for i in range(80):
        logger.info(f"line {i} " + "x" * 100)
    # flush 后轮转
    for h in logger.handlers:
        h.flush()
    files = sorted(p.name for p in tmp_path.glob("conversions.log*"))
    assert len(files) <= 3  # .log + .log.1 + .log.2 最多 3 份
    assert "conversions.log" in files
    # 最新的记录在 conversions.log 中
    assert "line 79" in (tmp_path / "conversions.log").read_text(encoding="utf-8")


def test_setup_twice_no_duplicate_handlers(tmp_path):
    logger = setup_file_logger(tmp_path)
    n1 = len(logger.handlers)
    logger2 = setup_file_logger(tmp_path)
    assert logger2 is logger
    assert len(logger2.handlers) == n1
