from __future__ import annotations

import pytest

from tars.domain.router.metrics import RouterMetrics  # type: ignore[import]


def test_router_metrics_tracks_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    metrics = RouterMetrics()

    timeline = [10.0, 12.5]

    def fake_monotonic() -> float:
        return timeline.pop(0)

    monkeypatch.setattr("tars.domain.router.metrics.time.monotonic", fake_monotonic)

    metrics.record_llm_request("req-1")
    metrics.record_llm_response("req-1")
    metrics.record_tts_message()

    snapshot = metrics.snapshot()

    assert snapshot["llm_requests"] == 1
    assert snapshot["llm_responses"] == 1
    assert snapshot["tts_messages"] == 1
    assert snapshot["llm_inflight"] == 0
    assert pytest.approx(snapshot["avg_llm_latency"], rel=1e-3) == 2.5


def test_router_metrics_abandon(monkeypatch: pytest.MonkeyPatch) -> None:
    metrics = RouterMetrics()

    def fake_monotonic() -> float:
        return 5.0

    monkeypatch.setattr("tars.domain.router.metrics.time.monotonic", fake_monotonic)

    metrics.record_llm_request("req-abandon")
    metrics.abandon_llm_request("req-abandon")

    snapshot = metrics.snapshot()
    assert snapshot["llm_requests"] == 1
    assert snapshot["llm_responses"] == 0
    assert snapshot["llm_inflight"] == 0
    assert snapshot["avg_llm_latency"] == 0.0
