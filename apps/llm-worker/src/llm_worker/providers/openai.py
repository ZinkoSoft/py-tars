from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Sequence
from enum import Enum
from typing import Any

import httpx
import orjson
from httpx import HTTPStatusError
from pydantic import ValidationError

from ..config import OPENAI_RESPONSES_MODELS
from .base import LLMProvider, LLMResult
from .models import ChatCompletionRequest, ChatCompletionResponse, StreamChunk


logger = logging.getLogger("llm-worker.openai")


class OpenAIEndpoint(str, Enum):
    CHAT_COMPLETIONS = "chat_completions"
    RESPONSES = "responses"


class _ModelRouter:
    def __init__(self, responses_patterns: Sequence[str] | None = None):
        self._responses_patterns = tuple(
            pattern.strip() for pattern in (responses_patterns or ()) if pattern.strip()
        )

    def endpoint_for(self, model: str | None) -> OpenAIEndpoint:
        if model and self._matches_responses(model):
            return OpenAIEndpoint.RESPONSES
        return OpenAIEndpoint.CHAT_COMPLETIONS

    def _matches_responses(self, model: str) -> bool:
        for pattern in self._responses_patterns:
            if pattern == "*":
                return True
            if pattern.endswith("*"):
                if model.startswith(pattern[:-1]):
                    return True
            elif model == pattern:
                return True
        return False


def _normalise_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
                elif "content" in item and isinstance(item["content"], str):
                    parts.append(item["content"])
                else:
                    parts.append(orjson.dumps(item).decode("utf-8"))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return text
        return orjson.dumps(value).decode("utf-8")
    return str(value)


def build_responses_input(messages: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert chat-style messages into the Responses API input format."""

    converted: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        entry: dict[str, Any] = {"role": role}
        if "name" in message and message.get("name"):
            entry["name"] = message["name"]
        entry["content"] = _normalise_content(message.get("content"))
        converted.append(entry)
    return converted


def _stringify_arguments(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return orjson.dumps(value).decode("utf-8")


def _collect_output_content(
    item: dict[str, Any], text_parts: list[str], tool_calls: list[dict[str, Any]]
) -> None:
    item_type = item.get("type")
    if item_type in {"text", "output_text"}:
        text = item.get("text")
        if text:
            text_parts.append(str(text))
        return
    if item_type == "tool_call":
        tool_calls.append(
            {
                "id": item.get("id"),
                "type": "function",
                "function": {
                    "name": item.get("name"),
                    "arguments": _stringify_arguments(item.get("arguments")),
                },
            }
        )
        return
    if item_type == "message":
        for inner in item.get("content", []) or []:
            if isinstance(inner, dict):
                _collect_output_content(inner, text_parts, tool_calls)
        return
    if "text" in item and not item_type:
        text_parts.append(str(item["text"]))


def extract_responses_output(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Extract assistant text and tool calls from a Responses API payload."""

    outputs = payload.get("output") or []
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in outputs:
        if not isinstance(block, dict):
            continue
        if block.get("content"):
            for item in block["content"]:
                if isinstance(item, dict):
                    _collect_output_content(item, text_parts, tool_calls)
        else:
            _collect_output_content(block, text_parts, tool_calls)
    return ("".join(text_parts), tool_calls)


def parse_responses_event(event: dict[str, Any]) -> tuple[str | None, bool, dict[str, Any] | None]:
    event_type = event.get("type")
    if event_type == "response.output_text.delta":
        delta = event.get("delta")
        if delta is None:
            return None, False, None
        return str(delta), False, None
    if event_type == "response.completed":
        return None, True, event.get("response")
    if event_type == "response.error":
        error = event.get("error") or {}
        message = error.get("message") or "OpenAI response error"
        raise RuntimeError(message)
    # Other event types (tool calls, refusals, etc.) are ignored for streaming text
    return None, False, None


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        responses_model_patterns: Sequence[str] | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self.timeout = timeout
        patterns = responses_model_patterns or OPENAI_RESPONSES_MODELS
        self._router = _ModelRouter(patterns)
        logger.debug(
            "OpenAIProvider initialized base_url=%s timeout=%.1fs responses_patterns=%s",
            self.base_url,
            self.timeout,
            ",".join(patterns),
        )

    def _http_error(self, exc: HTTPStatusError) -> RuntimeError:
        status = exc.response.status_code if exc.response else "?"
        body: str | None = None
        if exc.response is not None:
            try:
                data = exc.response.json()
                body = orjson.dumps(data).decode("utf-8")
            except Exception:
                try:
                    body = exc.response.text
                except Exception:  # pragma: no cover - httpx guards
                    body = None
        logger.error("OpenAI HTTP error status=%s body=%s", status, body)
        message = f"OpenAI request failed with status {status}"
        if body:
            message += f": {body}"
        return RuntimeError(message)

    async def generate(self, prompt: str, **kwargs) -> LLMResult:
        messages = [{"role": "user", "content": prompt}]
        return await self.generate_chat(messages=messages, **kwargs)

    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[dict[str, str | None]]:
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self.stream_chat(messages=messages, **kwargs):
            yield chunk

    async def generate_chat(self, messages: list[dict[str, Any]], **kwargs) -> LLMResult:
        model = kwargs.get("model")
        max_tokens = kwargs.get("max_tokens")
        temperature = kwargs.get("temperature")
        top_p = kwargs.get("top_p")
        system = kwargs.get("system")
        tools = kwargs.get("tools")

        chat_messages: list[dict[str, Any]] = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        endpoint = self._router.endpoint_for(model)
        if endpoint is OpenAIEndpoint.RESPONSES:
            return await self._responses_generate(
                messages=chat_messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                tools=tools,
            )
        return await self._chat_completions_generate(
            messages=chat_messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            tools=tools,
        )

    async def stream_chat(
        self, messages: list[dict[str, Any]], **kwargs
    ) -> AsyncIterator[dict[str, str | None]]:
        model = kwargs.get("model")
        max_tokens = kwargs.get("max_tokens")
        temperature = kwargs.get("temperature")
        top_p = kwargs.get("top_p")
        system = kwargs.get("system")
        tools = kwargs.get("tools")

        chat_messages: list[dict[str, Any]] = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        endpoint = self._router.endpoint_for(model)
        if endpoint is OpenAIEndpoint.RESPONSES:
            async for chunk in self._responses_stream(
                messages=chat_messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                tools=tools,
            ):
                yield chunk
            return
        async for chunk in self._chat_completions_stream(
            messages=chat_messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            tools=tools,
        ):
            yield chunk

    def _headers(self, accept: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if accept:
            headers["Accept"] = accept
        return headers

    async def _chat_completions_generate(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None,
        max_tokens: int | None,
        temperature: float | None,
        top_p: float | None,
        tools: list[dict[str, Any]] | None,
    ) -> LLMResult:
        payload = ChatCompletionRequest(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=False,
            tools=tools,
        )

        headers = self._headers()
        t0 = time.time()
        logger.info(
            "openai.generate_chat start endpoint=%s model=%s max_tokens=%s temp=%s top_p=%s messages=%d tools=%d",
            OpenAIEndpoint.CHAT_COMPLETIONS.value,
            model,
            max_tokens,
            temperature,
            top_p,
            len(messages),
            len(tools or []),
        )
        async with httpx.AsyncClient(timeout=self.timeout, base_url=self.base_url) as client:
            resp = await client.post(
                "/chat/completions",
                json=payload.model_dump(exclude_none=True),
                headers=headers,
            )
            logger.debug("openai.generate_chat HTTP status=%s", resp.status_code)
            if resp.status_code >= 400:
                logger.error(f"🔴 OpenAI API error response: {resp.text}")
            resp.raise_for_status()
            data = resp.json()
            try:
                parsed = ChatCompletionResponse.model_validate(data)
            except ValidationError as exc:
                logger.error("openai.generate_chat validation error: %s", exc)
                raise
        text = parsed.choices[0].message.content
        usage = parsed.usage.dict(exclude_none=True) if parsed.usage else None
        raw_tool_calls = (
            ((data.get("choices") or [{}])[0].get("message") or {}).get("tool_calls")
            if isinstance(data, dict)
            else None
        )
        tool_calls = raw_tool_calls or None
        dt = time.time() - t0
        logger.info(
            "openai.generate_chat done endpoint=%s model=%s reply_len=%d tool_calls=%d elapsed=%.3fs",
            OpenAIEndpoint.CHAT_COMPLETIONS.value,
            model,
            len(text or ""),
            len(tool_calls or []),
            dt,
        )
        logger.debug("usage=%s", usage)
        return LLMResult(
            text=text, usage=usage, model=model, provider=self.name, tool_calls=tool_calls
        )

    async def _responses_generate(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None,
        max_tokens: int | None,
        temperature: float | None,
        top_p: float | None,
        tools: list[dict[str, Any]] | None,
    ) -> LLMResult:
        payload: dict[str, Any] = {
            "model": model,
            "input": build_responses_input(messages),
            "temperature": temperature,
            "top_p": top_p,
        }
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools

        headers = self._headers()
        t0 = time.time()
        logger.info(
            "openai.generate_chat start endpoint=%s model=%s max_tokens=%s temp=%s top_p=%s messages=%d tools=%d",
            OpenAIEndpoint.RESPONSES.value,
            model,
            max_tokens,
            temperature,
            top_p,
            len(messages),
            len(tools or []),
        )
        async with httpx.AsyncClient(timeout=self.timeout, base_url=self.base_url) as client:
            try:
                resp = await client.post(
                    "/responses",
                    json={k: v for k, v in payload.items() if v is not None},
                    headers=headers,
                )
                logger.debug("openai.generate_chat HTTP status=%s", resp.status_code)
                resp.raise_for_status()
            except HTTPStatusError as exc:
                raise self._http_error(exc) from exc
            data = resp.json()

        text, tool_calls = extract_responses_output(data)
        usage = data.get("usage") if isinstance(data, dict) else None
        dt = time.time() - t0
        logger.info(
            "openai.generate_chat done endpoint=%s model=%s reply_len=%d tool_calls=%d elapsed=%.3fs",
            OpenAIEndpoint.RESPONSES.value,
            model,
            len(text or ""),
            len(tool_calls),
            dt,
        )
        logger.debug("usage=%s", usage)
        return LLMResult(
            text=text,
            usage=usage,
            model=model,
            provider=self.name,
            tool_calls=tool_calls or None,
        )

    async def _chat_completions_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None,
        max_tokens: int | None,
        temperature: float | None,
        top_p: float | None,
        tools: list[dict[str, Any]] | None,
    ) -> AsyncIterator[dict[str, str | None]]:
        payload = ChatCompletionRequest(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=True,
            tools=tools,
        )

        headers = self._headers("text/event-stream")
        t0 = time.time()
        first_dt: float | None = None
        total_len = 0
        chunks = 0
        logger.info(
            "openai.stream_chat start endpoint=%s model=%s temp=%s top_p=%s messages=%d tools=%d",
            OpenAIEndpoint.CHAT_COMPLETIONS.value,
            model,
            temperature,
            top_p,
            len(messages),
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
                    if not line or line.startswith(":"):
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
                    except ValidationError as exc:
                        logger.debug("openai.stream_chat JSON parse error: %s", exc)
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
                        logger.debug(
                            "openai.stream_chat chunk endpoint=%s #%d len=%d",
                            OpenAIEndpoint.CHAT_COMPLETIONS.value,
                            chunks,
                            len(text),
                        )
                        yield {"delta": text}
        dt = time.time() - t0
        logger.info(
            "openai.stream_chat done endpoint=%s chunks=%d total_len=%d elapsed=%.3fs first_token_latency=%.3fs",
            OpenAIEndpoint.CHAT_COMPLETIONS.value,
            chunks,
            total_len,
            dt,
            -1.0 if first_dt is None else first_dt,
        )

    async def _responses_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None,
        max_tokens: int | None,
        temperature: float | None,
        top_p: float | None,
        tools: list[dict[str, Any]] | None,
    ) -> AsyncIterator[dict[str, str | None]]:
        payload: dict[str, Any] = {
            "model": model,
            "input": build_responses_input(messages),
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools

        headers = self._headers("text/event-stream")
        t0 = time.time()
        first_dt: float | None = None
        total_len = 0
        chunks = 0
        completed_payload: dict[str, Any] | None = None
        logger.info(
            "openai.stream_chat start endpoint=%s model=%s temp=%s top_p=%s messages=%d tools=%d",
            OpenAIEndpoint.RESPONSES.value,
            model,
            temperature,
            top_p,
            len(messages),
            len(tools or []),
        )
        async with httpx.AsyncClient(timeout=None, base_url=self.base_url) as client:
            async with client.stream(
                "POST",
                "/responses",
                json={k: v for k, v in payload.items() if v is not None},
                headers=headers,
            ) as resp:
                logger.debug("openai.stream_chat HTTP status=%s", resp.status_code)
                try:
                    resp.raise_for_status()
                except HTTPStatusError as exc:
                    raise self._http_error(exc) from exc
                async for line in resp.aiter_lines():
                    if not line or line.startswith(":"):
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
                        logger.debug("openai.stream_chat responses received [DONE]")
                        break
                    try:
                        event = orjson.loads(data_str)
                    except orjson.JSONDecodeError as exc:
                        logger.debug("openai.stream_chat responses parse error: %s", exc)
                        continue
                    try:
                        delta_text, done, response_payload = parse_responses_event(event)
                    except RuntimeError as exc:
                        logger.error("openai.stream_chat responses error: %s", exc)
                        raise
                    if delta_text:
                        if first_dt is None:
                            first_dt = time.time() - t0
                            logger.info("openai.stream_chat first_token_latency=%.3fs", first_dt)
                        total_len += len(delta_text)
                        chunks += 1
                        logger.debug(
                            "openai.stream_chat chunk endpoint=%s #%d len=%d",
                            OpenAIEndpoint.RESPONSES.value,
                            chunks,
                            len(delta_text),
                        )
                        yield {"delta": delta_text}
                    if response_payload:
                        completed_payload = response_payload
                    if done:
                        logger.debug("openai.stream_chat responses completed event received")
                        break
        dt = time.time() - t0
        logger.info(
            "openai.stream_chat done endpoint=%s chunks=%d total_len=%d elapsed=%.3fs first_token_latency=%.3fs",
            OpenAIEndpoint.RESPONSES.value,
            chunks,
            total_len,
            dt,
            -1.0 if first_dt is None else first_dt,
        )
        if completed_payload:
            usage = completed_payload.get("usage") if isinstance(completed_payload, dict) else None
            if usage:
                logger.debug("responses stream usage=%s", usage)
