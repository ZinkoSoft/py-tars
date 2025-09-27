from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Dict


@dataclass(slots=True)
class RouterMetrics:
    """Collect simple counters and latency measurements for router events."""

    llm_requests: int = 0
    llm_responses: int = 0
    tts_messages: int = 0
    llm_latency_total: float = 0.0
    _llm_inflight: Dict[str, float] = field(default_factory=dict)

    def record_llm_request(self, request_id: str) -> None:
        if not request_id:
            return
        self.llm_requests += 1
        self._llm_inflight[request_id] = time.monotonic()

    def record_llm_response(self, request_id: str) -> None:
        if not request_id:
            return
        self.llm_responses += 1
        started = self._llm_inflight.pop(request_id, None)
        if started is not None:
            self.llm_latency_total += time.monotonic() - started

    def abandon_llm_request(self, request_id: str) -> None:
        if not request_id:
            return
        self._llm_inflight.pop(request_id, None)

    def record_tts_message(self) -> None:
        self.tts_messages += 1

    @property
    def avg_llm_latency(self) -> float:
        if self.llm_responses == 0:
            return 0.0
        return self.llm_latency_total / self.llm_responses

    def snapshot(self) -> dict[str, float | int]:
        return {
            "llm_requests": self.llm_requests,
            "llm_responses": self.llm_responses,
            "tts_messages": self.tts_messages,
            "avg_llm_latency": round(self.avg_llm_latency, 6),
            "llm_inflight": len(self._llm_inflight),
        }
