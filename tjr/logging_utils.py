"""tjr.logging_utils -- structured logging for production-grade observability.

Provides a small, dependency-free structured logger that emits one JSON object
per log record (with an opt-in text format for local debugging). It is wired into
the agent framework (hooks, tools, skill registry, orchestrator) so every step,
tool call, gate result and degradation event is observable and grep-able in CI.

This module never raises from a logging call path: if a configured file output
is unwritable it falls back to ``stderr`` with a single warning, so logging can
never take the harness down.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .config import LoggingSettings, Settings

__all__ = [
    "StructuredFormatter", "configure_logging", "get_logger",
    "log_event", "LOGGING_CONFIGURED",
]

_LOG_LOCK = threading.Lock()
LOGGING_CONFIGURED = False
_DEFAULT_LOGGER_NAME = "tjr"


class StructuredFormatter(logging.Formatter):
    """Formatter that emits either a JSON line or a human-readable text line."""

    def __init__(self, fmt: str = "json") -> None:
        super().__init__()
        self._fmt = fmt

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Attach structured extras (anything added via logger.info(..., extra=...)).
        std = set(vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()) | {"message", "asctime"}
        for k, v in record.__dict__.items():
            if k not in std and not k.startswith("_"):
                payload[k] = _safe_json(v)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        if self._fmt == "text":
            extras = " ".join(f"{k}={payload[k]}" for k in payload
                              if k not in {"ts", "level", "logger", "msg"})
            return f"{payload['ts']} {payload['level']} {payload['logger']}: {payload['msg']}" + (
                f" {extras}" if extras else "")
        return json.dumps(payload, ensure_ascii=False, default=str)


def _safe_json(v: Any) -> Any:
    try:
        json.dumps(v)
        return v
    except (TypeError, ValueError):
        return str(v)


def _resolve_handler(output: str) -> logging.Handler:
    if output in {"stderr", ""}:
        return logging.StreamHandler(sys.stderr)
    if output == "stdout":
        return logging.StreamHandler(sys.stdout)
    try:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        return logging.FileHandler(path, encoding="utf-8")
    except OSError:
        # Never let logging configuration crash the run.
        sys.stderr.write(f"[tjr.logging] could not open log file {output!r}; falling back to stderr\n")
        return logging.StreamHandler(sys.stderr)


def configure_logging(settings: Optional[Settings] = None,
                      *,
                      level: Optional[str] = None,
                      fmt: Optional[str] = None,
                      output: Optional[str] = None) -> logging.Logger:
    """Configure root + ``tjr`` loggers from settings and return the tjr logger.

    Idempotent: re-calls replace handlers cleanly under a lock.
    """
    global LOGGING_CONFIGURED
    s = settings or Settings()
    ls: LoggingSettings = s.logging
    lvl = (level or ls.level).upper()
    fmt_ = fmt or ls.format
    out = output or ls.output
    numeric = getattr(logging, lvl, logging.INFO)
    formatter = StructuredFormatter(fmt_)
    handler = _resolve_handler(out)
    handler.setFormatter(formatter)
    with _LOG_LOCK:
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)
        root.addHandler(handler)
        root.setLevel(numeric)
        logging.getLogger(_DEFAULT_LOGGER_NAME).setLevel(numeric)
        LOGGING_CONFIGURED = True
    return logging.getLogger(_DEFAULT_LOGGER_NAME)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a child logger of the ``tjr`` namespace (configuring if needed)."""
    if not LOGGING_CONFIGURED:
        configure_logging()
    if not name or name == _DEFAULT_LOGGER_NAME:
        return logging.getLogger(_DEFAULT_LOGGER_NAME)
    if name.startswith(_DEFAULT_LOGGER_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{_DEFAULT_LOGGER_NAME}.{name}")


def log_event(logger: logging.Logger, event: str, level: str = "INFO",
              **fields: Any) -> None:
    """Emit a structured event record with a stable ``event`` field."""
    getattr(logger, level.lower(), logger.info)(event, extra={"event": event, **fields})