from __future__ import annotations

import httpx
import asyncio
import logging
import time
from typing import Dict, Any, AsyncIterator
import json
from .base import LLMProvider, LLMResult


logger = logging.getLogger("llm-worker.openai")


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, base_url: str | None = None, timeout: float = 60.0):
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self.timeout = timeout
        logger.debug("OpenAIProvider initialized base_url=%s timeout=%.1fs", self.base_url, self.timeout)

    async def generate(self, prompt: str, **kwargs) -> LLMResult:
        model = kwargs.get("model")
        max_tokens = kwargs.get("max_tokens")
        temperature = kwargs.get("temperature")
        top_p = kwargs.get("top_p")
        system = kwargs.get("system")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        t0 = time.time()
        logger.info(
            "openai.generate start model=%s max_tokens=%s temp=%s top_p=%s prompt_len=%d",
            model,
            max_tokens,
            temperature,
            top_p,
            len(prompt or ""),
        )
        logger.debug("prompt preview: %s", (prompt or "")[:120].replace("\n", " "))
        async with httpx.AsyncClient(timeout=self.timeout, base_url=self.base_url) as client:
            resp = await client.post("/chat/completions", json=payload, headers=headers)
            logger.debug("openai.generate HTTP status=%s", resp.status_code)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage")
            dt = time.time() - t0
            logger.info("openai.generate done model=%s reply_len=%d elapsed=%.3fs", model, len(text or ""), dt)
            logger.debug("usage=%s", usage)
            return LLMResult(text=text, usage=usage, model=model, provider=self.name)

    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        model = kwargs.get("model")
        temperature = kwargs.get("temperature")
        top_p = kwargs.get("top_p")
        system = kwargs.get("system")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        logger.debug("openai.stream prompt preview: %s", (prompt or "")[:120].replace("\n", " "))

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
        }
        max_tokens = kwargs.get("max_tokens")
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        t0 = time.time()
        first_dt: float | None = None
        total_len = 0
        chunks = 0
        logger.info(
            "openai.stream start model=%s temp=%s top_p=%s prompt_len=%d",
            model,
            temperature,
            top_p,
            len(prompt or ""),
        )
        async with httpx.AsyncClient(timeout=None, base_url=self.base_url) as client:
            async with client.stream("POST", "/chat/completions", json=payload, headers=headers) as resp:
                logger.debug("openai.stream HTTP status=%s", resp.status_code)
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith(":"):
                        # SSE comment/heartbeat
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                    elif line.startswith("data:"):
                        data_str = line[5:].strip()
                    else:
                        continue
                    if not data_str:
                        continue
                    if data_str == "[DONE]":
                        logger.debug("openai.stream received [DONE]")
                        break
                    try:
                        chunk = json.loads(data_str)
                    except Exception as e:
                        logger.debug("openai.stream JSON parse error: %s", e)
                        continue
                    try:
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        text = delta.get("content")
                        if text:
                            if first_dt is None:
                                first_dt = time.time() - t0
                                logger.info("openai.stream first_token_latency=%.3fs", first_dt)
                            total_len += len(text)
                            chunks += 1
                            logger.debug("openai.stream chunk #%d len=%d", chunks, len(text))
                            yield {"delta": text}
                    except Exception as e:
                        logger.debug("openai.stream delta parse error: %s", e)
                        continue
        dt = time.time() - t0
        logger.info(
            "openai.stream done chunks=%d total_len=%d elapsed=%.3fs first_token_latency=%.3fs",
            chunks,
            total_len,
            dt,
            -1.0 if first_dt is None else first_dt,
        )
