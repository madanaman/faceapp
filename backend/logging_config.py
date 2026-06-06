from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler

from .config import LOG_FILE, log_level, log_retention_days


def configure_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    level_name = log_level()
    level = getattr(logging, level_name, logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    file_handler = TimedRotatingFileHandler(
        LOG_FILE,
        when="midnight",
        backupCount=max(log_retention_days(), 1),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    logging.getLogger(__name__).info(
        "Logging configured file=%s level=%s retention_days=%s",
        LOG_FILE,
        level_name,
        log_retention_days(),
    )
