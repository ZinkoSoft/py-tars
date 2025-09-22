from __future__ import annotations

import logging, os
from urllib.parse import urlparse
import asyncio_mqtt as mqtt
import orjson as json
from .config import (
    MQTT_URL, LOG_LEVEL,
    MEMORY_DIR, MEMORY_FILE,
    RAG_STRATEGY, TOP_K, EMBED_MODEL,
    TOPIC_STT_FINAL, TOPIC_TTS_SAY,
    TOPIC_QUERY, TOPIC_RESULTS, TOPIC_HEALTH,
)
from .hyperdb import HyperDB, HyperConfig
import numpy as np
from sentence_transformers import SentenceTransformer


logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("memory-worker")


def parse_mqtt(url: str):
    u = urlparse(url)
    return (u.hostname or "127.0.0.1", u.port or 1883, u.username, u.password)


class STEmbedder:
    """SentenceTransformer embedding wrapper."""

    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name, device="cpu")

    def __call__(self, texts: list[str]) -> np.ndarray:
        embs = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
        return embs.astype(np.float32)


class MemoryService:
    def __init__(self):
        os.makedirs(MEMORY_DIR, exist_ok=True)
        self.path = os.path.join(MEMORY_DIR, MEMORY_FILE)
        embedder = STEmbedder(EMBED_MODEL)
        self.db = HyperDB(embedding_fn=embedder, cfg=HyperConfig(rag_strategy=RAG_STRATEGY, top_k=TOP_K))
        # Load existing DB if available
        if os.path.exists(self.path):
            ok = self.db.load(self.path)
            logger.info(f"Loaded memory db: {ok}")
            # If vectors exist but have a different dim than current embedder, re-embed
            try:
                if ok and self.db.vectors is not None and self.db.vectors.size:
                    vectors_shape = tuple(self.db.vectors.shape)
                    current_dim = vectors_shape[1] if len(vectors_shape) == 2 else vectors_shape[-1]
                    probe = embedder(["dim_check"])  # expect (1, D) but be robust
                    probe_shape = tuple(probe.shape)
                    test_dim = probe_shape[1] if len(probe_shape) == 2 else probe_shape[0]
                    logger.info(f"Memory vectors dim={current_dim}, embedder dim={test_dim}, docs={len(self.db.documents)}")
                    if current_dim != test_dim:
                        logger.info(f"Embedding dim changed {current_dim} -> {test_dim}; re-embedding {len(self.db.documents)} docs")
                        # Rebuild vectors with new embedder
                        texts = [self.db._doc_to_text(d) for d in self.db.documents]
                        new_vecs = embedder(texts).astype(np.float32)
                        self.db.vectors = new_vecs
                        # Re-index BM25 side
                        self.db._ensure_bm25()
                        # Save upgraded db
                        try:
                            self.db.save(self.path)
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"Could not reconcile embedding dim: {e}")

    async def run(self):
        host, port, user, pwd = parse_mqtt(MQTT_URL)
        logger.info(f"Connecting to MQTT {host}:{port}")
        try:
            async with mqtt.Client(hostname=host, port=port, username=user, password=pwd, client_id="tars-memory") as client:
                logger.info(f"Connected to MQTT {host}:{port} as tars-memory")
                await client.publish(TOPIC_HEALTH, json.dumps({"ok": True, "event": "ready"}), retain=True)
                # Prepare message stream (unfiltered_messages is deprecated)
                async with client.messages() as mstream:
                    for t in [TOPIC_STT_FINAL, TOPIC_TTS_SAY, TOPIC_QUERY]:
                        await client.subscribe(t)
                        logger.info(f"Subscribed to {t}")
                    async for m in mstream:
                        try:
                            topic = m.topic if isinstance(m.topic, str) else m.topic.decode("utf-8", "ignore")
                            logger.info(f"MQTT msg on topic='{topic}' len={len(m.payload)}")
                            # Robust payload parsing: prefer JSON, but accept plain-text payloads
                            try:
                                data = json.loads(m.payload)
                            except Exception:
                                try:
                                    data_text = m.payload.decode("utf-8", "ignore").strip()
                                except Exception:
                                    data_text = ""
                                data = {"text": data_text} if data_text else {}
                            if topic == TOPIC_QUERY:
                                q = (data.get("text") or data.get("query") or "").strip()
                                k = int(data.get("top_k", TOP_K))
                                if not q:
                                    logger.info("Ignored empty memory/query")
                                    continue
                                logger.info(f"Processing memory/query: '{q}' k={k}")
                                results = self.db.query(q, top_k=k)
                                out = [{"document": doc, "score": score} for doc, score in results]
                                payload = {"query": q, "results": out, "k": k}
                                logger.info(f"Publishing memory/results: {len(out)} hits")
                                await client.publish(TOPIC_RESULTS, json.dumps(payload))
                            elif topic in (TOPIC_STT_FINAL, TOPIC_TTS_SAY):
                                # Record conversational pairings where possible
                                text = (data.get("text") or "").strip()
                                if not text:
                                    continue
                                doc = data
                                self.db.add([doc])
                                # Persist lightly
                                try:
                                    self.db.save(self.path)
                                except Exception:
                                    pass
                                logger.info("Indexed new doc into memory store")
                            else:
                                logger.debug(f"Unhandled topic: {topic}")
                        except Exception as e:
                            logger.error(f"Error handling message: {e}")
                            await client.publish(TOPIC_HEALTH, json.dumps({"ok": False, "err": str(e)}), retain=True)
        except Exception as e:
            logger.info(f"MQTT disconnected or error: {e}; shutting down gracefully")
