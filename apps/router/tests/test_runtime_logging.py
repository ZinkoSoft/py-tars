from __future__ import annotations

import io
import json
import logging

import pytest

from tars.runtime.logging import JsonFormatter, configure_logging  # type: ignore[import]


def test_json_formatter_includes_extra_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="router",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.topic = "tts/say"
    payload = json.loads(formatter.format(record))

    assert payload["message"] == "hello"
    assert payload["topic"] == "tts/say"
    assert payload["level"] == "INFO"


def test_configure_logging_uses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = io.StringIO()

    class CapturingHandler(logging.StreamHandler):
        def __init__(self) -> None:  # pragma: no cover - delegated to base
            super().__init__(stream)

    monkeypatch.setattr("logging.StreamHandler", CapturingHandler)

    logger = configure_logging("DEBUG", name="test-router")
    logger.info("structured", extra={"event": "test"})

    stream.seek(0)
    payload = json.loads(stream.readline())
    assert payload["message"] == "structured"
    assert payload["event"] == "test"
    assert payload["level"] == "INFO"