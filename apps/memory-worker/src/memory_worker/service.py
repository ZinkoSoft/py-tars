from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import asyncio_mqtt as mqtt  # For type hints only
import numpy as np
import orjson as json
from pydantic import ValidationError
from sentence_transformers import SentenceTransformer

from tars.adapters.mqtt_client import MQTTClient
from .config import (
    CHARACTER_DIR,
    CHARACTER_NAME,
    EMBED_MODEL,
    LOG_LEVEL,
    MEMORY_DIR,
    MEMORY_FILE,
    MQTT_URL,
    RAG_STRATEGY,
    TOPIC_CHAR_CURRENT,
    TOPIC_CHAR_GET,
    TOPIC_CHAR_RESULT,
    TOPIC_CHAR_UPDATE,
    TOPIC_HEALTH,
    TOPIC_QUERY,
    TOPIC_RESULTS,
    TOPIC_STT_FINAL,
    TOPIC_TTS_SAY,
    TOP_K,
)
from .hyperdb import HyperConfig, HyperDB

from tars.contracts.envelope import Envelope
from tars.contracts.registry import register
from tars.contracts.v1 import (
    EVENT_TYPE_SAY,
    EVENT_TYPE_STT_FINAL,
    FinalTranscript,
    HealthPing,
    TtsSay,
)
from tars.contracts.v1.memory import (
    EVENT_TYPE_CHARACTER_CURRENT,
    EVENT_TYPE_CHARACTER_GET,
    EVENT_TYPE_CHARACTER_RESULT,
    EVENT_TYPE_CHARACTER_UPDATE,
    EVENT_TYPE_MEMORY_HEALTH,
    EVENT_TYPE_MEMORY_QUERY,
    EVENT_TYPE_MEMORY_RESULTS,
    CharacterGetRequest,
    CharacterResetTraits,
    CharacterSection,
    CharacterSnapshot,
    CharacterTraitUpdate,
    MemoryQuery,
    MemoryResult,
    MemoryResults,
)

try:  # pragma: no cover - compatibility shim
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover - fallback for <=3.10
    import tomli as tomllib  # type: ignore


SOURCE_NAME = "memory-worker"

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("memory-worker")

# Suppress verbose third-party library logging
logging.getLogger("bm25s").setLevel(logging.WARNING)


class STEmbedder:
    """SentenceTransformer embedding wrapper with async support.

    Uses asyncio.to_thread() to offload CPU-bound embedding computation,
    keeping the event loop responsive during memory operations.
    """

    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name, device="cpu")
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="embed")

    def __call__(self, texts: list[str]) -> np.ndarray:
        """Synchronous embedding (blocks for CPU-bound computation).

        For async contexts, prefer embed_async() to avoid blocking the event loop.
        """
        return self._encode_sync(texts)

    def _encode_sync(self, texts: list[str]) -> np.ndarray:
        """Internal sync implementation of encoding."""
        embeddings = self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.astype(np.float32)

    async def embed_async(self, texts: list[str]) -> np.ndarray:
        """Async wrapper for embedding using thread pool.

        Offloads CPU-bound SentenceTransformer encoding to avoid blocking
        the event loop during MQTT message processing.

        Args:
            texts: List of text strings to embed

        Returns:
            numpy array of embeddings (normalized float32)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._encode_sync, texts)


class MemoryService:
    def __init__(self) -> None:
        self._register_topics()
        os.makedirs(MEMORY_DIR, exist_ok=True)
        self.database_path = os.path.join(MEMORY_DIR, MEMORY_FILE)

        # Create embedder with automatic NPU/CPU detection
        from .embedder_factory import create_embedder

        self.embedder = create_embedder(EMBED_MODEL)

        rerank_model = os.getenv(
            "RERANK_MODEL", None
        )  # None = disabled (faster), "ms-marco-MiniLM-L-12-v2" = enabled (slower but better)
        self.db = HyperDB(
            embedding_fn=self.embedder,
            cfg=HyperConfig(rag_strategy=RAG_STRATEGY, top_k=TOP_K, rerank_model=rerank_model),
        )
        self._load_or_initialize_db()
        self.character = self._load_character()
        self.mqtt_client = MQTTClient(
            MQTT_URL,
            client_id="tars-memory",
            source_name=SOURCE_NAME,
            enable_health=True,
            enable_heartbeat=True,
        )

    def _register_topics(self) -> None:
        register(EVENT_TYPE_MEMORY_QUERY, TOPIC_QUERY)
        register(EVENT_TYPE_MEMORY_RESULTS, TOPIC_RESULTS)
        register(EVENT_TYPE_MEMORY_HEALTH, TOPIC_HEALTH)
        register(EVENT_TYPE_CHARACTER_GET, TOPIC_CHAR_GET)
        register(EVENT_TYPE_CHARACTER_RESULT, TOPIC_CHAR_RESULT)
        register(EVENT_TYPE_CHARACTER_CURRENT, TOPIC_CHAR_CURRENT)
        register(EVENT_TYPE_CHARACTER_UPDATE, TOPIC_CHAR_UPDATE)
        register(EVENT_TYPE_STT_FINAL, TOPIC_STT_FINAL)
        register(EVENT_TYPE_SAY, TOPIC_TTS_SAY)

    def _load_or_initialize_db(self) -> None:
        if not os.path.exists(self.database_path):
            return
        try:
            loaded = self.db.load(self.database_path)
            logger.info("Loaded memory db from %s: %s", self.database_path, loaded)
            if loaded:
                self._reconcile_embedding_dim()
        except Exception:
            logger.exception("Failed to load memory database")

    def _reconcile_embedding_dim(self) -> None:
        try:
            vectors = self.db.vectors
            if vectors is None or getattr(vectors, "size", 0) == 0:
                return
            vectors_shape = tuple(vectors.shape)
            current_dim = vectors_shape[1] if len(vectors_shape) == 2 else vectors_shape[-1]
            probe = self.embedder(["dim_check"])
            probe_shape = tuple(probe.shape)
            embed_dim = probe_shape[1] if len(probe_shape) == 2 else probe_shape[0]
            logger.info(
                "Memory vectors dim=%s embedder dim=%s docs=%s",
                current_dim,
                embed_dim,
                len(self.db.documents),
            )
            if current_dim == embed_dim:
                return
            logger.info(
                "Embedding dim changed %s -> %s; re-embedding %s docs",
                current_dim,
                embed_dim,
                len(self.db.documents),
            )
            texts = [self.db._doc_to_text(doc) for doc in self.db.documents]
            self.db.vectors = self.embedder(texts).astype(np.float32)
            self.db._ensure_bm25()
            try:
                self.db.save(self.database_path)
            except Exception:
                logger.debug("Failed to persist reconciled memory db", exc_info=True)
        except Exception:
            logger.warning("Could not reconcile embedding dimensions", exc_info=True)

    async def run(self) -> None:
        """Main service loop with subscription-based message handling."""
        try:
            # Connect to MQTT broker
            await self.mqtt_client.connect()
            logger.info("Connected to MQTT broker")

            # Publish initial health and character state
            await self._publish_health_initial()
            await self._publish_character_current_initial()

            # Subscribe to all topics with individual handlers
            await self.mqtt_client.subscribe(TOPIC_QUERY, self._handle_query_message)
            await self.mqtt_client.subscribe(TOPIC_CHAR_GET, self._handle_char_get_message)
            await self.mqtt_client.subscribe(TOPIC_CHAR_UPDATE, self._handle_char_update_message)
            await self.mqtt_client.subscribe(TOPIC_STT_FINAL, self._handle_ingest_message)
            await self.mqtt_client.subscribe(TOPIC_TTS_SAY, self._handle_ingest_message)

            logger.info("Memory worker ready - processing messages via subscription handlers")

            # Keep service running (centralized client handles message dispatch)
            await asyncio.Event().wait()

        except Exception as exc:  # pragma: no cover - network layer
            logger.error("Memory worker error: %s", exc, exc_info=True)
        finally:
            await self.mqtt_client.shutdown()
            logger.info("Memory worker shutdown complete")

    # --- Initial publish helpers ---

    async def _publish_health_initial(self) -> None:
        """Publish initial health status on startup."""
        await self.mqtt_client.publish_event(
            topic=TOPIC_HEALTH,
            event_type=EVENT_TYPE_MEMORY_HEALTH,
            data=HealthPing(ok=True, event="ready"),
            qos=1,
            retain=True,
        )

    async def _publish_character_current_initial(self) -> None:
        """Publish initial character state on startup."""
        await self.mqtt_client.publish_event(
            topic=TOPIC_CHAR_CURRENT,
            event_type=EVENT_TYPE_CHARACTER_CURRENT,
            data=self.character,
            correlation_id=self.character.message_id,
            qos=1,
            retain=True,
        )

    # --- Subscription Handlers ---

    async def _handle_query_message(self, payload: bytes) -> None:
        """Handle memory/query subscription message."""
        try:
            query, correlate = self._decode_memory_query(payload)
            if query is None or not query.text.strip():
                logger.info("Ignored empty memory/query message")
                return
            await self._handle_memory_query(self.mqtt_client.client, query, correlate)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Error handling memory/query")
            await self._publish_health(self.mqtt_client.client, ok=False, err=str(exc), retain=True)

    async def _handle_char_get_message(self, payload: bytes) -> None:
        """Handle character/get subscription message."""
        try:
            request, correlate = self._decode_character_get(payload)
            await self._handle_char_get(self.mqtt_client.client, request, correlate)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Error handling character/get")
            await self._publish_health(self.mqtt_client.client, ok=False, err=str(exc), retain=True)

    async def _handle_char_update_message(self, payload: bytes) -> None:
        """Handle character/update subscription message."""
        try:
            await self._handle_character_update(self.mqtt_client.client, payload)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Error handling character/update")
            await self._publish_health(self.mqtt_client.client, ok=False, err=str(exc), retain=True)

    async def _handle_ingest_message(self, payload: bytes) -> None:
        """Handle stt/final or tts/say subscription message."""
        try:
            # Determine topic from payload (we can infer from structure or use a wrapper)
            # For now, let's just ingest both types similarly
            await self._ingest_document("ingestion", payload)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Error handling ingestion")
            await self._publish_health(self.mqtt_client.client, ok=False, err=str(exc), retain=True)

    # --- Original handler methods (updated signatures) ---

    async def _publish_health(
        self,
        client: mqtt.Client,
        *,
        ok: bool,
        event: str | None = None,
        err: str | None = None,
        retain: bool = False,
    ) -> None:
        payload = HealthPing(ok=ok, event=event, err=err)
        await self.mqtt_client.publish_event(
            topic=TOPIC_HEALTH,
            event_type=EVENT_TYPE_MEMORY_HEALTH,
            data=payload,
            correlation_id=None,
            qos=1,
            retain=retain,
        )

    async def _publish_character_current(self, client: mqtt.Client) -> None:
        await self.mqtt_client.publish_event(
            topic=TOPIC_CHAR_CURRENT,
            event_type=EVENT_TYPE_CHARACTER_CURRENT,
            data=self.character,
            correlation_id=self.character.message_id,
            qos=1,
            retain=True,
        )

    def _extract_text_from_doc(self, doc: Any) -> str:
        """Extract text content from a document for token counting."""
        if isinstance(doc, dict):
            # Prefer specific fields if present
            text_parts = []
            if "user_input" in doc:
                text_parts.append(str(doc["user_input"]))
            if "bot_response" in doc:
                text_parts.append(str(doc["bot_response"]))
            if "text" in doc:
                text_parts.append(str(doc["text"]))
            if text_parts:
                return " ".join(text_parts)
            # Fallback to all values
            return " ".join(str(v) for v in doc.values() if v)
        return str(doc)

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (can be improved with tiktoken later)."""
        return int(len(text.split()) * 1.3)

    async def _query_with_token_limit(
        self, query: str, max_tokens: int, top_k: int = 5
    ) -> list[MemoryResult]:
        """Token-aware memory retrieval."""
        accumulated_results = []
        accumulated_tokens = 0

        # Get base results from hybrid retrieval (fetch more to allow filtering)
        base_results = await self.db.query_async(query, top_k=top_k * 2)

        for doc, score in base_results:
            text = self._extract_text_from_doc(doc)
            doc_tokens = self._estimate_tokens(text)

            if accumulated_tokens + doc_tokens > max_tokens and accumulated_results:
                break

            # Include timestamp if available
            timestamp = None
            if isinstance(doc, dict) and "timestamp" in doc:
                timestamp = str(doc["timestamp"])

            accumulated_results.append(
                MemoryResult(
                    document=doc if isinstance(doc, dict) else {"text": str(doc)},
                    score=float(score),
                    timestamp=timestamp,
                    context_type="target",
                    token_count=doc_tokens,
                )
            )
            accumulated_tokens += doc_tokens

        return accumulated_results[:top_k]

    async def _get_context_window(
        self, target_indices: list[int], window_size: int = 1
    ) -> list[MemoryResult]:
        """Get surrounding context for target documents."""
        if not target_indices or window_size <= 0:
            return []

        context_results = []
        all_docs = self.db.documents

        for idx in target_indices:
            # Add previous context
            for i in range(max(0, idx - window_size), idx):
                if i < len(all_docs):
                    doc = all_docs[i]
                    text = self._extract_text_from_doc(doc)
                    timestamp = None
                    if isinstance(doc, dict) and "timestamp" in doc:
                        timestamp = str(doc["timestamp"])

                    context_results.append(
                        MemoryResult(
                            document=doc if isinstance(doc, dict) else {"text": str(doc)},
                            score=0.0,
                            timestamp=timestamp,
                            context_type="previous",
                            token_count=self._estimate_tokens(text),
                        )
                    )

            # Add next context
            for i in range(idx + 1, min(len(all_docs), idx + window_size + 1)):
                doc = all_docs[i]
                text = self._extract_text_from_doc(doc)
                timestamp = None
                if isinstance(doc, dict) and "timestamp" in doc:
                    timestamp = str(doc["timestamp"])

                context_results.append(
                    MemoryResult(
                        document=doc if isinstance(doc, dict) else {"text": str(doc)},
                        score=0.0,
                        timestamp=timestamp,
                        context_type="next",
                        token_count=self._estimate_tokens(text),
                    )
                )

        return context_results

    async def _query_recent_memories(
        self, max_tokens: int, max_entries: int = 20
    ) -> list[MemoryResult]:
        """Get recent memories within token budget."""
        if not self.db.documents:
            return []

        recent_docs = self.db.documents[-max_entries:]
        accumulated_results = []
        accumulated_tokens = 0

        for doc in reversed(recent_docs):  # Most recent first
            text = self._extract_text_from_doc(doc)
            doc_tokens = self._estimate_tokens(text)

            if accumulated_tokens + doc_tokens > max_tokens and accumulated_results:
                break

            timestamp = None
            if isinstance(doc, dict) and "timestamp" in doc:
                timestamp = str(doc["timestamp"])

            accumulated_results.append(
                MemoryResult(
                    document=doc if isinstance(doc, dict) else {"text": str(doc)},
                    score=1.0,  # Recent = high relevance
                    timestamp=timestamp,
                    context_type="target",
                    token_count=doc_tokens,
                )
            )
            accumulated_tokens += doc_tokens

        return list(reversed(accumulated_results))  # Restore chronological order

    async def _handle_memory_query(
        self,
        client: mqtt.Client,
        query: MemoryQuery,
        correlate: str | None,
    ) -> None:
        """Enhanced memory query handler with token awareness and context expansion."""
        logger.info(
            "Memory query: strategy=%s, max_tokens=%s, include_context=%s, top_k=%d",
            query.retrieval_strategy,
            query.max_tokens,
            query.include_context,
            query.top_k,
        )

        hits = []
        total_tokens = 0
        strategy_used = query.retrieval_strategy
        truncated = False

        # Route to appropriate retrieval strategy
        if query.retrieval_strategy == "recent":
            if query.max_tokens:
                hits = await self._query_recent_memories(query.max_tokens, query.top_k * 2)
            else:
                # Fallback to standard recent retrieval
                recent_docs = self.db.documents[-query.top_k :]
                hits = [
                    MemoryResult(
                        document=doc if isinstance(doc, dict) else {"text": str(doc)},
                        score=1.0,
                        timestamp=(
                            str(doc.get("timestamp"))
                            if isinstance(doc, dict) and "timestamp" in doc
                            else None
                        ),
                        context_type="target",
                        token_count=self._estimate_tokens(self._extract_text_from_doc(doc)),
                    )
                    for doc in reversed(recent_docs)
                ]

        elif query.retrieval_strategy == "similarity":
            # Pure vector similarity without token limits
            results = await self.db.query_async(query.text, top_k=query.top_k)
            hits = [
                MemoryResult(
                    document=doc if isinstance(doc, dict) else {"text": str(doc)},
                    score=float(score),
                    timestamp=(
                        str(doc.get("timestamp"))
                        if isinstance(doc, dict) and "timestamp" in doc
                        else None
                    ),
                    context_type="target",
                    token_count=self._estimate_tokens(self._extract_text_from_doc(doc)),
                )
                for doc, score in results
            ]

        else:  # "hybrid" - default
            if query.max_tokens:
                hits = await self._query_with_token_limit(query.text, query.max_tokens, query.top_k)
            else:
                # Standard hybrid retrieval
                results = await self.db.query_async(query.text, top_k=query.top_k)
                hits = [
                    MemoryResult(
                        document=doc if isinstance(doc, dict) else {"text": str(doc)},
                        score=float(score),
                        timestamp=(
                            str(doc.get("timestamp"))
                            if isinstance(doc, dict) and "timestamp" in doc
                            else None
                        ),
                        context_type="target",
                        token_count=self._estimate_tokens(self._extract_text_from_doc(doc)),
                    )
                    for doc, score in results
                ]

        # Add context expansion if requested
        if query.include_context and query.context_window > 0 and hits:
            # Find indices of target documents in the database
            target_indices = []
            for hit in hits:
                if hit.context_type == "target":
                    try:
                        idx = self.db.documents.index(hit.document)
                        target_indices.append(idx)
                    except (ValueError, AttributeError):
                        pass  # Document not found in original list

            if target_indices:
                context_hits = await self._get_context_window(target_indices, query.context_window)

                # Apply token limit to context if specified
                if query.max_tokens:
                    current_tokens = sum(hit.token_count or 0 for hit in hits)
                    remaining_tokens = query.max_tokens - current_tokens

                    if remaining_tokens > 0:
                        filtered_context = []
                        context_tokens = 0
                        for context_hit in context_hits:
                            hit_tokens = context_hit.token_count or 0
                            if context_tokens + hit_tokens <= remaining_tokens:
                                filtered_context.append(context_hit)
                                context_tokens += hit_tokens
                            else:
                                truncated = True
                                break
                        context_hits = filtered_context

                # Merge context with target results (context first, then targets)
                hits = context_hits + hits

        # Calculate total tokens
        total_tokens = sum(hit.token_count or 0 for hit in hits)

        # Check if we had to truncate
        if query.max_tokens and total_tokens >= query.max_tokens:
            truncated = True

        payload = MemoryResults(
            query=query.text,
            k=len([h for h in hits if h.context_type == "target"]),
            results=hits,
            total_tokens=total_tokens,
            strategy_used=strategy_used,
            truncated=truncated,
        )

        logger.info(
            "Memory results: %d total (%d targets), %d tokens, truncated=%s",
            len(hits),
            len([h for h in hits if h.context_type == "target"]),
            total_tokens,
            truncated,
        )

        await self.mqtt_client.publish_event(
            topic=TOPIC_RESULTS,
            event_type=EVENT_TYPE_MEMORY_RESULTS,
            data=payload,
            correlation_id=correlate or query.message_id,
            qos=1,
            retain=False,
        )

    async def _handle_char_get(
        self,
        client: mqtt.Client,
        request: CharacterGetRequest,
        correlate: str | None,
    ) -> None:
        snapshot_dict = self.character.model_dump()
        if not request.section:
            await self.mqtt_client.publish_event(
                topic=TOPIC_CHAR_RESULT,
                event_type=EVENT_TYPE_CHARACTER_RESULT,
                data=self.character,
                correlation_id=correlate or request.message_id,
                qos=0,
                retain=False,
            )
            return
        section = request.section
        if section in snapshot_dict:
            value: Any = snapshot_dict[section]
        else:
            value = {
                "error": f"unknown section '{section}'",
                "available": list(snapshot_dict.keys()),
            }
        payload = CharacterSection(section=section, value=value)
        await self.mqtt_client.publish_event(
            topic=TOPIC_CHAR_RESULT,
            event_type=EVENT_TYPE_CHARACTER_RESULT,
            data=payload,
            correlation_id=correlate or request.message_id,
            qos=0,
            retain=False,
        )

    async def _handle_character_update(self, client: mqtt.Client, payload: bytes) -> None:
        """Handle character/update messages to modify traits dynamically.

        Supported operations (typed with Pydantic models):
        1. Trait update: CharacterTraitUpdate(trait="humor", value=50)
        2. Reset all traits: CharacterResetTraits()
        """
        try:
            data, _ = self._decode_payload(payload)
            if not data:
                logger.warning("Empty character/update payload")
                return

            # Try to parse as CharacterResetTraits first
            if "action" in data and data["action"] == "reset_traits":
                try:
                    # Validate the request format
                    CharacterResetTraits.model_validate(data)
                    logger.info("Resetting all traits to defaults from character.toml")
                    self.character = self._load_character()
                    await self._publish_character_current(client)
                    logger.info(
                        "Reset complete: %d traits restored from %s",
                        len(self.character.traits),
                        CHARACTER_NAME,
                    )
                    return
                except ValidationError as e:
                    logger.warning("Invalid CharacterResetTraits payload: %s", e)
                    return

            # Try to parse as CharacterTraitUpdate
            if data.get("section") == "traits" and "trait" in data and "value" in data:
                try:
                    trait_update = CharacterTraitUpdate.model_validate(data)

                    # Get old value for logging
                    old_value = self.character.traits.get(trait_update.trait, "(not set)")

                    # Update trait
                    self.character.traits[trait_update.trait] = trait_update.value

                    # Publish updated character
                    await self._publish_character_current(client)

                    logger.info(
                        "Updated trait '%s': %s → %d (retained character/current published)",
                        trait_update.trait,
                        old_value,
                        trait_update.value,
                    )
                    return
                except ValidationError as e:
                    logger.warning("Invalid CharacterTraitUpdate payload: %s", e)
                    return

            logger.debug("Unhandled character/update format: %s", data)

        except Exception as exc:
            logger.exception("Failed to handle character/update: %s", exc)

    async def _ingest_document(self, topic: str, payload: bytes) -> None:
        """Ingest document asynchronously to avoid blocking event loop during embedding."""
        data, _ = self._decode_payload(payload)
        if not data:
            return
        if topic == TOPIC_STT_FINAL:
            doc = self._coerce_transcript(data)
        else:
            doc = self._coerce_tts_payload(data)
        if doc is None:
            return
        # Use async add to avoid blocking event loop during embedding
        await self.db.add_async([doc])
        try:
            self.db.save(self.database_path)
        except Exception:
            logger.debug("Failed to persist memory db after ingest", exc_info=True)
        logger.debug("Indexed doc from %s (total: %d)", topic, len(self.db.documents))

    def _coerce_transcript(self, data: dict[str, Any]) -> dict[str, Any] | None:
        try:
            transcript = FinalTranscript.model_validate(data)
            return transcript.model_dump()
        except ValidationError:
            text = str(data.get("text") or "").strip()
            if not text:
                return None
            clone = dict(data)
            clone["text"] = text
            clone.setdefault("is_final", True)
            return clone

    def _coerce_tts_payload(self, data: dict[str, Any]) -> dict[str, Any] | None:
        try:
            say = TtsSay.model_validate(data)
            return say.model_dump()
        except ValidationError:
            text = str(data.get("text") or "").strip()
            if not text:
                return None
            clone = dict(data)
            clone["text"] = text
            return clone

    def _decode_memory_query(self, payload: bytes) -> tuple[MemoryQuery | None, str | None]:
        data, message_id = self._decode_payload(payload)
        if not data:
            return None, message_id
        try:
            return MemoryQuery.model_validate(data), message_id
        except ValidationError:
            text = str(data.get("text") or data.get("query") or "").strip()
            if not text:
                return None, message_id
            top_k_raw = data.get("top_k", TOP_K)
            try:
                top_k_int = int(top_k_raw)
            except (TypeError, ValueError):
                top_k_int = TOP_K
            return MemoryQuery(text=text, top_k=max(1, top_k_int)), message_id

    def _decode_character_get(self, payload: bytes) -> tuple[CharacterGetRequest, str | None]:
        data, message_id = self._decode_payload(payload)
        try:
            return CharacterGetRequest.model_validate(data), message_id
        except ValidationError:
            section = data.get("section") if isinstance(data, dict) else None
            return (
                CharacterGetRequest(section=section if isinstance(section, str) else None),
                message_id,
            )

    def _decode_payload(self, payload: bytes) -> tuple[dict[str, Any], str | None]:
        envelope: Envelope | None = None
        try:
            envelope = Envelope.model_validate_json(payload)
            raw = envelope.data
            if isinstance(raw, dict):
                return raw, envelope.id
            return {}, envelope.id
        except ValidationError:
            pass
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                return parsed, None
        except Exception:
            try:
                text = payload.decode("utf-8", "ignore").strip()
            except Exception:
                text = ""
            if text:
                return {"text": text}, None
        return {}, None

    def _load_character(self) -> CharacterSnapshot:
        try:
            base = Path(CHARACTER_DIR) / CHARACTER_NAME
            toml_path = base / "character.toml"
            if not toml_path.exists():
                logger.warning("Character file not found: %s", toml_path)
                return CharacterSnapshot(name=CHARACTER_NAME)
            with open(toml_path, "rb") as fp:
                data = tomllib.load(fp)
            info = data.get("info", {}) or {}
            name = info.get("name") or CHARACTER_NAME
            description = info.get("description") or ""
            systemprompt = info.get("systemprompt") or ""
            traits = data.get("traits", {}) or {}
            voice = data.get("voice", {}) or {}
            meta = data.get("meta", {}) or {}
            scenario = data.get("scenario", {}) or {}
            personality_notes = data.get("personality_notes", {}) or {}
            example_interactions = data.get("example_interactions", {}) or {}
            snapshot = CharacterSnapshot(
                name=name,
                description=description or None,
                systemprompt=systemprompt or None,
                traits=traits,
                voice=voice,
                meta=meta,
                scenario=scenario,
                personality_notes=personality_notes,
                example_interactions=example_interactions,
            )
            logger.info("Loaded character '%s' with %d traits", snapshot.name, len(traits))
            return snapshot
        except Exception:
            logger.exception("Failed to load character config")
            return CharacterSnapshot(name=CHARACTER_NAME)
