# Memory Worker

Provides hybrid memory and retrieval over MQTT.

Topics:
- memory/query: { text, top_k? }
- memory/results: { query, k, results: [{document, score}] }
- system/health/memory: retained health

Persists to /data/{MEMORY_FILE} (default memory.pickle.gz).

Env:
- MQTT_URL (host, port, creds)
- MEMORY_DIR (/data)
- MEMORY_FILE
- RAG_STRATEGY: naive | hybrid
- MEMORY_TOP_K
