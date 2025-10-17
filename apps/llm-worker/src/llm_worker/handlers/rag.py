"""RAG (Retrieval Augmented Generation) support with token-aware retrieval."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Dict, Tuple, Optional

import asyncio_mqtt as mqtt

logger = logging.getLogger(__name__)


class RAGContext:
    """Container for RAG retrieval results with metadata."""

    def __init__(
        self, content: str, token_count: int, truncated: bool = False, strategy_used: str = "hybrid"
    ):
        self.content = content
        self.token_count = token_count
        self.truncated = truncated
        self.strategy_used = strategy_used


class RAGHandler:
    """Enhanced RAG handler with token-aware retrieval, caching, and observability."""

    def __init__(self, memory_query_topic: str, cache_ttl: int = 300):
        self.memory_query_topic = memory_query_topic
        self._pending_queries: Dict[str, asyncio.Future[RAGContext]] = {}

        # Query result cache (Priority 2)
        self._cache: Dict[str, Tuple[RAGContext, float]] = {}  # (query_hash, (result, timestamp))
        self._cache_ttl = cache_ttl  # Cache TTL in seconds (default 5 minutes)

        # Observability metrics (Priority 4)
        self._metrics = {
            "queries_total": 0,
            "queries_success": 0,
            "queries_timeout": 0,
            "queries_error": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "latency_sum": 0.0,
            "tokens_retrieved_sum": 0,
        }

    async def query(
        self,
        mqtt_client,  # MQTTClient wrapper
        client: mqtt.Client,  # Raw MQTT client
        prompt: str,
        top_k: int,
        correlation_id: str,
        max_tokens: Optional[int] = None,
        include_context: bool = False,
        context_window: int = 1,
        retrieval_strategy: str = "hybrid",
        use_cache: bool = True,
    ) -> RAGContext:
        """Execute enhanced RAG query with token budget, caching, and observability.

        Args:
            client: MQTT client for publishing
            prompt: Query text
            top_k: Maximum number of target results
            correlation_id: Unique identifier for correlation
            max_tokens: Optional token budget for results
            include_context: Whether to include surrounding conversation context
            context_window: Number of previous/next entries to include
            retrieval_strategy: "hybrid", "recent", or "similarity"
            use_cache: Whether to use cached results (default: True)

        Returns:
            RAGContext with formatted content and metadata
        """
        start_time = time.monotonic()
        self._metrics["queries_total"] += 1

        # Check cache first (Priority 2)
        if use_cache:
            cache_key = self._generate_cache_key(
                prompt, top_k, max_tokens, include_context, context_window, retrieval_strategy
            )
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                self._metrics["cache_hits"] += 1
                self._metrics["queries_success"] += 1
                latency = time.monotonic() - start_time
                logger.info(
                    "RAG cache hit: latency=%.3fs, tokens=%d, cache_key=%s",
                    latency,
                    cached_result.token_count,
                    cache_key[:12],
                )
                return cached_result
            self._metrics["cache_misses"] += 1

        future: asyncio.Future[RAGContext] = asyncio.Future()
        self._pending_queries[correlation_id] = future

        try:
            # Create MemoryQuery payload
            from tars.contracts.v1 import EVENT_TYPE_MEMORY_QUERY
            from tars.contracts.v1.memory import MemoryQuery

            query = MemoryQuery(
                text=prompt,
                top_k=top_k,
                max_tokens=max_tokens,
                include_context=include_context,
                context_window=context_window,
                retrieval_strategy=retrieval_strategy,
            )

            # Publish using envelope with correlation ID
            await mqtt_client.publish_event(
                topic=self.memory_query_topic,
                event_type=EVENT_TYPE_MEMORY_QUERY,
                data=query.model_dump(),
                correlation_id=correlation_id,
                qos=1,
                retain=False,
            )
            logger.debug(
                "Published enhanced RAG query: correlation_id=%s, strategy=%s, max_tokens=%s, context=%s",
                correlation_id,
                retrieval_strategy,
                max_tokens,
                include_context,
            )

            # Wait with timeout (5s - reduced from 10s per Priority 1 recommendation)
            # Typical queries: embedding ~100-500ms, retrieval ~200-500ms = <1s total
            context = await asyncio.wait_for(future, timeout=5.0)

            # Update metrics and cache on success
            latency = time.monotonic() - start_time
            self._metrics["queries_success"] += 1
            self._metrics["latency_sum"] += latency
            self._metrics["tokens_retrieved_sum"] += context.token_count

            logger.info(
                "RAG query complete: latency=%.3fs, tokens=%d, truncated=%s, strategy=%s",
                latency,
                context.token_count,
                context.truncated,
                context.strategy_used,
            )

            # Cache the result if enabled
            if use_cache:
                cache_key = self._generate_cache_key(
                    prompt, top_k, max_tokens, include_context, context_window, retrieval_strategy
                )
                self._add_to_cache(cache_key, context)

            return context

        except asyncio.TimeoutError:
            self._pending_queries.pop(correlation_id, None)
            self._metrics["queries_timeout"] += 1
            latency = time.monotonic() - start_time
            logger.warning(
                "RAG query timeout: correlation_id=%s, latency=%.3fs", correlation_id, latency
            )
            return RAGContext("", 0, truncated=False, strategy_used=retrieval_strategy)

        except Exception as e:
            self._pending_queries.pop(correlation_id, None)
            self._metrics["queries_error"] += 1
            latency = time.monotonic() - start_time
            logger.warning(
                "RAG query failed: correlation_id=%s, latency=%.3fs, error=%s",
                correlation_id,
                latency,
                e,
            )
            return RAGContext("", 0, truncated=False, strategy_used=retrieval_strategy)

    async def query_with_token_budget(
        self,
        mqtt_client,  # MQTTClient wrapper
        client: mqtt.Client,  # Raw MQTT client
        prompt: str,
        max_tokens: int,
        correlation_id: str,
        include_context: bool = False,
        top_k: int = 5,
    ) -> Tuple[str, int]:
        """Simplified token-budget query for backward compatibility.

        Returns:
            Tuple of (context_string, token_count)
        """
        context = await self.query(
            mqtt_client,
            client,
            prompt,
            top_k,
            correlation_id,
            max_tokens=max_tokens,
            include_context=include_context,
        )
        return context.content, context.token_count

    def handle_results(self, results_data: dict) -> None:
        """Handle enhanced memory/results response and resolve pending future."""
        corr_id = results_data.get("correlate") or results_data.get("id")
        if not corr_id or corr_id not in self._pending_queries:
            return

        future = self._pending_queries.pop(corr_id)
        if future.done():
            return

        results = results_data.get("results", [])
        total_tokens = results_data.get("total_tokens", 0)
        truncated = results_data.get("truncated", False)
        strategy_used = results_data.get("strategy_used", "hybrid")

        # Group results by context type for better organization
        context_snippets = []
        target_snippets = []

        for r in results:
            doc = r.get("document", {})
            context_type = r.get("context_type", "target")
            timestamp = r.get("timestamp")

            # Extract text from document
            text = self._extract_text_from_document(doc)
            if not text:
                continue

            # Format with context type and timestamp if available
            formatted_text = text
            if context_type != "target":
                prefix = f"[{context_type}]"
                if timestamp:
                    prefix += f" ({timestamp})"
                formatted_text = f"{prefix} {text}"
            elif timestamp:
                formatted_text = f"({timestamp}) {text}"

            if context_type == "target":
                target_snippets.append(formatted_text)
            else:
                context_snippets.append(formatted_text)

        # Combine context and target snippets
        all_snippets = context_snippets + target_snippets
        content = "\n".join(filter(None, all_snippets))

        rag_context = RAGContext(
            content=content,
            token_count=total_tokens,
            truncated=truncated,
            strategy_used=strategy_used,
        )

        future.set_result(rag_context)
        logger.debug(
            "Resolved enhanced RAG query %s: %d results, %d tokens, truncated=%s, strategy=%s",
            corr_id,
            len(results),
            total_tokens,
            truncated,
            strategy_used,
        )

    def _extract_text_from_document(self, doc: dict) -> str:
        """Extract meaningful text from a document."""
        if isinstance(doc, str):
            return doc

        if not isinstance(doc, dict):
            return str(doc)

        # Priority order for text extraction
        text_fields = ["text", "user_input", "bot_response", "content", "message"]

        for field in text_fields:
            if field in doc and doc[field]:
                return str(doc[field]).strip()

        # Fallback: combine all string values
        text_parts = []
        for key, value in doc.items():
            if isinstance(value, str) and value.strip():
                text_parts.append(value.strip())
            elif isinstance(value, (int, float)):
                text_parts.append(str(value))

        return " ".join(text_parts) if text_parts else str(doc)

    def _generate_cache_key(
        self,
        prompt: str,
        top_k: int,
        max_tokens: Optional[int],
        include_context: bool,
        context_window: int,
        retrieval_strategy: str,
    ) -> str:
        """Generate a cache key from query parameters."""
        # Create deterministic hash from all query parameters
        cache_input = (
            f"{prompt}|{top_k}|{max_tokens}|{include_context}|{context_window}|{retrieval_strategy}"
        )
        return hashlib.sha256(cache_input.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[RAGContext]:
        """Retrieve cached result if still valid."""
        if cache_key not in self._cache:
            return None

        result, timestamp = self._cache[cache_key]
        age = time.time() - timestamp

        # Check if cache entry is still valid
        if age > self._cache_ttl:
            # Expired - remove from cache
            del self._cache[cache_key]
            logger.debug("Cache entry expired: key=%s, age=%.1fs", cache_key[:12], age)
            return None

        logger.debug("Cache entry valid: key=%s, age=%.1fs", cache_key[:12], age)
        return result

    def _add_to_cache(self, cache_key: str, context: RAGContext) -> None:
        """Add a result to the cache."""
        self._cache[cache_key] = (context, time.time())
        logger.debug(
            "Cached RAG result: key=%s, tokens=%d, cache_size=%d",
            cache_key[:12],
            context.token_count,
            len(self._cache),
        )

        # Limit cache size to prevent unbounded growth (keep most recent 100 entries)
        if len(self._cache) > 100:
            # Remove oldest entries
            sorted_entries = sorted(self._cache.items(), key=lambda x: x[1][1])
            entries_to_remove = len(self._cache) - 100
            for key, _ in sorted_entries[:entries_to_remove]:
                del self._cache[key]
            logger.debug("Cache pruned: removed %d old entries", entries_to_remove)

    def get_metrics(self) -> dict:
        """Get current metrics for observability.

        Returns:
            Dictionary with query statistics and performance metrics
        """
        metrics = dict(self._metrics)

        # Calculate derived metrics
        if metrics["queries_total"] > 0:
            metrics["cache_hit_rate"] = metrics["cache_hits"] / metrics["queries_total"]
            metrics["success_rate"] = metrics["queries_success"] / metrics["queries_total"]
            metrics["timeout_rate"] = metrics["queries_timeout"] / metrics["queries_total"]
        else:
            metrics["cache_hit_rate"] = 0.0
            metrics["success_rate"] = 0.0
            metrics["timeout_rate"] = 0.0

        if metrics["queries_success"] > 0:
            metrics["avg_latency"] = metrics["latency_sum"] / metrics["queries_success"]
            metrics["avg_tokens"] = metrics["tokens_retrieved_sum"] / metrics["queries_success"]
        else:
            metrics["avg_latency"] = 0.0
            metrics["avg_tokens"] = 0.0

        return metrics

    def clear_cache(self) -> int:
        """Clear all cached results.

        Returns:
            Number of entries cleared
        """
        count = len(self._cache)
        self._cache.clear()
        logger.info("Cleared RAG cache: %d entries removed", count)
        return count

    def log_metrics(self) -> None:
        """Log current metrics for observability."""
        metrics = self.get_metrics()
        logger.info(
            "RAG Metrics: total=%d, success=%d, timeout=%d, cache_hit_rate=%.1f%%, "
            "avg_latency=%.3fs, avg_tokens=%d, cache_size=%d",
            metrics["queries_total"],
            metrics["queries_success"],
            metrics["queries_timeout"],
            metrics["cache_hit_rate"] * 100,
            metrics["avg_latency"],
            int(metrics["avg_tokens"]),
            len(self._cache),
        )
