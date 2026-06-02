"""
utils/logger.py

Centralised logging for Mintkey.
Writes to both the console (stderr) and ~/mintkey.log with timestamps,
log levels, and module names.

Usage in any module:
    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("Something happened")
    log.error("Something broke: %s", err)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOG_FILE = Path.home() / "mintkey.log"
_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger("mintkey")
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    # File handler - appends to ~/mintkey.log
    try:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass

    # Console handler - writes to stderr
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Silence noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger under the 'mintkey' root logger.
    Pass __name__ from the calling module so the module name appears in logs.
    """
    _configure()
    # Strip common path prefixes so names stay short (e.g. 'services.ai_service')
    short = name.removeprefix("mintkey.").removeprefix("__main__") or "main"
    return logging.getLogger(f"mintkey.{short}")
