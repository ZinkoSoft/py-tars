from __future__ import annotations

"""Async MQTT client wrapper for resilient publish/subscribe.

Behavior unchanged; adds typing, small docstrings, and an explicit __all__.
"""

import asyncio
import time
import logging
from urllib.parse import urlparse
from typing import Callable, Awaitable, Optional, Dict

import asyncio_mqtt as mqtt
import orjson

logger = logging.getLogger("stt-worker.mqtt")

__all__ = ["MQTTClientWrapper"]


class MQTTClientWrapper:
    """Minimal wrapper around asyncio-mqtt with auto-reconnect and dispatch loop."""

    def __init__(self, mqtt_url: str, client_id: str = "tars-stt"):
        self.mqtt_url = mqtt_url
        self.client_id = client_id
        self.client: Optional[mqtt.Client] = None
        self._handlers: Dict[str, Callable[[bytes], Awaitable[None]]] = {}
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._topics: set[str] = set()
        self._lock = asyncio.Lock()
        # App-level keepalive heartbeat
        self._keepalive_task: Optional[asyncio.Task] = None
        # Send a lightweight app heartbeat frequently to keep the connection active
        self._keepalive_interval = 5.0  # seconds
        self._last_hb = 0.0

    def parse(self) -> tuple[str, int, Optional[str], Optional[str]]:
        u = urlparse(self.mqtt_url)
        return u.hostname or "127.0.0.1", u.port or 1883, u.username, u.password

    async def connect(self) -> None:
        """Connect to the broker and resume prior subscriptions."""
        host, port, username, password = self.parse()
        logger.info("Connecting to MQTT %s:%s", host, port)
        # Use a short MQTT keepalive so broker pings occur frequently
        self.client = mqtt.Client(
            hostname=host,
            port=port,
            username=username,
            password=password,
            client_id=self.client_id,
            keepalive=15,
        )
        await self.client.__aenter__()
        logger.info("Connected to MQTT")
        # Re-subscribe to registered topics on (re)connect
        for t in list(self._topics):
            try:
                await self.client.subscribe(t)
                logger.info("Subscribed to %s", t)
            except Exception as e:
                logger.error("Subscribe failed for %s: %s", t, e)
        self._ensure_dispatcher()
        self._ensure_keepalive()

    async def disconnect(self) -> None:
        if self.client:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception:
                pass
            self.client = None
        # Stop heartbeat
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
        self._keepalive_task = None

    async def reconnect(self) -> None:
        async with self._lock:
            await self.disconnect()
            await self.connect()

    async def safe_publish(
        self,
        topic: str,
        obj: dict,
        retries: int = 3,
        retain: bool = False,
    ) -> None:
        if not self.client:
            return
        data = orjson.dumps(obj)
        for attempt in range(1, retries + 1):
            try:
                await self.client.publish(topic, data, retain=retain)
                return
            except Exception as e:
                logger.warning("Publish attempt %s to '%s' failed: %s", attempt, topic, e)
                if attempt == retries:
                    logger.error("Dropping message after %s attempts topic=%s", retries, topic)
                    return
                try:
                    await self.reconnect()
                except Exception as re:
                    logger.error("Reconnect failed: %s", re)
                await asyncio.sleep(0.5 * attempt)

    async def subscribe_stream(
        self,
        topic: str,
        handler: Callable[[bytes], Awaitable[None]],
    ) -> None:
        # Register handler and ensure we're subscribed and dispatching
        self._handlers[topic] = handler
        self._topics.add(topic)
        if self.client:
            try:
                await self.client.subscribe(topic)
                logger.info("Subscribed to %s", topic)
            except Exception as e:
                logger.error("Subscribe failed for %s: %s", topic, e)
        self._ensure_dispatcher()

    def _ensure_dispatcher(self) -> None:
        if self._dispatcher_task and not self._dispatcher_task.done():
            return
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())

    def _ensure_keepalive(self) -> None:
        if self._keepalive_task and not self._keepalive_task.done():
            return
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def _keepalive_loop(self) -> None:
        """Application-level heartbeat publish to keep the connection active and observable."""
        topic = f"system/keepalive/{self.client_id}"
        while True:
            try:
                # Publish first, then sleep so we send an immediate heartbeat on startup
                if self.client:
                    # Watchdog: if we've failed to publish heartbeats for too long, force reconnect
                    now = time.time()
                    if self._last_hb and (now - self._last_hb) > (self._keepalive_interval * 3):
                        logger.debug("Heartbeat watchdog triggering reconnect")
                        try:
                            await self.reconnect()
                        except Exception as re:
                            logger.debug("Watchdog reconnect failed: %s", re)
                    payload = orjson.dumps({"ok": True, "event": "hb", "ts": now})
                    try:
                        await asyncio.wait_for(
                            self.client.publish(topic, payload, retain=False),
                            timeout=2.0,
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Heartbeat publish timeout; forcing reconnect")
                        try:
                            await self.reconnect()
                        except Exception as re:
                            logger.debug("Reconnect after heartbeat timeout failed: %s", re)
                        # Skip sleep to attempt immediate next heartbeat on reconnect
                        continue
                    self._last_hb = now
                    logger.debug("stt heartbeat sent every %ss", self._keepalive_interval)
                await asyncio.sleep(self._keepalive_interval)
                if not self.client:
                    continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Heartbeat publish failed: %s", e)
                # Try to reconnect if we fell behind on heartbeats
                try:
                    await self.reconnect()
                except Exception as re:
                    logger.debug("Heartbeat reconnect failed: %s", re)
                continue

    async def _dispatch_loop(self) -> None:
        backoff = 0.5
        while True:
            if not self.client:
                try:
                    await self.reconnect()
                except Exception as e:
                    logger.error("Reconnect in dispatch loop failed: %s", e)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 5)
                    continue
            try:
                async with self.client.messages() as messages:
                    backoff = 0.5
                    async for msg in messages:
                        try:
                            handler = self._handlers.get(msg.topic)
                            if handler:
                                await handler(msg.payload)
                        except Exception as e:
                            logger.error("Handler error for topic %s: %s", msg.topic, e)
            except Exception as e:
                logger.error("Dispatch loop error: %s", e)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 5)
                continue
