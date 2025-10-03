from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import asyncio_mqtt as mqtt
import numpy as np
import orjson as json
from pydantic import ValidationError
from sentence_transformers import SentenceTransformer

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
    TOPIC_HEALTH,
    TOPIC_QUERY,
    TOPIC_RESULTS,
    TOPIC_STT_FINAL,
    TOPIC_TTS_SAY,
    TOP_K,
)
from .hyperdb import HyperConfig, HyperDB
from .mqtt_client import MemoryMQTTClient

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
    EVENT_TYPE_MEMORY_HEALTH,
    EVENT_TYPE_MEMORY_QUERY,
    EVENT_TYPE_MEMORY_RESULTS,
    CharacterGetRequest,
    CharacterSection,
    CharacterSnapshot,
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
        self.embedder = STEmbedder(EMBED_MODEL)
        self.db = HyperDB(embedding_fn=self.embedder, cfg=HyperConfig(rag_strategy=RAG_STRATEGY, top_k=TOP_K))
        self._load_or_initialize_db()
        self.character = self._load_character()
        self.mqtt_client = MemoryMQTTClient(MQTT_URL, source_name=SOURCE_NAME)

    def _register_topics(self) -> None:
        register(EVENT_TYPE_MEMORY_QUERY, TOPIC_QUERY)
        register(EVENT_TYPE_MEMORY_RESULTS, TOPIC_RESULTS)
        register(EVENT_TYPE_MEMORY_HEALTH, TOPIC_HEALTH)
        register(EVENT_TYPE_CHARACTER_GET, TOPIC_CHAR_GET)
        register(EVENT_TYPE_CHARACTER_RESULT, TOPIC_CHAR_RESULT)
        register(EVENT_TYPE_CHARACTER_CURRENT, TOPIC_CHAR_CURRENT)
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
        try:
            async with await self.mqtt_client.connect() as client:
                await self._publish_health(client, ok=True, event="ready", retain=True)
                await self._publish_character_current(client)
                
                # Subscribe to all topics
                topics = [TOPIC_STT_FINAL, TOPIC_TTS_SAY, TOPIC_QUERY, TOPIC_CHAR_GET]
                await self.mqtt_client.subscribe(client, topics)
                
                async with client.messages() as stream:
                    async for message in stream:
                        topic = str(getattr(message, "topic", ""))
                        payload = message.payload
                        try:
                            if topic == TOPIC_QUERY:
                                query, correlate = self._decode_memory_query(payload)
                                if query is None or not query.text.strip():
                                    logger.info("Ignored empty memory/query message")
                                    continue
                                await self._handle_memory_query(client, query, correlate)
                            elif topic == TOPIC_CHAR_GET:
                                request, correlate = self._decode_character_get(payload)
                                await self._handle_char_get(client, request, correlate)
                            elif topic in (TOPIC_STT_FINAL, TOPIC_TTS_SAY):
                                await self._ingest_document(topic, payload)
                            else:
                                logger.debug("Unhandled topic: %s", topic)
                        except Exception as exc:  # pragma: no cover - defensive
                            logger.exception("Error handling message on topic=%s", topic)
                            await self._publish_health(client, ok=False, err=str(exc), retain=True)
        except Exception as exc:  # pragma: no cover - network layer
            logger.info("MQTT disconnected or error: %s; shutting down gracefully", exc)

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
            client,
            event_type=EVENT_TYPE_MEMORY_HEALTH,
            topic=TOPIC_HEALTH,
            payload=payload,
            correlate=None,
            qos=1,
            retain=retain,
        )

    async def _publish_character_current(self, client: mqtt.Client) -> None:
        await self.mqtt_client.publish_event(
            client,
            event_type=EVENT_TYPE_CHARACTER_CURRENT,
            topic=TOPIC_CHAR_CURRENT,
            payload=self.character,
            correlate=self.character.message_id,
            qos=1,
            retain=True,
        )

    async def _handle_memory_query(
        self,
        client: mqtt.Client,
        query: MemoryQuery,
        correlate: str | None,
    ) -> None:
        top_k = query.top_k or TOP_K
        # Use async query to avoid blocking event loop during embedding
        results = await self.db.query_async(query.text, top_k=top_k)
        hits = [
            MemoryResult(
                document=doc if isinstance(doc, dict) else {"text": str(doc)},
                score=float(score),
            )
            for doc, score in results
        ]
        payload = MemoryResults(query=query.text, k=top_k, results=hits)
        await self.mqtt_client.publish_event(
            client,
            event_type=EVENT_TYPE_MEMORY_RESULTS,
            topic=TOPIC_RESULTS,
            payload=payload,
            correlate=correlate or query.message_id,
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
                client,
                event_type=EVENT_TYPE_CHARACTER_RESULT,
                topic=TOPIC_CHAR_RESULT,
                payload=self.character,
                correlate=correlate or request.message_id,
                qos=0,
                retain=False,
            )
            return
        section = request.section
        if section in snapshot_dict:
            value: Any = snapshot_dict[section]
        else:
            value = {"error": f"unknown section '{section}'", "available": list(snapshot_dict.keys())}
        payload = CharacterSection(section=section, value=value)
        await self.mqtt_client.publish_event(
            client,
            event_type=EVENT_TYPE_CHARACTER_RESULT,
            topic=TOPIC_CHAR_RESULT,
            payload=payload,
            correlate=correlate or request.message_id,
            qos=0,
            retain=False,
        )

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
        logger.info("Indexed new doc into memory store from %s", topic)

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
            return CharacterGetRequest(section=section if isinstance(section, str) else None), message_id

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
            snapshot = CharacterSnapshot(
                name=name,
                description=description or None,
                systemprompt=systemprompt or None,
                traits=traits,
                voice=voice,
                meta=meta,
            )
            logger.info("Loaded character '%s' with %d traits", snapshot.name, len(traits))
            return snapshot
        except Exception:
            logger.exception("Failed to load character config")
            return CharacterSnapshot(name=CHARACTER_NAME)
