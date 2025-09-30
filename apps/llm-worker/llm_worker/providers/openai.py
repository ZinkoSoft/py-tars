from __future__ import annotations

import httpx
import asyncio
import logging
import time
from typing import AsyncIterator

from pydantic import ValidationError

from .base import LLMProvider, LLMResult
from .models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    StreamChunk,
    build_messages,
)


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

        payload = ChatCompletionRequest(
            model=model,
            messages=build_messages(prompt, system),
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=False,
        )

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
            resp = await client.post("/chat/completions", json=payload.model_dump(exclude_none=True), headers=headers)
            logger.debug("openai.generate HTTP status=%s", resp.status_code)
            resp.raise_for_status()
            data = resp.json()
            try:
                parsed = ChatCompletionResponse.model_validate(data)
            except ValidationError as exc:
                logger.error("openai.generate validation error: %s", exc)
                raise
            text = parsed.choices[0].message.content
            usage = parsed.usage.dict(exclude_none=True) if parsed.usage else None
            dt = time.time() - t0
            logger.info("openai.generate done model=%s reply_len=%d elapsed=%.3fs", model, len(text or ""), dt)
            logger.debug("usage=%s", usage)
            return LLMResult(text=text, usage=usage, model=model, provider=self.name)

    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[dict[str, str | None]]:
        model = kwargs.get("model")
        temperature = kwargs.get("temperature")
        top_p = kwargs.get("top_p")
        system = kwargs.get("system")

        logger.debug("openai.stream prompt preview: %s", (prompt or "")[:120].replace("\n", " "))

        payload = ChatCompletionRequest(
            model=model,
            messages=build_messages(prompt, system),
            temperature=temperature,
            top_p=top_p,
            max_tokens=kwargs.get("max_tokens"),
            stream=True,
        )

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
            async with client.stream(
                "POST",
                "/chat/completions",
                json=payload.model_dump(exclude_none=True),
                headers=headers,
            ) as resp:
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
                        chunk = StreamChunk.model_validate_json(data_str)
                    except ValidationError as e:
                        logger.debug("openai.stream JSON parse error: %s", e)
                        continue
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    text = delta.content if delta else None
                    if text:
                        if first_dt is None:
                            first_dt = time.time() - t0
                            logger.info("openai.stream first_token_latency=%.3fs", first_dt)
                        total_len += len(text)
                        chunks += 1
                        logger.debug("openai.stream chunk #%d len=%d", chunks, len(text))
                        yield {"delta": text}
    async def generate_chat(self, messages: list[dict], **kwargs) -> LLMResult:
        model = kwargs.get("model")
        max_tokens = kwargs.get("max_tokens")
        temperature = kwargs.get("temperature")
        top_p = kwargs.get("top_p")
        system = kwargs.get("system")
        tools = kwargs.get("tools")  # List of tool specs

        # If system is provided, prepend it to messages
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        payload = ChatCompletionRequest(
            model=model,
            messages=chat_messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=False,
            tools=tools,
        )

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        t0 = time.time()
        logger.info(
            "openai.generate_chat start model=%s max_tokens=%s temp=%s top_p=%s messages=%d tools=%d",
            model,
            max_tokens,
            temperature,
            top_p,
            len(chat_messages),
            len(tools or []),
        )
        async with httpx.AsyncClient(timeout=self.timeout, base_url=self.base_url) as client:
            resp = await client.post("/chat/completions", json=payload.model_dump(exclude_none=True), headers=headers)
            logger.debug("openai.generate_chat HTTP status=%s", resp.status_code)
            resp.raise_for_status()
            data = resp.json()
            try:
                parsed = ChatCompletionResponse.model_validate(data)
            except ValidationError as exc:
                logger.error("openai.generate_chat validation error: %s", exc)
                raise
            text = parsed.choices[0].message.content
            tool_calls = getattr(parsed.choices[0].message, 'tool_calls', None)
            usage = parsed.usage.dict(exclude_none=True) if parsed.usage else None
            dt = time.time() - t0
            logger.info("openai.generate_chat done model=%s reply_len=%d tool_calls=%d elapsed=%.3fs", 
                       model, len(text or ""), len(tool_calls or []), dt)
            logger.debug("usage=%s", usage)
            return LLMResult(text=text, usage=usage, model=model, provider=self.name, tool_calls=tool_calls)

    async def stream_chat(self, messages: list[dict], **kwargs) -> AsyncIterator[dict[str, str | None]]:
        model = kwargs.get("model")
        temperature = kwargs.get("temperature")
        top_p = kwargs.get("top_p")
        system = kwargs.get("system")
        tools = kwargs.get("tools")  # List of tool specs

        # If system is provided, prepend it to messages
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        logger.debug("openai.stream_chat messages=%d", len(chat_messages))

        payload = ChatCompletionRequest(
            model=model,
            messages=chat_messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=kwargs.get("max_tokens"),
            stream=True,
            tools=tools,
        )

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
            "openai.stream_chat start model=%s temp=%s top_p=%s messages=%d tools=%d",
            model,
            temperature,
            top_p,
            len(chat_messages),
            len(tools or []),
        )
        async with httpx.AsyncClient(timeout=None, base_url=self.base_url) as client:
            async with client.stream(
                "POST",
                "/chat/completions",
                json=payload.model_dump(exclude_none=True),
                headers=headers,
            ) as resp:
                logger.debug("openai.stream_chat HTTP status=%s", resp.status_code)
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
                        logger.debug("openai.stream_chat received [DONE]")
                        break
                    try:
                        chunk = StreamChunk.model_validate_json(data_str)
                    except ValidationError as e:
                        logger.debug("openai.stream_chat JSON parse error: %s", e)
                        continue
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    text = delta.content if delta else None
                    if text:
                        if first_dt is None:
                            first_dt = time.time() - t0
                            logger.info("openai.stream_chat first_token_latency=%.3fs", first_dt)
                        total_len += len(text)
                        chunks += 1
                        logger.debug("openai.stream_chat chunk #%d len=%d", chunks, len(text))
                        yield {"delta": text}
        dt = time.time() - t0
        logger.info(
            "openai.stream_chat done chunks=%d total_len=%d elapsed=%.3fs first_token_latency=%.3fs",
            chunks,
            total_len,
            dt,
            -1.0 if first_dt is None else first_dt,
        )
