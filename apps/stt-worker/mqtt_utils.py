from __future__ import annotations

"""Async MQTT client wrapper for resilient publish/subscribe.

Behavior unchanged; adds typing, small docstrings, and an explicit __all__.
"""

import asyncio
import time
import logging
from urllib.parse import urlparse
import asyncio_mqtt as mqtt
import orjson
from typing import Callable, Awaitable, Optional, Dict

logger = logging.getLogger("stt-worker.mqtt")

__all__ = ["MQTTClientWrapper"]

class MQTTClientWrapper:
    """Minimal wrapper around asyncio-mqtt with auto-reconnect and dispatch loop."""
    def __init__(self, mqtt_url: str, client_id: str = 'tars-stt'):
        self.mqtt_url = mqtt_url
        self.client_id = client_id
        self.client: Optional[mqtt.Client] = None
        self._handlers: Dict[str, Callable[[bytes], Awaitable[None]]] = {}
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._topics: set[str] = set()
        self._lock = asyncio.Lock()
        # App-level keepalive heartbeat
        self._keepalive_task: Optional[asyncio.Task] = None
        self._keepalive_interval: float = 30.0  # seconds

    def parse(self):
        u = urlparse(self.mqtt_url)
        return u.hostname or '127.0.0.1', u.port or 1883, u.username, u.password

    async def connect(self):
        """Connect to the broker and resume prior subscriptions."""
        host, port, username, password = self.parse()
        logger.info(f"Connecting to MQTT {host}:{port}")
        # Use a moderate MQTT keepalive so broker pings occur frequently
        self.client = mqtt.Client(
            hostname=host,
            port=port,
            username=username,
            password=password,
            client_id=self.client_id,
            keepalive=60,
        )
        await self.client.__aenter__()
        logger.info("Connected to MQTT")
        # Re-subscribe to registered topics on (re)connect
        for t in list(self._topics):
            try:
                await self.client.subscribe(t)
                logger.info(f"Subscribed to {t}")
            except Exception as e:
                logger.error(f"Subscribe failed for {t}: {e}")
        self._ensure_dispatcher()
        self._ensure_keepalive()

    async def disconnect(self):
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

    async def reconnect(self):
        async with self._lock:
            await self.disconnect()
            await self.connect()

    async def safe_publish(self, topic: str, obj: dict, retries: int = 3, retain: bool = False):
        if not self.client:
            return
        data = orjson.dumps(obj)
        for attempt in range(1, retries + 1):
            try:
                await self.client.publish(topic, data, retain=retain)
                return
            except Exception as e:
                logger.warning(f"Publish attempt {attempt} to '{topic}' failed: {e}")
                if attempt == retries:
                    logger.error(f"Dropping message after {retries} attempts topic={topic}")
                    return
                try:
                    await self.reconnect()
                except Exception as re:
                    logger.error(f"Reconnect failed: {re}")
                await asyncio.sleep(0.5 * attempt)

    async def subscribe_stream(self, topic: str, handler: Callable[[bytes], Awaitable[None]]):
        # Register handler and ensure we're subscribed and dispatching
        self._handlers[topic] = handler
        self._topics.add(topic)
        if self.client:
            try:
                await self.client.subscribe(topic)
                logger.info(f"Subscribed to {topic}")
            except Exception as e:
                logger.error(f"Subscribe failed for {topic}: {e}")
        self._ensure_dispatcher()
        return None

    def _ensure_dispatcher(self):
        if self._dispatcher_task and not self._dispatcher_task.done():
            return
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())

    def _ensure_keepalive(self):
        if self._keepalive_task and not self._keepalive_task.done():
            return
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def _keepalive_loop(self):
        """Application-level heartbeat publish to keep the connection active and observable."""
        topic = f"system/keepalive/{self.client_id}"
        while True:
            try:
                await asyncio.sleep(self._keepalive_interval)
                if not self.client:
                    continue
                payload = orjson.dumps({"ok": True, "event": "hb", "ts": time.time()})
                await self.client.publish(topic, payload, retain=False)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Heartbeat publish failed: {e}")
                # Trigger reconnect on next dispatch iteration
                continue

    async def _dispatch_loop(self):
        backoff = 0.5
        while True:
            if not self.client:
                try:
                    await self.reconnect()
                except Exception as e:
                    logger.error(f"Reconnect in dispatch loop failed: {e}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 5)
                    continue
            try:
                async with self.client.messages() as messages:
                    backoff = 0.5
                    async for msg in messages:
                        try:
                            h = self._handlers.get(msg.topic)
                            if h:
                                await h(msg.payload)
                        except Exception as e:
                            logger.error(f"Handler error for topic {msg.topic}: {e}")
            except Exception as e:
                logger.error(f"Dispatch loop error: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 5)
                continue
