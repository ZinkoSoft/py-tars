from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse
from typing import Any, Dict

import asyncio_mqtt as mqtt
import orjson as json

from .config import (
    MQTT_URL,
    LOG_LEVEL,
    LLM_PROVIDER,
    LLM_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_TOP_P,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    RAG_ENABLED,
    RAG_TOP_K,
    RAG_PROMPT_TEMPLATE,
    TOPIC_LLM_REQUEST,
    TOPIC_LLM_RESPONSE,
    TOPIC_LLM_STREAM,
    TOPIC_LLM_CANCEL,
    TOPIC_HEALTH,
    TOPIC_MEMORY_QUERY,
    TOPIC_MEMORY_RESULTS,
    TOPIC_CHARACTER_CURRENT,
    TOPIC_CHARACTER_GET,
    TOPIC_CHARACTER_RESULT,
    # TTS streaming config
    LLM_TTS_STREAM,
    TOPIC_TTS_SAY,
    STREAM_MIN_CHARS,
    STREAM_MAX_CHARS,
    STREAM_BOUNDARY_CHARS,
)
from .providers.openai import OpenAIProvider


logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("llm-worker")


def parse_mqtt(url: str):
    u = urlparse(url)
    return (u.hostname or "127.0.0.1", u.port or 1883, u.username, u.password)


class LLMService:
    def __init__(self):
        # Provider selection (only OpenAI for now)
        provider = LLM_PROVIDER.lower()
        if provider == "openai":
            self.provider = OpenAIProvider(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL or None)
        else:
            logger.warning("Unsupported provider '%s', defaulting to openai", provider)
            self.provider = OpenAIProvider(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL or None)
        # Character/persona state (loaded via MQTT retained message)
        self.character: Dict[str, Any] = {}

    def _build_system_prompt(self, base_system: str | None = None) -> str | None:
        """Combine character persona and optional base system prompt.

        Expected character snapshot schema:
        { name, description, systemprompt, traits: { ... }, voice: { ... }, meta: { ... } }
        Priority:
        1) If character.systemprompt is provided, use it, and also append a compact traits line when traits exist.
        2) Otherwise, render compact persona from traits and description.
        Then append any base_system provided by the caller.
        """
        persona = None
        try:
            logger.debug("Building system prompt from character/current: %s", self.character or "<none>")
            if self.character:
                logger.info("Building system prompt from character/current: name=%s", self.character.get("name"))
                name = self.character.get("name") or "Assistant"
                sys_prompt = (self.character.get("systemprompt") or "").strip()
                traits = self.character.get("traits") or {}
                desc = self.character.get("description") or (self.character.get("meta") or {}).get("description")

                parts: list[str] = []
                if sys_prompt:
                    parts.append(sys_prompt)

                # Always append traits line if traits exist
                if traits:
                    trait_pairs = [f"{k}: {v}" for k, v in traits.items()]
                    trait_line = f"You are {name}. Traits: " + "; ".join(trait_pairs) + "."
                    if desc:
                        trait_line = (trait_line + " " + str(desc)).strip()
                    parts.append(trait_line)
                elif not sys_prompt:
                    # No systemprompt and no traits: fallback minimal persona (optionally with description)
                    fallback = f"You are {name}."
                    if desc:
                        fallback = (fallback + " " + str(desc)).strip()
                    parts.append(fallback)

                persona = "\n".join(p for p in parts if p).strip() or None
        except Exception:
            logger.warning("Failed to build system prompt from character/current")
            persona = None
        logger.debug("Built system prompt from character: %s", persona or "<none>")
        if base_system and persona:
            logger.debug("Combining with base system prompt of length %d", len(base_system or ""))
            return persona + "\n\n" + base_system
        logger.debug("Final system prompt set to %s", base_system or persona or "<none>")
        return base_system or persona

    def _should_flush(self, buf: str, incoming: str) -> bool:
        # Flush when boundary punctuation present (no min length),
        # or when adding incoming would exceed max
        if any(ch in buf for ch in STREAM_BOUNDARY_CHARS):
            return True
        return len(buf) + len(incoming) >= STREAM_MAX_CHARS

    def _split_on_boundary(self, text: str) -> tuple[str, str]:
        # Split at last boundary in text; return (sentence, remainder)
        idx = max((text.rfind(ch) for ch in STREAM_BOUNDARY_CHARS), default=-1)
        if idx >= 0:
            return text[: idx + 1].strip(), text[idx + 1 :].lstrip()
        return "", text

    async def _do_rag(self, client, prompt: str) -> str:
        try:
            payload = {"text": prompt, "top_k": RAG_TOP_K}
            await client.publish(TOPIC_MEMORY_QUERY, json.dumps(payload))
            # Wait for a single memory/results message; simple heuristic for MVP
            async with client.messages() as mstream:
                await client.subscribe(TOPIC_MEMORY_RESULTS)
                async for m in mstream:
                    try:
                        data = json.loads(m.payload)
                    except Exception:
                        continue
                    results = data.get("results") or []
                    if not results:
                        return ""
                    snippets = []
                    for r in results[:RAG_TOP_K]:
                        doc = r.get("document") or {}
                        t = doc.get("text") or json.dumps(doc)
                        snippets.append(t)
                    return "\n".join(snippets)
        except Exception as e:
            logger.warning("RAG failed: %s", e)
        return ""

    async def run(self):
        host, port, user, pwd = parse_mqtt(MQTT_URL)
        logger.info("Connecting to MQTT %s:%s", host, port)
        try:
            async with mqtt.Client(hostname=host, port=port, username=user, password=pwd, client_id="tars-llm") as client:
                await client.publish(TOPIC_HEALTH, json.dumps({"ok": True, "event": "ready"}), retain=True)
                async with client.messages() as mstream:
                    # Subscribe to LLM requests and character/current (retained)
                    await client.subscribe(TOPIC_LLM_REQUEST)
                    await client.subscribe(TOPIC_CHARACTER_CURRENT)
                    await client.subscribe(TOPIC_CHARACTER_RESULT)
                    logger.info("Subscribed to %s, %s and %s", TOPIC_LLM_REQUEST, TOPIC_CHARACTER_CURRENT, TOPIC_CHARACTER_RESULT)
                    # Request the current character snapshot once (memory-worker should respond or retained current will arrive)
                    try:
                        await client.publish(TOPIC_CHARACTER_GET, json.dumps({"section": None}))
                        logger.info("Requested character/get on startup")
                    except Exception:
                        logger.debug("character/get publish failed (may be offline)")
                    async for m in mstream:
                        topic = str(getattr(m, "topic", ""))
                        if topic == TOPIC_CHARACTER_CURRENT:
                            # Update persona from retained/current payload
                            try:
                                self.character = json.loads(m.payload)
                                logger.info("character/current updated: name=%s", self.character.get("name"))
                            except Exception:
                                logger.warning("Failed to parse character/current")
                            continue
                        if topic == TOPIC_CHARACTER_RESULT:
                            try:
                                data = json.loads(m.payload)
                            except Exception:
                                data = {}
                            if data:
                                # Accept either full snapshot or a subsection
                                if "name" in data:
                                    self.character = data
                                else:
                                    # Merge into existing snapshot
                                    self.character.update(data)
                                logger.info("character/result received: name=%s", self.character.get("name"))
                            continue
                        if topic != TOPIC_LLM_REQUEST:
                            continue
                        try:
                            req = json.loads(m.payload)
                        except Exception:
                            logger.warning("Invalid request payload (non-JSON)")
                            continue
                        logger.info("llm/request received: %s", req)
                        req_id = req.get("id") or ""
                        text = (req.get("text") or "").strip()
                        if not text:
                            continue
                        want_stream = bool(req.get("stream", False))
                        use_rag = bool(req.get("use_rag", RAG_ENABLED))
                        rag_k = int(req.get("rag_k", RAG_TOP_K))
                        system = req.get("system")
                        params = req.get("params") or {}
                        model = params.get("model", LLM_MODEL)
                        max_tokens = int(params.get("max_tokens", LLM_MAX_TOKENS))
                        temperature = float(params.get("temperature", LLM_TEMPERATURE))
                        top_p = float(params.get("top_p", LLM_TOP_P))

                        # Merge character persona into system prompt
                        system = self._build_system_prompt(system)

                        context = ""
                        if use_rag:
                            context = await self._do_rag(client, text)
                        prompt = text
                        if context:
                            prompt = RAG_PROMPT_TEMPLATE.format(context=context, user=text)

                        # Fast-fail when required creds are missing (avoid long HTTP timeouts)
                        if isinstance(self.provider, OpenAIProvider) and not OPENAI_API_KEY:
                            logger.warning("OPENAI_API_KEY not set; responding with error for id=%s", req_id)
                            await client.publish(
                                TOPIC_LLM_RESPONSE,
                                json.dumps({"id": req_id, "error": "OPENAI_API_KEY not set", "provider": self.provider.name, "model": model}),
                            )
                            continue

                        try:
                            if want_stream and getattr(self.provider, "name", "") == "openai":
                                seq = 0
                                logger.info("Starting streaming for id=%s via provider=%s (system_len=%s)", req_id, self.provider.name, len(system or ""))
                                tts_buf = ""
                                async for ch in self.provider.stream(
                                    prompt,
                                    model=model,
                                    max_tokens=max_tokens,
                                    temperature=temperature,
                                    top_p=top_p,
                                    system=system,
                                ):
                                    seq += 1
                                    out = {"id": req_id, "seq": seq, "delta": ch.get("delta"), "done": False, "provider": self.provider.name, "model": model}
                                    logger.debug("llm/stream id=%s seq=%d len=%d", req_id, seq, len(out.get("delta") or ""))
                                    await client.publish(TOPIC_LLM_STREAM, json.dumps(out))
                                    # Optional: accumulate and forward sentences to TTS.
                                    # Note: Router now bridges LLM -> TTS by default; this path remains behind LLM_TTS_STREAM flag for testing.
                                    if LLM_TTS_STREAM:
                                        delta = out.get("delta") or ""
                                        if delta:
                                            tts_buf += delta
                                            # If multiple sentence boundaries arrived at once, flush repeatedly
                                            while self._should_flush(tts_buf, ""):
                                                sent, remainder = self._split_on_boundary(tts_buf)
                                                if not sent:
                                                    break
                                                logger.info("TTS chunk publish len=%d", len(sent))
                                                await client.publish(TOPIC_TTS_SAY, json.dumps({"text": sent}))
                                                tts_buf = remainder
                                # Stream end
                                done = {"id": req_id, "seq": seq + 1, "done": True}
                                logger.info("Streaming done for id=%s with %d chunks", req_id, seq)
                                await client.publish(TOPIC_LLM_STREAM, json.dumps(done))
                                # Flush any remainder
                                if LLM_TTS_STREAM and tts_buf.strip():
                                    final_sent = tts_buf.strip()
                                    logger.info("TTS final chunk publish len=%d", len(final_sent))
                                    await client.publish(TOPIC_TTS_SAY, json.dumps({"text": final_sent}))
                            else:
                                result = await self.provider.generate(
                                    prompt,
                                    model=model,
                                    max_tokens=max_tokens,
                                    temperature=temperature,
                                    top_p=top_p,
                                    system=system,
                                )
                                resp = {
                                    "id": req_id,
                                    "reply": result.text,
                                    "provider": self.provider.name,
                                    "model": model,
                                    "tokens": result.usage or {},
                                }
                                logger.info("Publishing llm/response for id=%s (len=%d)", req_id, len(result.text or ""))
                                await client.publish(TOPIC_LLM_RESPONSE, json.dumps(resp))
                        except Exception as e:
                            logger.exception("generation failed")
                            await client.publish(
                                TOPIC_LLM_RESPONSE,
                                json.dumps({"id": req_id, "error": str(e), "provider": self.provider.name, "model": model}),
                            )
        except Exception as e:
            logger.info("MQTT disconnected or error: %s; shutting down gracefully", e)


def main() -> int:
    svc = LLMService()
    asyncio.run(svc.run())
    return 0
