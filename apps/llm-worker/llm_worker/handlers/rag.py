"""RAG (Retrieval Augmented Generation) support."""
from __future__ import annotations

import asyncio
import logging
from typing import Dict

import asyncio_mqtt as mqtt
import orjson as json

logger = logging.getLogger(__name__)


class RAGHandler:
    """Handles RAG queries with correlation-based futures."""
    
    def __init__(self, memory_query_topic: str):
        self.memory_query_topic = memory_query_topic
        self._pending_queries: Dict[str, asyncio.Future[str]] = {}
    
    async def query(self, client: mqtt.Client, prompt: str, top_k: int, correlation_id: str) -> str:
        """Execute non-blocking RAG query.
        
        Creates future keyed by correlation ID, publishes query, and waits
        for memory-worker to respond via handle_results().
        
        Returns:
            RAG context string (empty on timeout/error)
        """
        future: asyncio.Future[str] = asyncio.Future()
        self._pending_queries[correlation_id] = future
        
        try:
            payload = {"text": prompt, "top_k": top_k, "id": correlation_id}
            await client.publish(self.memory_query_topic, json.dumps(payload))
            logger.debug("Published RAG query with correlation_id=%s", correlation_id)
            
            # Wait with timeout
            context = await asyncio.wait_for(future, timeout=5.0)
            return context
        except asyncio.TimeoutError:
            self._pending_queries.pop(correlation_id, None)
            logger.warning("RAG query timeout for correlation_id=%s", correlation_id)
            return ""
        except Exception as e:
            self._pending_queries.pop(correlation_id, None)
            logger.warning("RAG query failed: %s", e)
            return ""
    
    def handle_results(self, results_data: dict) -> None:
        """Handle memory/results response and resolve pending future."""
        corr_id = results_data.get("correlate") or results_data.get("id")
        if not corr_id or corr_id not in self._pending_queries:
            return
        
        future = self._pending_queries.pop(corr_id)
        if future.done():
            return
        
        # Extract text from results
        results = results_data.get("results") or []
        snippets = []
        for r in results:
            doc = r.get("document") or {}
            text = doc.get("text")
            if text:
                snippets.append(text)
            else:
                # Fallback to JSON serialization (decode bytes to str)
                json_bytes = json.dumps(doc)
                snippets.append(json_bytes.decode('utf-8') if isinstance(json_bytes, bytes) else json_bytes)
        
        context = "\n".join(snippets)
        future.set_result(context)
        logger.debug("Resolved RAG query %s with %d results", corr_id, len(results))
