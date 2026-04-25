"""Centralized logging configuration.

Implements the contract defined in ``.context/LOGGING.md``:

* All logs go to ``logs/app.log`` with size-based rotation (128 MB x 5).
* Console mirror for developer feedback.
* Consistent ``<timestamp> | <level> | <logger> | <message>`` format.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 128 * 1024 * 1024  # 128 MB
_BACKUP_COUNT = 5

_configured = False


def _normalize_level(level: str) -> int:
    """Map config-style level names (``WARN``/``FATAL``) to ``logging`` ints."""
    mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "FATAL": logging.CRITICAL,
        "CRITICAL": logging.CRITICAL,
    }
    return mapping.get(level.upper(), logging.INFO)


def configure_logging(log_dir: Path | None = None) -> logging.Logger:
    """Configure the root logger. Safe to call multiple times (idempotent).

    Args:
        log_dir: Directory where ``app.log`` lives. Defaults to ``settings.log_dir``.

    Returns:
        The configured root logger.
    """
    global _configured

    root = logging.getLogger()
    if _configured:
        return root

    level = _normalize_level(settings.log_level)
    root.setLevel(level)
    # Clear any handlers installed by libraries (e.g. NiceGUI) before us.
    root.handlers.clear()

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # --- File handler ------------------------------------------------------
    target_dir = Path(log_dir or settings.log_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "app.log"

    if settings.log_clear_on_start and log_file.exists():
        log_file.unlink(missing_ok=True)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # --- Console handler ---------------------------------------------------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    _configured = True
    root.debug("Logging configured (level=%s, file=%s)", settings.log_level, log_file)
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger, configuring logging lazily if needed."""
    if not _configured:
        configure_logging()
    return logging.getLogger(name)
