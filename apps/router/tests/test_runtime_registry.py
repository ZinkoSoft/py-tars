from __future__ import annotations

import pytest

from tars.runtime.registry import register_topics  # type: ignore[import]


def test_register_topics_invokes_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_register(event_type: str, topic: str) -> None:
        calls.append((event_type, topic))

    monkeypatch.setattr("tars.runtime.registry.register", fake_register)

    mapping = {
        "tests.event.one": "tests/topic/one",
        "tests.event.two": "tests/topic/two",
    }

    register_topics(mapping)

    assert calls == list(mapping.items())


def test_register_topics_no_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_register(event_type: str, topic: str) -> None:  # pragma: no cover - sanity guard
        calls.append((event_type, topic))

    monkeypatch.setattr("tars.runtime.registry.register", fake_register)

    register_topics({})

    assert calls == []
