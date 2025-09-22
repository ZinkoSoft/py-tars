import asyncio
import logging
from urllib.parse import urlparse
import asyncio_mqtt as mqtt
import orjson
from typing import Callable, Awaitable, Optional, Dict

logger = logging.getLogger("stt-worker.mqtt")

class MQTTClientWrapper:
    def __init__(self, mqtt_url: str, client_id: str = 'tars-stt'):
        self.mqtt_url = mqtt_url
        self.client_id = client_id
        self.client: Optional[mqtt.Client] = None
        self._handlers: Dict[str, Callable[[bytes], Awaitable[None]]] = {}
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._topics: set[str] = set()
        self._lock = asyncio.Lock()

    def parse(self):
        u = urlparse(self.mqtt_url)
        return u.hostname or '127.0.0.1', u.port or 1883, u.username, u.password

    async def connect(self):
        host, port, username, password = self.parse()
        logger.info(f"Connecting to MQTT {host}:{port}")
        # Use a slightly longer keepalive to avoid broker idle disconnects
        self.client = mqtt.Client(hostname=host, port=port, username=username, password=password, client_id=self.client_id, keepalive=120)
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

    async def disconnect(self):
        if self.client:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception:
                pass
            self.client = None

    async def reconnect(self):
        async with self._lock:
            await self.disconnect()
            await self.connect()

    async def safe_publish(self, topic: str, obj: dict, retries: int = 3):
        if not self.client:
            return
        data = orjson.dumps(obj)
        for attempt in range(1, retries + 1):
            try:
                await self.client.publish(topic, data)
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
