"""RAG (Retrieval Augmented Generation) support with token-aware retrieval."""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Tuple, Optional

import asyncio_mqtt as mqtt
import orjson as json

logger = logging.getLogger(__name__)


class RAGContext:
    """Container for RAG retrieval results with metadata."""
    
    def __init__(self, content: str, token_count: int, truncated: bool = False, strategy_used: str = "hybrid"):
        self.content = content
        self.token_count = token_count
        self.truncated = truncated
        self.strategy_used = strategy_used


class RAGHandler:
    """Enhanced RAG handler with token-aware retrieval and context expansion."""
    
    def __init__(self, memory_query_topic: str):
        self.memory_query_topic = memory_query_topic
        self._pending_queries: Dict[str, asyncio.Future[RAGContext]] = {}
    
    async def query(
        self, 
        client: mqtt.Client, 
        prompt: str, 
        top_k: int, 
        correlation_id: str,
        max_tokens: Optional[int] = None,
        include_context: bool = False,
        context_window: int = 1,
        retrieval_strategy: str = "hybrid"
    ) -> RAGContext:
        """Execute enhanced RAG query with token budget and context expansion.
        
        Args:
            client: MQTT client for publishing
            prompt: Query text
            top_k: Maximum number of target results
            correlation_id: Unique identifier for correlation
            max_tokens: Optional token budget for results
            include_context: Whether to include surrounding conversation context
            context_window: Number of previous/next entries to include
            retrieval_strategy: "hybrid", "recent", or "similarity"
            
        Returns:
            RAGContext with formatted content and metadata
        """
        future: asyncio.Future[RAGContext] = asyncio.Future()
        self._pending_queries[correlation_id] = future
        
        try:
            payload = {
                "text": prompt, 
                "top_k": top_k,
                "max_tokens": max_tokens,
                "include_context": include_context,
                "context_window": context_window,
                "retrieval_strategy": retrieval_strategy,
                "id": correlation_id
            }
            
            await client.publish(self.memory_query_topic, json.dumps(payload))
            logger.debug(
                "Published enhanced RAG query: correlation_id=%s, strategy=%s, max_tokens=%s, context=%s",
                correlation_id, retrieval_strategy, max_tokens, include_context
            )
            
            # Wait with timeout
            context = await asyncio.wait_for(future, timeout=5.0)
            return context
            
        except asyncio.TimeoutError:
            self._pending_queries.pop(correlation_id, None)
            logger.warning("RAG query timeout for correlation_id=%s", correlation_id)
            return RAGContext("", 0, truncated=False, strategy_used=retrieval_strategy)
            
        except Exception as e:
            self._pending_queries.pop(correlation_id, None)
            logger.warning("RAG query failed: %s", e)
            return RAGContext("", 0, truncated=False, strategy_used=retrieval_strategy)
    
    async def query_with_token_budget(
        self, 
        client: mqtt.Client, 
        prompt: str, 
        max_tokens: int,
        correlation_id: str,
        include_context: bool = False,
        top_k: int = 5
    ) -> Tuple[str, int]:
        """Simplified token-budget query for backward compatibility.
        
        Returns:
            Tuple of (context_string, token_count)
        """
        context = await self.query(
            client, prompt, top_k, correlation_id, 
            max_tokens=max_tokens, include_context=include_context
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
            strategy_used=strategy_used
        )
        
        future.set_result(rag_context)
        logger.debug(
            "Resolved enhanced RAG query %s: %d results, %d tokens, truncated=%s, strategy=%s",
            corr_id, len(results), total_tokens, truncated, strategy_used
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
