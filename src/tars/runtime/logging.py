"""Runtime logging utilities and protocol definitions."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Protocol

import orjson


class Logger(Protocol):
    """Minimal logger protocol used across runtime helpers."""

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None: ...


_RESERVED_RECORD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
}


class JsonFormatter(logging.Formatter):
    """Basic JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        extra: Dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_ATTRS or key.startswith("_"):
                continue
            extra[key] = value

        if extra:
            payload.update(extra)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info:
            payload["stack"] = record.stack_info

        def _default(obj: Any) -> Any:
            try:
                return repr(obj)
            except Exception:  # pragma: no cover - defensive
                return "<unrepr-able>"

        return orjson.dumps(payload, default=_default).decode()


def configure_logging(level: str = "INFO", *, name: str = "router") -> logging.Logger:
    """Configure root logger with JSON formatter and return the requested logger."""

    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
    return logging.getLogger(name)


__all__ = ["Logger", "JsonFormatter", "configure_logging"]
