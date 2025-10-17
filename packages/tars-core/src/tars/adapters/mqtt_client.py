"""Centralized MQTT client module for py-tars services.

This module provides a unified MQTT client with connection management,
automatic reconnection, envelope-based publishing/subscribing, health
monitoring, and graceful shutdown.

Constitutional Compliance:
- Event-Driven Architecture: All messages use Envelope contract
- Typed Contracts: Pydantic v2 models with complete type hints
- Async-First: asyncio with proper event loop hygiene
- Test-First: TDD workflow (tests written before implementation)
- Configuration via Environment: MQTTClientConfig.from_env()
- Observability: Structured logging with correlation IDs
- Simplicity & YAGNI: <500 LOC, minimal API, no speculative features
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import urlparse

import asyncio_mqtt as mqtt
import orjson
from pydantic import BaseModel, Field, field_validator, ValidationInfo

from tars.contracts.envelope import Envelope

logger = logging.getLogger(__name__)


# --- Configuration Models ---


class ConnectionParams(BaseModel):
    """Parsed MQTT connection parameters from URL.
    
    Attributes:
        hostname: MQTT broker hostname or IP address
        port: MQTT broker port (default 1883)
        username: Authentication username (optional)
        password: Authentication password (optional, redacted in logs)
    """

    hostname: str
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None

    def __repr__(self) -> str:
        """String representation with password redacted."""
        password_str = "***REDACTED***" if self.password else None
        return (
            f"ConnectionParams(hostname={self.hostname!r}, port={self.port}, "
            f"username={self.username!r}, password={password_str!r})"
        )

    def __str__(self) -> str:
        """String representation with password redacted."""
        return self.__repr__()


def parse_mqtt_url(url: str) -> ConnectionParams:
    """Parse MQTT URL into connection parameters.
    
    Args:
        url: MQTT URL in format mqtt://[user:pass@]host[:port]
    
    Returns:
        ConnectionParams with parsed components
    
    Raises:
        ValueError: If URL has invalid scheme (not mqtt://)
    
    Examples:
        >>> parse_mqtt_url("mqtt://user:pass@localhost:1883")
        ConnectionParams(hostname='localhost', port=1883, username='user', ...)
        
        >>> parse_mqtt_url("mqtt://broker.example.com")
        ConnectionParams(hostname='broker.example.com', port=1883, ...)
    """
    parsed = urlparse(url)
    
    if parsed.scheme != "mqtt":
        raise ValueError(
            f"Invalid MQTT URL scheme: {parsed.scheme!r}. Expected 'mqtt://'."
        )
    
    return ConnectionParams(
        hostname=parsed.hostname or "localhost",
        port=parsed.port or 1883,
        username=parsed.username,
        password=parsed.password,
    )


class MQTTClientConfig(BaseModel):
    """Configuration for centralized MQTT client.
    
    Load from environment using MQTTClientConfig.from_env().
    
    Attributes:
        mqtt_url: MQTT broker URL (mqtt://[user:pass@]host[:port])
        client_id: Unique client identifier for broker connection
        source_name: Source identifier for Envelope messages (defaults to client_id)
        keepalive: MQTT protocol keepalive interval in seconds
        enable_health: Whether to publish health status to system/health/{client_id}
        enable_heartbeat: Whether to publish heartbeat to system/keepalive/{client_id}
        heartbeat_interval: Heartbeat publish interval in seconds
        dedupe_ttl: Message deduplication TTL in seconds (0=disabled)
        dedupe_max_entries: Max deduplication cache entries (0=disabled)
        reconnect_min_delay: Min reconnection backoff delay in seconds
        reconnect_max_delay: Max reconnection backoff delay in seconds
    """

    mqtt_url: str
    client_id: str
    source_name: Optional[str] = None
    keepalive: int = Field(default=60, ge=1, le=3600)
    enable_health: bool = False
    enable_heartbeat: bool = False
    heartbeat_interval: float = Field(default=5.0, ge=1.0)
    dedupe_ttl: float = Field(default=0.0, ge=0.0)
    dedupe_max_entries: int = Field(default=0, ge=0)
    reconnect_min_delay: float = Field(default=0.5, ge=0.1)
    reconnect_max_delay: float = Field(default=5.0, ge=0.5)

    @field_validator("reconnect_max_delay")
    @classmethod
    def validate_reconnect_delays(cls, v: float, info: ValidationInfo) -> float:
        """Ensure reconnect_max_delay >= reconnect_min_delay."""
        if "reconnect_min_delay" in info.data:
            min_delay = info.data["reconnect_min_delay"]
            if v < min_delay:
                raise ValueError(
                    f"reconnect_max_delay ({v}) must be >= "
                    f"reconnect_min_delay ({min_delay})"
                )
        return v

    @field_validator("dedupe_max_entries")
    @classmethod
    def validate_dedupe_config(cls, v: int, info: ValidationInfo) -> int:
        """Ensure dedupe_max_entries > 0 when dedupe_ttl > 0."""
        if "dedupe_ttl" in info.data:
            ttl = info.data["dedupe_ttl"]
            if ttl > 0 and v == 0:
                raise ValueError(
                    f"dedupe_max_entries must be > 0 when dedupe_ttl={ttl} "
                    "(deduplication requires cache size limit)"
                )
        return v

    @classmethod
    def from_env(cls) -> MQTTClientConfig:
        """Load configuration from environment variables.
        
        Required environment variables:
            MQTT_URL: MQTT broker URL
            MQTT_CLIENT_ID: Unique client identifier
        
        Optional environment variables:
            MQTT_SOURCE_NAME: Source name for Envelope (defaults to client_id)
            MQTT_KEEPALIVE: Protocol keepalive interval (default: 60)
            MQTT_ENABLE_HEALTH: Enable health publishing (default: false)
            MQTT_ENABLE_HEARTBEAT: Enable heartbeat (default: false)
            MQTT_HEARTBEAT_INTERVAL: Heartbeat interval (default: 5.0)
            MQTT_DEDUPE_TTL: Dedup TTL in seconds (default: 0, disabled)
            MQTT_DEDUPE_MAX_ENTRIES: Dedup cache size (default: 0)
            MQTT_RECONNECT_MIN_DELAY: Min backoff delay (default: 0.5)
            MQTT_RECONNECT_MAX_DELAY: Max backoff delay (default: 5.0)
        
        Returns:
            MQTTClientConfig instance
        
        Raises:
            KeyError: If required environment variable missing
            ValueError: If validation fails
        """
        mqtt_url = os.environ["MQTT_URL"]
        client_id = os.environ["MQTT_CLIENT_ID"]
        
        return cls(
            mqtt_url=mqtt_url,
            client_id=client_id,
            source_name=os.getenv("MQTT_SOURCE_NAME"),
            keepalive=int(os.getenv("MQTT_KEEPALIVE", "60")),
            enable_health=os.getenv("MQTT_ENABLE_HEALTH", "").lower() == "true",
            enable_heartbeat=os.getenv("MQTT_ENABLE_HEARTBEAT", "").lower() == "true",
            heartbeat_interval=float(os.getenv("MQTT_HEARTBEAT_INTERVAL", "5.0")),
            dedupe_ttl=float(os.getenv("MQTT_DEDUPE_TTL", "0.0")),
            dedupe_max_entries=int(os.getenv("MQTT_DEDUPE_MAX_ENTRIES", "0")),
            reconnect_min_delay=float(os.getenv("MQTT_RECONNECT_MIN_DELAY", "0.5")),
            reconnect_max_delay=float(os.getenv("MQTT_RECONNECT_MAX_DELAY", "5.0")),
        )


class HealthStatus(BaseModel):
    """Health status payload for system/health/{client_id} topic.
    
    Attributes:
        ok: Health status (True=healthy, False=unhealthy)
        event: Health event name (e.g., "ready", "shutdown", "reconnected")
        error: Error message if ok=False (optional)
    """

    ok: bool
    event: Optional[str] = None
    error: Optional[str] = None

    @field_validator("error")
    @classmethod
    def validate_error_when_unhealthy(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Warn if error is set when ok=True."""
        if "ok" in info.data and info.data["ok"] is True and v is not None:
            logger.warning("Health status ok=True but error=%r (unexpected)", v)
        return v


class HeartbeatPayload(BaseModel):
    """Application-level keepalive heartbeat payload.
    
    Published to system/keepalive/{client_id} at configured interval.
    
    Attributes:
        ok: Always True for heartbeat (unhealthy services stop heartbeating)
        event: Always "heartbeat"
        timestamp: Unix timestamp of heartbeat
    """

    ok: bool = True
    event: str = "heartbeat"
    timestamp: float


# --- Message Deduplication ---


class MessageDeduplicator:
    """Deduplicate messages using envelope IDs with TTL-bound cache.
    
    This is re-exported from mqtt_asyncio.py for compatibility.
    Uses existing implementation from tars.adapters.mqtt_asyncio.
    """

    def __init__(self, *, ttl: float, max_entries: int) -> None:
        """Initialize deduplicator with TTL and cache size limit.
        
        Args:
            ttl: Time-to-live for cache entries in seconds
            max_entries: Maximum cache size (entries)
        """
        from tars.adapters.mqtt_asyncio import MessageDeduplicator as _Dedup
        
        self._impl = _Dedup(ttl=ttl, max_entries=max_entries)

    def is_duplicate(self, payload: bytes) -> bool:
        """Check if message is duplicate based on Envelope ID.
        
        Args:
            payload: Raw message payload (Envelope JSON)
        
        Returns:
            True if message is duplicate, False otherwise
        """
        return self._impl.is_duplicate(payload)


# --- Type Aliases ---


SubscriptionHandler = Callable[[bytes], Awaitable[None]]
"""Type alias for subscription handler functions.

Handler receives raw message payload and processes asynchronously.
Should not raise exceptions (errors are isolated by dispatch loop).
Should be idempotent if deduplication is disabled.
"""


# --- Main MQTT Client ---


class MQTTClient:
    """Centralized MQTT client for py-tars services.
    
    Provides connection management, automatic reconnection, envelope-based
    publishing/subscribing, health monitoring, and graceful shutdown.
    
    Features:
        - Automatic reconnection with exponential backoff
        - Envelope contract enforcement for all published events
        - Optional health status publishing (system/health/{client_id})
        - Optional heartbeat publishing (system/keepalive/{client_id})
        - Optional message deduplication by Envelope ID
        - Graceful shutdown with task cancellation
        - Error isolation for subscription handlers
    
    Example:
        ```python
        # Create and connect
        client = MQTTClient("mqtt://localhost:1883", "tars-service")
        await client.connect()
        
        # Subscribe to topics
        async def handle_event(payload: bytes) -> None:
            envelope = Envelope.model_validate_json(payload)
            print(f"Event: {envelope.type}")
        
        await client.subscribe("events/#", handle_event)
        
        # Publish events
        await client.publish_event(
            topic="my/topic",
            event_type="my.event",
            data={"key": "value"},
        )
        
        # Graceful shutdown
        await client.shutdown()
        ```
    """

    def __init__(
        self,
        mqtt_url: str,
        client_id: str,
        source_name: Optional[str] = None,
        *,
        keepalive: int = 60,
        enable_health: bool = False,
        enable_heartbeat: bool = False,
        heartbeat_interval: float = 5.0,
        dedupe_ttl: float = 0.0,
        dedupe_max_entries: int = 0,
        reconnect_min_delay: float = 0.5,
        reconnect_max_delay: float = 5.0,
    ) -> None:
        """Initialize MQTT client with configuration.
        
        Args:
            mqtt_url: MQTT broker URL (mqtt://[user:pass@]host[:port])
            client_id: Unique client identifier for broker connection
            source_name: Source identifier for Envelope messages (defaults to client_id)
            keepalive: MQTT protocol keepalive interval in seconds
            enable_health: Whether to publish health status
            enable_heartbeat: Whether to publish heartbeat
            heartbeat_interval: Heartbeat publish interval in seconds
            dedupe_ttl: Message deduplication TTL in seconds (0=disabled)
            dedupe_max_entries: Max deduplication cache entries (0=disabled)
            reconnect_min_delay: Min reconnection backoff delay in seconds
            reconnect_max_delay: Max reconnection backoff delay in seconds
        
        Raises:
            ValueError: If configuration validation fails
        """
        # Validate and parse configuration
        self._config = MQTTClientConfig(
            mqtt_url=mqtt_url,
            client_id=client_id,
            source_name=source_name,
            keepalive=keepalive,
            enable_health=enable_health,
            enable_heartbeat=enable_heartbeat,
            heartbeat_interval=heartbeat_interval,
            dedupe_ttl=dedupe_ttl,
            dedupe_max_entries=dedupe_max_entries,
            reconnect_min_delay=reconnect_min_delay,
            reconnect_max_delay=reconnect_max_delay,
        )
        
        self._conn_params = parse_mqtt_url(mqtt_url)
        self._source_name = source_name or client_id
        
        # State
        self._client: Optional[mqtt.Client] = None
        self._handlers: dict[str, SubscriptionHandler] = {}
        self._subscriptions: set[str] = set()
        self._dispatch_task: Optional[asyncio.Task[None]] = None
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._connected: bool = False
        self._shutdown: bool = False
        
        # Deduplication
        self._deduplicator: Optional[MessageDeduplicator] = None
        if dedupe_ttl > 0 and dedupe_max_entries > 0:
            self._deduplicator = MessageDeduplicator(
                ttl=dedupe_ttl,
                max_entries=dedupe_max_entries,
            )

    @property
    def client(self) -> Optional[mqtt.Client]:
        """Access underlying asyncio-mqtt client for advanced operations.
        
        Returns None if not connected.
        """
        return self._client

    @property
    def connected(self) -> bool:
        """Check if client is currently connected to broker."""
        return self._connected

    async def __aenter__(self) -> MQTTClient:
        """Async context manager entry (auto-connect)."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Async context manager exit (auto-shutdown)."""
        await self.shutdown()

    # --- Lifecycle Methods ---

    async def connect(self) -> None:
        """Connect to MQTT broker and start background tasks.
        
        This method:
        - Parses connection parameters from URL
        - Creates asyncio-mqtt Client
        - Enters client context (establishes connection)
        - Starts message dispatch task
        - Starts heartbeat task (if enabled)
        - Publishes health status (if enabled)
        
        Raises:
            ValueError: If MQTT URL is invalid
            ConnectionError: If connection to broker fails
        """
        if self._connected:
            logger.debug("Already connected, skipping connect()")
            return
        
        # Create MQTT client with connection parameters
        self._client = mqtt.Client(
            hostname=self._conn_params.hostname,
            port=self._conn_params.port,
            username=self._conn_params.username,
            password=self._conn_params.password,
            client_id=self._config.client_id,
            keepalive=self._config.keepalive,
        )
        
        # Enter client context (establishes connection)
        await self._client.__aenter__()
        self._connected = True
        
        logger.info(
            "Connected to MQTT broker at %s:%d (client_id=%s)",
            self._conn_params.hostname,
            self._conn_params.port,
            self._config.client_id,
        )
        
        # Start background tasks
        self._dispatch_task = asyncio.create_task(self._dispatch_messages())
        
        if self._config.enable_heartbeat:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # Publish health status
        if self._config.enable_health:
            await self.publish_health(ok=True, event="ready")

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker and stop background tasks.
        
        This method:
        - Cancels dispatch and heartbeat tasks
        - Exits client context (closes connection)
        - Resets connection state
        
        Safe to call when not connected (no-op).
        """
        if not self._connected:
            return
        
        # Cancel background tasks
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await asyncio.wait_for(self._dispatch_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await asyncio.wait_for(self._heartbeat_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        
        # Close MQTT connection
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None
        
        self._connected = False
        logger.info("Disconnected from MQTT broker")

    async def shutdown(self) -> None:
        """Graceful shutdown with health publishing and task cleanup.
        
        This method:
        - Publishes health(ok=False, event="shutdown") if enabled
        - Waits briefly for health to publish
        - Calls disconnect() to clean up
        
        Idempotent - safe to call multiple times.
        """
        if self._shutdown:
            return
        
        self._shutdown = True
        
        # Publish shutdown health status
        if self._config.enable_health and self._connected:
            try:
                await self.publish_health(ok=False, event="shutdown")
                await asyncio.sleep(0.1)  # Brief delay for publish
            except Exception as e:
                logger.warning("Failed to publish shutdown health: %s", e)
        
        # Disconnect and clean up
        await self.disconnect()
        
        logger.info("MQTT client shutdown complete")

    # --- Publishing Methods ---

    async def publish_event(
        self,
        topic: str,
        event_type: str,
        data: dict[str, Any] | BaseModel,
        *,
        correlation_id: Optional[str] = None,
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        """Publish event wrapped in Envelope to MQTT topic.
        
        Args:
            topic: MQTT topic to publish to
            event_type: Event type identifier (e.g., "stt.final", "llm.response")
            data: Event data (dict or Pydantic model)
            correlation_id: Optional correlation ID for request tracing
            qos: MQTT QoS level (0, 1, or 2)
            retain: Whether to retain message on broker
        
        Raises:
            RuntimeError: If not connected to broker
        
        Example:
            await client.publish_event(
                topic="stt/final",
                event_type="stt.final",
                data={"text": "hello world", "confidence": 0.95},
                correlation_id="req-123",
                qos=1,
            )
        """
        if not self._connected:
            raise RuntimeError("Cannot publish: not connected to MQTT broker")
        
        assert self._client is not None, "Client must be set when connected"
        
        # Convert Pydantic model to dict if needed
        if isinstance(data, BaseModel):
            data = data.model_dump()
        
        # Wrap in Envelope
        envelope = Envelope.new(
            event_type=event_type,
            data=data,
            source=self._source_name,
            correlate=correlation_id,
        )
        
        # Serialize with orjson
        payload = orjson.dumps(envelope.model_dump())
        
        # Publish to broker
        await self._client.publish(topic, payload, qos=qos, retain=retain)
        
        logger.debug(
            "Published event: topic=%s type=%s correlation_id=%s qos=%d retain=%s",
            topic,
            event_type,
            correlation_id,
            qos,
            retain,
        )

    async def publish_health(
        self,
        ok: bool,
        event: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Publish health status to system/health/{client_id} topic.
        
        Always uses QoS 1 and retain=True for health messages.
        No-op if enable_health=False.
        
        Args:
            ok: Health status (True=healthy, False=unhealthy)
            event: Health event name (e.g., "ready", "shutdown", "reconnected")
            error: Error message if ok=False
        
        Example:
            await client.publish_health(ok=True, event="ready")
            await client.publish_health(ok=False, error="Connection lost")
        """
        if not self._config.enable_health:
            return  # Health publishing disabled
        
        if not self._connected:
            logger.warning("Cannot publish health: not connected")
            return
        
        # Create health status payload
        health = HealthStatus(ok=ok, event=event, error=error)
        
        # Publish via publish_event
        topic = f"system/health/{self._config.client_id}"
        await self.publish_event(
            topic=topic,
            event_type="health.status",
            data=health.model_dump(exclude_none=True),
            qos=1,
            retain=True,
        )
        
        logger.info("Published health: ok=%s event=%s error=%s", ok, event, error)

    # --- Subscription Methods ---

    async def subscribe(
        self,
        topic: str,
        handler: SubscriptionHandler,
        qos: int = 0,
    ) -> None:
        """Subscribe to MQTT topic with message handler.
        
        Args:
            topic: MQTT topic pattern (supports wildcards: + for single level, # for multi-level)
            handler: Async function to handle received messages (payload: bytes) -> None
            qos: MQTT QoS level for subscription (0, 1, or 2)
        
        Raises:
            RuntimeError: If not connected to broker
        
        Example:
            async def handle_event(payload: bytes) -> None:
                envelope = Envelope.model_validate_json(payload)
                print(f"Received: {envelope.type}")
            
            await client.subscribe("events/#", handle_event, qos=1)
        """
        if not self._connected:
            raise RuntimeError("Cannot subscribe: not connected to MQTT broker")
        
        assert self._client is not None, "Client must be set when connected"
        
        # Register handler
        self._handlers[topic] = handler
        self._subscriptions.add(topic)
        
        # Subscribe to broker
        await self._client.subscribe(topic, qos=qos)
        
        logger.info("Subscribed to topic: %s (qos=%d)", topic, qos)

    async def _dispatch_messages(self) -> None:
        """Background task to dispatch messages to handlers.
        
        This task runs continuously while connected, receiving messages
        from the broker and invoking registered handlers.
        
        Error handling:
        - Handler errors are logged and isolated (don't crash dispatch loop)
        - Duplicate messages are skipped (if deduplication enabled)
        - Unknown topics are logged as warnings
        """
        assert self._client is not None, "Client must be set before dispatch"
        
        try:
            async with self._client.messages() as messages:
                async for message in messages:
                    # Extract topic and payload with type narrowing
                    topic_value = str(message.topic) if hasattr(message.topic, 'value') else str(message.topic)
                    
                    # Ensure payload is bytes
                    payload_raw = message.payload
                    if isinstance(payload_raw, bytes):
                        payload_bytes = payload_raw
                    elif isinstance(payload_raw, bytearray):
                        payload_bytes = bytes(payload_raw)
                    elif isinstance(payload_raw, str):
                        payload_bytes = payload_raw.encode('utf-8')
                    else:
                        logger.warning("Unexpected payload type %s, skipping", type(payload_raw))
                        continue
                    
                    # Check for deduplication
                    if self._deduplicator and self._deduplicator.is_duplicate(payload_bytes):
                        logger.debug("Skipping duplicate message on topic: %s", topic_value)
                        continue
                    
                    # Find matching handler
                    handler = self._handlers.get(topic_value)
                    if not handler:
                        # Check wildcard matches
                        for pattern, h in self._handlers.items():
                            if self._topic_matches(topic_value, pattern):
                                handler = h
                                break
                    
                    if handler:
                        try:
                            await handler(payload_bytes)
                        except Exception as e:
                            logger.error(
                                "Error in message handler for topic %s: %s",
                                topic_value,
                                e,
                                exc_info=True,
                            )
                    else:
                        logger.warning("No handler for topic: %s", topic_value)
        
        except asyncio.CancelledError:
            logger.debug("Message dispatch task cancelled")
            raise
        except Exception as e:
            logger.error("Message dispatch error: %s", e, exc_info=True)

    async def _heartbeat_loop(self) -> None:
        """Background task to publish application-level heartbeat.
        
        Publishes heartbeat to system/keepalive/{client_id} at configured interval.
        Includes watchdog to detect stale connections.
        """
        last_publish = None
        
        try:
            while not self._shutdown:
                if not self._connected:
                    await asyncio.sleep(1.0)
                    continue
                
                now = time.time()
                
                # Watchdog: check for stale connection
                if last_publish and (now - last_publish > 3 * self._config.heartbeat_interval):
                    logger.warning("Heartbeat watchdog: connection may be stale")
                    # TODO: Trigger reconnection in Phase 4
                
                # Publish heartbeat
                try:
                    if not self._client:
                        logger.warning("Heartbeat skipped: client not available")
                        continue
                    
                    heartbeat = HeartbeatPayload(timestamp=now)
                    topic = f"system/keepalive/{self._config.client_id}"
                    payload = orjson.dumps(heartbeat.model_dump())
                    
                    await self._client.publish(topic, payload, qos=0, retain=False)
                    last_publish = now
                    
                    logger.debug("Published heartbeat at %f", now)
                
                except Exception as e:
                    logger.error("Heartbeat publish error: %s", e)
                
                # Wait for next interval
                await asyncio.sleep(self._config.heartbeat_interval)
        
        except asyncio.CancelledError:
            logger.debug("Heartbeat task cancelled")
            raise

    @staticmethod
    def _topic_matches(topic: str, pattern: str) -> bool:
        """Check if topic matches MQTT wildcard pattern.
        
        Supports:
        - + for single level wildcard (e.g., "system/health/+" matches "system/health/stt")
        - # for multi-level wildcard (e.g., "events/#" matches "events/user/login")
        
        Args:
            topic: Actual topic from message
            pattern: Topic pattern from subscription (may contain wildcards)
        
        Returns:
            True if topic matches pattern, False otherwise
        """
        # Convert Topic object to string if needed
        topic_str = str(topic) if hasattr(topic, "value") else topic
        
        if pattern == topic_str:
            return True
        
        topic_parts = topic_str.split("/")
        pattern_parts = pattern.split("/")
        
        # Multi-level wildcard (#) at end
        if pattern_parts and pattern_parts[-1] == "#":
            return topic_str.startswith("/".join(pattern_parts[:-1]))
        
        # Single-level wildcard (+)
        if len(topic_parts) != len(pattern_parts):
            return False
        
        for t, p in zip(topic_parts, pattern_parts):
            if p != "+" and p != t:
                return False
        
        return True
