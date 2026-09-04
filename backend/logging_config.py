"""
logging_config.py — Structured JSON logging for RecoverAI.

Why structured logging?
  - Every decision becomes a machine-readable log line (not just a string).
  - In production you'd ship these to Datadog / CloudWatch / Loki.
  - For the demo, you can `grep` or `jq` the log file to find exactly
    which payments were blocked, escalated, or recovered.

Usage:
    from logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("payment.diagnosed", extra={"payment_id": "p123", "score": 0.87})
"""

import logging
import json
import os
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Formats every log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any `extra={}` fields the caller passed in
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ):
                log_obj[key] = value

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


def setup_logging(level: int | str | None = None, log_file: str | None = None) -> None:
    """
    Call once at application startup.

    Args:
        level:    Minimum log level (INFO by default).
        log_file: Optional path for a file handler. Logs also always go to
                  stderr so you see them in the terminal.
    """
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()
    if isinstance(level, str):
        level = getattr(logging, level, logging.INFO)
    if log_file is None:
        log_file = os.getenv("LOG_FILE", "recoverai.log")

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any handlers added by libraries before we configure ours
    root.handlers.clear()

    formatter = JSONFormatter()

    # Console handler — always present
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # File handler — optional but useful for the demo (you can `cat` the file)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger. Call this at module level:
        logger = get_logger(__name__)
    """
    return logging.getLogger(name)
