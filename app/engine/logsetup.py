"""Rotating file logger (spec §7: logs/conversions.log, 5MB x 3)."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "format_factory"


def setup_file_logger(
    log_dir: Path, max_bytes: int = 5 * 1024 * 1024, backups: int = 2
) -> logging.Logger:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    # 重复调用不叠加 handler
    logger.handlers.clear()
    handler = RotatingFileHandler(
        log_dir / "conversions.log",
        maxBytes=max_bytes,
        backupCount=backups,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger
