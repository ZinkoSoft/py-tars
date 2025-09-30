from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Dict, Any, Optional


@dataclass
class LLMResult:
    text: str
    usage: Dict[str, Any] | None = None
    model: str | None = None
    provider: str | None = None
    tool_calls: list | None = None


class LLMProvider:
    name: str = "base"

    async def generate(self, prompt: str, **kwargs) -> LLMResult:  # pragma: no cover - abstract
        raise NotImplementedError

    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[Dict[str, Any]]:  # pragma: no cover - optional
        # yield {"delta": "text"}
        raise NotImplementedError
