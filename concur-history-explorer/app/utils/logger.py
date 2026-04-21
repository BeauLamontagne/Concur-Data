"""Centralized logging configuration for Concur History Explorer."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
LOG_FILE = LOG_DIR / "app.log"

_configured = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure rotating file + console logging. Safe to call multiple times."""
    global _configured
    if _configured:
        return logging.getLogger("concur")

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)

    _configured = True
    return logging.getLogger("concur")


def get_logger(name: str = "concur") -> logging.Logger:
    """Return a named child logger (call setup_logging once at app startup)."""
    return logging.getLogger(name)
