"""Structured logging for Sentsei.

Outputs JSON-lines format for easy parsing and debugging.
Set SENTSEI_LOG_LEVEL env var to control verbosity (DEBUG/INFO/WARNING/ERROR).
Set SENTSEI_LOG_FORMAT=text for human-readable output instead of JSON.
"""
import logging
import json
import os
import sys
import time
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["error"] = str(record.exc_info[1])
            entry["error_type"] = type(record.exc_info[1]).__name__
        # Include extra fields passed via `extra=`
        for key in ("component", "detail", "duration_ms", "count", "endpoint", "status_code", "ip"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        return json.dumps(entry, ensure_ascii=False, default=str)


def get_logger(name: str = "sentsei") -> logging.Logger:
    """Get or create a structured logger.

    Usage:
        from log import get_logger
        logger = get_logger(__name__)
        logger.info("Cache loaded", extra={"component": "cache", "count": 42})
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        level = os.environ.get("SENTSEI_LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, level, logging.INFO))

        handler = logging.StreamHandler(sys.stderr)
        fmt = os.environ.get("SENTSEI_LOG_FORMAT", "json")
        if fmt == "text":
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            ))
        else:
            handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger
